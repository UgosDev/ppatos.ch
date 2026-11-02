"""Controllo dei modelli: ogni errore di scrittura di un modello va trovato qui, non da un cliente.

Verifica: id unici, tipi e opzioni delle domande, sezioni esistenti, condizioni ben formate e su domande esistenti,
segnaposto su domande esistenti (e campi di opzione esistenti), domande che vengono prima di quelle da cui
dipendono, forma delle norme. Con un risolutore verifica anche che ogni norma esista nell'archivio.
"""

from __future__ import annotations

from . import condizioni, questionario
from .assembla import SEGNAPOSTO


def controlla(modello: dict, risolvi=None) -> list[str]:
    errori: list[str] = []
    for campo in ("id", "titolo", "domande", "sezioni", "clausole"):
        if campo not in modello:
            errori.append(f"manca il campo «{campo}»")
    if errori:
        return errori

    domande = {}
    for i, d in enumerate(modello["domande"]):
        dove = f"domanda {d.get('id', i)}"
        if d.get("id") in domande:
            errori.append(f"{dove}: id doppio")
        domande[d.get("id")] = d
        if d.get("tipo") not in questionario.TIPI:
            errori.append(f"{dove}: tipo «{d.get('tipo')}» sconosciuto")
        if not d.get("testo"):
            errori.append(f"{dove}: manca il testo")
        if d.get("tipo") in ("scelta", "scelte"):
            valori = [o.get("valore") for o in d.get("opzioni", [])]
            if not valori or len(valori) != len(set(valori)):
                errori.append(f"{dove}: opzioni mancanti o doppie")
        if d.get("tipo") == "tabella" and not d.get("campi"):
            errori.append(f"{dove}: una tabella vuole «campi»")
        errori += [f"{dove}: {e}" for e in condizioni.controlla(d.get("se"))]
        for usata in condizioni.domande_usate(d.get("se")):
            if usata not in domande:      # deve venire prima: il questionario segue l'ordine
                errori.append(f"{dove}: la condizione usa «{usata}», che non esiste o viene dopo")

    sezioni = {s["id"] for s in modello["sezioni"]}
    visti = set()
    for c in modello["clausole"]:
        dove = f"clausola {c.get('id')}"
        if c.get("id") in visti:
            errori.append(f"{dove}: id doppio")
        visti.add(c.get("id"))
        for campo in ("titolo", "sezione", "testo"):
            if not c.get(campo):
                errori.append(f"{dove}: manca «{campo}»")
        if c.get("sezione") not in sezioni:
            errori.append(f"{dove}: sezione «{c.get('sezione')}» inesistente")
        errori += [f"{dove}: {e}" for e in condizioni.controlla(c.get("se"))]
        for usata in condizioni.domande_usate(c.get("se")):
            if usata not in domande:
                errori.append(f"{dove}: la condizione usa la domanda inesistente «{usata}»")
        for p in c.get("punti_aperti", []):
            errori += [f"{dove}, punto aperto: {e}" for e in condizioni.controlla(p.get("se"))]
        for m in SEGNAPOSTO.finditer(c.get("testo", "")):
            did, filtro, campo = m.groups()
            if did not in domande:
                errori.append(f"{dove}: segnaposto {{{did}}} su una domanda inesistente")
                continue
            if filtro and filtro != "elenco":
                errori.append(f"{dove}: filtro «{filtro}» sconosciuto")
            if campo and not all(campo in o for o in domande[did].get("opzioni", [])):
                errori.append(f"{dove}: non tutte le opzioni di «{did}» hanno il campo «{campo}»")
        for n in c.get("norme", []):
            if not (("rs" in n) ^ ("ue" in n)) or "art" not in n:
                errori.append(f"{dove}: norma malformata {n!r}")
            elif risolvi is not None:
                info = risolvi(n)
                # il diritto UE puo mancare dall'archivio: la bozza lo segnala come punto aperto
                if not info["trovata"] and "rs" in n:
                    errori.append(f"{dove}: {info['citazione']}: {info['motivo']}")
        if not c.get("norme") and not c.get("senza_norme"):
            errori.append(f"{dove}: nessuna norma (se e voluto, metti \"senza_norme\": \"motivo\")")

    for ctrl in modello.get("controlli", []):
        errori += [f"controllo: {e}" for e in condizioni.controlla(ctrl.get("se"))]
        for usata in condizioni.domande_usate(ctrl.get("se")):
            if usata not in domande:
                errori.append(f"controllo: usa la domanda inesistente «{usata}»")
    return errori
