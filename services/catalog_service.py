from datetime import datetime
import logging
from pathlib import Path
import re
import sqlite3
from unicodedata import normalize

import pandas as pd

from config import DATABASE_PATH
from utils import CODIGOS_OPERADOR, EQUIPOS, OPERADORES


TABLA_EQUIPOS = "equipos"
TABLA_OPERADORES = "operadores"
logger = logging.getLogger(__name__)

FLOTA_EQUIPOS = ["9245", "9259", "9272", "9274", "9277", "9339"]


EQUIPOS_COLUMNAS = [
    "id",
    "codigo_equipo",
    "nombre_equipo",
    "modelo",
    "tipo",
    "estado",
    "activo",
    "created_at",
    "updated_at",
]

OPERADORES_COLUMNAS = [
    "id",
    "codigo_operador",
    "nombre_operador",
    "empresa",
    "cargo",
    "activo",
    "created_at",
    "updated_at",
]


CAUSAS_EQUIVALENTES = {
    "Cambio Turno": [
        "Cambio de turno",
        "CAMBIO TURNO",
        "cambio turno",
    ],
    "Standby por falta de tajo/patio": [
        "Standby Patio",
        "Stand By Patio",
        "Standby por falta de tajo",
        "Stand By por falta de tajo",
        "standby falta de tajo",
        "Falta de Tajo",
        "Falta de Patio",
    ],
}

CATEGORIAS_DETENCION = {
    "Operacional": [
        "Cambio Turno",
        "Standby por falta de tajo/patio",
        "Espera Topografía",
        "Espera Instrucción",
        "Reubicación Operacional",
        "Marcación",
    ],
    "Mantención": [
        "Mantención Programada",
        "MP",
        "Mantención Preventiva",
    ],
    "Mecánica": [
        "Avería Equipo",
        "Avería Mecánica",
        "Falla Hidráulica",
        "Falla Eléctrica",
        "Falla Compresor",
        "Falla Motor",
    ],
    "Abastecimiento": [
        "Carga Combustible",
        "Relleno Agua",
        "Cambio Aceros",
    ],
    "Seguridad": [
        "Bloqueo",
        "Permiso Trabajo",
        "Inspección Seguridad",
    ],
    "Externa": [
        "Tronadura",
        "Clima",
        "Lluvia",
        "Viento",
        "Polvo",
        "Caminos",
    ],
    "Sin Clasificar": [],
}

RECOMENDACIONES_OPERACIONALES = {
    "Mecánica": [
        "Revisar disponibilidad física de equipos.",
        "Analizar fallas repetitivas.",
        "Verificar tiempos de respuesta de mantención.",
        "Priorizar equipos con mayor impacto.",
    ],
    "Operacional": [
        "Revisar coordinación mina-perforación.",
        "Revisar disponibilidad de frente.",
        "Revisar tiempos de cambio de turno.",
        "Revisar esperas operacionales.",
    ],
    "Mantención": [
        "Evaluar cumplimiento de MP.",
        "Revisar planificación semanal.",
        "Revisar backlog de mantención.",
    ],
    "Abastecimiento": [
        "Revisar logística de combustible.",
        "Revisar abastecimiento de agua.",
        "Revisar frecuencia de cambios de aceros.",
    ],
    "Seguridad": [
        "Revisar permisos.",
        "Revisar bloqueos.",
        "Revisar restricciones operacionales.",
    ],
    "Externa": [
        "Revisar programación de tronaduras.",
        "Revisar gestión climática.",
        "Revisar coordinación con otras áreas.",
    ],
    "Sin Clasificar": [
        "Revisar clasificación de causas.",
        "Actualizar catálogo de categorías.",
    ],
}

_CAUSAS_EQUIVALENTES_NORMALIZADAS = None
_CATEGORIAS_DETENCION_NORMALIZADAS = None
_VARIANTES_CAUSA_LOGUEADAS = set()
_CAUSAS_SIN_CATEGORIA_LOGUEADAS = set()


