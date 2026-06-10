from datetime import datetime
from pathlib import Path
import json
import re
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from services import import_diagnostic_service, import_execution_service, source_service
from ui.formatting import dataframe_visible, texto_visible
from ui.page_header import render_page_header


TEMP_UPLOADS_DIR = ROOT_DIR / "temp_uploads"
TIPOS_EXCEL = ["xlsx", "xls"]


def _nombre_archivo_seguro(nombre):
    base = Path(nombre or "archivo.xlsx").name
    base = re.sub(r"[^A-Za-z0-9_. -]+", "_", base).strip(" ._")
    return base or "archivo.xlsx"


def _ruta_temporal_upload(nombre_archivo, carpeta=TEMP_UPLOADS_DIR, ahora=None):
    carpeta = Path(carpeta)
    stamp = (ahora or datetime.now()).strftime("%Y%m%d_%H%M%S_%f")
    nombre_seguro = _nombre_archivo_seguro(nombre_archivo)
    return carpeta / f"{stamp}_{nombre_seguro}"


def guardar_upload_temporal(uploaded_file, carpeta=TEMP_UPLOADS_DIR, ahora=None):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = _ruta_temporal_upload(uploaded_file.name, carpeta=carpeta, ahora=ahora)
    contador = 1
    while destino.exists():
        destino = destino.with_name(f"{destino.stem}_{contador}{destino.suffix}")
        contador += 1
    destino.write_bytes(uploaded_file.getbuffer())
    return destino


def fuente_confirmable(diagnostico):
    if not diagnostico:
        return False
    if diagnostico.get("tipo_fuente_detectado") == import_diagnostic_service.TIPO_DESCONOCIDO:
        return False
    if diagnostico.get("estado_diagnostico") == "error":
        return False
    return not bool(diagnostico.get("columnas_faltantes"))


def nombre_fuente_sugerido(diagnostico):
    tipo = diagnostico.get("tipo_fuente_detectado") or "excel"
    archivo = Path(diagnostico.get("archivo") or "Excel").stem
    return f"{tipo} - {archivo}"


def construir_observacion_diagnostico(diagnostico):
    resumen = {
        "estado_diagnostico": diagnostico.get("estado_diagnostico"),
        "tipo_fuente_detectado": diagnostico.get("tipo_fuente_detectado"),
        "hoja_principal_detectada": diagnostico.get("hoja_principal_detectada"),
        "columnas_faltantes": diagnostico.get("columnas_faltantes", []),
        "columnas_reconocidas": diagnostico.get("columnas_reconocidas", []),
        "observaciones": diagnostico.get("observaciones", []),
    }
    return "Diagnóstico previo Excel: " + json.dumps(resumen, ensure_ascii=False)


def _tabla_lista(nombre, valores, limite=80):
    valores = valores or []
    if not valores:
        app.st.caption(f"{nombre}: sin datos detectados.")
        return
    mostrar = valores[:limite]
    df = pd.DataFrame({nombre: mostrar})
    app.st.dataframe(dataframe_visible(df), width="stretch", hide_index=True)
    if len(valores) > limite:
        app.st.caption(f"Mostrando {limite} de {len(valores)} valores.")


def _mostrar_semaforo(diagnostico):
    estado = diagnostico.get("estado_diagnostico")
    tipo = diagnostico.get("tipo_fuente_detectado")
    faltantes = diagnostico.get("columnas_faltantes") or []
    if estado == "ok" and tipo != import_diagnostic_service.TIPO_DESCONOCIDO and not faltantes:
        app.st.success("Diagnóstico OK. La fuente puede registrarse como diagnosticada.")
        return
    if tipo == import_diagnostic_service.TIPO_DESCONOCIDO:
        app.st.error("Tipo de fuente desconocido. No se puede confirmar esta fuente.")
        return
    if faltantes:
        app.st.warning("El archivo tiene columnas faltantes. Revisa el diagnóstico antes de continuar.")
        return
    app.st.warning("El diagnóstico requiere revisión antes de confirmar la fuente.")


def _mostrar_diagnostico(diagnostico):
    _mostrar_semaforo(diagnostico)
    col1, col2, col3, col4 = app.st.columns(4)
    col1.metric("Tipo fuente", texto_visible(diagnostico.get("tipo_fuente_detectado")))
    col2.metric("Filas leídas", f"{int(diagnostico.get('total_filas_leidas') or 0):,}")
    col3.metric("Columnas", f"{int(diagnostico.get('total_columnas') or 0):,}")
    col4.metric("Metros estimados", f"{float(diagnostico.get('metros_totales_estimados') or 0):,.2f}")

    app.st.caption(f"Archivo: {Path(diagnostico.get('archivo') or '').name}")
    app.st.caption(f"Hoja principal detectada: {diagnostico.get('hoja_principal_detectada') or 'No detectada'}")
    app.st.caption(f"Fecha mínima: {diagnostico.get('fecha_min') or 'No detectada'}")
    app.st.caption(f"Fecha máxima: {diagnostico.get('fecha_max') or 'No detectada'}")

    tabs = app.st.tabs([
        "Hojas",
        "Columnas",
        "Equipos",
        "Operadores",
        "Observaciones",
    ])
    with tabs[0]:
        _tabla_lista("Hojas detectadas", diagnostico.get("hojas_detectadas", []))
    with tabs[1]:
        col_a, col_b, col_c = app.st.columns(3)
        with col_a:
            app.st.caption("Columnas reconocidas")
            _tabla_lista("Reconocidas", diagnostico.get("columnas_reconocidas", []))
        with col_b:
            app.st.caption("Columnas no reconocidas")
            _tabla_lista("No reconocidas", diagnostico.get("columnas_no_reconocidas", []))
        with col_c:
            app.st.caption("Columnas faltantes")
            _tabla_lista("Faltantes", diagnostico.get("columnas_faltantes", []))
    with tabs[2]:
        _tabla_lista("Equipos detectados", diagnostico.get("equipos_detectados", []))
    with tabs[3]:
        _tabla_lista("Operadores detectados", diagnostico.get("operadores_detectados", []))
    with tabs[4]:
        _tabla_lista("Observaciones", diagnostico.get("observaciones", []))


