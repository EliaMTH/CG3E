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
- `kind`: per i concetti degli schemi è una categoria che segue la derivazione
  dei tipi, per `xs:extension` o per `xs:restriction`, mai i nomi:
  - `feature`: deriva da `gml:AbstractFeature`;
  - `object`: deriva da `gml:AbstractGML` ma non da `gml:AbstractFeature`
    (per esempio `gml:Dictionary`, il cui tipo deriva per restrizione da
    `gml:AbstractGMLType`);
  - `datatype`: nessuna delle due, oppure tipo semplice o tipo `…PropertyType`;
  - `enumeration`: tipo semplice con valori elencati;
  - `ade`: ADE hook `ADEOf…`;
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
- `topLevel`: true per lo stereotipo «TopLevelFeatureType», che OGC 20-010
  assegna alle feature che rappresentano i componenti principali del modello
  concettuale e che possono essere scomposte in parti.
- `cityModelMember`: dove la classe può essere membro diretto di un
  `CityModel`, dalla più specifica:
  - `uml`: gli attributi dell'unione `CityModelMember` del dizionario dati il
    cui tipo è la classe o una sua superclasse UML;
  - `gml`: le proprietà di `core:CityModel` il cui elemento ammette quello
    della classe attraverso i gruppi di sostituzione.

  Per `bldg:Building`: `cityObjectMember` e `featureMember`. La frase di OGC
  20-010 sui membri diretti è in `standard.topLevelMembers`.
- `umlOnly`: true per le classi del modello concettuale senza elemento XSD.
- `source`, `line`, `xml`: file, riga ed estratto della dichiarazione.

### Gerarchia degli schemi

- `parents`, `ancestors`, `children`: gerarchia da `xs:extension`.
- `derivation`: `xs:extension` o `xs:restriction`; `restrictedBase` è la base di
  una restrizione. La restrizione dichiara di nuovo gli elementi, quindi la base
  non è fra gli `ancestors`; ne conserva però la categoria (`kind`) e gli
  attributi che non dichiara di nuovo né proibisce (XML Schema 1.0, Parte 1,
  3.4.2).
- `restrictionAttributes`: per una restrizione, gli identificatori delle
  proprietà della base che restano attributi del tipo derivato, per esempio
  `uom`, obbligatorio, di `gml:QuantityExtent`. L'interfaccia li mostra fra le
  proprietà ereditate.
- `substitution`: testa del `substitutionGroup`, separata dall'ereditarietà.
- `incompleteInheritance`: true se la gerarchia raggiunge un nodo esterno.
- `constraints`: faccette, `xs:choice`, liste, unioni, wildcard e gruppi non
  risolti. Liste e unioni sono lette anche nel tipo base anonimo di un
  `xs:restriction` (per esempio `ColorType`) e riportano la `line` della
  dichiarazione. Un `xs:choice` ha `value` (occorrenze dichiarate sulla scelta)
  e `occurs` (occorrenze nel tipo, comprese le ripetizioni dei gruppi che la
  contengono): a ogni occorrenza compare uno solo dei campi, quindi con più
  occorrenze i campi possono comparire tutti, alternati (per esempio i membri
  di `CityModel`, `occurs` `0..*`).

### Proprietà (`properties`)

