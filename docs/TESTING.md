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
  - `tests/test_fetch_sources.py` verifica lo script di download con risposte
    simulate: URL canonici, percorsi locali, host non ammessi, namespace
    inattesi, risposte HTML, formati dei documenti, import relativi, scrittura
    del manifest e segnalazione dei file non acquisiti. Non usa la rete.
- `python tests/browser_smoke.py`: carica pagina, catalogo e script in Chromium
  (Playwright), naviga ricerca, filtri per categoria (anche code list e primo
  livello), schede compresa Standard, la pagina di una code list e i riquadri;
  verifica la catena di ereditarietà con i prefissi, le superfici ammesse e
  l'assenza di errori
  JavaScript e salva `docs/screenshot-desktop.png` e `docs/screenshot-mobile.png`.
  Carica i file in memoria, quindi non verifica la policy `file://` del browser.

I test non verificano la disponibilità delle fonti ufficiali: per questo serve
eseguire `python scripts/fetch_sources.py`.
