# Catalogo di navigazione, versione 1

`data/catalog.json` e `data/catalog.js` contengono gli stessi dati. Il secondo
espone `window.CITYGML_CATALOG` per il caricamento locale senza fetch. Entrambi
sono generati da `scripts/build_catalog.py` a partire dalle fonti in `sources/`:
gli XSD danno la struttura, il documento OGC 20-010 e il modello UML (letti da
`scripts/conceptual_model.py`) le informazioni del modello concettuale. Il
frontend non modifica le sorgenti né il catalogo: scrive soltanto il dizionario
delle code list (`codelists/codelists.js`).

## Campi principali

| Campo | Contenuto |
|---|---|
| `schemaVersion` | versione di questo formato (1) |
| `title`, `sourceVersion` | titolo e versione degli schemi (`CityGML 3.0.0 (OGC 21-006r2)`) |
| `nodes` | dizionario dei concetti per identificatore |
| `files` | schemi letti, con provenienza |
| `dependencies` | `xs:import`, `xs:include` e `xs:redefine` di ogni schema |
| `standard` | modello concettuale: documento, modello UML, capitoli, requisiti, sezioni concettuali, rapporto di confronto (null se le fonti mancano) |
| `warnings` | problemi di lettura, cicli, file non registrati nel manifest, fonti del modello concettuale assenti |
| `stats` | conteggi di nodi, code list, oggetti di primo livello, file, proprietà e import non risolti |
| `initialId` | concetto aperto all'avvio (`Building`) |

## Identificatori dei nodi

```text
xsd:{http://www.opengis.net/citygml/building/3.0}element:Building
xsd:{http://www.opengis.net/gml/3.2}type:SolidPropertyType
uml:Building:RoofTypeValue
```

Un elemento XSD e il suo tipo convenzionale `NomeType` sono uniti nella stessa
scheda soltanto se il collegamento è esplicito e il tipo ha un unico
utilizzatore fra gli elementi globali. Il QName originale del tipo è conservato
in `xmlType`. Gli identificatori `uml:<package>:<nome>` indicano classi del
modello concettuale senza elemento XSD (code list, tipi base, unioni e un tipo
di dato).

## Campi dei nodi

- `name`, `qname`, `namespace`, `module`: nome locale, QName con prefisso,
  namespace e modulo (per CityGML il modulo deriva dal namespace).
- `family`: `CityGML` per i namespace CityGML 3.0 e per le classi del modello
  concettuale, `Supporto` per GML, ISO 19139, xAL, XLink e XML Schema.
- `kind`: per i concetti degli schemi è una categoria derivata dalla gerarchia
  `xs:extension`, mai dai nomi:
  - `feature`: discende da `gml:AbstractFeature`;
  - `object`: discende da `gml:AbstractGML` ma non da `gml:AbstractFeature`;
  - `datatype`: nessuna delle due, oppure tipo semplice o tipo `…PropertyType`;
  - `enumeration`: tipo semplice con valori elencati;
  - `ade`: agganci `ADEOf…`;
  - `external`: riferimento senza definizione locale.

  Per le classi presenti solo nel modello concettuale vale lo stereotipo UML:
  `codelist`, `basictype`, `union`, `datatype`.
- `cityObject`: true per le feature che discendono da `core:AbstractCityObject`.
- `spaceRole`: per gli oggetti di città, `space` se discendono da
  `core:AbstractSpace`, `boundary` se discendono da
  `core:AbstractSpaceBoundary`, altrimenti null.
- `abstract`, `technical` (tipi `…PropertyType` e strutture anonime),
  `external` (riferimento senza definizione locale), `builtin` (tipo
  predefinito di XML Schema).
- `description`: testo di `xs:annotation/xs:documentation`; per le classi solo
  UML, la definizione del documento.
- `uml`: classe corrispondente del modello concettuale, con `name`,
  `stereotype`, `package` e `anchor` (ancora della scheda nel dizionario dati
  del documento). La corrispondenza è per nome: l'elemento XSD ha il nome della
  classe UML; un'enumerazione o un tipo base XSD ha il nome UML più `Type`.
- `topLevel`: true per lo stereotipo «TopLevelFeatureType».
- `umlOnly`: true per le classi del modello concettuale senza elemento XSD.
- `literals`: valori di un'enumerazione con la definizione del documento
  (`value`, `definition`). Le code list non hanno valori nello standard.
- `allowedBoundaries`: per gli spazi, la riga della tabella
  `/req/<modulo>/boundaries` del documento: `items` (classi come scritte, con
  `withSubclasses`), `concrete` (superfici concrete risultanti, espandendo "e
  tutte le sottoclassi" con la gerarchia degli schemi), `ade` (ammesse classi da
  ADE), `none` (nessuna superficie ammessa), `requirement`, `table`, `anchor`.
