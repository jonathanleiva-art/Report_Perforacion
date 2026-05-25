"""
Esquema formal del sistema de reportes de perforacion.

Este modulo es pasivo: declara columnas, aliases y tipos esperados sin cambiar
la lectura/escritura actual basada en Excel.
"""

SQLITE_TABLE_REPORTES = "reportes"

DATE_COLUMNS = [
    "Fecha turno",
]

TIME_COLUMNS = [
    "Hora registro",
]

TEXT_COLUMNS = [
    "Modelo equipo",
    "Número equipo",
    "Operador",
    "Turno",
    "Código operador",
    "Área operacional",
    "Banco",
    "Malla",
    "Fase",
    "Tipo de perforación",
    "Número serie Tricono/Bit",
    "Condición del terreno",
    "Tipo detención",
    "Causa detención",
    "Observaciones",
    "Descripción avería equipo",
    "Observación estado equipo",
    "Equipo",
    "Fecha",
]

TEXT_TAG_COLUMNS = [
    "Banco",
    "Malla",
    "Fase",
    "Condición del terreno",
    "Tipo detención",
    "Tipo de perforación",
]

INTEGER_COLUMNS = [
    "Petróleo litros",
    "Aceite litros",
    "Horómetro inicial",
    "Horómetro final",
    "Diferencia horómetro",
    "Horas de motor",
    "Número precorte",
    "Horas turno",
    "Tronadura",
    "Falta operador",
    "Total horas ingresadas",
    "Total distribución turno",
    "Diferencia distribución",
    "Cantidad pozos perforados",
    "Pozos perforados turno",
    "Falla Operacional",
    "Geología",
    "Seguridad",
]

REAL_COLUMNS = [
    "Horas detención mecánica",
    "Horas detención No efectivas",
    "Horas efectivas perforando",
    "Trabajando",
    "Combustible",
    "Relleno de agua",
    "Colación",
    "Traslado",
    "Traslado de sector",
    "Traslado pozo a pozo",
    "Traslado largo",
    "Standby por falta de tajo/Patio",
    "Cambio de aceros",
    "Sin marcación",
    "Mantención Programada",
    "Avería",
    "Cambio turno",
    "Otros",
    "Metros perforados",
    "Metros totales operador",
    "Metros totales por equipo",
    "Rendimiento m/h",
    "Disponibilidad %",
    "Utilización %",
]

NUMERIC_COLUMNS = [
    *INTEGER_COLUMNS,
    *REAL_COLUMNS,
]

KPI_COLUMNS = [
    "Horas turno",
    "Horas efectivas perforando",
    "Trabajando",
    "Metros perforados",
    "Rendimiento m/h",
    "Disponibilidad %",
    "Utilización %",
    "Pozos perforados turno",
    "Metros totales operador",
    "Metros totales por equipo",
]

OPTIONAL_COLUMNS = [
    "Banco",
    "Malla",
    "Tipo de perforación",
    "Número serie Tricono/Bit",
    "Condición del terreno",
    "Causa detención",
    "Observaciones",
    "Descripción avería equipo",
    "Observación estado equipo",
    "Fecha",
    "Hora registro",
    "Metros totales operador",
    "Metros totales por equipo",
]

HISTORICAL_COMPATIBILITY_COLUMNS = [
    "Utilizaci?n %",
    "Cantidad pozos perforados",
    "Sin marcación",
]

