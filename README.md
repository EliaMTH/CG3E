# CityGML 3.0 Explorer

Esploratore statico del vocabolario CityGML 3.0. Si cerca una classe a sinistra
e si consultano a destra definizioni, attributi, proprietà geometriche,
cardinalità, ereditarietà, associazioni, superfici di confine ammesse, requisiti
e sorgente XML.

Il catalogo unisce le due parti dello standard OGC:

- **struttura** dagli schemi XSD ufficiali (CityGML 3.0 Part 2: GML Encoding,
  OGC 21-006r2): classi, attributi, cardinalità, ereditarietà, relazioni;
- **modello concettuale** dal documento OGC 20-010 (CityGML 3.0 Part 1:
  Conceptual Model) e dal suo modello UML: stereotipi, oggetti di primo livello,
  code list, valori delle enumerazioni, superfici di confine ammesse, requisiti,
  composizioni.

Funziona offline: nessun backend, database o CDN. Tutte le fonti necessarie sono
nella cartella `sources/`.

![Scheda di Building](docs/screenshot-desktop.png)

## Aprire il catalogo

Aprire `index.html` con doppio clic. La pagina legge `data/catalog.js`, generato
dalle fonti in `sources/`; non servono server né connessione. I collegamenti al
documento OGC 20-010 aprono la sua copia locale.

## Sorgenti

Ogni file è scaricato dall'URL ufficiale e salvato in `sources/<host>/<percorso>`,
con la stessa struttura dell'URL. Tutti i file sono stati scaricati il
**15 ottobre 2026**.

### Schemi XSD

| Schemi | File | Versione | Origine | Pubblicazione |
|---|---|---|---|---|
| CityGML 3.0: 17 moduli, profilo `CityGML.xsd`, `codeListMetaData.xsd` | 19 | 3.0.0 (`xs:schema/@version`) | `http://schemas.opengis.net/citygml/` | 2023-08-02, OGC 21-006r2 |
| xAL 3.0 (indirizzi): `xAL.xsd`, `xAL-types.xsd`, `CommonTypes.xsd` | 3 | OASIS CIQ v3.0 cs02, con import di W3C XLink | `http://schemas.opengis.net/citygml/xAL/3.0/` | 2023-08-04 |
| GML 3.2.1 (`gml.xsd` e componenti) | 28 | 3.2.2 (`xs:schema/@version`, correzione OGC CR 12-092) | `http://schemas.opengis.net/gml/3.2.1/` | 2016-12-02 |
| ISO/TS 19139:2007 (`gco`, `gmd`, `gsr`, `gss`, `gts`) | 26 | 2012-07-13 | `http://schemas.opengis.net/iso/19139/20070417/` | 2012-07-13 |
| W3C XLink | 1 | — | `http://www.w3.org/1999/xlink.xsd` | 2008-12-03 (`Last-Modified`) |
| W3C namespace XML | 1 | — | `http://www.w3.org/2001/xml.xsd` | 2009-01-21 (`Last-Modified`) |

Le date di pubblicazione OGC provengono dai file `ReadMe.txt` del repository
degli schemi; il server `schemas.opengis.net` riporta per tutti i file OGC
`Last-Modified: 2025-04-09`. I 22 file CityGML e xAL coincidono con il
pacchetto ufficiale `http://schemas.opengis.net/citygml/citygml-3_0_0.zip`.

### Modello concettuale

| Fonte | Versione | Origine | Pubblicazione |
|---|---|---|---|
| OGC 20-010, *OGC City Geography Markup Language (CityGML) Part 1: Conceptual Model Standard* (HTML) | 3.0.0 | `https://docs.ogc.org/is/20-010/20-010.html` | approvato 2021-06-04, pubblicato 2021-09-13 (`Last-Modified` del file: 2026-04-24) |
| Modello UML CityGML 3.0 (XMI esportato da Enterprise Architect), file `XMI Files.zip` | 3.0 | repository OGC `opengeospatial/CityGML-3.0CM`, commit `71ec3bee28f6b883e543a4439a0732bd37e2d9ab` | 2021-08-02 |

Dal documento provengono stereotipi, oggetti di primo livello, code list con le
loro definizioni, tipi UML degli attributi, definizioni dei valori delle
enumerazioni, superfici di confine ammesse (tabelle dei requisiti
`/req/<modulo>/boundaries`), requisiti, capitoli dei moduli e sezioni
concettuali. Dall'XMI (`Integrated/CityGML_3.0.xml` dentro lo zip) proviene il
tipo di aggregazione delle relazioni (composizione, aggregazione, associazione).
Le classi del modello e gli elementi degli schemi corrispondono per nome; le
differenze sono elencate nel riquadro **Sorgenti** dell'interfaccia.

Accanto alle fonti sono conservati i file di avvertenze pubblicati con esse:
`citygml/ReadMe.txt`, `citygml/xAL/3.0/ReadMe-xAL-3_0.txt`,
`citygml/xAL/3.0/OASIS_COPYRIGHT_NOTICE.txt`, `gml/ReadMe.txt`,
`iso/19139/ReadMe.txt`, `iso/19139/20070417/ReadMe.txt` e la licenza del
repository del modello UML (`LICENSE`).

