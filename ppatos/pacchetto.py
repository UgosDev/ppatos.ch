"""Uscite della bozza: il documento pulito e il pacchetto per l'avvocato.

- documento.md        il testo da pubblicare, senza note interne (i segnaposto «da decidere» restano visibili)
- pacchetto-avvocato.md
                      tutto cio che serve a una revisione rapida: fatti dichiarati, ogni clausola con motivo, norme e
                      alternative scartate, clausole non incluse e perche, punti aperti, norme con versione, impronta
                      ed estratto
- bozza.json          la bozza completa, base del monitoraggio (py -m ppatos controlla bozza.json)
"""

from __future__ import annotations

import json
from pathlib import Path

from .norme import ordine

TIPI_PUNTO = {
    "da_decidere": "Risposte ancora da dare",
    "risposta_mancante": "Clausole sospese in attesa di una risposta",
    "coerenza": "Incoerenze tra le risposte",
    "norma": "Norme da verificare",
    "per_avvocato": "Domande per l'avvocato",
}


def documento_md(b: dict) -> str:
    righe = [f"# {b['titolo']}", ""]
    for s in b["sezioni"]:
        righe += [f"## {s['numero']}. {s['titolo']}", ""]
        for c in (c for c in b["clausole"] if c["sezione"] == s["id"]):
            righe += [c["testo"].strip(), ""]
    return "\n".join(righe).rstrip() + "\n"


def _norme_clausola(b: dict, c: dict) -> list[str]:
    out = []
    for k in c["norme"]:
        n = b["norme"][k]
        stato = f"in vigore dal {n['vigenza']}" if n["trovata"] else f"NON VERIFICATA: {n['motivo']}"
        out.append(f"[{n['citazione']}]({n['url']}) — {stato}" if n.get("url") else f"{n['citazione']} — {stato}")
    return out


def pacchetto_md(b: dict) -> str:
    m = b["modello"]
    r = [f"# Pacchetto per l'avvocato — {b['titolo']}", "",
         f"Modello «{m['titolo']}» versione {m['versione']} ({m['revisione'] or 'stato di revisione non indicato'}), "
         f"motore PPaToS {b['motore']}. Bozza del {b['creata_il'][:10]}, impronta `{b['impronta'][:16]}`.", ""]
    if b.get("avvertenza"):
        r += [f"> {b['avvertenza']}", ""]
    stato = "completa" if b["completa"] else "incompleta: ci sono risposte ancora da dare"
    r += [f"**Stato della bozza:** {stato}. Clausole incluse: {len(b['clausole'])}; non incluse: {len(b['escluse'])}; "
          f"punti aperti: {len(b['punti_aperti'])}; norme citate: {len(b['norme'])} "
          f"(non verificate: {sum(1 for n in b['norme'].values() if not n['trovata'])}).", ""]

    r += ["## 1. Punti aperti", ""]
    if not b["punti_aperti"]:
        r += ["Nessuno.", ""]
    for tipo, titolo in TIPI_PUNTO.items():
        voci = [p for p in b["punti_aperti"] if p["tipo"] == tipo]
        if voci:
            r += [f"### {titolo}", ""]
            r += [f"- {p['testo']}" + (f" _(clausola {p['clausola']})_" if p["clausola"] else "") for p in voci]
            r += [""]

    r += ["## 2. Fatti dichiarati dal cliente", "", "| Domanda | Risposta | Perché la chiediamo |", "|---|---|---|"]
    for x in b["risposte"]:
        cella = lambda s: str(s).replace("|", "\\|").replace("\n", " ")  # noqa: E731
        r.append(f"| {cella(x['domanda'])} | {cella(x['risposta'])} | {cella(x['perche'])} |")
    r += [""]

    r += ["## 3. La bozza, clausola per clausola", ""]
    for s in b["sezioni"]:
        r += [f"### {s['numero']}. {s['titolo']}", ""]
        for c in (c for c in b["clausole"] if c["sezione"] == s["id"]):
            r += [f"#### {c['titolo']} `{c['id']}` — revisione: {c['revisione']}", ""]
            r += ["> " + c["testo"].strip().replace("\n", "\n> "), ""]
            if c["motivo"]:
                r += [f"**Perché:** {c['motivo']}", ""]
            norme = _norme_clausola(b, c)
            if norme:
                r += ["**Norme:**", ""] + [f"- {n}" for n in norme] + [""]
            if c["alternative"]:
                r += ["**Alternative scartate:**", ""]
                r += [f"- «{a['testo']}» — {a['perche']}" for a in c["alternative"]] + [""]

    r += ["## 4. Clausole del modello non incluse", ""]
    r += [f"- **{e['titolo']}** `{e['id']}`: {e['perche']}" for e in b["escluse"]] or ["Nessuna."]
    r += [""]

    r += ["## 5. Norme citate", "",
          "Testo letto nell'archivio di Nuova-Norma. L'impronta è lo SHA-256 del testo dell'articolo: se cambia, "
          "le clausole che lo citano vanno riviste. Fa fede la pubblicazione ufficiale.", ""]
    for k, n in sorted(b["norme"].items(), key=lambda x: ordine(x[0])):
        r += [f"### {n['citazione']}" + (f" — {n['rubrica']}" if n.get("rubrica") else ""), ""]
        if n["trovata"]:
            r += [f"Versione in vigore dal {n['vigenza']}"
                  + (f"; nuova versione dal {n['versione_futura']}" if n.get("versione_futura") else "")
                  + f". Impronta `{n['impronta'][:16]}`. Citata da: {', '.join(n['clausole'])}. [Testo ufficiale]({n['url']})", ""]
            r += ["> " + n["estratto"].strip().replace("\n", "\n> "), ""]
        else:
            r += [f"**Non verificata:** {n['motivo']}. Citata da: {', '.join(n['clausole'])}."
                  + (f" [Testo ufficiale]({n['url']})" if n.get("url") else ""), ""]
    return "\n".join(r).rstrip() + "\n"


def salva(b: dict, cartella: Path) -> list[Path]:
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    file = {
        "documento.md": documento_md(b),
        "pacchetto-avvocato.md": pacchetto_md(b),
        "bozza.json": json.dumps(b, ensure_ascii=False, indent=2),
    }
    out = []
    for nome, testo in file.items():
        p = cartella / nome
        p.write_text(testo, "utf-8")
        out.append(p)
    return out
