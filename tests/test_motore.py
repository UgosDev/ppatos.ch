"""Test del motore di PPaToS, senza rete e senza archivio (le norme le legge un risolutore finto)."""

import json
import tempfile
import unittest
from pathlib import Path

from ppatos import assembla, condizioni, controllo_modelli, monitora, norme, pacchetto, questionario
from ppatos.condizioni import DA_DECIDERE

ESEMPIO = Path(__file__).resolve().parent.parent / "esempi" / "cookie-banner.json"


class Finto:
    """Risolutore finto: ogni norma CH esiste con impronta prevedibile; il diritto UE manca."""

    def __init__(self, cambiate=()):
        self.cambiate = set(cambiate)

    def __call__(self, n):
        k = norme.chiave(n)
        if "ue" in n:
            return {"chiave": k, "trovata": False, "citazione": f"art. {n['art']} {n['ue']}", "url": "", "vigenza": "",
                    "impronta": "", "estratto": "", "rubrica": "", "versione_futura": "", "motivo": "non in archivio"}
        return {"chiave": k, "trovata": True, "citazione": f"art. {n['art']} RS {n['rs']}", "url": "https://x", "vigenza": "2025-07-07",
                "impronta": ("nuova" if k in self.cambiate else "vecchia") + k, "estratto": "testo", "rubrica": "", "versione_futura": "",
                "motivo": ""}


MINI = {
    "id": "mini", "titolo": "Mini", "versione": "0", "titolo_documento": "Documento di {nome}",
    "domande": [
        {"id": "nome", "tipo": "testo", "testo": "Nome?"},
        {"id": "ue", "tipo": "si_no", "testo": "UE?"},
        {"id": "rappr", "tipo": "testo", "testo": "Rappresentante?", "se": {"d": "ue", "vero": True}},
        {"id": "scopi", "tipo": "scelte", "testo": "Scopi?",
         "opzioni": [{"valore": "a", "etichetta": "A", "descrizione": "scopo A"}, {"valore": "b", "etichetta": "B", "descrizione": "scopo B"}]},
        {"id": "forn", "tipo": "tabella", "campi": ["nome", "paese"], "formato_riga": "{nome} ({paese})", "testo": "Fornitori?",
         "obbligatoria": False},
    ],
    "sezioni": [{"id": "s1", "titolo": "Uno"}, {"id": "s2", "titolo": "Due"}],
    "clausole": [
        {"id": "c2", "sezione": "s2", "titolo": "Scopi", "testo": "Scopi:{scopi|elenco:descrizione}", "norme": [{"rs": "235.1", "art": "6"}]},
        {"id": "c1", "sezione": "s1", "titolo": "Chi", "testo": "Titolare: {nome}.", "norme": [{"rs": "235.1", "art": "19", "cpv": "2"}],
         "punti_aperti": [{"testo": "sempre"}, {"testo": "solo UE", "se": {"d": "ue", "vero": True}}]},
        {"id": "c3", "sezione": "s1", "titolo": "UE", "se": {"d": "ue", "vero": True}, "testo": "Rappresentante: {rappr}.",
         "norme": [{"ue": "32016R0679", "art": "27"}]},
        {"id": "c4", "sezione": "s2", "titolo": "Fornitori", "se": {"d": "forn", "compilata": True}, "testo": "Fornitori:{forn|elenco}",
         "norme": [{"rs": "235.1", "art": "9"}]},
    ],
    "controlli": [{"se": {"d": "forn", "qualcuno": {"campo": "paese", "fuori": ["@CH"]}}, "messaggio": "fornitore estero"}],
}


