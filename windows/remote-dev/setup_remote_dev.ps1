# setup_remote_dev.ps1
# One-shot configuration of the remote dev stack from guide-ssh-tailscale-tmux.md
# Assumes all dependencies are already installed:
#   OpenSSH Server, WSL2 (Ubuntu), Tailscale, mosh (in WSL), tmux (in WSL)
# Run as Administrator for full access.

$pass = "[  OK  ]"
$fail = "[ FAIL ]"
$warn = "[ WARN ]"
$info = "[ INFO ]"
$sep  = "-" * 55

function Write-Pass($msg)   { Write-Host "$pass $msg" -ForegroundColor Green  }
function Write-Fail($msg)   { Write-Host "$fail $msg" -ForegroundColor Red    }
function Write-Warn($msg)   { Write-Host "$warn $msg" -ForegroundColor Yellow }
function Write-Info($msg)   { Write-Host "$info $msg" -ForegroundColor Cyan   }
function Write-Header($msg) {
    Write-Host ""
    Write-Host $sep -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host $sep -ForegroundColor Cyan
}

# Set-Service doesn't support AutomaticDelayedStart - must go via the registry.
# Sets the service to Automatic first, then flips the DelayedAutostart DWORD.
function Set-DelayedAutoStart {
    param([string]$ServiceName)
    Set-Service -Name $ServiceName -StartupType Automatic
    $regPath = "HKLM:\SYSTEM\CurrentControlSet\Services\$ServiceName"
    Set-ItemProperty -Path $regPath -Name "DelayedAutostart" -Value 1 -Type DWord
}

# -------------------------------------------------------
# Guard: must run as Administrator
# -------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Fail "This script must be run as Administrator. Please re-run via the .bat wrapper."
    exit 1
}

Write-Host ""
Write-Host "  Remote Dev Setup - SSH + Tailscale + tmux" -ForegroundColor Cyan
Write-Host "  Based on guide-ssh-tailscale-tmux.md" -ForegroundColor Cyan
Write-Host $sep -ForegroundColor Cyan

# -------------------------------------------------------
# Part 0 - WSL2 + Ubuntu
# -------------------------------------------------------
Write-Header "Part 0 - WSL2 + Ubuntu"

$wslExe = Get-Command wsl -ErrorAction SilentlyContinue
if (-not $wslExe) {
    Write-Warn "WSL is not installed - installing now..."
    Write-Info "This will install WSL2 with Ubuntu as the default distro"
    wsl --install
    Write-Pass "WSL install command issued"
    Write-Warn "A RESTART IS REQUIRED before WSL will be usable"
    Write-Warn "After rebooting, Ubuntu will finish setup on first launch (set a username/password)"
    Write-Warn "Then re-run this script to complete the remaining configuration"
    Write-Host ""
    Read-Host "Press Enter to exit - please restart your machine before continuing"
    exit 0
} else {
    Write-Pass "WSL is already installed"

    # Check a default distro is actually registered
    $wslList = (wsl --list --quiet 2>&1) -replace "`r", "" | Where-Object { $_ -ne "" }
    if ($wslList) {
        Write-Pass "Default distro: $($wslList | Select-Object -First 1)"
    } else {
        Write-Warn "WSL is installed but no distro found - run: wsl --install -d Ubuntu"
    }
}

# -------------------------------------------------------
# Part 1 - OpenSSH Server: service startup + firewall
# -------------------------------------------------------
Write-Header "Part 1 - OpenSSH Server"

$sshd = Get-Service -Name sshd -ErrorAction SilentlyContinue
if (-not $sshd) {
    Write-Fail "sshd service not found. Install OpenSSH Server via:"
    Write-Info "  Settings > System > Optional Features > Add a feature > OpenSSH Server"
    Write-Fail "Cannot continue without OpenSSH Server. Exiting."
    exit 1
}

# Set startup type to Automatic (Delayed Start)
Set-DelayedAutoStart -ServiceName sshd
Write-Pass "sshd startup type set to Automatic (Delayed Start)"

# Start the service if not already running
if ($sshd.Status -ne 'Running') {
    Start-Service sshd
    Write-Pass "sshd service started"
} else {
    Write-Pass "sshd service is already running"
}

