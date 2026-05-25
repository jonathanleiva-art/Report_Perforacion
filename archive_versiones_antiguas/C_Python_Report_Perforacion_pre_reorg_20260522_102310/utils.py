from pathlib import Path

HORAS_TURNO = 12
BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "reportes_perforacion.xlsx"

EQUIPOS = {
    "Sandvik D75KS": ["9245", "9277"],
    "SmartROC D65": ["9339"],
    "FlexiROC D65": ["9274", "9272", "9259"],
}

OPERADORES = [
    "Jonathan Leiva",
    "Carlos Rondon",
    "Jhan Calderon",
    "Mauricio Mora",
    "Nicolas Torres",
    "Matías Toro",
    "Valeria Millan",
]

CODIGOS_OPERADOR = {
    "Jonathan Leiva": "M-8086",
    "Carlos Rondon": "M-2036",
    "Jhan Calderon": "M-9464",
    "Nicolas Torres": "M-9698",
    "Mauricio Mora": "M-9939",
    "Matías Toro": "M-204167",
    "Valeria Millan": "M-203529",
}

TIPOS_DETENCION = [
    "Falla Operacional",
    "Avería mecánica",
    "Cambio de aceros",
    "Geología",
    "Seguridad",
    "Colación",
    "Agua",
    "Combustible",
    "Traslado",
    "Cambio Turno",
    "Standby por falta de tajo/Patio",
    "Sin marcación",
    "Mantención Programada",
    "Tronadura",
    "Falta operador",
    "Otros",
]

IMAGENES_EQUIPO = {
    "Sandvik D75KS": "SANDVIK D75 KS.jpeg",
    "SmartROC D65": "SMART ROC D65.jpeg",
    "FlexiROC D65": {
        "9274": "FLEXI ROC D65 9274.jpeg",
        "9272": "FLEXI ROC D65 9272.jpeg",
        "9259": "FLEXI ROC D5 9259",
    },
}


def limpiar_entero(valor):
    if valor is None:
        return ""

    texto = str(valor).strip()
    if texto.lower() in ("", "nan", "none", "nat"):
        return ""

    try:
        numero = float(texto)
    except ValueError:
        return texto

    if numero.is_integer():
        return str(int(numero))

    return texto


def unir_valores(valores):
    return ", ".join(str(valor).strip() for valor in valores if str(valor).strip())


def opciones_desde_historial(df, columna, base=None):
    opciones = list(base or [])
    if columna not in df.columns:
        return opciones

    for valor in df[columna].dropna().astype(str):
        for item in valor.split(","):
            item = limpiar_entero(item) if columna in ("Banco", "Fase", "Número equipo") else item.strip()
            if item and item not in opciones:
                opciones.append(item)

    return opciones


def ruta_imagen_equipo(modelo, numero):
    imagen = IMAGENES_EQUIPO.get(modelo)
    if isinstance(imagen, dict):
        imagen = imagen.get(numero)

    if not imagen:
        return None

    ruta = BASE_DIR / imagen
    return ruta if ruta.exists() else None
