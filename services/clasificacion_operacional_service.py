from unicodedata import normalize

import pandas as pd

import db


TIPOS_SECTOR = ("Producción", "Buffer 1", "Buffer 2", "Precorte", "Borde", "Otro")
COLUMNAS_CLASIFICACION = ["tipo_sector", "numero_precorte", "identificador_sector"]
COLUMNAS_REGISTRO = [
    "id",
    "Fecha turno",
    "Turno",
    "Número equipo",
    "Operador",
    "Fase",
    "Banco",
    "Malla",
    *COLUMNAS_CLASIFICACION,
]


def _texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _clave(valor):
    texto = normalize("NFKD", _texto(valor)).encode("ascii", "ignore").decode("ascii").lower().strip()
    if texto.startswith("producci"):
        return "produccion"
    return texto


def clasificacion_inferida(tipo_sector, malla):
    tipo = _texto(tipo_sector)
    if tipo:
        return tipo
    if _texto(malla):
        return "Producción"
    return "Sin clasificar"


def validar_clasificacion_registro(tipo_sector, malla="", numero_precorte="", identificador_sector=""):
    errores = []
    tipo = _texto(tipo_sector)
    if tipo and tipo not in TIPOS_SECTOR:
        errores.append("Tipo de sector no permitido.")
    if tipo == "Precorte" and not _texto(numero_precorte):
        errores.append("Si el registro es Precorte, debe ingresar número de precorte.")
    if tipo == "Producción" and not _texto(malla):
        errores.append("Si el registro es Producción, debe tener malla asociada.")
    if tipo == "Otro" and not _texto(identificador_sector):
        errores.append("Si el registro es Otro, debe ingresar identificador de sector.")
    return {"ok": not errores, "errores": errores}


def _asegurar_columnas(db_path):
    db.crear_tablas(db_path=db_path, columnas=COLUMNAS_CLASIFICACION)


def listar_registros_clasificacion(db_path=db.DB_PATH, solo_sin_clasificar=False, limit=300):
    _asegurar_columnas(db_path)
    with db.conectar_db(db_path) as connection:
        columnas_existentes = set(db.columnas_tabla(connection, db.TABLA_REGISTROS))
        columnas = [col for col in COLUMNAS_REGISTRO if col in columnas_existentes]
        if "id" not in columnas:
            return pd.DataFrame(columns=[*COLUMNAS_REGISTRO, "clasificacion_operacional"])
        sql = (
            f"SELECT {', '.join(db.quote_identifier(col) for col in columnas)} "
            f"FROM {db.quote_identifier(db.TABLA_REGISTROS)} ORDER BY id DESC"
        )
        if limit:
            sql += " LIMIT ?"
            df = pd.read_sql_query(sql, connection, params=[int(limit)])
        else:
            df = pd.read_sql_query(sql, connection)

    for columna in COLUMNAS_REGISTRO:
        if columna not in df.columns:
            df[columna] = ""
    df["clasificacion_operacional"] = df.apply(
        lambda fila: clasificacion_inferida(fila.get("tipo_sector"), fila.get("Malla")),
        axis=1,
    )
    if solo_sin_clasificar:
        mascara = df["clasificacion_operacional"].map(_clave).eq("sin clasificar")
        df = df[mascara].reset_index(drop=True)
    return df


def resumen_clasificacion_operacional(db_path=db.DB_PATH):
    df = listar_registros_clasificacion(db_path=db_path, limit=0)
    if df.empty:
        return {
            "total_registros": 0,
            "con_tipo_sector": 0,
            "inferidos_produccion": 0,
            "sin_clasificar": 0,
            "precorte_sin_numero": 0,
            "otro_sin_identificador": 0,
        }

    tipo = df["tipo_sector"].fillna("").astype(str).str.strip()
    malla = df["Malla"].fillna("").astype(str).str.strip()
    clasificacion = df["clasificacion_operacional"].fillna("").astype(str)
    numero_precorte = df["numero_precorte"].fillna("").astype(str).str.strip()
    identificador = df["identificador_sector"].fillna("").astype(str).str.strip()
    return {
        "total_registros": int(len(df)),
        "con_tipo_sector": int(tipo.ne("").sum()),
        "inferidos_produccion": int((tipo.eq("") & malla.ne("")).sum()),
        "sin_clasificar": int(clasificacion.map(_clave).eq("sin clasificar").sum()),
        "precorte_sin_numero": int((tipo.eq("Precorte") & numero_precorte.eq("")).sum()),
        "otro_sin_identificador": int((tipo.eq("Otro") & identificador.eq("")).sum()),
    }


def actualizar_clasificacion_registro(
    registro_id,
    tipo_sector,
    numero_precorte="",
    identificador_sector="",
    motivo="",
    usuario="",
    db_path=db.DB_PATH,
):
    _asegurar_columnas(db_path)
    with db.conectar_db(db_path) as connection:
        fila = connection.execute(
            f"SELECT * FROM {db.quote_identifier(db.TABLA_REGISTROS)} WHERE id = ?",
            (int(registro_id),),
        ).fetchone()
    if not fila:
        return {"ok": False, "mensaje": "El registro operacional no existe.", "actualizados": 0, "auditoria": 0}

    registro = dict(fila)
    tipo = _texto(tipo_sector)
    cambios = {
        "tipo_sector": tipo,
        "numero_precorte": _texto(numero_precorte) if tipo == "Precorte" else "",
        "identificador_sector": _texto(identificador_sector),
    }
    validacion = validar_clasificacion_registro(
        tipo,
        malla=registro.get("Malla", ""),
        numero_precorte=cambios.get("numero_precorte", ""),
        identificador_sector=cambios["identificador_sector"],
    )
    if not validacion["ok"]:
        return {"ok": False, "mensaje": " | ".join(validacion["errores"]), "actualizados": 0, "auditoria": 0}

    try:
        resultado = db.actualizar_registro_auditado(
            registro_id,
            cambios,
            motivo=motivo,
            usuario=usuario,
            db_path=db_path,
        )
    except ValueError as exc:
        return {"ok": False, "mensaje": str(exc), "actualizados": 0, "auditoria": 0}

    try:
        db.upsert_clasificacion_operacional(
            registro_id,
            tipo_sector=cambios["tipo_sector"],
            numero_precorte=cambios["numero_precorte"],
            identificador_sector=cambios["identificador_sector"],
            usuario=usuario,
            db_path=db_path,
        )
    except Exception as _exc:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "dual-write clasificacion_operacional fallido registro_id=%s: %s", registro_id, _exc
        )

    return {
        "ok": True,
        "mensaje": "Clasificación operacional actualizada correctamente.",
        "actualizados": resultado["actualizados"],
        "auditoria": resultado["auditoria"],
        "campos": resultado["campos"],
    }
