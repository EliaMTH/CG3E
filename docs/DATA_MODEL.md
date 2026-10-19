# Catalogo di navigazione, versione 1

`data/catalog.json` e `data/catalog.js` contengono gli stessi dati. Il secondo
espone `window.CITYGML_CATALOG` per il caricamento locale senza fetch. Entrambi
sono generati da `scripts/build_catalog.py` a partire dalle fonti in `sources/`:

- gli schemi XSD danno la struttura;
- il documento OGC 20-010 e il modello UML (letti da
  `scripts/conceptual_model.py`) danno le informazioni del modello concettuale;
- il documento OGC 21-006r2 (letto da `scripts/encoding_document.py`) dà le
  regole della codifica GML.

Il frontend non modifica le fonti né il catalogo: scrive soltanto il dizionario
delle code list (`codelists/codelists.js`).

## Campi principali

| Campo | Contenuto |
|---|---|
| `schemaVersion` | versione di questo formato (1) |
| `title`, `sourceVersion` | titolo e versione degli schemi (`CityGML 3.0.0 (OGC 21-006r2)`) |
| `nodes` | dizionario dei concetti per identificatore |
| `files` | schemi letti, con provenienza |
| `dependencies` | `xs:import`, `xs:include` e `xs:redefine` di ogni schema |
| `standard` | modello concettuale e codifica: documenti, modello UML, capitoli, requisiti, regole della codifica, rapporto di confronto, copertura; null se mancano le fonti del modello concettuale |
| `warnings` | problemi di lettura, cicli, file non registrati nel manifest, documenti assenti, tabelle di regole non riconosciute |
| `stats` | conteggi di nodi, code list, oggetti di primo livello, file, proprietà e import non risolti |
| `initialId` | concetto aperto all'avvio (`Building`) |

## Identificatori

```text
xsd:{http://www.opengis.net/citygml/building/3.0}element:Building
xsd:{http://www.opengis.net/gml/3.2}type:SolidPropertyType
uml:Building:RoofTypeValue
```

Un elemento XSD e il suo tipo convenzionale `NomeType` sono uniti nella stessa
scheda soltanto se il collegamento è esplicito e il tipo ha un unico
utilizzatore fra gli elementi globali; il QName originale del tipo è in
`xmlType`. Gli identificatori `uml:<package>:<nome>` indicano classi del
modello concettuale senza elemento XSD (code list, tipi base, unioni e un tipo
di dato).

Una proprietà XSD ha identificatore
`<identificatore del nodo>/property:<nome>:<riga>`, un membro UML (attributo o
ruolo) `<identificatore della classe>/uml:<nome>`.

## Campi dei nodi

### Identità e categoria

- `id`, `name`, `label`, `qname`, `namespace`, `module`: identificatore, nome
  locale, etichetta, QName con prefisso, namespace e modulo (per CityGML il
  modulo deriva dal namespace).
- `family`: `CityGML` per i namespace CityGML 3.0 e per le classi del modello
  concettuale, `Supporto` per GML, ISO 19139, xAL, XLink e XML Schema;
  `support` è true per questi ultimi.
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
- `topLevel`: true per lo stereotipo «TopLevelFeatureType».
- `umlOnly`: true per le classi del modello concettuale senza elemento XSD.
- `source`, `line`, `xml`: file, riga ed estratto della dichiarazione.

### Gerarchia degli schemi

- `parents`, `ancestors`, `children`: gerarchia da `xs:extension`.
- `derivation`: `xs:extension` o `xs:restriction`; `restrictedBase` è la base di
  una restrizione e non è un arco di ereditarietà.
- `substitution`: testa del `substitutionGroup`, separata dall'ereditarietà.
- `incompleteInheritance`: true se la gerarchia raggiunge un nodo esterno.
- `constraints`: faccette, `xs:choice`, liste, unioni, wildcard e gruppi non
  risolti. Liste e unioni sono lette anche nel tipo base anonimo di un
  `xs:restriction` (per esempio `ColorType`) e riportano la `line` della
  dichiarazione.

### Proprietà (`properties`)

