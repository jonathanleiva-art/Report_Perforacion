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


# ── Fase 2: tests JOIN con clasificacion_operacional ─────────────────────────


def _obtener_id_ultimo_registro(db_path):
    with db.conectar_db(db_path) as conn:
        return conn.execute(
            f"SELECT id FROM {db.quote_identifier(db.TABLA_REGISTROS)} ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]


def test_join_clasif_operacional_tiene_precedencia_sobre_columna_plana(tmp_path):
    """El dato en clasificacion_operacional sobreescribe la columna plana cuando ambos existen."""
    db_path = tmp_path / "avance.db"
    _insertar_registro_real(db_path, malla="", tipo_sector="Precorte", numero_precorte="01")
    rid = _obtener_id_ultimo_registro(db_path)
    db.upsert_clasificacion_operacional(rid, tipo_sector="Buffer 1", db_path=db_path)

    with malla_service.conectar_db(db_path) as conn:
        registros = malla_avance_service.obtener_registros_por_plan(conn, "F1", "B1")

    assert registros.iloc[0]["tipo_sector"] == "Buffer 1"
    assert registros.iloc[0]["numero_precorte"] == ""


def test_join_fallback_a_columnas_planas_cuando_no_hay_fila_co(tmp_path):
    """Sin fila en clasificacion_operacional, COALESCE cae a la columna plana."""
    db_path = tmp_path / "avance.db"
    _insertar_registro_real(db_path, malla="", tipo_sector="Buffer 2")

    with malla_service.conectar_db(db_path) as conn:
        registros = malla_avance_service.obtener_registros_por_plan(conn, "F1", "B1")

    assert registros.iloc[0]["tipo_sector"] == "Buffer 2"


def test_paridad_avance_columnas_planas_vs_join_precorte(tmp_path):
    """El avance calculado es idéntico tanto si el dato viene de flat como del JOIN (Precorte)."""
    db_path = tmp_path / "avance.db"
    _, sector_id = _crear_plan_sector(db_path, tipo_sector="Precorte", numero_precorte="07", pozos=10, metros=100)
    _insertar_registro_real(db_path, malla="", tipo_sector="Precorte", numero_precorte="07", pozos=3, metros=30)
    _insertar_registro_real(db_path, malla="", tipo_sector="Precorte", numero_precorte="07", pozos=4, metros=40)

    # Avance usando SOLO columnas planas (sin filas en clasificacion_operacional)
    with malla_service.conectar_db(db_path) as conn:
        avance_flat = malla_avance_service.calcular_avance_sector(conn, sector_id)

    # Ahora upsert las mismas clasificaciones en clasificacion_operacional
    with db.conectar_db(db_path) as conn:
        ids = [f[0] for f in conn.execute(
            f"SELECT id FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchall()]
    for rid in ids:
        db.upsert_clasificacion_operacional(rid, tipo_sector="Precorte", numero_precorte="07", db_path=db_path)

    # Avance usando JOIN (datos desde clasificacion_operacional)
    with malla_service.conectar_db(db_path) as conn:
        avance_join = malla_avance_service.calcular_avance_sector(conn, sector_id)

    assert avance_flat["pozos_perforados"] == avance_join["pozos_perforados"]
    assert avance_flat["metros_perforados"] == avance_join["metros_perforados"]
    assert avance_flat["avance_metros_pct"] == avance_join["avance_metros_pct"]
    assert avance_flat["estado_avance"] == avance_join["estado_avance"]


def test_paridad_avance_todos_los_tipos_sector(tmp_path):
    """Parity test completo: flat vs JOIN produce avance idéntico para todos los tipos de sector."""
    db_path = tmp_path / "avance.db"

    plan = malla_service.registrar_plan_perforacion(
        {"nombre_plan": "Plan paridad", "fase": "F9", "banco": "B9"},
        db_path=db_path,
    )
    plan_id = plan["plan_id"]

    # Crear sectores de cada tipo
    def _agregar_sector(tipo, malla="", precorte="", identificador="", pozos=10, metros=100):
        return malla_service.registrar_sector_perforacion(
            {
                "plan_id": plan_id,
                "tipo_sector": tipo,
                "identificador_sector": identificador or tipo,
                "malla": malla,
                "numero_precorte": precorte,
                "pozos_planificados": pozos,
                "metros_planificados": metros,
            },
            db_path=db_path,
        )["sector_id"]

    sec_prod = _agregar_sector("Producción", malla="M-99")
    sec_prec = _agregar_sector("Precorte", precorte="09")
    sec_buf1 = _agregar_sector("Buffer 1")
    sec_buf2 = _agregar_sector("Buffer 2")

    # Insertar registros con clasificación sólo en columnas planas
    columnas = ["Fecha turno", "Turno", "Número equipo", "Operador", "Fase", "Banco", "Malla",
                "tipo_sector", "numero_precorte", "identificador_sector", "Pozos perforados turno", "Metros perforados"]
    db.crear_tablas(db_path, columnas=columnas)
    casos = [
        ("F9", "B9", "M-99", "Producción", "", "", 5, 50),
        ("F9", "B9", "",     "Precorte",   "09", "", 4, 40),
        ("F9", "B9", "",     "Buffer 1",   "", "", 3, 30),
        ("F9", "B9", "",     "Buffer 2",   "", "", 2, 20),
    ]
    ids = []
    with db.conectar_db(db_path) as conn:
        for fase, banco, malla, tipo, precorte, ident, pozos, metros in casos:
            cur = conn.execute(
                f"INSERT INTO {db.quote_identifier(db.TABLA_REGISTROS)}"
                f" ({', '.join(db.quote_identifier(c) for c in columnas)}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                ("2026-07-13", "Día", "4001", "Op", fase, banco, malla, tipo, precorte, ident, pozos, metros),
            )
            ids.append(int(cur.lastrowid))
        conn.commit()

    # Avance con datos SÓLO en columnas planas
    with malla_service.conectar_db(db_path) as conn:
        avance_flat = malla_avance_service.calcular_avance_plan(conn, plan_id)

    # Upsert mismas clasificaciones en clasificacion_operacional
    for (_, _, _, tipo, precorte, ident, _, _), rid in zip(casos, ids):
        db.upsert_clasificacion_operacional(rid, tipo_sector=tipo, numero_precorte=precorte,
                                            identificador_sector=ident, db_path=db_path)

    # Avance con datos desde JOIN
    with malla_service.conectar_db(db_path) as conn:
        avance_join = malla_avance_service.calcular_avance_plan(conn, plan_id)

    assert avance_flat["metros_perforados_total"] == avance_join["metros_perforados_total"]
    assert avance_flat["pozos_perforados_total"] == avance_join["pozos_perforados_total"]
    assert avance_flat["avance_metros_pct"] == avance_join["avance_metros_pct"]

    # Verificar cada sector individualmente
    sectores_flat = {s["tipo_sector"]: s for s in avance_flat["sectores"]}
    sectores_join = {s["tipo_sector"]: s for s in avance_join["sectores"]}
    for tipo in ("Producción", "Precorte", "Buffer 1", "Buffer 2"):
        f = sectores_flat[tipo]
        j = sectores_join[tipo]
        assert f["metros_perforados"] == j["metros_perforados"], f"Divergencia en {tipo}"
        assert f["pozos_perforados"] == j["pozos_perforados"], f"Divergencia pozos en {tipo}"
