from text_utils import reparar_mojibake


def mojibake(texto, rondas=1):
    resultado = texto
    for _ in range(rondas):
        resultado = resultado.encode("utf-8").decode("latin1")
    return resultado


def test_reparar_mojibake_corrige_casos_visibles():
    casos = {
        mojibake("Día"): "Día",
        mojibake("Mantención"): "Mantención",
        mojibake("Número"): "Número",
        mojibake("utilización"): "utilización",
        mojibake("Día", 2): "Día",
        mojibake("Mantención", 2): "Mantención",
        mojibake("Número", 2): "Número",
        mojibake("utilización", 2): "utilización",
        mojibake("manersó"): "manera",
    }

    for entrada, esperado in casos.items():
        assert reparar_mojibake(entrada) == esperado
