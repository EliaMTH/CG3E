# Test

- `python scripts/verify_sources.py`: controlla gli SHA-256 di
  `sources/manifest.json`, l'assenza di XSD non registrati e la presenza locale
  di ogni import. Non usa la rete.
- `python -m unittest discover -s tests -v`:
  - `tests/test_catalog.py` verifica il catalogo generato: i 22 schemi CityGML
    alla versione 3.0.0, nessun import mancante né riferimento esterno, hash
    coerenti con il manifest, la scheda di `Building`, la risoluzione di tutti i
    riferimenti fra nodi e l'uguaglianza fra `catalog.js` e `catalog.json`;
    controlla le categorie (114 feature, 4 oggetti, 13 enumerazioni CityGML;
    66 oggetti di città concreti, di cui 42 spazi e 24 superfici), la
    classificazione delle proprietà di `Building` e i tipi di collegamento;
    verifica le informazioni del modello concettuale: i 20 oggetti di primo
    livello, le 140 code list, la code list di `roofType`, i valori di
    `RelativeToTerrain`, le superfici ammesse di `Building`, `BuildingUnit` e
    `PlantCover`, gli spazi delimitati da `TrafficArea`, composizioni e
    aggregazioni, i 50 requisiti e le 18 classi di requisiti, il rapporto di
    confronto;
    costruisce inoltre un catalogo sintetico per verificare la risoluzione degli
    import tramite manifest;
  - `tests/test_conceptual_model.py` verifica la lettura del documento e
    dell'XMI su file sintetici con la stessa struttura: metadati, classi
    distinte dai package omonimi, attributi, valori delle enumerazioni,
    tabelle dei confini con liste annidate, requisiti, capitoli, sezioni
    concettuali e tipi di aggregazione;
  - `tests/test_codelists.py` verifica `scripts/build_codelists.py` su esempi
    sintetici nei due formati (namespace dei metadati 3.0 e forma precedente),
    il riconoscimento dei segnaposto e delle liste non disponibili, e che
    `codelists/codelists.js` non venga sovrascritto senza `--reset`; sul
    dizionario fornito verifica le 140 code list (44 con valori, 95 segnaposto,
    1 non disponibile), la corrispondenza con le code list del catalogo e la
    struttura di ogni valore;
  - `tests/test_fetch_sources.py` verifica lo script di download con risposte
    simulate: URL canonici, percorsi locali, host non ammessi, namespace
    inattesi, risposte HTML, formati dei documenti (compresi i
    `gml:Dictionary`), import relativi, scrittura del manifest, segnalazione
    dei file non acquisiti ed esempi di code list non pubblicati registrati come
    `unavailable`. Non usa la rete.
- `python tests/browser_smoke.py`: carica pagina, catalogo, dizionario delle
  code list e script in Chromium (Playwright).
  - Naviga ricerca, filtri per categoria (anche code list e primo livello),
    schede compresa Standard e riquadri; verifica la catena di ereditarietà con
    i prefissi e le superfici ammesse.
  - Code list: valori nelle classi e nella pagina della code list, aggiunta e
    annullamento di un valore, ricerca per valore, pulsante Code list, Salva
    (con la File System Access API sostituita da uno stub: il testo scritto
    coincide byte per byte con `codelists/codelists.js`), Reset e download
    quando l'API manca.
  - Verifica l'assenza di errori JavaScript e salva `docs/screenshot-desktop.png`
    e `docs/screenshot-mobile.png`. Carica i file in memoria, quindi non
    verifica la policy `file://` del browser.

I test non verificano la disponibilità delle fonti ufficiali: per questo serve
eseguire `python scripts/fetch_sources.py`.
