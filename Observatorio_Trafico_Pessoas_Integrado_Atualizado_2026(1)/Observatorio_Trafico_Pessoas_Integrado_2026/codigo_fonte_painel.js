'use strict';
/** Painel totalmente local: dados embutidos, nenhum fetch, sem dependências externas. */
const D = JSON.parse(document.getElementById('all-data').textContent);
const IDS = {
  registros_unificados:'Registro unificado · todos os tipos',
  megabase:'Tabela gigante · relações temáticas',
  arestas_documentais:'Arestas · vínculos documentais',
  observacoes:'Observações oficiais numéricas',
  eurostat_serie:'Eurostat · série anual 2014–2024',
  fontes:'Fontes documentadas',
  indicadores:'Indicadores deduplicados',
  indicadores_recebidos:'CSV recebido · 34 indicadores',
  perguntas:'Perguntas públicas e analíticas',
  correlacoes:'Cruzamentos propostos',
  evidencias:'Evidências de publicações',
  auditoria_integracao:'Auditoria de importação'
};
const joins = [
 {label:'Indicadores ↔ relações (M001 = M001)',left:'megabase',leftKey:'Indicador ID',right:'indicadores',rightKey:'ID',mode:'exact'},
 {label:'Relações ↔ hipóteses de cruzamento (C01)',left:'megabase',leftKey:'Correlação ID',right:'correlacoes',rightKey:'ID',mode:'exact'},
 {label:'Relações ↔ perguntas (Q01)',left:'megabase',leftKey:'Pergunta relacionada ID',right:'perguntas',rightKey:'ID',mode:'token'},
 {label:'Relações ↔ catálogo de fontes (F01…)',left:'megabase',leftKey:'Fontes conjuntas ID',right:'fontes',rightKey:'ID',mode:'token'},
 {label:'Indicadores ↔ fontes citadas',left:'indicadores',leftKey:'Fontes IDs',right:'fontes',rightKey:'ID',mode:'token'},
 {label:'Perguntas ↔ fontes citadas',left:'perguntas',leftKey:'Fonte ID',right:'fontes',rightKey:'ID',mode:'token'},
 {label:'Cruzamentos ↔ fontes citadas',left:'correlacoes',leftKey:'Fonte ID',right:'fontes',rightKey:'ID',mode:'token'},
 {label:'Observações ↔ fonte de publicação',left:'observacoes',leftKey:'Fonte ID',right:'fontes',rightKey:'ID',mode:'token'},
 {label:'Evidências ↔ fonte de publicação',left:'evidencias',leftKey:'Fonte ID',right:'fontes',rightKey:'ID',mode:'token'},
 {label:'Eurostat ↔ fonte de publicação',left:'eurostat_serie',leftKey:'Fonte ID',right:'fontes',rightKey:'ID',mode:'token'},
 {label:'CSV enviado ↔ indicador canônico',left:'indicadores_recebidos',leftKey:'ID',right:'indicadores',rightKey:'ID',mode:'exact'}
];
const $ = id => document.getElementById(id);
const str = x => x==null?'':String(x);
const esc = x => str(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm = x => str(x).trim().toLocaleLowerCase('pt-BR');
const fmt = (x,d=0) => Number(x).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
const htmlBadge = (text,cl='')=>`<span class="badge ${cl}">${esc(text)}</span>`;
const niceName = k => IDS[k] || k.replace(/^importado_/, 'Importado · ').replaceAll('_',' ');
const keys = () => [...new Set(Object.keys(IDS).filter(k=>Array.isArray(D[k])).concat(Object.keys(D).filter(k=>k.startsWith('importado_')&&Array.isArray(D[k]))))];
function columns(arr){const ss=new Set;for(const r of arr.slice(0,2000)){Object.keys(r).forEach(x=>ss.add(x))}return [...ss]}
function setOpts(el,opts,sel){const prev=sel??el.value;el.innerHTML=opts.map(x=>{const id=Array.isArray(x)?x[0]:x,label=Array.isArray(x)?x[1]:x;return `<option value="${esc(id)}">${esc(label)}</option>`}).join('');if(opts.some(x=>(Array.isArray(x)?x[0]:x)===prev))el.value=prev;}
function safeUrl(text){const t=str(text).trim();try{let u=new URL(t);return ['https:','http:'].includes(u.protocol)?u.href:null}catch{return null}}
function pretty(v,full=false){if(v==null||v==='')return '<span class="muted">—</span>';let t=str(v);if(!full&&t.length>400)return `<span title="Ver campo em Detalhes">${esc(t.slice(0,250))}…</span>`;const urls=t.split(/\s+\|\s+/);if(urls.length>0&&urls.every(u=>safeUrl(u)))return urls.map((u,i)=>`<a href="${esc(safeUrl(u))}" target="_blank" rel="noopener noreferrer" title="${esc(u)}">Fonte ${i+1} ↗</a>`).join(' · ');const url=safeUrl(t);if(url)return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Abrir fonte ↗</a><br><span class="xs muted">${esc(t.slice(0,105))}</span>`;return esc(t)}
function safeCsv(v){let s=str(v);if(typeof v==='string' && /^[\s\u200b]*[=+@\-]/.test(s) && !/^\s*-?\d+(\.\d+)?\s*$/.test(s))s="'"+s;return /[;"\r\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s}
function rowsCSV(rows){if(!rows.length)return '\ufeff';const h=columns(rows);return '\ufeff'+h.map(safeCsv).join(';')+'\r\n'+rows.map(r=>h.map(k=>safeCsv(r[k])).join(';')).join('\r\n')}
function download(name,data,mime='text/csv;charset=utf-8'){const b=new Blob([data],{type:mime}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),2000)}
function dlCSV(name,rows){download(name,rowsCSV(rows))}
function dlJSON(name,rows){download(name,JSON.stringify(rows,null,2),'application/json;charset=utf-8')}
function textIncludes(row,term){return !term||Object.values(row).some(v=>norm(v).includes(term))}
function sortRows(rows,field,asc){if(!field)return rows;const c=rows.slice();c.sort((a,b)=>{const va=a[field],vb=b[field];if(typeof va==='number'&&typeof vb==='number')return (va-vb)*(asc?1:-1);return str(va).localeCompare(str(vb),'pt-BR',{numeric:true,sensitivity:'base'})*(asc?1:-1)});return c}
let detailSeq=0;const detailTables=new Map;
function makeTable(rows, {id='table',max=null,details=true,sortBy='',ascending=true}={}){
 if(!rows.length)return '<div class="empty">Nenhum registro encontrado para os filtros atuais.</div>';
 let ordered=sortRows(rows,sortBy,ascending), shown=max?ordered.slice(0,max):ordered, headers=columns(ordered);
 const tableToken=`t${++detailSeq}`;detailTables.set(tableToken,{name:id,rows:shown});if(detailTables.size>250){const first=detailTables.keys().next().value;detailTables.delete(first)}
 let html=`<div class="tablewrap"><table class="datatable"><thead><tr>${details?'<th>Registro</th>':''}${headers.map(h=>`<th data-sort-table="${esc(id)}" data-sort-key="${esc(h)}" title="Clique para ordenar">${esc(h)} ${sortBy===h?(ascending?'↑':'↓'):''}</th>`).join('')}</tr></thead><tbody>`;
 html+=shown.map((r,i)=>{
 let idx=i;
 return `<tr>${details?`<td class="narrow"><button class="open-row" data-record="${idx}" data-record-set="${tableToken}">Detalhes</button></td>`:''}${headers.map(c=>`<td>${pretty(r[c])}</td>`).join('')}</tr>`
 }).join('');
 html+='</tbody></table></div>';
 if(max&&ordered.length>max)html+=`<div class="blurb quiet">Prévia de ${fmt(shown.length)} de ${fmt(ordered.length)} linhas. A exportação inclui todas as correspondências.</div>`;
 return html;
}
function bindTable(container,sortCall){container.querySelectorAll('[data-record]').forEach(b=>b.addEventListener('click',()=>showRecord((()=>{const t=detailTables.get(b.dataset.recordSet);return t?{row:t.rows[Number(b.dataset.record)],name:t.name}:null})())));
 container.querySelectorAll('[data-sort-key]').forEach(th=>th.addEventListener('click',()=>sortCall?.(th.dataset.sortKey)));
}
function showRecord(entry){if(!entry)return;const row=entry.row;let id=row.ID??row['ID relação']??row['ID relação']??'Registro';$('detail-title').textContent=`${niceName(entry.name)} · ${id}`;
 $('detail-body').innerHTML=`<dl>${Object.entries(row).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${pretty(v,true)}</dd>`).join('')}</dl>`;
 $('detail-backdrop').classList.add('show');$('detail-close').focus();
}
function closeModal(){$('detail-backdrop').classList.remove('show')}
$('detail-close').addEventListener('click',closeModal);
$('detail-backdrop').addEventListener('click',e=>{if(e.target===$('detail-backdrop'))closeModal()});
window.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});
function nav(id){document.querySelectorAll('nav [data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===id));document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id===id));window.scrollTo({top:0,behavior:'instant'});if(id==='visao')renderHome();if(id==='estatistica')renderStats()}
document.querySelectorAll('nav [data-view]').forEach(btn=>btn.addEventListener('click',()=>nav(btn.dataset.view)));

// Visão geral
function renderHome(){let metrics=[['Fontes documentadas',D.fontes.length,'URLs, escopo e limites'],['Registros unificados',D.registros_unificados.length,'Não duplicados por arquivo'],['Vínculos documentais',D.arestas_documentais.length,'Não são casos criminais'],['Indicadores adicionais',D.indicadores.length,'34 linhas recebidas já presentes']];
 $('kpis').innerHTML=metrics.map(([label,val,sub])=>`<div class="metric-card"><div class="metric-num">${fmt(val)}</div><div class="metric-label">${esc(label)}</div><div class="metric-sub">${esc(sub)}</div></div>`).join('');
 const au=D.auditoria_integracao[0];$('audit-banner').innerHTML=`<strong>Integração sem duplicação:</strong> o CSV recebido tinha ${fmt(au['Linhas importadas'])} linhas; ${fmt(au['Correspondências idênticas'])} já constavam na base, ${fmt(au['Registros novos'])} eram novas e ${fmt(au['Registros diferentes'])} tinham diferenças. O original foi preservado como <strong>“CSV recebido”</strong> para auditoria.`;
 $('coverage').innerHTML=`<div class="mini"><b>${fmt(D.megabase.length)}</b><span>Linhas da tabela gigante (hipóteses de relacionamento)</span></div><div class="progress"><div><div class="fill" style="width:100%"></div></div><span class="xs">${fmt(D.correlacoes.length)} planos</span></div><p class="small muted">${fmt(D.perguntas.length)} perguntas, ${fmt(D.evidencias.length)} evidências documentais, ${fmt(D.observacoes.length)} observações quantitativas heterogêneas e ${fmt(D.eurostat_serie.length)} anos de série histórica.</p><p class="small"><strong>Use “Cruzar tabelas”</strong> para abrir registros correspondentes por ID ou <strong>“Data Science”</strong> para calcular correlações em dados numéricos compatíveis.</p>`;
 $('home-series').innerHTML=makeLineSvg(D.eurostat_serie,'Ano',['Exploração sexual (%)','Trabalho forçado (%)','Outras modalidades (%)'],460,285);
}

// Todos os dados e tabelas importadas
const rawState={dataset:'registros_unificados',search:'',field:'',value:'',all:false,sort:'',asc:true};
function populateAllSelectors(){setOpts($('raw-dataset'),keys().map(k=>[k,`${niceName(k)} (${fmt(D[k].length)})`]),rawState.dataset);
 for(const id of ['join-left','join-right'])setOpts($(id),keys().map(k=>[k,niceName(k)]));
 const numeric=keys().filter(k=>findNumericColumns(D[k]).length>=2);
 const options=[...numeric.map(k=>[k,`${niceName(k)} (${D[k].length})`])];if(Array.isArray(D.__join__))options.push(['__join__',`Última junção (${D.__join__.length})`]);
 setOpts($('stat-source'),options,'eurostat_serie');}
function rawCols(){return columns(D[rawState.dataset]||[])}
function refreshRawCols(){setOpts($('raw-field'),[['','Qualquer coluna'],...rawCols().map(h=>[h,h])],rawState.field);rawState.field=$('raw-field').value}
function rawFiltered(dataset){const q=norm(rawState.search),f=rawState.field,v=norm(rawState.value);return (D[dataset]||[]).filter(r=>textIncludes(r,q)&&(!f||dataset!==rawState.dataset||norm(r[f]).includes(v)))}
function renderRaw(){
 if(rawState.all){let total=0;const html=keys().map(k=>{let rows=rawFiltered(k);total+=rows.length;return `<div class="table-section"><h3>${esc(niceName(k))} ${htmlBadge(rows.length+' linhas','gray')}</h3>${makeTable(rows,{id:k})}</div>`}).join('');$('raw-count').textContent=`${fmt(total)} linhas distribuídas por ${fmt(keys().length)} conjuntos, sem paginação.`;$('raw-table').innerHTML=html;
 }else{let rows=rawFiltered(rawState.dataset);$('raw-count').textContent=`${fmt(rows.length)} de ${fmt(D[rawState.dataset].length)} linhas · ${rawCols().length} campos · dados originais preservados.`;$('raw-table').innerHTML=makeTable(rows,{id:rawState.dataset,sortBy:rawState.sort,ascending:rawState.asc});}
 bindTable($('raw-table'),col=>{if(rawState.all)return;rawState.asc=rawState.sort===col?!rawState.asc:true;rawState.sort=col;renderRaw()})}
$('raw-dataset').addEventListener('change',e=>{rawState.dataset=e.target.value;rawState.field='';rawState.value='';rawState.sort='';$('raw-value').value='';refreshRawCols();renderRaw()});
$('raw-search').addEventListener('input',e=>{rawState.search=e.target.value;renderRaw()});
$('raw-field').addEventListener('change',e=>{rawState.field=e.target.value;renderRaw()});
$('raw-value').addEventListener('input',e=>{rawState.value=e.target.value;renderRaw()});
$('btn-every-dataset').addEventListener('click',()=>{rawState.all=!rawState.all;$('btn-every-dataset').textContent=rawState.all?'Mostrar apenas tabela selecionada':'Mostrar todas as tabelas';renderRaw()});
$('raw-clear').addEventListener('click',()=>{rawState.search='';rawState.field='';rawState.value='';rawState.sort='';$('raw-search').value='';$('raw-value').value='';refreshRawCols();renderRaw()});
$('raw-export-csv').addEventListener('click',()=>dlCSV(`${rawState.dataset}_filtrado.csv`,rawFiltered(rawState.dataset)));
$('raw-export-json').addEventListener('click',()=>dlJSON(`${rawState.dataset}_filtrado.json`,rawFiltered(rawState.dataset)));
$('raw-all-json').addEventListener('click',()=>dlJSON('dados_completos_integrados.json',D));
$('export-manifest').addEventListener('click',()=>dlCSV('catalogo_de_conjuntos.csv',keys().map(k=>({'Conjunto':k,'Nome':niceName(k),'Linhas':D[k].length,'Colunas':columns(D[k]).length,'Situação':k.startsWith('importado_')?'Carregado localmente':'Incorporado offline'}))));

// CSV e JSON importados dinamicamente
function detectDelimiter(text){let row='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){i++;continue}quoted=!quoted}if(!quoted&&(c==='\n'||c==='\r'))break;row+=c}let counts=[';',',','\t'].map(d=>[d,row.split(d).length-1]);counts.sort((a,b)=>b[1]-a[1]);return counts[0][1]>0?counts[0][0]:';'}
function parseDelimited(text){text=text.replace(/^\ufeff/,'');const delim=detectDelimiter(text);let records=[],field='',row=[],quoted=false;
 for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){field+='"';i++}else quoted=!quoted}else if(!quoted&&c===delim){row.push(field);field=''}else if(!quoted&&(c==='\n'||c==='\r')){if(c==='\r'&&text[i+1]==='\n')i++;row.push(field);if(row.some(x=>x.trim()!==''))records.push(row);row=[];field=''}else field+=c;}
 if(quoted)throw new Error('CSV com aspas não fechadas');if(field!==''||row.length){row.push(field);if(row.some(x=>x.trim()!==''))records.push(row)}
 if(records.length<2)throw new Error('CSV sem linhas de dados');let head=records.shift().map((s,i)=>s.trim()||'Coluna '+(i+1));let uniques=new Set;head=head.map(h=>{let v=h,i=2;while(uniques.has(v))v=h+'_'+i++;uniques.add(v);return v});return records.map(r=>Object.fromEntries(head.map((h,i)=>[h,r[i]??''])))}
