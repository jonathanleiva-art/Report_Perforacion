from pathlib import Path
from contextlib import closing
import re
import sqlite3
from unicodedata import normalize

import pandas as pd


TABLA_OPERADORES = "operadores"

OPERADORES_CONOCIDOS = (
    ("009464", "Jhan Calderon"),
    ("204167", "Matías Toro"),
    ("203529", "Valeria Millan"),
    ("009608", "Nicolas Torres"),
    ("009939", "Mauricio Mora"),
    ("002036", "Carlos Rondon"),
    ("007494", "Jhon Tapia"),
    ("002268", "Diego Huerta"),
    ("009234", "Diego Aracena"),
    ("203666", "Martina Díaz"),
    ("203528", "Tereza Inostroza"),
    ("007540", "Javier Herrera"),
    ("008086", "Jonathan Leiva"),
)


def normalizar_codigo_operador(codigo):
    if codigo is None:
        return ""

    try:
        if pd.isna(codigo):
            return ""
    except (TypeError, ValueError):
        pass

    if isinstance(codigo, float) and codigo.is_integer():
        texto = str(int(codigo))
    else:
        texto = str(codigo)

    texto = texto.strip().upper()
    if re.fullmatch(r"\d+\.0+", texto):
        texto = texto.split(".", 1)[0]
    texto = re.sub(r"^\s*M\s*-\s*", "", texto)
    if re.fullmatch(r"\d+\.0+", texto):
        texto = texto.split(".", 1)[0]
    texto = texto.replace(".", "").replace("-", "")
    digitos = re.sub(r"\D+", "", texto)
    if not digitos:
        return ""
    if len(digitos) < 6:
        return digitos.zfill(6)
    return digitos