OFFICIAL_COLUMNS = [
    "Fecha turno",
    "Modelo equipo",
    "Número equipo",
    "Operador",
    "Turno",
    "Código operador",
    "Área operacional",
    "Petróleo litros",
    "Aceite litros",
    "Horómetro inicial",
    "Horómetro final",
    "Diferencia horómetro",
    "Banco",
    "Malla",
    "Fase",
    "Horas turno",
    "Tipo de perforación",
    "Número serie Tricono/Bit",
    "Condición del terreno",
    "Tipo detención",
    "Causa detención",
    "Horas detención mecánica",
    "Horas detención No efectivas",
    "Horas efectivas perforando",
    "Combustible",
    "Relleno de agua",
    "Colación",
    "Traslado",
    "Tronadura",
    "Mantención Programada",
    "Avería",
    "Total horas ingresadas",
    "Metros perforados",
    "Rendimiento m/h",
    "Disponibilidad %",
    "Utilización %",
    "Cambio turno",
    "Falta operador",
    "Otros",
    "Standby por falta de tajo/Patio",
    "Total distribución turno",
    "Diferencia distribución",
    "Observaciones",
    "Trabajando",
    "Pozos perforados turno",
    "Descripción avería equipo",
    "Observación estado equipo",
    "Traslado de sector",
    "Traslado pozo a pozo",
    "Traslado largo",
    "Metros totales operador",
    "Metros totales por equipo",
    "Equipo",
    "Fecha",
    "Hora registro",
    "Horas de motor",
    "Número precorte",
    "Falla Operacional",
    "Cambio de aceros",
    "Geología",
    "Seguridad",
]

NORMALIZED_DATAFRAME_COLUMNS = [
    *OFFICIAL_COLUMNS[:52],
    "Utilizaci?n %",
    *OFFICIAL_COLUMNS[52:],
]

COLUMN_ALIASES = {
    "Número equipo": "Número equipo",
    "Número equipo": "Número equipo",
    "Código operador": "Código operador",
    "Código operador": "Código operador",
    "Área operacional": "Área operacional",
    "Área operacional": "Área operacional",
    "Petróleo litros": "Petróleo litros",
    "Petróleo litros": "Petróleo litros",
    "Horómetro inicial": "Horómetro inicial",
    "Horómetro inicial": "Horómetro inicial",
    "Horómetro final": "Horómetro final",
    "Horómetro final": "Horómetro final",
    "Diferencia horómetro": "Diferencia horómetro",
    "Diferencia horómetro": "Diferencia horómetro",
    "Tipo de perforación": "Tipo de perforación",
    "Tipo de perforación": "Tipo de perforación",
    "Condición del terreno": "Condición del terreno",
    "Condición del terreno": "Condición del terreno",
    "Tipo detención": "Tipo detención",
    "Tipo detención": "Tipo detención",
    "Causa detención": "Causa detención",
    "Causa detención": "Causa detención",
    "Horas detención mecánica": "Horas detención mecánica",
    "Horas detención mecánica": "Horas detención mecánica",
    "Horas detención No efectivas": "Horas detención No efectivas",
    "Horas detención No efectivas": "Horas detención No efectivas",
    "Colación": "Colación",
    "Colación": "Colación",
    "Mantención": "Mantención Programada",
    "Mantención": "Mantención Programada",
    "Mantención": "Mantención Programada",
    "Avería": "Avería",
    "Avería": "Avería",
    "Utilización %": "Utilización %",
    "Utilización %": "Utilización %",
    "Utilizaci?n %": "Utilización %",
    "Otros distribución": "Otros",
    "Otros distribución": "Otros",
    "Otros distribución": "Otros",
    "Sin marcación": "Standby por falta de tajo/Patio",
}

EXPECTED_TYPES = {
    **{column: "DATE/TEXT ISO" for column in DATE_COLUMNS},
    **{column: "TEXT" for column in TIME_COLUMNS},
    **{column: "TEXT" for column in TEXT_COLUMNS},
    **{column: "INTEGER" for column in INTEGER_COLUMNS},
    **{column: "REAL" for column in REAL_COLUMNS},
    "Utilizaci?n %": "REAL",
}

SQLITE_TYPES = {
    column: (
        "TEXT"
        if expected_type == "DATE/TEXT ISO"
        else expected_type
    )
    for column, expected_type in EXPECTED_TYPES.items()
}