function normalizeImportedRows(rows){if(!Array.isArray(rows)||!rows.every(x=>x&&typeof x==='object'&&!Array.isArray(x)))throw Error('Preciso de uma lista JSON de objetos.');return rows.map(x=>Object.fromEntries(Object.entries(x).map(([k,v])=>[k,typeof v==='object'&&v!==null?JSON.stringify(v):v])))}
$('upload-files').addEventListener('change',async e=>{let reports=[];for(const file of e.target.files){try{
 if(file.size>20*1024*1024)throw Error('Arquivos individuais devem ter até 20 MB.');const txt=await file.text();let records;if(file.name.toLowerCase().endsWith('.json')){let j=JSON.parse(txt);records=normalizeImportedRows(Array.isArray(j)?j:(j.records||j.data||[]))}else records=parseDelimited(txt);
 if(records.length<1)throw Error('Sem registros.');const id='importado_'+str(file.name.replace(/\.[^.]+$/,'')).replace(/[^a-zA-Z0-9_]/g,'_').slice(0,55)+'_'+(Object.keys(D).filter(k=>k.startsWith('importado_')).length+1);
 D[id]=records;IDS[id]=`Arquivo importado · ${file.name}`;reports.push(`${file.name}: ${fmt(records.length)} linhas carregadas (sessão local)`);
 }catch(err){reports.push(`${file.name}: erro — ${err.message}`)}}$('upload-status').textContent=reports.join(' • ')||'Nenhuma alteração.';
 populateAllSelectors();refreshRawCols();renderRaw();setupJoinSelectors();setupStatsSource();e.target.value='';});

