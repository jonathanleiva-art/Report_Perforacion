import db
from services import malla_avance_service, malla_service


def _crear_plan_sector(
    db_path,
    tipo_sector="Producción",
    malla="M-01",
    numero_precorte="",
    identificador_sector="",
    pozos=10,
    metros=100,
):
    plan = malla_service.registrar_plan_perforacion(
        {"nombre_plan": "Plan avance", "fase": "F1", "banco": "B1"},
        db_path=db_path,
    )
    sector = malla_service.registrar_sector_perforacion(
        {
            "plan_id": plan["plan_id"],
            "tipo_sector": tipo_sector,
            "identificador_sector": identificador_sector or f"{tipo_sector} {malla}",
            "malla": malla,
            "numero_precorte": numero_precorte or ("01" if tipo_sector == "Precorte" else ""),
            "pozos_planificados": pozos,
            "metros_planificados": metros,
        },
        db_path=db_path,
    )
    return plan["plan_id"], sector["sector_id"]


def _insertar_registro_real(
    db_path,
    fase="F1",
    banco="B1",
    malla="M-01",
    tipo_sector="",
    numero_precorte="",
    identificador_sector="",
    pozos=5,
    metros=50,
):
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
        "Pozos perforados turno",
        "Metros perforados",
    ]
    db.crear_tablas(db_path, columnas=columnas)
    with db.conectar_db(db_path) as connection:
        connection.execute(
            f"""
            INSERT INTO {db.quote_identifier(db.TABLA_REGISTROS)}
            ({", ".join(db.quote_identifier(col) for col in columnas)})
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-04",
                "Día",
                "4001",
                "Operador A",
                fase,
                banco,
                malla,
                tipo_sector,
                numero_precorte,
                identificador_sector,
                pozos,
                metros,
            ),
        )
        connection.commit()


def test_avance_plan_cero_sin_registros(tmp_path):
    db_path = tmp_path / "avance.db"
    plan_id, _ = _crear_plan_sector(db_path)

    with malla_service.conectar_db(db_path) as conn:
        avance = malla_avance_service.calcular_avance_plan(conn, plan_id)

    assert avance["pozos_perforados_total"] == 0
    assert avance["metros_perforados_total"] == 0
    assert avance["avance_pozos_pct"] == 0
    assert avance["avance_metros_pct"] == 0


def test_avance_sector_parcial(tmp_path):
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(db_path, pozos=10, metros=100)
    _insertar_registro_real(db_path, pozos=5, metros=40)

    with malla_service.conectar_db(db_path) as conn:
        avance = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert avance["pozos_perforados"] == 5
    assert avance["metros_perforados"] == 40
    assert avance["avance_pozos_pct"] == 50
    assert avance["avance_metros_pct"] == 40
    assert avance["estado_avance"] == "En avance"


def test_avance_sector_completo(tmp_path):
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(db_path, pozos=10, metros=100)
    _insertar_registro_real(db_path, pozos=10, metros=100)

    with malla_service.conectar_db(db_path) as conn:
        avance = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert avance["avance_pozos_pct"] == 100
    assert avance["avance_metros_pct"] == 100
    assert avance["estado_avance"] == "Completo"
    assert avance["semaforo"] == "Azul"


def test_avance_sector_sobreperforado(tmp_path):
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(db_path, pozos=10, metros=100)
    _insertar_registro_real(db_path, pozos=12, metros=120)

    with malla_service.conectar_db(db_path) as conn:
        avance = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert avance["avance_metros_pct"] == 120
    assert avance["estado_avance"] == "Sobreperforado"
    assert avance["semaforo"] == "Morado"


def test_sector_produccion_cruza_por_fase_banco_malla(tmp_path):
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(db_path, malla="M-01", pozos=20, metros=200)
    _insertar_registro_real(db_path, malla="M-01", pozos=5, metros=50)
    _insertar_registro_real(db_path, malla="M-02", pozos=8, metros=80)

    with malla_service.conectar_db(db_path) as conn:
        avance = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert avance["pozos_perforados"] == 5
    assert avance["metros_perforados"] == 50


def test_buffer_y_precorte_quedan_sin_avance_vinculado(tmp_path):
    db_path = tmp_path / "avance.db"
    _, buffer_id = _crear_plan_sector(db_path, tipo_sector="Buffer 1", malla="", pozos=5, metros=50)
    _, precorte_id = _crear_plan_sector(db_path, tipo_sector="Precorte", malla="", pozos=5, metros=50)
    _insertar_registro_real(db_path, malla="M-01", pozos=5, metros=50)

    with malla_service.conectar_db(db_path) as conn:
        buffer = malla_avance_service.calcular_avance_sector(conn, buffer_id)
        precorte = malla_avance_service.calcular_avance_sector(conn, precorte_id)

    assert buffer["pozos_perforados"] == 0
    assert buffer["estado_avance"] == "Pendiente de clasificación operacional"
    assert precorte["metros_perforados"] == 0
    assert precorte["estado_avance"] == "Pendiente de clasificación operacional"


def test_sector_precorte_cruza_por_numero_precorte(tmp_path):
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(db_path, tipo_sector="Precorte", malla="", numero_precorte="02", pozos=5, metros=50)
    _insertar_registro_real(db_path, malla="", tipo_sector="Precorte", numero_precorte="02", pozos=3, metros=30)
    _insertar_registro_real(db_path, malla="", tipo_sector="Precorte", numero_precorte="03", pozos=4, metros=40)

    with malla_service.conectar_db(db_path) as conn:
        avance = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert avance["pozos_perforados"] == 3
    assert avance["metros_perforados"] == 30


def test_buffer_1_cruza_por_tipo_sector(tmp_path):
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(db_path, tipo_sector="Buffer 1", malla="", pozos=5, metros=50)
    _insertar_registro_real(db_path, malla="", tipo_sector="Buffer 1", pozos=2, metros=20)
    _insertar_registro_real(db_path, malla="", tipo_sector="Buffer 2", pozos=3, metros=30)

    with malla_service.conectar_db(db_path) as conn:
        avance = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert avance["pozos_perforados"] == 2
    assert avance["metros_perforados"] == 20


def test_buffer_2_cruza_por_tipo_sector(tmp_path):
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(db_path, tipo_sector="Buffer 2", malla="", pozos=5, metros=50)
    _insertar_registro_real(db_path, malla="", tipo_sector="Buffer 1", pozos=2, metros=20)
    _insertar_registro_real(db_path, malla="", tipo_sector="Buffer 2", pozos=3, metros=30)

    with malla_service.conectar_db(db_path) as conn:
        avance = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert avance["pozos_perforados"] == 3
    assert avance["metros_perforados"] == 30


def test_borde_cruza_por_identificador_si_existe(tmp_path):
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(
        db_path,
        tipo_sector="Borde",
        malla="",
        identificador_sector="Borde 1",
        pozos=5,
        metros=50,
    )
    _insertar_registro_real(db_path, malla="", tipo_sector="Borde", identificador_sector="Borde 1", pozos=2, metros=20)
    _insertar_registro_real(db_path, malla="", tipo_sector="Borde", identificador_sector="Borde 2", pozos=3, metros=30)

    with malla_service.conectar_db(db_path) as conn:
        avance = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert avance["pozos_perforados"] == 2
    assert avance["metros_perforados"] == 20


def test_registro_antiguo_con_malla_se_interpreta_como_produccion(tmp_path):
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(db_path, tipo_sector="Producción", malla="M-01", pozos=5, metros=50)
    _insertar_registro_real(db_path, malla="M-01", tipo_sector="", pozos=2, metros=20)

    with malla_service.conectar_db(db_path) as conn:
        registros = malla_avance_service.obtener_registros_por_plan(conn, "F1", "B1")
        avance = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert registros.iloc[0]["tipo_sector"] == "Producción"
    assert avance["pozos_perforados"] == 2
    assert avance["metros_perforados"] == 20


def test_registro_sin_clasificacion_ni_malla_queda_sin_clasificar(tmp_path):
    db_path = tmp_path / "avance.db"
    _insertar_registro_real(db_path, malla="", tipo_sector="", pozos=2, metros=20)

    with malla_service.conectar_db(db_path) as conn:
        registros = malla_avance_service.obtener_registros_por_plan(conn, "F1", "B1")

    assert registros.iloc[0]["tipo_sector"] == "Sin clasificar"
