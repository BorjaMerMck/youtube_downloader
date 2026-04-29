# YouTube Downloader

Aplicación de escritorio para descargar vídeos y audio de YouTube (MP4/MP3) y transcribir el audio a texto (TXT). Interfaz gráfica con PySide6 (Qt).

---

## Características

- **Vídeo (MP4):** descarga el vídeo con la mejor calidad disponible y audio incluido.
- **Audio (MP3):** extrae solo el audio en formato MP3.
- **Transcripción (TXT):** genera un archivo de texto a partir del audio usando [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

Puedes marcar una o varias opciones por descarga.

---

## Requisitos

- **Python** 3.10 o superior
- **FFmpeg** (en el PATH o configurado en `config.py`)
- **faster-whisper** (opcional; solo si quieres usar la transcripción)

---

## Instalación

1. Clona o descarga el proyecto y entra en la carpeta:

   ```bash
   cd youtube_downloader
   ```

2. Crea un entorno virtual (recomendado):

   ```bash
   python -m venv venv
   venv\Scripts\activate    # Windows
   # source venv/bin/activate   # Linux / macOS
   ```

3. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

4. **FFmpeg:**  
   - Si ya está en el PATH del sistema, no hace falta nada más.  
   - Si no, descarga FFmpeg, descomprímelo y en `config.py` ajusta la ruta en `FFMPEG_DIR` (por ejemplo `r"C:\ffmpeg\bin"` en Windows).

---

## Configuración

Edita `config.py` si necesitas:

- **`FFMPEG_DIR`:** ruta a la carpeta donde están `ffmpeg` y `ffprobe`. Pon `None` si FFmpeg está en el PATH.
- **`TRANSCRIBE_MAX_MINUTES`:** límite de minutos de audio a transcribir (0 = sin límite).

---

## Ejecución

### Opción fácil (Windows, sin ejecutables)

Para ejecutar la app en Windows:

1. Activa el entorno virtual (si ya lo creaste en la sección *Instalación*):
   ```bash
   venv\Scripts\activate
   ```

2. Instala dependencias (primera vez o si cambiaste `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```

3. Inicia la aplicación:
   ```bash
   python -m app.main
   ```

Solo necesitas tener **Python** 3.10+ instalado y **FFmpeg** (o configurar `FFMPEG_DIR` en `config.py`).

### Desde la terminal

```bash
python -m app.main
```

- **`app/config.py`**: Configuración global (FFMPEG_DIR, TRANSCRIBE_MAX_MINUTES) y utilidades
- **`app/signals/signals.py`**: Clase `Signals` - Señales Qt para comunicación entre hilos
- **`app/models/models.py`**: Clase `Job` - Dataclass que representa un trabajo de descarga/transcripción
- **`app/services/service.py`**: Clase `MediaService` - Servicio que maneja las operaciones de descarga y transcripción
- **`app/ui/ui.py`**: Ventana principal (`MainWindow`) y UI
- **`app/main.py`**: Punto de entrada principal de la aplicación

---

1. El usuario ingresa URL y selecciona opciones
2. Se crea un objeto `Job` con los parámetros
3. Se ejecuta en un hilo separado para no bloquear la UI
4. `MediaService` procesa el trabajo:
   - Descarga video (si está marcado)
   - Descarga audio (si está marcado o si se necesita para transcripción)
   - Transcribe audio a texto (si está marcado)
5. Los resultados se muestran en la interfaz mediante señales Qt

1. Pega la **URL** del vídeo de YouTube.
2. Elige la **carpeta** donde guardar los archivos.
3. Marca lo que quieras: **Vídeo (MP4)**, **Audio (MP3)** y/o **Transcribir (TXT)**.
4. Pulsa **Ejecutar**.

El progreso y los mensajes se muestran en la barra de estado y en el log. Los archivos se guardan en la carpeta elegida con nombres que incluyen título e ID del vídeo.

---

## Estructura del proyecto

```
youtube_downloader/
├── app/
│   ├── __init__.py
│   ├── main.py               # Punto de entrada
│   ├── config.py             # Configuración (FFmpeg, transcripción)
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py         # Modelo Job
│   ├── services/
│   │   ├── __init__.py
│   │   └── service.py        # Lógica de descarga y transcripción
│   ├── signals/
│   │   ├── __init__.py
│   │   └── signals.py        # Señales Qt para UI
│   └── ui/
│       ├── __init__.py
│       └── ui.py             # Interfaz (ventana de bienvenida + descargador)
├── requirements.txt
└── README.md
```

---

## Créditos

**YouTube Downloader** — by Borja Merchan McKenna

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) para las descargas.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) para la transcripción.
- [PySide6](https://doc.qt.io/qtforpython/) para la interfaz gráfica.