// Junção relacional com chaves exatas e listas de IDs.
const joinState={rows:[],left:'megabase',right:'indicadores',leftKey:'Indicador ID',rightKey:'ID',mode:'exact',search:'',sort:'',asc:true,statsEligible:false,multiplied:false};
function keyTokens(v,mode){const raw=str(v).trim();if(!raw)return [];return [...new Set((mode==='token'?raw.split(/[;|]/):[raw]).map(s=>s.trim().normalize('NFC').toLocaleUpperCase('pt-BR')).filter(Boolean))]}
function setupJoinSelectors(){const l=$('join-left').value||joinState.left,r=$('join-right').value||joinState.right;
 if(D[l])setOpts($('join-left'),keys().map(k=>[k,niceName(k)]),l);
 if(D[r])setOpts($('join-right'),keys().map(k=>[k,niceName(k)]),r);
 setOpts($('join-left-key'),columns(D[$('join-left').value]||[]),joinState.leftKey);
 setOpts($('join-right-key'),columns(D[$('join-right').value]||[]),joinState.rightKey);
}
function setJoinPreset(p){joinState.left=p.left;joinState.right=p.right;joinState.leftKey=p.leftKey;joinState.rightKey=p.rightKey;joinState.mode=p.mode;
 setOpts($('join-left'),keys().map(k=>[k,niceName(k)]),p.left);setOpts($('join-right'),keys().map(k=>[k,niceName(k)]),p.right);
 setOpts($('join-left-key'),columns(D[p.left]),p.leftKey);setOpts($('join-right-key'),columns(D[p.right]),p.rightKey);$('join-mode').value=p.mode;
}
function initJoin(){setOpts($('join-preset'),[['manual','Escolher manualmente'],...joins.map((p,i)=>[String(i),p.label])], '0');setJoinPreset(joins[0]);
 for(let id of ['join-left','join-right'])$(id).addEventListener('change',()=>{setOpts($(id==='join-left'?'join-left-key':'join-right-key'),columns(D[$(id).value]||[]));$('join-preset').value='manual'});
 for(let id of ['join-left-key','join-right-key','join-mode'])$(id).addEventListener('change',()=>{$('join-preset').value='manual'});
 $('join-preset').addEventListener('change',e=>{if(e.target.value!=='manual')setJoinPreset(joins[Number(e.target.value)])});
 $('join-custom').addEventListener('click',()=>{$('join-preset').value='manual';$('join-left').focus()});
 $('join-run').addEventListener('click',runJoin);$('join-search').addEventListener('input',e=>{joinState.search=e.target.value;renderJoined()});
 $('join-export').addEventListener('click',()=>dlCSV('cruzamento_tabelas.csv',joinedFiltered()));
 $('join-export-json').addEventListener('click',()=>dlJSON('cruzamento_tabelas.json',joinedFiltered()));}