def asegurar_tabla_operadores(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS operadores (
            codigo_operador TEXT PRIMARY KEY,
            nombre_operador TEXT NOT NULL,
            activo INTEGER DEFAULT 1,
            observacion TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        )
        """
    )
    connection.commit()


def upsert_operadores_conocidos(connection):
    asegurar_tabla_operadores(connection)
    for codigo, nombre in OPERADORES_CONOCIDOS:
        connection.execute(
            """
            INSERT INTO operadores (codigo_operador, nombre_operador, activo, observacion, updated_at)
            VALUES (?, ?, 1, 'operador conocido inicial', CURRENT_TIMESTAMP)
            ON CONFLICT(codigo_operador) DO UPDATE SET
                nombre_operador = excluded.nombre_operador,
                activo = 1,
                observacion = COALESCE(operadores.observacion, excluded.observacion),
                updated_at = CURRENT_TIMESTAMP
            """,
            (codigo, nombre),
        )
    connection.commit()


def inicializar_operadores(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        upsert_operadores_conocidos(connection)


def cargar_mapa_operadores(db_path=None, connection=None):
    cerrar = False
    if connection is None:
        if db_path is None:
            from config import DATABASE_PATH

            db_path = DATABASE_PATH
        if not Path(db_path).exists():
            return {}
        connection = sqlite3.connect(Path(db_path))
        cerrar = True

    try:
        asegurar_tabla_operadores(connection)
        filas = connection.execute(
            """
            SELECT codigo_operador, nombre_operador
            FROM operadores
            WHERE activo = 1
            """
        ).fetchall()
        return {str(codigo): str(nombre) for codigo, nombre in filas}
    except sqlite3.Error:
        return {}
    finally:
        if cerrar:
            connection.close()


def obtener_nombre_operador(codigo_operador, db_path=None):
    codigo = normalizar_codigo_operador(codigo_operador)
    if not codigo:
        return ""

    mapa = cargar_mapa_operadores(db_path=db_path)
    return mapa.get(codigo, codigo)


def actualizar_operador(codigo, nombre, db_path=None):
    codigo_normalizado = normalizar_codigo_operador(codigo)
    nombre_limpio = str(nombre or "").strip()
    if not codigo_normalizado:
        raise ValueError("Código de operador vacío o inválido.")
    if not nombre_limpio:
        raise ValueError("Nombre de operador vacío.")

    if db_path is None:
        from config import DATABASE_PATH

        db_path = DATABASE_PATH

    with closing(sqlite3.connect(Path(db_path))) as connection:
        asegurar_tabla_operadores(connection)
        connection.execute(
            """
            INSERT INTO operadores (codigo_operador, nombre_operador, activo, observacion, updated_at)
            VALUES (?, ?, 1, 'actualizado desde administración de operadores', CURRENT_TIMESTAMP)
            ON CONFLICT(codigo_operador) DO UPDATE SET
                nombre_operador = excluded.nombre_operador,
                activo = 1,
                observacion = excluded.observacion,
                updated_at = CURRENT_TIMESTAMP
            """,
            (codigo_normalizado, nombre_limpio),
        )
        connection.commit()

    try:
        from services.ciclos_service import sincronizar_operadores_ciclos

        sincronizacion = sincronizar_operadores_ciclos(db_path=db_path)
    except Exception as exc:
        sincronizacion = {"error_sincronizacion_ciclos": str(exc)}

    return {
        "codigo_operador": codigo_normalizado,
        "nombre_operador": nombre_limpio,
        "sincronizacion": sincronizacion,
    }


def etiqueta_operador(valor, db_path=None):
    texto = str(valor or "").strip()
    nombre = obtener_nombre_operador(texto, db_path=db_path)
    if nombre and texto and nombre != texto:
        return f"{nombre} ({texto})"
    return nombre or texto


def _resolver_columna(df, *candidatos):
    def clave(valor):
        texto = str(valor or "").replace("?", "o")
        texto = normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
        return re.sub(r"[^a-z0-9]+", "", texto)

    columnas = {clave(columna): columna for columna in df.columns}
    for candidato in candidatos:
        columna = columnas.get(clave(candidato))
        if columna:
            return columna
    return None


def agregar_columnas_operador_visual(df, db_path=None):
    if df is None or df.empty:
        return df

    resultado = df.copy()
    columna_codigo = _resolver_columna(
        resultado,
        "Código operador",
        "Codigo operador",
        "C?digo operador",
        "CÃ³digo operador",
        "CÃƒÂ³digo operador",
    )
    columna_operador = _resolver_columna(resultado, "Operador")

    if columna_codigo and columna_operador:
        fuente_codigo = resultado[columna_codigo].map(normalizar_codigo_operador)
        fuente_operador = resultado[columna_operador].map(normalizar_codigo_operador)
        fuente_codigo = fuente_codigo.where(fuente_codigo.astype(str).str.strip().ne(""), fuente_operador)
    elif columna_codigo:
        fuente_codigo = resultado[columna_codigo].map(normalizar_codigo_operador)
    elif columna_operador:
        fuente_codigo = resultado[columna_operador].map(normalizar_codigo_operador)
    else:
        resultado["operador_codigo"] = ""
        resultado["operador_nombre"] = ""
        return resultado

    resultado["operador_codigo"] = fuente_codigo
    mapa = cargar_mapa_operadores(db_path=db_path)
    resultado["operador_nombre"] = resultado["operador_codigo"].map(lambda codigo: mapa.get(codigo, codigo) if codigo else "")

    if columna_operador:
        operador_texto = resultado[columna_operador].fillna("").astype(str).str.strip()
        sin_nombre = operador_texto.eq("") | operador_texto.map(normalizar_codigo_operador).eq(resultado["operador_codigo"])
        resultado.loc[sin_nombre & resultado["operador_nombre"].ne(""), columna_operador] = resultado.loc[
            sin_nombre & resultado["operador_nombre"].ne(""),
            "operador_nombre",
        ]
        es_codigo_sin_mapear = resultado["operador_nombre"].eq(resultado["operador_codigo"])
        es_nombre_historico = (
            (resultado["operador_nombre"].eq("") | es_codigo_sin_mapear)
            & operador_texto.ne("")
            & operador_texto.map(normalizar_codigo_operador).eq("")
        )
        resultado.loc[es_nombre_historico, "operador_nombre"] = operador_texto[es_nombre_historico]

    return resultado

