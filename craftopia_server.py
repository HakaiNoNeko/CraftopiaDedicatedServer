#!/usr/bin/env python3
"""Craftopia server manager: supervises the stock dedicated server and adds
backups, whitelist, admins, in-game chat commands, scheduled restarts and a
remote HTTP API. Stdlib only. Usage: craftopia_server.py [run|ctl <command...>]"""
import json, os, re, shutil, signal, sqlite3, subprocess, sys, tarfile, tempfile
import threading, time, urllib.request
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULTS = {
    "install_dir": str(Path.home() / ".local/share/Steam/steamapps/common/CraftopiaDedicatedServer"),
    "data_dir": str(HERE / "data"),          # whitelist/admins/bans/backups/logs live here
    "extra_args": ["-batchmode", "-nographics", "-logFile", "-"],
    "api": {"enabled": True, "host": "127.0.0.1", "port": 27700, "token": ""},
    "backup": {"interval_min": 30, "keep": 24, "on_stop": True},
    "restart": {"every_hours": 0, "warn_min": [5, 1], "crash_delay_s": 10},
    "whitelist_enabled": False,
    "chat_prefix": "!",
    "poll_s": 10,
    "discord_webhook": "",
    # Output formats could not be verified without a connected client; adjust to your log
    # if joins/chat are not detected. Named groups: id, name (players); name, msg (chat).
    "player_regex": r"^\s*\[?(?P<id>\d+)\]?[\s:,\-]+(?P<name>[^\s,].*?)\s*$",
    "chat_regex": r"^\[?(?:Chat|Say)\]?\s*[\[<]?(?P<name>[^\]>:]+)[\]>:]\s*(?P<msg>.+)$",
}
NOISE = re.compile(r"mesh data|Convex Mesh|referenced script|Register NetworkObject|^\s*$")


def load_config(path):
    cfg = json.loads(json.dumps(DEFAULTS))
    if path.exists():
        for k, v in json.loads(path.read_text()).items():
            cfg[k].update(v) if isinstance(v, dict) and isinstance(cfg.get(k), dict) else cfg.__setitem__(k, v)
    else:
        cfg["api"]["token"] = os.urandom(16).hex()
        path.write_text(json.dumps(cfg, indent=2))
    return cfg


class Store:
    """Small JSON-list files (whitelist/admins). Names are matched case-insensitively."""
    def __init__(self, path): self.path, self.lock = Path(path), threading.Lock()
    def items(self):
        try: return json.loads(self.path.read_text())
        except FileNotFoundError: return []
    def has(self, name): return name.lower() in (n.lower() for n in self.items())
    def add(self, name):
        with self.lock:
            if not self.has(name): self.path.write_text(json.dumps(self.items() + [name], indent=1))
    def remove(self, name):
        with self.lock:
            self.path.write_text(json.dumps([n for n in self.items() if n.lower() != name.lower()], indent=1))


def save_dir_of(install):
    """The game concatenates savePath onto the install dir without a separator (stock bug),
    so we pin an absolute path in ServerSetting.ini and use the same one for backups."""
    ini = Path(install) / "ServerSetting.ini"
    m = re.search(r"^savePath=(.*)$", ini.read_text(), re.M) if ini.exists() else None
    p = Path(m.group(1).strip()) if m else Path(install) / "DedicatedServerSave"
    return p if p.is_absolute() else Path(install) / p


