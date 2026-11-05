"""Verificação real das fichas no Chrome; usa o banco local e não o altera."""
from http.server import ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

EXERCISE = r'''
const smokeTimer=setInterval(async()=>{
 if(!state.overview||!state.all.length)return;
 clearInterval(smokeTimer);
 try{
  if(document.querySelectorAll('.map-source-card').length!==59)throw Error('Catálogo incompleto');
  const documentRecord=state.all.find(r=>r.id==='documental-A01');
  recordDetail(documentRecord);
  const text=$('detail-body').textContent;
  if(!text.includes('2023-09-11')||!text.includes('2026-07-21')||!text.includes('2025'))throw Error('Datas e referência ausentes');
  if(/\bnull\b/.test(text))throw Error('null literal na ficha');
  if([...$('detail-body').querySelectorAll(':scope > dl > dt')].some(e=>e.textContent==='Valor'))throw Error('Valor indevido em documento');
  $('detail').close();
  const training=state.all.find(r=>r.municipio==='Guarulhos'&&r.unidade==='participantes_de_atividade_reportada'&&r.valor===200);
  if(!training)throw Error('Atividade verificada não encontrada');
  recordDetail(training);
  if(!$('detail-body').textContent.includes('200')||!$('detail-body').textContent.includes('Unidade informante')&&!$('detail-body').textContent.includes('unidade que produziu'))throw Error('Atividade/território incorretos');
  $('detail').close();
   $('map-source').value='A21';await refresh();
   if(!state.rows.length||state.rows.some(r=>r.fonte_id!=='A21'))throw Error('Filtro por fonte incorreto');
   view('completude');
   if($('completude').hidden||document.querySelectorAll('[data-coverage-indicator]').length!==34)throw Error('Cobertura de indicadores incompleta');
   const coverageSource=state.coverage.fontes.find(s=>s.id==='A01');
   if(!coverageSource.estatisticas||!coverageSource.arquivos.some(f=>f.tabelas_extraidas.includes('10')))throw Error('Tabelas nacionais ausentes na cobertura');
   $('coverage-status').value='sem_dados';renderCoverage();
   if(!document.querySelectorAll('[data-coverage-source]').length)throw Error('Filtro de pendências vazio');
   document.querySelector('[data-coverage-source]').click();
   if(!$('detail').open||!$('detail-body').textContent.includes('Sem registros importados'))throw Error('Detalhe de pendência ausente');
   $('detail').close();
   $('coverage-status').value='';renderCoverage();
   const national=state.all.find(r=>r.fonte_id==='A01'&&r.metadados.tabela===10&&r.ano===2021&&r.metadados.observacao.total&&r.metadados.observacao.recorte==='Interno');
   if(!national||national.valor!==11)throw Error('Valor de tabela nacional incorreto');
   view('explorar');document.querySelector('[data-world="virtual"]').click();
   if($('recruitment').hidden||!$('recruitment-list').textContent.includes('SaferNet'))throw Error('Área de recrutamento virtual ausente');
   if(!$('digital-profile').textContent.includes('131')||!$('digital-modalities').textContent.includes('Exploração sexual'))throw Error('Perfil ou modalidades ausentes');
   if(!$('digital-profile-recent').textContent.includes('237')||!$('digital-profile-recent').textContent.includes('2024')||!$('digital-profile-recent').textContent.includes('2025'))throw Error('Perfis recentes não aparecem');
   document.querySelector('[data-recent-profile]').click();
   if(!$('detail-body').textContent.includes('Trecho')&&!$('detail-body').textContent.includes('trecho'))throw Error('Evidência do perfil recente ausente');
   $('detail').close();
   $('employment-year').value='2024';$('employment-uf').value='PB';renderDigitalAnalysis();
   if(!$('employment-records').textContent.includes('37'))throw Error('Motivação de trabalho por unidade não encontrada');
   $('employment-category').value='Trabalho escravo';renderDigitalAnalysis();
   if(!$('employment-records').textContent.includes('37'))throw Error('Filtro por finalidade não funciona');
   document.querySelector('[data-employment]').click();
   if(!$('detail-body').textContent.includes('não necessariamente falsa'))throw Error('Limites da motivação ausentes');
   $('detail').close();
   $('digital-period').value='2025-S2';renderDigitalAnalysis();
   if(!$('digital-locations').textContent.includes('Uberlândia'))throw Error('Localidade de contexto ausente');
   $('digital-overlay').value='sim';renderDigitalAnalysis();
   if(map&&(!digitalAreas||!digitalAreas.getLayers().length))throw Error('Camada territorial contextual ausente');
   if(!$('recruitment').textContent.includes('não identificam canal digital'))throw Error('Contexto geral não identificado');
   $('recruitment-status').value='suspeita_nao_confirmada';renderRecruitment();
   if(!$('recruitment-list').textContent.includes('Nenhuma ficha'))throw Error('Filtro de evidência incorreto');
   $('recruitment-status').value='alerta_geral';renderRecruitment();
   if(!$('recruitment-count').textContent.includes('0 ofertas'))throw Error('Alerta geral contado como oferta');
   document.querySelector('[data-recruitment]').click();
   if(!$('detail-body').textContent.includes('falsas agências'))throw Error('Trecho documentado ausente');
   $('detail').close();
   document.body.dataset.smoke='ok';
 }catch(error){document.body.dataset.smoke='falhou';document.body.dataset.smokeError=error.message;}
},100);
'''


class Handler(app.Handler):
    def do_GET(self):
        if self.path == '/app.js':
            return self.send((app.ROOT / 'web' / 'app.js').read_text(encoding='utf-8') + EXERCISE, 'text/javascript; charset=utf-8')
        return super().do_GET()

    def log_message(self, *args):
        pass


class Result(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self.result = dict(attrs)


if __name__ == '__main__':
    chrome = shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:
        raise SystemExit('Chrome/Chromium não encontrado')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        process = subprocess.run([chrome, '--headless', '--disable-gpu', '--no-sandbox', '--virtual-time-budget=15000',
                                  '--dump-dom', f'http://127.0.0.1:{server.server_port}'], capture_output=True, text=True, timeout=75)
        result = Result()
        result.feed(process.stdout)
        print(result.result)
        assert process.returncode == 0 and result.result.get('data-smoke') == 'ok', result.result
        print('Chrome: datas, referência, ausência de null literal, atividade, unidade territorial e filtro por fonte verificados.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
