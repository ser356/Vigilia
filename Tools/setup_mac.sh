#!/usr/bin/env bash
# Vigilia - preparacion completa en macOS (Apple Silicon) con un solo comando:
#   1) descarga los assets CC0 de respaldo (Poly Haven)
#   2) compila el modulo C++ del juego
#   3) abre el editor y construye el salon automaticamente
#
# Uso:  ./Tools/setup_mac.sh            (detecta Unreal en /Users/Shared/Epic Games)
#       UE_ROOT="/ruta/a/UE_5.8" ./Tools/setup_mac.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPROJECT="$PROJECT_DIR/Vigilia.uproject"

if [[ -z "${UE_ROOT:-}" ]]; then
  for candidate in "/Users/Shared/Epic Games/UE_5.8" "/Users/Shared/Epic Games"/UE_5.*; do
    if [[ -d "$candidate/Engine" ]]; then UE_ROOT="$candidate"; break; fi
  done
fi
if [[ -z "${UE_ROOT:-}" || ! -d "$UE_ROOT/Engine" ]]; then
  echo "ERROR: no encuentro Unreal Engine. Instala UE 5.8 desde Epic Games Launcher o define UE_ROOT." >&2
  exit 1
fi
echo "==> Unreal Engine: $UE_ROOT"

if ! xcodebuild -version >/dev/null 2>&1; then
  echo "ERROR: hace falta Xcode completo (no solo Command Line Tools). UE 5.8 pide Xcode 26.0-26.3 (26.4 no es compatible)." >&2
  exit 1
fi
xcodebuild -version | head -1

echo "==> [1/3] Descargando assets CC0 de Poly Haven"
python3 "$PROJECT_DIR/Tools/fetch_polyhaven.py"

echo "==> [2/3] Compilando VigiliaEditor (Development, Mac)"
"$UE_ROOT/Engine/Build/BatchFiles/Mac/Build.sh" VigiliaEditor Mac Development -project="$UPROJECT" -waitmutex

echo "==> [3/3] Abriendo el editor y construyendo el salon (la primera vez compila shaders: paciencia)"
EDITOR="$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
"$EDITOR" "$UPROJECT" -ExecutePythonScript="$PROJECT_DIR/Scripts/build_room.py" -log &
echo
echo "Editor lanzado. Cuando termine veras el nivel L_LivingRoom: pulsa Play (Alt+P)."
echo "Informe de assets usados y pendientes: $PROJECT_DIR/Saved/Vigilia/asset_report.md"
