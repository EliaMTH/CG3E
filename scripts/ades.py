"""ADE (Application Domain Extension) dichiarate in config/sources.json, sezione "ades".

Un solo lettore per scripts/fetch_sources.py, scripts/build_catalog.py e
scripts/build_codelists.py. La sezione è facoltativa: senza, nessuna ADE.

  name, prefix, namespace  nome dell'ADE (il suo modulo nel catalogo), prefisso e namespace
  schema                   URL canonico dello schema, quello che i documenti citano
  local                    facoltativo, {baseUrl, folder}: un URL che inizia con baseUrl si legge
                           da folder (relativa alla radice del progetto o assoluta), senza rete
  codeLists                facoltativo, {baseUrl, files}: file <Modulo>.<Lista>.xml (Annex E);
                           con il nome dell'ADE come modulo è una code list dell'ADE, con un
                           modulo CityGML contiene voci per quella code list di CityGML
  codeListBindings         facoltativo, {"prefisso:Proprietario/prefisso:proprietà": "Lista"}:
                           la code list dell'ADE di una proprietà gml:CodeType
  topLevel                 facoltativo: elementi dell'ADE di primo livello

Lo schema di un'ADE non dice quale code list usa una proprietà gml:CodeType né quali classi
sono di primo livello: per CityGML lo dice OGC 20-010, per un'ADE la configurazione.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

CITYGML_MODULES = {'Appearance', 'Bridge', 'Building', 'CityFurniture', 'CityObjectGroup', 'CodeListMetaData',
                   'Construction', 'Core', 'Dynamizer', 'Generics', 'LandUse', 'PointCloud', 'Relief',
                   'Transportation', 'Tunnel', 'Vegetation', 'Versioning', 'WaterBody'}
# Moduli degli schemi importati: il modulo di un'ADE è il suo nome e non deve confondersi con questi.
SUPPORT_MODULES = {'GML', 'XML Schema', 'XML', 'xAL', 'xlink', 'gco', 'gmd', 'gsr', 'gss', 'gts'}
RESERVED_NAMESPACES = {'http://www.opengis.net/gml/3.2', 'http://www.w3.org/2001/XMLSchema',
                       'http://www.w3.org/1999/xlink', 'http://www.w3.org/XML/1998/namespace'}
NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_-]*$')
PREFIX = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]*$')
QNAME = re.compile(r'^([A-Za-z_][A-Za-z0-9_.-]*):([A-Za-z_][A-Za-z0-9_.-]*)$|^([A-Za-z_][A-Za-z0-9_.-]*)$')
FILE = re.compile(r'^([A-Za-z][A-Za-z0-9_-]*)\.([A-Za-z][A-Za-z0-9_-]*)\.xml$')


class ConfigError(Exception):
    """Sezione ades di config/sources.json non utilizzabile."""


def location(url):
    """Host e percorso di un URL http o https: i due schemi indicano la stessa risorsa."""
    p = urlparse(url)
    return (p.hostname or '') + p.path if p.scheme in ('http', 'https') and p.hostname else None


@dataclass
class Ade:
    name: str
    prefix: str
    namespace: str
    schema: str
    local_base: str | None = None
    local_folder: str | None = None
    local_root: Path | None = None
    code_list_base: str | None = None
    code_list_files: list = field(default_factory=list)
    bindings: dict = field(default_factory=dict)
    top_level: list = field(default_factory=list)

    def local_file(self, url):
        """(file, percorso come in configurazione) di un URL sotto local.baseUrl, altrimenti None."""
        base, target = location(self.local_base or ''), location(url)
        if not base or not target or not target.startswith(base):
            return None
        parts = [unquote(part) for part in target[len(base):].split('/') if part not in ('', '.', '..')]
        if not parts:
            return None
        return self.local_root.joinpath(*parts), '/'.join([self.local_folder.rstrip('/\\'), *parts])

    def code_lists(self):
        """(modulo, lista, URL) di ogni dizionario dichiarato in codeLists."""
        return [(*FILE.match(name).groups(), self.code_list_base + name) for name in self.code_list_files]

    def lists(self):
        """Code list dell'ADE: quelle con un dizionario e quelle citate dai collegamenti."""
        return sorted({name for module, name, _ in self.code_lists() if module == self.name} | set(self.bindings.values()))

    def dictionary(self, name):
        """URL del dizionario di una code list dell'ADE, o None se la lista parte vuota."""
        return next((url for module, list_name, url in self.code_lists() if module == self.name and list_name == name), None)

    def extensions(self):
        """(modulo, lista, URL) dei dizionari con voci per code list di CityGML."""
        return [item for item in self.code_lists() if item[0] != self.name]


def _text(entry, key, where):
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f'{where}: "{key}" mancante o vuoto.')
    return value


def _url(value, where, folder=False):
    p = urlparse(value)
    if p.scheme not in ('http', 'https') or not p.hostname or (folder and not value.endswith('/')):
        raise ConfigError(f'{where}: URL http o https non valido{" (deve terminare con /)" if folder else ""}: {value}.')
    return value


def _under(url, base):
    return location(url).startswith(location(base))


