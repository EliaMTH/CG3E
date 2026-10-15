# CityGML 3.0 Explorer

Esploratore statico del vocabolario CityGML 3.0, costruito dagli schemi XSD
ufficiali OGC (CityGML 3.0 Part 2: GML Encoding, OGC 21-006r2). Si cerca una
classe a sinistra e si consultano a destra definizioni, attributi, proprietà
geometriche, cardinalità, ereditarietà, associazioni e sorgente XML.

Funziona offline: nessun backend, database o CDN. Tutti gli schemi necessari,
compresi quelli importati (GML, ISO 19139, XLink), sono nella cartella `sources/`.

![Scheda di Building](docs/screenshot-desktop.png)

## Aprire il catalogo

Aprire `index.html` con doppio clic. La pagina legge `data/catalog.js`, generato
dagli schemi in `sources/`; non servono server né connessione.

## Sorgenti

Ogni file è scaricato dall'URL ufficiale indicato negli schemi e salvato in
`sources/<host>/<percorso>`, con la stessa struttura dell'URL. Tutti i file sono
stati scaricati il **15 ottobre 2026**.

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

Accanto agli schemi sono conservati i file di avvertenze pubblicati con essi:
`citygml/ReadMe.txt`, `citygml/xAL/3.0/ReadMe-xAL-3_0.txt`,
`citygml/xAL/3.0/OASIS_COPYRIGHT_NOTICE.txt`, `gml/ReadMe.txt`,
`iso/19139/ReadMe.txt` e `iso/19139/20070417/ReadMe.txt`.

```text
sources/
  schemas.opengis.net/
    citygml/        CityGML 3.0, profilo base, codeListMetaData, xAL 3.0
    gml/3.2.1/      GML
    iso/19139/      ISO/TS 19139:2007
  www.w3.org/       XLink e namespace XML
  manifest.json     per ogni file: URL, data di download, Last-Modified,
                    versione dichiarata, namespace, SHA-256, import
  xml-catalog.xml   catalogo OASIS XML che reindirizza gli URL ufficiali
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
| `python scripts/fetch_sources.py` | sì | Scarica gli URL di `config/sources.json` e, ricorsivamente, ogni `xs:import`, `xs:include` e `xs:redefine`; riscrive `sources/`, `sources/manifest.json` e `sources/xml-catalog.xml` |
| `python scripts/build_catalog.py` | no | Rigenera `data/catalog.json` e `data/catalog.js` dagli XSD in `sources/` |
| `python scripts/verify_sources.py` | no | Verifica gli hash di `sources/manifest.json`, l'assenza di XSD non registrati e la presenza locale di ogni import |

`fetch_sources.py` accetta solo host elencati in `allowedHosts`, scarica in
HTTPS, verifica che ogni file sia uno `xs:schema` con il namespace atteso e
registra nel manifest l'URL `http://` usato negli schemi. La verifica TLS usa il
bundle di certificati `certifi`.

Per aggiungere schemi (per esempio una ADE) si aggiunge l'URL all'elenco
`schemas` di `config/sources.json`, e l'host ad `allowedHosts` se necessario; poi
si eseguono `fetch_sources.py` e `build_catalog.py`. Lo stesso procedimento
aggiorna gli schemi esistenti quando le fonti ufficiali cambiano: il manifest
registra nuove date e hash.

## Struttura del repository

```text
index.html             pagina dell'esploratore
assets/                JavaScript e CSS, senza dipendenze esterne
data/catalog.js        catalogo caricato dalla pagina (window.CITYGML_CATALOG)
data/catalog.json      stesso catalogo in JSON
sources/               schemi XSD ufficiali e manifest
config/sources.json    URL di partenza e host ammessi per fetch_sources.py
scripts/               download, generazione e verifica
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

- Gli XSD descrivono la codifica GML/XML, non il modello concettuale UML
  (OGC 20-010). Stereotipi UML, nomi delle code list e requisiti del modello
  concettuale non compaiono negli schemi.
- I valori delle code list (`class`, `function`, `usage`…) non fanno parte degli
  schemi: gli attributi corrispondenti hanno tipo `gml:CodeType` e i valori sono
  definiti da dizionari esterni.
- Le categorie (feature, oggetto, tipo di dato, spazio, superficie di confine)
  e i tipi di collegamento (aggregazione, associazione, solo riferimento)
  derivano dalla gerarchia `xs:extension` e dalla forma XML delle proprietà;
  [docs/DATA_MODEL.md](docs/DATA_MODEL.md) descrive le regole. Approssimano gli
  stereotipi e le aggregazioni del modello UML, che negli schemi non sono
  dichiarati in modo esplicito.
- L'ereditarietà deriva da `xs:extension`; `substitutionGroup` e associazioni
  non trasferiscono proprietà.
- Non è un parser di file CityGML `.gml` né un validatore XML.

## Licenze

`LICENSE-app.txt` copre il codice, la configurazione e la documentazione
dell'applicazione. Gli schemi in `sources/` mantengono i termini dei rispettivi
autori: OGC (https://www.ogc.org/legal/), ISO/TC 211, OASIS
(`OASIS_COPYRIGHT_NOTICE.txt`) e W3C (avvertenze nei file).
