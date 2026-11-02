"""Renderizza la distribuzione statica di PPaToS.ch con il design autentico della triade."""

import os
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["NN_SITO"] = "https://nuova-norma.pagine.ch"
os.environ["ANORMA_SITO"] = "https://anorma.pagine.ch"
os.environ["PPATOS_SITO"] = "https://ppatos.pagine.ch"

from ppatos import web

DIST = ROOT / "dist"
if DIST.exists():
    shutil.rmtree(DIST)
DIST.mkdir(parents=True, exist_ok=True)

# 1. Homepage PPaToS (Design autentico triade blu: Cose da grandi senza il pathos)
home_html = web.home_page()
(DIST / "index.html").write_bytes(home_html)
print(f"✅ Generato dist/index.html ({len(home_html):,} bytes)")

# 2. Pagina Documenti / Modelli
doc_dir = DIST / "documenti"
doc_dir.mkdir(parents=True, exist_ok=True)
doc_html = web.documenti_page()
(doc_dir / "index.html").write_bytes(doc_html)
print(f"✅ Generato dist/documenti/index.html ({len(doc_html):,} bytes)")

# 3. Pagina Esempio (Bozza completa con clausole e pacchetto avvocato)
es_dir = DIST / "esempio"
es_dir.mkdir(parents=True, exist_ok=True)
es_html = web.esempio_page()
(es_dir / "index.html").write_bytes(es_html)
print(f"✅ Generato dist/esempio/index.html ({len(es_html):,} bytes)")

# 4. Risorse statiche condivise della triade (citazioni, copia, favicon, logo)
nn_static = DIST / "nn"
nn_static.mkdir(parents=True, exist_ok=True)

nn_src = ROOT.parent / "nuova-norma.ch" / "nn"
if nn_src.exists():
    for name in ["citazioni.js", "copia.js", "favicon.js", "logo.css"]:
        src = nn_src / name
        if src.exists():
            shutil.copy2(src, nn_static / name)
            shutil.copy2(src, DIST / name)

# 5. Copia configurazione pch.json
shutil.copy2(ROOT / "pch.json", DIST / "pch.json")
print("✅ Risorse e pch.json sincronizzati in dist/")
