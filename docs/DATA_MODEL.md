# Catalogo di navigazione, versione 1

`data/catalog.json` e `data/catalog.js` contengono gli stessi dati. Il secondo
espone `window.CITYGML_CATALOG` per il caricamento locale senza fetch. Entrambi
sono generati da `scripts/build_catalog.py` a partire dagli XSD in `sources/`;
il frontend non modifica le sorgenti.

## Campi principali

| Campo | Contenuto |
|---|---|
| `schemaVersion` | versione di questo formato (1) |
| `title`, `sourceVersion` | titolo e versione degli schemi (`CityGML 3.0.0 (OGC 21-006r2)`) |
| `nodes` | dizionario dei concetti per identificatore |
| `files` | schemi letti, con provenienza |
| `dependencies` | `xs:import`, `xs:include` e `xs:redefine` di ogni schema |
| `warnings` | problemi di lettura, cicli o file non registrati nel manifest |
| `stats` | conteggi di nodi, file, proprietà e import non risolti |
| `initialId` | concetto aperto all'avvio (`Building`) |

## Identificatori dei nodi

```text
xsd:{http://www.opengis.net/citygml/building/3.0}element:Building
xsd:{http://www.opengis.net/gml/3.2}type:SolidPropertyType
```

Un elemento XSD e il suo tipo convenzionale `NomeType` sono uniti nella stessa
scheda soltanto se il collegamento è esplicito e il tipo ha un unico
utilizzatore fra gli elementi globali. Il QName originale del tipo è conservato
in `xmlType`.

## Campi dei nodi

- `name`, `qname`, `namespace`, `module`: nome locale, QName con prefisso,
  namespace e modulo (per CityGML il modulo deriva dal namespace).
- `family`: `CityGML` per i namespace CityGML 3.0, `Supporto` per GML,
  ISO 19139, xAL, XLink e XML Schema.
- `kind`: categoria derivata dalla gerarchia `xs:extension`, mai dai nomi:
  - `feature`: discende da `gml:AbstractFeature`;
  - `object`: discende da `gml:AbstractGML` ma non da `gml:AbstractFeature`;
  - `datatype`: nessuna delle due, oppure tipo semplice o tipo `…PropertyType`;
  - `enumeration`: tipo semplice con valori elencati;
  - `ade`: agganci `ADEOf…`;
  - `external`: riferimento senza definizione locale.
- `cityObject`: true per le feature che discendono da `core:AbstractCityObject`.
- `spaceRole`: per gli oggetti di città, `space` se discendono da
  `core:AbstractSpace`, `boundary` se discendono da
  `core:AbstractSpaceBoundary`, altrimenti null.
- `abstract`, `technical` (tipi `…PropertyType` e strutture anonime),
  `external` (riferimento senza definizione locale), `builtin` (tipo
  predefinito di XML Schema).
- `description`: testo di `xs:annotation/xs:documentation`.
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
- `parents`, `ancestors`, `children`: gerarchia da `xs:extension`.
  `derivation` indica `xs:extension` o `xs:restriction`; `restrictedBase` è la
  base di una restrizione e non è un arco di ereditarietà.
- `substitution`: testa del `substitutionGroup`, separata dall'ereditarietà.
- `incoming`: proprietà che hanno questo nodo come destinazione esatta, con
  `kind` e `link` della proprietà.
- `constraints`: faccette, `xs:choice`, liste, unioni, wildcard e gruppi non
  risolti.
- `source`, `line`, `xml`: file, riga ed estratto della dichiarazione.
- `incompleteInheritance`: true se la gerarchia raggiunge un nodo esterno.

L'interfaccia calcola la vista ereditata senza sovrascrivere `properties` e
conserva l'origine di ogni proprietà mostrata su una sottoclasse.

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

## Vista a grafo

Usando gli ID come chiavi dei nodi, gli archi vanno tenuti distinti:

```text
parents          ereditarieta da xs:extension
properties       collegamento tramite proprieta (con ruolo e provenienza)
substitution     sostituzione XML
restrictedBase   derivazione per restrizione
```

Una composizione non va trasformata in ereditarietà, né una restrizione in
un'estensione.
