# Vigilia

Terror psicologico fotorrealista en primera persona. Unreal Engine 5.8, macOS (Apple Silicon, Metal SM6) y Windows (DX12 SM6).
Primera entrega: un salon de vivienda de los anos 90 completamente jugable.

## Puesta en marcha (un comando)

```bash
./Tools/setup_mac.sh
```

Descarga los assets CC0 de respaldo, compila el modulo C++ y abre el editor construyendo el nivel
`/Game/Vigilia/Maps/L_LivingRoom`. En Windows: `Tools\setup_windows.bat`.

Requisitos: UE 5.8 (Epic Games Launcher), Xcode 26.0-26.3 (26.4 no es compatible con UE 5.8), Python 3.

## Assets de Megascans

La habitacion se construye sola con modelos CC0 de Poly Haven y **se actualiza a Megascans** en cuanto los
anades al proyecto con el plugin de Fab (Window > Fab > My Library > Add to Project). Lista con enlaces en
[ASSETS.md](ASSETS.md). Despues vuelve a ejecutar `Scripts/build_room.py` (Tools > Execute Python Script).
El informe `Saved/Vigilia/asset_report.md` dice que usa cada hueco y que falta.

## Controles

| Accion | Tecla |
|---|---|
| Moverse | WASD |
| Mirar | Raton |
| Correr | Mayus izq. |
| Interactuar / coger / dejar | E o clic izquierdo |
| Dejar objeto examinado | Q o clic derecho |
| Linterna | F |

Consola: `VGSetSensitivity 0.8`, `VGInvertY 1`.

## Estructura

```
Source/Vigilia/      C++: personaje, interaccion (interfaz + componente), puerta, lampara, TV, examinables, eventos, audio
Scripts/             Pipeline del editor en Python: resolucion de assets, materiales, construccion del nivel
  asset_manifest.json    huecos de la escena y sus fuentes (Fab primero, Poly Haven de respaldo)
  layout_overrides.json  ajustes manuales guardados con save_layout.py
Tools/               setup, descarga de assets, generacion de recursos procedurales, empaquetado
SourceAssets/        audio sintetizado, ruido del CRT, malla de cortina, tus fotos (Photos/)
Config/              ajustes comunes + Mac/ y Windows/ por plataforma
```

## Iterar

- Mueve o gira cualquier actor `VG_*` y ejecuta `Scripts/save_layout.py`: la proxima reconstruccion lo respeta.
- Pon fotos `.jpg` en `SourceAssets/Photos/` y reconstruye: se asignan a los marcos.
- Lo que anadas a mano al nivel (sin la etiqueta `VG`) no se toca al reconstruir.