function runJoin(){const l=$('join-left').value,r=$('join-right').value,lk=$('join-left-key').value,rk=$('join-right-key').value,mode=$('join-mode').value;
 const A=D[l]||[],B=D[r]||[];if(!A.length||!B.length){$('join-warning').textContent='Tabela vazia. Importe registros ou escolha outras tabelas.';return}
 const rhs=new Map();let uniqueR=true;
 for(const [i,row] of B.entries())for(const key of keyTokens(row[rk],mode)){if(!rhs.has(key))rhs.set(key,[]);rhs.get(key).push(i);if(rhs.get(key).length>1)uniqueR=false}
 const result=[];let countL=0;let repeated=false;let matchedDistinctR=new Set;
 for(const [i,row] of A.entries()){
  const found=new Set();for(const k of keyTokens(row[lk],mode))for(const j of (rhs.get(k)||[]))found.add(j);
  if(found.size){countL++;if(found.size>1)repeated=true}
  for(const j of found){matchedDistinctR.add(j);const other=B[j];let out={'Chave A':str(row[lk]),'Chave B':str(other[rk])};for(const [key,val] of Object.entries(row))out['A · '+key]=val;for(const [key,val] of Object.entries(other))out['B · '+key]=val;
    result.push(out);if(result.length>50000)break;}
  if(result.length>50000)break;
 }
 joinState.rows=result;joinState.left=l;joinState.right=r;joinState.leftKey=lk;joinState.rightKey=rk;joinState.mode=mode;joinState.multiplied=repeated||!uniqueR;
 const isNumeric=(arr)=>findNumericColumns(arr).length>=2;
 joinState.statsEligible=!joinState.multiplied && result.length>=3 && (l==='eurostat_serie'||r==='eurostat_serie'||l.startsWith('importado_')||r.startsWith('importado_')) && isNumeric(result);
 D.__join__=result;IDS.__join__='Última junção de tabelas';populateAllSelectors();renderJoined();
 let msg=`Junção executada: ${fmt(result.length)} linha(s); ${fmt(countL)} de ${fmt(A.length)} registros da tabela A corresponderam a ${fmt(matchedDistinctR.size)} de ${fmt(B.length)} registros da tabela B.`;
 if(joinState.multiplied)msg+=' Foram encontradas correspondências de muitos-para-muitos; as linhas repetidas NÃO representam observações independentes.';
 if(result.length>50000)msg+=' Limite de segurança de 50.000 linhas atingido; resultado truncado.';
 msg+=' Trata-se de um vínculo por chave, não de evidência de crime.';
 $('join-warning').className='blurb '+(joinState.multiplied?'warning':'ok');$('join-warning').textContent=msg;
 $('join-mode-note').textContent=mode==='token'?'Chave com múltiplos IDs':'Correspondência exata';
}
function joinedFiltered(){const term=norm(joinState.search);return joinState.rows.filter(r=>textIncludes(r,term))}
function renderJoined(){let rows=joinedFiltered();$('join-count').textContent=`${fmt(rows.length)} de ${fmt(joinState.rows.length)} linhas na junção atual.`;
 $('join-table').innerHTML=makeTable(rows,{id:'__join__',max:180,sortBy:joinState.sort,ascending:joinState.asc});bindTable($('join-table'),field=>{joinState.asc=joinState.sort===field?!joinState.asc:true;joinState.sort=field;renderJoined()})}

