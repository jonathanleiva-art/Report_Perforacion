from contextlib import closing
import sqlite3

from services import operational_excel_service, source_adapter_service, source_service
from services.ciclos_service import quote_identifier


def _crear_fuente(db_path, nombre, tipo, estado="importada", total_registros=0):
    return source_service.crear_fuente_datos(
        nombre_fuente=nombre,
        tipo_fuente=tipo,
        archivo_origen=f"{nombre}.xlsx",
        total_registros=total_registros,
        fecha_min="2026-05-01",
        fecha_max="2026-05-02",
        estado=estado,
        db_path=db_path,
    )


def _insertar_operacional(
    db_path,
    id_fuente,
    fecha="2026-05-01",
    equipo="4001",
    operador="Operador A",
    metros=120,
    horas_efectivas=4,
):
    anio, mes, dia = [int(parte) for parte in fecha.split("-")]
    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        source_service.asegurar_tabla_fuentes_datos(connection)
        operational_excel_service._crear_tablas(connection)
        connection.execute(
            f"""
            INSERT INTO {quote_identifier(operational_excel_service.TABLA_REGISTROS_EXCEL)}
            (id_fuente, fecha_turno, anio, mes, dia, turno, numero_equipo, modelo, operador,
             total_metros, rendimiento_mh, horas_efectivas, horas_averia, horas_mp, horas_totales)
            VALUES (?, ?, ?, ?, ?, 'Dia', ?, 'D75KS', ?, ?, ?, ?, 1, 0, 12)
            """,
            (
                id_fuente,
                fecha,
                anio,
                mes,
                dia,
                equipo,
                operador,
                metros,
                metros / horas_efectivas,
                horas_efectivas,
            ),
        )
        connection.commit()


def test_adaptador_manual_sqlite_existe():
    adaptador = source_adapter_service.obtener_adaptador_fuente("manual_sqlite")

    assert adaptador.tipo_fuente == "manual_sqlite"
    assert adaptador.soporte == source_adapter_service.SOPORTE_COMPLETO


def test_adaptador_registro_operacional_excel_existe():
    adaptador = source_adapter_service.obtener_adaptador_fuente("registro_operacional_excel")

    assert adaptador.tipo_fuente == "registro_operacional_excel"
    assert adaptador.soporte == source_adapter_service.SOPORTE_COMPLETO


def test_ciclos_perforacion_retorna_soporte_parcial(tmp_path):
    db_path = tmp_path / "reportes.db"
    id_fuente = _crear_fuente(db_path, "Ciclos", "excel_ciclos")

    resultado = source_adapter_service.cargar_datos_fuente(id_fuente, db_path=db_path)

    assert resultado["tipo_fuente"] == "ciclos_perforacion"
    assert resultado["soporte"] == source_adapter_service.SOPORTE_PARCIAL
    assert resultado["registros"].empty
    assert resultado["mensaje"] == source_adapter_service.MENSAJE_CICLOS_PENDIENTE


def test_fuente_desconocida_retorna_no_soportado(tmp_path):
    db_path = tmp_path / "reportes.db"
    id_fuente = _crear_fuente(db_path, "Otro", "tipo_externo")

    validacion = source_adapter_service.validar_fuente_soportada(id_fuente, db_path=db_path)
    resultado = source_adapter_service.cargar_datos_fuente(id_fuente, db_path=db_path)

    assert validacion["soporte"] == source_adapter_service.SOPORTE_NO_SOPORTADO
    assert validacion["ok"] is False
    assert resultado["tipo_fuente"] == "desconocido"
    assert resultado["soporte"] == source_adapter_service.SOPORTE_NO_SOPORTADO


def test_resumen_normalizado_mismas_claves_para_fuentes_distintas(tmp_path):
    db_path = tmp_path / "reportes.db"
    id_excel = _crear_fuente(db_path, "Operacional", "excel_registro_operacional")
    id_ciclos = _crear_fuente(db_path, "Ciclos", "excel_ciclos")
    _insertar_operacional(db_path, id_excel, metros=180, horas_efectivas=6)

    resumen_manual = source_adapter_service.calcular_resumen_fuente_normalizado(
        "manual_sqlite",
        db_path=db_path,
    )
    resumen_excel = source_adapter_service.calcular_resumen_fuente_normalizado(
        id_excel,
        db_path=db_path,
    )
    resumen_ciclos = source_adapter_service.calcular_resumen_fuente_normalizado(
        id_ciclos,
        db_path=db_path,
    )

    claves = set(source_adapter_service.CLAVES_RESUMEN)
    assert set(resumen_manual) == claves
    assert set(resumen_excel) == claves
    assert set(resumen_ciclos) == claves


def test_no_mezcla_datos_de_fuentes_distintas(tmp_path):
    db_path = tmp_path / "reportes.db"
    fuente_a = _crear_fuente(db_path, "Operacional A", "excel_registro_operacional")
    fuente_b = _crear_fuente(db_path, "Operacional B", "excel_registro_operacional")
    _insertar_operacional(db_path, fuente_a, equipo="4001", operador="A", metros=100)
    _insertar_operacional(db_path, fuente_b, equipo="4002", operador="B", metros=250)

    resultado_a = source_adapter_service.cargar_datos_fuente(fuente_a, db_path=db_path)
    resumen_a = source_adapter_service.calcular_resumen_fuente_normalizado(fuente_a, db_path=db_path)

    assert resultado_a["soporte"] == source_adapter_service.SOPORTE_COMPLETO
    assert len(resultado_a["registros"]) == 1
    assert set(resultado_a["registros"]["equipo"]) == {"4001"}
    assert set(resultado_a["registros"]["operador"]) == {"A"}
    assert resumen_a["registros"] == 1
    assert resumen_a["metros_totales"] == 100
