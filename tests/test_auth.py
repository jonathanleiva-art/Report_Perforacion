from ui.auth import USUARIOS, autenticar, cargar_usuarios, hash_password


def test_autenticar_usuario_admin_valido():
    usuario = autenticar("Admin Jonathan", "Perforacion")

    assert usuario is not None
    assert usuario.username == "Admin Jonathan"
    assert usuario.nombre == "Admin Jonathan"
    assert usuario.rol == "admin"


def test_autenticar_normaliza_mayusculas_y_espacios():
    usuario = autenticar("  admin jonathan  ", "Perforacion")

    assert usuario is not None
    assert usuario.username == "Admin Jonathan"
    assert usuario.rol == "admin"


def test_autenticar_rechaza_password_incorrecto():
    assert autenticar("Admin Jonathan", "incorrecta") is None


def test_autenticar_rechaza_usuarios_antiguos():
    assert autenticar("admin", "Admin@2026") is None
    assert autenticar("supervisor", "Perfo@2026") is None
    assert autenticar("operador", "Turno@2026") is None


def test_passwords_se_guardan_como_hash():
    assert USUARIOS["admin jonathan"].password_hash == hash_password("Perforacion")
    assert USUARIOS["admin jonathan"].password_hash != "Perforacion"


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
