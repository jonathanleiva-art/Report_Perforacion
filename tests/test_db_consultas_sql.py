from pathlib import Path

import pandas as pd

import db


def crear_dataframe_base():
    return pd.DataFrame(
        [
            {
                "Fecha turno": "2026-05-20",
                "Turno": "Día",
                "Modelo equipo": "FlexiROC D65",
                "Número equipo": "9272",
                "Operador": "Ana Soto",
                "Banco": "B1",
                "Malla": "M1",
                "Utilización": 40,
                "Disponibilidad %": 90,
                "Rendimiento m/h": 10,
                "Horas turno": 12,
                "Horas efectivas perforando": 10,
                "Metros perforados": 100,
                "Horas detención mecánica": 0,
                "Mantención Programada": 0,
            },
            {
                "Fecha turno": "2026-05-21",
                "Turno": "Noche",
                "Modelo equipo": "FlexiROC D65",
                "Número equipo": "9272",
                "Operador": "Ana Soto",
                "Banco": "B2",
                "Malla": "M2",
                "Utilización": 70,
                "Disponibilidad %": 95,
                "Rendimiento m/h": 10,
                "Horas turno": 10,
                "Horas efectivas perforando": 10,
                "Metros perforados": 100,
                "Horas detención mecánica": 0,
                "Mantención Programada": 0,
            },
            {
                "Fecha turno": "2026-05-22",
                "Turno": "Día",
                "Modelo equipo": "Sandvik D75KS",
                "Número equipo": "9245",
                "Operador": "Luis Perez",
                "Banco": "B1",
                "Malla": "M1",
                "Utilización": 80,
                "Disponibilidad %": 96,
                "Rendimiento m/h": 10,
                "Horas turno": 12,
                "Horas efectivas perforando": 10,
                "Metros perforados": 100,
                "Horas detención mecánica": 0,
                "Mantención Programada": 0,
            },
        ]
    )


def crear_db_temporal(tmp_path):
    db_path = tmp_path / "reportes_perforacion.sqlite"
    db.crear_tablas(db_path=db_path, columnas=list(crear_dataframe_base().columns))
    db.insertar_dataframe_reportes(crear_dataframe_base(), db_path=db_path, source="test")
    return db_path


