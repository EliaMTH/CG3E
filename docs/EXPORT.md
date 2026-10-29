# Esportazioni, versione 1

`scripts/export.py` produce tre esportazioni del vocabolario CityGML 3.0 in uso;
`scripts/exporters.py` contiene le funzioni e può essere importato da un
programma Python.

| Exporter | Uscita | Destinatario |
|---|---|---|
| `city3d` | un JSON | l'editor degli attributi di City3D |
| `generator` | uno zip | un generatore di file CityGML a partire da dati sparsi |
| `standard` | uno zip | una persona che vuole consultare lo standard in uso |

Il formato è quello standard dove esiste: gli schemi sono gli XSD ufficiali
invariati, le code list seguono le forme di OGC 21-006r2, Annex E. Il contenuto
senza un formato standard sta in un solo file nostro per exporter, con il
riferimento alla fonte di ogni regola:

| Contenuto | Formato | Origine |
|---|---|---|
| Elementi, proprietà, cardinalità | XSD ufficiali | `sources/` |
| Code list e valori | `gml:Dictionary`, JSON e CSV di Annex E | dizionario delle code list |
| Documenti e modello UML | HTML OGC e XMI | `sources/` |
| Code list usata da ogni proprietà | `codeListUse` | catalogo |
| Struttura risolta degli XSD, regole che gli XSD non esprimono | `elements`, `rules` di `citygml-generator.json` | catalogo |

## Comando

```text
python scripts/export.py city3d|generator|standard --out PERCORSO
        [--codelists PATH]          dizionario; predefinito codelists/codelists.js
        [--exported-at ISO8601]     data con fuso orario; predefinita l'ora corrente
```

Gli input sono `data/catalog.json`, il dizionario salvato (le modifiche nella
pagina vanno prima salvate) e `sources/`. Il comando si ferma con un messaggio
`ERRORE:` e codice di uscita 1, senza scrivere nulla, se:

- lo SHA-256 di un file usato dal catalogo (schemi, documenti OGC 20-010 e
  21-006r2, XMI) non coincide con `sources/manifest.json`;
- un file di `sources/` da copiare non ha lo SHA-256 del manifest;
- `data/catalog.js` non coincide con `data/catalog.json` (`standard`);
- il dizionario non è nel formato 1 o non ha le 140 code list del catalogo;
- una code list con valori non ha identificatore, `codeSpace` o uno dei
  metadati di Annex E (`dataType`, `namespace`, `language`, `authority`,
  `version`): si completa con `scripts/codespaces.py`;
- un dizionario GML esportato non valida contro `gml.xsd` e
  `codeListMetaData.xsd` (`generator`, `standard`);
- due code list esportate hanno lo stesso `codeSpace` (`generator`).

La validazione usa solo le copie locali degli schemi, risolte con il catalogo
OASIS XML: un URL che il catalogo non risolve è un errore e non viene
scaricato.

Gli avvisi (`AVVISO:`) non fermano l'export:

- lista modificata che ha ancora il `codeSpace` dell'esempio OGC;
- valori senza codice, non esportati; l'avviso compare anche quando nessun
  valore della lista ha un codice e la lista resta fuori dall'export;
- segnaposto in una lista con valori, non esportati;
- codici ripetuti nello stesso `codeSpace` (negli esempi OGC:
  `BuildingFurnitureFunctionValue` e `BuildingFurnitureUsageValue`, codici 1270
  e 2200).

A parità di input e di `--exported-at` l'output è identico byte per byte: chiavi,
liste e file in ordine fisso; negli zip, file in ordine alfabetico con la data
dell'export e permessi fissi.

## Code list (OGC 21-006r2, Annex E)

Annex E è informativo: *"There is no standardized model for CityGML
codelists"*. Propone una struttura basata su `gml:Dictionary`, *"the expected
form for defining and exchanging codelists in a GML environment"*, e due
codifiche alternative, CSV e JSON. Per Annex E il `codeSpace` serve *"to
identify the codelist from which the value has been taken"*.

Annex E indica che il repository degli esempi OGC offre ogni code list in GML,
CSV e JSON. Al 19 ottobre 2026 i file JSON non sono pubblicati e i CSV hanno una
forma diversa da quella di Annex E (righe `Meta;CityGML_Version;3.0`,
`Meta|Module|…`, `Meta|DataType|…` in minuscolo, codici UUID diversi da quelli
dei file XML): per JSON e CSV gli export seguono il testo di Annex E.

