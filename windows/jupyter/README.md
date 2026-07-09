# jupyter

- `list-kernel-ipykernel-versions.ps1` — lists every registered Jupyter kernelspec and the ipykernel version installed in the Python environment each kernel points at. Useful for spotting kernels backed by stale or missing ipykernel installs.

Migrated from `tools other\powershell\kernelspec.ps` — renamed because `.ps` is not a valid PowerShell extension. Two bugs in the original were fixed after migration: kernelspec enumeration (the JSON parses to a PSCustomObject, which has no `.Keys`) and the interpreter lookup (now uses the kernelspec's `spec.argv[0]` instead of guessing a path relative to `resource_dir`).
