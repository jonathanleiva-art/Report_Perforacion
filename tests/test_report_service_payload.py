from services.report_service import construir_datos_registro


EXPECTED_KEYS = [
    "Modelo equipo",
    "Número equipo",
    "Operador",
    "Turno",
    "Código operador",
    "Fecha turno",
    "Área operacional",
    "Petróleo litros",
    "Horómetro inicial",
    "Horómetro final",
    "Diferencia horómetro",
    "Horas de motor",
    "Banco",
    "Malla",
    "Fase",
    "Tipo de perforación",
    "Número precorte",
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
    "Standby por falta de tajo/Patio",
    "Tronadura",
    "Mantención Programada",
    "Cambio de aceros",
    "Avería",
    "Cambio turno",
    "Falta operador",
    "Otros",
    "Total horas ingresadas",
    "Metros perforados",
    "Pozos perforados turno",
    "Rendimiento m/h",
    "Disponibilidad %",
    "Utilización",
    "Observaciones",
    "Estatus del Equipo",
]


def datos_formulario_base(tipo_perforacion=None, numero_precorte=7):
    return {
        "identificacion": {
            "modelo_equipo": "FlexiROC D65",
            "numero_equipo": "9274",
            "operador": "Valeria Millan",
            "turno": "Noche",
            "codigo_operador": "M-0001",
            "fecha_turno": "2026-05-23",
            "area_operacional": "Proyecto DES",
        },
        "ubicacion": {
            "banco": ["2360"],
            "malla": ["254"],
            "fase": ["2"],
            "tipo_perforacion": tipo_perforacion or ["Precorte", "Buffer 2"],
            "numero_precorte": numero_precorte,
            "numero_bit": "BIT-123",
            "condicion_terreno": ["Blando", "Estable"],
        },
        "produccion": {
            "petroleo": 10.0,
            "horometro_inicial": 100.0,
            "horometro_final": 112.0,
            "diferencia_horometro": 12.0,
            "tipo_detencion": ["Combustible", "Traslado"],
            "causa_detencion": "Sin detencion critica",
            "metros": 120.5,
            "pozos": 8,
            "observaciones": "Turno de prueba",
            "estatus_equipo": "En observación",
        },
        "horas": {
            "horas_averia": 0.5,
            "horas_no_efectivas": 1.5,
            "horas_efectivas": 10.0,
            "horas_combustible": 0.5,
            "horas_agua": 0.0,
            "horas_colacion": 0.5,
            "horas_traslado": 0.5,
            "horas_standby": 0.0,
            "horas_tronadura": 0.0,
            "horas_mantencion": 0.0,
            "horas_cambio_turno": 0.0,
            "horas_falta_operador": 0.0,
            "horas_otros": 0.0,
            "total_horas": 12.0,
        },
        "kpi": {
            "rendimiento_turno": 12.049,
            "disponibilidad": 95.555,
            "utilizacion": 83.333,
        },
    }


def test_construir_datos_registro_mantiene_claves_oficiales_y_cantidad():
    payload = construir_datos_registro(datos_formulario_base())

    assert list(payload.keys()) == EXPECTED_KEYS
    assert len(payload) == 44


def test_construir_datos_registro_con_precorte_mantiene_numero_precorte():
    payload = construir_datos_registro(
        datos_formulario_base(tipo_perforacion=["Precorte"], numero_precorte=11)
    )

    assert payload["Tipo de perforación"] == "Precorte"
    assert payload["Número precorte"] == 11


def test_construir_datos_registro_sin_precorte_deja_numero_precorte_vacio():
    payload = construir_datos_registro(
        datos_formulario_base(tipo_perforacion=["Producción"], numero_precorte=11)
    )

    assert payload["Tipo de perforación"] == "Producción"
    assert payload["Número precorte"] == ""


def test_construir_datos_registro_mantiene_valores_principales():
    payload = construir_datos_registro(datos_formulario_base())

    assert payload["Modelo equipo"] == "FlexiROC D65"
    assert payload["Número equipo"] == "9274"
    assert payload["Operador"] == "Valeria Millan"
    assert payload["Turno"] == "Noche"
    assert payload["Banco"] == "2360"
    assert payload["Malla"] == "254"
    assert payload["Fase"] == "2"
    assert payload["Condición del terreno"] == "Blando, Estable"
    assert payload["Tipo detención"] == "Combustible, Traslado"
    assert payload["Horas efectivas perforando"] == 10.0
    assert payload["Total horas ingresadas"] == 12.0
    assert payload["Metros perforados"] == 120.5
    assert payload["Pozos perforados turno"] == 8
    assert payload["Rendimiento m/h"] == 12.05
    assert payload["Disponibilidad %"] == 95.56
    assert payload["Utilización"] == 83.33
    assert payload["Observaciones"] == (
        "Turno de prueba\nCausa detención histórica: Sin detencion critica"
    )
    assert payload["Estatus del Equipo"] == "En observación"
