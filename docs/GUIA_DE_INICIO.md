# Guía de inicio de LoRaCAP

Esta guía lleva de un computador sin LoRaCAP hasta la capacidad de su propio
sitio. Supone que usted conoce LoRaWAN (spreading factors, data rates, RSSI,
ADR) y que nunca ha usado Python. Cada comando aparece completo y se escribe
tal como está.

Tiene dos partes. Primero se instala LoRaCAP y se corre el estudio de
ejemplo que trae, para ver cómo luce un resultado terminado y comprobar que
su instalación da las mismas cifras que cualquier otra. Después se arma el
estudio de su sitio en la página web de LoRaCAP, a partir de un contorno
dibujado en Google Earth y del RSSI que usted midió en campo.

El [README](../README.md), en inglés, explica cada opción a fondo. Esta guía
cubre solo lo que necesita un primer estudio y remite al README para el
resto. La versión en inglés de esta guía está en
[GETTING_STARTED.md](GETTING_STARTED.md).

LoRaCAP escribe en inglés sus archivos, sus figuras, `study.py` y los
mensajes del simulador. La página web se lee en los dos idiomas. Esta guía
da los rótulos de la página en español y los textos del simulador en inglés,
como usted los verá.

## 1. Instalar

### Python

LoRaCAP necesita Python 3.8 o posterior. Abra una terminal y revise qué
versión tiene:

- Windows: abra PowerShell y escriba `py --version`.
- macOS o Linux: abra Terminal y escriba `python3 --version`.

