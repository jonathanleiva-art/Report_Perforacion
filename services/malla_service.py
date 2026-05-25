from datetime import datetime
from pathlib import Path
import logging
import shutil
import sqlite3
import textwrap

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

try:
    import fitz
except ImportError:  # pragma: no cover - fallback when PyMuPDF is absent
    fitz = None

import db
from config import PLANOS_MALLA_DIR, PLANOS_MALLA_PREVIEW_DIR, REPORTES_OPERADORES_DIR


LOGGER = logging.getLogger(__name__)

TABLA_MALLAS = "mallas_avance"
TABLA_POZOS = "pozos_avance"
TABLA_PLANOS = "planos_malla_avance"
TABLA_POZOS_PLANO = "pozos_plano_avance"
TABLA_REPORTES_OPERADORES = "reportes_operador_avance"
TABLA_POZOS_REPORTE_OPERADOR = "pozos_reporte_operador_avance"
TABLA_ARCHIVOS_PLANOS_MALLA = "archivos_planos_malla"
TABLA_ARCHIVOS_REPORTES_OPERADOR = "archivos_reportes_operador"
TABLA_POZOS_MALLA_CONTROL = "pozos_malla_control"

ESTADOS_POZO_VALIDOS = (
    "pendiente",
    "perforado",
    "repaso",
    "colapsado",
    "no perforar",
)

ESTADOS_POZO_COLOR = {
    "pendiente": "#F59E0B",
    "perforado": "#16A34A",
    "repaso": "#0F766E",
    "colapsado": "#DC2626",
    "no perforar": "#64748B",
}

TIPOS_ARCHIVO_PLANO = ("pdf",)
TIPOS_ARCHIVO_REPORTE = ("jpg", "jpeg", "png", "pdf")
TIPOS_POZO_MALLA_CONTROL = ("Producción", "Buffer", "Precorte", "Otro")
ESTADOS_POZO_MALLA_CONTROL = ("pendiente", "realizado")

TIPOS_PERFORACION = (
    "Producción",
    "Buffer 01",
    "Buffer 02",
    "Precorte 1",
    "Precorte 2",
    "Precorte 3",
    "Precorte 5",
    "otro",
)


def conectar_db(db_path=db.DB_PATH):
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _numero(valor):
    if valor in (None, ""):
        return 0.0
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _asegurar_directorio_preview_plano(preview_dir=PLANOS_MALLA_PREVIEW_DIR):
    ruta = Path(preview_dir)
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _ruta_preview_plano_malla(archivo_info, preview_dir=PLANOS_MALLA_PREVIEW_DIR):
    ruta_archivo_texto = _texto(archivo_info.get("ruta_archivo", ""))
    if not ruta_archivo_texto:
        return None
    ruta_archivo = Path(ruta_archivo_texto)
    directorio = _asegurar_directorio_preview_plano(preview_dir)
    return directorio / f"{ruta_archivo.stem}.png"


def _dibujar_texto_envuelto(dibujo, texto, posicion, ancho_caracteres=42, color="#0F172A", font=None, separacion=8):
    font = font or ImageFont.load_default()
    lineas = []
    for bloque in str(texto).splitlines() or [""]:
        if not bloque.strip():
            lineas.append("")
        else:
            lineas.extend(textwrap.wrap(bloque, width=ancho_caracteres) or [""])
    texto_envuelto = "\n".join(lineas)
    dibujo.multiline_text(posicion, texto_envuelto, fill=color, font=font, spacing=separacion)


def generar_preview_pdf_real(ruta_pdf, preview_dir=PLANOS_MALLA_PREVIEW_DIR, forzar=False):
    ruta_pdf = Path(ruta_pdf)
    if not ruta_pdf.exists() or ruta_pdf.suffix.lower() != ".pdf":
        return None
    if fitz is None:
        return None

    directorio = _asegurar_directorio_preview_plano(preview_dir)
    ruta_preview = directorio / f"{ruta_pdf.stem}.png"
    if ruta_preview.exists() and not forzar:
        return ruta_preview

    try:
        with fitz.open(str(ruta_pdf)) as documento:
            if len(documento) == 0:
                return None
            pagina = documento.load_page(0)
            pixmap = pagina.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            pixmap.save(str(ruta_preview))
        return ruta_preview
    except Exception:
        LOGGER.exception("No fue posible rasterizar el PDF del plano: %s", ruta_pdf)
        return None


def generar_preview_plano_malla(archivo_info, preview_dir=PLANOS_MALLA_PREVIEW_DIR, forzar=False):
    if not archivo_info:
        return None
    ruta_archivo_texto = _texto(archivo_info.get("ruta_archivo", ""))
    if not ruta_archivo_texto:
        return None
    ruta_archivo = Path(ruta_archivo_texto)
    if not ruta_archivo.exists():
        return None

    ruta_preview = _ruta_preview_plano_malla(archivo_info, preview_dir=preview_dir)
    if ruta_preview is None:
        return None
    if ruta_preview.exists() and not forzar:
        return ruta_preview

    preview_real = generar_preview_pdf_real(ruta_archivo, preview_dir=preview_dir, forzar=forzar)
    if preview_real is not None:
        return preview_real

    imagen = Image.new("RGB", (1400, 1800), "#F8FAFC")
    dibujo = ImageDraw.Draw(imagen)
    font_titulo = ImageFont.load_default()
    font_texto = ImageFont.load_default()

    dibujo.rounded_rectangle((40, 40, 1360, 1760), radius=28, outline="#1D4ED8", width=4, fill="#FFFFFF")
    dibujo.rounded_rectangle((72, 72, 1328, 220), radius=22, outline="#CBD5E1", width=2, fill="#EFF6FF")
    dibujo.text((110, 105), "Vista previa del plano de perforación", fill="#1D4ED8", font=font_titulo)
    dibujo.text((110, 145), "Vista previa asistida", fill="#475569", font=font_texto)

    contenido = [
        f"Archivo: {ruta_archivo.name}",
        f"Ruta: {ruta_archivo}",
        f"Tipo: {_texto(archivo_info.get('tipo_archivo', 'pdf')).upper()}",
        f"Categoría: {_texto(archivo_info.get('categoria', 'plano_malla'))}",
        f"Fecha carga: {_texto(archivo_info.get('fecha_carga', ''))}",
        f"Banco: {_texto(archivo_info.get('banco', ''))}",
        f"Fase: {_texto(archivo_info.get('fase', ''))}",
        f"Malla: {_texto(archivo_info.get('malla', ''))}",
        f"Turno: {_texto(archivo_info.get('turno', ''))}",
        "",
        "El entorno actual no dispone de un motor PDF para rasterizar la primera página.",
        "Se genera una vista previa asistida para mantener la visualización dentro del sistema.",
        "La carga original del PDF permanece guardada en data/planos_malla/.",
    ]
    _dibujar_texto_envuelto(dibujo, "\n".join(contenido), (90, 280), ancho_caracteres=62, font=font_texto, separacion=10)
    dibujo.rounded_rectangle((90, 1540, 1310, 1688), radius=18, outline="#94A3B8", width=2, fill="#F1F5F9")
    _dibujar_texto_envuelto(
        dibujo,
        "Vista previa asistida sin OCR.\nSi se incorpora un motor PDF en el futuro, aquí se podrá rasterizar la primera página real.",
        (120, 1570),
        ancho_caracteres=72,
        color="#0F172A",
        font=font_texto,
        separacion=8,
    )
    imagen.save(ruta_preview)
    return ruta_preview


def obtener_preview_plano_malla(archivo_id, db_path=db.DB_PATH, preview_dir=PLANOS_MALLA_PREVIEW_DIR):
    archivo_info = obtener_archivo_plano_malla(archivo_id, db_path=db_path)
    if archivo_info is None:
        return None
    return generar_preview_plano_malla(archivo_info, preview_dir=preview_dir)


def normalizar_estado_pozo(estado):
    texto = _texto(estado).lower()
    if texto in ESTADOS_POZO_VALIDOS:
        return texto
    return "pendiente"


