"""
Script de sincronización de flota hacia el sistema Gestion_Espacial_Mina.

Uso:
    python export_flota.py

Cuándo ejecutarlo:
    - Al agregar o desactivar equipos en el catálogo del sistema principal
    - Como tarea programada (ej. diaria, o al iniciar el turno)

La ruta destino está definida en DEST_JSON (relativa al directorio del script
o como ruta absoluta). Ajústala si el proyecto nuevo está en otra ubicación.
"""

from pathlib import Path
import json
import sys

# Ruta del sistema nuevo — ajustar si cambia la ubicación
DEST_JSON = Path(__file__).parent.parent / "Gestion_Espacial_Mina" / "data" / "flota_sincronizada.json"

def main():
    try:
        from services.catalog_service import equipos_esperados_activos
    except ImportError as exc:
        print(f"[export_flota] Error al importar catalog_service: {exc}")
        print("  Asegúrate de correr este script desde el directorio del sistema principal.")
        sys.exit(1)

    equipos_raw = equipos_esperados_activos()

    flota = [
        {"modelo": str(modelo), "numero": str(numero)}
        for modelo, numero in equipos_raw
    ]

    DEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    DEST_JSON.write_text(
        json.dumps(flota, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[export_flota] {len(flota)} equipos exportados -> {DEST_JSON}")
    for eq in flota:
        print(f"  {eq['modelo']:20s}  #{eq['numero']}")


if __name__ == "__main__":
    main()
