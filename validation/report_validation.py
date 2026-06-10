import pandas as pd

from schema import columnas_equivalentes
from utils import HORAS_TURNO, limpiar_entero


def numero_o_none(valor):
    numero = pd.to_numeric(pd.Series([valor]), errors="coerce").iloc[0]
    if pd.isna(numero):
        return None
    return float(numero)


def horas_turno_validas(total_horas, horas_turno=HORAS_TURNO):
    total = numero_o_none(total_horas)
    turno = numero_o_none(horas_turno)
    if total is None or turno is None:
        return False
    return abs(total - turno) <= 0.01


def mensaje_horas_turno_invalidas(total_horas, horas_turno=HORAS_TURNO):
    return f"No se puede guardar. El turno suma {float(total_horas):.2f} h y debe sumar {float(horas_turno):.2f} h."


def operador_valido(operador):
    return bool(str(operador or "").strip())


def mensaje_operador_vacio():
    return "Debe ingresar el nombre del operador."


def fecha_turno_valida(fecha_turno):
    if fecha_turno is None:
        return False
    return not pd.isna(pd.to_datetime(pd.Series([fecha_turno]), errors="coerce").iloc[0])


def turno_valido(turno):
    return bool(str(turno or "").strip())


def equipo_tiene_numero(numero_equipo):
    return bool(limpiar_entero(numero_equipo))


def metros_validos(metros):
    numero = numero_o_none(metros)
    return numero is not None and numero >= 0


def pozos_validos(pozos):
    numero = numero_o_none(pozos)
    return numero is not None and numero >= 0 and numero.is_integer()


def horometro_valido(inicial, final, diferencia=None):
    inicial_num = numero_o_none(inicial)
    final_num = numero_o_none(final)
    if inicial_num is None or final_num is None:
        return False
    if final_num < inicial_num:
        return False
    if diferencia is None:
        return True
    diferencia_num = numero_o_none(diferencia)
    if diferencia_num is None:
        return False
    return abs((final_num - inicial_num) - diferencia_num) <= 0.01


def valores_numericos_negativos(datos):
    negativos = {}
    for campo, valor in (datos or {}).items():
        numero = pd.to_numeric(pd.Series([valor]), errors="coerce").iloc[0]
        if pd.notna(numero) and float(numero) < 0:
            negativos[campo] = float(numero)
    return negativos


def campos_obligatorios_faltantes(datos, campos_obligatorios):
    faltantes = []
    for campo in campos_obligatorios:
        valor = (datos or {}).get(campo)
        if valor is None or not str(valor).strip():
            faltantes.append(campo)
    return faltantes


def mensaje_fecha_turno_invalida():
    return "Fecha turno vacía o inválida."


def mensaje_turno_vacio():
    return "Turno vacío."


def mensaje_equipo_sin_numero():
    return "Equipo sin número."


def mensaje_horometro_invalido():
    return "Horómetro inválido: el final debe ser mayor o igual al inicial y la diferencia debe coincidir."


def mensaje_metros_invalidos():
    return "Metros perforados vacíos o inválidos."


def mensaje_pozos_invalidos():
    return "Pozos perforados debe ser un número entero mayor o igual a cero."


def mensaje_valores_negativos(campos):
    return "Valores numéricos negativos: " + ", ".join(campos)


def existe_reporte_duplicado(df, fecha_turno, turno, modelo_equipo, numero_equipo, operador):
    if df.empty:
        return False

    fecha_col = buscar_columna(df, "fecha_turno")
    turno_col = buscar_columna(df, "turno")
    modelo_col = buscar_columna(df, "modelo_equipo")
    numero_col = buscar_columna(df, "numero_equipo")
    operador_col = buscar_columna(df, "operador")
    if not all([fecha_col, turno_col, modelo_col, numero_col, operador_col]):
        return False

    fechas = pd.to_datetime(df[fecha_col], errors="coerce").dt.date
    return bool(
        (
            fechas.eq(fecha_turno)
            & df[turno_col].astype(str).str.strip().eq(str(turno).strip())
            & df[modelo_col].astype(str).str.strip().eq(str(modelo_equipo).strip())
            & df[numero_col].astype(str).apply(limpiar_entero).eq(limpiar_entero(numero_equipo))
            & df[operador_col].astype(str).str.strip().eq(str(operador).strip())
        ).any()
    )


def buscar_columna(df, clave):
    for columna in columnas_equivalentes(clave):
        if columna in df.columns:
            return columna
    return None


def mensaje_reporte_duplicado():
    return "Ya existe un reporte registrado para este equipo, operador, turno y fecha."


def horas_sin_categorizar(horas_averia, horas_mantencion, horas_no_efectivas):
    return (
        float(horas_averia or 0) + float(horas_mantencion or 0) == 0
        and float(horas_no_efectivas or 0) > 0
    )


def turno_improductivo_sin_causa(
    horas_efectivas, metros, horas_averia, horas_mantencion,
    horas_standby, horas_tronadura, horas_no_efectivas,
):
    sin_produccion = float(metros or 0) == 0 and float(horas_efectivas or 0) == 0
    causas = (
        float(horas_averia or 0) + float(horas_mantencion or 0)
        + float(horas_standby or 0) + float(horas_tronadura or 0)
        + float(horas_no_efectivas or 0)
    )
    return sin_produccion and causas == 0


def mensaje_horas_sin_categorizar():
    return "Las horas de detención no están categorizadas. Revisa avería o mantención."


def mensaje_turno_sin_causa():
    return (
        "El turno no registra producción ni causa de no producción. "
        "Ingresa avería, mantención, standby, tronadura u otra causa."
    )


def validar_calidad_reporte(datos, df_historial=None):
    errores = []

    if not horas_turno_validas((datos or {}).get("Total horas ingresadas", 0)):
        errores.append(mensaje_horas_turno_invalidas((datos or {}).get("Total horas ingresadas", 0)))
    if not operador_valido((datos or {}).get("Operador")):
        errores.append(mensaje_operador_vacio())
    if not fecha_turno_valida((datos or {}).get("Fecha turno")):
        errores.append(mensaje_fecha_turno_invalida())
    if not turno_valido((datos or {}).get("Turno")):
        errores.append(mensaje_turno_vacio())
    if not equipo_tiene_numero((datos or {}).get("Número equipo", (datos or {}).get("Número equipo"))):
        errores.append(mensaje_equipo_sin_numero())
    if not metros_validos((datos or {}).get("Metros perforados", 0)):
        errores.append(mensaje_metros_invalidos())
    if not pozos_validos((datos or {}).get("Pozos perforados turno", 0)):
        errores.append(mensaje_pozos_invalidos())
    if not horometro_valido(
        (datos or {}).get("Horómetro inicial"),
        (datos or {}).get("Horómetro final"),
        (datos or {}).get("Diferencia horómetro"),
    ):
        errores.append(mensaje_horometro_invalido())

    negativos = valores_numericos_negativos(datos)
    if negativos:
        errores.append(mensaje_valores_negativos(negativos.keys()))

    if df_historial is not None and existe_reporte_duplicado(
        df_historial,
        (datos or {}).get("Fecha turno"),
        (datos or {}).get("Turno"),
        (datos or {}).get("Modelo equipo"),
        (datos or {}).get("Número equipo", (datos or {}).get("Número equipo")),
        (datos or {}).get("Operador"),
    ):
        errores.append(mensaje_reporte_duplicado())

    return errores
