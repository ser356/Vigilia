#!/usr/bin/env bash
# Empaqueta el juego. Uso: ./Tools/package.sh Mac   |   en Windows: usar RunUAT.bat con -platform=Win64
set -euo pipefail
PLATFORM="${1:-Mac}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UE_ROOT="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
"$UE_ROOT/Engine/Build/BatchFiles/RunUAT.sh" BuildCookRun -project="$PROJECT_DIR/Vigilia.uproject" \
  -platform="$PLATFORM" -clientconfig=Development -build -cook -stage -pak -archive \
  -archivedirectory="$PROJECT_DIR/Build/$PLATFORM" -nop4 -utf8output