def parse(root, config):
    """Le ADE di config/sources.json (già letto), controllate. Solleva ConfigError."""
    entries = config.get('ades') or []
    if not isinstance(entries, list):
        raise ConfigError('"ades" deve essere un elenco.')
    reserved = {m.lower() for m in CITYGML_MODULES | SUPPORT_MODULES}
    result, names, prefixes, namespaces = [], set(), set(), set()
    for i, entry in enumerate(entries):
        where = f'config/sources.json, ades[{i}]'
        if not isinstance(entry, dict):
            raise ConfigError(f'{where}: ogni ADE è un oggetto.')
        name, prefix = _text(entry, 'name', where), _text(entry, 'prefix', where)
        namespace, schema = _text(entry, 'namespace', where), _url(_text(entry, 'schema', where), where)
        where = f'config/sources.json, ADE {name}'
        if not NAME.match(name):
            raise ConfigError(f'{where}: il nome è il modulo nei nomi dei file <Modulo>.<Lista>.xml: solo lettere, cifre, "_" e "-".')
        if name.lower() in reserved:
            raise ConfigError(f'{where}: il nome coincide con un modulo di CityGML o di uno schema importato.')
        if not PREFIX.match(prefix) or prefix.lower().startswith('xml'):
            raise ConfigError(f'{where}: prefisso non valido: {prefix}.')
        if not urlparse(namespace).scheme or 'opengis.net/citygml/' in namespace or namespace in RESERVED_NAMESPACES \
                or namespace.startswith('urn:oasis:names:tc:ciq:'):
            raise ConfigError(f'{where}: il namespace deve essere un URI proprio dell\'ADE, non di CityGML o di uno schema importato: {namespace}.')
        for value, seen, label in ((name.lower(), names, 'nome'), (prefix, prefixes, 'prefisso'), (namespace, namespaces, 'namespace')):
            if value in seen:
                raise ConfigError(f'{where}: {label} già usato da un\'altra ADE.')
            seen.add(value)
        ade = Ade(name, prefix, namespace, schema)
        local = entry.get('local')
        if local is not None:
            if not isinstance(local, dict):
                raise ConfigError(f'{where}: "local" è un oggetto {{baseUrl, folder}}.')
            ade.local_base = _url(_text(local, 'baseUrl', where + ', local'), where + ', local', folder=True)
            ade.local_folder = _text(local, 'folder', where + ', local')
            ade.local_root = Path(root)/ade.local_folder
            if not _under(schema, ade.local_base):
                raise ConfigError(f'{where}: lo schema non è sotto local.baseUrl ({ade.local_base}).')
        lists = entry.get('codeLists')
        if lists is not None:
            if not isinstance(lists, dict) or not isinstance(lists.get('files', []), list):
                raise ConfigError(f'{where}: "codeLists" è un oggetto {{baseUrl, files}}.')
            ade.code_list_base = _url(_text(lists, 'baseUrl', where + ', codeLists'), where + ', codeLists', folder=True)
            if ade.local_base and not _under(ade.code_list_base, ade.local_base):
                raise ConfigError(f'{where}: codeLists.baseUrl non è sotto local.baseUrl ({ade.local_base}).')
            for file_name in lists.get('files', []):
                match = FILE.match(file_name) if isinstance(file_name, str) else None
                if not match:
                    raise ConfigError(f'{where}: nome di dizionario non nella forma <Modulo>.<Lista>.xml: {file_name}.')
                if match.group(1) != name and match.group(1) not in CITYGML_MODULES:
                    raise ConfigError(f'{where}: {file_name}: il modulo deve essere {name} (code list dell\'ADE) o un modulo di CityGML.')
                if file_name in ade.code_list_files:
                    raise ConfigError(f'{where}: dizionario ripetuto: {file_name}.')
                ade.code_list_files.append(file_name)
        bindings = entry.get('codeListBindings') or {}
        if not isinstance(bindings, dict):
            raise ConfigError(f'{where}: "codeListBindings" è un oggetto.')
        for key, list_name in sorted(bindings.items()):
            owner, _, prop = key.partition('/')
            owner_match, prop_match = QNAME.match(owner), QNAME.match(prop)
            if not owner_match or not prop_match or owner_match.group(1) != prefix:
                raise ConfigError(f'{where}: collegamento non nella forma {prefix}:Proprietario/{prefix}:proprietà: {key}.')
            if not isinstance(list_name, str) or not NAME.match(list_name):
                raise ConfigError(f'{where}: {key}: nome di code list non valido: {list_name}.')
            ade.bindings[key] = list_name
        top = entry.get('topLevel') or []
        if not isinstance(top, list) or any(not isinstance(q, str) or not QNAME.match(q) or QNAME.match(q).group(1) != prefix for q in top):
            raise ConfigError(f'{where}: "topLevel" elenca elementi dell\'ADE con il prefisso {prefix}.')
        ade.top_level = list(top)
        result.append(ade)
    return result


def read(root):
    """Le ADE di <root>/config/sources.json; nessuna se il file non c'è."""
    path = Path(root)/'config/sources.json'
    if not path.exists():
        return []
    return parse(root, json.loads(path.read_text(encoding='utf-8')))
