<#
.SYNOPSIS
    Updates all installed PowerShell Gallery modules to their latest version.

.DESCRIPTION
    Wraps Update-Module, which upgrades every module originally installed
    with Install-Module. Modules that ship with PowerShell itself, or that
    were installed some other way, are left untouched.

.EXAMPLE
    PS> .\update_modules.ps1
    Updates every PowerShell Gallery module already installed.

.NOTES
    Modules installed to the AllUsers scope can only be updated from an
    elevated session; run via update_all.bat, which handles elevation,
    rather than a non-admin prompt.
#>

[CmdletBinding()]
param ()

Update-Module -Force
