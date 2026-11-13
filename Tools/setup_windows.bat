@echo off
rem Vigilia - preparacion completa en Windows (DirectX 12). Uso: Tools\setup_windows.bat
rem Define UE_ROOT si Unreal no esta en la ruta por defecto.
setlocal
set "PROJECT_DIR=%~dp0.."
if "%UE_ROOT%"=="" set "UE_ROOT=C:\Program Files\Epic Games\UE_5.8"
if not exist "%UE_ROOT%\Engine" (
  echo ERROR: no encuentro Unreal Engine en "%UE_ROOT%". Define UE_ROOT.
  exit /b 1
)
echo [1/3] Descargando assets CC0 de Poly Haven
python "%PROJECT_DIR%\Tools\fetch_polyhaven.py" || exit /b 1
echo [2/3] Compilando VigiliaEditor (Development, Win64)
call "%UE_ROOT%\Engine\Build\BatchFiles\Build.bat" VigiliaEditor Win64 Development -project="%PROJECT_DIR%\Vigilia.uproject" -waitmutex || exit /b 1
echo [3/3] Abriendo el editor y construyendo el salon
start "" "%UE_ROOT%\Engine\Binaries\Win64\UnrealEditor.exe" "%PROJECT_DIR%\Vigilia.uproject" -ExecutePythonScript="%PROJECT_DIR%\Scripts\build_room.py" -log
endlocal
