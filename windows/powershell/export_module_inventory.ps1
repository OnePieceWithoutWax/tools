<#
.SYNOPSIS
    Snapshots installed modules and the current profile to a JSON file.

.DESCRIPTION
    Writes a JSON file recording the installed PowerShell Gallery modules
    (name, version, repository) and the content of $PROFILE, so a machine's
    PowerShell setup can be reproduced elsewhere or compared over time.

.PARAMETER OutputDirectory
    Folder to write the inventory file into. Defaults to the current
    working directory if not specified.

.EXAMPLE
    PS> .\export_module_inventory.ps1
    Writes powershell-inventory_<timestamp>.json to the current directory.

.EXAMPLE
    PS> .\export_module_inventory.ps1 -OutputDirectory C:\Backups
    Writes the inventory file to C:\Backups instead.
#>

[CmdletBinding()]
param (
    [string]$OutputDirectory = (Get-Location).Path
)

if (-not (Test-Path -LiteralPath $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
}

$profilePath = $PROFILE.CurrentUserAllHosts
$timestamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$outFile = Join-Path $OutputDirectory "powershell-inventory_$timestamp.json"

$inventory = [ordered]@{
    GeneratedAt    = (Get-Date).ToString('o')
    PSVersion      = $PSVersionTable.PSVersion.ToString()
    Modules        = Get-InstalledModule | Select-Object Name, Version, Repository | Sort-Object Name
    ProfilePath    = $profilePath
    ProfileContent = if (Test-Path -LiteralPath $profilePath) { Get-Content -LiteralPath $profilePath -Raw } else { $null }
}

$inventory | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $outFile -Encoding utf8

Write-Host "Inventory written to $outFile"
