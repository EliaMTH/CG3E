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
  dedicato (unioni e tipi base) e i loro collegamenti; la molteplicità di
  `Building.buildingPart` (`0..*` del modello, `1..*` del dizionario); i 12
  vincoli OCL con il testo su più righe; le 4 descrizioni prese dal dizionario
  dati; il tipo degli elementi delle liste annidate (`ColorType`, matrici di
  trasformazione);
- **copertura**: conteggi per dimensione, con le generalizzazioni del dizionario
  (123) e del modello UML (132); le 78 molteplicità e le 10 generalizzazioni in
  cui dizionario e modello divergono; i 3 membri senza corrispondenza, le
  corrispondenze per ereditarietà e per unione, le proprietà
  `CityModel.…Member` collegate a `cityModelMember`;
- **regole della codifica**: 43 requisiti, 4 raccomandazioni e 18 classi di
  OGC 21-006r2, identificatori brevi in comune con OGC 20-010 distinti dal
  documento, regole collegate alle proprietà, copertura dei documenti
  normativi.

Contro fonti da cui il catalogo non è costruito (`IndependentSourceTests`):

- **schemi XSD**: per i 113 ruoli UML con una proprietà XSD, il limite inferiore
  della molteplicità è il `minOccurs` dello schema e il limite superiore `*`
  corrisponde a `maxOccurs="unbounded"`;
- **figure di OGC 20-010**: `buildingPart` `0..*` (figura 64);
  `genericAttribute` `0..*` in `AbstractCityObject` e `1..*` in
  `GenericAttributeSet`, superclasse `AbstractGenericAttribute` degli otto
  attributi generici (figura 37); superclasse
  `AbstractTextureParameterization` di `TexCoordGen` e `TexCoordList` e
  composizione di `textureParameterization` (figura 27);
- **regole del modello**: nessuno spazio senza superfici ammesse (come
  `PlantCover`) eredita un `boundary` obbligatorio; aggregazioni delle
  association class;
- **istanze validate con gli schemi ufficiali, offline**: gli attributi scritti
  con il nome del catalogo (`srsName` di `TexCoordGen`, `codeSpace` di
  `gml:CodeType`, `xlink:href` di `xal:Address`); un `Building` con
  `gml:boundedBy` nil; un `gml:Dictionary` senza `gml:id`, rifiutato, mentre il
  catalogo lo classifica come oggetto; un `CityModel` con membri alternati, come
  ammette la scelta ripetuta `0..*`.

Su dati sintetici verifica:

- che un membro, una generalizzazione, un vincolo o una lista persi dal
  catalogo diventino rilievi della copertura, mentre un'unione codificata come
  alternative e una classe ISO no; che una generalizzazione presente solo nel
  modello UML conti nella copertura e che le divergenze fra dizionario e
  modello siano elencate;
- la risoluzione degli import tramite manifest;
- le forme di collegamento (incluso, riferimento, entrambe, ereditate per
  estensione, tolte da una restrizione, base non disponibile) e le liste
  dirette, annidate e in tipi anonimi di proprietà.

### `tests/test_exporters.py`

Sui dati del progetto verifica:

- **code list**: 44 liste e 2295 valori esportati, senza segnaposto; la forma
  GML degli esempi OGC (radice, metadati, `gml:id`, ordine degli elementi) con
  gli stessi codici, nomi e `codeSpace` del file d'esempio di `RoofTypeValue`;
  la validazione di tutti i dizionari GML contro gli schemi locali; le forme
  JSON e CSV confrontate con gli esempi di Annex E letti dalla copia locale di
  OGC 21-006r2; i `codeSpace` propri dei valori di `TrafficAreaFunctionValue`;
- **controlli iniziali**, su dati sintetici: catalogo non allineato al manifest
  (il comando esce con errore e non scrive il file), dizionario in un altro
  formato o con code list diverse da quelle del catalogo, file di `sources/`
  alterato, data dell'export senza fuso orario; uno schema che il catalogo XML
  non risolve è un errore e non viene scaricato;
- **dati sintetici**: `codeSpace` del valore o della lista, esclusione di
  segnaposto e valori senza codice, lista senza metadati di Annex E, testo non
  rappresentabile in XML, avvisi;
- **`city3d`**: intestazione, 140 code list (44 con `Dictionary`), stati,
  struttura di Annex E;
- **`codeListUse`**: 158 voci su 63 elementi e 136 code list, coppie
  (elemento, proprietà) uniche, le voci di `TrafficArea`/`function` e
  `Building`/`roofType`, uguaglianza fra `city3d` e `generator`;
