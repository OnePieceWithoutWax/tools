<#
.SYNOPSIS
    Updates PowerShell (pwsh) to the latest release using winget.

.DESCRIPTION
    Thin wrapper around `winget upgrade` for the Microsoft.PowerShell package.
    This targets PowerShell 7+ (pwsh.exe) — the version installed from the
    Microsoft Store / MSI / winget. It does not touch Windows PowerShell 5.1,
    which ships with Windows and is updated via Windows Update instead.

    Installing/upgrading writes to Program Files, so this requires an elevated
    session. Run it via update_powershell.bat, which handles elevation
    automatically, rather than calling this script directly from a
    non-admin prompt.

.EXAMPLE
    PS> .\update_powershell.ps1
    Checks winget for a newer Microsoft.PowerShell release and installs it
    if one is available.

.NOTES
    --accept-package-agreements and --accept-source-agreements are required
    here because this typically runs from a freshly-elevated, non-interactive
    window (launched via Start-Process -Verb RunAs) — without them, winget
    would stall waiting for a prompt no one can see.
#>

[CmdletBinding()]
param ()

winget upgrade --id Microsoft.PowerShell --exact --source winget `
    --accept-package-agreements --accept-source-agreements

exit $LASTEXITCODE