# Firewall rule for SSH port 22
$existingSshRule = Get-NetFirewallRule -Name "sshd" -ErrorAction SilentlyContinue
if ($existingSshRule) {
    Write-Pass "SSH firewall rule already exists - skipping"
} else {
    New-NetFirewallRule -Name sshd `
        -DisplayName 'OpenSSH Server (sshd)' `
        -Enabled True `
        -Direction Inbound `
        -Protocol TCP `
        -Action Allow `
        -LocalPort 22 | Out-Null
    Write-Pass "Firewall rule created: OpenSSH Server (sshd) - TCP port 22 inbound"
}

# -------------------------------------------------------
# Part 2 - Mosh UDP firewall rule
# -------------------------------------------------------
Write-Header "Part 2 - Mosh UDP Firewall Rule"

$existingMoshRule = Get-NetFirewallRule -Name "mosh" -ErrorAction SilentlyContinue
if ($existingMoshRule) {
    Write-Pass "Mosh firewall rule already exists - skipping"
} else {
    New-NetFirewallRule -Name mosh `
        -DisplayName 'Mosh UDP' `
        -Enabled True `
        -Direction Inbound `
        -Protocol UDP `
        -Action Allow `
        -LocalPort 60000-61000 | Out-Null
    Write-Pass "Firewall rule created: Mosh UDP - UDP ports 60000-61000 inbound"
}

# -------------------------------------------------------
# Part 3 - Configure sshd_config
# -------------------------------------------------------
Write-Header "Part 3 - sshd_config"

$sshdConfig = "C:\ProgramData\ssh\sshd_config"

if (-not (Test-Path $sshdConfig)) {
    Write-Fail "sshd_config not found at $sshdConfig - cannot configure SSH"
} else {
    Write-Pass "sshd_config found"

    # Back up original before touching it
    $backupPath = "$sshdConfig.bak"
    if (-not (Test-Path $backupPath)) {
        Copy-Item $sshdConfig $backupPath
        Write-Pass "Backup created at $backupPath"
    } else {
        Write-Warn "Backup already exists at $backupPath - not overwriting"
    }

    $config = Get-Content $sshdConfig

    # Helper: set or add a config directive, handling commented-out lines
    function Set-SshdOption {
        param([string[]]$Content, [string]$Key, [string]$Value)

        $pattern      = "^\s*#?\s*$Key\s+"
        $activeLine   = "^\s*$Key\s+"
        $newLine      = "$Key $Value"

        $activeIndex    = ($Content | Select-String $activeLine).LineNumber - 1
        $commentedIndex = ($Content | Select-String $pattern | Where-Object {
            $_.Line -match "^\s*#"
        } | Select-Object -First 1).LineNumber - 1

        if ($activeIndex -ge 0) {
            if ($Content[$activeIndex] -eq $newLine) { return $Content }
            $Content[$activeIndex] = $newLine
        } elseif ($commentedIndex -ge 0) {
            $Content[$commentedIndex] = $newLine
        } else {
            $Content += $newLine
        }
        return $Content
    }

    # Apply all required settings
    # Leave PasswordAuthentication yes for now - guide says disable AFTER confirming key auth
    $config = Set-SshdOption $config "PubkeyAuthentication"   "yes"
    $config = Set-SshdOption $config "PasswordAuthentication" "yes"
    $config = Set-SshdOption $config "ClientAliveInterval"    "60"
    $config = Set-SshdOption $config "ClientAliveCountMax"    "3"
    $config = Set-SshdOption $config "LogLevel"               "VERBOSE"

    Set-Content -Path $sshdConfig -Value $config
    Write-Pass "sshd_config updated:"
    Write-Info "  PubkeyAuthentication   yes"
    Write-Info "  PasswordAuthentication yes  (disable AFTER confirming key auth works)"
    Write-Info "  ClientAliveInterval    60"
    Write-Info "  ClientAliveCountMax    3"
    Write-Info "  LogLevel               VERBOSE"

    # Enable the OpenSSH Operational event log
    try {
        $log = New-Object System.Diagnostics.Eventing.Reader.EventLogConfiguration 'OpenSSH/Operational'
        $log.IsEnabled = $true
        $log.SaveChanges()
        Write-Pass "OpenSSH/Operational event log enabled"
    } catch {
        Write-Warn "Could not enable OpenSSH/Operational log: $_"
    }

    # Restart sshd to apply changes
    Restart-Service sshd
    Write-Pass "sshd restarted to apply config changes"
}

# -------------------------------------------------------
# Part 4 & 5 - SSH Authorized Keys (admin-aware)
# -------------------------------------------------------
Write-Header "Part 4 & 5 - SSH Authorized Keys"

