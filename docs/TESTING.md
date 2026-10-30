# Test

## Fonti

`python scripts/verify_sources.py` controlla gli SHA-256 di
`sources/manifest.json`, l'assenza di XSD non registrati e la presenza locale di
ogni import. Non usa la rete.

I test non verificano la disponibilità delle fonti ufficiali: per questo serve
eseguire `python scripts/fetch_sources.py`.

## Test unitari

`python -m unittest discover -s tests -v`

I conteggi sui dati del progetto (140 code list, 107 elementi, 158 voci di
`codeListUse`…) riguardano la parte CityGML: restano validi anche con ADE
dichiarate in `config/sources.json`, che aggiungono elementi, code list e voci.
I test nel browser `browser_smoke.py` e `browser_export.py` presuppongono invece
il progetto senza ADE (per esempio il contatore `44/140` e le tre opzioni del
filtro degli schemi).

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
  association class e loro collegamento, nei due versi, con i ruoli che
  qualificano (`Role`, `CityObjectRelation`, `TextureAssociation`);
- **membri di un CityModel**: per `Building`, `Appearance`, `Version`,
  `VersionTransition`, `WallSurface` e `CityModel` gli schemi ufficiali
  accettano l'elemento esattamente nei membri di `CityModel` che il catalogo
  elenca, e i membri UML sono gli attributi di `CityModelMember` il cui tipo è
  una superclasse nel dizionario dati (`Building`: `cityObjectMember`, poi
  `featureMember`); la frase di OGC 20-010 sui membri diretti è nella sezione
  6.2.3 che il catalogo collega;
- **derivazione negli schemi**: nessun tipo complesso che deriva da
  `gml:AbstractGML` resta un tipo di dato (`gml:SurfaceType`,
  `gml:DictionaryType`, `gml:DiscreteCoverageType`…); `TINRelief.tin`, con tipo
  anonimo verso `gml:TriangulatedSurface`, è una geometria;
- **istanze validate con gli schemi ufficiali, offline**: gli attributi scritti
  con il nome del catalogo (`srsName` di `TexCoordGen`, `codeSpace` di
  `gml:CodeType`, `xlink:href` di `xal:Address`); un `Building` con
  `gml:boundedBy` nil; un `gml:Dictionary` senza `gml:id`, rifiutato, mentre il
  catalogo lo classifica come oggetto; un `CityModel` con membri alternati, come
  ammette la scelta ripetuta `0..*`; un `gml:QuantityExtent` senza `uom`,
  rifiutato, mentre il catalogo riporta `uom` fra gli attributi che la
  restrizione eredita dal tipo base (9 tipi GML con attributi ereditati per
  restrizione).

Su dati sintetici verifica:

- che un membro, una generalizzazione, un vincolo o una lista persi dal
  catalogo diventino rilievi della copertura, mentre un'unione codificata come
  alternative e una classe ISO no; che una generalizzazione presente solo nel
  modello UML conti nella copertura e che le divergenze fra dizionario e
  modello siano elencate; che un ruolo qualificato da una classe di
  associazione e non collegato diventi un rilievo;
- la risoluzione degli import tramite manifest;
- i nomi XML delle proprietà (attributi locali non qualificati, `form`
  qualificato, riferimenti con il namespace della dichiarazione) e gli
  attributi che una restrizione eredita dalla base, esclusi quelli dichiarati di
  nuovo o proibiti;
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
  non risolve è un errore e non viene scaricato; la chiave qualificata di una
  code list di un'ADE e il messaggio che indica `build_codelists.py --align`;
- **dati sintetici**: `codeSpace` del valore o della lista, esclusione di
  segnaposto e valori senza codice, lista senza metadati di Annex E, testo non
  rappresentabile in XML, avvisi; i valori senza codice segnalati sempre, anche
  quando nessun valore ha un codice e la lista resta fuori dall'export
  (`exportedValues` 0), mentre i segnaposto degli esempi OGC non producono
  avvisi;
- **`city3d`**: intestazione, 140 code list (44 con `Dictionary`), stati,
  valori esportati, struttura di Annex E; `elements` ed `enumerations` uguali a
  quelli di `generator`;
- **`codeListUse`**: 158 voci su 63 elementi e 136 code list, coppie
  (elemento, proprietà) uniche, le voci di `TrafficArea`/`function` e
  `Building`/`roofType`, uguaglianza fra `city3d` e `generator`;