- `boundaryOf`: per le superfici, gli spazi concreti che le ammettono.
- `properties`: dichiarazioni dirette del tipo. Ogni proprietà ha nome, QName,
  `kind`, `link`, `typeId`/`typeName`, `targets`, `min`, `max`,
  `multiplicity`, `choices`, `nillable`, `default`, `fixed`, `declaredIn`,
  `source`, `line`, `targetEvidence` (come è stata risolta la destinazione) e
  l'estratto `xml`.
  - `kind`: `association` se una destinazione è una `feature` o un `object`;
    `attribute` se le destinazioni sono tipi di dato; `geometry` per le
    proprietà `lod…` e i tipi geometrici GML; `ade` per `adeOf…`;
    `xmlAttribute` per `xs:attribute`.
  - `link`, solo per le associazioni: `aggregation` se il tipo della
    proprietà estende `gml:AbstractFeatureMemberType` o
    `gml:AbstractMemberType`; `reference` se è `gml:ReferenceType`;
    `association` negli altri casi.
  - `umlType`, `umlTypeId`: tipo dell'attributo o destinazione del ruolo nel
    modello concettuale, e il nodo corrispondente.
  - `codeList`: nodo della code list, quando il tipo UML è una «CodeList».
  - `aggregation`: tipo di aggregazione dell'associazione nel modello UML
    (`composite`, `shared`, `none`).
- `parents`, `ancestors`, `children`: gerarchia da `xs:extension`.
  `derivation` indica `xs:extension` o `xs:restriction`; `restrictedBase` è la
  base di una restrizione e non è un arco di ereditarietà.
- `substitution`: testa del `substitutionGroup`, separata dall'ereditarietà.
- `incoming`: proprietà che hanno questo nodo come destinazione esatta o come
  code list, con `kind` e `link` della proprietà.
- `constraints`: faccette, `xs:choice`, liste, unioni, wildcard e gruppi non
  risolti.
- `source`, `line`, `xml`: file, riga ed estratto della dichiarazione.
- `incompleteInheritance`: true se la gerarchia raggiunge un nodo esterno.

L'interfaccia calcola la vista ereditata senza sovrascrivere `properties` e
conserva l'origine di ogni proprietà mostrata su una sottoclasse.

## Modello concettuale (`standard`)

| Campo | Contenuto |
|---|---|
| `document` | titolo, numero, versione, date di approvazione e pubblicazione, percorso locale, URL, data di download, SHA-256 |
| `umlModel` | percorso dello zip, URL, commit, file XMI letto, data di download, SHA-256 |
| `modules` | capitolo di ogni modulo nel documento (numero e ancora) |
| `concepts` | sezioni del capitolo 6 (concetti generali) con numero, titolo, ancora e livello |
| `requirements` | requisiti, classi di requisiti, raccomandazioni e permessi: tipo, titolo, identificatore, modulo, testo, ancora |
| `report` | differenze fra schemi e modello concettuale: concetti XSD senza classe UML, proprietà senza attributo o ruolo UML, relazioni senza associazione nell'XMI, spazi senza tabella dei confini, righe o superfici delle tabelle senza classe XSD |

## File e import

Ogni voce di `files` riporta `path`, `name`, `namespace`, `citygml` (true per
gli schemi sotto `schemas.opengis.net/citygml/`), `url` ufficiale,
`retrievedAt`, `lastModified`, `schemaVersion`, `sha256` e `bytes`. I valori di
provenienza provengono da `sources/manifest.json`.

Ogni voce di `dependencies` riporta `from`, `kind`, `namespace`, l'URL assoluto
dello schema importato, `status` (`local` o `missing`) e `localPath`. Un import
è locale quando il suo URL è un file registrato nel manifest.

Il parser è strettamente locale e disabilita la risoluzione di entità esterne;
lo scaricamento è separato in `scripts/fetch_sources.py`.

## Dizionario delle code list

`codelists/codelists.default.js` espone `window.CITYGML_CODELISTS_DEFAULT`,
`codelists/codelists.js` espone `window.CITYGML_CODELISTS`. Il contenuto è lo
stesso oggetto JSON, serializzato con indentazione di uno spazio sia da
`scripts/build_codelists.py` sia dall'interfaccia:

| Campo | Contenuto |
|---|---|
| `format` | versione di questo formato (1) |
| `kind` | `default` (stato iniziale) o `local` (dizionario locale) |
| `source` | titolo, versione, riferimento (OGC 21-006r2 Annex E), URL di base, host e data di download degli esempi |
| `codeLists` | una voce per ognuna delle 140 code list, con chiave il nome della code list |

Ogni voce di `codeLists`:

| Campo | Contenuto |
|---|---|
| `module`, `url` | modulo CityGML e URL dell'esempio OGC |
| `path`, `retrievedAt`, `sha256` | copia locale dell'esempio in `sources/` (assenti se non pubblicato) |
| `identifier`, `codeSpace`, `description` | identificatore del dizionario con il suo `codeSpace` e descrizione |
| `metadata` | `CodeListMetaData` dell'esempio (`dataType`, `namespace`, `language`, `authority`, `version`) e `metadataNamespace` |
| `values` | valori: `code`, `codeSpace`, `name`, `description` |
| `placeholder` | true se tutti i valori della fonte sono segnaposto `{example-N}` |
| `unavailable`, `availableAtSource` | presenti quando l'esempio non è pubblicato alla fonte |
| `edited` | true per le code list modificate dall'interfaccia |

Il catalogo collega gli attributi alle code list con `codeList`; il nome del
nodo della code list è la chiave in `codeLists`.

## Vista a grafo

Usando gli ID come chiavi dei nodi, gli archi vanno tenuti distinti:

```text
parents             ereditarieta da xs:extension
properties          collegamento tramite proprieta (con ruolo e provenienza)
substitution        sostituzione XML
restrictedBase      derivazione per restrizione
allowedBoundaries   superfici ammesse dal modello concettuale
```

Una composizione non va trasformata in ereditarietà, né una restrizione in
un'estensione.
