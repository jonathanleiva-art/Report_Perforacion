from pathlib import Path
import sys

import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
import db
from ml.features import FEATURE_COLUMNS, cargar_registros_sqlite, preparar_features
from ml.model_training import entrenar_modelos
from ml.predictor import generar_predicciones
from ui.formatting import dataframe_visible
from utils import EXCEL_PATH


def main():
    st.title("Machine Learning operacional")
    st.caption(
        f"Modelo de apoyo | SQLite: {db.DB_PATH} | Excel respaldo: {EXCEL_PATH}"
    )
    st.warning("Modelo de apoyo, no reemplaza criterio operacional")

    df = cargar_registros_sqlite()
    features = preparar_features(df)
    resultado = generar_predicciones(df)
    entrenamiento = entrenar_modelos(df)

    c1, c2, c3 = st.columns(3)
    c1.metric("Registros usados", f"{resultado['total_registros']:,}")
    c2.metric("Modo", resultado["modo"].capitalize())
    c3.metric("SQLite", "Conectada" if db.DB_PATH.exists() else "No disponible")

    st.subheader("Estado del modelo")
    st.info(resultado["estado_modelo"])
    if entrenamiento.trained:
        st.success(entrenamiento.status)
        st.json(entrenamiento.metrics or {})
    else:
        st.warning(entrenamiento.status)

    for advertencia in resultado["advertencias"]:
        st.caption(advertencia)

    st.subheader("Variables consideradas")
    st.dataframe(
        dataframe_visible(
            _variables_dataframe(resultado["variables"])
        ),
        width="stretch",
        hide_index=True,
    )

    st.subheader("Predicción por equipo")
    predicciones = resultado["predicciones"]
    if predicciones.empty:
        st.info("No hay registros suficientes para generar predicciones.")
    else:
        st.dataframe(dataframe_visible(predicciones), width="stretch", hide_index=True)

    st.subheader("Alertas predictivas")
    if predicciones.empty:
        st.info("Sin alertas predictivas por falta de datos.")
    else:
        baja_utilizacion = predicciones[predicciones["Riesgo baja utilización"].isin(["Alto", "Medio"])]
        bajo_rendimiento = predicciones[predicciones["Riesgo bajo rendimiento"].isin(["Alto", "Medio"])]

        if baja_utilizacion.empty:
            st.success("No se detecta riesgo relevante de baja utilización según reglas actuales.")
        else:
            st.warning("Equipos con alerta de baja utilización")
            st.dataframe(
                dataframe_visible(baja_utilizacion[["Equipo", "Riesgo baja utilización", "Recomendación operacional"]]),
                width="stretch",
                hide_index=True,
            )

        if bajo_rendimiento.empty:
            st.success("No se detecta riesgo relevante de bajo rendimiento según reglas actuales.")
        else:
            st.warning("Equipos con alerta de bajo rendimiento")
            st.dataframe(
                dataframe_visible(bajo_rendimiento[["Equipo", "Riesgo bajo rendimiento", "Recomendación operacional"]]),
                width="stretch",
                hide_index=True,
            )

    with st.expander("Muestra de datos usados por el modelo", expanded=False):
        st.dataframe(dataframe_visible(features.tail(25)), width="stretch", hide_index=True)


def _variables_dataframe(variables):
    import pandas as pd

    base = variables or FEATURE_COLUMNS
    return pd.DataFrame({"Variable": base})


main()