Sono esportate le code list con valori reali; i valori segnaposto
`{example-N}` e i valori senza codice sono esclusi. Nel dizionario attuale: 44
liste, 2295 valori. Il file di ogni lista si chiama
`<Modulo>.<CodeList>.<xml|json|csv>`, come negli esempi OGC.

### GML

La forma degli esempi OGC (`https://data.ogc.org/citygml-swg/CodeList_Examples_3.0.0/`):

```xml
<gml:Dictionary xmlns:gml="http://www.opengis.net/gml/3.2"
    xmlns:cmd="http://www.opengis.net/citygml/codelistmetadata/3.0" gml:id="RoofTypeValue" …>
  <gml:metaDataProperty>
    <cmd:CodeListMetaData>
      <cmd:dataType>RoofTypeValue</cmd:dataType>
      <cmd:namespace>http://www.opengis.net/citygml/building/3.0</cmd:namespace>
      <cmd:language>en-US</cmd:language>
      <cmd:authority>SIG3D</cmd:authority>
      <cmd:version>1.0</cmd:version>
    </cmd:CodeListMetaData>
  </gml:metaDataProperty>
  <gml:description></gml:description>
  <gml:identifier codeSpace="https://www.sig3d.org/codelists/citygml/building/3.0/RoofTypeValue">RoofTypeValue</gml:identifier>
  <gml:dictionaryEntry>
    <gml:Definition gml:id="id1">
      <gml:description>flat roof</gml:description>
      <gml:identifier codeSpace="https://www.sig3d.org/codelists/citygml/building/3.0/RoofTypeValue">1000</gml:identifier>
      <gml:name>flat roof</gml:name>
    </gml:Definition>
  </gml:dictionaryEntry>
  …
</gml:Dictionary>
```

- `gml:id` del dizionario è il nome della code list; quello dei valori è `id1`,
  `id2`, … nell'ordine del dizionario, come in tutti gli esempi OGC.
- I metadati usano sempre il namespace di `codeListMetaData.xsd`, anche per le
  liste derivate da esempi OGC con `http://www.opengis.net/citygml/codelist-metadata`.
- `xsi:schemaLocation` indica gli URL ufficiali di `gml.xsd` e
  `codeListMetaData.xsd`.
- Il `codeSpace` di un valore è il suo, se il dizionario ne ha uno, altrimenti
  quello della lista. In tre liste di Transportation (`TrafficAreaFunctionValue`,
  `AuxiliaryTrafficAreaFunctionValue`, `TrafficAreaUsageValue`) gli esempi OGC
  danno a ogni valore un `codeSpace` proprio.

### JSON

La struttura di Annex E §E.2.3:

```json
{"Dictionary": {
  "@id": "RoofTypeValue",
  "metaDataProperty": {"CodeListMetaData": {"dataType": "…", "namespace": "…", "language": "…", "authority": "…", "version": "…"}},
  "description": "",
  "identifier": {"@codeSpace": "…", "#text": "RoofTypeValue"},
  "dictionaryEntry": [
    {"Definition": {"@id": "id1", "description": "flat roof",
                    "identifier": {"@codeSpace": "…", "#text": "1000"}, "name": "flat roof"}}
  ]}}
```

### CSV

La struttura di Annex E §E.2.2, con il separatore `|` dell'esempio; le righe
terminano con CRLF, come in RFC 4180:

```text
CodeType|Identifier|Description
Meta|CityGML_DataType|Building|RoofTypeValue
Meta|CityGML_Namespace|http://www.opengis.net/citygml/building/3.0
Meta|Language|en-US
Meta|Version|1.0
Code|1000|flat roof
```

La terza colonna delle righe `Code` è il nome del valore: nell'esempio di
Annex E `Code|1000|flat roof` corrisponde a `gml:name` dell'esempio GML. La
forma CSV non contiene autorità né `codeSpace`. Un campo che contiene `|` o `"`
è racchiuso fra virgolette.

## `codeListUse`

