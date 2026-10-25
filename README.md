# youMP3gmr

Aplicación de escritorio en Python con Tkinter y yt-dlp. Permite analizar un
video o playlist, revisar su cola de canciones y descargar el audio como MP3.
La ventana usa el icono `youMP3gmr.ico`, muestra el nombre de la aplicación
en su cabecera y ofrece controles integrados para minimizar,
maximizar/restaurar y cerrar.

## Estructura del proyecto

```text
main.py                         Punto de entrada
app/
  config/theme.py               Colores y tema predeterminado
  services/media_provider.py    Adaptador de yt-dlp y carga de portadas
  ui/main_window.py             Ventana y estado compartido
  ui/layout.py                  Componentes y cola visual
  ui/theme.py                   Aplicación de temas
  ui/widgets.py                 Controles reutilizables
  ui/image_adapter.py           Adaptador de Pillow para las imágenes
  ui/download_controller.py     Metadatos, descargas y eventos de progreso
```

La interfaz se mantiene separada del proveedor multimedia: si en el futuro se
cambia yt-dlp, el punto principal de integración es
`app/services/media_provider.py`. El acceso a Pillow está centralizado en
`app/ui/image_adapter.py`.

## Requisitos e instalación (Windows)

Para descargar y convertir audio, cada persona debe instalar:

1. **Python 3.10 o posterior**, desde [python.org](https://www.python.org/downloads/windows/).
   Durante la instalación, activa **Add Python to PATH**. Tkinter viene incluido
   con el instalador oficial de Python para Windows.
2. **FFmpeg**, necesario para convertir las descargas a MP3. Se puede instalar
   con `winget` desde PowerShell:

   ```powershell
   winget install --id Gyan.FFmpeg.Shared --exact
   ```

   Si winget no está disponible, instala una compilación de FFmpeg y agrega la
   carpeta que contiene `ffmpeg.exe` al `PATH` de Windows. Cierra y vuelve a
   abrir PowerShell después de instalarlo. Comprueba que esté disponible con:

   ```powershell
   ffmpeg -version
   ```

3. **Los paquetes de Python del proyecto**, instalados desde la carpeta que
   contiene `requirements.txt`. yt-dlp, Pillow y python-vlc se instalan con este
   paso; no hace falta instalarlos por separado.

   ```powershell
   py -m pip install -r requirements.txt
   ```

Para obtener el proyecto, clona el repositorio o descarga y extrae su ZIP desde
GitHub. Después, abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
py main.py
```

**Opcional: vista previa y editor de fragmentos.** Para reproducir el video
dentro de youMP3gmr se necesita **VLC media player de 64 bits**, además del
paquete python-vlc que ya se instala desde `requirements.txt`. Si VLC falta, el
botón **Instalar VLC** de la aplicación puede ofrecer instalarlo con winget o
abrir la página oficial. Reinicia youMP3gmr después de instalar VLC. VLC no es
necesario para descargar canciones completas o playlists.

Pega un enlace y pulsa **Analizar playlist**. La cola muestra miniatura, título,
artista, duración, calidad y progreso individual. La opción **Incrustar carátula
y metadatos** está activada por defecto e incluye la portada y los metadatos en
el MP3, siempre que el medio disponga de miniatura. Desmárcala si prefieres no
incrustarlos. La portada incrustada se ajusta a 300 × 300 píxeles. Selecciona
las canciones que quieres procesar y pulsa
**Descargar selección** o **Descargar todo en MP3**.
En modo canción individual, **Editar fragmento** abre una vista previa del
video. Reproduce, pausa o avanza por la línea de tiempo, marca el inicio y el
final con precisión de milisegundos y pulsa **Descargar fragmento**; para la
pista completa, selecciona **Usar audio completo**. El reproductor requiere VLC
media player de 64 bits instalado además de las dependencias Python. Si el sitio
entrega el video y el audio por separado, la vista previa los combina en VLC.
Si no se detecta VLC, el botón **Instalar VLC** ofrece instalarlo mediante
winget tras pedir confirmación; la instalación puede solicitar permisos de
Windows. Si winget no está disponible, ofrece abrir la página oficial de VLC.
Los mensajes informativos de FFmpeg se ocultan durante las descargas; los
errores se notifican en la aplicación.
Al terminar una pista, el botón de carpeta de su fila abre la ubicación del
archivo descargado.
Puedes cambiar entre tema oscuro y claro con el botón de la esquina superior
derecha.

La interfaz usa la paleta `#FF0033`, `#00F0FF`, `#A855F7` y `#94A3B8`. Los
controles de calidad, normalización, pausa y limpieza se muestran como elementos
visuales y están deshabilitados mientras se prepara su implementación.

Usa la aplicación solo con contenido que tengas derecho a descargar y de
acuerdo con las condiciones del sitio de origen.
