#!/usr/bin/env python3
"""Observatório Brasil: servidor local e ferramentas de dados, somente stdlib."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('OBSERVATORIO_DATA', str(ROOT / 'var')))
CATALOG = ROOT.parent / 'Observatorio_Trafico_Pessoas_Integrado_Atualizado_2026(1)' / 'Observatorio_Trafico_Pessoas_Integrado_2026'


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'observatorio.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def read_csv(name):
    with (CATALOG / 'dados' / (name + '.csv')).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


def worlds(number):
    if number <= 9 or number in (17, 18, 19, 28, 29, 30):
        return ['virtual', 'real'] if number in (6, 9, 17, 18, 30) else ['virtual']
    if number in (16, 20, 31) or number >= 32:
        return ['real', 'virtual']
    return ['real']


def source_role(row):
    ident = row['ID']
    if ident in ('A01', 'A02', 'A03', 'A04', 'A11', 'A12', 'A16', 'A17', 'A18', 'A19', 'A20', 'A21', 'A22', 'A29', 'A30'):
        return 'brasil'
    if ident in ('A06', 'A07', 'A24', 'A36', 'A37', 'F13'):
        return 'fora_do_recorte'
    return 'contexto_ou_recorte_brasil_a_verificar'


def init_db():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS catalogo (tipo TEXT, id TEXT, dados TEXT NOT NULL, PRIMARY KEY(tipo,id));
        CREATE TABLE IF NOT EXISTS fontes (id TEXT PRIMARY KEY, nome TEXT NOT NULL, url TEXT NOT NULL,
          escopo TEXT NOT NULL, dados TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS coletas (id INTEGER PRIMARY KEY, fonte_id TEXT REFERENCES fontes(id),
          inicio TEXT NOT NULL, fim TEXT, situacao TEXT NOT NULL, mensagem TEXT, linhas INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS recursos (id TEXT PRIMARY KEY, fonte_id TEXT REFERENCES fontes(id),
          url TEXT NOT NULL, titulo TEXT NOT NULL, formato TEXT NOT NULL, descoberto_em TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, fonte_id TEXT REFERENCES fontes(id),
          url TEXT NOT NULL, sha256 TEXT NOT NULL, arquivo TEXT NOT NULL, coletado_em TEXT NOT NULL,
          UNIQUE(fonte_id,url,sha256));
        CREATE TABLE IF NOT EXISTS registros (id TEXT PRIMARY KEY, fonte_id TEXT NOT NULL REFERENCES fontes(id),
          recurso_url TEXT NOT NULL, titulo TEXT NOT NULL, descricao TEXT NOT NULL,
          ambiente TEXT NOT NULL, tipo TEXT NOT NULL, tema TEXT NOT NULL, ano INTEGER,
          uf TEXT, municipio_ibge TEXT, municipio TEXT, precisao TEXT NOT NULL,
          latitude REAL, longitude REAL, valor REAL, unidade TEXT, origem_publicacao TEXT NOT NULL,
          relacao_brasil TEXT NOT NULL, situacao TEXT NOT NULL, indicadores TEXT NOT NULL,
          coletado_em TEXT NOT NULL, metadados TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS registros_filtro ON registros(ambiente,uf,ano,tema);
        CREATE TABLE IF NOT EXISTS localidades (id TEXT PRIMARY KEY, nome TEXT, uf TEXT, nome_normalizado TEXT);
        CREATE INDEX IF NOT EXISTS localidades_nome ON localidades(nome_normalizado,uf);
        CREATE TABLE IF NOT EXISTS geometrias (id TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado_em TEXT NOT NULL);
        ''')
        for name in ('indicadores', 'correlacoes', 'perguntas'):
            for row in read_csv(name):
                if name == 'indicadores':
                    row['ambientes'] = worlds(int(row['ID'][1:]))
                db.execute('INSERT INTO catalogo VALUES (?,?,?) ON CONFLICT(tipo,id) DO UPDATE SET dados=excluded.dados',
                           (name, row['ID'], dumps(row)))
        for row in read_csv('fontes'):
            db.execute('INSERT INTO fontes VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET nome=excluded.nome,url=excluded.url,escopo=excluded.escopo,dados=excluded.dados',
                       (row['ID'], row['Fonte'], row['URL oficial ou pública'], source_role(row), dumps(row)))


def put_record(db, record):
    allowed = {'id', 'fonte_id', 'recurso_url', 'titulo', 'descricao', 'ambiente', 'tipo', 'tema', 'ano', 'uf',
               'municipio_ibge', 'municipio', 'precisao', 'latitude', 'longitude', 'valor', 'unidade',
               'origem_publicacao', 'relacao_brasil', 'situacao', 'indicadores', 'coletado_em', 'metadados'}
    required = {'id', 'fonte_id', 'recurso_url', 'titulo', 'descricao', 'ambiente', 'tipo', 'tema'}
    if set(record) - allowed or not required.issubset(record):
        raise ValueError('Campos desconhecidos ou campos obrigatórios ausentes no registro')
    base = dict(ano=None, uf=None, municipio_ibge=None, municipio=None, precisao='pais', latitude=None,
                longitude=None, valor=None, unidade=None, origem_publicacao='Brasil',
                relacao_brasil='Informação publicada sobre o Brasil', situacao='publicado_pela_fonte',
                indicadores=[], metadados={}, coletado_em=now())
    base.update(record)
    if base['ano'] is not None and (type(base['ano']) is not int or not 1900 <= base['ano'] <= datetime.now().year):
        raise ValueError('Ano inválido')
    for key in ('valor', 'latitude', 'longitude'):
        if base[key] is not None and (type(base[key]) not in (int, float) or not math.isfinite(base[key])):
            raise ValueError('Valor numérico inválido: ' + key)
    if base['tipo'] not in ('estatistica', 'documento', 'acontecimento', 'contexto'):
        raise ValueError('Natureza do registro inválida')
    if urlparse(base['recurso_url']).scheme not in ('https', 'http'):
        raise ValueError('Registro exige URL pública HTTP(S)')
    if base['uf'] and base['uf'] not in {'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'}:
        raise ValueError('UF inválida')
    if base['latitude'] is not None and not -90 <= base['latitude'] <= 90:
        raise ValueError('Latitude inválida')
    if base['longitude'] is not None and not -180 <= base['longitude'] <= 180:
        raise ValueError('Longitude inválida')
    if not isinstance(base['indicadores'], list) or not isinstance(base['metadados'], dict):
        raise ValueError('Indicadores devem ser lista e metadados devem ser objeto')
    known = {r[0] for r in db.execute("SELECT id FROM catalogo WHERE tipo='indicadores'")}
    if set(base['indicadores']) - known:
        raise ValueError('Indicador desconhecido')
    if base['municipio_ibge']:
        town = db.execute('SELECT uf FROM localidades WHERE id=?', (base['municipio_ibge'],)).fetchone()
        if not town or town[0] != base['uf']:
            raise ValueError('Município não corresponde à UF na referência IBGE coletada')
    if base['precisao'] == 'municipio' and not base['municipio_ibge']:
        raise ValueError('Precisão municipal exige código IBGE validado')
    if base['origem_publicacao'] != 'Brasil' and not base['metadados'].get('trecho_relacao_brasil'):
        raise ValueError('Publicação internacional exige trecho_relacao_brasil nos metadados')
    if base['ambiente'] not in ('real', 'virtual', 'ambos'):
        raise ValueError('Ambiente inválido')
    if base['precisao'] not in ('pais', 'uf', 'municipio', 'local_exato', 'nao_informada'):
        raise ValueError('Precisão geográfica inválida')
    if base['precisao'] == 'local_exato' and (base['latitude'] is None or base['longitude'] is None):
        raise ValueError('Local exato exige coordenadas documentadas')
    if base['precisao'] != 'local_exato' and (base['latitude'] is not None or base['longitude'] is not None):
        raise ValueError('Coordenadas pontuais exigem precisão local_exato')
    if base['tipo'] == 'estatistica' and (base['valor'] is None or not base['unidade']):
        raise ValueError('Estatística exige valor e unidade')
    if not base['relacao_brasil'].strip():
        raise ValueError('É necessário documentar a relação com o Brasil')
    for field in ('indicadores', 'metadados'):
        base[field] = dumps(base[field])
    columns = list(base)
    db.execute(f"INSERT INTO registros ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) "
               f"ON CONFLICT(id) DO UPDATE SET {','.join(c+'=excluded.'+c for c in columns if c != 'id')}",
               list(base.values()))


def decode_record(row):
    obj = dict(row)
    for field in ('indicadores', 'metadados'):
        obj[field] = json.loads(obj[field])
    obj['disponibilidade'] = field_availability(obj)
    return obj


def field_availability(record):
    metadata = record['metadados']
    result = {}
    for key in ('ano', 'valor', 'unidade', 'uf', 'municipio', 'municipio_ibge', 'latitude', 'longitude'):
        value = record.get(key)
        if value is not None and value != '':
            status, reason = 'disponivel', 'Informação estruturada a partir da fonte.'
        elif key in ('valor', 'unidade') and record['tipo'] != 'estatistica':
            status, reason = 'nao_aplicavel', 'Documento/contexto não constitui uma observação numérica. Tabelas vinculadas são extraídas em registros próprios.'
        elif key in ('latitude', 'longitude') and record['precisao'] != 'local_exato':
            status, reason = 'nao_aplicavel', 'Registro representado por área territorial, sem coordenada pontual de ocorrência.'
        elif key in ('uf', 'municipio', 'municipio_ibge') and record['precisao'] == 'pais':
            status, reason = 'nao_aplicavel', 'Abrangência nacional deste registro; documentos locais podem existir em fichas vinculadas.'
        elif key in ('municipio', 'municipio_ibge') and record['precisao'] == 'uf':
            status, reason = 'nao_aplicavel', 'Abrangência estadual; não é uma observação municipal.'
        elif key == 'ano' and metadata.get('periodos_referencia'):
            status, reason = 'disponivel_como_periodo', 'O período está estruturado nos metadados; não foi reduzido artificialmente a um único ano.'
        elif key == 'ano' and metadata.get('investigacao_temporal'):
            status, reason = 'nao_localizado_na_parte_examinada', 'Nenhuma data ou período inequívoco estruturado na parte examinada; a fonte ainda pode disponibilizá-lo em arquivo ou campo específico.'
        else:
            status, reason = 'nao_extraido', 'Campo ainda não estruturado; não significa que a fonte não o disponibilize.'
        result[key] = {'situacao': status, 'motivo': reason}
    for key in ('data_publicacao', 'data_atualizacao'):
        result[key] = {'situacao': 'disponivel' if metadata.get(key) else 'nao_localizado_na_parte_examinada' if metadata.get('investigacao_temporal') else 'nao_extraido',
                       'motivo': 'Data estruturada com evidência da fonte.' if metadata.get(key) else 'Metadados e cabeçalhos examinados; data não estruturada na parte analisada, sem presumir que inexista na fonte.' if metadata.get('investigacao_temporal') else 'Data editorial ainda não estruturada.'}
    return result


def query_records(db, params):
    clauses, values = [], []
    for field in ('uf', 'municipio_ibge', 'tipo', 'fonte_id'):
        value = params.get(field, [''])[0]
        if value:
            clauses.append(field + '=?')
            values.append(value)
    year = params.get('ano', [''])[0]
    if year:
        clauses.append("(ano=? OR EXISTS (SELECT 1 FROM json_each(json_extract(registros.metadados,'$.periodos_referencia')) p WHERE CAST(? AS INTEGER) BETWEEN json_extract(p.value,'$.inicio') AND json_extract(p.value,'$.fim')))")
        values.extend([year, year])
    theme = params.get('tema', [''])[0]
    if theme:
        clauses.append("(tema=? OR EXISTS (SELECT 1 FROM json_each(registros.indicadores) ri JOIN catalogo c ON c.tipo='indicadores' AND c.id=ri.value WHERE json_extract(c.dados,'$.Dimensão')=?))")
        values.extend([theme, theme])
    ambiente = params.get('ambiente', [''])[0]
    if ambiente in ('real', 'virtual'):
        clauses.append("ambiente IN (?, 'ambos')")
        values.append(ambiente)
    text = params.get('q', [''])[0].strip()
    if text:
        clauses.append("(titulo LIKE ? ESCAPE '\\' OR descricao LIKE ? ESCAPE '\\' OR municipio LIKE ? ESCAPE '\\')")
        text = '%' + text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        values.extend([text] * 3)
    indicador = params.get('indicador', [''])[0]
    if indicador:
        clauses.append('EXISTS (SELECT 1 FROM json_each(registros.indicadores) WHERE value=?)')
        values.append(indicador)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    return [decode_record(r) for r in db.execute('SELECT * FROM registros' + where + ' ORDER BY ano DESC,titulo,id', values)]


def get_catalog(db):
    result = {}
    for row in db.execute('SELECT * FROM catalogo ORDER BY id'):
        result.setdefault(row['tipo'], []).append(json.loads(row['dados']))
    return result


def get_sources(db):
    result = []
    collectors = {'A01': 'descoberta de documentos', 'A02': 'descoberta + CSV por mapeamento',
                  'A03': 'descoberta de documentos', 'A04': 'cadastro vigente agregado por UF/ano fiscal + descoberta documental',
                  'A11': 'localidades + malha de UFs', 'A22': 'estatísticas publicadas + documentos'}
    for row in db.execute('SELECT * FROM fontes ORDER BY id'):
        obj = dict(row)
        obj['dados'] = json.loads(obj['dados'])
        last = db.execute('SELECT * FROM coletas WHERE fonte_id=? ORDER BY id DESC LIMIT 1', (obj['id'],)).fetchone()
        obj['ultima_coleta'] = dict(last) if last else None
        obj['registros'] = db.execute('SELECT count(*) FROM registros WHERE fonte_id=?', (obj['id'],)).fetchone()[0]
        obj['recursos'] = db.execute('SELECT count(*) FROM recursos WHERE fonte_id=?', (obj['id'],)).fetchone()[0]
        obj['coletor'] = collectors.get(obj['id'], 'leitura documental pública; extração quantitativa específica pendente')
        result.append(obj)
    return result


def map_overview(db, params):
    """Cobertura editorial de todas as fontes, separada das observações territoriais."""
    records = query_records(db, params)
    national_params = {k: v for k, v in params.items() if k not in ('uf', 'municipio_ibge')}
    national = [r for r in query_records(db, national_params) if not r['uf'] and not r['municipio_ibge'] and r['precisao'] == 'pais']
    catalog = get_catalog(db)
    sources = get_sources(db)
    all_records = query_records(db, {})
    theme = params.get('tema', [''])[0]
    selected = params.get('fonte_id', [''])[0]
    indicator = params.get('indicador', [''])[0]
    for source in sources:
        linked = [i for i in catalog.get('indicadores', []) if source['id'] in
                  [x.strip() for x in i.get('Fontes IDs', '').split(';')]]
        source_records = [r for r in all_records if r['fonte_id'] == source['id']]
        source['indicadores'] = sorted(set([i['ID'] for i in linked] + [ident for r in source_records for ident in r['indicadores']]))
        source['temas'] = sorted(set([i['Dimensão'] for i in catalog['indicadores'] if i['ID'] in source['indicadores']] + [r['tema'] for r in source_records]))
        source['ambientes'] = sorted(set(w for i in linked for w in i['ambientes'])) or ['real', 'virtual']
        source['registros_no_filtro'] = sum(r['fonte_id'] == source['id'] for r in records)
        source['registros_nacionais'] = sum(r['fonte_id'] == source['id'] for r in national)
        source['ufs_com_dados'] = sorted({r['uf'] for r in source_records if r['uf']})
        source['municipios_com_dados'] = sorted({r['municipio_ibge'] for r in source_records if r['municipio_ibge']})
        source['cobertura_mapa'] = ('territorial' if source['ufs_com_dados'] else 'nacional' if source_records
                                  else 'fora_do_recorte' if source['escopo'] == 'fora_do_recorte' else 'sem_observacoes_importadas')
        source['relacao_com_territorio'] = ('Observações disponíveis no território selecionado' if source['registros_no_filtro'] and (params.get('uf') or params.get('municipio_ibge'))
                                          else 'Informação nacional; não é observação local' if source['registros_nacionais']
                                          else 'Referência do catálogo; não estabelece ocorrência neste território')
    visible = [s for s in sources if (not selected or s['id'] == selected)
               and (not theme or theme in s['temas'])
               and (not indicator or indicator in s['indicadores'] or any(r['fonte_id'] == s['id'] for r in records))]
    return {'fontes': visible, 'total_fontes': len(sources), 'registros': records,
            'nacionais': national, 'territorio': {'uf': params.get('uf', [''])[0], 'municipio_ibge': params.get('municipio_ibge', [''])[0]}}


class Handler(BaseHTTPRequestHandler):
    def send(self, body, content_type='application/json; charset=utf-8', status=200, extra=None):
        if not isinstance(body, bytes):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Cache-Control', 'no-store')
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path, params = parsed.path, parse_qs(parsed.query)
        if path == '/painel-original':
            return self.send((CATALOG / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/format.js': ('format.js', 'text/javascript; charset=utf-8'),
                  '/mapa.css': ('mapa.css', 'text/css; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path in assets:
            filename, mime = assets[path]
            return self.send((ROOT / 'web' / filename).read_bytes(), mime)
        if not path.startswith('/api/'):
            return self.send(dumps({'erro': 'Não encontrado'}), status=404)
        try:
            with connect() as db:
                if path == '/api/catalogo':
                    result = get_catalog(db)
                elif path == '/api/fontes':
                    result = get_sources(db)
                elif path == '/api/cobertura':
                    from coverage import overview
                    result = overview(db)
                elif path == '/api/recrutamento':
                    from recrutamento import query
                    result = query(db, params)
                elif path == '/api/analise-digital':
                    from analise_digital import overview
                    result = overview(db)
                elif path == '/api/mapa':
                    result = map_overview(db, params)
                elif path == '/api/coletas':
                    result = [dict(r) for r in db.execute('SELECT * FROM coletas ORDER BY id DESC LIMIT 100')]
                elif path == '/api/recursos':
                    result = [dict(r) for r in db.execute('SELECT * FROM recursos ORDER BY fonte_id,titulo')]
                elif path == '/api/investigacoes':
                    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='investigacoes'").fetchone()
                    result = [dict(r) for r in db.execute('SELECT * FROM investigacoes ORDER BY fonte_id,url')] if exists else []
                elif path == '/api/geografia':
                    if params.get('nivel', [''])[0] == 'municipios':
                        features = []
                        for row in db.execute("SELECT dados FROM geometrias WHERE id LIKE 'municipio:%'"):
                            item = json.loads(row[0])
                            features.extend(item.get('features', []))
                        result = {'type': 'FeatureCollection', 'features': features}
                    else:
                        row = db.execute("SELECT dados FROM geometrias WHERE id='ufs'").fetchone()
                        result = json.loads(row[0]) if row else {'type': 'FeatureCollection', 'features': []}
                elif path == '/api/localidades':
                    uf = params.get('uf', [''])[0]
                    result = [dict(r) for r in db.execute('SELECT id,nome,uf FROM localidades WHERE uf=? ORDER BY nome', (uf,))] if uf else []
                elif path in ('/api/registros', '/api/exportar.csv'):
                    rows = query_records(db, params)
                    if path.endswith('.csv'):
                        buf = io.StringIO(newline='')
                        if rows:
                            writer = csv.DictWriter(buf, fieldnames=list(rows[0]), delimiter=';')
                            writer.writeheader()
                            for row in rows:
                                clean = {}
                                for key, value in row.items():
                                    value = dumps(value) if isinstance(value, (dict, list)) else value
                                    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                                        value = "'" + value
                                    clean[key] = value
                                writer.writerow(clean)
                        return self.send('\ufeff' + buf.getvalue(), 'text/csv; charset=utf-8', extra={'Content-Disposition': 'attachment; filename="observatorio_brasil.csv"'})
                    result = {'total': len(rows), 'registros': rows}
                elif path == '/api/resumo':
                    result = {'registros': db.execute('SELECT count(*) FROM registros').fetchone()[0],
                              'fontes': db.execute('SELECT count(*) FROM fontes').fetchone()[0],
                              'fontes_com_dados': db.execute('SELECT count(DISTINCT fonte_id) FROM registros').fetchone()[0],
                              'municipios': db.execute('SELECT count(DISTINCT municipio_ibge) FROM registros WHERE municipio_ibge IS NOT NULL').fetchone()[0],
                              'localidades': db.execute('SELECT count(*) FROM localidades').fetchone()[0],
                              'ultima_coleta': db.execute('SELECT max(fim) FROM coletas').fetchone()[0],
                              'tipos': [dict(r) for r in db.execute('SELECT tipo,count(*) quantidade FROM registros GROUP BY tipo')]}
                else:
                    return self.send(dumps({'erro': 'API não encontrada'}), status=404)
            return self.send(dumps(result))
        except (ValueError, sqlite3.Error) as exc:
            self.log_error('%s', exc)
            return self.send(dumps({'erro': 'Falha ao consultar a base local.'}), status=500)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init', help='Importa os 59 itens e os catálogos originais')
    sub.add_parser('collect-mte-cadastro', help='Importa agregados por UF e ano fiscal do cadastro vigente do MTE')
    sub.add_parser('collect-perfil-recente', help='Importa perfis institucionais verificados dos relatórios nacionais 2024 e 2025')
    virtual_import = sub.add_parser('import-recrutamento', help='Importa fichas documentadas de recrutamento digital')
    virtual_import.add_argument('arquivo', type=Path)
    serve = sub.add_parser('serve', help='Inicia a aplicação local')
    serve.add_argument('--port', type=int, default=8765)
    collect = sub.add_parser('collect', help='Executa coletores disponíveis')
    collect.add_argument('--source', choices=['todas', 'A01', 'A02', 'A03', 'A04', 'A11', 'A22'], default='todas')
    collect.add_argument('--max-mb', type=int, default=40)
    imp = sub.add_parser('import-disque', help='Importa CSV Disque 100 com mapeamento explícito de colunas')
    imp.add_argument('arquivo', type=Path)
    imp.add_argument('--mapping', required=True, type=Path)
    imp.add_argument('--url', required=True, help='URL oficial do arquivo de origem')
    imp.add_argument('--encoding', default='utf-8-sig')
    imp.add_argument('--delimiter', default=';')
    download = sub.add_parser('download', help='Baixa um recurso oficial Disque 100, com limite e SHA256')
    download.add_argument('--url', required=True)
    download.add_argument('--max-mb', type=int, default=100)
    records = sub.add_parser('import-registros', help='Importa registros documentados, inclusive fontes internacionais sobre o Brasil')
    records.add_argument('arquivo', type=Path)
    profile = sub.add_parser('profile-disque', help='Lista cabeçalho e categorias de tráfico, sem expor linhas pessoais')
    profile.add_argument('arquivo', type=Path)
    profile.add_argument('--encoding', default='utf-8-sig')
    profile.add_argument('--delimiter', default=';')
    pipeline = sub.add_parser('collect-disque', help='Baixa e importa automaticamente um recurso Disque 100 já mapeado')
    pipeline.add_argument('--url', required=True)
    pipeline.add_argument('--mapping', type=Path, required=True)
    pipeline.add_argument('--max-mb', type=int, default=100)
    documental = sub.add_parser('collect-catalogo', help='Verifica as 59 fontes e importa trechos documentais públicos sobre o Brasil')
    documental.add_argument('--workers', type=int, default=4)
    documental.add_argument('--max-mb', type=int, default=4)
    documental.add_argument('--source', default='todas', help='IDs separados por vírgula, ou todas')
    enrich = sub.add_parser('enrich', help='Enriquece datas e examina PDFs vinculados, recuperando URLs migradas do MJSP')
    enrich.add_argument('--source', default='A01,A04,A21,A22')
    enrich.add_argument('--limit', type=int, default=24)
    enrich.add_argument('--workers', type=int, default=4)
    enrich.add_argument('--max-mb', type=int, default=20)
    enrich.add_argument('--cached-only', action='store_true', help='Reprocessa snapshots locais sem novos downloads')
    args = parser.parse_args()
    init_db()
    if args.command == 'collect-perfil-recente':
        from perfil_recente import collect as collect_profile
        collect_profile()
    elif args.command == 'import-recrutamento':
        from recrutamento import import_file
        import_file(args.arquivo)
    elif args.command == 'collect-mte-cadastro':
        from mte import collect as collect_mte
        collect_mte()
    elif args.command == 'serve':
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
        print(f'Observatório Brasil: http://127.0.0.1:{args.port} (Ctrl+C para encerrar)', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    elif args.command == 'collect':
        from collectors import collect_sources
        collect_sources(args.source, args.max_mb)
    elif args.command == 'import-disque':
        from collectors import import_disque
        import_disque(args.arquivo, args.mapping, args.url, args.encoding, args.delimiter)
    elif args.command == 'download':
        from collectors import download_disque
        download_disque(args.url, args.max_mb)
    elif args.command == 'import-registros':
        from collectors import import_records
        import_records(args.arquivo)
    elif args.command == 'profile-disque':
        from collectors import profile_disque
        profile_disque(args.arquivo, args.encoding, args.delimiter)
    elif args.command == 'collect-disque':
        from collectors import download_disque, import_disque
        target = download_disque(args.url, args.max_mb)
        import_disque(target, args.mapping, args.url)
    elif args.command == 'collect-catalogo':
        from documents import collect_catalog
        collect_catalog(args.workers, args.max_mb, args.source)
    elif args.command == 'enrich':
        from enrichment import enrich_sources
        enrich_sources(args.source, args.limit, args.workers, args.max_mb, args.cached_only)
    else:
        print('Base inicializada. Execute python3 app.py collect e python3 app.py serve.')


if __name__ == '__main__':
    main()