Una voce per ogni elemento CityGML concreto (feature, oggetti, tipi di dato;
esclusi astratti, tipi tecnici e ADE hook) e per ogni sua proprietà con code
list, ereditate comprese. Elementi in ordine di namespace e nome, proprietà
nell'ordine dell'XML. Nel catalogo attuale: 158 voci, 63 elementi, 136 code list.

```json
{"element": "TrafficArea", "elementNamespace": "http://www.opengis.net/citygml/transportation/3.0",
 "property": "function", "propertyNamespace": "http://www.opengis.net/citygml/transportation/3.0",
 "codeList": "TrafficAreaFunctionValue",
 "declaredIn": "TrafficArea", "declaredInNamespace": "http://www.opengis.net/citygml/transportation/3.0",
 "multiplicity": "0..*"}
```

La stessa proprietà porta a liste diverse secondo l'elemento (`function` di
`Building` e di `TrafficArea`): la chiave è la coppia (elemento, proprietà),
ognuna con nome locale e namespace. `multiplicity` è quella degli schemi.

## Intestazione dei JSON

| Campo | Contenuto |
|---|---|
| `format` | `citygml-explorer/city3d` o `citygml-explorer/generator` |
| `formatVersion` | versione del formato (1) |
| `exportedAt` | data dell'export, UTC |
| `schemas` | versione degli schemi (`CityGML 3.0.0 (OGC 21-006r2)`) |
| `dictionary` | `sha256` del dizionario esportato, `edited` (liste modificate), `codeSpacePolicy` (politica dei `codeSpace`, o `null`) |
| `sources` | `conceptualModel` ed `encoding` (numero, titolo, versione, data di approvazione, URL e SHA-256 dei documenti OGC 20-010 e 21-006r2), `schemaFiles` (numero di XSD), `codeListExamples` (fonte degli esempi OGC) |

## `city3d`

`python scripts/export.py city3d --out citygml-codelists.city3d.json`

Un JSON con l'intestazione, `codeLists` e `codeListUse`. `codeLists` ha una
voce per ognuna delle 140 code list, in ordine di nome:

| Campo | Contenuto |
|---|---|
| `module` | modulo CityGML |
| `state` | `values`, `placeholder` (solo segnaposto), `empty`, `unavailable` (esempio non pubblicato) |
| `exportedValues` | numero di valori esportati; 0 per una lista `values` senza nessun valore con codice, che non è esportata |
| `edited` | presente e true per le liste modificate |
| `Dictionary` | il contenuto della forma JSON di Annex E, solo per le liste con valori reali |

## `generator`

`python scripts/export.py generator --out citygml-generator.zip`

| Percorso | Contenuto |
|---|---|
| `README.md` | contenuto, versioni, validazione offline |
| `manifest.json` | percorso, SHA-256 e dimensione di ogni file |
| `citygml-generator.json` | intestazione, `codeLists`, `codeListUse`, `elements`, `rules` |
| `xml-catalog.xml` | catalogo OASIS XML: URL degli schemi → `schemas/`, `codeSpace` delle liste → `codelists/` |
| `schemas/<host>/<percorso>` | i 78 XSD di `sources/` (22 CityGML e xAL, 56 importati: GML, ISO 19139, XLink, XML), con lo SHA-256 del manifest, e le avvertenze pubblicate con essi |
| `codelists/` | dizionari GML e JSON |

`xml-catalog.xml` risolve gli URL `http` e `https` di `schemas.opengis.net` e
`www.w3.org` e il `codeSpace` di ogni lista esportata. I `codeSpace` propri dei
valori non sono risolti: negli esempi OGC alcuni sono condivisi fra liste
diverse (`…/gml/drainage`, `…/gml/unknown`). Lo schema completo è
`schemas/schemas.opengis.net/citygml/profiles/base/3.0/CityGML.xsd`:

```text
XML_CATALOG_FILES=xml-catalog.xml xmllint --nonet --noout \
  --schema schemas/schemas.opengis.net/citygml/profiles/base/3.0/CityGML.xsd file.gml
```

### `codeLists`

Una voce per code list, come in `city3d` senza `Dictionary`; le liste
esportate hanno `codeSpace` e `files` (`.xml` e `.json` in `codelists/`).

### `elements`

Gli elementi di `codeListUse` (oggi 107: 80 feature, 23 tipi di dato, 4
oggetti), in ordine di namespace e nome:

