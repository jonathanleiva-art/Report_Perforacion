"""Operational catalogs for the drilling report project.

This module is passive for now. Existing modules still import these catalogs
from utils.py, so application behavior remains unchanged.
"""

EQUIPOS = {
    "Sandvik D75KS": ["9245", "9277"],
    "SmartROC D65": ["9239"],
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

TURNOS = ["Día", "Noche"]

MALLAS_BASE = [str(numero) for numero in range(107, 126)]

FASES_BASE = [str(numero) for numero in range(1, 9)]

TIPOS_PERFORACION = [
    "Producción",
    "Precorte",
    "Buffer 1",
    "Buffer 2",
    "Repaso",
    "Borde",
    "Auxiliares",
]

CONDICIONES_TERRENO = [
    "Blando",
    "Medio",
    "Duro",
    "Fracturado",
    "Inestable",
    "Relleno",
    "Con presencia de agua",
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
