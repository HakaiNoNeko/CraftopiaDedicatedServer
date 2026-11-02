#!/usr/bin/env bash
# Craftopia Server Manager installer (Linux). Usage: ./install.sh [path/to/CraftopiaDedicatedServer] [--service]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SERVER=""; SERVICE=0
for a in "$@"; do case "$a" in --service) SERVICE=1;; *) SERVER="$a";; esac; done
SERVER="${SERVER:-$HOME/.local/share/Steam/steamapps/common/CraftopiaDedicatedServer}"
[ -x "$SERVER/Craftopia.x86_64" ] || { echo "Craftopia dedicated server not found at: $SERVER"; echo "Install it from Steam (Craftopia Dedicated Server) or pass its folder as the first argument."; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))' || { echo "Python 3.8+ is required"; exit 1; }

echo "Installing BepInEx + chat plugin into $SERVER"
cp -r "$HERE/bepinex/." "$SERVER/"
chmod +x "$SERVER/run_bepinex.sh"
mkdir -p "$SERVER/BepInEx/plugins"
cp "$HERE/CraftopiaServerChat.dll" "$SERVER/BepInEx/plugins/"

APP="$HOME/.local/share/craftopia-server-manager"; CFG="$HOME/.config/craftopia-server-manager"
mkdir -p "$APP" "$CFG" "$HOME/.local/bin"
cp "$HERE/craftopia_server.py" "$APP/"
if [ ! -f "$CFG/config.json" ]; then
  TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
  python3 - "$CFG/config.json" "$SERVER" "$TOKEN" <<'PY'
import json, sys
json.dump({"install_dir": sys.argv[2], "api": {"token": sys.argv[3]}}, open(sys.argv[1], "w"), indent=2)
PY
  chmod 600 "$CFG/config.json"
fi
cat > "$HOME/.local/bin/craftopia-server" <<LAUNCH
#!/usr/bin/env bash
export CSM_HOME="$CFG"
exec python3 "$APP/craftopia_server.py" "\$@"
LAUNCH
chmod +x "$HOME/.local/bin/craftopia-server"

if [ "$SERVICE" = 1 ]; then
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/craftopia-server.service" <<UNIT
[Unit]
Description=Craftopia dedicated server (manager)
After=network-online.target

[Service]
ExecStart=$HOME/.local/bin/craftopia-server
Restart=on-failure
KillSignal=SIGINT
TimeoutStopSec=120

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload && systemctl --user enable --now craftopia-server.service
  echo "Service enabled. To keep it running without logging in: loginctl enable-linger $USER"
fi
cat <<MSG

Done.
  Start:   craftopia-server        (make sure ~/.local/bin is on your PATH)
  Config:  $CFG/config.json  (API token + settings)
  Game port: UDP 6587 - open it in your firewall/router to let others join.
MSG
