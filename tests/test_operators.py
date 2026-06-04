from contextlib import closing
import sqlite3

import pandas as pd

import db
from config import DATABASE_PATH
from operators import (
    agregar_columnas_operador_visual,
    obtener_nombre_operador,
    normalizar_codigo_operador,
    upsert_operadores_conocidos,
)


def test_normalizar_codigo_operador():
    assert normalizar_codigo_operador("M-7494") == "007494"
    assert normalizar_codigo_operador("7494") == "007494"
    assert normalizar_codigo_operador("007494") == "007494"
    assert normalizar_codigo_operador("M-203528") == "203528"


def test_obtener_nombre_operador_conocido(tmp_path):
    db_path = tmp_path / "operadores.db"
    with closing(sqlite3.connect(db_path)) as connection:
        upsert_operadores_conocidos(connection)

    assert obtener_nombre_operador("7494", db_path=db_path) == "Jhon Tapia"


def test_obtener_nombre_operador_desconocido_no_falla(tmp_path):
    db_path = tmp_path / "operadores.db"
    with closing(sqlite3.connect(db_path)) as connection:
        upsert_operadores_conocidos(connection)

    assert obtener_nombre_operador("codigo_desconocido", db_path=db_path) == ""


def test_agregar_columnas_operador_visual_usa_operador_si_codigo_oficial_viene_vacio(tmp_path):
    db_path = tmp_path / "operadores.db"
    with closing(sqlite3.connect(db_path)) as connection:
        upsert_operadores_conocidos(connection)

    df = pd.DataFrame(
        [
            {"Operador": "007494", "Código operador": ""},
            {"Operador": "M-2268", "Código operador": ""},
            {"Operador": "9234", "Código operador": None},
        ]
    )

    resultado = agregar_columnas_operador_visual(df, db_path=db_path)

    assert resultado["operador_codigo"].tolist() == ["007494", "002268", "009234"]
    assert resultado["operador_nombre"].tolist() == ["Jhon Tapia", "Diego Huerta", "Diego Aracena"]
    assert resultado["Operador"].tolist() == ["Jhon Tapia", "Diego Huerta", "Diego Aracena"]


def test_agregar_columnas_operador_visual_detecta_codigo_operador_con_encabezado_degradado(tmp_path):
    db_path = tmp_path / "operadores.db"
    with closing(sqlite3.connect(db_path)) as connection:
        upsert_operadores_conocidos(connection)

    df = pd.DataFrame([{"Operador": "", "C?digo operador": "M-203528"}])

    resultado = agregar_columnas_operador_visual(df, db_path=db_path)

    assert resultado.iloc[0]["operador_codigo"] == "203528"
    assert resultado.iloc[0]["operador_nombre"] == "Tereza Inostroza"


def test_agregar_columnas_operador_visual_prefiere_nombre_historico_si_codigo_no_esta_mapeado(tmp_path):
    db_path = tmp_path / "operadores.db"
    with closing(sqlite3.connect(db_path)) as connection:
        upsert_operadores_conocidos(connection)

    df = pd.DataFrame([{"Operador": "Carlos Rondon", "Código operador": "M-2036"}])

    resultado = agregar_columnas_operador_visual(df, db_path=db_path)

    assert resultado.iloc[0]["operador_codigo"] == "002036"
    assert resultado.iloc[0]["operador_nombre"] == "Carlos Rondon"
    assert resultado.iloc[0]["Operador"] == "Carlos Rondon"


def test_operadores_conocidos_resuelven_desde_base_oficial():
    assert DATABASE_PATH.exists()
    registros_reales = db.leer_registros(db_path=DATABASE_PATH)
    assert not registros_reales.empty
    assert "operador_codigo" in registros_reales.columns
    assert "operador_nombre" in registros_reales.columns

    casos = {
        "007494": "Jhon Tapia",
        "002268": "Diego Huerta",
        "009234": "Diego Aracena",
        "203666": "Martina Díaz",
        "203528": "Tereza Inostroza",
    }
    df = pd.DataFrame(
        [{"Operador": codigo, "Código operador": ""} for codigo in casos]
    )

    resultado = agregar_columnas_operador_visual(df, db_path=DATABASE_PATH)

    assert resultado["operador_nombre"].tolist() == list(casos.values())
    assert resultado["Operador"].tolist() == list(casos.values())
