import streamlit as st

from ui.components import metric_card

from ui.form_helpers import alerta_horas_detencion_cero, detenciones_seleccionadas_por_hora
from ui.formatting import dataframe_visible, texto_visible
from services import catalog_service
from utils import HORAS_TURNO, TIPOS_DETENCION, opciones_desde_historial, ruta_imagen_equipo


ESTATUS_EQUIPO = [
    "Equipo Operativo con marcación",
    "Equipo Operativo, sin marcación",
    "Equipo Operativo, sin patio de perforación",
    "Equipo en Mantención Programada",
    "Equipo en Avería",
]


def render_equipo_operador_fecha(k):
    col_equipo, col_operador, col_fecha = st.columns([1.2, 1.2, 1])
    equipos = catalog_service.equipos_por_modelo_activos()
    operadores = catalog_service.nombres_operadores_activos()
    codigos_operador = catalog_service.codigos_por_nombre_operador_activo()

    with col_equipo:
        modelo_equipo = st.selectbox("Modelo equipo", list(equipos.keys()), key=k("modelo_equipo"))
        numero_equipo = st.selectbox("Numero equipo", equipos.get(modelo_equipo, []), key=k(f"numero_{modelo_equipo}"))
        imagen = ruta_imagen_equipo(modelo_equipo, numero_equipo)
        if imagen:
            st.image(str(imagen), caption=f"{modelo_equipo} {numero_equipo}", width="stretch")
        else:
            st.caption(f"Sin foto disponible para {modelo_equipo} {numero_equipo}")

    with col_operador:
        operador = st.selectbox(
            "Operador",
            operadores,
            index=None,
            placeholder="Selecciona operador",
            key=k("operador"),
        )
        codigo_operador = codigos_operador.get(operador, "")
        st.text_input(
            "Código de operador",
            value=codigo_operador,
            disabled=True,
            key=f"{k('codigo_operador')}_{operador or 'sin_operador'}",
        )
        turno = st.selectbox("Turno", ["Día", "Noche"], format_func=texto_visible, key=k("turno"))

    with col_fecha:
        fecha_turno = st.date_input("Fecha turno", key=k("fecha_turno"))
        area_operacional = st.text_input("Área operacional", value="Proyecto DES", key=k("area_operacional"))

    return {
        "modelo_equipo": modelo_equipo,
        "numero_equipo": numero_equipo,
        "operador": operador,
        "codigo_operador": codigo_operador,
        "turno": turno,
        "fecha_turno": fecha_turno,
        "area_operacional": area_operacional,
    }


def render_ubicacion_condiciones(df_historial, k):
    st.subheader("Ubicación y condiciones")
    col_ubicacion_1, col_ubicacion_2, col_ubicacion_3 = st.columns(3)
    with col_ubicacion_1:
        banco = st.multiselect(
            "Banco",
            opciones_desde_historial(df_historial, "Banco"),
            accept_new_options=True,
            placeholder="Escribe y presiona Enter",
            key=k("banco"),
        )
        malla = st.multiselect(
            "Malla",
            opciones_desde_historial(
                df_historial,
                "Malla",
                [str(numero) for numero in range(107, 126)],
            ),
            accept_new_options=True,
            placeholder="Escribe y presiona Enter",
            key=k("malla"),
        )
    with col_ubicacion_2:
        fase = st.multiselect(
            "Fase",
            opciones_desde_historial(
                df_historial,
                "Fase",
                [str(numero) for numero in range(1, 9)],
            ),
            accept_new_options=True,
            placeholder="Escribe y presiona Enter",
            key=k("fase"),
        )
        tipo_perforacion = []
        identificador_sector = ""
    with col_ubicacion_3:
        condicion_terreno = st.multiselect(
            "Condición del terreno",
            opciones_desde_historial(
                df_historial,
                "Condición del terreno",
                [
                    "Blando",
                    "Medio",
                    "Duro",
                    "Estable",
                    "Fracturado",
                    "Inestable",
                    "Relleno",
                    "Con presencia de agua",
                ],
            ),
            accept_new_options=True,
            placeholder="Escribe y presiona Enter",
            key=k("condicion_terreno"),
        )
        numero_bit = st.text_input("Número serie Tricono/Bit", key=k("numero_bit"))

    # Widget multi-sector (ancho completo, debajo de las 3 columnas)
    from ui.sectores_widget import render_sectores, sectores_a_json
    st.divider()
    sectores = render_sectores(k)

    return {
        "banco": banco,
        "malla": malla,
        "fase": fase,
        "tipo_perforacion": tipo_perforacion,
        "sectores": sectores,
        "sectores_json": sectores_a_json(sectores),
        "identificador_sector": identificador_sector,
        "condicion_terreno": condicion_terreno,
        "numero_bit": numero_bit,
    }


