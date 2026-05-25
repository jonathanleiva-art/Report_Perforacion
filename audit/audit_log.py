from datetime import datetime
import csv
import json
import logging
from pathlib import Path

from config import LOGS_DIR


LOGGER = logging.getLogger(__name__)

LOG_DIR = LOGS_DIR
AUDIT_LOG_PATH = LOG_DIR / "audit_log.csv"

AUDIT_COLUMNS = [
    "fecha_hora",
    "accion",
    "usuario",
    "equipo",
    "numero_equipo",
    "turno",
    "resultado",
    "detalle",
]


def registrar_evento(
    accion,
    *,
    usuario="",
    equipo="",
    numero_equipo="",
    turno="",
    resultado="",
    detalle="",
    log_path=AUDIT_LOG_PATH,
):
    fila = {
        "fecha_hora": datetime.now().isoformat(timespec="seconds"),
        "accion": texto(accion),
        "usuario": texto(usuario),
        "equipo": texto(equipo),
        "numero_equipo": texto(numero_equipo),
        "turno": texto(turno),
        "resultado": texto(resultado),
        "detalle": serializar_detalle(detalle),
    }
    escribir_fila_audit(fila, log_path=log_path)
    return fila


def registrar_creacion_reporte(registro, resultado="ok", detalle="Reporte guardado correctamente."):
    datos = datos_desde_registro(registro)
    return registrar_evento(
        "creacion_reporte",
        usuario=datos.get("operador", ""),
        equipo=datos.get("modelo_equipo", ""),
        numero_equipo=datos.get("numero_equipo", ""),
        turno=datos.get("turno", ""),
        resultado=resultado,
        detalle=detalle,
    )


def registrar_guardado_rechazado(
    *,
    usuario="",
    equipo="",
    numero_equipo="",
    turno="",
    detalle="",
):
    return registrar_evento(
        "intento_guardado_rechazado",
        usuario=usuario,
        equipo=equipo,
        numero_equipo=numero_equipo,
        turno=turno,
        resultado="rechazado",
        detalle=detalle,
    )


def registrar_error_validacion(
    *,
    usuario="",
    equipo="",
    numero_equipo="",
    turno="",
    detalle="",
):
    return registrar_evento(
        "error_validacion",
        usuario=usuario,
        equipo=equipo,
        numero_equipo=numero_equipo,
        turno=turno,
        resultado="error",
        detalle=detalle,
    )


def registrar_generacion_pdf(
    *,
    usuario="",
    equipo="",
    numero_equipo="",
    turno="",
    resultado="ok",
    detalle="",
):
    return registrar_evento(
        "generacion_pdf",
        usuario=usuario,
        equipo=equipo,
        numero_equipo=numero_equipo,
        turno=turno,
        resultado=resultado,
        detalle=detalle,
    )


def registrar_respaldo_sqlite(
    *,
    usuario="",
    resultado="ok",
    detalle="",
):
    return registrar_evento(
        "respaldo_sqlite",
        usuario=usuario,
        resultado=resultado,
        detalle=detalle,
    )


def escribir_fila_audit(fila, *, log_path=AUDIT_LOG_PATH):
    try:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        escribir_encabezado = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as archivo:
            writer = csv.DictWriter(archivo, fieldnames=AUDIT_COLUMNS)
            if escribir_encabezado:
                writer.writeheader()
            writer.writerow({columna: fila.get(columna, "") for columna in AUDIT_COLUMNS})
    except Exception:
        LOGGER.exception("No se pudo escribir el log de auditoria.")


def datos_desde_registro(registro):
    if registro is None:
        return {}

    if hasattr(registro, "empty") and not registro.empty:
        fila = registro.iloc[0].to_dict()
    elif isinstance(registro, dict):
        fila = registro
    else:
        return {}

    return {
        "operador": valor(fila, "Operador"),
        "modelo_equipo": valor(fila, "Modelo equipo", "Equipo"),
        "numero_equipo": valor(fila, "Número equipo", "Número equipo"),
        "turno": valor(fila, "Turno"),
    }


def valor(datos, *claves):
    for clave in claves:
        if clave in datos:
            return texto(datos.get(clave))
    return ""


def texto(valor):
    if valor is None:
        return ""
    return str(valor)


def serializar_detalle(detalle):
    if detalle is None:
        return ""
    if isinstance(detalle, (dict, list, tuple, set)):
        try:
            return json.dumps(detalle, ensure_ascii=False, default=str)
        except TypeError:
            return str(detalle)
    return str(detalle)