$userSshDir  = "$env:USERPROFILE\.ssh"
$userKeys    = "$userSshDir\authorized_keys"
$adminKeys   = "C:\ProgramData\ssh\administrators_authorized_keys"
$placeholder = "# Paste your iPhone public key below this line (ssh-ed25519 AAAA...)"
$keyStub     = "Paste_Key_Here"

# Determine if this account is an Administrator
$adminCheck = (net localgroup administrators 2>&1) | Where-Object { $_ -match [regex]::Escape($env:USERNAME) }
$isAdminAccount = [bool]$adminCheck

if ($isAdminAccount) {
    Write-Warn "Account '$env:USERNAME' is a local Administrator"
    Write-Info "OpenSSH ignores ~\.ssh\authorized_keys for admin accounts"
    Write-Info "Keys must live in: $adminKeys"

    # Create the admin key file with placeholder if it doesn't exist
    if (-not (Test-Path $adminKeys)) {
        Set-Content -Path $adminKeys -Value @($placeholder, $keyStub)
        Write-Pass "Created $adminKeys with placeholder"
    } else {
        $existingContent = Get-Content $adminKeys
        $realKeys = $existingContent | Where-Object { $_ -match '^ssh-' }
        if ($realKeys) {
            Write-Pass "administrators_authorized_keys already contains $(@($realKeys).Count) key(s) - not overwriting"
        } else {
            Write-Warn "administrators_authorized_keys exists but has no ssh- keys - leaving as-is"
        }
    }

    # Set strict permissions (OpenSSH rejects the file if permissions are wrong)
    icacls $adminKeys /inheritance:r /grant "NT AUTHORITY\SYSTEM:(F)" /grant "BUILTIN\Administrators:(F)" 2>&1 | Out-Null
    Write-Pass "Permissions locked: SYSTEM + Administrators only"

    # Open the directory in Explorer so the user can paste their key
    Write-Info "Opening C:\ProgramData\ssh\ in File Explorer..."
    Start-Process explorer.exe "C:\ProgramData\ssh"

} else {
    Write-Info "Account '$env:USERNAME' is a standard user"
    Write-Info "Key file location: $userKeys"

    New-Item -ItemType Directory -Force -Path $userSshDir | Out-Null

    if (-not (Test-Path $userKeys)) {
        Set-Content -Path $userKeys -Value @($placeholder, $keyStub)
        Write-Pass "Created $userKeys with placeholder"
    } else {
        $realKeys = Get-Content $userKeys | Where-Object { $_ -match '^ssh-' }
        if ($realKeys) {
            Write-Pass "authorized_keys already contains $(@($realKeys).Count) key(s) - not overwriting"
        } else {
            Write-Warn "authorized_keys exists but has no ssh- keys - leaving as-is"
        }
    }

    # Open the directory in Explorer
    Write-Info "Opening $userSshDir in File Explorer..."
    Start-Process explorer.exe $userSshDir
}

# -------------------------------------------------------
# Part 6 - Tailscale service startup type
# -------------------------------------------------------
Write-Header "Part 6 - Tailscale Service"

$tailscale = Get-Service -Name Tailscale -ErrorAction SilentlyContinue
if (-not $tailscale) {
    Write-Fail "Tailscale service not found - install from https://tailscale.com/download"
    Write-Warn "After install: re-run this script to configure the startup type"
} else {
    Set-DelayedAutoStart -ServiceName Tailscale
    Write-Pass "Tailscale startup type set to Automatic (Delayed Start)"

    if ($tailscale.Status -ne 'Running') {
        Start-Service Tailscale
        Write-Pass "Tailscale service started"
    } else {
        Write-Pass "Tailscale is already running"
    }

    # Show Tailscale IP if available
    $tsExe = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($tsExe) {
        $tsStatus = tailscale status 2>&1
        $myIp = ($tsStatus | Select-String -Pattern '100\.\d+\.\d+\.\d+' | Select-Object -First 1).Matches.Value
        if ($myIp) {
            Write-Pass "Tailscale IP: $myIp"
        } else {
            Write-Warn "Tailscale may not be authenticated yet - run 'tailscale up' if needed"
        }
    } else {
        Write-Warn "'tailscale' not on PATH - can't read status"
    }
}

