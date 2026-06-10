from unicodedata import normalize

import pandas as pd

import db
from services import malla_service


COLUMNAS_REGISTROS = {
    "fecha": ["Fecha turno", "Fecha"],
    "turno": ["Turno"],
    "equipo": ["Número equipo", "Equipo"],
    "operador": ["Operador"],
    "fase": ["Fase"],
    "banco": ["Banco"],
    "malla": ["Malla"],
    "tipo_sector": ["tipo_sector", "Tipo sector", "Tipo de sector"],
    "numero_precorte": ["numero_precorte", "Numero precorte operacional", "Número precorte operacional", "Número precorte"],
    "identificador_sector": ["identificador_sector", "Identificador sector"],
    "pozos_perforados": ["Pozos perforados turno", "Cantidad pozos perforados", "Pozos perforados"],
    "metros_perforados": ["Metros perforados"],
}


def _texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _clave(valor):
    texto = normalize("NFKD", _texto(valor)).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    if texto.startswith("producci"):
        return "produccion"
    return texto


def _normalizar_tipo_sector_registro(tipo_sector, malla):
    tipo = _texto(tipo_sector)
    if tipo:
        return tipo
    if _texto(malla):
        return "Producción"
    return "Sin clasificar"


def _sumar_registros(registros):
    if registros.empty:
        return 0.0, 0.0
    return float(registros["pozos_perforados"].sum()), float(registros["metros_perforados"].sum())


def _filtrar_por_clave(registros, columna, valor):
    clave = _clave(valor)
    if not clave or columna not in registros.columns:
        return registros.iloc[0:0].copy()
    return registros[registros[columna].map(_clave).eq(clave)].copy()


def _filtrar_registros_sector(registros_plan, sector):
    tipo_sector = _clave(sector.get("tipo_sector"))
    if tipo_sector == "produccion":
        return _filtrar_por_clave(registros_plan, "malla", sector.get("malla"))
    if tipo_sector == "precorte":
        return _filtrar_por_clave(registros_plan, "numero_precorte", sector.get("numero_precorte"))
    if tipo_sector in {"buffer 1", "buffer 2"}:
        return _filtrar_por_clave(registros_plan, "tipo_sector", sector.get("tipo_sector"))
    if tipo_sector == "borde":
        identificador = _texto(sector.get("identificador_sector"))
        if identificador:
            return _filtrar_por_clave(registros_plan, "identificador_sector", identificador)
        return _filtrar_por_clave(registros_plan, "tipo_sector", sector.get("tipo_sector"))
    if tipo_sector == "otro":
        return _filtrar_por_clave(registros_plan, "identificador_sector", sector.get("identificador_sector"))
    return registros_plan.iloc[0:0].copy()


def _numero(valor):
    numero = pd.to_numeric(pd.Series([valor]), errors="coerce").iloc[0]
    if pd.isna(numero):
        return 0.0
    return max(float(numero), 0.0)


def _pct(real, planificado):
    real = max(float(real or 0), 0.0)
    planificado = max(float(planificado or 0), 0.0)
    if planificado <= 0:
        return 0.0
    return round((real / planificado) * 100, 2)


def _estado_avance(porcentaje):
    porcentaje = max(float(porcentaje or 0), 0.0)
    if porcentaje > 105:
        return "Sobreperforado"
    if porcentaje >= 100:
        return "Completo"
    if porcentaje > 0:
        return "En avance"
    return "Sin iniciar"


def _semaforo(porcentaje):
    porcentaje = max(float(porcentaje or 0), 0.0)
    if porcentaje > 105:
        return "Morado"
    if porcentaje >= 100:
        return "Azul"
    if porcentaje > 70:
        return "Verde"
    if porcentaje > 30:
        return "Amarillo"
    return "Rojo"


def _tabla_existe(conn, tabla):
    fila = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (tabla,),
    ).fetchone()
    return fila is not None


def _columnas_tabla(conn, tabla):
    return [fila[1] for fila in conn.execute(f"PRAGMA table_info({db.quote_identifier(tabla)})").fetchall()]


