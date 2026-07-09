# Remote Dev from iPhone — Guide 2: VS Code Remote Tunnels

A browser-based VS Code environment streamed from your Windows dev machine.
Best for real editing sessions with good WiFi. Includes a terminal for Claude Code.

---

## Overview

```
iPhone browser (Safari / Chrome)
    └── vscode.dev (Microsoft-hosted relay)
            └── Encrypted tunnel
                    └── VS Code Server on Windows
                            └── Your files, terminal, extensions
```

> Unlike Guide 1, this does **not** require Tailscale or any network configuration.
> Microsoft's relay handles the routing. The tradeoff is slightly higher bandwidth
> and a dependency on Microsoft's infrastructure.

---

## Software Requirements

### On Windows (dev machine)
| Software | Purpose | Cost |
|---|---|---|
| VS Code | Hosts the tunnel server | Free |
| Claude Code | AI coding assistant | Free (needs Anthropic account) |
| A Microsoft or GitHub account | Authenticates the tunnel | Free |

> That's it. No extra installs, no firewall rules, no Tailscale required.

### On iPhone
| App | Purpose | Cost |
|---|---|---|
| Safari or Chrome | Access vscode.dev | Free |
| (Optional) Tailscale | Only needed if combining with Guide 1 | Free |

---

## Part 1 — Windows: Install VS Code

1. Download VS Code from [code.visualstudio.com](https://code.visualstudio.com)
2. Install normally
3. During install, check **"Add to PATH"** — this lets you run `code` from any terminal

Verify the PATH addition worked:
```powershell
code --version
# Should print something like: 1.88.0
```

---

## Part 2 — Windows: Start a Remote Tunnel

VS Code has tunnel support built in — no extension required.

### Option A: Via the VS Code GUI (easiest first time)

1. Open VS Code
2. Click the **accounts icon** (bottom-left, looks like a person) → **Turn on Remote Tunnel Access...**
3. Sign in with your **GitHub** or **Microsoft** account
4. VS Code will register the tunnel and show you the machine name

### Option B: Via the terminal (better for automation / running headlessly)

```powershell
# Start the tunnel — VS Code doesn't need to be open as a window
code tunnel
```

First run will prompt you to authenticate:
```
? How would you like to log in to Visual Studio Code? GitHub Account
Please open https://github.com/login/device and enter code: XXXX-XXXX
```

Open that URL on any device, enter the code, and the tunnel is registered.

After auth, you'll see:
```
[2024-xx-xx] info  Creating tunnel with the name: your-pc-name
Open this link in your browser: https://vscode.dev/tunnel/your-pc-name
```

### Make the tunnel start automatically on login

Run this once in PowerShell as Administrator:
```powershell
code tunnel service install --accept-server-license-terms
```

This registers VS Code tunnel as a Windows service — it will start automatically
on boot, even without anyone logged in.

Verify it's running:
```powershell
code tunnel service log
```

---

## Part 3 — iPhone: Connect to the Tunnel

1. Open Safari (or Chrome) on your iPhone
2. Navigate to **[vscode.dev](https://vscode.dev)**
3. Sign in with the **same GitHub/Microsoft account** as your Windows machine
4. Click the **Remote Explorer** icon in the left sidebar (looks like a monitor with a connection symbol)
5. Your Windows machine will appear under **Remote Tunnels** — click **Connect**

You now have a full VS Code environment in your mobile browser, running against your
Windows machine's filesystem and compute.

### Add to iPhone Home Screen (optional but recommended)
In Safari: tap the **Share** button → **Add to Home Screen**
This gives you a near-app experience with no browser chrome.

---

## Part 4 — Using the Terminal (for Claude Code)

1. In vscode.dev, open the terminal: **Ctrl+\`** (or via the menu: **Terminal → New Terminal**)
2. This opens a PowerShell session running on your Windows machine
3. Navigate to your project and run Claude Code normally:

```powershell
cd C:\path\to\your\project
claude
```

> **Session persistence caveat:** Unlike the Moshi + tmux approach, if your browser tab closes
> or your iPhone locks mid-session, the terminal process may be interrupted.
>
> **Workaround:** Run Claude Code inside tmux even within the VS Code terminal:
> ```powershell
> # In the VS Code terminal
> wsl   # enter WSL
> tmux new-session -As vscode-session
> claude
> ```
> Now your Claude Code session survives browser disconnects. This is the same tmux
> setup from Guide 1 — the sessions are shared, so you can start a job here and
> check on it later from Moshi.

---

## Part 5 — Install Useful Extensions

Extensions run on the remote machine (Windows), so they have full access to your
environment. Install them once via vscode.dev and they persist.

Recommended for Python dev:

```
ms-python.python          # Python language support
ms-python.pylance         # Fast type checking and intellisense
ms-toolsai.jupyter        # Jupyter notebook support
eamodio.gitlens           # Better git integration
```

Install from the Extensions panel (Ctrl+Shift+X) in vscode.dev as normal.

---

## Part 6 — Daily Workflow

### Starting your session
1. The tunnel service starts automatically on Windows boot (if you ran `service install`)
2. On iPhone: open **vscode.dev** (or your home screen shortcut) → sign in → connect

### Working comfortably on a phone screen
- Use **Ctrl+P** (or tap the search icon) to open files by name — faster than navigating the file tree
- **Ctrl+Shift+P** opens the command palette — most actions are accessible here
- Pinch to zoom in on code if needed
- In landscape mode you get significantly more screen real estate
- Enable **Zen Mode** (Ctrl+K Z) to hide all UI chrome and focus on one file

### Ending your session
Just close the browser tab. The tunnel keeps running on Windows, ready for next time.
Your unsaved files remain open in VS Code's state.

---

## Comparing Tunnel vs SSH+tmux in Practice

| Scenario | Better approach |
|---|---|
| Editing multiple files, navigating a codebase | **Remote Tunnels** |
| Running Claude Code for an extended session | **Moshi + tmux** |
| On a slow / mobile data connection | **Moshi + tmux** |
| Good WiFi, want visual file explorer | **Remote Tunnels** |
| Session must survive phone locking | **Moshi + tmux** (or tmux inside VS Code terminal) |
| Need push notifications when Claude needs input | **Moshi + tmux** |
| Zero network config available | **Remote Tunnels** |

---

## Troubleshooting

**Machine doesn't appear in Remote Explorer**
- Check the tunnel service is running: `code tunnel service log`
- Confirm you're signed into vscode.dev with the same account as on Windows
- Restart the service: `code tunnel service restart`

**Terminal works but Claude Code isn't found**
- Confirm Claude Code is installed and on PATH in PowerShell:
  ```powershell
  where.exe claude
  ```
- If installed in a specific venv or location, activate it first:
  ```powershell
  & "C:\path\to\venv\Scripts\Activate.ps1"
  ```

**vscode.dev is slow / laggy**
- This usually means bandwidth is the bottleneck — switch to SSH+tmux
- Try disabling unused extensions, which can increase the data the tunnel sends

**Tunnel stops after Windows sleep/hibernate**
- In Power Settings, set the machine to never sleep (or sleep only the display)
- The service will keep running as long as Windows is awake

---

*Previous: [Guide 1 — SSH + Tailscale + tmux](./guide-ssh-tailscale-tmux.md)*
