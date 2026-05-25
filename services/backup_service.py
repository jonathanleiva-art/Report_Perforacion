from datetime import datetime
from io import BytesIO
from pathlib import Path
import shutil

import pandas as pd

import db
from config import BACKUP_DIR, BASE_DIR, EXCEL_PATH, REPORTES_PDF_DIR
from data import preparar_dataframe


CONTRATO_DATOS_PATH = BASE_DIR / "CONTRATO_DATOS.md"


def timestamp_respaldo():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ruta_unica(path):
    path = Path(path)
    if not path.exists():
        return path

    indice = 1
    while True:
        candidata = path.with_name(f"{path.stem}_{indice}{path.suffix}")
        if not candidata.exists():
            return candidata
        indice += 1


def respaldar_archivo(origen, prefijo, backup_dir=BACKUP_DIR, timestamp=None):
    origen = Path(origen)
    if not origen.exists():
        return None

    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    marca = timestamp or timestamp_respaldo()
    destino = ruta_unica(backup_dir / f"{prefijo}_{marca}{origen.suffix}")
    shutil.copy2(origen, destino)
    return destino


def respaldar_carpeta_zip(origen, prefijo, backup_dir=BACKUP_DIR, timestamp=None):
    origen = Path(origen)
    if not origen.exists() or not origen.is_dir():
        return None

    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    marca = timestamp or timestamp_respaldo()
    destino = ruta_unica(backup_dir / f"{prefijo}_{marca}.zip")
    base_name = destino.with_suffix("")
    shutil.make_archive(str(base_name), "zip", root_dir=origen)
    generado = base_name.with_suffix(".zip")
    if generado != destino and generado.exists():
        generado.rename(destino)
    return destino


def generar_respaldo_manual(
    db_path=db.DB_PATH,
    excel_path=EXCEL_PATH,
    reportes_pdf_dir=REPORTES_PDF_DIR,
    backup_dir=BACKUP_DIR,
    incluir_sqlite=True,
    incluir_excel=True,
    incluir_pdf=True,
):
    marca = timestamp_respaldo()
    respaldos = []

    if incluir_sqlite:
        respaldos.append({
            "tipo": "SQLite",
            "ruta": respaldar_archivo(db_path, "sqlite_reportes_perforacion", backup_dir, marca),
        })
    if incluir_excel:
        respaldos.append({
            "tipo": "Excel operacional",
            "ruta": respaldar_archivo(excel_path, "excel_reportes_perforacion", backup_dir, marca),
        })
    if incluir_pdf:
        respaldos.append({
            "tipo": "Reportes PDF",
            "ruta": respaldar_carpeta_zip(reportes_pdf_dir, "reportes_pdf", backup_dir, marca),
        })

    return [item for item in respaldos if item["ruta"] is not None]


def listar_respaldos(backup_dir=BACKUP_DIR):
    backup_dir = Path(backup_dir)
    columnas = ["nombre", "ruta", "tipo", "tamano_bytes", "fecha_modificacion"]
    if not backup_dir.exists():
        return pd.DataFrame(columns=columnas)

    filas = []
    for path in sorted(backup_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        filas.append({
            "nombre": path.name,
            "ruta": str(path),
            "tipo": tipo_respaldo(path),
            "tamano_bytes": path.stat().st_size,
            "fecha_modificacion": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        })
    return pd.DataFrame(filas, columns=columnas)


def tipo_respaldo(path):
    nombre = Path(path).name.lower()
    if nombre.startswith("sqlite_") or nombre.endswith(".db") or nombre.endswith(".sqlite"):
        return "SQLite"
    if nombre.startswith("excel_") or nombre.endswith(".xlsx"):
        return "Excel"
    if nombre.startswith("reportes_pdf") or nombre.endswith(".zip"):
        return "PDF ZIP"
    return "Archivo"


def dataframe_a_excel_bytes(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.getvalue()


def exportar_datos_filtrados_excel(
    filtros,
    db_path=db.DB_PATH,
    backup_dir=BACKUP_DIR,
):
    df = db.consultar_historial_filtrado(db_path=db_path, **(filtros or {}))
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    destino = ruta_unica(backup_dir / f"export_reportes_filtrados_{timestamp_respaldo()}.xlsx")
    df.to_excel(destino, index=False)
    return destino, df


def exportar_auditoria_ediciones_excel(
    db_path=db.DB_PATH,
    backup_dir=BACKUP_DIR,
):
    df = db.leer_auditoria_ediciones(db_path=db_path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    destino = ruta_unica(backup_dir / f"export_auditoria_ediciones_{timestamp_respaldo()}.xlsx")
    df.to_excel(destino, index=False)
    return destino, df


def contar_registros_excel(excel_path=EXCEL_PATH):
    path = Path(excel_path)
    if not path.exists():
        return 0
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception:
        return 0
    return len(preparar_dataframe(df))


def obtener_fecha_ultimo_registro(db_path=db.DB_PATH):
    df = db.leer_registros(db_path=db_path)
    if df.empty or "Fecha turno" not in df.columns:
        return ""
    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce").dropna()
    if fechas.empty:
        return ""
    return fechas.max().date().isoformat()


def verificar_integridad(db_path=db.DB_PATH, excel_path=EXCEL_PATH):
    existe_db = Path(db_path).exists()
    existe_excel = Path(excel_path).exists()
    registros_sqlite = db.contar_registros(db_path=db_path) if existe_db else 0
    registros_excel = contar_registros_excel(excel_path) if existe_excel else 0
    auditorias = len(db.leer_auditoria_ediciones(db_path=db_path)) if existe_db else 0

    return {
        "existe_base_datos": existe_db,
        "existe_excel": existe_excel,
        "registros_sqlite": registros_sqlite,
        "registros_excel": registros_excel,
        "fecha_ultimo_registro": obtener_fecha_ultimo_registro(db_path) if existe_db else "",
        "auditorias_ediciones": auditorias,
    }


def leer_contrato_datos(path=CONTRATO_DATOS_PATH):
    path = Path(path)
    if not path.exists():
        return b""
    return path.read_bytes()
