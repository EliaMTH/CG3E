# CityGML 3.0 Explorer – due cataloghi indipendenti

Esploratore statico del vocabolario CityGML 3.0: cerca una classe a sinistra,
consulta a destra definizioni, attributi, proprietà geometriche, cardinalità,
ereditarietà, associazioni e sorgente. Nessun backend, database o CDN.

**La sorgente iniziale è esattamente il tuo `voc.zip`: 22 file XSD + 3 file OWL.**
I file sono copiati invariati in `sources/original-voc/`. Lo script
`python scripts/verify_sources.py` verifica i loro SHA-256.

## Due comandi, un'interfaccia

Dopo l'estrazione dello ZIP, apri un terminale nella cartella con `index.html`.
Installa i requisiti Python una volta sola (es. nel tuo `.venv`):

```bash
python -m pip install -r requirements.txt
```

### A. Solo CityGML 3.0 (senza alcuna ontologia)

```bash
python scripts/build_citygml.py
```

- Usa **solo i 22 XSD originali** e gli eventuali XSD in
  `sources/dependencies/citygml/`.
- Cerca e scarica gli **XSD tecnici mancanti** (GML 3.2.1, XLink,
  ISO 19139, ecc.) e i loro import transitivi; non scarica OWL.
- Rigenera `data/catalog.js` e `data/catalog.json` e rende **attivo**
  il profilo **Solo CityGML**.
- Non legge neppure gli OWL originali, anche se rimangono nella cartella.

### B. CityGML 3.0 + OWL

```bash
python scripts/build_citygml_owl.py
```

- Usa gli stessi 22 XSD **e** i 3 OWL originali.
- Cerca e scarica le dipendenze XSD nella cartella `citygml/` e gli import
  delle ontologie (CityOWL LIRIS, SOSA/SSN, GeoSPARQL e altri)
  in `sources/dependencies/owl/`.
- Attiva il profilo **CityGML + OWL**: potrai navigare anche i concetti
  UISH e i collegamenti espliciti verso CityOWL. Non esegue reasoning OWL.

In entrambi i casi, **l'ultimo comando eseguito sceglie cosa la webapp mostra**.
Se `index.html` era aperto, **ricarica la pagina** (su file locale, `Ctrl+F5` se
il browser mantiene una copia in cache). Apri `index.html` con doppio clic:
usa direttamente il `data/catalog.js` generato, senza server.

### Se vuoi rigenerare senza rete

```bash
python scripts/build_citygml.py --offline
python scripts/build_citygml_owl.py --offline
```

I due script fanno comunque il build **anche quando un download fallisce** e
segnalano le dipendenze non risolte. Gli import mancanti non implicano che il
catalogo sia inutilizzabile: restano visibili come riferimenti esterni.

Per motivi di riproducibilità la versione scaricata è verificata per namespace
(XSD) oppure per IRI/versionIRI dichiarato (OWL). Il downloader non inserisce
automaticamente una versione ontologica diversa da quella richiesta.

Opzioni utili: `--verbose`, `--timeout 5`, `--max-files 180`; per il profilo
completo puoi **scegliere esplicitamente** `--w3c-editor-draft` (moduli SSN W3C
in sviluppo) e fissarne la revisione con `--w3c-ref COMMIT`.

## Struttura della cartella `sources/`

```text
sources/
  original-voc/                   25 file identici al tuo voc.zip
    *.xsd                        22 schemi CityGML e ausiliari
    *.owl                         3 ontologie originali UISH / unità
  dependencies/
    citygml/                     SOLO XSD tecnici scaricati
    owl/                         SOLO ontologie TTL/OWL/RDF scaricate
  original-manifest.json         inventario SHA-256 dei 25 originali
  download-lock.json            creato al primo download riuscito
  download-report.json          risultato dell'ultimo download
  dependency-manifest-citygml.json  import del profilo CityGML
  dependency-manifest-full.json     import del profilo CityGML + OWL
  dependency-manifest.json      copia del manifest del profilo attivo
  xml-catalog-citygml.xml       catalogo URI XML del profilo CityGML
  xml-catalog-full.xml          catalogo URI XML del profilo completo
```

I file in `sources/dependencies/` **non erano nel tuo ZIP**: vengono
acquisiti dagli script da fonti esterne e salvati con host e percorso di origine,
con i controlli di hash in `download-lock.json`. In questo archivio le due
cartelle partono vuote (a parte un README), perché qui non è possibile
scaricare dalla rete i documenti ufficiali. Non devi copiare a mano XSD già
presenti in `original-voc`: il downloader li riconosce tramite namespace e nome.

