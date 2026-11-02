"""Le norme citate dalle clausole, lette nell'archivio di Nuova-Norma.

Una norma nel modello:
  {"rs": "235.1", "art": "19", "cpv": "2", "lett": "a"}      diritto federale (Raccolta sistematica)
  {"ue": "32016R0679", "art": "13"}                          diritto UE (fonte eurlex di Nuova-Norma)

Il risolutore apre l'archivio in sola lettura e restituisce per ogni norma: citazione, versione in vigore,
impronta SHA-256 del testo dell'articolo (stessa regola del registro delle fonti di Anorma), estratto e link
alla pubblicazione ufficiale. L'impronta e cio che il monitoraggio confronta: se cambia, la clausola va rivista.
Nessuna rete: una norma che non e in archivio risulta «non trovata» e diventa un punto aperto.
"""

from __future__ import annotations

import datetime
import hashlib
import os
import re
import sqlite3
from pathlib import Path

SIGLE = {"220": "CO", "210": "CC", "101": "Cost.", "311.0": "CP", "272": "CPC"}
_SIGLA = re.compile(r"\(([A-Za-zÀ-ÿ.\-]{2,12})\)\s*$")


def chiave(n: dict) -> str:
    base = f"UE:{n['ue']}" if "ue" in n else f"CH:{n['rs']}"
    return f"{base}:{n['art']}" + (f":{n['cpv']}" if n.get("cpv") else "") + (f":{n['lett']}" if n.get("lett") else "")


def ordine(k: str) -> tuple:
    """Chiave di ordinamento naturale: art. 6 prima di art. 19, RS 210 prima di RS 235.1."""
    return tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"[:.]|(?<=\d)(?=[a-z])", k) if x)


def _dettaglio(n: dict) -> str:
    s = f"art. {n['art']}"
    if n.get("cpv"):
        s += f" cpv. {n['cpv']}"
    if n.get("lett"):
        s += f" lett. {n['lett']}"
    return s


def sigla(rs: str, titolo: str) -> str:
    if rs in SIGLE:
        return SIGLE[rs]
    m = _SIGLA.search(titolo or "")
    return m.group(1) if m else f"RS {rs}"


def impronta(testo: str) -> str:
    return hashlib.sha256(testo.encode("utf-8")).hexdigest() if testo else ""


def percorso_archivio() -> Path:
    """Lo stesso archivio di Nuova-Norma (NN_DB, altrimenti nuova-norma/data/nuova-norma.sqlite)."""
    if os.environ.get("NN_DB"):
        return Path(os.environ["NN_DB"])
    from . import _nn  # noqa: F401
    import nn
    return Path(nn.__file__).resolve().parent.parent / "data" / "nuova-norma.sqlite"


