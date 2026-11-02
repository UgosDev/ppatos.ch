"""Riga di comando di PPaToS.

  py -m ppatos modelli
  py -m ppatos questionario privacy-nlpd --risposte mie.json     # domanda per domanda, salva dopo ogni risposta
  py -m ppatos domande privacy-nlpd --risposte mie.json          # cosa manca ancora
  py -m ppatos compila privacy-nlpd --risposte mie.json [--uscita cartella] [--completa]
  py -m ppatos controlla data/bozze/.../bozza.json               # le norme citate sono cambiate?
  py -m ppatos controlla-modelli [--archivio]
  py -m ppatos sito [--porta 8767] [--senza-browser]               # il sito locale

Nelle risposte «?» vuol dire «da decidere»: la bozza si compila lo stesso, con il segnaposto e un punto aperto.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from . import assembla, condizioni, controllo_modelli, monitora, norme, pacchetto, questionario

DATA = Path(__file__).resolve().parent.parent / "data"


def _leggi_risposte(p: Path | None) -> dict:
    if p and p.exists():
        return json.loads(p.read_text("utf-8"))
    return {}


def _scrivi_risposte(p: Path, risposte: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(risposte, ensure_ascii=False, indent=2), "utf-8")


def cmd_modelli(a) -> int:
    for m in questionario.elenco_modelli():
        print(f"{m['id']:<20} {m['titolo']} (v. {m['versione']})")
    return 0


def cmd_domande(a) -> int:
    modello = questionario.carica_modello(a.modello)
    pulite, errori = questionario.valida(modello, _leggi_risposte(a.risposte))
    for k, v in errori.items():
        print(f"ERRORE {k}: {v}")
    prossime = questionario.prossime(modello, pulite)
    da_decidere = [d for d in questionario.mancanti(modello, pulite) if d["id"] in pulite]
    if not prossime and not da_decidere:
        print("Questionario completo.")
    for d in prossime:
        print(f"- {d['id']}: {d['testo']}")
    for d in da_decidere:
        print(f"- {d['id']}: {d['testo']}  (da decidere)")
    if prossime:
        print("Dopo queste risposte potrebbero comparire altre domande.")
    return 1 if errori else 0


def _chiedi(d: dict):
    print()
    print(d["testo"] + ("" if d.get("obbligatoria", True) else "  (facoltativa: invio per saltare)"))
    if d.get("aiuto"):
        print(f"  {d['aiuto']}")
    opzioni = d.get("opzioni", [])
    for i, o in enumerate(opzioni, 1):
        print(f"  {i}. {o['etichetta']}")
    tipo = d["tipo"]
    if tipo == "tabella":
        print(f"  Una riga per voce, campi separati da «;»: {'; '.join(d['campi'])}. Riga vuota per finire.")
        righe = []
        while True:
            s = input("  > ").strip()
            if not s:
                return righe
            if s == "?":
                return condizioni.DA_DECIDERE
            parti = [x.strip() for x in s.split(";")]
            righe.append(dict(zip(d["campi"], parti)))
    if tipo == "elenco":
        print("  Una voce per riga. Riga vuota per finire.")
        voci = []
        while True:
            s = input("  > ").strip()
            if not s:
                return voci
            if s == "?":
                return condizioni.DA_DECIDERE
            voci.append(s)
    suggerimento = {"si_no": "s/n", "scelta": "numero", "scelte": "numeri separati da virgola", "data": "AAAA-MM-GG o «oggi»"}
    s = input(f"  ({suggerimento.get(tipo, 'testo')}, «?» = da decidere) > ").strip()
    if s == "?":
        return condizioni.DA_DECIDERE
    if not s and not d.get("obbligatoria", True):
        return None
    if tipo in ("scelta", "scelte") and s:
        try:
            scelte = [opzioni[int(x) - 1]["valore"] for x in s.replace(" ", "").split(",")]
        except (ValueError, IndexError):
            return s     # normalizza() dara l'errore
        return scelte[0] if tipo == "scelta" else scelte
    return s


def cmd_questionario(a) -> int:
    modello = questionario.carica_modello(a.modello)
    print(f"{modello['titolo']}. Le risposte si salvano in {a.risposte} dopo ognuna.")
    risposte = _leggi_risposte(a.risposte)
    while True:
        pulite, _ = questionario.valida(modello, risposte)
        prossime = questionario.prossime(modello, pulite)
        if not prossime:
            break
        d = prossime[0]
        try:
            valore = _chiedi(d)
        except (EOFError, KeyboardInterrupt):
            print("\nInterrotto: le risposte date sono salvate.")
            return 1
        if valore is None:
            valore = [] if d["tipo"] in ("elenco", "tabella", "scelte") else condizioni.DA_DECIDERE
        try:
            risposte[d["id"]] = questionario.normalizza(d, valore)
        except ValueError as e:
            print(f"  Non va: {e}")
            continue
        _scrivi_risposte(a.risposte, risposte)
    print("\nFatto. Ora: py -m ppatos compila", a.modello, "--risposte", a.risposte)
    return 0


def cmd_compila(a) -> int:
    modello = questionario.carica_modello(a.modello)
    risolvi = norme.Risolutore.da_archivio()
    if risolvi.con is None:
        print("Attenzione: archivio di Nuova-Norma non trovato, nessuna norma verra verificata.", file=sys.stderr)
    try:
        b = assembla.assembla(modello, _leggi_risposte(a.risposte), risolvi, completa=a.completa)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    uscita = a.uscita or DATA / "bozze" / f"{modello['id']}-{datetime.datetime.now():%Y%m%d-%H%M%S}"
    for p in pacchetto.salva(b, uscita):
        print(p)
    print(f"Clausole: {len(b['clausole'])}, punti aperti: {len(b['punti_aperti'])}, "
          f"norme: {len(b['norme'])} ({sum(1 for n in b['norme'].values() if n['trovata'])} verificate). "
          + ("Bozza completa." if b["completa"] else "Bozza incompleta: vedi i punti aperti."))
    return 0


def cmd_controlla(a) -> int:
    b = json.loads(Path(a.bozza).read_text("utf-8"))
    esiti = monitora.confronta(b, norme.Risolutore.da_archivio())
    for e in esiti:
        extra = f" (nuova versione dal {e['versione_futura']})" if e["versione_futura"] else ""
        print(f"{e['stato']:<16} {e['citazione']}{extra}  -> {', '.join(e['clausole'])}")
    rivedere = monitora.da_rivedere(esiti)
    print(f"Da rivedere: {len(rivedere)} norme su {len(esiti)}.")
    return 1 if rivedere else 0


def cmd_controlla_modelli(a) -> int:
    risolvi = norme.Risolutore.da_archivio() if a.archivio else None
    if a.archivio and risolvi.con is None:
        print("Archivio di Nuova-Norma non trovato.", file=sys.stderr)
        return 2
    totale = 0
    for m in questionario.elenco_modelli():
        errori = controllo_modelli.controlla(questionario.carica_modello(m["id"]), risolvi)
        totale += len(errori)
        print(f"{m['id']}: {'OK' if not errori else f'{len(errori)} errori'}")
        for e in errori:
            print(f"  - {e}")
    return 1 if totale else 0


def cmd_sito(a) -> int:
    from . import web
    web.serve(a.porta, open_browser=not a.senza_browser)
    return 0


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="ppatos", description="PPaToS: documenti legali su misura, legati alle norme.")
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("modelli", help="elenca i modelli").set_defaults(f=cmd_modelli)
    for nome, f, aiuto in (("domande", cmd_domande, "cosa manca nel questionario"),
                           ("questionario", cmd_questionario, "risponde domanda per domanda")):
        s = sub.add_parser(nome, help=aiuto)
        s.add_argument("modello")
        s.add_argument("--risposte", type=Path, required=(nome == "questionario"))
        s.set_defaults(f=f)
    s = sub.add_parser("compila", help="compone documento, pacchetto per l'avvocato e bozza.json")
    s.add_argument("modello")
    s.add_argument("--risposte", type=Path, required=True)
    s.add_argument("--uscita", type=Path)
    s.add_argument("--completa", action="store_true", help="rifiuta se manca anche una sola risposta")
    s.set_defaults(f=cmd_compila)
    s = sub.add_parser("controlla", help="le norme citate da una bozza sono cambiate?")
    s.add_argument("bozza", type=Path)
    s.set_defaults(f=cmd_controlla)
    s = sub.add_parser("controlla-modelli", help="verifica la scrittura dei modelli")
    s.add_argument("--archivio", action="store_true", help="verifica anche che le norme esistano in archivio")
    s.set_defaults(f=cmd_controlla_modelli)
    s = sub.add_parser("sito", help="apre il sito locale (porta 8767)")
    s.add_argument("--porta", type=int, default=8767)
    s.add_argument("--senza-browser", action="store_true")
    s.set_defaults(f=cmd_sito)
    a = p.parse_args(argv)
    sys.exit(a.f(a))
