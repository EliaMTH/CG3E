# Esportazione del vocabolario CityGML 3.0

Stato: piano, non implementato.

## Obiettivo

Fissare una versione del vocabolario usato da un progetto (schemi CityGML 3.0
più code list compilate nel dizionario locale) in un pacchetto distribuibile e
verificabile, da usare per produrre e validare file CityGML.

## Prassi di riferimento

- **Schemi**: non si modificano. OGC li distribuisce come archivio
  (`citygml-3_0_0.zip`) con la stessa struttura degli URL, e raccomanda di usarli
  in locale con un catalogo XML OASIS (`schemas.opengis.net/USAGE.txt`).
- **Code list**: un `gml:Dictionary` per code list, con i metadati
  `CodeListMetaData` (`codeListMetaData.xsd`), pubblicato a un URI stabile e
  versionato che i file CityGML richiamano con `codeSpace`. È la forma descritta
  in OGC 21-006r2, Annex E, e usata dagli esempi OGC
  (`CodeList_Examples_3.0.0/<Modulo>.<CodeList>.xml`) e da PLATEAU, che
  pubblica una cartella versionata con un file per code list (per esempio
  `…/iur/codelists/3.2/TrafficArea_function.xml`).
- **Il vocabolario non è un unico GML**: gli schemi sono XSD; solo le code list
  sono GML.

## Contenuto del pacchetto

```text
<nome>-<versione>.zip
  README.md            versione, data, autorità, URI di base, fonti, licenze
  manifest.json        ogni file con percorso, URI, SHA-256
  xml-catalog.xml      URI ufficiali e URI delle code list -> file locali
  schemas.opengis.net/ schemi ufficiali invariati e avvertenze (da sources/)
  www.w3.org/
  codelists/<versione>/
    <Modulo>.<CodeList>.xml   un gml:Dictionary per ogni code list esportata
```

## Parametri

| Parametro | Uso |
|---|---|
| `--base-uri` | URI sotto cui saranno pubblicate le code list, per esempio `https://example.org/citygml/codelists/` |
| `--version` | versione del pacchetto; entra nel percorso (`codelists/<versione>/`) e in `CodeListMetaData/version` |
| `--authority` | `CodeListMetaData/authority` |
| `--language` | `CodeListMetaData/language` |
| `--include` | `with-values` (predefinito: solo code list con valori reali), `all` |

## Trasformazione di `codelists/codelists.js`

Per ogni code list:

| Elemento GML | Valore |
|---|---|
| `gml:Dictionary/@gml:id` | nome della code list |
| `gml:identifier/@codeSpace` | `<base-uri><versione>/<Modulo>.<CodeList>.xml` |
| `gml:identifier` | nome della code list |
| `cmd:dataType` | nome della code list |
| `cmd:namespace` | namespace del modulo CityGML (dal catalogo) |
| `cmd:language`, `cmd:authority`, `cmd:version` | parametri |
| `gml:Definition/@gml:id` | identificatore XML derivato dal codice |
| `gml:Definition/gml:identifier` | codice, con `codeSpace` uguale a quello del dizionario |
| `gml:name`, `gml:description` | nome e descrizione del valore |

Il namespace dei metadati è quello di `codeListMetaData.xsd`
(`http://www.opengis.net/citygml/codelistmetadata/3.0`), anche per le code list
nate da esempi OGC che usano la versione precedente.

## Validazione

Ogni dizionario esportato viene validato con lxml contro `gml.xsd` e
`codeListMetaData.xsd` presenti in `sources/`, risolvendo gli import con
`sources/xml-catalog.xml`, senza rete. L'esportazione si interrompe al primo
dizionario non valido, indicando file e riga.

## Implementazione

- `scripts/export_vocabulary.py`: produce lo zip. È uno script perché la pagina,
  aperta da `file://`, non può leggere gli schemi in `sources/`.
- Interfaccia (facoltativo): pulsante "Esporta code list" che scrive i soli
  dizionari in una cartella scelta dall'utente con `showDirectoryPicker`
  (Chrome, Edge).
- Test: struttura dello zip, validità di ogni dizionario, coerenza fra
  `codeSpace` e URI di base, `xml-catalog.xml` che risolve ogni URI.

## Variante a file unico

Un `gml:Dictionary` può contenere altri dizionari come voci (`dictionary.xsd`).
Un solo file `codelists.xml` con un dizionario per code list è valido; i file
CityGML lo richiamano con `codeSpace="<uri>/codelists.xml#<CodeList>"`. Molti
strumenti si aspettano un dizionario per URI, quindi la variante resta
un'opzione (`--single-file`).

## URI per bozze e test

Gli URI servono solo all'esportazione e ai file CityGML che usano i valori.
Il catalogo non ne ha bisogno: identifica le code list per nome (chiave in
`codelists/codelists.js` e nodo del catalogo), mostra il `codeSpace` e lo
salva così com'è, senza risolverlo né usarlo per collegare valori e classi.
I `codeSpace` del dizionario locale restano quelli degli esempi OGC finché non
vengono modificati; l'esportazione li sostituisce con quelli derivati da
`--base-uri`.

Per pacchetti non ancora pubblicati, `--base-uri` accetta URI che non
richiedono registrazione:

- `https://example.org/…` (dominio riservato alla documentazione, RFC 2606);
- `urn:uuid:<uuid>` (RFC 9562, già RFC 4122), univoco senza registrazione;
- `tag:<dominio-o-email>,<data>:…` (RFC 4151), con un dominio o un indirizzo
  che si controlla alla data indicata.

Con un URI di bozza i file restano sintatticamente validi; il catalogo
`xml-catalog.xml` del pacchetto li risolve in locale. Quando il vocabolario
viene pubblicato si riesporta con l'URI definitivo.

## Decisioni aperte

- Code list con soli segnaposto e code list vuote: escluse per default, oppure
  esportate vuote per completezza.
- Inclusione degli schemi nello zip o solo riferimento agli URI ufficiali.
- Firma o checksum dell'intero pacchetto oltre a quelli per file.