class Condizioni(unittest.TestCase):
    def test_tre_valori(self):
        r = {"a": True, "b": DA_DECIDERE}
        self.assertTrue(condizioni.valuta({"d": "a", "vero": True}, r))
        self.assertIsNone(condizioni.valuta({"d": "b", "vero": True}, r))
        self.assertIsNone(condizioni.valuta({"d": "c", "uguale": 1}, r))
        self.assertFalse(condizioni.valuta({"tutte": [{"d": "a", "vero": False}, {"d": "b", "vero": True}]}, r))
        self.assertTrue(condizioni.valuta({"una": [{"d": "a", "vero": True}, {"d": "b", "vero": True}]}, r))
        self.assertIsNone(condizioni.valuta({"non": {"d": "b", "vero": True}}, r))

    def test_compilata_e_qualcuno(self):
        self.assertFalse(condizioni.valuta({"d": "f", "compilata": True}, {"f": []}))
        self.assertTrue(condizioni.valuta({"d": "f", "compilata": False}, {"f": []}))
        righe = [{"paese": "CH"}, {"paese": "Germania"}]
        self.assertTrue(condizioni.valuta({"d": "f", "qualcuno": {"campo": "paese", "fuori": ["@CH"]}}, {"f": righe}))
        self.assertFalse(condizioni.valuta({"d": "f", "qualcuno": {"campo": "paese", "fuori": ["@CH_UE_SEE"]}}, {"f": righe}))

    def test_forma(self):
        self.assertEqual(condizioni.controlla({"d": "a", "vero": True}), [])
        self.assertTrue(condizioni.controlla({"d": "a"}))
        self.assertTrue(condizioni.controlla({"tutte": []}))


class Questionario(unittest.TestCase):
    def test_adattivo(self):
        self.assertEqual([d["id"] for d in questionario.prossime(MINI, {})], ["nome", "ue", "scopi", "forn"])
        self.assertIn("rappr", [d["id"] for d in questionario.prossime(MINI, {"ue": True})])
        self.assertNotIn("rappr", [d["id"] for d in questionario.prossime(MINI, {"ue": False})])

    def test_normalizza(self):
        d = {d["id"]: d for d in MINI["domande"]}
        self.assertIs(questionario.normalizza(d["ue"], "sì"), True)
        self.assertEqual(questionario.normalizza(d["scopi"], "b, a"), ["a", "b"])
        with self.assertRaises(ValueError):
            questionario.normalizza(d["scopi"], ["z"])
        with self.assertRaises(ValueError):
            questionario.normalizza(d["forn"], [{"nome": "X"}])
        self.assertEqual(questionario.normalizza(d["nome"], DA_DECIDERE), DA_DECIDERE)

    def test_mancanti(self):
        r = {"nome": DA_DECIDERE, "ue": False, "scopi": ["a"], "forn": []}
        self.assertEqual([d["id"] for d in questionario.mancanti(MINI, r)], ["nome"])
        self.assertFalse(questionario.completo(MINI, r))


class Assemblaggio(unittest.TestCase):
    def test_bozza(self):
        r = {"nome": "Eric", "ue": True, "rappr": DA_DECIDERE, "scopi": ["a", "b"], "forn": [{"nome": "Y", "paese": "US"}]}
        b = assembla.assembla(MINI, r, Finto())
        self.assertEqual(b["titolo"], "Documento di Eric")
        self.assertEqual([c["id"] for c in b["clausole"]], ["c1", "c3", "c2", "c4"])   # ordine delle sezioni
        testi = {c["id"]: c["testo"] for c in b["clausole"]}
        self.assertEqual(testi["c2"], "Scopi:\n- scopo A;\n- scopo B.")
        self.assertIn("[DA DECIDERE: Rappresentante?]", testi["c3"])
        self.assertEqual(testi["c4"], "Fornitori:\n- Y (US).")
        tipi = [p["tipo"] for p in b["punti_aperti"]]
        for t in ("da_decidere", "per_avvocato", "norma", "coerenza"):
            self.assertIn(t, tipi)
        self.assertFalse(b["completa"])
        self.assertEqual(len(b["impronta"]), 64)

    def test_esclusa_con_motivo_e_sospesa(self):
        b = assembla.assembla(MINI, {"nome": "Eric", "ue": False, "scopi": ["a"]}, Finto())
        esc = {e["id"]: e for e in b["escluse"]}
        self.assertIn("c3", esc)
        self.assertIn("UE?", esc["c3"]["perche"])
        self.assertNotIn("solo UE", [p["testo"] for p in b["punti_aperti"]])
        self.assertIn("risposta_mancante", [p["tipo"] for p in b["punti_aperti"]])   # c4 aspetta i fornitori

    def test_domanda_non_posta_esclude(self):
        # rappr non si pone (ue = no): la clausola che lo usa e esclusa, non sospesa, anche con una risposta vecchia
        b = assembla.assembla(MINI, {"nome": "Eric", "ue": False, "rappr": "vecchio", "scopi": ["a"], "forn": []}, Finto())
        self.assertNotIn("rappr", [x["id"] for x in b["risposte"]])
        self.assertFalse([p for p in b["punti_aperti"] if p["tipo"] == "risposta_mancante"])
        modello = questionario.carica_modello("privacy-nlpd")
        r = json.loads(ESEMPIO.read_text("utf-8"))
        b = assembla.assembla(modello, r, Finto())
        self.assertIn("conservazione_contabile", [e["id"] for e in b["escluse"]])
        self.assertIn("domanda non posta", {e["id"]: e for e in b["escluse"]}["conservazione_contabile"]["perche"])

    def test_completa_rifiuta(self):
        with self.assertRaises(assembla.Incompleto):
            assembla.assembla(MINI, {"nome": "Eric"}, Finto(), completa=True)

    def test_risposte_sbagliate(self):
        with self.assertRaises(ValueError):
            assembla.assembla(MINI, {"nome": "Eric", "inventata": 1}, Finto())

    def test_impronta_cambia_con_la_norma(self):
        r = {"nome": "Eric", "ue": False, "scopi": ["a"], "forn": []}
        a = assembla.assembla(MINI, r, Finto())["impronta"]
        b = assembla.assembla(MINI, r, Finto(cambiate={"CH:235.1:6"}))["impronta"]
        self.assertNotEqual(a, b)


