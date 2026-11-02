<h1 align="center">Craftopia Server Manager</h1>

<p align="center">
  A wrapper around the stock Craftopia dedicated server (Steam app 1670340) that adds backups, a whitelist,
  admins, remote control and automatic restarts.<br>
  Pure Python 3 standard library. No game files are modified. Nothing to build.
</p>

<p align="center">
  <img alt="Visitors" src="https://count.getloli.com/@HakaiNoNeko-CraftopiaDedicatedServer?name=HakaiNoNeko-CraftopiaDedicatedServer&theme=yuki-catboy&padding=7&offset=0&align=top&scale=0.5&pixelated=1&darkmode=auto">
</p>

<p align="center">
  <a href="../../releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/HakaiNoNeko/CraftopiaDedicatedServer?style=flat-square"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green?style=flat-square"></a>
  <img alt="Python 3, standard library only" src="https://img.shields.io/badge/python-3%20(stdlib)-3776AB?style=flat-square">
  <img alt="Platforms: Windows and Linux" src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey?style=flat-square">
</p>

<p align="center">
  <a href="#installation">Installation</a> |
  <a href="#features">Features</a> |
  <a href="#usage">Usage</a> |
  <a href="#commands">Commands</a> |
  <a href="#configuration">Configuration</a> |
  <a href="#remote-api">Remote API</a> |
  <a href="#known-limitations">Known limitations</a>
</p>

---

## Overview

The stock Craftopia dedicated server has a small console and no management features. This manager supervises the
server process and fills the gaps: it restarts the server after a crash, takes consistent backups of the save,
enforces a whitelist and ban list, and exposes everything through an HTTP API and a command-line client.

| | |
|---|---|
| **Stock server has** | `help`, `list`, `kick <id>`, `ban <id>` (IP-based), `pardon <address>`, `say`, `tell`, `lock` / `unlock`, `fps`, `stop` |
| **Stock server lacks** | whitelist, backups, remote control, admins by name, in-game chat commands, crash restart, scheduled restarts |
| **Also fixed** | The stock `savePath=DedicatedServerSave/` is joined to the install path without a slash (`...CraftopiaDedicatedServerDedicatedServerSave`). The manager pins an absolute `savePath` (`data/save/`). |

## Features

- **Crash recovery.** Automatic restart after a crash, plus optional scheduled restarts with in-game countdown warnings.
- **Backups.** Consistent copies of the live `.db` files using the SQLite online-backup API, taken on an interval and
  on stop, with configurable retention.
- **Access control.** Whitelist, persisted name bans and an admin list. Players who are not whitelisted, or who are
  banned, are kicked on join.
