import pandas as pd

import db
from config import DATABASE_PATH
from metrics import calcular_kpis_consolidados_dataframe
from services import data_source_selector_service as selector_service
from services import operational_excel_query_service


SOPORTE_COMPLETO = "completo"
SOPORTE_PARCIAL = "parcial"
SOPORTE_NO_SOPORTADO = "no_soportado"

MENSAJE_CICLOS_PENDIENTE = "Dashboard de ciclos pendiente de integración"
MENSAJE_FUENTE_NO_SOPORTADA = "Fuente no soportada por adaptadores operacionales"

CLAVES_RESUMEN = [
    "id_fuente",
    "tipo_fuente",
    "registros",
    "metros_totales",
    "fecha_min",
    "fecha_max",
    "equipos",
    "operadores",
    "horas_efectivas",
    "disponibilidad_promedio",
    "utilizacion_promedio",
    "rendimiento_promedio",
    "mensaje",
]


def _respuesta_datos(id_fuente, tipo_fuente, soporte, registros=None, mensaje=""):
    return {
        "id_fuente": id_fuente,
        "tipo_fuente": tipo_fuente,
        "soporte": soporte,
        "registros": registros if registros is not None else pd.DataFrame(),
        "mensaje": mensaje,
    }


def _resumen_base(id_fuente, tipo_fuente, mensaje=""):
    return {
        "id_fuente": id_fuente,
        "tipo_fuente": tipo_fuente,
        "registros": 0,
        "metros_totales": 0.0,
        "fecha_min": None,
        "fecha_max": None,
        "equipos": 0,
        "operadores": 0,
        "horas_efectivas": 0.0,
        "disponibilidad_promedio": 0.0,
        "utilizacion_promedio": 0.0,
        "rendimiento_promedio": 0.0,
        "mensaje": mensaje,
    }


def _serie_texto_no_vacia(df, columna):
    if df is None or df.empty or columna not in df.columns:
        return pd.Series(dtype=str)
    serie = df[columna].dropna().astype(str).str.strip()
    return serie[serie.ne("")]


class ManualSqliteAdapter:
    tipo_fuente = selector_service.TIPO_MANUAL_SQLITE
    soporte = SOPORTE_COMPLETO

    def cargar_datos(self, id_fuente=None, db_path=DATABASE_PATH):
        registros = db.leer_registros(db_path=db_path)
        return _respuesta_datos(
            selector_service.ID_MANUAL_SQLITE,
            self.tipo_fuente,
            self.soporte,
            registros=registros,
            mensaje="Registros manuales SQLite cargados",
        )

    def resumen(self, id_fuente=None, db_path=DATABASE_PATH):
        datos = self.cargar_datos(id_fuente, db_path=db_path)["registros"]
        resumen = _resumen_base(selector_service.ID_MANUAL_SQLITE, self.tipo_fuente)
        if datos.empty:
            resumen["mensaje"] = "No hay registros manuales SQLite"
            return resumen

        fechas = pd.to_datetime(datos.get("Fecha turno", pd.Series(dtype=object)), errors="coerce").dropna()
        kpis = calcular_kpis_consolidados_dataframe(datos)
        equipo_col = "Equipo" if "Equipo" in datos.columns else "Número equipo"
        resumen.update({
            "registros": int(len(datos)),
            "metros_totales": round(float(kpis["metros"]), 2),
            "fecha_min": fechas.min().date() if not fechas.empty else None,
            "fecha_max": fechas.max().date() if not fechas.empty else None,
            "equipos": int(_serie_texto_no_vacia(datos, equipo_col).nunique()),
            "operadores": int(_serie_texto_no_vacia(datos, "Operador").nunique()),
            "horas_efectivas": round(float(kpis["horas_efectivas"]), 2),
            "disponibilidad_promedio": round(float(kpis["disponibilidad"]), 2),
            "utilizacion_promedio": round(float(kpis["utilizacion"]), 2),
            "rendimiento_promedio": round(float(kpis["rendimiento"]), 2),
            "mensaje": "Resumen manual SQLite calculado",
        })
        return resumen


