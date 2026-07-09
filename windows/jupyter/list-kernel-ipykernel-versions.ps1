# list-kernel-ipykernel-versions.ps1
# Lists every registered Jupyter kernelspec and, for each one, the ipykernel
# version installed in the Python environment the kernel points at. Useful for
# spotting kernels backed by stale or missing ipykernel installs.
# (Migrated from "tools other\powershell\kernelspec.ps" - logic unchanged.)

$j = jupyter kernelspec list --json | ConvertFrom-Json
foreach ($k in $j.kernelspecs.Keys) {
    $path = $j.kernelspecs[$k].resource_dir
    $envdir = Split-Path (Split-Path $path)
    Write-Host "Kernel: $k"
    & "$envdir\python.exe" -m pip show ipykernel | Select-String Version
    Write-Host ""
}
