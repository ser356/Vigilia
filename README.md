# Vigilia

Terror psicologico fotorrealista en primera persona. Unreal Engine 5.8, macOS (Apple Silicon, Metal SM6) y Windows (DX12 SM6).
Casa domestica de terror con sotano, planta baja y planta superior. El ala original se conserva conectada a una galeria de doce estancias nuevas, con escaleras fisicas entre niveles.

## Puesta en marcha (un comando)

```bash
./Tools/setup_mac.sh
```

Descarga los assets CC0 de respaldo, compila el modulo C++ y abre el editor construyendo el nivel
`/Game/Vigilia/Maps/L_Mansion`. En Windows: `Tools\setup_windows.bat`.

Requisitos: UE 5.8 (Epic Games Launcher), Xcode 26.0-26.3 (26.4 no es compatible con UE 5.8), Python 3.

## Assets de Megascans

La casa se construye sola con modelos CC0 de Poly Haven y **se actualiza a Megascans** en cuanto los
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
- Pon fotos `.jpg` en `SourceAssets/Photos/` y reconstruye: se asignan a los marcos (ver `SourceAssets/Photos/LEEME.txt`).
- Lo que anadas a mano al nivel (sin la etiqueta `VG`) no se toca al reconstruir.

## Mansion y ritmo de terror

- Mapa nuevo: `L_Mansion`; no se sobrescribe el antiguo `L_LivingRoom`.
- Ala principal de 15,7 x 16 m por planta: biblioteca, sala de estar, comedor y despacho;
  dormitorios, cuarto infantil y bano arriba; archivo, taller, lavanderia y almacen abajo.
- Todas las bombillas y el CRT empiezan apagados. La linterna empieza encendida (`F`);
  interruptores junto a las puertas controlan luces locales. Ventanas reales reciben luz exterior fria.
- Una presencia animada, sin estatua/maniqui de respaldo: primera aparicion posible a los 300 s,
  distancia minima 8 m, pausa global de 120 s. No aparece en el encuadre, dura como maximo 5 s
  y se retira al acercarse o al mirarla fijamente. Las persecuciones estan desactivadas.
- Las galerias requieren volver a entrar en su extremo oeste para intentar una aparicion.
  El tiempo por si solo no la fuerza. Si no existe un personaje de terror con idle del mismo
  esqueleto, se mantiene solo la tension sonora; el informe indica la ausencia.

La referencia es la escala domestica, las vistas parciales y el ritmo de Visage. Esta version es
una base generada: no se ha certificado equivalencia visual con Visage. Las ventanas, molduras,
librerias y escaleras son procedurales; el mobiliario usa los modelos gratuitos del manifiesto.
No se han descargado aqui recursos privados de tu cuenta de Epic ni se ha sustituido el modelo
por un personaje nuevo. La presencia existente se presenta como silueta animada distante.

## Validacion

```bash
python3 -m unittest discover -s Tests -v
python3 -m compileall -q Scripts Tools
```

Las pruebas comprueban soporte, altura libre en ambos tramos y rellanos, accesos de las doce
habitaciones y conexion con el ala original. No verifican materiales, orientacion de assets,
colisiones de modelos importados ni rendimiento GPU. Hay que compilar con UE 5.8 y recorrer
`L_Mansion` en Play para aprobar el resultado visual. Vease [MANSION_REVIEW.md](MANSION_REVIEW.md).
