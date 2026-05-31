from datetime import datetime, timedelta
import json
from pathlib import Path
from unicodedata import normalize

import pandas as pd

import db
from metrics import calcular_disponibilidad, calcular_rendimiento_consolidado, calcular_utilizacion
from services.alert_service import evaluar_alertas_operacionales as evaluar_alertas_base


TABLA_ALERTAS = "alertas_inteligentes"
TABLA_CONTROL = "alertas_inteligentes_control"

ALERTAS_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "alert_key": "TEXT NOT NULL UNIQUE",
    "registro_id": "INTEGER NOT NULL",
    "fecha_turno": "TEXT",
    "turno": "TEXT",
    "equipo": "TEXT",
    "numero_equipo": "TEXT",
    "operador": "TEXT",
    "causa": "TEXT NOT NULL",
    "recomendacion": "TEXT NOT NULL",
    "criticidad": "TEXT NOT NULL",
    "estado": "TEXT NOT NULL DEFAULT 'pendiente'",
    "regla": "TEXT NOT NULL",
    "valor_metrico": "REAL",
    "valor_referencia": "REAL",
    "detalle": "TEXT",
    "first_seen_at": "TEXT NOT NULL",
    "last_seen_at": "TEXT NOT NULL",
    "resolved_at": "TEXT",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL",
}

CONTROL_COLUMNS = {
    "clave": "TEXT PRIMARY KEY",
    "valor": "TEXT",
    "updated_at": "TEXT NOT NULL",
}

CONTRATO_ALERTA = {
    "baja_utilizacion": {
        "causa": "Baja utilización",
        "criticidad": "PREVENTIVA",
        "recomendacion": "Revisar continuidad operacional, detenciones y secuencia de perforación.",
    },
    "baja_disponibilidad": {
        "causa": "Baja disponibilidad",
        "criticidad": "CRÍTICA",
        "recomendacion": "Revisar averías, mantención y tiempos muertos del equipo.",
    },
    "rendimiento_bajo_promedio": {
        "causa": "Rendimiento bajo promedio",
        "criticidad": "PREVENTIVA",
        "recomendacion": "Revisar parámetros de perforación y condición de terreno.",
    },
    "exceso_horas_no_efectivas": {
        "causa": "Exceso de horas no efectivas",
        "criticidad": "CRÍTICA",
        "recomendacion": "Priorizar revisión de detenciones y tiempos improductivos.",
    },
    "exceso_repaso": {
        "causa": "Exceso de repaso",
        "criticidad": "PREVENTIVA",
        "recomendacion": "Verificar secuencia de perforación y necesidad de re-trabajo.",
    },
    "operador_fuera_tendencia": {
        "causa": "Operador fuera de tendencia",
        "criticidad": "PREVENTIVA",
        "recomendacion": "Comparar con su tendencia histórica y revisar apoyo operacional.",
    },
    "equipo_detenciones_recurrentes": {
        "causa": "Equipo con detenciones recurrentes",
        "criticidad": "CRÍTICA",
        "recomendacion": "Revisar recurrencia de fallas y plan de mantenimiento.",
    },
    "equipo_caida_rendimiento": {
        "causa": "Caída progresiva de rendimiento",
        "criticidad": "CRÍTICA",
        "recomendacion": "Revisar secuencia temporal del equipo y cambios de condición de terreno.",
    },
    "exceso_cambio_aceros": {
        "causa": "Exceso de cambios de aceros",
        "criticidad": "PREVENTIVA",
        "recomendacion": "Revisar desgaste de aceros y condición de perforación.",
    },
    "desviacion_operadores_equipo": {
        "causa": "Diferencia anormal entre operadores del mismo equipo",
        "criticidad": "PREVENTIVA",
        "recomendacion": "Comparar desempeño por operador y revisar curva de aprendizaje.",
    },
}

ESTADOS_ALERTA = ("pendiente", "vista", "atendida")
VENTANA_HISTORICA_DIAS = 60
UMBRAL_REPASO = 2
UMBRAL_REPETICION_DETENCION = 3


def _conexion(db_path=db.DB_PATH):
    return db.conectar_db(db_path)


def _quote(columna):
    return db.quote_identifier(columna)


def _ahora():
    return datetime.now().isoformat(timespec="seconds")


