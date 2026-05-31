from schema import (
    alias_columna,
    columna_canonica,
    columnas_equivalentes,
    contrato_columnas,
    es_columna_canonica,
    variantes_columna,
)


def mojibake(texto, rondas=1):
    resultado = texto
    for _ in range(rondas):
        resultado = resultado.encode("utf-8").decode("latin1")
    return resultado


def test_alias_columna_acepta_nombre_ascii_sin_acentos():
    assert alias_columna("Numero equipo") == "Número equipo"
    assert alias_columna("Número equipo") == "Número equipo"
    assert alias_columna("Utilizacion") == "Utilización"
    assert alias_columna("Utilización") == "Utilización"
    assert alias_columna("Utilización %") == "Utilización"
    assert alias_columna("Petroleo litros") == "Petr\u00f3leo litros"


def test_alias_columna_repara_mojibake_historico():
    assert alias_columna(mojibake("N\u00famero equipo")) == "Número equipo"
    assert alias_columna(mojibake("Utilizaci\u00f3n %", 2)) == "Utilización"


def test_alias_columna_corrige_faltas_ortograficas_comunes():
    assert alias_columna("Nro equipo") == "Número equipo"
    assert alias_columna("Utilisacion") == "Utilización"
    assert alias_columna("Horometro inicial") == "Horómetro inicial"
    assert alias_columna("Mantencion Programada") == "Mantención Programada"
    assert alias_columna("Descripcion averia equipo") == "Descripción avería equipo"


def test_columnas_equivalentes_incluye_variantes_ascii():
    columnas = columnas_equivalentes("numero_equipo")

    assert "N\u00famero equipo" in columnas
    assert "Numero equipo" in columnas


def test_contrato_columnas_expone_canonicas_tipos_y_variantes():
    contrato = contrato_columnas()

    assert "N\u00famero equipo" in contrato
    assert contrato["Utilización"]["tipo"] == "REAL"
    assert "Utilización %" in contrato["Utilización"]["variantes"]
    assert "Numero equipo" in contrato["N\u00famero equipo"]["variantes"]


def test_columna_canonica_y_es_columna_canonica():
    assert columna_canonica("Numero equipo") == "N\u00famero equipo"
    assert columna_canonica("Utilización %") == "Utilización"
    assert es_columna_canonica("N\u00famero equipo") is True
    assert es_columna_canonica("Numero equipo") is False


def test_variantes_columna_devuelve_aliases_de_la_canonica():
    variantes = variantes_columna("Número equipo")

    assert "N\u00famero equipo" in variantes
    assert "Numero equipo" in variantes
