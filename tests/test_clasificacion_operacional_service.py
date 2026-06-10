import db
from services import clasificacion_operacional_service


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
