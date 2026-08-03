# PHYsteam (Decky Loader plugin)

Ported from the standalone `physteam.py` + `install_physteam.sh` /
`uninstall_physteam.sh` scripts. What changed and why:

| Old (systemd/cron script) | New (Decky plugin) |
|---|---|
| `install_physteam.sh` sets up autostart (systemd user service, or crontab `@reboot` fallback) | Decky Loader itself already autostarts at boot — the plugin's `_main()` just runs inside it. No install script needed. |
| Console `--configure` prompt (`input()`) picks mode/drive/require_card | A Quick Access Menu panel (`src/index.tsx`) calls backend methods instead |
| `physteam_config.json` / `physteam_known_games.json` next to the script | Stored via Decky's `SettingsManager` under `DECKY_PLUGIN_SETTINGS_DIR` |
| `physteam.log` in the script's folder | Decky's own logger (`decky_plugin.logger`), viewable in the Decky Loader log panel |
| `uninstall_physteam.sh` stops the process, removes the systemd unit / crontab line | Just delete the plugin through Decky's plugin manager — it calls `_unload()` then `_uninstall()` |

The actual cartridge-detection logic (drive polling, App ID parsing,
`kill_by_app_id` via `/proc`, Steam library registration) is untouched —
it's copied into `main.py` almost verbatim, just wrapped in `async def`
and using `asyncio.sleep` instead of `time.sleep`/`threading`.

## 1. Prerequisites

**On the Deck (or whatever SteamOS/Linux device is running Steam):**
- [Decky Loader](https://decky.xyz) installed. If you don't have it yet, use the official installer — do this in Desktop Mode:
  ```bash
  curl -L https://github.com/SteamDeckHomebrew/decky-installer/releases/latest/download/decky_installer.desktop -o ~/Desktop/decky_installer.desktop
  ```
  then double-click it on the desktop, or follow the current instructions at https://decky.xyz.
- In the Quick Access Menu → Decky settings → enable **Developer Mode**. This unlocks "Install from ZIP" and lets you sideload plugins without going through the plugin store.

**On your dev machine** (can be the Deck's Desktop Mode, or any PC — you just need it once, to build):
- Node.js v16.14+ 
- `pnpm` v9 (install with `npm i -g pnpm@9` — the Decky CI is picky about the version)
- (Only needed if you later add a compiled/non-Python backend component — not needed here.)

## 2. Build the frontend

From this folder:

```bash
pnpm install
pnpm run build
```

This produces `dist/index.js` — the compiled Quick Access Menu panel.
`main.py` needs no build step; Decky runs it with the system Python directly.

## 3. Install it for testing (sideload)

Copy the whole folder to the Deck under `~/homebrew/plugins/PHYsteam/`. If
you're building directly on the Deck, that's just:

```bash
mkdir -p ~/homebrew/plugins/PHYsteam
cp -r plugin.json package.json main.py dist LICENSE.md README.md ~/homebrew/plugins/PHYsteam/
```

If you built on a separate PC, `scp`/`rsync` those same files/folders over
to the Deck at that path instead.

Then restart the loader so it picks up the new plugin:

```bash
sudo systemctl restart plugin_loader
```

Open the Quick Access Menu (the `...` button in Game Mode, or the
equivalent menu in Desktop Mode) → the plugin list on the left should now
show **PHYsteam** with the disc icon. Open it — you'll see the Mode /
Drive / "Require cartridge" controls from `src/index.tsx`.

Alternative to steps above: zip the folder (`zip -r PHYsteam.zip .` from
inside it) and use Decky's **Settings → Developer → Install Plugin from
ZIP** — same result, just through the UI instead of `scp`.

## 4. Verify it's actually watching drives

Insert a USB stick/SD card with a `launch_game_linux.py` file at its root
(same format the old script expected — a `STEAM_APP_ID = "..."` line for
the enforcer to key on). Watch the Decky Loader log:

```bash
journalctl --user -u plugin_loader -f
# or, if Decky logs to its own file, tail that instead — check
# ~/homebrew/logs/ or the path decky_plugin.DECKY_PLUGIN_LOG_DIR resolves to
```

You should see the same "Launching ..." / "Registered X as Steam library"
lines the original script produced, just coming from the plugin now.

## 5. Uninstalling

No more `uninstall_physteam.sh` — Decky's plugin manager handles it: Quick
Access Menu → Decky settings → plugin list → uninstall PHYsteam. That
triggers `_unload()` (stops the watch/enforcer tasks) then `_uninstall()`,
and Decky removes the plugin folder and its settings directory itself.

## 6. Optional: submitting to the Decky plugin store

Not required for personal use, but if you want it installable by others
without sideloading: fork the `decky-plugin-template` conventions (this
repo already follows them), then follow
https://wiki.deckbrew.xyz/en/plugin-dev/plugin-submission — it's a PR
against the plugin database repo with your built `dist/`, `plugin.json`,
and `main.py`, plus a review pass from the Decky team.

## Notes / things worth double-checking before you rely on this

- `import decky_plugin` in `main.py` matches the API most current example
  plugins use, but Decky has been mid-rename to a plain `decky` module in
  some newer loader versions. If `main.py` fails to import on your loader
  version, check the log — the fix is usually just changing that one
  import line and the `decky_plugin.DECKY_PLUGIN_SETTINGS_DIR` /
  `decky_plugin.logger` references to whatever `decky.pyi` in your
  installed loader actually exposes.
- The frontend uses `@decky/ui` + `@decky/api` (current package names).
  If your `pnpm install` pulls a much older/newer major version, some
  component props (e.g. `Dropdown`'s `rgOptions`) may have shifted —
  the Decky Loader Discord's `#plugin-dev` channel and
  https://wiki.deckbrew.xyz are the fastest way to check current signatures.
- Killing by `AppId=` cmdline marker (Steam's reaper process) still assumes
  a normal Steam launch. Nothing about the Decky wrapping changes that
  behavior — it's exactly the same mechanism as the original script.
