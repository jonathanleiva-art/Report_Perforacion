from contextlib import closing
import sqlite3

import pandas as pd

from services import import_diagnostic_service, import_execution_service, operational_excel_service, source_service
from services.ciclos_service import quote_identifier


def _crear_excel_operacional(path, filas=None):
    datos = filas or [
        {
            "Año": 2026,
            "Mes": "Mayo",
            "Día": 1,
            "Turno": 1,
            "Nº Equipo": "4001",
            "Modelo": "D75KS",
            "Operador": "Jonathan Leiva",
            "Producción": 10,
            "Precorte": 0,
            "Buffer": 0,
            "Repaso": 0,
            "Total metros": 120,
            "m/h": 30,
            "Horas Trabajo": 12,
            "Horas Efectivas": 4,
            "Horas Avería": 1,
            "Horas MP": 0,
            "Colación": 1,
            "Horas Sin marca": 0,
            "Horas Disponible": 11,
            "Horas Totales": 12,
            "Nº Bit Tricono": "BT-1",
            "Martillo": "M1",
            "Observaciones": "Prueba",
        },
        {
            "Año": 2026,
            "Mes": "Mayo",
            "Día": 2,
            "Turno": "Noche",
            "Nº Equipo": "4002",
            "Modelo": "D75KS",
            "Operador": "Valeria Millan",
            "Producción": 20,
            "Precorte": 0,
            "Buffer": 0,
            "Repaso": 0,
            "Total metros": 180,
            "m/h": 45,
            "Horas Trabajo": 12,
            "Horas Efectivas": 4,
            "Horas Avería": 0,
            "Horas MP": 2,
            "Colación": 1,
            "Horas Sin marca": 0,
            "Horas Disponible": 10,
            "Horas Totales": 12,
            "Nº Bit Tricono": "BT-2",
            "Martillo": "M2",
            "Observaciones": "Prueba 2",
        },
    ]
    pd.DataFrame(datos).to_excel(path, sheet_name="Registro", index=False)
    return path


def _crear_fuente_diagnosticada(db_path, archivo):
    return source_service.crear_fuente_datos(
        nombre_fuente="Registro operacional prueba",
        tipo_fuente=import_diagnostic_service.TIPO_REGISTRO_OPERACIONAL,
        archivo_origen=str(archivo),
        total_registros=2,
        fecha_min="2026-05-01",
        fecha_max="2026-05-02",
        estado="diagnosticada",
        db_path=db_path,
    )


def _contar_fuentes(db_path):
    return len(source_service.listar_fuentes_datos(db_path=db_path, incluir_eliminadas=True))


