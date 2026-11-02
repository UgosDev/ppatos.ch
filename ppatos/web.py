"""Sito locale di PPaToS (porta 8767): home, da dove partiamo, questionario, bozza e pacchetto per l'avvocato.

Dal canvas «PPaToS — design» (tavole Home, Da dove partiamo, Questionario, Bozza, Logo) e dalle «Regole della
triade». Stile e componenti vengono da Nuova-Norma (nn.web.CSS con nn.triade.CSS_TRIADE); l'accento e il blu
di PPaToS. Ascolta solo su questo computer. Solo libreria standard.

Le risposte di ogni documento stanno in data/sessioni/<codice>.json (fuori da git): niente account, niente cookie.
Il codice nell'indirizzo e l'unica chiave: chi lo conosce riprende il documento.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import secrets
import threading
import urllib.parse
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import _nn  # noqa: F401  rende importabile nn dalla cartella accanto
from nn import triade
from nn.web import CSS, LOGO_CSS, citazioni_init, errore_html, logo_anim, non_trovato_html, serve_static, vuoto_html

from . import __version__, assembla, condizioni, norme, pacchetto, questionario
from .condizioni import DA_DECIDERE, NASCOSTA

DATA = Path(__file__).resolve().parent.parent / "data"
ESEMPI = Path(__file__).resolve().parent.parent / "esempi"
NN_SITO = os.environ.get("NN_SITO", "http://127.0.0.1:8765")
ANORMA_SITO = os.environ.get("ANORMA_SITO", "http://127.0.0.1:8766")
SITI = {"nuova-norma": NN_SITO + "/", "anorma": ANORMA_SITO + "/"}
_CODICE = re.compile(r"^[A-Za-z0-9_-]{12,40}$")

# Sostituibile nei test (archivio finto)
RISOLUTORE = norme.Risolutore.da_archivio

# Documenti annunciati in home che non hanno ancora un modello: compaiono «in arrivo», mai come disponibili.
IN_ARRIVO = [
    ("Condizioni d'uso", "Codice delle obbligazioni, LCSl per le condizioni generali"),
    ("Contratto di trattamento dati", "Per chi tratta dati per conto dei propri clienti (art. 9 LPD, art. 28 GDPR)"),
    ("Contratto di lavoro", "Su misura del ruolo, del cantone e del contratto collettivo"),
    ("Patto tra soci", "Quote, decisioni, uscita di un socio"),
]
DESCRIZIONI = {"privacy-nlpd": "nLPD, e GDPR se hai utenti nell'UE"}

CSS_PPATOS = """
header .in,main{max-width:1120px} main.largo,header .in.largo{max-width:1240px}
header .in{padding:24px 2rem;justify-content:space-between;flex-wrap:wrap}
header nav a{padding:12px 14px;color:var(--muted);font-weight:400}
header nav a.bordo{color:var(--fg);border:1px solid var(--line);border-radius:999px}
main{padding:24px 2rem 96px}
h1{font-size:clamp(30px,3.4vw,42px);font-weight:500;letter-spacing:-.02em;line-height:1.2;margin:0 0 12px}
h1.grande{font-size:clamp(40px,5vw,64px);letter-spacing:-.03em;line-height:1.08;margin:0 0 20px}
h2.sez{font-size:28px;font-weight:500;letter-spacing:-.01em;margin:0 0 12px}
.intro{font-size:18px;line-height:1.55;color:var(--muted);max-width:720px;margin:0 0 40px}
.lead{font-size:20px;line-height:1.55;color:var(--muted);max-width:640px;margin:0 0 36px}
.azioni{display:flex;flex-wrap:wrap;gap:12px}
section.blocco{border-top:1px solid var(--line);padding:64px 0}
.griglia{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px}
.passo{background:var(--soft);border-radius:20px;padding:28px;display:flex;flex-direction:column;gap:12px}
.passo h3{margin:0;font-size:19px;font-weight:600} .passo p{margin:0;color:var(--muted);line-height:1.5}
.pannello{border:1px solid var(--line);border-radius:20px;padding:28px;display:flex;flex-direction:column;gap:16px;background:var(--card)}
.pannello.attivo{border-color:var(--accent)}
.pannello h2{margin:0;font-size:20px;font-weight:600}
.pannello p{margin:0;line-height:1.5;color:var(--muted)}
.pannello .testa{display:flex;justify-content:space-between;align-items:center}
ul.elenco{margin:0;padding:0;list-style:none;border:1px solid var(--line);border-radius:16px}
ul.elenco>li{padding:20px 24px;display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px 16px;border-top:1px solid var(--line)}
ul.elenco>li:first-child{border-top:0}
ul.elenco .tit{font-size:18px} ul.elenco .sotto{margin:4px 0 0;font-size:15px;color:var(--muted)}
.onesto{background:var(--soft);border-radius:20px;padding:36px;display:flex;flex-wrap:wrap;gap:24px 48px}
.onesto h2{margin:0;flex:1 1 260px;font-size:24px;font-weight:500;line-height:1.3}
.onesto p{margin:0;flex:2 1 420px;font-size:17px;line-height:1.6;color:var(--muted)}
footer.pie{max-width:1120px;margin:0 auto;padding:32px 2rem 48px;border-top:1px solid var(--line);display:flex;flex-wrap:wrap;
 justify-content:space-between;gap:16px;font-size:14px;color:var(--muted)}