def asegurar_tablas(db_path=db.DB_PATH):
    with conectar_db(db_path) as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA_MALLAS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                banco TEXT NOT NULL,
                fase TEXT NOT NULL,
                malla TEXT NOT NULL,
                descripcion TEXT,
                fecha TEXT,
                turno TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(banco, fase, malla, fecha, turno)
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA_POZOS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                malla_id INTEGER NOT NULL,
                numero_pozo TEXT NOT NULL,
                tipo_pozo TEXT,
                estado TEXT NOT NULL,
                metros_planificados REAL NOT NULL DEFAULT 0,
                metros_perforados REAL NOT NULL DEFAULT 0,
                operador TEXT,
                equipo TEXT,
                fecha TEXT,
                turno TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(malla_id, numero_pozo),
                FOREIGN KEY (malla_id) REFERENCES {TABLA_MALLAS}(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA_PLANOS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_plano TEXT NOT NULL,
                banco TEXT NOT NULL,
                fase TEXT NOT NULL,
                malla TEXT NOT NULL,
                fecha TEXT,
                turno TEXT,
                archivo_nombre TEXT,
                archivo_ruta TEXT,
                archivo_tipo TEXT,
                observacion TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(nombre_plano, banco, fase, malla, fecha, turno)
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA_POZOS_PLANO} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plano_id INTEGER NOT NULL,
                numero_pozo TEXT NOT NULL,
                tipo_pozo TEXT,
                metros_planificados REAL NOT NULL DEFAULT 0,
                estado_inicial TEXT NOT NULL DEFAULT 'pendiente',
                coordenada_x REAL NOT NULL DEFAULT 0,
                coordenada_y REAL NOT NULL DEFAULT 0,
                observacion TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(plano_id, numero_pozo),
                FOREIGN KEY (plano_id) REFERENCES {TABLA_PLANOS}(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA_REPORTES_OPERADORES} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plano_id INTEGER,
                operador TEXT NOT NULL,
                equipo TEXT,
                fecha TEXT,
                turno TEXT,
                banco TEXT,
                fase TEXT,
                malla TEXT,
                archivo_foto TEXT,
                archivo_ruta TEXT,
                archivo_tipo TEXT,
                observacion TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (plano_id) REFERENCES {TABLA_PLANOS}(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA_POZOS_REPORTE_OPERADOR} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporte_id INTEGER NOT NULL,
                numero_pozo TEXT NOT NULL,
                fase TEXT,
                banco TEXT,
                malla TEXT,
                tipo_perforacion TEXT,
                metros_planificados REAL NOT NULL DEFAULT 0,
                metros_perforados REAL NOT NULL DEFAULT 0,
                tiempo_perforacion REAL NOT NULL DEFAULT 0,
                tricono_bit TEXT,
                operador TEXT,
                equipo TEXT,
                fecha TEXT,
                turno TEXT,
                estado TEXT NOT NULL DEFAULT 'pendiente',
                observacion TEXT,
                es_critico INTEGER NOT NULL DEFAULT 0,
                motivo_critico TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(reporte_id, numero_pozo, tipo_perforacion),
                FOREIGN KEY (reporte_id) REFERENCES {TABLA_REPORTES_OPERADORES}(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA_ARCHIVOS_PLANOS_MALLA} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_archivo TEXT NOT NULL,
                ruta_archivo TEXT NOT NULL,
                tipo_archivo TEXT NOT NULL,
                fecha_carga TEXT NOT NULL,
                categoria TEXT NOT NULL
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA_ARCHIVOS_REPORTES_OPERADOR} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_archivo TEXT NOT NULL,
                ruta_archivo TEXT NOT NULL,
                tipo_archivo TEXT NOT NULL,
                fecha_carga TEXT NOT NULL,
                categoria TEXT NOT NULL
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA_POZOS_MALLA_CONTROL} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archivo_plano_id INTEGER NOT NULL,
                numero_pozo TEXT NOT NULL,
                tipo_pozo TEXT NOT NULL DEFAULT 'Otro',
                metros_planificados REAL NOT NULL DEFAULT 0,
                estado TEXT NOT NULL DEFAULT 'pendiente',
                realizado INTEGER NOT NULL DEFAULT 0,
                observacion TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(archivo_plano_id, numero_pozo),
                FOREIGN KEY (archivo_plano_id) REFERENCES {TABLA_ARCHIVOS_PLANOS_MALLA}(id) ON DELETE CASCADE
            )
            """
        )
        columnas_pozos_plano = db.columnas_tabla(connection, TABLA_POZOS_PLANO)
        for columna in ("coordenada_x", "coordenada_y", "observacion"):
            if columna not in columnas_pozos_plano:
                tipo = "REAL NOT NULL DEFAULT 0" if columna in ("coordenada_x", "coordenada_y") else "TEXT"
                connection.execute(f"ALTER TABLE {TABLA_POZOS_PLANO} ADD COLUMN {columna} {tipo}")
        columnas_reportes_operador = db.columnas_tabla(connection, TABLA_REPORTES_OPERADORES)
        for columna, tipo in (
            ("plano_id", "INTEGER"),
            ("archivo_foto", "TEXT"),
            ("archivo_ruta", "TEXT"),
            ("archivo_tipo", "TEXT"),
            ("observacion", "TEXT"),
        ):
            if columna not in columnas_reportes_operador:
                connection.execute(f"ALTER TABLE {TABLA_REPORTES_OPERADORES} ADD COLUMN {columna} {tipo}")
        columnas_pozos_reporte = db.columnas_tabla(connection, TABLA_POZOS_REPORTE_OPERADOR)
        for columna, tipo in (
            ("fase", "TEXT"),
            ("banco", "TEXT"),
            ("malla", "TEXT"),
            ("tipo_perforacion", "TEXT"),
            ("metros_planificados", "REAL NOT NULL DEFAULT 0"),
            ("metros_perforados", "REAL NOT NULL DEFAULT 0"),
            ("tiempo_perforacion", "REAL NOT NULL DEFAULT 0"),
            ("tricono_bit", "TEXT"),
            ("operador", "TEXT"),
            ("equipo", "TEXT"),
            ("fecha", "TEXT"),
            ("turno", "TEXT"),
            ("estado", "TEXT NOT NULL DEFAULT 'pendiente'"),
            ("observacion", "TEXT"),
            ("es_critico", "INTEGER NOT NULL DEFAULT 0"),
            ("motivo_critico", "TEXT"),
        ):
            if columna not in columnas_pozos_reporte:
                connection.execute(f"ALTER TABLE {TABLA_POZOS_REPORTE_OPERADOR} ADD COLUMN {columna} {tipo}")
        connection.commit()


def _clave_malla(datos):
    return {
        "banco": _texto(datos.get("banco")),
        "fase": _texto(datos.get("fase")),
        "malla": _texto(datos.get("malla")),
        "fecha": _texto(datos.get("fecha")),
        "turno": _texto(datos.get("turno")),
    }


def _malla_existente(connection, datos):
    clave = _clave_malla(datos)
    fila = connection.execute(
        f"""
        SELECT id
        FROM {TABLA_MALLAS}
        WHERE banco = ? AND fase = ? AND malla = ? AND fecha = ? AND turno = ?
        """,
        tuple(clave.values()),
    ).fetchone()
    return fila["id"] if fila else None


def registrar_malla(datos, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    registro = {
        "banco": _texto(datos.get("banco")),
        "fase": _texto(datos.get("fase")),
        "malla": _texto(datos.get("malla")),
        "descripcion": _texto(datos.get("descripcion")),
        "fecha": _texto(datos.get("fecha")),
        "turno": _texto(datos.get("turno")),
    }
    with conectar_db(db_path) as connection:
        malla_id = _malla_existente(connection, registro)
        if malla_id is not None:
            connection.execute(
                f"""
                UPDATE {TABLA_MALLAS}
                SET descripcion = ?, updated_at = ?
                WHERE id = ?
                """,
                (registro["descripcion"], _ahora(), malla_id),
            )
            connection.commit()
            return {
                "ok": True,
                "malla_id": malla_id,
                "mensaje": "Malla actualizada correctamente.",
                "registro": obtener_malla(malla_id, db_path=db_path),
            }

        cursor = connection.execute(
            f"""
            INSERT INTO {TABLA_MALLAS} (
                banco, fase, malla, descripcion, fecha, turno, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                registro["banco"],
                registro["fase"],
                registro["malla"],
                registro["descripcion"],
                registro["fecha"],
                registro["turno"],
                _ahora(),
                _ahora(),
            ),
        )
        connection.commit()
        malla_id = cursor.lastrowid
        return {
            "ok": True,
            "malla_id": malla_id,
            "mensaje": "Malla registrada correctamente.",
            "registro": obtener_malla(malla_id, db_path=db_path),
        }


