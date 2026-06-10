import pytest

import db
from services import catalog_service


def test_catalogos_crean_tablas(tmp_path):
    db_path = tmp_path / "catalogos.db"

    catalog_service.asegurar_tablas_catalogo(db_path=db_path)

    with db.conectar_db(db_path) as connection:
        equipos = db.columnas_tabla(connection, catalog_service.TABLA_EQUIPOS)
        operadores = db.columnas_tabla(connection, catalog_service.TABLA_OPERADORES)

    assert {"codigo_equipo", "nombre_equipo", "modelo", "activo"}.issubset(set(equipos))
    assert {"codigo_operador", "nombre_operador", "empresa", "cargo", "activo"}.issubset(set(operadores))


def test_listar_equipos_activos_usa_fallback_si_tabla_vacia(tmp_path):
    db_path = tmp_path / "catalogos.db"

    equipos = catalog_service.listar_equipos_activos(db_path=db_path)

    assert not equipos.empty
    assert {"9245", "9274"}.issubset(set(equipos["codigo_equipo"].astype(str)))


def test_listar_operadores_activos_usa_fallback_si_tabla_vacia(tmp_path):
    db_path = tmp_path / "catalogos.db"

    operadores = catalog_service.listar_operadores_activos(db_path=db_path)

    assert not operadores.empty
    assert "008086" in set(operadores["codigo_operador"].astype(str))
    assert "Jonathan Leiva" in set(operadores["nombre_operador"].astype(str))


def test_crear_equipo_no_permite_codigo_duplicado(tmp_path):
    db_path = tmp_path / "catalogos.db"

    catalog_service.crear_equipo("EQ-001", "Equipo Uno", modelo="Modelo A", db_path=db_path)

    with pytest.raises(ValueError, match="duplicado"):
        catalog_service.crear_equipo("EQ-001", "Equipo Duplicado", db_path=db_path)


def test_crear_operador_no_permite_codigo_duplicado(tmp_path):
    db_path = tmp_path / "catalogos.db"

    catalog_service.crear_operador("M-8086", "Jonathan Leiva", db_path=db_path)

    with pytest.raises(ValueError, match="duplicado"):
        catalog_service.crear_operador("008086", "Jonathan Duplicado", db_path=db_path)


def test_crear_catalogos_requiere_nombre(tmp_path):
    db_path = tmp_path / "catalogos.db"

    with pytest.raises(ValueError, match="Nombre"):
        catalog_service.crear_equipo("EQ-001", "", db_path=db_path)
    with pytest.raises(ValueError, match="Nombre"):
        catalog_service.crear_operador("M-8086", "", db_path=db_path)


def test_desactivar_equipo_es_logico(tmp_path):
    db_path = tmp_path / "catalogos.db"
    catalog_service.crear_equipo("EQ-001", "Equipo Uno", db_path=db_path)

    desactivados = catalog_service.desactivar_equipo("EQ-001", db_path=db_path)
    activos = catalog_service.listar_equipos_activos(db_path=db_path)

    assert desactivados == 1
    assert "EQ-001" not in set(activos["codigo_equipo"].astype(str))
    with db.conectar_db(db_path) as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM {db.quote_identifier(catalog_service.TABLA_EQUIPOS)} WHERE codigo_equipo = ?",
            ("EQ-001",),
        ).fetchone()[0]
    assert total == 1


def test_desactivar_operador_es_logico(tmp_path):
    db_path = tmp_path / "catalogos.db"
    catalog_service.crear_operador("M-8086", "Jonathan Leiva", db_path=db_path)

    desactivados = catalog_service.desactivar_operador("008086", db_path=db_path)
    activos = catalog_service.listar_operadores_activos(db_path=db_path)

    assert desactivados == 1
    assert "008086" not in set(activos["codigo_operador"].astype(str))
    with db.conectar_db(db_path) as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM {db.quote_identifier(catalog_service.TABLA_OPERADORES)} WHERE codigo_operador = ?",
            ("008086",),
        ).fetchone()[0]
    assert total == 1
