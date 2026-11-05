"""Coletores com snapshots versionados e sem inferir casos a partir de indicadores."""
import csv
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import unicodedata
import time
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import app


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text)) if not unicodedata.combining(c)).casefold().strip()


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.texts, self.link, self.skip = [], [], None, 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.skip += 1
        if tag == 'a' and attrs.get('href'):
            self.link = [attrs['href'], []]

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        if tag == 'a' and self.link:
            self.links.append((self.link[0], ' '.join(self.link[1]).strip()))
            self.link = None

    def handle_data(self, text):
        if not self.skip:
            self.texts.append(text)
            if self.link:
                self.link[1].append(text.strip())

    @property
    def text(self):
        return re.sub(r'\s+', ' ', ' '.join(self.texts)).strip()


def fetch(db, source, url, max_mb=40):
    request = Request(url, headers={'User-Agent': 'ObservatorioBrasil/1.0 (local public data research)', 'Accept-Encoding': 'gzip'})
    limit = max_mb * 1024 * 1024
    with urlopen(request, timeout=60) as response:
        if int(response.headers.get('Content-Length', '0')) > limit:
            raise ValueError(f'Recurso excede limite de {max_mb} MB; download interrompido')
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError(f'Recurso excede limite de {max_mb} MB')
        if response.headers.get('Content-Encoding') == 'gzip':
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
                body = compressed.read(limit + 1)
            if len(body) > limit:
                raise ValueError('Conteúdo descompactado excede limite')
        content_type = response.headers.get('Content-Type', '')
    digest = hashlib.sha256(body).hexdigest()
    folder = app.DATA / 'snapshots'
    folder.mkdir(exist_ok=True)
    filename = digest + '.bin'
    target = folder / filename
    if not target.exists():
        target.write_bytes(body)
    ident = hashlib.sha256((source + url + digest).encode()).hexdigest()
    db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?,?,?)',
               (ident, source, url, digest, 'snapshots/' + filename, app.now()))
    return body, content_type, digest


def resource(db, source, url, title, format_name):
    if urlparse(url).scheme not in ('http', 'https'):
        return
    ident = hashlib.sha256((source + url).encode()).hexdigest()
    db.execute('INSERT INTO recursos VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET titulo=excluded.titulo,formato=excluded.formato',
               (ident, source, url, title or url, format_name, app.now()))


def discover(db, source, url, max_mb):
    body, mime, digest = fetch(db, source, url, max_mb)
    if 'html' not in mime:
        raise ValueError(f'Esperava HTML, recebeu {mime}')
    page = Page()
    page.feed(body.decode('utf-8', errors='replace'))
    for href, label in page.links:
        target = urljoin(url, href)
        path = urlparse(target).path.lower()
        text = normalize(label)
        # Ignora os arquivos de menus globais do gov.br, alheios ao assunto.
        if source == 'A02' and '/dados-abertos/disque100/' not in path:
            continue
        if source == 'A01' and not any(s in target for s in ('/trafico-de-pessoas/', 'drive.google.com/file/', 'app.powerbi.com/')):
            continue
        if source == 'A04' and not any(s in target for s in ('/combate-ao-trabalho-escravo', '/trabalho-escravo', '/cadastro-de-empregadores', '/fiscalizacao-para-erradicacao')):
            continue
        fmt = next((extension for extension in ('csv', 'zip', 'xlsx', 'pdf') if '.' + extension in path), None)
        if fmt or (source == 'A02' and '/disque100/' in path and ('semestre' in path or 'trimestre' in path)):
            resource(db, source, target, label, fmt or 'pagina_de_download')
        elif 'powerbi.com/' in target or 'drive.google.com/file/' in target:
            resource(db, source, target, label, 'painel' if 'powerbi' in target else 'documento_externo')
    return page, digest