| Campo | Contenuto |
|---|---|
| `name`, `namespace`, `qname` | identità dell'elemento |
| `kind` | `feature`, `object`, `datatype` |
| `type` | tipo XML |
| `spaceRole` | `space`, `boundary` o `null` |
| `topLevel` | true per lo stereotipo «TopLevelFeatureType» di OGC 20-010: le feature che rappresentano i componenti principali del modello concettuale e possono essere scomposte in parti |
| `substitutionGroup` | catena dei `substitutionGroup` fino a GML |
| `description` | documentazione dello schema |
| `properties` | tutte le proprietà, ereditate comprese, nell'ordine richiesto dall'XML: prima quelle del tipo base più lontano, poi a scendere; in ogni tipo, l'ordine del modello di contenuto (oggi 3483). Fanno eccezione i membri di un gruppo `xs:choice` ripetuto, che possono comparire alternati (vedi `choiceGroups`) |
| `choiceGroups` | presente se l'elemento ha gruppi `xs:choice`: per ognuno, con chiave l'identificatore usato in `choices`, `minOccurs` e `maxOccurs` (occorrenze nel tipo, comprese le ripetizioni dei gruppi che lo contengono) e `members`. A ogni occorrenza compare uno solo dei membri: con `maxOccurs` maggiore di 1 i membri possono comparire tutti, in qualsiasi ordine fra loro. Oggi solo `core:CityModel`, con i cinque membri `…Member` e occorrenze `0..unbounded` |

Ogni proprietà:

| Campo | Contenuto |
|---|---|
| `name`, `namespace`, `qname` | nome XML della proprietà; `namespace` null e `qname` senza prefisso per un attributo locale non qualificato (per esempio `srsName` di `app:TexCoordGen`) |
| `xmlKind` | `element` o `attribute` |
| `group` | `attribute`, `xmlAttribute`, `association`, `geometry`, `ade` |
| `minOccurs`, `maxOccurs` | cardinalità degli schemi (`maxOccurs` intero o `unbounded`) |
| `choices` | gruppi `xs:choice` che contengono la proprietà, come `<dichiarante>/choice:<riga>`; le proprietà con lo stesso identificatore sono alternative a ogni occorrenza del gruppo, descritto in `choiceGroups` dell'elemento |
| `type` | tipo XML dichiarato (QName), `null` per un tipo anonimo |
| `targets` | elementi di destinazione; vuoto per le proprietà che sono esse stesse un elemento globale (`xs:element/@ref`) |
| `candidates` | elementi concreti ammessi dagli schemi al posto delle destinazioni: le destinazioni stesse, se concrete, e gli elementi del loro `substitutionGroup` |
| `declaredIn` | elemento che dichiara la proprietà |
| `description` | documentazione dello schema |
| `nillable`, `default`, `fixed` | presenti se dichiarati; per un riferimento, quelli della dichiarazione globale (per esempio `gml:boundedBy` è nillable) |
| `encoding` | `allowsInline`, `allowsReference`: forme di collegamento ammesse dal tipo della proprietà |
| `codeList` | code list della proprietà |
| `uml` | membro corrispondente del modello concettuale: `class`, `member`, `type`, `multiplicity` (del modello UML, come nelle figure di OGC 20-010) e `dictionaryMultiplicity` quando il dizionario dati riporta un valore diverso (per esempio `boundary`: `0..*`, dizionario `1..*`) |

È una vista risolta degli XSD, non una fonte alternativa: la validità si
verifica contro `schemas/`.

### `rules`

Le regole che gli XSD non esprimono, ognuna con `source`. Sono dati da leggere:
il pacchetto non le applica.

| Chiave | Contenuto | Fonte |
|---|---|---|
| `allowedBoundaries` | per ognuno dei 58 spazi con tabella dei confini: `space`, `namespace`, `abstract`, superfici scritte nella tabella (`written`, con `withSubclasses`), superfici concrete risultanti (`concrete`), `ade` (classi da ADE ammesse), `none` (nessuna superficie ammessa) | OGC 20-010, tabelle `/req/<modulo>/boundaries`: `requirement`, `table`, `url` |
| `topLevel` | i 20 elementi con lo stereotipo «TopLevelFeatureType», i componenti principali del modello concettuale | OGC 20-010, stereotipo `TopLevelFeatureType`: `stereotype`, `url` |
| `referenceOnly` | le 12 proprietà da scrivere solo come `xlink:href`: `element`, `property` | schemi (`schemas`) e requisiti `/reference` di OGC 21-006r2 (`requirements`, con punto e `url`) |
| `constraints` | i 12 vincoli OCL: `class` (classe UML), `xsd` (elemento o tipo degli schemi, `null` se la classe non ne ha), `name`, `text` | OGC 20-010, tabelle Metadata: `table`, `url` |
| `encodingRules` | requisiti, raccomandazioni e classi di requisiti di OGC 21-006r2: `kind`, `title`, `id`, `module`, `text`, `parts`, `notes`, `targetType` e `dependencies` per le classi, `properties` nominate (`element`, `property`, `part`) | OGC 21-006r2: `url` |

