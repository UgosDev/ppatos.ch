"""Assemblaggio della bozza: dalle risposte alle clausole, ognuna legata alle sue norme.

Regole:
- il testo viene solo dalle clausole del modello; il codice sostituisce i segnaposto, non scrive frasi giuridiche;
- una clausola entra se la sua condizione e vera; se dipende da una risposta mancante non entra e diventa un punto
  aperto; se e falsa finisce tra le clausole non incluse, con il motivo in parole;
- una risposta «da decidere» lascia nel testo un segnaposto visibile «[DA DECIDERE: ...]» e un punto aperto;
- ogni norma citata viene letta nell'archivio (versione in vigore e impronta); una norma non trovata e un punto aperto;
- la bozza ha un'impronta propria: cambia se cambia anche una sola parola o la versione di una norma.

Segnaposto nel testo delle clausole:
  {id}                  la risposta in forma leggibile (etichetta per le scelte, «sì/no», righe di una tabella)
  {id|elenco}           un elenco puntato (scelte multiple: etichette; tabella: una riga per voce)
  {id|elenco:campo}     elenco puntato con un campo delle opzioni (es. descrizione, base_ue)
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re

from . import __version__, condizioni, questionario
from .condizioni import DA_DECIDERE

SEGNAPOSTO = re.compile(r"\{(\w+)(?:\|(\w+)(?::(\w+))?)?\}")


class Incompleto(ValueError):
    pass


def _segnaposto(d: dict) -> str:
    return f"[DA DECIDERE: {d.get('breve') or d['testo']}]"


def _opzione(d: dict, valore) -> dict:
    return next((o for o in d.get("opzioni", []) if o["valore"] == valore), {"valore": valore, "etichetta": str(valore)})


def rendi(testo: str, domande: dict, risposte: dict, da_decidere: set) -> str:
    def sostituisci(m):
        did, filtro, campo = m.group(1), m.group(2), m.group(3)
        d = domande[did]
        valore = risposte.get(did)
        if condizioni.manca(valore):
            da_decidere.add(did)
            return _segnaposto(d)
        if filtro == "elenco":
            if isinstance(valore, list) and valore and isinstance(valore[0], dict):
                voci = [condizioni.mostra(d, [r]) for r in valore]
            elif isinstance(valore, list):
                voci = [_opzione(d, v).get(campo or "etichetta", str(v)) for v in valore]
            else:
                voci = [_opzione(d, valore).get(campo or "etichetta", str(valore))]
            voci = [str(v).strip().rstrip(";.").rstrip() for v in voci]
            return "".join(f"\n- {v}{';' if i < len(voci) - 1 else '.'}" for i, v in enumerate(voci))
        if campo:
            return str(_opzione(d, valore).get(campo, valore))
        return condizioni.mostra(d, valore)
    return SEGNAPOSTO.sub(sostituisci, testo)


def assembla(modello: dict, risposte: dict, risolvi, completa: bool = False, oggi: str | None = None) -> dict:
    """La bozza come dizionario (salvabile in JSON). risolvi: callable(norma) -> dict (vedi norme.Risolutore)."""
    pulite, errori = questionario.valida(modello, risposte)
    if errori:
        raise ValueError("Risposte non valide:\n" + "\n".join(f"- {k}: {v}" for k, v in errori.items()))
    r = questionario.effettive(modello, pulite)
    if completa:
        mancano = questionario.prossime(modello, pulite) + questionario.mancanti(modello, pulite)
        if mancano:
            raise Incompleto("Mancano risposte: " + ", ".join(dict.fromkeys(d["id"] for d in mancano)))

    domande = questionario.per_id(modello)
    sezioni = {s["id"]: s for s in modello["sezioni"]}
    norme: dict[str, dict] = {}
    incluse, escluse, punti = [], [], []
    da_decidere: set = set()

    def punto(testo, tipo, clausola=""):
        p = {"tipo": tipo, "testo": testo, "clausola": clausola}
        if p not in punti:
            punti.append(p)

    for c in modello["clausole"]:
        esito = condizioni.valuta(c.get("se"), r)
        if esito is None:
            punto(f"La clausola «{c['titolo']}» dipende da una risposta non ancora data: "
                  f"{condizioni.descrivi(c.get('se'), domande, r)}.", "risposta_mancante", c["id"])
            continue
        if not esito:
            escluse.append({"id": c["id"], "titolo": c["titolo"], "sezione": c["sezione"],
                            "perche": "Si applica solo se " + condizioni.descrivi(c.get("se"), domande, r) + "."})
            continue
        prima = set(da_decidere)
        testo = rendi(c["testo"], domande, r, da_decidere)
        rif = []
        for n in c.get("norme", []):
            info = risolvi(n)
            k = info.get("chiave") or n.get("chiave") or json.dumps(n, sort_keys=True)
            norme.setdefault(k, {**info, "norma": n, "clausole": []})["clausole"].append(c["id"])
            rif.append(k)
        for p in c.get("punti_aperti", []):
            if condizioni.valuta(p.get("se"), r) is not False:
                punto(p["testo"], "per_avvocato", c["id"])
        for did in sorted(da_decidere - prima, key=list(domande).index):
            punto(f"Da decidere: {domande[did]['testo']}", "da_decidere", c["id"])
        incluse.append({"id": c["id"], "titolo": c["titolo"], "sezione": c["sezione"], "testo": testo, "norme": rif,
                        "motivo": c.get("motivo", ""), "alternative": c.get("alternative", []),
                        "revisione": c.get("revisione", modello.get("revisione", "bozza"))})

    for k, info in norme.items():
        if not info["trovata"]:
            punto(f"Norma non verificata: {info['citazione']} ({info['motivo']}).", "norma", ", ".join(info["clausole"]))
        elif info.get("versione_futura"):
            punto(f"{info['citazione']}: c'e una versione che entra in vigore il {info['versione_futura']}; "
                  "verificare se cambia la clausola.", "norma", ", ".join(info["clausole"]))

    for ctrl in modello.get("controlli", []):
        if condizioni.valuta(ctrl["se"], r) is True:
            punto(ctrl["messaggio"], "coerenza")

    ordine = [s["id"] for s in modello["sezioni"]]
    incluse.sort(key=lambda c: ordine.index(c["sezione"]))
    numerate, n = [], 0
    for sid in ordine:
        if any(c["sezione"] == sid for c in incluse):
            n += 1
            numerate.append({"id": sid, "numero": n, "titolo": sezioni[sid]["titolo"]})

    bozza = {
        "formato": "ppatos-bozza/1",
        "motore": __version__,
        "modello": {"id": modello["id"], "titolo": modello["titolo"], "versione": modello.get("versione", ""),
                    "revisione": modello.get("revisione", "")},
        "creata_il": datetime.datetime.now().isoformat(timespec="seconds"),
        "oggi": oggi or datetime.date.today().isoformat(),
        "titolo": rendi(modello.get("titolo_documento", modello["titolo"]), domande, r, da_decidere),
        "avvertenza": modello.get("avvertenza", ""),
        "risposte": [{"id": d["id"], "domanda": d["testo"], "risposta": condizioni.mostra(d, r[d["id"]]),
                      "valore": r[d["id"]], "perche": d.get("perche", "")}
                     for d in questionario.visibili(modello, pulite) if d["id"] in r and r[d["id"]] is not condizioni.NASCOSTA],
        "sezioni": numerate,
        "clausole": incluse,
        "escluse": escluse,
        "norme": norme,
        "punti_aperti": punti,
        "completa": not any(p["tipo"] in ("da_decidere", "risposta_mancante") for p in punti),
    }
    bozza["impronta"] = impronta_bozza(bozza)
    return bozza


def impronta_bozza(bozza: dict) -> str:
    """SHA-256 del contenuto che conta: testo delle clausole e versione/impronta delle norme citate."""
    nucleo = {"modello": bozza["modello"], "titolo": bozza["titolo"],
              "clausole": [(c["id"], c["testo"], c["norme"]) for c in bozza["clausole"]],
              "norme": {k: (v["vigenza"], v["impronta"]) for k, v in sorted(bozza["norme"].items())}}
    return hashlib.sha256(json.dumps(nucleo, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


__all__ = ["assembla", "rendi", "impronta_bozza", "Incompleto", "DA_DECIDERE"]
