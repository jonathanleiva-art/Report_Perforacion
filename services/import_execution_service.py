from datetime import datetime
from pathlib import Path
import json
import shutil

from config import DATA_DIR, DATABASE_PATH
from services import import_diagnostic_service, operational_excel_service, source_service


IMPORTS_DIR = DATA_DIR / "imports"

ESTADO_DIAGNOSTICADA = "diagnosticada"
ESTADO_IMPORTANDO = "importando"
ESTADO_IMPORTADA = "importada"
ESTADO_PENDIENTE_IMPORTADOR = "pendiente_importador"
ESTADO_ERROR_IMPORTACION = "error_importacion"

TIPOS_IMPORTABLES = {
    import_diagnostic_service.TIPO_CICLOS,
    import_diagnostic_service.TIPO_REGISTRO_OPERACIONAL,
}

TIPOS_REGISTRO_OPERACIONAL = {
    import_diagnostic_service.TIPO_REGISTRO_OPERACIONAL,
    operational_excel_service.TIPO_FUENTE,
}


def _resultado(
    *,
    ok,
    estado,
    mensaje,
    id_fuente=None,
    tipo_fuente=None,
    ruta_origen=None,
    ruta_imports=None,
    registros_importados=0,
):
    return {
        "ok": bool(ok),
        "id_fuente": id_fuente,
        "tipo_fuente": tipo_fuente,
        "estado": estado,
        "mensaje": mensaje,
        "ruta_origen": str(ruta_origen) if ruta_origen else None,
        "ruta_imports": str(ruta_imports) if ruta_imports else None,
        "registros_importados": int(registros_importados or 0),
    }


def _observacion_importacion(mensaje, ruta_imports=None):
    resumen = {
        "fase": "ejecucion_controlada_importacion",
        "mensaje": mensaje,
        "ruta_imports": str(ruta_imports) if ruta_imports else None,
        "fecha": datetime.now().isoformat(timespec="seconds"),
    }
    return "Ejecucion controlada de importacion: " + json.dumps(resumen, ensure_ascii=False)


def _resolver_ruta_archivo(fuente):
    archivo = str(fuente.get("archivo_origen") or "").strip()
    if not archivo:
        return Path("")

    ruta = Path(archivo)
    if ruta.exists():
        return ruta

    candidatos = [
        Path.cwd() / archivo,
        Path.cwd() / "temp_uploads" / Path(archivo).name,
        IMPORTS_DIR / Path(archivo).name,
    ]
    for candidato in candidatos:
        if candidato.exists():
            return candidato
    return ruta


def validar_fuente_importable(id_fuente, db_path=DATABASE_PATH):
    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    if not fuente:
        return _resultado(
            ok=False,
            id_fuente=id_fuente,
            estado=None,
            mensaje="La fuente no existe.",
        )

    estado = str(fuente.get("estado") or "").strip().lower()
    tipo_fuente = str(fuente.get("tipo_fuente") or "").strip()
    if estado != ESTADO_DIAGNOSTICADA:
        return _resultado(
            ok=False,
            id_fuente=id_fuente,
            tipo_fuente=tipo_fuente,
            estado=estado,
            mensaje="La fuente no esta en estado diagnosticada.",
        )

    if tipo_fuente == import_diagnostic_service.TIPO_DESCONOCIDO:
        return _resultado(
            ok=False,
            id_fuente=id_fuente,
            tipo_fuente=tipo_fuente,
            estado=estado,
            mensaje="No se puede importar una fuente de tipo desconocido.",
        )

    ruta_origen = _resolver_ruta_archivo(fuente)
    if not ruta_origen.exists() or not ruta_origen.is_file():
        return _resultado(
            ok=False,
            id_fuente=id_fuente,
            tipo_fuente=tipo_fuente,
            estado=estado,
            ruta_origen=ruta_origen,
            mensaje="El archivo origen de la fuente no existe.",
        )

    return _resultado(
        ok=True,
        id_fuente=id_fuente,
        tipo_fuente=tipo_fuente,
        estado=estado,
        ruta_origen=ruta_origen,
        mensaje="Fuente validada para importacion controlada.",
    )


def copiar_archivo_a_imports(ruta_origen, imports_dir=IMPORTS_DIR):
    origen = Path(ruta_origen)
    if not origen.exists() or not origen.is_file():
        raise FileNotFoundError(f"El archivo origen no existe: {origen}")

    destino_dir = Path(imports_dir)
    destino_dir.mkdir(parents=True, exist_ok=True)

    destino = destino_dir / origen.name
    contador = 1
    while destino.exists():
        destino = destino_dir / f"{origen.stem}_{contador}{origen.suffix}"
        contador += 1

    shutil.copy2(origen, destino)
    return destino