def _resolver_columna(columnas, posibles):
    for columna in posibles:
        if columna in columnas:
            return columna
    return None


def obtener_registros_por_plan(conn, fase, banco):
    if not _tabla_existe(conn, db.TABLA_REGISTROS):
        return pd.DataFrame(columns=list(COLUMNAS_REGISTROS))

    columnas = _columnas_tabla(conn, db.TABLA_REGISTROS)
    seleccion = {}
    for destino, posibles in COLUMNAS_REGISTROS.items():
        origen = _resolver_columna(columnas, posibles)
        seleccion[destino] = origen

    columnas_select = [col for col in dict.fromkeys(seleccion.values()) if col]
    if not columnas_select:
        return pd.DataFrame(columns=list(COLUMNAS_REGISTROS))

    sql = f"SELECT {', '.join(db.quote_identifier(col) for col in columnas_select)} FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
    df = pd.read_sql_query(sql, conn)
    if df.empty:
        return pd.DataFrame(columns=list(COLUMNAS_REGISTROS))

    normalizado = pd.DataFrame()
    for destino, origen in seleccion.items():
        normalizado[destino] = df[origen] if origen and origen in df.columns else ""

    normalizado["fase"] = normalizado["fase"].astype(str).str.strip()
    normalizado["banco"] = normalizado["banco"].astype(str).str.strip()
    normalizado["malla"] = normalizado["malla"].astype(str).str.strip()
    normalizado["tipo_sector"] = normalizado.apply(
        lambda fila: _normalizar_tipo_sector_registro(fila.get("tipo_sector"), fila.get("malla")),
        axis=1,
    )
    normalizado["numero_precorte"] = normalizado["numero_precorte"].astype(str).str.strip()
    normalizado["identificador_sector"] = normalizado["identificador_sector"].astype(str).str.strip()
    normalizado["pozos_perforados"] = pd.to_numeric(normalizado["pozos_perforados"], errors="coerce").fillna(0).clip(lower=0)
    normalizado["metros_perforados"] = pd.to_numeric(normalizado["metros_perforados"], errors="coerce").fillna(0).clip(lower=0)

    mascara = normalizado["fase"].map(_clave).eq(_clave(fase)) & normalizado["banco"].map(_clave).eq(_clave(banco))
    return normalizado[mascara].reset_index(drop=True)


def _obtener_sector(conn, sector_id):
    fila = conn.execute(
        f"""
        SELECT s.*, p.fase, p.banco, p.nombre_plan
        FROM {malla_service.TABLA_SECTORES_PERFORACION} s
        INNER JOIN {malla_service.TABLA_PLANES_PERFORACION} p ON p.id = s.plan_id
        WHERE s.id = ?
        """,
        (int(sector_id),),
    ).fetchone()
    return dict(fila) if fila else None


def _obtener_plan(conn, plan_id):
    fila = conn.execute(
        f"SELECT * FROM {malla_service.TABLA_PLANES_PERFORACION} WHERE id = ?",
        (int(plan_id),),
    ).fetchone()
    return dict(fila) if fila else None


def _sectores_plan(conn, plan_id):
    filas = conn.execute(
        f"""
        SELECT s.*, p.fase, p.banco, p.nombre_plan
        FROM {malla_service.TABLA_SECTORES_PERFORACION} s
        INNER JOIN {malla_service.TABLA_PLANES_PERFORACION} p ON p.id = s.plan_id
        WHERE s.plan_id = ? AND COALESCE(s.activo, 1) = 1
        ORDER BY s.id
        """,
        (int(plan_id),),
    ).fetchall()
    return [dict(fila) for fila in filas]


