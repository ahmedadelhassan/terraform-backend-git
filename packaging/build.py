#!/usr/bin/env python3
"""Build the reviewed upstream source with pinned manifests; never update dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    pin = json.loads((HERE / "build/pin.json").read_text())
    for directory in ["home", "tmp", "artifacts"]:
        (work / directory).mkdir()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(work / "home"),
           "TMPDIR": str(work / "tmp"), "LANG": "C.UTF-8",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GOPATH": str(work / "gopath"), "GOCACHE": str(work / "cache"),
           "GOMAXPROCS": "2", "GOMEMLIMIT": "900MiB", "GOTOOLCHAIN": "local"}

    def run(*command, cwd=work):
        subprocess.run(command, cwd=cwd, env=env, check=True)

    compiler = pin["compiler"]
    archive = work / compiler["filename"]
    # Public, checksum-pinned compiler; no controller environment is inherited.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("https://go.dev/dl/" + archive.name, timeout=60) as response:
        with archive.open("wb") as output:
            shutil.copyfileobj(response, output)
    if digest(archive) != compiler["sha256"]:
        raise RuntimeError("Compiler checksum mismatch")
    with tarfile.open(archive) as source:
        source.extractall(work, filter="data")
    env["PATH"] = str(work / "go/bin") + ":/usr/bin:/bin"
    source = work / "source"
    run("git", "clone", "--quiet", "--no-checkout", pin["upstream_repository"], str(source))
    run("git", "checkout", "--quiet", pin["upstream_commit"], cwd=source)
    expected = json.loads((HERE / "build/source-hashes.json").read_text())
    actual = {str(path.relative_to(source)): digest(path) for path in source.rglob("*.go")
              if ".git" not in path.parts}
    if actual != expected:
        raise RuntimeError("Upstream Go source differs from reviewed files")
    for name in ["go.mod", "go.sum"]:
        shutil.copyfile(HERE.parent / name, source / name)
    run("go", "mod", "download", "-modcacherw", cwd=source)
    run("go", "mod", "verify", cwd=source)
    artifact = work / "artifacts" / ("terraform-backend-git-" + pin["platform"])
    run("go", "build", "-mod=readonly", "-modcacherw", "-trimpath", "-o", str(artifact), ".", cwd=source)
    if digest(artifact) != pin["binary_sha256"]:
        raise RuntimeError("Build is not byte-identical to the validated candidate; do not promote")
    run("go", "test", "-mod=readonly", "-modcacherw", "./...", cwd=source)
    if any(digest(source / name) != digest(HERE.parent / name) for name in ["go.mod", "go.sum"]):
        raise RuntimeError("Build changed dependency manifests")
    shutil.copyfile(source / "LICENSE", work / "artifacts/LICENSE")
    shutil.copyfile(HERE / "build/pin.json", work / "artifacts/pin.json")
    (work / "artifacts/SHA256SUMS").write_text(digest(artifact) + "  " + artifact.name + "\n")
    for directory in ["go", "gopath", "cache", "tmp"]:
        shutil.rmtree(work / directory, ignore_errors=True)
    archive.unlink()
    print("PASS: pinned build reproduced byte for byte; upstream tests passed.")
    print("Candidate artifacts: " + str(work / "artifacts"))


if __name__ == "__main__":
    main()
