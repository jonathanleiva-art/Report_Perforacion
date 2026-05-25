"""Shared schema constants for the drilling report project.

This module is intentionally passive for now: existing modules do not import it
yet, so current Streamlit, Excel, PDF, charts, and form behavior is unchanged.
"""

# Official workbook column names.
COL_FECHA_TURNO = "Fecha turno"
COL_MODELO_EQUIPO = "Modelo equipo"
COL_NUMERO_EQUIPO = "Número equipo"
COL_OPERADOR = "Operador"
COL_TURNO = "Turno"
COL_CODIGO_OPERADOR = "Código operador"
COL_AREA_OPERACIONAL = "Área operacional"
COL_TIPO_DETENCION = "Tipo detención"
COL_CAUSA_DETENCION = "Causa detención"
COL_HORAS_TURNO = "Horas turno"
COL_HORAS_EFECTIVAS = "Horas efectivas perforando"
COL_HORAS_DETENCION_MECANICA = "Horas detención mecánica"
COL_HORAS_DETENCION_NO_EFECTIVAS = "Horas detención No efectivas"
COL_TOTAL_HORAS_INGRESADAS = "Total horas ingresadas"
COL_METROS_PERFORADOS = "Metros perforados"
COL_RENDIMIENTO = "Rendimiento m/h"
COL_DISPONIBILIDAD = "Disponibilidad %"
COL_UTILIZACION = "Utilización %"
COL_EQUIPO = "Equipo"

KEY_COLUMNS = [
    COL_FECHA_TURNO,
    COL_TURNO,
    COL_MODELO_EQUIPO,
    COL_NUMERO_EQUIPO,
    COL_OPERADOR,
]

KPI_COLUMNS = [
    COL_METROS_PERFORADOS,
    COL_HORAS_EFECTIVAS,
    COL_HORAS_DETENCION_MECANICA,
    COL_HORAS_DETENCION_NO_EFECTIVAS,
    COL_RENDIMIENTO,
    COL_DISPONIBILIDAD,
    COL_UTILIZACION,
]

OFFICIAL_KPI_COLUMNS = KPI_COLUMNS

COALESCE_DUPLICATE_COLUMNS = {
    COL_UTILIZACION,
}

DETENCION_HORAS_COLUMNAS = {
    "Falla Operacional": "Falla Operacional",
    "Avería mecánica": COL_HORAS_DETENCION_MECANICA,
    "Cambio de aceros": "Cambio de aceros",
    "Geología": "Geología",
    "Seguridad": "Seguridad",
    "Colación": "Colación",
    "Agua": "Relleno de agua",
    "Combustible": "Combustible",
    "Traslado": "Traslado",
    "Cambio Turno": "Cambio turno",
    "Standby por falta de tajo/Patio": "Standby por falta de tajo/Patio",
    "Sin marcación": "Sin marcación",
    "Mantención Programada": "Mantención Programada",
    "Tronadura": "Tronadura",
    "Falta operador": "Falta operador",
    "Otros": "Otros",
}

COLUMNAS_HORAS_DETENCION = list(dict.fromkeys(DETENCION_HORAS_COLUMNAS.values()))

# Legacy and mojibake column aliases found in historical workbooks.
COLUMNAS_CORREGIDAS = {
    'Número equipo': 'Número equipo',
    'Número equipo': 'Número equipo',
    'Código operador': 'Código operador',
    'Código operador': 'Código operador',
    'Área operacional': 'Área operacional',
    'Área operacional': 'Área operacional',
    'Petróleo litros': 'Petróleo litros',
    'Petróleo litros': 'Petróleo litros',
    'Horómetro inicial': 'Horómetro inicial',
    'Horómetro inicial': 'Horómetro inicial',
    'Horómetro final': 'Horómetro final',
    'Horómetro final': 'Horómetro final',
    'Diferencia horómetro': 'Diferencia horómetro',
    'Diferencia horómetro': 'Diferencia horómetro',
    'Tipo de perforación': 'Tipo de perforación',
    'Tipo de perforación': 'Tipo de perforación',
    'Condición del terreno': 'Condición del terreno',
    'Condición del terreno': 'Condición del terreno',
    'Tipo detención': 'Tipo detención',
    'Tipo detención': 'Tipo detención',
    'Causa detención': 'Causa detención',
    'Causa detención': 'Causa detención',
    'Horas detención mecánica': 'Horas detención mecánica',
    'Horas detención mecánica': 'Horas detención mecánica',
    'Horas detención No efectivas': 'Horas detención No efectivas',
    'Horas detención No efectivas': 'Horas detención No efectivas',
    'Colación': 'Colación',
    'Colación': 'Colación',
    'Mantención': 'Mantención Programada',
    'Mantención': 'Mantención Programada',
    'Mantención': 'Mantención Programada',
    'Avería': 'Avería',
    'Avería': 'Avería',
    'Utilización %': 'Utilización %',
    'Utilización %': 'Utilización %',
    'Utilizaci?n %': 'Utilización %',
    'Otros distribución': 'Otros',
    'Otros distribución': 'Otros',
    'Otros distribución': 'Otros',
    'Sin marcación': 'Standby por falta de tajo/Patio',
}

NUMERIC_COLUMNS = [
    "Petróleo litros",
    "Aceite litros",
    "Horómetro inicial",
    "Horómetro final",
    "Diferencia horómetro",
    "Horas de motor",
    "Número precorte",
    COL_HORAS_TURNO,
    COL_HORAS_DETENCION_MECANICA,
    COL_HORAS_DETENCION_NO_EFECTIVAS,
    COL_HORAS_EFECTIVAS,
    "Trabajando",
    "Combustible",
    "Relleno de agua",
    "Colación",
    "Traslado",
    "Traslado de sector",
    "Traslado pozo a pozo",
    "Traslado largo",
    "Standby por falta de tajo/Patio",
    "Falla Operacional",
    "Cambio de aceros",
    "Geología",
    "Seguridad",
    "Sin marcación",
    "Tronadura",
    "Mantención Programada",
    "Avería",
    "Cambio turno",
    "Falta operador",
    "Otros",
    "Total distribución turno",
    "Diferencia distribución",
    COL_TOTAL_HORAS_INGRESADAS,
    COL_METROS_PERFORADOS,
    "Cantidad pozos perforados",
    "Pozos perforados turno",
    COL_RENDIMIENTO,
    COL_DISPONIBILIDAD,
    COL_UTILIZACION,
]

TEXT_TAG_COLUMNS = [
    "Banco",
    "Malla",
    "Fase",
    "Condición del terreno",
    COL_TIPO_DETENCION,
    "Tipo de perforación",
]
