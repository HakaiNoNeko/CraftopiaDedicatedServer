#!/usr/bin/env bash
# Builds release payloads into build/: pinned BepInEx for linux+win, and the plugin DLL. Used by CI and locally.
set -euo pipefail
cd "$(dirname "$0")/.."
BEP=5.4.23.6
declare -A SHA=( [linux_x64]=f8ac87a97fb1ef85451c04ace1fddb7dd7eb0b079c179b989d6bc462c98bd365
                 [win_x64]=6c57a714a892efb4e9e1fef63d608a3391f30ec984031c465404e4ee381a0755 )
mkdir -p build
for plat in linux_x64 win_x64; do
  zip="build/BepInEx_${plat}_${BEP}.zip"
  [ -f "$zip" ] || curl -fsSL -o "$zip" "https://github.com/BepInEx/BepInEx/releases/download/v${BEP}/BepInEx_${plat}_${BEP}.zip"
  echo "${SHA[$plat]}  $zip" | sha256sum -c -
  rm -rf "build/bepinex-$plat"; mkdir -p "build/bepinex-$plat"
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$zip" "build/bepinex-$plat"
done
# plugin only reads BepInEx.dll/0Harmony.dll from ServerDir; the Deploy step copies the DLL into its plugins folder
dotnet build -c Release plugin -p:ServerDir="$PWD/build/bepinex-linux_x64"
cp plugin/bin/Release/netstandard2.1/CraftopiaServerChat.dll build/