def asegurar_tablas(db_path=db.DB_PATH):
    with _conexion(db_path) as connection:
        db.crear_tablas(db_path=db_path)
        columnas_sql = ", ".join(f"{_quote(col)} {tipo}" for col, tipo in ALERTAS_COLUMNS.items())
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS { _quote(TABLA_ALERTAS) } (
                {columnas_sql}
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS { _quote(TABLA_CONTROL) } (
                {", ".join(f"{_quote(col)} {tipo}" for col, tipo in CONTROL_COLUMNS.items())}
            )
            """
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS { _quote('idx_alertas_inteligentes_estado') } ON { _quote(TABLA_ALERTAS) } ({_quote('estado')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS { _quote('idx_alertas_inteligentes_fecha') } ON { _quote(TABLA_ALERTAS) } ({_quote('fecha_turno')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS { _quote('idx_alertas_inteligentes_equipo') } ON { _quote(TABLA_ALERTAS) } ({_quote('equipo')})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS { _quote('idx_alertas_inteligentes_operador') } ON { _quote(TABLA_ALERTAS) } ({_quote('operador')})"
        )
        connection.commit()


def _set_control(clave, valor, db_path=db.DB_PATH):
    asegurar_tablas(db_path=db_path)
    with _conexion(db_path) as connection:
        connection.execute(
            f"""
            INSERT INTO {_quote(TABLA_CONTROL)} ({_quote('clave')}, {_quote('valor')}, {_quote('updated_at')})
            VALUES (?, ?, ?)
            ON CONFLICT({_quote('clave')})
            DO UPDATE SET {_quote('valor')} = excluded.{_quote('valor')},
                          {_quote('updated_at')} = excluded.{_quote('updated_at')}
            """,
            (clave, str(valor), _ahora()),
        )
        connection.commit()


def _get_control(clave, db_path=db.DB_PATH, default=""):
    asegurar_tablas(db_path=db_path)
    with _conexion(db_path) as connection:
        fila = connection.execute(
            f"SELECT {_quote('valor')} FROM {_quote(TABLA_CONTROL)} WHERE {_quote('clave')} = ?",
            (clave,),
        ).fetchone()
    return fila["valor"] if fila else default


def obtener_ultimo_registro_procesado(db_path=db.DB_PATH):
    valor = _get_control("ultimo_registro_procesado", db_path=db_path, default="0")
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def guardar_ultimo_registro_procesado(valor, db_path=db.DB_PATH):
    _set_control("ultimo_registro_procesado", int(valor), db_path=db_path)


def obtener_ultima_ejecucion(db_path=db.DB_PATH):
    return _get_control("ultima_ejecucion", db_path=db_path, default="")


def _normalizar(valor):
    return normalize("NFKD", str(valor)).encode("ascii", "ignore").decode("ascii").lower().strip()


def _buscar_columna(df, *candidatos):
    normalizadas = {_normalizar(col): col for col in df.columns}
    for candidato in candidatos:
        columna = normalizadas.get(_normalizar(candidato))
        if columna:
            return columna
    return None


def _serie(df, *columnas):
    columna = _buscar_columna(df, *columnas)
    if not columna:
        return pd.Series(0, index=df.index, dtype=float)
    return pd.to_numeric(df[columna], errors="coerce").fillna(0)


def _numero(valor):
    try:
        if pd.isna(valor):
            return 0.0
    except (TypeError, ValueError):
        pass
    numero = pd.to_numeric(pd.Series([valor]), errors="coerce").fillna(0).iloc[0]
    return float(numero)


def _valor_texto(df, fila, *columnas):
    columna = _buscar_columna(df, *columnas)
    if not columna:
        return ""
    valor = df.at[fila, columna]
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def _buscar_registros_recientes(db_path, fecha_turno, equipo=None, operador=None, dias=VENTANA_HISTORICA_DIAS):
    fecha = pd.to_datetime(pd.Series([fecha_turno]), errors="coerce").iloc[0]
    if pd.isna(fecha):
        return pd.DataFrame()
    fecha_inicio = (fecha - timedelta(days=dias)).date().isoformat()
    fecha_fin = fecha.date().isoformat()
    return db.consultar_historial_filtrado(
        db_path=db_path,
        fecha_desde=fecha_inicio,
        fecha_hasta=fecha_fin,
        equipo=[equipo] if equipo else None,
        operador=[operador] if operador else None,
    )


def _detectar_repaso(fila):
    texto = " ".join(
        part for part in [
            str(fila.get("Tipo detención", "")),
            str(fila.get("Causa detención", "")),
            str(fila.get("Observaciones", "")),
        ]
        if part
    ).lower()
    return "repaso" in texto


def _generar_alertas_fila(registro, contexto, db_path):
    alertas = []
    equipo = str(registro.get("Equipo") or registro.get("Modelo equipo") or "").strip()
    numero_equipo = str(registro.get("Número equipo") or "").strip()
    operador = str(registro.get("Operador") or "").strip()
    fecha_turno = registro.get("Fecha turno")
    turno = str(registro.get("Turno") or "").strip()
    registro_id = int(registro.get("id", 0) or 0)

    horas_turno = _numero(registro.get("Horas turno", 12))
    metros = _numero(registro.get("Metros perforados", 0))
    utilizacion = _numero(registro.get("Utilización", registro.get("Utilización", 0)))
    disponibilidad = _numero(registro.get("Disponibilidad %", 0))
    rendimiento = _numero(registro.get("Rendimiento m/h", 0))
    horas_no_efectivas = _numero(registro.get("Horas detención No efectivas", 0))
    horas_efectivas = _numero(registro.get("Horas efectivas perforando", 0))
    horas_averia = _numero(registro.get("Horas detención mecánica", 0))
    horas_mantencion = _numero(registro.get("Mantención Programada", 0))
    tipo_detencion = str(registro.get("Tipo detención", "") or "")
    horas_cambios_aceros = _numero(registro.get("Cambio de aceros", 0))

    if rendimiento <= 0 and horas_efectivas > 0 and metros > 0:
        rendimiento = metros / horas_efectivas
    if utilizacion <= 0 and horas_turno > 0:
        utilizacion = calcular_utilizacion(horas_efectivas, horas_turno=horas_turno)
    if disponibilidad <= 0 and horas_turno > 0:
        disponibilidad = calcular_disponibilidad(
            horas_averia,
            horas_turno=horas_turno,
            horas_mantencion=horas_mantencion,
        )

    historico = contexto.copy() if not contexto.empty else pd.DataFrame([registro])
    if "Fecha turno" in historico.columns:
        historico["Fecha turno"] = pd.to_datetime(historico["Fecha turno"], errors="coerce")
        historico = historico.sort_values("Fecha turno")

    base_rendimiento = float(calcular_rendimiento_consolidado(historico))
    promedio_utilizacion = float(_serie(historico, "Utilización", "Utilización").mean()) if not historico.empty else utilizacion
    promedio_disponibilidad = float(_serie(historico, "Disponibilidad %").mean()) if not historico.empty else disponibilidad
    promedio_horas_no_efectivas = float(_serie(historico, "Horas detención No efectivas").mean()) if not historico.empty else horas_no_efectivas
    promedio_horas_efectivas = float(_serie(historico, "Horas efectivas perforando").mean()) if not historico.empty else horas_efectivas

    if utilizacion < 55:
        alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "baja_utilizacion", utilizacion, 55))
    if disponibilidad < 70:
        alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "baja_disponibilidad", disponibilidad, 70))
    if rendimiento > 0 and rendimiento < 10:
        alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "rendimiento_bajo_promedio", rendimiento, 10))
    if horas_no_efectivas > max(2.0, horas_efectivas * 0.25):
        alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "exceso_horas_no_efectivas", horas_no_efectivas, max(2.0, horas_efectivas * 0.25)))
    if _detectar_repaso(registro):
        alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "exceso_repaso", horas_no_efectivas, UMBRAL_REPASO))
    if horas_cambios_aceros >= 3:
        alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "exceso_cambio_aceros", horas_cambios_aceros, 3))

    if not historico.empty:
        operador_hist = historico[historico["Operador"].astype(str).eq(operador)] if "Operador" in historico.columns else historico.iloc[0:0]
        equipo_hist = historico[historico["Equipo"].astype(str).eq(equipo)] if "Equipo" in historico.columns else historico.iloc[0:0]
        if len(operador_hist) >= 3:
            media_op = float(_serie(operador_hist, "Utilización", "Utilización").mean())
            if media_op > 0 and utilizacion < media_op * 0.75:
                alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "operador_fuera_tendencia", utilizacion, media_op))
        if len(equipo_hist) >= 4:
            rendimientos = _serie(equipo_hist, "Rendimiento m/h")
            if rendimientos.tail(3).is_monotonic_decreasing and rendimientos.tail(3).iloc[0] - rendimientos.tail(3).iloc[-1] >= 2:
                alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "equipo_caida_rendimiento", rendimiento, float(rendimientos.tail(3).iloc[-1])))
            if equipo_hist["Tipo detención"].astype(str).str.contains("aver", case=False, na=False).sum() >= UMBRAL_REPETICION_DETENCION:
                alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "equipo_detenciones_recurrentes", equipo_hist["Tipo detención"].astype(str).str.contains("aver", case=False, na=False).sum(), UMBRAL_REPETICION_DETENCION))

        if "Equipo" in historico.columns and "Operador" in historico.columns and equipo_hist is not None:
            resumen_ops = historico[historico["Equipo"].astype(str).eq(equipo)].groupby("Operador", as_index=False).agg({
                "Metros perforados": "sum",
                "Horas efectivas perforando": "sum",
            })
            if len(resumen_ops) >= 2:
                metros_por_hora = resumen_ops["Metros perforados"] / resumen_ops["Horas efectivas perforando"].replace(0, pd.NA)
                metros_por_hora = metros_por_hora.fillna(0)
                if metros_por_hora.max() > 0 and metros_por_hora.max() - metros_por_hora.min() > metros_por_hora.mean() * 0.4:
                    alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "desviacion_operadores_equipo", float(metros_por_hora.max()), float(metros_por_hora.min())))

    if rendimiento > 0 and base_rendimiento > 0 and rendimiento < base_rendimiento * 0.8:
        alertas.append(_alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, "operador_fuera_tendencia", rendimiento, base_rendimiento))

    return alertas


def _alerta(registro_id, fecha_turno, turno, equipo, numero_equipo, operador, regla, valor_metrico, valor_referencia):
    meta = CONTRATO_ALERTA[regla]
    return {
        "alert_key": f"{regla}:{registro_id}",
        "registro_id": int(registro_id),
        "fecha_turno": _formato_fecha(fecha_turno),
        "turno": turno,
        "equipo": equipo,
        "numero_equipo": numero_equipo,
        "operador": operador,
        "causa": meta["causa"],
        "recomendacion": meta["recomendacion"],
        "criticidad": meta["criticidad"],
        "estado": "pendiente",
        "regla": regla,
        "valor_metrico": round(float(valor_metrico), 2),
        "valor_referencia": round(float(valor_referencia), 2),
        "detalle": json.dumps({
            "regla": regla,
            "valor_metrico": round(float(valor_metrico), 2),
            "valor_referencia": round(float(valor_referencia), 2),
        }, ensure_ascii=False),
        "first_seen_at": _ahora(),
        "last_seen_at": _ahora(),
        "created_at": _ahora(),
        "updated_at": _ahora(),
        "resolved_at": None,
    }


def _persistir_alertas(alertas, db_path=db.DB_PATH):
    if not alertas:
        return 0

    asegurar_tablas(db_path=db_path)
    now = _ahora()
    insertadas = 0
    with _conexion(db_path) as connection:
        for alerta in alertas:
            existente = connection.execute(
                f"SELECT {_quote('id')}, {_quote('estado')}, {_quote('first_seen_at')} FROM {_quote(TABLA_ALERTAS)} WHERE {_quote('alert_key')} = ?",
                (alerta["alert_key"],),
            ).fetchone()
            if existente:
                connection.execute(
                    f"""
                    UPDATE {_quote(TABLA_ALERTAS)}
                    SET {_quote('registro_id')} = ?,
                        {_quote('fecha_turno')} = ?,
                        {_quote('turno')} = ?,
                        {_quote('equipo')} = ?,
                        {_quote('numero_equipo')} = ?,
                        {_quote('operador')} = ?,
                        {_quote('causa')} = ?,
                        {_quote('recomendacion')} = ?,
                        {_quote('criticidad')} = ?,
                        {_quote('estado')} = ?,
                        {_quote('regla')} = ?,
                        {_quote('valor_metrico')} = ?,
                        {_quote('valor_referencia')} = ?,
                        {_quote('detalle')} = ?,
                        {_quote('last_seen_at')} = ?,
                        {_quote('updated_at')} = ?
                    WHERE {_quote('alert_key')} = ?
                    """,
                    (
                        alerta["registro_id"],
                        alerta["fecha_turno"],
                        alerta["turno"],
                        alerta["equipo"],
                        alerta["numero_equipo"],
                        alerta["operador"],
                        alerta["causa"],
                        alerta["recomendacion"],
                        alerta["criticidad"],
                        existente["estado"] or "pendiente",
                        alerta["regla"],
                        alerta["valor_metrico"],
                        alerta["valor_referencia"],
                        alerta["detalle"],
                        now,
                        now,
                        alerta["alert_key"],
                    ),
                )
            else:
                connection.execute(
                    f"""
                    INSERT INTO {_quote(TABLA_ALERTAS)}
                    (
                        {_quote('alert_key')},
                        {_quote('registro_id')},
                        {_quote('fecha_turno')},
                        {_quote('turno')},
                        {_quote('equipo')},
                        {_quote('numero_equipo')},
                        {_quote('operador')},
                        {_quote('causa')},
                        {_quote('recomendacion')},
                        {_quote('criticidad')},
                        {_quote('estado')},
                        {_quote('regla')},
                        {_quote('valor_metrico')},
                        {_quote('valor_referencia')},
                        {_quote('detalle')},
                        {_quote('first_seen_at')},
                        {_quote('last_seen_at')},
                        {_quote('created_at')},
                        {_quote('updated_at')},
                        {_quote('resolved_at')}
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alerta["alert_key"],
                        alerta["registro_id"],
                        alerta["fecha_turno"],
                        alerta["turno"],
                        alerta["equipo"],
                        alerta["numero_equipo"],
                        alerta["operador"],
                        alerta["causa"],
                        alerta["recomendacion"],
                        alerta["criticidad"],
                        alerta["estado"],
                        alerta["regla"],
                        alerta["valor_metrico"],
                        alerta["valor_referencia"],
                        alerta["detalle"],
                        alerta["first_seen_at"],
                        alerta["last_seen_at"],
                        alerta["created_at"],
                        alerta["updated_at"],
                        alerta["resolved_at"],
                    ),
                )
                insertadas += 1
        connection.commit()
    return insertadas