def collect_ibge(db, max_mb):
    base = 'https://servicodados.ibge.gov.br/api/'
    raw, _, _ = fetch(db, 'A11', base + 'v1/localidades/estados', max_mb)
    states = {str(r['id']): r['sigla'] for r in json.loads(raw)}
    raw, _, _ = fetch(db, 'A11', base + 'v1/localidades/municipios', max_mb)
    towns = json.loads(raw)
    for row in towns:
        code = str(row['id'])
        db.execute('INSERT INTO localidades VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET nome=excluded.nome,uf=excluded.uf,nome_normalizado=excluded.nome_normalizado',
                   (code, row['nome'], states.get(code[:2]), normalize(row['nome'])))
    raw, _, _ = fetch(db, 'A11', base + 'v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF', max_mb)
    geo = json.loads(raw)
    if geo.get('type') != 'FeatureCollection' or not geo.get('features'):
        raise ValueError('Malha territorial inesperada')
    for feature in geo['features']:
        props = feature.setdefault('properties', {})
        props['sigla'] = states.get(str(props.get('codarea', feature.get('id', ''))), '')
    db.execute('INSERT INTO geometrias VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET dados=excluded.dados,atualizado_em=excluded.atualizado_em',
               ('ufs', app.dumps(geo), app.now()))
    codes = [r[0] for r in db.execute('SELECT DISTINCT municipio_ibge FROM registros WHERE municipio_ibge IS NOT NULL')]
    for code in codes:
        if db.execute('SELECT 1 FROM geometrias WHERE id=?', ('municipio:' + code,)).fetchone():
            continue
        raw, _, _ = fetch(db, 'A11', base + f'v3/malhas/municipios/{code}?formato=application/vnd.geo+json&qualidade=minima', max_mb)
        shape = json.loads(raw)
        if shape.get('type') != 'FeatureCollection' or not shape.get('features'):
            raise ValueError('Malha municipal inesperada: ' + code)
        for feature in shape['features']:
            feature.setdefault('properties', {})['municipio_ibge'] = code
        db.execute('INSERT INTO geometrias VALUES (?,?,?)', ('municipio:' + code, app.dumps(shape), app.now()))
    return len(towns), f'Localidades, malha de UFs e limites de {len(codes)} municípios com dados coletados; são referência geográfica, não ocorrências.'


def collect_safernet(db, url, max_mb):
    page, digest = discover(db, 'A22', url, max_mb)
    # Extrai apenas as contagens que a publicação nomeia explicitamente. Não usa o percentual divergente do texto.
    match = re.search(r'recebeu\s+([\d.]+)\s+denúncias.*?contra\s+([\d.]+)\s+em\s+(\d{4})', page.text, re.I)
    year_match = re.search(r'Brasília,\s*4\s+de\s+julho\s+de\s+(\d{4})', page.text, re.I)
    if not match or not year_match or int(year_match[1]) != 2025 or int(match[3]) != 2023:
        raise ValueError('Publicação mudou: extração automática suspensa; revisar esquema e anos')
    rows = [(2024, int(match[1].replace('.', ''))), (2023, int(match[2].replace('.', '')))]
    for year, value in rows:
        app.put_record(db, {'id': f'A22-denuncias-trafico-online-{year}', 'fonte_id': 'A22', 'recurso_url': url,
                       'titulo': f'Denúncias de conteúdo suspeito de tráfico de pessoas online — {year}',
                       'descricao': 'Denúncias recebidas pelo canal da SaferNet Brasil contendo links com conteúdo suspeito. Contagem de denúncias, não de vítimas ou casos confirmados.',
                       'ambiente': 'virtual', 'tipo': 'estatistica', 'tema': 'Recrutamento digital', 'ano': year,
                       'valor': value, 'unidade': 'denuncias_recebidas', 'indicadores': ['M032', 'M033'],
                       'metadados': {'snapshot_sha256': digest, 'trecho': match[0], 'deduplicacao': 'Contagem de denúncias recebidas; não corresponde à contagem de links únicos.',
                                     'limite': 'Sem localização municipal ou identificação pública dos links nesta publicação.'}})
    links = re.search(r'remetidos ao Minist[eé]rio P[uú]blico Federal\s+([\d.]+)\s+links,\s+ap[oó]s a exclus[aã]o de casos repetidos', page.text, re.I)
    if links:
        app.put_record(db, {'id': 'A22-links-encaminhados-mpf-2024', 'fonte_id': 'A22', 'recurso_url': url,
                           'titulo': 'Links encaminhados pela SaferNet ao MPF após exclusão de repetidos — 2024',
                           'descricao': 'Links encaminhados ao Ministério Público Federal, após exclusão de repetidos, segundo a publicação de 04/07/2025. Unidade distinta das denúncias recebidas.',
                           'ambiente': 'virtual', 'tipo': 'estatistica', 'tema': 'Recrutamento digital', 'ano': 2024,
                           'valor': int(links[1].replace('.', '')), 'unidade': 'links_encaminhados_mpf_apos_exclusao_repetidos',
                           'indicadores': ['M033'], 'metadados': {'snapshot_sha256': digest, 'trecho_fonte': links[0],
                                                               'limite': 'Não somar aos totais de denúncias; links não equivalem a vítimas ou condenações.'}})
    app.put_record(db, {'id': 'A22-publicacao-2025-07-04', 'fonte_id': 'A22', 'recurso_url': url,
                   'titulo': 'Recrutamento online e exploração sexual: publicação da SaferNet Brasil',
                   'descricao': 'A publicação descreve denúncias de sites e contas falsas usados para recrutamento com fins de exploração sexual no Brasil e no exterior. Não individualiza acontecimentos ou locais.',
                   'ambiente': 'ambos', 'tipo': 'documento', 'tema': 'Recrutamento digital', 'ano': 2025,
                   'indicadores': ['M002', 'M033'], 'metadados': {'snapshot_sha256': digest, 'publicado_em': '2025-07-04', 'natureza': 'Publicação institucional da sociedade civil'}})
    return 3 + bool(links), 'Denúncias anuais e publicação; links encaminhados ao MPF extraídos quando explícitos, sem somar unidades distintas. Sem microdados ou pontos municipais.'