- **candidati**: ogni candidato CityGML (o di un'ADE) ha la sua voce in
  `elements`; quelli senza voce sono soltanto elementi GML e xAL;
- **`generator`**: 78 XSD con lo SHA-256 del manifest, avvertenze, 88 file di
  code list, `manifest.json`; 107 elementi e 3483 proprietà, ordine delle
  proprietà di `Building`, campo `uml` di `boundary` con la molteplicità del
  modello e quella del dizionario, `gml:boundedBy` nillable, attributi non
  qualificati di `TexCoordGen`, `choices` e `choiceGroups` di `CityModel`
  (unico elemento con gruppi `xs:choice`); 13 tipi enumeration, uno per ogni
  tipo enumeration delle proprietà di `elements`, i valori di
  `RelativeToTerrainType` con le descrizioni, valori uguali a quelli del modello
  concettuale; regole (10 superfici di
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
non scrive nulla. Per le ADE: il `codeSpace` di una code list dell'ADE nella
cartella dei suoi dizionari, con identificatore e nome del file senza prefisso,
e le voci di un'ADE in una lista di CityGML che conservano il loro `codeSpace`.

### `tests/test_ade.py`

Un'ADE dalla configurazione agli export, sulle fonti reali e sull'ADE di prova
di `tests/fixtures/ade`: un'ADE sintetica scritta sui casi della Test ADE di
OGC 21-006r2, Annex B (hook su `bldg:ADEOfAbstractBuilding`, una feature
derivata da `core:AbstractOccupiedSpace` di primo livello, un tipo usato da due
elementi, un `xs:include`, un'enumerazione, due code list con dizionario e una
senza, voci per `BuildingClassValue`) e un documento d'esempio. Gli input del
progetto sono copiati in una cartella temporanea; `fetch_sources.py` gira con la
rete disattivata, riusa `sources/` e legge l'ADE dalla sua cartella locale.
Verifica:

- **fonti**: copie locali con `origin: "local"`, nessun download,
  `verify_sources.py` senza errori, le altre fonti invariate;
- **catalogo**: famiglia `ADE`, modulo e prefisso dalla configurazione; nodi
  delle code list con la descrizione del dizionario; collegamenti applicati
  anche agli elementi del tipo condiviso; avviso per la proprietà
  `gml:CodeType` senza code list; primo livello e appartenenza al `CityModel`;
  sezione `ades` e statistiche; parte CityGML invariata, spazio dell'ADE fuori da
  `spacesWithoutBoundaryTable`;
- **dizionario**: `build_codelists.py --align` aggiunge le code list dell'ADE e
  le sue voci per `BuildingClassValue` dopo quelle SIG3D; record di Annex E con
  `gml:id` e file senza prefisso, validi contro gli schemi; avviso sul CSV;
- **export**: elementi dell'ADE in `elements`, candidati di `adeOfAbstractBuilding`
  e `cityObjectMember`, nessun candidato CityGML o ADE senza voce in `elements`;
  il tipo enumeration dell'ADE in `enumerations`, con i valori del suo XSD;
  `codeListUse` con le liste dell'ADE; intestazione `ades`; primo livello da
  configurazione in `rules`; XSD dell'ADE e riscrittura della sola loro cartella
  in `xml-catalog.xml`; `CityGML-ADE.xsd` con cui il documento d'esempio valida
  offline nel pacchetto estratto, mentre con il solo `CityGML.xsd` non valida;
  README dei pacchetti; determinismo.

### Altri test

- `tests/test_conceptual_model.py` verifica la lettura del documento OGC 20-010
  e dell'XMI su file sintetici con la stessa struttura: metadati, classi
  distinte dai package omonimi, attributi, vincoli (più righe *Constraint*
  nella stessa tabella, testo su più righe), valori delle enumerazioni,
  tabelle dei confini con liste annidate, requisiti, capitoli, sezioni
  concettuali e la frase sui membri diretti di un city model. Dell'XMI, con la struttura dell'export di Enterprise Architect:
  molteplicità di attributi e ruoli (il `*` scritto nel connettore, con limite
  inferiore -1 nel modello), tipi di aggregazione, estremità di un'association
  class distinte dai suoi attributi e collegate al ruolo che qualifica,
  generalizzazioni anche verso classi fuori dal file, identificatori ripetuti
  nell'estensione; l'ancora di una classe con il segno × nel nome.
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
  venga sovrascritto senza `--reset`; per le ADE, le code list con chiave
  qualificata (con dizionario e vuote), le voci per una code list di CityGML con
  il loro `codeSpace`, l'errore per una lista che non è del modulo indicato,
  `--align` che aggiunge solo ciò che manca (e ripristina una voce dell'ADE
  tolta a mano) e `--prune` che toglie liste e voci di ADE non più configurate,
  il comando che senza `--align` non scrive e lo segnala; sul dizionario fornito verifica le 140
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
  Per un'ADE locale: copia dalla cartella senza rete e con un host non ammesso,
  `xs:include` seguito, record conservato a contenuto invariato, copie
  cancellate quando l'ADE esce dalla configurazione, file locale mancante
  segnalato, configurazione non valida che non scrive nulla. Non usa la rete.
- `tests/test_ade_config.py` verifica la lettura della sezione `ades`
  (`scripts/ades.py`): campi, code list con e senza dizionario, voci per code
  list di CityGML, file locali per URL `http` e `https`, e gli errori (nome di un
  modulo CityGML, prefisso o namespace riservati, URL fuori da `local.baseUrl`,
  nomi dei dizionari, collegamenti e `topLevel` non validi, nomi, prefissi e
  namespace ripetuti).

## Test nel browser

`python tests/browser_smoke.py` carica pagina, catalogo, dizionario delle code
list e script in Chromium (Playwright). Verifica:

- **navigazione**: ricerca, filtri per categoria (anche code list e primo
  livello), schede compresa Standard e riquadri, catena di ereditarietà con i
  prefissi, superfici ammesse;
- **ricerca delle proprietà**: classe dichiarante, apertura della proprietà con
  le classi concrete che la hanno, riapertura dei dettagli con lo stesso
  risultato, dettagli chiusi da Indietro e riaperti da Avanti, dettagli
  indicati come codifica GML, proprietà di classi astratte
  visibili con il filtro "solo concreti", dichiarazione XSD prima dei membri UML
  omonimi;
- **livelli di lettura**: passaggio da Codifica GML a Modello UML e ritorno, con
  il livello nell'URL e nei cambi di scheda, anche passando dalla pagina Code
  list; al livello UML la molteplicità del modello con il badge del dizionario
  (`buildingPart` `0..*`, "dizionario: 1..*"), anche nell'export; export con il
  livello dichiarato; selettore e Esporta JSON visibili a 390 e 850 px;
- **relazioni e generalizzazioni**: `buildingPart` letta come composizione anche
  nelle connessioni in ingresso di `BuildingPart`; la generalizzazione di
  `StringAttribute` presente solo nel modello UML, con la nota sul dizionario;
  `uom` fra le proprietà ereditate di `gml:QuantityExtent`, definito in
  `gml:MeasureOrNilReasonListType`; `Role` come classe di associazione di
  `CityObjectGroup.groupMember`, nei due versi; `TINRelief.tin` fra le
  geometrie; il campo Primo livello con il significato dello stereotipo
  «TopLevelFeatureType» e, a parte, i membri di `CityModel` che ammettono la
  classe, con la frase di OGC 20-010, §6.2.3, e la divergenza segnalata per le
  classi concrete senza lo stereotipo (`Building`, `Appearance`, `Version`,
  `VersionTransition`, `WallSurface`);
- **destinazioni**: `boundary` nel contesto della classe visitata
  (`BuildingUnit` senza le superfici di `Building`, divieto per `PlantCover`),
  separate dagli elementi sostituibili negli schemi;
- **modello concettuale**: generalizzazione UML, membri di un tipo base
  (diretti ed ereditati) e di un'unione, vincoli OCL, badge "solo riferimento",
  descrizione presa dal dizionario dati, membri nella scheda Standard con la
  loro corrispondenza negli schemi, requisiti della codifica GML nella scheda
  Standard e nei dettagli di una proprietà;
- **classi senza tipo XSD dedicato**: badge, numero dei membri nella scheda
  Proprietà (`CityModelMember`: 5), proprietà che le usano come tipo nella
  scheda Sorgente, messaggio dell'esempio d'uso per una code list senza
  proprietà che la usano e per una code list vuota;
- **riquadro Sorgenti**: documenti, copertura del modello concettuale e dei
  documenti normativi, generalizzazioni per fonte, divergenze fra dizionario e
  modello UML;
- **code list**: valori nelle classi e nella pagina della code list; esempio
  d'uso e stato aggiornati mentre si scrive, con il cursore che resta nel campo,
  e caratteri speciali di XML (`A&B` scritto `A&amp;B`); `codeSpace` del
  dizionario seguito dalle voci senza un `codeSpace` proprio e `codeSpace`
  propri mostrati sotto il codice (`TrafficAreaFunctionValue`), conservati
  anche quando il `codeSpace` del dizionario coincide per un momento con il
  loro (incolla, digitazione, cancellazione), con una voce aggiunta che segue
  il dizionario e gli URI attesi nell'export della scheda; export della
  scheda con i valori locali (`localCodeList`); aggiunta e annullamento di un
  valore, ricerca per valore, pulsante Code list, Salva (con la File System
  Access API sostituita da uno stub: il testo scritto coincide byte per byte con
  `codelists/codelists.js`), modifica durante la scrittura (resta da salvare;
  Salva e Reset sono disabilitati finché la scrittura non termina), scrittura
  fallita, Reset la cui scrittura fallisce (la tabella mostra subito lo stato
  iniziale e resta modificabile), Reset, download quando l'API manca, pagina
  Code list con i suoi filtri;
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

`python tests/browser_ade.py` costruisce, in una cartella temporanea, il catalogo
e il dizionario con l'ADE di prova di `tests/fixtures/ade` (come
`tests/test_ade.py`, senza rete) e li carica in Chromium. Verifica l'opzione ADE
del filtro degli schemi, la scheda di un elemento dell'ADE con il badge e la
scheda Standard (ADE di provenienza, primo livello, code list dalla
configurazione), i candidati dell'ADE in `adeOfAbstractBuilding`, la pagina di
una code list dell'ADE con il suo dizionario e un valore modificato e salvato,
le voci dell'ADE in `BuildingClassValue` in sola lettura ed eliminabili, il
riquadro Sorgenti con la sezione dell'ADE; l'assenza di errori JavaScript.
