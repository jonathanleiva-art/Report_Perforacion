from services import enaex_pdf_extraction_service


def test_extraer_datos_enaex_desde_texto_general_y_sectores():
    texto = """
    ENAEX
    Plano: Banco 204 Malla 118 Producción Norte
    Banco: 204
    Malla: 118
    Fecha: 04-06-2026
    Producción pozos: 25 metros: 300 pasadura: 1.5 diametro: 10.5
    Buffer 1 pozos: 8 metros: 96 pasadura: 1.2 diametro: 10.5
    Buffer 2 pozos: 6 metros: 72 pasadura: 1.2 diametro: 10.5
    Borde pozos: 4 metros: 48 pasadura: 1.0 diametro: 10.5
    Precorte 02 pozos: 10 metros: 120 pasadura: 0.8 diametro: 6.75
    """

    resultado = enaex_pdf_extraction_service.extraer_datos_enaex_desde_texto(texto, nombre_archivo="enaex.pdf")

    assert resultado["ok"] is True
    assert resultado["banco"] == "204"
    assert resultado["malla"] == "118"
    assert resultado["fecha_plan"] == "2026-06-04"
    assert resultado["nombre_plan"].startswith("Banco 204")
    assert [sector["tipo_sector"] for sector in resultado["sectores"]] == [
        "Producción",
        "Buffer 1",
        "Buffer 2",
        "Borde",
        "Precorte",
    ]
    produccion = resultado["sectores"][0]
    precorte = resultado["sectores"][-1]
    assert produccion["pozos_planificados"] == 25
    assert produccion["metros_planificados"] == 300
    assert produccion["pasadura"] == "1.5"
    assert produccion["diametro"] == "10.5"
    assert precorte["numero_precorte"] == "02"


def test_extraer_datos_enaex_detecta_sectores_por_presencia_si_no_hay_metricas():
    texto = "Banco: 205\nMalla: 119\nFecha: 2026-06-05\nProducción Buffer 1 Precorte"

    resultado = enaex_pdf_extraction_service.extraer_datos_enaex_desde_texto(texto)

    tipos = {sector["tipo_sector"] for sector in resultado["sectores"]}
    assert {"Producción", "Buffer 1", "Precorte"}.issubset(tipos)


def test_extraer_datos_enaex_usa_nombre_archivo_para_fase_y_banco():
    texto = "Malla: 114\nProduccion pozos: 10 metros: 120"

    resultado = enaex_pdf_extraction_service.extraer_datos_enaex_desde_texto(
        texto,
        nombre_archivo="DES_F01_B2296 (1).pdf",
    )

    assert resultado["ok"] is True
    assert resultado["fase"] == "1"
    assert resultado["banco"] == "2296"
    assert resultado["malla"] == "114"
    assert resultado["nombre_plan"] == "DES_F01_B2296 (1)"
    assert resultado["texto_len"] > 0
    assert "No se detecto fase." not in resultado["errores"]
    assert "No se detecto banco." not in resultado["errores"]