## `standard`

`python scripts/export.py standard --out citygml-explorer.zip`

| Percorso | Contenuto |
|---|---|
| `EXPORT.md` | come aprirlo, contenuto, versioni e date dei documenti, data di download delle fonti, liste modificate, politica dei `codeSpace`, data dell'export |
| `manifest.json` | percorso, SHA-256 e dimensione di ogni file |
| `index.html`, `assets/`, `data/catalog.js` | l'explorer e il catalogo |
| `codelists/codelists.js` | il dizionario esportato |
| `codelists/codelists.default.js` | lo stato iniziale del dizionario |
| `sources/` | i file di `sources/manifest.json`, con lo SHA-256 del manifest, `manifest.json` e `xml-catalog.xml` |
| `dictionaries/` | dizionari GML e CSV |
| `README.md`, `LICENSE-app.txt` | descrizione e licenza dell'applicazione |

Estratto in una cartella qualsiasi, `index.html` si apre da `file://`; i
collegamenti ai documenti OGC aprono le copie in `sources/`. Restano fuori
`scripts/`, `tests/`, `config/`, `docs/` e `data/catalog.json`. La dimensione è
di circa 30 MB, dominata dai documenti OGC.

## `manifest.json` dei pacchetti

```json
{"format": "citygml-explorer/generator-manifest", "formatVersion": 1, "exportedAt": "…",
 "files": [{"path": "README.md", "sha256": "…", "bytes": 1234}]}
```

Elenca ogni file del pacchetto tranne sé stesso, in ordine alfabetico.

## `codeSpace` delle code list proprie

```text
python scripts/codespaces.py --base URI --version V --authority NOME
        [--language L]               predefinita: quella della lista
        [--lists NOME,…]             predefinite: le liste modificate (edited)
        [--dry-run]                  mostra le modifiche senza scriverle
        [--codelists PATH]           predefinito codelists/codelists.js
        [--applied-at ISO8601]       data da registrare; predefinita l'ora corrente
```

Una lista usata com'è pubblicata conserva il `codeSpace` della fonte; una lista
compilata o modificata nel progetto ne ha uno proprio. Per ogni lista trattata:

- il `codeSpace` della lista e di ogni suo valore diventa
  `<base><versione>/<Modulo>.<CodeList>.xml`, l'URL del file GML esportato se la
  cartella dei dizionari è pubblicata sotto `<base><versione>/`;
- `authority`, `version` e, con `--language`, `language` dei metadati prendono
  i valori del comando;
- identificatore e `dataType` diventano il nome della code list, `namespace` il
  namespace del suo modulo negli schemi;
- la lista è segnata come modificata (`edited`).

Una lista senza valori reali non è trattata e il comando lo segnala. `--base`
è un URI assoluto `https:`, `http:`, `urn:` o `tag:`; un URL termina con `/`.
Per pacchetti in bozza: `https://example.org/…` (RFC 2606) o
`tag:dominio,data:…` (RFC 4151).

Il dizionario registra la politica in `codeSpacePolicy` (base, versione,
autorità, lingua se indicata, liste trattate, data). Con gli stessi base,
versione, autorità e lingua la politica si estende alle nuove liste; con valori
diversi la sostituisce. Rieseguito con gli stessi argomenti, il comando non
cambia nulla. Il file è scritto come lo scrive Salva nell'interfaccia (testo
JSON con indentazione di uno spazio, righe terminate da LF). Reset
nell'interfaccia riporta il dizionario agli esempi OGC, `codeSpace` compresi:
dopo un Reset il comando va rieseguito.
