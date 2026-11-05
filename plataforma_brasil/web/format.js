'use strict';
(function(root){
  const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function text(value){
    if(value===null||value===undefined||value==='')return 'Não informado';
    if(typeof value==='boolean')return value?'Sim':'Não';
    if(typeof value==='number')return value.toLocaleString('pt-BR');
    return String(value);
  }
  function html(value){
    if(value===null||value===undefined||value==='')return '<span class="muted">Não informado</span>';
    if(Array.isArray(value))return value.length?'<ul>'+value.map(v=>'<li>'+html(v)+'</li>').join('')+'</ul>':'<span class="muted">Nenhum item registrado</span>';
    if(typeof value==='object')return '<dl class="metadata">'+Object.entries(value).filter(([,v])=>v!==null&&v!==undefined).map(([k,v])=>'<dt>'+esc(k.replaceAll('_',' '))+'</dt><dd>'+html(v)+'</dd>').join('')+'</dl>';
    if(typeof value==='string'&&/^https?:\/\//.test(value)){
      try{const url=new URL(value);return '<a href="'+esc(url.href)+'" target="_blank" rel="noopener noreferrer">'+esc(value)+'</a>';}catch{}
    }
    return esc(text(value));
  }
  function periods(record){
    const metadata=record.metadados||{}, refs=metadata.periodos_referencia||[];
    if(refs.length)return refs.map(p=>p.inicio===p.fim?String(p.inicio):`${p.inicio}–${p.fim}`).join('; ');
    if(metadata.periodo)return metadata.periodo;
    if(record.ano!==null&&record.ano!==undefined)return String(record.ano);
    if(metadata.data_publicacao?.valor)return 'Publicação: '+metadata.data_publicacao.valor;
    if(metadata.data_atualizacao?.valor)return 'Atualização: '+metadata.data_atualizacao.valor;
    return 'Período ainda não estruturado';
  }
  function years(record){
    const metadata=record.metadados||{}, values=new Set();
    if(Number.isInteger(record.ano))values.add(record.ano);
    for(const period of metadata.periodos_referencia||[]){
      if(Number.isInteger(period.inicio)&&Number.isInteger(period.fim))for(let y=Math.max(1900,period.inicio);y<=Math.min(new Date().getFullYear(),period.fim);y++)values.add(y);
    }
    return [...values];
  }
  const api={html,text,periods,years};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.ObservatorioFormat=api;
})(typeof window!=='undefined'?window:globalThis);
