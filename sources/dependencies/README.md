# Cache delle dipendenze divisa per profilo

Le cartelle sono **esclusive per formato**:

- `citygml/` contiene XSD tecnici importati da CityGML 3.0: GML, XLink, ISO 19139 ecc.
- `owl/` contiene le ontologie RDF/OWL/TTL esterne e i loro import.

Nessuna delle dipendenze esterne è stata incorporata senza download e controllo:
le cartelle partono vuote salvo i README. Gli **originali** sono in
`../original-voc/` e non vengono mai sovrascritti.

Dalla radice della webapp esegui **uno** dei due comandi:

```bash
python scripts/build_citygml.py       # solo XSD -> CityGML
python scripts/build_citygml_owl.py   # XSD e OWL -> CityGML + OWL
```

Gli script cercano solo le risorse mancanti del profilo selezionato e
**rigenerano il catalogo anche se un'importazione fallisce**. Con `--offline`
non effettuano richieste di rete. Per dettagli consulta `../../README.md`.
