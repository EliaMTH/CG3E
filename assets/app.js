/* CityGML Explorer - no framework, no CDN, no runtime network requests. */
'use strict';
(() => {
  const $ = s => document.querySelector(s);
  const data = window.CITYGML_CATALOG;
  if (!data || !data.nodes) {
    $('#content').innerHTML = '<div class="empty-state">Catalogo non trovato. Mantieni data/catalog.js accanto alla pagina, oppure esegui build_citygml.py o build_citygml_owl.py.</div>';
    return;
  }
  const nodes = data.nodes;
  const isFull = data.mode === 'full';
  const modeLabel = isFull ? 'CityGML + OWL' : 'Solo CityGML';
  document.title = 'CityGML Explorer - ' + modeLabel;
  const modeElement = document.getElementById('catalog-mode');
  if (modeElement) modeElement.textContent = modeLabel;
  if (!isFull) {
    const familySelect = document.getElementById('family');
    for (const option of Array.from(familySelect.options)) {
      if (['UISH', 'CityOWL'].includes(option.value)) option.remove();
    }
    familySelect.options[0].text = 'CityGML';
  }

  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeUrl = u => /^(https?:\/\/|sources\/|README\.md$)/.test(u || '') ? u : '#';
  const href = (id, tab='overview') => '#'+new URLSearchParams({node:id, tab}).toString();
  const fmt = n => new Intl.NumberFormat('it-IT').format(n);
  const kinds = {class:'Classe', datatype:'Tipo di dato', enumeration:'Enumerazione', ade:'Punto di estensione ADE', external:'Riferimento esterno',objectProperty:'Object property',dataProperty:'Datatype property',annotationProperty:'Annotation property',individual:'Individuo'};
  const groups = {attribute:['Attributi e valori','teal'],association:['Relazioni','purple'],geometry:['Geometrie e LOD','blue'],ade:['Punti di estensione ADE','amber'],xmlAttribute:['Attributi XML','teal']};
  const tabs = {overview:'Panoramica',properties:'Propriet\u00e0',connections:'Connessioni',source:'Sorgente'};
  let current = data.initialId, activeTab = 'overview', inherited = true, propertyQuery = '', propertyKind = 'all';
  let previous = null, searchTimer = null, toastTimer = null;
  try { inherited = localStorage.getItem('cg-inherited') !== 'false'; } catch (_) {}
  const scroll = new Map();
  const byName = (a,b) => a.name.localeCompare(b.name, 'en', {sensitivity:'base'});
  const allNodes = Object.values(nodes).sort(byName);

  function ref(id, label, className='') {
    const n = nodes[id];
    if (!n) return '<span class="muted">'+esc(label || id || 'Non specificato')+'</span>';
    return `<a class="${className} ${n.external?'external':''}" href="${esc(href(id))}" title="${esc(n.qname || n.iri || n.name)}">${esc(label || n.name)}</a>${n.external?'<span class="external-tag" title="Definizione non disponibile localmente">est.</span>':''}`;
  }
  function icon(n) {
    const css = n.format==='OWL' ? 'owl' : n.kind==='ade' ? 'ade' : ['datatype','enumeration'].includes(n.kind)?'datatype':'';
    const glyph = n.external?'?':n.kind==='ade'?'+':n.kind.includes('Property')?'P':['datatype','enumeration'].includes(n.kind)?'T':n.format==='OWL'?'O':'C';
    return `<span class="type-icon ${css}" aria-hidden="true">${glyph}</span>`;
  }
  function properties(n, include=inherited) {
    const seen = new Set(), result = [];
    for (const id of [n.id,...(include ? n.ancestors || [] : [])]) {
      for (const p of nodes[id]?.properties || []) {
        const key = p.propertyId || (p.qname+'|'+p.xmlKind);
        if (seen.has(key)) continue;
        seen.add(key); result.push(p);
      }
    }
    return result;
  }
  function activeCount(n, kind) { return properties(n).filter(p=>p.kind===kind).length; }
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
    return family==='all' || (family==='curated' ? ['CityGML','UISH'].includes(n.family) : n.family===family);
  }
  function moduleOptions() {
    const selected=$('#module').value, family=$('#family').value;
    const mods=[...new Set(allNodes.filter(n=>allowed(n,family)).map(n=>n.module))].sort();
    $('#module').innerHTML='<option value="">Tutti i moduli</option>'+mods.map(m=>`<option value="${esc(m)}">${esc(m)}</option>`).join('');
    if (mods.includes(selected)) $('#module').value=selected;
  }
  function listItem(n) {
    return `<a href="${esc(href(n.id))}" class="concept-item ${current===n.id?'active':''}" ${current===n.id?'aria-current="page"':''} title="${esc(n.label!==n.name?n.name+' \u00b7 '+n.label:n.name)}">${icon(n)}<span class="item-name">${esc(n.label!==n.name&&n.module==='Unit Ontology'?n.label:n.name)}</span>${n.abstract?'<span class="abstract-mark" title="Astratta">A</span>':''}</a>`;
  }
  function renderList() {
    const q=$('#search').value.trim().toLowerCase(), family=$('#family').value, mod=$('#module').value;
    let matches=allNodes.filter(n=>allowed(n,family) && (!mod||n.module===mod)
      && ($('#technical').checked || (!n.technical && n.kind!=='ade'))
      && ($('#include-external').checked || !n.external)
      && (!$('#only-concrete').checked || (n.kind==='class' && !n.abstract && !n.external))
      && (!q || [n.name,n.label,n.qname,n.iri].some(s=>(s||'').toLowerCase().includes(q))));
    $('#results-count').textContent=fmt(matches.length);
    const box=$('#concept-list'), pos=box.scrollTop;
    if (!matches.length) {
      box.innerHTML='<div class="list-empty">Nessun risultato.<br><br>Prova a cambiare vocabolario o ad attivare i tipi tecnici nei filtri.</div>';
      return;
    }
    if (q) {
      const score=n=>n.name.toLowerCase()===q?0:n.name.toLowerCase().startsWith(q)?1:2;
      matches.sort((a,b)=>score(a)-score(b)||byName(a,b));
      box.innerHTML=matches.map(listItem).join('');
    } else {
      const order=['Building','Core','Construction','Transportation','UISH Building','UISH Sensors'];
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
    // Multi-parent OWL hierarchies are shown as sets, never as an invented linear chain.
    const multiparent = n.parents.length>1 || (n.ancestors||[]).some(a=>nodes[a]?.parents.length>1);
    let body;
    if (multiparent) {
      body=`<div class="chain"><span class="current">${esc(n.name)}</span><span class="arrow">\u2192</span>${n.parents.map(p=>ref(p)).join('<span class="arrow">+</span>')}</div>`;
      if (inherited) body+=`<div class="tiny muted" style="margin-top:8px">Antenati raggiungibili: ${(n.ancestors||[]).map(a=>ref(a)).join(', ')}</div>`;
    } else {
      const ids=[...(n.ancestors||[])].reverse();
      body='<div class="chain">'+ids.map(a=>ref(a)+'<span class="arrow">\u203a</span>').join('')+`<span class="current">${esc(n.name)}</span></div>`;
    }
    const label=n.format==='OWL'?'GERARCHIA RDFS \u00b7 SOTTOCLASSI NOMINALI':'EREDITARIET\u00c0 DEI TIPI \u00b7 XS:EXTENSION';
    return `<div class="inheritance-box"><div class="caption">${label}</div>${body}${n.restrictedBase?`<div class="tiny">Derivazione per restrizione: ${ref(n.restrictedBase)} (non espansa come estensione).</div>`:''}</div>`;
  }
  function propTable(props, n) {
    if (!props.length) return empty('Nessuna propriet\u00e0 in questa sezione con i filtri correnti.');
    const isOWL=n.format==='OWL';
    return `<div class="prop-table"><table><thead><tr><th>Propriet\u00e0</th><th>${isOWL?'Range dichiarato':'Tipo / destinazione'}</th><th>${isOWL?'Vincolo':'Occorrenze'}</th><th>${isOWL?'Dominio dichiarato':'Definita in'}</th></tr></thead><tbody>${props.map(p=>{
      const direct=p.declaredIn===n.id;
      const targets=p.targets.length?p.targets.map(t=>ref(t,undefined,'prop-type')).join(''):'<span class="muted tiny">Non specificato</span>';
      const cardinal=p.multiplicity===null?'<span class="muted tiny">'+(p.functional?'Funzionale':'Non specificato')+'</span>':`<span class="multiplicity">${esc(p.multiplicity)}</span>`;
      const label=p.propertyId?ref(p.propertyId,p.name,'prop-name'):`<button class="prop-name-button" data-property="${esc(p.id)}">${esc(p.name)}</button>`;
      return `<tr><td>${label}<div class="prop-description">${esc(p.description||'Nessuna descrizione nella sorgente.')}</div>${p.choices?.length?'<span class="badge amber" title="Campo in un gruppo xs:choice: le alternative non sono indipendenti">alternativa XML</span>':''}</td><td>${targets}${(p.rangeExpressions||[]).map(expression).join('')}</td><td>${cardinal}</td><td>${ref(p.declaredIn,undefined,'prop-origin '+(direct?'direct':''))}<div class="prop-origin-label">${direct?(isOWL?'dominio esplicito':'diretta'):(isOWL?'dominio di una superclasse':'ereditata')}</div></td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function propSections(props, n, all=false) {
    return Object.entries(groups).filter(([k])=>all||props.some(p=>p.kind===k)).map(([k,[title]])=>{
      const ps=props.filter(p=>p.kind===k);if(!ps.length)return'';
      const sub=k==='geometry'?'Propriet\u00e0 spaziali, non CRS separati per LOD':k==='ade'?'Meccanismi di estensione, non sottoclassi dell\u2019oggetto':n.format==='OWL'?'Dichiarazioni esplicite \u00b7 nessun reasoning':'Nome XML, tipo, molteplicit\u00e0 e provenienza';
      return section(title,propTable(ps,n),ps.length,sub);
    }).join('');
  }
  function card(id, role, css='') {
    const n=nodes[id];if(!n)return'';
    return `<a class="connection-card ${css}" href="${esc(href(id))}"><span class="conn-icon">${n.external?'?':n.format==='OWL'?'O':'C'}</span><span class="conn-content"><strong>${esc(n.name)}</strong><small>${esc(role)}${n.external?' \u00b7 definizione esterna':''}</small></span><span class="conn-arrow" aria-hidden="true">\u2197</span></a>`;
  }
  function extensions(n) {
    const paths=[];
    for(const p of properties(n)) {
      if(p.kind!=='ade')continue;
      for(const target of p.targets) {
        for(const bridge of nodes[target]?.bridges||[]) {
          for(const child of nodes[bridge.target]?.children||[]) {
            paths.push({id:child,via:p.name+' \u2192 '+nodes[target].name});
          }
        }
      }
    }
    if(!paths.length)return'';
    return section('Estensioni ontologiche collegate',`<div class="connection-grid">${paths.map(p=>card(p.id,p.via,'owl-card')).join('')}</div><p class="tiny muted">Collegamento di navigazione XSD\u2013OWL configurato esplicitamente. Le propriet\u00e0 OWL non vengono aggiunte al tipo XML.</p>`,paths.length,'UISH / OWL');
  }
  function expression(e) {
    if(!e)return'';
    if(e.ref)return ref(e.ref);
    if(e.literal!==undefined)return `<code>${esc(e.literal)}</code>${e.language?`<span class="tiny muted"> @${esc(e.language)}</span>`:''}`;
    if(e.note)return `<span class="muted tiny">${esc(e.note)}</span>`;
    if(e.expression)return '<div class="expr">'+e.expression.map(x=>`<div class="expr-row"><span class="expr-key">${esc(x.predicate)}</span>${x.items?x.items.map(expression).join(' \u00b7 '):expression(x.value)}</div>`).join('')+'</div>';
    return '';
  }
  function axioms(n, includeAll=false) {
    const ids=[n.id,...(inherited?n.ancestors||[]:[])];
    const items=ids.flatMap(id=>(nodes[id]?.axioms||[]).map(a=>({...a,owner:id})));
    if(!items.length)return'';
    return section('Assiomi e restrizioni OWL',items.map(a=>`<div class="axiom"><div class="axiom-label">${esc(a.predicate.split('#').pop())} \u00b7 ${ref(a.owner)}</div>${expression(a.value)}</div>`).join(''),items.length,'Struttura RDF esplicita, non inferenze');
  }
  function owlProperty(n) {
    if(!n.kind.includes('Property'))return'';
    const domains=n.domains||[],ranges=n.ranges||[];
    return section('Definizione della propriet\u00e0',`<dl class="metadata-grid"><dt>IRI</dt><dd>${esc(n.iri)}</dd><dt>Domain</dt><dd>${domains.length?domains.map(expression).join('<br>'):'Non specificato'}</dd><dt>Range</dt><dd>${ranges.length?ranges.map(expression).join('<br>'):'Non specificato'}</dd><dt>Funzionale</dt><dd>${n.functional?'S\u00ec, dichiarato owl:FunctionalProperty':'Non dichiarato'}</dd><dt>Subproperty of</dt><dd>${(n.superProperties||[]).map(id=>ref(id)).join(', ')||'Nessuna dichiarazione'}</dd><dt>Inverse of</dt><dd>${(n.inverseOf||[]).map(id=>ref(id)).join(', ')||'Nessuna dichiarazione'}</dd></dl>`);
  }
  function constraints(n) {
    const cs=[n.id,...(inherited?n.ancestors||[]:[])].flatMap(id=>(nodes[id]?.constraints||[]).map(c=>({...c,owner:id})));
    if(!cs.length)return'';
    return section('Vincoli e struttura XML',cs.map(c=>`<div class="axiom"><div class="axiom-label">${esc(c.kind)} \u00b7 ${ref(c.owner)}</div>${c.value!==undefined?`<code>${esc(c.value)}</code>`:''}${(c.targets||[]).map(id=>ref(id)).join(', ')}${c.description?`<div class="tiny muted">${esc(c.description)}</div>`:''}</div>`).join(''),cs.length);
  }
  function overview(n) {
    const props=properties(n);
    const geom=props.filter(p=>p.kind==='geometry'), attrs=props.filter(p=>['attribute','xmlAttribute'].includes(p.kind)), rels=props.filter(p=>p.kind==='association'), ade=props.filter(p=>p.kind==='ade');
    let body=chain(n);
    if(n.external) body+=notice('Questa risorsa \u00e8 referenziata dai file, ma la sua definizione non \u00e8 disponibile localmente. I collegamenti noti sono mostrati; attributi e antenati mancanti non vengono inventati. <button class="text-button" data-action="sources">Vedi dipendenze</button>');
    else if(n.incompleteInheritance)body+=notice('La gerarchia raggiunge una definizione esterna non inclusa. Le propriet\u00e0 qui elencate sono quelle ricavabili dai file locali; l\u2019ereditariet\u00e0 non \u00e8 completa. <a href="#" data-action="sources">Dettagli delle sorgenti</a>');
    if(n.format==='OWL')body+=notice('Vista delle dichiarazioni OWL: domain e range non sono campi obbligatori n\u00e9 una lista chiusa di propriet\u00e0 ammesse. Le restrizioni restano separate; nessun reasoner \u00e8 attivo.','purple');
    if(props.length)body+=`<div class="stats-grid">${[[attrs,'Attributi e valori','teal','properties'],[rels,'Relazioni','purple','connections'],[geom,'Geometrie / LOD','blue','properties'],[ade,'Punti ADE','amber','properties']].map(([ps,label,color,tab])=>`<button class="stat-card" data-tab="${tab}" data-kind="${label==='Geometrie / LOD'?'geometry':label==='Punti ADE'?'ade':'all'}"><span class="stat-label"><i class="line-dot ${color}"></i>${label}</span><strong>${ps.length}</strong><small>${ps.filter(p=>p.declaredIn===n.id).length} dirette \u00b7 ${ps.filter(p=>p.declaredIn!==n.id).length} ereditate</small></button>`).join('')}</div>`;
    body+=extensions(n)+owlProperty(n);
    if(attrs.length)body+=section(n.format==='OWL'?'Propriet\u00e0 di dato con dominio':'Attributi e valori',propTable(attrs,n),attrs.length,'Clicca sul nome per aprire i dettagli','01');
    if(rels.length)body+=section(n.format==='OWL'?'Propriet\u00e0 oggetto con dominio':'Relazioni',propTable(rels,n),rels.length,'Destinazioni navigabili','02');
    if(geom.length)body+=section('Geometrie e livelli di dettaglio',propTable(geom,n),geom.length,'LOD0 \u2014 LOD3','03');
    if(ade.length)body+=`<details class="section-collapse"><summary>Punti di estensione ADE <span class="count">${ade.length}</span></summary><div>${propTable(ade,n)}</div></details>`;
    body+=axioms(n)+constraints(n);
    if(n.children.length)body+=section('Sottoclassi / tipi derivati',`<div class="connection-grid">${n.children.map(id=>card(id,n.format==='OWL'?'rdfs:subClassOf':'xs:extension')).join('')}</div>`,n.children.length);
    if(!props.length&&!n.axioms.length&&!n.constraints.length&&!n.kind.includes('Property'))body+=empty('Nessuna propriet\u00e0 diretta o ereditata disponibile nel catalogo per questa risorsa. Consulta Connessioni e Sorgente.');
    return body;
  }
  function propertiesView(n) {
    return `<div class="property-toolbar"><input type="search" id="property-search" value="${esc(propertyQuery)}" placeholder="Filtra le propriet\u00e0..." aria-label="Filtra propriet\u00e0 nella scheda"><div class="segment"><button data-kind="all" class="${propertyKind==='all'?'active':''}">Tutte</button>${Object.entries(groups).map(([k,[title]])=>`<button data-kind="${k}" class="${propertyKind===k?'active':''}">${title}</button>`).join('')}</div></div><div id="property-results">${propertyResults(n)}</div>`;
  }
  function propertyResults(n) {
    const query=propertyQuery.toLowerCase(),props=properties(n).filter(p=>(propertyKind==='all'||p.kind===propertyKind)&&(!query||(p.name+' '+p.description+' '+p.typeName).toLowerCase().includes(query)));
    return props.length?propSections(props,n):empty('Nessuna propriet\u00e0 corrisponde ai filtri. '+(inherited?'':'Attiva le propriet\u00e0 ereditate per includere le superclassi.'));
  }
  function connections(n) {
    let body='<div class="legend" style="margin-bottom:22px"><span>Associazione</span><span class="geom">Geometria</span><span class="owl">OWL / ponte</span><span class="ade">ADE</span></div>';
    body+=section('Superclasse / tipo base',n.parents.length?`<div class="connection-grid">${n.parents.map(id=>card(id,n.derivation)).join('')}</div>`:empty('Nessuna superclasse nominale dichiarata.'),n.parents.length);
    if(n.children.length)body+=section('Sottoclassi / tipi derivati',`<div class="connection-grid">${n.children.map(id=>card(id,n.format==='OWL'?'rdfs:subClassOf':'xs:extension')).join('')}</div>`,n.children.length);
    if(n.substitution)body+=section('Sostituzione XML',card(n.substitution,'substitutionGroup \u2014 non \u00e8 l\u2019ereditariet\u00e0 del tipo'));
    const outgoing=properties(n).filter(p=>['association','geometry','ade'].includes(p.kind));
    if(outgoing.length)body+=section('Collegamenti in uscita',propTable(outgoing,n),outgoing.length);
    if(n.incoming.length)body+=section('Chi fa riferimento a questo concetto',`<div class="connection-grid">${n.incoming.map(p=>card(p.source,p.property+(p.multiplicity?' \u00b7 '+p.multiplicity:''))).join('')}</div>`,n.incoming.length,'Riferimenti diretti alla destinazione esatta');
    if(n.bridges.length)body+=section('Corrispondenze di navigazione XSD / OWL',notice('Ponte manuale dichiarato in config/navigation-bridges.json. Non \u00e8 un assioma di equivalenza e non trasferisce attributi tra modelli.','purple')+`<div class="connection-grid">${n.bridges.map(b=>card(b.target,'Ponte di navigazione esplicito','owl-card')).join('')}</div>`,n.bridges.length);
    body+=extensions(n)+axioms(n);
    return body;
  }
  function sourceView(n) {
    let body=section('Provenienza',`<dl class="metadata-grid"><dt>Identificatore</dt><dd>${esc(n.iri||n.id)}</dd><dt>Formato</dt><dd>${n.format}</dd><dt>Namespace</dt><dd>${esc(n.namespace||'')}</dd>${n.xmlType?`<dt>Tipo XML</dt><dd>${esc(n.xmlType)}</dd>`:''}<dt>File</dt><dd>${n.source.length?n.source.map(p=>sourceLink(p)).join('<br>'):'Definizione non disponibile localmente'}</dd>${n.line?`<dt>Riga</dt><dd>${n.line}</dd>`:''}<dt>Stato</dt><dd>${n.external?'Solo riferimento esterno':n.builtin?'Tipo predefinito':'Dichiarazione disponibile'}</dd></dl>`);
    if(n.xml)body+=section(n.format==='OWL'?'Estratto RDF in Turtle':'Dichiarazione XML Schema',`<pre class="source-block"><code>${esc(n.xml)}</code></pre>`,'',n.format==='OWL'?'Risorsa e blank node collegati; serializzazione normalizzata':'Estratto locale \u00b7 file originale invariato');
    if(n.annotations.length)body+=`<details class="section-collapse"><summary>Annotazioni RDF <span class="count">${n.annotations.length}</span></summary><div>${n.annotations.map(a=>`<div class="axiom"><div class="axiom-label">${esc(a.predicate)}</div>${esc(a.value)}${a.language?` <span class="muted">@${esc(a.language)}</span>`:''}</div>`).join('')}</div></details>`;
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
    document.title=n.name+' \u00b7 CityGML Explorer';
    $('#breadcrumb').innerHTML=`<b>${esc(n.module)}</b><span>/</span>${esc(n.name)}`;
    const shortId=n.format==='XSD'?(n.qname||n.name):n.iri;
    $('#content').innerHTML=`<article class="page"><div class="eyebrow"><span>${esc(n.family)}</span><span class="slash">/</span><span>${esc(n.module)}</span><span class="slash">/</span><span>${n.format}</span></div><div class="hero"><div><h1>${esc(n.name)}</h1><div class="hero-subtitle"><code>${esc(shortId)}</code><button class="icon-button" data-action="copy-id" aria-label="Copia identificatore" title="Copia identificatore">&#10697;</button></div></div><div class="hero-actions"><button class="text-button" data-action="export">Esporta JSON \u2197</button><button class="text-button" data-tab="source">&lt;/&gt; Sorgente</button></div></div><div class="badges"><span class="badge ${n.format==='OWL'?'purple':'teal'}">${esc(kinds[n.kind]||n.kind)}</span>${n.kind==='class'?`<span class="badge">${n.abstract?'Astratta':n.format==='XSD'?'Concreta':'Classe nominale'}</span>`:''}<span class="badge">${esc(n.format==='XSD'?n.xmlType||'XML Schema':'Dichiarazioni RDF')}</span>${n.external?'<span class="badge amber">Definizione da acquisire</span>':''}${n.technical?'<span class="badge">Tipo tecnico</span>':''}</div><p class="definition ${n.description?'':'empty'}">${esc(n.description || 'Nessuna definizione testuale disponibile nella sorgente locale.')}</p><div class="tabbar" role="tablist" aria-label="Sezioni della scheda">${Object.entries(tabs).map(([id,label])=>`<button class="tab ${activeTab===id?'active':''}" data-tab="${id}" id="tab-${id}" role="tab" aria-selected="${activeTab===id}" aria-controls="tab-content">${label}${id==='properties'?`<span class="count">${props.length}</span>`:''}</button>`).join('')}<label class="inherited-control"><span class="switch"><input type="checkbox" id="inherited" ${inherited?'checked':''} aria-label="Mostra propriet\u00e0 ereditate"><span></span></span>Includi ereditate</label></div><div class="tab-content" id="tab-content" role="tabpanel" aria-labelledby="tab-${activeTab}">${activeTab==='overview'?overview(n):activeTab==='properties'?propertiesView(n):activeTab==='connections'?connections(n):sourceView(n)}</div><footer class="page-footer"><span>${esc(n.format==='XSD'?'Vista della codifica XML, non ricostruzione completa UML':'Vista RDF dichiarativa, senza reasoning')}</span><span>${n.source.length} sorgent${n.source.length===1?'e':'i'} locali</span><a href="#" data-action="help">Guida alla lettura \u2197</a></footer></article>`;
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
  function sourcesModal() {
    const unique=Object.values(Object.fromEntries(data.dependencies.map(d=>[d.url,d])));
    const missing=unique.filter(d=>d.status==='missing');
    showModal('Sorgenti e dipendenze',`<div class="stats-grid"><div class="stat-card"><span class="stat-label">File originali</span><strong>${data.stats.originalFiles}</strong></div><div class="stat-card"><span class="stat-label">File esterni acquisiti</span><strong>${data.stats.addedFiles}</strong></div><div class="stat-card"><span class="stat-label">Import da risolvere</span><strong>${missing.length}</strong></div><div class="stat-card"><span class="stat-label">Riferimenti senza definizione</span><strong>${data.stats.external}</strong></div></div>${missing.length?notice('Questo pacchetto non contiene ancora tutte le dipendenze esterne. Il download diretto non era disponibile durante la preparazione. Gli originali sono integri; esegui <code>python scripts/download_dependencies.py</code> e poi <code>python scripts/build_catalog.py</code> per completare il catalogo con accesso a Internet.'):notice('Tutti gli import espliciti identificati sono disponibili localmente. Questo non equivale a validazione completa o reasoning.','info')}<h3>Import esterni non risolti</h3>${missing.length?`<table class="source-table"><thead><tr><th>Dipendenza</th><th>Richiesta da</th></tr></thead><tbody>${missing.map(d=>`<tr><td class="url"><a href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener">${esc(d.url)}</a></td><td>${esc(d.from.replace('sources/original-voc/',''))}</td></tr>`).join('')}</tbody></table>`:empty('Nessun import esplicito mancante.')}<h3>File inclusi</h3><table class="source-table"><thead><tr><th>File</th><th>Tipo</th><th>Provenienza</th><th>SHA-256 (inizio)</th></tr></thead><tbody>${data.files.map(f=>`<tr><td>${sourceLink(f.path,f.name)}</td><td>${f.format}</td><td>${f.original?'ZIP originale':'Acquisito'}</td><td><code title="${esc(f.sha256)}">${f.sha256.slice(0,12)}\u2026</code></td></tr>`).join('')}</tbody></table><p>Hash completi e import: ${sourceLink('sources/dependency-manifest.json','dependency-manifest.json')}. File e limitazioni sono descritti nel ${sourceLink('README.md','README')}.</p>`);
  }
  function helpModal() {
    showModal('Come leggere il catalogo',`<p>Cerca un concetto a sinistra, apri la scheda e segui i nomi cliccabili. La pagina funziona offline: non legge automaticamente cartelle arbitrarie, ma un indice preparato dai file nella cartella <code>sources/</code>.</p><h3>Ereditariet\u00e0 e associazioni</h3><p>Le propriet\u00e0 ereditate provengono soltanto da <code>xs:extension</code> o dalle superclassi nominali <code>rdfs:subClassOf</code>. Le associazioni, i punti ADE e <code>substitutionGroup</code> non trasferiscono attributi. Per una <code>xs:restriction</code> viene mostrata la struttura dichiarata, senza espandere automaticamente il tipo base.</p><h3>Propriet\u00e0 XSD</h3><p>Attributi e valori \u00e8 una categoria di lettura: molti sono <code>xs:element</code>, non <code>xs:attribute</code>. Le occorrenze includono i gruppi contenitori; un campo in <code>xs:choice</code> resta un\u2019alternativa, non un requisito indipendente. Il codice XML rimane la fonte da verificare.</p><h3>Propriet\u00e0 OWL</h3><p>Domain e range descrivono implicazioni semantiche, non una lista chiusa di campi ammessi. Pi\u00f9 domain/range sono congiuntivi. Un range assente resta non specificato. Restrizioni, unioni e intersezioni sono mostrate come espressioni, senza inferenze automatiche. Classi e individui possono condividere lo stesso IRI; tutti i tipi RDF restano nell\u2019estratto.</p><h3>Stato delle sorgenti</h3><p>La sigla <strong>est.</strong> indica una definizione esterna non presente nel pacchetto. Il browser non inventa le propriet\u00e0 mancanti e non afferma di mostrare un modello completo quando una superclasse manca.</p><h3>Legenda</h3><div class="legend"><span>C: classe XSD</span><span class="geom">T: tipo di dato</span><span class="owl">O/P: OWL / propriet\u00e0</span><span class="ade">+: punto ADE</span></div><p>Premi <kbd>/</kbd> per cercare. I pulsanti Indietro/Avanti e la cronologia del browser seguono i concetti. Ogni scheda ha un URL con identificatore e sezione.</p><p>${sourceLink('README.md','Apri il README del progetto')}</p>`);
  }
  function propertyModal(id) {
    const prop=properties(nodes[current],true).find(p=>p.id===id);
    if(!prop)return;
    showModal(prop.name,`<p>${esc(prop.description||'Nessuna descrizione nella sorgente.')}</p><dl class="metadata-grid"><dt>Tipo XML</dt><dd>${esc(prop.xmlKind||prop.semantics||'')}</dd><dt>Nome</dt><dd>${esc(prop.qname||prop.name)}</dd><dt>Tipo dichiarato</dt><dd>${prop.typeId?ref(prop.typeId,prop.typeName):esc(prop.typeName)}</dd><dt>Destinazione</dt><dd>${prop.targets.map(t=>ref(t)).join(', ')||'Non specificata'}</dd><dt>Occorrenze</dt><dd>${esc(prop.multiplicity??'Non specificate')}${prop.choices?.length?' \u2014 campo alternativo in xs:choice':''}</dd><dt>Definita in</dt><dd>${ref(prop.declaredIn)}</dd><dt>Sorgente</dt><dd>${sourceLink(prop.source)}${prop.line?' : '+prop.line:''}</dd><dt>Nillable</dt><dd>${prop.nillable?'S\u00ec':'No / non dichiarato'}</dd><dt>Default / fixed</dt><dd>${esc(prop.default??'\u2014')} / ${esc(prop.fixed??'\u2014')}</dd><dt>Risoluzione</dt><dd>${esc((prop.targetEvidence||[]).join('; ')||'Tipo dichiarato')}</dd></dl><pre class="source-block"><code>${esc(prop.xml||'')}</code></pre>`);
  }
  function exportCurrent() {
    const n=nodes[current], payload={schemaVersion:data.schemaVersion,concept:n,visibleProperties:properties(n),includeInherited:inherited,notes:'Structural view only; external definitions and OWL entailments may be absent.'};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=n.name.replace(/[^a-z0-9_-]/gi,'_')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    showToast('Scheda esportata in JSON');
  }

  document.addEventListener('click',e=>{
    const prop=e.target.closest('[data-property]');if(prop){propertyModal(prop.dataset.property);return;}
    const action=e.target.closest('[data-action]');
    if(action){e.preventDefault();const a=action.dataset.action;if(a==='sources')sourcesModal();else if(a==='help')helpModal();else if(a==='copy-id')copyText(nodes[current].iri||nodes[current].id);else if(a==='export')exportCurrent();return;}
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
  for(const id of ['module','technical','only-concrete','include-external'])$('#'+id).addEventListener('change',renderList);
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