def make_backup(save_dir, backup_dir, keep):
    """Consistent snapshot: .db files go through SQLite's online backup API (the server is
    writing them), everything else is copied. Returns the archive path."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for src in save_dir.rglob("*"):
            if src.is_dir() or "Backup" in src.relative_to(save_dir).parts[:1]: continue
            dst = Path(tmp) / src.relative_to(save_dir)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.suffix == ".db":
                s, d = sqlite3.connect(f"file:{src}?mode=ro", uri=True), sqlite3.connect(dst)
                with d: s.backup(d)
                s.close(); d.close()
            else:
                shutil.copy2(src, dst)
        out = backup_dir / f"craftopia-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"
        with tarfile.open(out, "w:gz") as t: t.add(tmp, arcname="save")
    for old in sorted(backup_dir.glob("craftopia-*.tar.gz"))[:-keep]: old.unlink()
    return out


class Manager:
    def __init__(self, cfg):
        self.cfg, self.install = cfg, Path(cfg["install_dir"])
        self.data = Path(cfg["data_dir"]); self.data.mkdir(parents=True, exist_ok=True)
        self.whitelist, self.admins = Store(self.data / "whitelist.json"), Store(self.data / "admins.json")
        self.bans = Store(self.data / "bans.json")  # banned player names (the game itself only bans IPs)
        self.log = open(self.data / "server.log", "a", buffering=1)
        self.tail = deque(maxlen=500)
        self.proc, self.ready, self.stopping, self.restart_req = None, False, False, False
        self.players, self.capture = {}, None
        self.player_re, self.chat_re = re.compile(cfg["player_regex"]), re.compile(cfg["chat_regex"])
        self.started_at = 0

    # ---- process I/O
    def send(self, line):
        if self.proc and self.proc.poll() is None:
            self.proc.stdin.write(line + "\n"); self.proc.stdin.flush()

    def say(self, msg): self.send("say " + msg)

    def notify(self, msg):
        self.log.write(f"[manager] {msg}\n")
        if self.cfg["discord_webhook"]:
            try:
                urllib.request.urlopen(urllib.request.Request(self.cfg["discord_webhook"],
                    json.dumps({"content": msg}).encode(), {"Content-Type": "application/json"}), timeout=5)
            except Exception: pass

    def on_line(self, line):
        if NOISE.search(line): return
        self.log.write(line + "\n"); self.tail.append(line); print(line, flush=True)
        if self.capture is not None: self.capture.append(line)
        m = self.chat_re.match(line)
        if m and m["msg"].startswith(self.cfg["chat_prefix"]):
            threading.Thread(target=self.chat_command, args=(m["name"].strip(), m["msg"].strip()), daemon=True).start()

    def check_ready(self):
        # "World is loaded!" is written to Unity's player log only, never to stdout.
        logs = sorted((Path.home() / ".config/unity3d/PocketPair/Craftopia/Logs_DS").glob("PlayerLog_*.log"))
        if logs and logs[-1].stat().st_mtime >= self.started_at and "World is loaded" in logs[-1].read_bytes().decode("utf-16", "ignore"):
            self.ready = True; self.notify("Server is up")

    def reader(self, proc):
        for line in proc.stdout: self.on_line(line.rstrip("\n"))

    # ---- game-side admin actions
    def poll_players(self):
        self.capture = []
        self.send("list"); time.sleep(1.5)
        lines, self.capture = self.capture, None
        found = {}
        for l in lines:
            m = self.player_re.match(l)
            if m: found[m["id"]] = m["name"]
        for pid, name in found.items():
            if pid not in self.players: self.notify(f"{name} joined")
        for pid, name in self.players.items():
            if pid not in found: self.notify(f"{name} left")
        self.players = found
        for pid, name in found.items():
            if self.bans.has(name) or (self.cfg["whitelist_enabled"] and not self.whitelist.has(name) and not self.admins.has(name)):
                self.send(f"kick {pid}")
                self.notify(f"Refused {name} ({'banned' if self.bans.has(name) else 'not whitelisted'})")

    def find(self, who):
        who = who.lower()
        for pid, name in self.players.items():
            if who in (pid, name.lower()): return pid, name
        return None

    def backup(self):
        out = make_backup(save_dir_of(self.install), self.data / "backups", self.cfg["backup"]["keep"])
        self.notify(f"Backup written: {out.name}"); return out.name

    # ---- commands (shared by console, chat, HTTP)
    def run_command(self, line, admin=True):
        a = line.strip().split(maxsplit=2); cmd = a[0].lower() if a else ""
        arg = lambda i: a[i] if len(a) > i else ""
        user_cmds = {"help", "players"}
        if not admin and cmd not in user_cmds: return "Admins only."
        if cmd == "help": return "Commands: players, kick, ban, unban, whitelist, admin, backup, restart, say"
        if cmd == "players": return ", ".join(self.players.values()) or "No players online."
        if cmd in ("kick", "ban"):
            p = self.find(arg(1))
            if cmd == "ban" and arg(1): self.bans.add(p[1] if p else arg(1))
            if p: self.send(f"kick {p[0]}")
            return f"{cmd}: {p[1] if p else arg(1) + ' (offline; recorded)' if cmd == 'ban' else 'player not found'}"
        if cmd == "unban": self.bans.remove(arg(1)); return f"unbanned {arg(1)}"
        if cmd in ("whitelist", "admin"):
            store = self.whitelist if cmd == "whitelist" else self.admins
            op, name = arg(1).lower(), arg(2)
            if cmd == "whitelist" and op in ("on", "off"):
                self.cfg["whitelist_enabled"] = op == "on"; return f"whitelist {op}"
            if op == "add" and name: store.add(name); return f"{cmd}: added {name}"
            if op == "remove" and name: store.remove(name); return f"{cmd}: removed {name}"
            return f"{cmd} list: {', '.join(store.items()) or '(empty)'}"
        if cmd == "backup": return "Backup: " + self.backup()
        if cmd == "restart": self.restart_req = True; self.stop_server(); return "Restarting."
        if cmd in ("stop", "shutdown"): self.stopping = True; self.stop_server(); return "Shutting down."
        if cmd == "say": self.say(line.split(maxsplit=1)[1] if len(a) > 1 else ""); return "sent"
        self.send(line); return "(sent to server console)"  # anything else goes straight to the game

    def chat_command(self, name, msg):
        admin = self.admins.has(name)
        reply = self.run_command(msg[len(self.cfg["chat_prefix"]):], admin)
        if cmd_is_chat_reply(reply): self.say(reply)

    # ---- lifecycle
    def stop_server(self):
        if self.cfg["backup"]["on_stop"]:
            try: self.say("Server stopping, saving..."); self.backup()
            except Exception as e: self.notify(f"Backup failed: {e}")
        self.send("stop")

    def scheduler(self):
        last_backup = last_poll = time.time(); b = self.cfg["backup"]; r = self.cfg["restart"]
        warned = set()
        while not self.stopping:
            time.sleep(1); now = time.time()
            if not self.ready: self.check_ready()
            if not self.ready: continue
            if b["interval_min"] and now - last_backup >= b["interval_min"] * 60:
                last_backup = now
                try: self.backup()
                except Exception as e: self.notify(f"Backup failed: {e}")
            if now - last_poll >= self.cfg["poll_s"]:
                last_poll = now; self.poll_players()
            if r["every_hours"]:
                left = self.started_at + r["every_hours"] * 3600 - now
                for w in r["warn_min"]:
                    if left <= w * 60 and w not in warned: warned.add(w); self.say(f"Restarting in {w} min")
                if left <= 0: warned.clear(); self.run_command("restart")

    def pin_save_path(self):
        ini = self.install / "ServerSetting.ini"
        if ini.exists():
            want = f"savePath={self.data / 'save'}/"
            ini.write_text(re.sub(r"^savePath=.*$", lambda _: want, ini.read_text(), flags=re.M))

    def serve(self):
        self.pin_save_path()
        threading.Thread(target=self.scheduler, daemon=True).start()
        if self.cfg["api"]["enabled"]: start_api(self)
        threading.Thread(target=lambda: [self.run_command(l) for l in sys.stdin], daemon=True).start()
        for s in (signal.SIGINT, signal.SIGTERM): signal.signal(s, lambda *_: self.run_command("shutdown"))
        while not self.stopping:
            self.ready, self.restart_req, self.players = False, False, {}
            self.proc = subprocess.Popen([str(self.install / "Craftopia.x86_64"), *self.cfg["extra_args"]],
                cwd=self.install, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            self.started_at = time.time()
            threading.Thread(target=self.reader, args=(self.proc,), daemon=True).start()
            self.proc.wait()
            if self.stopping: break
            if not self.restart_req:
                self.notify(f"Server exited with code {self.proc.returncode}; restarting")
                time.sleep(self.cfg["restart"]["crash_delay_s"])


def cmd_is_chat_reply(reply): return bool(reply) and not reply.startswith("(")


def start_api(mgr):
    token = mgr.cfg["api"]["token"]

    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def _auth(self):
            if self.headers.get("Authorization") == f"Bearer {token}" and token: return True
            self._send(401, {"error": "unauthorized"}); return False
        def do_GET(self):
            if not self._auth(): return
            if self.path == "/status":
                self._send(200, {"ready": mgr.ready, "uptime_s": int(time.time() - mgr.started_at), "players": list(mgr.players.values()),
                                 "whitelist_enabled": mgr.cfg["whitelist_enabled"]})
            elif self.path == "/logs": self._send(200, {"lines": list(mgr.tail)[-100:]})
            else: self._send(404, {"error": "not found"})
        def do_POST(self):
            if not self._auth(): return
            if self.path != "/command": return self._send(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length", 0))
            self._send(200, {"result": mgr.run_command(json.loads(self.rfile.read(n))["command"])})
        def log_message(self, *a): pass

    srv = ThreadingHTTPServer((mgr.cfg["api"]["host"], mgr.cfg["api"]["port"]), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def ctl(cfg, words):
    req = urllib.request.Request(f"http://{cfg['api']['host']}:{cfg['api']['port']}/command",
        json.dumps({"command": " ".join(words)}).encode(), {"Authorization": f"Bearer {cfg['api']['token']}"})
    print(json.loads(urllib.request.urlopen(req, timeout=60).read())["result"])


if __name__ == "__main__":
    cfg = load_config(HERE / "config.json")
    if len(sys.argv) > 1 and sys.argv[1] == "ctl": ctl(cfg, sys.argv[2:])
    else: Manager(cfg).serve()