def _confirmar_fuente(diagnostico, nombre_fuente):
    id_fuente = source_service.crear_fuente_datos(
        nombre_fuente=nombre_fuente.strip() or nombre_fuente_sugerido(diagnostico),
        tipo_fuente=diagnostico.get("tipo_fuente_detectado"),
        archivo_origen=str(Path(diagnostico.get("archivo") or "")),
        total_registros=int(diagnostico.get("total_filas_leidas") or 0),
        fecha_min=diagnostico.get("fecha_min"),
        fecha_max=diagnostico.get("fecha_max"),
        estado="diagnosticada",
        observacion=construir_observacion_diagnostico(diagnostico),
    )
    return id_fuente


def _fuentes_diagnosticadas():
    fuentes = source_service.listar_fuentes_datos(incluir_eliminadas=False)
    if fuentes.empty or "estado" not in fuentes.columns:
        return fuentes
    estados = fuentes["estado"].fillna("").astype(str).str.lower()
    return fuentes[estados.eq("diagnosticada")].copy()


def _mostrar_importacion_controlada():
    app.st.divider()
    app.st.subheader("Importacion controlada")
    app.st.caption("Solo se importan fuentes previamente diagnosticadas y confirmadas por el usuario.")

    fuentes = _fuentes_diagnosticadas()
    if fuentes.empty:
        app.st.info("No hay fuentes en estado diagnosticada pendientes de importacion.")
        return

    columnas = [
        columna
        for columna in [
            "id_fuente",
            "nombre_fuente",
            "tipo_fuente",
            "archivo_origen",
            "total_registros",
            "fecha_min",
            "fecha_max",
            "estado",
        ]
        if columna in fuentes.columns
    ]
    app.st.dataframe(dataframe_visible(fuentes[columnas]), width="stretch", hide_index=True)

    opciones = {
        f"{int(fila.id_fuente)} - {fila.nombre_fuente}": int(fila.id_fuente)
        for fila in fuentes.itertuples()
    }
    seleccion = app.st.selectbox(
        "Fuente diagnosticada",
        options=list(opciones.keys()),
        key="importar_excel_fuente_diagnosticada",
    )
    if app.st.button(
        "Importar fuente diagnosticada",
        type="primary",
        key="importar_excel_ejecutar_importacion",
    ):
        resultado = import_execution_service.importar_fuente_diagnosticada(opciones[seleccion])
        if resultado.get("ok") and resultado.get("estado") == import_execution_service.ESTADO_PENDIENTE_IMPORTADOR:
            app.st.warning(resultado.get("mensaje"))
        elif resultado.get("ok"):
            app.st.success(resultado.get("mensaje"))
        else:
            app.st.error(resultado.get("mensaje"))
        if resultado.get("ruta_imports"):
            app.st.caption(f"Archivo en imports: {resultado.get('ruta_imports')}")
        app.st.caption(f"Estado final: {resultado.get('estado')}")


def main():
    if not app.requerir_acceso(admin=True):
        return
    render_page_header(
        app.st,
        "Importar Excel",
        "Diagnóstico previo y registro de fuentes Excel sin importar registros operacionales.",
    )

    archivo = app.st.file_uploader(
        "Archivo Excel",
        type=TIPOS_EXCEL,
        key="importar_excel_diagnostico_upload",
    )
    if archivo is None:
        app.st.info("Sube un archivo Excel para ejecutar el diagnóstico previo.")
        _mostrar_importacion_controlada()
        return

    if app.st.button("Diagnosticar Excel", type="primary", key="importar_excel_diagnosticar"):
        try:
            ruta_temporal = guardar_upload_temporal(archivo)
            diagnostico = import_diagnostic_service.diagnosticar_excel(ruta_temporal)
        except Exception as exc:
            app.st.error(f"No fue posible diagnosticar el Excel: {exc}")
            return
        app.st.session_state["importar_excel_diagnostico"] = diagnostico

    diagnostico = app.st.session_state.get("importar_excel_diagnostico")
    if not diagnostico:
        return

    _mostrar_diagnostico(diagnostico)
    nombre_fuente = app.st.text_input(
        "Nombre fuente",
        value=nombre_fuente_sugerido(diagnostico),
        key="importar_excel_nombre_fuente",
    )
    deshabilitar = not fuente_confirmable(diagnostico)
    if app.st.button(
        "Confirmar fuente diagnosticada",
        type="primary",
        disabled=deshabilitar,
        key="importar_excel_confirmar_fuente",
    ):
        try:
            id_fuente = _confirmar_fuente(diagnostico, nombre_fuente)
        except Exception as exc:
            app.st.error(f"No fue posible registrar la fuente diagnosticada: {exc}")
            return
        app.st.success(f"Fuente diagnosticada registrada con id {id_fuente}. No se importaron registros operacionales.")

    _mostrar_importacion_controlada()


if __name__ == "__main__":
    main()