def ejecutar_motor_alertas(db_path=db.DB_PATH, force=False):
    asegurar_tablas(db_path=db_path)
    ultimo = obtener_ultimo_registro_procesado(db_path=db_path)
    if force:
        ultimo = 0

    df_nuevos = _obtener_registros_pendientes(db_path=db_path, ultimo_id=ultimo)
    if df_nuevos.empty:
        _set_control("ultima_ejecucion", _ahora(), db_path=db_path)
        return {"nuevas_alertas": 0, "registros_procesados": 0, "ultimo_registro": ultimo}

    alertas = []
    max_id = ultimo
    for _, fila in df_nuevos.iterrows():
        registro = fila.to_dict()
        registro_id = int(registro.get("id", 0) or 0)
        if registro_id > max_id:
            max_id = registro_id
        contexto = _buscar_registros_recientes(
            db_path=db_path,
            fecha_turno=registro.get("Fecha turno"),
            equipo=registro.get("Equipo") or registro.get("Modelo equipo"),
            operador=registro.get("Operador"),
        )
        alertas.extend(_generar_alertas_fila(registro, contexto, db_path))

    alertas = _deduplicar_alertas(alertas)
    insertadas = _persistir_alertas(alertas, db_path=db_path)
    guardar_ultimo_registro_procesado(max_id, db_path=db_path)
    _set_control("ultima_ejecucion", _ahora(), db_path=db_path)
    return {
        "nuevas_alertas": insertadas,
        "registros_procesados": len(df_nuevos),
        "ultimo_registro": max_id,
    }