// Matriz e drill-down, sempre contagens de vínculos.
function matrixFields(){const all=columns(D.megabase);return all.filter(k=>['Dimensão','Correlação ID','Natureza do sinal','Força da vinculação metodológica','Indicador ID'].includes(k))}
function initHeat(){setOpts($('heat-dim'),matrixFields(),'Dimensão');setOpts($('heat-cross'),matrixFields(),'Correlação ID');$('heat-dim').addEventListener('change',renderHeat);$('heat-cross').addEventListener('change',renderHeat);$('heat-reset').addEventListener('click',()=>{$('heat-dim').value='Dimensão';$('heat-cross').value='Correlação ID';renderHeat()});renderHeat()}
function renderHeat(){let y=$('heat-dim').value,x=$('heat-cross').value;if(x===y){$('heat-map').textContent='Escolha dois campos diferentes.';return}
 const categories=(k)=>[...new Set(D.megabase.map(r=>str(r[k])))].sort((a,b)=>a.localeCompare(b,'pt-BR',{numeric:true}));
 let yy=categories(y),xx=categories(x);let max=0, counts=new Map;
 for(const r of D.megabase){let key=r[y]+'\u0000'+r[x],n=(counts.get(key)||0)+1;counts.set(key,n);max=Math.max(max,n)}
 let t=`<table class="heat"><thead><tr><th>${esc(y)} ↓ / ${esc(x)} →</th>${xx.map(v=>`<th title="${esc(v)}">${esc(v)}</th>`).join('')}</tr></thead><tbody>`;
 for(const ry of yy){t+=`<tr><th>${esc(ry)}</th>`;for(const cx of xx){let n=counts.get(ry+'\u0000'+cx)||0;let rank=n===0?0:n/max<.2?1:n/max<.42?2:n/max<.72?3:4;t+=`<td class="v${rank}" tabindex="0" role="button" data-matrix-row="${esc(encodeURIComponent(ry))}" data-matrix-col="${esc(encodeURIComponent(cx))}" title="Ver ${n} vínculo(s)">${n||'·'}</td>`}t+='</tr>'}
 t+='</tbody></table>';$('heat-map').innerHTML=t;
 $('heat-map').querySelectorAll('[data-matrix-row]').forEach(td=>{const fn=()=>{let a=decodeURIComponent(td.dataset.matrixRow),b=decodeURIComponent(td.dataset.matrixCol);let rows=D.megabase.filter(r=>str(r[y])===a&&str(r[x])===b);$('heat-drill').innerHTML=`<div class="table-section"><h3>${esc(a)} × ${esc(b)} · ${rows.length} vínculos</h3>${makeTable(rows,{id:'megabase'})}</div>`;bindTable($('heat-drill'))};td.addEventListener('click',fn);td.addEventListener('keydown',e=>{if(e.key==='Enter')fn()})});}

// Utilitários numéricos e correlações
function strictNum(raw){if(typeof raw==='number'&&Number.isFinite(raw))return raw;if(typeof raw!=='string')return null;let s=raw.trim();if(s==='')return null;
 if(!/^[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)$/.test(s))return null;
 if(s.includes(','))s=s.replace(',','.');const v=Number(s);return Number.isFinite(v)?v:null}
function findNumericColumns(rows){if(!rows?.length)return [];const h=columns(rows);return h.filter(col=>{let valid=0,nonnull=0;for(const r of rows.slice(0,800)){let v=r[col];if(v!==''&&v!=null){nonnull++;if(strictNum(v)!==null)valid++}}return valid>=3 && nonnull>=3 && valid/nonnull>=.82;})}
function rank(vals){let idx=vals.map((v,i)=>[v,i]).sort((a,b)=>a[0]-b[0]),rs=Array(vals.length);for(let i=0;i<idx.length;){let j=i+1;while(j<idx.length&&idx[j][0]===idx[i][0])j++;let v=((i+1)+j)/2;for(let k=i;k<j;k++)rs[idx[k][1]]=v;i=j}return rs}
function Pearson(xs,ys){let n=xs.length;if(n<3)return null;const mx=xs.reduce((a,b)=>a+b,0)/n,my=ys.reduce((a,b)=>a+b,0)/n;let xx=0,yy=0,xy=0;for(let i=0;i<n;i++){let dx=xs[i]-mx,dy=ys[i]-my;xx+=dx*dx;yy+=dy*dy;xy+=dx*dy}if(xx===0||yy===0)return null;let r=xy/Math.sqrt(xx*yy);return {n,r:Math.max(-1,Math.min(1,r)),slope:xy/xx,intercept:my-(xy/xx)*mx,r2:r*r}}
function statOverview(rows,x,y){let pairs=rows.map((r,i)=>({x:strictNum(r[x]),y:strictNum(r[y]),source:r,ord:i})).filter(r=>r.x!==null&&r.y!==null);let p=Pearson(pairs.map(z=>z.x),pairs.map(z=>z.y));if(!p)return {pairs,p:null,sp:null};let xs=pairs.map(z=>z.x),ys=pairs.map(z=>z.y);let sp=Pearson(rank(xs),rank(ys));return {pairs,p,sp};}
function fmt2(v){return v===null||v===undefined||!Number.isFinite(v)?'—':fmt(v,3)}
function scale(min,max,a,b){return x=>a+(x-min)/((max-min)||1)*(b-a)}
function expandRange(vals){let lo=Math.min(...vals),hi=Math.max(...vals);if(lo===hi){let m=Math.abs(lo)*.15||1;return [lo-m,hi+m]}let pad=(hi-lo)*.07;return [lo-pad,hi+pad]}
const palette=['#137a87','#995cb6','#c68b42','#a63e56'];
function plotAxes(w,h,p,minx,maxx,miny,maxy){let innerW=w-p.l-p.r,innerH=h-p.t-p.b,sx=scale(minx,maxx,p.l,p.l+innerW),sy=scale(miny,maxy,p.t+innerH,p.t);
 let out='';for(let i=0;i<=4;i++){let vy=miny+(maxy-miny)*i/4,py=sy(vy);out+=`<line x1="${p.l}" y1="${py}" x2="${w-p.r}" y2="${py}" stroke="#e4ecf0" stroke-width="1"/><text class="plot-label" x="${p.l-9}" y="${py+4}" text-anchor="end">${esc(fmt(vy,Math.abs(maxy-miny)<10?1:0))}</text>`;const isYear=minx>1900&&maxx<2100;let vx=minx+(maxx-minx)*i/4;if(isYear)vx=Math.round(vx);let px=sx(vx);out+=`<text class="plot-label" x="${px}" y="${h-16}" text-anchor="middle">${esc(isYear?String(Math.round(vx)):fmt(vx,Math.abs(maxx-minx)<40?1:0))}</text>`}
 return {out,sx,sy}}
