from contextlib import closing
import sqlite3

from services import operational_excel_query_service as query_service
from services import operational_excel_service, source_service
from services.ciclos_service import quote_identifier


def _crear_fuente(db_path, nombre, tipo="excel_registro_operacional", estado="importada"):
    return source_service.crear_fuente_datos(
        nombre_fuente=nombre,
        tipo_fuente=tipo,
        archivo_origen=f"{nombre}.xlsx",
        total_registros=0,
        fecha_min="2026-05-01",
        fecha_max="2026-05-02",
        estado=estado,
        db_path=db_path,
    )


def _insertar_registro(
    db_path,
    *,
    id_fuente,
    fecha_turno,
    equipo,
    operador,
    metros,
    horas_efectivas,
    horas_averia=0,
    horas_mp=0,
    horas_totales=12,
    turno="Dia",
):
    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        source_service.asegurar_tabla_fuentes_datos(connection)
        operational_excel_service._crear_tablas(connection)
        connection.execute(
            f"""
            INSERT INTO {quote_identifier(operational_excel_service.TABLA_REGISTROS_EXCEL)}
            (id_fuente, fecha_turno, anio, mes, dia, turno, numero_equipo, modelo, operador,
             total_metros, rendimiento_mh, horas_efectivas, horas_averia, horas_mp, horas_totales)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id_fuente,
                fecha_turno,
                int(fecha_turno[:4]),
                int(fecha_turno[5:7]),
                int(fecha_turno[8:10]),
                turno,
                equipo,
                "D75KS",
                operador,
                metros,
                metros / horas_efectivas if horas_efectivas else None,
                horas_efectivas,
                horas_averia,
                horas_mp,
                horas_totales,
            ),
        )
        connection.commit()


def test_listar_fuentes_operacionales_importadas_filtra_tipo_y_estado(tmp_path):
    db_path = tmp_path / "reportes.db"
    id_importada = _crear_fuente(db_path, "Operacional importada")
    _crear_fuente(db_path, "Operacional diagnosticada", estado="diagnosticada")
    _crear_fuente(db_path, "Ciclos importada", tipo="excel_ciclos")

    fuentes = query_service.listar_fuentes_operacionales_importadas(db_path=db_path)

    assert list(fuentes["id_fuente"].astype(int)) == [id_importada]
    assert set(fuentes["tipo_fuente"]) == {"excel_registro_operacional"}
    assert set(fuentes["estado"]) == {"importada"}


def test_cargar_registros_por_fuente_no_mezcla_fuentes(tmp_path):
    db_path = tmp_path / "reportes.db"
    fuente_1 = _crear_fuente(db_path, "Fuente 1")
    fuente_2 = _crear_fuente(db_path, "Fuente 2")
    _insertar_registro(db_path, id_fuente=fuente_1, fecha_turno="2026-05-01", equipo="4001", operador="A", metros=100, horas_efectivas=4)
    _insertar_registro(db_path, id_fuente=fuente_2, fecha_turno="2026-05-01", equipo="4002", operador="B", metros=200, horas_efectivas=5)

    registros = query_service.cargar_registros_operacionales_por_fuente(fuente_1, db_path=db_path)

    assert len(registros) == 1
    assert set(registros["equipo"]) == {"4001"}
    assert set(registros["operador"]) == {"A"}
    assert float(registros["metros"].sum()) == 100.0


def test_calcular_resumen_operacional_excel(tmp_path):
    db_path = tmp_path / "reportes.db"
    fuente = _crear_fuente(db_path, "Fuente resumen")
    _insertar_registro(db_path, id_fuente=fuente, fecha_turno="2026-05-01", equipo="4001", operador="A", metros=120, horas_efectivas=4, horas_averia=1)
    _insertar_registro(db_path, id_fuente=fuente, fecha_turno="2026-05-02", equipo="4002", operador="B", metros=180, horas_efectivas=6, horas_mp=2)

    resumen = query_service.calcular_resumen_operacional_excel(fuente, db_path=db_path)

    assert resumen["registros"] == 2
    assert resumen["metros_totales"] == 300.0
    assert resumen["fecha_min"].isoformat() == "2026-05-01"
    assert resumen["fecha_max"].isoformat() == "2026-05-02"
    assert resumen["equipos"] == 2
    assert resumen["operadores"] == 2
    assert resumen["horas_efectivas"] == 10
    assert resumen["horas_averia"] == 1
    assert resumen["horas_mp"] == 2
    assert resumen["rendimiento_promedio_mh"] == 30.0


def test_obtener_ranking_equipos_excel(tmp_path):
    db_path = tmp_path / "reportes.db"
    fuente = _crear_fuente(db_path, "Fuente equipos")
    _insertar_registro(db_path, id_fuente=fuente, fecha_turno="2026-05-01", equipo="4001", operador="A", metros=100, horas_efectivas=4)
    _insertar_registro(db_path, id_fuente=fuente, fecha_turno="2026-05-02", equipo="4001", operador="B", metros=80, horas_efectivas=2)
    _insertar_registro(db_path, id_fuente=fuente, fecha_turno="2026-05-01", equipo="4002", operador="A", metros=50, horas_efectivas=2)

    ranking = query_service.obtener_ranking_equipos_excel(fuente, db_path=db_path)

    assert list(ranking["equipo"]) == ["4001", "4002"]
    assert float(ranking.loc[0, "metros_totales"]) == 180.0
    assert int(ranking.loc[0, "registros"]) == 2


def test_obtener_ranking_operadores_excel(tmp_path):
    db_path = tmp_path / "reportes.db"
    fuente = _crear_fuente(db_path, "Fuente operadores")
    _insertar_registro(db_path, id_fuente=fuente, fecha_turno="2026-05-01", equipo="4001", operador="A", metros=100, horas_efectivas=4)
    _insertar_registro(db_path, id_fuente=fuente, fecha_turno="2026-05-02", equipo="4002", operador="A", metros=80, horas_efectivas=2)
    _insertar_registro(db_path, id_fuente=fuente, fecha_turno="2026-05-01", equipo="4003", operador="B", metros=50, horas_efectivas=2)

    ranking = query_service.obtener_ranking_operadores_excel(fuente, db_path=db_path)

    assert list(ranking["operador"]) == ["A", "B"]
    assert float(ranking.loc[0, "metros_totales"]) == 180.0
    assert int(ranking.loc[0, "registros"]) == 2