- **`generator`**: 78 XSD con lo SHA-256 del manifest, avvertenze, 88 file di
  code list, `manifest.json`; 107 elementi e 3483 proprietà, ordine delle
  proprietà di `Building`, campo `uml` di `boundary` con la molteplicità del
  modello e quella del dizionario, `gml:boundedBy` nillable, attributi non
  qualificati di `TexCoordGen`, `choices` e `choiceGroups` di `CityModel`
  (unico elemento con gruppi `xs:choice`); regole (10 superfici di
  `Building`, nessuna per `PlantCover`, 20 oggetti di primo livello, 12
  proprietà solo per riferimento, 12 vincoli, 65 regole di codifica);
  `xml-catalog.xml` che riconduce ogni `codeSpace` al suo file;
- **estremo a estremo**: un `CityModel` con un `Building` (`gml:id`, `function`
  con codice e `codeSpace` di `BuildingFunctionValue`, `lod0MultiSurface`,
  `lod1Solid`) costruito con le sole informazioni del pacchetto valida offline
  contro `CityGML.xsd` del pacchetto con il suo `xml-catalog.xml`, e non valida
  con le proprietà in ordine inverso; un `Building` con un `TrafficArea` come
  `boundary` valida ma non è fra le superfici ammesse di `rules`; un `CityModel`
  con membri alternati (`cityObjectMember`, `appearanceMember`,
  `cityObjectMember`) valida, come dice `choiceGroups`;
- **`standard`**: file presenti ed esclusi, SHA-256 delle fonti, dizionario
  esportato invariato, dizionari GML validi con il catalogo XML del pacchetto,
  contenuto di `EXPORT.md`;
- **determinismo**: due esecuzioni con la stessa data producono gli stessi byte
  per i tre exporter.

### `tests/test_codespaces.py`

Su un dizionario sintetico (una lista modificata, una SIG3D invariata, una di
soli segnaposto, una senza metadati) verifica: liste trattate senza `--lists`,
`codeSpace` di lista e valori, metadati, liste non trattate invariate,
`codeSpacePolicy`, completamento di una lista senza metadati e sua
esportabilità, lingua obbligatoria quando manca, liste indicate, idempotenza,
estensione e sostituzione della politica, controllo di `--base` e `--version`,
serializzazione con l'intestazione di `assets/app.js` e righe LF. Da riga di
comando, su una copia del dizionario: `--dry-run` non scrive, la scrittura
cambia solo la lista trattata, la seconda esecuzione non cambia nulla, un errore
non scrive nulla.

### Altri test

- `tests/test_conceptual_model.py` verifica la lettura del documento OGC 20-010
  e dell'XMI su file sintetici con la stessa struttura: metadati, classi
  distinte dai package omonimi, attributi, vincoli (più righe *Constraint*
  nella stessa tabella, testo su più righe), valori delle enumerazioni,
  tabelle dei confini con liste annidate, requisiti, capitoli, sezioni
  concettuali. Dell'XMI, con la struttura dell'export di Enterprise Architect:
  molteplicità di attributi e ruoli (il `*` scritto nel connettore, con limite
  inferiore -1 nel modello), tipi di aggregazione, estremità di un'association
  class distinte dai suoi attributi, generalizzazioni anche verso classi fuori
  dal file, identificatori ripetuti nell'estensione.
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
  il livello nell'URL e nei cambi di scheda; al livello UML la molteplicità del
  modello con il badge del dizionario (`buildingPart` `0..*`, "dizionario:
  1..*"), anche nell'export; export con il livello dichiarato, selettore
  visibile su mobile;
- **relazioni e generalizzazioni**: `buildingPart` letta come composizione anche
  nelle connessioni in ingresso di `BuildingPart`; la generalizzazione di
  `StringAttribute` presente solo nel modello UML, con la nota sul dizionario;
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
  documenti normativi, generalizzazioni per fonte, divergenze fra dizionario e
  modello UML;
- **code list**: valori nelle classi e nella pagina della code list, esempio
  d'uso con i caratteri speciali di XML (`A&B` scritto `A&amp;B`), aggiunta e
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

`python tests/browser_export.py` applica `scripts/codespaces.py` a
`RoofTypeValue` in una copia del dizionario, esporta il pacchetto `standard` con
quel dizionario, lo estrae in una cartella temporanea e apre `index.html` da
`file://`, con le richieste di rete bloccate. Verifica la scheda di `Building`,
il riquadro Sorgenti con i collegamenti ai file locali (compresi i documenti OGC
20-010 e 21-006r2), la pagina di `RoofTypeValue` con il nuovo `codeSpace`
nell'editor, nell'esempio d'uso e l'autorità nei metadati, e che Salva scriva
gli stessi byte di `scripts/codespaces.py`; l'assenza di errori JavaScript.
