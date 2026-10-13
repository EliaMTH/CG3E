# Catalogo di navigazione, versione 1

`data/catalog.json` e `data/catalog.js` contengono gli stessi dati. Il secondo
espone `window.CITYGML_CATALOG` per permettere il caricamento locale senza fetch.
Il frontend non modifica le sorgenti.

## Oggetti principali

`nodes` e un dizionario per identificatore. Ogni nodo conserva nome, etichetta,
modulo, famiglia di vocabolario, formato, categoria, definizione e provenienza.
Le categorie visive sono aiuti di lettura, non stereotipi UML attestati.

Esempi di identificatore:

```text
xsd:{http://www.opengis.net/citygml/building/3.0}element:Building
xsd:{http://www.opengis.net/gml/3.2}type:SolidPropertyType
owl:http://uish/ontology#BuildingQuality
```

Un elemento XSD e il suo tipo convenzionale `NomeType` vengono normalizzati nella
stessa scheda soltanto se il collegamento e esplicito e il tipo ha un unico
utilizzatore fra gli elementi globali. Il QName originale del tipo e conservato.
Le IRI OWL non vengono mai unite a XSD per una somiglianza di nome.

## Campi dei nodi

- `properties`: dichiarazioni direttamente associate alla risorsa. Ogni
  proprieta ha `declaredIn`, `source`, nome, tipo e destinazioni. Le XSD hanno
  `min`, `max`, `multiplicity`, `choices`, `xmlKind` e sorgente XML. Per OWL,
  `multiplicity` e null: i vincoli ontologici non diventano regole di un form.
- `parents`, `ancestors`, `children`: gerarchia nominale, separata da
  `substitution`, `restrictedBase`, `superProperties` e `bridges`.
- `incoming`: riferimenti alla destinazione esatta, non tutte le possibili
  applicazioni ottenibili mediante inferenze.
- `constraints`: faccette XSD, choice, liste, unioni di tipi, wildcard e gruppi
  non risolti.
- `axioms`: strutture OWL, comprese le espressioni anonime. `ref` punta a un nodo;
  `literal` conserva un valore; `expression` conserva le coppie predicato/valore.
- `source`, `line`, `xml`: origine ed estratto. Per RDF `xml` contiene una
  serializzazione Turtle della risorsa e dei blank node collegati, non il file
  XML originario. Gli originali restano in `sources/`.
- `external`: true quando e noto un riferimento ma manca una definizione locale.
- `incompleteInheritance`: true se la gerarchia nota raggiunge un nodo esterno.
- `builtin`: tipo XML Schema predefinito riconosciuto, senza fingere una copia
  locale della definizione normativa.

L'interfaccia calcola la vista ereditata senza sovrascrivere `properties`.
Conserva l'origine anche quando una proprieta e mostrata su una sottoclasse.
I ponti configurati non sono mai usati come archi di ereditarieta.

## Import e tracciabilita

`files` riporta formato, namespace/IRI, dimensione e SHA-256; `dependencies`
conserva gli import originari, la provenienza, lo stato e gli eventuali percorsi
locali. `warnings` segnala problemi di parsing o cicli, non equivale a un report
di validazione formale.

Il parser delle sorgenti e strettamente locale e disabilita la risoluzione di
entita XML esterne. L'acquisizione di rete e isolata in uno script separato,
con limiti e controlli di identita.

## Aggiungere una vista a grafo

Usare gli ID esistenti come chiavi dei nodi e mantenere distinti:

```text
parents          ereditarieta nominale
properties       collegamento tramite proprieta (con ruolo e provenienza)
substitution     sostituzione XML
restrictedBase   derivazione per restrizione
bridges          ponte editoriale XSD / OWL, non equivalenza
axioms           espressione ontologica, non generico arco is-a
```

Un'espansione deve evitare di trasformare un `unionOf` in piu superclassi o una
composizione in ereditarieta. Lo stesso principio vale per le proprieta
provenienti da domain OWL: non sono una whitelist di relazioni possibili.
