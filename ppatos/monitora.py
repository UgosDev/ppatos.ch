"""Monitoraggio: le norme citate da una bozza sono cambiate?

Si rileggono le norme nell'archivio di Nuova-Norma (aggiornato ogni notte) e si confrontano versione e impronta con
quelle registrate al momento della bozza. Ogni differenza indica le clausole da rivedere.
"""

from __future__ import annotations

STATI = ("invariata", "cambiata", "non_piu_trovata", "ora_trovata", "non_trovata")


def confronta(bozza: dict, risolvi) -> list[dict]:
    esiti = []
    for k, prima in sorted(bozza["norme"].items()):
        ora = risolvi(prima["norma"])
        if prima["trovata"] and ora["trovata"]:
            stato = "invariata" if ora["impronta"] == prima["impronta"] else "cambiata"
        elif prima["trovata"]:
            stato = "non_piu_trovata"
        elif ora["trovata"]:
            stato = "ora_trovata"
        else:
            stato = "non_trovata"
        esiti.append({"norma": k, "citazione": ora.get("citazione") or prima["citazione"], "stato": stato,
                      "vigenza_prima": prima.get("vigenza", ""), "vigenza_ora": ora.get("vigenza", ""),
                      "versione_futura": ora.get("versione_futura", ""), "clausole": prima["clausole"],
                      "motivo": ora.get("motivo", "")})
    return esiti


def da_rivedere(esiti: list[dict]) -> list[dict]:
    return [e for e in esiti if e["stato"] != "invariata" or e["versione_futura"]]
