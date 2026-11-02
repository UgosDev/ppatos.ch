"""Condizioni dei modelli: un piccolo linguaggio in JSON, valutato dal codice (niente eval).

Forme ammesse:
  {"d": "id", "uguale": valore}         la risposta e uguale a valore
  {"d": "id", "contiene": valore}       la risposta (scelte multiple o elenco) contiene valore
  {"d": "id", "vero": true}             risposta si/no (anche "vero": false)
  {"d": "id", "compilata": true}        c'e una risposta non vuota (un elenco vuoto non conta)
  {"d": "id", "qualcuno": {"campo": "paese", "fuori": [...]}}
                                        in una tabella, almeno una riga con il campo fuori dall'elenco
                                        ("@CH" e "@CH_UE_SEE" sono elenchi di Stati gia pronti)
  {"tutte": [...]}, {"una": [...]}, {"non": {...}}

Logica a tre valori: se una condizione dipende da una risposta non ancora data o «da decidere» (DA_DECIDERE),
il risultato e None. Il questionario non mostra una domanda finche la sua condizione e None; l'assemblaggio
non include la clausola e la segnala tra i punti aperti.
"""

from __future__ import annotations

DA_DECIDERE = "?"


class _Nascosta:
    """Risposta di una domanda che non si pone (la sua condizione e falsa): conta come «no» o «vuota»."""

    def __repr__(self):
        return "NASCOSTA"


NASCOSTA = _Nascosta()

_CH = {"ch", "che", "svizzera", "schweiz", "suisse", "svizra", "switzerland"}
_UE_SEE = {
    # codici ISO e nomi italiani degli Stati UE e SEE
    "at", "austria", "be", "belgio", "bg", "bulgaria", "cy", "cipro", "cz", "cechia", "repubblica ceca", "de", "germania",
    "dk", "danimarca", "ee", "estonia", "es", "spagna", "fi", "finlandia", "fr", "francia", "gr", "grecia", "hr", "croazia",
    "hu", "ungheria", "ie", "irlanda", "it", "italia", "lt", "lituania", "lu", "lussemburgo", "lv", "lettonia", "mt", "malta",
    "nl", "paesi bassi", "olanda", "pl", "polonia", "pt", "portogallo", "ro", "romania", "se", "svezia", "si", "slovenia",
    "sk", "slovacchia", "is", "islanda", "li", "liechtenstein", "no", "norvegia", "ue", "eu", "unione europea",
}
ELENCHI = {"@CH": _CH, "@CH_UE_SEE": _CH | _UE_SEE}

OPERATORI = ("uguale", "contiene", "vero", "compilata", "qualcuno")


def manca(valore) -> bool:
    return valore is None or valore is NASCOSTA or valore == DA_DECIDERE


def _elenco(voci) -> set:
    insieme = set()
    for v in voci:
        insieme |= ELENCHI.get(v, {str(v).strip().lower()})
    return insieme


def valuta(cond, risposte: dict):
    """True, False o None (dipende da una risposta mancante). Una condizione assente vale True."""
    if cond is None:
        return True
    if "tutte" in cond:
        esiti = [valuta(c, risposte) for c in cond["tutte"]]
        if False in esiti:
            return False
        return None if None in esiti else True
    if "una" in cond:
        esiti = [valuta(c, risposte) for c in cond["una"]]
        if True in esiti:
            return True
        return None if None in esiti else False
    if "non" in cond:
        e = valuta(cond["non"], risposte)
        return None if e is None else not e
    valore = risposte.get(cond["d"])
    if valore is NASCOSTA:
        return (not cond["compilata"]) if "compilata" in cond else False
    if "compilata" in cond:
        if valore is None:
            return None
        piena = valore != DA_DECIDERE and valore not in ("", [], {})
        return piena == bool(cond["compilata"])
    if manca(valore):
        return None
    if "uguale" in cond:
        return valore == cond["uguale"]
    if "contiene" in cond:
        return isinstance(valore, list) and cond["contiene"] in valore
    if "vero" in cond:
        return bool(valore) == bool(cond["vero"])
    if "qualcuno" in cond:
        q = cond["qualcuno"]
        ammessi = _elenco(q.get("fuori", []))
        return any(str(r.get(q["campo"], "")).strip().lower() not in ammessi for r in (valore or []))
    raise ValueError(f"Condizione non riconosciuta: {cond!r}")