Si el comando no existe, o la versión es anterior a la 3.8, instale Python
desde [python.org](https://www.python.org/downloads/). En Windows, marque
"Add python.exe to PATH" en la primera pantalla del instalador.

Esta guía escribe cada comando como `python3 ...`. En Windows escriba
`py ...`, con el resto de la línea igual.

### LoRaCAP

En [github.com/wilcashe/loracap](https://github.com/wilcashe/loracap), el
botón verde "Code" ofrece "Download ZIP". Descomprímalo donde prefiera. La
última versión numerada también está en la página Releases del mismo sitio.

En la terminal, entre a la carpeta descomprimida. La carpeta correcta es la
que contiene `run.py`:

```bash
cd ruta/a/loracap
```

Todos los comandos de esta guía se escriben desde esa carpeta.

### La biblioteca de figuras

La simulación no necesita nada aparte de Python. Dibujar las figuras
necesita una biblioteca, matplotlib:

```bash
python3 -m pip install -r requirements.txt
```

Algunas distribuciones de Linux rechazan esta orden con un mensaje sobre un
"externally managed environment". En ese caso cree un entorno propio para
LoRaCAP dentro de su carpeta e instale ahí:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Vuelva a escribir `source .venv/bin/activate` cada vez que abra una
terminal nueva. Sin matplotlib cada cifra se calcula y se guarda igual, y
los comandos avisan que no se dibujó ninguna figura.

### Comprobar la instalación

```bash
python3 run.py test
```

Esta orden corre 682 pruebas del simulador en unos veinte segundos. Las
últimas líneas deben decir `OK` y "The fast checks pass". Si alguna prueba
falla, deténgase ahí. Un resultado salido de una instalación dañada no es
confiable.

## 2. Correr el ejemplo

LoRaCAP trae tres estudios. Para verlos:

```bash
python3 run.py list
```

`iot4cows` es un despliegue de monitoreo de ganado en Guamal, Meta,
Colombia: un gateway, un sitio de 88.5 ha, US915 y nodos en SF7, SF8 o SF9.
Antes de correr cualquier estudio, revíselo:

```bash
python3 run.py check iot4cows
```

`check` no simula nada. Lee el estudio y dice lo que encontró: la banda, el
data rate de cada spreading factor, la longitud del frame en el aire, el
área del sitio y hasta dónde llega cada spreading factor. Para este estudio
dice, entre otras cosas:

```
SF9 reaches 3096 m (an extrapolation: the measurements stop at 2210 m),
well beyond the site's 958 m. Range is not the binding constraint here.
```

Es decir, SF9 llega a 3096 m, más allá de los 958 m del sitio, aunque esa
cifra extrapola el modelo, porque las mediciones terminan en 2210 m.
También imprime una advertencia: el modelo de propagación de este estudio
no tiene shadowing. Así se publicó el estudio, y el README discute qué
cambia el shadowing. Lea cada advertencia que `check` dé sobre su propio
estudio. Un parámetro equivocado no hace fallar la simulación. Hace que
devuelva una respuesta equivocada sin quejarse.

Ahora córralo:

```bash
python3 run.py run iot4cows
```

Simula 81 puntos (3 escenarios por 27 cantidades de nodos), con 30
ejecuciones cada uno, e imprime una línea por punto. En el computador donde
se comprobó esta guía tardó menos de dos minutos. Al final imprime:

```
Capacity at DER = 0.9

  Scenario      Nodes            95% CI
  SF7            88.0      [87.1, 89.1]
  SF8            49.9      [49.3, 50.5]
  SF9            26.3      [25.6, 27.1]
```

Usted debe obtener exactamente estas cifras. El estudio fija su semilla
aleatoria, así que cualquier computador con una instalación sana las
reproduce. Si las suyas difieren, algo anda mal en la instalación, y
`python3 run.py test` es el punto de partida.

La tabla se lee así. Con todos los nodos en SF8, un payload de 32 bytes y un
reporte cada 15 segundos, el gateway recibe al menos el 90 % de los paquetes
enviados hasta unos 50 nodos. El intervalo entre corchetes es el intervalo
de confianza del 95 % de ese cruce, calculado por bootstrap sobre las 30
ejecuciones. Mide la incertidumbre de la propia simulación, no la del
modelo que hay detrás.

La ejecución escribió sus archivos en `studies/iot4cows/outputs/`:

| Archivo | Qué contiene |
|---|---|
| `results.json` | cada punto y cada ejecución, con la configuración completa del estudio |
| `capacity.json` | las capacidades de la tabla anterior |
| `results.csv` | los mismos puntos, para una hoja de cálculo |
| `iot4cows_capacity.png` (también `.pdf` y `.svg`) | la DER frente a la cantidad de nodos, una curva por escenario |
| `iot4cows_capacity_site_map.png` | dónde quedan los nodos de una ejecución, coloreados por spreading factor |
| `site_map.json` | la colocación de la que se dibuja el mapa |

Las cifras que cita el README salen de los experimentos de
`studies/iot4cows/experiments.py`, cuyas salidas viven en subcarpetas de
`outputs/`. Un `run` sencillo nunca las sobrescribe.

## 3. Preparar sus datos

El estudio de su sitio necesita tres cosas: la posición del gateway, el
contorno del área que cubren los nodos y un modelo de propagación. Las dos
primeras salen de un mapa. La tercera es lo único que no se puede tomar
prestado de otro sitio, y sale de sus mediciones de RSSI.

### El contorno del sitio (KML)

Dibuje el área que ocuparán los nodos como un polígono en Google Earth y
guárdelo como archivo `.kml`. Un `.kmz` es un KML comprimido y la página no
lo lee, así que elija KML al guardar. Se acepta un archivo con varios
polígonos. La página muestra el área de cada uno y si alguno se superpone,
porque dos polígonos superpuestos inflan el área y amontonan nodos donde se
cruzan.

### La posición del gateway

Escríbala en grados decimales (`5.501139`, `-73.492939`) o como la escribe
un GPS o una planilla de levantamiento (`5°30′04.10″ N`, `73°29′34.58″ O`).
La página acepta `O` o `W` para el oeste y la coma como separador decimal.
Debajo de una posición en grados, minutos y segundos, la página muestra los
grados decimales que leyó. Revise esa cifra, porque es el único valor que
usa la simulación.

### Las mediciones de RSSI (CSV)

El archivo lleva una fila por mensaje que recibió el gateway, con el RSSI en
dBm tal como lo reportó el gateway, más la latitud y la longitud del nodo en
grados decimales:

```
rssi,latitude,longitude
-83,3.917401,-73.820015
-91,3.918220,-73.821540
```

Las demás columnas se ignoran, así que una exportación del servidor de red
suele servir tal cual. Los nombres de columna se reconocen en sus formas
habituales (`rssi`, `rssi_dbm`, `lat`, `latitude`, `lon`, `lng`,
`longitude` y algunas más), siempre en inglés. Antes de cargarlo haga tres
cosas:

1. Deje un solo spreading factor y un solo gateway. El RSSI también cambia
   con el spreading factor y con el gateway, por razones que nada tienen que
   ver con la distancia, y el ajuste de un archivo mezclado parece sano y
   está mal. LoRaCAP avisa cuando ve más de uno de cualquiera de los dos,
   pero no puede saber qué parte quería usted conservar.
2. Quite las filas tomadas fuera del sitio, como una prueba de banco antes
   de salir a campo.
3. Asegúrese de que los números usen punto decimal. Las columnas pueden ir
   separadas por comas, punto y coma o tabuladores, y el archivo puede
   guardarse como "CSV UTF-8" o como "CSV" sencillo, que es como lo escribe
   Excel. Una hoja de cálculo configurada en español escribe coma decimal,
   y LoRaCAP solo lee el punto. En Excel, en Archivo > Opciones >
   Avanzadas, desmarque "Usar separadores del sistema" y escriba un punto
   como separador decimal antes de guardar. Un archivo con coma decimal se
   detiene con un mensaje en inglés que cita uno de sus valores y dice "use
   a comma as the decimal mark".

Los puntos a menos de 30 m del gateway se excluyen por defecto, porque el
receptor se satura a muy corta distancia y reporta un RSSI menor que el
real.

Anote el equipo con que midió: la potencia de transmisión del nodo, las
ganancias de las antenas del nodo y del gateway, y las pérdidas del nodo y
del cable. La página las necesita para convertir cada RSSI en una pérdida
del terreno. Pueden ser distintas del transceptor que va a simular el
estudio.

Si no tiene ninguna medición, la página igual puede construir un modelo a
partir del tipo de entorno y del alcance que usted espera. Ese modelo es
entonces un supuesto, la página lo rotula como tal y la sección 7 de esta
guía dice qué hacer al respecto.

## 4. Armar el estudio en la página web

```bash
python3 run.py serve
```

Esta orden abre `http://127.0.0.1:8765/` en el navegador. La página corre
solo en su computador, y nada fuera de él puede alcanzarla. Deje la
terminal abierta mientras usa la página y oprima Ctrl+C en ella al
terminar.

La página se lee en inglés o en español, con el selector "English |
Español" de la esquina superior. Abre en modo "Básico", que muestra solo lo
que no tiene valor predeterminado o se suele cambiar. Un campo con asterisco
es obligatorio. "Avanzado" muestra el resto, agrupado en bloques. Un bloque
cerrado enumera cada valor suyo que difiere del predeterminado, así que nada
cambia a sus espaldas.

El panel "Comprobaciones" de la derecha se actualiza mientras usted
escribe. Cada mensaje nombra el campo afectado, y un clic lleva a él. Los
mensajes vienen del simulador y se muestran en inglés en las dos versiones
de la página.

### 1. Sitio

Dé al estudio un nombre corto (letras, dígitos, guion o guion bajo), la
latitud y la longitud del gateway, y cargue el KML con "Elegir KML…". La
página muestra el área, si el gateway queda dentro del contorno, a qué
distancia está el punto más lejano y un esquema del sitio.

### 2. Radio

Elija la región y la potencia de transmisión del nodo. AU915 y AS923 piden
además el uplink dwell time. Cada una de sus opciones tiene un tope de
payload distinto, y en los data rates lentos la diferencia supera diez
veces, así que no hay un valor seguro que suponer por usted. El chip del
gateway, las antenas, las pérdidas en el cable y el ancho de banda están en
las opciones avanzadas de radio. Bajo el chip, una nota da la sensibilidad,
los canales y el límite de demodulación que usará la simulación.

### 3. Propagación

Con mediciones, quédese en la pestaña "Tengo mediciones de campo". Llene
los cuatro campos del equipo con que midió y luego cargue el CSV con
"Elegir CSV de mediciones…". La página ajusta el modelo y muestra hasta tres
ajustes lado a lado:

| Ajuste | Cuándo aparece | Qué hace |
|---|---|---|
| sin agrupar | siempre | cada fila cuenta una vez |
| agrupado (10 m) | siempre | cada franja de 10 m cuenta una vez, así que un punto medido muchas veces no domina |
| por posición | cuando algunas coordenadas se repiten exactamente | cada posición cuenta una vez, y la dispersión se separa en shadowing y fading |

Las primeras líneas bajo el botón dicen cómo se leyó el archivo: el
separador que encontró y la codificación del texto. Si alguna fila se
descartó porque un valor no se pudo leer como número, otra línea da cuántas.
Revíselas antes que las cifras.

Cada fila da el exponente n, el R², la σ, la pérdida en d₀ y la cantidad de
puntos, con un botón "Usar". Un ajuste marcado "dudoso" tiene un exponente
fuera de 1.45 a 5.97 (el rango que cubren las mediciones publicadas) o
explica menos del 15 % de la dispersión del RSSI. Las advertencias encima
de la tabla dicen cuál de las dos. Elija un ajuste a conciencia y anote cuál
eligió. Cuando aparece el ajuste por posición, es el que separa la
dispersión propia del lugar donde está un nodo (shadowing) de la que cambia
de un paquete a otro (fading).

"Usar" copia el ajuste en los campos de las opciones avanzadas de
propagación: el exponente, la pérdida en d₀, la σ del shadowing, la
distancia más lejana que usted midió y una línea con el origen del modelo,
que queda en `study.py`. El ajuste por posición llena además la σ del
fading. Si los campos del equipo están vacíos, el ajuste da igual el
exponente y la σ, pero no la pérdida en d₀, porque un valor predeterminado
ahí sería una cifra sin respaldo.

La medición más lejana importa después. Más allá de ella cada potencia
recibida es la recta del ajuste extrapolada, y las comprobaciones lo avisan
dondequiera que el sitio o un alcance quede más lejos.

### 4. Tráfico y experimento

Escriba el payload de la aplicación en bytes (lo que envía su aplicación,
sin el header LoRaWAN, que el simulador suma para el tiempo en el aire), el
intervalo de envío en segundos y el umbral de DER. Use el intervalo más
corto que pueda producir el despliegue. Una capacidad hallada en el peor
caso es una cota defendible.

Marque al menos un escenario:

- Un spreading factor fijo pone todos los nodos en él.
- MULTI pone cada nodo en el spreading factor más rápido que alcanza su
  enlace, sin margen y a plena potencia, así que es una cota y no una red.
- ADR es lo que adopta una red ya convergida, con un margen de enlace y
  potencia de transmisión reducida.

Correr MULTI y ADR juntos muestra cuánto vale la idealización. El coding
rate, el tiempo simulado, las ejecuciones por punto, la semilla aleatoria y
el modelo del receptor están en los bloques avanzados de esta sección. Para
un primer estudio, déjelos con sus valores predeterminados.

### 5. Crear y ejecutar

"Escribir study.py" escribe `studies/<nombre>/study.py` y `site_polygon.py`
y le muestra el archivo. Desde ese momento es un estudio corriente, que
usted puede editar a mano y correr desde la terminal. "Ejecutar la
simulación" lo corre y muestra su avance. La página simula con el mismo
código que la línea de comandos.

Antes de ejecutar, abra la pestaña "6. Salida" si quiere más figuras:
mensajes entregados por hora, energía por mensaje entregado, dónde se
pierden los paquetes y el mapa del sitio. La elección se guarda en
`study.py` y no cambia ninguna cifra.

## 5. Leer los resultados

Al terminar la ejecución, la página muestra una tabla con la capacidad de
cada escenario y su intervalo del 95 %, junto con la figura de DER. La
pestaña de salida ofrece entonces un botón que descarga el estudio con sus
archivos en un zip. Los
archivos mismos quedan en `studies/<nombre>/outputs/`.

"sin cruce" significa que la DER nunca bajó del umbral dentro de las
cantidades de nodos simuladas, de 3 a 300 en un estudio escrito por la
página, así que la capacidad está por encima de la última. Para buscar más
lejos, abra `study.py`, agregue cantidades mayores a la lista
`node_counts`, y revise y corra el estudio desde la terminal (sección 6).

Una capacidad es una estimación de simulación, condicional al modelo con
que se calculó. Repórtela con esas condiciones:

- la regla del receptor, la de LoRaSim por defecto
- el umbral de captura, 6 dB por defecto
- si los spreading factors se trataron como ortogonales, que es lo
  predeterminado, o qué tabla de rechazo se usó
- el modelo de propagación y su origen
- el umbral de DER, el payload y el intervalo de envío

La tabla de capacidad, que se escribe en Markdown o LaTeX si usted la elige
en la pestaña de salida, declara las tres primeras bajo las cifras. La
campaña de campo valida la cobertura y la calidad del enlace. No valida la
capacidad, y ninguna regla del receptor de LoRaCAP se ha comprobado contra
la capacidad medida en una red real.

## 6. Después, desde la terminal

Una vez que la página escribió el estudio, estas órdenes funcionan sobre él
como sobre cualquier otro:

```bash
python3 run.py check <nombre>     # revisarlo otra vez tras editar study.py
python3 run.py run <nombre>       # correrlo otra vez: misma semilla, mismas cifras
python3 run.py plot <nombre>      # redibujar las figuras sin simular
```

`study.py` es un archivo de texto comentado, en inglés. Cualquier editor lo
abre, y el README explica cada uno de sus campos.

## 7. Si no tenía mediciones

Un modelo construido a partir del entorno y de un alcance esperado es un
supuesto. Mientras cada spreading factor alcance todo el sitio, la capacidad
casi no depende de él, porque las colisiones dependen de cuántos nodos
transmiten y de cuánto difieren sus potencias recibidas. Cuando el sitio
deja de estar cubierto, el modelo decide el resultado. Después de la
ejecución, la página ofrece un barrido que mide justamente eso, y la
terminal hace lo mismo:

```bash
python3 run.py sweep <nombre>
```

El barrido varía el exponente de pérdida de trayecto y reporta, para cada
valor, el alcance, si el sitio queda cubierto y la capacidad. Si la
capacidad se mantiene casi plana en todo el rango, el modelo supuesto es
defendible siempre que se reporte como supuesto. Si no, hacen falta
mediciones. La sección "Simulating without field measurements" del README
recorre el razonamiento con las cifras del estudio de ejemplo.

## Problemas frecuentes

| Lo que aparece | Qué significa |
|---|---|
| No se encuentra `python3` o `py` | Python no está instalado o, en Windows, se instaló sin "Add python.exe to PATH". |
| `can't open file 'run.py'` | La terminal no está en la carpeta de LoRaCAP. Entre a la carpeta que contiene `run.py`. |
| "externally managed environment" al instalar | Use el entorno propio que describe la sección 1. |
| "matplotlib is not installed, so no figure was drawn." | Las cifras están bien. Instale matplotlib para tener las figuras. |
| "use a comma as the decimal mark" | Los números tienen coma decimal. Guárdelos con punto (sección 3). |
| "Could not find a column for rssi, latitude, longitude" | Los nombres de columna no están entre las formas habituales. El mensaje enumera los nombres que encontró. |
| Un ajuste marcado "dudoso" | Lea la advertencia encima de la tabla. Las causas habituales son una coordenada equivocada o un archivo mezclado. |
| La página no abre | Abra `http://127.0.0.1:8765/` a mano. Si el puerto está ocupado, iníciela con `python3 run.py serve --port 8800`. |
| Sus cifras del ejemplo difieren de la sección 2 | Corra `python3 run.py test` y no confíe en ningún resultado hasta que pase. |
