# Verifica di questa versione a due profili

- `python scripts/build_citygml_owl.py --offline`: rigenera il profilo con
  i 25 file originari e attiva `full`.
- `python scripts/build_citygml.py --offline`: rigenera il profilo con
  solo i 22 XSD e attiva `citygml`.
- `python -m unittest discover -s tests -v`: verifica isolamento, origini,
  integrità, navigazione e capacità di commutazione.
- `python tests/browser_modes.py`: test visuale e screenshot se Chromium e
  Playwright sono presenti. Non esegue richieste di rete.

Questi test offline non verificano la disponibilità dei siti esterni né la
completezza degli import GML/OWL dopo il download sul computer dell'utente.
