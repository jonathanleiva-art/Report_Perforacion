import pandas as pd

import db
from config import DATABASE_PATH
from services import operational_excel_query_service, operational_excel_service, source_service
from services.ciclos_service import leer_ciclos_operacional


ID_MANUAL_SQLITE = "manual_sqlite"
TIPO_MANUAL_SQLITE = "manual_sqlite"
TIPO_REGISTRO_OPERACIONAL_EXCEL = "registro_operacional_excel"
TIPO_CICLOS_PERFORACION = "ciclos_perforacion"
TIPO_DESCONOCIDO = "desconocido"

ESTADOS_VISIBLES = {"activa", "diagnosticada", "importada", "pendiente_importador"}


def _texto(valor, default=""):
    texto = str(valor if valor is not None else "").strip()
    return texto or default


def _estado_normalizado(valor):
    return _texto(valor, "activa").lower()


def _activo(valor):
    try:
        return int(valor) == 1
    except (TypeError, ValueError):
        return bool(valor)


def _fuente_manual():
    return {
        "id_fuente": ID_MANUAL_SQLITE,
        "nombre_fuente": "Registros manuales SQLite",
        "tipo_fuente": TIPO_MANUAL_SQLITE,
        "tipo_dashboard": TIPO_MANUAL_SQLITE,
        "estado": "activa",
        "activo": 1,
        "archivo_origen": "",
        "fecha_importacion": "",
        "total_registros": None,
        "fecha_min": None,
        "fecha_max": None,
        "recomendacion_dashboard": "Dashboard principal",
    }


def clasificar_fuente_para_dashboard(fuente):
    tipo = _texto((fuente or {}).get("tipo_fuente")).lower()
    estado = _estado_normalizado((fuente or {}).get("estado"))

    if tipo == TIPO_MANUAL_SQLITE:
        return TIPO_MANUAL_SQLITE
    if tipo in operational_excel_service.TIPOS_FUENTE_OPERACIONAL:
        return TIPO_REGISTRO_OPERACIONAL_EXCEL
    if tipo == "excel_ciclos":
        return TIPO_CICLOS_PERFORACION
    if estado in ESTADOS_VISIBLES:
        return TIPO_DESCONOCIDO
    return TIPO_DESCONOCIDO


def _recomendacion_dashboard(fuente):
    estado = _estado_normalizado((fuente or {}).get("estado"))
    if estado == "diagnosticada":
        return "Pendiente de importación"
    if estado == "pendiente_importador":
        return "Importador pendiente"

    clasificacion = clasificar_fuente_para_dashboard(fuente)
    if clasificacion == TIPO_MANUAL_SQLITE:
        return "Dashboard principal"
    if clasificacion == TIPO_REGISTRO_OPERACIONAL_EXCEL:
        return "Dashboard Excel Operacional" if estado == "importada" else "Pendiente de importación"
    if clasificacion == TIPO_CICLOS_PERFORACION:
        return "Dashboard Ciclos pendiente"
    return "Revisar tipo de fuente"


def _normalizar_fuente(fuente):
    item = dict(fuente)
    item["estado"] = _estado_normalizado(item.get("estado"))
    item["tipo_dashboard"] = clasificar_fuente_para_dashboard(item)
    item["recomendacion_dashboard"] = _recomendacion_dashboard(item)
    return item


def listar_fuentes_disponibles(db_path=DATABASE_PATH):
    filas = [_fuente_manual()]
    fuentes = source_service.listar_fuentes_datos(
        db_path=db_path,
        solo_activas=False,
        incluir_eliminadas=False,
    )
    if not fuentes.empty:
        for _, fuente in fuentes.iterrows():
            item = fuente.to_dict()
            estado = _estado_normalizado(item.get("estado"))
            if not _activo(item.get("activo")):
                continue
            if estado not in ESTADOS_VISIBLES:
                continue
            filas.append(_normalizar_fuente(item))
    return pd.DataFrame(filas)


