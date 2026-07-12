from dataclasses import dataclass
import base64
import hashlib
import hmac
import html
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


def _is_bcrypt_hash(value):
    return str(value).startswith(("$2b$", "$2a$", "$2y$"))


def verificar_password(password, stored_hash):
    try:
        if _is_bcrypt_hash(stored_hash):
            import bcrypt
            return bcrypt.checkpw(str(password).encode("utf-8"), stored_hash.encode("utf-8"))
        return hmac.compare_digest(stored_hash, hash_password(password))
    except Exception:
        return False


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
    nombre = str(env.get("REPORT_PERFORACION_ADMIN_NAME", username)).strip() or username
    rol = str(env.get("REPORT_PERFORACION_ADMIN_ROLE", "admin")).strip().lower() or "admin"

    password_hash = str(env.get("REPORT_PERFORACION_ADMIN_PASSWORD_HASH", "")).strip()
    if not password_hash:
        # Legacy: plaintext password, hash with SHA256
        password = str(env.get("REPORT_PERFORACION_ADMIN_PASSWORD", "")).strip()
        if not password:
            return {}
        password_hash = hash_password(password)

    if not username or not password_hash:
        return {}

    return {
        username.lower(): Usuario(
            username=username,
            nombre=nombre,
            rol=rol,
            password_hash=password_hash,
        )
    }


_cargar_env_local()
USUARIOS = cargar_usuarios()


def autenticar(username, password, usuarios=None):
    usuarios = USUARIOS if usuarios is None else usuarios
    usuario = usuarios.get(str(username or "").strip().lower())
    if usuario is None:
        return None
    if not verificar_password(password, usuario.password_hash):
        return None
    return usuario


def usuario_actual():
    return st.session_state.get("usuario_actual")


def esta_autenticado():
    return usuario_actual() is not None


def es_admin():
    usuario = usuario_actual()
    if not usuario:
        return False
    if isinstance(usuario, dict):
        rol = usuario.get("rol")
    else:
        rol = getattr(usuario, "rol", None)
    return str(rol or "").strip().lower() == "admin"


def cerrar_sesion():
    st.session_state.pop("usuario_actual", None)
    st.session_state.pop("autenticado", None)
    st.session_state.pop("usuario", None)


def _imagen_base64(path):
    try:
        return base64.b64encode(path.read_bytes()).decode("ascii")
    except FileNotFoundError:
        return ""


