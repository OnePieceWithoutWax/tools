# jupyter

- `list-kernel-ipykernel-versions.ps1` — lists every registered Jupyter kernelspec and the ipykernel version installed in the Python environment each kernel points at. Useful for spotting kernels backed by stale or missing ipykernel installs.

Migrated from `tools other\powershell\kernelspec.ps` — renamed because `.ps` is not a valid PowerShell extension; the logic is unchanged.