def render_produccion_consumos(k):
    st.subheader("Producción y consumos")
    col_prod_1, col_prod_2, col_prod_3 = st.columns(3)
    with col_prod_1:
        metros = st.number_input("Metros perforados", min_value=0.0, step=1.0, key=k("metros"))
        pozos = st.number_input("Pozos perforados turno", min_value=0, step=1, key=k("pozos"))
    with col_prod_2:
        petroleo = st.number_input("Petróleo litros", min_value=0.0, step=1.0, key=k("petroleo"))
    with col_prod_3:
        horometro_inicial = st.number_input("Horómetro inicial", min_value=0.0, step=0.1, format="%.1f", key=k("horometro_inicial"))
        horometro_final = st.number_input("Horómetro final", min_value=0.0, step=0.1, format="%.1f", key=k("horometro_final"))
        diferencia_horometro = round(horometro_final - horometro_inicial, 2)
        st.metric("Horas de motor", f"{diferencia_horometro:.2f} h")

    tipo_detencion = st.multiselect(
        "Tipo detención",
        TIPOS_DETENCION,
        format_func=texto_visible,
        key=k("tipo_detencion"),
    )
    observaciones = st.text_area("Observaciones del equipo", key=k("observaciones"))
    estatus_equipo = st.selectbox(
        "Estatus del Equipo",
        ESTATUS_EQUIPO,
        key=k("estatus_equipo"),
    )

    return {
        "metros": metros,
        "pozos": pozos,
        "petroleo": petroleo,
        "horometro_inicial": horometro_inicial,
        "horometro_final": horometro_final,
        "diferencia_horometro": diferencia_horometro,
        "tipo_detencion": tipo_detencion,
        "causa_detencion": "",
        "observaciones": observaciones,
        "estatus_equipo": estatus_equipo,
    }


