import pandas as pd

from services import import_diagnostic_service as service


def test_normalizar_nombre_columna_limpia_tildes_espacios_y_variantes():
    assert service.normalizar_nombre_columna(" Nº Equipo ") == "numero_equipo"
    assert service.normalizar_nombre_columna("N° Equipo") == "numero_equipo"
    assert service.normalizar_nombre_columna("Número   de Equipo") == "numero_equipo"
    assert service.normalizar_nombre_columna("Horas Efectivas") == "horas_efectivas"
    assert service.normalizar_nombre_columna("m/h") == "rendimiento_m_h"


def test_detectar_tipo_fuente_ciclos_perforacion():
    columnas = [
        "Pozo Perforación",
        "Banco",
        "Profundidad de Pozo (MTR)",
        "Norte",
        "Este",
        "Operador de Unidad de Perforación",
        "Unidad de Perforación",
    ]

    assert service.detectar_tipo_fuente(columnas) == service.TIPO_CICLOS


def test_detectar_tipo_fuente_registro_operacional_excel():
    columnas = [
        "Año",
        "Mes",
        "Día",
        "Turno",
        "Nº Equipo",
        "Operador",
        "Total metros",
        "Horas Efectivas",
        "Horas Avería",
        "Disponibilidad",
        "Utilización",
    ]

    assert service.detectar_tipo_fuente(columnas) == service.TIPO_REGISTRO_OPERACIONAL


def test_detectar_tipo_fuente_desconocido():
    columnas = ["Producto", "Precio", "Cliente"]

    assert service.detectar_tipo_fuente(columnas) == service.TIPO_DESCONOCIDO


def test_diagnosticar_excel_registro_operacional_temporal(tmp_path):
    ruta = tmp_path / "registro_operacional.xlsx"
    df = pd.DataFrame(
        [
            {
                "Año": 2026,
                "Mes": "Mayo",
                "Día": 1,
                "Turno": "Día",
                "Nº Equipo": 9275,
                "Operador": "Operador A",
                "Total metros": 100.5,
                "Horas Efectivas": 4.0,
                "Horas Avería": 1.0,
                "Disponibilidad": 90.0,
                "Utilización": 70.0,
            },
            {
                "Año": 2026,
                "Mes": "Mayo",
                "Día": 2,
                "Turno": "Noche",
                "Nº Equipo": 9274,
                "Operador": "Operador B",
                "Total metros": 120.0,
                "Horas Efectivas": 5.0,
                "Horas Avería": 0.0,
                "Disponibilidad": 95.0,
                "Utilización": 80.0,
            },
        ]
    )
    df.to_excel(ruta, sheet_name="Registro", index=False)

    diagnostico = service.diagnosticar_excel(ruta)

    assert diagnostico["archivo"] == str(ruta)
    assert diagnostico["hojas_detectadas"] == ["Registro"]
    assert diagnostico["hoja_principal_detectada"] == "Registro"
    assert diagnostico["total_filas_leidas"] == 2
    assert diagnostico["total_columnas"] == len(df.columns)
    assert diagnostico["tipo_fuente_detectado"] == service.TIPO_REGISTRO_OPERACIONAL
    assert diagnostico["fecha_min"] == "2026-05-01"
    assert diagnostico["fecha_max"] == "2026-05-02"
    assert diagnostico["equipos_detectados"] == ["9274", "9275"]
    assert diagnostico["operadores_detectados"] == ["Operador A", "Operador B"]
    assert diagnostico["metros_totales_estimados"] == 220.5
    assert diagnostico["estado_diagnostico"] == "ok"


def test_diagnosticar_excel_desconocido_temporal(tmp_path):
    ruta = tmp_path / "desconocido.xlsx"
    pd.DataFrame({"Producto": ["A"], "Precio": [100]}).to_excel(ruta, index=False)

    diagnostico = service.diagnosticar_excel(ruta)

    assert diagnostico["tipo_fuente_detectado"] == service.TIPO_DESCONOCIDO
    assert diagnostico["estado_diagnostico"] == "advertencia"
    assert diagnostico["metros_totales_estimados"] == 0.0
    assert diagnostico["observaciones"]