Dichiarazioni dirette del tipo. Ogni proprietà ha `id`, `name`, `qname`,
`namespace`, `xmlKind` (`xs:element` o `xs:attribute`), `kind`, `link`, `typeId`
e `typeName` (`(tipo anonimo)` quando il tipo è dichiarato dentro l'elemento),
`targets`, `min`, `max`, `multiplicity`, `choices`, `nillable`, `default`,
`fixed`, `declaredIn`, `source`, `line`, `targetEvidence` (come è stata risolta
la destinazione) e l'estratto `xml`.

- `qname`, `namespace`: il nome XML della proprietà. Per un riferimento
  (`xs:element/@ref`, `xs:attribute/@ref`) è il nome della dichiarazione
  globale, per esempio `xlink:href` in `xal:Address`; per una dichiarazione
  locale, il namespace del tipo se è qualificata (`form`, `elementFormDefault`,
  `attributeFormDefault` dello schema), altrimenti nessuno: `namespace` null e
  `qname` senza prefisso, per esempio `codeSpace` di `gml:CodeType` e `srsName`
  di `app:TexCoordGen`.
- `nillable`, `default`, `fixed`: per un riferimento, quelli della dichiarazione
  globale (per esempio `gml:boundedBy` è nillable); un riferimento ad attributo
  può dichiarare `default` o `fixed` propri.

- `kind`: `association` se una destinazione è una `feature` o un `object`;
  `attribute` se le destinazioni sono tipi di dato; `geometry` per le proprietà
  `lod…`, per i tipi geometrici GML e per le proprietà le cui destinazioni
  derivano da `gml:AbstractGeometry` (per esempio `tin` di `TINRelief`, con un
  tipo anonimo); `ade` per `adeOf…`; `xmlAttribute` per
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
  (`composite`, `shared`, `none`), comprese le associazioni che sono association
  class (`TextureAssociation`, `Role`, `CityObjectRelation`).
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

Classe corrispondente del modello concettuale, separata dai campi degli schemi:
definizione, stereotipo, membri con i loro tipi e vincoli come li scrive il
dizionario dati di OGC 20-010; molteplicità e generalizzazioni come le dichiara
il modello UML (XMI), cioè come le disegnano le figure del documento. Dove il
dizionario riporta un valore diverso, il suo valore resta accanto
(`dictionaryMultiplicity`, `dictionaryParents`). La corrispondenza è per nome:
l'elemento XSD ha il nome della classe UML; un'enumerazione o un tipo base XSD
ha il nome UML più `Type`.

- `name`, `stereotype`, `package`, `anchor` (ancora della scheda nel dizionario
  dati), `definition`.
- `parents`, `children`, `ancestors`: generalizzazioni del dizionario (riga
  *Subclass of* delle tabelle Metadata) e del modello UML, fra nodi del
  catalogo.
- `dictionaryParents`: presente quando il dizionario dichiara superclassi
  diverse da quelle del modello UML: le superclassi del dizionario (lista vuota
  per «Subclass of: None»). Le superclassi fuori dal file XMI (classi ISO) non
  sono una divergenza.
- `unresolvedParents`: superclassi che non sono classi del catalogo (classi
  ISO, per esempio `AnyFeature`).
- `properties`: attributi e ruoli dichiarati dalla classe:
  - `id`, `name`, `kind` (`attribute` o `association`), `definition`;
  - `multiplicity`: dal modello UML; per un ruolo è la molteplicità scritta nel
    modello (connettore di Enterprise Architect), dove `*` vale `0..*`;
    l'XMI la esporta con limite inferiore -1, che non è un limite;
  - `dictionaryMultiplicity`: il valore del dizionario dati, presente quando è
    diverso (per esempio `[1..*]` dove il modello scrive `*`);
  - `type` e `typeId` (null se il tipo non è una classe del catalogo);
  - `codeList`: true se il tipo è una code list;
  - `aggregation`: per i ruoli, dall'XMI, comprese le association class;
  - `associationClass`: per un ruolo qualificato da una classe di associazione
    del modello UML, il nodo di quella classe (per esempio `Role` per
    `CityObjectGroup.groupMember`);
  - `xsd`: proprietà XSD con lo stesso nome nella stessa classe, oppure null;
  - `xsdMapping`, quando `xsd` è null in una classe con tipo XSD: la
    corrispondenza ricavata dagli schemi, con `rule` `inherited` (proprietà con
    lo stesso nome in un antenato `xs:extension`) o `unionAlternatives` (il tipo
    del membro è un'unione e la classe ha proprietà con i nomi delle sue
    alternative) e gli identificatori delle `properties`.
- `associationOf`: per una classe di associazione (`Role`, `CityObjectRelation`,
  `TextureAssociation`), gli identificatori dei membri UML dei ruoli che
  qualifica; i suoi attributi descrivono quel legame.
- `constraints`: righe *Constraint* delle tabelle Metadata, con `name`, `text`
  (testo originale, a capo compresi) e `table`.

## Standard (`standard`)

| Campo | Contenuto |
|---|---|
| `document` | OGC 20-010: titolo, numero, versione, date di approvazione e pubblicazione, percorso locale, URL, data di download, SHA-256 |
| `umlModel` | percorso dello zip, URL, commit, file XMI letto, data di download, SHA-256 |
| `modules` | capitolo di ogni modulo nel documento (numero e ancora) |
| `concepts` | sezioni del capitolo 6 (concetti generali) con numero, titolo, ancora e livello |
| `topLevelMembers` | la frase del capitolo 6 sui membri diretti di un city model, con numero, titolo e ancora della sezione (6.2.3) |
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

Le dimensioni `classes`, `members`, `generalizations`, `associationClasses`,
`constraints` e `simpleTypes` riportano:

- `total`: dichiarazioni nella fonte (il dizionario dati per le classi CityGML;
  per le generalizzazioni il dizionario e il modello UML, con il conteggio di
  ciascuno in `declaredBy`; per `associationClasses` i ruoli qualificati da una
  classe di associazione nel modello UML; gli schemi CityGML per liste e
  unioni);
- `represented`: dichiarazioni presenti nel catalogo;
- `excluded`: dichiarazioni fuori dal catalogo, con `declaration` e `reason`
  (classi ISO e ciò che dichiarano);
- `findings`: dichiarazioni mancanti, con `declaration`, `expected` e `outcome`
  `unresolved`;
- `xsd`: i nomi delle dichiarazioni per categoria di rappresentazione negli
  schemi: `sameName` e `withoutXsdType` per le classi; `sameName`, `inherited`,
  `unionAlternatives`, `classWithoutXsdType` e `none` per i membri;
  `xsExtension` e `umlOnly` per le generalizzazioni.

`coverage.divergences` elenca dove il dizionario dati e il modello UML
dichiarano cose diverse: `multiplicities` (`declaration` classe.membro,
`dictionary`, `model`) e `generalizations` (`declaration` classe, superclassi
del dizionario e del modello).

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
| `codeSpacePolicy` | presente dopo `scripts/codespaces.py`: `base`, `version`, `authority`, `language` (se indicata), `lists` (liste trattate), `appliedAt` |

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
| `edited` | true per le code list modificate dall'interfaccia o trattate da `scripts/codespaces.py` |

Il catalogo collega gli attributi alle code list con `codeList`; il nome del
nodo della code list è la chiave in `codeLists`.

Per ogni lista trattata, `scripts/codespaces.py` scrive in `codeSpace` della
lista e dei valori `<base><versione>/<Modulo>.<CodeList>.xml`, in `identifier` e
`metadata.dataType` il nome della code list, in `metadata.namespace` il
namespace del suo modulo, e in `metadata` autorità, versione e lingua indicate.
Le esportazioni del dizionario sono descritte in [EXPORT.md](EXPORT.md).

## Esportazione di una scheda

**Esporta JSON** salva un oggetto con `schemaVersion`, `sourceVersion`, `level`
(`gml` o `uml`), `concept` (il nodo del catalogo), `visibleProperties` (le
proprietà XSD al livello `gml`, i membri UML con la classe che li dichiara al
livello `uml`; ereditate comprese se `includeInherited` è true) e `notes`. Per
una code list aggiunge `localCodeList`: la voce del dizionario locale, con
`file`, `normative` (false), `saved` (false se la pagina ha modifiche non
ancora scritte) e `note`.

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