def test_importar_registro_operacional_desde_fuente_inserta_con_id_fuente(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel = _crear_excel_operacional(tmp_path / "registro.xlsx")
    id_fuente = _crear_fuente_diagnosticada(db_path, excel)

    resumen = operational_excel_service.importar_registro_operacional_excel_desde_fuente(
        id_fuente,
        excel,
        db_path=db_path,
    )
    registros = operational_excel_service.leer_registros_operacional(db_path=db_path, id_fuente=id_fuente)

    assert resumen["filas_leidas"] == 2
    assert resumen["filas_validas"] == 2
    assert resumen["filas_insertadas"] == 2
    assert resumen["duplicados"] == 0
    assert resumen["fecha_min"] == "2026-05-01"
    assert resumen["fecha_max"] == "2026-05-02"
    assert resumen["metros_totales"] == 300.0
    assert set(registros["id_fuente"].astype(int)) == {id_fuente}
    assert set(registros["numero_equipo"]) == {"4001", "4002"}


def test_importar_registro_operacional_no_crea_fuente_duplicada(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel = _crear_excel_operacional(tmp_path / "registro.xlsx")
    id_fuente = _crear_fuente_diagnosticada(db_path, excel)
    fuentes_antes = _contar_fuentes(db_path)

    operational_excel_service.importar_registro_operacional_excel_desde_fuente(
        id_fuente,
        excel,
        db_path=db_path,
    )

    assert _contar_fuentes(db_path) == fuentes_antes


def test_importar_registro_operacional_detecta_duplicados_por_fuente(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel = _crear_excel_operacional(tmp_path / "registro.xlsx")
    id_fuente = _crear_fuente_diagnosticada(db_path, excel)

    primero = operational_excel_service.importar_registro_operacional_excel_desde_fuente(
        id_fuente,
        excel,
        db_path=db_path,
    )
    segundo = operational_excel_service.importar_registro_operacional_excel_desde_fuente(
        id_fuente,
        excel,
        db_path=db_path,
    )

    assert primero["filas_insertadas"] == 2
    assert segundo["filas_insertadas"] == 0
    assert segundo["duplicados"] == 2


def test_importar_registro_operacional_conserva_historicos_id_fuente_null(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel = _crear_excel_operacional(tmp_path / "registro.xlsx")
    id_fuente = _crear_fuente_diagnosticada(db_path, excel)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {quote_identifier(operational_excel_service.TABLA_REGISTROS_EXCEL)} (
                id_registro INTEGER PRIMARY KEY AUTOINCREMENT,
                id_fuente INTEGER,
                fecha_turno TEXT,
                turno TEXT,
                numero_equipo TEXT,
                operador TEXT,
                total_metros REAL
            )
            """
        )
        connection.execute(
            f"""
            INSERT INTO {quote_identifier(operational_excel_service.TABLA_REGISTROS_EXCEL)}
            (id_fuente, fecha_turno, turno, numero_equipo, operador, total_metros)
            VALUES (NULL, '2026-04-30', 'Dia', '3999', 'Historico', 50)
            """
        )
        connection.commit()

    operational_excel_service.importar_registro_operacional_excel_desde_fuente(
        id_fuente,
        excel,
        db_path=db_path,
    )

    with closing(sqlite3.connect(db_path)) as connection:
        historicos_null = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(operational_excel_service.TABLA_REGISTROS_EXCEL)} WHERE id_fuente IS NULL"
        ).fetchone()[0]
        nuevos = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(operational_excel_service.TABLA_REGISTROS_EXCEL)} WHERE id_fuente = ?",
            (id_fuente,),
        ).fetchone()[0]
    assert historicos_null == 1
    assert nuevos == 2


def test_import_execution_service_cambia_estado_a_importada(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel = _crear_excel_operacional(tmp_path / "registro.xlsx")
    id_fuente = _crear_fuente_diagnosticada(db_path, excel)

    resultado = import_execution_service.importar_fuente_diagnosticada(
        id_fuente,
        db_path=db_path,
        imports_dir=tmp_path / "imports",
    )

    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    registros = operational_excel_service.leer_registros_operacional(db_path=db_path, id_fuente=id_fuente)
    assert resultado["ok"]
    assert resultado["estado"] == import_execution_service.ESTADO_IMPORTADA
    assert resultado["registros_importados"] == 2
    assert fuente["estado"] == import_execution_service.ESTADO_IMPORTADA
    assert len(registros) == 2


def test_resumen_fuentes_operacionales_muestra_metricas_importadas(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel = _crear_excel_operacional(tmp_path / "registro.xlsx")
    id_fuente = _crear_fuente_diagnosticada(db_path, excel)
    import_execution_service.importar_fuente_diagnosticada(
        id_fuente,
        db_path=db_path,
        imports_dir=tmp_path / "imports",
    )

    resumen = operational_excel_service.resumen_fuentes_operacionales(db_path=db_path)

    assert len(resumen) == 1
    fila = resumen.iloc[0]
    assert int(fila["id_fuente"]) == id_fuente
    assert int(fila["registros_importados"]) == 2
    assert float(fila["metros_importados"]) == 300.0
    assert int(fila["equipos"]) == 2
    assert int(fila["operadores"]) == 2
    assert fila["estado"] == import_execution_service.ESTADO_IMPORTADA


def test_leer_operacional_dashboard_conserva_fuente_importada(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel = _crear_excel_operacional(tmp_path / "registro.xlsx")
    id_fuente = _crear_fuente_diagnosticada(db_path, excel)
    import_execution_service.importar_fuente_diagnosticada(
        id_fuente,
        db_path=db_path,
        imports_dir=tmp_path / "imports",
    )

    df = operational_excel_service.leer_operacional_dashboard(db_path=db_path, id_fuente=id_fuente)

    assert len(df) == 2
    assert set(df["id_fuente"].astype(int)) == {id_fuente}
    assert set(df["Fuente de datos"]) == {"Registro operacional prueba"}
    assert float(df["Metros perforados"].sum()) == 300.0
    assert set(df["Equipo"]) == {"4001", "4002"}


def test_leer_fuente_operacional_normalizada_expone_campos_estandar(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel = _crear_excel_operacional(tmp_path / "registro.xlsx")
    id_fuente = _crear_fuente_diagnosticada(db_path, excel)
    import_execution_service.importar_fuente_diagnosticada(
        id_fuente,
        db_path=db_path,
        imports_dir=tmp_path / "imports",
    )

    df = operational_excel_service.leer_fuente_operacional_normalizada(id_fuente, db_path=db_path)

    columnas = {
        "fecha_turno",
        "turno",
        "equipo",
        "operador",
        "metros",
        "horas_efectivas",
        "horas_averia",
        "horas_mp",
        "disponibilidad",
        "utilizacion",
        "rendimiento",
    }
    assert columnas.issubset(df.columns)
    assert len(df) == 2
    assert df.loc[0, "fecha_turno"].isoformat() == "2026-05-01"
    assert df.loc[0, "equipo"] == "4001"
    assert df.loc[0, "operador"] == "Jonathan Leiva"
    assert float(df["metros"].sum()) == 300.0
    assert round(float(df.loc[0, "utilizacion"]), 2) == 36.36


def test_leer_operacional_dashboard_incluye_aliases_normalizados(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel = _crear_excel_operacional(tmp_path / "registro.xlsx")
    id_fuente = _crear_fuente_diagnosticada(db_path, excel)
    import_execution_service.importar_fuente_diagnosticada(
        id_fuente,
        db_path=db_path,
        imports_dir=tmp_path / "imports",
    )

    df = operational_excel_service.leer_operacional_dashboard(db_path=db_path, id_fuente=id_fuente)

    assert {"fecha_turno", "equipo", "operador", "metros", "utilizacion"}.issubset(df.columns)
    assert set(df["equipo"]) == {"4001", "4002"}
    assert set(df["operador"]) == {"Jonathan Leiva", "Valeria Millan"}
    assert float(df["metros"].sum()) == float(df["Metros perforados"].sum())
