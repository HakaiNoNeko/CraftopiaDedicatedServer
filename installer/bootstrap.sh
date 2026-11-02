#!/usr/bin/env bash
# One-line installer:  curl -fsSL https://github.com/HakaiNoNeko/CraftopiaDedicatedServer/releases/latest/download/install.sh | bash -s -- [server dir] [--service]
set -euo pipefail
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
curl -fsSL https://github.com/HakaiNoNeko/CraftopiaDedicatedServer/releases/latest/download/craftopia-server-manager-linux.tar.gz | tar xz -C "$TMP"
"$TMP/craftopia-server-manager/install.sh" "$@"
