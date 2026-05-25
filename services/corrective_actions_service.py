from datetime import datetime, timedelta
from pathlib import Path
from unicodedata import normalize

import pandas as pd

import db


TABLA_ACCIONES = "acciones_correctivas"

ACCIONES_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "fecha": "TEXT NOT NULL",
    "equipo": "TEXT NOT NULL",
    "operador": "TEXT NOT NULL",
    "tipo_problema": "TEXT NOT NULL",
    "descripcion_problema": "TEXT NOT NULL",
    "accion_correctiva": "TEXT NOT NULL",
    "responsable": "TEXT NOT NULL",
    "prioridad": "TEXT NOT NULL",
    "fecha_compromiso": "TEXT NOT NULL",
    "estado": "TEXT NOT NULL",
    "observacion_final": "TEXT",
    "origen_fuente": "TEXT",
    "origen_regla": "TEXT",
    "origen_detalle": "TEXT",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL",
}

PRIORIDADES = ("Baja", "Media", "Alta", "Crítica")
ESTADOS = ("Pendiente", "En revisión", "Corregido", "Cerrado")
ESTADOS_TERMINALES = {"Corregido", "Cerrado"}


def _conexion(db_path=db.DB_PATH):
    return db.conectar_db(db_path)


def _quote(columna):
    return db.quote_identifier(columna)


def _ahora():
    return datetime.now().isoformat(timespec="seconds")


def _normalizar_texto(valor):
    return normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode("ascii").lower().strip()


def _texto(valor):
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valor).strip()


def _fecha_iso(valor):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    fecha = pd.to_datetime(pd.Series([valor]), errors="coerce").iloc[0]
    if pd.isna(fecha):
        return _texto(valor)
    return pd.Timestamp(fecha).date().isoformat()


def _dias_desde_hoy(fecha_texto):
    fecha = pd.to_datetime(pd.Series([fecha_texto]), errors="coerce").iloc[0]
    if pd.isna(fecha):
        return None
    return (pd.Timestamp(fecha).date() - datetime.now().date()).days