def obtener_malla(malla_id, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"SELECT * FROM {TABLA_MALLAS} WHERE id = ?",
            (malla_id,),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def _asegurar_malla_id(connection, datos):
    malla_id = _malla_existente(connection, datos)
    if malla_id is not None:
        return malla_id

    cursor = connection.execute(
        f"""
        INSERT INTO {TABLA_MALLAS} (
            banco, fase, malla, descripcion, fecha, turno, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _texto(datos.get("banco")),
            _texto(datos.get("fase")),
            _texto(datos.get("malla")),
            _texto(datos.get("descripcion")),
            _texto(datos.get("fecha")),
            _texto(datos.get("turno")),
            _ahora(),
            _ahora(),
        ),
    )
    return cursor.lastrowid


def registrar_pozo(datos, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    registro = {
        "banco": _texto(datos.get("banco")),
        "fase": _texto(datos.get("fase")),
        "malla": _texto(datos.get("malla")),
        "numero_pozo": _texto(datos.get("numero_pozo")),
        "tipo_pozo": _texto(datos.get("tipo_pozo")),
        "estado": normalizar_estado_pozo(datos.get("estado")),
        "metros_planificados": _numero(datos.get("metros_planificados")),
        "metros_perforados": _numero(datos.get("metros_perforados")),
        "operador": _texto(datos.get("operador")),
        "equipo": _texto(datos.get("equipo")),
        "fecha": _texto(datos.get("fecha")),
        "turno": _texto(datos.get("turno")),
        "descripcion": _texto(datos.get("descripcion")),
    }

    with conectar_db(db_path) as connection:
        malla_id = _asegurar_malla_id(connection, registro)
        existente = connection.execute(
            f"""
            SELECT id
            FROM {TABLA_POZOS}
            WHERE malla_id = ? AND numero_pozo = ?
            """,
            (malla_id, registro["numero_pozo"]),
        ).fetchone()

        if existente is not None:
            connection.execute(
                f"""
                UPDATE {TABLA_POZOS}
                SET tipo_pozo = ?,
                    estado = ?,
                    metros_planificados = ?,
                    metros_perforados = ?,
                    operador = ?,
                    equipo = ?,
                    fecha = ?,
                    turno = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    registro["tipo_pozo"],
                    registro["estado"],
                    registro["metros_planificados"],
                    registro["metros_perforados"],
                    registro["operador"],
                    registro["equipo"],
                    registro["fecha"],
                    registro["turno"],
                    _ahora(),
                    existente["id"],
                ),
            )
            connection.commit()
            pozo_id = existente["id"]
            mensaje = "Pozo actualizado correctamente."
        else:
            cursor = connection.execute(
                f"""
                INSERT INTO {TABLA_POZOS} (
                    malla_id, numero_pozo, tipo_pozo, estado,
                    metros_planificados, metros_perforados, operador, equipo,
                    fecha, turno, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    malla_id,
                    registro["numero_pozo"],
                    registro["tipo_pozo"],
                    registro["estado"],
                    registro["metros_planificados"],
                    registro["metros_perforados"],
                    registro["operador"],
                    registro["equipo"],
                    registro["fecha"],
                    registro["turno"],
                    _ahora(),
                    _ahora(),
                ),
            )
            connection.commit()
            pozo_id = cursor.lastrowid
            mensaje = "Pozo registrado correctamente."

    return {
        "ok": True,
        "pozo_id": pozo_id,
        "malla_id": malla_id,
        "mensaje": mensaje,
        "registro": obtener_pozo(pozo_id, db_path=db_path),
    }


def obtener_pozo(pozo_id, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"""
            SELECT p.*, m.banco, m.fase, m.malla, m.fecha, m.turno
            FROM {TABLA_POZOS} p
            INNER JOIN {TABLA_MALLAS} m ON m.id = p.malla_id
            WHERE p.id = ?
            """,
            (pozo_id,),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def listar_pozos(db_path=db.DB_PATH, malla_id=None):
    asegurar_tablas(db_path)
    consulta = f"""
        SELECT
            p.id,
            p.malla_id,
            m.banco,
            m.fase,
            m.malla,
            p.numero_pozo,
            p.tipo_pozo,
            p.estado,
            p.metros_planificados,
            p.metros_perforados,
            p.operador,
            p.equipo,
            COALESCE(p.fecha, m.fecha) AS fecha,
            COALESCE(p.turno, m.turno) AS turno,
            p.created_at,
            p.updated_at
        FROM {TABLA_POZOS} p
        INNER JOIN {TABLA_MALLAS} m ON m.id = p.malla_id
    """
    parametros = []
    if malla_id is not None:
        consulta += " WHERE p.malla_id = ?"
        parametros.append(malla_id)
    consulta += " ORDER BY m.fecha DESC, m.turno, m.banco, m.fase, m.malla, CAST(p.numero_pozo AS INTEGER), p.numero_pozo"
    with conectar_db(db_path) as connection:
        filas = connection.execute(consulta, parametros).fetchall()
    return pd.DataFrame([dict(fila) for fila in filas])


def listar_mallas(db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    consulta = f"""
        SELECT
            m.id AS malla_id,
            m.banco,
            m.fase,
            m.malla,
            m.descripcion,
            m.fecha,
            m.turno,
            COUNT(p.id) AS pozos_totales,
            SUM(CASE WHEN p.estado = 'perforado' THEN 1 ELSE 0 END) AS pozos_perforados,
            SUM(CASE WHEN p.estado = 'pendiente' THEN 1 ELSE 0 END) AS pozos_pendientes,
            ROUND(COALESCE(SUM(p.metros_planificados), 0), 2) AS metros_planificados,
            ROUND(COALESCE(SUM(p.metros_perforados), 0), 2) AS metros_perforados,
            CASE
                WHEN COALESCE(SUM(p.metros_planificados), 0) > 0
                THEN ROUND(COALESCE(SUM(p.metros_perforados), 0) / SUM(p.metros_planificados) * 100, 2)
                ELSE 0
            END AS porcentaje_avance
        FROM {TABLA_MALLAS} m
        LEFT JOIN {TABLA_POZOS} p ON p.malla_id = m.id
        GROUP BY m.id, m.banco, m.fase, m.malla, m.descripcion, m.fecha, m.turno
        ORDER BY m.fecha DESC, m.turno, m.banco, m.fase, m.malla
    """
    with conectar_db(db_path) as connection:
        filas = connection.execute(consulta).fetchall()
    return pd.DataFrame([dict(fila) for fila in filas])


def resumen_avance_malla(db_path=db.DB_PATH, malla_id=None):
    resumen = listar_mallas(db_path=db_path)
    if malla_id is None or resumen.empty:
        return resumen
    return resumen[resumen["malla_id"] == malla_id].copy()


def _crear_directorio_planos():
    PLANOS_MALLA_DIR.mkdir(parents=True, exist_ok=True)
    return PLANOS_MALLA_DIR


def _extension_archivo(nombre_archivo):
    return Path(nombre_archivo).suffix.lower().lstrip(".")


def _guardar_archivo_plano(archivo_subido, nombre_plano, banco, fase, malla, fecha, turno):
    if archivo_subido is None:
        return None

    directorio = _crear_directorio_planos()
    nombre_original = _texto(getattr(archivo_subido, "name", "")) or f"plano_{nombre_plano}"
    extension = Path(nombre_original).suffix or ".bin"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_seguro = "_".join(
        parte for parte in [
            _texto(nombre_plano),
            _texto(banco),
            _texto(fase),
            _texto(malla),
            _texto(fecha),
            _texto(turno),
            timestamp,
        ]
        if parte
    )
    nombre_seguro = nombre_seguro.replace(" ", "_").replace("/", "-")
    destino = directorio / f"{nombre_seguro}{extension}"

    contenido = None
    if hasattr(archivo_subido, "getbuffer"):
        contenido = bytes(archivo_subido.getbuffer())
    elif hasattr(archivo_subido, "read"):
        contenido = archivo_subido.read()
    elif hasattr(archivo_subido, "getvalue"):
        contenido = archivo_subido.getvalue()
    elif isinstance(archivo_subido, (bytes, bytearray)):
        contenido = bytes(archivo_subido)

    if contenido is None:
        raise ValueError("No fue posible leer el archivo del plano.")

    with open(destino, "wb") as archivo_destino:
        archivo_destino.write(contenido)

    return {
        "archivo_nombre": nombre_original,
        "archivo_ruta": str(destino),
        "archivo_tipo": _extension_archivo(nombre_original),
    }


def _guardar_archivo_reporte_operador(archivo_subido, operador, equipo, fecha, turno, banco, fase, malla):
    if archivo_subido is None:
        return None

    REPORTES_OPERADORES_DIR.mkdir(parents=True, exist_ok=True)
    nombre_original = _texto(getattr(archivo_subido, "name", "")) or f"reporte_{operador}"
    extension = Path(nombre_original).suffix or ".bin"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_seguro = "_".join(
        parte for parte in [
            _texto(operador),
            _texto(equipo),
            _texto(fecha),
            _texto(turno),
            _texto(banco),
            _texto(fase),
            _texto(malla),
            timestamp,
        ]
        if parte
    )
    nombre_seguro = nombre_seguro.replace(" ", "_").replace("/", "-")
    destino = REPORTES_OPERADORES_DIR / f"{nombre_seguro}{extension}"

    contenido = None
    if hasattr(archivo_subido, "getbuffer"):
        contenido = bytes(archivo_subido.getbuffer())
    elif hasattr(archivo_subido, "read"):
        contenido = archivo_subido.read()
    elif hasattr(archivo_subido, "getvalue"):
        contenido = archivo_subido.getvalue()
    elif isinstance(archivo_subido, (bytes, bytearray)):
        contenido = bytes(archivo_subido)

    if contenido is None:
        raise ValueError("No fue posible leer el archivo del reporte del operador.")

    with open(destino, "wb") as archivo_destino:
        archivo_destino.write(contenido)

    return {
        "archivo_foto": nombre_original,
        "archivo_ruta": str(destino),
        "archivo_tipo": _extension_archivo(nombre_original),
    }


def _guardar_archivo_simple(archivo_subido, destino_dir, prefijo):
    if archivo_subido is None:
        return None

    destino_dir.mkdir(parents=True, exist_ok=True)
    nombre_original = _texto(getattr(archivo_subido, "name", "")) or f"{prefijo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    extension = Path(nombre_original).suffix or ".bin"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_seguro = f"{prefijo}_{timestamp}".replace(" ", "_").replace("/", "-")
    destino = destino_dir / f"{nombre_seguro}{extension}"

    contenido = None
    if hasattr(archivo_subido, "getbuffer"):
        contenido = bytes(archivo_subido.getbuffer())
    elif hasattr(archivo_subido, "read"):
        contenido = archivo_subido.read()
    elif hasattr(archivo_subido, "getvalue"):
        contenido = archivo_subido.getvalue()
    elif isinstance(archivo_subido, (bytes, bytearray)):
        contenido = bytes(archivo_subido)

    if contenido is None:
        raise ValueError("No fue posible leer el archivo cargado.")

    with open(destino, "wb") as archivo_destino:
        archivo_destino.write(contenido)

    return {
        "nombre_archivo": nombre_original,
        "ruta_archivo": str(destino),
        "tipo_archivo": _extension_archivo(nombre_original),
    }


def _registrar_archivo_simple(tabla, archivo_info, categoria, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        cursor = connection.execute(
            f"""
            INSERT INTO {tabla} (
                nombre_archivo, ruta_archivo, tipo_archivo, fecha_carga, categoria
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                archivo_info["nombre_archivo"],
                archivo_info["ruta_archivo"],
                archivo_info["tipo_archivo"],
                _ahora(),
                categoria,
            ),
        )
        connection.commit()
        registro_id = cursor.lastrowid

    return registro_id


