#!/usr/bin/env bash
# Installs BepInEx (Linux x64, Mono) into the dedicated server and builds+deploys the chat plugin.
set -euo pipefail
SERVER="${SERVER_DIR:-$HOME/.local/share/Steam/steamapps/common/CraftopiaDedicatedServer}"
VER=v5.4.23.6
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
if [ ! -f "$SERVER/BepInEx/core/BepInEx.dll" ]; then
  gh release download "$VER" -R BepInEx/BepInEx -p 'BepInEx_linux_x64_*.zip' -D "$TMP"
  unzip -q -o "$TMP"/BepInEx_linux_x64_*.zip -d "$SERVER"
  chmod +x "$SERVER/run_bepinex.sh"
fi
export PATH="$HOME/.dotnet:$PATH" DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
dotnet build -c Release "$(dirname "$0")/plugin" -p:ServerDir="$SERVER"