def _obtener_registros_pendientes(db_path=db.DB_PATH, ultimo_id=0):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()
    with _conexion(db_path) as connection:
        query = f"""
            SELECT *
            FROM {_quote(db.TABLA_REGISTROS)}
            WHERE id > ?
            ORDER BY id
        """
        df = pd.read_sql_query(query, connection, params=[int(ultimo_id)])
    from data import preparar_dataframe
    return preparar_dataframe(df)


def _formato_fecha(valor):
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.isna(fecha):
        return ""
    return fecha.date().isoformat()


def _deduplicar_alertas(alertas):
    unicas = {}
    for alerta in alertas:
        unicas[alerta["alert_key"]] = alerta
    return list(unicas.values())


def obtener_alertas_inteligentes(
    db_path=db.DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    turno=None,
    equipo=None,
    operador=None,
    criticidad=None,
    estado=None,
):
    asegurar_tablas(db_path=db_path)
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame(columns=list(ALERTAS_COLUMNS.keys()))

    filtros = []
    params = []
    if fecha_desde:
        filtros.append(f"date({_quote('fecha_turno')}) >= date(?)")
        params.append(str(fecha_desde))
    if fecha_hasta:
        filtros.append(f"date({_quote('fecha_turno')}) <= date(?)")
        params.append(str(fecha_hasta))
    if turno:
        valores = _normalizar_lista(turno)
        if valores:
            filtros.append(f"{_quote('turno')} IN ({', '.join('?' for _ in valores)})")
            params.extend(valores)
    if equipo:
        valores = _normalizar_lista(equipo)
        if valores:
            filtros.append(f"{_quote('equipo')} IN ({', '.join('?' for _ in valores)})")
            params.extend(valores)
    if operador:
        valores = _normalizar_lista(operador)
        if valores:
            filtros.append(f"{_quote('operador')} IN ({', '.join('?' for _ in valores)})")
            params.extend(valores)
    if criticidad:
        valores = _normalizar_lista(criticidad)
        if valores:
            filtros.append(f"{_quote('criticidad')} IN ({', '.join('?' for _ in valores)})")
            params.extend(valores)
    if estado:
        valores = _normalizar_lista(estado)
        if valores:
            filtros.append(f"{_quote('estado')} IN ({', '.join('?' for _ in valores)})")
            params.extend(valores)

    query = f"SELECT * FROM {_quote(TABLA_ALERTAS)}"
    if filtros:
        query += " WHERE " + " AND ".join(filtros)
    query += f" ORDER BY {_quote('created_at')} DESC, {_quote('id')} DESC"

    with _conexion(db_path) as connection:
        return pd.read_sql_query(query, connection, params=params)