def collect_sources(source='todas', max_mb=40):
    if max_mb < 1:
        raise ValueError('--max-mb deve ser positivo')
    sources = ['A11', 'A22', 'A01', 'A02', 'A03', 'A04'] if source == 'todas' else [source]
    for ident in sources:
        with app.connect() as db:
            run_id = db.execute('INSERT INTO coletas(fonte_id,inicio,situacao) VALUES (?,?,?)', (ident, app.now(), 'em_execucao')).lastrowid
        try:
            with app.connect() as db:
                url = db.execute('SELECT url FROM fontes WHERE id=?', (ident,)).fetchone()[0]
                if ident == 'A11':
                    count, message = collect_ibge(db, max_mb)
                elif ident == 'A22':
                    count, message = collect_safernet(db, url, max_mb)
                else:
                    db.execute('DELETE FROM recursos WHERE fonte_id=?', (ident,))
                    discover(db, ident, url, max_mb)
                    count = db.execute('SELECT count(*) FROM recursos WHERE fonte_id=?', (ident,)).fetchone()[0]
                    message = f'{count} recursos catalogados. Esta execução realizou descoberta documental, sem extrair novas observações quantitativas.'
                status = 'sucesso' if ident in ('A11', 'A22') else 'descoberta'
        except Exception as exc:
            status, count, message = 'falhou', 0, f'{type(exc).__name__}: {exc}'
        with app.connect() as db:
            db.execute('UPDATE coletas SET fim=?,situacao=?,mensagem=?,linhas=? WHERE id=?', (app.now(), status, message, count, run_id))
        print(f'{ident}: {status} — {message}', flush=True)


def aggregate_disque(reader, mapping, db):
    """Deduplica protocolo por município/ano, jamais soma violações como vítimas."""
    fields = ('id_denuncia', 'data', 'uf', 'municipio', 'violacao')
    if any(not mapping.get(f) for f in fields):
        raise ValueError('Mapeamento exige: ' + ', '.join(fields))
    missing = set(mapping[f] for f in fields) - set(reader.fieldnames or [])
    if missing:
        raise ValueError('Colunas não encontradas: ' + ', '.join(sorted(missing)))
    patterns = mapping.get('valores_violacao', [])
    if not patterns or any('trafico' not in normalize(p) or 'pessoa' not in normalize(p) for p in patterns):
        raise ValueError('Informe valores_violacao explícitos relacionados a tráfico de pessoas')
    date_format = mapping.get('formato_data', '%d/%m/%Y')
    from datetime import datetime
    matched, excluded, duplicates, groups = 0, 0, 0, {}
    for row in reader:
        violation = normalize(row.get(mapping['violacao'], ''))
        if not any(normalize(p) == violation for p in patterns):
            continue
        matched += 1
        ident = row[mapping['id_denuncia']].strip()
        uf = row[mapping['uf']].strip().upper()
        town = row[mapping['municipio']].strip()
        if re.match(r'^\d{7}\s*\|', town):
            town = town.split('|')[0].strip()
        try:
            year = datetime.strptime(row[mapping['data']].strip(), date_format).year
            if not 1900 <= year <= datetime.now().year:
                raise ValueError('Ano inválido')
        except ValueError:
            excluded += 1
            continue
        if not ident:
            excluded += 1
            continue
        # Não adivinha municípios nem transforma campos suprimidos em zeros.
        if town.isdigit() and len(town) == 7:
            matches = db.execute('SELECT id,nome,uf FROM localidades WHERE id=? AND uf=?', (town, uf)).fetchall()
        else:
            matches = db.execute('SELECT id,nome,uf FROM localidades WHERE nome_normalizado=? AND uf=?', (normalize(town), uf)).fetchall()
        if len(matches) != 1:
            excluded += 1
            continue
        place = matches[0]
        key = (year, place['id'], place['nome'], place['uf'])
        values = groups.setdefault(key, set())
        if ident in values:
            duplicates += 1
        values.add(ident)
    return groups, {'linhas_trafico': matched, 'linhas_excluidas_data_id_ou_local': excluded, 'linhas_repetidas_na_mesma_celula': duplicates}


