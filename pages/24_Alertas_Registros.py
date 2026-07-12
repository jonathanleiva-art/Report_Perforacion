from datetime import date, timedelta
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from services.alert_service import (
    EQUIPOS_REPORTES_REQUERIDOS,
    TURNOS_REPORTES_REQUERIDOS,
    get_reportes_faltantes,
)
from ui.page_header import render_page_header


_TURNO_ICON = {"Día": "🌅", "Noche": "🌙"}


def _resolver_rango():
    hoy = date.today()
    opciones = {
        "Últimos 7 días": 7,
        "Últimos 14 días": 14,
        "Últimos 30 días": 30,
        "Rango personalizado": None,
    }
    with st.sidebar:
        st.header("Filtros")
        seleccion = st.radio(
            "Período",
            list(opciones.keys()),
            index=0,
            key="alertas_registros_periodo",
        )
        if opciones[seleccion] is not None:
            dias = opciones[seleccion]
            return hoy - timedelta(days=dias - 1), hoy
        rango = st.date_input(
            "Rango de fechas",
            value=(hoy - timedelta(days=6), hoy),
            key="alertas_registros_rango",
        )
        if isinstance(rango, tuple) and len(rango) == 2:
            return rango[0], rango[1]
        return hoy - timedelta(days=6), hoy


def _render_tarjeta_fecha(fecha_d: date, grupo: pd.DataFrame, hoy: date) -> None:
    dias_atraso = max((hoy - fecha_d).days, 0)
    dia_semana = fecha_d.strftime("%A").capitalize()
    atraso_color = "#E74C3C" if dias_atraso >= 3 else "#F39C12"

    turnos_html = ""
    for turno in TURNOS_REPORTES_REQUERIDOS:
        sub = grupo[grupo["Turno"] == turno]
        if sub.empty:
            continue
        equipos = sorted(sub["Equipo"].tolist())
        icon = _TURNO_ICON.get(turno, "")
        todos = len(equipos) == len(EQUIPOS_REPORTES_REQUERIDOS)
        badge_color = "#E74C3C" if todos else "#F39C12"
        chips = "".join(
            f'<span style="background:#1a1a1a;border:1px solid #444;color:#E0E0E0;'
            f'font-size:0.73rem;border-radius:4px;padding:2px 6px;margin:2px;">{e}</span>'
            for e in equipos
        )
        turnos_html += (
            f'<div style="margin-top:6px;padding:7px 10px;background:#111318;'
            f'border-radius:6px;border-left:3px solid #E67E22;">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">'
            f'<span style="font-size:1rem;">{icon}</span>'
            f'<span style="color:#E67E22;font-weight:600;font-size:0.82rem;">Turno {turno}</span>'
            f'<span style="color:{badge_color};font-size:0.75rem;margin-left:auto;">'
            f'{"⛔ Todos" if todos else f"⚠ {len(equipos)}"} equipo(s) sin reporte</span>'
            f'</div>'
            f'<div style="display:flex;flex-wrap:wrap;">{chips}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div style="background:#0d0e10;border:1px solid #E67E22;border-radius:8px;'
        f'padding:10px 14px;margin-bottom:8px;">'
        f'<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:2px;">'
        f'<span style="font-size:1rem;font-weight:700;color:#F0F0F0;">'
        f'⚠ {fecha_d.strftime("%d-%m-%Y")}</span>'
        f'<span style="font-size:0.8rem;color:#888;">{dia_semana}</span>'
        f'<span style="font-size:0.75rem;color:{atraso_color};margin-left:auto;">'
        f'{dias_atraso}d de atraso</span>'
        f'</div>'
        f'{turnos_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def main():
    if not app.requerir_acceso():
        return

    render_page_header(
        st,
        "Alertas de Registros",
        "Reportes faltantes por fecha, turno y equipo · Fuente: reportes_perforacion.db",
    )

    fecha_desde, fecha_hasta = _resolver_rango()
    faltantes = get_reportes_faltantes(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)

    total_pendientes = len(faltantes)
    fechas_afectadas = int(faltantes["Fecha"].nunique()) if not faltantes.empty else 0
    atraso_maximo = int(faltantes["Días de atraso"].max()) if not faltantes.empty else 0

    # ── Métricas ────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Reportes faltantes", f"{total_pendientes:,}")
    k2.metric("Fechas afectadas", f"{fechas_afectadas:,}")
    k3.metric("Atraso máximo", f"{atraso_maximo} días")
    k4.metric("Equipos monitoreados", len(EQUIPOS_REPORTES_REQUERIDOS))

    st.caption(
        "Equipos: " + ", ".join(EQUIPOS_REPORTES_REQUERIDOS)
        + " · Turnos: " + " / ".join(TURNOS_REPORTES_REQUERIDOS)
        + f" · Período: {fecha_desde.strftime('%d-%m-%Y')} — {fecha_hasta.strftime('%d-%m-%Y')}"
    )

    if faltantes.empty:
        st.markdown(
            '<div style="background:#0d0e10;border:1px solid #2ECC71;border-radius:8px;'
            'padding:16px 18px;margin-top:12px;">'
            '<span style="color:#2ECC71;font-size:0.95rem;font-weight:600;">'
            '✓ Sin reportes faltantes</span><br>'
            '<span style="color:#BDC3C7;font-size:0.82rem;">'
            'Todos los turnos están registrados para los equipos monitoreados '
            'en el período seleccionado.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    st.divider()
    st.subheader("Detalle por fecha")

    hoy = date.today()
    faltantes_sorted = faltantes.sort_values("Fecha", ascending=False)
    mes_actual = None

    for fecha_val, grupo in faltantes_sorted.groupby("Fecha", sort=False):
        fecha_d = pd.to_datetime(fecha_val).date()
        mes = fecha_d.strftime("%B %Y").capitalize()

        if mes != mes_actual:
            st.markdown(
                f'<div style="color:#E67E22;font-size:0.88rem;font-weight:700;'
                f'margin:18px 0 6px 0;border-bottom:2px solid #E67E22;'
                f'padding-bottom:4px;">{mes}</div>',
                unsafe_allow_html=True,
            )
            mes_actual = mes

        _render_tarjeta_fecha(fecha_d, grupo, hoy)


main()
