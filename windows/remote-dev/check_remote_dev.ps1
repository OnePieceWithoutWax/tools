# check_remote_dev.ps1
# Health check for remote dev subsystems (OpenSSH, Tailscale, WSL, mosh, firewall)
# Run as Administrator for full results

$pass  = "[  OK  ]"
$fail  = "[ FAIL ]"
$warn  = "[ WARN ]"
$sep   = "-" * 55

function Write-Pass($msg) { Write-Host "$pass $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "$fail $msg" -ForegroundColor Red }
function Write-Warn($msg) { Write-Host "$warn $msg" -ForegroundColor Yellow }
function Write-Header($msg) {
    Write-Host ""
    Write-Host $sep -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host $sep -ForegroundColor Cyan
}

# -------------------------------------------------------
# 1. OpenSSH Server
# -------------------------------------------------------
Write-Header "OpenSSH Server"

$sshd = Get-Service -Name sshd -ErrorAction SilentlyContinue
if (-not $sshd) {
    Write-Fail "sshd service not found - OpenSSH Server may not be installed"
} elseif ($sshd.Status -eq 'Running') {
    Write-Pass "sshd service is running"
    Write-Pass "Startup type: $($sshd.StartType)"
} else {
    Write-Fail "sshd service exists but is not running (status: $($sshd.Status))"
}

# Check sshd_config exists
$sshdConfig = "C:\ProgramData\ssh\sshd_config"
if (Test-Path $sshdConfig) {
    Write-Pass "sshd_config found at $sshdConfig"

    $configContent = Get-Content $sshdConfig
    $pubkeyLine = $configContent | Where-Object { $_ -match '^\s*PubkeyAuthentication\s+yes' }
    if ($pubkeyLine) {
        Write-Pass "PubkeyAuthentication is enabled"
    } else {
        Write-Warn "PubkeyAuthentication not explicitly set to yes - check sshd_config"
    }

    $passwordLine = $configContent | Where-Object { $_ -match '^\s*PasswordAuthentication\s+no' }
    if ($passwordLine) {
        Write-Pass "PasswordAuthentication is disabled (good)"
    } else {
        Write-Warn "PasswordAuthentication may still be enabled - consider disabling after confirming key auth works"
    }
} else {
    Write-Fail "sshd_config not found at expected path"
}

# -------------------------------------------------------
# 2. Authorized Keys
# -------------------------------------------------------
Write-Header "SSH Authorized Keys"

$adminKeys = "C:\ProgramData\ssh\administrators_authorized_keys"
$userKeys   = "$env:USERPROFILE\.ssh\authorized_keys"

if (Test-Path $adminKeys) {
    $keyCount = (Get-Content $adminKeys | Where-Object { $_ -match '^ssh-' }).Count
    Write-Pass "administrators_authorized_keys exists ($keyCount keys found)"

    # Check permissions - should only have SYSTEM and Administrators
    $acl = (icacls $adminKeys 2>&1) -join " "
    if ($acl -match "BUILTIN\\Users" -or $acl -match "Everyone") {
        Write-Fail "Permissions too permissive on administrators_authorized_keys - OpenSSH will reject keys"
        Write-Warn "Run: icacls '$adminKeys' /inheritance:r /grant 'NT AUTHORITY\SYSTEM:(F)' /grant 'BUILTIN\Administrators:(F)'"
    } else {
        Write-Pass "Permissions on administrators_authorized_keys look correct"
    }
} else {
    Write-Fail "administrators_authorized_keys not found"
    Write-Warn "Your account is likely an Administrator - keys must go in $adminKeys"
    Write-Warn "Run: Copy-Item '$userKeys' '$adminKeys'"
}

if (Test-Path $userKeys) {
    Write-Warn "~\.ssh\authorized_keys also exists - note this file is ignored for Administrator accounts"
}

# -------------------------------------------------------
# 3. Firewall Rules
# -------------------------------------------------------
Write-Header "Firewall Rules"

# SSH port 22
$sshRule = Get-NetFirewallRule -Name "*sshd*" -ErrorAction SilentlyContinue |
           Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' }
if ($sshRule) {
    Write-Pass "SSH inbound firewall rule exists and is enabled"
} else {
    Write-Fail "No enabled inbound firewall rule found for SSH - port 22 may be blocked"
}

# Mosh UDP 60000-61000
$moshRule = Get-NetFirewallRule -Name "*mosh*" -ErrorAction SilentlyContinue |
            Where-Object { $_.Enabled -eq 'True' }
if ($moshRule) {
    $portFilter = $moshRule | Get-NetFirewallPortFilter
    if ($portFilter.Protocol -eq 'UDP' -and $portFilter.LocalPort -eq '60000-61000') {
        Write-Pass "Mosh UDP firewall rule exists (ports 60000-61000)"
    } else {
        Write-Warn "Mosh firewall rule exists but port/protocol may be misconfigured"
        Write-Warn "  Protocol: $($portFilter.Protocol), Ports: $($portFilter.LocalPort)"
    }
} else {
    Write-Fail "No mosh firewall rule found - UDP 60000-61000 may be blocked"
    Write-Warn "Run: New-NetFirewallRule -Name mosh -DisplayName 'Mosh UDP' -Enabled True -Direction Inbound -Protocol UDP -Action Allow -LocalPort 60000-61000"
}

# -------------------------------------------------------
# 4. Tailscale
# -------------------------------------------------------
Write-Header "Tailscale"

$tailscale = Get-Service -Name Tailscale -ErrorAction SilentlyContinue
if (-not $tailscale) {
    Write-Fail "Tailscale service not found - is Tailscale installed?"
} elseif ($tailscale.Status -eq 'Running') {
    Write-Pass "Tailscale service is running"

    # Check if tailscale.exe is on PATH and get status
    $tsExe = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($tsExe) {
        $tsStatus = tailscale status 2>&1
        if ($tsStatus -match "logged out") {
            Write-Fail "Tailscale is running but not logged in"
        } elseif ($tsStatus -match "\d+\.\d+\.\d+\.\d+") {
            Write-Pass "Tailscale is authenticated and connected"
            # Extract and show this machine's Tailscale IP
            $myIp = ($tsStatus | Select-String -Pattern '100\.\d+\.\d+\.\d+' | Select-Object -First 1).Matches.Value
            if ($myIp) { Write-Pass "Tailscale IP: $myIp" }
        } else {
            Write-Warn "Tailscale status unclear - run 'tailscale status' manually"
        }
    } else {
        Write-Warn "Tailscale service running but 'tailscale' not on PATH - can't verify connection status"
    }
} else {
    Write-Fail "Tailscale service is not running (status: $($tailscale.Status))"
}

# -------------------------------------------------------
# 5. WSL + mosh-server
# -------------------------------------------------------
Write-Header "WSL + mosh-server"

$wslExe = Get-Command wsl -ErrorAction SilentlyContinue
if (-not $wslExe) {
    Write-Fail "WSL not found - is it installed?"
} else {
    Write-Pass "WSL is installed"

    # Check default distro is running
    $wslStatus = (wsl --status 2>&1) -replace "`r", ""
    if ($wslStatus -match "Default Distribution") {
        Write-Pass "WSL has a default distribution configured"
    }

    # Check mosh-server is installed and accessible
    $moshPath = (wsl which mosh-server 2>&1) -replace "`r", ""
    if ($moshPath -match "/usr/bin/mosh-server" -or $moshPath -match "/bin/mosh-server") {
        Write-Pass "mosh-server found at: $($moshPath.Trim())"

        # Check version
        $moshVersion = ((wsl mosh-server --version 2>&1) -replace "`r", "") | Select-Object -First 1
        Write-Pass "mosh version: $($moshVersion.Trim())"
    } elseif ($moshPath -match "not found") {
        Write-Fail "mosh-server not found in WSL"
        Write-Warn "Run inside WSL: sudo apt update ; sudo apt install mosh"
    } else {
        Write-Warn "mosh-server check returned unexpected output: $moshPath"
        Write-Warn "Verify manually inside WSL: which mosh-server"
    }

    # Check tmux is installed
    $tmuxPath = (wsl which tmux 2>&1) -replace "`r", ""
    if ($tmuxPath -match "/usr/bin/tmux" -or $tmuxPath -match "/bin/tmux") {
        Write-Pass "tmux found at: $($tmuxPath.Trim())"
    } else {
        Write-Fail "tmux not found in WSL"
        Write-Warn "Run inside WSL: sudo apt install tmux"
    }

    # Check tmux.conf exists
    $tmuxConfCheck = (wsl bash -c "test -f ~/.tmux.conf && echo found || echo missing" 2>&1) -replace "`r", ""
    if ($tmuxConfCheck -match "found") {
        Write-Pass "~/.tmux.conf exists"
    } else {
        Write-Warn "~/.tmux.conf not found - tmux will use defaults"
    }

    # Check for active tmux sessions
    $tmuxSessions = (wsl bash -c "tmux list-sessions 2>&1") -replace "`r", ""
    if ($LASTEXITCODE -eq 0 -and $tmuxSessions -notmatch "no server running") {
        $sessionLines = ($tmuxSessions | Where-Object { $_ -match ':' })
        $sessionCount = @($sessionLines).Count
        Write-Pass "tmux server is running ($sessionCount active session(s))"
        foreach ($line in $sessionLines) {
            Write-Pass "  Session: $($line.Trim())"
        }
    } else {
        Write-Warn "No active tmux sessions (server not running - normal if you haven't connected yet)"
    }
}

# -------------------------------------------------------
# Summary
# -------------------------------------------------------
Write-Host ""
Write-Host $sep -ForegroundColor Cyan
Write-Host "  Done" -ForegroundColor Cyan
Write-Host $sep -ForegroundColor Cyan
Write-Host ""