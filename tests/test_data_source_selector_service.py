from contextlib import closing
import sqlite3

from services import data_source_selector_service as selector_service
from services import operational_excel_service, source_service
from services.ciclos_service import quote_identifier


def _crear_fuente(db_path, nombre, tipo, estado="activa", activo=None, total_registros=0):
    return source_service.crear_fuente_datos(
        nombre_fuente=nombre,
        tipo_fuente=tipo,
        archivo_origen=f"{nombre}.xlsx",
        total_registros=total_registros,
        fecha_min="2026-05-01",
        fecha_max="2026-05-02",
        estado=estado,
        activo=activo,
        db_path=db_path,
    )


def _insertar_operacional(db_path, id_fuente, equipo="4001", operador="Operador A", metros=120):
    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        source_service.asegurar_tabla_fuentes_datos(connection)
        operational_excel_service._crear_tablas(connection)
        connection.execute(
            f"""
            INSERT INTO {quote_identifier(operational_excel_service.TABLA_REGISTROS_EXCEL)}
            (id_fuente, fecha_turno, anio, mes, dia, turno, numero_equipo, modelo, operador,
             total_metros, horas_efectivas, horas_averia, horas_mp, horas_totales)
            VALUES (?, '2026-05-01', 2026, 5, 1, 'Dia', ?, 'D75KS', ?, ?, 4, 1, 0, 12)
            """,
            (id_fuente, equipo, operador, metros),
        )
        connection.commit()


def test_listar_fuentes_disponibles_incluye_manual_sqlite(tmp_path):
    fuentes = selector_service.listar_fuentes_disponibles(db_path=tmp_path / "reportes.db")

    manual = fuentes[fuentes["id_fuente"].astype(str).eq(selector_service.ID_MANUAL_SQLITE)]
    assert len(manual) == 1
    assert manual.iloc[0]["nombre_fuente"] == "Registros manuales SQLite"
    assert manual.iloc[0]["tipo_dashboard"] == selector_service.TIPO_MANUAL_SQLITE
    assert manual.iloc[0]["recomendacion_dashboard"] == "Dashboard principal"


def test_listar_fuentes_disponibles_incluye_activas_validas_y_excluye_eliminadas(tmp_path):
    db_path = tmp_path / "reportes.db"
    activa = _crear_fuente(db_path, "Activa", "excel_registro_operacional", estado="activa")
    diagnosticada = _crear_fuente(db_path, "Diagnosticada", "excel_registro_operacional", estado="diagnosticada")
    importada = _crear_fuente(db_path, "Importada", "excel_registro_operacional", estado="importada")
    pendiente = _crear_fuente(db_path, "Pendiente", "excel_registro_operacional", estado="pendiente_importador")
    _crear_fuente(db_path, "Eliminada", "excel_registro_operacional", estado="eliminada")
    _crear_fuente(db_path, "Inactiva", "excel_registro_operacional", estado="activa", activo=0)

    fuentes = selector_service.listar_fuentes_disponibles(db_path=db_path)
    ids = set(fuentes["id_fuente"].astype(str))

    assert str(activa) in ids
    assert str(diagnosticada) in ids
    assert str(importada) in ids
    assert str(pendiente) in ids
    assert "Eliminada" not in set(fuentes["nombre_fuente"])
    assert "Inactiva" not in set(fuentes["nombre_fuente"])


def test_clasifica_registro_operacional_excel_y_recomienda_dashboard(tmp_path):
    fuente = {"tipo_fuente": "excel_registro_operacional", "estado": "importada"}

    assert selector_service.clasificar_fuente_para_dashboard(fuente) == selector_service.TIPO_REGISTRO_OPERACIONAL_EXCEL
    disponible = selector_service.listar_fuentes_disponibles(db_path=tmp_path / "reportes.db")
    assert "recomendacion_dashboard" in disponible.columns


def test_clasifica_ciclos_perforacion_y_recomienda_pendiente(tmp_path):
    db_path = tmp_path / "reportes.db"
    id_fuente = _crear_fuente(db_path, "Ciclos", "excel_ciclos", estado="importada")

    fuente = selector_service.obtener_fuente_seleccionable(id_fuente, db_path=db_path)

    assert selector_service.clasificar_fuente_para_dashboard(fuente) == selector_service.TIPO_CICLOS_PERFORACION
    assert fuente["recomendacion_dashboard"] == "Dashboard Ciclos pendiente"


def test_recomienda_estados_no_importados(tmp_path):
    db_path = tmp_path / "reportes.db"
    diagnosticada = _crear_fuente(db_path, "Diag", "excel_registro_operacional", estado="diagnosticada")
    pendiente = _crear_fuente(db_path, "Pend", "excel_registro_operacional", estado="pendiente_importador")

    fuente_diag = selector_service.obtener_fuente_seleccionable(diagnosticada, db_path=db_path)
    fuente_pend = selector_service.obtener_fuente_seleccionable(pendiente, db_path=db_path)

    assert fuente_diag["recomendacion_dashboard"] == "Pendiente de importación"
    assert fuente_pend["recomendacion_dashboard"] == "Importador pendiente"


def test_obtener_resumen_fuente_operacional_importada(tmp_path):
    db_path = tmp_path / "reportes.db"
    id_fuente = _crear_fuente(db_path, "Operacional", "excel_registro_operacional", estado="importada")
    _insertar_operacional(db_path, id_fuente, equipo="4001", operador="A", metros=120)
    _insertar_operacional(db_path, id_fuente, equipo="4002", operador="B", metros=180)

    resumen = selector_service.obtener_resumen_fuente(id_fuente, db_path=db_path)

    assert resumen["tipo_dashboard"] == selector_service.TIPO_REGISTRO_OPERACIONAL_EXCEL
    assert resumen["registros"] == 2
    assert resumen["metros_totales"] == 300
    assert resumen["equipos"] == 2
    assert resumen["operadores"] == 2
    assert resumen["recomendacion_dashboard"] == "Dashboard Excel Operacional"
