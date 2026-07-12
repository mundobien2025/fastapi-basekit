"""Configuración global de pytest."""

import os
import sys
from pathlib import Path

# JWTService ahora FALLA si falta JWT_SECRET (antes caía a una clave pública).
# Seteamos un secret de test a nivel import, antes de que cualquier test cree un
# JWTService — así los tests corren como debe correr producción (con secret), no
# apoyados en el fallback inseguro. Los tests del propio fail-loud manipulan el
# env con monkeypatch.
os.environ.setdefault("JWT_SECRET", "test-secret-fixed-do-not-use-in-prod-0123456789")

# Agregar el directorio raíz al PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Agregar tests al path para importar example_crud
tests_dir = Path(__file__).parent
sys.path.insert(0, str(tests_dir))


# --- Shim de test: compat mongomock <-> beanie 2.x -------------------------
# beanie 2.1 llama Database.list_collection_names(authorizedCollections=...);
# la firma de mongomock (filter=, session=) rechaza ese kwarg y revienta el
# setup de TODOS los tests Beanie. Envolvemos para descartar kwargs no
# soportados y así el Mongo en memoria (mongomock-motor) funciona en tests.
# Parche SOLO de test — no toca la lib ni el runtime de producción.
try:  # pragma: no cover - defensivo
    import mongomock.database as _mm_db

    _orig_list_collection_names = _mm_db.Database.list_collection_names

    def _patched_list_collection_names(
        self, filter=None, session=None, **_ignored
    ):
        return _orig_list_collection_names(self, filter=filter, session=session)

    _mm_db.Database.list_collection_names = _patched_list_collection_names
except Exception:  # pragma: no cover
    pass