# -------------------------------------------------------
# Part 7 - tmux config in WSL
# -------------------------------------------------------
Write-Header "Part 7 - tmux config in WSL"

$wslExe = Get-Command wsl -ErrorAction SilentlyContinue
if (-not $wslExe) {
    Write-Fail "WSL not found - install via: wsl --install"
} else {
    # Write ~/.tmux.conf via a Windows temp file to avoid heredoc escaping issues
    $tmuxConfLines = @(
        '# Mouse support - tap to switch panes on iPhone',
        'set -g mouse on',
        '',
        '# Large scrollback buffer',
        'set -g history-limit 50000',
        '',
        '# Renumber windows when one closes',
        'set -g renumber-windows on',
        '',
        "# Don't exit when last session closes - keeps things running",
        'set -g detach-on-destroy off',
        '',
        '# Pass window titles to Moshi (shows current tmux window in app)',
        'set -g set-titles on',
        'set -g set-titles-string "#I: #T"',
        '',
        '# Start window numbering at 1',
        'set -g base-index 1',
        'setw -g pane-base-index 1'
    )

    # Check if tmux.conf already exists
    $existsCheck = (wsl bash -c "test -f ~/.tmux.conf && echo found || echo missing" 2>&1) -replace "`r", ""

    if ($existsCheck -match "found") {
        Write-Warn "~/.tmux.conf already exists in WSL - not overwriting"
        Write-Info "To replace it, delete it inside WSL: rm ~/.tmux.conf"
    } else {
        # Write to Windows temp file, then copy into WSL via /mnt path
        $tmpFile = "$env:TEMP\tmux_conf_tmp"
        Set-Content -Path $tmpFile -Value $tmuxConfLines -Encoding UTF8
        $wslTmpPath = "/mnt/" + ($tmpFile -replace "\\", "/" -replace ":", "").ToLower()
        wsl bash -c "cp '$wslTmpPath' ~/.tmux.conf" 2>&1 | Out-Null

        $writeCheck = (wsl bash -c "test -f ~/.tmux.conf && echo found || echo missing" 2>&1) -replace "`r", ""
        if ($writeCheck -match "found") {
            Write-Pass "~/.tmux.conf written to WSL home directory"
        } else {
            Write-Fail "Failed to write ~/.tmux.conf - write it manually inside WSL"
        }
        Remove-Item $tmpFile -ErrorAction SilentlyContinue
    }
}

# -------------------------------------------------------
# Summary + next steps
# -------------------------------------------------------
Write-Host ""
Write-Host $sep -ForegroundColor Cyan
Write-Host "  Setup Complete - Next Steps" -ForegroundColor Cyan
Write-Host $sep -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. PASTE YOUR KEY" -ForegroundColor Yellow
if ($isAdminAccount) {
    Write-Host "     File Explorer opened to C:\ProgramData\ssh\"
    Write-Host "     Open administrators_authorized_keys in a text editor"
} else {
    Write-Host "     File Explorer opened to $userSshDir"
    Write-Host "     Open authorized_keys in a text editor"
}
Write-Host "     Replace 'Paste_Key_Here' with your actual ssh-ed25519 public key"
Write-Host "     from Moshi: Settings > SSH Keys > Copy Public Key"
Write-Host ""
Write-Host "  2. DISABLE PASSWORD AUTH (after key auth is confirmed working)" -ForegroundColor Yellow
Write-Host "     In C:\ProgramData\ssh\sshd_config, set:"
Write-Host "       PasswordAuthentication no"
Write-Host "     Then restart: Restart-Service sshd"
Write-Host ""
Write-Host "  3. TAILSCALE (if not already logged in)" -ForegroundColor Yellow
Write-Host "     Run: tailscale up"
Write-Host "     Then enable MagicDNS in the Tailscale admin console (DNS tab)"
Write-Host ""
Write-Host "  4. MOSHI CONNECTION SETTINGS" -ForegroundColor Yellow
Write-Host "     Host:            your-pc  (Tailscale MagicDNS name)"
Write-Host "     User:            $env:USERNAME"
Write-Host "     Port:            22"
Write-Host "     Connection type: Mosh"
Write-Host "     Mosh server:     /usr/bin/mosh-server"
Write-Host ""
Write-Host "  5. FIRST CONNECTION" -ForegroundColor Yellow
Write-Host "     After connecting: tmux new-session -As main"
Write-Host ""
Write-Host $sep -ForegroundColor Cyan
Write-Host ""
