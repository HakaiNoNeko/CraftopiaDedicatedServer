# Craftopia Server Manager

A wrapper around the stock Craftopia dedicated server (Steam app 1670340) that adds what it lacks.
Pure Python 3 stdlib, no game files modified, nothing to build.

## Install

Install **Craftopia Dedicated Server** from Steam first, then:

**Windows:** download `CraftopiaServerManager-Setup.exe` from the [latest release](../../releases/latest) and run it. Pick your
`CraftopiaDedicatedServer` folder when asked. It installs BepInEx and the chat plugin into the server and adds a Start Menu entry.
(Windows support is new and was built by CI; please report problems.)

**Linux:**

```bash
curl -fsSL https://github.com/HakaiNoNeko/CraftopiaDedicatedServer/releases/latest/download/install.sh | bash -s -- --service
```

Drop `--service` to skip the systemd user service, or pass your server folder as the first argument if it is not in the default Steam path.
Then run `craftopia-server`. Open **UDP 6587** in your firewall/router so others can join.

## What the stock server has / lacks

Stock console commands: `help`, `list`, `kick <id>`, `ban <id>` (IP-based), `pardon <address>`, `say`, `tell`, `lock`/`unlock`, `fps`, `stop`.
Missing: whitelist, backups, remote control, admins by name, in-game chat commands, crash restart, scheduled restarts.
Also fixed: the stock `savePath=DedicatedServerSave/` is glued onto the install path without a slash
(`...CraftopiaDedicatedServerDedicatedServerSave`), so the manager pins an absolute `savePath` (`data/save/`).

## Features

- Crash auto-restart, optional scheduled restarts with in-game countdown warnings
- Consistent backups (SQLite online-backup API on the live `.db` files), interval + on-stop, retention
- Whitelist, name bans (persisted), admin list; non-whitelisted/banned players are kicked on join
- Chat-command handling (`!kick`, `!ban`, `!whitelist add X`, ...) is implemented but needs a chat source; see limits
- Remote HTTP API (bearer token, localhost by default) and `ctl` CLI; Discord webhook for join/leave/backup/crash
- Any unrecognised command is passed straight to the game console

## Use

```bash
python3 craftopia_server.py            # first run writes config.json (random API token)
python3 craftopia_server.py ctl backup # talk to the running manager
python3 craftopia_server.py ctl whitelist add SomeName
python3 -m unittest
```

API: `GET /status`, `GET /logs`, `POST /command {"command": "..."}` with `Authorization: Bearer <token>`.
Edit `config.json` for the install path, backup/restart schedule, API port (default 27700) and whitelist toggle.

## Known limits (please read)

- **Verified against a real join:** `list` prints CSV (`playerId,name`, rows like `800,"Kisaragi"`; the name is empty
  until the client finishes joining, which is ignored). Join/leave detection uses that.
- **In-game chat commands need the bundled plugin.** The stock server never logs player chat (it travels over the
  `OcNetRpc_Chat` RPC). `./install_plugin.sh` unpacks BepInEx into the server and builds `plugin/`, which prints
  `[Chat] <playerId>: <text>` to stdout; the manager then launches the server through `run_bepinex.sh` automatically.
  `!`-prefixed messages are hidden from other players. Installed and hook confirmed loading; end-to-end chat not yet
  verified with a real player, and the chat sender id is assumed to equal the `list` playerId.
- Whitelist/ban enforcement is based on the verified `list` format but has not yet been exercised with a non-whitelisted player.
- Players are matched by display name (the console exposes no stable account id), so names can be impersonated.
- World load takes 2-3 minutes; the manager treats the server as ready on the "World is loaded" line.
