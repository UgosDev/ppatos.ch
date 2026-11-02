"""Rende importabile il motore di Nuova-Norma (pacchetto nn) dalla cartella accanto: excited-bohr/nuova-norma.

Come per Anorma: stesso archivio, stesso file .env. Con NN_CARTELLA si puo indicare un'altra posizione.
Si importa solo quando serve l'archivio (norme.py); il resto del motore funziona anche senza.
"""

import os
import sys
from pathlib import Path

try:
    import nn  # noqa: F401
except ImportError:
    here = Path(__file__).resolve()
    cartella = Path(os.environ.get("NN_CARTELLA") or "")
    if not (cartella / "nn" / "__init__.py").exists():
        candidates = []
        for p in here.parents:
            candidates.extend([p / "nuova-norma.ch", p / "nuova-norma"])
        for candidata in candidates:
            if (candidata / "nn" / "__init__.py").exists():
                cartella = candidata
                break
    if not (cartella / "nn" / "__init__.py").exists():
        raise ImportError(f"Non trovo Nuova-Norma in {cartella}: PPaToS la usa per leggere le norme. "
                          "Imposta NN_CARTELLA o metti le cartelle una accanto all'altra.")
    sys.path.insert(0, str(cartella))
    import nn  # noqa: F401,E402
