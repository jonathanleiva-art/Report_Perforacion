import pandas as pd

import charts
from services import executive_service


def test_indice_salud_operacional_verde_con_indicadores_estables():
    resultado = executive_service.calcular_indice_salud_operacional(
        utilizacion=86,
        disponibilidad=92,
        rendimiento=16,
        horas_no_efectivas=4,
        horas_totales=100,
        cantidad_alertas=0,
        cantidad_registros=10,
    )

    assert resultado["indice"] >= 75
    assert resultado["semaforo"]["estado"] == "verde"
    assert resultado["detalle"]["utilizacion"] == 100
    assert resultado["detalle"]["disponibilidad"] == 100


def test_indice_salud_operacional_amarillo_con_desviaciones_moderadas():
    resultado = executive_service.calcular_indice_salud_operacional(
        utilizacion=60,
        disponibilidad=75,
        rendimiento=10,
        horas_no_efectivas=30,
        horas_totales=100,
        cantidad_alertas=2,
        cantidad_registros=10,
    )

    assert 50 <= resultado["indice"] < 75
    assert resultado["semaforo"]["estado"] == "amarillo"


def test_indice_salud_operacional_rojo_con_condicion_critica():
    resultado = executive_service.calcular_indice_salud_operacional(
        utilizacion=25,
        disponibilidad=45,
        rendimiento=4,
        horas_no_efectivas=70,
        horas_totales=100,
        cantidad_alertas=8,
        cantidad_registros=10,
    )

    assert resultado["indice"] < 50
    assert resultado["semaforo"]["estado"] == "rojo"


def test_calcular_kpis_ejecutivos_resume_operacion():
    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-01",
            "Equipo": "FlexiROC D65 9274",
            "Operador": "Operador Uno",
            "Metros perforados": 100,
            "Horas efectivas perforando": 5,
            "Horas detención No efectivas": 2,
            "Disponibilidad %": 90,
            "Utilización %": 80,
        },
        {
            "Fecha turno": "2026-05-02",
            "Equipo": "FlexiROC D65 9275",
            "Operador": "Operador Dos",
            "Metros perforados": 150,
            "Horas efectivas perforando": 10,
            "Horas detención No efectivas": 1,
            "Disponibilidad %": 100,
            "Utilización %": 90,
        },
    ])

    kpis = executive_service.calcular_kpis_ejecutivos(df)

    assert kpis["metros_perforados_totales"] == 250
    assert kpis["horas_efectivas"] == 15
    assert kpis["horas_no_efectivas"] == 3
    assert kpis["horas_averia"] == 0
    assert kpis["disponibilidad_promedio"] == 95
    assert kpis["utilizacion_promedio"] == 85
    assert round(kpis["rendimiento_promedio"], 2) == 16.67
    assert kpis["equipos_activos"] == 2
    assert kpis["operadores_registrados"] == 2


def test_rankings_y_tendencia_generan_salidas_ejecutivas():
    df = pd.DataFrame([
        {
            "Fecha turno": f"2026-05-{dia:02d}",
            "Equipo": "Equipo A" if dia % 2 else "Equipo B",
            "Operador": "Operador Uno" if dia <= 4 else "Operador Dos",
            "Metros perforados": 100 + dia,
            "Horas efectivas perforando": 5,
            "Utilización %": 80 - dia,
            "Disponibilidad %": 90,
            "Tipo detención": "Colación",
            "Causa detención": "Cambio de turno" if dia % 2 else "Relleno de agua",
        }
        for dia in range(1, 9)
    ])

    rankings = executive_service.calcular_rankings(df)
    tendencia = executive_service.calcular_tendencia(df)

    assert not rankings["mejor_rendimiento_equipos"].empty
    assert not rankings["menor_utilizacion_equipos"].empty
    assert not rankings["mayor_metraje_operadores"].empty
    assert not rankings["principales_causas_detencion"].empty
    assert not tendencia.empty
    assert "Periodo" in tendencia.columns


def test_construir_panel_ejecutivo_compone_kpis_salud_y_alertas():
    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-01",
            "Modelo equipo": "FlexiROC D65",
            "Número equipo": "9274",
            "Operador": "Operador Uno",
            "Metros perforados": 100,
            "Horas efectivas perforando": 5,
            "Horas detención No efectivas": 2,
            "Horas detención mecánica": 1,
            "Disponibilidad %": 90,
            "Utilización %": 80,
            "Tipo detención": "Colación",
            "Causa detención": "Cambio de turno",
        },
        {
            "Fecha turno": "2026-05-02",
            "Modelo equipo": "FlexiROC D65",
            "Número equipo": "9275",
            "Operador": "Operador Dos",
            "Metros perforados": 150,
            "Horas efectivas perforando": 10,
            "Horas detención No efectivas": 1,
            "Horas detención mecánica": 0,
            "Disponibilidad %": 100,
            "Utilización %": 90,
            "Tipo detención": "Relleno de agua",
            "Causa detención": "Relleno de agua",
        },
    ])

    panel = executive_service.construir_panel_ejecutivo(df)

    assert panel["total_registros"] == 2
    assert panel["kpis"]["horas_averia"] == 1
    assert "indice" in panel["salud"]
    assert "rankings" in panel
    assert "tendencia" in panel
    assert "alertas" in panel
    assert "detalle" in panel["alertas"]


def test_graficos_ejecutivos_principales_generan_figuras():
    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-01",
            "Modelo equipo": "FlexiROC D65",
            "Número equipo": "9274",
            "Operador": "Operador Uno",
            "Metros perforados": 100,
            "Horas efectivas perforando": 5,
            "Horas detención No efectivas": 2,
            "Horas detención mecánica": 1,
            "Disponibilidad %": 90,
            "Utilización %": 80,
            "Tipo detención": "Colación",
            "Causa detención": "Cambio de turno",
        },
        {
            "Fecha turno": "2026-05-02",
            "Modelo equipo": "Sandvik D75KS",
            "Número equipo": "9245",
            "Operador": "Operador Dos",
            "Metros perforados": 150,
            "Horas efectivas perforando": 10,
            "Horas detención No efectivas": 1,
            "Horas detención mecánica": 0,
            "Disponibilidad %": 100,
            "Utilización %": 90,
            "Tipo detención": "Relleno de agua",
            "Causa detención": "Relleno de agua",
        },
        {
            "Fecha turno": "2026-05-03",
            "Modelo equipo": "Sandvik D75KS",
            "Número equipo": "9245",
            "Operador": "Operador Dos",
            "Metros perforados": 120,
            "Horas efectivas perforando": 6,
            "Horas detención No efectivas": 0,
            "Horas detención mecánica": 3,
            "Disponibilidad %": 85,
            "Utilización %": 70,
            "Tipo detención": "Avería mecánica",
            "Causa detención": "Avería mecánica",
        },
    ])

    detalle_alertas = pd.DataFrame([
        {"Tipo de alerta": "Utilización muy baja"},
        {"Tipo de alerta": "Baja disponibilidad"},
    ])

    assert charts.fig_utilizacion_disponibilidad_equipo(df) is not None
    assert charts.fig_pareto_detenciones(df) is not None
    assert charts.fig_ranking_operadores_metros(df) is not None
    assert charts.fig_evolucion_diaria_metros_ejecutivo(df) is not None
    assert charts.fig_alertas_operacionales_ejecutivo(detalle_alertas) is not None
