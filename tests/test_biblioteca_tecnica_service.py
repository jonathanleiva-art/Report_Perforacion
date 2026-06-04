from contextlib import closing
import sqlite3

from services import documentation_service


PDF_VALIDO = b"%PDF-1.4\n%Biblioteca tecnica\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def _registrar_documento(db_path, root, **metadata):
    datos = {
        "titulo": "Manual Sandvik D75KS",
        "tipo_documento": "Manual de equipo",
        "equipo_asociado": "Sandvik D75KS",
        "categoria": "Manual",
        "criticidad": "Alta",
        "observacion": "Manual del equipo",
    }
    datos.update(metadata)
    return documentation_service.registrar_documento_biblioteca(
        datos,
        contenido_pdf=PDF_VALIDO,
        nombre_archivo=f"{datos['titulo']}.pdf",
        db_path=db_path,
        biblioteca_root=root,
    )


def test_crear_tabla_biblioteca_documentos(tmp_path):
    db_path = tmp_path / "reportes.db"

    documentation_service.asegurar_tabla_biblioteca_documentos(db_path=db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        columnas = {
            fila[1]
            for fila in connection.execute(
                "PRAGMA table_info(biblioteca_documentos)"
            ).fetchall()
        }

    assert "id_documento" in columnas
    assert "titulo" in columnas
    assert "ruta_archivo" in columnas
    assert "activo" in columnas


def test_registrar_documento_pdf_en_biblioteca(tmp_path):
    db_path = tmp_path / "reportes.db"
    root = tmp_path / "biblioteca_tecnica"

    documento = _registrar_documento(db_path, root)

    assert documento["titulo"] == "Manual Sandvik D75KS"
    assert documento["extension"] == ".pdf"
    assert documento["activo"] == 1
    assert (root / "manuales_equipos" / documento["nombre_archivo"]).exists()


def test_filtrar_biblioteca_por_equipo(tmp_path):
    db_path = tmp_path / "reportes.db"
    root = tmp_path / "biblioteca_tecnica"
    _registrar_documento(db_path, root, titulo="Manual D75KS", equipo_asociado="Sandvik D75KS")
    _registrar_documento(db_path, root, titulo="Manual D65", equipo_asociado="FlexiROC D65")

    documentos = documentation_service.listar_documentos_biblioteca(
        db_path=db_path,
        equipo_asociado="FlexiROC D65",
    )

    assert len(documentos) == 1
    assert documentos.iloc[0]["titulo"] == "Manual D65"


def test_filtrar_biblioteca_por_criticidad(tmp_path):
    db_path = tmp_path / "reportes.db"
    root = tmp_path / "biblioteca_tecnica"
    _registrar_documento(db_path, root, titulo="Checklist", criticidad="Media")
    _registrar_documento(db_path, root, titulo="Procedimiento crítico", criticidad="Crítica")

    documentos = documentation_service.listar_documentos_biblioteca(
        db_path=db_path,
        criticidad="Crítica",
    )

    assert len(documentos) == 1
    assert documentos.iloc[0]["titulo"] == "Procedimiento crítico"


def test_validar_pdf_biblioteca(tmp_path):
    assert documentation_service.validar_pdf_biblioteca("manual.pdf", PDF_VALIDO) is True
    assert documentation_service.validar_pdf_biblioteca("manual.txt", PDF_VALIDO) is False
    assert documentation_service.validar_pdf_biblioteca("manual.pdf", b"no es pdf") is False


def test_desactivar_documento_biblioteca(tmp_path):
    db_path = tmp_path / "reportes.db"
    root = tmp_path / "biblioteca_tecnica"
    documento = _registrar_documento(db_path, root)

    desactivado = documentation_service.desactivar_documento_biblioteca(
        documento["id_documento"],
        db_path=db_path,
    )
    activos = documentation_service.listar_documentos_biblioteca(db_path=db_path)

    assert desactivado["activo"] == 0
    assert activos.empty
