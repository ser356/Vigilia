# Mansion: alcance y comprobacion en Unreal

## Direccion

Casa grande habitada y envejecida, no castillo ni hospital: parquet, papel pintado, carpinteria,
libros, mobiliario domestico y luz fria que entra por ventanas. La referencia de Visage se aplica
a la escala, los encuadres de puertas y la incertidumbre, sin copiar su plano ni sus assets.

La construccion nueva usa tres cotas (-300, 0 y 300 cm), doce habitaciones, galerias de 220 cm
y una caja de escaleras de dos tramos por nivel. El ala domestica anterior sigue al oeste.
La escalera tiene contrahuellas de 15 cm, huellas de 28 cm y dos tramos de 170 cm de anchura.
Las losas tienen aberturas y los peldanos son de 20 cm de espesor: no son bloques que rellenen
todo el volumen y obstruyan la escalera de abajo.

El mapa generado se llama `L_Mansion`. El mapa binario antiguo sigue en el repositorio;
el nuevo se genera al ejecutar el constructor con Unreal. El cambio de codigo por si solo
no contiene un `.umap` nuevo ni assets de Fab recien descargados.

## Luz

Todas las lamparas y el CRT empiezan apagados; la linterna empieza encendida y puede apagarse
con F. Los interruptores de las nuevas habitaciones y galerias permiten encender luz local.
Las ventanas tienen aberturas fisicas, marcos, cristal sin sombra opaca y focos exteriores con
sombras. Los focos tienen distancia de dibujado limitada. La exposicion se mantiene entre
EV100 -1 y 1 con compensacion -0,2; estos son valores iniciales que necesitan ajuste visual.

Se han reducido niebla, grano, aberracion y vineta para no ocultar materiales ni detalle util.
El resultado no debe juzgarse solo por la vista previa del editor con exposicion automatica.

## Presencia

Una sola entidad, sin corredor ni perseguidor adicionales. Usa un personaje de terror importado,
con idle perteneciente exactamente a su esqueleto, presentado como silueta. No utiliza una
estatua ni un maniqui cuando no hay personaje valido. La seleccion y los faltantes aparecen
en el informe de assets. No es un modelo de personaje nuevo.

Guardas en C++ (tambien protegen secuencias de mapas antiguos): minimo 300 s de partida,
8 m de distancia al aparecer, misma planta y 120 s entre manifestaciones. No se materializa
en una zona visible del encuadre. Se retira al acercarse a 6 m, tras mirarla de frente durante
1 s o, como maximo, a los 5 s. En el mapa nuevo se solicitan 4 s. No gira continuamente para
seguir al jugador. No se fuerza la averia de linterna ni se programa una persecucion.

## Pruebas realizadas aqui

- Compilacion de sintaxis de todos los scripts Python.
- Cuatro pruebas de estructura: habitaciones, galeria-rellanos, conexion oeste y altura libre
  de ambos tramos y su giro, para un personaje de 178 cm y 52 cm de diametro.
- Revision de diferencias y espacios (`git diff --check`).

Estas pruebas ejecutan el generador con una API de editor simulada, sin modelos importados.
No comprueban APIs reales de Unreal, compilacion C++, materiales, orientacion de mallas ni FPS.

## Comprobacion pendiente en el Mac

1. Cerrar Unreal y ejecutar `./Tools/setup_mac.sh` desde esta rama. Compila C++ y genera el mapa.
2. Revisar `Saved/Vigilia/asset_report.md`; resolver ausencias desde Window > Fab si procede,
   con calidad Medium, y ejecutar de nuevo `Scripts/build_room.py`.
3. En Play, comprobar que todas las bombillas y el CRT estan apagados, que F funciona y que
   cada interruptor ilumina su estancia. La ventana debe dibujar luz sin atravesar tabiques.
4. Recorrer ala antigua, doce habitaciones, dos rellanos intermedios y los tres niveles.
   Comprobar puertas con su malla real, giros, muebles, suelo y techo. Las pruebas estructurales
   no detectan que un armario importado tenga un tamano o una colision inesperados.
5. Antes de 300 s no debe aparecer ninguna entidad. Despues, volver al extremo oeste de una
   galeria; la aparicion se puede omitir si la zona de destino esta en pantalla o demasiado cerca.
   No debe haber persecucion ni otra aparicion en los siguientes 120 s.
6. Medir FPS en Play en las tres plantas, con luces apagadas y encendidas; ajustar luces y
   exposicion segun el resultado. No se ha medido rendimiento del M4 en este entorno.

Esta entrega deja una base construible y revisable. La aprobacion artistica exige capturas y una
pasada en Unreal; no se declara acabado fotorrealista ni equivalencia visual con Visage.
