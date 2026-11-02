"""Il sito di PPaToS (tavole del canvas «PPaToS — design»), senza rete e senza archivio."""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

from ppatos import norme, web


class TestSito(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["PPATOS_SESSIONI"] = cls.tmp.name
        web.RISOLUTORE = lambda: norme.Risolutore(None)   # nessun archivio: le norme risultano da verificare
        cls.server = web.Server(("127.0.0.1", 0), web.Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        os.environ.pop("PPATOS_SESSIONI", None)
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.read().decode("utf-8"), r.geturl()

    def post(self, path, dati):
        corpo = urllib.parse.urlencode(dati, doseq=True).encode()
        with urllib.request.urlopen(urllib.request.Request(self.base + path, corpo)) as r:
            return r.status, r.read().decode("utf-8"), r.geturl()

    def nuovo(self):
        _, html, url = self.post("/nuovo", {"modello": "privacy-nlpd"})
        return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["s"][0], html

    def test_home_con_accento_e_famiglia(self):
        _, html, _ = self.get("/")
        self.assertIn("Cose da grandi,<br>senza il pathos.", html)
        self.assertIn("--accent:#2b5c9e", html)
        self.assertIn('aria-label="PPaToS"', html)
        self.assertIn("In arrivo", html)                 # i documenti senza modello non sono «disponibili»
        self.assertIn("/nn/copia.js", html)
        self.assertNotIn("N/D", html)

    def test_questionario_fino_alla_bozza(self):
        s, html = self.nuovo()
        self.assertIn("Da dove partiamo?", html)
        _, html, _ = self.get(f"/domanda?s={s}")
        self.assertIn("Come si chiama il servizio?", html)
        self.assertIn("Il documento prende forma", html)
        _, html, _ = self.post("/domanda", {"s": s, "id": "servizio_nome", "v": "prova.ch", "azione": "avanti"})
        self.assertIn("Qual è l&#x27;indirizzo del servizio?", html)
        # risposta non valida: resta sulla domanda con il motivo
        _, html, _ = self.post("/domanda", {"s": s, "id": "servizio_url", "v": "prova", "azione": "avanti"})
        self.assertIn("Non va ancora", html)
        # «decidiamo dopo»
        _, html, _ = self.post("/domanda", {"s": s, "id": "servizio_url", "azione": "decidere"})
        _, html, _ = self.get(f"/bozza?s={s}")
        self.assertIn("Pacchetto per l'avvocato", html)
        self.assertIn('class="decidere"', html)          # segnaposto evidenziato come punto aperto
        self.assertIn("Norma da verificare", html)       # senza archivio nessuna norma e «verificata»
        self.assertIn("data-fonte=", html)               # la copia con la fonte sa da dove viene il testo

    def test_elenco_dal_codice_si_conferma_riga_per_riga(self):
        s, _ = self.nuovo()
        elenco = json.dumps({"servizio_nome": "x.ch", "cookie": ["necessari"], "sconosciuta": 1})
        _, html, _ = self.post("/carica", {"s": s, "elenco": elenco})
        self.assertIn("Cosa abbiamo trovato", html)
        self.post("/conferma", {"s": s, "r0": "si", "r1": "no"})
        sess = web.leggi_sessione(s)
        self.assertEqual(sess["risposte"], {"servizio_nome": "x.ch"})
        _, html, _ = self.post("/carica", {"s": s, "elenco": "non json"})
        self.assertIn("Non riesco a leggere l&#x27;elenco", html)

    def test_nota_per_l_avvocato_dal_menu(self):
        s, _ = self.nuovo()
        _, corpo, _ = self.post("/nota", {"s": s, "testo": "entro 30 giorni", "fonte": "art. 6 LPD"})
        self.assertEqual(json.loads(corpo)["note"], 1)
        with urllib.request.urlopen(f"{self.base}/scarica?s={s}&f=pacchetto") as r:
            testo = r.read().decode("utf-8")
            self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertIn("Da chiarire: «entro 30 giorni» (art. 6 LPD)", testo)

    def test_esempio_e_documenti(self):
        _, html, _ = self.get("/esempio")
        self.assertIn("cookie-banner.ch", html)
        _, html, _ = self.get("/documenti")
        self.assertIn("I tuoi documenti", html)

    def test_codice_sconosciuto(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get("/bozza?s=nonesiste1234567")
        self.assertEqual(e.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/bozza?s=../../etc")

    def test_script_condivisi(self):
        with urllib.request.urlopen(self.base + "/nn/copia.js") as r:
            js = r.read().decode("utf-8")
        self.assertIn("contextmenu", js)
        self.assertIn("text/html", js)


class TestSezioni(unittest.TestCase):
    def test_stato_sezioni(self):
        from ppatos import questionario
        m = questionario.carica_modello("privacy-nlpd")
        st = {x["id"]: x["stato"] for x in web.stato_sezioni(m, {}, "titolare_nome")}
        self.assertEqual(st["titolare"], "ora")
        self.assertEqual(st["dati"], "da_fare")


if __name__ == "__main__":
    unittest.main()
