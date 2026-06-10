from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from services import operator_admin_service
from ui.formatting import dataframe_visible
from ui.page_header import render_page_header


def main():
    if not app.requerir_acceso(admin=True):
        return

    render_page_header(
        app.st,
        "Administración de Operadores",
        "Asignación de nombres a códigos detectados en Ciclos de Perforación Excel.",
    )

    if app.st.button("Sincronizar operadores de ciclos", key="sync_operadores_ciclos"):
        resultado = operator_admin_service.sincronizar_operadores_ciclos()
        app.st.success(
            "Sincronización completa: "
            f"{resultado.get('registros_actualizados', 0)} registros actualizados."
        )

    pendientes = operator_admin_service.listar_pendientes_ciclos()
    operadores = operator_admin_service.listar_operadores()

    app.st.subheader("Operadores registrados")
    app.st.dataframe(dataframe_visible(operadores), width="stretch", hide_index=True)

    app.st.subheader("Pendientes detectados en ciclos")
    if pendientes.empty:
        app.st.info("No hay operadores pendientes en ciclos_perforacion.")
    else:
        app.st.dataframe(dataframe_visible(pendientes), width="stretch", hide_index=True)

    app.st.subheader("Asignar nombre a código")
    opciones = pendientes["codigo_original"].tolist() if not pendientes.empty else []
    codigo = app.st.selectbox(
        "Código pendiente",
        opciones,
        index=None,
        placeholder="Selecciona un código pendiente",
        key="admin_operador_codigo_select",
    )
    codigo_manual = app.st.text_input(
        "O ingresar código manualmente",
        value="" if codigo else "",
        placeholder="Ejemplo: M-8086, 8086 o 008086",
        key="admin_operador_codigo_manual",
    )
    nombre = app.st.text_input(
        "Nombre operador",
        placeholder="Nombre y apellido",
        key="admin_operador_nombre",
    )

    codigo_final = codigo_manual.strip() or (codigo or "")
    if app.st.button("Guardar operador", type="primary", key="admin_operador_guardar"):
        try:
            resultado = operator_admin_service.actualizar_operador(codigo_final, nombre)
        except ValueError as exc:
            app.st.error(str(exc))
        else:
            app.st.success(
                f"Operador actualizado: {resultado['codigo_operador']} = {resultado['nombre_operador']}"
            )
            app.st.rerun()


main()
