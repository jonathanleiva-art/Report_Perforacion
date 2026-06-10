import app_perforacion as app
from services import catalog_service
from ui.formatting import dataframe_visible


app.configurar_pagina_principal()
if not app.requerir_acceso(admin=True):
    app.st.stop()

app.render_page_header("Administracion de catalogos", "Equipos y operadores activos")


def _mostrar_error(exc):
    app.st.error(str(exc))


tab_equipos, tab_operadores = app.st.tabs(["Equipos", "Operadores"])

with tab_equipos:
    equipos = catalog_service.listar_equipos_activos()
    app.st.dataframe(dataframe_visible(equipos), width="stretch", hide_index=True)

    with app.st.form("crear_equipo_catalogo"):
        app.st.subheader("Agregar equipo")
        codigo = app.st.text_input("Codigo equipo")
        nombre = app.st.text_input("Nombre equipo")
        modelo = app.st.text_input("Modelo")
        tipo = app.st.text_input("Tipo")
        estado = app.st.text_input("Estado", value="operativo")
        crear = app.st.form_submit_button("Agregar equipo", type="primary")
    if crear:
        try:
            catalog_service.crear_equipo(codigo, nombre, modelo=modelo, tipo=tipo, estado=estado)
            app.st.success("Equipo agregado.")
            app.st.rerun()
        except ValueError as exc:
            _mostrar_error(exc)

    codigos_equipos = equipos["codigo_equipo"].dropna().astype(str).tolist() if not equipos.empty else []
    if codigos_equipos:
        app.st.divider()
        seleccion = app.st.selectbox("Equipo a desactivar", codigos_equipos, key="catalogo_equipo_desactivar")
        if app.st.button("Desactivar equipo"):
            catalog_service.desactivar_equipo(seleccion)
            app.st.success("Equipo desactivado.")
            app.st.rerun()

with tab_operadores:
    operadores = catalog_service.listar_operadores_activos()
    app.st.dataframe(dataframe_visible(operadores), width="stretch", hide_index=True)

    with app.st.form("crear_operador_catalogo"):
        app.st.subheader("Agregar operador")
        codigo = app.st.text_input("Codigo operador")
        nombre = app.st.text_input("Nombre operador")
        empresa = app.st.text_input("Empresa")
        cargo = app.st.text_input("Cargo")
        crear = app.st.form_submit_button("Agregar operador", type="primary")
    if crear:
        try:
            catalog_service.crear_operador(codigo, nombre, empresa=empresa, cargo=cargo)
            app.st.success("Operador agregado.")
            app.st.rerun()
        except ValueError as exc:
            _mostrar_error(exc)

    codigos_operadores = operadores["codigo_operador"].dropna().astype(str).tolist() if not operadores.empty else []
    if codigos_operadores:
        app.st.divider()
        seleccion = app.st.selectbox("Operador a desactivar", codigos_operadores, key="catalogo_operador_desactivar")
        if app.st.button("Desactivar operador"):
            catalog_service.desactivar_operador(seleccion)
            app.st.success("Operador desactivado.")
            app.st.rerun()