def domande_usate(cond) -> set:
    """Gli id delle domande da cui dipende una condizione (per i controlli del modello)."""
    if cond is None:
        return set()
    for chiave in ("tutte", "una"):
        if chiave in cond:
            return set().union(*(domande_usate(c) for c in cond[chiave])) if cond[chiave] else set()
    if "non" in cond:
        return domande_usate(cond["non"])
    return {cond["d"]}


def controlla(cond) -> list[str]:
    """Errori di forma di una condizione (lista vuota se e corretta)."""
    if cond is None:
        return []
    if not isinstance(cond, dict):
        return [f"condizione non valida: {cond!r}"]
    errori = []
    for chiave in ("tutte", "una"):
        if chiave in cond:
            if not isinstance(cond[chiave], list) or not cond[chiave]:
                return [f"«{chiave}» vuole un elenco non vuoto"]
            for c in cond[chiave]:
                errori += controlla(c)
            return errori
    if "non" in cond:
        return controlla(cond["non"])
    if "d" not in cond:
        return [f"manca «d» in {cond!r}"]
    ops = [o for o in OPERATORI if o in cond]
    if len(ops) != 1:
        return [f"serve esattamente un operatore tra {', '.join(OPERATORI)} in {cond!r}"]
    if ops[0] == "qualcuno" and "campo" not in cond["qualcuno"]:
        errori.append(f"«qualcuno» senza «campo» in {cond!r}")
    return errori


def descrivi(cond, domande: dict, risposte: dict) -> str:
    """La condizione in parole, con la risposta data: serve a spiegare perche una clausola non c'e."""
    if cond is None:
        return "sempre"
    if "tutte" in cond:
        return " e ".join(descrivi(c, domande, risposte) for c in cond["tutte"])
    if "una" in cond:
        return "(" + " oppure ".join(descrivi(c, domande, risposte) for c in cond["una"]) + ")"
    if "non" in cond:
        return "non " + descrivi(cond["non"], domande, risposte)
    d = domande.get(cond["d"], {})
    titolo = d.get("testo", cond["d"])
    data = risposte.get(cond["d"])
    if data is NASCOSTA:
        detto = "domanda non posta"
    elif manca(data):
        detto = "ancora da decidere"
    else:
        detto = mostra(d, data)
    if "uguale" in cond:
        atteso = etichetta(d, cond["uguale"])
        return f"«{titolo}» = {atteso} (risposta: {detto})"
    if "contiene" in cond:
        return f"«{titolo}» comprende {etichetta(d, cond['contiene'])} (risposta: {detto})"
    if "vero" in cond:
        return f"«{titolo}» = {'sì' if cond['vero'] else 'no'} (risposta: {detto})"
    if "compilata" in cond:
        return f"«{titolo}» {'compilata' if cond['compilata'] else 'vuota'} (risposta: {detto})"
    q = cond["qualcuno"]
    return f"in «{titolo}» almeno una riga con {q['campo']} fuori da {', '.join(q.get('fuori', []))}"


def etichetta(domanda: dict, valore) -> str:
    for o in domanda.get("opzioni", []):
        if o["valore"] == valore:
            return o.get("etichetta", str(valore))
    if isinstance(valore, bool):
        return "sì" if valore else "no"
    return str(valore)


def mostra(domanda: dict, valore) -> str:
    """Una risposta in forma leggibile, su una riga."""
    if manca(valore):
        return "da decidere"
    if isinstance(valore, bool):
        return "sì" if valore else "no"
    if isinstance(valore, list):
        if not valore:
            return "nessuno"
        if isinstance(valore[0], dict):
            fmt = domanda.get("formato_riga")
            return "; ".join(fmt.format_map(_Riga(r)) if fmt else ", ".join(str(v) for v in r.values()) for r in valore)
        return ", ".join(etichetta(domanda, v) for v in valore)
    return etichetta(domanda, valore)


class _Riga(dict):
    def __missing__(self, chiave):
        return f"[{chiave}?]"
