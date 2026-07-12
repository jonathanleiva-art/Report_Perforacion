from datetime import date

import pandas as pd

import db
from services.alert_service import get_reportes_faltantes
from services.catalog_service import FLOTA_EQUIPOS


def _guardar_reportes(db_path, filas):
    df = pd.DataFrame(filas)
    db.insertar_dataframe_reportes(df, db_path=db_path, source="test")


def test_get_reportes_faltantes_detecta_matriz_fecha_equipo_turno(tmp_path):
    db_path = tmp_path / "reportes.db"
    equipos = FLOTA_EQUIPOS
    filas = []
    for equipo in equipos:
        for turno in ["Día", "Noche"]:
            if (equipo, turno) in {("9277", "Noche"), ("9339", "Día")}:
                continue
            filas.append({"Fecha turno": "2026-06-10", "Turno": turno, "Número equipo": equipo})

    _guardar_reportes(db_path, filas)

    faltantes = get_reportes_faltantes(
        fecha_desde=date(2026, 6, 10),
        fecha_hasta=date(2026, 6, 10),
        db_path=db_path,
        reference_date=date(2026, 6, 12),
    )

    assert len(faltantes) == 2
    assert set(zip(faltantes["Equipo"], faltantes["Turno"])) == {("9277", "Noche"), ("9339", "Día")}
    assert set(faltantes["Días de atraso"]) == {2}


def test_get_reportes_faltantes_respeta_rango_personalizado(tmp_path):
    db_path = tmp_path / "reportes.db"
    _guardar_reportes(
        db_path,
        [
            {"Fecha turno": "2026-06-01", "Turno": "Día", "Número equipo": "9245"},
            {"Fecha turno": "2026-06-02", "Turno": "Día", "Número equipo": "9245"},
        ],
    )

    faltantes = get_reportes_faltantes(
        fecha_desde=date(2026, 6, 2),
        fecha_hasta=date(2026, 6, 2),
        db_path=db_path,
        equipos=["9245"],
        turnos=["Día"],
        reference_date=date(2026, 6, 10),
    )

    assert faltantes.empty


def test_get_reportes_faltantes_normaliza_turno_y_numero_equipo(tmp_path):
    db_path = tmp_path / "reportes.db"
    _guardar_reportes(
        db_path,
        [
            {"Fecha turno": "2026-06-10", "Turno": "Dia", "Número equipo": "9245.0"},
            {"Fecha turno": "2026-06-10", "Turno": "noche", "Número equipo": 9245},
        ],
    )

    faltantes = get_reportes_faltantes(
        fecha_desde=date(2026, 6, 10),
        fecha_hasta=date(2026, 6, 10),
        db_path=db_path,
        equipos=["9245"],
        turnos=["Día", "Noche"],
        reference_date=date(2026, 6, 10),
    )

    assert faltantes.empty