def obtener_fuente_seleccionable(id_fuente, db_path=DATABASE_PATH):
    if str(id_fuente) == ID_MANUAL_SQLITE:
        return _fuente_manual()
    try:
        id_entero = int(id_fuente)
    except (TypeError, ValueError):
        return None
    fuentes = listar_fuentes_disponibles(db_path=db_path)
    if fuentes.empty:
        return None
    coincidencias = fuentes[fuentes["id_fuente"].astype(str).eq(str(id_entero))]
    if coincidencias.empty:
        return None
    return coincidencias.iloc[0].to_dict()


def _resumen_manual_sqlite(db_path=DATABASE_PATH):
    registros = db.leer_registros(db_path=db_path)
    if registros.empty:
        fecha_min = fecha_max = None
        equipos = operadores = 0
    else:
        fechas = pd.to_datetime(registros.get("Fecha turno", pd.Series(dtype=object)), errors="coerce").dropna()
        fecha_min = fechas.min().date() if not fechas.empty else None
        fecha_max = fechas.max().date() if not fechas.empty else None
        equipo_col = "Equipo" if "Equipo" in registros.columns else "Número equipo"
        equipos = registros.get(equipo_col, pd.Series(dtype=str)).dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()
        operadores = registros.get("Operador", pd.Series(dtype=str)).dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()
    return {
        "id_fuente": ID_MANUAL_SQLITE,
        "tipo_dashboard": TIPO_MANUAL_SQLITE,
        "registros": int(len(registros)),
        "fecha_min": fecha_min,
        "fecha_max": fecha_max,
        "equipos": int(equipos),
        "operadores": int(operadores),
        "recomendacion_dashboard": "Dashboard principal",
    }


def _resumen_ciclos(id_fuente, db_path):
    datos = leer_ciclos_operacional(db_path=db_path, id_fuente=int(id_fuente), solo_activas=False)
    fechas = pd.to_datetime(datos.get("fecha_turno", pd.Series(dtype=object)), errors="coerce").dropna() if not datos.empty else pd.Series(dtype="datetime64[ns]")
    return {
        "id_fuente": int(id_fuente),
        "tipo_dashboard": TIPO_CICLOS_PERFORACION,
        "registros": int(len(datos)),
        "fecha_min": fechas.min().date() if not fechas.empty else None,
        "fecha_max": fechas.max().date() if not fechas.empty else None,
        "equipos": int(datos.get("numero_equipo", pd.Series(dtype=str)).dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()) if not datos.empty else 0,
        "operadores": int(datos.get("operador", pd.Series(dtype=str)).dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()) if not datos.empty else 0,
        "recomendacion_dashboard": "Dashboard Ciclos pendiente",
    }


def obtener_resumen_fuente(id_fuente, db_path=DATABASE_PATH):
    fuente = obtener_fuente_seleccionable(id_fuente, db_path=db_path)
    if not fuente:
        return {}
    clasificacion = clasificar_fuente_para_dashboard(fuente)
    if clasificacion == TIPO_MANUAL_SQLITE:
        return _resumen_manual_sqlite(db_path=db_path)
    if clasificacion == TIPO_REGISTRO_OPERACIONAL_EXCEL:
        resumen = operational_excel_query_service.calcular_resumen_operacional_excel(
            int(fuente["id_fuente"]),
            db_path=db_path,
        )
        resumen["tipo_dashboard"] = TIPO_REGISTRO_OPERACIONAL_EXCEL
        resumen["recomendacion_dashboard"] = _recomendacion_dashboard(fuente)
        return resumen
    if clasificacion == TIPO_CICLOS_PERFORACION:
        return _resumen_ciclos(fuente["id_fuente"], db_path)
    return {
        "id_fuente": fuente.get("id_fuente"),
        "tipo_dashboard": TIPO_DESCONOCIDO,
        "registros": int(fuente.get("total_registros") or 0),
        "fecha_min": fuente.get("fecha_min"),
        "fecha_max": fuente.get("fecha_max"),
        "equipos": 0,
        "operadores": 0,
        "recomendacion_dashboard": _recomendacion_dashboard(fuente),
    }
