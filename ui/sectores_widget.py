# -*- coding: utf-8 -*-
"""Widget reutilizable: múltiples sectores perforados en un turno."""

import json
import streamlit as st

TIPOS_SECTOR = ["Producción", "Precorte", "Buffer 1", "Buffer 2", "Auxiliar", "Borde", "Pozo Satélite", "Geófonos"]


# ─── SERIALIZACIÓN ────────────────────────────────────────────────────────────

def json_a_sectores(json_str):
    """Devuelve lista de dicts {tipo, numero} o None si inválido/vacío."""
    if not json_str:
        return None
    try:
        data = json.loads(str(json_str))
        if isinstance(data, list) and data:
            return [
                {
                    "tipo":   str(s.get("tipo", "Producción")),
                    # clave "numero" (nuevo) o "numero_precorte" (legacy)
                    "numero": str(
                        s.get("numero", "") or s.get("numero_precorte", "") or ""
                    ),
                }
                for s in data
            ]
    except Exception:
        pass
    return None


def sectores_a_json(sectores):
    """Convierte lista de dicts a JSON compacto para almacenamiento."""
    out = []
    for s in sectores:
        entry = {
            "tipo":   str(s.get("tipo", "")),
        }
        num = str(
            s.get("numero", "") or s.get("numero_precorte", "") or ""
        ).strip()
        if s.get("tipo") == "Precorte" and num:
            entry["numero"] = num
        out.append(entry)
    return json.dumps(out, ensure_ascii=False)


# ─── ESTADO ───────────────────────────────────────────────────────────────────

def init_sectores(kf, sectores_init=None):
    """Inicializa el estado de sectores. kf: callable nombre → clave."""
    init = sectores_init or [{"tipo": "Producción", "numero": ""}]
    st.session_state[kf("sec_n")] = len(init)
    for i, s in enumerate(init):
        st.session_state[kf(f"sec_{i}_tipo")] = str(s.get("tipo", "Producción"))
        st.session_state[kf(f"sec_{i}_num")] = str(
            s.get("numero", "") or s.get("numero_precorte", "") or ""
        )


def limpiar_sectores(kf, n_max=30):
    """Elimina todas las claves de sector del session_state."""
    for key in [kf("sec_n"), kf("sec_add")]:
        st.session_state.pop(key, None)
    for i in range(n_max):
        for suf in ("_tipo", "_num", "_del"):
            st.session_state.pop(kf(f"sec_{i}{suf}"), None)


# ─── RENDERIZADO ──────────────────────────────────────────────────────────────

def render_sectores(kf):
    """
    Renderiza el componente multi-sector y devuelve la lista de sectores actual.
    kf  : callable que mapea un nombre a una clave de session_state única.
    Devuelve: list[dict{tipo, numero}]
    """
    k_n = kf("sec_n")

    # Auto-inicializar (modo wizard: primera renderización sin init previo)
    if k_n not in st.session_state:
        init_sectores(kf)

    n = max(1, int(st.session_state.get(k_n, 1)))

    st.markdown("**Sectores trabajados en el turno**")

    # ── Filas de sector ──────────────────────────────────────────────────
    to_delete = None
    for i in range(n):
        tipo_key = kf(f"sec_{i}_tipo")
        num_key  = kf(f"sec_{i}_num")
        del_key  = kf(f"sec_{i}_del")

        if tipo_key not in st.session_state:
            st.session_state[tipo_key] = "Producción"
        if num_key not in st.session_state:
            st.session_state[num_key] = ""

        es_precorte = st.session_state.get(tipo_key, "Producción") == "Precorte"
        lv = "visible" if i == 0 else "collapsed"

        c1, c2, c3 = st.columns([3, 2, 0.5])

        with c1:
            st.selectbox("Tipo", TIPOS_SECTOR, label_visibility=lv, key=tipo_key)

        with c2:
            if es_precorte:
                st.text_input(
                    "N° Precorte",
                    placeholder="Ej: 01, 14",
                    label_visibility=lv,
                    key=num_key,
                )
            else:
                if st.session_state.get(num_key):
                    st.session_state[num_key] = ""
                st.empty()

        with c3:
            if i == 0:
                st.write("")  # alinea botón con los inputs de la primera fila
            if n > 1:
                if st.button("🗑", key=del_key, width="stretch"):
                    to_delete = i

    if to_delete is not None:
        _eliminar_sector(kf, to_delete, n)
        st.rerun()

    # ── Botón agregar ────────────────────────────────────────────────────
    if st.button("+ Agregar sector", key=kf("sec_add"), type="primary"):
        _agregar_sector(kf, n)
        st.rerun()

    n_act = int(st.session_state.get(k_n, 0))

    # ── Recolectar resultado ─────────────────────────────────────────────
    return [
        {
            "tipo":   st.session_state.get(kf(f"sec_{i}_tipo"), "Producción"),
            "numero": str(st.session_state.get(kf(f"sec_{i}_num"), "") or ""),
        }
        for i in range(n_act)
    ]


# ─── PRIVADO ──────────────────────────────────────────────────────────────────

def _agregar_sector(kf, n_actual):
    i = n_actual
    st.session_state[kf(f"sec_{i}_tipo")] = "Producción"
    st.session_state[kf(f"sec_{i}_num")]  = ""
    st.session_state[kf("sec_n")] = n_actual + 1


def _eliminar_sector(kf, idx, n_actual):
    for i in range(idx, n_actual - 1):
        st.session_state[kf(f"sec_{i}_tipo")] = st.session_state.get(
            kf(f"sec_{i+1}_tipo"), "Producción"
        )
        st.session_state[kf(f"sec_{i}_num")] = st.session_state.get(
            kf(f"sec_{i+1}_num"), ""
        )
    last = n_actual - 1
    for suf in ("_tipo", "_num"):
        st.session_state.pop(kf(f"sec_{last}{suf}"), None)
    st.session_state[kf("sec_n")] = max(1, n_actual - 1)