class Risolutore:
    """Legge le norme nell'archivio. Con con=None ogni norma risulta non trovata (utile senza archivio)."""

    def __init__(self, con: sqlite3.Connection | None, lang: str = "it", oggi: str | None = None):
        self.con = con
        self.lang = lang
        self.oggi = oggi or datetime.date.today().isoformat()
        self._cache: dict[str, dict] = {}

    @classmethod
    def da_archivio(cls, db: Path | None = None, lang: str = "it") -> "Risolutore":
        try:
            db = db or percorso_archivio()
        except ImportError:
            return cls(None, lang)
        if not Path(db).exists():
            return cls(None, lang)
        con = sqlite3.connect(f"{Path(db).resolve().as_uri()}?mode=ro", uri=True, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return cls(con, lang)

    def __call__(self, n: dict) -> dict:
        k = chiave(n)
        if k not in self._cache:
            self._cache[k] = self._ue(n) if "ue" in n else self._ch(n)
            self._cache[k]["chiave"] = k
        return dict(self._cache[k])

    def _vuota(self, citazione: str, url: str = "", motivo: str = "non in archivio") -> dict:
        return {"trovata": False, "citazione": citazione, "url": url, "vigenza": "", "impronta": "", "estratto": "",
                "rubrica": "", "versione_futura": "", "motivo": motivo}

    def _ch(self, n: dict) -> dict:
        rs = str(n["rs"])
        citazione = f"{_dettaglio(n)} RS {rs}"
        if self.con is None:
            return self._vuota(citazione, motivo="archivio di Nuova-Norma non disponibile")
        from . import _nn  # noqa: F401
        from nn import store
        act = store.find_act(self.con, rs)
        if act is None:
            return self._vuota(citazione, motivo=f"la legge RS {rs} non e in archivio (py -m nn importa {rs})")
        s = sigla(rs, act["title"])
        citazione = f"{_dettaglio(n)} {s} (RS {rs})"
        url = act["uri"].replace("fedlex.data.admin.ch", "www.fedlex.admin.ch") + f"/{self.lang}"
        if not act["in_force"]:
            return self._vuota(citazione, url, "la legge non e piu in vigore")
        date = store.list_dates(self.con, act["uri"], self.lang)
        if not date:
            return self._vuota(citazione, url, f"nessuna versione in lingua {self.lang}")
        vigenza = store.in_force_date(date, self.oggi)
        art = store.find_article(self.con, act["uri"], self.lang, str(n["art"]), vigenza)
        if art is None:
            return self._vuota(citazione, url, f"l'art. {n['art']} non esiste nella versione in vigore")
        future = [d for d in date if d > self.oggi]
        return {"trovata": True, "citazione": citazione, "legge": act["title"], "sigla": s, "url": f"{url}#{art.eid}",
                "vigenza": vigenza, "versione_futura": future[0] if future else "", "rubrica": art.heading or "",
                "impronta": impronta(art.text), "estratto": _estratto(art.text, n.get("cpv")), "motivo": ""}

    def _ue(self, n: dict) -> dict:
        celex = n["ue"]
        citazione = f"{_dettaglio(n)} {celex}"
        url = f"https://eur-lex.europa.eu/legal-content/{self.lang.upper()}/TXT/?uri=CELEX:{celex}"
        if self.con is None:
            return self._vuota(citazione, url, "archivio di Nuova-Norma non disponibile")
        from . import _nn  # noqa: F401
        from nn import documenti
        try:
            doc = documenti.find(self.con, "eurlex", celex)
        except sqlite3.Error:
            doc = None
        if not doc:
            return self._vuota(citazione, url, f"l'atto UE {celex} non e in archivio (py -m nn aggiorna-raccolte eurlex)")
        citazione = f"{_dettaglio(n)} {doc.get('title') or celex}"
        testo = _articolo_ue(doc.get("text") or "", str(n["art"]))
        if not testo:
            return self._vuota(citazione, url, f"l'art. {n['art']} non si trova nel testo in archivio")
        return {"trovata": True, "citazione": citazione, "legge": doc.get("title") or celex, "sigla": celex, "url": url,
                "vigenza": doc.get("valid_from") or "", "versione_futura": "", "rubrica": "",
                "impronta": impronta(testo), "estratto": testo[:1500], "motivo": ""}


def _estratto(testo: str, cpv: str | None, massimo: int = 1500) -> str:
    """Il capoverso citato, se si riesce a isolarlo; altrimenti l'inizio dell'articolo."""
    if cpv:
        m = re.search(rf"(?:^|\s){re.escape(str(cpv))}\s+(.+?)(?=\s\d+\s+[A-ZÀ-Ý]|$)", testo, re.S)
        if m:
            return f"{cpv} {m.group(1).strip()}"[:massimo]
    return testo[:massimo]


def _articolo_ue(testo: str, art: str) -> str:
    m = re.search(rf"Articolo\s+{re.escape(art)}\b(.+?)(?=\nArticolo\s+\d+|\Z)", testo, re.S)
    return ("Articolo " + art + m.group(1)).strip() if m else ""
