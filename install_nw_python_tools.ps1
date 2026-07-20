<#
.SYNOPSIS
    Installs, or reinstalls, every Python tool in this workspace globally via uv.

.DESCRIPTION
    Reads the workspace member list from the root pyproject.toml and runs
    `uv tool install --force --reinstall` against each member's directory, so
    globally installed tools always reflect the current source rather than
    whatever was installed last. --reinstall is required because these tools
    keep a static version (e.g. 0.1.0) while their source changes; without it
    uv serves a stale wheel from its build cache even under --force. Safe to
    re-run any time after pulling changes.

.EXAMPLE
    PS> .\install_python_tools.ps1
    Reinstalls every workspace member (currently git-tools, pdf-scrub).

.NOTES
    Tool paths are resolved relative to this script's own location, so it
    can be run from any working directory.
#>

[CmdletBinding()]
param ()

$repoRoot = $PSScriptRoot
$pyprojectPath = Join-Path $repoRoot 'pyproject.toml'
$pyproject = Get-Content -LiteralPath $pyprojectPath -Raw

$match = [regex]::Match($pyproject, 'members\s*=\s*\[(?<list>[^\]]*)\]')
if (-not $match.Success) {
    throw "Could not find [tool.uv.workspace] members in $pyprojectPath"
}

$members = $match.Groups['list'].Value -split ',' |
    ForEach-Object { $_.Trim().Trim('"''') } |
    Where-Object { $_ }

if (-not $members) {
    throw "No workspace members found in $pyprojectPath"
}

$failed = [System.Collections.Generic.List[string]]::new()
foreach ($member in $members) {
    $toolPath = Join-Path $repoRoot $member
    Write-Host "Installing $member ..."
    uv tool install --force --reinstall $toolPath
    if ($LASTEXITCODE -ne 0) {
        $failed.Add($member)
    }
}

if ($failed.Count -gt 0) {
    Write-Error "Failed to install: $($failed -join ', ')"
    exit 1
}

Write-Host "Installed $($members.Count) tool(s): $($members -join ', ')"
Pause