Dichiarazioni dirette del tipo. Ogni proprietà ha `id`, `name`, `qname`,
`xmlKind` (`xs:element` o `xs:attribute`), `kind`, `link`, `typeId` e
`typeName` (`(tipo anonimo)` quando il tipo è dichiarato dentro l'elemento),
`targets`, `min`, `max`, `multiplicity`, `choices`, `nillable`, `default`,
`fixed`, `declaredIn`, `source`, `line`, `targetEvidence` (come è stata risolta
la destinazione) e l'estratto `xml`.

- `kind`: `association` se una destinazione è una `feature` o un `object`;
  `attribute` se le destinazioni sono tipi di dato; `geometry` per le proprietà
  `lod…` e i tipi geometrici GML; `ade` per `adeOf…`; `xmlAttribute` per
  `xs:attribute`.
- `link`, solo per le associazioni: `aggregation` se il tipo della proprietà
  estende `gml:AbstractFeatureMemberType` o `gml:AbstractMemberType`;
  `reference` se è `gml:ReferenceType`; `association` negli altri casi.
- `encoding`, solo per le associazioni il cui elemento contiene l'oggetto:
  `allowsInline` (il tipo della proprietà ammette l'oggetto come elemento
  figlio) e `allowsReference` (il tipo ha l'attributo `xlink:href`), seguendo
  le basi `xs:extension` e i gruppi; un `xs:restriction` non eredita i figli
  della base. Null quando parte della definizione non è disponibile.
- `description`: documentazione dello schema; se manca, la definizione del
  membro UML con lo stesso nome, con `descriptionSource: "uml"`.
- `umlType`, `umlTypeId`: tipo dell'attributo o destinazione del ruolo nel
  modello concettuale, e il nodo corrispondente.
- `umlMember`: per una proprietà che è un'alternativa del tipo unione di un
  membro della classe (per esempio `CityModel.cityObjectMember` per
  `cityModelMember`), l'identificatore di quel membro; `umlType` è allora il
  tipo dell'alternativa.
- `codeList`: nodo della code list, quando il tipo UML è una «CodeList».
- `aggregation`: tipo di aggregazione dell'associazione nel modello UML
  (`composite`, `shared`, `none`).
- `rules`: regole di OGC 21-006r2 che nominano la proprietà, con `document`,
  `id`, `part` e `anchor`.

L'interfaccia calcola la vista ereditata senza sovrascrivere `properties` e
conserva l'origine di ogni proprietà mostrata su una sottoclasse.

### Collegamenti

- `incoming`: proprietà che hanno questo nodo come destinazione esatta o come
  code list, con `kind` e `link` della proprietà; con `kind: "umlMember"`, i
  membri UML senza proprietà XSD con lo stesso nome che hanno questo nodo come
  tipo.
- `allowedBoundaries`: per gli spazi, la riga della tabella
  `/req/<modulo>/boundaries` del documento OGC 20-010: `items` (classi come
  scritte, con `withSubclasses`), `concrete` (superfici concrete risultanti,
  espandendo "e tutte le sottoclassi" con la gerarchia degli schemi), `ade`
  (ammesse classi da ADE), `none` (nessuna superficie ammessa), `requirement`,
  `table`, `anchor`.
- `boundaryOf`: per le superfici, gli spazi concreti che le ammettono.
- `literals`: valori di un'enumerazione con la definizione del documento
  (`value`, `definition`). Le code list non hanno valori nello standard.

### Modello concettuale (`uml`)

Classe corrispondente del modello concettuale, come la scrive il dizionario
dati di OGC 20-010, separata dai campi degli schemi. La corrispondenza è per
nome: l'elemento XSD ha il nome della classe UML; un'enumerazione o un tipo base
XSD ha il nome UML più `Type`.

- `name`, `stereotype`, `package`, `anchor` (ancora della scheda nel dizionario
  dati), `definition`.
- `parents`, `children`, `ancestors`: generalizzazioni UML (riga *Subclass of*
  delle tabelle Metadata), fra nodi del catalogo.
- `unresolvedParents`: superclassi che non sono classi del catalogo (classi
  ISO, per esempio `AnyFeature`).
- `properties`: attributi e ruoli dichiarati dalla classe:
  - `id`, `name`, `kind` (`attribute` o `association`), `multiplicity`,
    `definition`;
  - `type` e `typeId` (null se il tipo non è una classe del catalogo);
  - `codeList`: true se il tipo è una code list;
  - `aggregation`: per i ruoli, dall'XMI;
  - `xsd`: proprietà XSD con lo stesso nome nella stessa classe, oppure null;
  - `xsdMapping`, quando `xsd` è null in una classe con tipo XSD: la
    corrispondenza ricavata dagli schemi, con `rule` `inherited` (proprietà con
    lo stesso nome in un antenato `xs:extension`) o `unionAlternatives` (il tipo
    del membro è un'unione e la classe ha proprietà con i nomi delle sue
    alternative) e gli identificatori delle `properties`.
- `constraints`: righe *Constraint* delle tabelle Metadata, con `name`, `text`
  (testo originale, a capo compresi) e `table`.

## Standard (`standard`)

| Campo | Contenuto |
|---|---|
| `document` | OGC 20-010: titolo, numero, versione, date di approvazione e pubblicazione, percorso locale, URL, data di download, SHA-256 |
| `umlModel` | percorso dello zip, URL, commit, file XMI letto, data di download, SHA-256 |
| `modules` | capitolo di ogni modulo nel documento (numero e ancora) |
| `concepts` | sezioni del capitolo 6 (concetti generali) con numero, titolo, ancora e livello |
| `requirements` | requisiti, classi di requisiti, raccomandazioni e permessi di OGC 20-010: `kind`, `title`, `id`, `module`, `text`, `anchor`, `document` (`20-010`) |
| `encoding` | documento OGC 21-006r2 e sue regole; null se il documento manca |
| `report` | differenze fra schemi e modello concettuale |
| `coverage` | confronto fra le fonti e il catalogo |

### Regole della codifica (`encoding`)

`encoding.document` riporta titolo, numero, versione, date, percorso, URL, data
di download e SHA-256; `encoding.unrecognized` le tabelle di regole con una
struttura non riconosciuta.

Le regole di `encoding.requirements` hanno `kind` (`Requirement`,
`Recommendation`, `Permission`, `Requirements class`), `title` (con il numero
stampato), `id` (identificatore breve, oppure l'URI per le classi di
requisiti), `module` (`global` per le regole generali), `text` (enunciato),
`parts` (`label` A, B, … e `text`), `notes`, `anchor` nel documento, `document`
(`21-006r2`), `properties` (proprietà nominate dal testo, con `id` e `part`) ed
eventuali `unresolvedMentions`; le classi di requisiti hanno anche `targetType`
e `dependencies`. Gli identificatori brevi coincidono in parte con quelli di
OGC 20-010: una regola si identifica con `document` e `id`.

### Rapporto di confronto (`report`)

| Chiave | Contenuto |
|---|---|
| `xsdWithoutUml` | concetti XSD senza classe UML |
| `propertiesWithoutUml` | proprietà XSD senza attributo o ruolo UML |
| `propertiesMappedToUnion` | proprietà XSD che codificano le alternative di un'unione UML |
| `associationsWithoutXmi` | relazioni XSD senza associazione nell'XMI |
| `spacesWithoutBoundaryTable` | spazi concreti senza tabella dei confini |
| `boundaryRowsWithoutXsd`, `boundaryClassesWithoutXsd` | righe o superfici delle tabelle dei confini senza classe XSD, se presenti |

### Copertura (`coverage`)

Le dimensioni `classes`, `members`, `generalizations`, `constraints` e
`simpleTypes` riportano:

- `total`: dichiarazioni nella fonte (il dizionario dati per le classi CityGML,
  gli schemi CityGML per liste e unioni);
- `represented`: dichiarazioni presenti nel catalogo;
- `excluded`: dichiarazioni fuori dal catalogo, con `declaration` e `reason`
  (classi ISO e ciò che dichiarano);
- `findings`: dichiarazioni mancanti, con `declaration`, `expected` e `outcome`
  `unresolved`;
- `xsd`: i nomi delle dichiarazioni per categoria di rappresentazione negli
  schemi: `sameName` e `withoutXsdType` per le classi; `sameName`, `inherited`,
  `unionAlternatives`, `classWithoutXsdType` e `none` per i membri;
  `xsExtension` e `umlOnly` per le generalizzazioni.

`coverage.documents` elenca i documenti normativi: `document`, `role`,
`acquired`, `rules` (conteggi per tipo) e, per OGC 21-006r2,
`unrecognizedTables`, `linkedProperties` e `unresolvedMentions`.

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

## Esportazione di una scheda

**Esporta JSON** salva un oggetto con `schemaVersion`, `sourceVersion`, `level`
(`gml` o `uml`), `concept` (il nodo del catalogo), `visibleProperties` (le
proprietà XSD al livello `gml`, i membri UML con la classe che li dichiara al
livello `uml`; ereditate comprese se `includeInherited` è true) e `notes`.

## Vista a grafo

Usando gli identificatori come chiavi dei nodi, gli archi vanno tenuti distinti:

```text
parents             ereditarietà da xs:extension
uml.parents         generalizzazione del modello concettuale
properties          collegamento tramite proprietà (con ruolo e provenienza)
substitution        sostituzione XML
restrictedBase      derivazione per restrizione
allowedBoundaries   superfici ammesse dal modello concettuale
```

Una composizione non va trasformata in ereditarietà, né una restrizione in
un'estensione.
