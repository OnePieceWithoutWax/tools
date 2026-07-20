# PowerShell maintenance scripts

Scripts for keeping a local PowerShell installation, its modules, and its
help files up to date, plus a snapshot of what's installed.

## Files

- **update_powershell.ps1** — Runs `winget upgrade` for the
  `Microsoft.PowerShell` package to update PowerShell 7+ (`pwsh.exe`) to the
  latest release. Does not affect Windows PowerShell 5.1, which is built
  into Windows and updates via Windows Update instead.
- **update_help.ps1** — Runs `Update-Help` to refresh offline cmdlet help
  (`Get-Help`, `Get-Command -Syntax`) for installed modules.
- **update_modules.ps1** — Runs `Update-Module` to upgrade every module
  originally installed with `Install-Module` (PowerShell Gallery modules).
- **export_module_inventory.ps1** — Writes a JSON snapshot of installed
  modules (name/version/repository) and the current `$PROFILE` content to
  a timestamped file, so a setup can be reproduced or diffed later. Takes
  an optional `-OutputDirectory` (defaults to the current directory).
- **update_all.bat** — Double-click entry point. Elevates to Administrator
  once, then runs the four scripts above in order: PowerShell itself, help
  files, modules, then the inventory export.

## Usage

Run everything in one pass:

```bat
update_all.bat
```

Or run any script individually from an elevated PowerShell prompt — useful
for a custom inventory location:

```powershell
.\export_module_inventory.ps1 -OutputDirectory C:\Backups
```

## Requirements

- [winget](https://learn.microsoft.com/windows/package-manager/winget/) (App
  Installer), preinstalled on current Windows 10/11 builds.
- Administrator rights (handled automatically by `update_all.bat`).
- `update_modules.ps1` only affects modules installed via `Install-Module`;
  modules installed another way (manually copied, or via the newer
  `Install-PSResource`) are left untouched.

## Related tooling ideas (not implemented)

- **General package updates** — `winget upgrade --all` for other installed
  software, as a sibling script alongside this one.

## Applying user settings/preferences programmatically

- **`$PROFILE`** is just a `.ps1` file PowerShell dot-sources on startup
  (`$PROFILE.CurrentUserAllHosts` for all hosts, `$PROFILE` for the current
  host). A setup script can write/symlink a repo-tracked profile file to that
  path so aliases, prompt customization, and module imports are versioned
  here rather than living only on one machine.
- **PSReadLine options** (history search mode, prediction source, key
  bindings) are set via `Set-PSReadLineOption` / `Set-PSReadLineKeyHandler` —
  typically called from `$PROFILE`, so they're really an extension of the
  point above.
- **`$PSStyle`** (PowerShell 7.2+) controls ANSI output colors/formatting
  programmatically, also normally set from `$PROFILE`.
- **Module repository trust** — `Set-PSResourceRepository` /
  `Set-PSRepository` can mark a gallery as `Trusted` so module installs skip
  the confirmation prompt, useful for unattended setup scripts.
- **winget itself** has a settings file
  (`%LOCALAPPDATA%\Microsoft\WinGet\Settings\settings.json`) that can be
  written programmatically to configure its own defaults (e.g. default
  install scope, source auto-update behavior).

If useful, a `set_powershell_profile.ps1` (or similar) could symlink a
repo-tracked profile into `$PROFILE` and apply a baseline set of PSReadLine
options — worth confirming the exact baseline first, since it's a matter of
personal preference (see the recommendations below as a starting point).

## Prompt and editor setup

None of this is installed by the scripts here — it changes what your shell
looks and feels like, which is a personal-preference call best made once,
not re-applied by an update script. Recommendations below, aimed at someone
new to PowerShell who wants a noticeably better day-to-day experience
without a lot of moving parts.

**Recommended (in priority order):**

1. **PSReadLine — just turn on predictive IntelliSense.** PSReadLine
   already ships with PowerShell 7 and provides tab completion and line
   editing; nothing to install. The one setting worth adding to `$PROFILE`
   is predictive suggestions from history, shown as you type:

   ```powershell
   Set-PSReadLineOption -PredictionSource History -PredictionViewStyle ListView
   ```

   This is the single highest-value, lowest-effort change for a beginner —
   it surfaces commands you've run before as you type, which doubles as a
   way to learn/recall syntax.

2. **oh-my-posh — prompt theming, including git status.** A cross-shell
   prompt engine ([ohmyposh.dev](https://ohmyposh.dev/)) that shows useful
   context (current path, git branch/status, error state) directly in the
   prompt using pre-built themes, so no manual prompt-scripting is needed.
   Install via winget and initialize from `$PROFILE`:

   ```powershell
   winget install JanDeDobbeleer.OhMyPosh -s winget
   oh-my-posh font install CascadiaCode   # installs a Nerd Font for icons/glyphs
   # then in $PROFILE:
   oh-my-posh init pwsh --config "$env:POSH_THEMES_PATH\jandedobbeleer.omp.json" | Invoke-Expression
   ```

   Requires a Nerd Font-patched font (the command above installs one) and a
   terminal that renders it — Windows Terminal does, by default the
   built-in `powershell.exe` console host does not.

3. **Terminal-Icons — file-type icons in directory listings.** A module
   that adds icons/colors to `Get-ChildItem` (`ls`) output in a Nerd
   Font-capable terminal. Small quality-of-life win, no configuration
   needed beyond importing it:

   ```powershell
   Install-Module -Name Terminal-Icons -Repository PSGallery
   # then in $PROFILE:
   Import-Module Terminal-Icons
   ```

**Optional, situational:**

- **posh-git** — adds git tab-completion (`git chec<TAB>` → `checkout`) and
  a git-aware prompt segment. Skip it if using oh-my-posh, since oh-my-posh
  already shows git status in the prompt and the two can conflict/duplicate
  effort; install it only if the git *tab-completion* specifically is
  wanted without the rest of oh-my-posh.

**Prerequisite for icons/glyphs:** both oh-my-posh and Terminal-Icons need
a [Nerd Font](https://www.nerdfonts.com/) and a terminal that renders it —
use [Windows Terminal](https://aka.ms/terminal) (Microsoft Store or
`winget install Microsoft.WindowsTerminal`) rather than the legacy console
host.

If you confirm you want this baseline (PSReadLine tweak + oh-my-posh +
Terminal-Icons), it can be turned into a `set_powershell_profile.ps1`
companion script that installs the modules/font and writes the profile
lines above — see the section above on applying settings programmatically.
