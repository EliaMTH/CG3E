# Test

## Fonti

`python scripts/verify_sources.py` controlla gli SHA-256 di
`sources/manifest.json`, l'assenza di XSD non registrati e la presenza locale di
ogni import. Non usa la rete.

I test non verificano la disponibilità delle fonti ufficiali: per questo serve
eseguire `python scripts/fetch_sources.py`.

## Test unitari

`python -m unittest discover -s tests -v`

### `tests/test_catalog.py`

Sul catalogo generato verifica:

- **schemi e file**: i 22 schemi CityGML alla versione 3.0.0, nessun import
  mancante né riferimento esterno, hash coerenti con il manifest,
  l'uguaglianza fra `catalog.js` e `catalog.json`, la risoluzione di tutti i
  riferimenti fra nodi (gerarchie XSD e UML, proprietà, membri, collegamenti
  entranti);
- **categorie**: 114 feature, 4 oggetti e 13 enumerazioni CityGML; 66 oggetti
  di città concreti, di cui 42 spazi e 24 superfici; la scheda di `Building` e
  la classificazione delle sue proprietà;
- **collegamenti**: tipi di collegamento, composizioni e aggregazioni
  dall'XMI; forme di codifica, con le 12 proprietà solo per riferimento uguali a
  quelle nominate dai requisiti `/reference` di OGC 21-006r2 e le 3 solo
  incluse;
- **modello concettuale**: i 20 oggetti di primo livello, le 140 code list, la
  code list di `roofType`, i valori di `RelativeToTerrain`, le superfici ammesse
  di `Building`, `BuildingUnit` e `PlantCover`, gli spazi delimitati da
  `TrafficArea`, i 50 requisiti e le 18 classi di requisiti, il rapporto di
  confronto;
- **classi UML**: le 9 generalizzazioni che gli schemi non esprimono e la
  coerenza fra superclassi e sottoclassi; i membri delle 8 classi senza tipo XSD
  dedicato (unioni e tipi base) e i loro collegamenti; i 12 vincoli OCL con il
  testo su più righe; le 4 descrizioni prese dal dizionario dati; il tipo degli
  elementi delle liste annidate (`ColorType`, matrici di trasformazione);
- **copertura**: conteggi per dimensione, i 3 membri senza corrispondenza, le
  corrispondenze per ereditarietà e per unione, le proprietà `CityModel.…Member`
  collegate a `cityModelMember`;
- **regole della codifica**: 43 requisiti, 4 raccomandazioni e 18 classi di
  OGC 21-006r2, identificatori brevi in comune con OGC 20-010 distinti dal
  documento, regole collegate alle proprietà, copertura dei documenti
  normativi.

Su dati sintetici verifica:

- che un membro, una generalizzazione, un vincolo o una lista persi dal
  catalogo diventino rilievi della copertura, mentre un'unione codificata come
  alternative e una classe ISO no;
- la risoluzione degli import tramite manifest;
- le forme di collegamento (incluso, riferimento, entrambe, ereditate per
  estensione, tolte da una restrizione, base non disponibile) e le liste
  dirette, annidate e in tipi anonimi di proprietà.

### Altri test

- `tests/test_conceptual_model.py` verifica la lettura del documento OGC 20-010
  e dell'XMI su file sintetici con la stessa struttura: metadati, classi
  distinte dai package omonimi, attributi, vincoli (più righe *Constraint*
  nella stessa tabella, testo su più righe), valori delle enumerazioni,
  tabelle dei confini con liste annidate, requisiti, capitoli, sezioni
  concettuali e tipi di aggregazione.
- `tests/test_encoding_document.py` verifica la lettura del documento OGC
  21-006r2 su un file sintetico con la stessa struttura: metadati, classe di
  requisiti con dipendenze, requisito con punti, note e proprietà nominate,
  raccomandazione, esclusione di classi e test di conformità, tabella con
  struttura inattesa segnalata come non riconosciuta.