def importar_fuente_diagnosticada(id_fuente, db_path=DATABASE_PATH, imports_dir=IMPORTS_DIR):
    validacion = validar_fuente_importable(id_fuente, db_path=db_path)
    if not validacion["ok"]:
        if validacion.get("estado") == ESTADO_DIAGNOSTICADA:
            source_service.actualizar_estado_fuente(
                id_fuente,
                ESTADO_ERROR_IMPORTACION,
                db_path=db_path,
                observacion=_observacion_importacion(validacion["mensaje"]),
            )
            validacion["estado"] = ESTADO_ERROR_IMPORTACION
        return validacion

    tipo_fuente = validacion["tipo_fuente"]
    ruta_origen = Path(validacion["ruta_origen"])

    source_service.actualizar_estado_fuente(
        id_fuente,
        ESTADO_IMPORTANDO,
        db_path=db_path,
        observacion=_observacion_importacion("Inicio de importacion controlada."),
    )

    try:
        ruta_imports = copiar_archivo_a_imports(ruta_origen, imports_dir=imports_dir)
        if tipo_fuente in TIPOS_REGISTRO_OPERACIONAL:
            resumen = operational_excel_service.importar_registro_operacional_excel_desde_fuente(
                id_fuente,
                ruta_imports,
                db_path=db_path,
            )
            if resumen.get("errores"):
                mensaje = "; ".join(str(error) for error in resumen.get("errores", []))
                source_service.actualizar_estado_fuente(
                    id_fuente,
                    ESTADO_ERROR_IMPORTACION,
                    db_path=db_path,
                    observacion=_observacion_importacion(mensaje, ruta_imports),
                )
                return _resultado(
                    ok=False,
                    id_fuente=id_fuente,
                    tipo_fuente=tipo_fuente,
                    estado=ESTADO_ERROR_IMPORTACION,
                    mensaje=mensaje,
                    ruta_origen=ruta_origen,
                    ruta_imports=ruta_imports,
                    registros_importados=resumen.get("filas_insertadas", 0),
                )

            mensaje = (
                "Importacion operacional Excel completada. "
                f"Filas insertadas: {resumen.get('filas_insertadas', 0)}; "
                f"duplicados: {resumen.get('duplicados', 0)}."
            )
            source_service.actualizar_estado_fuente(
                id_fuente,
                ESTADO_IMPORTADA,
                db_path=db_path,
                observacion=_observacion_importacion(mensaje, ruta_imports),
            )
            return _resultado(
                ok=True,
                id_fuente=id_fuente,
                tipo_fuente=tipo_fuente,
                estado=ESTADO_IMPORTADA,
                mensaje=mensaje,
                ruta_origen=ruta_origen,
                ruta_imports=ruta_imports,
                registros_importados=resumen.get("filas_insertadas", 0),
            )

        if tipo_fuente in TIPOS_IMPORTABLES:
            mensaje = (
                "Archivo copiado a data/imports. El importador real queda pendiente "
                "hasta validar una integracion que respete el id_fuente diagnosticado."
            )
        else:
            mensaje = (
                "Archivo copiado a data/imports. No existe importador compatible "
                "para este tipo de fuente."
            )
        source_service.actualizar_estado_fuente(
            id_fuente,
            ESTADO_PENDIENTE_IMPORTADOR,
            db_path=db_path,
            observacion=_observacion_importacion(mensaje, ruta_imports),
        )
        return _resultado(
            ok=True,
            id_fuente=id_fuente,
            tipo_fuente=tipo_fuente,
            estado=ESTADO_PENDIENTE_IMPORTADOR,
            mensaje=mensaje,
            ruta_origen=ruta_origen,
            ruta_imports=ruta_imports,
            registros_importados=0,
        )
    except Exception as exc:
        mensaje = f"Error durante la ejecucion controlada de importacion: {exc}"
        source_service.actualizar_estado_fuente(
            id_fuente,
            ESTADO_ERROR_IMPORTACION,
            db_path=db_path,
            observacion=_observacion_importacion(mensaje),
        )
        return _resultado(
            ok=False,
            id_fuente=id_fuente,
            tipo_fuente=tipo_fuente,
            estado=ESTADO_ERROR_IMPORTACION,
            mensaje=mensaje,
            ruta_origen=ruta_origen,
            registros_importados=0,
        )


def obtener_resumen_importacion(id_fuente, db_path=DATABASE_PATH):
    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    if not fuente:
        return {
            "existe": False,
            "id_fuente": id_fuente,
            "mensaje": "La fuente no existe.",
        }
    return {
        "existe": True,
        "id_fuente": fuente.get("id_fuente"),
        "nombre_fuente": fuente.get("nombre_fuente"),
        "tipo_fuente": fuente.get("tipo_fuente"),
        "archivo_origen": fuente.get("archivo_origen"),
        "estado": fuente.get("estado"),
        "activo": fuente.get("activo"),
        "total_registros": fuente.get("total_registros"),
        "fecha_min": fuente.get("fecha_min"),
        "fecha_max": fuente.get("fecha_max"),
        "observacion": fuente.get("observacion"),
        "registros_importados": 0,
    }