def registrar_archivo_plano_malla(archivo_subido, db_path=db.DB_PATH):
    if archivo_subido is None:
        return {
            "ok": False,
            "mensaje": "Debe seleccionar un archivo PDF para el plano.",
            "archivo_id": None,
            "registro": None,
        }

    archivo_info = _guardar_archivo_simple(archivo_subido, PLANOS_MALLA_DIR, "plano_malla")
    if archivo_info is None:
        return {
            "ok": False,
            "mensaje": "No fue posible guardar el archivo del plano.",
            "archivo_id": None,
            "registro": None,
        }
    archivo_info["tipo_archivo"] = archivo_info["tipo_archivo"] or "pdf"
    archivo_id = _registrar_archivo_simple(
        TABLA_ARCHIVOS_PLANOS_MALLA,
        archivo_info,
        "plano_malla",
        db_path=db_path,
    )
    return {
        "ok": True,
        "archivo_id": archivo_id,
        "mensaje": "Plano de perforación cargado correctamente.",
        "registro": obtener_archivo_plano_malla(archivo_id, db_path=db_path),
    }


def registrar_archivo_reporte_operador(archivo_subido, db_path=db.DB_PATH):
    if archivo_subido is None:
        return {
            "ok": False,
            "mensaje": "Debe seleccionar una imagen o PDF del reporte del operador.",
            "archivo_id": None,
            "registro": None,
        }

    archivo_info = _guardar_archivo_simple(archivo_subido, REPORTES_OPERADORES_DIR, "reporte_operador")
    if archivo_info is None:
        return {
            "ok": False,
            "mensaje": "No fue posible guardar el archivo del reporte del operador.",
            "archivo_id": None,
            "registro": None,
        }
    archivo_id = _registrar_archivo_simple(
        TABLA_ARCHIVOS_REPORTES_OPERADOR,
        archivo_info,
        "reporte_operador",
        db_path=db_path,
    )
    return {
        "ok": True,
        "archivo_id": archivo_id,
        "mensaje": "Reporte físico del operador cargado correctamente.",
        "registro": obtener_archivo_reporte_operador(archivo_id, db_path=db_path),
    }