class RegistroOperacionalExcelAdapter:
    tipo_fuente = selector_service.TIPO_REGISTRO_OPERACIONAL_EXCEL
    soporte = SOPORTE_COMPLETO

    def cargar_datos(self, id_fuente, db_path=DATABASE_PATH):
        registros = operational_excel_query_service.cargar_registros_operacionales_por_fuente(
            int(id_fuente),
            db_path=db_path,
        )
        return _respuesta_datos(
            int(id_fuente),
            self.tipo_fuente,
            self.soporte,
            registros=registros,
            mensaje="Registros operacionales Excel cargados",
        )

    def resumen(self, id_fuente, db_path=DATABASE_PATH):
        resumen_excel = operational_excel_query_service.calcular_resumen_operacional_excel(
            int(id_fuente),
            db_path=db_path,
        )
        resumen = _resumen_base(int(id_fuente), self.tipo_fuente)
        resumen.update({
            "registros": int(resumen_excel.get("registros") or 0),
            "metros_totales": float(resumen_excel.get("metros_totales") or 0),
            "fecha_min": resumen_excel.get("fecha_min"),
            "fecha_max": resumen_excel.get("fecha_max"),
            "equipos": int(resumen_excel.get("equipos") or 0),
            "operadores": int(resumen_excel.get("operadores") or 0),
            "horas_efectivas": float(resumen_excel.get("horas_efectivas") or 0),
            "disponibilidad_promedio": float(resumen_excel.get("disponibilidad_promedio") or 0),
            "utilizacion_promedio": float(resumen_excel.get("utilizacion_promedio") or 0),
            "rendimiento_promedio": float(resumen_excel.get("rendimiento_promedio_mh") or 0),
            "mensaje": "Resumen Excel operacional calculado",
        })
        return resumen


class CiclosPerforacionAdapter:
    tipo_fuente = selector_service.TIPO_CICLOS_PERFORACION
    soporte = SOPORTE_PARCIAL

    def cargar_datos(self, id_fuente, db_path=DATABASE_PATH):
        return _respuesta_datos(
            int(id_fuente),
            self.tipo_fuente,
            self.soporte,
            registros=pd.DataFrame(),
            mensaje=MENSAJE_CICLOS_PENDIENTE,
        )

    def resumen(self, id_fuente, db_path=DATABASE_PATH):
        return _resumen_base(
            int(id_fuente),
            self.tipo_fuente,
            mensaje=MENSAJE_CICLOS_PENDIENTE,
        )


class FuenteNoSoportadaAdapter:
    tipo_fuente = selector_service.TIPO_DESCONOCIDO
    soporte = SOPORTE_NO_SOPORTADO

    def cargar_datos(self, id_fuente=None, db_path=DATABASE_PATH):
        return _respuesta_datos(
            id_fuente,
            self.tipo_fuente,
            self.soporte,
            registros=pd.DataFrame(),
            mensaje=MENSAJE_FUENTE_NO_SOPORTADA,
        )

    def resumen(self, id_fuente=None, db_path=DATABASE_PATH):
        return _resumen_base(
            id_fuente,
            self.tipo_fuente,
            mensaje=MENSAJE_FUENTE_NO_SOPORTADA,
        )


def obtener_adaptador_fuente(tipo_fuente):
    tipo = str(tipo_fuente or "").strip()
    if tipo == selector_service.TIPO_MANUAL_SQLITE:
        return ManualSqliteAdapter()
    if tipo == selector_service.TIPO_REGISTRO_OPERACIONAL_EXCEL:
        return RegistroOperacionalExcelAdapter()
    if tipo == selector_service.TIPO_CICLOS_PERFORACION:
        return CiclosPerforacionAdapter()
    return FuenteNoSoportadaAdapter()


def _resolver_fuente(id_fuente, db_path=DATABASE_PATH):
    return selector_service.obtener_fuente_seleccionable(id_fuente, db_path=db_path)


def _resolver_tipo(id_fuente, db_path=DATABASE_PATH):
    fuente = _resolver_fuente(id_fuente, db_path=db_path)
    if not fuente:
        return selector_service.TIPO_DESCONOCIDO
    return selector_service.clasificar_fuente_para_dashboard(fuente)


def cargar_datos_fuente(id_fuente, db_path=DATABASE_PATH):
    tipo = _resolver_tipo(id_fuente, db_path=db_path)
    adaptador = obtener_adaptador_fuente(tipo)
    return adaptador.cargar_datos(id_fuente, db_path=db_path)


def calcular_resumen_fuente_normalizado(id_fuente, db_path=DATABASE_PATH):
    tipo = _resolver_tipo(id_fuente, db_path=db_path)
    adaptador = obtener_adaptador_fuente(tipo)
    resumen = adaptador.resumen(id_fuente, db_path=db_path)
    return {clave: resumen.get(clave) for clave in CLAVES_RESUMEN}


def validar_fuente_soportada(id_fuente, db_path=DATABASE_PATH):
    tipo = _resolver_tipo(id_fuente, db_path=db_path)
    adaptador = obtener_adaptador_fuente(tipo)
    fuente = _resolver_fuente(id_fuente, db_path=db_path)
    if not fuente:
        return {
            "id_fuente": id_fuente,
            "tipo_fuente": selector_service.TIPO_DESCONOCIDO,
            "soporte": SOPORTE_NO_SOPORTADO,
            "ok": False,
            "mensaje": "La fuente no existe o no es seleccionable",
        }
    return {
        "id_fuente": id_fuente,
        "tipo_fuente": tipo,
        "soporte": adaptador.soporte,
        "ok": adaptador.soporte == SOPORTE_COMPLETO,
        "mensaje": "" if adaptador.soporte == SOPORTE_COMPLETO else adaptador.cargar_datos(id_fuente, db_path=db_path)["mensaje"],
    }
