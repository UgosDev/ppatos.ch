"""Modelli e questionario adattivo.

Un modello (ppatos/modelli/<id>.json) contiene le domande, le sezioni e le clausole di un tipo di documento.
Le domande si mostrano solo quando la loro condizione «se» e vera: il questionario si adatta alle risposte.
Ogni risposta puo essere «da decidere» (DA_DECIDERE): il documento si compila lo stesso, con il segnaposto
visibile e un punto aperto nel pacchetto per l'avvocato.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from . import condizioni
from .condizioni import DA_DECIDERE

CARTELLA_MODELLI = Path(__file__).resolve().parent / "modelli"

TIPI = ("si_no", "scelta", "scelte", "testo", "email", "url", "data", "elenco", "tabella")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL = re.compile(r"^https?://[^\s]+$")


def elenco_modelli() -> list[dict]:
    return [{"id": m["id"], "titolo": m["titolo"], "versione": m.get("versione", "")}
            for m in (carica_modello(p) for p in sorted(CARTELLA_MODELLI.glob("*.json")))]


def carica_modello(rif) -> dict:
    """Per id (es. "privacy-nlpd") o per percorso di un file JSON."""
    p = Path(rif)
    if not p.suffix:
        p = CARTELLA_MODELLI / f"{rif}.json"
    if not p.exists():
        disponibili = ", ".join(x.stem for x in CARTELLA_MODELLI.glob("*.json"))
        raise FileNotFoundError(f"Modello «{rif}» non trovato. Disponibili: {disponibili}")
    return json.loads(p.read_text("utf-8"))


def per_id(modello: dict) -> dict:
    return {d["id"]: d for d in modello["domande"]}


def _oggi() -> str:
    return datetime.date.today().isoformat()


def effettive(modello: dict, risposte: dict) -> dict:
    """Le risposte come le vede il motore. Non modifica l'originale.

    - valori predefiniti applicati (es. data di oggi);
    - le domande che non si pongono (condizione falsa) valgono NASCOSTA, anche se avevano una risposta vecchia:
      cosi una clausola legata a una domanda mai posta e esclusa, non sospesa.
    """
    out = dict(risposte)
    for d in modello["domande"]:
        if condizioni.valuta(d.get("se"), out) is False:
            out[d["id"]] = condizioni.NASCOSTA
        elif d["id"] not in out and "predefinito" in d:
            v = d["predefinito"]
            out[d["id"]] = _oggi() if v == "{oggi}" else v
    return out


def visibili(modello: dict, risposte: dict) -> list[dict]:
    r = effettive(modello, risposte)
    return [d for d in modello["domande"] if condizioni.valuta(d.get("se"), r) is True]


def prossime(modello: dict, risposte: dict) -> list[dict]:
    """Le domande visibili non ancora risposte, nell'ordine del modello."""
    r = effettive(modello, risposte)
    return [d for d in visibili(modello, risposte) if d["id"] not in r]


def mancanti(modello: dict, risposte: dict) -> list[dict]:
    """Le domande visibili e obbligatorie senza una risposta definitiva (assenti o «da decidere»)."""
    r = effettive(modello, risposte)
    return [d for d in visibili(modello, risposte)
            if d.get("obbligatoria", True) and condizioni.manca(r.get(d["id"]))]


def completo(modello: dict, risposte: dict) -> bool:
    return not prossime(modello, risposte) and not mancanti(modello, risposte)


def normalizza(domanda: dict, valore):
    """Controlla e normalizza una risposta. Solleva ValueError con un messaggio comprensibile."""
    if valore == DA_DECIDERE:
        return DA_DECIDERE
    tipo = domanda["tipo"]
    valori = [o["valore"] for o in domanda.get("opzioni", [])]
    if tipo == "si_no":
        if isinstance(valore, bool):
            return valore
        s = str(valore).strip().lower()
        if s in ("si", "sì", "s", "yes", "y", "true", "1"):
            return True
        if s in ("no", "n", "false", "0"):
            return False
        raise ValueError("rispondi sì o no")
    if tipo == "scelta":
        if valore not in valori:
            raise ValueError(f"scegli una di queste: {', '.join(valori)}")
        return valore
    if tipo == "scelte":
        lista = valore if isinstance(valore, list) else [v.strip() for v in str(valore).split(",") if v.strip()]
        sbagliate = [v for v in lista if v not in valori]
        if sbagliate:
            raise ValueError(f"valori non previsti: {', '.join(map(str, sbagliate))}")
        if not lista and domanda.get("obbligatoria", True):
            raise ValueError("scegline almeno una")
        return [v for v in valori if v in lista]   # ordine del modello, senza doppioni
    if tipo in ("testo", "email", "url"):
        s = str(valore).strip()
        if not s:
            raise ValueError("la risposta e vuota")
        if tipo == "email" and not _EMAIL.match(s):
            raise ValueError("indirizzo email non valido")
        if tipo == "url" and not _URL.match(s):
            raise ValueError("indirizzo web non valido (deve iniziare con https://)")
        return s
    if tipo == "data":
        s = str(valore).strip().lower()
        if s == "oggi":
            return _oggi()
        try:
            return datetime.date.fromisoformat(s).isoformat()
        except ValueError:
            raise ValueError("data non valida (formato AAAA-MM-GG)") from None
    if tipo == "elenco":
        lista = valore if isinstance(valore, list) else [v.strip() for v in str(valore).split("\n")]
        return [str(v).strip() for v in lista if str(v).strip()]
    if tipo == "tabella":
        if not isinstance(valore, list):
            raise ValueError("serve un elenco di righe")
        campi = domanda["campi"]
        righe = []
        for i, r in enumerate(valore, 1):
            if not isinstance(r, dict):
                raise ValueError(f"riga {i}: serve un oggetto con {', '.join(campi)}")
            vuoti = [c for c in campi if not str(r.get(c, "")).strip()]
            if vuoti:
                raise ValueError(f"riga {i}: manca {', '.join(vuoti)}")
            righe.append({c: str(r[c]).strip() for c in campi})
        return righe
    raise ValueError(f"tipo di domanda sconosciuto: {tipo}")


def valida(modello: dict, risposte: dict) -> tuple[dict, dict]:
    """(risposte normalizzate, errori per id). Le risposte a domande sconosciute sono errori."""
    domande = per_id(modello)
    pulite, errori = {}, {}
    for k, v in risposte.items():
        if k.startswith("_"):          # commenti nel file delle risposte
            continue
        if k not in domande:
            errori[k] = "domanda inesistente in questo modello"
            continue
        try:
            pulite[k] = normalizza(domande[k], v)
        except ValueError as e:
            errori[k] = str(e)
    return pulite, errori
