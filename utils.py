from config import BASE_DIR, EXCEL_PATH

HORAS_TURNO = 12

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
    "Relleno de agua",
    "Combustible",
    "Traslado",
    "Cambio Turno",
    "Standby por falta de tajo/Patio",
    "Mantención Programada",
    "Tronadura",
    "Falta operador",
    "Otros",
]

IMAGENES_EQUIPO = {
    "sandvik d75ks": "SANDVIK D75 KS.jpeg",
    "smartroc d65": "SMART ROC D65.jpeg",
    "flexiroc d65": {
        "9274": "FLEXI ROC D65 9274.jpeg",
        "9272": "FLEXI ROC D65 9272.jpeg",
        "9259": "FLEXI ROC D65 9259.jpeg",
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
    clave_modelo = str(modelo or "").strip().lower()
    imagen = IMAGENES_EQUIPO.get(clave_modelo)
    if isinstance(imagen, dict):
        clave_numero = str(numero or "").strip()
        imagen = imagen.get(clave_numero)

    if not imagen:
        return None

    for carpeta in (BASE_DIR / "assets", BASE_DIR):
        ruta = carpeta / imagen
        if ruta.exists():
            return ruta
    return None


DETENCION_HORAS_COLUMNAS = {
    "Falla Operacional": "Falla Operacional",
    "Avería mecánica": "Horas detención mecánica",
    "Cambio de aceros": "Cambio de aceros",
    "Geología": "Geología",
    "Seguridad": "Seguridad",
    "Colación": "Colación",
    "Relleno de agua": "Relleno de agua",
    "Combustible": "Combustible",
    "Traslado": "Traslado",
    "Cambio Turno": "Cambio turno",
    "Standby por falta de tajo/Patio": "Standby por falta de tajo/Patio",
    "Mantención Programada": "Mantención Programada",
    "Tronadura": "Tronadura",
    "Falta operador": "Falta operador",
    "Otros": "Otros",
}

COLUMNAS_HORAS_DETENCION = list(dict.fromkeys(DETENCION_HORAS_COLUMNAS.values()))


def color_estado_operacional(estado):
    return {
        # Valores oficiales
        "Equipo Operativo con marcación":              "#2ECC71",
        "Equipo Operativo, sin marcación":             "#BDC3C7",
        "Equipo Operativo, sin patio de perforación":  "#F39C12",
        "Equipo en Mantención Programada":             "#3498DB",
        "Equipo en Avería":                            "#E74C3C",
        # Legacy
        "Sin marcación":                               "#BDC3C7",
        "Con marcación":                               "#2ECC71",
        "Con marcación (parcial)":                     "#F39C12",
        "Fuera de servicio por avería":                "#E74C3C",
        "En mantención programada":                    "#3498DB",
        "Standby por falta de tajo/Patio":             "#F39C12",
        "Operativo":                                   "#2ECC71",
        "Operativo parcial":                           "#F39C12",
        "Avería":                                      "#E74C3C",
        "Mantención Programada":                       "#3498DB",
    }.get(estado, "#F3F4F6")


def color_texto_estado_operacional(estado):
    return {
        # Valores oficiales
        "Equipo Operativo con marcación":              "#145A32",
        "Equipo Operativo, sin marcación":             "#616A6B",
        "Equipo Operativo, sin patio de perforación":  "#7D6608",
        "Equipo en Mantención Programada":             "#1A5276",
        "Equipo en Avería":                            "#7B241C",
        # Legacy
        "Sin marcación":                               "#616A6B",
        "Con marcación":                               "#145A32",
        "Con marcación (parcial)":                     "#7D6608",
        "Fuera de servicio por avería":                "#7B241C",
        "En mantención programada":                    "#1A5276",
        "Standby por falta de tajo/Patio":             "#7D6608",
        "Operativo":                                   "#145A32",
        "Operativo parcial":                           "#7D6608",
        "Avería":                                      "#7B241C",
        "Mantención Programada":                       "#1A5276",
    }.get(estado, "#4B5563")
