"""Fichas documentadas de recrutamento digital, separadas dos agregados territoriais."""
import hashlib
import json
import re
from datetime import date
from urllib.parse import urlparse

import app

CLASSIFICACOES = {'trafico_documentado', 'suspeita_nao_confirmada', 'golpe_sem_vinculo_trafico', 'alerta_geral'}
RECORTES = {'brasil', 'conexao_brasil', 'internacional'}
ALLOWED = {'id', 'titulo', 'descricao', 'classificacao', 'recorte', 'pais', 'plataforma', 'data_publicacao',
           'fonte_id', 'fonte_nome', 'fonte_url', 'trecho_evidencia', 'relacao_brasil', 'sinais', 'limites'}
REQUIRED = {'id', 'titulo', 'descricao', 'classificacao', 'recorte', 'pais', 'fonte_nome', 'fonte_url', 'trecho_evidencia', 'limites'}


def init(db):
    db.execute('''CREATE TABLE IF NOT EXISTS recrutamento (
      id TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado_em TEXT NOT NULL)''')


def validate(row, db):
    if not isinstance(row, dict) or set(row) - ALLOWED or not REQUIRED.issubset(row):
        raise ValueError('Ficha contém campos desconhecidos ou obrigatórios ausentes')
    for name in REQUIRED - {'classificacao', 'recorte'}:
        if not isinstance(row[name], str) or not row[name].strip() or len(row[name]) > 10000:
            raise ValueError('Campo obrigatório inválido: ' + name)
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', row['id']):
        raise ValueError('ID deve usar letras, números, hífen ou sublinhado')
    if row['classificacao'] not in CLASSIFICACOES or row['recorte'] not in RECORTES:
        raise ValueError('Classificação ou recorte inválido')
    url = urlparse(row['fonte_url'])
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
        raise ValueError('Fonte deve ser URL pública HTTP(S) válida')
    if row.get('fonte_id') and not db.execute('SELECT 1 FROM fontes WHERE id=?', (row['fonte_id'],)).fetchone():
        raise ValueError('Fonte não cadastrada')
    if row['recorte'] in ('brasil', 'conexao_brasil') and not str(row.get('relacao_brasil', '')).strip():
        raise ValueError('Recorte brasileiro exige evidência da relação com o Brasil')
    if row.get('data_publicacao'):
        try:
            parsed = date.fromisoformat(row['data_publicacao'])
            if parsed > date.today():
                raise ValueError('Data futura')
        except (TypeError, ValueError):
            raise ValueError('Data de publicação inválida; use AAAA-MM-DD')
    if not isinstance(row.get('sinais', []), list) or any(not isinstance(s, str) or not s.strip() for s in row.get('sinais', [])):
        raise ValueError('Sinais devem ser uma lista de textos')
    if row.get('plataforma') is not None and not isinstance(row['plataforma'], str):
        raise ValueError('Plataforma inválida')


def import_file(path):
    raw = path.read_bytes()
    data = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data, list) or not data:
        raise ValueError('Arquivo deve conter uma lista não vazia')
    with app.connect() as db:
        init(db)
        ids = set()
        for row in data:
            validate(row, db)
            if row['id'] in ids:
                raise ValueError('ID duplicado no arquivo: ' + row['id'])
            existing = db.execute('SELECT dados FROM recrutamento WHERE id=?', (row['id'],)).fetchone()
            if existing and json.loads(existing['dados'])['fonte_url'] != row['fonte_url']:
                raise ValueError('ID já pertence a outra fonte; use um novo ID: ' + row['id'])
            ids.add(row['id'])
        for row in data:
            row = {**row, 'sha256_importacao': hashlib.sha256(raw).hexdigest()}
            db.execute('INSERT INTO recrutamento VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET dados=excluded.dados,atualizado_em=excluded.atualizado_em',
                       (row['id'], app.dumps(row), app.now()))
    print(f'{len(data)} fichas importadas ou atualizadas; SHA256: {hashlib.sha256(raw).hexdigest()}')


def query(db, params):
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='recrutamento'").fetchone()
    if not exists:
        return {'total': 0, 'fichas': []}
    rows = [json.loads(row['dados']) | {'atualizado_em': row['atualizado_em']} for row in db.execute('SELECT dados,atualizado_em FROM recrutamento')]
    for field in ('classificacao', 'recorte', 'fonte_id', 'plataforma'):
        value = params.get(field, [''])[0]
        if value:
            rows = [r for r in rows if r.get(field) == value]
    year = params.get('ano', [''])[0]
    if year:
        rows = [r for r in rows if r.get('data_publicacao', '').startswith(year + '-')]
    term = params.get('q', [''])[0].strip().casefold()
    if term:
        rows = [r for r in rows if term in ' '.join(str(r.get(k, '')) for k in ('titulo', 'descricao', 'pais', 'plataforma', 'fonte_nome')).casefold()]
    rows.sort(key=lambda r: (r.get('data_publicacao') or '', r['id']), reverse=True)
    return {'total': len(rows), 'fichas': rows}