```text
sources/
  schemas.opengis.net/
    citygml/        CityGML 3.0, profilo base, codeListMetaData, xAL 3.0
    gml/3.2.1/      GML
    iso/19139/      ISO/TS 19139:2007
  www.w3.org/       XLink e namespace XML
  docs.ogc.org/     documento OGC 20-010
  raw.githubusercontent.com/opengeospatial/CityGML-3.0CM/<commit>/
                    XMI del modello UML e licenza del repository
  manifest.json     per ogni file: URL, data di download, Last-Modified,
                    versione dichiarata, namespace, SHA-256, import, ruolo
  xml-catalog.xml   catalogo OASIS XML che reindirizza gli URL degli schemi
                    alle cartelle locali
```

`sources/xml-catalog.xml` permette di usare gli schemi offline anche con
validatori XML che supportano i cataloghi OASIS.

## Aggiornare o estendere il catalogo

Requisiti: Python 3.10 o successivo.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
.venv/bin/python -m pip install -r requirements.txt       # Linux / macOS
```

I comandi seguenti vanno eseguiti con il Python dell'ambiente virtuale.

| Comando | Rete | Effetto |
|---|---|---|
| `python scripts/fetch_sources.py` | sì | Scarica gli schemi di `config/sources.json` e, ricorsivamente, ogni `xs:import`, `xs:include` e `xs:redefine`; scarica i documenti; riscrive `sources/`, `sources/manifest.json` e `sources/xml-catalog.xml` |
| `python scripts/build_catalog.py` | no | Rigenera `data/catalog.json` e `data/catalog.js` dalle fonti in `sources/` |
| `python scripts/verify_sources.py` | no | Verifica gli hash di `sources/manifest.json`, l'assenza di XSD non registrati e la presenza locale di ogni import |

`fetch_sources.py` accetta solo host elencati in `allowedHosts` e scarica in
HTTPS. Uno schema è accettato solo se è uno `xs:schema` con il namespace atteso,
e nel manifest resta l'URL `http://` usato negli schemi; un documento solo se
corrisponde al formato dichiarato (`text`, `html` o `zip`). La verifica TLS usa
il bundle di certificati `certifi`.

In `config/sources.json` il campo `role` dei documenti indica a
`build_catalog.py` quale file è il documento del modello concettuale
(`conceptual-model-document`) e quale archivio contiene l'XMI (`uml-model`).
Senza questi file il catalogo contiene solo le informazioni degli schemi.

Per aggiungere schemi (per esempio una ADE) si aggiunge l'URL all'elenco
`schemas` di `config/sources.json`, e l'host ad `allowedHosts` se necessario; poi
si eseguono `fetch_sources.py` e `build_catalog.py`. Lo stesso procedimento
aggiorna le fonti quando cambiano: il manifest registra nuove date e hash.

## Struttura del repository

```text
index.html             pagina dell'esploratore
assets/                JavaScript e CSS, senza dipendenze esterne
data/catalog.js        catalogo caricato dalla pagina (window.CITYGML_CATALOG)
data/catalog.json      stesso catalogo in JSON
sources/               fonti ufficiali e manifest
config/sources.json    URL, host ammessi e ruoli delle fonti
scripts/               download, lettura del modello concettuale, generazione e verifica
tests/                 test automatici
docs/                  modello dati del catalogo, test, schermate
```

Il formato di `data/catalog.json` è descritto in [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

## Test

```bash
python -m unittest discover -s tests -v
```

Il test nel browser richiede Playwright e Chromium
(`pip install playwright` e `python -m playwright install chromium`):

```bash
python tests/browser_smoke.py
```

Dettagli in [docs/TESTING.md](docs/TESTING.md).

## Limiti

- I valori delle code list (`class`, `function`, `usage`…) non fanno parte dello
  standard: il catalogo mostra nome e definizione di ogni code list, mentre i
  valori sono definiti da dizionari esterni indicati con `codeSpace`.
- Le categorie ricavate dagli schemi (feature, oggetto, tipo di dato, spazio,
  superficie di confine) e i tipi di collegamento (aggregazione, associazione,
  solo riferimento) seguono le regole di [docs/DATA_MODEL.md](docs/DATA_MODEL.md);
  stereotipi e composizioni provengono dal modello concettuale.
- Le superfici di confine ammesse sono quelle delle tabelle di OGC 20-010; quando
  una tabella dice "e tutte le sottoclassi", l'elenco delle superfici concrete è
  calcolato dalla gerarchia degli schemi.
- L'ereditarietà deriva da `xs:extension`; `substitutionGroup` e associazioni
  non trasferiscono proprietà.
- Non è un parser di file CityGML `.gml` né un validatore XML.

## Licenze

`LICENSE-app.txt` copre il codice, la configurazione e la documentazione
dell'applicazione. Le fonti in `sources/` mantengono i termini dei rispettivi
autori: OGC (https://www.ogc.org/legal/; il documento 20-010 è conservato senza
modifiche, con le sue note di copyright), ISO/TC 211, OASIS
(`OASIS_COPYRIGHT_NOTICE.txt`), W3C (avvertenze nei file) e, per l'XMI, la
licenza MIT del repository `opengeospatial/CityGML-3.0CM` (`LICENSE`).
