from pathlib import Path

from services import documentation_service


def _crear_documentos_base(docs_root):
    (docs_root / "manuales").mkdir(parents=True, exist_ok=True)
    (docs_root / "seguridad").mkdir(parents=True, exist_ok=True)
    (docs_root / "procedimientos").mkdir(parents=True, exist_ok=True)

    pdf_path = docs_root / "manuales" / "Manual_FlexiROC_v1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%Biblioteca tecnica\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

    md_path = docs_root / "seguridad" / "Seguridad_Operacional.md"
    md_path.write_text("# Seguridad operacional\n\nDocumento de prueba.", encoding="utf-8")

    txt_path = docs_root / "procedimientos" / "Procedimiento_Cambio_Broca.txt"
    txt_path.write_text("Procedimiento de prueba.", encoding="utf-8")

    return pdf_path, md_path, txt_path


def test_asegurar_estructura_y_sincronizar_biblioteca(tmp_path):
    docs_root = tmp_path / "docs"
    db_path = tmp_path / "biblioteca.sqlite"

    base = documentation_service.asegurar_estructura_documental(docs_root)
    assert (base / "manuales").exists()
    assert (base / "procedimientos").exists()
    assert (base / "seguridad").exists()
    assert (base / "capacitaciones").exists()
    assert (base / "troubleshooting").exists()

    pdf_path, md_path, txt_path = _crear_documentos_base(docs_root)
    cantidad = documentation_service.sincronizar_biblioteca_documental(db_path=db_path, docs_root=docs_root)
    assert cantidad >= 3

    df = documentation_service.listar_documentos(db_path=db_path, docs_root=docs_root)
    assert len(df) >= 3
    assert set(Path(ruta).name for ruta in df["ruta_absoluta"].astype(str)) >= {pdf_path.name, md_path.name, txt_path.name}
    assert "archivo_existe" in df.columns


def test_registrar_documento_y_filtros_por_metadata(tmp_path):
    docs_root = tmp_path / "docs"
    db_path = tmp_path / "biblioteca.sqlite"
    pdf_path, _, _ = _crear_documentos_base(docs_root)

    documento = documentation_service.registrar_documento(
        {
            "ruta_relativa": pdf_path.relative_to(docs_root).as_posix(),
            "nombre": "Manual FlexiROC D65",
            "categoria": "Manual fabricante",
            "fabricante": "Epiroc",
            "equipo_asociado": "FlexiROC D65 9272",
            "version": "v1.0",
            "fecha_documento": "2026-05-20",
            "tipo_documento": "PDF",
            "palabras_clave": "FlexiROC, manual, perforación",
            "criticidad": "Alta",
            "autor_responsable": "Ingeniería Mina",
            "descripcion": "Manual técnico del equipo.",
        },
        db_path=db_path,
        docs_root=docs_root,
    )

    assert documento["fabricante"] == "Epiroc"
    assert documento["criticidad"] == "Alta"

    por_categoria = documentation_service.listar_documentos(
        db_path=db_path,
        docs_root=docs_root,
        categoria=["Manual fabricante"],
    )
    assert len(por_categoria) == 1

    por_fabricante = documentation_service.listar_documentos(
        db_path=db_path,
        docs_root=docs_root,
        fabricante=["Epiroc"],
    )
    assert len(por_fabricante) == 1

    por_equipo = documentation_service.listar_documentos(
        db_path=db_path,
        docs_root=docs_root,
        equipo=["FlexiROC D65 9272"],
    )
    assert len(por_equipo) == 1

    por_busqueda = documentation_service.listar_documentos(
        db_path=db_path,
        docs_root=docs_root,
        buscar="perforación",
    )
    assert len(por_busqueda) == 1

    categorias = documentation_service.obtener_categorias_documentales(db_path=db_path, docs_root=docs_root)
    fabricantes = documentation_service.obtener_fabricantes_documentales(db_path=db_path, docs_root=docs_root)
    equipos = documentation_service.obtener_equipos_documentales(db_path=db_path, docs_root=docs_root)
    criticidades = documentation_service.obtener_criticidades_documentales(db_path=db_path, docs_root=docs_root)

    assert "Manual fabricante" in categorias
    assert "Epiroc" in fabricantes
    assert "FlexiROC D65 9272" in equipos
    assert "Alta" in criticidades or "Crítica" in criticidades


def test_leer_bytes_y_resumen_biblioteca(tmp_path):
    docs_root = tmp_path / "docs"
    db_path = tmp_path / "biblioteca.sqlite"
    pdf_path, _, _ = _crear_documentos_base(docs_root)
    documentation_service.sincronizar_biblioteca_documental(db_path=db_path, docs_root=docs_root)

    df = documentation_service.listar_documentos(db_path=db_path, docs_root=docs_root)
    documento = df[df["extension"].astype(str).str.lower().eq(".pdf")].iloc[0].to_dict()
    contenido = documentation_service.leer_bytes_documento(documento, docs_root=docs_root)
    assert contenido.startswith(b"%PDF")

    resumen = documentation_service.resumen_biblioteca_documental(db_path=db_path, docs_root=docs_root)
    assert resumen["total"] >= 3
    assert resumen["pdf"] >= 1
    assert resumen["detalle"].empty is False
