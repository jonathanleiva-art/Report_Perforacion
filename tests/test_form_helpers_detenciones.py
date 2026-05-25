from ui.form_helpers import detenciones_seleccionadas_por_hora


def test_detencion_cambio_de_aceros_se_mapea_a_horas():
    seleccionadas = detenciones_seleccionadas_por_hora(["Cambio de aceros"])

    assert "horas_cambios_aceros" in seleccionadas


def test_detencion_cambios_de_aceros_tambien_se_mapea_a_horas():
    seleccionadas = detenciones_seleccionadas_por_hora(["Cambios de aceros"])

    assert "horas_cambios_aceros" in seleccionadas
