from contextlib import closing
import shutil
import sqlite3

from config import DATABASE_PATH
from operators import actualizar_operador, upsert_operadores_conocidos
from services import ciclos_service


def test_leer_excel_ciclos_detecta_columnas_y_filas():
    df = ciclos_service.leer_excel_ciclos()

    assert len(df) == 6669
    assert ciclos_service.COLUMNA_IDENT in df.columns
    assert ciclos_service.COLUMNA_OPERADOR in df.columns
    assert ciclos_service.COLUMNA_PROFUNDIDAD in df.columns


def test_importar_excel_ciclos_crea_tabla_separada_y_evita_duplicados(tmp_path):
    db_path = tmp_path / "ciclos.db"
    with closing(sqlite3.connect(db_path)) as connection:
        upsert_operadores_conocidos(connection)

    primera = ciclos_service.importar_excel_ciclos(db_path=db_path)
    segunda = ciclos_service.importar_excel_ciclos(db_path=db_path)
    df = ciclos_service.leer_ciclos(db_path=db_path)

    assert primera["filas_excel"] == 6669
    assert primera["filas_importadas"] == 6669
    assert primera["duplicados_omitidos"] == 0
    assert segunda["filas_importadas"] == 0
    assert segunda["duplicados_omitidos"] == 6669
    assert len(df) == 6669
    assert df["ident_registro"].is_unique


def test_importar_excel_ciclos_registra_fuentes_y_filtra_por_id_fuente(tmp_path):
    db_path = tmp_path / "ciclos.db"
    excel_copia = tmp_path / f"Ciclos copia{ciclos_service.ruta_excel_ciclos().suffix}"
    shutil.copy2(ciclos_service.ruta_excel_ciclos(), excel_copia)
    with closing(sqlite3.connect(db_path)) as connection:
        upsert_operadores_conocidos(connection)

    primera = ciclos_service.importar_excel_ciclos(db_path=db_path)
    repetida = ciclos_service.importar_excel_ciclos(db_path=db_path)
    segunda = ciclos_service.importar_excel_ciclos(
        db_path=db_path,
        excel_path=excel_copia,
        nombre_fuente="Ciclos de Perforacion Excel - Archivo copia",
    )

    fuentes = ciclos_service.listar_fuentes_datos(db_path=db_path)
    df_primera = ciclos_service.leer_ciclos_operacional(db_path=db_path, id_fuente=primera["id_fuente"])
    df_segunda = ciclos_service.leer_ciclos_operacional(db_path=db_path, id_fuente=segunda["id_fuente"])
    df_todas = ciclos_service.leer_ciclos_operacional(db_path=db_path, solo_activas=True)

    assert len(fuentes) == 2
    assert primera["id_fuente"] == repetida["id_fuente"]
    assert repetida["filas_importadas"] == 0
    assert segunda["id_fuente"] != primera["id_fuente"]
    assert segunda["filas_importadas"] == primera["filas_excel"]
    assert len(df_primera) == primera["filas_excel"]
    assert len(df_segunda) == primera["filas_excel"]
    assert len(df_todas) == primera["filas_excel"] * 2
    assert set(df_todas["id_fuente"].astype(int)) == {primera["id_fuente"], segunda["id_fuente"]}


def test_ciclos_operacional_muestra_nombre_o_codigo_segun_tabla_operadores(tmp_path):
    db_path = tmp_path / "ciclos.db"
    with closing(sqlite3.connect(db_path)) as connection:
        upsert_operadores_conocidos(connection)
    ciclos_service.importar_excel_ciclos(db_path=db_path)

    df = ciclos_service.leer_ciclos_operacional(db_path=db_path)

    displays = set(df["operador_display"].dropna().astype(str))
    assert "Jhon Tapia" in displays
    assert "Diego Huerta" in displays
    assert "Diego Aracena" in displays
    assert "Martina Díaz" in displays
    assert "Tereza Inostroza" in displays
    assert "Javier Herrera" in displays
    assert "Jonathan Leiva" in displays


def test_ciclos_reales_muestran_operadores_identificados():
    ciclos_service.recalcular_operadores_ciclos(db_path=DATABASE_PATH)

    df = ciclos_service.leer_ciclos_operacional(db_path=DATABASE_PATH)
    displays = set(df["operador_display"].dropna().astype(str))
    operadores = set(df["Operador"].dropna().astype(str))

    esperados = {
        "Jhon Tapia",
        "Diego Huerta",
        "Diego Aracena",
        "Martina Díaz",
        "Tereza Inostroza",
        "Javier Herrera",
        "Jonathan Leiva",
        "Jhan Calderon",
        "Matías Toro",
        "Valeria Millan",
        "Nicolas Torres",
        "Mauricio Mora",
        "Carlos Rondon",
    }
    assert esperados.issubset(displays)
    assert esperados.issubset(operadores)


def test_opciones_filtros_ciclos_salen_de_columnas_normalizadas():
    ciclos_service.sincronizar_operadores_ciclos(db_path=DATABASE_PATH)

    opciones = ciclos_service.obtener_opciones_filtros_ciclos(db_path=DATABASE_PATH)

    assert "Jhon Tapia" in opciones["operadores"]
    assert "Diego Huerta" in opciones["operadores"]
    assert "Diego Aracena" in opciones["operadores"]
    assert "Martina Díaz" in opciones["operadores"]
    assert "Tereza Inostroza" in opciones["operadores"]
    assert "Javier Herrera" in opciones["operadores"]
    assert "Jonathan Leiva" in opciones["operadores"]
    assert "Jhan Calderon" in opciones["operadores"]
    assert "Matías Toro" in opciones["operadores"]
    assert "Valeria Millan" in opciones["operadores"]
    assert "Nicolas Torres" in opciones["operadores"]
    assert "Mauricio Mora" in opciones["operadores"]
    assert "Carlos Rondon" in opciones["operadores"]
    assert "PE9245" in opciones["equipos"]
    assert {"1", "2"}.issubset(set(opciones["turnos"]))
    assert opciones["fechas"]


def test_actualizar_operador_recalcula_ciclos_sin_reimportar(tmp_path):
    db_path = tmp_path / "ciclos.db"
    with closing(sqlite3.connect(db_path)) as connection:
        upsert_operadores_conocidos(connection)
    ciclos_service.importar_excel_ciclos(db_path=db_path)

    antes = ciclos_service.leer_ciclos_operacional(db_path=db_path)
    assert "Jonathan Leiva" in set(antes["operador_display"].dropna().astype(str))

    resultado = actualizar_operador("M-8086", "Operador Nuevo", db_path=db_path)
    despues = ciclos_service.leer_ciclos_operacional(db_path=db_path)

    assert resultado["codigo_operador"] == "008086"
    assert "Operador Nuevo" in set(despues["operador_display"].dropna().astype(str))
    assert "Jonathan Leiva" not in set(despues["operador_display"].dropna().astype(str))


