"""
Tests que verifican que insertar_registro captura el lastrowid correcto
via cursor.execute() dentro de la misma conexión/transacción, eliminando
la condición de carrera que tenía el patrón anterior SELECT MAX(id).
"""
import threading

import pandas as pd
import pytest

import db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _crear_db(tmp_path):
    db_path = tmp_path / "test_lastrowid.db"
    db.crear_tablas(db_path=db_path, columnas=["Operador", "tipo_sector"])
    return db_path


def _insertar_via_db(db_path, operador, tipo_sector=""):
    """Llama a db.insertar_registro y devuelve (n_rows, lastrowid)."""
    df = pd.DataFrame([{
        "Fecha turno": "2026-07-12",
        "Turno": "Día",
        "Número equipo": "9001",
        "Operador": operador,
        "tipo_sector": tipo_sector,
    }])
    return db.insertar_registro(df, db_path=db_path)


# ---------------------------------------------------------------------------
# Tests unitarios: insertar_dataframe_reportes devuelve (n, lastrowid)
# ---------------------------------------------------------------------------

def test_insertar_dataframe_reportes_devuelve_tupla(tmp_path):
    db_path = _crear_db(tmp_path)
    df = pd.DataFrame([{"Fecha turno": "2026-07-12", "Turno": "Día", "Número equipo": "1"}])

    resultado = db.insertar_dataframe_reportes(df, db_path=db_path)

    assert isinstance(resultado, tuple), "debe devolver una tupla (n_rows, lastrowid)"
    n_rows, lastrowid = resultado
    assert n_rows == 1
    assert isinstance(lastrowid, int) and lastrowid > 0


def test_insertar_dataframe_reportes_vacio_devuelve_cero_none(tmp_path):
    db_path = _crear_db(tmp_path)
    n_rows, lastrowid = db.insertar_dataframe_reportes(pd.DataFrame(), db_path=db_path)

    assert n_rows == 0
    assert lastrowid is None


def test_insertar_registro_devuelve_lastrowid_del_registro_insertado(tmp_path):
    db_path = _crear_db(tmp_path)

    n1, id1 = _insertar_via_db(db_path, "Operador A")
    n2, id2 = _insertar_via_db(db_path, "Operador B")

    assert n1 == 1 and n2 == 1
    assert id2 == id1 + 1, "los IDs deben ser consecutivos"

    with db.conectar_db(db_path) as conn:
        fila1 = conn.execute(
            f"SELECT * FROM {db.quote_identifier(db.TABLA_REGISTROS)} WHERE id = ?", (id1,)
        ).fetchone()
        fila2 = conn.execute(
            f"SELECT * FROM {db.quote_identifier(db.TABLA_REGISTROS)} WHERE id = ?", (id2,)
        ).fetchone()

    assert fila1["Operador"] == "Operador A", f"id {id1} debe pertenecer a 'Operador A'"
    assert fila2["Operador"] == "Operador B", f"id {id2} debe pertenecer a 'Operador B'"


# ---------------------------------------------------------------------------
# Test de concurrencia: lastrowid correcto bajo inserciones simultáneas
# ---------------------------------------------------------------------------

