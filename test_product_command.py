#!/usr/bin/env python3
"""Script de prueba para verificar la sintaxis del comando product."""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Importar typer y verificar que el comando esté registrado
    import typer
    from main import app

    # Verificar que el comando 'product' esté registrado
    commands = app.registered_commands
    command_names = [cmd.name for cmd in commands]

    print("✅ Comandos registrados:")
    for cmd_name in command_names:
        print(f"   - {cmd_name}")

    if "product" in command_names:
        print("\n✅ Comando 'product' registrado correctamente")
        print("\n📋 Uso del comando:")
        print("   python main.py product SKU")
        print("   python main.py product 00042")
        print("   python main.py product 00042 --output producto.json")
        print("   python main.py product 00042 --compact")
    else:
        print("\n❌ ERROR: Comando 'product' NO encontrado")
        sys.exit(1)

except ImportError as e:
    print(f"❌ Error de importación: {e}")
    print("   Asegúrate de que typer y las dependencias estén instaladas")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error inesperado: {e}")
    sys.exit(1)
