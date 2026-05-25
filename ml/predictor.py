import pandas as pd

from ml.features import calcular_umbral_rendimiento, preparar_features, resumen_por_equipo


MIN_REGISTROS_ML = 100


def generar_predicciones(df):
    features = preparar_features(df)
    total_registros = len(features)
    modo = "heuristico"
    estado_modelo = (
        "Reglas heuristicas activas: se requieren al menos "
        f"{MIN_REGISTROS_ML} registros para entrenar ML real."
    )

    resumen = resumen_por_equipo(features)
    predicciones = _predicciones_heuristicas(resumen, features)
    return {
        "total_registros": total_registros,
        "modo": modo,
        "estado_modelo": estado_modelo,
        "variables": list(features.columns),
        "predicciones": predicciones,
        "advertencias": _advertencias(total_registros),
    }


def _predicciones_heuristicas(resumen_equipos, features):
    columnas = [
        "Equipo",
        "Riesgo baja utilización",
        "Riesgo bajo rendimiento",
        "Probabilidad turno improductivo",
        "Riesgo mantenimiento",
        "Recomendación operacional",
        "Base del análisis",
    ]
    if resumen_equipos is None or resumen_equipos.empty:
        return pd.DataFrame(columns=columnas)

    umbral_rendimiento = calcular_umbral_rendimiento(features)
    filas = []
    for _, equipo in resumen_equipos.iterrows():
        utilizacion = float(equipo.get("Utilización %", 0) or 0)
        rendimiento = float(equipo.get("Rendimiento m/h", 0) or 0)
        disponibilidad = float(equipo.get("Disponibilidad %", 0) or 0)
        metros = float(equipo.get("Metros perforados", 0) or 0)
        horas_efectivas = float(equipo.get("Horas efectivas perforando", 0) or 0)
        horas_no_efectivas = float(equipo.get("Horas detención No efectivas", 0) or 0)
        horas_averia = float(equipo.get("Horas detención mecánica", 0) or 0)

        riesgo_utilizacion = _riesgo_baja_utilizacion(utilizacion)
        riesgo_rendimiento = _riesgo_bajo_rendimiento(rendimiento, umbral_rendimiento)
        improductivo = _probabilidad_improductiva(metros, horas_efectivas, utilizacion)
        mantenimiento = "Alto" if disponibilidad < 70 or horas_averia > 0 else "Bajo"
        recomendacion = _recomendacion(
            riesgo_utilizacion,
            riesgo_rendimiento,
            improductivo,
            mantenimiento,
            horas_no_efectivas,
            horas_averia,
        )
        base = (
            f"Utilización {utilizacion:.2f}%, rendimiento {rendimiento:.2f} m/h, "
            f"disponibilidad {disponibilidad:.2f}%, metros {metros:.2f}"
        )
        filas.append({
            "Equipo": equipo.get("Equipo", ""),
            "Riesgo baja utilización": riesgo_utilizacion,
            "Riesgo bajo rendimiento": riesgo_rendimiento,
            "Probabilidad turno improductivo": improductivo,
            "Riesgo mantenimiento": mantenimiento,
            "Recomendación operacional": recomendacion,
            "Base del análisis": base,
        })

    return pd.DataFrame(filas, columns=columnas)


def _riesgo_baja_utilizacion(utilizacion):
    if utilizacion < 40:
        return "Alto"
    if utilizacion < 60:
        return "Medio"
    return "Bajo"


def _riesgo_bajo_rendimiento(rendimiento, umbral):
    if rendimiento <= 0:
        return "Alto"
    if rendimiento < umbral:
        return "Medio"
    return "Bajo"


def _probabilidad_improductiva(metros, horas_efectivas, utilizacion):
    if metros <= 0 and horas_efectivas <= 0:
        return "Alta"
    if utilizacion < 40:
        return "Media"
    return "Baja"


def _recomendacion(riesgo_utilizacion, riesgo_rendimiento, improductivo, mantenimiento, horas_no_efectivas, horas_averia):
    if mantenimiento == "Alto":
        return "Revisar disponibilidad, averías y condición mecánica antes de exigir producción."
    if improductivo == "Alta":
        return "Verificar disponibilidad de frente/tajo/patio y registrar causa operacional precisa."
    if riesgo_utilizacion == "Alto":
        return "Revisar distribución de horas no efectivas y continuidad operacional del turno."
    if riesgo_rendimiento in ("Alto", "Medio"):
        return "Revisar condición de terreno, parámetros de perforación y estado de aceros."
    if horas_no_efectivas > horas_averia and horas_no_efectivas > 0:
        return "Monitorear tiempos no efectivos para evitar caída de utilización."
    return "Sin alerta crítica según datos disponibles; mantener seguimiento operacional."


def _advertencias(total_registros):
    advertencias = ["Modelo de apoyo, no reemplaza criterio operacional."]
    if total_registros < MIN_REGISTROS_ML:
        advertencias.append(
            f"Base pequeña ({total_registros} registros): se usan reglas simples, no ML entrenado."
        )
    return advertencias
