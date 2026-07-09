# list-kernel-ipykernel-versions.ps1
# Lists every registered Jupyter kernelspec and, for each one, the ipykernel
# version installed in the Python environment the kernel points at. Useful for
# spotting kernels backed by stale or missing ipykernel installs.
# (Migrated from "tools other\powershell\kernelspec.ps"; fixed kernelspec
# enumeration - ConvertFrom-Json returns a PSCustomObject, which has no .Keys -
# and the interpreter lookup, which guessed a python.exe path that never
# existed. spec.argv[0] is the interpreter the kernel actually launches.)

$j = jupyter kernelspec list --json | ConvertFrom-Json
foreach ($k in $j.kernelspecs.PSObject.Properties) {
    $python = $k.Value.spec.argv[0]
    Write-Host "Kernel: $($k.Name)"
    if (Test-Path $python) {
        & $python -m pip show ipykernel | Select-String Version
    } else {
        Write-Host "  interpreter not found: $python"
    }
    Write-Host ""
}