def calcular_avance_sector(conn, sector_id):
    sector = _obtener_sector(conn, sector_id)
    if not sector:
        return {}

    pozos_planificados = _numero(sector.get("pozos_planificados"))
    metros_planificados = _numero(sector.get("metros_planificados"))
    pozos_perforados = 0.0
    metros_perforados = 0.0
    registros = pd.DataFrame(columns=list(COLUMNAS_REGISTROS))
    mensaje = ""

    tipo_sector = _clave(sector.get("tipo_sector"))
    registros_plan = obtener_registros_por_plan(conn, sector.get("fase"), sector.get("banco"))
    registros = _filtrar_registros_sector(registros_plan, sector)
    if not registros.empty:
        pozos_perforados, metros_perforados = _sumar_registros(registros)
    elif tipo_sector in {"precorte", "buffer 1", "buffer 2", "borde", "otro"}:
        mensaje = "Pendiente de clasificación operacional"
    avance_pozos_pct = _pct(pozos_perforados, pozos_planificados)
    avance_metros_pct = _pct(metros_perforados, metros_planificados)
    porcentaje_estado = avance_metros_pct if metros_planificados > 0 else avance_pozos_pct

    return {
        "sector_id": int(sector["id"]),
        "plan_id": int(sector["plan_id"]),
        "fase": sector.get("fase", ""),
        "banco": sector.get("banco", ""),
        "tipo_sector": sector.get("tipo_sector", ""),
        "malla": sector.get("malla", ""),
        "precorte": sector.get("numero_precorte", ""),
        "pozos_planificados": round(pozos_planificados, 2),
        "pozos_perforados": round(max(pozos_perforados, 0.0), 2),
        "pozos_pendientes": round(max(pozos_planificados - pozos_perforados, 0.0), 2),
        "avance_pozos_pct": avance_pozos_pct,
        "metros_planificados": round(metros_planificados, 2),
        "metros_perforados": round(max(metros_perforados, 0.0), 2),
        "metros_pendientes": round(max(metros_planificados - metros_perforados, 0.0), 2),
        "avance_metros_pct": avance_metros_pct,
        "estado_avance": mensaje or _estado_avance(porcentaje_estado),
        "semaforo": _semaforo(porcentaje_estado),
        "mensaje": mensaje,
        "registros": registros.reset_index(drop=True),
    }


def calcular_avance_plan(conn, plan_id):
    sectores = _sectores_plan(conn, plan_id)
    avances = [calcular_avance_sector(conn, sector["id"]) for sector in sectores]
    avances = [avance for avance in avances if avance]

    pozos_planificados = sum(avance["pozos_planificados"] for avance in avances)
    metros_planificados = sum(avance["metros_planificados"] for avance in avances)
    pozos_perforados = sum(avance["pozos_perforados"] for avance in avances)
    metros_perforados = sum(avance["metros_perforados"] for avance in avances)

    return {
        "plan_id": int(plan_id),
        "pozos_planificados_total": round(pozos_planificados, 2),
        "metros_planificados_total": round(metros_planificados, 2),
        "pozos_perforados_total": round(max(pozos_perforados, 0.0), 2),
        "metros_perforados_total": round(max(metros_perforados, 0.0), 2),
        "pozos_pendientes": round(max(pozos_planificados - pozos_perforados, 0.0), 2),
        "metros_pendientes": round(max(metros_planificados - metros_perforados, 0.0), 2),
        "avance_pozos_pct": _pct(pozos_perforados, pozos_planificados),
        "avance_metros_pct": _pct(metros_perforados, metros_planificados),
        "sectores": avances,
    }


def obtener_resumen_avance_plan(conn, plan_id):
    plan = _obtener_plan(conn, plan_id)
    avance = calcular_avance_plan(conn, plan_id)
    sectores = avance.pop("sectores", [])
    sectores_df = pd.DataFrame([{k: v for k, v in item.items() if k != "registros"} for item in sectores])
    registros = []
    for item in sectores:
        detalle = item.get("registros")
        if isinstance(detalle, pd.DataFrame) and not detalle.empty:
            registros.append(detalle)
    registros_df = pd.concat(registros, ignore_index=True) if registros else pd.DataFrame(columns=list(COLUMNAS_REGISTROS))
    return {
        "plan": plan,
        "avance": avance,
        "sectores": sectores_df,
        "registros": registros_df,
    }
