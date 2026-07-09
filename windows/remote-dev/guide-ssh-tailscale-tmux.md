# Remote Dev from iPhone — Guide 1: Moshi + Tailscale + tmux

A low-bandwidth, high-resilience setup for terminal-based work (including Claude Code)
from your iPhone, over any network.

---

## Overview

```
iPhone (Moshi app)
    └── Tailscale VPN (encrypted, no port forwarding)
            └── SSH handshake → mosh-server (WSL) on Windows
                    └── tmux session
                            └── Claude Code / Python / etc.
```

---

## Software Requirements

### On Windows (dev machine)
| Software | Purpose | Cost |
|---|---|---|
| OpenSSH Server | Built-in Windows feature | Free |
| WSL (Windows Subsystem for Linux) | Runs mosh-server | Free |
| Tailscale | Mesh VPN, replaces port forwarding | Free (personal) |
| tmux | Session persistence (installed inside WSL) | Free |
| Claude Code | AI coding assistant | Free (needs Anthropic account) |

### On iPhone
| App | Purpose | Cost |
|---|---|---|
| Moshi: SSH & MOSH Terminal | SSH/mosh client, push notifications, voice input | Free trial (20 mosh sessions), then ~$20/yr |
| Tailscale iOS app | Connects your phone to the VPN | Free |

---

## Part 1 — Windows: Enable OpenSSH Server

1. Open **Settings → System → Optional Features**
2. Click **Add a feature** and search for **OpenSSH Server**
3. Install it, then open **Services** (`services.msc`):
   - Find **OpenSSH SSH Server**
   - Set **Startup type** to `Automatic (Delayed Start)`
   - Click **Start**
4. Allow SSH through Windows Firewall — run in PowerShell as Administrator:
   ```powershell
   New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' `
     -Enabled True -Direction Inbound -Protocol TCP `
     -Action Allow -LocalPort 22
   ```

### Verify it's running
```powershell
Get-Service sshd
# Should show: Status = Running
```

---

## Part 2 — Windows: Install WSL and mosh-server

Moshi uses the mosh protocol for resilient connections. Mosh requires `mosh-server`
to be installed on the Windows machine — the easiest way is via WSL.

### Install WSL (if not already installed)
In PowerShell as Administrator:
```powershell
wsl --install
```
Restart when prompted. WSL will install Ubuntu by default.

### Install mosh inside WSL
```bash
sudo apt update && sudo apt install mosh
```

### Verify mosh-server is accessible
```bash
which mosh-server
# Should return: /usr/bin/mosh-server
```

Also verify Windows can see it (run in PowerShell):
```powershell
wsl mosh-server --version
# Should print the mosh version number
```

If this errors, see the Troubleshooting section at the end.

### Open the mosh UDP port range in Windows Firewall
Mosh uses SSH (port 22) only for the initial handshake, then switches to UDP ports
60000–61000. Both must be open or Moshi will hang at "checking the server".

```powershell
New-NetFirewallRule -Name mosh -DisplayName 'Mosh UDP' `
  -Enabled True -Direction Inbound -Protocol UDP `
  -Action Allow -LocalPort 60000-61000
```

---

## Part 3 — Windows: Configure sshd_config

The config file lives at `C:\ProgramData\ssh\sshd_config`. Open it in Notepad
as Administrator.

Make (or confirm) these settings:

```
# Key auth on, password auth off (after keys are set up)
PubkeyAuthentication yes
PasswordAuthentication no

# Keep sessions alive through mobile network drops
ClientAliveInterval 60
ClientAliveCountMax 3

# Verbose logging — useful for diagnosing auth issues
LogLevel VERBOSE
```

After editing, restart the SSH service:
```powershell
Restart-Service sshd
```

> **Note:** Leave `PasswordAuthentication yes` temporarily until you've confirmed
> key-based auth works. Then disable it.

### Enable SSH logs (useful for troubleshooting)
```powershell
Get-WinEvent -LogName 'OpenSSH/Operational' -MaxEvents 20 | Format-List TimeCreated, Message
```

If that errors, enable the log first:
```powershell
$log = New-Object System.Diagnostics.Eventing.Reader.EventLogConfiguration 'OpenSSH/Operational'
$log.IsEnabled = $true
$log.SaveChanges()
```

---

## Part 4 — iPhone: Generate SSH Keys in Moshi

1. Open **Moshi** → tap **Settings** (gear icon) → **SSH Keys**
2. Tap **+** → **Generate New Key**
   - Type: `ED25519`
   - Give it a name, e.g. `iphone-dev`
3. Tap the key → **Copy Public Key**

Now add the public key to your Windows machine. Connect temporarily with password
auth, or paste directly in PowerShell:

```powershell
# Create the .ssh folder if it doesn't exist
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh"

# Add your public key (replace the key string with what you copied from Moshi)
Add-Content "$env:USERPROFILE\.ssh\authorized_keys" "ssh-ed25519 AAAA... your-key-here"
```

---

## ⚠️ Part 5 — Windows: Administrator Account Key Location

> **This is the most common failure point on personal Windows machines.**

If your Windows account is an Administrator (which it almost certainly is on a
personal machine), OpenSSH **ignores** the standard `~\.ssh\authorized_keys` file
and looks in a different location instead:

```
C:\ProgramData\ssh\administrators_authorized_keys
```

### Check if your account is an administrator
```powershell
net localgroup administrators | findstr /i $env:USERNAME
```

If your username appears, run these commands to copy the key to the correct location
and set the required permissions:

```powershell
# Copy key to the correct location
Copy-Item "$env:USERPROFILE\.ssh\authorized_keys" `
  "C:\ProgramData\ssh\administrators_authorized_keys"