.campo-testo,input.campo-testo,textarea.campo-testo{min-height:48px;padding:0 16px;border:1px solid var(--ctrl);border-radius:12px;font:inherit;font-size:16px;width:100%;background:var(--card);color:var(--fg)}
textarea.campo-testo{padding:12px 16px;min-height:120px}
.codice{background:var(--soft);border-radius:12px;padding:14px 16px;font-family:var(--mono);font-size:14px;overflow-x:auto;white-space:pre}
/* questionario */
.q-layout,.b-layout{display:flex;flex-wrap:wrap;gap:48px;align-items:flex-start}
.q-dom{flex:999 1 560px;min-width:0} .q-lato{flex:1 1 320px;min-width:0;background:var(--soft);border-radius:20px;padding:28px}
.avanz-testa{display:flex;justify-content:space-between;font-size:14px;color:var(--muted);margin-bottom:10px}
.barra-q{height:6px;border-radius:999px;background:var(--line)} .barra-q span{display:block;height:6px;border-radius:999px;background:var(--accent)}
form.qform{display:flex;flex-direction:column;gap:28px;margin-top:40px}
form.qform fieldset{border:0;padding:0;margin:0;display:flex;flex-direction:column;gap:14px;min-width:0}
form.qform legend{padding:0;margin:0 0 8px;font-size:clamp(24px,2.8vw,34px);font-weight:500;letter-spacing:-.02em;line-height:1.25}
.q-aiuto{margin:0 0 8px;font-size:16px;line-height:1.55;color:var(--muted)}
label.opzione{display:flex;gap:14px;align-items:center;min-height:56px;padding:10px 20px;border:1px solid var(--ctrl);border-radius:16px;font-size:17px;cursor:pointer;background:var(--card)}
label.opzione:has(input:checked){border-color:var(--accent);background:var(--tint)}
label.opzione input{width:20px;height:20px;accent-color:var(--accent);flex:none;margin:0}
label.opzione:focus-within{outline:2px solid var(--accent);outline-offset:2px}
.q-etichetta{font-size:14px;color:var(--muted)}
table.righe{width:100%;border-collapse:separate;border-spacing:0 8px} table.righe th{font-size:14px;color:var(--muted);font-weight:500;text-align:left;padding:0 8px 0 0}
table.righe td{padding:0 8px 0 0}
details.perche{border-top:1px solid var(--line);padding-top:18px;margin:0}
details.perche summary{font-size:16px;color:var(--accent);min-height:44px;display:flex;align-items:center}
details.perche p{margin:8px 0 0;font-size:16px;line-height:1.6;color:var(--muted)}
.q-piede{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;align-items:center}
.q-piede .dx{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
ol.sezioni{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:14px;font-size:16px}
ol.sezioni li{display:flex;gap:12px;align-items:center} ol.sezioni li.ora{font-weight:600} ol.sezioni li.da_fare{color:var(--muted)}
.nota-privata{margin-top:24px;padding-top:20px;border-top:1px solid var(--line);font-size:14px;color:var(--muted);display:flex;gap:10px}
.errore-campo{border:1px solid var(--warn);background:var(--warn-bg);border-radius:16px;padding:12px 16px;display:flex;gap:10px;align-items:flex-start}
/* bozza */
.b-doc{flex:999 1 620px;min-width:0} .b-lato{flex:1 1 360px;min-width:0;display:flex;flex-direction:column;gap:20px}
.b-doc h1{font-family:var(--serif);font-size:40px;font-weight:400;letter-spacing:-.01em;margin:0 0 32px}
.b-sez{border-top:1px solid var(--line)}
.b-claus{display:flex;flex-wrap:wrap;gap:12px 32px;padding:28px 0;border-bottom:1px solid var(--line)}
.b-testo{flex:999 1 420px;font-family:var(--serif);font-size:18px;line-height:1.65;white-space:pre-line}
.b-testo h2{margin:0 0 10px;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:17px;font-weight:600;white-space:normal}
.b-testo p{margin:0}
.b-margine{flex:1 1 200px;font-size:14px;display:flex;flex-direction:column;gap:6px}
.b-margine .st{display:inline-flex;align-items:flex-start;gap:6px;color:var(--muted)} .b-margine .st.ap{color:var(--warn)}
.b-margine .st svg{margin-top:2px}
mark.decidere{background:var(--warn-bg);color:var(--fg);padding:0 3px;border-radius:4px}
.pacchetto{background:var(--soft);border-radius:20px;padding:28px}
.pacchetto h2{margin:0 0 6px;font-size:19px;font-weight:600}
.pacchetto ul{margin:0 0 24px;padding:0;list-style:none;display:flex;flex-direction:column;gap:12px;font-size:16px}
.pacchetto li{display:flex;justify-content:space-between;gap:12px} .pacchetto li .n{color:var(--muted);font-variant-numeric:tabular-nums}
.pacchetto li.ap,.pacchetto li.ap .n{color:var(--warn)}
.pacchetto .btn{width:100%}
.punti{border:1px solid var(--line);border-radius:20px;padding:24px}
.punti h2{margin:0 0 14px;font-size:16px;font-weight:600}
.punti ol{margin:0;padding:0 0 0 20px;display:flex;flex-direction:column;gap:10px;font-size:15px;line-height:1.5;color:var(--muted)}
.punti .tipo{display:block;font-size:13px;color:var(--warn)}
details.escluse{margin-top:32px} details.escluse summary{font-size:15px}
details.escluse li{margin:8px 0;color:var(--muted);font-size:15px}
.trovato li .valore{font-family:var(--mono);font-size:14px;color:var(--muted);margin:4px 0 0}
.trovato .scelta-riga{display:flex;gap:8px}
.trovato label.mini{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 16px;border:1px solid var(--ctrl);border-radius:999px;font-size:14px;cursor:pointer}
.trovato label.mini:has(input:checked){border-color:var(--accent);background:var(--tint)}
.trovato label.mini input{accent-color:var(--accent);margin:0}
@media (max-width:700px){header .in{padding:16px} main{padding:16px 16px 64px} .b-doc h1{font-size:30px}}
"""

# ---------------------------------------------------------------------------
# Sessioni (un file JSON per documento)
# ---------------------------------------------------------------------------

_LOCK = threading.Lock()


def _cartella() -> Path:
    p = Path(os.environ.get("PPATOS_SESSIONI") or DATA / "sessioni")
    p.mkdir(parents=True, exist_ok=True)
    return p


def nuova_sessione(modello: str) -> str:
    questionario.carica_modello(modello)   # solleva se non esiste
    codice = secrets.token_urlsafe(16)
    salva_sessione(codice, {"modello": modello, "risposte": {}, "note": [], "proposte": [],
                            "creata": datetime.datetime.now().isoformat(timespec="seconds")})
    return codice


def leggi_sessione(codice: str) -> dict | None:
    if not codice or not _CODICE.match(codice):
        return None
    p = _cartella() / f"{codice}.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def salva_sessione(codice: str, s: dict) -> None:
    s["aggiornata"] = datetime.datetime.now().isoformat(timespec="seconds")
    with _LOCK:
        p = _cartella() / f"{codice}.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, ensure_ascii=False, indent=2), "utf-8")
        os.replace(tmp, p)


def elenco_sessioni() -> list[dict]:
    out = []
    for p in sorted(_cartella().glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            s = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"codice": p.stem, **s})
    return out


# ---------------------------------------------------------------------------
# Dal modello: quali domande servono a quali sezioni e clausole
# ---------------------------------------------------------------------------

def dipendenze(clausola: dict) -> set:
    """Le domande da cui dipende una clausola: la sua condizione e i segnaposto del testo."""
    return condizioni.domande_usate(clausola.get("se")) | {m.group(1) for m in assembla.SEGNAPOSTO.finditer(clausola["testo"])}


def sezioni_di(modello: dict, did: str) -> list[str]:
    return list(dict.fromkeys(c["sezione"] for c in modello["clausole"] if did in dipendenze(c)))


def stato_sezioni(modello: dict, pulite: dict, corrente: str | None) -> list[dict]:
    """Per il pannello «Il documento prende forma»: fatto, ora, da fare."""
    visibili = {d["id"] for d in questionario.visibili(modello, pulite)}
    out = []
    for s in modello["sezioni"]:
        dip = set().union(*(dipendenze(c) for c in modello["clausole"] if c["sezione"] == s["id"])) & visibili
        if corrente and corrente in dip:
            stato = "ora"
        elif all(d in pulite for d in dip):
            stato = "fatto"
        else:
            stato = "da_fare"
        out.append({"id": s["id"], "titolo": s["titolo"], "stato": stato})
    return out


def norme_della_domanda(modello: dict, did: str, risolvi) -> list[dict]:
    viste, out = set(), []
    for c in modello["clausole"]:
        if did not in dipendenze(c):
            continue
        for n in c.get("norme", []):
            k = norme.chiave(n)
            if k not in viste:
                viste.add(k)
                out.append(risolvi(n))
    return sorted(out, key=lambda x: norme.ordine(x.get("chiave", "")))[:5]


# ---------------------------------------------------------------------------
# Pagine
# ---------------------------------------------------------------------------

_DEV = ('<svg aria-hidden="true" width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="var(--accent)" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round">{}</svg>')
_IC_DOMANDE = _DEV.format('<rect x="4" y="4" width="20" height="20" rx="6"/><path d="M10 11h8M10 15h8M10 19h5"/>')
_IC_SITO = _DEV.format('<circle cx="14" cy="14" r="10"/><path d="M4 14h20M14 4c3 3 4 6.5 4 10s-1 7-4 10M14 4c-3 3-4 6.5-4 10s1 7 4 10"/>')
_IC_CODICE = _DEV.format('<path d="M10 8l-6 6 6 6M18 8l6 6-6 6"/>')
_IC_LUCCHETTO = ('<svg aria-hidden="true" width="18" height="18" viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1.6" '
                 'stroke-linecap="round" style="flex:none"><path d="M5 10V8a6 6 0 0 1 12 0v2"/><rect x="4" y="10" width="14" height="9" rx="3"/></svg>')


def _q(**params) -> str:
    return urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})


def _page(title: str, body: str, testa: str = "", largo: bool = False, azione: dict | None = None,
          pie: bool = True) -> bytes:
    nav = testa or (f'<nav aria-label="Principale" style="display:flex;flex-wrap:wrap;gap:8px;font-size:15px">'
                    f'<a href="/#documenti">Documenti</a><a href="/#come">Come funziona</a>'
                    f'<a href="/documenti" class="bordo">I tuoi documenti</a></nav>')
    footer = ('<footer class="pie"><span>ppatos.ch · Privacy Policy And Terms Of Service · versione '
              f'{escape(__version__)}</span><span>Dati in Svizzera · Nessun tracciamento · Non è una consulenza legale</span>'
              '</footer>') if pie else ""
    cl = ' class="largo"' if largo else ""
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">
<title>{escape(title)} · PPaToS</title><style>{CSS}{CSS_PPATOS}{LOGO_CSS}{triade.tema_css("ppatos")}</style>{triade.favicon_init("ppatos")}</head>
<body><header><div class="in{' largo' if largo else ''}"><a href="/" class="marchio" aria-label="PPaToS, pagina iniziale">{triade.marchio_html("ppatos", 22)}</a>
{nav}</div></header>
<main{cl}>{body}</main>{footer}{citazioni_init(NN_SITO)}{triade.copia_init("ppatos", NN_SITO, azione)}</body></html>""".encode("utf-8")


def home_page() -> bytes:
    modelli = questionario.elenco_modelli()
    righe = "".join(
        f'<li><div><form method="post" action="/nuovo" style="display:inline"><input type="hidden" name="modello" value="{escape(m["id"])}">'
        f'<button type="submit" class="btn-testo" style="padding:0;min-height:0;font-size:18px;color:var(--accent);background:none;border:0;cursor:pointer">'
        f'{escape(m["titolo"])}</button></form><p class="sotto">{escape(DESCRIZIONI.get(m["id"], ""))}</p></div>'
        f'<span class="etichetta">Disponibile</span></li>' for m in modelli)
    righe += "".join(f'<li><div><span class="tit">{escape(t)}</span><p class="sotto">{escape(d)}</p></div>'
                     f'<span class="etichetta e-arrivo">In arrivo</span></li>' for t, d in IN_ARRIVO)
    primo = modelli[0]["id"] if modelli else ""
    passi = [("01", "Racconti cosa fai", "Rispondi a domande che cambiano in base alle risposte. Se sei uno sviluppatore, "
              "puoi anche incollare l'elenco di ciò che il tuo codice usa, e le risposte si compilano da sole."),
             ("02", "Ricevi la bozza", "Ogni clausola porta l'articolo che la giustifica, letto sul testo in vigore. "
              "Quello che le norme non decidono resta segnato come punto aperto."),
             ("03", "L'avvocato rivede", "Gli consegni un pacchetto con bozza, motivi, norme e domande già formulate. "
              "Rivede e firma: meno ore, risposte più chiare.")]
    body = f"""
<section aria-labelledby="h-hero" style="padding:88px 0 80px;max-width:820px">
<p class="occhiello">Documenti legali per piccole realtà</p>
<h1 id="h-hero" class="grande">Cose da grandi,<br>senza il pathos.</h1>
<p class="lead">Privacy policy, condizioni d'uso e, poi, contratti scritti sulla tua situazione, non da un modello vuoto.
Ogni clausola è legata alla norma in vigore. Poi un avvocato rivede, invece di partire da zero.</p>
<div class="azioni"><form method="post" action="/nuovo"><input type="hidden" name="modello" value="{escape(primo)}">
<button type="submit" class="btn btn-primario btn-grande">Inizia un documento</button></form>
<a href="/esempio" class="btn btn-bordo btn-grande">Guarda un esempio</a></div>
</section>
<section class="blocco" id="come" aria-labelledby="h-come"><h2 id="h-come" class="sez" style="margin-bottom:40px">Tre passi, una sola volta dall'avvocato</h2>
<ol class="griglia" style="margin:0;padding:0;list-style:none">{"".join(
        f'<li class="passo"><span class="muted tabular" style="font-size:14px">{n}</span><h3>{escape(t)}</h3><p>{escape(d)}</p></li>'
        for n, t, d in passi)}</ol></section>
<section class="blocco" id="documenti" aria-labelledby="h-doc"><h2 id="h-doc" class="sez">I documenti</h2>
<p class="muted" style="margin:0 0 32px;font-size:17px">Si parte da quelli che servono a chi lancia un servizio online.</p>
<ul class="elenco">{righe}</ul></section>
<section class="blocco" aria-labelledby="h-conf"><h2 id="h-conf" class="sez" style="margin-bottom:32px">Dove si risparmia</h2>
<div class="griglia">
<div class="pannello"><h3 style="margin:0;font-size:17px;font-weight:600;color:var(--muted)">Consulenza da zero</h3>
<ul style="margin:0;padding-left:18px;line-height:1.7;color:var(--muted)"><li>L'avvocato raccoglie i fatti</li><li>Cerca e legge le norme</li>
<li>Scrive la bozza</li><li>Rivede con te</li></ul></div>
<div class="pannello attivo"><h3 style="margin:0;font-size:17px;font-weight:600;color:var(--accent)">Con PPaToS</h3>
<ul style="margin:0;padding-left:18px;line-height:1.7"><li>I fatti li dai tu, una volta</li><li>Le norme sono già citate e verificate</li>
<li>La bozza è pronta</li><li>L'avvocato rivede i punti aperti</li></ul></div></div></section>
<section class="blocco" aria-labelledby="h-onesto"><div class="onesto"><h2 id="h-onesto">Una bozza seria, non un parere legale.</h2>
<p>PPaToS prepara il lavoro e mostra le sue fonti, ma non sostituisce l'avvocato. Per questo ogni documento esce con
l'indicazione chiara di cosa è verificato sul testo della legge e cosa resta da decidere. I modelli di clausola non sono
ancora stati rivisti da un avvocato: la bozza va sempre rivista.</p></div></section>
<section class="blocco" style="padding-bottom:0" aria-labelledby="h-fam"><h2 id="h-fam" style="margin:0 0 32px;font-size:20px;font-weight:500;color:var(--muted)">Fa parte della stessa famiglia</h2>
{triade.famiglia_html("ppatos", SITI)}</section>"""
    return _page("Cose da grandi, senza il pathos", body)


def _testa_doc(s: dict, codice: str, extra: str = "") -> str:
    m = questionario.carica_modello(s["modello"])
    nome = s["risposte"].get("servizio_nome")
    nome = nome if isinstance(nome, str) and nome != DA_DECIDERE else ""
    return (f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;font-size:15px;color:var(--muted)">'
            f'<span>{escape(m["titolo"])}{" · " + escape(nome) if nome else ""}</span>{extra}</div>')


def inizio_page(codice: str, s: dict, errore: str = "") -> bytes:
    proposte = s.get("proposte") or []
    trovato = ""
    if proposte:
        m = questionario.carica_modello(s["modello"])
        dom = questionario.per_id(m)
        righe = []
        for i, (k, v) in enumerate(proposte):
            d = dom[k]
            righe.append(f'<li><div style="min-width:0"><p style="margin:0;font-size:17px">{escape(d["testo"])}</p>'
                         f'<p class="valore">{escape(condizioni.mostra(d, v))}</p></div><div class="scelta-riga">'
                         f'<label class="mini"><input type="radio" name="r{i}" value="si" checked> Confermo</label>'
                         f'<label class="mini"><input type="radio" name="r{i}" value="no"> Non è così</label></div></li>')
        trovato = f"""<section aria-labelledby="i-trov" style="margin-top:64px;border-top:1px solid var(--line);padding-top:48px">
<p class="occhiello">Elenco caricato</p><h2 id="i-trov" class="sez" style="font-size:24px;margin:0 0 8px">Cosa abbiamo trovato</h2>
<p class="muted" style="margin:0 0 28px">Conferma o correggi ogni riga. Le righe confermate rispondono già a una parte del questionario;
quelle che scarti te le chiediamo di nuovo.</p>
<form method="post" action="/conferma" style="display:block"><input type="hidden" name="s" value="{escape(codice)}">
<ul class="elenco trovato">{"".join(righe)}</ul>
<div class="azioni" style="margin-top:24px"><button type="submit" class="btn btn-primario">Usa le righe confermate</button>
<button type="submit" name="azione" value="scarta" class="btn btn-testo">Scarta l'elenco</button></div></form></section>"""
    err = f'<div class="errore-campo" role="alert" style="margin-bottom:24px">{triade.icona_stato("aperto")}<div>{escape(errore)}</div></div>' if errore else ""
    body = f"""{err}<h1>Da dove partiamo?</h1>
<p class="intro">Puoi rispondere tu a tutte le domande, oppure partire da un elenco di ciò che il tuo servizio usa davvero.
In ogni caso rivedi e confermi tutto prima della bozza.</p>
<div class="griglia" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">
<section class="pannello" aria-labelledby="i-1">{_IC_DOMANDE}<h2 id="i-1">Rispondo alle domande</h2>
<p style="flex:1">Per chi non ha ancora un sito o preferisce raccontarlo. Da 10 a 30 domande, secondo le risposte.</p>
<a href="/domanda?{_q(s=codice)}" class="btn btn-bordo">Inizia</a></section>
<section class="pannello" aria-labelledby="i-2"><div class="testa">{_IC_SITO}<span class="etichetta e-arrivo">In arrivo</span></div>
<h2 id="i-2">Analizza il mio sito</h2>
<p>Visiteremo le pagine pubbliche come farebbe un utente: cookie, servizi di terzi caricati, moduli, paese dei server.
Non è ancora pronto: per ora rispondi alle domande.</p>
<label for="i-url" class="q-etichetta">Indirizzo del sito</label>
<input id="i-url" type="url" class="campo-testo" placeholder="https://" disabled aria-describedby="i-2">
<button type="button" class="btn btn-bordo" disabled>Analizza</button></section>
<section class="pannello attivo" aria-labelledby="i-3"><div class="testa">{_IC_CODICE}<span class="etichetta e-prodotto">Per sviluppatori</span></div>
<h2 id="i-3">Parto dal mio codice</h2>
<p>Il codice non lascia mai la tua macchina: a PPaToS arriva solo l'elenco di ciò che usa, come risposte in JSON
(lo stesso formato di <span class="mono" style="font-size:14px">esempi/cookie-banner.json</span>). Lo strumento che lo
ricava dal codice è in arrivo; intanto puoi scriverlo o generarlo tu.</p>
<form method="post" action="/carica" style="display:flex;flex-direction:column;gap:12px">
<input type="hidden" name="s" value="{escape(codice)}">
<label for="i-json" class="q-etichetta">Incolla l'elenco trovato (JSON)</label>
<textarea id="i-json" name="elenco" class="campo-testo mono" style="font-size:14px" spellcheck="false" placeholder='{{"servizio_nome": "...", "cookie": ["necessari"]}}'></textarea>
<button type="submit" class="btn btn-primario">Carica l'elenco trovato</button></form></section>
</div>{trovato}"""
    return _page("Da dove partiamo", body, testa=_testa_doc(s, codice))


def _input_html(d: dict, valore) -> str:
    """Il controllo giusto per il tipo di domanda, con il valore gia dato."""
    did, tipo = d["id"], d["tipo"]
    v = None if condizioni.manca(valore) else valore
    if tipo in ("si_no", "scelta", "scelte"):
        opz = ([{"valore": True, "etichetta": "Sì"}, {"valore": False, "etichetta": "No"}] if tipo == "si_no"
               else d.get("opzioni", []))
        t = "checkbox" if tipo == "scelte" else "radio"
        out = []
        for o in opz:
            val = "si" if o["valore"] is True else "no" if o["valore"] is False else str(o["valore"])
            scelto = (o["valore"] in v) if (tipo == "scelte" and isinstance(v, list)) else (v == o["valore"] and v is not None)
            desc = o.get("descrizione", "")
            sotto = (f'<span class="muted" style="display:block;font-size:14px;line-height:1.4">{escape(desc.rstrip(";."))}</span>'
                     if desc and desc.rstrip(";.").lower() != o["etichetta"].lower() else "")
            out.append(f'<label class="opzione"><input type="{t}" name="v" value="{escape(val)}"{" checked" if scelto else ""}>'
                       f'<span><span style="display:block">{escape(o["etichetta"][:1].upper() + o["etichetta"][1:])}</span>{sotto}</span></label>')
        return "".join(out)
    if tipo == "elenco":
        testo = "\n".join(v) if isinstance(v, list) else ""
        return (f'<label class="q-etichetta" for="v">Una voce per riga</label>'
                f'<textarea id="v" name="v" class="campo-testo">{escape(testo)}</textarea>')
    if tipo == "tabella":
        righe = list(v) if isinstance(v, list) else []
        righe += [{}] * max(2, 5 - len(righe))
        campi = d["campi"]
        testa = "".join(f'<th scope="col">{escape(c.capitalize())}</th>' for c in campi)
        corpo = "".join("<tr>" + "".join(
            f'<td><input class="campo-testo" name="{escape(c)}_{i}" value="{escape(str(r.get(c, "")))}" '
            f'aria-label="{escape(c.capitalize())}, riga {i + 1}"></td>' for c in campi) + "</tr>" for i, r in enumerate(righe))
        return f'<div style="overflow-x:auto"><table class="righe"><thead><tr>{testa}</tr></thead><tbody>{corpo}</tbody></table></div>'
    kind = {"email": "email", "url": "url", "data": "date"}.get(tipo, "text")
    if v is None and d.get("predefinito") == "{oggi}":
        v = datetime.date.today().isoformat()
    lungo = tipo == "testo" and (len(str(v or "")) > 80 or did in ("conservazione",))
    if lungo:
        return (f'<label class="q-etichetta" for="v">La tua risposta</label>'
                f'<textarea id="v" name="v" class="campo-testo">{escape(str(v or ""))}</textarea>')
    segnaposto = 'placeholder="https://" ' if kind == "url" else ""
    return (f'<label class="q-etichetta" for="v">La tua risposta</label>'
            f'<input id="v" name="v" type="{kind}" class="campo-testo" value="{escape(str(v or ""))}" '
            f'{segnaposto}autocomplete="off">')


def leggi_valore(d: dict, form: dict):
    """Dal modulo al valore grezzo che normalizza() controlla."""
    tipo = d["tipo"]
    if tipo == "tabella":
        righe, i = [], 0
        while any(f"{c}_{i}" in form for c in d["campi"]):
            r = {c: form.get(f"{c}_{i}", [""])[0].strip() for c in d["campi"]}
            if any(r.values()):
                righe.append(r)
            i += 1
        return righe
    vals = form.get("v", [])
    if tipo == "scelte":
        return vals
    v = vals[0] if vals else ""
    if tipo == "si_no":
        return v if v else ""
    if tipo == "elenco":
        return v
    return v


def domanda_page(codice: str, s: dict, did: str = "", errore: str = "") -> bytes:
    m = questionario.carica_modello(s["modello"])
    pulite, _ = questionario.valida(m, s["risposte"])
    visibili = questionario.visibili(m, pulite)
    prossime = questionario.prossime(m, pulite)
    d = next((x for x in visibili if x["id"] == did), None) if did else None
    if d is None:
        d = prossime[0] if prossime else None
    if d is None:
        return None   # completo: si va alla bozza
    ids = [x["id"] for x in visibili]
    risposte = sum(1 for x in visibili if x["id"] in pulite and x["id"] != d["id"])
    numero = ids.index(d["id"]) + 1
    totale = max(len(visibili), numero)
    pct = round(100 * risposte / max(totale, 1))
    sez = {x["id"]: x["titolo"] for x in m["sezioni"]}
    gruppo = next((sez[x] for x in sezioni_di(m, d["id"])), "Il servizio")
    prec = next((ids[i] for i in range(ids.index(d["id"]) - 1, -1, -1) if ids[i] in pulite), "")
    risolvi = RISOLUTORE()
    nrm = norme_della_domanda(m, d["id"], risolvi)
    link_norme = " · ".join(
        (f'<a class="cite" href="{escape(n["url"])}" data-nn-cita="{escape(n["citazione"])}" data-nn-url="{escape(n["url"])}" '
         f'target="_blank" rel="noopener">{escape(n["citazione"])}</a>') if n.get("url") else escape(n["citazione"]) for n in nrm)
    stato_norme = ("testo in vigore, verificato oggi" if nrm and all(n["trovata"] for n in nrm)
                   else "alcune norme non sono in archivio: restano da verificare" if nrm else "")
    perche = f"""<details class="perche"><summary>Perché lo chiediamo</summary>
<p>{escape(d.get("perche") or "Serve a decidere quali clausole entrano nel documento.")}</p>
{f'<p style="font-size:15px">{link_norme} · <span class="muted">{escape(stato_norme)}</span></p>' if nrm else ""}</details>"""
    lato = "".join(
        f'<li class="{x["stato"]}">{triade.icona_stato(x["stato"])}<span>{escape(x["titolo"])}'
        f'<span class="sr-only" style="position:absolute;left:-9999px">, {"fatto" if x["stato"] == "fatto" else "in corso" if x["stato"] == "ora" else "da fare"}</span></span></li>'
        for x in stato_sezioni(m, pulite, d["id"]))
    err = (f'<div class="errore-campo" role="alert">{logo_anim("shake", 20)}<div>Non va ancora: {escape(errore)}.</div></div>'
           if errore else "")
    facoltativa = not d.get("obbligatoria", True)
    body = f"""<div class="q-layout"><section class="q-dom" aria-labelledby="q-dom">
<div><div class="avanz-testa"><span>{escape(gruppo)}</span><span class="tabular">{numero} di circa {totale}</span></div>
<div class="barra-q" role="progressbar" aria-label="Avanzamento del questionario" aria-valuemin="0" aria-valuemax="{totale}" aria-valuenow="{risposte}">
<span style="width:{pct}%"></span></div></div>
<form class="qform" method="post" action="/domanda"><input type="hidden" name="s" value="{escape(codice)}"><input type="hidden" name="id" value="{escape(d["id"])}">
{err}<fieldset><legend id="q-dom">{escape(d["testo"])}{' <span class="muted" style="font-size:.55em;font-weight:400;letter-spacing:0">facoltativa</span>' if facoltativa else ""}</legend>
{f'<p class="q-aiuto">{escape(d["aiuto"])}</p>' if d.get("aiuto") else ""}
{_input_html(d, s["risposte"].get(d["id"]))}</fieldset>
{perche}
<div class="q-piede">{f'<a class="btn btn-bordo btn-grande" href="/domanda?{_q(s=codice, id=prec)}">Indietro</a>' if prec else f'<a class="btn btn-bordo btn-grande" href="/inizio?{_q(s=codice)}">Indietro</a>'}
<div class="dx"><button type="submit" name="azione" value="decidere" class="btn btn-testo">{"Salta" if facoltativa else "Non lo so ancora: decidiamo dopo"}</button>
<button type="submit" name="azione" value="avanti" class="btn btn-primario btn-grande">Avanti</button></div></div></form></section>
<aside class="q-lato" aria-labelledby="q-prev"><h2 id="q-prev" style="margin:0 0 6px;font-size:17px;font-weight:600">Il documento prende forma</h2>
<p class="muted" style="margin:0 0 20px;font-size:14px">Ogni risposta riempie una sezione.</p>
<ol class="sezioni">{lato}</ol>
<p style="margin:20px 0 0"><a href="/bozza?{_q(s=codice)}" style="font-size:15px">Guarda la bozza com'è adesso</a></p>
<div class="nota-privata">{_IC_LUCCHETTO}<span>Le risposte restano su questo computer e servono solo a scrivere il tuo documento.</span></div>
</aside></div>"""
    testa = _testa_doc(s, codice, f'<a class="btn btn-bordo btn-piccolo" href="/documenti?{_q(s=codice)}">Salva e continua dopo</a>')
    return _page(d["testo"], body, testa=testa, largo=True, pie=False)


_DECIDERE_RE = re.compile(r"\[DA DECIDERE: [^\]]+\]")


def _testo_clausola(t: str) -> str:
    """Escape del testo, con i segnaposto «da decidere» evidenziati come punto aperto."""
    out, i = [], 0
    for mm in _DECIDERE_RE.finditer(t):
        out.append(escape(t[i:mm.start()]))
        out.append(f'<mark class="decidere">{escape(mm.group(0))}</mark>')
        i = mm.end()
    out.append(escape(t[i:]))
    return "".join(out)


def bozza_html(b: dict, modello: dict, codice: str = "", note: list | None = None, esempio: bool = False) -> str:
    """La bozza con le norme a margine e il pacchetto per l'avvocato (tavola Bozza)."""
    ordine_risposte = [r["id"] for r in b["risposte"]]
    claus_mod = {c["id"]: c for c in modello["clausole"]}
    sez = []
    for s in b["sezioni"]:
        blocchi = []
        prima = True
        for c in (c for c in b["clausole"] if c["sezione"] == s["id"]):
            margine = []
            for k in c["norme"]:
                n = b["norme"][k]
                if n.get("url"):
                    impr = f' data-nn-impronta="{escape(n["impronta"])}"' if n.get("impronta") else ""
                    margine.append(f'<a class="cite" href="{escape(n["url"])}" target="_blank" rel="noopener" '
                                   f'data-nn-cita="{escape(n["citazione"])}" data-nn-url="{escape(n["url"])}"{impr}>'
                                   f'{escape(n["citazione"])}</a>')
                else:
                    margine.append(f'<span>{escape(n["citazione"])}</span>')
            trovate = [b["norme"][k] for k in c["norme"]]
            if trovate and all(n["trovata"] for n in trovate):
                margine.append(f'<span class="st">{triade.icona_stato("verificata", 14)}Verificata sul testo in vigore</span>')
            elif trovate:
                motivo = next(n["motivo"] for n in trovate if not n["trovata"])
                margine.append(f'<span class="st ap">{triade.icona_stato("aperto", 14)}Norma da verificare: {escape(motivo)}</span>')
            if _DECIDERE_RE.search(c["testo"]):
                margine.append(f'<span class="st ap">{triade.icona_stato("aperto", 14)}Punto aperto: manca una tua risposta</span>')
            dip = dipendenze(claus_mod[c["id"]]) if c["id"] in claus_mod else set()
            numeri = sorted(ordine_risposte.index(x) + 1 for x in dip if x in ordine_risposte)
            if numeri:
                parola = "Dalla tua risposta" if len(numeri) == 1 else "Dalle tue risposte"
                margine.append(f'<span class="st">{parola} {", ".join(map(str, numeri[:4]))}{"…" if len(numeri) > 4 else ""}</span>')
            fonte = b["norme"][c["norme"][0]] if c["norme"] else None
            df = (f' data-fonte="{escape(fonte["citazione"])}" data-fonte-url="{escape(fonte.get("url", ""))}"' if fonte else "")
            titolo = f'<h2>{s["numero"]}. {escape(s["titolo"])}</h2>' if prima else ""
            prima = False
            blocchi.append(f'<section class="b-claus" id="c-{escape(c["id"])}"{df}><div class="b-testo">{titolo}'
                           f'<p>{_testo_clausola(c["testo"].strip())}</p></div><div class="b-margine">{"".join(margine)}</div></section>')
        sez.append("".join(blocchi))
    punti = list(b["punti_aperti"])
    for nt in note or []:
        punti.append({"tipo": "per_avvocato", "testo": f"Da chiarire: «{nt['testo']}»" + (f" ({nt['fonte']})" if nt.get("fonte") else ""),
                      "clausola": ""})
    punti_html = "".join(
        f'<li><span class="tipo">{escape(pacchetto.TIPI_PUNTO.get(p["tipo"], p["tipo"]))}</span>{escape(p["testo"])}</li>' for p in punti)
    n_aperti = len(punti)
    n_norme = len(b["norme"])
    n_verif = sum(1 for n in b["norme"].values() if n["trovata"])
    scarica = (lambda f: f"/esempio/scarica?{_q(f=f)}") if esempio else (lambda f: f"/scarica?{_q(s=codice, f=f)}")
    escluse = "".join(f'<li><strong style="color:var(--fg);font-weight:600">{escape(e["titolo"])}</strong>: {escape(e["perche"])}</li>'
                      for e in b["escluse"])
    stato = "completa, in attesa di revisione" if b["completa"] else "incompleta: ci sono risposte da dare"
    g = datetime.date.fromisoformat(b["oggi"])
    data = f"{g.day}.{g.month}.{g.year}"
    return f"""<div class="b-layout"><article class="b-doc" aria-labelledby="b-tit">
<p class="muted" style="margin:0 0 8px;font-size:14px">{"Esempio · " if esempio else ""}Bozza · {escape(data)} · {escape(stato)}</p>
<h1 id="b-tit">{_testo_clausola(b["titolo"])}</h1>
<div class="b-sez">{"".join(sez)}</div>
{f'<details class="escluse"><summary>Clausole del modello non incluse ({len(b["escluse"])}) e perché</summary><ul>{escluse}</ul></details>' if escluse else ""}
<p class="muted" style="font-size:14px;margin-top:32px">{escape(b.get("avvertenza", ""))}</p>
</article>
<aside class="b-lato" aria-labelledby="b-pac">
<div class="pacchetto"><h2 id="b-pac">Pacchetto per l'avvocato</h2>
<p class="muted" style="margin:0 0 20px;font-size:15px;line-height:1.5">Tutto quello che serve per una revisione breve, in un solo file.</p>
<ul><li><span>Bozza completa</span><span class="n">{len(b["sezioni"])} sezioni</span></li>
<li><span>Norme citate, con il testo</span><span class="n">{n_norme}{f" ({n_norme - n_verif} da verificare)" if n_verif < n_norme else ""}</span></li>
<li><span>Motivo di ogni scelta</span><span class="n">per clausola</span></li>
<li><span>Le tue risposte</span><span class="n">{len(b["risposte"])}</span></li>
<li class="{"ap" if n_aperti else ""}"><span>Punti aperti, già formulati</span><span class="n">{n_aperti}</span></li></ul>
<a href="{scarica("pacchetto")}" class="btn btn-primario btn-grande">Scarica il pacchetto</a>
<a href="{scarica("bozza")}" class="btn btn-testo" style="margin-top:6px">Dati della bozza (JSON, per il controllo delle norme)</a></div>
<div class="punti"><h2>Punti aperti</h2>{f"<ol>{punti_html}</ol>" if punti_html else '<p class="muted" style="margin:0">Nessuno.</p>'}
<p class="muted" style="margin:14px 0 0;font-size:13px">Seleziona una frase della bozza e fai clic destro: «Aggiungi una domanda per l'avvocato» la mette qui.</p></div>
<p class="muted" style="margin:0;font-size:14px;line-height:1.5;display:flex;gap:10px">{triade.delta_svg(18, "var(--muted)", "flex:none;margin-top:1px")}
<span>Ogni norma citata ha un'impronta del testo: se l'articolo cambia, il controllo delle norme lo vede e segnala le clausole da rivedere.
Impronta della bozza <span class="mono">{escape(b["impronta"][:12])}</span>.</span></p>
</aside></div>"""


def _porta_atrium_html(b: dict, note: list | None = None) -> str:
    """«Invita un socio o il tuo avvocato»: apre una questione su Atrium con il titolo del documento e i punti aperti.
    La bozza completa resta qui (si scarica quando serve): nella questione non entrano le risposte al questionario."""
    punti = [p["testo"] for p in b["punti_aperti"]] + [f"Da chiarire: {nt['testo']}" for nt in (note or [])]
    righe = "\n".join("· " + t for t in punti[:6]) + (f"\n· e altri {len(punti) - 6}" if len(punti) > 6 else "")
    n = len(b["clausole"])
    testo = (f"Bozza con {n} {'clausola' if n == 1 else 'clausole'}"
             + (f" e {len(punti)} {'punto aperto' if len(punti) == 1 else 'punti aperti'}:\n{righe}" if punti
                else ", nessun punto aperto."))
    return triade.porta_atrium_html(
        {"prodotto": "ppatos", "titolo": b["titolo"], "testo": testo},
        "Rivedila con qualcuno",
        "Invita un socio, un collega o il tuo avvocato in una questione su Atrium. Porti il titolo e i punti aperti; "
        "la bozza completa resta qui e la scarichi quando serve.",
        "Invita un socio o il tuo avvocato")


def bozza_page(codice: str, s: dict) -> bytes:
    m = questionario.carica_modello(s["modello"])
    b = assembla.assembla(m, s["risposte"], RISOLUTORE())
    testa = (f'<div style="display:flex;flex-wrap:wrap;gap:8px"><a class="btn btn-bordo btn-piccolo" href="/risposte?{_q(s=codice)}">Modifica le risposte</a>'
             f'<a class="btn btn-scuro btn-piccolo" href="/scarica?{_q(s=codice, f="documento")}">Scarica</a></div>')
    azione = {"tipo": "nota", "etichetta": "Aggiungi una domanda per l'avvocato", "url": "/nota", "campi": {"s": codice},
              "fatto": "Aggiunto ai punti aperti per l'avvocato"}
    corpo = bozza_html(b, m, codice, s.get("note")) + _porta_atrium_html(b, s.get("note"))
    ricarica = "<script>document.addEventListener('triade:azione',function(){setTimeout(function(){location.reload()},900)})</script>"
    return _page(b["titolo"], corpo + ricarica, testa=testa, largo=True, azione=azione)


def esempio_bozza() -> tuple[dict, dict]:
    m = questionario.carica_modello("privacy-nlpd")
    r = json.loads((ESEMPI / "cookie-banner.json").read_text("utf-8"))
    return assembla.assembla(m, r, RISOLUTORE()), m


def esempio_page() -> bytes:
    b, m = esempio_bozza()
    testa = (f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center"><span class="etichetta e-arrivo">Esempio</span>'
             f'<form method="post" action="/nuovo" style="display:inline"><input type="hidden" name="modello" value="privacy-nlpd">'
             f'<button class="btn btn-primario btn-piccolo">Inizia il tuo</button></form></div>')
    return _page("Esempio di bozza", bozza_html(b, m, esempio=True), testa=testa, largo=True)


def risposte_page(codice: str, s: dict) -> bytes:
    m = questionario.carica_modello(s["modello"])
    pulite, _ = questionario.valida(m, s["risposte"])
    righe = []
    for i, d in enumerate(questionario.visibili(m, pulite), 1):
        v = pulite.get(d["id"])
        if d["id"] not in pulite:
            val, cl = '<span class="etichetta e-arrivo">Non ancora risposta</span>', ""
        elif v == DA_DECIDERE:
            val, cl = '<span class="etichetta e-aperto">Da decidere</span>', ""
        else:
            val, cl = escape(condizioni.mostra(d, v)), ""
        righe.append(f'<li><div style="min-width:0;flex:1 1 380px"><span class="muted tabular" style="font-size:14px">{i}</span>'
                     f'<p style="margin:2px 0 0;font-size:17px">{escape(d["testo"])}</p><p class="sotto"{cl}>{val}</p></div>'
                     f'<a class="btn btn-bordo btn-piccolo" href="/domanda?{_q(s=codice, id=d["id"])}">Modifica</a></li>')
    body = (f'<h1>Le tue risposte</h1><p class="intro">Cambiane una e la bozza si ricompone: le domande che non servono più spariscono, '
            f'quelle nuove compaiono.</p><ul class="elenco">{"".join(righe)}</ul>'
            f'<div class="azioni" style="margin-top:32px"><a class="btn btn-primario btn-grande" href="/bozza?{_q(s=codice)}">Torna alla bozza</a></div>')
    return _page("Le tue risposte", body, testa=_testa_doc(s, codice))


def documenti_page(evidenzia: str = "") -> bytes:
    sess = elenco_sessioni()
    if not sess:
        corpo = vuoto_html("Non hai ancora documenti su questo computer. Il primo parte dalla pagina iniziale.")
    else:
        righe = []
        for x in sess:
            try:
                m = questionario.carica_modello(x["modello"])
            except FileNotFoundError:
                continue
            pulite, _ = questionario.valida(m, x.get("risposte", {}))
            completo = questionario.completo(m, pulite)
            nome = pulite.get("servizio_nome") if isinstance(pulite.get("servizio_nome"), str) and pulite.get("servizio_nome") != DA_DECIDERE else "Senza nome"
            dove = "/bozza" if completo or not questionario.prossime(m, pulite) else "/domanda"
            stato = ('<span class="etichetta">Bozza pronta</span>' if completo else
                     '<span class="etichetta e-aperto">Risposte da dare</span>' if not questionario.prossime(m, pulite) else
                     '<span class="etichetta e-arrivo">Questionario in corso</span>')
            agg = (x.get("aggiornata") or x.get("creata") or "")[:16].replace("T", " ")
            ev = ' style="border-left:3px solid var(--accent)"' if x["codice"] == evidenzia else ""
            righe.append(f'<li{ev}><div><a class="tit" href="{dove}?{_q(s=x["codice"])}">{escape(nome)}</a>'
                         f'<p class="sotto">{escape(m["titolo"])} · aggiornato {escape(agg)}</p></div>{stato}</li>')
        corpo = f'<ul class="elenco">{"".join(righe)}</ul>'
    nota = ""
    if evidenzia:
        nota = (f'<div class="pannello" style="margin-bottom:32px"><p style="color:var(--fg)">Salvato. Per riprendere da un altro '
                f'browser su questo computer usa questo indirizzo:</p><p class="mono" style="font-size:14px;word-break:break-all">'
                f'http://127.0.0.1:8767/domanda?{_q(s=evidenzia)}</p></div>')
    return _page("I tuoi documenti", f"<h1>I tuoi documenti</h1>{nota}{corpo}")


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, status: int = 200, tipo: str = "text/html; charset=utf-8", nome: str = "") -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        if nome:
            self.send_header("Content-Disposition", f'attachment; filename="{nome}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, fmt, *args):
        pass

    def _non_trovato(self, testo: str = "Pagina non trovata.") -> None:
        self._send(_page("Non trovato", non_trovato_html(testo, '<a href="/">Torna alla pagina iniziale</a>')), 404)

    def _sessione(self, codice: str):
        s = leggi_sessione(codice)
        if s is None:
            self._non_trovato("Non ritrovo questo documento. Controlla l'indirizzo, oppure guarda tra i tuoi documenti.")
        return s

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if serve_static(self, url.path):
            return
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        try:
            p = url.path
            if p == "/":
                return self._send(home_page())
            if p == "/esempio":
                return self._send(esempio_page())
            if p == "/esempio/scarica":
                return self._scarica(*esempio_bozza()[:1], q.get("f", ""), "esempio")
            if p == "/documenti":
                return self._send(documenti_page(q.get("s", "") if leggi_sessione(q.get("s", "")) else ""))
            if p in ("/inizio", "/domanda", "/bozza", "/risposte", "/scarica"):
                codice = q.get("s", "")
                s = self._sessione(codice)
                if s is None:
                    return
                if p == "/inizio":
                    return self._send(inizio_page(codice, s))
                if p == "/domanda":
                    pag = domanda_page(codice, s, q.get("id", ""))
                    return self._send(pag) if pag else self._redirect("/bozza?" + _q(s=codice))
                if p == "/risposte":
                    return self._send(risposte_page(codice, s))
                if p == "/bozza":
                    return self._send(bozza_page(codice, s))
                m = questionario.carica_modello(s["modello"])
                b = assembla.assembla(m, s["risposte"], RISOLUTORE())
                for nt in s.get("note") or []:
                    b["punti_aperti"].append({"tipo": "per_avvocato", "clausola": "",
                                              "testo": f"Da chiarire: «{nt['testo']}»" + (f" ({nt['fonte']})" if nt.get("fonte") else "")})
                return self._scarica(b, q.get("f", ""), m["id"])
            return self._non_trovato()
        except Exception as e:   # pagina leggibile invece di una connessione chiusa
            self._send(_page("Errore", errore_html(f"Non sono riuscito a preparare la pagina ({type(e).__name__}: {e}). "
                                                    "Le tue risposte sono salvate: riprova.")), 500)

    def _scarica(self, b: dict, f: str, base: str) -> None:
        if f == "documento":
            return self._send(pacchetto.documento_md(b).encode("utf-8"), tipo="text/markdown; charset=utf-8", nome=f"{base}-documento.md")
        if f == "pacchetto":
            return self._send(pacchetto.pacchetto_md(b).encode("utf-8"), tipo="text/markdown; charset=utf-8",
                              nome=f"{base}-pacchetto-avvocato.md")
        if f == "bozza":
            return self._send(json.dumps(b, ensure_ascii=False, indent=2).encode("utf-8"), tipo="application/json; charset=utf-8",
                              nome=f"{base}-bozza.json")
        return self._non_trovato()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > 200_000:
            return self._send(_page("Troppo lungo", errore_html("Il testo inviato è troppo lungo.")), 413)
        form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"), keep_blank_values=True)
        uno = lambda k: (form.get(k) or [""])[0]   # noqa: E731
        try:
            if self.path == "/nuovo":
                try:
                    codice = nuova_sessione(uno("modello") or "privacy-nlpd")
                except FileNotFoundError:
                    return self._non_trovato("Questo documento non esiste ancora.")
                return self._redirect("/inizio?" + _q(s=codice))
            codice = uno("s")
            s = self._sessione(codice)
            if s is None:
                return
            m = questionario.carica_modello(s["modello"])
            if self.path == "/domanda":
                d = questionario.per_id(m).get(uno("id"))
                if d is None:
                    return self._redirect("/domanda?" + _q(s=codice))
                if uno("azione") == "decidere":
                    valore = [] if (not d.get("obbligatoria", True) and d["tipo"] in ("tabella", "elenco", "scelte")) else DA_DECIDERE
                else:
                    valore = leggi_valore(d, form)
                    if valore in ("", []) and d["tipo"] not in ("tabella", "elenco") and not (d["tipo"] == "scelte" and not d.get("obbligatoria", True)):
                        return self._send(domanda_page(codice, s, d["id"], "scegli o scrivi una risposta, oppure «decidiamo dopo»"))
                try:
                    s["risposte"][d["id"]] = questionario.normalizza(d, valore)
                except ValueError as e:
                    return self._send(domanda_page(codice, s, d["id"], str(e)))
                salva_sessione(codice, s)
                pulite, _ = questionario.valida(m, s["risposte"])
                return self._redirect(("/domanda?" if questionario.prossime(m, pulite) else "/bozza?") + _q(s=codice))
            if self.path == "/carica":
                try:
                    dati = json.loads(uno("elenco") or "{}")
                    if not isinstance(dati, dict):
                        raise ValueError
                except ValueError:
                    return self._send(inizio_page(codice, s, "Non riesco a leggere l'elenco: serve un oggetto JSON, "
                                                             "come in esempi/cookie-banner.json."))
                pulite, errori = questionario.valida(m, dati)
                if not pulite:
                    msg = "Nell'elenco non ho trovato risposte che conosco."
                    if errori:
                        msg += " " + "; ".join(f"{k}: {v}" for k, v in list(errori.items())[:4]) + "."
                    return self._send(inizio_page(codice, s, msg))
                s["proposte"] = [[k, v] for k, v in pulite.items()]
                salva_sessione(codice, s)
                return self._redirect("/inizio?" + _q(s=codice) + "#i-trov")
            if self.path == "/conferma":
                if uno("azione") != "scarta":
                    for i, (k, v) in enumerate(s.get("proposte") or []):
                        if uno(f"r{i}") == "si":
                            s["risposte"][k] = v
                s["proposte"] = []
                salva_sessione(codice, s)
                return self._redirect("/domanda?" + _q(s=codice))
            if self.path == "/nota":
                testo = " ".join(uno("testo").split())[:1200]
                if not testo:
                    return self._send(b'{"errore":"vuoto"}', 400, "application/json")
                s.setdefault("note", []).append({"testo": testo, "fonte": uno("fonte")[:200],
                                                 "il": datetime.datetime.now().isoformat(timespec="seconds")})
                salva_sessione(codice, s)
                return self._send(json.dumps({"note": len(s["note"])}).encode(), tipo="application/json")
            return self._non_trovato()
        except Exception as e:
            self._send(_page("Errore", errore_html(f"Non sono riuscito a salvare ({type(e).__name__}: {e}). Riprova.")), 500)


class Server(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


def serve(port: int = 8767, open_browser: bool = True) -> None:
    try:
        server = Server(("127.0.0.1", port), Handler)
    except OSError:
        raise SystemExit(f"La porta {port} e gia occupata: probabilmente PPaToS e gia aperto in un'altra finestra.")
    url = f"http://127.0.0.1:{port}/"
    print(f"PPaToS {__version__} e aperto su {url}  (Ctrl+C per chiudere)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nChiuso.")
    finally:
        server.server_close()