def aplicar_estilo_login(st_module=st):
    imagen = _imagen_base64(LOGIN_BACKGROUND) or _imagen_base64(LOGIN_BACKGROUND_FALLBACK)
    if imagen:
        fondo_app = (
            f"linear-gradient(135deg, rgba(0,0,0,0.75), rgba(10,30,20,0.65)), "
            f"url('data:image/jpeg;base64,{imagen}')"
        )
    else:
        fondo_app = "linear-gradient(135deg, #050b0c 0%, #14251f 100%)"

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
                background: {fondo_app} !important;
                background-size: cover !important;
                background-position: center center !important;
                background-attachment: fixed !important;
            }}

            [data-testid="stAppViewContainer"] {{
                background: transparent !important;
            }}

            .main .block-container {{
                min-height: 100vh;
                max-width: 420px;
                padding: 0 1rem;
                margin: 0 auto;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }}

            /* --- Tarjeta glassmorphism --- */
            .stForm,
            div[data-testid="stForm"] {{
                background: rgba(15, 25, 20, 0.85) !important;
                backdrop-filter: blur(12px) !important;
                -webkit-backdrop-filter: blur(12px) !important;
                border: 1px solid rgba(255, 255, 255, 0.10) !important;
                border-radius: 16px !important;
                padding: 2.5rem 2rem 2rem !important;
                box-shadow: 0 25px 50px rgba(0, 0, 0, 0.50) !important;
            }}

            /* --- Badge circular RP --- */
            .login-brand {{
                text-align: center;
                margin-bottom: 1rem;
            }}

            .login-mark {{
                width: 56px;
                height: 56px;
                margin: 0 auto 0.75rem;
                border-radius: 50%;
                display: grid;
                place-items: center;
                background: rgba(0, 0, 0, 0.50);
                border: 1.5px solid #00E676;
                box-shadow: 0 0 18px rgba(0, 230, 118, 0.35);
                color: #00E676;
                font-size: 18px;
                font-weight: 700;
                letter-spacing: 0;
            }}

            .login-brand h2 {{
                margin: 0 0 0.2rem;
                color: #FFFFFF;
                font-size: 1.05rem;
                font-weight: 700;
                letter-spacing: 3px;
                text-transform: uppercase;
            }}

            .login-brand p {{
                margin: 0;
                color: #9E9E9E;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 2px;
                text-transform: uppercase;
            }}

            .login-divider {{
                border: none;
                border-top: 1px solid rgba(255, 255, 255, 0.08);
                margin: 16px 0 0;
            }}

            /* --- Etiquetas de campos --- */
            [data-testid="stWidgetLabel"] p {{
                color: #9E9E9E !important;
                font-size: 11px !important;
                font-weight: 700 !important;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }}

            /* --- Inputs activos --- */
            [data-testid="stTextInput"] input {{
                height: 2.35rem;
                border-radius: 8px !important;
                border: 1px solid rgba(255, 255, 255, 0.15) !important;
                background: rgba(255, 255, 255, 0.06) !important;
                color: #FFFFFF !important;
                font-size: 0.88rem !important;
                box-shadow: none !important;
            }}

            [data-testid="stTextInput"] input:focus {{
                border-color: #00E676 !important;
                box-shadow: 0 0 0 2px rgba(0, 230, 118, 0.15) !important;
            }}

            /* --- Input deshabilitado (usuario fijo) --- */
            [data-testid="stTextInput"] input:disabled {{
                color: #64748b !important;
                background: rgba(255, 255, 255, 0.03) !important;
                border-color: rgba(255, 255, 255, 0.08) !important;
                cursor: not-allowed !important;
                -webkit-text-fill-color: #64748b !important;
            }}

            /* --- Botón submit naranja --- */
            .stButton > button,
            .stFormSubmitButton > button,
            button[kind="primary"] {{
                width: 100%;
                min-height: 2.5rem;
                border-radius: 8px;
                border: none;
                background: linear-gradient(90deg, #FF8F00, #FF6F00);
                color: #FFFFFF;
                font-size: 0.8rem;
                font-weight: 700;
                letter-spacing: 0.10rem;
                text-transform: uppercase;
                box-shadow: 0 4px 14px rgba(255, 111, 0, 0.25);
                transition: all 0.18s ease;
            }}

            .stButton > button:hover,
            .stFormSubmitButton > button:hover,
            button[kind="primary"]:hover {{
                transform: translateY(-1px);
                box-shadow: 0 6px 20px rgba(255, 111, 0, 0.40);
            }}

            /* --- Error personalizado --- */
            .login-error {{
                background: rgba(244, 67, 54, 0.15);
                border: 1px solid rgba(244, 67, 54, 0.40);
                border-radius: 8px;
                padding: 10px 14px;
                text-align: center;
                color: #EF9A9A;
                font-size: 13px;
                margin-top: 0.5rem;
            }}

            /* --- Nota pie --- */
            .login-footnote {{
                text-align: center;
                color: #616161;
                font-size: 10px;
                letter-spacing: 0.06rem;
                margin-top: 1rem;
            }}

            @media (max-width: 640px) {{
                .main .block-container {{
                    max-width: 100%;
                    padding-left: 1rem;
                    padding-right: 1rem;
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _username_configurado():
    if USUARIOS:
        return next(iter(USUARIOS.values())).username
    return "ProyectoDES"


def render_login(st_module=st):
    if esta_autenticado():
        return True

    aplicar_estilo_login(st_module)

    username_fijo = _username_configurado()
    username_html = html.escape(username_fijo)

    st_module.markdown(
        f"""
        <div class="login-brand">
            <div class="login-mark">RP</div>
            <h2>REPORT PERFORACIÓN</h2>
            <p>Operational Command Center — {username_html}</p>
            <hr class="login-divider">
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st_module.form("login_operacional"):
        st_module.text_input(
            "Usuario",
            value=username_fijo,
            disabled=True,
            key="login_username_display",
        )
        password = st_module.text_input(
            "Contraseña",
            type="password",
            placeholder="Ingrese su clave",
            key="login_password",
        )
        enviar = st_module.form_submit_button("Ingresar al sistema", type="primary")

    if enviar:
        if not USUARIOS:
            st_module.markdown(
                '<div class="login-error">⚠ No hay credenciales configuradas. Revise el archivo .env del proyecto.</div>',
                unsafe_allow_html=True,
            )
            return False
        usuario = autenticar(username_fijo, password)
        if usuario is None:
            st_module.markdown(
                '<div class="login-error">⚠ Contraseña incorrecta.</div>',
                unsafe_allow_html=True,
            )
            return False
        st.session_state["usuario_actual"] = {
            "username": usuario.username,
            "nombre": usuario.nombre,
            "rol": usuario.rol,
        }
        st.session_state["autenticado"] = True
        st.session_state["usuario"] = usuario.username
        st_module.rerun()

    st_module.markdown(
        '<div class="login-footnote">Acceso restringido · Personal autorizado · Tepsac © 2026</div>',
        unsafe_allow_html=True,
    )
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
    st_module.caption(f"Sesión: {usuario['nombre']}")
    st_module.caption(f"Rol: {usuario['rol']}")
    if st_module.button("Cerrar sesión"):
        cerrar_sesion()
        st_module.rerun()
