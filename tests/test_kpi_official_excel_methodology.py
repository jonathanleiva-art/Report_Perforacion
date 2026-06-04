import pandas as pd

from metrics import (
    calcular_disponibilidad,
    calcular_horas_disponibles,
    calcular_kpis_consolidados_dataframe,
    calcular_utilizacion,
)
from services import operational_excel_service


def test_metodologia_excel_oficial_caso_base():
    horas_disponibles = calcular_horas_disponibles(
        12,
        horas_averia=2,
        horas_mantencion=1,
    )
    disponibilidad = calcular_disponibilidad(
        horas_averia=2,
        horas_turno=12,
        horas_mantencion=1,
    )
    utilizacion = calcular_utilizacion(
        6,
        horas_turno=12,
        horas_averia=2,
        horas_mantencion=1,
    )
    kpis = calcular_kpis_consolidados_dataframe(pd.DataFrame([{
        "Horas Totales": 12,
        "Horas detencion mecanica": 2,
        "Mantencion Programada": 1,
        "Horas efectivas perforando": 6,
        "Metros perforados": 240,
    }]))

    assert horas_disponibles == 9
    assert disponibilidad == 75
    assert round(utilizacion, 2) == 66.67
    assert kpis["horas_disponibles"] == 9
    assert kpis["disponibilidad"] == 75
    assert kpis["utilizacion"] == 66.67
    assert kpis["rendimiento"] == 40


def test_excel_operacional_dashboard_recalcula_utilizacion_con_horas_disponibles():
    registros = pd.DataFrame([{
        "id_fuente": 1,
        "nombre_fuente": "Excel oficial prueba",
        "fecha_turno": "2026-05-01",
        "modelo": "D75KS",
        "numero_equipo": "4001",
        "operador": "Operador prueba",
        "turno": "Dia",
        "banco": "",
        "malla": "",
        "fase": "",
        "total_metros": 240,
        "numero_pozos": 4,
        "rendimiento_mh": None,
        "horas_totales": 12,
        "horas_efectivas": 6,
        "horas_averia": 2,
        "horas_mp": 1,
        "horas_disponible": 12,
        "observaciones": "",
    }])

    dashboard = operational_excel_service.registros_a_dataframe_dashboard(registros)

    assert dashboard.iloc[0]["Horas Disponible"] == 9
    assert dashboard.iloc[0]["Disponibilidad %"] == 75
    assert round(float(dashboard.iloc[0]["Utilización"]), 2) == 66.67
    assert dashboard.iloc[0]["Rendimiento m/h"] == 40
