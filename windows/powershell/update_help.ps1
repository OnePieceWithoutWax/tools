<#
.SYNOPSIS
    Updates offline help files for installed PowerShell modules.

.DESCRIPTION
    Wraps Update-Help so cmdlet help (Get-Help, Get-Command -Syntax) stays
    current. Not every module ships updatable help or a help source that's
    reachable, so per-module failures are expected here and are suppressed
    rather than treated as a script failure.

.EXAMPLE
    PS> .\update_help.ps1
    Downloads and installs the latest help files for every module that
    supports it.

.NOTES
    Help for built-in modules can only be updated from an elevated session;
    run via update_all.bat, which handles elevation, rather than a
    non-admin prompt.
#>

[CmdletBinding()]
param ()

Update-Help -Force -ErrorAction SilentlyContinue
