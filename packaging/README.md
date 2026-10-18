# Reviewed dependency-refresh build

Build the audited upstream commit with the committed go.mod/go.sum refresh:

```sh
python3 packaging/build.py --work-dir /absolute/new/build-directory
```

The recipe verifies the pinned official compiler, all upstream Go source hashes,
module integrity, upstream tests and exact binary checksum. It changes no upstream
Go implementation. Successful builds discard compiler/module/build caches and
produce the binary, pin manifest, LICENSE and SHA256SUMS under artifacts/.
The upstream source commit is intentionally fixed even if fork master advances.

After review, publish these files as a versioned fork release. Deployment consumers
pin its binary checksum and do not rebuild or use latest. No release is published
yet. Project state, tokens, encryption identities and controller/vault adapters
never belong in this public fork. Use Standalone Terraform HTTP Backend Mode.
