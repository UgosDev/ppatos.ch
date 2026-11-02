# PPaToS: cose da grandi, senza il pathos

Documenti legali su misura per sviluppatori e piccole realtà, con ogni clausola legata alla norma in vigore e un
pacchetto pronto per la revisione dell'avvocato. Terzo prodotto della triade: Nuova-Norma *sa*, Anorma *risponde*,
PPaToS *scrive*.

```
excited-bohr/
  nuova-norma/   archivio delle norme (PPaToS lo legge in sola lettura)
  anorma/        verifica «sei a norma?»
  ppatos/        questo motore
```

## Come lavora

1. **Questionario adattivo**: le domande compaiono solo quando servono (es. il rappresentante UE solo se il servizio
   si rivolge all'UE). Ogni risposta può essere `"?"`, cioè *da decidere*.
2. **Assemblaggio**: il testo viene solo dalle clausole del modello, mai generato. Una clausola entra se la sua
   condizione è vera; quelle escluse restano elencate con il motivo.
3. **Norme**: ogni clausola cita articoli che il motore legge nell'archivio di Nuova-Norma (versione in vigore,
   impronta SHA-256 del testo, estratto, link a Fedlex). Una norma non trovata diventa un punto aperto.
4. **Uscite**: `documento.md` (il testo da pubblicare), `pacchetto-avvocato.md` (fatti dichiarati, motivo di ogni
   clausola, norme, alternative scartate, clausole escluse, punti aperti), `bozza.json` (per il monitoraggio).
5. **Monitoraggio**: `controlla` rilegge le norme e segnala le clausole da rivedere quando un'impronta cambia.

## Comandi

```
py -m ppatos modelli
py -m ppatos questionario privacy-nlpd --risposte data\risposte\mio-servizio.json
py -m ppatos domande privacy-nlpd --risposte esempi\cookie-banner.json
py -m ppatos compila privacy-nlpd --risposte esempi\cookie-banner.json
py -m ppatos controlla data\bozze\<cartella>\bozza.json
py -m ppatos controlla-modelli --archivio
```

## Scrivere un modello

I modelli sono file JSON in `ppatos/modelli/`: domande, sezioni, clausole, controlli di coerenza.
Le condizioni (`se`) sono JSON valutato dal codice (vedi `condizioni.py`); i segnaposto nel testo sono `{id}`,
`{id|elenco}` e `{id|elenco:campo}`. Ogni clausola ha `norme`, `motivo`, eventuali `alternative` scartate e
`punti_aperti` per l'avvocato. `py -m ppatos controlla-modelli --archivio` trova gli errori di scrittura e le norme
che non esistono nell'archivio.

Modelli disponibili: `privacy-nlpd` (informativa sulla protezione dei dati, con parti GDPR condizionali).
Stato di revisione: bozze non ancora riviste da un avvocato.

## Test

```
py -m unittest discover -s tests
```
