from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


ROOT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT_DIR / "assets"
CSS_PATH = ASSETS_DIR / "styles.css"
JS_PATH = ASSETS_DIR / "ui_effects.js"


def _leer_archivo(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def aplicar_tema_profesional() -> None:
    css = _leer_archivo(CSS_PATH)
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    js = _leer_archivo(JS_PATH)
    if js:
        components.html(f"<script>{js}</script>", height=1, scrolling=False)
