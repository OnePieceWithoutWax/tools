# remote-dev

One-shot setup and health check for a Windows remote-dev stack: OpenSSH Server, Tailscale, WSL2 (Ubuntu), mosh, and tmux — so the machine can be reached from a phone (Moshi) or another computer over Tailscale.

## Prerequisites

Installed before running (the setup script configures, it mostly doesn't install):

- **OpenSSH Server** (Windows optional feature) — setup exits if missing
- **Tailscale** — https://tailscale.com/download
- **WSL2 with Ubuntu** — setup will run `wsl --install` for you if missing (restart required, then re-run)
- **mosh** and **tmux** inside WSL (`sudo apt install mosh tmux`)

## Run order

1. `setup_remote_dev.bat` — configures everything: sshd service (delayed auto-start) + firewall rule, mosh UDP firewall rule, `sshd_config` hardening, authorized_keys placement (admin-aware — admin accounts use `C:\ProgramData\ssh\administrators_authorized_keys`), Tailscale service startup, and a `~/.tmux.conf` inside WSL. Ends with a checklist of manual next steps (paste your public key, disable password auth, `tailscale up`).
2. `check_remote_dev.bat` — health check that verifies each subsystem and reports OK / WARN / FAIL per item.

The `.bat` files are elevation launchers: each one relaunches itself as Administrator if needed, then runs the same-named `.ps1` from its own directory. Run the `.ps1` files directly only from an already-elevated PowerShell.

## Guides

- [guide-ssh-tailscale-tmux.md](guide-ssh-tailscale-tmux.md) — the walkthrough these scripts automate (SSH + Tailscale + mosh + tmux)
- [guide-vscode-remote-tunnels.md](guide-vscode-remote-tunnels.md) — alternative approach using VS Code Remote Tunnels
