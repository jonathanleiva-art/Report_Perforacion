from contextlib import nullcontext
from html import escape

import streamlit as st


def _safe(value):
    return escape(str(value or ""))


def section_header(title, subtitle="", *, kicker="Operacion", st_module=None):
    st_target = st_module or st
    st_target.markdown(
        f"""
        <div class="rp-section-heading">
            <div class="rp-section-kicker">{_safe(kicker)}</div>
            <h2>{_safe(title)}</h2>
            <p style="color:rgba(255,255,255,0.70);font-size:13px;margin:0.18rem 0 0;">{_safe(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_container(st_module=None):
    st_target = st_module or st
    container = getattr(st_target, "container", None)
    if container is None:
        return nullcontext()
    return container(border=True)


def metric_card(label, value, detail="", *, state="neutral", st_module=None):
    st_target = st_module or st
    st_target.markdown(
        f"""
        <div class="rp-metric-card rp-metric-{_safe(state)}">
            <div class="rp-metric-label">{_safe(label)}</div>
            <div class="rp-metric-value">{_safe(value)}</div>
            <div class="rp-metric-detail">{_safe(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def control_center_header(title, subtitle="", *, meta="", st_module=None):
    st_target = st_module or st
    st_target.markdown(
        f"""
        <div class="rp-control-header">
            <div>
                <div class="rp-control-kicker">Centro de control operacional</div>
                <h1>{_safe(title)}</h1>
                <p>{_safe(subtitle)}</p>
            </div>
            <div class="rp-control-meta">{_safe(meta)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_hero_card(label, value, detail="", *, state="neutral", st_module=None):
    st_target = st_module or st
    st_target.markdown(
        f"""
        <div class="rp-kpi-hero rp-kpi-hero-{_safe(state)}">
            <div class="rp-kpi-hero-label">{_safe(label)}</div>
            <div class="rp-kpi-hero-value">{_safe(value)}</div>
            <div class="rp-kpi-hero-detail">{_safe(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def fleet_status_card(equipo, estado, *, detail="", metrics=None, state="neutral", st_module=None):
    st_target = st_module or st
    metric_items = metrics or []
    metrics_html = "".join(
        f"""
        <div class="rp-fleet-metric">
            <span>{_safe(item.get("label", ""))}</span>
            <strong>{_safe(item.get("value", ""))}</strong>
        </div>
        """
        for item in metric_items
    )
    st_target.markdown(
        f"""
        <div class="rp-fleet-card rp-fleet-{_safe(state)}">
            <div class="rp-fleet-topline">
                <div>
                    <div class="rp-fleet-name">{_safe(equipo)}</div>
                    <div class="rp-fleet-detail">{_safe(detail)}</div>
                </div>
                <div class="rp-fleet-state">{_safe(estado)}</div>
            </div>
            <div class="rp-fleet-grid">{metrics_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def operational_alert_card(title, detail="", *, state="warning", st_module=None):
    st_target = st_module or st
    st_target.markdown(
        f"""
        <div class="rp-operational-alert rp-alert-{_safe(state)}">
            <div class="rp-alert-title">{_safe(title)}</div>
            <div class="rp-alert-detail">{_safe(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def recommendation_panel(title, message, *, state="info", st_module=None):
    st_target = st_module or st
    st_target.markdown(
        f"""
        <div class="rp-recommendation-panel rp-recommendation-{_safe(state)}">
            <div class="rp-recommendation-title">{_safe(title)}</div>
            <div class="rp-recommendation-message">{_safe(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_panel(title, message="", *, state="neutral", meta="", st_module=None):
    st_target = st_module or st
    st_target.markdown(
        f"""
        <div class="rp-status-panel rp-status-{_safe(state)}">
            <div>
                <div class="rp-status-title">{_safe(title)}</div>
                <div class="rp-status-message">{_safe(message)}</div>
            </div>
            <div class="rp-status-meta">{_safe(meta)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def document_tile(title, detail="", *, state="neutral", st_module=None):
    st_target = st_module or st
    st_target.markdown(
        f"""
        <div class="rp-doc-tile rp-doc-{_safe(state)}">
            <div class="rp-doc-title">{_safe(title)}</div>
            <div class="rp-doc-detail">{_safe(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
