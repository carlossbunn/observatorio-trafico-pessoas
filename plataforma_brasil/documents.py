"""Leitura documental do catálogo; nunca converte texto em contagens de casos."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
from html.parser import HTMLParser
import io
import re
import shutil
import subprocess
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import app
from collectors import normalize, resource

# Serviços cujo catálogo já documenta necessidade de autorização/credencial ou custo.
RESTRICTED = {'A23', 'A25', 'A26', 'A27', 'A28', 'A30', 'A31', 'A34', 'A35', 'F07', 'F08', 'F09', 'F14', 'F17'}
COUNTRIES = {'A05': 'Organização internacional', 'A08': 'Organização internacional', 'A09': 'Publicação internacional',
             'A10': 'Estados Unidos', 'A13': 'Organização internacional', 'A14': 'Organização internacional',
             'A15': 'Organização internacional', 'A32': 'Publicação internacional', 'A33': 'Publicação internacional',
             'A38': 'Organização internacional', 'A39': 'Organização internacional', 'A40': 'Organização internacional'}
BOILERPLATE = ('cookie', 'javascript', 'termos mais buscados', 'ao compartilhar sua opiniao',
               'melhorar a navegacao para voce', 'seu navegador', 'ajude a melhorar o gov')


def substantive(paragraph):
    return not any(term in normalize(paragraph) for term in BOILERPLATE)


class Article(HTMLParser):
    """Extrai parágrafos e h1; menus e rodapés não provam relação com o Brasil."""
    def __init__(self):
        super().__init__()
        self.stack, self.capture, self.title, self.paragraphs, self.links = [], None, '', [], []
        self.link = None
        self.dates = {}
        self.headings = []
        self.link_contexts = {}
        self.heading = ''
        self.date_capture = None
        self.intro = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        property_name = (attrs.get('property') or attrs.get('name') or attrs.get('itemprop') or '').lower()
        if not property_name and tag == 'span':
            classes = attrs.get('class', '').split()
            property_name = 'datepublished' if 'documentPublished' in classes else 'datemodified' if 'documentModified' in classes else ''
        date_kind = ('publicacao' if any(s in property_name for s in ('published', 'datecreated', 'datepublished', 'created'))
                     else 'atualizacao' if any(s in property_name for s in ('modified', 'datemodified')) else None)
        date_value = attrs.get('content') or attrs.get('datetime')
        if date_kind and date_value:
            self.dates.setdefault(date_kind, []).append({'valor': date_value, 'evidencia': property_name + ': ' + date_value})
        elif date_kind:
            self.date_capture = (tag, date_kind, property_name, [], len(self.stack) + 1)
        if tag not in ('br', 'img', 'meta', 'link', 'input', 'hr', 'source', 'wbr', 'area', 'embed'):
            self.stack.append(tag)
        blocked = any(t in self.stack for t in ('nav', 'footer', 'aside', 'script', 'style', 'form'))
        if not blocked and tag in ('p', 'h1', 'h2', 'h3', 'h4'):
            self.capture = (tag, [])
        if not blocked and tag == 'a' and attrs.get('href'):
            self.link = (attrs['href'], [])

    def handle_endtag(self, tag):
        if self.date_capture and tag == self.date_capture[0] and len(self.stack) == self.date_capture[4]:
            _, kind, prop, texts, _ = self.date_capture
            value = ' '.join(texts).strip()
            self.dates.setdefault(kind, []).append({'valor': value, 'evidencia': prop + ': ' + value})
            self.date_capture = None
        if self.capture and tag == self.capture[0]:
            text = re.sub(r'\s+', ' ', ' '.join(self.capture[1])).strip()
            if tag == 'h1' and not self.title:
                self.title = text
            if tag.startswith('h'):
                self.headings.append(text)
                self.heading = text
            elif tag == 'p':
                if text and len(self.intro) < 8:
                    self.intro.append(text)
                if len(text) >= 80:
                    self.paragraphs.append(text)
            self.capture = None
        if tag == 'a' and self.link:
            self.links.append((self.link[0], ' '.join(self.link[1]).strip()))
            self.link_contexts[self.link[0]] = self.heading
            self.link = None
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if self.date_capture:
            self.date_capture[3].append(data)
        if not any(t in self.stack for t in ('nav', 'footer', 'aside', 'script', 'style', 'form')):
            if self.capture:
                self.capture[1].append(data)
            if self.link:
                self.link[1].append(data)


def brazil_paragraphs(article):
    return [p for p in article.paragraphs if re.search(r'\b(brasil|brazil|brasileir\w*|brazilian\w*)\b', normalize(p))
            and substantive(p)]


def download_document(source, max_mb):
    ident = source['id']
    if ident in RESTRICTED:
        return {'status': 'acesso_condicionado', 'message': 'Fonte exige credenciais, autorização ou condições específicas; nenhuma consulta autenticada realizada.'}
    if source['escopo'] == 'fora_do_recorte':
        return {'status': 'fora_do_recorte', 'message': 'Catálogo sem recorte documentado sobre o Brasil; mantido como referência temática.'}
    request = Request(source['url'], headers={'User-Agent': 'ObservatorioBrasil/1.1 (public documentary research)', 'Accept-Encoding': 'gzip'})
    limit = max_mb * 1024 * 1024
    with urlopen(request, timeout=18) as response:
        mime = response.headers.get('Content-Type', '').lower()
        pdf = 'application/pdf' in mime
        if 'html' not in mime and not pdf:
            return {'status': 'formato_especifico', 'message': f'Recurso {mime or "sem tipo"}: requer extrator específico; nenhum texto importado.'}
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError('Página excede limite configurado')
        if response.headers.get('Content-Encoding') == 'gzip':
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as zipped:
                body = zipped.read(limit + 1)
        if len(body) > limit:
            raise ValueError('Página descompactada excede limite configurado')
        encoding = response.headers.get_content_charset() or 'utf-8'
    article = Article()
    if pdf:
        executable = shutil.which('pdftotext')
        if not executable:
            return {'status': 'formato_especifico', 'message': 'PDF público: instale pdftotext para extrair os trechos documentais.'}
        result = subprocess.run([executable, '-layout', '-', '-'], input=body, capture_output=True, timeout=25, check=True)
        text = result.stdout.decode('utf-8', errors='replace')
        article.title = source['nome']
        article.paragraphs = [re.sub(r'\s+', ' ', p).strip() for p in re.split(r'\n\s*\n', text) if len(p.strip()) >= 80]
    else:
        article.feed(body.decode(encoding, errors='replace'))
    paragraphs = brazil_paragraphs(article)
    if source['escopo'] == 'brasil' and not paragraphs:
        paragraphs = [p for p in article.paragraphs if substantive(p)][:3]
    status = 'documento_importado' if paragraphs else 'sem_trecho_brasil'
    return {'status': status, 'body': body, 'article': article, 'paragraphs': paragraphs[:6],
            'message': 'Trechos documentais importados, sem extração de valores estatísticos.' if paragraphs
            else 'Página consultada; nenhum parágrafo com relação ao Brasil encontrado. Conteúdo dinâmico ou global requer revisão.'}


def store_document(db, source, result):
    if 'body' not in result:
        return 0
    ident, url = source['id'], source['url']
    digest = hashlib.sha256(result['body']).hexdigest()
    folder = app.DATA / 'snapshots'
    folder.mkdir(exist_ok=True)
    filename = digest + '.bin'
    if not (folder / filename).exists():
        (folder / filename).write_bytes(result['body'])
    snapshot_id = hashlib.sha256((ident + url + digest).encode()).hexdigest()
    db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?,?,?)', (snapshot_id, ident, url, digest, 'snapshots/' + filename, app.now()))
    article = result['article']
    resource(db, ident, url, article.title or source['nome'], 'pagina_consultada')
    for href, title in article.links:
        target = urljoin(url, href)
        path = urlparse(target).path.lower()
        extension = next((ext for ext in ('pdf', 'csv', 'xlsx', 'zip') if path.endswith('.' + ext)), None)
        if extension:
            resource(db, ident, target, title, extension)
    if not result['paragraphs']:
        db.execute("DELETE FROM registros WHERE id=? AND situacao='extracao_documental_automatica'", ('documental-' + ident,))
        return 0
    catalog = app.get_catalog(db)
    indicators = [i for i in catalog['indicadores'] if ident in [s.strip() for s in i.get('Fontes IDs', '').split(';')]]
    worlds = set(w for i in indicators for w in i['ambientes'])
    world = next(iter(worlds)) if len(worlds) == 1 else 'ambos'
    foreign = source['escopo'] != 'brasil'
    excerpts = '\n\n'.join(result['paragraphs'])
    technical = ident in ('A03', 'A11', 'A12', 'A13', 'A14', 'A29', 'A32', 'A33')
    from enrichment import temporal_metadata
    temporal = temporal_metadata(article, url)
    app.put_record(db, {'id': 'documental-' + ident, 'fonte_id': ident, 'recurso_url': url,
                       'titulo': article.title or source['nome'], 'descricao': excerpts,
                       'ambiente': world, 'tipo': 'contexto' if technical else 'documento',
                       'tema': indicators[0]['Dimensão'] if indicators else 'Fontes e contexto',
                       'ano': temporal['ano'], 'precisao': 'pais',
                       'origem_publicacao': COUNTRIES.get(ident, 'Publicação internacional') if foreign else 'Brasil',
                       'relacao_brasil': 'Parágrafos da publicação mencionam explicitamente o Brasil.' if foreign
                       else 'Página institucional brasileira do catálogo; informação documental de abrangência nacional.',
                       'indicadores': [i['ID'] for i in indicators],
                       'situacao': 'extracao_documental_automatica',
                       'metadados': {**temporal['metadados'], 'trecho_fonte': excerpts, **({'trecho_relacao_brasil': excerpts} if foreign else {}),
                                     'snapshot_sha256': digest, 'metodo': 'Parágrafos públicos; sem inferir números, datas de ocorrência ou municípios.',
                                     'classificacao_tematica': 'Vínculo editorial do catálogo, não confirmação automática de cada indicador no texto.',
                                     'limite': 'Trechos de página podem descrever serviços ou contexto; não são novos casos confirmados.'}})
    return 1


def collect_catalog(workers=4, max_mb=4, selected='todas'):
    if not 1 <= workers <= 8 or not 1 <= max_mb <= 40:
        raise ValueError('Use de 1 a 8 workers e de 1 a 40 MB por página')
    with app.connect() as db:
        sources = app.get_sources(db)
        if selected != 'todas':
            requested = {s.strip() for s in selected.split(',')}
            if requested - {s['id'] for s in sources}:
                raise ValueError('Fonte desconhecida')
            sources = [s for s in sources if s['id'] in requested]
        runs = {s['id']: db.execute('INSERT INTO coletas(fonte_id,inicio,situacao) VALUES (?,?,?)',
                                   (s['id'], app.now(), 'em_execucao')).lastrowid for s in sources}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_document, s, max_mb): s for s in sources}
        for future in as_completed(futures):
            source = futures[future]
            count = 0
            try:
                result = future.result()
                with app.connect() as db:
                    count = store_document(db, source, result)
                status, message = result['status'], result['message']
            except Exception as exc:
                status, message = 'falhou', f'{type(exc).__name__}: {exc}'
            with app.connect() as db:
                db.execute('UPDATE coletas SET fim=?,situacao=?,mensagem=?,linhas=? WHERE id=?',
                           (app.now(), status, message, count, runs[source['id']]))
            print(f'{source["id"]}: {status} — {message}', flush=True)
