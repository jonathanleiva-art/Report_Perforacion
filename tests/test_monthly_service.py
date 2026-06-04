import gc
import warnings

import pandas as pd

import db
from services.monthly_service import (
    obtener_ranking_equipos_mensual,
    obtener_ranking_operadores_mensual,
    obtener_resumen_mensual,
)


def _crear_datos_mensuales(db_path):
    registros = pd.DataFrame(
        [
            {
                "Fecha turno": "2026-05-01",
                "Equipo": "Equipo 1",
                "Número equipo": "9274",
                "Operador": "Ana Soto",
                "Metros perforados": 100,
                "Horas efectivas perforando": 5,
                "Horas detencion No efectivas": 1,
                "Horas detencion mecanica": 0.5,
                "Disponibilidad %": 90,
                "Utilización": 80,
                "Rendimiento m/h": 20,
            },
            {
                "Fecha turno": "2026-05-15",
                "Equipo": "Equipo 2",
                "Número equipo": "9275",
                "Operador": "Luis Perez",
                "Metros perforados": 150,
                "Horas efectivas perforando": 10,
                "Horas detencion No efectivas": 2,
                "Horas detencion mecanica": 1.5,
                "Disponibilidad %": 100,
                "Utilización": 90,
                "Rendimiento m/h": 15,
            },
            {
                "Fecha turno": "2026-06-01",
                "Equipo": "Equipo 1",
                "Número equipo": "9274",
                "Operador": "Ana Soto",
                "Metros perforados": 80,
                "Horas efectivas perforando": 4,
                "Horas detencion No efectivas": 0,
                "Horas detencion mecanica": 0,
                "Disponibilidad %": 95,
                "Utilización": 70,
                "Rendimiento m/h": 20,
            },
        ]
    )
    db.insertar_dataframe_reportes(registros, db_path=db_path, source="test_monthly")


def test_obtener_resumen_mensual_mes_con_datos(tmp_path):
    db_path = tmp_path / "mensual.db"
    _crear_datos_mensuales(db_path)

    resumen = obtener_resumen_mensual(2026, 5, db_path=db_path)

    assert resumen["anio"] == 2026
    assert resumen["mes"] == 5
    assert resumen["fecha_inicio"] == "2026-05-01"
    assert resumen["fecha_fin"] == "2026-05-31"
    assert resumen["cantidad_registros"] == 2
    assert resumen["metros_totales"] == 250
    assert resumen["horas_efectivas_totales"] == 15
    assert resumen["horas_no_efectivas_totales"] == 3
    assert resumen["horas_averias_totales"] == 2
    assert resumen["disponibilidad_promedio"] == 91.67
    assert resumen["utilizacion_promedio"] == 68.18
    assert resumen["rendimiento_promedio"] == 16.67
    assert resumen["equipos_distintos"] == 2
    assert resumen["operadores_distintos"] == 2


def test_obtener_resumen_mensual_mes_sin_datos(tmp_path):
    db_path = tmp_path / "mensual_vacio.db"
    _crear_datos_mensuales(db_path)

    resumen = obtener_resumen_mensual(2026, 7, db_path=db_path)

    assert resumen == {
        "anio": 2026,
        "mes": 7,
        "fecha_inicio": "2026-07-01",
        "fecha_fin": "2026-07-31",
        "cantidad_registros": 0,
        "metros_totales": 0.0,
        "horas_efectivas_totales": 0.0,
        "horas_no_efectivas_totales": 0.0,
        "horas_averias_totales": 0.0,
        "disponibilidad_promedio": 0.0,
        "utilizacion_promedio": 0.0,
        "rendimiento_promedio": 0.0,
        "equipos_distintos": 0,
        "operadores_distintos": 0,
    }


def test_obtener_resumen_mensual_estructura_diccionario(tmp_path):
    db_path = tmp_path / "mensual_estructura.db"
    db.crear_tablas(db_path=db_path)

    resumen = obtener_resumen_mensual(2026, 2, db_path=db_path)

    assert list(resumen.keys()) == [
        "anio",
        "mes",
        "fecha_inicio",
        "fecha_fin",
        "cantidad_registros",
        "metros_totales",
        "horas_efectivas_totales",
        "horas_no_efectivas_totales",
        "horas_averias_totales",
        "disponibilidad_promedio",
        "utilizacion_promedio",
        "rendimiento_promedio",
        "equipos_distintos",
        "operadores_distintos",
    ]
    assert resumen["fecha_fin"] == "2026-02-28"