- `tests/test_codelists.py` verifica `scripts/build_codelists.py` su esempi
  sintetici con i due namespace dei metadati
  (`http://www.opengis.net/citygml/codelistmetadata/3.0` e
  `http://www.opengis.net/citygml/codelist-metadata`), il riconoscimento dei
  segnaposto e delle liste non disponibili, e che `codelists/codelists.js` non
  venga sovrascritto senza `--reset`; sul dizionario fornito verifica le 140
  code list (44 con valori, 95 segnaposto, 1 non disponibile), la
  corrispondenza con le code list del catalogo e la struttura di ogni valore.
- `tests/test_assets.py` verifica che `assets/styles-dark.css` coincida con
  quanto genera `scripts/build_dark_theme.py`, che le variabili CSS non vengano
  trasformate, la conversione dei colori, che ombre e sfondo delle finestre
  modali restino invariati e che ogni dimensione del testo segua
  `--font-scale`.
- `tests/test_fetch_sources.py` verifica lo script di download con risposte
  simulate: URL canonici, percorsi locali, host non ammessi, namespace
  inattesi, risposte HTML, formati dei documenti (compresi i `gml:Dictionary`),
  import relativi, scrittura del manifest, segnalazione dei file non acquisiti,
  esempi di code list non pubblicati registrati come `unavailable` e
  `--reuse-local`, che riscarica solo i file mancanti o modificati localmente.
  Non usa la rete.

## Test nel browser

`python tests/browser_smoke.py` carica pagina, catalogo, dizionario delle code
list e script in Chromium (Playwright). Verifica:

- **navigazione**: ricerca, filtri per categoria (anche code list e primo
  livello), schede compresa Standard e riquadri, catena di ereditarietà con i
  prefissi, superfici ammesse;
- **ricerca delle proprietà**: classe dichiarante, apertura della proprietà con
  le classi concrete che la hanno, proprietà di classi astratte visibili con il
  filtro "solo concreti", dichiarazione XSD prima dei membri UML omonimi;
- **livelli di lettura**: passaggio da Codifica GML a Modello UML e ritorno, con
  il livello nell'URL e nei cambi di scheda, molteplicità diverse fra i due
  livelli (`buildingPart` 1..* e 0..*), export con il livello dichiarato,
  selettore visibile su mobile;
- **destinazioni**: `boundary` nel contesto della classe visitata
  (`BuildingUnit` senza le superfici di `Building`, divieto per `PlantCover`),
  separate dagli elementi sostituibili negli schemi;
- **modello concettuale**: generalizzazione UML, membri di un tipo base
  (diretti ed ereditati) e di un'unione, vincoli OCL, badge "solo riferimento",
  descrizione presa dal dizionario dati, membri nella scheda Standard con la
  loro corrispondenza negli schemi, requisiti della codifica GML nella scheda
  Standard e nei dettagli di una proprietà;
- **classi senza tipo XSD dedicato**: badge, proprietà che le usano come tipo
  nella scheda Sorgente, messaggio dell'esempio d'uso per una code list senza
  proprietà che la usano e per una code list vuota;
- **riquadro Sorgenti**: documenti, copertura del modello concettuale e dei
  documenti normativi;
- **code list**: valori nelle classi e nella pagina della code list, aggiunta e
  annullamento di un valore, ricerca per valore, pulsante Code list, Salva (con
  la File System Access API sostituita da uno stub: il testo scritto coincide
  byte per byte con `codelists/codelists.js`), modifica durante la scrittura
  (resta da salvare; Salva e Reset sono disabilitati finché la scrittura non
  termina), scrittura fallita, Reset, download quando l'API manca, pagina Code
  list con i suoi filtri;
- **opzioni di visualizzazione**: tema scuro, dimensione del testo, chiusura
  del pannello; la persistenza delle scelte è verificata sulla pagina reale
  aperta da `file://` e ricaricata;
- l'assenza di errori JavaScript.

Salva `docs/screenshot-desktop.png` e `docs/screenshot-mobile.png`. Salvo il
controllo della persistenza, carica i file in memoria; il salvataggio reale con
la File System Access API, che apre una finestra di scelta del file, non è
automatizzato.
