"""Tests unitarios para _detectar_doble_asignacion_operador (Escenario A).

Cubre los tres subtipos:
  1. Sin columna de metros → todos cobertura (fallback seguro)
  2. Un solo equipo productivo → cobertura admin (INFO)
  3. Cero equipos productivos → cobertura admin (INFO)
  4. 2 equipos con metros DISTINTOS → producción simultánea (WARNING)
  5. Operadores distintos en el mismo grupo → no se mezclan
  6. Operador vacío → ignorado (no se procesa)
  7. 2 equipos con metros EXACTAMENTE IGUALES → posible copia (WARNING)
     Caso real: Matías Toro, 2026-06-14, equipos 9259 y 9274, ambos 114.9 m
"""

import pandas as pd
import pytest

from services.data_quality_service import _detectar_doble_asignacion_operador

COL_EQ = "Número equipo"


def _df(*filas):
    return pd.DataFrame(list(filas))


def _fila(operador, equipo, metros, fecha="2026-06-14", turno="Noche"):
    return {
        "Fecha turno": fecha,
        "Turno": turno,
        COL_EQ: str(equipo),
        "Operador": operador,
        "Metros perforados": metros,
    }


# ---------------------------------------------------------------------------
# Test 1 — sin columna Metros perforados: todo va a cobertura (fallback seguro)
# ---------------------------------------------------------------------------
def test_sin_columna_metros_todo_cobertura():
    df = pd.DataFrame([
        {"Fecha turno": "2026-06-14", "Turno": "Noche", COL_EQ: "9259", "Operador": "Juan"},
        {"Fecha turno": "2026-06-14", "Turno": "Noche", COL_EQ: "9274", "Operador": "Juan"},
    ])
    cob, sim, cop = _detectar_doble_asignacion_operador(df)
    assert len(cob) == 2
    assert len(sim) == 0
    assert len(cop) == 0


# ---------------------------------------------------------------------------
# Test 2 — un solo equipo con metros > 0: cobertura administrativa (INFO)
# ---------------------------------------------------------------------------
def test_un_equipo_productivo_es_cobertura():
    df = _df(
        _fila("Juan", "9259", 120.0),   # metros > 0
        _fila("Juan", "9274", 0.0),     # metros = 0 → cobertura
    )
    cob, sim, cop = _detectar_doble_asignacion_operador(df)
    assert len(cob) == 2
    assert len(sim) == 0
    assert len(cop) == 0


# ---------------------------------------------------------------------------
# Test 3 — cero equipos con metros > 0: también cobertura administrativa
# ---------------------------------------------------------------------------
def test_cero_equipos_productivos_es_cobertura():
    df = _df(
        _fila("Juan", "9259", 0.0),
        _fila("Juan", "9274", 0.0),
    )
    cob, sim, cop = _detectar_doble_asignacion_operador(df)
    assert len(cob) == 2
    assert len(sim) == 0
    assert len(cop) == 0


# ---------------------------------------------------------------------------
# Test 4 — 2 equipos con metros DISTINTOS: producción simultánea (WARNING)
# ---------------------------------------------------------------------------
def test_metros_distintos_es_simultanea():
    df = _df(
        _fila("Juan", "9259", 100.0),
        _fila("Juan", "9274", 85.5),   # distinto → no es copia
    )
    cob, sim, cop = _detectar_doble_asignacion_operador(df)
    assert len(cob) == 0
    assert len(sim) == 2
    assert len(cop) == 0


# ---------------------------------------------------------------------------
# Test 5 — operadores distintos en el mismo turno: grupos independientes
# ---------------------------------------------------------------------------
def test_operadores_distintos_grupos_independientes():
    df = _df(
        _fila("Juan",  "9259", 120.0),
        _fila("Juan",  "9274", 0.0),   # Juan → cobertura
        _fila("Pedro", "9259", 90.0),  # Pedro solo en un equipo → no es candidato
    )
    cob, sim, cop = _detectar_doble_asignacion_operador(df)
    # Juan: 1 equipo productivo → cobertura (2 filas)
    # Pedro: 1 equipo solo → no aparece como candidato
    assert len(cob) == 2
    assert len(sim) == 0
    assert len(cop) == 0


# ---------------------------------------------------------------------------
# Test 6 — operador vacío: filas ignoradas (no procesadas como candidatos)
# ---------------------------------------------------------------------------
def test_operador_vacio_ignorado():
    df = _df(
        _fila("", "9259", 100.0),
        _fila("", "9274", 100.0),
    )
    cob, sim, cop = _detectar_doble_asignacion_operador(df)
    assert len(cob) == 0
    assert len(sim) == 0
    assert len(cop) == 0


# ---------------------------------------------------------------------------
# Test 7 — metros EXACTAMENTE IGUALES en 2 equipos: posible copia (WARNING)
# Caso real: Matías Toro, 2026-06-14, equipos 9259 y 9274, ambos 114.9 m
# ---------------------------------------------------------------------------
def test_metros_identicos_es_posible_copia():
    df = _df(
        _fila("Matías Toro", "9259", 114.9),
        _fila("Matías Toro", "9274", 114.9),  # mismo valor exacto → sospecha de copia
    )
    cob, sim, cop = _detectar_doble_asignacion_operador(df)
    assert len(cob) == 0
    assert len(sim) == 0
    assert len(cop) == 2  # ambas filas del grupo van a índices_copia
