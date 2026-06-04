from dataclasses import dataclass
import base64
import hashlib
import hmac
import os
from pathlib import Path

import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
LOGIN_BACKGROUND = ROOT_DIR / "assets" / "perforadoras-login.jpg"
LOGIN_BACKGROUND_FALLBACK = ROOT_DIR / "assets" / "FLEXI ROC D65 9274.jpeg"
ENV_PATH = ROOT_DIR / ".env"


@dataclass(frozen=True)
class Usuario:
    username: str
    nombre: str
    rol: str
    password_hash: str


def hash_password(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def _cargar_env_local(path=ENV_PATH):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def cargar_usuarios(env=None):
    env = os.environ if env is None else env
    username = str(env.get("REPORT_PERFORACION_ADMIN_USER", "")).strip()
    password = str(env.get("REPORT_PERFORACION_ADMIN_PASSWORD", "")).strip()
    nombre = str(env.get("REPORT_PERFORACION_ADMIN_NAME", username)).strip() or username
    rol = str(env.get("REPORT_PERFORACION_ADMIN_ROLE", "admin")).strip().lower() or "admin"
    if not username or not password:
        return {}
    return {
        username.lower(): Usuario(
            username=username,
            nombre=nombre,
            rol=rol,
            password_hash=hash_password(password),
        )
    }


_cargar_env_local()
USUARIOS = cargar_usuarios()


def autenticar(username, password, usuarios=None):
    usuarios = USUARIOS if usuarios is None else usuarios
    usuario = usuarios.get(str(username or "").strip().lower())
    if usuario is None:
        return None
    if not hmac.compare_digest(usuario.password_hash, hash_password(password)):
        return None
    return usuario


def usuario_actual():
    return st.session_state.get("usuario_actual")


def esta_autenticado():
    return usuario_actual() is not None


def es_admin():
    usuario = usuario_actual()
    return bool(usuario and usuario.get("rol") == "admin")


def cerrar_sesion():
    st.session_state.pop("usuario_actual", None)


def _imagen_base64(path):
    try:
        return base64.b64encode(path.read_bytes()).decode("ascii")
    except FileNotFoundError:
        return ""


def aplicar_estilo_login(st_module=st):
    imagen = _imagen_base64(LOGIN_BACKGROUND) or _imagen_base64(LOGIN_BACKGROUND_FALLBACK)
    fondo = (
        f"linear-gradient(180deg, rgba(1, 8, 14, 0.58), rgba(1, 8, 14, 0.78)), "
        f"url('data:image/jpeg;base64,{imagen}')"
        if imagen
        else "linear-gradient(135deg, #050b0c 0%, #14251f 100%)"
    )
    st_module.markdown(
        f"""
        <style>
            [data-testid="stHeader"],
            [data-testid="stToolbar"],
            [data-testid="stSidebar"],
            footer {{
                display: none !important;
            }}

            .stApp {{
                background: {fondo};
                background-size: cover;
                background-position: center center;
                background-attachment: fixed;
            }}

            [data-testid="stAppViewContainer"] {{
                background:
                    radial-gradient(circle at 47% 18%, rgba(63, 255, 92, 0.24), transparent 15rem),
                    repeating-linear-gradient(0deg, rgba(255,255,255,0.035) 0, rgba(255,255,255,0.035) 1px, transparent 1px, transparent 4px),
                    linear-gradient(90deg, rgba(2, 6, 10, 0.72), rgba(2, 6, 10, 0.2), rgba(2, 6, 10, 0.72));
            }}

            .main .block-container {{
                min-height: 100vh;
                max-width: 560px;
                padding: 6vh 1.5rem 2rem;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }}

            .login-brand {{
                text-align: center;
                margin-bottom: 0;
            }}

            .login-mark {{
                width: 112px;
                height: 82px;
                margin: 0 auto 1.15rem;
                border-radius: 2px;
                display: grid;
                place-items: center;
                background:
                    linear-gradient(180deg, rgba(7, 14, 21, 0.96), rgba(4, 9, 14, 0.98));
                box-shadow: 0 18px 42px rgba(0, 0, 0, 0.45), 0 0 26px rgba(34, 197, 94, 0.24);
                color: #42ff67;
                font-size: 1.25rem;
                font-weight: 900;
                letter-spacing: 0;
            }}

            .login-mark span {{
                display: block;
                color: #d9ffe1;
                font-size: 0.58rem;
                letter-spacing: 0.06rem;
                margin-top: 0.25rem;
            }}

            .login-brand h1 {{
                margin: 0;
                color: #42ff67;
                font-size: 1.75rem;
                font-weight: 860;
                letter-spacing: 0.18rem;
                text-transform: uppercase;
            }}

            .login-brand p {{
                margin: 0.65rem 0 0;
                color: rgba(226, 232, 240, 0.68);
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.18rem;
                text-transform: uppercase;
            }}

            .login-title-card {{
                border: 1px solid rgba(34, 197, 94, 0.38);
                border-radius: 10px;
                padding: 2rem 1.5rem 1.7rem;
                margin-bottom: 0.9rem;
                background:
                    linear-gradient(180deg, rgba(9, 17, 24, 0.9), rgba(5, 11, 16, 0.86));
                box-shadow: 0 20px 55px rgba(0, 0, 0, 0.42), 0 0 30px rgba(34, 197, 94, 0.12) inset;
                backdrop-filter: blur(9px);
            }}

            .stForm,
            div[data-testid="stForm"] {{
                border: 1px solid rgba(148, 163, 184, 0.16);
                border-radius: 0;
                padding: 1rem 1.05rem 0.9rem;
                background:
                    linear-gradient(180deg, rgba(9, 14, 20, 0.64), rgba(5, 10, 15, 0.58));
                box-shadow: none;
                backdrop-filter: blur(7px);
            }}

            [data-testid="stWidgetLabel"] p {{
                color: #e5e7eb !important;
                font-size: 0.7rem;
                font-weight: 800 !important;
                letter-spacing: 0.08rem;
                text-transform: uppercase;
            }}

            [data-testid="stTextInput"] input {{
                height: 2.55rem;
                border-radius: 3px !important;
                border: 1px solid rgba(148, 163, 184, 0.18) !important;
                background: rgba(30, 35, 46, 0.82) !important;
                color: #f8fafc !important;
                box-shadow: none !important;
            }}

            [data-testid="stTextInput"] input:focus {{
                border-color: rgba(66, 255, 103, 0.72) !important;
                box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.14) !important;
            }}

            [data-testid="stCheckbox"] label,
            [data-testid="stCheckbox"] p {{
                color: rgba(241, 245, 249, 0.88) !important;
                font-size: 0.8rem;
            }}

            .stButton > button,
            .stFormSubmitButton > button,
            button[kind="primary"] {{
                width: auto;
                min-height: 2.3rem;
                border-radius: 4px;
                border: 1px solid rgba(66, 255, 103, 0.46);
                background: linear-gradient(180deg, rgba(7, 18, 13, 0.98) 0%, rgba(4, 12, 9, 0.98) 100%);
                color: #ccffd7;
                font-weight: 850;
                letter-spacing: 0.06rem;
                text-transform: uppercase;
                box-shadow: 0 0 18px rgba(34, 197, 94, 0.18);
            }}

            .stButton > button:hover,
            .stFormSubmitButton > button:hover,
            button[kind="primary"]:hover {{
                border-color: rgba(66, 255, 103, 0.82);
                background: linear-gradient(180deg, rgba(16, 45, 25, 0.98) 0%, rgba(6, 22, 13, 0.98) 100%);
                color: #ffffff;
            }}

            [data-testid="stAlert"] {{
                border-radius: 8px;
                background: rgba(127, 29, 29, 0.78);
                color: #fff;
            }}

            .login-footnote {{
                margin-top: 1.05rem;
                text-align: center;
                color: rgba(226, 232, 240, 0.78);
                font-size: 0.74rem;
            }}

            @media (max-width: 640px) {{
                .main .block-container {{
                    max-width: 100%;
                    padding-left: 1rem;
                    padding-right: 1rem;
                }}

                .login-brand h1 {{
                    font-size: 1.28rem;
                    letter-spacing: 0.1rem;
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login(st_module=st):
    if esta_autenticado():
        return True

    aplicar_estilo_login(st_module)
    st_module.markdown(
        """
        <div class="login-brand">
            <div class="login-mark">RP<span>PERFORACIÓN</span></div>
            <div class="login-title-card">
                <h1>Perforación</h1>
                <p>Operational Command Center</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st_module.form("login_operacional"):
        username = st_module.text_input("Identificador", placeholder="Admin Jonathan")
        password = st_module.text_input("Password", type="password", placeholder="Ingrese su clave")
        recordar = st_module.checkbox("Recordar sesión en este equipo")
        enviar = st_module.form_submit_button("Desbloquear sistema", type="primary")

    st_module.markdown(
        '<div class="login-footnote">Acceso restringido a personal autorizado</div>',
        unsafe_allow_html=True,
    )

    if enviar:
        if not USUARIOS:
            st_module.error("No hay credenciales configuradas. Revise el archivo .env del proyecto.")
            return False
        usuario = autenticar(username, password)
        if usuario is None:
            st_module.error("Credenciales inválidas.")
            return False
        st.session_state["usuario_actual"] = {
            "username": usuario.username,
            "nombre": usuario.nombre,
            "rol": usuario.rol,
            "recordar": recordar,
        }
        st_module.rerun()
    return False


def requerir_login(st_module=st, admin=False):
    if not render_login(st_module):
        return False
    if admin and not es_admin():
        st_module.error("Acceso restringido a administrador.")
        return False
    return True


def render_usuario_sidebar(st_module=st):
    usuario = usuario_actual()
    if not usuario:
        return
    st_module.caption(f"Sesi\u00f3n: {usuario['nombre']}")
    st_module.caption(f"Rol: {usuario['rol']}")
    if st_module.button("Cerrar sesi\u00f3n"):
        cerrar_sesion()
        st_module.rerun()

