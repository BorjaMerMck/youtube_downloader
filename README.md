# YouTube Downloader

Aplicación de escritorio desarrollada en Python con PySide6 para descargar vídeos y audio de YouTube y transcribir el audio a texto. Permite consultar playlists, elegir la resolución de descarga y seguir el proceso desde una interfaz gráfica con tema oscuro.

**Autor:** Borja Merchan McKenna · [LinkedIn](https://www.linkedin.com/in/borja-merchan-mckenna/) · [GitHub](https://github.com/BorjaMerMck)

**Estado:** en desarrollo, con funciones implementadas y validación final pendiente. La documentación describe el código actual; no acredita pruebas de ejecución en otros equipos.

## Funcionalidades

| Función | Comportamiento actual |
| --- | --- |
| Vídeo | Descarga vídeo con audio, priorizando la mejor calidad disponible y la fusión en un contenedor MP4. |
| Selección de calidad | Consulta las resoluciones antes de descargar y permite elegir la máxima disponible o una altura objetivo. |
| Audio | Extrae audio en MP3 con calidad objetivo de 192 kb/s. |
| Transcripción | Genera un TXT en español mediante faster-whisper, con el modelo `small`, CPU y cálculo `int8`. |
| Playlists | Descarga vídeo, audio y genera una transcripción por vídeo; procesa las entradas consecutivamente. |
| Cancelación | Solicita detener el trabajo en curso mediante una señal de cancelación cooperativa. |
| Seguimiento | Muestra la fase actual, el progreso general por etapas, el progreso de transferencia y un registro de mensajes. |
| Interfaz | Bienvenida con tabla de funciones sin iconos, tarjetas de selección, tema oscuro y enlaces a los perfiles del autor. |
| Ejecutable | Genera una distribución de Windows con icono propio y sus dependencias en una carpeta. |
| Organización | Guarda los resultados en una subcarpeta con el título del vídeo. |
| Acceso a resultados | Permite abrir la carpeta del último trabajo completado en Windows. |

Las opciones de vídeo, audio y transcripción pueden combinarse para vídeos individuales y playlists. Si se solicita transcripción, también se descarga y conserva el MP3, aunque la casilla de audio no esté marcada.

## Tecnologías y arquitectura

- **Python:** lógica de aplicación y ejecución de tareas con `threading.Thread`.
- **PySide6 / Qt:** ventanas, controles y señales de comunicación con la interfaz.
- **yt-dlp:** consulta de metadatos, formatos y descargas.
- **FFmpeg:** fusión de vídeo/audio y conversión del audio a MP3.
- **faster-whisper:** transcripción local del audio.

El proyecto separa la interfaz, el modelo de trabajo, las señales y el servicio multimedia. `Job` es una dataclass inmutable que contiene la URL, la carpeta de salida, las operaciones solicitadas y la altura de vídeo elegida.

## Requisitos

- Python **3.10 o superior por la sintaxis del proyecto**. La versión elegida debe ser compatible con las versiones de las dependencias instaladas.
- Un entorno de escritorio para ejecutar la interfaz Qt.
- FFmpeg y ffprobe instalados y accesibles desde el `PATH` o mediante `FFMPEG_DIR`.
- Conexión a Internet para consultar YouTube y descargar contenido.
- `PySide6` y `yt-dlp`.
- `faster-whisper` si se desea generar transcripciones.

**Plataforma de referencia: Windows.** El botón «Abrir carpeta» utiliza `os.startfile`, por lo que necesita adaptación para Linux y macOS. La compatibilidad completa con esos sistemas está pendiente de validación.

## Instalación

### 1. Descargar el proyecto

Clona el repositorio o descarga su contenido y abre una terminal en la carpeta raíz:

```bash
cd youtube_downloader
```

### 2. Crear un entorno virtual

```bash
python -m venv .venv
```

Actívalo según tu terminal:

**Windows — PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows — CMD:**

```bat
.venv\Scripts\activate.bat
```

**Linux / macOS — preparación del entorno, con las limitaciones indicadas:**

```bash
source .venv/bin/activate
```

### 3. Instalar las dependencias

Instala las dependencias del proyecto:

```bash
python -m pip install -r requirements.txt
```

Para transcribir, `faster-whisper` debe estar instalado en el mismo entorno. Si no está incluido en tu archivo de dependencias:

```bash
python -m pip install faster-whisper
```

Para una instalación reproducible, conserva en `requirements.txt` las versiones que hayas probado.

### 4. Configurar FFmpeg

Comprueba que los ejecutables están disponibles en el `PATH`:

```bash
ffmpeg -version
ffprobe -version
```

Si no están en el `PATH`, configura la carpeta que contiene ambos ejecutables en `app/config.py`:

```python
FFMPEG_DIR = r"C:\ffmpeg\bin"
```

Si ya están en el `PATH`:

```python
FFMPEG_DIR = None
```

La configuración actual contiene `C:\ffmpeg\bin`. Si no encuentra allí FFmpeg, la aplicación intenta localizarlo en el `PATH`. La función de detección comprueba `ffmpeg`, pero no verifica expresamente la presencia de `ffprobe`.

## Ejecución

Desde la raíz del proyecto y con el entorno virtual activado:

```bash
python -m app.main
```

También se admite:

```bash
python app/main.py
```

La aplicación muestra una bienvenida con una tabla de sus funciones y enlaces a LinkedIn y GitHub. Pulsa **Comenzar** para acceder al descargador y **Menú** para regresar.

## Uso

1. Pega una URL de YouTube.
2. Selecciona el destino con **Elegir carpeta…**. Por defecto, se utiliza `Videos` dentro de la carpeta del usuario; si no se puede crear, se usa la carpeta del usuario.
3. Marca **Vídeo (MP4)**, **Audio (MP3)** o **Transcribir (TXT)**.
4. Pulsa **Ejecutar**.
5. Si has elegido vídeo, confirma la calidad en el diálogo previo a la descarga.
6. Sigue la fase actual, el progreso general, la transferencia en curso y los mensajes del registro.
7. Al terminar, pulsa **Abrir carpeta** para acceder a los resultados.

Vídeo y audio aparecen marcados inicialmente. Si se solicitan ambos sin transcripción, la aplicación pregunta si también debe generar un MP3 independiente.

La interfaz reconoce enlaces habituales de vídeo, enlaces cortos `youtu.be` y rutas `/shorts/`, `/embed/` y `/live/`. Reconocer una URL no garantiza que el contenido esté disponible para descargar.

### Playlists

- **Ver playlist** consulta los títulos y los muestra en el registro, sin descargar los archivos. La consulta devuelve hasta 300 entradas; el registro también tiene un límite de 300 mensajes.
- Si un enlace de vídeo incluye `list=`, la aplicación permite elegir entre ese vídeo y la playlist completa.
- Para descargar una lista completa, utiliza su enlace de playlist y confirma la descarga de toda la lista.
- No hay selección individual de elementos desde el listado.
- La consulta de calidad de una playlist toma como referencia su primer vídeo. La disponibilidad real puede variar entre elementos.
- La transcripción está disponible para toda la playlist, también cuando solo se marca TXT. Se genera un TXT por vídeo y se conserva su MP3.
- El procesamiento completo no tiene el límite de 300 entradas de la consulta «Ver playlist».
- El modelo de transcripción se carga una vez por trabajo, se reutiliza entre vídeos y se libera al terminar.
- Si falla un vídeo, el trabajo se detiene e identifica la entrada que falló y cuántos vídeos se completaron. Los resultados anteriores se conservan; no se omite automáticamente el vídeo fallido.

### Cancelación y limpieza

**Cancelar** solicita detener la operación. La cancelación se comprueba en los puntos previstos por el servicio y puede tardar durante consultas de red, carga del modelo o procesamiento externo.

Al detectar una cancelación durante la escritura de la transcripción, el servicio intenta eliminar el TXT parcial. Los archivos ya descargados pueden permanecer en el destino.

**Limpiar** vacía el registro y reinicia los indicadores de la interfaz; no elimina los archivos descargados.

## Archivos generados

Ejemplo de salida al solicitar vídeo, audio y transcripción:

```text
carpeta_de_salida/
└── Título del vídeo/
    ├── Título del vídeo [ID_DEL_VIDEO] (VIDEO).mp4
    ├── Título del vídeo [ID_DEL_VIDEO] (AUDIO).mp3
    └── Título del vídeo [ID_DEL_VIDEO] (AUDIO).txt
```

Las plantillas limitan el título a 80 caracteres en la carpeta y a 100 en el nombre del archivo. Se aplica la opción de nombres compatibles con Windows y se conserva el ID para distinguir vídeos con títulos iguales. Las rutas de destino muy largas todavía pueden causar problemas. Este esquema se aplica a nuevas descargas; no renombra archivos anteriores. El TXT comparte el nombre base del MP3 y se escribe en UTF-8, con un segmento de texto por línea, sin marcas temporales.

El MP4 es el formato de fusión solicitado. El código conserva el códec de vídeo y no fuerza una conversión general de todos los formatos a MP4/H.264; la extensión final y la reproducción dependen del formato seleccionado y del procesamiento realizado.

## Configuración de la transcripción

En `app/config.py`:

```python
TRANSCRIBE_MAX_MINUTES = 0
```

- `0`: sin límite de duración configurado.
- Un valor positivo: limita los segmentos de audio incluidos en el TXT. No limita el tiempo de ejecución del programa ni la duración del MP3 descargado.

El servicio deja de escribir cuando el final de un segmento alcanza o supera el límite; ese segmento se excluye, por lo que el texto puede terminar algo antes del minuto indicado.

Los siguientes parámetros están fijados en `app/services/service.py` y no se seleccionan desde la interfaz:

| Parámetro | Valor actual |
| --- | --- |
| Modelo | `small` |
| Dispositivo | `cpu` |
| Tipo de cálculo | `int8` |
| Idioma | Español (`es`) |
| Búsqueda | `beam_size=5` |
| Filtro de actividad de voz | `vad_filter=True` |

## Estructura del proyecto

```text
youtube_downloader/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── service.py
│   ├── signals/
│   │   ├── __init__.py
│   │   └── signals.py
│   └── ui/
│       ├── __init__.py
│       └── ui.py
├── tests/
│   └── test_playlists.py
├── debug.py
├── build_exe.py
├── YouTubeDownloader.spec
├── ico.png
├── ico.ico
├── requirements.txt
└── README.md
```

`build/`, `dist/` y `YouTubeDownloader.zip` se generan durante la compilación. Las carpetas `__pycache__/` son cachés de Python.

| Archivo | Responsabilidad |
| --- | --- |
| `app/main.py` | Crea `QApplication` y abre la ventana principal. |
| `app/config.py` | Configuración, detección de FFmpeg e importación opcional de faster-whisper. |
| `app/models/models.py` | Define el trabajo inmutable `Job`. |
| `app/services/service.py` | Consulta metadatos, descarga, convierte audio, transcribe y gestiona la cancelación. |
| `app/signals/signals.py` | Define las señales Qt de progreso, estado, resultados y errores. |
| `app/ui/ui.py` | Pantalla de bienvenida con tabla de funciones, descargador, validaciones y diálogo de calidad. |
| `build_exe.py` | Limpia compilaciones anteriores, instala dependencias, ejecuta PyInstaller y crea el ZIP de distribución. |
| `YouTubeDownloader.spec` | Configura el ejecutable, el icono y los recursos, incluidos los modelos ONNX de faster-whisper. |
| `ico.png` / `ico.ico` | Icono de la ventana y del ejecutable, respectivamente. |
| `tests/test_playlists.py` | Comprobaciones automatizadas de playlists y selección de opciones. |
| `debug.py` | Ejecuta esas comprobaciones y presenta los resultados en una tabla legible. |

Las consultas y los trabajos se ejecutan en hilos de Python. El servicio comunica el estado a la interfaz mediante señales Qt. Cuando se solicitan varias salidas, el orden es vídeo, audio y transcripción.

## Generar el ejecutable de Windows

Desde Windows, con el entorno virtual activo y la aplicación cerrada:

```powershell
python build_exe.py
```

El script utiliza el mismo intérprete de Python con el que se ejecuta y el archivo `YouTubeDownloader.spec`. Antes de compilar, elimina las carpetas `build/` y `dist/` y el ZIP anterior: no guardes archivos personales en esas ubicaciones.

La compilación requiere `ico.png`, `ico.ico` y el `.spec` en la raíz. Para esta distribución con transcripción también debe estar instalado `faster-whisper`: el `.spec` recoge sus archivos de datos y comprueba que haya modelos ONNX disponibles.

Resultados:

- `dist/YouTubeDownloader/YouTubeDownloader.exe`: ejecutable nuevo.
- `dist/YouTubeDownloader/_internal/`: dependencias y recursos necesarios.
- `YouTubeDownloader.zip`: contenido de la carpeta de distribución, listo para extraer.

**Distribuye toda la carpeta o el ZIP; no copies únicamente el EXE.** El destinatario debe extraer el ZIP antes de abrir la aplicación. Una copia antigua del EXE en la raíz o en otra ubicación no se actualiza al compilar.

El empaquetado actual no incluye explícitamente los ejecutables de FFmpeg ni los pesos del modelo Whisper `small`. Configura FFmpeg en el equipo de destino y prevé conexión para obtener el modelo si todavía no está disponible en su caché. Incluir el modelo de detección de voz ONNX no equivale a incluir los pesos de transcripción.

Después de cambiar archivos Python, iconos o configuración del empaquetado, vuelve a generar el ejecutable para distribuir esos cambios.

## Comprobaciones

Ejecuta desde la raíz:

```powershell
python debug.py
```

El informe muestra una tabla con el resultado de cada comprobación. Conserva `tests/test_playlists.py`: `debug.py` necesita ese archivo.

También puedes utilizar directamente unittest:

```powershell
python -m unittest discover -s tests -p test_playlists.py -v
```

La suite incluye 12 pruebas sobre combinaciones de opciones, playlists, progreso global, cancelación, errores, listas de más de 300 entradas, escritura de TXT y reutilización del modelo. Se obtuvo un resultado de 12 pruebas correctas durante el desarrollo, antes de los últimos cambios de nombres y diseño.

Las pruebas simulan descargas y transcripción: no verifican YouTube en directo, reconocimiento real de voz, interfaz gráfica ni el empaquetado del EXE. Antes de publicar, comprueba vídeo, MP3 y TXT reales, una playlist corta y la cancelación tanto desde Python como desde el ejecutable.

## Limitaciones conocidas

- La transcripción está fijada en español, también para playlists; no detecta automáticamente el idioma.
- La altura elegida no es un límite estricto: el selector incluye una alternativa de máxima calidad sin restricción si no encuentra formatos compatibles con el límite.
- El progreso general cuenta etapas completadas; no estima el tiempo restante. Descargar un vídeo y transcribirlo pueden tardar tiempos muy distintos. La barra de transferencia muestra la descarga en curso; el procesamiento usa un indicador indeterminado.
- No se incluye una interfaz para seleccionar GPU, modelo o idioma.
- «Abrir carpeta» depende actualmente de Windows.
- Las pruebas en otro PC y la validación final del ejecutable están pendientes. Docker no forma parte de la distribución actual.

## Resolución de problemas

| Problema | Comprobación |
| --- | --- |
| No se encuentra el módulo `app` | Ejecuta el comando desde la raíz, donde está la carpeta `app`. |
| Falta `PySide6` o `yt_dlp` | Comprueba que el entorno virtual está activo y que instalaste las dependencias en ese entorno. |
| Error de FFmpeg o ffprobe | Revisa los ejecutables, el `PATH` y `FFMPEG_DIR`. |
| faster-whisper no disponible | Instala la dependencia opcional en el entorno utilizado por la aplicación. |
| Error `NO_SUCHFILE` con `silero_vad_v6.onnx` | Regenera el ejecutable con el `.spec` actualizado, que incluye los datos de `faster_whisper`. Distribuye también `_internal`. |
| El ejecutable no refleja los cambios | Vuelve a compilar y abre el EXE de `dist`; las copias anteriores no se actualizan. |
| Error de red o descarga | Consulta el mensaje del registro y comprueba la conexión y disponibilidad del contenido. |
| La calidad no se puede consultar | La descarga de vídeo se interrumpe antes de comenzar; revisa el error y reintenta. |
| «Abrir carpeta» falla fuera de Windows | Esa acción requiere una implementación compatible con el sistema operativo. |

## Próximos pasos

- [ ] Revisar las dependencias y fijar las versiones probadas en `requirements.txt`.
- [ ] Corregir y validar las limitaciones antes de etiquetar una versión final.
- [ ] Probar una instalación limpia en otro PC: vídeo, audio, transcripción, playlists, cancelación y errores.
- [ ] Validar el ZIP de distribución de Windows en otro PC, incluidas las dependencias externas y la primera transcripción.
- [ ] Organizar los cambios en commits descriptivos y preparar una versión publicada en GitHub.
- [ ] Añadir el proyecto al CV y LinkedIn con sus funcionalidades verificadas y el enlace al repositorio.

## Créditos y referencias

- [yt-dlp](https://github.com/yt-dlp/yt-dlp): descargas y extracción de metadatos.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): transcripción.
- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython/): interfaz gráfica.
- [FFmpeg](https://ffmpeg.org/): procesamiento multimedia.

La documentación describe la implementación del proyecto y la configuración de empaquetado. Las comprobaciones automatizadas y las pruebas manuales se distinguen para no dar por validada una función únicamente por haber compilado el programa.