def registrar_pozo_malla_control(datos, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    archivo_plano_id = datos.get("archivo_plano_id")
    if not archivo_plano_id:
        return {
            "ok": False,
            "mensaje": "Debe seleccionar un plano cargado.",
            "pozo_id": None,
            "registro": None,
        }

    registro = {
        "numero_pozo": _texto(datos.get("numero_pozo")),
        "tipo_pozo": _texto(datos.get("tipo_pozo")) or "Otro",
        "metros_planificados": _numero(datos.get("metros_planificados")),
        "estado": _texto(datos.get("estado")) or "pendiente",
        "realizado": 1 if bool(datos.get("realizado")) or _texto(datos.get("estado")).lower() == "realizado" else 0,
        "observacion": _texto(datos.get("observacion")),
    }
    if not registro["numero_pozo"]:
        return {
            "ok": False,
            "mensaje": "El número de pozo es obligatorio.",
            "pozo_id": None,
            "registro": None,
        }
    if registro["tipo_pozo"] not in TIPOS_POZO_MALLA_CONTROL:
        registro["tipo_pozo"] = "Otro"
    if registro["estado"] not in ESTADOS_POZO_MALLA_CONTROL:
        registro["estado"] = "pendiente"

    with conectar_db(db_path) as connection:
        existente = connection.execute(
            f"""
            SELECT id
            FROM {TABLA_POZOS_MALLA_CONTROL}
            WHERE archivo_plano_id = ? AND numero_pozo = ?
            """,
            (archivo_plano_id, registro["numero_pozo"]),
        ).fetchone()

        if existente is not None:
            connection.execute(
                f"""
                UPDATE {TABLA_POZOS_MALLA_CONTROL}
                SET tipo_pozo = ?,
                    metros_planificados = ?,
                    estado = ?,
                    realizado = ?,
                    observacion = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    registro["tipo_pozo"],
                    registro["metros_planificados"],
                    registro["estado"],
                    registro["realizado"],
                    registro["observacion"],
                    _ahora(),
                    existente["id"],
                ),
            )
            connection.commit()
            pozo_id = existente["id"]
            mensaje = "Pozo de la malla actualizado correctamente."
        else:
            cursor = connection.execute(
                f"""
                INSERT INTO {TABLA_POZOS_MALLA_CONTROL} (
                    archivo_plano_id, numero_pozo, tipo_pozo, metros_planificados,
                    estado, realizado, observacion, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    archivo_plano_id,
                    registro["numero_pozo"],
                    registro["tipo_pozo"],
                    registro["metros_planificados"],
                    registro["estado"],
                    registro["realizado"],
                    registro["observacion"],
                    _ahora(),
                    _ahora(),
                ),
            )
            connection.commit()
            pozo_id = cursor.lastrowid
            mensaje = "Pozo de la malla registrado correctamente."

    return {
        "ok": True,
        "pozo_id": pozo_id,
        "mensaje": mensaje,
        "registro": obtener_pozo_malla_control(pozo_id, db_path=db_path),
    }


def obtener_pozo_malla_control(pozo_id, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"""
            SELECT p.*, a.nombre_archivo, a.ruta_archivo, a.tipo_archivo, a.fecha_carga
            FROM {TABLA_POZOS_MALLA_CONTROL} p
            INNER JOIN {TABLA_ARCHIVOS_PLANOS_MALLA} a ON a.id = p.archivo_plano_id
            WHERE p.id = ?
            """,
            (pozo_id,),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def listar_pozos_malla_control(db_path=db.DB_PATH, archivo_plano_id=None):
    asegurar_tablas(db_path)
    consulta = f"""
        SELECT
            p.id,
            p.archivo_plano_id,
            a.nombre_archivo,
            a.ruta_archivo,
            a.tipo_archivo,
            a.fecha_carga,
            p.numero_pozo,
            p.tipo_pozo,
            p.metros_planificados,
            p.estado,
            p.realizado,
            p.observacion,
            p.created_at,
            p.updated_at
        FROM {TABLA_POZOS_MALLA_CONTROL} p
        INNER JOIN {TABLA_ARCHIVOS_PLANOS_MALLA} a ON a.id = p.archivo_plano_id
    """
    parametros = []
    if archivo_plano_id is not None:
        consulta += " WHERE p.archivo_plano_id = ?"
        parametros.append(archivo_plano_id)
    consulta += " ORDER BY CAST(p.numero_pozo AS INTEGER), p.numero_pozo, p.id"
    with conectar_db(db_path) as connection:
        filas = connection.execute(consulta, parametros).fetchall()
    return pd.DataFrame([dict(fila) for fila in filas])


def actualizar_pozo_malla_control(pozo_id, datos, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        existente = connection.execute(
            f"SELECT id FROM {TABLA_POZOS_MALLA_CONTROL} WHERE id = ?",
            (pozo_id,),
        ).fetchone()
        if existente is None:
            return {
                "ok": False,
                "mensaje": "El pozo no existe.",
                "pozo_id": None,
                "registro": None,
            }

        estado = _texto(datos.get("estado")).lower() or "pendiente"
        if estado not in ESTADOS_POZO_MALLA_CONTROL:
            estado = "pendiente"
        tipo_pozo = _texto(datos.get("tipo_pozo")) or "Otro"
        if tipo_pozo not in TIPOS_POZO_MALLA_CONTROL:
            tipo_pozo = "Otro"
        realizado = 1 if bool(datos.get("realizado")) or estado == "realizado" else 0

        connection.execute(
            f"""
            UPDATE {TABLA_POZOS_MALLA_CONTROL}
            SET numero_pozo = ?,
                tipo_pozo = ?,
                metros_planificados = ?,
                estado = ?,
                realizado = ?,
                observacion = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                _texto(datos.get("numero_pozo")),
                tipo_pozo,
                _numero(datos.get("metros_planificados")),
                estado,
                realizado,
                _texto(datos.get("observacion")),
                _ahora(),
                pozo_id,
            ),
        )
        connection.commit()

    return {
        "ok": True,
        "pozo_id": pozo_id,
        "mensaje": "Pozo actualizado correctamente.",
        "registro": obtener_pozo_malla_control(pozo_id, db_path=db_path),
    }


def resumen_malla_control(db_path=db.DB_PATH, archivo_plano_id=None):
    pozos = listar_pozos_malla_control(db_path=db_path, archivo_plano_id=archivo_plano_id)
    if pozos.empty:
        return {
            "pozos_totales": 0,
            "pozos_realizados": 0,
            "pozos_pendientes": 0,
            "metros_planificados_totales": 0.0,
            "metros_realizados_estimados": 0.0,
            "porcentaje_avance": 0.0,
            "avance_metros": 0.0,
        }

    total = int(len(pozos))
    realizados = int(pozos["realizado"].fillna(0).astype(int).sum()) if "realizado" in pozos.columns else 0
    pendientes = total - realizados
    metros_planificados = float(pd.to_numeric(pozos.get("metros_planificados", 0), errors="coerce").fillna(0).sum())
    pozos_realizados = pozos[pozos["realizado"].fillna(0).astype(int) == 1] if "realizado" in pozos.columns else pd.DataFrame()
    metros_realizados_estimados = float(pd.to_numeric(pozos_realizados.get("metros_planificados", 0), errors="coerce").fillna(0).sum()) if not pozos_realizados.empty else 0.0
    porcentaje_avance = round((realizados / total) * 100, 2) if total else 0.0
    avance_metros = round((metros_realizados_estimados / metros_planificados) * 100, 2) if metros_planificados else 0.0
    return {
        "pozos_totales": total,
        "pozos_realizados": realizados,
        "pozos_pendientes": pendientes,
        "metros_planificados_totales": round(metros_planificados, 2),
        "metros_realizados_estimados": round(metros_realizados_estimados, 2),
        "porcentaje_avance": porcentaje_avance,
        "avance_metros": avance_metros,
    }


def obtener_archivo_plano_malla(archivo_id, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"SELECT * FROM {TABLA_ARCHIVOS_PLANOS_MALLA} WHERE id = ?",
            (archivo_id,),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def obtener_archivo_reporte_operador(archivo_id, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"SELECT * FROM {TABLA_ARCHIVOS_REPORTES_OPERADOR} WHERE id = ?",
            (archivo_id,),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def listar_archivos_planos_malla(db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        filas = connection.execute(
            f"""
            SELECT *
            FROM {TABLA_ARCHIVOS_PLANOS_MALLA}
            ORDER BY fecha_carga DESC, id DESC
            """
        ).fetchall()
    return pd.DataFrame([dict(fila) for fila in filas])


def listar_archivos_reportes_operador(db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        filas = connection.execute(
            f"""
            SELECT *
            FROM {TABLA_ARCHIVOS_REPORTES_OPERADOR}
            ORDER BY fecha_carga DESC, id DESC
            """
        ).fetchall()
    return pd.DataFrame([dict(fila) for fila in filas])


def limpiar_avance_malla(db_path=db.DB_PATH, limpiar_archivos=False):
    asegurar_tablas(db_path)
    tablas = [
        TABLA_POZOS_REPORTE_OPERADOR,
        TABLA_REPORTES_OPERADORES,
        TABLA_POZOS_PLANO,
        TABLA_PLANOS,
        TABLA_POZOS,
        TABLA_MALLAS,
        TABLA_ARCHIVOS_REPORTES_OPERADOR,
        TABLA_ARCHIVOS_PLANOS_MALLA,
    ]
    with conectar_db(db_path) as connection:
        for tabla in tablas:
            connection.execute(f"DELETE FROM {tabla}")
        connection.commit()

    if limpiar_archivos:
        for directorio in (PLANOS_MALLA_DIR, REPORTES_OPERADORES_DIR):
            if directorio.exists():
                for path in directorio.iterdir():
                    if path.is_file():
                        path.unlink()

    return {
        "ok": True,
        "mensaje": "Avance de malla limpio correctamente.",
        "tablas": tablas,
    }


def _obtener_plano_coincidente(connection, datos):
    fila = connection.execute(
        f"""
        SELECT id
        FROM {TABLA_PLANOS}
        WHERE banco = ? AND fase = ? AND malla = ? AND fecha = ? AND turno = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (
            _texto(datos.get("banco")),
            _texto(datos.get("fase")),
            _texto(datos.get("malla")),
            _texto(datos.get("fecha")),
            _texto(datos.get("turno")),
        ),
    ).fetchone()
    return fila["id"] if fila else None


def registrar_plano_malla(datos, archivo_subido=None, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    base = {
        "nombre_plano": _texto(datos.get("nombre_plano")),
        "banco": _texto(datos.get("banco")),
        "fase": _texto(datos.get("fase")),
        "malla": _texto(datos.get("malla")),
        "fecha": _texto(datos.get("fecha")),
        "turno": _texto(datos.get("turno")),
        "observacion": _texto(datos.get("observacion")),
    }
    if not base["nombre_plano"] or not base["banco"] or not base["fase"] or not base["malla"]:
        return {
            "ok": False,
            "mensaje": "Nombre del plano, banco, fase y malla son obligatorios.",
            "plano_id": None,
            "registro": None,
        }

    archivo_info = _guardar_archivo_plano(
        archivo_subido,
        base["nombre_plano"],
        base["banco"],
        base["fase"],
        base["malla"],
        base["fecha"],
        base["turno"],
    )
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"""
            SELECT id, archivo_nombre, archivo_ruta, archivo_tipo
            FROM {TABLA_PLANOS}
            WHERE nombre_plano = ? AND banco = ? AND fase = ? AND malla = ? AND fecha = ? AND turno = ?
            """,
            (
                base["nombre_plano"],
                base["banco"],
                base["fase"],
                base["malla"],
                base["fecha"],
                base["turno"],
            ),
        ).fetchone()
        if fila is not None:
            archivo_nombre = archivo_info["archivo_nombre"] if archivo_info else fila["archivo_nombre"]
            archivo_ruta = archivo_info["archivo_ruta"] if archivo_info else fila["archivo_ruta"]
            archivo_tipo = archivo_info["archivo_tipo"] if archivo_info else fila["archivo_tipo"]
            connection.execute(
                f"""
                UPDATE {TABLA_PLANOS}
                SET observacion = ?, archivo_nombre = ?, archivo_ruta = ?, archivo_tipo = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    base["observacion"],
                    archivo_nombre,
                    archivo_ruta,
                    archivo_tipo,
                    _ahora(),
                    fila["id"],
                ),
            )
            connection.commit()
            plano_id = fila["id"]
            mensaje = "Plano actualizado correctamente."
        else:
            cursor = connection.execute(
                f"""
                INSERT INTO {TABLA_PLANOS} (
                    nombre_plano, banco, fase, malla, fecha, turno,
                    archivo_nombre, archivo_ruta, archivo_tipo, observacion,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    base["nombre_plano"],
                    base["banco"],
                    base["fase"],
                    base["malla"],
                    base["fecha"],
                    base["turno"],
                    archivo_info["archivo_nombre"] if archivo_info else "",
                    archivo_info["archivo_ruta"] if archivo_info else "",
                    archivo_info["archivo_tipo"] if archivo_info else "",
                    base["observacion"],
                    _ahora(),
                    _ahora(),
                ),
            )
            connection.commit()
            plano_id = cursor.lastrowid
            mensaje = "Plano registrado correctamente."

    return {
        "ok": True,
        "plano_id": plano_id,
        "mensaje": mensaje,
        "registro": obtener_plano_malla(plano_id, db_path=db_path),
    }


def obtener_plano_malla(plano_id, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"SELECT * FROM {TABLA_PLANOS} WHERE id = ?",
            (plano_id,),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def registrar_reporte_operador(datos, archivo_subido=None, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    base = {
        "operador": _texto(datos.get("operador")),
        "equipo": _texto(datos.get("equipo")),
        "fecha": _texto(datos.get("fecha")),
        "turno": _texto(datos.get("turno")),
        "banco": _texto(datos.get("banco")),
        "fase": _texto(datos.get("fase")),
        "malla": _texto(datos.get("malla")),
        "observacion": _texto(datos.get("observacion")),
    }
    if not base["operador"] or not base["banco"] or not base["fase"] or not base["malla"]:
        return {
            "ok": False,
            "mensaje": "Operador, banco, fase y malla son obligatorios.",
            "reporte_id": None,
            "registro": None,
        }

    archivo_info = _guardar_archivo_reporte_operador(
        archivo_subido,
        base["operador"],
        base["equipo"],
        base["fecha"],
        base["turno"],
        base["banco"],
        base["fase"],
        base["malla"],
    )
    with conectar_db(db_path) as connection:
        plano_id = _obtener_plano_coincidente(connection, base)
        cursor = connection.execute(
            f"""
            INSERT INTO {TABLA_REPORTES_OPERADORES} (
                plano_id, operador, equipo, fecha, turno, banco, fase, malla,
                archivo_foto, archivo_ruta, archivo_tipo, observacion, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plano_id,
                base["operador"],
                base["equipo"],
                base["fecha"],
                base["turno"],
                base["banco"],
                base["fase"],
                base["malla"],
                archivo_info["archivo_foto"] if archivo_info else "",
                archivo_info["archivo_ruta"] if archivo_info else "",
                archivo_info["archivo_tipo"] if archivo_info else "",
                base["observacion"],
                _ahora(),
                _ahora(),
            ),
        )
        connection.commit()
        reporte_id = cursor.lastrowid

    return {
        "ok": True,
        "reporte_id": reporte_id,
        "mensaje": "Reporte del operador registrado correctamente.",
        "registro": obtener_reporte_operador(reporte_id, db_path=db_path),
    }


def obtener_reporte_operador(reporte_id, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"""
            SELECT r.*, p.nombre_plano
            FROM {TABLA_REPORTES_OPERADORES} r
            LEFT JOIN {TABLA_PLANOS} p ON p.id = r.plano_id
            WHERE r.id = ?
            """,
            (reporte_id,),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def listar_reportes_operador(db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        filas = connection.execute(
            f"""
            SELECT r.*, p.nombre_plano
            FROM {TABLA_REPORTES_OPERADORES} r
            LEFT JOIN {TABLA_PLANOS} p ON p.id = r.plano_id
            ORDER BY fecha DESC, turno, banco, fase, malla, created_at DESC
            """
        ).fetchall()
    return pd.DataFrame([dict(fila) for fila in filas])


def registrar_detalle_reporte_operador(datos, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    reporte_id = datos.get("reporte_id")
    if not reporte_id:
        return {
            "ok": False,
            "mensaje": "Debe seleccionar un reporte del operador.",
            "detalle_id": None,
            "registro": None,
        }

    registro = {
        "numero_pozo": _texto(datos.get("numero_pozo")),
        "fase": _texto(datos.get("fase")),
        "banco": _texto(datos.get("banco")),
        "malla": _texto(datos.get("malla")),
        "tipo_perforacion": _texto(datos.get("tipo_perforacion")),
        "metros_planificados": _numero(datos.get("metros_planificados")),
        "metros_perforados": _numero(datos.get("metros_perforados")),
        "tiempo_perforacion": _numero(datos.get("tiempo_perforacion")),
        "tricono_bit": _texto(datos.get("tricono_bit")),
        "operador": _texto(datos.get("operador")),
        "equipo": _texto(datos.get("equipo")),
        "fecha": _texto(datos.get("fecha")),
        "turno": _texto(datos.get("turno")),
        "estado": normalizar_estado_pozo(datos.get("estado")),
        "observacion": _texto(datos.get("observacion")),
        "es_critico": 1 if bool(datos.get("es_critico")) else 0,
        "motivo_critico": _texto(datos.get("motivo_critico")),
    }
    if not registro["numero_pozo"]:
        return {
            "ok": False,
            "mensaje": "El número de pozo es obligatorio.",
            "detalle_id": None,
            "registro": None,
        }

    with conectar_db(db_path) as connection:
        existente = connection.execute(
            f"""
            SELECT id
            FROM {TABLA_POZOS_REPORTE_OPERADOR}
            WHERE reporte_id = ? AND numero_pozo = ? AND COALESCE(tipo_perforacion, '') = COALESCE(?, '')
            """,
            (reporte_id, registro["numero_pozo"], registro["tipo_perforacion"]),
        ).fetchone()
        if existente is not None:
            connection.execute(
                f"""
                UPDATE {TABLA_POZOS_REPORTE_OPERADOR}
                SET fase = ?,
                    banco = ?,
                    malla = ?,
                    metros_planificados = ?,
                    metros_perforados = ?,
                    tiempo_perforacion = ?,
                    tricono_bit = ?,
                    operador = ?,
                    equipo = ?,
                    fecha = ?,
                    turno = ?,
                    estado = ?,
                    observacion = ?,
                    es_critico = ?,
                    motivo_critico = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    registro["fase"],
                    registro["banco"],
                    registro["malla"],
                    registro["metros_planificados"],
                    registro["metros_perforados"],
                    registro["tiempo_perforacion"],
                    registro["tricono_bit"],
                    registro["operador"],
                    registro["equipo"],
                    registro["fecha"],
                    registro["turno"],
                    registro["estado"],
                    registro["observacion"],
                    registro["es_critico"],
                    registro["motivo_critico"],
                    _ahora(),
                    existente["id"],
                ),
            )
            connection.commit()
            detalle_id = existente["id"]
            mensaje = "Detalle del reporte actualizado correctamente."
        else:
            cursor = connection.execute(
                f"""
                INSERT INTO {TABLA_POZOS_REPORTE_OPERADOR} (
                    reporte_id, numero_pozo, fase, banco, malla, tipo_perforacion,
                    metros_planificados, metros_perforados, tiempo_perforacion, tricono_bit,
                    operador, equipo, fecha, turno, estado, observacion, es_critico,
                    motivo_critico, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reporte_id,
                    registro["numero_pozo"],
                    registro["fase"],
                    registro["banco"],
                    registro["malla"],
                    registro["tipo_perforacion"],
                    registro["metros_planificados"],
                    registro["metros_perforados"],
                    registro["tiempo_perforacion"],
                    registro["tricono_bit"],
                    registro["operador"],
                    registro["equipo"],
                    registro["fecha"],
                    registro["turno"],
                    registro["estado"],
                    registro["observacion"],
                    registro["es_critico"],
                    registro["motivo_critico"],
                    _ahora(),
                    _ahora(),
                ),
            )
            connection.commit()
            detalle_id = cursor.lastrowid
            mensaje = "Detalle del reporte registrado correctamente."

    return {
        "ok": True,
        "detalle_id": detalle_id,
        "reporte_id": reporte_id,
        "mensaje": mensaje,
        "registro": obtener_detalle_reporte_operador(detalle_id, db_path=db_path),
    }


def obtener_detalle_reporte_operador(detalle_id, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"""
            SELECT d.*, r.operador AS reporte_operador, r.equipo AS reporte_equipo, r.fecha AS reporte_fecha, r.turno AS reporte_turno,
                   r.banco AS reporte_banco, r.fase AS reporte_fase, r.malla AS reporte_malla, r.archivo_foto, r.archivo_ruta, r.archivo_tipo
            FROM {TABLA_POZOS_REPORTE_OPERADOR} d
            INNER JOIN {TABLA_REPORTES_OPERADORES} r ON r.id = d.reporte_id
            WHERE d.id = ?
            """,
            (detalle_id,),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def listar_pozos_reporte_operador(db_path=db.DB_PATH, reporte_id=None):
    asegurar_tablas(db_path)
    consulta = f"""
        SELECT
            d.id,
            d.reporte_id,
            r.operador AS reporte_operador,
            r.equipo AS reporte_equipo,
            r.fecha AS reporte_fecha,
            r.turno AS reporte_turno,
            r.banco AS reporte_banco,
            r.fase AS reporte_fase,
            r.malla AS reporte_malla,
            d.numero_pozo,
            d.fase,
            d.banco,
            d.malla,
            d.tipo_perforacion,
            d.metros_planificados,
            d.metros_perforados,
            d.tiempo_perforacion,
            d.tricono_bit,
            d.operador,
            d.equipo,
            d.fecha,
            d.turno,
            d.estado,
            d.observacion,
            d.es_critico,
            d.motivo_critico,
            d.created_at,
            d.updated_at
        FROM {TABLA_POZOS_REPORTE_OPERADOR} d
        INNER JOIN {TABLA_REPORTES_OPERADORES} r ON r.id = d.reporte_id
    """
    parametros = []
    if reporte_id is not None:
        consulta += " WHERE d.reporte_id = ?"
        parametros.append(reporte_id)
    consulta += " ORDER BY r.fecha DESC, r.turno, r.banco, r.fase, r.malla, CAST(d.numero_pozo AS INTEGER), d.numero_pozo"
    with conectar_db(db_path) as connection:
        filas = connection.execute(consulta, parametros).fetchall()
    return pd.DataFrame([dict(fila) for fila in filas])


def comparar_reporte_operador_con_plano(reporte_id, db_path=db.DB_PATH, plano_id=None):
    reporte = obtener_reporte_operador(reporte_id, db_path=db_path)
    if reporte is None:
        return {
            "ok": False,
            "mensaje": "El reporte del operador no existe.",
            "reporte": None,
            "plano": None,
            "coincidentes": pd.DataFrame(),
            "no_encontrados_plano": pd.DataFrame(),
            "plan_no_reportado": pd.DataFrame(),
            "resumen": {},
        }

    if plano_id is None:
        plano_id = int(reporte["plano_id"]) if reporte.get("plano_id") else None
    if plano_id is None:
        with conectar_db(db_path) as connection:
            plano_id = _obtener_plano_coincidente(connection, reporte)
    if plano_id is None:
        return {
            "ok": True,
            "mensaje": "No se encontró un plano coincidente para comparar.",
            "reporte": reporte,
            "plano": None,
            "coincidentes": pd.DataFrame(),
            "no_encontrados_plano": pd.DataFrame(),
            "plan_no_reportado": pd.DataFrame(),
            "resumen": {
                "pozos_coincidentes": 0,
                "pozos_no_encontrados_plano": 0,
                "pozos_plan_no_reportados": 0,
                "metros_perforados_total": 0.0,
                "metros_planificados_plano_total": 0.0,
                "diferencia_metros_total": 0.0,
            },
        }

    plano = obtener_plano_malla(plano_id, db_path=db_path)
    reportes = listar_pozos_reporte_operador(db_path=db_path, reporte_id=reporte_id)
    planos = listar_pozos_plano(db_path=db_path, plano_id=plano_id)
    if reportes.empty:
        return {
            "ok": True,
            "mensaje": "El reporte no tiene pozos registrados.",
            "reporte": reporte,
            "plano": plano,
            "coincidentes": pd.DataFrame(),
            "no_encontrados_plano": pd.DataFrame(),
            "plan_no_reportado": planos.copy() if not planos.empty else pd.DataFrame(),
            "resumen": {
                "pozos_coincidentes": 0,
                "pozos_no_encontrados_plano": 0,
                "pozos_plan_no_reportados": int(len(planos)) if not planos.empty else 0,
                "metros_perforados_total": 0.0,
                "metros_planificados_plano_total": float(planos["metros_planificados"].sum()) if not planos.empty else 0.0,
                "diferencia_metros_total": 0.0,
            },
        }

    reporte_df = reportes.copy()
    plano_df = planos.copy() if not planos.empty else pd.DataFrame()
    reporte_df["numero_pozo_norm"] = reporte_df["numero_pozo"].astype(str).str.strip()
    if not plano_df.empty:
        plano_df["numero_pozo_norm"] = plano_df["numero_pozo"].astype(str).str.strip()
    coincidentes = reporte_df.merge(
        plano_df,
        on="numero_pozo_norm",
        how="inner",
        suffixes=("_reporte", "_plano"),
    ) if not plano_df.empty else pd.DataFrame()
    no_encontrados = reporte_df[~reporte_df["numero_pozo_norm"].isin(coincidentes["numero_pozo_norm"] if not coincidentes.empty else [])].copy()
    plan_no_reportado = plano_df[~plano_df["numero_pozo_norm"].isin(coincidentes["numero_pozo_norm"] if not coincidentes.empty else [])].copy() if not plano_df.empty else pd.DataFrame()

    metros_perforados_total = float(reporte_df["metros_perforados"].sum()) if "metros_perforados" in reporte_df.columns else 0.0
    metros_planificados_plano_total = float(plano_df["metros_planificados"].sum()) if not plano_df.empty and "metros_planificados" in plano_df.columns else 0.0
    diferencia_metros_total = metros_perforados_total - metros_planificados_plano_total

    if not coincidentes.empty:
        if "metros_planificados_plano" in coincidentes.columns and "metros_perforados" in coincidentes.columns:
            coincidentes["diferencia_metros"] = coincidentes["metros_perforados"].fillna(0) - coincidentes["metros_planificados_plano"].fillna(0)

    resumen = {
        "pozos_coincidentes": int(len(coincidentes)),
        "pozos_no_encontrados_plano": int(len(no_encontrados)),
        "pozos_plan_no_reportados": int(len(plan_no_reportado)),
        "metros_perforados_total": round(metros_perforados_total, 2),
        "metros_planificados_plano_total": round(metros_planificados_plano_total, 2),
        "diferencia_metros_total": round(diferencia_metros_total, 2),
    }
    return {
        "ok": True,
        "mensaje": "Comparación ejecutada correctamente.",
        "reporte": reporte,
        "plano": plano,
        "coincidentes": coincidentes,
        "no_encontrados_plano": no_encontrados,
        "plan_no_reportado": plan_no_reportado,
        "resumen": resumen,
    }


def listar_pozos_plano(db_path=db.DB_PATH, plano_id=None):
    asegurar_tablas(db_path)
    consulta = f"""
        SELECT
            p.id,
            p.plano_id,
            pl.nombre_plano,
            pl.banco,
            pl.fase,
            pl.malla,
            pl.fecha,
            pl.turno,
            p.numero_pozo,
            p.tipo_pozo,
            p.metros_planificados,
            p.estado_inicial,
            p.coordenada_x,
            p.coordenada_y,
            p.observacion,
            p.created_at,
            p.updated_at
        FROM {TABLA_POZOS_PLANO} p
        INNER JOIN {TABLA_PLANOS} pl ON pl.id = p.plano_id
    """
    parametros = []
    if plano_id is not None:
        consulta += " WHERE p.plano_id = ?"
        parametros.append(plano_id)
    consulta += " ORDER BY pl.fecha DESC, pl.turno, pl.banco, pl.fase, pl.malla, CAST(p.numero_pozo AS INTEGER), p.numero_pozo"
    with conectar_db(db_path) as connection:
        filas = connection.execute(consulta, parametros).fetchall()
    return pd.DataFrame([dict(fila) for fila in filas])


def registrar_pozo_plano(datos, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    plano_id = datos.get("plano_id")
    if not plano_id:
        return {
            "ok": False,
            "mensaje": "Debe seleccionar un plano base.",
            "pozo_id": None,
            "registro": None,
        }

    registro = {
        "numero_pozo": _texto(datos.get("numero_pozo")),
        "tipo_pozo": _texto(datos.get("tipo_pozo")),
        "metros_planificados": _numero(datos.get("metros_planificados")),
        "estado_inicial": normalizar_estado_pozo(datos.get("estado_inicial")),
        "coordenada_x": _numero(datos.get("coordenada_x")),
        "coordenada_y": _numero(datos.get("coordenada_y")),
        "observacion": _texto(datos.get("observacion")),
    }
    if not registro["numero_pozo"]:
        return {
            "ok": False,
            "mensaje": "El número de pozo es obligatorio.",
            "pozo_id": None,
            "registro": None,
        }

    with conectar_db(db_path) as connection:
        existente = connection.execute(
            f"""
            SELECT id
            FROM {TABLA_POZOS_PLANO}
            WHERE plano_id = ? AND numero_pozo = ?
            """,
            (plano_id, registro["numero_pozo"]),
        ).fetchone()

        if existente is not None:
            connection.execute(
                f"""
                UPDATE {TABLA_POZOS_PLANO}
                SET tipo_pozo = ?,
                    metros_planificados = ?,
                    estado_inicial = ?,
                    coordenada_x = ?,
                    coordenada_y = ?,
                    observacion = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    registro["tipo_pozo"],
                    registro["metros_planificados"],
                    registro["estado_inicial"],
                    registro["coordenada_x"],
                    registro["coordenada_y"],
                    registro["observacion"],
                    _ahora(),
                    existente["id"],
                ),
            )
            connection.commit()
            pozo_id = existente["id"]
            mensaje = "Pozo del plano actualizado correctamente."
        else:
            cursor = connection.execute(
                f"""
                INSERT INTO {TABLA_POZOS_PLANO} (
                    plano_id, numero_pozo, tipo_pozo, metros_planificados, estado_inicial, coordenada_x, coordenada_y, observacion, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plano_id,
                    registro["numero_pozo"],
                    registro["tipo_pozo"],
                    registro["metros_planificados"],
                    registro["estado_inicial"],
                    registro["coordenada_x"],
                    registro["coordenada_y"],
                    registro["observacion"],
                    _ahora(),
                    _ahora(),
                ),
            )
            connection.commit()
            pozo_id = cursor.lastrowid
            mensaje = "Pozo del plano registrado correctamente."

    return {
        "ok": True,
        "pozo_id": pozo_id,
        "plano_id": plano_id,
        "mensaje": mensaje,
        "registro": obtener_pozo_plano(pozo_id, db_path=db_path),
    }


def obtener_pozo_plano(pozo_id, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        fila = connection.execute(
            f"""
            SELECT p.*, pl.nombre_plano, pl.banco, pl.fase, pl.malla, pl.fecha, pl.turno
            FROM {TABLA_POZOS_PLANO} p
            INNER JOIN {TABLA_PLANOS} pl ON pl.id = p.plano_id
            WHERE p.id = ?
            """,
            (pozo_id,),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def editar_pozo_plano(pozo_id, datos, db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    with conectar_db(db_path) as connection:
        existente = connection.execute(
            f"SELECT id FROM {TABLA_POZOS_PLANO} WHERE id = ?",
            (pozo_id,),
        ).fetchone()
        if existente is None:
            return {
                "ok": False,
                "mensaje": "El pozo del plano no existe.",
                "pozo_id": None,
                "registro": None,
            }

        registro = {
            "tipo_pozo": _texto(datos.get("tipo_pozo")),
            "metros_planificados": _numero(datos.get("metros_planificados")),
            "estado_inicial": normalizar_estado_pozo(datos.get("estado")),
            "coordenada_x": _numero(datos.get("coordenada_x")),
            "coordenada_y": _numero(datos.get("coordenada_y")),
            "observacion": _texto(datos.get("observacion")),
        }
        connection.execute(
            f"""
            UPDATE {TABLA_POZOS_PLANO}
            SET tipo_pozo = ?,
                metros_planificados = ?,
                estado_inicial = ?,
                coordenada_x = ?,
                coordenada_y = ?,
                observacion = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                registro["tipo_pozo"],
                registro["metros_planificados"],
                registro["estado_inicial"],
                registro["coordenada_x"],
                registro["coordenada_y"],
                registro["observacion"],
                _ahora(),
                pozo_id,
            ),
        )
        connection.commit()

    return {
        "ok": True,
        "pozo_id": pozo_id,
        "mensaje": "Pozo del plano actualizado correctamente.",
        "registro": obtener_pozo_plano(pozo_id, db_path=db_path),
    }


def resumen_planos_malla(db_path=db.DB_PATH):
    planos = listar_planos_malla(db_path=db_path)
    return planos


def listar_planos_malla(db_path=db.DB_PATH):
    asegurar_tablas(db_path)
    planos = pd.DataFrame()
    with conectar_db(db_path) as connection:
        filas = connection.execute(
            f"""
            SELECT *
            FROM {TABLA_PLANOS}
            ORDER BY fecha DESC, turno, banco, fase, malla, created_at DESC
            """
        ).fetchall()
        planos = pd.DataFrame([dict(fila) for fila in filas])

    if planos.empty:
        return planos

    pozos = listar_pozos_plano(db_path=db_path)
    resumenes = []
    for _, fila in planos.iterrows():
        bloque = pozos[pozos["plano_id"] == fila["id"]].copy() if not pozos.empty else pd.DataFrame()
        tipos = []
        estados = []
        total_pozos = 0
        metros_planificados = 0.0
        if not bloque.empty:
            total_pozos = len(bloque)
            metros_planificados = pd.to_numeric(bloque.get("metros_planificados", 0), errors="coerce").fillna(0).sum()
            tipos = sorted(dict.fromkeys(bloque.get("tipo_pozo", pd.Series(dtype=str)).dropna().astype(str).str.strip()))
            estados = sorted(dict.fromkeys(bloque.get("estado_inicial", pd.Series(dtype=str)).dropna().astype(str).str.strip()))
        resumenes.append({
            "plano_id": fila["id"],
            "nombre_plano": fila.get("nombre_plano", ""),
            "banco": fila.get("banco", ""),
            "fase": fila.get("fase", ""),
            "malla": fila.get("malla", ""),
            "fecha": fila.get("fecha", ""),
            "turno": fila.get("turno", ""),
            "archivo_nombre": fila.get("archivo_nombre", ""),
            "archivo_ruta": fila.get("archivo_ruta", ""),
            "observacion": fila.get("observacion", ""),
            "total_pozos_registrados": total_pozos,
            "metros_planificados": round(float(metros_planificados), 2),
            "tipos_pozo": ", ".join(tipos),
            "estados": ", ".join(estados),
        })

    return pd.DataFrame(resumenes)


def mapa_pozos_plano(plano_id, db_path=db.DB_PATH):
    pozos = listar_pozos_plano(db_path=db_path, plano_id=plano_id)
    if pozos.empty:
        return pozos
    return pozos.copy()


def mapa_pozos_plano(plano_id, db_path=db.DB_PATH):
    pozos = listar_pozos_plano(db_path=db_path, plano_id=plano_id)
    if pozos.empty:
        return pozos
    return pozos.copy()