def import_disque(path, mapping_path, url, encoding='utf-8-sig', delimiter=';'):
    host = (urlparse(url).hostname or '').lower()
    if urlparse(url).scheme != 'https' or not (host == 'gov.br' or host.endswith('.gov.br')):
        raise ValueError('Informe a URL HTTPS oficial gov.br do recurso')
    mapping = json.loads(mapping_path.read_text(encoding='utf-8'))
    period = mapping.get('periodo')
    if not period or not mapping.get('campo_data_descricao') or not mapping.get('identificador_descricao'):
        raise ValueError('Mapeamento exige periodo, campo_data_descricao e identificador_descricao para preservar a cobertura')
    unit = mapping.get('unidade_contagem')
    if unit not in ('registros_administrativos_distintos_na_celula', 'denuncias_distintas_na_celula_do_recurso'):
        raise ValueError('Defina unidade_contagem e documente o significado do identificador')
    with path.open('rb') as raw_file:
        digest = hashlib.file_digest(raw_file, 'sha256').hexdigest()
    with app.connect() as db:
        run_id = db.execute('INSERT INTO coletas(fonte_id,inicio,situacao) VALUES (?,?,?)', ('A02', app.now(), 'em_execucao')).lastrowid
    try:
        with app.connect() as db:
            if not db.execute('SELECT 1 FROM localidades LIMIT 1').fetchone():
                raise ValueError('Colete A11 antes da importação para validar municípios')
            with path.open(encoding=encoding, newline='') as file:
                groups, audit = aggregate_disque(csv.DictReader(file, delimiter=delimiter), mapping, db)
            resource_id = hashlib.sha256(url.encode()).hexdigest()[:20]
            # Substitui a versão do mesmo recurso, incluindo células retiradas na nova versão.
            db.execute('DELETE FROM registros WHERE fonte_id=? AND recurso_url=?', ('A02', url))
            for (year, code, town, uf), ids in groups.items():
                app.put_record(db, {'id': f'A02-{resource_id}-{year}-{code}', 'fonte_id': 'A02', 'recurso_url': url,
                               'titulo': f'Registros de tráfico de pessoas — {town}/{uf} — {period}',
                               'descricao': 'Identificadores distintos na célula município/ano/período do recurso. Município, data e identificador têm o significado especificado no mapeamento da fonte. Células de recursos diferentes não são somáveis automaticamente.',
                               'ambiente': 'real', 'tipo': 'estatistica', 'tema': 'Denúncias de tráfico de pessoas',
                               'ano': year, 'uf': uf, 'municipio_ibge': code, 'municipio': town, 'precisao': 'municipio',
                               'valor': len(ids), 'unidade': unit, 'indicadores': ['M032', 'M033'],
                               'metadados': {'sha256_arquivo_importado': digest, 'periodo': period,
                                             'campo_data_descricao': mapping['campo_data_descricao'], 'mapeamento': mapping,
                                             'auditoria': audit, 'cobertura_anual_completa': bool(mapping.get('cobertura_anual_completa', False)),
                                             'limite': 'Não equivale a vítimas identificadas. Sem inferência sobre canal digital. Não somar recursos sobrepostos.'}})
            message = app.dumps(audit) + f'; {len(groups)} células municipais. SHA256: {digest}'
            db.execute('UPDATE coletas SET fim=?,situacao=?,mensagem=?,linhas=? WHERE id=?', (app.now(), 'sucesso', message, len(groups), run_id))
            resource(db, 'A02', url, path.name, 'csv_importado')
        print(message)
    except Exception as exc:
        with app.connect() as db:
            db.execute('UPDATE coletas SET fim=?,situacao=?,mensagem=? WHERE id=?', (app.now(), 'falhou', str(exc), run_id))
        raise