def test_obtener_resumen_mensual_sin_resourcewarning_sqlite(tmp_path):
    db_path = tmp_path / "mensual_warning.db"
    _crear_datos_mensuales(db_path)

    with warnings.catch_warnings(record=True) as capturadas:
        warnings.simplefilter("always", ResourceWarning)
        obtener_resumen_mensual(2026, 5, db_path=db_path)
        gc.collect()

    sqlite_warnings = [
        warning
        for warning in capturadas
        if issubclass(warning.category, ResourceWarning)
        and "unclosed database" in str(warning.message)
    ]
    assert sqlite_warnings == []


def test_obtener_resumen_mensual_rendimiento_ponderado_ignora_rendimiento_simple_y_no_productivos(tmp_path):
    db_path = tmp_path / "mensual_ponderado.db"
    registros = pd.DataFrame(
        [
            {
                "Fecha turno": "2026-05-01",
                "Equipo": "Equipo 1",
                "Operador": "Ana Soto",
                "Metros perforados": 100,
                "Horas efectivas perforando": 5,
                "Rendimiento m/h": 999,
            },
            {
                "Fecha turno": "2026-05-02",
                "Equipo": "Equipo 2",
                "Operador": "Luis Perez",
                "Metros perforados": 150,
                "Horas efectivas perforando": 10,
                "Rendimiento m/h": 1,
            },
            {
                "Fecha turno": "2026-05-03",
                "Equipo": "Equipo 3",
                "Operador": "Sin Horas",
                "Metros perforados": 50,
                "Horas efectivas perforando": 0,
                "Rendimiento m/h": 100,
            },
            {
                "Fecha turno": "2026-05-04",
                "Equipo": "Equipo 4",
                "Operador": "Sin Metros",
                "Metros perforados": 0,
                "Horas efectivas perforando": 2,
                "Rendimiento m/h": 100,
            },
        ]
    )
    db.insertar_dataframe_reportes(registros, db_path=db_path, source="test_monthly_weighted")

    resumen = obtener_resumen_mensual(2026, 5, db_path=db_path)

    assert resumen["metros_totales"] == 300
    assert resumen["horas_efectivas_totales"] == 17
    assert resumen["rendimiento_promedio"] == 17.65


def test_obtener_ranking_equipos_mensual_con_datos_ordenado(tmp_path):
    db_path = tmp_path / "ranking_equipos.db"
    _crear_datos_mensuales(db_path)

    ranking = obtener_ranking_equipos_mensual(2026, 5, db_path=db_path)

    assert list(ranking.columns) == [
        "numero_equipo",
        "metros_totales",
        "horas_efectivas_totales",
        "horas_no_efectivas_totales",
        "horas_averias_totales",
        "disponibilidad_promedio",
        "utilizacion_promedio",
        "rendimiento_promedio",
        "cantidad_registros",
    ]
    assert ranking["metros_totales"].tolist() == [150, 100]
    assert ranking.iloc[0]["numero_equipo"] == "9275"
    assert ranking.iloc[0]["cantidad_registros"] == 1


def test_obtener_ranking_operadores_mensual_con_datos_ordenado(tmp_path):
    db_path = tmp_path / "ranking_operadores.db"
    _crear_datos_mensuales(db_path)

    ranking = obtener_ranking_operadores_mensual(2026, 5, db_path=db_path)

    assert list(ranking.columns) == [
        "operador",
        "metros_totales",
        "horas_efectivas_totales",
        "horas_no_efectivas_totales",
        "horas_averias_totales",
        "disponibilidad_promedio",
        "utilizacion_promedio",
        "rendimiento_promedio",
        "cantidad_registros",
    ]
    assert ranking["metros_totales"].tolist() == [150, 100]
    assert ranking.iloc[0]["operador"] == "Luis Perez"
    assert ranking.iloc[1]["operador"] == "Ana Soto"


def test_rankings_mensuales_vacios_sin_datos(tmp_path):
    db_path = tmp_path / "ranking_vacio.db"
    _crear_datos_mensuales(db_path)

    equipos = obtener_ranking_equipos_mensual(2026, 7, db_path=db_path)
    operadores = obtener_ranking_operadores_mensual(2026, 7, db_path=db_path)

    assert equipos.empty
    assert operadores.empty
    assert list(equipos.columns) == [
        "numero_equipo",
        "metros_totales",
        "horas_efectivas_totales",
        "horas_no_efectivas_totales",
        "horas_averias_totales",
        "disponibilidad_promedio",
        "utilizacion_promedio",
        "rendimiento_promedio",
        "cantidad_registros",
    ]
    assert list(operadores.columns) == [
        "operador",
        "metros_totales",
        "horas_efectivas_totales",
        "horas_no_efectivas_totales",
        "horas_averias_totales",
        "disponibilidad_promedio",
        "utilizacion_promedio",
        "rendimiento_promedio",
        "cantidad_registros",
    ]