def test_consultar_historial_filtrado_aplica_filtros_y_paginacion(tmp_path, monkeypatch):
    db_path = crear_db_temporal(tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("leer_registros no debe usarse en consultas SQL filtradas")

    monkeypatch.setattr(db, "leer_registros", fail_if_called)

    total = db.contar_historial_filtrado(
        db_path=db_path,
        turno=["Día"],
        equipo=["FlexiROC D65"],
        operador=["Ana Soto"],
        banco=["B1"],
        malla=["M1"],
    )
    assert total == 1

    df = db.consultar_historial_filtrado(
        db_path=db_path,
        turno=["Día"],
        equipo=["FlexiROC D65"],
        operador=["Ana Soto"],
        banco=["B1"],
        malla=["M1"],
        limit=1,
        offset=0,
    )

    assert len(df) == 1
    assert df.iloc[0]["Operador"] == "Ana Soto"
    assert df.iloc[0]["Banco"] == "B1"
    assert df.iloc[0]["Malla"] == "M1"


def test_obtener_valores_distintos_columna_lee_sql_sin_dataframe(tmp_path, monkeypatch):
    db_path = crear_db_temporal(tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("leer_registros no debe usarse para obtener opciones")

    monkeypatch.setattr(db, "leer_registros", fail_if_called)

    operadores = db.obtener_valores_distintos_columna("Operador", db_path=db_path)
    equipos = db.obtener_valores_distintos_columna("Modelo equipo", db_path=db_path)
    equipos_completos = db.obtener_valores_distintos_columna("Equipo", db_path=db_path)

    assert operadores == ["Ana Soto", "Luis Perez"]
    assert equipos == ["FlexiROC D65", "Sandvik D75KS"]
    assert "FlexiROC D65 9272" in equipos_completos
    assert "Sandvik D75KS 9245" in equipos_completos


def test_consultar_alertas_operacionales_filtradas_aplica_tipo_alerta_y_limit_offset(tmp_path, monkeypatch):
    db_path = crear_db_temporal(tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("leer_registros no debe usarse en alertas filtradas")

    monkeypatch.setattr(db, "leer_registros", fail_if_called)

    resultado = db.consultar_alertas_operacionales_filtradas(
        db_path=db_path,
        fecha_desde="2026-05-20",
        fecha_hasta="2026-05-22",
        equipo=["FlexiROC D65"],
        operador=["Ana Soto"],
        tipo_alerta=["Utilización muy baja"],
        limit=2,
        offset=0,
        horas_turno=12,
    )

    assert resultado["total_registros"] == 2
    assert resultado["sin_alertas"] is False
    detalle = resultado["detalle"]
    assert not detalle.empty
    assert all(detalle["Tipo de alerta"].astype(str).str.contains("Utilización muy baja", case=False, na=False))

    resultado_tipo_mismatch = db.consultar_alertas_operacionales_filtradas(
        db_path=db_path,
        fecha_desde="2026-05-20",
        fecha_hasta="2026-05-22",
        equipo=["FlexiROC D65"],
        operador=["Ana Soto"],
        tipo_alerta=["Horas turno distintas de 12"],
        limit=2,
        offset=0,
        horas_turno=12,
    )

    assert resultado_tipo_mismatch["total_registros"] == 2
    assert resultado_tipo_mismatch["sin_alertas"] is False
    assert not resultado_tipo_mismatch["detalle"].empty
    assert all(
        resultado_tipo_mismatch["detalle"]["Tipo de alerta"]
        .astype(str)
        .str.contains("Horas turno distintas de 12", case=False, na=False)
    )


def test_consultar_alertas_operacionales_filtradas_acepta_filtros_dashboard_completos(tmp_path, monkeypatch):
    db_path = crear_db_temporal(tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("leer_registros no debe usarse en alertas filtradas")

    monkeypatch.setattr(db, "leer_registros", fail_if_called)

    resultado = db.consultar_alertas_operacionales_filtradas(
        db_path=db_path,
        fecha_inicio="2026-05-20",
        fecha_fin="2026-05-22",
        equipos=["FlexiROC D65"],
        operadores=["Ana Soto"],
        turnos=["Día"],
        tipos_detencion=["Utilización muy baja"],
        banco=["B1"],
        malla=["M1"],
        fase=["Fase 1"],
        tipo_perforacion=["Rotación"],
        horas_turno=12,
    )

    assert "detalle" in resultado
    assert "mensajes" in resultado
    assert "sin_alertas" in resultado


def test_consultar_historial_filtrado_acepta_equipo_completo(tmp_path, monkeypatch):
    db_path = crear_db_temporal(tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("leer_registros no debe usarse en consultas SQL filtradas")

    monkeypatch.setattr(db, "leer_registros", fail_if_called)

    df = db.consultar_historial_filtrado(
        db_path=db_path,
        equipos=["FlexiROC D65 9272"],
    )

    assert len(df) == 2
    assert set(df["Modelo equipo"].astype(str)) == {"FlexiROC D65"}
    assert set(df["Número equipo"].astype(str)) == {"9272"}


def test_obtener_rango_fechas_y_resumenes_sql(tmp_path, monkeypatch):
    db_path = crear_db_temporal(tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("leer_registros no debe usarse en resúmenes SQL")

    monkeypatch.setattr(db, "leer_registros", fail_if_called)

    fecha_min, fecha_max = db.obtener_rango_fechas(db_path=db_path)
    assert str(fecha_min) == "2026-05-20"
    assert str(fecha_max) == "2026-05-22"

    resumen_operadores = db.consultar_resumen_operadores_filtrado(db_path=db_path)
    assert {"Ana Soto", "Luis Perez"}.issubset(set(resumen_operadores["Operador"]))
    ana = resumen_operadores[resumen_operadores["Operador"] == "Ana Soto"].iloc[0]
    assert round(float(ana["Metros totales perforados"]), 2) == 200.0
    assert round(float(ana["Rendimiento consolidado m/h"]), 2) == 10.0
    assert round(float(ana["Disponibilidad promedio"]), 2) == 100.0
    assert round(float(ana["Utilización promedio"]), 2) == 90.91

    resumen_equipos = db.consultar_resumen_operacional_equipos_filtrado(db_path=db_path)
    equipo_9272 = resumen_equipos[resumen_equipos["Número equipo"].astype(str) == "9272"].iloc[0]
    assert equipo_9272["Modelo equipo"] == "FlexiROC D65"
    assert round(float(equipo_9272["Metros perforados"]), 2) == 200.0
    assert round(float(equipo_9272["Horas efectivas perforando"]), 2) == 20.0
    assert round(float(equipo_9272["Rendimiento consolidado m/h"]), 2) == 10.0
    assert str(equipo_9272["Estado operacional"]) == "Operativo"

    resumen_aceros = db.consultar_resumen_aceros_filtrado(db_path=db_path)
    assert not resumen_aceros.empty
    assert {"FlexiROC D65", "Sandvik D75KS"}.issubset(set(resumen_aceros["Modelo equipo"]))
