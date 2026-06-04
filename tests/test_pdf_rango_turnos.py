from datetime import date

import pandas as pd

import pdf_report
from ui.pdf_section import (
    MENSAJE_SIN_DATOS_PDF,
    _filtrar_pdf_por_rango_turno,
    _normalizar_turno_pdf,
    _turnos_incluidos_pdf,
)


def _df_pdf_base():
    return pd.DataFrame(
        [
            {
                "Fecha turno": date(2026, 5, 1),
                "Turno": "Día",
                "Fuente de datos": "Prueba operacional",
                "Modelo equipo": "FlexiROC D65",
                "Número equipo": "9275",
                "Equipo": "9275",
                "Operador": "Operador A",
                "Metros perforados": 100.0,
                "Pozos perforados turno": 5,
                "Horas efectivas perforando": 4.0,
                "Horas detención No efectivas": 2.0,
                "Horas detención mecánica": 1.0,
                "Mantención Programada": 0.5,
                "Horas MP": 0.5,
                "Disponibilidad %": 90.0,
                "Utilización": 70.0,
                "Rendimiento m/h": 25.0,
                "Observaciones": "",
            },
            {
                "Fecha turno": date(2026, 5, 1),
                "Turno": "Noche",
                "Fuente de datos": "Prueba operacional",
                "Modelo equipo": "FlexiROC D65",
                "Número equipo": "9274",
                "Equipo": "9274",
                "Operador": "Operador B",
                "Metros perforados": 120.0,
                "Pozos perforados turno": 6,
                "Horas efectivas perforando": 5.0,
                "Horas detención No efectivas": 1.0,
                "Horas detención mecánica": 0.0,
                "Mantención Programada": 0.0,
                "Horas MP": 0.0,
                "Disponibilidad %": 95.0,
                "Utilización": 80.0,
                "Rendimiento m/h": 24.0,
                "Observaciones": "",
            },
            {
                "Fecha turno": date(2026, 5, 2),
                "Turno": "1",
                "Fuente de datos": "Prueba operacional",
                "Modelo equipo": "Sandvik D75KS",
                "Número equipo": "9277",
                "Equipo": "9277",
                "Operador": "Operador A",
                "Metros perforados": 130.0,
                "Pozos perforados turno": 7,
                "Horas efectivas perforando": 5.0,
                "Horas detención No efectivas": 1.0,
                "Horas detención mecánica": 0.0,
                "Mantención Programada": 0.0,
                "Horas MP": 0.0,
                "Disponibilidad %": 96.0,
                "Utilización": 82.0,
                "Rendimiento m/h": 26.0,
                "Observaciones": "",
            },
            {
                "Fecha turno": date(2026, 5, 3),
                "Turno": "2",
                "Fuente de datos": "Prueba operacional",
                "Modelo equipo": "Sandvik D75KS",
                "Número equipo": "9245",
                "Equipo": "9245",
                "Operador": "Operador C",
                "Metros perforados": 140.0,
                "Pozos perforados turno": 8,
                "Horas efectivas perforando": 5.0,
                "Horas detención No efectivas": 1.0,
                "Horas detención mecánica": 0.0,
                "Mantención Programada": 0.0,
                "Horas MP": 0.0,
                "Disponibilidad %": 97.0,
                "Utilización": 84.0,
                "Rendimiento m/h": 28.0,
                "Observaciones": "",
            },
        ]
    )


def _generar_pdf_temporal(monkeypatch, tmp_path, df, fechas, turnos, archivo):
    monkeypatch.setattr(pdf_report, "REPORTES_PDF_DIR", tmp_path)
    return pdf_report.generar_pdf(
        df,
        fechas,
        turnos,
        df,
        fuente_datos="Prueba operacional",
        turno_archivo=archivo,
    )


def test_normalizacion_turnos_pdf_acepta_codigos_y_etiquetas():
    assert _normalizar_turno_pdf("1") == "1"
    assert _normalizar_turno_pdf("Día") == "1"
    assert _normalizar_turno_pdf("Dia") == "1"
    assert _normalizar_turno_pdf("2") == "2"
    assert _normalizar_turno_pdf("Noche") == "2"
    assert _turnos_incluidos_pdf(["Día y Noche"])[0] == ["1", "2"]


def test_pdf_un_dia_turno_dia(monkeypatch, tmp_path):
    df = _df_pdf_base()
    turnos, archivo, etiqueta = _turnos_incluidos_pdf(["Día"])
    filtrado = _filtrar_pdf_por_rango_turno(df, date(2026, 5, 1), date(2026, 5, 1), turnos)

    ruta = _generar_pdf_temporal(monkeypatch, tmp_path, filtrado, (date(2026, 5, 1), date(2026, 5, 1)), etiqueta, archivo)

    assert len(filtrado) == 1
    assert ruta.name == "Reporte_Perforacion_2026-05-01_a_2026-05-01_Dia.pdf"
    assert ruta.exists()
    assert ruta.stat().st_size > 0


def test_pdf_un_dia_turno_noche(monkeypatch, tmp_path):
    df = _df_pdf_base()
    turnos, archivo, etiqueta = _turnos_incluidos_pdf(["Noche"])
    filtrado = _filtrar_pdf_por_rango_turno(df, date(2026, 5, 1), date(2026, 5, 1), turnos)

    ruta = _generar_pdf_temporal(monkeypatch, tmp_path, filtrado, (date(2026, 5, 1), date(2026, 5, 1)), etiqueta, archivo)

    assert len(filtrado) == 1
    assert ruta.name == "Reporte_Perforacion_2026-05-01_a_2026-05-01_Noche.pdf"
    assert ruta.exists()
    assert ruta.stat().st_size > 0


def test_pdf_rango_tres_dias_dia_y_noche(monkeypatch, tmp_path):
    df = _df_pdf_base()
    turnos, archivo, etiqueta = _turnos_incluidos_pdf(["Día y Noche"])
    filtrado = _filtrar_pdf_por_rango_turno(df, date(2026, 5, 1), date(2026, 5, 3), turnos)

    ruta = _generar_pdf_temporal(monkeypatch, tmp_path, filtrado, (date(2026, 5, 1), date(2026, 5, 3)), etiqueta, archivo)

    assert len(filtrado) == 4
    assert filtrado["Metros perforados"].sum() == 490.0
    assert ruta.name == "Reporte_Perforacion_2026-05-01_a_2026-05-03_Dia_Noche.pdf"
    assert ruta.exists()
    assert ruta.stat().st_size > 0


def test_pdf_sin_datos_para_rango_muestra_mensaje_claro():
    df = _df_pdf_base()
    turnos, _, _ = _turnos_incluidos_pdf(["Noche"])
    filtrado = _filtrar_pdf_por_rango_turno(df, date(2026, 5, 2), date(2026, 5, 2), turnos)

    assert filtrado.empty
    assert MENSAJE_SIN_DATOS_PDF == "No existen registros para el rango de fechas y turnos seleccionados."
