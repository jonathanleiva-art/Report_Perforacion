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


def _imagen_base64(path):
    try:
        return base64.b64encode(path.read_bytes()).decode("ascii")
    except FileNotFoundError:
        return ""


def aplicar_estilo_login(st_module=st):
    imagen = _imagen_base64(LOGIN_BACKGROUND) or _imagen_base64(LOGIN_BACKGROUND_FALLBACK)
    if imagen:
        fondo_app = (
            f"linear-gradient(180deg, rgba(1, 8, 14, 0.35) 0%, rgba(1, 8, 14, 0.52) 100%), "
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
                max-width: 360px;
                padding: 0 1rem;
                margin: 0 auto;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }}

            /* --- Tarjeta glassmorphism --- */
            .stForm,
            div[data-testid="stForm"] {{
                background: rgba(5, 13, 22, 0.62) !important;
                backdrop-filter: blur(14px) !important;
                -webkit-backdrop-filter: blur(14px) !important;
                border: 1px solid rgba(66, 255, 103, 0.22) !important;
                border-radius: 10px !important;
                padding: 1.45rem 1.35rem 1.25rem !important;
                box-shadow:
                    0 22px 56px rgba(0, 0, 0, 0.44),
                    0 0 40px rgba(34, 197, 94, 0.06) inset !important;
            }}

            /* --- Logo marca --- */
            .login-brand {{
                text-align: center;
                margin-bottom: 0.95rem;
            }}

            .login-mark {{
                width: 64px;
                height: 48px;
                margin: 0 auto 0.7rem;
                border-radius: 10px;
                display: grid;
                place-items: center;
                background: linear-gradient(180deg, rgba(7, 18, 13, 0.95), rgba(4, 11, 8, 0.98));
                border: 1px solid rgba(66, 255, 103, 0.30);
                box-shadow: 0 0 22px rgba(34, 197, 94, 0.22);
                color: #42ff67;
                font-size: 1.05rem;
                font-weight: 900;
                letter-spacing: 0;
            }}

            .login-mark span {{
                display: block;
                color: #d9ffe1;
                font-size: 0.5rem;
                letter-spacing: 0.05rem;
                margin-top: 0.18rem;
            }}

            .login-brand h2 {{
                margin: 0 0 0.2rem;
                color: #e2f5e8;
                font-size: 1.08rem;
                font-weight: 800;
                letter-spacing: 0.12rem;
                text-transform: uppercase;
            }}

            .login-brand p {{
                margin: 0;
                color: rgba(148, 163, 184, 0.72);
                font-size: 0.68rem;
                font-weight: 600;
                letter-spacing: 0.15rem;
                text-transform: uppercase;
            }}

            /* --- Etiquetas de campos --- */
            [data-testid="stWidgetLabel"] p {{
                color: #94a3b8 !important;
                font-size: 0.68rem !important;
                font-weight: 700 !important;
                letter-spacing: 0.08rem;
                text-transform: uppercase;
            }}

            /* --- Inputs activos --- */
            [data-testid="stTextInput"] input {{
                height: 2.35rem;
                border-radius: 8px !important;
                border: 1px solid rgba(100, 116, 139, 0.25) !important;
                background: rgba(15, 23, 35, 0.70) !important;
                color: #f1f5f9 !important;
                font-size: 0.88rem !important;
                box-shadow: none !important;
            }}

            [data-testid="stTextInput"] input:focus {{
                border-color: rgba(66, 255, 103, 0.60) !important;
                box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.12) !important;
            }}

            /* --- Input deshabilitado (usuario fijo) --- */
            [data-testid="stTextInput"] input:disabled {{
                color: #64748b !important;
                background: rgba(10, 17, 26, 0.55) !important;
                border-color: rgba(71, 85, 105, 0.20) !important;
                cursor: not-allowed !important;
                -webkit-text-fill-color: #64748b !important;
            }}

            /* --- Botón submit --- */
            .stButton > button,
            .stFormSubmitButton > button,
            button[kind="primary"] {{
                width: 100%;
                min-height: 2.35rem;
                border-radius: 8px;
                border: 1px solid rgba(66, 255, 103, 0.40);
                background: linear-gradient(180deg, rgba(10, 28, 18, 0.98) 0%, rgba(5, 16, 10, 0.98) 100%);
                color: #a7f3c0;
                font-size: 0.8rem;
                font-weight: 800;
                letter-spacing: 0.10rem;
                text-transform: uppercase;
                box-shadow: 0 0 20px rgba(34, 197, 94, 0.14);
                transition: all 0.18s ease;
            }}

            .stButton > button:hover,
            .stFormSubmitButton > button:hover,
            button[kind="primary"]:hover {{
                border-color: rgba(66, 255, 103, 0.75);
                background: linear-gradient(180deg, rgba(18, 52, 28, 0.98) 0%, rgba(8, 28, 15, 0.98) 100%);
                color: #ffffff;
                box-shadow: 0 0 28px rgba(34, 197, 94, 0.28);
            }}

            /* --- Alerta de error --- */
            [data-testid="stAlert"] {{
                border-radius: 8px;
                background: rgba(120, 20, 20, 0.72) !important;
                border: 1px solid rgba(248, 113, 113, 0.30) !important;
                color: #fecaca !important;
                backdrop-filter: blur(8px);
                font-size: 0.82rem;
            }}

            /* --- Nota pie --- */
            .login-footnote {{
                text-align: center;
                color: rgba(100, 116, 139, 0.80);
                font-size: 0.66rem;
                letter-spacing: 0.06rem;
                margin-top: 0.9rem;
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
            <div class="login-mark">RP<span>PERF</span></div>
            <h2>Perforación</h2>
            <p>Operational Command Center</p>
            <p>{username_html}</p>
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

    st_module.markdown(
        '<div class="login-footnote">Acceso restringido · Personal autorizado</div>',
        unsafe_allow_html=True,
    )

    if enviar:
        if not USUARIOS:
            st_module.error("No hay credenciales configuradas. Revise el archivo .env del proyecto.")
            return False
        usuario = autenticar(username_fijo, password)
        if usuario is None:
            st_module.error("Contraseña incorrecta.")
            return False
        st.session_state["usuario_actual"] = {
            "username": usuario.username,
            "nombre": usuario.nombre,
            "rol": usuario.rol,
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
    st_module.caption(f"Sesión: {usuario['nombre']}")
    st_module.caption(f"Rol: {usuario['rol']}")
    if st_module.button("Cerrar sesión"):
        cerrar_sesion()
        st_module.rerun()
