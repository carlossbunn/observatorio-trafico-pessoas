'use strict';
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = v => Number(v).toLocaleString('pt-BR');
const label = v => String(v ?? '').replaceAll('_', ' ');
const F=window.ObservatorioFormat;
const state = {world:'real', theme:'', catalog:{}, sources:[], all:[], rows:[], shown:40, selectedIndicator:'', generation:0, overview:null, resources:[], investigations:[]};
const ufs = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];
let map, areas, townAreas, digitalAreas, points, geo, townGeo, searchTimer, tiles;
function link(url, title='Abrir fonte ↗') {
  try {const u = new URL(url); if (!['https:','http:'].includes(u.protocol)) return '';return `<a href="${esc(u.href)}" target="_blank" rel="noopener noreferrer">${esc(title)}</a>`;}catch{return '';}
}
async function api(path) {const response=await fetch(path);if(!response.ok)throw Error(`Falha na consulta (${response.status}).`);return response.json();}
function showError(error) {$('error').textContent=error.message;$('error').hidden=false;}
function detail(title, values) {$('detail-title').textContent=title;$('detail-body').innerHTML=`<dl>${Object.entries(values).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${k==='Fonte pública'?link(v):['Metadados e cobertura','Documentos e situação da investigação','Recursos descobertos'].includes(k)?`<details><summary>Consultar ${Array.isArray(v)?v.length+' documentos e acessos':'evidências e detalhes técnicos'}</summary>${F.html(v)}</details>`:F.html(v)}</dd>`).join('')}</dl>`;$('detail').showModal();}
$('close-detail').onclick=()=>$('detail').close();
$('detail').addEventListener('click', e=>{if(e.target===$('detail'))$('detail').close();});
function view(id) {document.querySelectorAll('.view').forEach(e=>e.hidden=e.id!==id);document.querySelectorAll('[data-view]').forEach(e=>e.classList.toggle('active',e.dataset.view===id));if(id==='explorar'&&map)setTimeout(()=>map.invalidateSize(),30);}
document.querySelectorAll('[data-view]').forEach(e=>e.onclick=()=>view(e.dataset.view));
function params() {const p=new URLSearchParams({ambiente:state.world});for(const [field,id] of [['q','search'],['ano','year'],['uf','uf'],['municipio_ibge','town'],['tipo','type'],['fonte_id','map-source']])if($(id).value)p.set(field,$(id).value);if(state.theme)p.set('tema',state.theme);if(state.selectedIndicator)p.set('indicador',state.selectedIndicator);return p;}
function themes() {
  const groups=[...new Set([...(state.catalog.indicadores||[]).map(i=>i['Dimensão']),...state.all.map(r=>r.tema)])];
  const available=state.all.filter(r=>r.ambiente===state.world||r.ambiente==='ambos');
  $('themes').innerHTML=[['','Todas as camadas'],...groups.map(g=>[g,g]),...(!groups.includes('Denúncias de tráfico de pessoas')?[['Denúncias de tráfico de pessoas','Denúncias de tráfico de pessoas']]:[])].map(([key,title])=>{
    const count=available.filter(r=>!key||r.tema===key||(state.catalog.indicadores||[]).some(i=>i['Dimensão']===key&&r.indicadores.includes(i.ID))).length;
    return `<button class="theme ${state.theme===key?'active':''}" data-theme="${esc(key)}" aria-pressed="${state.theme===key}">${esc(title)}<span>${count} reg.</span></button>`;
  }).join('');
  $('themes').querySelectorAll('[data-theme]').forEach(b=>b.onclick=()=>{state.theme=b.dataset.theme;state.selectedIndicator='';themes();refresh().catch(showError);});
}
async function refresh() {
  const generation=++state.generation;
  const result=await api('/api/mapa?'+params());
  if(generation!==state.generation)return;
  state.rows=result.registros;state.shown=40;state.overview=result;
  $('export').href='/api/exportar.csv?'+params();
  renderRecords();renderMap();renderMapSources();renderNational();
}
function renderRecords() {
  const stats=state.rows.filter(r=>r.tipo==='estatistica'), docs=state.rows.filter(r=>r.tipo==='documento');
  $('record-count').textContent=`${fmt(state.rows.length)} registros · ${fmt(stats.length)} observações estatísticas · ${fmt(docs.length)} documentos. Contagens não representam vítimas.`;
  $('coverage').textContent=state.selectedIndicator?`Filtro pelo indicador ${state.selectedIndicator}. Use “Limpar” para voltar a todos os registros.`:state.world==='virtual'?'O ambiente digital reúne os temas do catálogo com dados publicados sobre o Brasil. País de hospedagem de um site não é localização de uma vítima.':'A localização respeita a precisão da fonte: Brasil, UF, município ou local exato. Camadas de contexto e documentos não são ocorrências.';
  $('records').innerHTML=state.rows.length?state.rows.slice(0,state.shown).map(r=>`<article class="record"><div class="record-header"><span class="badge ${r.tipo==='documento'?'purple':'gray'}">${esc(label(r.tipo))}</span><span class="badge gray">${esc(r.fonte_id)}</span><span class="badge gray">${esc(F.periods(r))}</span>${r.ambiente==='ambos'?'<span class="badge purple">Real ↔ Virtual</span>':''}${r.origem_publicacao!=='Brasil'?'<span class="badge amber">Fonte internacional sobre o Brasil</span>':''}</div><h3>${esc(r.titulo)}</h3><p>${esc(r.descricao.length>850?r.descricao.slice(0,850)+'…':r.descricao)}</p><p>${esc(r.municipio?`${r.municipio}/${r.uf}`:r.uf||'Brasil')} · precisão: ${esc(label(r.precisao))}${r.metadados.referencia_territorial==='unidade_informante'?' · Unidade informante (não local de ocorrência)':''}</p><div class="record-bottom">${r.valor!==null?`<div class="record-value">${fmt(r.valor)} <small>${esc(label(r.unidade))}</small></div>`:'<span class="small muted">Informação documental · consulte as evidências</span>'}<button class="secondary" data-detail="${esc(r.id)}">Origem e detalhes ↗</button></div></article>`).join(''):'<div class="empty"><b>Nenhum registro importado para estes filtros.</b><p>Consulte “Fontes e coleta” para verificar cobertura e recursos disponíveis.</p></div>';
  $('records').querySelectorAll('[data-detail]').forEach(b=>b.onclick=()=>recordDetail(state.rows.find(r=>r.id===b.dataset.detail)));
  $('more').hidden=state.shown>=state.rows.length;
}
function recordDetail(r) {
  const metadata=r.metadados||{}, fields=r.disponibilidade||{};
  const dateValue=key=>metadata[key]||fields[key]?.motivo||'Data ainda não investigada';
  const territory=r.precisao==='pais'?'Abrangência nacional — não se aplica município a esta ficha':r.precisao==='uf'?`${r.uf} · abrangência estadual`:`${r.municipio||'Município ainda não estruturado'}/${r.uf||'UF ainda não estruturada'}`;
  const values={'Identificador':r.id,'Natureza':label(r.tipo),'Ambiente':label(r.ambiente),'Tema':r.tema,'Descrição':r.descricao,
     'Referência temporal':F.periods(r),'Significado do ano':label(metadata.significado_ano||(r.tipo==='estatistica'?'ano_da_observacao':'ano_ainda_nao_classificado')),
     ...(metadata.cobertura_anual_completa===false?{'Cobertura do período':metadata.nota_cobertura||'Período parcial; não corresponde ao ano completo.'}:{}),
     ...(metadata.tabela?{'Tabela de origem':metadata.tabela}:{}),
     ...(metadata.observacao?.pagina?{'Página do PDF':metadata.observacao.pagina,'Página com evidência':r.recurso_url.split('#')[0]+'#page='+metadata.observacao.pagina}:{}),
    'Data de publicação':dateValue('data_publicacao'),'Data de atualização':dateValue('data_atualizacao'),
    ...(r.tipo==='estatistica'?{'Valor':r.valor,'Unidade':label(r.unidade)}:{}),
    'Abrangência territorial':territory,...(r.municipio_ibge?{'Código IBGE':r.municipio_ibge}:{}),
    'Papel da localização':metadata.referencia_territorial==='unidade_informante'?'Local da unidade que produziu o relatório; não equivale ao local de aliciamento/exploração.':'Abrangência declarada pela fonte',
    ...(r.precisao==='local_exato'?{'Coordenadas':`${r.latitude}, ${r.longitude}`}:{'Representação no mapa':'Área territorial; coordenadas pontuais não se aplicam'}),
    'País de publicação':r.origem_publicacao,'Relação com o Brasil':r.relacao_brasil,'Situação':label(r.situacao),
    'Indicadores':r.indicadores,'Coletado em':r.coletado_em,'Fonte pública':r.recurso_url,
    'Documentos e situação da investigação':linkedResources(r.fonte_id),
    'Disponibilidade dos campos':fields,'Metadados e cobertura':metadata};
  detail(r.titulo,values);
}
$('more').onclick=()=>{state.shown+=40;renderRecords();};
function initMap() {
  if(!window.L){$('map').hidden=true;$('map-fallback').hidden=false;return;}
  map=L.map('map',{scrollWheelZoom:false}).setView([-14.5,-52.5],4);
  map.attributionControl.addAttribution('Limites territoriais: <a href="https://servicodados.ibge.gov.br/api/docs/malhas?versao=3">IBGE</a>');
  points=L.layerGroup().addTo(map);
}
function renderMap() {
  $('world-label').textContent=state.world==='real'?'MUNDO REAL':'MUNDO VIRTUAL';
  $('map-title').textContent=state.world==='real'?'Território brasileiro':'Conexões digitais com o Brasil';
  const territorial=state.rows.filter(r=>r.uf), national=state.rows.filter(r=>!r.uf);
  $('map-note').textContent=`${territorial.length} registros com referência de UF ou município · ${national.length} sem localização subnacional. Cor das UFs: quantidade de registros publicados, não intensidade de tráfico. Municípios são consultados pelo filtro; não há marcadores em seus centroides.`;
  if(!map)return;
  points.clearLayers();if(areas)map.removeLayer(areas);
  if(townAreas)map.removeLayer(townAreas);
  if(digitalAreas){map.removeLayer(digitalAreas);digitalAreas=null;}
  if(geo?.features?.length){
    const counts=Object.fromEntries(ufs.map(uf=>[uf,territorial.filter(r=>r.uf===uf).length]));
    areas=L.geoJSON(geo,{style:f=>({color:'#7faaa2',weight:1,fillColor:counts[f.properties.sigla]?(state.world==='real'?'#188577':'#7961a8'):'#dce9e4',fillOpacity:counts[f.properties.sigla]?0.6:0.15}),onEachFeature:(f,layer)=>{
      const uf=f.properties.sigla||f.properties.codarea;
      layer.bindTooltip(`${esc(uf)} · ${counts[uf]||0} registros com referência territorial`);
      layer.on('click',()=>{if(ufs.includes(uf)){$('uf').value=uf;$('town').value='';map.fitBounds(layer.getBounds(),{maxZoom:7});loadTowns().then(refresh).catch(showError);}});
    }}).addTo(map);
  }else $('map-note').textContent+=' Malha de UFs ainda não coletada: execute o coletor A11.';
  const municipalRows=state.rows.filter(r=>r.municipio_ibge);
  if(townGeo?.features?.length&&municipalRows.length){
    const codes=new Set(municipalRows.map(r=>r.municipio_ibge));
    townAreas=L.geoJSON(townGeo,{filter:f=>codes.has(f.properties.municipio_ibge),style:()=>({color:state.world==='real'?'#086d61':'#6754a1',weight:2,fillColor:state.world==='real'?'#2ca78e':'#9676ce',fillOpacity:0.48}),onEachFeature:(f,layer)=>{
      const code=f.properties.municipio_ibge, rows=municipalRows.filter(r=>r.municipio_ibge===code), first=rows[0];
      layer.bindTooltip(`${esc(first.municipio)}/${esc(first.uf)} · ${rows.length} registros publicados. Área municipal, não local de ocorrência.`);
      layer.on('click',()=>{$('uf').value=first.uf;loadTowns().then(()=>{$('town').value=code;map.fitBounds(layer.getBounds(),{maxZoom:11});return refresh();}).catch(showError);});
    }}).addTo(map);
    if($('town').value&&townAreas.getLayers().length)map.fitBounds(townAreas.getBounds(),{maxZoom:11});
  }
  for(const r of state.rows.filter(r=>r.precisao==='local_exato'&&r.latitude!==null&&r.longitude!==null)){
    const container=document.createElement('div');const title=document.createElement('strong');title.textContent=r.titulo;container.append(title,document.createElement('br'));const button=document.createElement('button');button.textContent='Ver origem e detalhes';button.onclick=()=>recordDetail(r);container.append(button);L.marker([r.latitude,r.longitude]).bindPopup(container).addTo(points);
  }
  if(state.world==='virtual'&&$('digital-overlay').value==='sim'&&townGeo?.features?.length){
    const rows=(state.digitalAnalysis?.localidades_contexto||[]).filter(r=>r.metadados.periodo===$('digital-period').value), byCode=new Map(rows.map(r=>[r.municipio_ibge,r]));
    digitalAreas=L.geoJSON(townGeo,{filter:f=>byCode.has(f.properties.municipio_ibge),style:()=>({color:'#b96910',weight:2,fillColor:'#f6b44a',fillOpacity:.55}),onEachFeature:(f,layer)=>{const r=byCode.get(f.properties.municipio_ibge);layer.bindTooltip(`${esc(r.municipio)}/${esc(r.uf)} · ${fmt(r.valor)} registros administrativos · contexto geral, canal digital desconhecido`);layer.on('click',()=>recordDetail(r));}}).addTo(map);
    $('map-note').textContent+=` Camada laranja: ${rows.length} municípios do Disque 100 em ${$('digital-period').value}; contexto geral, sem comprovação de uso da internet.`;
  }
}
$('reset-map').onclick=()=>map?.setView([-14.5,-52.5],4);
async function loadTowns(){const uf=$('uf').value;const rows=uf?await api('/api/localidades?uf='+encodeURIComponent(uf)):[];if($('uf').value!==uf)return;$('town').innerHTML='<option value="">Todos os municípios</option>'+rows.map(r=>`<option value="${esc(r.id)}">${esc(r.nome)}</option>`).join('');}
document.querySelectorAll('[data-world]').forEach(b=>b.onclick=()=>{state.world=b.dataset.world;state.selectedIndicator='';$('recruitment').hidden=state.world!=='virtual';document.body.classList.toggle('virtual',state.world==='virtual');document.querySelectorAll('[data-world]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));});themes();refresh().catch(showError);});
for(const id of ['year','town','type','map-source'])$(id).onchange=()=>refresh().catch(showError);
$('uf').onchange=()=>{loadTowns().then(refresh).catch(showError);};
$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>refresh().catch(showError),250);};
$('clear').onclick=()=>{for(const id of ['year','uf','type','search','map-source','map-source-search','map-source-coverage'])$(id).value='';state.theme='';state.selectedIndicator='';loadTowns().then(refresh).catch(showError);themes();};
function renderCatalog(){
  const q=$('catalog-search').value.toLocaleLowerCase('pt-BR');
  const sections=[['indicadores','Indicadores'],['correlacoes','Cruzamentos propostos'],['perguntas','Perguntas e hipóteses']];
  $('catalog-content').innerHTML=sections.map(([key,title])=>{
    const rows=(state.catalog[key]||[]).filter(r=>JSON.stringify(r).toLocaleLowerCase('pt-BR').includes(q));
    return `<section class="catalog-group"><h2>${title} <span class="badge gray">${rows.length}</span></h2><div class="catalog-grid">${rows.map(r=>`<article class="catalog-card"><span class="badge ${key==='indicadores'?'':'purple'}">${esc(r.ID)}</span>${(r.ambientes||[]).map(w=>` <span class="badge gray">${w==='real'?'Mundo real':'Mundo virtual'}</span>`).join('')}<h3>${esc(r['Indicador em português']||r.Cruzamento||r['Pergunta em português'])}</h3><p>${esc(r['Definição operacional']||r['Pergunta / resultado de análise']||r['Cuidados de interpretação'])}</p><p>${esc(r['Dimensão']||r.Camada||r.Tema)} · ${esc(r.Natureza||r['Status de observação']||'Hipótese metodológica')}</p><button class="secondary" data-catalog="${key}" data-id="${esc(r.ID)}">Definição e relações ↗</button>${key==='indicadores'?` <button data-indicator="${esc(r.ID)}">Ver dados</button>`:''}</article>`).join('')}</div></section>`;
  }).join('');
  $('catalog-content').querySelectorAll('[data-catalog]').forEach(b=>b.onclick=()=>{
    const row=state.catalog[b.dataset.catalog].find(r=>r.ID===b.dataset.id);
    const ids=String(row['Fontes IDs']||row['Fonte ID']||'').split(';').map(s=>s.trim());
    const related=state.sources.filter(s=>ids.includes(s.id));
    const values={...row,'Fontes relacionadas':related.map(s=>`${s.id} · ${s.nome}`).join('\n')};
    if(b.dataset.catalog==='indicadores')values['Cruzamentos por fonte comum (vínculos documentais)']=state.catalog.correlacoes.filter(c=>String(c['Fonte ID']).split(';').some(s=>ids.includes(s.trim()))).map(c=>`${c.ID} · ${c.Cruzamento}`).join('\n');
    detail(row.ID+' · definição e relações',values);
  });
  $('catalog-content').querySelectorAll('[data-indicator]').forEach(b=>b.onclick=()=>{state.selectedIndicator=b.dataset.indicator;state.theme='';view('explorar');themes();refresh().catch(showError);});
}
$('catalog-search').oninput=renderCatalog;
function renderSources(){
  const q=$('source-search').value.toLocaleLowerCase('pt-BR');
  $('sources').innerHTML=state.sources.filter(s=>JSON.stringify(s).toLocaleLowerCase('pt-BR').includes(q)).map(s=>`<article class="source-card"><span class="badge gray">${esc(s.id)}</span> <span class="badge ${s.escopo==='brasil'?'':'amber'}">${esc(label(s.escopo))}</span><h3>${esc(s.nome)}</h3><p>${esc(s.dados['O que fornece'])}</p><p><b>Acesso:</b> ${esc(s.dados['Acesso disponível'])}<br><b>Condição:</b> ${esc(s.dados['Condição de acesso / limitação'])}</p><p><b>Coletor:</b> ${esc(s.coletor)}</p><div class="status"><b>${esc(label(s.ultima_coleta?.situacao||'nao_executado'))}</b> · ${s.registros} registros · ${s.recursos} recursos<p>${esc(s.ultima_coleta?.mensagem||'Fonte catalogada; dados não coletados.')}</p>${link(s.url)}</div></article>`).join('');
}
$('source-search').oninput=renderSources;
async function boot(){
   const [catalog,sources,records,summary,geography,municipalGeography,runs,resources,investigations,coverage,recruitment,digitalAnalysis]=await Promise.all(['/api/catalogo','/api/fontes','/api/registros','/api/resumo','/api/geografia','/api/geografia?nivel=municipios','/api/coletas','/api/recursos','/api/investigacoes','/api/cobertura','/api/recrutamento','/api/analise-digital'].map(api));
   state.coverage=coverage;renderCoverage();
   state.recruitment=recruitment.fichas;initRecruitment();
   state.digitalAnalysis=digitalAnalysis;initDigitalAnalysis();
  state.catalog=catalog;state.sources=sources;state.all=records.registros;state.resources=resources;state.investigations=investigations;geo=geography;townGeo=municipalGeography;
  $('map-source').innerHTML='<option value="">Todas as 59 fontes</option>'+sources.map(s=>`<option value="${esc(s.id)}">${esc(s.id+' · '+s.nome)}</option>`).join('');
  $('summary').innerHTML=[['Fontes catalogadas',summary.fontes],['Fontes com registros',summary.fontes_com_dados],['Registros publicados',summary.registros],['Municípios com dados',summary.municipios]].map(([title,value])=>`<div class="metric"><b>${fmt(value)}</b><span>${title}</span></div>`).join('');
  $('year').innerHTML='<option value="">Todos os anos</option>'+[...new Set(state.all.flatMap(F.years))].sort((a,b)=>b-a).map(y=>`<option>${y}</option>`).join('');
  $('uf').innerHTML='<option value="">Todo o Brasil</option>'+ufs.map(uf=>`<option>${uf}</option>`).join('');
  $('runs').innerHTML=runs.length?runs.map(r=>`<div class="run"><b>${esc(r.fonte_id)} · ${esc(label(r.situacao))}</b><span class="muted"> · ${esc(r.fim||r.inicio)}</span><p>${esc(r.mensagem||'Em execução')}</p></div>`).join(''):'<div class="empty">Nenhuma coleta executada. Execute <code>python3 app.py collect</code>.</div>';
  $('resources').innerHTML=resources.length?resources.map(r=>`<div class="resource"><b>${esc(r.fonte_id)} · ${esc(r.formato)}</b> · ${link(r.url,r.titulo)}<br><small>Descoberto em ${esc(r.descoberto_em)}. Descoberta não significa importação de dados.</small></div>`).join(''):'<div class="empty">Nenhum recurso descoberto.</div>';
   if(!map)initMap();themes();renderCatalog();renderSources();await refresh();
}
boot().catch(showError);

function updateBasemap(){
  if(!map)return;
  if(tiles){map.removeLayer(tiles);tiles=null;}
  $('basemap-error').hidden=true;
  if($('basemap').value==='osm'){
    tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,referrerPolicy:'strict-origin-when-cross-origin',attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'});
    tiles.on('tileerror',()=>{$('basemap-error').hidden=false;});
    tiles.addTo(map);
  }
}
$('basemap').onchange=updateBasemap;
function sourceDetail(id){
  const source=(state.overview?.fontes||[]).find(s=>s.id===id)||state.sources.find(s=>s.id===id);
  const records=state.all.filter(r=>r.fonte_id===id), resources=state.resources.filter(r=>r.fonte_id===id);
  detail(source.nome,{'ID':id,'Descrição':source.dados['O que fornece'],'Escopo original':source.dados['Escopo geográfico'],'Recorte Brasil':label(source.escopo),'Cobertura no mapa':label(source.cobertura_mapa||'Ver registros importados'),'Relação com o território':source.relacao_com_territorio||'Sem atribuição territorial automática','Acesso':source.dados['Acesso disponível'],'Limitação':source.dados['Condição de acesso / limitação'],'Temas':source.temas||[],'Indicadores relacionados':source.indicadores||[],'Situação da última coleta':label(source.ultima_coleta?.situacao||'nao_executado'),'Resultado da coleta':source.ultima_coleta?.mensagem||'Ainda não consultada','Registros disponíveis':records.map(r=>r.titulo),'Recursos descobertos':linkedResources(id),'Fonte pública':source.url});
}
function linkedResources(id){
  return state.resources.filter(r=>r.fonte_id===id).map(r=>{
    const investigation=state.investigations.find(i=>i.fonte_id===id&&i.url===r.url);
    return {documento:r.titulo,url:r.url,situacao:investigation?label(investigation.situacao):r.formato==='pdf_examinado'?'PDF examinado':'Descoberto; extração específica pendente',...(investigation?{resultado:investigation.detalhe,verificado_em:investigation.verificado_em}:{})};
  });
}
function renderMapSources(){
  if(!state.overview)return;
  const q=$('map-source-search').value.toLocaleLowerCase('pt-BR'), coverage=$('map-source-coverage').value;
  const sources=state.overview.fontes.filter(s=>(!coverage||s.cobertura_mapa===coverage)&&JSON.stringify(s).toLocaleLowerCase('pt-BR').includes(q));
  $('map-source-count').textContent=`${sources.length} de ${state.overview.total_fontes} fontes`;
  $('map-sources').innerHTML=sources.length?sources.map(s=>`<article class="map-source-card ${$('map-source').value===s.id?'selected':''}"><span class="badge gray">${esc(s.id)}</span> <span class="badge ${s.cobertura_mapa==='territorial'?'':'amber'}">${esc(label(s.cobertura_mapa))}</span><h3>${esc(s.nome)}</h3><p>${esc(s.dados['O que fornece'])}</p><p><b>${s.registros_no_filtro}</b> registros no filtro · <b>${s.registros_nacionais}</b> nacionais relacionados</p><p>${esc(s.relacao_com_territorio)}</p><div class="source-buttons"><button class="secondary" data-source-details="${esc(s.id)}">Informações da fonte</button><button data-source-filter="${esc(s.id)}">Ver no mapa</button></div></article>`).join(''):'<div class="empty">Nenhuma fonte corresponde à seleção. Use “Limpar” para consultar as 59 entradas.</div>';
  $('map-sources').querySelectorAll('[data-source-details]').forEach(b=>b.onclick=()=>sourceDetail(b.dataset.sourceDetails));
  $('map-sources').querySelectorAll('[data-source-filter]').forEach(b=>b.onclick=()=>{$('map-source').value=b.dataset.sourceFilter;refresh().catch(showError);});
}
$('map-source-search').oninput=renderMapSources;
$('map-source-coverage').onchange=renderMapSources;
function renderNational(){
  const rows=state.overview?.nacionais||[];
  const territory=$('town').value?$('town').selectedOptions[0]?.textContent:($('uf').value||'Brasil');
  $('territory-title').textContent=territory+' · contexto nacional relacionado';
  $('national-count').textContent=rows.length+' informações nacionais';
  $('national-records').innerHTML=rows.length?rows.map(r=>`<button data-national="${esc(r.id)}">${esc(r.titulo)}<small>${esc(r.fonte_id)} · ${esc(label(r.tipo))} · ${r.origem_publicacao==='Brasil'?'Publicação brasileira':'Fonte internacional sobre o Brasil'}</small></button>`).join(''):'<span class="muted small">Nenhuma informação nacional importada para estes filtros. As fontes do catálogo permanecem consultáveis abaixo.</span>';
  $('national-records').querySelectorAll('[data-national]').forEach(b=>b.onclick=()=>recordDetail(rows.find(r=>r.id===b.dataset.national)));
}

function renderCoverage(){
  if(!state.coverage)return;
  const data=state.coverage, s=data.resumo;
  $('coverage-summary').innerHTML=[['Fontes com estatísticas',`${s.fontes_com_estatisticas} / ${s.fontes}`],['PDFs examinados parcialmente',`${s.pdfs_examinados} / ${s.pdfs}`],['PDFs pendentes',s.pdfs_pendentes],['Indicadores com vínculos',`${s.indicadores_com_registros} / ${s.indicadores}`]].map(([title,value])=>`<div class="metric"><b>${esc(value)}</b><span>${esc(title)}</span></div>`).join('');
  $('coverage-note').textContent=data.nota+' Consulta: '+new Date(data.gerado_em).toLocaleString('pt-BR');
  const q=$('coverage-search').value.toLocaleLowerCase('pt-BR'), status=$('coverage-status').value;
  const sources=data.fontes.filter(s=>(!status||s.situacao===status)&&JSON.stringify(s).toLocaleLowerCase('pt-BR').includes(q));
  $('coverage-sources').innerHTML=sources.length?sources.map(s=>`<article class="source-card"><span class="badge gray">${esc(s.id)}</span> <span class="badge amber">${esc(label(s.situacao))}</span><h3>${esc(s.nome)}</h3><p><b>${s.estatisticas}</b> estatísticas · ${s.documentos} documentos · ${s.registros} registros</p><p><b>Anos publicados/referenciados:</b> ${esc(s.anos.join(', ')||'Não estruturados')}<br><b>Território:</b> ${esc(s.ufs.join(', ')||'Sem UF estruturada')} · ${s.municipios} municípios</p><p><b>PDFs:</b> ${s.pdfs_examinados} examinados parcialmente / ${s.pdfs} descobertos</p><ul>${s.pendencias.map(p=>`<li>${esc(p)}</li>`).join('')}</ul><button class="secondary" data-coverage-source="${esc(s.id)}">Arquivos, campos e unidades ↗</button></article>`).join(''):'<p class="empty">Nenhuma fonte corresponde aos filtros.</p>';
  $('coverage-sources').querySelectorAll('[data-coverage-source]').forEach(b=>b.onclick=()=>{const s=data.fontes.find(s=>s.id===b.dataset.coverageSource);detail(s.id+' · '+s.nome,{'Situação':label(s.situacao),'Pendências':s.pendencias,'Unidades estatísticas':s.unidades,'Campos pendentes (quantidade de fichas)':s.campos_pendentes,'Documentos e situação da investigação':s.arquivos,'Última coleta':s.ultima_coleta||'Nenhuma coleta'});});
  $('coverage-indicators').innerHTML=data.indicadores.map(i=>`<article class="catalog-card"><span class="badge gray">${esc(i.id)}</span><h3>${esc(i.nome)}</h3><p>${esc(label(i.situacao))}</p><p>${i.registros} registros vinculados · ${i.estatisticas} estatísticas</p><p>Fontes com vínculos: ${esc(i.fontes_com_registros.join(', ')||'Nenhuma')}<br>Fontes previstas: ${esc(i.fontes_previstas.join(', ')||'Nenhuma')}</p><button class="secondary" data-coverage-indicator="${esc(i.id)}">Consultar registros</button></article>`).join('');
  $('coverage-indicators').querySelectorAll('[data-coverage-indicator]').forEach(b=>b.onclick=()=>{for(const id of ['year','uf','town','type','search','map-source'])$(id).value='';state.theme='';state.selectedIndicator=b.dataset.coverageIndicator;view('explorar');themes();loadTowns().then(refresh).catch(showError);});
}
$('coverage-search').oninput=renderCoverage;
$('coverage-status').onchange=renderCoverage;
$('coverage-refresh').onclick=async()=>{const button=$('coverage-refresh');button.disabled=true;try{await boot();}catch(error){showError(error);}finally{button.disabled=false;}};

const recruitmentLabels={trafico_documentado:'Vínculo com tráfico documentado pela fonte',suspeita_nao_confirmada:'Suspeita não confirmada',golpe_sem_vinculo_trafico:'Golpe sem vínculo comprovado com tráfico',alerta_geral:'Alerta geral · sem oferta individual',brasil:'Brasil',conexao_brasil:'Conexão com Brasil',internacional:'Internacional'};
function initRecruitment(){
  const rows=state.recruitment||[];
  for(const [id,values] of [['recruitment-year',rows.map(r=>r.data_publicacao?.slice(0,4))],['recruitment-source',rows.map(r=>r.fonte_id)],['recruitment-platform',rows.map(r=>r.plataforma)]]){
    const select=$(id), prior=select.value, first=select.options[0].outerHTML;
    select.innerHTML=first+[...new Set(values.filter(Boolean))].sort().map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');select.value=prior;
  }
  renderRecruitment();
}
function renderRecruitment(){
  const q=$('recruitment-search').value.trim().toLocaleLowerCase('pt-BR');
  const rows=(state.recruitment||[]).filter(r=>(!$('recruitment-status').value||r.classificacao===$('recruitment-status').value)&&(!$('recruitment-region').value||r.recorte===$('recruitment-region').value)&&(!$('recruitment-year').value||r.data_publicacao?.startsWith($('recruitment-year').value+'-'))&&(!$('recruitment-source').value||r.fonte_id===$('recruitment-source').value)&&(!$('recruitment-platform').value||r.plataforma===$('recruitment-platform').value)&&(!q||[r.titulo,r.descricao,r.pais,r.plataforma,r.fonte_nome].join(' ').toLocaleLowerCase('pt-BR').includes(q)));
  $('recruitment-count').textContent=`${rows.length} fichas · ${rows.filter(r=>r.classificacao!=='alerta_geral').length} ofertas ou casos individuais`;
  $('recruitment-list').innerHTML=rows.length?rows.map(r=>`<article class="source-card"><span class="badge amber">${esc(recruitmentLabels[r.classificacao])}</span> <span class="badge gray">${esc(recruitmentLabels[r.recorte])}</span><h3>${esc(r.titulo)}</h3><p>${esc(r.descricao)}</p><p><b>Fonte:</b> ${esc(r.fonte_nome)} · ${esc(r.data_publicacao||'Data não informada')}<br><b>País:</b> ${esc(r.pais)} · <b>Plataforma:</b> ${esc(r.plataforma||'Não informada')}</p><p><b>Limites:</b> ${esc(r.limites)}</p><button class="secondary" data-recruitment="${esc(r.id)}">Evidência e detalhes ↗</button> ${link(r.fonte_url,'Fonte pública ↗')}</article>`).join(''):'<div class="empty">Nenhuma ficha importada corresponde aos filtros. Ausência na lista não indica ausência de ofertas.</div>';
  $('recruitment-list').querySelectorAll('[data-recruitment]').forEach(b=>b.onclick=()=>{const r=rows.find(r=>r.id===b.dataset.recruitment);detail(r.titulo,{'Classificação':recruitmentLabels[r.classificacao],'Recorte':recruitmentLabels[r.recorte],'Descrição':r.descricao,'Trecho da fonte':r.trecho_evidencia,'Relação com o Brasil':r.relacao_brasil||'Não documentada; referência internacional','País':r.pais,'Plataforma':r.plataforma||'Não informada','Sinais documentados':r.sinais||[],'Limitações':r.limites,'Data da publicação':r.data_publicacao||'Não informada','Fonte pública':r.fonte_url,'Fonte':r.fonte_nome,'Última importação':r.atualizado_em});});
}
for(const id of ['recruitment-search','recruitment-status','recruitment-region','recruitment-year','recruitment-source','recruitment-platform'])$(id).addEventListener(id==='recruitment-search'?'input':'change',renderRecruitment);

function initDigitalAnalysis(){
  const select=$('digital-period'), prior=select.value;
  select.innerHTML='<option value="">Selecione um período</option>'+(state.digitalAnalysis.periodos||[]).map(p=>`<option value="${esc(p)}">${esc(p)}</option>`).join('');
  select.value=prior||(state.digitalAnalysis.periodos||[]).includes('2025-S2')&&'2025-S2'||state.digitalAnalysis.periodos[0]||'';
  const employment=state.digitalAnalysis.motivacoes_trabalho||[];
  for(const [id,values] of [['employment-year',employment.map(r=>r.ano)],['employment-uf',employment.map(r=>r.uf)]]){const el=$(id), previous=el.value;el.innerHTML=el.options[0].outerHTML+[...new Set(values.filter(Boolean))].sort().reverse().map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');el.value=previous;}
  renderDigitalAnalysis();
}
function renderDigitalAnalysis(){
  const data=state.digitalAnalysis;if(!data)return;
  const profile=data.perfil_nacional||[], years=[...new Set(profile.map(r=>r.ano))].sort();
  $('digital-profile').innerHTML=years.length?years.map(year=>{const rows=profile.filter(r=>r.ano===year), total=rows.find(r=>r.metadados.observacao.categoria==='Total');return `<article class="source-card"><h3>${year} · perfil nacional</h3>${rows.filter(r=>r!==total).map(r=>`<p>${esc(r.metadados.observacao.categoria)}: <b>${fmt(r.valor)}</b>${total?.valor?` (${(100*r.valor/total.valor).toLocaleString('pt-BR',{maximumFractionDigits:1})}%)`:''}</p>`).join('')}<p><b>Total da tabela: ${total?fmt(total.valor):'não informado'}</b></p>${rows[0]?link(rows[0].recurso_url+'#page='+rows[0].metadados.observacao.pagina,'Relatório nacional · tabela 3 ↗'):''}</article>`;}).join(''):'<p class="empty">Perfil ainda não importado.</p>';
  const recent=data.perfil_institucional_recente||[], keys=[...new Set(recent.map(r=>r.ano+'|'+r.metadados.grupo_perfil))].sort();
  $('digital-profile-recent').innerHTML=keys.length?keys.map(key=>{const rows=recent.filter(r=>r.ano+'|'+r.metadados.grupo_perfil===key),total=rows.find(r=>r.metadados.observacao.total),first=rows[0];return `<article class="source-card"><h3>${esc(first.ano)} · ${esc(first.metadados.instituicao)}</h3>${rows.filter(r=>!r.metadados.observacao.total).map(r=>`<p>${esc(r.metadados.observacao.categoria)}: <b>${fmt(r.valor)}</b>${total?.valor?` (${(100*r.valor/total.valor).toLocaleString('pt-BR',{maximumFractionDigits:1})}%)`:''}</p>`).join('')}<p><b>Total desta fonte: ${total?fmt(total.valor):'não informado'}</b><br><small>${esc(label(first.unidade))}</small></p><p class="muted small">${esc(first.metadados.limite)}</p><button class="secondary" data-recent-profile="${esc(first.id)}">Fonte e evidência ↗</button></article>`;}).join(''):'<p class="empty">Perfis de 2024 e 2025 ainda não importados.</p>';
  $('digital-profile-recent').querySelectorAll('[data-recent-profile]').forEach(b=>b.onclick=()=>recordDetail(recent.find(r=>r.id===b.dataset.recentProfile)));
  const modality=(data.modalidades_contexto||[]).filter(r=>String(r.ano)===$('digital-modality-year').value);
  $('digital-modalities').innerHTML=modality.length?modality.map(r=>`<p>${esc(r.metadados.observacao.categoria)}: <b>${fmt(r.valor)}</b> inquéritos</p>`).join('')+link(modality[0].recurso_url+'#page='+modality[0].metadados.observacao.pagina,'Relatório nacional · tabela 5 ↗'):'<p class="muted">Dados não importados para este ano.</p>';
  const employment=(data.motivacoes_trabalho||[]).filter(r=>(!$('employment-year').value||String(r.ano)===$('employment-year').value)&&(!$('employment-uf').value||r.uf===$('employment-uf').value)&&r.metadados.observacao.categoria===$('employment-category').value).sort((a,b)=>(b.ano||0)-(a.ano||0)||String(a.uf).localeCompare(String(b.uf)));
  $('employment-records').innerHTML=employment.length?employment.map(r=>`<article class="source-card"><span class="badge gray">${esc(r.ano||'Ano não estruturado')}</span><h3>${esc(r.municipio?`${r.municipio}/${r.uf}`:r.uf||'Unidade não estruturada')}</h3><p><b>${fmt(r.valor)}</b> · ${esc(r.metadados.observacao.categoria)}</p><p class="muted small">Local da unidade informante; não é local de aliciamento. Evidência limitada à tabela.</p><button class="secondary" data-employment="${esc(r.id)}">Ver origem e limites ↗</button></article>`).join(''):'<p class="empty">Nenhuma linha completa extraída para estes filtros; não significa ausência na fonte.</p>';
  $('employment-records').querySelectorAll('[data-employment]').forEach(b=>b.onclick=()=>recordDetail(employment.find(r=>r.id===b.dataset.employment)));
  const locations=(data.localidades_contexto||[]).filter(r=>r.metadados.periodo===$('digital-period').value).sort((a,b)=>b.valor-a.valor||a.municipio.localeCompare(b.municipio));
  $('digital-locations').innerHTML=locations.length?locations.map(r=>`<article class="source-card"><h3>${esc(r.municipio)}/${esc(r.uf)}</h3><p><b>${fmt(r.valor)}</b> registros administrativos distintos na célula · ${esc(r.metadados.periodo)}</p><button class="secondary" data-context-location="${esc(r.id)}">Fonte e limites ↗</button></article>`).join(''):'<p class="empty">Selecione um período com dados disponíveis.</p>';
  $('digital-locations').querySelectorAll('[data-context-location]').forEach(b=>b.onclick=()=>recordDetail(locations.find(r=>r.id===b.dataset.contextLocation)));
  if(map)renderMap();
}
for(const id of ['digital-period','digital-overlay','digital-modality-year','employment-year','employment-uf','employment-category'])$(id).onchange=renderDigitalAnalysis;
