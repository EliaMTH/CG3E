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
  const href = (id, tab='overview') => '#'+new URLSearchParams({node:id, tab}).toString();
  const fmt = n => new Intl.NumberFormat('it-IT').format(n);
  const standard = data.standard;
  const kinds = {feature:'Feature', object:'Oggetto (non feature)', datatype:'Tipo di dato', enumeration:'Enumerazione', codelist:'Code list', basictype:'Tipo base', union:'Unione', ade:'Punto di estensione ADE', external:'Riferimento esterno'};
  const kindNotes = {
    feature:'Discende da gml:AbstractFeature: oggetto con identità propria.',
    object:'Discende da gml:AbstractGML ma non da gml:AbstractFeature: ha identità (gml:id) ma non è una feature.',
    datatype:'Non discende da gml:AbstractGML: struttura di valori senza identità propria.',
    enumeration:'Tipo semplice con valori ammessi elencati nello schema.',
    codelist:'Vocabolario aperto definito nel modello concettuale (OGC 20-010); i valori sono definiti fuori dallo standard.',
    basictype:'Tipo base del modello concettuale (OGC 20-010).',
    union:'Unione del modello concettuale (OGC 20-010): il valore è uno dei tipi alternativi.',
    ade:'Aggancio per le estensioni di dominio (ADE).',
    external:'Riferimento senza definizione negli schemi locali.'};
  const roles = {space:['Spazio','Discende da core:AbstractSpace: oggetto che occupa o delimita un volume.'],
    boundary:['Superficie di confine','Discende da core:AbstractSpaceBoundary: superficie che delimita uno spazio.']};
  const links = {aggregation:['aggregazione','blue','Forma member (estende gml:AbstractFeatureMemberType): l’oggetto collegato è membro, cioè parte, di questo.'],
    association:['associazione','','Tipo …PropertyType: l’oggetto collegato può essere incluso o indicato con xlink:href.'],
    reference:['solo riferimento','amber','gml:ReferenceType: l’oggetto collegato è indicato soltanto con xlink:href.']};
  const displayName = n => n.family==='CityGML' ? n.name : (n.qname || n.name);
  const groups = {attribute:['Attributi e valori','teal'],association:['Relazioni','purple'],geometry:['Geometrie e LOD','blue'],ade:['Punti di estensione ADE','amber'],xmlAttribute:['Attributi XML','teal']};
  const tabs = {overview:'Panoramica',properties:'Proprietà',connections:'Connessioni',standard:'Standard',source:'Sorgente'};
  const docHref = anchor => standard ? standard.document.path+(anchor?'#'+anchor:'') : '#';
  const docLink = (anchor, label) => standard ? `<a href="${esc(docHref(anchor))}" target="_blank" rel="noopener">${esc(label)}</a>` : esc(label);
  const onlineLink = (anchor, label) => standard ? `<a href="${esc(standard.document.url+(anchor?'#'+anchor:''))}" target="_blank" rel="noopener">${esc(label)}</a>` : '';
  let current = data.initialId, activeTab = 'overview', inherited = true, propertyQuery = '', propertyKind = 'all';
  let previous = null, searchTimer = null, toastTimer = null;
  try { inherited = localStorage.getItem('cg-inherited') !== 'false'; } catch (_) {}
  const scroll = new Map();
  const byName = (a,b) => a.name.localeCompare(b.name, 'en', {sensitivity:'base'});
  const allNodes = Object.values(nodes).sort(byName);

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
  function linkBadge(p) {
    if (p.link==='aggregation' && p.aggregation==='composite')
      return '<span class="badge blue" title="Forma member nello schema; nel modello UML (XMI) è una composizione: la parte appartiene a un solo intero e non esiste senza di esso.">composizione</span>';
    const l=links[p.link];
    return l?`<span class="badge ${l[1]}" title="${esc(l[2])}">${l[0]}</span>`:'';
  }
  function categoryMatch(n, category) {
    if (!category) return true;
    if (category==='topLevel') return n.topLevel;
    if (category==='cityObject') return n.cityObject;
    if (category==='space' || category==='boundary') return n.spaceRole===category;
    return n.kind===category;
  }
  function properties(n, include=inherited) {
    const seen = new Set(), result = [];
    for (const id of [n.id,...(include ? n.ancestors || [] : [])]) {
      for (const p of nodes[id]?.properties || []) {
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
  function listItem(n) {
    return `<a href="${esc(href(n.id))}" class="concept-item ${current===n.id?'active':''}" ${current===n.id?'aria-current="page"':''} title="${esc(n.qname || n.name)}">${icon(n)}<span class="item-name">${esc(displayName(n))}</span>${n.abstract?'<span class="abstract-mark" title="Astratta">A</span>':''}</a>`;
  }
  function renderList() {
    const q=$('#search').value.trim().toLowerCase(), family=$('#family').value, mod=$('#module').value, category=$('#category').value;
    let matches=allNodes.filter(n=>allowed(n,family) && (!mod||n.module===mod) && categoryMatch(n,category)
      && ($('#technical').checked || (!n.technical && n.kind!=='ade'))
      && ($('#include-external').checked || !n.external)
      && (!$('#only-concrete').checked || (!n.abstract && !n.external && n.kind!=='ade'))
      && (!q || [n.name,n.label,n.qname].some(s=>(s||'').toLowerCase().includes(q))));
    $('#results-count').textContent=fmt(matches.length);
    const box=$('#concept-list'), pos=box.scrollTop;
    if (!matches.length) {
      box.innerHTML='<div class="list-empty">Nessun risultato.<br><br>Prova a cambiare gruppo di schemi o ad attivare i tipi tecnici nei filtri.</div>';
      return;
    }
    if (q) {
      const score=n=>n.name.toLowerCase()===q?0:n.name.toLowerCase().startsWith(q)?1:2;
      matches.sort((a,b)=>score(a)-score(b)||byName(a,b));
      box.innerHTML=matches.map(listItem).join('');
    } else {
      const order=['Building','Core','Construction','Transportation'];
      const mods=[...new Set(matches.map(n=>n.module))].sort((a,b)=>{
        const ai=order.indexOf(a),bi=order.indexOf(b);return(ai<0?99:ai)-(bi<0?99:bi)||a.localeCompare(b);
      });
      box.innerHTML=mods.map(m=>{
        const group=matches.filter(n=>n.module===m);
        return `<div class="module-group"><div class="module-label"><span>${esc(m)}</span><small>${group.length}</small></div>${group.map(listItem).join('')}</div>`;
      }).join('');
    }
    box.scrollTop=pos;
  }

  function chain(n) {
    if (!n.parents.length && !n.children.length && !n.restrictedBase) return '';
    const ids=[...(n.ancestors||[])].reverse();
    const body='<div class="chain">'+ids.map(a=>ref(a)+'<span class="arrow">›</span>').join('')+`<span class="current">${esc(displayName(n))}</span></div>`;
    return `<div class="inheritance-box"><div class="caption">EREDITARIETÀ DEI TIPI · XS:EXTENSION</div>${body}${n.restrictedBase?`<div class="tiny">Derivazione per restrizione: ${ref(n.restrictedBase)} (non espansa come estensione).</div>`:''}</div>`;
  }
  function propTable(props, n) {
    if (!props.length) return empty('Nessuna proprietà in questa sezione con i filtri correnti.');
    return `<div class="prop-table"><table><thead><tr><th>Proprietà</th><th>Tipo / destinazione</th><th>Occorrenze</th><th>Definita in</th></tr></thead><tbody>${props.map(p=>{
      const direct=p.declaredIn===n.id;
      const targets=(p.targets.length?p.targets.map(t=>ref(t,undefined,'prop-type')).join(''):'<span class="muted tiny">Non specificato</span>')
        +(p.codeList?`<div class="tiny muted" title="Code list del modello concettuale (OGC 20-010)">code list ${ref(p.codeList,undefined,'prop-type')}</div>`:'');
      return `<tr><td><button class="prop-name-button" data-property="${esc(p.id)}">${esc(p.name)}</button><div class="prop-description">${esc(p.description||'Nessuna descrizione nella sorgente.')}</div>${linkBadge(p)}${p.choices?.length?'<span class="badge amber" title="Campo in un gruppo xs:choice: le alternative non sono indipendenti">alternativa XML</span>':''}</td><td>${targets}</td><td><span class="multiplicity">${esc(p.multiplicity)}</span></td><td>${ref(p.declaredIn,undefined,'prop-origin '+(direct?'direct':''))}<div class="prop-origin-label">${direct?'diretta':'ereditata'}</div></td></tr>`;
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
    return section('Vincoli e struttura XML',cs.map(c=>`<div class="constraint"><div class="constraint-label">${esc(c.kind)} · ${ref(c.owner)}</div>${c.value!==undefined?`<code>${esc(c.value)}</code>`:''}${(c.targets||[]).map(id=>ref(id)).join(', ')}${c.description?`<div class="tiny muted">${esc(c.description)}</div>`:''}</div>`).join(''),cs.length);
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
  function codeListView(n) {
    let body=notice('Code list del modello concettuale (OGC 20-010). I valori non fanno parte dello standard: ogni dataset li prende da un dizionario esterno, indicato con l’attributo <code>codeSpace</code> del valore.','info');
    body+=literals(n);
    body+=section('Usata da',n.incoming.length?cardGrid(n.incoming.map(i=>i.source),'attributo che la usa'):empty('Nessun attributo degli schemi usa questa code list.'),n.incoming.length,esc(n.incoming.map(i=>i.property).filter((v,i,a)=>a.indexOf(v)===i).join(', ')));
    return body;
  }
  function overview(n) {
    if(n.kind==='codelist') return codeListView(n);
    const props=properties(n);
    const geom=props.filter(p=>p.kind==='geometry'), attrs=props.filter(p=>['attribute','xmlAttribute'].includes(p.kind)), rels=props.filter(p=>p.kind==='association'), ade=props.filter(p=>p.kind==='ade');
    let body=chain(n);
    if(n.external) body+=notice('Questa risorsa è referenziata dagli schemi, ma la sua definizione non è disponibile in sources/. I collegamenti noti sono mostrati; attributi e antenati mancanti non vengono inventati. <button class="text-button" data-action="sources">Vedi sorgenti</button>');
    else if(n.incompleteInheritance)body+=notice('La gerarchia raggiunge una definizione esterna non inclusa. Le proprietà qui elencate sono quelle ricavabili dagli schemi locali; l’ereditarietà non è completa. <a href="#" data-action="sources">Dettagli delle sorgenti</a>');
    if(props.length)body+=`<div class="stats-grid">${[[attrs,'Attributi e valori','teal','properties'],[rels,'Relazioni','purple','connections'],[geom,'Geometrie / LOD','blue','properties'],[ade,'Punti ADE','amber','properties']].map(([ps,label,color,tab])=>`<button class="stat-card" data-tab="${tab}" data-kind="${label==='Geometrie / LOD'?'geometry':label==='Punti ADE'?'ade':'all'}"><span class="stat-label"><i class="line-dot ${color}"></i>${label}</span><strong>${ps.length}</strong><small>${ps.filter(p=>p.declaredIn===n.id).length} dirette · ${ps.filter(p=>p.declaredIn!==n.id).length} ereditate</small></button>`).join('')}</div>`;
    if(attrs.length)body+=section('Attributi e valori',propTable(attrs,n),attrs.length,'Clicca sul nome per aprire i dettagli','01');
    if(rels.length)body+=section('Relazioni',propTable(rels,n),rels.length,'Destinazioni navigabili','02');
    body+=boundarySections(n)+literals(n);
    if(geom.length)body+=section('Geometrie e livelli di dettaglio',propTable(geom,n),geom.length,'LOD0 — LOD3','03');
    if(ade.length)body+=`<details class="section-collapse"><summary>Punti di estensione ADE <span class="count">${ade.length}</span></summary><div>${propTable(ade,n)}</div></details>`;
    body+=constraints(n);
    if(n.children.length)body+=section('Sottoclassi / tipi derivati',`<div class="connection-grid">${n.children.map(id=>card(id,'xs:extension')).join('')}</div>`,n.children.length);
    if(!props.length&&!n.constraints.length&&!n.literals?.length)body+=empty('Nessuna proprietà diretta o ereditata disponibile nel catalogo per questa risorsa. Consulta Connessioni e Sorgente.');
    return body;
  }
  function propertiesView(n) {
    return `<div class="property-toolbar"><input type="search" id="property-search" value="${esc(propertyQuery)}" placeholder="Filtra le proprietà..." aria-label="Filtra proprietà nella scheda"><div class="segment"><button data-kind="all" class="${propertyKind==='all'?'active':''}">Tutte</button>${Object.entries(groups).map(([k,[title]])=>`<button data-kind="${k}" class="${propertyKind===k?'active':''}">${title}</button>`).join('')}</div></div><div id="property-results">${propertyResults(n)}</div>`;
  }
  function propertyResults(n) {
    const query=propertyQuery.toLowerCase(),props=properties(n).filter(p=>(propertyKind==='all'||p.kind===propertyKind)&&(!query||(p.name+' '+p.description+' '+p.typeName).toLowerCase().includes(query)));
    return props.length?propSections(props,n):empty('Nessuna proprietà corrisponde ai filtri. '+(inherited?'':'Attiva le proprietà ereditate per includere le superclassi.'));
  }
  function connections(n) {
    let body='<div class="legend" style="margin-bottom:22px"><span>Associazione</span><span class="geom">Geometria</span><span class="ade">ADE</span></div>';
    body+=section('Superclasse / tipo base',n.parents.length?`<div class="connection-grid">${n.parents.map(id=>card(id,n.derivation)).join('')}</div>`:empty('Nessuna superclasse nominale dichiarata.'),n.parents.length);
    if(n.children.length)body+=section('Sottoclassi / tipi derivati',`<div class="connection-grid">${n.children.map(id=>card(id,'xs:extension')).join('')}</div>`,n.children.length);
    if(n.substitution)body+=section('Sostituzione XML',card(n.substitution,'substitutionGroup — non è l’ereditarietà del tipo'));
    const outgoing=properties(n).filter(p=>['association','geometry','ade'].includes(p.kind));
    if(outgoing.length)body+=section('Collegamenti in uscita',propTable(outgoing,n),outgoing.length);
    body+=boundarySections(n);
    if(n.incoming.length)body+=section('Chi fa riferimento a questo concetto',`<div class="connection-grid">${n.incoming.map(p=>card(p.source,p.property+(links[p.link]?' · '+links[p.link][0]:'')+(p.multiplicity?' · '+p.multiplicity:''))).join('')}</div>`,n.incoming.length,'Riferimenti diretti alla destinazione esatta');
    return body;
  }
  function requirementBlock(r) {
    return `<div class="constraint"><div class="constraint-label">${esc(r.title)} · ${docLink(r.anchor, r.id)}</div>${r.text.map(t=>`<div class="tiny">${esc(t)}</div>`).join('')}</div>`;
  }
  function standardView(n) {
    if(!standard) return empty('Il documento del modello concettuale non è presente nel catalogo.');
    if(n.family!=='CityGML') return empty('Questo concetto appartiene a uno schema importato: non fa parte del modello concettuale CityGML.');
    let body='';
    if(n.uml){
      body+=section('Classe nel modello concettuale',`<dl class="metadata-grid"><dt>Nome UML</dt><dd>${esc(n.uml.name)}${n.uml.name!==n.name?' <span class="muted">(nello schema: '+esc(n.name)+')</span>':''}</dd><dt>Stereotipo</dt><dd>«${esc(n.uml.stereotype)}»</dd><dt>Package</dt><dd>${esc(n.uml.package||'')}</dd>${n.kind==='feature'?`<dt>Primo livello</dt><dd>${n.topLevel?'Sì: può essere membro diretto di un CityModel':'No'}</dd>`:''}<dt>Dizionario dati</dt><dd>${n.uml.anchor?docLink(n.uml.anchor,'copia locale')+' · '+onlineLink(n.uml.anchor,'online'):'senza ancora nel documento'}</dd></dl>`);
    } else {
      body+=notice('Questo concetto esiste negli schemi XSD ma non ha una classe corrispondente nel modello concettuale.');
    }
    const chapter=standard.modules[n.module];
    if(chapter) body+=section('Capitolo del modulo',`<p>${docLink(chapter.anchor, chapter.number+' '+n.module)} · ${onlineLink(chapter.anchor,'online')}</p>`);
    body+=boundarySections(n);
    const reqs=standard.requirements.filter(r=>r.module===n.module.toLowerCase());
    if(reqs.length) body+=`<details class="section-collapse"><summary>Requisiti del modulo ${esc(n.module)} <span class="count">${reqs.length}</span></summary><div>${reqs.map(requirementBlock).join('')}</div></details>`;
    return body;
  }
  function fileInfo(path) {
    return data.files.find(f=>f.path===path);
  }
  function sourceView(n) {
    if(n.umlOnly) return section('Provenienza',`<dl class="metadata-grid"><dt>Identificatore</dt><dd>${esc(n.id)}</dd><dt>Fonte</dt><dd>${esc(standard.document.title)} (OGC ${esc(standard.document.documentNumber)}, versione ${esc(standard.document.version)})</dd><dt>Scheda</dt><dd>${n.uml.anchor?docLink(n.uml.anchor,'dizionario dati, copia locale')+' · '+onlineLink(n.uml.anchor,'online'):'—'}</dd><dt>Negli schemi XSD</dt><dd>Nessun elemento corrispondente: la codifica GML non rappresenta questa classe.</dd></dl>`);
    const file=fileInfo(n.source[0]);
    let body=section('Provenienza',`<dl class="metadata-grid"><dt>Identificatore</dt><dd>${esc(n.id)}</dd><dt>Namespace</dt><dd>${esc(n.namespace||'')}</dd>${n.xmlType?`<dt>Tipo XML</dt><dd>${esc(n.xmlType)}</dd>`:''}<dt>File</dt><dd>${n.source.length?n.source.map(p=>sourceLink(p)).join('<br>'):'Definizione non disponibile localmente'}</dd>${n.line?`<dt>Riga</dt><dd>${n.line}</dd>`:''}${file?.url?`<dt>URL ufficiale</dt><dd>${sourceLink(file.url)}</dd><dt>Versione schema</dt><dd>${esc(file.schemaVersion||'non dichiarata')}</dd><dt>Scaricato il</dt><dd>${esc(file.retrievedAt.slice(0,10))}</dd>`:''}<dt>Stato</dt><dd>${n.external?'Solo riferimento esterno':n.builtin?'Tipo predefinito':'Dichiarazione disponibile'}</dd></dl>`);
    if(n.xml)body+=section('Dichiarazione XML Schema',`<pre class="source-block"><code>${esc(n.xml)}</code></pre>`,'','Estratto dello schema ufficiale');
    body+=constraints(n);
    return body;
  }
  function renderPage(reset=false) {
    const n=nodes[current];
    if(!n) {
      $('#content').innerHTML=empty('Identificatore non presente nel catalogo. '+ref(data.initialId,'Torna a Building'));
      $('#breadcrumb').textContent='Risorsa non trovata';return;
    }
    const props=properties(n);
    document.title=n.name+' · CityGML Explorer';
    $('#breadcrumb').innerHTML=`<b>${esc(n.module)}</b><span>/</span>${esc(n.name)}`;
    $('#content').innerHTML=`<article class="page"><div class="eyebrow"><span>${esc(n.family)}</span><span class="slash">/</span><span>${esc(n.module)}</span><span class="slash">/</span><span>${n.umlOnly?'UML':'XSD'}</span></div><div class="hero"><div><h1>${esc(n.name)}</h1><div class="hero-subtitle"><code>${esc(n.qname||n.name)}</code><button class="icon-button" data-action="copy-id" aria-label="Copia identificatore" title="Copia identificatore">&#10697;</button></div></div><div class="hero-actions"><button class="text-button" data-action="export">Esporta JSON ↗</button><button class="text-button" data-tab="source">&lt;/&gt; Sorgente</button></div></div><div class="badges"><span class="badge teal" title="${esc(kindNotes[n.kind]||'')}">${esc(kinds[n.kind]||n.kind)}</span>${['feature','object','datatype'].includes(n.kind)&&!n.technical&&!n.umlOnly?`<span class="badge">${n.abstract?'Astratta':'Concreta'}</span>`:''}${n.topLevel?'<span class="badge teal" title="«TopLevelFeatureType» in OGC 20-010: può essere membro diretto di un CityModel.">Primo livello</span>':''}${n.uml?`<span class="badge" title="Stereotipo UML (OGC 20-010)">«${esc(n.uml.stereotype)}»</span>`:''}${n.umlOnly?'<span class="badge amber" title="Definito nel modello concettuale; la codifica XSD non ha un elemento corrispondente.">Solo nel modello UML</span>':''}${n.cityObject?'<span class="badge blue" title="Discende da core:AbstractCityObject.">Oggetto di città</span>':''}${n.spaceRole?`<span class="badge blue" title="${esc(roles[n.spaceRole][1])}">${roles[n.spaceRole][0]}</span>`:''}${n.umlOnly?'':`<span class="badge">${esc(n.xmlType||'XML Schema')}</span>`}${n.external?'<span class="badge amber">Definizione non disponibile</span>':''}${n.technical?'<span class="badge">Tipo tecnico</span>':''}</div><p class="definition ${n.description?'':'empty'}">${esc(n.description || 'Nessuna definizione testuale disponibile nello schema.')}</p><div class="tabbar" role="tablist" aria-label="Sezioni della scheda">${Object.entries(tabs).map(([id,label])=>`<button class="tab ${activeTab===id?'active':''}" data-tab="${id}" id="tab-${id}" role="tab" aria-selected="${activeTab===id}" aria-controls="tab-content">${label}${id==='properties'?`<span class="count">${props.length}</span>`:''}</button>`).join('')}<label class="inherited-control"><span class="switch"><input type="checkbox" id="inherited" ${inherited?'checked':''} aria-label="Mostra proprietà ereditate"><span></span></span>Includi ereditate</label></div><div class="tab-content" id="tab-content" role="tabpanel" aria-labelledby="tab-${activeTab}">${activeTab==='overview'?overview(n):activeTab==='properties'?propertiesView(n):activeTab==='connections'?connections(n):activeTab==='standard'?standardView(n):sourceView(n)}</div><footer class="page-footer"><span>Codifica XML di CityGML 3.0 e modello concettuale OGC 20-010</span><span>${n.source.length} ${n.source.length===1?'sorgente locale':'sorgenti locali'}</span><a href="#" data-action="help">Guida alla lettura ↗</a></footer></article>`;
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
    const next=params.get('node')||data.initialId,tab=params.get('tab');
    if(next!==current){propertyQuery='';propertyKind='all';}
    current=next;activeTab=Object.hasOwn(tabs,tab)?tab:'overview';
    previous=current+'|'+activeTab;
    renderList();renderPage(true);
    $('#sidebar').classList.remove('open');$('#mobile-menu').setAttribute('aria-expanded','false');
  }
  function standardSources() {
    if(!standard) return '';
    const d=standard.document, u=standard.umlModel, r=standard.report;
    const labels={xsdWithoutUml:'Concetti XSD senza classe UML',propertiesWithoutUml:'Proprietà XSD senza attributo o ruolo UML',associationsWithoutXmi:'Relazioni XSD senza associazione nell’XMI',spacesWithoutBoundaryTable:'Spazi concreti senza tabella dei confini',boundaryRowsWithoutXsd:'Righe delle tabelle dei confini senza classe XSD',boundaryClassesWithoutXsd:'Superfici delle tabelle senza classe XSD'};
    const report=Object.entries(r).map(([k,v])=>`<div class="constraint"><div class="constraint-label">${esc(labels[k]||k)} · ${v.length}</div>${v.length?`<div class="tiny">${esc(v.join(', '))}</div>`:''}</div>`).join('');
    return `<h3>Modello concettuale</h3><table class="source-table"><thead><tr><th>Fonte</th><th>Versione</th><th>Scaricato il</th><th>SHA-256 (inizio)</th></tr></thead><tbody><tr><td>${sourceLink(d.path,d.title)}<div class="tiny muted">OGC ${esc(d.documentNumber)} · approvato ${esc(d.approvalDate||'')} · pubblicato ${esc(d.publicationDate||'')} · ${sourceLink(d.url,'online')}</div></td><td>${esc(d.version||'—')}</td><td>${esc(d.retrievedAt.slice(0,10))}</td><td><code title="${esc(d.sha256)}">${d.sha256.slice(0,12)}…</code></td></tr>${u?`<tr><td>${sourceLink(u.path,'Modello UML (XMI)')}<div class="tiny muted">${esc(u.member)} · commit <code>${esc((u.commit||'').slice(0,12))}</code> · ${sourceLink(u.url,'online')}</div></td><td>3.0</td><td>${esc(u.retrievedAt.slice(0,10))}</td><td><code title="${esc(u.sha256)}">${u.sha256.slice(0,12)}…</code></td></tr>`:''}</tbody></table><p class="tiny muted">Dal documento: stereotipi, oggetti di primo livello, code list, tipi UML degli attributi, valori delle enumerazioni, superfici di confine ammesse, requisiti. Dall’XMI: composizione o aggregazione delle relazioni. Le corrispondenze con gli schemi sono per nome; le differenze sono elencate qui sotto.</p><details class="section-collapse"><summary>Confronto fra schemi XSD e modello concettuale</summary><div>${report}</div></details>`;
  }
  function sourcesModal() {
    const unique=Object.values(Object.fromEntries(data.dependencies.map(d=>[d.url,d])));
    const missing=unique.filter(d=>d.status==='missing');
    const rows=files=>files.map(f=>`<tr><td>${sourceLink(f.path,f.path.replace(/^sources\//,''))}</td><td>${esc(f.schemaVersion||'—')}</td><td>${esc((f.retrievedAt||'').slice(0,10))}</td><td><code title="${esc(f.sha256)}">${f.sha256.slice(0,12)}…</code></td></tr>`).join('');
    const table=files=>`<table class="source-table"><thead><tr><th>File</th><th>Versione</th><th>Scaricato il</th><th>SHA-256 (inizio)</th></tr></thead><tbody>${rows(files)}</tbody></table>`;
    showModal('Sorgenti',`<div class="stats-grid"><div class="stat-card"><span class="stat-label">Schemi CityGML 3.0</span><strong>${data.stats.citygmlFiles}</strong></div><div class="stat-card"><span class="stat-label">Schemi importati</span><strong>${data.stats.dependencyFiles}</strong></div><div class="stat-card"><span class="stat-label">Import non risolti</span><strong>${missing.length}</strong></div><div class="stat-card"><span class="stat-label">Riferimenti senza definizione</span><strong>${data.stats.external}</strong></div></div>${missing.length?notice('Alcuni import non sono presenti in <code>sources/</code>. Esegui <code>python scripts/fetch_sources.py</code> e poi <code>python scripts/build_catalog.py</code>.'):notice('Tutti gli import degli schemi sono presenti in <code>sources/</code>: il catalogo è consultabile offline.','info')}${missing.length?`<h3>Import non risolti</h3><table class="source-table"><thead><tr><th>Dipendenza</th><th>Richiesta da</th></tr></thead><tbody>${missing.map(d=>`<tr><td class="url"><a href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener">${esc(d.url)}</a></td><td>${esc(d.from)}</td></tr>`).join('')}</tbody></table>`:''}<h3>CityGML 3.0</h3>${table(data.files.filter(f=>f.citygml))}<h3>Schemi importati (GML, ISO 19139, XLink, XML)</h3>${table(data.files.filter(f=>!f.citygml))}${standardSources()}<p>URL di origine, date e hash completi: ${sourceLink('sources/manifest.json','sources/manifest.json')}. Versioni e fonti sono descritte nel ${sourceLink('README.md','README')}.</p>`);
  }
  function helpModal() {
    showModal('Come leggere il catalogo',`<p>Cerca un concetto a sinistra, apri la scheda e segui i nomi cliccabili. La pagina funziona offline: legge un indice preparato dagli schemi XSD ufficiali nella cartella <code>sources/</code>.</p><h3>Ereditarietà e associazioni</h3><p>Le proprietà ereditate provengono soltanto da <code>xs:extension</code>. Le associazioni, i punti ADE e <code>substitutionGroup</code> non trasferiscono attributi. Per una <code>xs:restriction</code> viene mostrata la struttura dichiarata, senza espandere automaticamente il tipo base.</p><h3>Proprietà</h3><p>Attributi e valori è una categoria di lettura: molti sono <code>xs:element</code>, non <code>xs:attribute</code>. Le occorrenze includono i gruppi contenitori; un campo in <code>xs:choice</code> resta un’alternativa, non un requisito indipendente. Il codice XML rimane la fonte da verificare.</p><h3>Categorie</h3><p>Le categorie derivano dalla gerarchia <code>xs:extension</code>. <strong>Feature</strong>: discende da <code>gml:AbstractFeature</code>. <strong>Oggetto (non feature)</strong>: discende da <code>gml:AbstractGML</code> ma non da <code>gml:AbstractFeature</code>. <strong>Tipo di dato</strong>: nessuna delle due, quindi senza identità propria. Gli <strong>oggetti di città</strong> discendono da <code>core:AbstractCityObject</code>; fra questi gli <strong>spazi</strong> discendono da <code>core:AbstractSpace</code> e le <strong>superfici di confine</strong> da <code>core:AbstractSpaceBoundary</code>.</p><h3>Relazioni</h3><p>Una proprietà è una relazione quando la destinazione è una feature o un oggetto; verso un tipo di dato è un attributo. La forma XML indica il tipo di collegamento: <strong>aggregazione</strong> se il tipo estende <code>gml:AbstractFeatureMemberType</code> (l’oggetto collegato è parte di questo), <strong>solo riferimento</strong> se il tipo è <code>gml:ReferenceType</code>, <strong>associazione</strong> negli altri casi.</p><h3>Modello concettuale</h3><p>La scheda <strong>Standard</strong> e i badge «stereotipo», <strong>Primo livello</strong> e <strong>Solo nel modello UML</strong> provengono dal documento OGC 20-010 (CityGML 3.0 Part 1: Conceptual Model); le <strong>superfici di confine ammesse</strong> dalle sue tabelle <code>/req/&lt;modulo&gt;/boundaries</code>; la distinzione fra <strong>composizione</strong> e aggregazione dal modello UML (XMI). Le <strong>code list</strong> hanno un nome e una definizione nello standard, ma i loro valori sono definiti da dizionari esterni.</p>${standard?`<h3>Concetti dello standard</h3><p class="tiny muted">Capitolo 6 del documento, copia locale.</p><ul class="concept-links">${standard.concepts.map(c=>`<li class="level-${c.level}">${docLink(c.anchor,c.number+' '+c.title)}</li>`).join('')}</ul>`:''}<h3>Stato delle sorgenti</h3><p>La sigla <strong>est.</strong> indica una definizione non presente in <code>sources/</code>. Il browser non inventa le proprietà mancanti.</p><h3>Legenda</h3><div class="legend"><span>F: feature</span><span>O: oggetto (non feature)</span><span class="geom">T: tipo di dato, enumerazione, tipo base o unione</span><span class="geom">L: code list</span><span class="ade">+: punto ADE</span></div><p>I concetti degli schemi importati sono mostrati con il prefisso del namespace, per esempio <code>gml:AbstractFeature</code>.</p><p>Premi <kbd>/</kbd> per cercare. I pulsanti Indietro/Avanti e la cronologia del browser seguono i concetti. Ogni scheda ha un URL con identificatore e sezione.</p><p>${sourceLink('README.md','Apri il README del progetto')}</p>`);
  }
  function propertyModal(id) {
    const prop=properties(nodes[current],true).find(p=>p.id===id);
    if(!prop)return;
    showModal(prop.name,`<p>${esc(prop.description||'Nessuna descrizione nella sorgente.')}</p><dl class="metadata-grid"><dt>Tipo XML</dt><dd>${esc(prop.xmlKind)}</dd><dt>Nome</dt><dd>${esc(prop.qname||prop.name)}</dd><dt>Tipo dichiarato</dt><dd>${prop.typeId?ref(prop.typeId,prop.typeName):esc(prop.typeName)}</dd><dt>Destinazione</dt><dd>${prop.targets.map(t=>ref(t)).join(', ')||'Non specificata'}</dd>${prop.umlType?`<dt>Tipo UML</dt><dd>${prop.umlTypeId?ref(prop.umlTypeId,prop.umlType):esc(prop.umlType)}${prop.codeList?' (code list)':''}</dd>`:''}${prop.aggregation?`<dt>Aggregazione UML</dt><dd>${esc({composite:'composizione',shared:'aggregazione',none:'associazione semplice'}[prop.aggregation])} (XMI)</dd>`:''}<dt>Occorrenze</dt><dd>${esc(prop.multiplicity)}${prop.choices?.length?' — campo alternativo in xs:choice':''}</dd><dt>Definita in</dt><dd>${ref(prop.declaredIn)}</dd><dt>Sorgente</dt><dd>${sourceLink(prop.source)}${prop.line?' : '+prop.line:''}</dd><dt>Nillable</dt><dd>${prop.nillable?'Sì':'No / non dichiarato'}</dd><dt>Default / fixed</dt><dd>${esc(prop.default??'—')} / ${esc(prop.fixed??'—')}</dd><dt>Risoluzione</dt><dd>${esc((prop.targetEvidence||[]).join('; ')||'Tipo dichiarato')}</dd></dl><pre class="source-block"><code>${esc(prop.xml||'')}</code></pre>`);
  }
  function exportCurrent() {
    const n=nodes[current], payload={schemaVersion:data.schemaVersion,sourceVersion:data.sourceVersion,concept:n,visibleProperties:properties(n),includeInherited:inherited,notes:'CityGML 3.0: structure from the XSD encoding (OGC 21-006r2), conceptual model information from OGC 20-010 and its UML model.'};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=n.name.replace(/[^a-z0-9_-]/gi,'_')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    showToast('Scheda esportata in JSON');
  }

  document.addEventListener('click',e=>{
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
    if(e.key==='Escape'){$('#sidebar').classList.remove('open');$('#mobile-menu').setAttribute('aria-expanded','false');}
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
  $('#about-btn').addEventListener('click',helpModal);
  $('#close-modal').addEventListener('click',()=>$('#modal').close());
  $('#modal').addEventListener('click',e=>{if(e.target===$('#modal')){const r=$('#modal').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('#modal').close();}});
  $('#mobile-menu').addEventListener('click',()=>{const open=$('#sidebar').classList.toggle('open');$('#mobile-menu').setAttribute('aria-expanded',String(open));});
  $('#file-count').textContent=data.files.length;
  window.addEventListener('hashchange',route);
  moduleOptions();route();
})();