Se hai già scaricato i file nella tua vecchia installazione puoi conservarli e
riutilizzarli copiando **solo i file XSD** nella nuova
`sources/dependencies/citygml/` e **solo i file TTL/OWL/RDF** in
`sources/dependencies/owl/`, preferibilmente mantenendo la struttura relativa
degli URL. Dopo averli copiati esegui il relativo comando con `--offline`.

## File `data/` e attivazione

```text
data/catalog-citygml.json    snapshot dell'ultimo build CityGML
    /catalog-full.json       snapshot dell'ultimo build CityGML + OWL
    /catalog.json            catalogo ATTIVO (sovrascritto a ogni esecuzione)
    /catalog.js              catalogo ATTIVO per apertura via file://
    /active-mode.json        nome del profilo ATTIVO
```

I due snapshot sono inclusi nell'archivio così puoi già aprire la pagina
in modalità **Solo CityGML** senza prima eseguire alcuno script. Gli snapshot
sono stati generati dai 25 originali **senza dipendenze scaricate**: i riferimenti
GML e alcuni termini esterni potranno essere incompleti fino a quando
eseguirai i comandi collegato alla rete.

Nell'interfaccia il profilo attivo compare in alto a destra. I due profili
**non si mescolano**: quello solo XSD non contiene nodi OWL, non contiene
ponti XSD–OWL e non consulta la cartella `sources/dependencies/owl/`.

## Che cosa era già presente e cosa abbiamo aggiunto

**Originali, invariati:** 25 file in `voc.zip`, verificabili con
`python scripts/verify_sources.py`. Tra gli XSD: `core.xsd`, `building.xsd`,
`construction.xsd`, `transportation.xsd`, `xAL.xsd` e gli altri moduli CityGML.
Tra gli OWL: `uish_ontology_building.owl`, `uish_ontology_sensors.owl`,
`uo-full.owl`.

**Aggiunto dall'applicazione:** interfaccia HTML/CSS/JS, generatore
`scripts/build_catalog.py`, downloader `scripts/download_dependencies.py`,
configurazione dei soli ponti di navigazione XSD–CityOWL,
`scripts/build_citygml.py` e `scripts/build_citygml_owl.py`, cartelle
`dependencies/citygml/` e `dependencies/owl/`, cataloghi JSON e test.
Non sono state aggiunte classi CityGML inventate né modificate le sorgenti.

**Aggiunte esterne opzionali:** i documenti scaricati dagli script non fanno
parte dei 25 originali e restano segregati nelle due cartelle di dipendenze.
Per una lista completa di URL e import leggi i due file
`dependency-manifest-*.json` oppure la scheda “Sorgenti” nell'interfaccia.

## Verifica e test

```bash
python scripts/verify_sources.py
python -m unittest discover -s tests -v
```

Se installati Chromium e Playwright, per uno smoke test del browser (HTML, CSS e JS caricati in memoria, senza verificare la policy `file://` del browser):

```bash
python tests/browser_modes.py
```

## Limiti e trasparenza

- Gli XSD descrivono la codifica GML/XML, **non il modello UML originario**.
  Si possono esplorare molti attributi e relazioni, ma non ogni sfumatura UML.
- Tipi GML, tipi di supporto e attributi XML possono comparire come concetti
  tecnici; si possono filtrare nella UI.
- La distinzione fra attributi, relazioni e geometrie nella UI è una
  classificazione di navigazione derivata dai tipi e nomi XML.
- L'ereditarietà deriva da `xs:extension` in XSD e da `rdfs:subClassOf`
  dichiarati esplicitamente in OWL, **non da associazioni padre-figlio**.
- La modalità completa presenta affermazioni OWL esplicite senza inferenze;
  per i collegamenti tra XSD e CityOWL si usano ponti di navigazione
  dichiarati in `config/navigation-bridges.json`, **non equivalenze OWL**.
- Se un import manca, non viene sostituito da un file diverso per nasconderlo.
  Il build termina comunque e la UI segnala il riferimento esterno.
- Non è un parser di file CityGML `.gml`, né un sistema per validare XML,
  né un triplestore RDF.

Licenze: consulta `LICENSE-app.txt` per l'interfaccia e le intestazioni e i
termini originali delle singole sorgenti per gli schemi e vocabolari esterni.