# Set strict permissions — OpenSSH will silently reject the key if these are wrong
icacls "C:\ProgramData\ssh\administrators_authorized_keys" `
  /inheritance:r `
  /grant "NT AUTHORITY\SYSTEM:(F)" `
  /grant "BUILTIN\Administrators:(F)"
```

> **Why does this happen?** OpenSSH treats admin accounts differently as a security
> measure — a compromised per-user authorized_keys file shouldn't be able to grant
> admin access. The centralised `administrators_authorized_keys` file must be
> owned/controlled only by the Administrators group itself.

---

## Part 6 — Set Up Tailscale

### On Windows
1. Download and install Tailscale from [tailscale.com/download](https://tailscale.com/download)
2. Log in with a Google/GitHub/Microsoft account
3. Your machine will appear in the Tailscale admin console at [login.tailscale.com](https://login.tailscale.com)
4. In Services (`services.msc`), set Tailscale to `Automatic (Delayed Start)`

### On iPhone
1. Install **Tailscale** from the App Store
2. Log in with the **same account**
3. Toggle Tailscale on — your iPhone is now on the same private network as your PC

### Find your machine's Tailscale hostname
In the Tailscale admin console, your machine will have a stable name like:
```
your-pc.tail1234.ts.net
```
Enable **MagicDNS** in the admin console (DNS tab) to use short names like just `your-pc`.

---

## Part 7 — Set Up tmux in WSL

### Install tmux
```bash
# Inside WSL (already done if you installed mosh)
sudo apt install tmux
```

### Configure tmux
Create `~/.tmux.conf` inside WSL:

```bash
# Mouse support — tap to switch panes on iPhone
set -g mouse on

# Large scrollback buffer
set -g history-limit 50000

# Renumber windows when one closes
set -g renumber-windows on

# Don't exit when last session closes — keeps things running
set -g detach-on-destroy off

# Pass window titles to Moshi (shows current tmux window in app)
set -g set-titles on
set -g set-titles-string "#I: #T"

# Start window numbering at 1
set -g base-index 1
setw -g pane-base-index 1
```

---

## Part 8 — Connect via Moshi

1. Open **Moshi** → tap **+** to add a new host
2. Fill in:
   - **Host:** your Tailscale hostname (e.g. `your-pc` if MagicDNS is enabled)
   - **User:** your Windows username (check with `$env:USERNAME` in PowerShell)
   - **Port:** `22`
   - **Key:** select `iphone-dev`
   - **Connection type:** `Mosh` (not SSH)
   - **Mosh server path:** `/usr/bin/mosh-server` (set this explicitly to avoid PATH issues)
3. Tap **Connect**

Moshi will authenticate via SSH first, then hand off to mosh-server. The initial
connection takes a few seconds — this is normal.

---

## Part 9 — Daily Workflow

### First connection
```bash
# Moshi connects and drops you into a WSL shell
# Start or attach to your tmux session
tmux new-session -As main   # creates 'main' if it doesn't exist, attaches if it does
```

### Inside tmux — essential commands
| Action | Keys |
|---|---|
| New window | `Ctrl+b c` |
| Switch window | `Ctrl+b n` / `Ctrl+b p` |
| Split pane horizontally | `Ctrl+b "` |
| Split pane vertically | `Ctrl+b %` |
| Detach (leave running) | `Ctrl+b d` |
| Reattach later | `tmux attach -t main` |

### Running Claude Code
```bash
# Inside your tmux session
cd /path/to/your/project
claude
```

Your Claude Code session **persists even if your phone locks, the mosh connection
roams, or you switch apps.** Just reconnect and `tmux attach`.

### Moshi-specific features for Claude Code

**Push notifications** — Claude Code can notify you when it needs input or finishes
a task. Add this to your Claude Code workflow:
```bash
# Send a notification when a long task completes
your-long-command && curl -s -X POST https://api.getmoshi.app/api/webhook \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_MOSHI_TOKEN", "title": "Done", "message": "Task complete"}'
```
Find your webhook token in Moshi → Settings → Notifications.

**Voice input** — hold the mic button in Moshi to dictate commands using on-device
Whisper. Useful for quick approvals ("yes", "continue") without typing.

---

## Troubleshooting

**"Checking the server" hangs in Moshi**
- Most likely `mosh-server` is not installed or not on PATH
- Verify: `wsl mosh-server --version` in PowerShell
- Set the mosh server path explicitly in Moshi connection settings: `/usr/bin/mosh-server`
- Confirm the UDP firewall rule is in place (port range 60000–61000)

**Auth fails (key rejected)**
- On admin accounts, the key must be in `C:\ProgramData\ssh\administrators_authorized_keys`
  not in your user profile — see Part 5
- Check permissions: `icacls "C:\ProgramData\ssh\administrators_authorized_keys"`
  — only SYSTEM and Administrators should appear
- Check SSH logs: `Get-WinEvent -LogName 'OpenSSH/Operational' -MaxEvents 10 | Format-List TimeCreated, Message`

**Connected via SSH but mosh fails**
- Confirm UDP 60000–61000 is open in Windows Firewall
- Confirm `mosh-server` is installed in WSL: `which mosh-server`
- Try setting the explicit path in Moshi connection settings

**Wrong shell / landed in PowerShell instead of WSL**
- In Moshi connection settings, set the **remote command** to `wsl`
- Or add to the bottom of `sshd_config`: `Match All` / `ForceCommand wsl`

---

*Next: [Guide 2 — VS Code Remote Tunnels](./guide-vscode-remote-tunnels.md)*