function scatterSvg(pairs,info,w=560,h=305){if(!pairs.length)return '<div class="empty">Sem dados.</div>';let xs=pairs.map(d=>d.x),ys=pairs.map(d=>d.y),[xmin,xmax]=expandRange(xs),[ymin,ymax]=expandRange(ys),p={l:65,r:22,t:20,b:40};let {out,sx,sy}=plotAxes(w,h,p,xmin,xmax,ymin,ymax);
 if(info){let x1=Math.min(...xs),x2=Math.max(...xs),y1=info.slope*x1+info.intercept,y2=info.slope*x2+info.intercept;out+=`<line x1="${sx(x1)}" y1="${sy(y1)}" x2="${sx(x2)}" y2="${sy(y2)}" stroke="#b68b40" stroke-width="2.5" stroke-dasharray="6 5"/>`}
 out+=pairs.map(d=>`<circle cx="${sx(d.x)}" cy="${sy(d.y)}" r="4.1" fill="#0f8791" opacity=".85"><title>X: ${esc(d.x)} · Y: ${esc(d.y)}</title></circle>`).join('');
 return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Dispersão de pares numéricos"><rect width="${w}" height="${h}" fill="#fff"/>${out}</svg>`}
function linePairsSvg(pairs,w=560,h=305){if(!pairs.length)return '<div class="empty">Sem dados.</div>';let sorted=pairs.slice().sort((a,b)=>a.x-b.x),xx=sorted.map(d=>d.x),yy=sorted.map(d=>d.y),[xmin,xmax]=expandRange(xx),[ymin,ymax]=expandRange(yy),p={l:65,r:22,t:20,b:40};let {out,sx,sy}=plotAxes(w,h,p,xmin,xmax,ymin,ymax);
 out+=`<polyline points="${sorted.map(d=>`${sx(d.x)},${sy(d.y)}`).join(' ')}" stroke="#12838b" stroke-width="2.3" fill="none"/>`+sorted.map(d=>`<circle cx="${sx(d.x)}" cy="${sy(d.y)}" r="4" fill="#12838b"><title>${esc(d.x)} — ${esc(d.y)}</title></circle>`).join('');return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Série ordenada pela variável X"><rect width="${w}" height="${h}" fill="#fff"/>${out}</svg>`}
function makeLineSvg(rows,x,ys,w=560,h=295){let xs=rows.map(r=>strictNum(r[x])),series=ys.map(y=>rows.map(r=>strictNum(r[y])));let flat=series.flat().filter(x=>x!==null),vmax=Math.max(100,...flat),p={l:53,r:17,t:23,b:59},xx=[Math.min(...xs),Math.max(...xs)],yy=[0,vmax],{out,sx,sy}=plotAxes(w,h,p,xx[0],xx[1],yy[0],yy[1]);
 for(let j=0;j<ys.length;j++){let points=rows.map((r,i)=>[sx(xs[i]),sy(series[j][i])]);out+=`<polyline points="${points.map(p=>p.join(',')).join(' ')}" stroke="${palette[j]}" fill="none" stroke-width="2.7"/>`+points.map((v,i)=>`<circle cx="${v[0]}" cy="${v[1]}" r="3.6" fill="${palette[j]}"><title>${esc(xs[i])}: ${esc(ys[j])} = ${esc(series[j][i])}%</title></circle>`).join('')}
 out+=ys.map((key,i)=>`<rect x="${15+i*173}" y="${h-16}" width="10" height="9" fill="${palette[i]}"/><text class="plot-label" x="${29+i*173}" y="${h-7}">${esc(key.replace(' (%)',''))}</text>`).join('');return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Evolução da composição dos registros"><rect width="${w}" height="${h}" fill="#fff"/>${out}</svg>`}
function countryRateSvg(){let rows=D.observacoes.filter(r=>r.Categoria==='Eurostat — taxa territorial');const w=650,h=Math.max(260,rows.length*37+35),pl=135,pr=70,barW=w-pl-pr,max=Math.max(...rows.map(r=>r.Valor))*1.12;
 let out='';rows.forEach((r,i)=>{let top=14+i*37,v=Number(r.Valor),len=barW*v/max;out+=`<text class="plot-label" x="${pl-12}" y="${top+17}" text-anchor="end">${esc(r.Geografia)}</text><rect x="${pl}" y="${top}" height="23" width="${len}" fill="#1e8990" rx="3"/><text class="plot-label" x="${pl+len+8}" y="${top+16}">${fmt(v)}</text>`});return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Taxas de vítimas registradas por milhão de pessoas"><rect width="${w}" height="${h}" fill="white"/>${out}</svg>`}

// O campo de grupo exige semântica comparável, não apenas números.
function isComparableDataset(key,rows){if(key==='eurostat_serie')return {valid:true,reason:'Série anual publicada: interpretações limitadas à composição percentual dos registros.'};
 if(['megabase','arestas_documentais','registros_unificados','fontes','indicadores','indicadores_recebidos','perguntas','correlacoes','auditoria_integracao'].includes(key))return {valid:false,reason:'Conjunto documental/catálogo. Não representa pares de mensurações quantitativas.'};
 if(['observacoes','evidencias'].includes(key))return {valid:false,reason:'Reúne indicadores, unidades, universos e períodos distintos. Use uma tabela homogênea construída a partir de observações comparáveis.'};
 if(key==='__join__'&&!joinState.statsEligible)return {valid:false,reason:'Junção não é um painel numérico independente 1:1. Se houver repetição de linhas, ela causaria pseudorreplicação; faça a agregação correta antes da análise.'};
 const units=new Set(rows.map(r=>r.Unidade).filter(x=>x!=null&&x!==''));if(units.size>1)return {valid:false,reason:'Existem unidades diferentes nesta amostra; filtre para uma só unidade.'};
 return {valid:true,reason:'Conjunto numérico importado ou junção 1:1. Verifique manualmente universo, período, unidade, independência e valores ausentes.'}}
function statRows(){let arr=D[$('stat-source').value]||[];const c=$('stat-filter-col').value,v=$('stat-filter-val').value;return c&&v!=='__all__'?arr.filter(r=>str(r[c])===v):arr}
function setupStatsSource(){let key=$('stat-source').value;if(!D[key])key='eurostat_serie';let sources=keys().filter(k=>findNumericColumns(D[k]).length>=2).map(k=>[k,`${niceName(k)} (${D[k].length})`]);if(D.__join__?.length&&findNumericColumns(D.__join__).length>=2&&!sources.some(o=>o[0]==='__join__'))sources.push(['__join__','Última junção · análise numérica']);setOpts($('stat-source'),sources,key);setupStatFields()}
function setupStatFields(){let key=$('stat-source').value,rows=D[key]||[],nums=findNumericColumns(rows),oldx=$('stat-x').value,oldy=$('stat-y').value;
 const defaultX=nums.includes('Ano')?'Ano':nums[0],defaultY=nums.includes('Trabalho forçado (%)')?'Trabalho forçado (%)':nums.find(x=>x!==defaultX)||nums[0];
 setOpts($('stat-x'),nums,nums.includes(oldx)?oldx:defaultX);setOpts($('stat-y'),nums,nums.includes(oldy)?oldy:defaultY);
 const flds=columns(rows).filter(c=>{let vals=new Set(rows.slice(0,2000).map(x=>str(x[c])));return vals.size>1&&vals.size<=45});setOpts($('stat-filter-col'),[['','Sem filtro'],...flds.map(x=>[x,x])],'');setupStatFilter();}
function setupStatFilter(){let field=$('stat-filter-col').value;let vals=field?[...new Set((D[$('stat-source').value]||[]).map(r=>str(r[field])))].sort((a,b)=>a.localeCompare(b,'pt-BR',{numeric:true})):[];setOpts($('stat-filter-val'),[['__all__','Todos'],...vals.map(v=>[v,v||'(vazio)'])],'__all__')}
$('stat-source').addEventListener('change',setupStatFields);
$('stat-filter-col').addEventListener('change',setupStatFilter);
$('stat-run').addEventListener('click',renderStats);
$('stat-x').addEventListener('change',renderStats);
$('stat-y').addEventListener('change',renderStats);
$('stat-filter-val').addEventListener('change',renderStats);
let currentPairs=[];
function renderStats(){const key=$('stat-source').value,x=$('stat-x').value,y=$('stat-y').value,rows=statRows();let check=isComparableDataset(key,rows),overview=statOverview(rows,x,y),{pairs,p,sp}=overview;currentPairs=pairs;
 const warn=$('stat-warning'),met=$('stat-metrics');
 if(!check.valid){warn.className='blurb warning';warn.textContent=check.reason;met.innerHTML='';$('stat-scatter').innerHTML='<div class="empty">Cálculo desabilitado para dados heterogêneos ou de catálogo.</div>';$('stat-lines').innerHTML='';$('stat-pairs').innerHTML='';return}
 if(x===y){warn.className='blurb warning';warn.textContent='Selecione duas variáveis diferentes. A autocorrelação de uma variável consigo mesma é trivial.';met.innerHTML='';$('stat-scatter').innerHTML='';$('stat-lines').innerHTML='';$('stat-pairs').innerHTML='';return}
 if(!p){warn.className='blurb warning';warn.textContent=`Não é possível calcular correlação: ${fmt(pairs.length)} par(es) completos ou variância nula. São necessários pelo menos 3 pares e valores variados.`;met.innerHTML='';$('stat-scatter').innerHTML='';$('stat-lines').innerHTML='';$('stat-pairs').innerHTML='';return}
 warn.className='blurb '+(key==='eurostat_serie'?'quiet':'warning');warn.textContent=check.reason+' • Resultados exploratórios; correlação não implica causalidade.';
 met.innerHTML=[['Pares válidos',fmt(p.n),`de ${rows.length} linhas`],['Pearson r',fmt2(p.r),'associação linear'],['Spearman ρ',fmt2(sp?.r),'associação monotônica'],['Regressão: inclinação',fmt2(p.slope),'unidades de Y por unidade de X']].map(([a,b,c])=>`<div class="mini"><span>${esc(a)}</span><b>${esc(b)}</b><span>${esc(c)}</span></div>`).join('');
 $('stat-scatter-heading').textContent=`Dispersão: ${x} × ${y}`;$('stat-scatter').innerHTML=scatterSvg(pairs,p);$('stat-lines').innerHTML=linePairsSvg(pairs);
 $('stat-pairs').innerHTML=`<table><thead><tr><th>Linha original</th><th>${esc(x)}</th><th>${esc(y)}</th></tr></thead><tbody>${pairs.map(a=>`<tr><td>${a.ord+1}</td><td>${esc(a.x)}</td><td>${esc(a.y)}</td></tr>`).join('')}</tbody></table>`;
}
$('stat-pairs-csv').addEventListener('click',()=>dlCSV('pares_numericos_validos.csv',currentPairs.map(x=>({linha:x.ord+1,'X':x.x,'Y':x.y}))));

// Rede de referências documentais
let networkRows=[];
function initNetwork(){let kinds=[...new Set(D.arestas_documentais.map(r=>r['Tipo de vínculo']))];setOpts($('network-kind'),[['','Todos os tipos'],...kinds.map(x=>[x,x])],'');let values=[...new Set(D.arestas_documentais.flatMap(r=>[r['Origem ID'],r['Destino ID']]))];$('id-suggestions').innerHTML=values.map(v=>`<option value="${esc(v)}"></option>`).join('');$('network-search').addEventListener('click',renderNetwork);$('network-node').addEventListener('keydown',e=>{if(e.key==='Enter')renderNetwork()});$('network-kind').addEventListener('change',renderNetwork);$('network-export').addEventListener('click',()=>dlCSV('rede_documental.csv',networkRows));renderNetwork()}
function networkSvg(node,rows){let neighbors=[...new Set(rows.map(r=>r['Origem ID']===node?r['Destino ID']:r['Origem ID']))];if(!neighbors.length)return '<div class="empty">Nenhum vínculo localizado para esse identificador.</div>';let view=neighbors.slice(0,22),w=720,h=380,cx=w/2,cy=h/2,radius=144;let pieces=[];
 view.forEach((id,i)=>{let angle=2*Math.PI*i/view.length-Math.PI/2,x=cx+Math.cos(angle)*radius*1.7,y=cy+Math.sin(angle)*radius,xx=Math.min(w-65,Math.max(65,x));pieces.push(`<line x1="${cx}" y1="${cy}" x2="${xx}" y2="${y}" stroke="#a5cbd0" stroke-width="1.4"/><rect x="${xx-24}" y="${y-13}" width="48" height="26" rx="10" fill="#ecf6f6" stroke="#b2d5d7"/><text x="${xx}" y="${y+4}" text-anchor="middle" font-size="11" fill="#1b6875" font-weight="700">${esc(id)}</text>`)});
 pieces.push(`<circle cx="${cx}" cy="${cy}" r="29" fill="#0b7884"/><text x="${cx}" y="${cy+4}" text-anchor="middle" fill="white" font-size="12" font-weight="750">${esc(node)}</text>`);
 return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Grafo local de vínculos documentais"><rect width="${w}" height="${h}" fill="white"/>${pieces.join('')}</svg>${neighbors.length>22?`<div class="caption">Exibindo 22 de ${neighbors.length} identificadores no gráfico. A tabela contém todas as ligações.</div>`:''}`}
function renderNetwork(){const node=str($('network-node').value).trim().toLocaleUpperCase('pt-BR'),kind=$('network-kind').value;networkRows=D.arestas_documentais.filter(r=>(r['Origem ID']===node||r['Destino ID']===node)&&(!kind||r['Tipo de vínculo']===kind));
 const kinds=[...new Set(networkRows.map(r=>r['Tipo de vínculo']))];$('network-summary').innerHTML=`<strong>${fmt(networkRows.length)} vínculo(s)</strong> para <strong>${esc(node)}</strong>. Tipos presentes: ${esc(kinds.join(', ')||'nenhum')}. O gráfico mostra relações documentais, não operações criminais ou relações pessoais.`;
 $('network-graph').innerHTML=networkSvg(node,networkRows);$('network-table').innerHTML=makeTable(networkRows,{id:'arestas_documentais',max:150});bindTable($('network-table'));}

// Fontes e procedência
function initSources(){const opts=[['','Todas as categorias'],...[...new Set(D.fontes.map(r=>r.Categoria))].sort().map(v=>[v,v])];setOpts($('source-type'),opts,'');const geo=[['','Todas as regiões'],...[...new Set(D.fontes.map(r=>r['Escopo geográfico']))].sort().map(v=>[v,v])];setOpts($('source-geo'),geo,'');
 $('source-search').addEventListener('input',renderSources);$('source-type').addEventListener('change',renderSources);$('source-geo').addEventListener('change',renderSources);$('export-sources').addEventListener('click',()=>dlCSV('fontes_catalogadas.csv',D.fontes));renderSources()}
function renderSources(){const q=norm($('source-search').value),cat=$('source-type').value,geo=$('source-geo').value;let rows=D.fontes.filter(r=>textIncludes(r,q)&&(!cat||r.Categoria===cat)&&(!geo||r['Escopo geográfico']===geo));$('sources-count').textContent=`${rows.length} fonte(s) de ${D.fontes.length}. A referência não significa que todos os microdados foram baixados.`;
 $('sources-grid').innerHTML=rows.map(r=>{let link=safeUrl(r['URL oficial ou pública']);return `<article class="source-card"><div class="source-id">${esc(r.ID)} · ${esc(r['Escopo geográfico'])}</div><h4>${esc(r.Fonte)}</h4><p>${esc(r['O que fornece'])}</p><div class="meta">${esc(r.Categoria)} · ${esc(r['Acesso disponível'])}</div><div class="bottom">${htmlBadge(r['Origem do catálogo']||'Fonte','gray')}${link?`<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">Consultar origem ↗</a>`:'URL indisponível'}</div></article>`}).join('');}

// Inicialização
function boot(){populateAllSelectors();refreshRawCols();renderRaw();renderHome();initJoin();initHeat();setupStatsSource();renderStats();$('country-rates').innerHTML=countryRateSvg();initNetwork();initSources();}
boot();
// Permite testes automatizados locais sem qualquer rede.
window.ObservatorioTeste={D,joins,runJoin,statOverview,strictNum,parseDelimited,findNumericColumns,renderStats,networkSearch:()=>networkRows};
