from datetime import datetime
from pathlib import Path
import base64
import mimetypes
import re
from unicodedata import normalize

import pandas as pd

from config import DOCS_ROOT, OPERATIONAL_DATA_ROOT
import db


DOCS_EXTENSIONS = {".pdf", ".md", ".txt", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
CATEGORIAS_INICIALES = [
    "Procedimientos operacionales",
    "Seguridad",
    "Mantención",
    "Hidráulica",
    "Eléctrica",
    "Perforación",
    "EDC / Controles Críticos",
    "ART",
    "Manual fabricante",
    "Troubleshooting",
]

TABLA_DOCUMENTOS = "documentacion_tecnica"
TABLA_BIBLIOTECA_DOCUMENTOS = "biblioteca_documentos"
BIBLIOTECA_TECNICA_ROOT = OPERATIONAL_DATA_ROOT / "biblioteca_tecnica"

TIPOS_DOCUMENTO_BIBLIOTECA = [
    "Manual de equipo",
    "Procedimiento de perforación",
    "Instructivo operacional",
    "Checklist",
    "Plan de mantenimiento",
    "Seguridad",
    "Aceros de perforación",
    "Otro",
]

EQUIPOS_BIBLIOTECA = [
    "Sandvik D75KS",
    "FlexiROC D65",
    "SmartROC D65",
    "D90KS",
    "FlexiROC T40",
    "General",
]

SUBCARPETAS_BIBLIOTECA = {
    "Manual de equipo": "manuales_equipos",
    "Procedimiento de perforación": "procedimientos",
    "Instructivo operacional": "procedimientos",
    "Checklist": "checklist",
    "Plan de mantenimiento": "mantenimiento",
    "Seguridad": "seguridad",
    "Aceros de perforación": "aceros",
    "Otro": "otros",
}

SUGERENCIAS_DOCUMENTOS_BIBLIOTECA = [
    "Manual Sandvik D75KS",
    "Manual FlexiROC D65",
    "Manual SmartROC D65",
    "Procedimiento de perforación producción",
    "Procedimiento de precorte",
    "Checklist preoperacional D75KS",
    "Checklist preoperacional D65",
    "Procedimiento cambio de aceros",
    "Estándar de comunicación entre turnos",
    "Procedimiento ante falla operacional",
    "Procedimiento de traslado entre pozos",
    "Parámetros de perforación por terreno",
]

BIBLIOTECA_DOCUMENTOS_COLUMNS = {
    "id_documento": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "titulo": "TEXT NOT NULL",
    "tipo_documento": "TEXT",
    "equipo_asociado": "TEXT",
    "categoria": "TEXT",
    "criticidad": "TEXT",
    "observacion": "TEXT",
    "nombre_archivo": "TEXT",
    "ruta_archivo": "TEXT",
    "extension": "TEXT",
    "fecha_carga": "TEXT",
    "activo": "INTEGER DEFAULT 1",
}

DOCUMENTOS_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "nombre": "TEXT NOT NULL",
    "categoria": "TEXT NOT NULL",
    "fabricante": "TEXT",
    "equipo_asociado": "TEXT",
    "version": "TEXT",
    "fecha_documento": "TEXT",
    "tipo_documento": "TEXT",
    "palabras_clave": "TEXT",
    "criticidad": "TEXT",
    "autor_responsable": "TEXT",
    "descripcion": "TEXT",
    "ruta_relativa": "TEXT NOT NULL UNIQUE",
    "extension": "TEXT",
    "tamano_bytes": "INTEGER",
    "fecha_archivo": "TEXT",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL",
}

CRITICIDADES = ("Baja", "Media", "Alta", "Crítica")
PRIORIDAD_CRITICIDAD = {"Crítica": 0, "Alta": 1, "Media": 2, "Baja": 3}

