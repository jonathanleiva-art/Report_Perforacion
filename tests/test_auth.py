import streamlit as st

from ui.auth import Usuario, USUARIOS, autenticar, cargar_usuarios, es_admin, hash_password


def test_autenticar_usuario_admin_valido():
    usuario = USUARIOS["proyectodes"]
    assert usuario.username == "ProyectoDES"
    assert usuario.nombre == "ProyectoDES"
    assert usuario.rol == "admin"


def test_autenticar_normaliza_mayusculas_y_espacios():
    usuarios = cargar_usuarios(
        {
            "REPORT_PERFORACION_ADMIN_USER": "ProyectoDES",
            "REPORT_PERFORACION_ADMIN_PASSWORD": "ClaveTemporalPrueba",
            "REPORT_PERFORACION_ADMIN_NAME": "ProyectoDES",
            "REPORT_PERFORACION_ADMIN_ROLE": "admin",
        }
    )
    usuario = autenticar("  proyectodes  ", "ClaveTemporalPrueba", usuarios=usuarios)

    assert usuario is not None
    assert usuario.username == "ProyectoDES"
    assert usuario.rol == "admin"


def test_autenticar_rechaza_password_incorrecto():
    assert autenticar("ProyectoDES", "incorrecta") is None


def test_autenticar_rechaza_usuarios_antiguos():
    assert autenticar("admin", "Admin@2026") is None
    assert autenticar("supervisor", "Perfo@2026") is None
    assert autenticar("operador", "Turno@2026") is None


def test_passwords_se_guardan_como_hash():
    assert USUARIOS["proyectodes"].password_hash
    assert USUARIOS["proyectodes"].password_hash.startswith(("$2b$", "$2a$", "$2y$"))


def test_cargar_usuarios_requiere_usuario_y_password():
    assert cargar_usuarios({}) == {}


def test_cargar_usuarios_desde_configuracion():
    usuarios = cargar_usuarios(
        {
            "REPORT_PERFORACION_ADMIN_USER": "Admin Mina",
            "REPORT_PERFORACION_ADMIN_PASSWORD": "ClaveSegura",
            "REPORT_PERFORACION_ADMIN_NAME": "Administrador Mina",
            "REPORT_PERFORACION_ADMIN_ROLE": "admin",
        }
    )

    usuario = autenticar("admin mina", "ClaveSegura", usuarios=usuarios)

    assert usuario is not None
    assert usuario.nombre == "Administrador Mina"
    assert usuario.password_hash != "ClaveSegura"


def test_es_admin_soporta_dict_y_dataclass():
    st.session_state["usuario_actual"] = {"username": "ProyectoDES", "nombre": "ProyectoDES", "rol": "admin"}
    assert es_admin()

    st.session_state["usuario_actual"] = Usuario(
        username="ProyectoDES",
        nombre="ProyectoDES",
        rol="admin",
        password_hash=hash_password("temporal"),
    )
    assert es_admin()

    st.session_state["usuario_actual"] = {"username": "Operador", "nombre": "Operador", "rol": "operador"}
    assert not es_admin()
    st.session_state.pop("usuario_actual", None)