def _normalizar_lista(valor):
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set, pd.Index, pd.Series)):
        valores = list(valor)
    else:
        valores = [valor]
    return [str(item).strip() for item in valores if str(item).strip()]


def marcar_alertas_estado(alert_keys, estado, db_path=db.DB_PATH):
    if estado not in ESTADOS_ALERTA:
        raise ValueError("Estado de alerta inválido.")
    claves = _normalizar_lista(alert_keys)
    if not claves:
        return 0
    asegurar_tablas(db_path=db_path)
    now = _ahora()
    with _conexion(db_path) as connection:
        connection.executemany(
            f"""
            UPDATE {_quote(TABLA_ALERTAS)}
            SET {_quote('estado')} = ?,
                {_quote('updated_at')} = ?,
                {_quote('resolved_at')} = CASE WHEN ? = 'atendida' THEN ? ELSE {_quote('resolved_at')} END
            WHERE {_quote('alert_key')} = ?
            """,
            [(estado, now, estado, now, key) for key in claves],
        )
        connection.commit()
    return len(claves)


def resumen_alertas_inteligentes(db_path=db.DB_PATH):
    df = obtener_alertas_inteligentes(db_path=db_path)
    if df.empty:
        return {
            "total": 0,
            "pendientes": 0,
            "vistas": 0,
            "atendidas": 0,
            "por_criticidad": pd.DataFrame(columns=["criticidad", "cantidad"]),
        }
    conteos = df["estado"].value_counts().to_dict()
    por_criticidad = df.groupby("criticidad", as_index=False).size().rename(columns={"size": "cantidad"})
    return {
        "total": int(len(df)),
        "pendientes": int(conteos.get("pendiente", 0)),
        "vistas": int(conteos.get("vista", 0)),
        "atendidas": int(conteos.get("atendida", 0)),
        "por_criticidad": por_criticidad,
    }
