from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from PIL import Image


EXTENSIONES_SOPORTADAS = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
EXTENSIONES_PREVIEW = {".png", ".jpg", ".jpeg"}
MAX_PREVIEW_SIZE = (2400, 1600)


@dataclass(frozen=True)
class Ortomosaico:
    ruta_maestra: Path
    ruta_preview: Path
    ancho: int
    alto: int
    ancho_preview: int
    alto_preview: int
    tamano_bytes: int

    @property
    def nombre(self):
        return self.ruta_maestra.name

    @property
    def extension(self):
        return self.ruta_maestra.suffix.upper().lstrip(".")


def listar_archivos_ortomosaico(carpeta):
    return _listar_archivos_ortomosaico_cached(str(Path(carpeta).resolve()), _archivo_mtime(carpeta))


def _archivo_mtime(ruta):
    path = Path(ruta)
    return path.stat().st_mtime if path.exists() else 0


@st.cache_data(show_spinner=False)
def _listar_archivos_ortomosaico_cached(carpeta_texto, mtime):
    ruta_carpeta = Path(carpeta_texto)
    if not ruta_carpeta.exists():
        return []
    archivos = [
        ruta
        for ruta in ruta_carpeta.iterdir()
        if ruta.is_file()
        and ruta.suffix.lower() in EXTENSIONES_SOPORTADAS
        and not ruta.stem.endswith("_preview")
    ]
    return sorted(archivos, key=lambda ruta: ruta.name.lower())


def ruta_preview(ruta_maestra):
    ruta = Path(ruta_maestra)
    if ruta.suffix.lower() in EXTENSIONES_PREVIEW:
        return ruta
    return ruta.with_name(f"{ruta.stem}_preview.jpg")


def asegurar_preview(ruta_maestra, max_size=MAX_PREVIEW_SIZE):
    return _asegurar_preview_cached(str(Path(ruta_maestra).resolve()), _archivo_mtime(ruta_maestra), max_size)


@st.cache_data(show_spinner=False)
def _asegurar_preview_cached(ruta_maestra_texto, mtime, max_size):
    ruta = Path(ruta_maestra_texto)
    preview = ruta_preview(ruta)
    if preview.exists():
        return preview
    if ruta.suffix.lower() not in {".tif", ".tiff"}:
        return ruta

    Image.MAX_IMAGE_PIXELS = None
    with Image.open(ruta) as imagen:
        vista = imagen.copy()
        vista.thumbnail(max_size)
        if vista.mode != "RGB":
            vista = vista.convert("RGB")
        vista.save(preview, "JPEG", quality=85, optimize=True)
    return preview


def obtener_ortomosaico(ruta_maestra):
    return _obtener_ortomosaico_cached(str(Path(ruta_maestra).resolve()), _archivo_mtime(ruta_maestra))


@st.cache_data(show_spinner=False)
def _obtener_ortomosaico_cached(ruta_maestra_texto, mtime):
    ruta = Path(ruta_maestra_texto)
    preview = asegurar_preview(ruta)
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(ruta) as imagen:
        ancho, alto = imagen.size
    with Image.open(preview) as imagen_preview:
        ancho_preview, alto_preview = imagen_preview.size
    return Ortomosaico(
        ruta_maestra=ruta,
        ruta_preview=preview,
        ancho=ancho,
        alto=alto,
        ancho_preview=ancho_preview,
        alto_preview=alto_preview,
        tamano_bytes=ruta.stat().st_size,
    )


def imagen_data_uri(ruta_imagen):
    ruta = Path(ruta_imagen)
    mime = "image/jpeg" if ruta.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    data = b64encode(ruta.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def formato_tamano(bytes_archivo):
    if bytes_archivo >= 1024 * 1024:
        return f"{bytes_archivo / (1024 * 1024):.2f} MB"
    return f"{bytes_archivo / 1024:.1f} KB"