SQLITE_TECHNICAL_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "created_at": "TEXT",
    "updated_at": "TEXT",
    "source": "TEXT",
    "source_row": "INTEGER",
}

MODERN_COLUMN_ALIASES = {
    "Número equipo": "Número equipo",
    "Código operador": "Código operador",
    "Área operacional": "Área operacional",
    "Área operacional": "Área operacional",
    "Petróleo litros": "Petróleo litros",
    "Horómetro inicial": "Horómetro inicial",
    "Horómetro final": "Horómetro final",
    "Diferencia horómetro": "Diferencia horómetro",
    "Tipo de perforación": "Tipo de perforación",
    "Condición del terreno": "Condición del terreno",
    "Tipo detención": "Tipo detención",
    "Causa detención": "Causa detención",
    "Horas detención mecánica": "Horas detención mecánica",
    "Horas detención No efectivas": "Horas detención No efectivas",
    "Colación": "Colación",
    "Mantención": "Mantención Programada",
    "Mantención": "Mantención Programada",
    "Mantención Programada": "Mantención Programada",
    "Avería": "Avería",
    "Utilización %": "Utilización %",
    "C?digo operador": "Código operador",
    "Número precorte": "Número precorte",
    "Número serie Tricono/Bit": "Número serie Tricono/Bit",
    "Otros distribución": "Otros",
    "Otros distribución": "Otros",
    "Sin marcación": "Standby por falta de tajo/Patio",
}

COLUMN_ALIASES.update(MODERN_COLUMN_ALIASES)

COLUMN_EQUIVALENTS = {
    "numero_equipo": ["Número equipo", "Número equipo"],
    "modelo_equipo": ["Modelo equipo"],
    "operador": ["Operador"],
    "turno": ["Turno"],
    "fecha_turno": ["Fecha turno"],
    "metros_perforados": ["Metros perforados"],
    "pozos_perforados": ["Pozos perforados turno", "Cantidad pozos perforados"],
    "horas_efectivas": ["Horas efectivas perforando"],
    "horas_no_efectivas": ["Horas detención No efectivas", "Horas detención No efectivas"],
    "horas_averia": ["Horas detención mecánica", "Horas detención mecánica", "Avería", "Avería"],
    "horas_mantencion": ["Mantención Programada", "Mantención Programada", "Mantencion Programada", "Mantención", "Mantención"],
    "horas_standby": ["Standby por falta de tajo/Patio"],
    "sin_marcacion": ["Sin marcación", "Sin marcación"],
    "utilizacion": ["Utilización %", "Utilización %", "Utilizacion %", "Utilizaci?n %"],
    "disponibilidad": ["Disponibilidad %"],
    "rendimiento": ["Rendimiento m/h"],
}


def columnas_equivalentes(clave):
    return COLUMN_EQUIVALENTS.get(clave, [clave])


def alias_columna(nombre):
    texto = str(nombre).strip()
    return COLUMN_ALIASES.get(texto, texto)


def aliases_columnas():
    return COLUMN_ALIASES.copy()


MODERN_NUMERIC_COLUMNS = [
    "Petróleo litros",
    "Horómetro inicial",
    "Horómetro final",
    "Diferencia horómetro",
    "Número precorte",
    "Horas detención mecánica",
    "Horas detención No efectivas",
    "Colación",
    "Sin marcación",
    "Mantención Programada",
    "Avería",
    "Total distribución turno",
    "Diferencia distribución",
    "Utilización %",
]

for _column in MODERN_NUMERIC_COLUMNS:
    if _column not in NUMERIC_COLUMNS:
        NUMERIC_COLUMNS.append(_column)

MODERN_TEXT_TAG_COLUMNS = [
    "Condición del terreno",
    "Tipo detención",
    "Tipo de perforación",
]

for _column in MODERN_TEXT_TAG_COLUMNS:
    if _column not in TEXT_TAG_COLUMNS:
        TEXT_TAG_COLUMNS.append(_column)