def download_disque(url, max_mb):
    host = (urlparse(url).hostname or '').lower()
    if urlparse(url).scheme != 'https' or not (host == 'gov.br' or host.endswith('.gov.br')) or max_mb < 1:
        raise ValueError('Download exige URL oficial HTTPS gov.br e limite positivo')
    folder = app.DATA / 'downloads'
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()[:20]
    temporary = folder / (key + '.part')
    target = folder / (key + '.csv')
    complete = False
    try:
        digest, total = hashlib.sha256(), 0
        # Retoma apenas se o servidor confirmar o intervalo exato solicitado.
        if temporary.exists():
            with temporary.open('rb') as previous:
                for block in iter(lambda: previous.read(1024 * 1024), b''):
                    digest.update(block)
                    total += len(block)
        headers = {'User-Agent': 'ObservatorioBrasil/1.0', 'Accept-Encoding': 'identity'}
        if total:
            headers['Range'] = f'bytes={total}-'
        request = Request(url, headers=headers)
        with urlopen(request, timeout=90) as response:
            if total and (response.status != 206 or not response.headers.get('Content-Range', '').startswith(f'bytes {total}-')):
                total, digest = 0, hashlib.sha256()
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise ValueError('Servidor retornou arquivo comprimido; baixe e descompacte manualmente')
            if 'text/csv' not in response.headers.get('Content-Type', '') and '.csv' not in urlparse(url).path:
                raise ValueError('URL não retornou CSV; consulte os recursos descobertos')
            print(f'Download iniciado em {total // (1024 * 1024)} MB; limite {max_mb} MB.', flush=True)
            started = last_progress = time.monotonic()
            with temporary.open('ab' if total else 'wb') as output:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > max_mb * 1024 * 1024:
                        complete = True  # Limite explícito: descarta o parcial.
                        raise ValueError(f'Download excede {max_mb} MB; arquivo parcial descartado')
                    digest.update(block)
                    output.write(block)
                    if time.monotonic() - last_progress > 15:
                        print(f'{total // (1024 * 1024)} MB recebidos ({int(time.monotonic() - started)} s).', flush=True)
                        last_progress = time.monotonic()
        temporary.replace(target)
        complete = True
        print(f'Arquivo: {target}\nBytes: {total}\nSHA256: {digest.hexdigest()}\nRevise o cabeçalho e o dicionário antes de importar.')
        return target
    finally:
        if complete:
            temporary.unlink(missing_ok=True)


def import_records(path):
    rows = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError('Arquivo deve conter lista de registros')
    with path.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    with app.connect() as db:
        for row in rows:
            if not row.get('metadados', {}).get('trecho_fonte'):
                raise ValueError('Cada registro importado exige metadados.trecho_fonte')
            row.setdefault('metadados', {})['sha256_arquivo_importado'] = digest
            if db.execute('SELECT 1 FROM registros WHERE id=? AND fonte_id<>?', (row.get('id'), row.get('fonte_id'))).fetchone():
                raise ValueError('Identificador já pertence a outra fonte')
            app.put_record(db, row)
        for source in {r['fonte_id'] for r in rows}:
            count = sum(r['fonte_id'] == source for r in rows)
            db.execute('INSERT INTO coletas(fonte_id,inicio,fim,situacao,mensagem,linhas) VALUES (?,?,?,?,?,?)',
                       (source, app.now(), app.now(), 'importacao_documentada', 'Importação JSON: ' + digest, count))
    print(f'{len(rows)} registros importados; SHA256: {digest}')


def profile_disque(path, encoding='utf-8-sig', delimiter=';'):
    from collections import Counter
    counts = Counter()
    total = 0
    with path.open(encoding=encoding, newline='') as file:
        reader = csv.DictReader(file, delimiter=delimiter)
        print('Colunas:', app.dumps(reader.fieldnames), flush=True)
        column = next((c for c in (reader.fieldnames or []) if normalize(c) in ('violacao', 'violacoes')), None)
        if not column:
            raise ValueError('Coluna de violação não reconhecida; consulte o dicionário da fonte')
        for row in reader:
            total += 1
            value = row.get(column, '') or ''
            if 'trafico' in normalize(value) and 'pessoa' in normalize(value):
                counts[value] += 1
    print(app.dumps({'linhas_totais': total, 'categorias_trafico_de_pessoas': counts}))
