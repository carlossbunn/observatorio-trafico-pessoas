"""Enriquecimento verificável: datas, períodos, documentos e tabelas vinculadas."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlparse, urljoin, unquote
from urllib.request import Request, urlopen

import app
from collectors import normalize, resource
from tables import national_rows, campaign_rows, employment_motivation_rows

MONTHS = {m: i + 1 for i, m in enumerate(('janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho',
                                         'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'))}
OLD_NETP = 'nucleos-de-enfrentamento-ao-trafico-de-pessoas-netp-e-postos-avancados-de-atendimento-humanizado-ao-migrante-paahm/'
NEW_NETP = 'rede-de-nucleos-de-enfrentamento-ao-trafico-de-pessoas-netp-e-postos-avancados-de-atendimento-humanizado-ao-migrante-paahms/'
UF_NAMES = dict(zip(('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO').split(),
                   ('acre|alagoas|amapa|amazonas|bahia|ceara|distrito federal|espirito santo|goias|maranhao|mato grosso|mato grosso do sul|minas gerais|para|paraiba|parana|pernambuco|piaui|rio de janeiro|rio grande do norte|rio grande do sul|rondonia|roraima|santa catarina|sao paulo|sergipe|tocantins').split('|')))


def iso_date(value):
    value = re.sub(r'^(?:Publicado em|Atualizado em)\s*', '', value.strip(), flags=re.I)
    match = re.match(r'^(\d{4}-\d{2}-\d{2})(?:T|\s|$)', value.strip())
    if match:
        try:
            return date.fromisoformat(match[1]).isoformat()
        except ValueError:
            return None
    match = re.match(r'^(\d{2})/(\d{2})/(\d{4})(?:\s|$)', value.strip())
    if match:
        try:
            return date(int(match[3]), int(match[2]), int(match[1])).isoformat()
        except ValueError:
            pass
    return None


def temporal_metadata(article, url):
    """Não confunde anos de leis, fundação ou exemplos de API com o período do registro."""
    metadata = {'enriquecido_em': app.now(), 'origem_temporal': url}
    for kind in ('publicacao', 'atualizacao'):
        for item in article.dates.get(kind, []):
            parsed = iso_date(item['valor'])
            if parsed:
                metadata['data_' + kind] = {'valor': parsed, 'evidencia': item['evidencia'], 'url': url}
                break
    # Dateline apenas no início do primeiro parágrafo, não em datas históricas no corpo.
    if 'data_publicacao' not in metadata:
        for lead in (article.intro or article.paragraphs[:1]):
            match = re.match(r'^(?:[\w .-]{1,50},\s*)?(\d{1,2})\s+de\s+(\w+)\s+de\s+(20\d{2})\b', normalize(lead))
            if match and match[2] in MONTHS:
                try:
                    parsed = date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
                    metadata['data_publicacao'] = {'valor': parsed, 'evidencia': lead[:350], 'url': url}
                    break
                except ValueError:
                    pass
    references, seen = [], set()
    candidates = [article.title, *article.headings, *article.paragraphs]
    pattern = r'\b(?:dados(?:\s+(?:de|do|referentes\s+a[o]?))?|balanco|relatorio(?:\s+(?:nacional|anual))?(?:\s*[—–:-]\s*dados)?(?:\s+de)?|serie(?:\s+de)?)\s*[:—–-]?\s*(20\d{2})(?:\s*(?:a|ate|[–—-])\s*(20\d{2}))?\b'
    for text in candidates:
        # Exemplos de chamadas de API não são séries coletadas.
        if any(s in normalize(text) for s in ('for example', 'por exemplo', 'example is')):
            continue
        for match in re.finditer(pattern, normalize(text)):
            start, end = int(match[1]), int(match[2] or match[1])
            if not 2000 <= start <= end <= date.today().year:
                continue
            if (start, end) not in seen:
                references.append({'inicio': start, 'fim': end, 'evidencia': text[:800], 'url': url})
                seen.add((start, end))
    if references:
        metadata['periodos_referencia'] = references
    year = None
    if metadata.get('data_publicacao'):
        year = int(metadata['data_publicacao']['valor'][:4])
        metadata['significado_ano'] = 'ano_publicacao'
    elif len(references) == 1 and references[0]['inicio'] == references[0]['fim']:
        year = references[0]['inicio']
        metadata['significado_ano'] = 'ano_referencia_documental'
    metadata['investigacao_temporal'] = 'Metadados da página, cabeçalhos e parágrafos examinados; anos históricos isolados não foram usados.'
    return {'ano': year, 'metadados': metadata}


def fetch_link(url, max_mb=20):
    """Recupera apenas a migração de diretório conhecida do próprio MJSP, confirmando HTTP/conteúdo."""
    candidates = [url]
    if urlparse(url).hostname == 'www.gov.br' and '/mj/' in url and OLD_NETP in url:
        candidates.append(url.replace(OLD_NETP, NEW_NETP))
    last = None
    for candidate in candidates:
        try:
            request = Request(candidate, headers={'User-Agent': 'ObservatorioBrasil/1.2 (document enrichment)', 'Accept-Encoding': 'gzip'})
            with urlopen(request, timeout=25) as response:
                started, chunks, size = time.monotonic(), [], 0
                while True:
                    if time.monotonic() - started > 40:
                        raise TimeoutError('Tempo total de download excedido')
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > max_mb * 1024 * 1024:
                        raise ValueError('Documento excede limite de download')
                body = b''.join(chunks)
                if response.headers.get('Content-Encoding') == 'gzip':
                    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
                        body = stream.read(max_mb * 1024 * 1024 + 1)
                if len(body) > max_mb * 1024 * 1024:
                    raise ValueError('Documento excede limite de download/descompactação')
                return body, response.headers.get('Content-Type', ''), response.geturl()
        except HTTPError as exc:
            last = exc
            if exc.code not in (404, 410):
                raise
    raise last or ValueError('Documento inacessível')


def extract_pdf(body):
    executable = shutil.which('pdftotext')
    if not executable:
        raise ValueError('Utilitário pdftotext não encontrado')
    if not body.startswith(b'%PDF'):
        raise ValueError('Recurso não é um PDF válido')
    return subprocess.run([executable, '-layout', '-', '-'], input=body, capture_output=True,
                          timeout=40, check=True).stdout.decode('utf-8', errors='replace')


def pdf_reference(text):
    cover = text
    national_cover = normalize('\f'.join(text.split('\f')[:3]))
    national = re.search(r'relatorio\s+nacional.{0,180}?dados\s*(20\d{2})\s*[a–—-]\s*(20\d{2})', national_cover, re.S)
    if national:
        return {'inicio': int(national[1]), 'fim': int(national[2]), 'evidencia': national[0], 'pagina': national_cover[:national.start()].count('\f') + 1}
    campaign = re.search(r'semana nacional.{0,200}?enfrentamento ao trafico de pessoas\s*[-–—]\s*(20\d{2})', national_cover, re.S)
    if campaign:
        year = int(campaign[1])
        return {'inicio': year, 'fim': year, 'evidencia': campaign[0], 'pagina': national_cover[:campaign.start()].count('\f') + 1}
    pattern = r'(?:dados\s+referentes\s+ao|exercicio\s*(?:de)?\s*:|ano\s+de\s+referencia\s*:)[ \t\r\n\f:\u200b]*(?:exercicio\s*de\s*:[ \t\r\n]*)?(20\s?\d\s?\d)\b'
    normalized = normalize(cover)
    match = re.search(pattern, normalized, re.S)
    if not match:
        match = re.search(r'(?:relatorio\s+nacional.{0,180}?)(20\d{2})\s*[a–—-]\s*(20\d{2})', normalized, re.S)
        if match:
            return {'inicio': int(match[1]), 'fim': int(match[2]), 'evidencia': match[0], 'pagina': normalized[:match.start()].count('\f') + 1}
        return None
    year = int(re.sub(r'\s', '', match[1]))
    if not 2000 <= year <= date.today().year:
        return None
    return {'inicio': year, 'fim': year, 'evidencia': match[0], 'pagina': normalized[:match.start()].count('\f') + 1}


def pdf_territory(text, db):
    cover = '\n'.join(text.split('\f')[:3])
    match = re.search(r'^.*unidade da federacao\s*:\s*([^\n]+)', normalize(cover).replace('\u200b', ''), re.M)
    if not match:
        first_page = normalize(text.split('\f')[0])
        header = re.search(r'^\s*([a-z -]+?)\s*/\s*([a-z]{2})\s*$', first_page, re.M)
        if header and header[2].upper() in UF_NAMES:
            rows = db.execute('SELECT id,nome FROM localidades WHERE uf=? AND nome_normalizado=?', (header[2].upper(), header[1].strip())).fetchall()
            if len(rows) == 1:
                return {'uf': header[2].upper(), 'municipio_ibge': rows[0]['id'], 'municipio': rows[0]['nome'], 'precisao': 'municipio', 'evidencia_territorial': header[0].strip()}
        return {}
    value = match[1].strip()
    town = re.search(r'municipio\s+de\s+(.+?)\s*[-/]\s*([a-z]{2})\b', value)
    if town and town[2].upper() in UF_NAMES:
        uf = town[2].upper()
        rows = db.execute('SELECT id,nome FROM localidades WHERE uf=? AND nome_normalizado=?', (uf, town[1].strip())).fetchall()
        if len(rows) == 1:
            return {'uf': uf, 'municipio_ibge': rows[0]['id'], 'municipio': rows[0]['nome'], 'precisao': 'municipio',
                    'evidencia_territorial': match[0].strip()}
    for uf, name in UF_NAMES.items():
        if value == name or value == uf.lower() or value.startswith(name + ' ') or re.fullmatch(re.escape(name) + r'\s*[-/]\s*' + uf.lower(), value):
            return {'uf': uf, 'precisao': 'uf', 'evidencia_territorial': match[0].strip()}
    return {}


def training_rows(text):
    """Tabelas de capacitação: só linhas com colunas e quantidade explícitas; vazio nunca vira zero."""
    rows = []
    for page_no, page in enumerate(text.split('\f'), 1):
        if not re.search(r'14\.?\s*(?:[–—-]\s*)?REALIZA[ÇC][ÃA]O DE CAPACITA', page, re.I):
            continue
        pattern = r'^[ \t]*(\d+)[ \t]{2,}(.+?)[ \t]{2,}(\d{1,2}[-/]\d{1,2}.+?)[ \t]{2,}(.+?)[ \t]{2,}(.+?)[ \t]{2,}(\d+)[ \t]*$'
        lines = page.splitlines()
        for index, line in enumerate(lines):
            match = re.fullmatch(pattern, line)
            if not match or any(not match[group].strip() for group in (2, 3, 4, 5)):
                continue
            cells = {key: [match[group].strip()] for key, group in (('tema', 2), ('data_declarada', 3), ('local_declarado', 4), ('publico', 5))}
            starts = [match.start(group) for group in (2, 3, 4, 5, 6)]
            evidence, blank = [line], 0
            for continuation in lines[index + 1:index + 9]:
                if re.match(r'^[ \t]*\d+\b', continuation):
                    break
                if not continuation.strip():
                    blank += 1
                    if blank >= 2:
                        break
                    continue
                blank = 0
                evidence.append(continuation)
                for column, key in enumerate(cells):
                    part = continuation[starts[column]:starts[column + 1]].strip()
                    if part:
                        cells[key].append(part)
            rows.append({'linha': int(match[1]), **{key: ' '.join(parts) for key, parts in cells.items()},
                         'participantes': int(match[6]), 'pagina': page_no, 'evidencia': '\n'.join(evidence).strip()})
    return rows


def victim_rows(text):
    categories = [
        ('Remoção de órgãos, tecidos ou partes do corpo', r'remocao de orgaos,? tecidos ou partes do corpo'),
        ('Trabalho em condições análogas à escravidão', r'trabalho em condicoes analogas? [aà] (?:de )?escravo'),
        ('Qualquer tipo de servidão', r'qualquer tipo de servidao'),
        ('Adoção ilegal', r'adocao ilegal'), ('Exploração sexual', r'exploracao sexual'), ('Total', r'total')]
    result = []
    for page_no, page in enumerate(text.split('\f'), 1):
        cleaned = normalize(page.replace('\u200b', ''))
        if not re.search(r'1[ \t]*[–—-][ \t]*quantidade de vitimas atendidas', cleaned):
            continue
        for title, pattern in categories:
            match = re.search(r'^[ \t]*(' + pattern + r')[ \t]{2,}([0-9]+(?:\.[0-9]{3})*)[ \t]*$', cleaned, re.M)
            if match:
                result.append({'categoria': title, 'valor': int(match[2].replace('.', '')), 'pagina': page_no,
                               'evidencia': match[0].strip(), 'total': title == 'Total'})
    return result


def save_pdf(db, source, resource_row, body, resolved, text):
    digest = hashlib.sha256(body).hexdigest()
    filename = digest + '.bin'
    folder = app.DATA / 'snapshots'
    folder.mkdir(exist_ok=True)
    if not (folder / filename).exists():
        (folder / filename).write_bytes(body)
    sid = hashlib.sha256((source['id'] + resolved + digest).encode()).hexdigest()
    db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?,?,?)', (sid, source['id'], resolved, digest, 'snapshots/' + filename, app.now()))
    reference = pdf_reference(text)
    territory = pdf_territory(text, db)
    evidence = territory.pop('evidencia_territorial', '')
    doc_id = 'pdf-' + hashlib.sha256((source['id'] + resource_row['url']).encode()).hexdigest()[:24]
    # Um PDF pode ser publicado em vários endereços (copy_of, migração).
    # Conserva um documento e suas observações por conteúdo, com todos os links de origem.
    duplicates = db.execute("SELECT * FROM registros WHERE fonte_id=? AND tipo='documento' AND id LIKE 'pdf-%' AND json_extract(metadados,'$.snapshot_sha256')=? ORDER BY id",
                            (source['id'], digest)).fetchall()
    aliases = {resource_row['url'], resolved}
    if duplicates:
        incoming_id = doc_id
        doc_id = duplicates[0]['id']
        for previous in duplicates:
            previous_metadata = json.loads(previous['metadados'])
            aliases.update(previous_metadata.get('urls_alternativas', []))
            aliases.update(filter(None, (previous_metadata.get('url_original'), previous['recurso_url'])))
        for obsolete in {r['id'] for r in duplicates} | {incoming_id}:
            if obsolete != doc_id:
                db.execute("DELETE FROM registros WHERE json_extract(metadados,'$.documento_id')=? OR id=?", (obsolete, obsolete))
    year = reference['inicio'] if reference and reference['inicio'] == reference['fim'] else None
    # Não usa o nome do arquivo como confirmação do ano no conteúdo.
    title = resource_row['titulo']
    if title.startswith(('http:', 'https:')):
        title = unquote(urlparse(resource_row['url']).path.rsplit('/', 1)[-1]).replace('_', ' ')
    intro = normalize(text[:2500])
    if source['id'] == 'A01' and 'relatorio nacional' in intro and reference:
        title = f'Relatório nacional sobre tráfico de pessoas — Dados {reference["inicio"]}–{reference["fim"]}'
    elif source['id'] == 'A21' and 'relatorio anual de dados' in intro:
        title = 'Relatório anual de dados da unidade informante'
    elif source['id'] == 'A21' and 'relatorio institucional' in intro:
        title = 'Relatório institucional da unidade informante'
    elif source['id'] == 'A04':
        title = next((line.strip() for line in text.splitlines() if line.strip()), title)
    title += (' — ' + str(year)) if year and str(year) not in title else ''
    title += (' · ' + (territory.get('municipio') or territory.get('uf', ''))) if territory else ''
    cover = '\n'.join(text.split('\f')[:3])[:9000]
    metadata = {'snapshot_sha256': digest, 'url_original': resource_row['url'], 'url_resolvida': resolved,
                'urls_alternativas': sorted(aliases),
                'trecho_fonte': cover, 'paginas': len(text.split('\f')) - (1 if text.endswith('\f') else 0),
                'enriquecido_em': app.now(), 'versao_extrator': '1.6', 'investigacao_temporal': 'Identificação, cabeçalhos e rótulos explícitos de exercício/período do PDF examinados.',
                'referencia_territorial': 'unidade_informante' if source['id'] == 'A21' else 'abrangencia_do_documento',
                'limite': 'Município/UF da unidade informante não é automaticamente local de aliciamento ou exploração.',
                'extracao_tabelas': 'Extração parcial: seções 1, 10 (linha oferta de trabalho completa), 13.1 e 14 da rede NETP/PAAHM; tabelas 1–11 do relatório nacional 2021–2023. Outros formatos, tabelas e gráficos continuam pendentes.',
                'situacao_extracao': 'parcial',
                'escopo_extrator': 'NETP/PAAHM: vítimas, motivação para migrar, materiais e capacitações' if source['id'] == 'A21' else 'Relatório nacional 2021–2023: tabelas 1–11' if source['id'] == 'A01' else 'Identificação documental; tabelas quantitativas pendentes'}
    updated = re.search(r'atualizacao\s+(?:periodica\s+)?(?:de\s+)?(\d{1,2})\s+de\s+(\w+)\s+de\s+(20\d{2})', normalize(text[:6000]))
    if updated and updated[2] in MONTHS:
        metadata['data_atualizacao'] = {'valor': date(int(updated[3]), MONTHS[updated[2]], int(updated[1])).isoformat(), 'evidencia': updated[0], 'url': resolved}
    if source['id'] == 'A21' and not territory:
        metadata['investigacao_territorial'] = 'Unidade informante ainda não estruturada com segurança; alternativas de formulário/checkbox não foram presumidas como seleções.'
    if evidence:
        metadata['evidencia_territorial'] = evidence
    if reference:
        metadata.update(periodos_referencia=[{**reference, 'url': resolved}], significado_ano='ano_referencia_documental')
    theme = 'Prevenção e atendimento' if source['id'] == 'A21' else 'Fiscalização e trabalho escravo' if source['id'] == 'A04' else 'Dados oficiais'
    national = national_rows(text) if source['id'] == 'A01' else []
    campaigns = campaign_rows(text) if source['id'] == 'A21' else []
    employment = employment_motivation_rows(text) if source['id'] == 'A21' else []
    metadata['tabelas_com_celulas_extraidas'] = sorted({str(r['tabela']) for r in national} | ({'10'} if employment else set()) | ({'13.1'} if campaigns else set()) | ({'1'} if source['id'] == 'A21' and victim_rows(text) else set()) | ({'14'} if source['id'] == 'A21' and training_rows(text) else set()))
    app.put_record(db, {'id': doc_id, 'fonte_id': source['id'], 'recurso_url': resolved, 'titulo': title,
                       'descricao': cover, 'ambiente': 'ambos', 'tipo': 'documento', 'tema': theme,
                       'ano': year, 'precisao': 'nao_informada' if source['id'] == 'A21' and not territory else 'pais', **territory, 'metadados': metadata})
    db.execute("DELETE FROM registros WHERE json_extract(metadados,'$.documento_id')=?", (doc_id,))
    activities = training_rows(text) if source['id'] == 'A21' else []
    for activity in activities:
        app.put_record(db, {'id': f'{doc_id}-capacitacao-{activity["pagina"]}-{activity["linha"]}',
                           'fonte_id': source['id'], 'recurso_url': resolved,
                           'titulo': f'Participantes de atividade reportada — item {activity["linha"]} · {territory.get("municipio") or territory.get("uf") or "unidade a estruturar"}',
                           'descricao': activity['evidencia'], 'ambiente': 'real', 'tipo': 'estatistica',
                           'tema': 'Prevenção e atendimento', 'ano': year, 'valor': activity['participantes'],
                           'unidade': 'participantes_de_atividade_reportada', 'precisao': 'pais' if territory else 'nao_informada', **territory,
                           'metadados': {**metadata, 'atividade': activity, 'documento_id': doc_id,
                                         'trecho_fonte': activity['evidencia'],
                                         'limite': 'Participantes de ações de orientação/prevenção, não vítimas identificadas. Local declarado preservado; sem coordenadas inferidas.'}})
    victims = victim_rows(text) if source['id'] == 'A21' else []
    for index, observation in enumerate(victims):
        app.put_record(db, {'id': f'{doc_id}-atendimentos-{index}', 'fonte_id': source['id'], 'recurso_url': resolved,
                           'titulo': f'Vítimas atendidas reportadas — {observation["categoria"]} · {territory.get("municipio") or territory.get("uf") or "unidade a estruturar"}',
                           'descricao': observation['evidencia'], 'ambiente': 'real', 'tipo': 'estatistica',
                           'tema': 'Atendimento a vítimas', 'ano': year, 'valor': observation['valor'],
                           'unidade': 'vitimas_atendidas_reportadas_pela_unidade', 'precisao': 'pais' if territory else 'nao_informada', **territory,
                           'metadados': {**metadata, 'documento_id': doc_id, 'tabela': '1 - Quantidade de vítimas atendidas',
                                         'observacao': observation, 'trecho_fonte': observation['evidencia'],
                                         'nao_somar_total_com_componentes': True,
                                          'limite': 'Atendimentos reportados por esta unidade; não é prevalência nem total deduplicado entre instituições. Total e modalidades não devem ser somados.'}})
    for observation in employment:
        category_id = ('remocao', 'trabalho', 'servidao', 'adocao', 'sexual', 'total')[['Remoção de órgãos', 'Trabalho escravo', 'Servidão', 'Adoção ilegal', 'Exploração sexual', 'Total'].index(observation['categoria'])]
        app.put_record(db, {'id': f'{doc_id}-motivo-trabalho-{observation["pagina"]}-{category_id}',
                           'fonte_id': source['id'], 'recurso_url': resolved,
                           'titulo': f'Oferta de trabalho como motivação para migrar — {observation["categoria"]} · {territory.get("municipio") or territory.get("uf") or "unidade a estruturar"}',
                           'descricao': observation['evidencia'], 'ambiente': 'real', 'tipo': 'estatistica',
                           'tema': 'Motivações para migrar', 'ano': year, 'valor': observation['valor'],
                           'unidade': 'pessoas_atendidas_oferta_trabalho_motivo_migracao',
                           'precisao': 'nao_informada', **territory,
                           'metadados': {**metadata, 'documento_id': doc_id, 'tabela': '10 - Motivações para migrar',
                                         'observacao': observation, 'trecho_fonte': observation['evidencia'],
                                         'nao_somar_total_com_componentes': True,
                                         'limite': 'Oferta de trabalho declarada como motivação para migrar, não necessariamente falsa, digital ou meio de aliciamento. UF/município identifica a unidade informante, não o local de aliciamento. Total e categorias não devem ser somados; unidades podem se sobrepor.'}})
    for index, observation in enumerate(national):
        app.put_record(db, {'id': f'{doc_id}-nacional-{index}', 'fonte_id': source['id'], 'recurso_url': resolved,
                           'titulo': f'{observation["titulo"]} — {observation["recorte"]} · {observation["categoria"]} · {observation["ano"]}',
                           'descricao': observation['evidencia'], 'ambiente': 'real', 'tipo': 'estatistica',
                           'tema': 'Denúncias e resposta institucional', 'ano': observation['ano'],
                           'valor': observation['valor'], 'unidade': observation['unidade'], 'precisao': 'pais',
                           'metadados': {**metadata, 'periodos_referencia': [{'inicio': observation['ano'], 'fim': observation['ano'], 'url': resolved}],
                                        'significado_ano': 'ano_da_observacao', 'documento_id': doc_id,
                                        'tabela': observation['tabela'], 'observacao': observation,
                                        **({'cobertura_anual_completa': False, 'nota_cobertura': observation['nota']} if observation.get('parcial') else {}),
                                        'trecho_fonte': observation['evidencia'], 'nao_somar_total_com_componentes': True,
                                        'limite': 'Unidades institucionais diferentes não são somáveis. Categorias do MPF podem se sobrepor. Processos, inquéritos e denúncias não são vítimas nem condenações.'}})
    for observation in campaigns:
        app.put_record(db, {'id': f'{doc_id}-material-{observation["pagina"]}-{observation["linha"]}',
                           'fonte_id': source['id'], 'recurso_url': resolved,
                           'titulo': f'Material de campanha — {observation["categoria"]} · {territory.get("municipio") or territory.get("uf") or "unidade a estruturar"}',
                           'descricao': observation['evidencia'], 'ambiente': 'real', 'tipo': 'estatistica',
                           'tema': 'Prevenção e atendimento', 'ano': year, 'valor': observation['valor'],
                           'unidade': 'unidades_de_material_de_campanha', 'precisao': 'nao_informada', **territory,
                           'metadados': {**metadata, 'documento_id': doc_id, 'tabela': '13.1', 'observacao': observation,
                                        'trecho_fonte': observation['evidencia'],
                                        'limite': 'Materiais produzidos, não pessoas atendidas nem vítimas.'}})
    resource(db, source['id'], resolved, title, 'pdf_examinado')
    return 1 + len(activities) + len(victims) + len(national) + len(campaigns) + len(employment)


def init_audit(db):
    db.execute('''CREATE TABLE IF NOT EXISTS investigacoes (
        fonte_id TEXT, url TEXT, situacao TEXT, detalhe TEXT, verificado_em TEXT,
        PRIMARY KEY(fonte_id,url))''')


def enrich_existing(db):
    from documents import Article
    changed = 0
    for raw in db.execute('SELECT * FROM registros WHERE tipo IN (\'documento\',\'contexto\')').fetchall():
        record = app.decode_record(raw)
        if record['metadados'].get('snapshot_sha256') and record['id'].startswith('pdf-'):
            continue  # PDFs são reprocessados pelo extrator específico; não sobrescrever períodos com a capa.
        record.pop('disponibilidade', None)
        metadata = record['metadados']
        snapshot = db.execute('SELECT arquivo FROM snapshots WHERE fonte_id=? AND url=? ORDER BY coletado_em DESC LIMIT 1',
                              (record['fonte_id'], record['recurso_url'])).fetchone()
        article = Article()
        if snapshot:
            content = (app.DATA / snapshot['arquivo']).read_bytes()
            if not content.startswith(b'%PDF'):
                article.feed(content.decode('utf-8', errors='replace'))
        if not article.paragraphs:
            article.title = record['titulo']
            article.paragraphs = record['descricao'].split('\n\n')
        temporal = temporal_metadata(article, record['recurso_url'])
        metadata.update(temporal['metadados'])
        if temporal['ano'] is not None:
            record['ano'] = temporal['ano']
        record['metadados'] = {k: v for k, v in metadata.items() if v is not None}
        app.put_record(db, record)
        changed += 1
    return changed


def enrich_sources(selected='A01,A04,A21,A22', limit=24, workers=4, max_mb=20, cached_only=False):
    if not 1 <= limit <= 200 or not 1 <= workers <= 8 or not 1 <= max_mb <= 40:
        raise ValueError('Limites: 1–200 documentos, 1–8 workers e 1–40 MB por arquivo')
    ids = {s.strip() for s in selected.split(',')}
    with app.connect() as db:
        init_audit(db)
        sources = {s['id']: s for s in app.get_sources(db)}
        if ids - sources.keys():
            raise ValueError('Fonte desconhecida')
        changed = enrich_existing(db)
        cached = [r for r in db.execute("SELECT * FROM registros WHERE id LIKE 'pdf-%' AND tipo='documento'") if r['fonte_id'] in ids]
        for raw in cached:
            record = app.decode_record(raw)
            metadata = record['metadados']
            snapshot = db.execute('SELECT arquivo FROM snapshots WHERE sha256=? LIMIT 1', (metadata.get('snapshot_sha256'),)).fetchone()
            original = db.execute('SELECT * FROM recursos WHERE fonte_id=? AND url=?', (record['fonte_id'], metadata.get('url_original'))).fetchone()
            if snapshot and original:
                body = (app.DATA / snapshot['arquivo']).read_bytes()
                save_pdf(db, sources[record['fonte_id']], dict(original), body, record['recurso_url'], extract_pdf(body))
        rows = [dict(r) for r in db.execute("SELECT * FROM recursos WHERE formato='pdf' ORDER BY fonte_id,url") if r['fonte_id'] in ids]
        # Períodos recentes primeiro. Um recurso por URL; documentos já examinados são reutilizados.
        rows.sort(key=lambda r: (max([int(y) for y in re.findall(r'20\d{2}', r['url'])] or [0]), r['url']), reverse=True)
        pending = [] if cached_only else [r for r in rows if not db.execute("SELECT 1 FROM investigacoes WHERE fonte_id=? AND url=? AND situacao='extraido'", (r['fonte_id'], r['url'])).fetchone()][:limit]
    print(f'{changed} registros existentes enriquecidos; {len(pending)} PDFs selecionados.', flush=True)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        tasks = {executor.submit(fetch_link, r['url'], max_mb): r for r in pending}
        for future in as_completed(tasks):
            row = tasks[future]
            count = 0
            try:
                body, mime, resolved = future.result()
                text = extract_pdf(body)
                if len(text.strip()) < 80:
                    raise ValueError('PDF sem texto suficiente; requer OCR')
                with app.connect() as db:
                    count = save_pdf(db, sources[row['fonte_id']], row, body, resolved, text)
                status, message = 'extraido', f'{count} registros; URL confirmada: {resolved}'
            except Exception as exc:
                status, message = 'acesso_pendente', f'{type(exc).__name__}: {exc}'
            with app.connect() as db:
                db.execute('INSERT INTO investigacoes VALUES (?,?,?,?,?) ON CONFLICT(fonte_id,url) DO UPDATE SET situacao=excluded.situacao,detalhe=excluded.detalhe,verificado_em=excluded.verificado_em',
                           (row['fonte_id'], row['url'], status, message, app.now()))
                db.execute('INSERT INTO coletas(fonte_id,inicio,fim,situacao,mensagem,linhas) VALUES (?,?,?,?,?,?)',
                           (row['fonte_id'], app.now(), app.now(), status, message, count))
            print(f'{row["fonte_id"]}: {status} — {message}', flush=True)