- **Chat commands.** `!kick`, `!ban`, `!whitelist add <name>` and others, handled in game (requires the bundled
  plugin, see [Known limitations](#known-limitations)).
- **Remote control.** HTTP API with bearer-token authentication (localhost by default) and a `ctl` command-line client.
- **Notifications.** Optional Discord webhook for join, leave, backup and crash events.
- **Console passthrough.** Any command the manager does not recognise is sent straight to the game console.

## Installation

Install **Craftopia Dedicated Server** from Steam first.

### Windows

1. Download `CraftopiaServerManager-Setup.exe` from the [latest release](../../releases/latest).
2. Run it and select your `CraftopiaDedicatedServer` folder when asked.

The installer sets up BepInEx and the chat plugin inside the server folder and adds a Start Menu entry.

> Windows support is new and is built by CI. Please report any problems.

### Linux

```bash
curl -fsSL https://github.com/HakaiNoNeko/CraftopiaDedicatedServer/releases/latest/download/install.sh | bash -s -- --service
```

- Omit `--service` to skip the systemd user service.
- Pass your server folder as the first argument if it is not in the default Steam path.
- Start the manager with `craftopia-server`.

### Networking

Open **UDP 6587** in your firewall and router so other players can join.

## Usage

```bash
python3 craftopia_server.py             # start the manager (first run writes config.json with a random API token)
python3 craftopia_server.py ctl backup  # send a command to the running manager
python3 craftopia_server.py ctl whitelist add SomeName
python3 -m unittest                     # run the tests
```

## Commands

The same commands work from `ctl`, from the HTTP API and, for admins, from in-game chat with the `!` prefix.

| Command | Description |
|---|---|
| `help` | List the available commands |
| `players` | List players currently online (available to everyone in chat) |
| `kick <name>` | Kick a player |
| `ban <name>` | Ban by name (persisted) and kick if online |
| `unban <name>` | Remove a name ban |
| `whitelist add\|remove <name>` | Edit the whitelist |
| `whitelist on\|off` | Enable or disable whitelist enforcement |
| `whitelist` | Show the whitelist |
| `admin add\|remove <name>` | Edit the admin list (`admin` alone shows it) |
| `backup` | Take a backup now |
| `restart` | Restart the game server (takes a backup first if `backup.on_stop` is on) |
| `stop` / `shutdown` | Stop the game server and shut the manager down (same backup behaviour) |
| `say <text>` | Broadcast a message in game |
| anything else | Passed to the game console unchanged |

Chat commands other than `help` and `players` are limited to admins.

## Configuration

`config.json` is created on first run and stores only your overrides; defaults live in the code. It sits next to the
script when run from a checkout, and in `~/.config/craftopia-server-manager` (Linux) or
`%APPDATA%\CraftopiaServerManager` (Windows) when installed. Set `CSM_HOME` to use a different folder.

| Key | Default | Description |
|---|---|---|
| `install_dir` | Steam `CraftopiaDedicatedServer` folder | Server install path |
| `data_dir` | `data` next to the config | Whitelist, admins, bans, backups, logs and the pinned save folder |
| `extra_args` | `["-batchmode", "-nographics", "-logFile", "-"]` | Extra arguments passed to the game executable |
| `api.enabled` | `true` | Enable the HTTP API |
| `api.host` / `api.port` | `127.0.0.1` / `27700` | API bind address and port |
| `api.token` | random, generated on first run | Bearer token required by the API |
| `backup.interval_min` | `30` | Minutes between backups (`0` disables) |
| `backup.keep` | `24` | Number of backups to retain |
| `backup.on_stop` | `true` | Take a backup when the server stops |
| `restart.every_hours` | `0` | Scheduled restart interval in hours (`0` disables) |
| `restart.warn_min` | `[5, 1]` | Minutes before a scheduled restart at which players are warned |
| `restart.crash_delay_s` | `10` | Seconds to wait before restarting after a crash |
| `whitelist_enabled` | `false` | Kick players who are not on the whitelist |
| `chat_prefix` | `!` | Prefix for in-game chat commands |
| `poll_s` | `10` | Seconds between player-list polls |
| `discord_webhook` | empty | Webhook URL for event notifications |

## Remote API

All requests need the header `Authorization: Bearer <token>`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/status` | JSON with `ready`, `uptime_s`, `players` and `whitelist_enabled` |
| `GET` | `/logs` | Last 100 log lines |
| `POST` | `/command` | Run a command, body `{"command": "..."}` |

## Known limitations

- **Player list format is verified against a real join.** `list` prints CSV (`playerId,name`, rows such as
  `800,"Kisaragi"`). The name is empty until the client finishes joining, and such rows are ignored. Join and leave
  detection relies on this format.
- **In-game chat commands need the bundled plugin.** The stock server never logs player chat, because it travels over
  the `OcNetRpc_Chat` RPC. `./install_plugin.sh` unpacks BepInEx into the server and builds `plugin/`, which prints
  `[Chat] <playerId>: <text>` to stdout. The manager then launches the server through `run_bepinex.sh`
  automatically, and messages starting with `!` are hidden from other players. The plugin is installed and its hook
  is confirmed to load, but end-to-end chat has not been verified with a real player, and the chat sender id is
  assumed to equal the `list` playerId.
- **Whitelist and ban enforcement is untested against a non-whitelisted player.** It is built on the verified `list`
  format but has not yet been exercised in a real session.
- **Players are matched by display name.** The console exposes no stable account id, so names can be impersonated.
- **World loading is slow.** It takes 2 to 3 minutes. The manager treats the server as ready on the "World is loaded" line.

## Development

```bash
python3 -m unittest      # tests in test_craftopia_server.py
./install_plugin.sh      # unpack BepInEx into the server and build plugin/
```

## License

Released under the [MIT License](LICENSE). Visitor counter by [Moe Counter](https://github.com/journey-ad/Moe-Counter).