def _connect(db_path=DATABASE_PATH):
    import db

    return db.conectar_db(db_path)


def _quote(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _texto(valor):
    return str(valor or "").strip()


def _clave_causa_detencion(valor):
    texto = normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s/]", " ", texto)
    texto = re.sub(r"\bde\b", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    texto = texto.replace("stand by", "standby")
    return texto


def _titulo_causa_detencion(valor):
    texto = normalize("NFKC", str(valor or "")).strip()
    texto = re.sub(r"[;|]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    if not texto:
        return ""
    return texto.lower().title()


def _mapa_causas_equivalentes():
    global _CAUSAS_EQUIVALENTES_NORMALIZADAS
    if _CAUSAS_EQUIVALENTES_NORMALIZADAS is not None:
        return _CAUSAS_EQUIVALENTES_NORMALIZADAS

    mapa = {}
    for causa_canonica, variantes in CAUSAS_EQUIVALENTES.items():
        canonica = re.sub(r"\s+", " ", str(causa_canonica or "")).strip()
        mapa[_clave_causa_detencion(canonica)] = canonica
        for variante in variantes:
            mapa[_clave_causa_detencion(variante)] = canonica
    _CAUSAS_EQUIVALENTES_NORMALIZADAS = mapa
    return mapa


def normalizar_causa_detencion(valor):
    texto = _titulo_causa_detencion(valor)
    if not texto:
        return ""

    clave = _clave_causa_detencion(texto)
    causa_catalogada = _mapa_causas_equivalentes().get(clave)
    if causa_catalogada:
        return causa_catalogada

    if clave and clave not in _mapa_categorias_detencion() and clave not in _VARIANTES_CAUSA_LOGUEADAS:
        logger.warning("Causa de detencion no catalogada detectada: %s", texto)
        _VARIANTES_CAUSA_LOGUEADAS.add(clave)
    return texto


def _mapa_categorias_detencion():
    global _CATEGORIAS_DETENCION_NORMALIZADAS
    if _CATEGORIAS_DETENCION_NORMALIZADAS is not None:
        return _CATEGORIAS_DETENCION_NORMALIZADAS

    mapa = {}
    for categoria, causas in CATEGORIAS_DETENCION.items():
        if categoria == "Sin Clasificar":
            continue
        for causa in causas:
            causa_normalizada = _mapa_causas_equivalentes().get(
                _clave_causa_detencion(causa),
                re.sub(r"\s+", " ", str(causa or "")).strip(),
            )
            clave = _clave_causa_detencion(causa_normalizada)
            if clave:
                mapa[clave] = categoria
    _CATEGORIAS_DETENCION_NORMALIZADAS = mapa
    return mapa


def clasificar_categoria_detencion(causa):
    causa_normalizada = normalizar_causa_detencion(causa)
    if not causa_normalizada:
        return "Sin Clasificar"

    clave = _clave_causa_detencion(causa_normalizada)
    categoria = _mapa_categorias_detencion().get(clave)
    if categoria:
        return categoria

    if clave and clave not in _CAUSAS_SIN_CATEGORIA_LOGUEADAS:
        logger.warning("Causa de detencion sin categoria operacional: %s", causa_normalizada)
        _CAUSAS_SIN_CATEGORIA_LOGUEADAS.add(clave)
    return "Sin Clasificar"


def generar_recomendacion_operacional(categoria, horas, porcentaje):
    categoria = str(categoria or "Sin Clasificar").strip() or "Sin Clasificar"
    try:
        horas = float(horas)
    except (TypeError, ValueError):
        horas = 0.0
    try:
        porcentaje = float(porcentaje)
    except (TypeError, ValueError):
        porcentaje = 0.0

    if porcentaje < 15:
        semaforo = "Verde"
        estado = "ok"
        prioridad = "Baja"
    elif porcentaje <= 30:
        semaforo = "Amarillo"
        estado = "warning"
        prioridad = "Media"
    elif porcentaje <= 45:
        semaforo = "Rojo"
        estado = "alert"
        prioridad = "Alta"
    else:
        semaforo = "Rojo"
        estado = "alert"
        prioridad = "Crítica"

    acciones = RECOMENDACIONES_OPERACIONALES.get(
        categoria,
        RECOMENDACIONES_OPERACIONALES["Sin Clasificar"],
    )
    recomendacion = " ".join(acciones)
    detalle = "\n".join(f"- {accion}" for accion in acciones)
    mensaje = (
        f"Categoría dominante: {categoria}\n"
        f"Horas perdidas: {horas:.1f} h\n"
        f"Impacto: {porcentaje:.1f}%\n"
        f"Semáforo: {semaforo}\n"
        f"Prioridad: {prioridad}\n"
        f"Recomendación generada:\n{detalle}"
    )
    return {
        "categoria": categoria,
        "horas": horas,
        "porcentaje": porcentaje,
        "semaforo": semaforo,
        "prioridad": prioridad,
        "estado": estado,
        "recomendacion": recomendacion,
        "acciones": acciones,
        "mensaje": mensaje,
    }


def _codigo_equipo(valor):
    return _texto(valor)


def _codigo_operador(valor):
    from operators import normalizar_codigo_operador

    return normalizar_codigo_operador(valor)


def _columnas(connection, tabla):
    try:
        filas = connection.execute(f"PRAGMA table_info({_quote(tabla)})").fetchall()
    except sqlite3.DatabaseError:
        return []
    return [fila["name"] if isinstance(fila, sqlite3.Row) else fila[1] for fila in filas]


def _agregar_columna_si_falta(connection, tabla, existentes, columna, definicion):
    if columna not in existentes:
        connection.execute(f"ALTER TABLE {_quote(tabla)} ADD COLUMN {_quote(columna)} {definicion}")
        existentes.add(columna)


def asegurar_tablas_catalogo(db_path=DATABASE_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote(TABLA_EQUIPOS)} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_equipo TEXT NOT NULL UNIQUE,
                nombre_equipo TEXT NOT NULL,
                modelo TEXT,
                tipo TEXT,
                estado TEXT DEFAULT 'operativo',
                activo INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote(TABLA_OPERADORES)} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_operador TEXT NOT NULL UNIQUE,
                nombre_operador TEXT NOT NULL,
                empresa TEXT,
                cargo TEXT,
                activo INTEGER DEFAULT 1,
                observacion TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        existentes_equipos = set(_columnas(connection, TABLA_EQUIPOS))
        _agregar_columna_si_falta(connection, TABLA_EQUIPOS, existentes_equipos, "nombre_equipo", "TEXT")
        _agregar_columna_si_falta(connection, TABLA_EQUIPOS, existentes_equipos, "modelo", "TEXT")
        _agregar_columna_si_falta(connection, TABLA_EQUIPOS, existentes_equipos, "tipo", "TEXT")
        _agregar_columna_si_falta(connection, TABLA_EQUIPOS, existentes_equipos, "estado", "TEXT DEFAULT 'operativo'")
        _agregar_columna_si_falta(connection, TABLA_EQUIPOS, existentes_equipos, "activo", "INTEGER DEFAULT 1")
        _agregar_columna_si_falta(connection, TABLA_EQUIPOS, existentes_equipos, "created_at", "TEXT")
        _agregar_columna_si_falta(connection, TABLA_EQUIPOS, existentes_equipos, "updated_at", "TEXT")

        existentes_operadores = set(_columnas(connection, TABLA_OPERADORES))
        _agregar_columna_si_falta(connection, TABLA_OPERADORES, existentes_operadores, "empresa", "TEXT")
        _agregar_columna_si_falta(connection, TABLA_OPERADORES, existentes_operadores, "cargo", "TEXT")
        _agregar_columna_si_falta(connection, TABLA_OPERADORES, existentes_operadores, "activo", "INTEGER DEFAULT 1")
        _agregar_columna_si_falta(connection, TABLA_OPERADORES, existentes_operadores, "created_at", "TEXT")
        _agregar_columna_si_falta(connection, TABLA_OPERADORES, existentes_operadores, "updated_at", "TEXT")
        connection.commit()


def _fallback_equipos():
    filas = []
    for modelo, numeros in EQUIPOS.items():
        for numero in numeros:
            codigo = _codigo_equipo(numero)
            filas.append(
                {
                    "id": None,
                    "codigo_equipo": codigo,
                    "nombre_equipo": f"{modelo} {codigo}".strip(),
                    "modelo": modelo,
                    "tipo": "",
                    "estado": "operativo",
                    "activo": 1,
                    "created_at": "",
                    "updated_at": "",
                }
            )
    return pd.DataFrame(filas, columns=EQUIPOS_COLUMNAS)


def _fallback_operadores():
    filas = []
    for nombre in OPERADORES:
        codigo = _codigo_operador(CODIGOS_OPERADOR.get(nombre, nombre))
        filas.append(
            {
                "id": None,
                "codigo_operador": codigo,
                "nombre_operador": nombre,
                "empresa": "",
                "cargo": "",
                "activo": 1,
                "created_at": "",
                "updated_at": "",
            }
        )
    return pd.DataFrame(filas, columns=OPERADORES_COLUMNAS)


def listar_equipos_activos(db_path=DATABASE_PATH):
    asegurar_tablas_catalogo(db_path=db_path)
    with _connect(db_path) as connection:
        total = int(connection.execute(f"SELECT COUNT(*) FROM {_quote(TABLA_EQUIPOS)}").fetchone()[0])
        df = pd.read_sql_query(
            f"""
            SELECT {", ".join(_quote(columna) for columna in EQUIPOS_COLUMNAS if columna in _columnas(connection, TABLA_EQUIPOS))}
            FROM {_quote(TABLA_EQUIPOS)}
            WHERE COALESCE(activo, 1) = 1
            ORDER BY modelo, codigo_equipo
            """,
            connection,
        )
    if df.empty and total == 0:
        return _fallback_equipos()
    return df.reindex(columns=EQUIPOS_COLUMNAS)


def listar_operadores_activos(db_path=DATABASE_PATH):
    asegurar_tablas_catalogo(db_path=db_path)
    with _connect(db_path) as connection:
        total = int(connection.execute(f"SELECT COUNT(*) FROM {_quote(TABLA_OPERADORES)}").fetchone()[0])
        columnas = [columna for columna in OPERADORES_COLUMNAS if columna in _columnas(connection, TABLA_OPERADORES)]
        df = pd.read_sql_query(
            f"""
            SELECT {", ".join(_quote(columna) for columna in columnas)}
            FROM {_quote(TABLA_OPERADORES)}
            WHERE COALESCE(activo, 1) = 1
            ORDER BY nombre_operador
            """,
            connection,
        )
    if df.empty and total == 0:
        return _fallback_operadores()
    return df.reindex(columns=OPERADORES_COLUMNAS)


def equipos_por_modelo_activos(db_path=DATABASE_PATH):
    equipos = listar_equipos_activos(db_path=db_path)
    resultado = {}
    if equipos.empty:
        return resultado
    for _, fila in equipos.iterrows():
        modelo = _texto(fila.get("modelo"))
        codigo = _codigo_equipo(fila.get("codigo_equipo"))
        if not modelo or not codigo:
            continue
        resultado.setdefault(modelo, [])
        if codigo not in resultado[modelo]:
            resultado[modelo].append(codigo)
    return resultado


def equipos_esperados_activos(db_path=DATABASE_PATH):
    equipos = listar_equipos_activos(db_path=db_path)
    if equipos.empty:
        return []
    filas = []
    for _, fila in equipos.iterrows():
        modelo = _texto(fila.get("modelo"))
        codigo = _codigo_equipo(fila.get("codigo_equipo"))
        if modelo and codigo:
            filas.append((modelo, codigo))
    return filas


def nombres_operadores_activos(db_path=DATABASE_PATH):
    operadores = listar_operadores_activos(db_path=db_path)
    if operadores.empty:
        return []
    nombres = []
    for nombre in operadores["nombre_operador"].dropna().astype(str):
        nombre = nombre.strip()
        if nombre and nombre not in nombres:
            nombres.append(nombre)
    return nombres


def codigos_por_nombre_operador_activo(db_path=DATABASE_PATH):
    operadores = listar_operadores_activos(db_path=db_path)
    if operadores.empty:
        return {}
    resultado = {}
    for _, fila in operadores.iterrows():
        nombre = _texto(fila.get("nombre_operador"))
        codigo = _codigo_operador(fila.get("codigo_operador"))
        if nombre and codigo and nombre not in resultado:
            resultado[nombre] = codigo
    return resultado


def crear_equipo(codigo_equipo, nombre_equipo, modelo="", tipo="", estado="operativo", db_path=DATABASE_PATH):
    codigo = _codigo_equipo(codigo_equipo)
    nombre = _texto(nombre_equipo)
    if not codigo:
        raise ValueError("Codigo de equipo obligatorio.")
    if not nombre:
        raise ValueError("Nombre de equipo obligatorio.")

    asegurar_tablas_catalogo(db_path=db_path)
    now = _now()
    with _connect(db_path) as connection:
        existente = connection.execute(
            f"SELECT 1 FROM {_quote(TABLA_EQUIPOS)} WHERE codigo_equipo = ?",
            (codigo,),
        ).fetchone()
        if existente:
            raise ValueError("Codigo de equipo duplicado.")
        connection.execute(
            f"""
            INSERT INTO {_quote(TABLA_EQUIPOS)}
                (codigo_equipo, nombre_equipo, modelo, tipo, estado, activo, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (codigo, nombre, _texto(modelo), _texto(tipo), _texto(estado) or "operativo", now, now),
        )
        connection.commit()
    return {"codigo_equipo": codigo, "nombre_equipo": nombre}


def crear_operador(codigo_operador, nombre_operador, empresa="", cargo="", db_path=DATABASE_PATH):
    codigo = _codigo_operador(codigo_operador)
    nombre = _texto(nombre_operador)
    if not codigo:
        raise ValueError("Codigo de operador obligatorio.")
    if not nombre:
        raise ValueError("Nombre de operador obligatorio.")

    asegurar_tablas_catalogo(db_path=db_path)
    now = _now()
    with _connect(db_path) as connection:
        existente = connection.execute(
            f"SELECT 1 FROM {_quote(TABLA_OPERADORES)} WHERE codigo_operador = ?",
            (codigo,),
        ).fetchone()
        if existente:
            raise ValueError("Codigo de operador duplicado.")
        connection.execute(
            f"""
            INSERT INTO {_quote(TABLA_OPERADORES)}
                (codigo_operador, nombre_operador, empresa, cargo, activo, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (codigo, nombre, _texto(empresa), _texto(cargo), now, now),
        )
        connection.commit()
    return {"codigo_operador": codigo, "nombre_operador": nombre}


def desactivar_equipo(codigo_equipo, db_path=DATABASE_PATH):
    codigo = _codigo_equipo(codigo_equipo)
    asegurar_tablas_catalogo(db_path=db_path)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            f"UPDATE {_quote(TABLA_EQUIPOS)} SET activo = 0, updated_at = ? WHERE codigo_equipo = ?",
            (_now(), codigo),
        )
        rowcount = cursor.rowcount
        connection.commit()
    return rowcount


def desactivar_operador(codigo_operador, db_path=DATABASE_PATH):
    codigo = _codigo_operador(codigo_operador)
    asegurar_tablas_catalogo(db_path=db_path)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            f"UPDATE {_quote(TABLA_OPERADORES)} SET activo = 0, updated_at = ? WHERE codigo_operador = ?",
            (_now(), codigo),
        )
        rowcount = cursor.rowcount
        connection.commit()
    return rowcount