def test_lastrowid_correcto_con_dos_inserciones_concurrentes(tmp_path):
    """
    Demuestra que lastrowid capturado dentro del execute() es siempre el id
    del registro propio, aunque otro hilo inserte entre medias.

    El patrón anterior (SELECT MAX(id) en conexión separada) es incorrecto:
    si el hilo B inserta DESPUÉS de que A cometa pero ANTES de que A consulte
    MAX(id), A leerá el id de B y escribirá la clasificación en la fila equivocada.
    """
    db_path = _crear_db(tmp_path)

    resultados = {}
    max_ids_post_insert = {}

    # Sincronización: A inserta → señala → B inserta → señala → A lee MAX(id)
    evento_a_insertado = threading.Event()
    evento_b_insertado = threading.Event()

    def hilo_a():
        n, lastrowid = _insertar_via_db(db_path, "Operador A", tipo_sector="Produccion")
        resultados["A"] = {"n": n, "lastrowid": lastrowid}
        evento_a_insertado.set()          # A ya insertó y capturó lastrowid
        evento_b_insertado.wait()         # espera que B también inserte
        # Simula lo que hacía el código anterior: SELECT MAX(id) post-insert
        with db.conectar_db(db_path) as conn:
            fila = conn.execute(
                f"SELECT MAX(id) AS m FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
            ).fetchone()
        max_ids_post_insert["A"] = fila["m"]

    def hilo_b():
        evento_a_insertado.wait()         # espera que A inserte primero
        n, lastrowid = _insertar_via_db(db_path, "Operador B", tipo_sector="Precorte")
        resultados["B"] = {"n": n, "lastrowid": lastrowid}
        evento_b_insertado.set()          # B insertó; A puede continuar

    t_a = threading.Thread(target=hilo_a, daemon=True)
    t_b = threading.Thread(target=hilo_b, daemon=True)
    t_a.start()
    t_b.start()
    t_a.join(timeout=10)
    t_b.join(timeout=10)

    assert not t_a.is_alive() and not t_b.is_alive(), "los hilos no terminaron a tiempo"

    id_a = resultados["A"]["lastrowid"]
    id_b = resultados["B"]["lastrowid"]

    # 1. Los IDs son distintos
    assert id_a != id_b, "cada hilo debe haber insertado en una fila distinta"

    # 2. lastrowid de A apunta a la fila de A
    with db.conectar_db(db_path) as conn:
        fila_a = conn.execute(
            f"SELECT \"Operador\" FROM {db.quote_identifier(db.TABLA_REGISTROS)} WHERE id = ?",
            (id_a,),
        ).fetchone()
        fila_b = conn.execute(
            f"SELECT \"Operador\" FROM {db.quote_identifier(db.TABLA_REGISTROS)} WHERE id = ?",
            (id_b,),
        ).fetchone()

    assert fila_a["Operador"] == "Operador A", (
        f"lastrowid={id_a} de A apunta a '{fila_a['Operador']}', esperaba 'Operador A'"
    )
    assert fila_b["Operador"] == "Operador B", (
        f"lastrowid={id_b} de B apunta a '{fila_b['Operador']}', esperaba 'Operador B'"
    )

    # 3. Demuestra el bug del patrón anterior: MAX(id) que A lee DESPUÉS de que
    #    B insertó devuelve el id de B, no el de A.
    max_visto_por_a = max_ids_post_insert["A"]
    assert max_visto_por_a == id_b, (
        f"MAX(id) visto por A tras la inserción de B es {max_visto_por_a}, "
        f"que es el id de B ({id_b}) — este era el bug: A hubiera escrito "
        f"la clasificacion en la fila de B en vez de la suya ({id_a})"
    )


# ---------------------------------------------------------------------------
# Test de integración: clasificacion_operacional apunta a la fila correcta
# ---------------------------------------------------------------------------

def test_lastrowid_es_la_fk_correcta_en_clasificacion_operacional(tmp_path):
    """
    Inserta dos registros consecutivos con tipo_sector distinto y verifica
    que clasificacion_operacional tiene FK → registro correcto para cada uno.
    """
    db_path = _crear_db(tmp_path)

    _, id_prod = _insertar_via_db(db_path, "Operador A", tipo_sector="Produccion")
    _, id_prec = _insertar_via_db(db_path, "Operador B", tipo_sector="Precorte")

    db.upsert_clasificacion_operacional(id_prod, tipo_sector="Produccion", db_path=db_path)
    db.upsert_clasificacion_operacional(id_prec, tipo_sector="Precorte",
                                        numero_precorte="PC-01", db_path=db_path)

    with db.conectar_db(db_path) as conn:
        co_prod = conn.execute(
            "SELECT co.tipo_sector, rp.\"Operador\" "
            "FROM clasificacion_operacional co "
            f"JOIN {db.quote_identifier(db.TABLA_REGISTROS)} rp ON rp.id = co.registro_id "
            "WHERE co.registro_id = ?",
            (id_prod,),
        ).fetchone()
        co_prec = conn.execute(
            "SELECT co.tipo_sector, co.numero_precorte, rp.\"Operador\" "
            "FROM clasificacion_operacional co "
            f"JOIN {db.quote_identifier(db.TABLA_REGISTROS)} rp ON rp.id = co.registro_id "
            "WHERE co.registro_id = ?",
            (id_prec,),
        ).fetchone()

    assert co_prod["tipo_sector"] == "Produccion"
    assert co_prod["Operador"] == "Operador A"
    assert co_prec["tipo_sector"] == "Precorte"
    assert co_prec["numero_precorte"] == "PC-01"
    assert co_prec["Operador"] == "Operador B"