MAPPER_CATEGORIAS = {
    "manuales": "Manual fabricante",
    "procedimientos": "Procedimientos operacionales",
    "seguridad": "Seguridad",
    "capacitaciones": "ART",
    "troubleshooting": "Troubleshooting",
}


def _conexion(db_path=db.DB_PATH):
    return db.conectar_db(db_path)


def _quote(columna):
    return db.quote_identifier(columna)


def _ahora():
    return datetime.now().isoformat(timespec="seconds")


def _texto(valor):
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valor).strip()


def _normalizar_texto(valor):
    return normalize("NFKD", _texto(valor)).encode("ascii", "ignore").decode("ascii").lower().strip()


def _fecha_iso(valor):
    if valor in (None, ""):
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    fecha = pd.to_datetime(pd.Series([valor]), errors="coerce").iloc[0]
    if pd.isna(fecha):
        return _texto(valor)
    return pd.Timestamp(fecha).date().isoformat()


def _asegurar_estructura_documental(base_dir=DOCS_ROOT):
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    for carpeta in ["manuales", "procedimientos", "seguridad", "capacitaciones", "troubleshooting"]:
        (base / carpeta).mkdir(parents=True, exist_ok=True)
    return base


def asegurar_estructura_documental(base_dir=DOCS_ROOT):
    return _asegurar_estructura_documental(base_dir)


def asegurar_tabla(db_path=db.DB_PATH):
    with _conexion(db_path) as connection:
        columnas_sql = ", ".join(f"{_quote(col)} {tipo}" for col, tipo in DOCUMENTOS_COLUMNS.items())
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote(TABLA_DOCUMENTOS)} (
                {columnas_sql}
            )
            """
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_documentacion_categoria')} ON {_quote(TABLA_DOCUMENTOS)} ({_quote('categoria')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_documentacion_fabricante')} ON {_quote(TABLA_DOCUMENTOS)} ({_quote('fabricante')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_documentacion_equipo')} ON {_quote(TABLA_DOCUMENTOS)} ({_quote('equipo_asociado')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_documentacion_criticidad')} ON {_quote(TABLA_DOCUMENTOS)} ({_quote('criticidad')})"
        )
        connection.commit()


def asegurar_estructura_biblioteca_tecnica(base_dir=BIBLIOTECA_TECNICA_ROOT):
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    for carpeta in [
        "manuales_equipos",
        "procedimientos",
        "checklist",
        "seguridad",
        "aceros",
        "mantenimiento",
        "otros",
    ]:
        (base / carpeta).mkdir(parents=True, exist_ok=True)
    return base


def asegurar_tabla_biblioteca_documentos(db_path=db.DB_PATH):
    with _conexion(db_path) as connection:
        columnas_sql = ", ".join(
            f"{_quote(columna)} {tipo}" for columna, tipo in BIBLIOTECA_DOCUMENTOS_COLUMNS.items()
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote(TABLA_BIBLIOTECA_DOCUMENTOS)} (
                {columnas_sql}
            )
            """
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_biblioteca_equipo')} "
            f"ON {_quote(TABLA_BIBLIOTECA_DOCUMENTOS)} ({_quote('equipo_asociado')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_biblioteca_criticidad')} "
            f"ON {_quote(TABLA_BIBLIOTECA_DOCUMENTOS)} ({_quote('criticidad')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_biblioteca_tipo')} "
            f"ON {_quote(TABLA_BIBLIOTECA_DOCUMENTOS)} ({_quote('tipo_documento')})"
        )
        connection.commit()


def _subcarpeta_biblioteca(tipo_documento):
    return SUBCARPETAS_BIBLIOTECA.get(_texto(tipo_documento), "otros")


def _nombre_archivo_seguro(nombre):
    nombre = Path(_texto(nombre) or "documento.pdf").name
    stem = Path(nombre).stem or "documento"
    extension = Path(nombre).suffix.lower() or ".pdf"
    stem = normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "documento"
    return f"{stem}{extension}"