def _asegurar_tabla(db_path=db.DB_PATH):
    with _conexion(db_path) as connection:
        columnas_sql = ", ".join(f"{_quote(col)} {tipo}" for col, tipo in ACCIONES_COLUMNS.items())
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote(TABLA_ACCIONES)} (
                {columnas_sql}
            )
            """
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_acciones_fecha')} ON {_quote(TABLA_ACCIONES)} ({_quote('fecha')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_acciones_estado')} ON {_quote(TABLA_ACCIONES)} ({_quote('estado')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_acciones_equipo')} ON {_quote(TABLA_ACCIONES)} ({_quote('equipo')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_quote('idx_acciones_responsable')} ON {_quote(TABLA_ACCIONES)} ({_quote('responsable')})"
        )
        connection.commit()


def _normalizar_prioridad(valor):
    texto = _texto(valor)
    mapa = {
        "baja": "Baja",
        "media": "Media",
        "alta": "Alta",
        "critica": "Crítica",
        "crítica": "Crítica",
    }
    return mapa.get(_normalizar_texto(texto), texto or "Media")


def _normalizar_estado(valor):
    texto = _texto(valor)
    mapa = {
        "pendiente": "Pendiente",
        "en revision": "En revisión",
        "en revisión": "En revisión",
        "corregido": "Corregido",
        "cerrado": "Cerrado",
    }
    return mapa.get(_normalizar_texto(texto), texto or "Pendiente")


def _validar_no_vacio(campo, valor):
    if _texto(valor):
        return
    raise ValueError(f"El campo '{campo}' es obligatorio.")


def _cargar_accion(row):
    if row is None:
        return {}
    datos = dict(row)
    datos["vencida"] = _es_vencida(datos)
    datos["dias_para_compromiso"] = _dias_para_compromiso(datos.get("fecha_compromiso"))
    return datos


def _es_vencida(fila):
    estado = _normalizar_estado(fila.get("estado"))
    if estado in ESTADOS_TERMINALES:
        return False
    dias = _dias_desde_hoy(fila.get("fecha_compromiso"))
    return dias is not None and dias < 0


def _dias_para_compromiso(fecha_compromiso):
    fecha = pd.to_datetime(pd.Series([fecha_compromiso]), errors="coerce").iloc[0]
    if pd.isna(fecha):
        return None
    return (pd.Timestamp(fecha).date() - datetime.now().date()).days


def obtener_accion_por_id(accion_id, db_path=db.DB_PATH):
    path = Path(db_path)
    if not path.exists():
        return {}

    _asegurar_tabla(db_path)
    with _conexion(path) as connection:
        fila = connection.execute(
            f"SELECT * FROM {_quote(TABLA_ACCIONES)} WHERE {_quote('id')} = ?",
            (int(accion_id),),
        ).fetchone()
    return _cargar_accion(fila)


def registrar_accion_correctiva(
    accion,
    db_path=db.DB_PATH,
):
    _asegurar_tabla(db_path)
    accion = dict(accion or {})

    for campo in [
        "fecha",
        "equipo",
        "operador",
        "tipo_problema",
        "descripcion_problema",
        "accion_correctiva",
        "responsable",
        "prioridad",
        "fecha_compromiso",
    ]:
        _validar_no_vacio(campo, accion.get(campo))

    data = {
        "fecha": _fecha_iso(accion.get("fecha")),
        "equipo": _texto(accion.get("equipo")),
        "operador": _texto(accion.get("operador")),
        "tipo_problema": _texto(accion.get("tipo_problema")),
        "descripcion_problema": _texto(accion.get("descripcion_problema")),
        "accion_correctiva": _texto(accion.get("accion_correctiva")),
        "responsable": _texto(accion.get("responsable")),
        "prioridad": _normalizar_prioridad(accion.get("prioridad")),
        "fecha_compromiso": _fecha_iso(accion.get("fecha_compromiso")),
        "estado": _normalizar_estado(accion.get("estado", "Pendiente")),
        "observacion_final": _texto(accion.get("observacion_final")),
        "origen_fuente": _texto(accion.get("origen_fuente")),
        "origen_regla": _texto(accion.get("origen_regla")),
        "origen_detalle": _texto(accion.get("origen_detalle")),
    }
    now = _ahora()
    with _conexion(db_path) as connection:
        cursor = connection.execute(
            f"""
            INSERT INTO {_quote(TABLA_ACCIONES)} (
                {_quote('fecha')},
                {_quote('equipo')},
                {_quote('operador')},
                {_quote('tipo_problema')},
                {_quote('descripcion_problema')},
                {_quote('accion_correctiva')},
                {_quote('responsable')},
                {_quote('prioridad')},
                {_quote('fecha_compromiso')},
                {_quote('estado')},
                {_quote('observacion_final')},
                {_quote('origen_fuente')},
                {_quote('origen_regla')},
                {_quote('origen_detalle')},
                {_quote('created_at')},
                {_quote('updated_at')}
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["fecha"],
                data["equipo"],
                data["operador"],
                data["tipo_problema"],
                data["descripcion_problema"],
                data["accion_correctiva"],
                data["responsable"],
                data["prioridad"],
                data["fecha_compromiso"],
                data["estado"],
                data["observacion_final"],
                data["origen_fuente"],
                data["origen_regla"],
                data["origen_detalle"],
                now,
                now,
            ),
        )
        connection.commit()
        return obtener_accion_por_id(cursor.lastrowid, db_path=db_path)


def crear_accion_desde_observacion(observacion, db_path=db.DB_PATH, responsable=None, prioridad=None, fecha_compromiso=None):
    observacion = dict(observacion or {})
    tipo_problema = _texto(observacion.get("Regla") or observacion.get("tipo_problema") or "Observación de calidad")
    descripcion = _texto(observacion.get("Mensaje") or observacion.get("descripcion_problema") or "Observación detectada por el módulo de calidad de datos.")
    accion_correctiva = _texto(observacion.get("Recomendación operacional") or observacion.get("accion_correctiva") or "Revisar la observación detectada.")
    equipo = _texto(observacion.get("Modelo equipo") or observacion.get("equipo") or observacion.get("Equipo"))
    operador = _texto(observacion.get("Operador") or observacion.get("operador"))
    fecha = observacion.get("Fecha turno") or observacion.get("fecha") or datetime.now().date().isoformat()
    prioridad = _normalizar_prioridad(prioridad or ("Crítica" if _normalizar_texto(observacion.get("Estado")) == "error" else "Alta"))
    if fecha_compromiso is None:
        dias = {"Crítica": 1, "Alta": 3, "Media": 5, "Baja": 7}.get(prioridad, 5)
        fecha_compromiso = (pd.Timestamp(datetime.now().date()) + pd.Timedelta(days=dias)).date().isoformat()
    return registrar_accion_correctiva(
        {
            "fecha": fecha,
            "equipo": equipo or "Sin equipo",
            "operador": operador or "Sin operador",
            "tipo_problema": tipo_problema,
            "descripcion_problema": descripcion,
            "accion_correctiva": accion_correctiva,
            "responsable": responsable or operador or "Sin responsable",
            "prioridad": prioridad,
            "fecha_compromiso": fecha_compromiso,
            "estado": "Pendiente",
            "observacion_final": "",
            "origen_fuente": "calidad_datos",
            "origen_regla": tipo_problema,
            "origen_detalle": descripcion,
        },
        db_path=db_path,
    )


