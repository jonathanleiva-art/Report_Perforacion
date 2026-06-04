import pandas as pd

from ui import data_status


class FakeStreamlit:
    def __init__(self):
        self.captions = []
        self.warnings = []
        self.dataframes = []

    def caption(self, texto):
        self.captions.append(texto)

    def warning(self, texto):
        self.warnings.append(texto)

    def dataframe(self, df, **kwargs):
        self.dataframes.append((df, kwargs))


def test_resumen_contrato_columnas_formatea_anomalias():
    integridad = {
        "columnas_no_canonicas_sqlite": [
            {"columna": "Numero equipo", "columna_canonica": "Número equipo"}
        ],
        "columnas_extra_sqlite": [],
        "columnas_no_canonicas_excel": [
            {"columna": "Utilización %", "columna_canonica": "Utilización"}
        ],
        "columnas_extra_excel": ["Columna experimental"],
    }

    resumen = data_status.resumen_contrato_columnas(integridad)

    assert list(resumen["Fuente"]) == ["SQLite", "Excel", "Excel"]
    assert list(resumen["Tipo"]) == ["No canónica", "No canónica", "Extra"]
    assert list(resumen["Corrección sugerida"]) == [
        "Número equipo",
        "Utilización",
        "Revisar si debe agregarse al contrato",
    ]


def test_renderizar_estado_contrato_columnas_ok_muestra_caption():
    fake = FakeStreamlit()

    resumen = data_status.renderizar_estado_contrato_columnas(fake, {})

    assert resumen.empty
    assert fake.captions == ["Contrato de columnas: OK, sin encabezados fuera de estándar."]
    assert fake.warnings == []
    assert fake.dataframes == []


def test_renderizar_estado_contrato_columnas_con_anomalias_muestra_tabla():
    fake = FakeStreamlit()
    integridad = {
        "columnas_no_canonicas_excel": [
            {"columna": "Numero equipo", "columna_canonica": "Número equipo"}
        ],
    }

    resumen = data_status.renderizar_estado_contrato_columnas(fake, integridad)

    assert not resumen.empty
    assert fake.warnings == ["Se detectaron columnas fuera del contrato oficial."]
    assert len(fake.dataframes) == 1


def test_tabla_archivos_operativos_devuelve_resumen_estable():
    estado = {
        "existe_db": True,
        "sqlite_integrity_check": "ok",
        "fecha_db": "2026-05-31 10:00:00",
        "existe_excel": True,
        "registros_excel": 5,
        "fecha_excel": "2026-05-31 10:01:00",
        "ultimo_pdf": None,
        "ultimo_backup": None,
    }

    tabla = data_status._tabla_archivos_operativos(estado)

    assert isinstance(tabla, pd.DataFrame)
    assert list(tabla["Elemento"]) == ["SQLite principal", "Excel operacional", "Último PDF", "Último respaldo"]
    assert tabla.loc[0, "Detalle"] == "ok"
    assert tabla.loc[2, "Estado"] == "Sin PDF"
