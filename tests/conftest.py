"""Configuración global de pytest."""

import sys
from pathlib import Path

# Agregar el directorio raíz al PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Agregar tests al path para importar example_crud
tests_dir = Path(__file__).parent
sys.path.insert(0, str(tests_dir))
