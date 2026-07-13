import db
from services import clasificacion_operacional_service
from db import upsert_clasificacion_operacional


def _insertar_registro(db_path, malla="", tipo_sector="", numero_precorte="", identificador_sector=""):
    columnas = [
        "Fecha turno",
        "Turno",
        "Número equipo",
        "Operador",
        "Fase",
        "Banco",
        "Malla",
        "tipo_sector",
        "numero_precorte",
        "identificador_sector",
    ]
    db.crear_tablas(db_path=db_path, columnas=columnas)
    with db.conectar_db(db_path) as connection:
        cursor = connection.execute(
            f"""
            INSERT INTO {db.quote_identifier(db.TABLA_REGISTROS)}
            ({", ".join(db.quote_identifier(columna) for columna in columnas)})
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-04",
                "Día",
                "4001",
                "Operador A",
                "F1",
                "B1",
                malla,
                tipo_sector,
                numero_precorte,
                identificador_sector,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def test_listar_registros_clasificacion_infiere_produccion_y_sin_clasificar(tmp_path):
    db_path = tmp_path / "clasificacion.db"
    _insertar_registro(db_path, malla="M-01")
    _insertar_registro(db_path, malla="")

    registros = clasificacion_operacional_service.listar_registros_clasificacion(db_path=db_path, limit=0)
    sin_clasificar = clasificacion_operacional_service.listar_registros_clasificacion(
        db_path=db_path,
        solo_sin_clasificar=True,
        limit=0,
    )

    assert set(registros["clasificacion_operacional"]) == {"Producción", "Sin clasificar"}
    assert len(sin_clasificar) == 1
    assert sin_clasificar.iloc[0]["clasificacion_operacional"] == "Sin clasificar"


def test_actualizar_clasificacion_registro_audita_cambios(tmp_path):
    db_path = tmp_path / "clasificacion.db"
    registro_id = _insertar_registro(db_path, malla="", tipo_sector="")

    resultado = clasificacion_operacional_service.actualizar_clasificacion_registro(
        registro_id,
        "Precorte",
        numero_precorte="02",
        identificador_sector="Precorte 02",
        motivo="Clasificación operacional FASE 4",
        usuario="tester",
        db_path=db_path,
    )
    auditoria = db.leer_auditoria_ediciones(registro_id, db_path=db_path)
    registros = clasificacion_operacional_service.listar_registros_clasificacion(db_path=db_path, limit=0)

    assert resultado["ok"] is True
    assert set(resultado["campos"]) == {"tipo_sector", "numero_precorte", "identificador_sector"}
    assert registros.iloc[0]["tipo_sector"] == "Precorte"
    assert registros.iloc[0]["numero_precorte"] == "02"
    assert len(auditoria) == 3


def test_actualizar_clasificacion_precorte_exige_numero(tmp_path):
    db_path = tmp_path / "clasificacion.db"
    registro_id = _insertar_registro(db_path, malla="")

    resultado = clasificacion_operacional_service.actualizar_clasificacion_registro(
        registro_id,
        "Precorte",
        numero_precorte="",
        motivo="Corrección incompleta",
        db_path=db_path,
    )

    assert resultado["ok"] is False
    assert "número de precorte" in resultado["mensaje"]


# ── Fase 2: tests JOIN listar_registros_clasificacion ────────────────────────


def test_listar_registros_join_co_tiene_precedencia(tmp_path):
    """listar_registros_clasificacion devuelve tipo_sector de clasificacion_operacional, no del flat."""
    db_path = tmp_path / "clasif_join.db"
    registro_id = _insertar_registro(db_path, malla="", tipo_sector="Precorte", numero_precorte="03")
    # Upsert a diferente clasificación en la tabla canónica
    upsert_clasificacion_operacional(registro_id, tipo_sector="Buffer 2", db_path=db_path)

    registros = clasificacion_operacional_service.listar_registros_clasificacion(db_path=db_path, limit=0)

    assert registros.iloc[0]["tipo_sector"] == "Buffer 2"
    assert registros.iloc[0]["clasificacion_operacional"] == "Buffer 2"


def test_listar_registros_fallback_a_flat_sin_fila_co(tmp_path):
    """Sin fila en clasificacion_operacional, listar devuelve la columna plana."""
    db_path = tmp_path / "clasif_flat.db"
    _insertar_registro(db_path, malla="", tipo_sector="Buffer 1")

    registros = clasificacion_operacional_service.listar_registros_clasificacion(db_path=db_path, limit=0)

    assert registros.iloc[0]["tipo_sector"] == "Buffer 1"


def test_listar_registros_paridad_flat_vs_join(tmp_path):
    """La clasificacion_operacional inferida es idéntica independientemente de la fuente del dato."""
    db_path = tmp_path / "clasif_paridad.db"
    rid_prod = _insertar_registro(db_path, malla="M-01")
    rid_prec = _insertar_registro(db_path, malla="", tipo_sector="Precorte", numero_precorte="04")
    rid_sin = _insertar_registro(db_path, malla="")

    # Leer con sólo columnas planas
    registros_flat = clasificacion_operacional_service.listar_registros_clasificacion(db_path=db_path, limit=0)
    clasif_flat = dict(zip(registros_flat["id"], registros_flat["clasificacion_operacional"]))

    # Poblar clasificacion_operacional con los mismos datos
    upsert_clasificacion_operacional(rid_prod, tipo_sector="", db_path=db_path)
    upsert_clasificacion_operacional(rid_prec, tipo_sector="Precorte", numero_precorte="04", db_path=db_path)
    upsert_clasificacion_operacional(rid_sin, tipo_sector="", db_path=db_path)

    # Leer ahora usando JOIN
    registros_join = clasificacion_operacional_service.listar_registros_clasificacion(db_path=db_path, limit=0)
    clasif_join = dict(zip(registros_join["id"], registros_join["clasificacion_operacional"]))

    assert clasif_flat == clasif_join


# ── Fase 2: tests obtener_registro_por_id con overlay ────────────────────────


def test_obtener_registro_por_id_overlay_co(tmp_path):
    """obtener_registro_por_id devuelve tipo_sector de clasificacion_operacional cuando existe."""
    db_path = tmp_path / "reg_overlay.db"
    registro_id = _insertar_registro(db_path, malla="", tipo_sector="Precorte", numero_precorte="05")
    upsert_clasificacion_operacional(registro_id, tipo_sector="Buffer 1", db_path=db_path)

    registro = db.obtener_registro_por_id(registro_id, db_path=db_path)

    assert registro.get("tipo_sector") == "Buffer 1"


def test_obtener_registro_por_id_fallback_flat_sin_co(tmp_path):
    """Sin fila CO, obtener_registro_por_id devuelve tipo_sector de la columna plana."""
    db_path = tmp_path / "reg_flat.db"
    registro_id = _insertar_registro(db_path, malla="", tipo_sector="Precorte", numero_precorte="06")

    registro = db.obtener_registro_por_id(registro_id, db_path=db_path)

    assert registro.get("tipo_sector") == "Precorte"