def _ruta_sin_sobrescribir(carpeta, nombre_archivo):
    carpeta = Path(carpeta)
    nombre = _nombre_archivo_seguro(nombre_archivo)
    destino = carpeta / nombre
    if not destino.exists():
        return destino
    stem = destino.stem
    suffix = destino.suffix
    contador = 1
    while True:
        candidato = carpeta / f"{stem}_{contador}{suffix}"
        if not candidato.exists():
            return candidato
        contador += 1


def validar_pdf_biblioteca(nombre_archivo, contenido=None):
    if Path(_texto(nombre_archivo)).suffix.lower() != ".pdf":
        return False
    if contenido is None:
        return True
    return bytes(contenido).lstrip().startswith(b"%PDF")


def registrar_documento_biblioteca(
    metadata,
    contenido_pdf,
    nombre_archivo,
    db_path=db.DB_PATH,
    biblioteca_root=BIBLIOTECA_TECNICA_ROOT,
):
    metadata = dict(metadata or {})
    titulo = _texto(metadata.get("titulo"))
    if not titulo:
        raise ValueError("El título del documento es obligatorio.")
    if not validar_pdf_biblioteca(nombre_archivo, contenido_pdf):
        raise ValueError("Solo se permiten archivos PDF válidos.")

    tipo_documento = _texto(metadata.get("tipo_documento")) or "Otro"
    equipo_asociado = _texto(metadata.get("equipo_asociado")) or "General"
    categoria = _texto(metadata.get("categoria"))
    criticidad = _normalizar_criticidad(metadata.get("criticidad"))
    observacion = _texto(metadata.get("observacion"))

    base = asegurar_estructura_biblioteca_tecnica(biblioteca_root)
    asegurar_tabla_biblioteca_documentos(db_path)
    carpeta = base / _subcarpeta_biblioteca(tipo_documento)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = _ruta_sin_sobrescribir(carpeta, nombre_archivo)
    destino.write_bytes(bytes(contenido_pdf))

    fecha_carga = _ahora()
    with _conexion(db_path) as connection:
        cursor = connection.execute(
            f"""
            INSERT INTO {_quote(TABLA_BIBLIOTECA_DOCUMENTOS)} (
                {_quote("titulo")},
                {_quote("tipo_documento")},
                {_quote("equipo_asociado")},
                {_quote("categoria")},
                {_quote("criticidad")},
                {_quote("observacion")},
                {_quote("nombre_archivo")},
                {_quote("ruta_archivo")},
                {_quote("extension")},
                {_quote("fecha_carga")},
                {_quote("activo")}
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                titulo,
                tipo_documento,
                equipo_asociado,
                categoria,
                criticidad,
                observacion,
                destino.name,
                str(destino),
                ".pdf",
                fecha_carga,
            ),
        )
        connection.commit()
        id_documento = int(cursor.lastrowid)

    return obtener_documento_biblioteca_por_id(id_documento, db_path=db_path)


def _normalizar_filtro(valor):
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set, pd.Index, pd.Series)):
        valores = list(valor)
    else:
        valores = [valor]
    return [_texto(item) for item in valores if _texto(item)]


def listar_documentos_biblioteca(
    db_path=db.DB_PATH,
    tipo_documento=None,
    equipo_asociado=None,
    criticidad=None,
    categoria=None,
    texto=None,
    solo_activos=True,
):
    asegurar_estructura_biblioteca_tecnica()
    asegurar_tabla_biblioteca_documentos(db_path)
    with _conexion(db_path) as connection:
        df = pd.read_sql_query(
            f"SELECT * FROM {_quote(TABLA_BIBLIOTECA_DOCUMENTOS)} ORDER BY {_quote('fecha_carga')} DESC, {_quote('id_documento')} DESC",
            connection,
        )
    if df.empty:
        return pd.DataFrame(columns=list(BIBLIOTECA_DOCUMENTOS_COLUMNS))

    if solo_activos and "activo" in df.columns:
        df = df[df["activo"].fillna(0).astype(int).eq(1)].copy()

    for valor, columna in [
        (tipo_documento, "tipo_documento"),
        (equipo_asociado, "equipo_asociado"),
        (criticidad, "criticidad"),
        (categoria, "categoria"),
    ]:
        filtros = _normalizar_filtro(valor)
        if filtros:
            df = df[df[columna].astype(str).isin(filtros)].copy()

    texto_busqueda = _normalizar_texto(texto)
    if texto_busqueda:
        mascara = pd.Series(False, index=df.index)
        for columna in ["titulo", "categoria", "observacion", "tipo_documento", "equipo_asociado"]:
            mascara = mascara | df[columna].astype(str).map(_normalizar_texto).str.contains(texto_busqueda, na=False)
        df = df[mascara].copy()

    return df.reset_index(drop=True)


def obtener_documento_biblioteca_por_id(id_documento, db_path=db.DB_PATH):
    asegurar_tabla_biblioteca_documentos(db_path)
    with _conexion(db_path) as connection:
        fila = connection.execute(
            f"SELECT * FROM {_quote(TABLA_BIBLIOTECA_DOCUMENTOS)} WHERE {_quote('id_documento')} = ?",
            (int(id_documento),),
        ).fetchone()
    return dict(fila) if fila else {}


def desactivar_documento_biblioteca(id_documento, db_path=db.DB_PATH):
    asegurar_tabla_biblioteca_documentos(db_path)
    with _conexion(db_path) as connection:
        connection.execute(
            f"UPDATE {_quote(TABLA_BIBLIOTECA_DOCUMENTOS)} SET {_quote('activo')} = 0 WHERE {_quote('id_documento')} = ?",
            (int(id_documento),),
        )
        connection.commit()
    return obtener_documento_biblioteca_por_id(id_documento, db_path=db_path)


def leer_bytes_documento_biblioteca(documento):
    if not documento:
        return b""
    ruta = Path(documento.get("ruta_archivo", ""))
    if not ruta.exists() or not ruta.is_file():
        return b""
    return ruta.read_bytes()


def resumen_biblioteca_tecnica(db_path=db.DB_PATH):
    df = listar_documentos_biblioteca(db_path=db_path)
    if df.empty:
        return {"total": 0, "pdf": 0, "criticos": 0, "categorias": 0}
    return {
        "total": int(len(df)),
        "pdf": int(df["extension"].astype(str).str.lower().eq(".pdf").sum()),
        "criticos": int(df["criticidad"].astype(str).isin(["Crítica", "CrÃ­tica"]).sum()),
        "categorias": int(df["categoria"].astype(str).replace("", pd.NA).dropna().nunique()),
    }


def _tipo_documento_por_extension(extension):
    ext = _texto(extension).lower()
    if ext == ".pdf":
        return "PDF"
    if ext in {".doc", ".docx"}:
        return "Documento Word"
    if ext in {".xls", ".xlsx"}:
        return "Planilla"
    if ext in {".ppt", ".pptx"}:
        return "Presentación"
    if ext in {".md", ".txt"}:
        return "Texto"
    return "Archivo"


def _inferir_categoria_por_ruta(ruta_relativa):
    primera_parte = Path(ruta_relativa).parts[0].lower() if Path(ruta_relativa).parts else ""
    return MAPPER_CATEGORIAS.get(primera_parte, "Manual fabricante")


def _inferir_version(nombre):
    texto = _texto(nombre)
    for token in texto.replace("_", " ").split():
        if token.lower().startswith("v") and any(caracter.isdigit() for caracter in token):
            return token
    return ""


def _inferir_palabras_clave(nombre, categoria, fabricante, equipo, tipo_documento):
    palabras = [nombre, categoria, fabricante, equipo, tipo_documento]
    tokens = []
    for valor in palabras:
        for parte in _texto(valor).replace("/", " ").replace("_", " ").split():
            parte_limpia = parte.strip(",.;:-")
            if parte_limpia and parte_limpia.lower() not in {"de", "del", "la", "el", "y"}:
                tokens.append(parte_limpia)
    return ", ".join(dict.fromkeys(tokens))


def _normalizar_criticidad(valor):
    texto = _texto(valor)
    if not texto:
        return "Media"
    mapa = {
        "baja": "Baja",
        "media": "Media",
        "alta": "Alta",
        "critica": "Crítica",
        "crítica": "Crítica",
    }
    return mapa.get(_normalizar_texto(texto), texto)


def _ruta_relativa_desde(base_dir, ruta_absoluta):
    base = Path(base_dir)
    ruta = Path(ruta_absoluta)
    return ruta.relative_to(base).as_posix()


def _ruta_absoluta_desde(base_dir, ruta_relativa):
    return Path(base_dir) / Path(ruta_relativa)


def _archivo_documental_valido(ruta):
    return Path(ruta).is_file() and Path(ruta).suffix.lower() in DOCS_EXTENSIONS


def _metadata_desde_archivo(ruta_absoluta, docs_root=DOCS_ROOT):
    ruta = Path(ruta_absoluta)
    categoria = _inferir_categoria_por_ruta(_ruta_relativa_desde(docs_root, ruta))
    nombre = ruta.stem.replace("_", " ").replace("-", " ").strip()
    extension = ruta.suffix.lower()
    tipo_documento = _tipo_documento_por_extension(extension)
    fecha_archivo = datetime.fromtimestamp(ruta.stat().st_mtime).date().isoformat()
    return {
        "nombre": nombre,
        "categoria": categoria,
        "fabricante": "",
        "equipo_asociado": "",
        "version": _inferir_version(ruta.stem),
        "fecha_documento": fecha_archivo,
        "tipo_documento": tipo_documento,
        "palabras_clave": _inferir_palabras_clave(nombre, categoria, "", "", tipo_documento),
        "criticidad": "Media",
        "autor_responsable": "",
        "descripcion": "",
        "ruta_relativa": _ruta_relativa_desde(docs_root, ruta),
        "extension": extension,
        "tamano_bytes": int(ruta.stat().st_size),
        "fecha_archivo": fecha_archivo,
    }


def registrar_documento(metadata, db_path=db.DB_PATH, docs_root=DOCS_ROOT):
    _asegurar_estructura_documental(docs_root)
    asegurar_tabla(db_path)

    metadata = dict(metadata or {})
    ruta_relativa = _texto(metadata.get("ruta_relativa") or metadata.get("ruta_archivo"))
    if not ruta_relativa:
        raise ValueError("La ruta relativa del documento es obligatoria.")

    ruta_absoluta = _ruta_absoluta_desde(docs_root, ruta_relativa)
    if not ruta_absoluta.exists():
        raise FileNotFoundError(f"No existe el documento: {ruta_absoluta}")

    nombre = _texto(metadata.get("nombre")) or ruta_absoluta.stem.replace("_", " ").replace("-", " ").strip()
    categoria = _texto(metadata.get("categoria")) or _inferir_categoria_por_ruta(ruta_relativa)
    fabricante = _texto(metadata.get("fabricante"))
    equipo_asociado = _texto(metadata.get("equipo_asociado"))
    version = _texto(metadata.get("version")) or _inferir_version(ruta_absoluta.stem)
    fecha_documento = _fecha_iso(metadata.get("fecha_documento")) or datetime.fromtimestamp(ruta_absoluta.stat().st_mtime).date().isoformat()
    extension = ruta_absoluta.suffix.lower()
    tipo_documento = _texto(metadata.get("tipo_documento")) or _tipo_documento_por_extension(extension)
    palabras_clave = _texto(metadata.get("palabras_clave")) or _inferir_palabras_clave(nombre, categoria, fabricante, equipo_asociado, tipo_documento)
    criticidad = _normalizar_criticidad(metadata.get("criticidad"))
    autor_responsable = _texto(metadata.get("autor_responsable"))
    descripcion = _texto(metadata.get("descripcion"))
    tamano_bytes = int(ruta_absoluta.stat().st_size)
    fecha_archivo = datetime.fromtimestamp(ruta_absoluta.stat().st_mtime).date().isoformat()
    now = _ahora()

    with _conexion(db_path) as connection:
        connection.execute(
            f"""
            INSERT INTO {_quote(TABLA_DOCUMENTOS)} (
                {_quote("nombre")},
                {_quote("categoria")},
                {_quote("fabricante")},
                {_quote("equipo_asociado")},
                {_quote("version")},
                {_quote("fecha_documento")},
                {_quote("tipo_documento")},
                {_quote("palabras_clave")},
                {_quote("criticidad")},
                {_quote("autor_responsable")},
                {_quote("descripcion")},
                {_quote("ruta_relativa")},
                {_quote("extension")},
                {_quote("tamano_bytes")},
                {_quote("fecha_archivo")},
                {_quote("created_at")},
                {_quote("updated_at")}
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT({_quote("ruta_relativa")}) DO UPDATE SET
                {_quote("nombre")} = excluded.{_quote("nombre")},
                {_quote("categoria")} = excluded.{_quote("categoria")},
                {_quote("fabricante")} = excluded.{_quote("fabricante")},
                {_quote("equipo_asociado")} = excluded.{_quote("equipo_asociado")},
                {_quote("version")} = excluded.{_quote("version")},
                {_quote("fecha_documento")} = excluded.{_quote("fecha_documento")},
                {_quote("tipo_documento")} = excluded.{_quote("tipo_documento")},
                {_quote("palabras_clave")} = excluded.{_quote("palabras_clave")},
                {_quote("criticidad")} = excluded.{_quote("criticidad")},
                {_quote("autor_responsable")} = excluded.{_quote("autor_responsable")},
                {_quote("descripcion")} = excluded.{_quote("descripcion")},
                {_quote("extension")} = excluded.{_quote("extension")},
                {_quote("tamano_bytes")} = excluded.{_quote("tamano_bytes")},
                {_quote("fecha_archivo")} = excluded.{_quote("fecha_archivo")},
                {_quote("updated_at")} = excluded.{_quote("updated_at")}
            """,
            (
                nombre,
                categoria,
                fabricante,
                equipo_asociado,
                version,
                fecha_documento,
                tipo_documento,
                palabras_clave,
                criticidad,
                autor_responsable,
                descripcion,
                ruta_relativa,
                extension,
                tamano_bytes,
                fecha_archivo,
                now,
                now,
            ),
        )
        connection.commit()

    return obtener_documento_por_ruta(ruta_relativa, db_path=db_path, docs_root=docs_root)


def sincronizar_biblioteca_documental(db_path=db.DB_PATH, docs_root=DOCS_ROOT):
    base = _asegurar_estructura_documental(docs_root)
    asegurar_tabla(db_path)

    encontrados = []
    for ruta in base.rglob("*"):
        if _archivo_documental_valido(ruta):
            encontrados.append(ruta)

    existentes = set()
    with _conexion(db_path) as connection:
        filas = connection.execute(f"SELECT {_quote('ruta_relativa')} FROM {_quote(TABLA_DOCUMENTOS)}").fetchall()
        existentes = {str(fila["ruta_relativa"]) for fila in filas}

    for ruta in encontrados:
        relativa = _ruta_relativa_desde(base, ruta)
        if relativa not in existentes:
            registrar_documento({"ruta_relativa": relativa}, db_path=db_path, docs_root=docs_root)

    return len(encontrados)


def obtener_documento_por_ruta(ruta_relativa, db_path=db.DB_PATH, docs_root=DOCS_ROOT):
    ruta_relativa = _texto(ruta_relativa)
    if not ruta_relativa:
        return {}

    asegurar_tabla(db_path)
    with _conexion(db_path) as connection:
        fila = connection.execute(
            f"SELECT * FROM {_quote(TABLA_DOCUMENTOS)} WHERE {_quote('ruta_relativa')} = ?",
            (ruta_relativa,),
        ).fetchone()

    if not fila:
        return {}

    datos = dict(fila)
    ruta_absoluta = _ruta_absoluta_desde(docs_root, ruta_relativa)
    datos["ruta_absoluta"] = str(ruta_absoluta)
    datos["archivo_existe"] = ruta_absoluta.exists()
    datos["mimetype"] = mimetypes.guess_type(str(ruta_absoluta))[0] or "application/octet-stream"
    return datos


def obtener_documento_por_id(documento_id, db_path=db.DB_PATH, docs_root=DOCS_ROOT):
    asegurar_tabla(db_path)
    with _conexion(db_path) as connection:
        fila = connection.execute(
            f"SELECT * FROM {_quote(TABLA_DOCUMENTOS)} WHERE {_quote('id')} = ?",
            (int(documento_id),),
        ).fetchone()
    if not fila:
        return {}
    return obtener_documento_por_ruta(fila["ruta_relativa"], db_path=db_path, docs_root=docs_root)


def listar_documentos(
    db_path=db.DB_PATH,
    docs_root=DOCS_ROOT,
    categoria=None,
    fabricante=None,
    equipo=None,
    criticidad=None,
    buscar=None,
    palabras_clave=None,
    solo_existentes=True,
    limit=None,
):
    sincronizar_biblioteca_documental(db_path=db_path, docs_root=docs_root)
    asegurar_tabla(db_path)

    with _conexion(db_path) as connection:
        df = pd.read_sql_query(f"SELECT * FROM {_quote(TABLA_DOCUMENTOS)} ORDER BY {_quote('updated_at')} DESC, {_quote('id')} DESC", connection)

    if df.empty:
        columnas = list(DOCUMENTOS_COLUMNS.keys()) + ["ruta_absoluta", "archivo_existe", "mimetype"]
        return pd.DataFrame(columns=columnas)

    df = df.copy()
    df["ruta_absoluta"] = df["ruta_relativa"].apply(lambda valor: str(_ruta_absoluta_desde(docs_root, valor)))
    df["archivo_existe"] = df["ruta_absoluta"].apply(lambda valor: Path(valor).exists())
    df["mimetype"] = df["ruta_absoluta"].apply(lambda valor: mimetypes.guess_type(str(valor))[0] or "application/octet-stream")

    if solo_existentes:
        df = df[df["archivo_existe"]].copy()

    filtros = [
        (categoria, "categoria"),
        (fabricante, "fabricante"),
        (equipo, "equipo_asociado"),
        (criticidad, "criticidad"),
    ]
    for valor, columna in filtros:
        valores = _normalizar_lista(valor)
        if valores:
            serie = df[columna].astype(str)
            df = df[serie.isin(valores)].copy()

    if palabras_clave:
        df = _filtrar_por_texto(df, palabras_clave, ["palabras_clave", "descripcion", "nombre", "categoria", "fabricante", "equipo_asociado", "tipo_documento", "autor_responsable"])
    if buscar:
        df = _filtrar_por_texto(df, buscar, ["palabras_clave", "descripcion", "nombre", "categoria", "fabricante", "equipo_asociado", "tipo_documento", "autor_responsable"])

    if limit is not None:
        df = df.head(int(limit)).copy()

    return df.reset_index(drop=True)


def _normalizar_lista(valor):
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set, pd.Index, pd.Series)):
        valores = list(valor)
    else:
        valores = [valor]
    resultado = []
    for item in valores:
        texto = _texto(item)
        if texto:
            resultado.append(texto)
    return resultado


def _filtrar_por_texto(df, texto, columnas):
    texto_normalizado = _normalizar_texto(texto)
    if not texto_normalizado:
        return df
    mascara = pd.Series(False, index=df.index)
    for columna in columnas:
        if columna not in df.columns:
            continue
        mascara = mascara | df[columna].astype(str).map(_normalizar_texto).str.contains(texto_normalizado, na=False)
    return df[mascara].copy()


def obtener_categorias_documentales(db_path=db.DB_PATH, docs_root=DOCS_ROOT):
    df = listar_documentos(db_path=db_path, docs_root=docs_root, solo_existentes=False)
    valores = sorted(set(CATEGORIAS_INICIALES) | set(df.get("categoria", pd.Series(dtype=str)).dropna().astype(str)))
    return [valor for valor in valores if valor]


def obtener_fabricantes_documentales(db_path=db.DB_PATH, docs_root=DOCS_ROOT):
    df = listar_documentos(db_path=db_path, docs_root=docs_root, solo_existentes=False)
    valores = sorted(set(df.get("fabricante", pd.Series(dtype=str)).dropna().astype(str)))
    return [valor for valor in valores if valor]


def obtener_equipos_documentales(db_path=db.DB_PATH, docs_root=DOCS_ROOT):
    df = listar_documentos(db_path=db_path, docs_root=docs_root, solo_existentes=False)
    valores = sorted(set(df.get("equipo_asociado", pd.Series(dtype=str)).dropna().astype(str)))
    return [valor for valor in valores if valor]


def obtener_criticidades_documentales(db_path=db.DB_PATH, docs_root=DOCS_ROOT):
    df = listar_documentos(db_path=db_path, docs_root=docs_root, solo_existentes=False)
    valores = sorted(set(CRITICIDADES) | set(df.get("criticidad", pd.Series(dtype=str)).dropna().astype(str)), key=lambda valor: PRIORIDAD_CRITICIDAD.get(valor, 99))
    return [valor for valor in valores if valor]


def leer_bytes_documento(documento, docs_root=DOCS_ROOT):
    if isinstance(documento, (str, Path)):
        ruta = Path(documento)
    elif isinstance(documento, dict):
        ruta = Path(documento.get("ruta_absoluta") or _ruta_absoluta_desde(docs_root, documento.get("ruta_relativa", "")))
    else:
        return b""

    if not ruta.exists() or not ruta.is_file():
        return b""
    return ruta.read_bytes()


def ruta_documento_absoluta(documento, docs_root=DOCS_ROOT):
    if isinstance(documento, dict):
        ruta_relativa = documento.get("ruta_relativa", "")
    else:
        ruta_relativa = str(documento)
    return _ruta_absoluta_desde(docs_root, ruta_relativa)


def resumen_biblioteca_documental(db_path=db.DB_PATH, docs_root=DOCS_ROOT):
    df = listar_documentos(db_path=db_path, docs_root=docs_root)
    if df.empty:
        return {
            "total": 0,
            "pdf": 0,
            "criticos": 0,
            "categorias": 0,
            "fabricantes": 0,
            "equipos": 0,
            "detalle": df,
        }

    return {
        "total": int(len(df)),
        "pdf": int(df["extension"].astype(str).str.lower().eq(".pdf").sum()) if "extension" in df.columns else 0,
        "criticos": int(df["criticidad"].astype(str).eq("Crítica").sum()) if "criticidad" in df.columns else 0,
        "categorias": int(df["categoria"].astype(str).nunique()) if "categoria" in df.columns else 0,
        "fabricantes": int(df["fabricante"].astype(str).replace("", pd.NA).dropna().nunique()) if "fabricante" in df.columns else 0,
        "equipos": int(df["equipo_asociado"].astype(str).replace("", pd.NA).dropna().nunique()) if "equipo_asociado" in df.columns else 0,
        "detalle": df,
    }
