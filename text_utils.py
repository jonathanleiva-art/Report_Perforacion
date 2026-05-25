def _mojibake(texto, rondas=1, encoding="latin1"):
    resultado = texto
    for _ in range(rondas):
        resultado = resultado.encode("utf-8").decode(encoding)
    return resultado


_TEXTOS_CANONICOS = [
    "Día",
    "día",
    "Número",
    "número",
    "Código",
    "Área",
    "Perforación",
    "perforación",
    "Aplicación",
    "Versión",
    "Ubicación",
    "Producción",
    "Petróleo",
    "Horómetro",
    "horómetro",
    "Detención",
    "detención",
    "Condición",
    "condición",
    "Avería",
    "avería",
    "mecánica",
    "Colación",
    "Mantención",
    "mantención",
    "Utilización",
    "utilización",
    "operación",
    "Operación",
    "Geología",
    "Área operacional",
    "Aquí",
    "modificación",
    "Tamaño",
    "válidas",
    "están",
    "Sin marcación",
    "Con marcación",
    "distribución",
    "Descripción",
    "Observación",
    "exportación",
    "información",
    "edición",
]


def _variantes_mojibake(texto):
    variantes = set()
    for rondas in (1, 2, 3, 4):
        variantes.add(_mojibake(texto, rondas, "latin1"))
        try:
            variantes.add(_mojibake(texto, rondas, "cp1252"))
        except UnicodeDecodeError:
            pass
    return variantes


REEMPLAZOS_MOJIBAKE = {
    variante: texto
    for texto in _TEXTOS_CANONICOS
    for variante in _variantes_mojibake(texto)
    if variante
}

REEMPLAZOS_MOJIBAKE.update({
    "Día": "Día",
    "día": "día",
    "Número": "Número",
    "número": "número",
    "Código": "Código",
    "Utilización": "Utilización",
    "utilización": "utilización",
    "\u00c3\\x81rea": "Área",
    "\u00c3\\x81rea operacional": "Área operacional",
    "\u00c3\u0192\u00c2\\x81rea": "Área",
    "\u00c3\u0192\u00c2\\x81rea operacional": "Área operacional",
    "Diferencia hor\u00c3\u00b3metro": "Diferencia horómetro",
    "Diferencia hor\u00c3\u0192\u00c2\u00b3metro": "Diferencia horómetro",
    "Marcaci\u00c3\u00b3n": "Marcación",
    "Aver\u00c3\\xada": "Avería",
    "Aver\u00c3\u0192\u00c2\\xada": "Avería",
    _mojibake("manersó"): "manera",
    "manersó": "manera",
    "\ufffd": "",
    "\ufeff": "",
})


def reparar_mojibake(valor):
    if valor is None:
        return ""

    texto = str(valor)
    for _ in range(4):
        corregido = texto
        for encoding in ("latin1", "cp1252"):
            try:
                corregido = texto.encode(encoding).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        if corregido == texto:
            break
        texto = corregido

    for origen, destino in REEMPLAZOS_MOJIBAKE.items():
        texto = texto.replace(origen, destino)
    return texto