def actualizar_estado_accion(accion_id, estado, observacion_final="", db_path=db.DB_PATH):
    estado_normalizado = _normalizar_estado(estado)
    if estado_normalizado not in ESTADOS:
        raise ValueError(f"Estado inválido: {estado}")

    _asegurar_tabla(db_path)
    now = _ahora()
    with _conexion(db_path) as connection:
        cursor = connection.execute(
            f"""
            UPDATE {_quote(TABLA_ACCIONES)}
            SET {_quote('estado')} = ?,
                {_quote('observacion_final')} = ?,
                {_quote('updated_at')} = ?
            WHERE {_quote('id')} = ?
            """,
            (estado_normalizado, _texto(observacion_final), now, int(accion_id)),
        )
        connection.commit()
        return cursor.rowcount


def listar_acciones_correctivas(
    db_path=db.DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    equipo=None,
    estado=None,
    responsable=None,
    prioridad=None,
    limit=None,
):
    path = Path(db_path)
    if not path.exists():
        columnas = list(ACCIONES_COLUMNS.keys()) + ["vencida", "dias_para_compromiso"]
        return pd.DataFrame(columns=columnas)

    _asegurar_tabla(db_path)
    with _conexion(path) as connection:
        where = []
        params = []
        if fecha_desde:
            where.append(f"date({_quote('fecha')}) >= date(?)")
            params.append(_fecha_iso(fecha_desde))
        if fecha_hasta:
            where.append(f"date({_quote('fecha')}) <= date(?)")
            params.append(_fecha_iso(fecha_hasta))
        if equipo:
            equipos = [equipo] if not isinstance(equipo, (list, tuple, set)) else list(equipo)
            equipos = [_texto(item) for item in equipos if _texto(item)]
            if equipos:
                where.append(f"{_quote('equipo')} IN ({', '.join('?' for _ in equipos)})")
                params.extend(equipos)
        if estado:
            estados = [estado] if not isinstance(estado, (list, tuple, set)) else list(estado)
            estados = [_normalizar_estado(item) for item in estados if _texto(item)]
            if estados:
                where.append(f"{_quote('estado')} IN ({', '.join('?' for _ in estados)})")
                params.extend(estados)
        if responsable:
            responsables = [responsable] if not isinstance(responsable, (list, tuple, set)) else list(responsable)
            responsables = [_texto(item) for item in responsables if _texto(item)]
            if responsables:
                where.append(f"{_quote('responsable')} IN ({', '.join('?' for _ in responsables)})")
                params.extend(responsables)
        if prioridad:
            prioridades = [prioridad] if not isinstance(prioridad, (list, tuple, set)) else list(prioridad)
            prioridades = [_normalizar_prioridad(item) for item in prioridades if _texto(item)]
            if prioridades:
                where.append(f"{_quote('prioridad')} IN ({', '.join('?' for _ in prioridades)})")
                params.extend(prioridades)

        sql = f"SELECT * FROM {_quote(TABLA_ACCIONES)}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {_quote('updated_at')} DESC, {_quote('id')} DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        df = pd.read_sql_query(sql, connection, params=params)

    if df.empty:
        df["vencida"] = pd.Series(dtype=bool)
        df["dias_para_compromiso"] = pd.Series(dtype=float)
        return df

    df["vencida"] = df.apply(_es_vencida, axis=1)
    df["dias_para_compromiso"] = df["fecha_compromiso"].apply(_dias_para_compromiso)
    return df


def resumen_acciones_correctivas(db_path=db.DB_PATH):
    df = listar_acciones_correctivas(db_path=db_path)
    if df.empty:
        return {
            "total": 0,
            "pendientes": 0,
            "vencidas": 0,
            "cerradas": 0,
            "criticas": 0,
            "detalle": df,
        }

    estados_normalizados = df["estado"].astype(str).map(_normalizar_estado)
    prioridades_normalizadas = df["prioridad"].astype(str).map(_normalizar_prioridad)
    return {
        "total": int(len(df)),
        "pendientes": int((estados_normalizados == "Pendiente").sum()),
        "vencidas": int(df["vencida"].fillna(False).sum()),
        "cerradas": int(estados_normalizados.isin(ESTADOS_TERMINALES).sum()),
        "criticas": int((prioridades_normalizadas == "Crítica").sum()),
        "detalle": df,
    }


def obtener_valores_distintos_acciones(columna, db_path=db.DB_PATH):
    df = listar_acciones_correctivas(db_path=db_path)
    if df.empty or columna not in df.columns:
        return []
    valores = []
    for valor in df[columna].dropna().astype(str):
        texto = valor.strip()
        if texto and texto not in valores:
            valores.append(texto)
    return sorted(valores)