def render_horas_turno(tipo_detencion, k):
    st.subheader("Horas del turno")
    horas_efectivas = st.number_input(
        "Horas efectivas perforando",
        min_value=0.0,
        max_value=12.0,
        step=0.5,
        key=k("horas_efectivas"),
    )

    campos_detencion = [
        ("horas_averia", "Horas avería equipo"),
        ("horas_combustible", "Abastecimiento combustible"),
        ("horas_agua", "Abastecimiento agua"),
        ("horas_colacion", "Colación"),
        ("horas_traslado", "Traslado"),
        ("horas_standby", "Standby por falta de tajo/Patio"),
        ("horas_tronadura", "Tronadura"),
        ("horas_mantencion", "Mantención Programada"),
        ("horas_cambios_aceros", "Cambios de aceros"),
        ("horas_cambio_turno", "Cambio turno"),
        ("horas_falta_operador", "Falta operador"),
        ("horas_otros", "Otros"),
    ]
    campos_destacados = detenciones_seleccionadas_por_hora(tipo_detencion)
    valores_horas = {}

    def capturar_hora(campo, etiqueta):
        valor = st.number_input(etiqueta, min_value=0.0, max_value=12.0, step=0.5, key=k(campo))
        if campo in campos_destacados and valor == 0:
            alerta_horas_detencion_cero(etiqueta)
        return valor

    if campos_destacados:
        st.markdown("**Horas asociadas a detenciones seleccionadas**")
        columnas_destacadas = st.columns(min(3, max(1, len(campos_destacados))))
        for indice, (campo, etiqueta) in enumerate([item for item in campos_detencion if item[0] in campos_destacados]):
            with columnas_destacadas[indice % len(columnas_destacadas)]:
                valores_horas[campo] = capturar_hora(campo, etiqueta)

        campos_secundarios = [item for item in campos_detencion if item[0] not in campos_destacados]
        with st.expander("Otros campos no seleccionados", expanded=False):
            columnas_secundarias = st.columns(3)
            for indice, (campo, etiqueta) in enumerate(campos_secundarios):
                with columnas_secundarias[indice % len(columnas_secundarias)]:
                    valores_horas[campo] = capturar_hora(campo, etiqueta)
    else:
        col_horas_1, col_horas_2, col_horas_3 = st.columns(3)
        columnas_horas = [
            col_horas_1,
            col_horas_1,
            col_horas_1,
            col_horas_1,
            col_horas_2,
            col_horas_2,
            col_horas_2,
            col_horas_2,
            col_horas_3,
            col_horas_3,
            col_horas_3,
            col_horas_3,
        ]
        for columna, (campo, etiqueta) in zip(columnas_horas, campos_detencion):
            with columna:
                valores_horas[campo] = capturar_hora(campo, etiqueta)

    horas_averia = valores_horas.get("horas_averia", 0.0)
    horas_combustible = valores_horas.get("horas_combustible", 0.0)
    horas_agua = valores_horas.get("horas_agua", 0.0)
    horas_colacion = valores_horas.get("horas_colacion", 0.0)
    horas_traslado = valores_horas.get("horas_traslado", 0.0)
    horas_standby = valores_horas.get("horas_standby", 0.0)
    horas_tronadura = valores_horas.get("horas_tronadura", 0.0)
    horas_mantencion = valores_horas.get("horas_mantencion", 0.0)
    horas_cambios_aceros = valores_horas.get("horas_cambios_aceros", valores_horas.get("horas_cambio_aceros", 0.0))
    horas_cambio_turno = valores_horas.get("horas_cambio_turno", 0.0)
    horas_falta_operador = valores_horas.get("horas_falta_operador", 0.0)
    horas_otros = valores_horas.get("horas_otros", 0.0)

    horas_no_efectivas = round(
        horas_combustible
        + horas_agua
        + horas_colacion
        + horas_traslado
        + horas_standby
        + horas_tronadura
        + horas_mantencion
        + horas_cambios_aceros
        + horas_cambio_turno
        + horas_falta_operador
        + horas_otros,
        2,
    )
    total_horas = round(horas_efectivas + horas_averia + horas_no_efectivas, 2)

    st.info(
        f"Total turno: {total_horas:.2f} / {HORAS_TURNO} h | "
        f"Efectivas {horas_efectivas:.2f} h | "
        f"Avería {horas_averia:.2f} h | "
        f"No efectivas {horas_no_efectivas:.2f} h"
    )

    return {
        "horas_efectivas": horas_efectivas,
        "horas_averia": horas_averia,
        "horas_combustible": horas_combustible,
        "horas_agua": horas_agua,
        "horas_colacion": horas_colacion,
        "horas_traslado": horas_traslado,
        "horas_standby": horas_standby,
        "horas_tronadura": horas_tronadura,
        "horas_mantencion": horas_mantencion,
        "horas_cambios_aceros": horas_cambios_aceros,
        "horas_cambio_aceros": horas_cambios_aceros,
        "horas_cambio_turno": horas_cambio_turno,
        "horas_falta_operador": horas_falta_operador,
        "horas_otros": horas_otros,
        "horas_no_efectivas": horas_no_efectivas,
        "total_horas": total_horas,
    }


def render_kpi_turno(rendimiento_turno, utilizacion, disponibilidad):
    k1, k2, k3 = st.columns(3)
    with k1:
        metric_card("Rendimiento m/h", f"{rendimiento_turno:.2f}", "Productividad del turno", state="info", st_module=st)
    with k2:
        metric_card("Utilización", f"{utilizacion:.2f}%", "Uso operativo del equipo", state="ok", st_module=st)
    with k3:
        metric_card("Disponibilidad", f"{disponibilidad:.2f}%", "Condición disponible", state="warning", st_module=st)


def render_preview_duplicado(registro_existente_preview):
    st.warning("Advertencia antes de guardar: ya existe un reporte para este equipo, fecha, turno y operador.")
    columnas_existente = [
        columna
        for columna in ["Fecha turno", "Modelo equipo", "Número equipo", "Operador", "Turno", "Metros perforados", "Hora registro"]
        if columna in registro_existente_preview.columns
    ]
    if columnas_existente:
        st.dataframe(dataframe_visible(registro_existente_preview[columnas_existente]), width="stretch", hide_index=True)
    st.info("Si necesita corregir información, use edición de registro en vez de crear uno nuevo.")