class Uscite(unittest.TestCase):
    def test_salva_e_monitora(self):
        r = {"nome": "Eric", "ue": False, "scopi": ["a"], "forn": []}
        b = assembla.assembla(MINI, r, Finto())
        with tempfile.TemporaryDirectory() as t:
            file = pacchetto.salva(b, Path(t))
            self.assertEqual({p.name for p in file}, {"documento.md", "pacchetto-avvocato.md", "bozza.json"})
            doc = (Path(t) / "documento.md").read_text("utf-8")
            self.assertIn("## 1. Uno", doc)
            self.assertNotIn("Perché", doc)
            pac = (Path(t) / "pacchetto-avvocato.md").read_text("utf-8")
            self.assertIn("Punti aperti", pac)
            self.assertIn("Clausole del modello non incluse", pac)
            ricaricata = json.loads((Path(t) / "bozza.json").read_text("utf-8"))
        esiti = monitora.confronta(ricaricata, Finto(cambiate={"CH:235.1:6"}))
        stati = {e["norma"]: e["stato"] for e in esiti}
        self.assertEqual(stati["CH:235.1:6"], "cambiata")
        self.assertEqual(stati["CH:235.1:19:2"], "invariata")
        self.assertEqual(len(monitora.da_rivedere(esiti)), 1)


class Modelli(unittest.TestCase):
    def test_tutti_i_modelli_sono_scritti_bene(self):
        self.assertTrue(questionario.elenco_modelli())
        for m in questionario.elenco_modelli():
            self.assertEqual(controllo_modelli.controlla(questionario.carica_modello(m["id"])), [], m["id"])

    def test_mini_e_scritto_bene(self):
        self.assertEqual(controllo_modelli.controlla(MINI), [])

    def test_errori_trovati(self):
        rotto = json.loads(json.dumps(MINI))
        rotto["clausole"][0]["testo"] = "{inesistente}"
        rotto["clausole"][1]["sezione"] = "s9"
        rotto["domande"][2]["se"] = {"d": "dopo", "vero": True}
        errori = controllo_modelli.controlla(rotto)
        self.assertEqual(len(errori), 3, errori)

    def test_esempio_privacy(self):
        modello = questionario.carica_modello("privacy-nlpd")
        r = json.loads(ESEMPIO.read_text("utf-8"))
        b = assembla.assembla(modello, r, Finto())
        ids = [c["id"] for c in b["clausole"]]
        for atteso in ("titolare", "scopi", "fornitori", "estero_no", "cookie_necessari", "diritti", "modifiche"):
            self.assertIn(atteso, ids)
        self.assertNotIn("basi_ue", ids)                      # utenti UE solo occasionali
        self.assertIn("[DA DECIDERE:", b["clausole"][0]["testo"])
        self.assertIn("coerenza", [p["tipo"] for p in b["punti_aperti"]])   # avviso sul GDPR
        self.assertFalse(b["completa"])


if __name__ == "__main__":
    unittest.main()
