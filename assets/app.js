/* CityGML Explorer - no framework, no CDN, no runtime network requests. */
'use strict';
(() => {
  const $ = s => document.querySelector(s);
  const data = window.CITYGML_CATALOG;
  if (!data || !data.nodes) {
    $('#content').innerHTML = '<div class="empty-state">Catalogo non trovato. Mantieni data/catalog.js accanto alla pagina, oppure esegui python scripts/build_catalog.py.</div>';
    return;
  }
  const nodes = data.nodes;
  const versionElement = document.getElementById('catalog-version');
  if (versionElement) versionElement.textContent = data.sourceVersion;

  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeUrl = u => /^(https?:\/\/|sources\/|README\.md$)/.test(u || '') ? u : '#';
  let level = 'gml';
  const href = (id, tab='overview', prop='', lv=level) => '#'+new URLSearchParams({node:id, tab, ...(prop?{prop}:{}), ...(lv==='uml'?{level:'uml'}:{})}).toString();
  const umlLevel = n => level==='uml' && n.uml && !n.umlOnly;
  const fmt = n => new Intl.NumberFormat('it-IT').format(n);
  const standard = data.standard;
  const kinds = {feature:'Feature', object:'Oggetto (non feature)', datatype:'Tipo di dato', enumeration:'Enumerazione', codelist:'Code list', basictype:'Tipo base', union:'Unione', ade:'ADE hook', external:'Riferimento esterno'};
  const kindNotes = {
    feature:'Deriva da gml:AbstractFeature: oggetto con identità propria.',
    object:'Deriva da gml:AbstractGML, per estensione o per restrizione, ma non da gml:AbstractFeature: ha identità (gml:id) ma non è una feature.',
    datatype:'Non deriva da gml:AbstractGML: struttura di valori senza identità propria.',
    enumeration:'Tipo semplice con valori ammessi elencati nello schema.',
    codelist:'Vocabolario aperto definito nel modello concettuale (OGC 20-010); i valori sono definiti fuori dallo standard.',
    basictype:'Tipo base del modello concettuale (OGC 20-010).',
    union:'Unione del modello concettuale (OGC 20-010): il valore è uno dei tipi alternativi.',
    ade:'Permette a un’estensione di dominio (ADE) di aggiungere proprietà alla classe (OGC 20-010).',
    external:'Riferimento senza definizione negli schemi locali.'};
  const roles = {space:['Spazio','Discende da core:AbstractSpace: entità di estensione volumetrica nel mondo reale (OGC 20-010).'],
    boundary:['Superficie di confine','Discende da core:AbstractSpaceBoundary: entità di estensione areale che delimita uno spazio (OGC 20-010).']};
  const displayName = n => n.family==='CityGML' ? n.name : (n.qname || n.name);
  const groups = {attribute:['Attributi e valori','teal'],association:['Relazioni','purple'],geometry:['Geometrie e LOD','blue'],ade:['ADE hook','amber'],xmlAttribute:['Attributi XML','teal']};
  const tabs = {overview:'Panoramica',properties:'Proprietà',connections:'Connessioni',standard:'Standard',source:'Sorgente'};
  const docHref = anchor => standard ? standard.document.path+(anchor?'#'+anchor:'') : '#';
  const docLink = (anchor, label) => standard ? `<a href="${esc(docHref(anchor))}" target="_blank" rel="noopener">${esc(label)}</a>` : esc(label);
  const encoding = standard?.encoding || null;
  const encodingLink = (anchor, label) => encoding ? `<a href="${esc(encoding.document.path+(anchor?'#'+anchor:''))}" target="_blank" rel="noopener">${esc(label)}</a>` : esc(label);
  /* Local code list dictionary (codelists/codelists.js). Its values are not part of the standard. */
  const clone = o => o ? JSON.parse(JSON.stringify(o)) : null;
  const defaultCodeLists = window.CITYGML_CODELISTS_DEFAULT || null;
  let codeLists = clone(window.CITYGML_CODELISTS || defaultCodeLists);
  let savedCodeLists = clone(codeLists);
  let codeListsDirty = false, saveInFlight = false;
  const PLACEHOLDER = /^\{example-\d+\}$/;
  const codeListStates = {
    values:['con valori','teal','Valori presenti nel dizionario locale.'],
    placeholder:['solo segnaposto','amber','La fonte OGC fornisce solo segnaposto generati automaticamente ({example-1}, …).'],
    empty:['vuota','amber','Nessun valore nel dizionario locale.'],
    unavailable:['non disponibile','amber','Il file d’esempio OGC non è pubblicato alla fonte: la code list parte vuota.'],
    missing:['assente','amber','Dizionario locale non caricato.']};
  function codeListOf(n) { return n && n.kind==='codelist' ? codeLists?.codeLists?.[n.name] || null : null; }
  function codeListState(l) {
    if (!l) return 'missing';
    if (!l.values.length) return l.unavailable ? 'unavailable' : 'empty';
    return l.values.every(v=>PLACEHOLDER.test(v.name)) ? 'placeholder' : 'values';
  }
  function stateBadge(l) { const s=codeListStates[codeListState(l)]; return `<span class="badge ${s[1]}" title="${esc(s[2])}">${s[0]}</span>`; }
  function codeListSummary() {
    const all=Object.values(codeLists?.codeLists||{}), count=state=>all.filter(l=>codeListState(l)===state).length;
    return {total:all.length, values:count('values'), placeholder:count('placeholder'), empty:count('empty')+count('unavailable'), edited:all.filter(l=>l.edited).length};
  }
  function updateCodeListIndicator() {
    const s=codeListSummary(), button=$('#codelists-btn');
    $('#codelist-count').textContent=`${s.values}/${s.total}${codeListsDirty?' •':''}`;
    button.classList.toggle('dirty',codeListsDirty);
    button.title=codeListsDirty?'Modifiche al dizionario locale non salvate':'Code list con valori nel dizionario locale';
  }
  function serializeCodeLists(obj) {
    return '/* Local code list dictionary, edited by the interface (Save) and restored by Reset. Values are not part of the CityGML standard. */\nwindow.CITYGML_CODELISTS = '+JSON.stringify(obj,null,1)+';\n';
  }
  const HANDLE_DB='citygml-explorer', HANDLE_STORE='handles';
  function openHandleDb() {
    return new Promise((resolve,reject)=>{const r=indexedDB.open(HANDLE_DB,1);r.onupgradeneeded=()=>r.result.createObjectStore(HANDLE_STORE);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
  }
  async function storedHandle() {
    try { const db=await openHandleDb(); return await new Promise(res=>{const q=db.transaction(HANDLE_STORE).objectStore(HANDLE_STORE).get('codelists');q.onsuccess=()=>res(q.result||null);q.onerror=()=>res(null);}); }
    catch (_) { return null; }
  }
  async function storeHandle(handle) {
    try { const db=await openHandleDb(); db.transaction(HANDLE_STORE,'readwrite').objectStore(HANDLE_STORE).put(handle,'codelists'); } catch (_) {}
  }
  function downloadText(text, name) {
    const url=URL.createObjectURL(new Blob([text],{type:'text/javascript'}));
    const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  async function writeCodeLists(obj) {
    const text=serializeCodeLists(obj);
    if (!window.showSaveFilePicker) { downloadText(text,'codelists.js'); return 'download'; }
    let handle=await storedHandle();
    if (handle) {
      let permission=await handle.queryPermission({mode:'readwrite'});
      if (permission!=='granted') permission=await handle.requestPermission({mode:'readwrite'});
      if (permission!=='granted') handle=null;
    }
    if (!handle) {
      handle=await window.showSaveFilePicker({suggestedName:'codelists.js',types:[{description:'Dizionario delle code list',accept:{'text/javascript':['.js']}}]});
      await storeHandle(handle);
    }
    const writable=await handle.createWritable();await writable.write(text);await writable.close();
    return handle.name;
  }
  function saveButtons() {
    const locked=saveInFlight?' disabled':'';
    return `<button class="text-button" data-cl-action="revert">Annulla modifiche</button><button class="text-button" data-cl-action="reset"${locked}>Reset allo stato iniziale</button><button class="text-button primary" data-cl-action="save"${locked}>Salva</button>`;
  }
  function lockSaveButtons() {
    document.querySelectorAll('[data-cl-action="save"],[data-cl-action="reset"]').forEach(b=>{b.disabled=saveInFlight;});
  }
  async function saveCodeLists() {
    if (saveInFlight) return;
    // The snapshot is what gets written: edits made while writing stay marked as unsaved.
    const snapshot=clone(codeLists);
    saveInFlight=true;lockSaveButtons();
    try {
      const where=await writeCodeLists(snapshot);
      savedCodeLists=snapshot;codeListsDirty=JSON.stringify(codeLists)!==JSON.stringify(snapshot);updateCodeListIndicator();
      if (!codeListsDirty) renderPage();
      showToast(where==='download'?'File scaricato: sostituisci codelists/codelists.js':`Salvato in ${where}`+(codeListsDirty?': le modifiche fatte durante il salvataggio non sono salvate':''));
    } catch (err) { if (err?.name!=='AbortError') showToast('Salvataggio non riuscito: '+(err?.message||err)); }
    finally { saveInFlight=false;lockSaveButtons(); }
  }
  function revertCodeLists() { codeLists=clone(savedCodeLists);codeListsDirty=false;updateCodeListIndicator();renderPage(); }
  async function resetCodeLists() {
    if (saveInFlight) return;
    if (!defaultCodeLists) { showToast('Stato iniziale non disponibile: manca codelists/codelists.default.js'); return; }
    if (!confirm('Ripristinare tutte le code list allo stato iniziale (esempi OGC)? Le modifiche in codelists/codelists.js andranno perse.')) return;
    // The page shows the new state at once: if the write is cancelled or fails, it stays to be saved.
    codeLists={...clone(defaultCodeLists),kind:'local'};codeListsDirty=true;updateCodeListIndicator();renderPage();
    await saveCodeLists();
  }
  function markCodeListEdited(l) { l.edited=true;codeListsDirty=true;updateCodeListIndicator(); }
  /* Values that follow the codeSpace of their list, decided once, the first time the page shows the list: those without
     a codeSpace or with the one of the list. A value with its own codeSpace keeps it while the codeSpace of the list is
     edited, also when the two coincide for a moment. The file does not record the choice: when the page is opened
     again, a value saved with the codeSpace of its list follows it. */
  const followers = new WeakMap();
  function followersOf(l) {
    if (!followers.has(l)) followers.set(l, new Set(l.values.filter(v=>!v.codeSpace||v.codeSpace===l.codeSpace)));
    return followers.get(l);
  }

  /* Display options: saved in localStorage and applied by index.html before the first paint. */
  const FONT_STEPS=[0.85,0.9,1,1.1,1.25,1.4];
  const darkQuery=window.matchMedia?window.matchMedia('(prefers-color-scheme: dark)'):null;
  function storedOption(key, fallback) { try { return localStorage.getItem(key) ?? fallback; } catch (_) { return fallback; } }
  function saveOption(key, value) { try { localStorage.setItem(key, value); } catch (_) {} }
  let themeChoice=storedOption('cg-theme','light'), fontScale=parseFloat(storedOption('cg-font-scale','1'))||1;
  function applyTheme() {
    document.documentElement.dataset.theme=themeChoice==='system'?(darkQuery?.matches?'dark':'light'):themeChoice;
    document.querySelectorAll('[data-theme-choice]').forEach(b=>b.setAttribute('aria-checked',String(b.dataset.themeChoice===themeChoice)));
  }
  function applyFontScale() {
    document.documentElement.style.setProperty('--font-scale',fontScale);
    $('#font-scale-value').textContent=Math.round(fontScale*100)+'%';
    document.querySelectorAll('[data-font-step]').forEach(b=>{b.disabled=b.dataset.fontStep==='-1'?fontScale<=FONT_STEPS[0]:fontScale>=FONT_STEPS[FONT_STEPS.length-1];});
  }
  function stepFont(step) {
    const nearest=FONT_STEPS.reduce((best,v,i)=>Math.abs(v-fontScale)<Math.abs(FONT_STEPS[best]-fontScale)?i:best,0);
    fontScale=FONT_STEPS[Math.min(FONT_STEPS.length-1,Math.max(0,nearest+step))];
    saveOption('cg-font-scale',fontScale);applyFontScale();
  }
  function toggleOptions(open) { $('#options-panel').hidden=!open;$('#options-btn').setAttribute('aria-expanded',String(open)); }

  /* Code list overview page (#view=codelists). */
  let view=null, codeListFilter='all';
  function codeListOverview() {
    if (!codeLists) return empty('Dizionario locale non caricato: mancano codelists/codelists.js e codelists/codelists.default.js.');
    const s=codeListSummary(), lists=allNodes.filter(n=>n.kind==='codelist');
    const shown=lists.filter(n=>{const state=codeListState(codeListOf(n));return codeListFilter==='all'||(codeListFilter==='values'?state==='values':state!=='values');});
    const modules=[...new Set(shown.map(n=>n.module))].sort();
    const usedBy=n=>[...new Set(n.incoming.map(i=>(nodes[i.source]?.name||'')+'.'+i.property))].join(', ');
    const rows=m=>shown.filter(n=>n.module===m).map(n=>{const l=codeListOf(n);return `<tr><td>${ref(n.id)}</td><td>${stateBadge(l)}${l?.edited?' <span class="badge">modificata</span>':''}</td><td>${l?.values.length??0}</td><td class="tiny">${esc(usedBy(n))}</td></tr>`;}).join('');
    const filters=[['all','Tutte',s.total],['values','Con valori',s.values],['missing','Da compilare',s.total-s.values]];
    return notice('Lo standard definisce queste code list ma non i loro valori, che affida a dizionari esterni. I valori qui sotto vengono dal <strong>dizionario locale</strong> (<code>codelists/codelists.js</code>): parte dagli esempi OGC e si modifica dalla pagina di ogni code list.','info')
      +`<div class="stats-grid"><div class="stat-card"><span class="stat-label">Con valori</span><strong>${s.values}</strong></div><div class="stat-card"><span class="stat-label">Solo segnaposto</span><strong>${s.placeholder}</strong></div><div class="stat-card"><span class="stat-label">Vuote o non disponibili</span><strong>${s.empty}</strong></div><div class="stat-card"><span class="stat-label">Modificate</span><strong>${s.edited}</strong></div></div>`
      +`<div class="segment cl-filters">${filters.map(([k,label,count])=>`<button data-cl-filter="${k}" class="${codeListFilter===k?'active':''}">${label} <span class="count">${count}</span></button>`).join('')}</div>`
      +modules.map(m=>section(esc(m),`<div class="prop-table"><table><thead><tr><th>Code list</th><th>Stato</th><th>Valori</th><th>Usata da</th></tr></thead><tbody>${rows(m)}</tbody></table></div>`,shown.filter(n=>n.module===m).length)).join('')
      +`<div class="cl-actions"><span class="spacer"></span>${saveButtons()}</div>`;
  }
  function renderCodeListOverview() {
    document.title='Code list · CityGML Explorer';
    $('#breadcrumb').innerHTML='<b>Code list</b><span>/</span>dizionario locale';
    $('#content').innerHTML=`<article class="page"><div class="eyebrow"><span>CityGML</span><span class="slash">/</span><span>Code list</span></div><div class="hero"><div><h1>Code list</h1><div class="hero-subtitle"><code>codelists/codelists.js</code></div></div></div>${codeListOverview()}</article>`;
  }
  const onlineLink = (anchor, label) => standard ? `<a href="${esc(standard.document.url+(anchor?'#'+anchor:''))}" target="_blank" rel="noopener">${esc(label)}</a>` : '';
  let current = data.initialId, activeTab = 'overview', inherited = true, propertyQuery = '', propertyKind = 'all';
  let previous = null, searchTimer = null, toastTimer = null;
  try { inherited = localStorage.getItem('cg-inherited') !== 'false'; } catch (_) {}
  const scroll = new Map();
  const byName = (a,b) => a.name.localeCompare(b.name, 'en', {sensitivity:'base'});
  const allNodes = Object.values(nodes).sort(byName);
  /* XSD properties by UML type: how a class without its own XSD type appears in the encoding. */
  const umlTypeUses = {}, propertyIndex = {};
  for (const n of allNodes) for (const p of n.properties) {
    propertyIndex[p.id] = p;
    if (p.umlTypeId) (umlTypeUses[p.umlTypeId] ??= []).push({source:n.id, prop:p});
  }

  /* Property names for the search. XSD declarations and the UML members without an XSD property of the same name in their class. */
  const umlIncoming = {};
  for (const n of allNodes) for (const m of n.uml?.properties||[]) if (m.typeId) (umlIncoming[m.typeId] ??= []).push({source:n.id, member:m});
  const propertyEntries = [];
  for (const n of allNodes) {
    for (const p of n.properties) propertyEntries.push({name:p.name, lower:p.name.toLowerCase(), node:n, id:p.id, uml:false});
    for (const m of n.uml?.properties||[]) if (!m.xsd) propertyEntries.push({name:m.name, lower:m.name.toLowerCase(), node:n, id:m.id, uml:true});
  }
  function ref(id, label, className='') {
    const n = nodes[id];
    if (!n) return '<span class="muted">'+esc(label || id || 'Non specificato')+'</span>';
    return `<a class="${className} ${n.external?'external':''}" href="${esc(href(id))}" title="${esc(n.qname || n.name)}">${esc(label || displayName(n))}</a>${n.external?'<span class="external-tag" title="Definizione non disponibile localmente">est.</span>':''}`;
  }
  function icon(n) {
    const css = n.kind==='ade' ? 'ade' : ['datatype','enumeration','codelist','basictype','union'].includes(n.kind)?'datatype':'';
    const glyph = n.external?'?':n.kind==='ade'?'+':n.kind==='codelist'?'L':['datatype','enumeration','basictype','union'].includes(n.kind)?'T':n.kind==='object'?'O':'F';
    return `<span class="type-icon ${css}" aria-hidden="true" title="${esc(kinds[n.kind]||n.kind)}">${glyph}</span>`;
  }
  /* Relation from the UML model (XMI), or from the member form when the XMI has no association; encoding form from the schema. */
  const relations = {composite:['composizione','blue','Nel modello UML (XMI) è una composizione: la parte appartiene a un solo intero e non esiste senza di esso.'],
    aggregation:['aggregazione','blue','Nel modello UML (XMI) è un’aggregazione: l’oggetto collegato è parte di questo.','Forma member nello schema (estende gml:AbstractFeatureMemberType o gml:AbstractMemberType): per GML questo oggetto è una collezione che contiene quello collegato, senza implicarne il possesso; il catalogo la legge come aggregazione.'],
    association:['associazione','','Nel modello UML (XMI) è un’associazione, senza relazione di parte.','Nello schema la proprietà non ha la forma member.']};
  const encodings = {reference:['solo riferimento','amber','Nello schema la proprietà non ammette l’oggetto come elemento figlio: si indica con xlink:href.'],
    inline:['solo incluso','teal','Nello schema la proprietà non ha l’attributo xlink:href: l’oggetto si include come elemento figlio.'],
    unknown:['forma non determinata','amber','Parte della definizione del tipo non è disponibile localmente.']};
  const relationOf = a => a==='composite'?'composite':a==='shared'?'aggregation':'association';
  function encodingForm(e) {
    if (!e) return null;
    if (e.allowsInline===null || e.allowsReference===null) return 'unknown';
    return !e.allowsInline&&e.allowsReference?'reference':e.allowsInline&&!e.allowsReference?'inline':null;
  }
  const relationKind = p => p.aggregation?relationOf(p.aggregation):p.link==='aggregation'?'aggregation':p.link?'association':null;
  function linkBadge(p) {
    const r=relations[relationKind(p)], form=encodings[encodingForm(p.encoding)];
    return (r?`<span class="badge ${r[1]}" title="${esc(r[p.aggregation?2:3]||r[2])}">${r[0]}</span>`:'')+(form?`<span class="badge ${form[1]}" title="${esc(form[2])}">${form[0]}</span>`:'');
  }
  /* The same relation as text, for the cards of the links towards a concept. */
  const relationText = p => [relations[relationKind(p)]?.[0], encodings[encodingForm(p.encoding)]?.[0]].filter(Boolean).join(' · ');
  /* Value of the data dictionary of OGC 20-010 where it differs from the UML model (XMI). */
  const dictionaryBadge = (value, model) => `<span class="badge amber" title="${esc(`Il dizionario dati di OGC 20-010 riporta ${value}; il modello UML (XMI), disegnato nelle figure del documento, riporta ${model}. Il livello UML mostra il valore del modello.`)}">dizionario: ${esc(value)}</span>`;
  /* XML text and attribute values in the examples written for the reader. */
  const xmlEscape = s => String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  const describe = p => esc(p.description||'Nessuna descrizione nella sorgente.')+(p.descriptionSource==='uml'?' <span class="muted" title="Lo schema non documenta la proprietà: il testo è la definizione del dizionario dati di OGC 20-010.">(OGC 20-010)</span>':'');
  function categoryMatch(n, category) {
    if (!category) return true;
    if (category==='topLevel') return n.topLevel;
    if (category==='codelistFilled') return n.kind==='codelist' && codeListState(codeListOf(n))==='values';
    if (category==='codelistMissing') return n.kind==='codelist' && codeListState(codeListOf(n))!=='values';
    if (category==='cityObject') return n.cityObject;
    if (category==='space' || category==='boundary') return n.spaceRole===category;
    return n.kind===category;
  }
  function properties(n, include=inherited) {
    const seen = new Set(), result = [];
    for (const id of [n.id,...(include ? n.ancestors || [] : [])]) {
      // A restriction keeps the attributes of its base type that it does not declare again.
      const kept = include ? (nodes[id]?.restrictionAttributes || []).map(k=>propertyIndex[k]).filter(Boolean) : [];
      for (const p of [...(nodes[id]?.properties || []), ...kept]) {
        const key = p.qname+'|'+p.xmlKind;
        if (seen.has(key)) continue;
        seen.add(key); result.push(p);
      }
    }
    return result;
  }
  function sourceLink(path, label) {
    return `<a href="${esc(safeUrl(path))}" target="_blank" rel="noopener">${esc(label || path)}</a>`;
  }
  function notice(text, kind='') {
    return `<div class="notice ${kind}"><span class="notice-icon" aria-hidden="true">${kind==='info'?'i':'!'}</span><span>${text}</span></div>`;
  }
  function section(title, body, count='', sub='', num='') {
    return `<section class="section"><div class="section-heading">${num?`<span class="section-num">${esc(num)}</span>`:''}<h2>${title}</h2>${count!==''?`<span class="count">${count}</span>`:''}${sub?`<span class="sub">${sub}</span>`:''}</div>${body}</section>`;
  }
  function empty(text) { return `<div class="empty-state">${text}</div>`; }
  function showToast(text) {
    $('#toast').textContent = text; $('#toast').classList.add('visible');
    clearTimeout(toastTimer); toastTimer = setTimeout(()=>$('#toast').classList.remove('visible'), 2300);
  }
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); showToast('Copiato negli appunti'); }
    catch (_) {
      const a = document.createElement('textarea'); a.value=text; a.style.position='fixed';a.style.opacity='0';document.body.append(a);a.select();
      const ok = document.execCommand('copy');a.remove();showToast(ok?'Copiato negli appunti':'Copia non disponibile: seleziona il testo nella scheda.');
    }
  }
  function showModal(title, body) {
    $('#modal-title').textContent = title; $('#modal-body').innerHTML = body;
    if (!$('#modal').open) $('#modal').showModal();
  }

  function allowed(n, family) {
    return family==='all' || n.family===family;
  }
  function moduleOptions() {
    const selected=$('#module').value, family=$('#family').value;
    const mods=[...new Set(allNodes.filter(n=>allowed(n,family)).map(n=>n.module))].sort();
    $('#module').innerHTML='<option value="">Tutti i moduli</option>'+mods.map(m=>`<option value="${esc(m)}">${esc(m)}</option>`).join('');
    if (mods.includes(selected)) $('#module').value=selected;
  }
  function listItem(n, hint='') {
    return `<a href="${esc(href(n.id))}" class="concept-item ${current===n.id?'active':''}" ${current===n.id?'aria-current="page"':''} title="${esc(n.qname || n.name)}">${icon(n)}<span class="item-name">${esc(displayName(n))}${hint?`<small class="item-hint">valore: ${esc(hint)}</small>`:''}</span>${n.abstract?'<span class="abstract-mark" title="Astratta">A</span>':''}</a>`;
  }
  function propertyItem(e) {
    const n=e.node, where=`in ${displayName(n)}${n.abstract?' (astratta)':''}${e.uml?' · membro UML':''}`;
    return `<a href="${esc(e.uml?href(n.id,'standard'):href(n.id,'properties',e.id))}" class="concept-item property-item" title="${esc(e.name+' '+where)}"><span class="type-icon" aria-hidden="true">P</span><span class="item-name">${esc(e.name)}<small class="item-hint">${esc(where)}</small></span></a>`;
  }
  function valueMatch(n, q) {
    const v=codeListOf(n)?.values.find(v=>[v.code,v.name,v.description].some(s=>(s||'').toLowerCase().includes(q)));
    return v ? (v.name||v.code) : '';
  }
  function renderList() {
    const q=$('#search').value.trim().toLowerCase(), family=$('#family').value, mod=$('#module').value, category=$('#category').value;
    let matches=allNodes.filter(n=>allowed(n,family) && (!mod||n.module===mod) && categoryMatch(n,category)
      && ($('#technical').checked || (!n.technical && n.kind!=='ade'))
      && ($('#include-external').checked || !n.external)
      && (!$('#only-concrete').checked || (!n.abstract && !n.external && n.kind!=='ade'))
      && (!q || [n.name,n.label,n.qname].some(s=>(s||'').toLowerCase().includes(q)) || (n.kind==='codelist' && valueMatch(n,q))));
    // Properties follow the schema group and the technical filter of their declaring class; module, category and
    // "only concrete" select classes, so they do not hide a property declared in an abstract class.
    const props=q?propertyEntries.filter(e=>e.lower.includes(q) && allowed(e.node,family)
      && ($('#technical').checked || (!e.node.technical && e.node.kind!=='ade' && !e.node.anonymous))):[];
    $('#results-count').textContent=fmt(matches.length)+(props.length?` + ${fmt(props.length)} proprietà`:'');
    const box=$('#concept-list'), pos=box.scrollTop;
    if (!matches.length && !props.length) {
      box.innerHTML='<div class="list-empty">Nessun risultato.<br><br>Prova a cambiare gruppo di schemi o ad attivare i tipi tecnici nei filtri.</div>';
      return;
    }
    if (q) {
      const score=n=>n.name.toLowerCase()===q?0:n.name.toLowerCase().startsWith(q)?1:2;
      matches.sort((a,b)=>score(a)-score(b)||byName(a,b));
      const item=n=>listItem(n,n.kind==='codelist'&&![n.name,n.label,n.qname].some(s=>(s||'').toLowerCase().includes(q))?valueMatch(n,q):'');
      const rank=e=>e.lower===q?0:e.lower.startsWith(q)?1:2;
      props.sort((a,b)=>rank(a)-rank(b)||a.name.localeCompare(b.name)||a.uml-b.uml||byName(a.node,b.node));
      const exact=props.filter(e=>e.lower===q), partial=props.filter(e=>e.lower!==q), shown=partial.slice(0,60);
      const note='<small>nella classe che le dichiara</small>';
      box.innerHTML=matches.filter(n=>score(n)===0).map(item).join('')
        +(exact.length?`<div class="module-label"><span>Proprietà con questo nome</span>${note}</div>${exact.map(propertyItem).join('')}`:'')
        +matches.filter(n=>score(n)>0).map(item).join('')
        +(partial.length?`<div class="module-label"><span>Altre proprietà</span>${note}</div>${shown.map(propertyItem).join('')}${partial.length>shown.length?`<div class="list-empty">e altre ${fmt(partial.length-shown.length)}: precisa la ricerca.</div>`:''}`:'');
    } else {
      const order=['Building','Core','Construction','Transportation'];
      const mods=[...new Set(matches.map(n=>n.module))].sort((a,b)=>{
        const ai=order.indexOf(a),bi=order.indexOf(b);return(ai<0?99:ai)-(bi<0?99:bi)||a.localeCompare(b);
      });
      box.innerHTML=mods.map(m=>{
        const group=matches.filter(n=>n.module===m);
        return `<div class="module-group"><div class="module-label"><span>${esc(m)}</span><small>${group.length}</small></div>${group.map(n=>listItem(n)).join('')}</div>`;
      }).join('');
    }
    box.scrollTop=pos;
  }

  function chain(n) {
    if (!n.parents.length && !n.children.length && !n.restrictedBase) return '';
    const ids=[...(n.ancestors||[])].reverse();
    const body='<div class="chain">'+ids.map(a=>ref(a)+'<span class="arrow">›</span>').join('')+`<span class="current">${esc(displayName(n))}</span></div>`;
    return `<div class="inheritance-box"><div class="caption">EREDITARIETÀ DEI TIPI · XS:EXTENSION</div>${body}${n.restrictedBase?`<div class="tiny">Derivazione per restrizione: ${ref(n.restrictedBase)}. Gli elementi sono quelli dichiarati qui; gli attributi della base non dichiarati di nuovo sono ereditati.</div>`:''}</div>`;
  }
  /* Conceptual model (OGC 20-010): generalizations, members and constraints, kept apart from the XSD fields. */
  const umlParentsExtra = n => (n.uml?.parents||[]).filter(id=>!(n.ancestors||[]).includes(id));
  const umlChildrenExtra = n => (n.uml?.children||[]).filter(id=>!n.children.includes(id));
  function umlMembers(n, include=inherited) {
    const seen=new Set(), result=[];
    for (const id of [n.id,...(include?n.uml?.ancestors||[]:[])])
      for (const m of nodes[id]?.uml?.properties||[]) if(!seen.has(m.name)){seen.add(m.name);result.push({...m,owner:id});}
    return result;
  }
  /* Generalization of the UML model (XMI) that the data dictionary does not state. */
  function parentsNote(n) {
    if(!n.uml?.dictionaryParents) return '';
    return `<div class="tiny">Generalizzazione del modello UML (XMI), disegnata nelle figure del documento; il dizionario dati riporta «Subclass of: ${esc(n.uml.dictionaryParents.join(', ')||'None')}».</div>`;
  }
  function umlChain(n) {
    const ids=[...(n.uml?.ancestors||[])].reverse();
    const unresolved=(n.uml?.unresolvedParents||[]).map(s=>`<span class="muted" title="Classe non rappresentata nel catalogo">${esc(s)}</span><span class="arrow">›</span>`).join('');
    return `<div class="inheritance-box"><div class="caption">GENERALIZZAZIONE NEL MODELLO CONCETTUALE · OGC 20-010</div><div class="chain">${unresolved}${ids.map(a=>ref(a)+'<span class="arrow">›</span>').join('')}<span class="current">${esc(n.uml.name)}</span></div>${parentsNote(n)}</div>`;
  }
  function xsdCell(m) {
    if(m.xsd) return 'proprietà con lo stesso nome';
    const props=(m.xsdMapping?.properties||[]).map(id=>propertyIndex[id]).filter(Boolean);
    if(m.xsdMapping?.rule==='inherited') return `proprietà ereditata da ${props.map(p=>ref(p.declaredIn)).join(', ')}`;
    if(m.xsdMapping?.rule==='unionAlternatives') return `alternative dell’unione come proprietà: ${props.map(p=>`<code>${esc(p.name)}</code>`).join(', ')}`;
    return '<span class="muted">nessuna corrispondenza ricavabile dagli schemi</span>';
  }
  function umlMemberTable(members, n) {
    const xsd=!n.umlOnly;
    return `<div class="prop-table"><table class="${xsd?'uml-members':''}"><thead><tr><th>Membro</th><th>Tipo</th><th>Molteplicità</th><th>Definito in</th>${xsd?'<th>Negli schemi XSD</th>':''}</tr></thead><tbody>${members.map(m=>{
      const direct=m.owner===n.id, r=m.aggregation?relations[relationOf(m.aggregation)]:null;
      const type=m.typeId?ref(m.typeId,m.type,'prop-type'):`<code>${esc(m.type)}</code>`;
      return `<tr><td><span class="prop-name">${esc(m.name)}</span><div class="prop-description">${esc(m.definition||'Nessuna definizione nel documento.')}</div>${r?`<span class="badge ${r[1]}" title="${esc(r[2])}">${r[0]}</span>`:''}${m.associationClass?`<div class="tiny">qualificato dalla classe di associazione ${ref(m.associationClass)}</div>`:''}</td><td>${type}${m.codeList?' <span class="tiny muted">code list</span>':''}</td><td><span class="multiplicity">${esc(m.multiplicity||'')}</span>${m.dictionaryMultiplicity?dictionaryBadge(m.dictionaryMultiplicity,m.multiplicity):''}</td><td>${ref(m.owner,undefined,'prop-origin '+(direct?'direct':''))}<div class="prop-origin-label">${direct?'diretto':'ereditato'}</div></td>${xsd?`<td class="tiny">${xsdCell(m)}</td>`:''}</tr>`;
    }).join('')}</tbody></table></div>`;
  }
  /* Association class of the UML model: the roles it qualifies, with the classes that own them. */
  function associationSection(n) {
    const roles=(n.uml?.associationOf||[]).map(id=>id.split('/uml:'));
    if(!roles.length) return '';
    return section('Classe di associazione',`<p>Nel modello UML questa classe qualifica ${roles.map(([owner,member])=>`il ruolo <code>${esc(member)}</code> di ${ref(owner)}`).join(', ')}: i suoi attributi descrivono il legame.</p><div class="connection-grid">${roles.map(([owner,member])=>card(owner,'ruolo '+member+' qualificato')).join('')}</div>`,roles.length,'AssociationClass dell’XMI');
  }
  function umlMemberSection(n) {
    const members=umlMembers(n);
    if(!members.length) return '';
    const union=n.uml.stereotype==='Union'?notice('Unione: un valore è uno solo dei membri elencati. La molteplicità di ciascuno vale quando è quello scelto, non significa che siano richiesti tutti.','info'):'';
    return section('Membri nel modello concettuale',union+umlMemberTable(members,n),members.length,'Attributi e ruoli di OGC 20-010, molteplicità del modello UML (XMI)');
  }
  function umlConstraints(n) {
    const cs=[n.id,...(inherited?n.uml?.ancestors||[]:[])].flatMap(id=>(nodes[id]?.uml?.constraints||[]).map(c=>({...c,owner:id})));
    if(!cs.length) return '';
    return section('Vincoli del modello concettuale',cs.map(c=>`<div class="constraint"><div class="constraint-label">${esc(c.name||'vincolo')} · ${ref(c.owner)} · ${nodes[c.owner].uml.anchor?docLink(nodes[c.owner].uml.anchor,c.table):esc(c.table)}</div><pre class="source-block"><code>${esc(c.text)}</code></pre></div>`).join(''),cs.length,'Metadata del dizionario dati di OGC 20-010, testo originale');
  }
  function umlHierarchySections(n, all) {
    const parents=all?n.uml?.parents||[]:umlParentsExtra(n), children=all?n.uml?.children||[]:umlChildrenExtra(n);
    const note=all?'':'Non espresse con xs:extension negli schemi';
    return (parents.length?section('Superclasse nel modello concettuale',cardGrid(parents,'generalizzazione UML'),parents.length,note):'')
      +(children.length?section('Sottoclassi nel modello concettuale',cardGrid(children,'specializzazione UML'),children.length,note):'');
  }
  function propTable(props, n) {
    if (!props.length) return empty('Nessuna proprietà in questa sezione con i filtri correnti.');
    return `<div class="prop-table"><table><thead><tr><th>Proprietà</th><th>Tipo / destinazione</th><th>Occorrenze</th><th>Definita in</th></tr></thead><tbody>${props.map(p=>{
      const direct=p.declaredIn===n.id;
      const targets=(p.targets.length?p.targets.map(t=>ref(t,undefined,'prop-type')).join(''):'<span class="muted tiny">Non specificato</span>')
        +(p.codeList?`<div class="tiny muted" title="Code list del modello concettuale (OGC 20-010)">code list ${ref(p.codeList,undefined,'prop-type')} ${codeListCount(p.codeList)}</div>`:'');
      return `<tr><td><button class="prop-name-button" data-property="${esc(p.id)}">${esc(p.name)}</button><div class="prop-description">${describe(p)}</div>${linkBadge(p)}${p.choices?.length?'<span class="badge amber" title="Campo in un gruppo xs:choice: le alternative non sono indipendenti">alternativa XML</span>':''}</td><td>${targets}</td><td><span class="multiplicity">${esc(p.multiplicity)}</span></td><td>${ref(p.declaredIn,undefined,'prop-origin '+(direct?'direct':''))}<div class="prop-origin-label">${direct?'diretta':'ereditata'}</div></td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function propSections(props, n, all=false) {
    return Object.entries(groups).filter(([k])=>all||props.some(p=>p.kind===k)).map(([k,[title]])=>{
      const ps=props.filter(p=>p.kind===k);if(!ps.length)return'';
      const sub=k==='geometry'?'Proprietà spaziali, non CRS separati per LOD':k==='ade'?'Meccanismi di estensione, non sottoclassi dell’oggetto':'Nome XML, tipo, molteplicità e provenienza';
      return section(title,propTable(ps,n),ps.length,sub);
    }).join('');
  }
  function card(id, role) {
    const n=nodes[id];if(!n)return'';
    return `<a class="connection-card" href="${esc(href(id))}">${icon(n).replace('type-icon','conn-icon')}<span class="conn-content"><strong>${esc(displayName(n))}</strong><small>${esc(role)}${n.external?' · definizione esterna':''}</small></span><span class="conn-arrow" aria-hidden="true">↗</span></a>`;
  }
  function constraints(n) {
    const cs=[n.id,...(inherited?n.ancestors||[]:[])].flatMap(id=>(nodes[id]?.constraints||[]).map(c=>({...c,owner:id})));
    if(!cs.length)return'';
    return section('Vincoli e struttura XML',cs.map(c=>`<div class="constraint"><div class="constraint-label">${esc(c.kind)} · ${ref(c.owner)}</div>${c.value!==undefined?`<code>${esc(c.value)}</code>`:''}${c.occurs&&c.occurs!==c.value?` <span class="tiny">occorrenze nel tipo, con i gruppi che la contengono: <code>${esc(c.occurs)}</code></span>`:''}${(c.targets||[]).map(id=>ref(id)).join(', ')}${c.description?`<div class="tiny muted">${esc(c.description)}</div>`:''}</div>`).join(''),cs.length);
  }
  function cardGrid(ids, role) {
    return `<div class="connection-grid">${ids.map(id=>card(id,role)).join('')}</div>`;
  }
  function boundarySections(n) {
    let body='';
    const ab=n.allowedBoundaries;
    if(ab){
      const source=`OGC 20-010 · ${docLink(ab.anchor, ab.table)} · <code>${esc(ab.requirement)}</code>`;
      const written=ab.items.map(i=>ref(i.id)+(i.withSubclasses?' e sottoclassi':'')).join(', ');
      const content=ab.none?empty('Il documento non ammette superfici di confine per questa classe.')
        :`${cardGrid(ab.concrete,'superficie ammessa')}<p class="tiny muted">Come scritto nella tabella: ${written}${ab.ade?'; inoltre possibili classi da ADE':''}.</p>`;
      body+=section('Superfici di confine ammesse',content,ab.none?'':ab.concrete.length,source);
    }
    if(n.boundaryOf?.length) body+=section('Può delimitare',cardGrid(n.boundaryOf,'spazio che la ammette come confine'),n.boundaryOf.length,'Spazi concreti che la ammettono nelle tabelle di OGC 20-010');
    return body;
  }
  function literals(n) {
    if(!n.literals?.length) return '';
    return section('Valori ammessi',`<div class="prop-table"><table><thead><tr><th>Valore</th><th>Definizione</th></tr></thead><tbody>${n.literals.map(l=>`<tr><td><code>${esc(l.value)}</code></td><td>${esc(l.definition)}</td></tr>`).join('')}</tbody></table></div>`,n.literals.length,'Definizioni da OGC 20-010');
  }
  function codeListCount(id) {
    const l=codeListOf(nodes[id]), state=codeListState(l);
    return state==='values'?`<span class="muted">· ${l.values.length} valori</span>`:`<span class="muted">· ${codeListStates[state][0]}</span>`;
  }
  function codeListValuesSection(n) {
    const props=properties(n).filter(p=>p.codeList);
    if (!props.length) return '';
    const rows=props.map(p=>{
      const l=codeListOf(nodes[p.codeList]), state=codeListState(l), values=l?.values||[];
      const shown=state==='values'
        ?values.slice(0,12).map(v=>`<span class="value-chip" title="${esc(v.code+(v.description?' — '+v.description:''))}">${esc(v.name||v.code)}</span>`).join('')+(values.length>12?` <a href="${esc(href(p.codeList))}">+${values.length-12}</a>`:'')
        :`<span class="muted tiny">${esc(codeListStates[state][2])}</span>`;
      return `<tr><td><span class="prop-name">${esc(p.name)}</span></td><td>${ref(p.codeList)} ${stateBadge(l)}</td><td>${shown}</td></tr>`;
    }).join('');
    return section('Valori delle code list',`<div class="prop-table"><table class="cl-values"><thead><tr><th>Attributo</th><th>Code list</th><th>Valori del dizionario locale</th></tr></thead><tbody>${rows}</tbody></table></div>`,props.length,'Non normativi · da codelists/codelists.js');
  }
  const stateBadges = l => stateBadge(l)+(l.edited?' <span class="badge">modificata</span>':'');
  function usageContent(n, l) {
    return !l.values.length?empty('Aggiungi almeno un valore per vedere l’esempio.')
      :usageExample(n,l)||empty('Nessuna proprietà degli schemi XSD ha questa code list come tipo: manca l’elemento da cui ricavare l’esempio.'+(n.uml?.parents?.length?' Specializza '+n.uml.parents.map(id=>ref(id)).join(', ')+'.':''));
  }
  function usageExample(n, l) {
    const use=n.incoming.find(i=>i.kind!=='umlMember');
    if (!use) return '';
    const prop=nodes[use.source]?.properties.find(p=>p.id===use.id), tag=prop?.qname||use.property, v=l.values[0];
    return `<pre class="source-block"><code>${esc(`<${tag} codeSpace="${xmlEscape(l.codeSpace||'')}">${xmlEscape(v.code)}</${tag}>`)}</code></pre><p class="tiny muted"><code>codeSpace</code> identifica il dizionario; il contenuto è il codice di una voce, qui “${esc(v.name)}”.</p>`;
  }
  function codeListEditor(l) {
    const follow=followersOf(l), own=v=>v.codeSpace&&!follow.has(v)?`<div class="tiny muted mono" title="codeSpace proprio della voce, usato per il suo codice nei file CityGML e negli export">${esc(v.codeSpace)}</div>`:'';
    const rows=l.values.map((v,i)=>`<tr><td><input class="cl-input mono" data-cl-field="code" data-cl-index="${i}" value="${esc(v.code)}" aria-label="Codice">${own(v)}</td><td><input class="cl-input" data-cl-field="name" data-cl-index="${i}" value="${esc(v.name)}" aria-label="Nome"></td><td><input class="cl-input" data-cl-field="description" data-cl-index="${i}" value="${esc(v.description)}" aria-label="Descrizione"></td><td><button class="icon-button" data-cl-action="delete" data-cl-index="${i}" title="Elimina valore" aria-label="Elimina valore">×</button></td></tr>`).join('');
    return `<label class="cl-toolbar">codeSpace del dizionario <input class="cl-input mono" data-cl-field="codeSpace" value="${esc(l.codeSpace||'')}"></label><div class="prop-table"><table class="cl-table"><thead><tr><th>Codice</th><th>Nome</th><th>Descrizione</th><th></th></tr></thead><tbody>${rows||'<tr><td colspan="4" class="muted tiny">Nessun valore.</td></tr>'}</tbody></table></div><div class="cl-actions"><button class="text-button" data-cl-action="add">+ Aggiungi valore</button><span class="spacer"></span>${saveButtons()}</div><p class="tiny muted">Il <code>codeSpace</code> del dizionario vale anche per le voci che non ne hanno uno proprio; una voce con un <code>codeSpace</code> proprio lo mostra sotto il codice e lo conserva quando cambia quello del dizionario, anche se per un momento i due coincidono. Le voci che seguono il dizionario sono quelle che, all’apertura della lista, non hanno un <code>codeSpace</code> o hanno lo stesso del dizionario.</p><p class="tiny muted">Salva scrive <code>codelists/codelists.js</code>: la prima volta scegli quel file nella cartella del progetto (Chrome, Edge). Negli altri browser il file viene scaricato e va sostituito a mano. Reset riporta tutte le code list agli esempi OGC di <code>codelists/codelists.default.js</code>.</p>`;
  }
  function codeListView(n) {
    let body=notice('Code list del modello concettuale (OGC 20-010). I valori non fanno parte dello standard: vanno definiti esternamente, e l’attributo <code>codeSpace</code>, facoltativo, identifica la code list da cui un valore è preso (OGC 21-006r2, Annex E). Qui compaiono i valori del <strong>dizionario locale</strong> (<code>codelists/codelists.js</code>), modificabili.','info');
    const l=codeListOf(n);
    if (!l) body+=notice('Dizionario locale non caricato: mancano codelists/codelists.js e codelists/codelists.default.js.');
    else {
      const state=codeListState(l), meta=l.metadata||{};
      if (state==='placeholder') body+=notice('La fonte OGC fornisce per questa code list solo segnaposto generati automaticamente: sostituiscili con i valori del tuo progetto.');
      if (state==='unavailable') body+=notice('Il file d’esempio OGC per questa code list non è pubblicato alla fonte: il dizionario parte vuoto.');
      body+=section('Origine dei valori',`<dl class="metadata-grid"><dt>Stato</dt><dd id="cl-state">${stateBadges(l)}</dd><dt>Esempio OGC</dt><dd>${l.path?sourceLink(l.path,l.path.split('/').pop())+' · '+sourceLink(l.url,'online'):esc(l.url)}</dd><dt>Autorità</dt><dd>${esc(meta.authority||'—')}</dd><dt>Versione · lingua</dt><dd>${esc(meta.version||'—')} · ${esc(meta.language||'—')}</dd><dt>Riferimento</dt><dd>${esc(codeLists.source.title)} ${esc(codeLists.source.version)} · ${esc(codeLists.source.reference)}</dd></dl>`);
      body+=section('Valori',codeListEditor(l),l.values.length,'Dizionario locale, non normativo');
      body+=section('Come si usa in un file CityGML',`<div id="cl-usage">${usageContent(n,l)}</div>`);
    }
    body+=literals(n);
    body+=section('Usata da',n.incoming.length?`<div class="connection-grid">${n.incoming.map(i=>card(i.source,(i.kind==='umlMember'?'membro UML ':'attributo ')+i.property)).join('')}</div>`:empty('Nessuna proprietà degli schemi XSD ha questa code list come tipo.'),n.incoming.length,esc(n.incoming.map(i=>i.property).filter((v,i,a)=>a.indexOf(v)===i).join(', ')));
    body+=umlHierarchySections(n,true);
    return body;
  }
  function overview(n) {
    if(n.kind==='codelist') return codeListView(n);
    if(umlLevel(n)) return overviewUml(n);
    const props=properties(n);
    const geom=props.filter(p=>p.kind==='geometry'), attrs=props.filter(p=>['attribute','xmlAttribute'].includes(p.kind)), rels=props.filter(p=>p.kind==='association'), ade=props.filter(p=>p.kind==='ade');
    let body=levelNote(n)+chain(n)+(n.uml&&(n.umlOnly?n.uml.parents.length:umlParentsExtra(n).length)?umlChain(n):'');
    if(n.external) body+=notice('Questa risorsa è referenziata dagli schemi, ma la sua definizione non è disponibile in sources/. I collegamenti noti sono mostrati; attributi e antenati mancanti non vengono inventati. <button class="text-button" data-action="sources">Vedi sorgenti</button>');
    else if(n.incompleteInheritance)body+=notice('La gerarchia raggiunge una definizione esterna non inclusa. Le proprietà qui elencate sono quelle ricavabili dagli schemi locali; l’ereditarietà non è completa. <a href="#" data-action="sources">Dettagli delle sorgenti</a>');
    if(props.length)body+=`<div class="stats-grid">${[[attrs,'Attributi e valori','teal','properties','all'],[rels,'Relazioni','purple','connections','all'],[geom,'Geometrie / LOD','blue','properties','geometry'],[ade,'ADE hook','amber','properties','ade']].map(([ps,label,color,tab,kind])=>`<button class="stat-card" data-tab="${tab}" data-kind="${kind}"><span class="stat-label"><i class="line-dot ${color}"></i>${label}</span><strong>${ps.length}</strong><small>${ps.filter(p=>p.declaredIn===n.id).length} dirette · ${ps.filter(p=>p.declaredIn!==n.id).length} ereditate</small></button>`).join('')}</div>`;
    if(attrs.length)body+=section('Attributi e valori',propTable(attrs,n),attrs.length,'Clicca sul nome per aprire i dettagli','01');
    if(rels.length)body+=section('Relazioni',propTable(rels,n),rels.length,'Destinazioni navigabili','02');
    body+=codeListValuesSection(n)+boundarySections(n)+literals(n);
    if(n.umlOnly)body+=umlMemberSection(n);
    if(geom.length)body+=section('Geometrie e livelli di dettaglio',propTable(geom,n),geom.length,'LOD0 — LOD3','03');
    if(ade.length)body+=`<details class="section-collapse"><summary>ADE hook <span class="count">${ade.length}</span></summary><div>${propTable(ade,n)}</div></details>`;
    body+=constraints(n)+umlConstraints(n);
    if(n.children.length)body+=section('Sottoclassi / tipi derivati',`<div class="connection-grid">${n.children.map(id=>card(id,'xs:extension')).join('')}</div>`,n.children.length);
    if(n.uml){const extra=umlChildrenExtra(n);if(extra.length)body+=section('Sottoclassi nel modello concettuale',cardGrid(extra,'specializzazione UML'),extra.length,n.umlOnly?'':'Non espresse con xs:extension negli schemi');}
    if(!props.length&&!n.constraints.length&&!n.literals?.length&&!umlMembers(n).length)body+=empty('Nessuna proprietà diretta o ereditata disponibile nel catalogo per questa risorsa. Consulta Connessioni e Sorgente.');
    return body;
  }
  function levelNote(n) {
    if(!n.uml||n.umlOnly) return '';
    return `<p class="tiny muted level-note">${umlLevel(n)?'Livello: modello concettuale (OGC 20-010). Tipi e definizioni del dizionario dati; molteplicità e generalizzazioni del modello UML (XMI), come nelle figure del documento.':'Livello: codifica GML (schemi XSD). Elementi, tipi XML, cardinalità ed ereditarietà dei tipi.'}</p>`;
  }
  function encodedBy(n) {
    return section('Negli schemi XSD',`<p>${ref(n.id,n.qname||n.name)} · ${esc(n.xmlType||'')} <a href="${esc(href(n.id,activeTab,'','gml'))}">vedi la codifica GML</a></p><p class="tiny muted">Per ogni membro, la colonna «Negli schemi XSD» indica la proprietà corrispondente: stesso nome, proprietà ereditata o alternative di un’unione; senza prove la corrispondenza non è indicata.</p>`);
  }
  function overviewUml(n) {
    let body=levelNote(n)+(n.uml.ancestors?.length?umlChain(n):'');
    body+=umlMemberSection(n)||empty('La classe non ha attributi né ruoli nel dizionario dati.');
    body+=associationSection(n)+boundarySections(n)+literals(n)+umlConstraints(n);
    const children=n.uml.children||[];
    if(children.length)body+=section('Sottoclassi nel modello concettuale',cardGrid(children,'specializzazione UML'),children.length);
    return body+encodedBy(n);
  }
  function connectionsUml(n) {
    let body=levelNote(n)+umlHierarchySections(n,true)+associationSection(n);
    const out=umlMembers(n).filter(m=>m.typeId), incoming=umlIncoming[n.id]||[];
    if(out.length)body+=section('Collegamenti in uscita',`<div class="connection-grid">${out.map(m=>card(m.typeId,m.name+(m.multiplicity?' · '+m.multiplicity:'')+(m.owner!==n.id?' · ereditato':''))).join('')}</div>`,out.length,'Tipi dei membri UML');
    body+=boundarySections(n);
    if(incoming.length)body+=section('Chi fa riferimento a questo concetto',`<div class="connection-grid">${incoming.map(i=>card(i.source,i.member.name+(i.member.multiplicity?' · '+i.member.multiplicity:''))).join('')}</div>`,incoming.length,'Membri UML che hanno questa classe come tipo');
    return body;
  }
  function propertiesView(n) {
    if(umlLevel(n)) return levelNote(n)+(umlMemberSection(n)||empty('La classe non ha attributi né ruoli nel dizionario dati.'));
    if(n.umlOnly) return umlMemberSection(n)||empty('La classe non ha attributi né ruoli nel dizionario dati.');
    return levelNote(n)+ `<div class="property-toolbar"><input type="search" id="property-search" value="${esc(propertyQuery)}" placeholder="Filtra le proprietà..." aria-label="Filtra proprietà nella scheda"><div class="segment"><button data-kind="all" class="${propertyKind==='all'?'active':''}">Tutte</button>${Object.entries(groups).map(([k,[title]])=>`<button data-kind="${k}" class="${propertyKind===k?'active':''}">${title}</button>`).join('')}</div></div><div id="property-results">${propertyResults(n)}</div>`;
  }
  function propertyResults(n) {
    const query=propertyQuery.toLowerCase(),props=properties(n).filter(p=>(propertyKind==='all'||p.kind===propertyKind)&&(!query||(p.name+' '+p.description+' '+p.typeName).toLowerCase().includes(query)));
    return props.length?propSections(props,n):empty('Nessuna proprietà corrisponde ai filtri. '+(inherited?'':'Attiva le proprietà ereditate per includere le superclassi.'));
  }
  function connections(n) {
    if(umlLevel(n)) return connectionsUml(n);
    let body=levelNote(n)+'<div class="legend" style="margin-bottom:22px"><span>Associazione</span><span class="geom">Geometria</span><span class="ade">ADE hook</span></div>';
    if(!n.umlOnly)body+=section('Superclasse / tipo base',n.parents.length?`<div class="connection-grid">${n.parents.map(id=>card(id,n.derivation)).join('')}</div>`:empty('Nessuna superclasse nominale dichiarata.'),n.parents.length);
    if(n.children.length)body+=section('Sottoclassi / tipi derivati',`<div class="connection-grid">${n.children.map(id=>card(id,'xs:extension')).join('')}</div>`,n.children.length);
    if(n.substitution)body+=section('Sostituzione XML',card(n.substitution,'substitutionGroup — non è l’ereditarietà del tipo'));
    body+=umlHierarchySections(n,n.umlOnly)+associationSection(n);
    const umlOut=n.umlOnly?umlMembers(n).filter(m=>m.typeId):[];
    if(umlOut.length)body+=section('Collegamenti nel modello concettuale',`<div class="connection-grid">${umlOut.map(m=>card(m.typeId,m.name+(m.multiplicity?' · '+m.multiplicity:''))).join('')}</div>`,umlOut.length,'Tipi dei membri UML');
    const outgoing=properties(n).filter(p=>['association','geometry','ade'].includes(p.kind));
    if(outgoing.length)body+=section('Collegamenti in uscita',propTable(outgoing,n),outgoing.length);
    body+=boundarySections(n);
    // The relation of the referring property, read as in its own card.
    const incomingLabel=i=>i.kind==='umlMember'?'membro UML':propertyIndex[i.id]?relationText(propertyIndex[i.id]):'';
    if(n.incoming.length)body+=section('Chi fa riferimento a questo concetto',`<div class="connection-grid">${n.incoming.map(i=>{const label=incomingLabel(i);return card(i.source,i.property+(label?' · '+label:'')+(i.multiplicity?' · '+i.multiplicity:''));}).join('')}</div>`,n.incoming.length,'Riferimenti diretti alla destinazione esatta');
    return body;
  }
  function requirementBlock(r) {
    const link=r.document===encoding?.document.documentNumber?encodingLink:docLink;
    return `<div class="constraint"><div class="constraint-label">${esc(r.title)} · ${link(r.anchor, r.id)}</div>${r.text.map(t=>`<div class="tiny">${esc(t)}</div>`).join('')}${(r.parts||[]).map(x=>`<div class="tiny"><strong>${esc(x.label)}</strong> ${esc(x.text)}</div>`).join('')}${(r.notes||[]).map(t=>`<div class="tiny muted">${esc(t)}</div>`).join('')}</div>`;
  }
  /* Where the class can be a direct member of a CityModel: the union CityModelMember of the data dictionary and the
     elements of CityModel in the schemas, next to the sentence of OGC 20-010 on top-level features. */
  function cityModelRow(n) {
    const c=n.cityModelMember;
    if(!c) return '';
    const uml=c.uml.map(id=>{const [owner,name]=id.split('/uml:');return {owner,m:(nodes[owner]?.uml?.properties||[]).find(p=>p.name===name)};}).filter(x=>x.m);
    const gml=c.gml.map(id=>propertyIndex[id]).filter(Boolean), rule=standard.topLevelMembers;
    const sources=[uml.length?`attributi dell’unione ${ref(uml[0].owner)} nel dizionario dati`:'',gml.length?`elementi ${gml.map(p=>`<code>${esc(p.qname)}</code>`).join(', ')} di ${ref(gml[0].declaredIn)} negli schemi XSD`:''].filter(Boolean).join('; ');
    const divergence=rule&&uml.length&&!n.topLevel&&!n.abstract?` La classe non ha lo stereotipo «TopLevelFeatureType», ma ${ref(uml[0].owner)} la ammette: su questo il paragrafo e il dizionario dati non coincidono.`:'';
    return `<dt>Membro diretto di un CityModel</dt><dd>${uml.map(({m})=>`<div><code>${esc(m.name)}</code> · ${ref(m.typeId,m.type)}<div class="tiny muted">${esc(m.definition||'')}</div></div>`).join('')}<div class="tiny">${sources.charAt(0).toUpperCase()+sources.slice(1)}.</div>${rule?`<div class="tiny">OGC ${esc(standard.document.documentNumber)}, ${docLink(rule.anchor,'§'+rule.number+' '+rule.title)} · ${onlineLink(rule.anchor,'online')}: «${esc(rule.text)}»${divergence}</div>`:''}</dd>`;
  }
  function standardView(n) {
    if(!standard) return empty('Il documento del modello concettuale non è presente nel catalogo.');
    if(n.family!=='CityGML') return empty('Questo concetto appartiene a uno schema importato: non fa parte del modello concettuale CityGML.');
    let body='';
    if(n.uml){
      body+=section('Classe nel modello concettuale',`<dl class="metadata-grid"><dt>Nome UML</dt><dd>${esc(n.uml.name)}${n.uml.name!==n.name?' <span class="muted">(nello schema: '+esc(n.name)+')</span>':''}</dd><dt>Stereotipo</dt><dd>«${esc(n.uml.stereotype)}»</dd><dt>Package</dt><dd>${esc(n.uml.package||'')}</dd>${n.kind==='feature'?`<dt>Primo livello</dt><dd>${n.topLevel?'Sì: stereotipo «TopLevelFeatureType», uno dei componenti principali del modello concettuale, scomponibile in parti':'No: non ha lo stereotipo «TopLevelFeatureType»'}</dd>`:''}${cityModelRow(n)}<dt>Superclassi</dt><dd>${[...(n.uml.unresolvedParents||[]).map(s=>`${esc(s)} <span class="muted">(non nel catalogo)</span>`),...(n.uml.parents||[]).map(id=>ref(id))].join(', ')||'nessuna'}${parentsNote(n)}</dd><dt>Sottoclassi</dt><dd>${(n.uml.children||[]).map(id=>ref(id)).join(', ')||'nessuna'}</dd><dt>Dizionario dati</dt><dd>${n.uml.anchor?docLink(n.uml.anchor,'copia locale')+' · '+onlineLink(n.uml.anchor,'online'):'senza ancora nel documento'}</dd></dl>`);
      if(n.uml.ancestors?.length) body+=umlChain(n);
      body+=umlMemberSection(n)+associationSection(n)+umlConstraints(n);
    } else {
      body+=notice('Questo concetto esiste negli schemi XSD ma non ha una classe corrispondente nel modello concettuale.');
    }
    const chapter=standard.modules[n.module];
    if(chapter) body+=section('Capitolo del modulo',`<p>${docLink(chapter.anchor, chapter.number+' '+n.module)} · ${onlineLink(chapter.anchor,'online')}</p>`);
    body+=boundarySections(n);
    const reqs=standard.requirements.filter(r=>r.module===n.module.toLowerCase());
    const encodingRules=(encoding?.requirements||[]).filter(r=>r.module===n.module.toLowerCase()), globalRules=(encoding?.requirements||[]).filter(r=>r.module==='global');
    if(reqs.length) body+=`<details class="section-collapse"><summary>Requisiti del modulo ${esc(n.module)} (OGC ${esc(standard.document.documentNumber)}) <span class="count">${reqs.length}</span></summary><div>${reqs.map(requirementBlock).join('')}</div></details>`;
    if(encodingRules.length) body+=`<details class="section-collapse"><summary>Requisiti della codifica GML del modulo ${esc(n.module)} (OGC ${esc(encoding.document.documentNumber)}) <span class="count">${encodingRules.length}</span></summary><div>${encodingRules.map(requirementBlock).join('')}</div></details>`;
    if(globalRules.length) body+=`<details class="section-collapse"><summary>Requisiti globali della codifica GML (OGC ${esc(encoding.document.documentNumber)}) <span class="count">${globalRules.length}</span></summary><div>${globalRules.map(requirementBlock).join('')}</div></details>`;
    return body;
  }
  function fileInfo(path) {
    return data.files.find(f=>f.path===path);
  }
  function sourceView(n) {
    if(n.umlOnly) {
      const uses=umlTypeUses[n.id]||[];
      const encoding=uses.length
        ?'Nessun tipo o elemento con questo nome. Proprietà con questa classe come tipo UML:<br>'+uses.map(u=>`${ref(u.source)} · <code>${esc(u.prop.qname||u.prop.name)}</code>: ${u.prop.typeId?ref(u.prop.typeId,u.prop.typeName):`<code>${esc(u.prop.typeName)}</code>`}`).join('<br>')
        :'Nessun tipo o elemento con questo nome e nessuna proprietà con questa classe come tipo UML: il catalogo non registra come la codifica la rappresenta.';
      return section('Provenienza',`<dl class="metadata-grid"><dt>Identificatore</dt><dd>${esc(n.id)}</dd><dt>Fonte</dt><dd>${esc(standard.document.title)} (OGC ${esc(standard.document.documentNumber)}, versione ${esc(standard.document.version)})</dd><dt>Scheda</dt><dd>${n.uml.anchor?docLink(n.uml.anchor,'dizionario dati, copia locale')+' · '+onlineLink(n.uml.anchor,'online'):'—'}</dd><dt>Negli schemi XSD</dt><dd>${encoding}</dd></dl>`);
    }
    const file=fileInfo(n.source[0]);
    let body=section('Provenienza',`<dl class="metadata-grid"><dt>Identificatore</dt><dd>${esc(n.id)}</dd><dt>Namespace</dt><dd>${esc(n.namespace||'')}</dd>${n.xmlType?`<dt>Tipo XML</dt><dd>${esc(n.xmlType)}</dd>`:''}<dt>File</dt><dd>${n.source.length?n.source.map(p=>sourceLink(p)).join('<br>'):'Definizione non disponibile localmente'}</dd>${n.line?`<dt>Riga</dt><dd>${n.line}</dd>`:''}${file?.url?`<dt>URL ufficiale</dt><dd>${sourceLink(file.url)}</dd><dt>Versione schema</dt><dd>${esc(file.schemaVersion||'non dichiarata')}</dd><dt>Scaricato il</dt><dd>${esc(file.retrievedAt.slice(0,10))}</dd>`:''}<dt>Stato</dt><dd>${n.external?'Solo riferimento esterno':n.builtin?'Tipo predefinito':'Dichiarazione disponibile'}</dd></dl>`);
    if(n.xml)body+=section('Dichiarazione XML Schema',`<pre class="source-block"><code>${esc(n.xml)}</code></pre>`,'','Estratto dello schema ufficiale');
    body+=constraints(n);
    return body;
  }
  function renderPage(reset=false) {
    if(view==='codelists'){renderCodeListOverview();return;}
    const n=nodes[current];
    if(!n) {
      $('#content').innerHTML=empty('Identificatore non presente nel catalogo. '+ref(data.initialId,'Torna a Building'));
      $('#breadcrumb').textContent='Risorsa non trovata';return;
    }
    const props=properties(n), uml=umlLevel(n);
    document.title=n.name+' · CityGML Explorer';
    $('#breadcrumb').innerHTML=`<b>${esc(n.module)}</b><span>/</span>${esc(n.name)}`;
    $('#content').innerHTML=`<article class="page"><div class="eyebrow"><span>${esc(n.family)}</span><span class="slash">/</span><span>${esc(n.module)}</span><span class="slash">/</span><span>${n.umlOnly||uml?'UML':'XSD'}</span></div><div class="hero"><div><h1>${esc(n.name)}</h1><div class="hero-subtitle"><code>${esc(n.qname||n.name)}</code><button class="icon-button" data-action="copy-id" aria-label="Copia identificatore" title="Copia identificatore">&#10697;</button></div></div><div class="hero-actions">${n.uml&&!n.umlOnly?`<div class="segment level-switch" role="group" aria-label="Livello di lettura"><button data-level="gml" class="${uml?'':'active'}" aria-pressed="${!uml}" title="Elementi, tipi e cardinalità degli schemi XSD">Codifica GML</button><button data-level="uml" class="${uml?'active':''}" aria-pressed="${uml}" title="Classe, membri e molteplicità del modello concettuale">Modello UML</button></div>`:''}<button class="text-button" data-action="export">Esporta JSON ↗</button><button class="text-button" data-tab="source">&lt;/&gt; Sorgente</button></div></div><div class="badges"><span class="badge teal" title="${esc(kindNotes[n.kind]||'')}">${esc(kinds[n.kind]||n.kind)}</span>${['feature','object','datatype'].includes(n.kind)&&!n.technical&&!n.umlOnly?`<span class="badge">${n.abstract?'Astratta':'Concreta'}</span>`:''}${n.topLevel?'<span class="badge teal" title="«TopLevelFeatureType» in OGC 20-010: feature che rappresenta uno dei componenti principali del modello concettuale e può essere scomposta in parti.">Primo livello</span>':''}${n.uml?`<span class="badge" title="Stereotipo UML (OGC 20-010)">«${esc(n.uml.stereotype)}»</span>`:''}${n.umlOnly?'<span class="badge amber" title="Definita nel modello concettuale (OGC 20-010); gli schemi XSD non hanno un tipo o un elemento con questo nome. La scheda Sorgente elenca le proprietà XSD che la usano come tipo.">Senza tipo XSD dedicato</span>':''}${n.cityObject?'<span class="badge blue" title="Discende da core:AbstractCityObject.">Oggetto di città</span>':''}${n.spaceRole?`<span class="badge blue" title="${esc(roles[n.spaceRole][1])}">${roles[n.spaceRole][0]}</span>`:''}${n.umlOnly?'':`<span class="badge">${esc(n.xmlType||'XML Schema')}</span>`}${n.external?'<span class="badge amber">Definizione non disponibile</span>':''}${n.technical?'<span class="badge">Tipo tecnico</span>':''}</div>${uml?`<p class="definition ${n.uml.definition?'':'empty'}">${esc(n.uml.definition||'Nessuna definizione nel dizionario dati.')} <span class="muted tiny">(OGC 20-010)</span></p>`:`<p class="definition ${n.description?'':'empty'}">${esc(n.description || 'Nessuna definizione testuale disponibile nello schema.')}</p>`}<div class="tabbar" role="tablist" aria-label="Sezioni della scheda">${Object.entries(tabs).map(([id,label])=>`<button class="tab ${activeTab===id?'active':''}" data-tab="${id}" id="tab-${id}" role="tab" aria-selected="${activeTab===id}" aria-controls="tab-content">${label}${id==='properties'?`<span class="count">${uml||n.umlOnly?umlMembers(n).length:props.length}</span>`:''}</button>`).join('')}<label class="inherited-control"><span class="switch"><input type="checkbox" id="inherited" ${inherited?'checked':''} aria-label="Mostra proprietà ereditate"><span></span></span>Includi ereditate</label></div><div class="tab-content" id="tab-content" role="tabpanel" aria-labelledby="tab-${activeTab}">${activeTab==='overview'?overview(n):activeTab==='properties'?propertiesView(n):activeTab==='connections'?connections(n):activeTab==='standard'?standardView(n):sourceView(n)}</div><footer class="page-footer"><span>Codifica XML di CityGML 3.0 e modello concettuale OGC 20-010</span><span>${n.source.length} ${n.source.length===1?'sorgente locale':'sorgenti locali'}</span><a href="#" data-action="help">Guida alla lettura ↗</a></footer></article>`;
    $('#inherited').addEventListener('change',e=>{
      inherited=e.target.checked;try{localStorage.setItem('cg-inherited',inherited);}catch(_){}
      const pos=$('#content').scrollTop;renderPage();$('#content').scrollTop=pos;
    });
    $('#property-search')?.addEventListener('input',e=>{propertyQuery=e.target.value;$('#property-results').innerHTML=propertyResults(n);});
    if(reset)$('#content').scrollTop=scroll.get(current+'|'+activeTab)||0;
  }
  function route() {
    if(previous)scroll.set(previous,$('#content').scrollTop);
    let params;
    try{params=new URLSearchParams(location.hash.slice(1));}catch(_){params=new URLSearchParams();}
    view=params.get('view')==='codelists'?'codelists':null;
    level=params.get('level')==='uml'?'uml':'gml';
    if(view){
      current=null;previous='view|codelists';
      renderList();renderCodeListOverview();$('#content').scrollTop=scroll.get(previous)||0;
      $('#sidebar').classList.remove('open');$('#mobile-menu').setAttribute('aria-expanded','false');
      return;
    }
    const next=params.get('node')||data.initialId,tab=params.get('tab'),prop=params.get('prop');
    if(next!==current){propertyQuery='';propertyKind='all';}
    current=next;activeTab=Object.hasOwn(tabs,tab)?tab:'overview';
    const target=prop&&nodes[current]?properties(nodes[current],true).find(p=>p.id===prop):null;
    if(target){propertyQuery=target.name;propertyKind='all';}
    previous=current+'|'+activeTab;
    renderList();renderPage(true);
    // The details follow the URL: Back to an address without the property closes them.
    if(target)propertyModal(target.id);else if($('#modal').open)$('#modal').close();
    $('#sidebar').classList.remove('open');$('#mobile-menu').setAttribute('aria-expanded','false');
  }
  function codeListSources() {
    if(!codeLists) return '<h3>Code list</h3>'+notice('Dizionario locale non caricato: mancano codelists/codelists.js e codelists/codelists.default.js.');
    const s=codeListSummary(), src=codeLists.source;
    return `<h3>Code list (dizionario locale)</h3><div class="stats-grid"><div class="stat-card"><span class="stat-label">Con valori</span><strong>${s.values}</strong></div><div class="stat-card"><span class="stat-label">Solo segnaposto</span><strong>${s.placeholder}</strong></div><div class="stat-card"><span class="stat-label">Vuote o non disponibili</span><strong>${s.empty}</strong></div><div class="stat-card"><span class="stat-label">Modificate</span><strong>${s.edited}</strong></div></div><p>Lo standard definisce le ${s.total} code list ma non i loro valori. Lo stato iniziale del dizionario locale proviene da ${esc(src.title)} ${esc(src.version)} (${esc(src.reference)}), scaricati il ${esc((src.retrievedAt||'').slice(0,10))} in ${sourceLink('sources/'+src.host+'/citygml-swg/CodeList_Examples_3.0.0/','sources/'+src.host)}. I valori sono esempi non normativi; il dizionario si modifica dalla pagina di ogni code list e si salva in <code>codelists/codelists.js</code>.</p>`;
  }
  function coverageTable(cov) {
    const dims={classes:'Classi',members:'Attributi e ruoli',generalizations:'Generalizzazioni',associationClasses:'Ruoli qualificati da classi di associazione',constraints:'Vincoli OCL',simpleTypes:'Liste e unioni degli schemi'};
    const xsd={sameName:'con lo stesso nome',withoutXsdType:'senza tipo XSD dedicato',inherited:'con proprietà ereditata',unionAlternatives:'come alternative di un’unione',classWithoutXsdType:'in classi senza tipo XSD',none:'senza corrispondenza',xsExtension:'con xs:extension',umlOnly:'solo nel modello concettuale'};
    const rows=Object.entries(dims).filter(([k])=>cov[k]).map(([k,label])=>{const c=cov[k];
      const by=c.declaredBy?`<div class="tiny muted">dizionario ${c.declaredBy.dictionary} · modello UML ${c.declaredBy.model}</div>`:'';
      return `<tr><td>${label}</td><td>${c.total}${by}</td><td>${c.represented}${c.findings.length?` <span class="badge amber">${c.findings.length} mancanti</span>`:''}</td><td>${c.excluded.length||'—'}</td><td class="tiny">${Object.keys(xsd).filter(r=>c.xsd[r]).map(r=>`${c.xsd[r].length} ${xsd[r]}`).join(' · ')||'—'}</td></tr>`;}).join('');
    const dv=cov.divergences||{multiplicities:[],generalizations:[]};
    const pairs=[...new Set(dv.multiplicities.map(d=>`dizionario ${d.dictionary}, modello ${d.model}`))];
    const divergences=(dv.multiplicities.length?[`<div class="constraint"><div class="constraint-label">Molteplicità diverse fra dizionario dati e modello UML · ${dv.multiplicities.length}</div><div class="tiny">${pairs.map(p=>`${esc(p)}: ${esc(dv.multiplicities.filter(d=>`dizionario ${d.dictionary}, modello ${d.model}`===p).map(d=>d.declaration).join(', '))}`).join('<br>')}</div></div>`]:[])
      .concat(dv.generalizations.length?[`<div class="constraint"><div class="constraint-label">Generalizzazioni diverse fra dizionario dati e modello UML · ${dv.generalizations.length}</div><div class="tiny">${dv.generalizations.map(d=>`${esc(d.declaration)} → ${esc(d.model.join(', '))} (dizionario: ${esc(d.dictionary.join(', ')||'None')})`).join(', ')}</div></div>`]:[]).join('');
    const summary=dv.multiplicities.length||dv.generalizations.length?`<p class="tiny">Il dizionario dati e il modello UML divergono su ${dv.multiplicities.length} molteplicità e ${dv.generalizations.length} generalizzazioni: il livello Modello UML mostra i valori del modello e, accanto, quelli del dizionario.</p>`:'';
    const listed=['inherited','unionAlternatives','none','umlOnly'];
    const details=Object.entries(dims).filter(([k])=>cov[k]).flatMap(([k,label])=>[
      ...cov[k].findings.map(f=>`<div class="constraint"><div class="constraint-label">${label} · non nel catalogo</div><div class="tiny">${esc(f.declaration)} — atteso: ${esc(f.expected)}</div></div>`),
      ...listed.filter(r=>cov[k].xsd[r]).map(r=>[r,cov[k].xsd[r]]).map(([r,v])=>`<div class="constraint"><div class="constraint-label">${label} · ${esc(xsd[r])} · ${v.length}</div><div class="tiny">${esc(v.join(', '))}</div></div>`),
      ...(cov[k].excluded.length?[`<div class="constraint"><div class="constraint-label">${label} · esclusi · ${cov[k].excluded.length}</div><div class="tiny">${esc([...new Set(cov[k].excluded.map(e=>e.reason))].join('; '))}: ${esc(cov[k].excluded.map(e=>e.declaration).join(', '))}</div></div>`]:[])]).join('');
    return `<table class="source-table"><thead><tr><th>Dimensione</th><th>Nella fonte</th><th>Nel catalogo</th><th>Esclusi</th><th>Negli schemi XSD</th></tr></thead><tbody>${rows}</tbody></table><p class="tiny muted">Fonti: dizionario dati di OGC 20-010 (capitolo 8), solo le classi CityGML; per le generalizzazioni anche il modello UML (XMI), da cui provengono i ruoli qualificati dalle classi di associazione; per liste e unioni, gli schemi CityGML. Il confronto riguarda la presenza delle dichiarazioni e la loro corrispondenza con gli schemi, ricavata da nomi, ereditarietà e unioni; non verifica l’equivalenza dei significati.</p>${summary}<details class="section-collapse"><summary>Dettagli della copertura</summary><div>${divergences}${details}</div></details>`;
  }
  function encodingSource() {
    if(!encoding) return '<h3>Codifica GML</h3>'+notice('Il documento OGC 21-006r2 non è fra le fonti: i requisiti di codifica non sono nel catalogo.');
    const e=encoding.document;
    return `<h3>Codifica GML</h3><table class="source-table"><thead><tr><th>Fonte</th><th>Versione</th><th>Scaricato il</th><th>SHA-256 (inizio)</th></tr></thead><tbody><tr><td>${sourceLink(e.path,e.title)}<div class="tiny muted">OGC ${esc(e.documentNumber)} · approvato ${esc(e.approvalDate||'')} · pubblicato ${esc(e.publicationDate||'')} · ${sourceLink(e.url,'online')}</div></td><td>${esc(e.version||'—')}</td><td>${esc(e.retrievedAt.slice(0,10))}</td><td><code title="${esc(e.sha256)}">${e.sha256.slice(0,12)}…</code></td></tr></tbody></table><p class="tiny muted">Dal documento: requisiti, raccomandazioni e classi di requisiti della codifica, con i punti e le note. Una regola che nomina una proprietà («the X property … of the E element») compare nei dettagli di quella proprietà.</p>`;
  }
  function documentsTable(docs) {
    if(!docs.length) return '';
    const kinds={Requirement:'requisiti','Requirements class':'classi di requisiti',Recommendation:'raccomandazioni',Permission:'permessi'};
    const rows=docs.map(d=>`<tr><td>OGC ${esc(d.document||'—')}<div class="tiny muted">${esc(d.role==='gml-encoding-document'?'codifica GML (Parte 2)':'modello concettuale (Parte 1)')}</div></td><td>${d.acquired?'sì':'<span class="badge amber">no</span>'}</td><td class="tiny">${Object.entries(d.rules||{}).map(([k,v])=>`${v} ${esc(kinds[k]||k)}`).join(' · ')||'—'}</td><td>${d.linkedProperties??'—'}</td><td class="tiny">${[...(d.unresolvedMentions||[]),...(d.unrecognizedTables||[])].map(esc).join(', ')||'—'}</td></tr>`).join('');
    return `<table class="source-table"><thead><tr><th>Documento normativo</th><th>Acquisito</th><th>Regole estratte</th><th>Proprietà collegate</th><th>Non risolti</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  function standardSources() {
    if(!standard) return '';
    const d=standard.document, u=standard.umlModel, r=standard.report;
    const labels={xsdWithoutUml:'Concetti XSD senza classe UML',propertiesWithoutUml:'Proprietà XSD senza attributo o ruolo UML',propertiesMappedToUnion:'Proprietà XSD che codificano le alternative di un’unione UML',associationsWithoutXmi:'Relazioni XSD senza associazione nell’XMI',spacesWithoutBoundaryTable:'Spazi concreti senza tabella dei confini',boundaryRowsWithoutXsd:'Righe delle tabelle dei confini senza classe XSD',boundaryClassesWithoutXsd:'Superfici delle tabelle senza classe XSD'};
    const report=Object.entries(r).map(([k,v])=>`<div class="constraint"><div class="constraint-label">${esc(labels[k]||k)} · ${v.length}</div>${v.length?`<div class="tiny">${esc(v.join(', '))}</div>`:''}</div>`).join('');
    return `<h3>Modello concettuale</h3><table class="source-table"><thead><tr><th>Fonte</th><th>Versione</th><th>Scaricato il</th><th>SHA-256 (inizio)</th></tr></thead><tbody><tr><td>${sourceLink(d.path,d.title)}<div class="tiny muted">OGC ${esc(d.documentNumber)} · approvato ${esc(d.approvalDate||'')} · pubblicato ${esc(d.publicationDate||'')} · ${sourceLink(d.url,'online')}</div></td><td>${esc(d.version||'—')}</td><td>${esc(d.retrievedAt.slice(0,10))}</td><td><code title="${esc(d.sha256)}">${d.sha256.slice(0,12)}…</code></td></tr>${u?`<tr><td>${sourceLink(u.path,'Modello UML (XMI)')}<div class="tiny muted">${esc(u.member)} · commit <code>${esc((u.commit||'').slice(0,12))}</code> · ${sourceLink(u.url,'online')}</div></td><td>3.0</td><td>${esc(u.retrievedAt.slice(0,10))}</td><td><code title="${esc(u.sha256)}">${u.sha256.slice(0,12)}…</code></td></tr>`:''}</tbody></table><p class="tiny muted">Dal documento: stereotipi, oggetti di primo livello, code list, attributi e ruoli con i loro tipi e definizioni, vincoli, valori delle enumerazioni, superfici di confine ammesse, requisiti. Dall’XMI: molteplicità di attributi e ruoli, generalizzazioni, composizione o aggregazione delle relazioni; dove il dizionario dati riporta un valore diverso, la scheda mostra anche quello. Le corrispondenze con gli schemi sono per nome; le differenze sono elencate qui sotto.</p>${encodingSource()}${standard.coverage?'<h3>Copertura del modello concettuale</h3>'+coverageTable(standard.coverage)+documentsTable(standard.coverage.documents||[]):''}<details class="section-collapse"><summary>Confronto fra schemi XSD e modello concettuale</summary><div>${report}</div></details>`;
  }
  function sourcesModal() {
    const unique=Object.values(Object.fromEntries(data.dependencies.map(d=>[d.url,d])));
    const missing=unique.filter(d=>d.status==='missing');
    const rows=files=>files.map(f=>`<tr><td>${sourceLink(f.path,f.path.replace(/^sources\//,''))}</td><td>${esc(f.schemaVersion||'—')}</td><td>${esc((f.retrievedAt||'').slice(0,10))}</td><td><code title="${esc(f.sha256)}">${f.sha256.slice(0,12)}…</code></td></tr>`).join('');
    const table=files=>`<table class="source-table"><thead><tr><th>File</th><th>Versione</th><th>Scaricato il</th><th>SHA-256 (inizio)</th></tr></thead><tbody>${rows(files)}</tbody></table>`;
    showModal('Sorgenti',`<div class="stats-grid"><div class="stat-card"><span class="stat-label">Schemi CityGML 3.0</span><strong>${data.stats.citygmlFiles}</strong></div><div class="stat-card"><span class="stat-label">Schemi importati</span><strong>${data.stats.dependencyFiles}</strong></div><div class="stat-card"><span class="stat-label">Import non risolti</span><strong>${missing.length}</strong></div><div class="stat-card"><span class="stat-label">Riferimenti senza definizione</span><strong>${data.stats.external}</strong></div></div>${missing.length?notice('Alcuni import non sono presenti in <code>sources/</code>. Esegui <code>python scripts/fetch_sources.py</code> e poi <code>python scripts/build_catalog.py</code>.'):notice('Tutti gli import degli schemi sono presenti in <code>sources/</code>: il catalogo è consultabile offline.','info')}${missing.length?`<h3>Import non risolti</h3><table class="source-table"><thead><tr><th>Dipendenza</th><th>Richiesta da</th></tr></thead><tbody>${missing.map(d=>`<tr><td class="url"><a href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener">${esc(d.url)}</a></td><td>${esc(d.from)}</td></tr>`).join('')}</tbody></table>`:''}<h3>CityGML 3.0</h3>${table(data.files.filter(f=>f.citygml))}<h3>Schemi importati (GML, ISO 19139, XLink, XML)</h3>${table(data.files.filter(f=>!f.citygml))}${standardSources()}${codeListSources()}<p>URL di origine, date e hash completi: ${sourceLink('sources/manifest.json','sources/manifest.json')}. Versioni e fonti sono descritte nel ${sourceLink('README.md','README')}.</p>`);
  }
  function helpModal() {
    showModal('Come leggere il catalogo',`<p>Cerca un concetto a sinistra, apri la scheda e segui i nomi cliccabili. La ricerca trova classi, valori delle code list e nomi delle proprietà, ciascuna nella classe che la dichiara. La pagina funziona offline: legge un indice preparato dalle fonti ufficiali (schemi XSD e documenti OGC) nella cartella <code>sources/</code>.</p><h3>Categorie</h3><p>Le categorie seguono la derivazione dei tipi, per <code>xs:extension</code> o per <code>xs:restriction</code>. <strong>Feature</strong>: deriva da <code>gml:AbstractFeature</code>. <strong>Oggetto (non feature)</strong>: deriva da <code>gml:AbstractGML</code> ma non da <code>gml:AbstractFeature</code>. <strong>Tipo di dato</strong>: nessuna delle due, quindi senza identità propria. Gli <strong>oggetti di città</strong> discendono da <code>core:AbstractCityObject</code>; fra questi gli <strong>spazi</strong> discendono da <code>core:AbstractSpace</code> e le <strong>superfici di confine</strong> da <code>core:AbstractSpaceBoundary</code>.</p><h3>Ereditarietà e associazioni</h3><p>Nella codifica GML, <code>xs:extension</code> estende il contenuto del tipo base. Una derivazione per <code>xs:restriction</code> ridefinisce il contenuto di elementi e conserva gli attributi della base che non vengono ridefiniti o proibiti: compaiono fra le proprietà ereditate. Le associazioni, gli ADE hook e <code>substitutionGroup</code> non trasferiscono proprietà. Nel modello UML l’ereditarietà segue le generalizzazioni del modello (XMI).</p><h3>Proprietà</h3><p>Attributi e valori è una categoria di lettura: molti sono <code>xs:element</code>, non <code>xs:attribute</code>. Le occorrenze includono i gruppi contenitori; un campo in <code>xs:choice</code> resta un’alternativa, non un requisito indipendente: a ogni occorrenza della scelta compare un solo campo, e se la scelta si ripete i campi possono comparire tutti. Il codice XML rimane la fonte da verificare.</p><h3>Relazioni</h3><p>Una proprietà è una relazione quando la destinazione è una feature o un oggetto; verso un tipo di dato è un attributo. Il badge della relazione viene dal modello UML (XMI): <strong>composizione</strong>, <strong>aggregazione</strong> (l’oggetto collegato è parte di questo) o <strong>associazione</strong>; se l’XMI non ha l’associazione, il catalogo la legge come <strong>aggregazione</strong> quando il tipo estende <code>gml:AbstractFeatureMemberType</code> o <code>gml:AbstractMemberType</code>, che per GML rendono l’oggetto una collezione di quelli collegati, senza implicarne il possesso. Un secondo badge indica la forma ammessa dallo schema: <strong>solo riferimento</strong> se l’oggetto si indica soltanto con <code>xlink:href</code>, <strong>solo incluso</strong> se si include soltanto come elemento figlio; senza badge sono ammesse entrambe.</p><h3>Livelli di lettura</h3><p>Una classe con tipo XSD e classe UML si legge come <strong>Codifica GML</strong> (elementi, tipi e cardinalità degli schemi) o come <strong>Modello UML</strong> (membri del dizionario dati di OGC 20-010, con le molteplicità e le generalizzazioni del modello UML disegnate nelle figure del documento; dove il dizionario riporta un valore diverso, compare accanto con il badge <strong>dizionario</strong>), con il selettore nella testata. Le due cardinalità non si mescolano: ogni tabella dichiara il proprio livello.</p><h3>Destinazioni</h3><p>Nei dettagli di una proprietà, le destinazioni sono lette nel contesto della classe visitata: per i confini di uno spazio vale la tabella <code>/req/&lt;modulo&gt;/boundaries</code> di quella classe; gli <strong>elementi sostituibili negli schemi</strong> (<code>substitutionGroup</code>) sono candidati, non destinazioni conformi.</p><h3>Modello concettuale</h3><p>La scheda <strong>Standard</strong> e i badge «stereotipo», <strong>Primo livello</strong> e <strong>Senza tipo XSD dedicato</strong> provengono dal documento OGC 20-010 (CityGML 3.0 Part 1: Conceptual Model). La scheda riporta superclassi e sottoclassi, membri (attributi e ruoli) e vincoli della classe: definizioni, tipi e vincoli come li scrive il dizionario dati, molteplicità e generalizzazioni come le dichiara il modello UML (XMI); poi le <strong>superfici di confine ammesse</strong> dalle tabelle <code>/req/&lt;modulo&gt;/boundaries</code>. Per una feature indica in quali membri di un <code>CityModel</code> può stare, secondo l’unione <code>CityModelMember</code> e gli schemi XSD, accanto alla frase di OGC 20-010, §6.2.3, sui membri diretti; dove le due parti del documento non coincidono lo segnala. La distinzione fra <strong>composizione</strong> e aggregazione viene dal modello UML (XMI). La Panoramica mostra la generalizzazione UML quando gli schemi non la esprimono con <code>xs:extension</code>. Le <strong>code list</strong> hanno un nome e una definizione nello standard, ma i loro valori sono definiti da dizionari esterni.</p><h3>Codifica GML</h3><p>I requisiti e le raccomandazioni del documento OGC 21-006r2 (CityGML 3.0 Part 2: GML Encoding) compaiono nella scheda Standard, per modulo e globali, e nei dettagli delle proprietà che nominano.</p><h3>Copertura</h3><p>Il riquadro <strong>Sorgenti</strong> riporta quante classi, attributi e ruoli, generalizzazioni e vincoli del dizionario dati e del modello UML sono nel catalogo, come li rappresentano gli schemi e dove dizionario e modello divergono, e quali regole dei documenti normativi sono estratte e collegate alle proprietà.</p><h3>Code list e dizionario locale</h3><p>Lo standard non definisce i <strong>valori delle code list</strong>: li affida a dizionari esterni. Il catalogo carica un <strong>dizionario locale</strong> (<code>codelists/codelists.js</code>), inizializzato con gli esempi OGC e modificabile dalla pagina di ogni code list: i valori compaiono nelle classi che usano quella code list e nella ricerca. Il pulsante <strong>Code list</strong> in alto indica quante hanno valori; <strong>Reset</strong> riporta il dizionario allo stato iniziale. I valori non sono normativi.</p>${standard?`<h3>Concetti dello standard</h3><p class="tiny muted">Capitolo 6 del documento, copia locale.</p><ul class="concept-links">${standard.concepts.map(c=>`<li class="level-${c.level}">${docLink(c.anchor,c.number+' '+c.title)}</li>`).join('')}</ul>`:''}<h3>Stato delle sorgenti</h3><p>La sigla <strong>est.</strong> indica una definizione non presente in <code>sources/</code>. Il browser non inventa le proprietà mancanti.</p><h3>Legenda</h3><div class="legend"><span>F: feature</span><span>O: oggetto (non feature)</span><span class="geom">T: tipo di dato, enumerazione, tipo base o unione</span><span class="geom">L: code list</span><span class="ade">+: ADE hook</span><span>P: proprietà, nei risultati della ricerca</span></div><p>I concetti degli schemi importati sono mostrati con il prefisso del namespace, per esempio <code>gml:AbstractFeature</code>.</p><p>Premi <kbd>/</kbd> per cercare. I pulsanti Indietro/Avanti e la cronologia del browser seguono i concetti. Ogni scheda ha un URL con identificatore, sezione e livello di lettura.</p><p>${sourceLink('README.md','Apri il README del progetto')}</p>`);
  }
  /* Destinations of a property in the context of the visited class: the boundary table of OGC 20-010 for the space
     boundaries, and the elements that the schemas allow in place of the target (substitutionGroup), as candidates. */
  const SPACE_BOUNDARY = 'xsd:{http://www.opengis.net/citygml/3.0}element:AbstractSpaceBoundary';
  const substitutes = {};
  for (const n of allNodes) if (n.substitution) (substitutes[n.substitution] ??= []).push(n.id);
  function substitutionGroup(id) {
    const found=new Set(), stack=[id];
    while(stack.length) for(const member of substitutes[stack.pop()]||[]) if(!found.has(member)){found.add(member);stack.push(member);}
    return [...found];
  }
  function destinations(prop, context) {
    let body='';
    if(prop.targets.includes(SPACE_BOUNDARY)){
      const ab=context.allowedBoundaries;
      body+=!ab?`<p>Nessuna tabella dei confini per ${ref(context.id)}${context.abstract?': la classe è astratta, le tabelle riguardano le sue sottoclassi concrete':''}.</p>`
        :ab.none?`<p>OGC 20-010 non ammette superfici di confine per ${ref(context.id)} (${docLink(ab.anchor,ab.table)}, <code>${esc(ab.requirement)}</code>).</p>`
        :`<p>Ammesse per ${ref(context.id)} da OGC 20-010 (${docLink(ab.anchor,ab.table)}, <code>${esc(ab.requirement)}</code>): ${ab.concrete.map(id=>ref(id)).join(', ')}${ab.ade?'; inoltre classi da ADE':''}.</p>`;
    }
    const candidates=[...new Set(prop.targets.flatMap(substitutionGroup))].filter(id=>!nodes[id].abstract&&nodes[id].kind!=='ade').sort((a,b)=>byName(nodes[a],nodes[b]));
    if(candidates.length) body+=`<details class="section-collapse"><summary>Elementi sostituibili negli schemi <span class="count">${candidates.length}</span></summary><div><p>${candidates.map(id=>ref(id)).join(', ')}</p><p class="tiny muted">Elementi concreti nel substitutionGroup della destinazione: sono i candidati ammessi dagli schemi, non un elenco di destinazioni conformi; regole del modello concettuale o della codifica possono restringerli, e altri schemi (per esempio ADE) possono aggiungerne.</p></div></details>`;
    return body;
  }
  function concreteWith(id) {
    const found=new Set(), stack=[id];
    while(stack.length) for(const child of nodes[stack.pop()]?.children||[]) if(!found.has(child)){found.add(child);stack.push(child);}
    return [id,...found].filter(i=>nodes[i]&&!nodes[i].abstract&&!nodes[i].technical&&!nodes[i].external&&nodes[i].kind!=='ade').sort((a,b)=>byName(nodes[a],nodes[b]));
  }
  function propertyModal(id) {
    const prop=properties(nodes[current],true).find(p=>p.id===id);
    if(!prop)return;
    const e=prop.encoding, yes=v=>v===null?'non determinato':v?'sì':'no';
    showModal(prop.name,`<p class="tiny muted">Dettagli della codifica GML (schemi XSD)${umlLevel(nodes[current])?': la proprietà è aperta dal livello Modello UML, ma tipo, occorrenze e attributi qui sotto sono quelli degli schemi':''}.</p><p>${describe(prop)}</p><dl class="metadata-grid"><dt>Tipo XML</dt><dd>${esc(prop.xmlKind)}</dd><dt>Nome</dt><dd>${esc(prop.qname||prop.name)}</dd><dt>Tipo dichiarato</dt><dd>${prop.typeId?ref(prop.typeId,prop.typeName):esc(prop.typeName)}</dd><dt>Destinazione</dt><dd>${prop.targets.map(t=>ref(t)).join(', ')||'Non specificata'}${(()=>{const d=destinations(prop,nodes[current]);return d?`<div class="destinations"><div class="tiny muted">Nel contesto di ${esc(displayName(nodes[current]))}:</div>${d}</div>`:'';})()}</dd>${prop.umlMember?`<dt>Membro UML</dt><dd>${esc(prop.umlMember.split('/uml:').pop())}: la proprietà è un’alternativa del suo tipo unione</dd>`:''}${prop.umlType?`<dt>Tipo UML</dt><dd>${prop.umlTypeId?ref(prop.umlTypeId,prop.umlType):esc(prop.umlType)}${prop.codeList?' (code list)':''}</dd>`:''}${prop.aggregation?`<dt>Aggregazione UML</dt><dd>${esc({composite:'composizione',shared:'aggregazione',none:'associazione semplice'}[prop.aggregation])} (XMI)</dd>`:''}${e?`<dt>Oggetto incluso</dt><dd>${yes(e.allowsInline)} (elemento figlio nel tipo della proprietà)</dd><dt>Riferimento</dt><dd>${yes(e.allowsReference)} (xlink:href)</dd>`:''}${prop.rules?.length?`<dt>Requisiti della codifica</dt><dd>${prop.rules.map(r=>encodingLink(r.anchor,r.id+(r.part?' '+r.part:''))).join(', ')} (OGC ${esc(prop.rules[0].document)})</dd>`:''}<dt>Occorrenze</dt><dd>${esc(prop.multiplicity)}${prop.choices?.length?' — campo alternativo in xs:choice':''}</dd><dt>Definita in</dt><dd>${ref(prop.declaredIn)}</dd>${(()=>{const c=concreteWith(prop.declaredIn);return `<dt>Classi concrete con la proprietà</dt><dd>${c.length?`${c.length}: `+c.slice(0,60).map(i=>ref(i)).join(', ')+(c.length>60?' …':''):'nessuna'}</dd>`;})()}<dt>Sorgente</dt><dd>${sourceLink(prop.source)}${prop.line?' : '+prop.line:''}</dd><dt>Nillable</dt><dd>${prop.nillable?'Sì':'No / non dichiarato'}</dd><dt>Default / fixed</dt><dd>${esc(prop.default??'—')} / ${esc(prop.fixed??'—')}</dd><dt>Risoluzione</dt><dd>${esc((prop.targetEvidence||[]).join('; ')||'Tipo dichiarato')}</dd></dl><pre class="source-block"><code>${esc(prop.xml||'')}</code></pre>`);
  }
  function exportCurrent() {
    const n=nodes[current], uml=umlLevel(n)||n.umlOnly;
    const payload={schemaVersion:data.schemaVersion,sourceVersion:data.sourceVersion,level:uml?'uml':'gml',concept:n,visibleProperties:uml?umlMembers(n):properties(n),includeInherited:inherited,
      notes:uml?'Conceptual model level: attributes and roles of the data dictionary of OGC 20-010, with the multiplicities and generalizations of the UML model (XMI); dictionaryMultiplicity is the value of the data dictionary where it differs.':'GML encoding level: XSD declarations of OGC 21-006r2 with XML cardinalities. Conceptual model information from OGC 20-010 and its UML model is in concept.uml.'};
    // The values of a code list are not in the standard: the local dictionary, as shown on the page.
    const list=codeListOf(n);
    if(list)payload.localCodeList={file:'codelists/codelists.js',normative:false,saved:!codeListsDirty,
      note:'Values of the local dictionary, not part of the CityGML standard; saved is false when the page has changes not yet written to the file.',...clone(list)};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=n.name.replace(/[^a-z0-9_-]/gi,'_')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    showToast('Scheda esportata in JSON');
  }

  let listTimer=null;
  document.addEventListener('input',e=>{
    const field=e.target.closest('[data-cl-field]');
    if(!field)return;
    const n=nodes[current], l=codeListOf(n);
    if(!l)return;
    if(field.dataset.clField==='codeSpace'){
      // Only the values that follow the list change with it, never decided again from equal URIs while typing.
      const follow=followersOf(l);l.codeSpace=field.value;
      for(const v of l.values)if(follow.has(v))v.codeSpace=field.value;
    } else {
      const v=l.values[+field.dataset.clIndex];
      if(!v)return;
      v[field.dataset.clField]=field.value;
    }
    markCodeListEdited(l);
    // What derives from the values follows the input, without redrawing the field being edited.
    const usage=$('#cl-usage'), state=$('#cl-state');
    if(usage)usage.innerHTML=usageContent(n,l);
    if(state)state.innerHTML=stateBadges(l);
    clearTimeout(listTimer);listTimer=setTimeout(renderList,150);
  });
  function codeListAction(button) {
    const action=button.dataset.clAction, l=codeListOf(nodes[current]);
    if(action==='save'){saveCodeLists();return;}
    if(action==='revert'){revertCodeLists();return;}
    if(action==='reset'){resetCodeLists();return;}
    if(!l)return;
    if(action==='add'){
      const v={code:'',codeSpace:l.codeSpace||null,name:'',description:''};
      followersOf(l).add(v);l.values.push(v);markCodeListEdited(l);renderPage();
      const inputs=document.querySelectorAll('[data-cl-field="code"]');inputs[inputs.length-1]?.focus();
    }
    if(action==='delete'){l.values.splice(+button.dataset.clIndex,1);markCodeListEdited(l);renderPage();}
  }
  document.addEventListener('click',e=>{
    if(!$('#options-panel').hidden&&!e.target.closest('#options-panel,#options-btn'))toggleOptions(false);
    const themeButton=e.target.closest('[data-theme-choice]');if(themeButton){themeChoice=themeButton.dataset.themeChoice;saveOption('cg-theme',themeChoice);applyTheme();return;}
    const fontButton=e.target.closest('[data-font-step]');if(fontButton){stepFont(+fontButton.dataset.fontStep);return;}
    const filter=e.target.closest('[data-cl-filter]');if(filter){codeListFilter=filter.dataset.clFilter;renderCodeListOverview();return;}
    const levelButton=e.target.closest('[data-level]');if(levelButton){location.hash=href(current,activeTab,'',levelButton.dataset.level);return;}
    const clButton=e.target.closest('[data-cl-action]');if(clButton){e.preventDefault();codeListAction(clButton);return;}
    const prop=e.target.closest('[data-property]');if(prop){propertyModal(prop.dataset.property);return;}
    const action=e.target.closest('[data-action]');
    if(action){e.preventDefault();const a=action.dataset.action;if(a==='sources')sourcesModal();else if(a==='help')helpModal();else if(a==='copy-id')copyText(nodes[current].id);else if(a==='export')exportCurrent();return;}
    const tab=e.target.closest('[data-tab]');
    if(tab){if(tab.dataset.kind)propertyKind=tab.dataset.kind;location.hash=href(current,tab.dataset.tab);return;}
    const kind=e.target.closest('[data-kind]');if(kind){propertyKind=kind.dataset.kind;renderPage();return;}
    const link=e.target.closest('a[href^="#node="]');if(link&&$('#modal').open)$('#modal').close();
  });
  document.addEventListener('keydown',e=>{
    if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!$('#modal').open){e.preventDefault();$('#sidebar').classList.add('open');$('#search').focus();}
    if(e.key==='Escape'){$('#sidebar').classList.remove('open');$('#mobile-menu').setAttribute('aria-expanded','false');toggleOptions(false);}
    if(e.target.getAttribute('role')==='tab'&&['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){
      e.preventDefault();const list=[...document.querySelectorAll('[role=tab]')];let idx=list.indexOf(e.target);
      idx=e.key==='Home'?0:e.key==='End'?list.length-1:(idx+(e.key==='ArrowRight'?1:-1)+list.length)%list.length;
      list[idx].focus();list[idx].click();
    }
  });
  $('#search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(renderList,70);});
  $('#family').addEventListener('change',()=>{moduleOptions();renderList();});
  for(const id of ['module','category','technical','only-concrete','include-external'])$('#'+id).addEventListener('change',renderList);
  $('#filters-btn').addEventListener('click',()=>{const box=$('#extra-filters');box.hidden=!box.hidden;$('#filters-btn').setAttribute('aria-expanded',String(!box.hidden));});
  $('#home-link').addEventListener('click',e=>{e.preventDefault();location.hash=href(data.initialId);});
  $('#back-btn').addEventListener('click',()=>history.back());
  $('#forward-btn').addEventListener('click',()=>history.forward());
  $('#sources-btn').addEventListener('click',sourcesModal);
  $('#codelists-btn').addEventListener('click',()=>{location.hash='#view=codelists'+(level==='uml'?'&level=uml':'');});
  $('#options-btn').addEventListener('click',()=>toggleOptions($('#options-panel').hidden));
  darkQuery?.addEventListener?.('change',()=>{if(themeChoice==='system')applyTheme();});
  window.addEventListener('beforeunload',e=>{if(codeListsDirty){e.preventDefault();e.returnValue='';}});
  $('#about-btn').addEventListener('click',helpModal);
  $('#close-modal').addEventListener('click',()=>$('#modal').close());
  // Closing the details of a property takes it out of the URL: the same link opens them again.
  $('#modal').addEventListener('close',()=>{
    const params=new URLSearchParams(location.hash.slice(1));
    if(params.has('prop')){params.delete('prop');history.replaceState(null,'','#'+params.toString());}
  });
  $('#modal').addEventListener('click',e=>{if(e.target===$('#modal')){const r=$('#modal').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('#modal').close();}});
  $('#mobile-menu').addEventListener('click',()=>{const open=$('#sidebar').classList.toggle('open');$('#mobile-menu').setAttribute('aria-expanded',String(open));});
  $('#file-count').textContent=data.files.length;
  updateCodeListIndicator();applyTheme();applyFontScale();
  window.addEventListener('hashchange',route);
  moduleOptions();route();
})();
