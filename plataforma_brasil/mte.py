"""Agregados do cadastro público do MTE, preservando o recorte do cadastro vigente."""
from collections import Counter
import csv
import io
import re
from datetime import datetime

import app
from collectors import fetch, resource

URL = 'https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/inspecao-do-trabalho/areas-de-atuacao/cadastro_de_empregadores.csv'
UFS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
REQUIRED = {'ID', 'Ano da ação fiscal', 'UF', 'Trabalhadores envolvidos', 'Inclusão no Cadastro de Empregadores'}


def aggregate(body):
    reader = csv.DictReader(io.StringIO(body.decode('cp1252'), newline=''), delimiter=';')
    if not REQUIRED.issubset(reader.fieldnames or []):
        raise ValueError('Esquema do cadastro MTE mudou; importação suspensa')
    counts, excluded, identifiers, total = Counter(), 0, set(), 0
    for row in reader:
        total += 1
        ident = (row.get('ID') or '').strip()
        year = (row.get('Ano da ação fiscal') or '').strip()
        uf = (row.get('UF') or '').strip().upper()
        if not ident or ident in identifiers:
            raise ValueError('Identificador de linha ausente ou duplicado; importação suspensa')
        identifiers.add(ident)
        if not re.fullmatch(r'\d{4}', year) or not 1900 <= int(year) <= datetime.now().year or uf not in UFS:
            excluded += 1
            continue
        counts[(int(year), uf)] += 1
    if not total or not counts:
        raise ValueError('Cadastro vazio ou sem ano/UF válidos; importação suspensa')
    return counts, {'linhas_total': total, 'linhas_excluidas_ano_ou_uf': excluded}


def collect():
    with app.connect() as db:
        run = db.execute('INSERT INTO coletas(fonte_id,inicio,situacao) VALUES (?,?,?)', ('A04', app.now(), 'em_execucao')).lastrowid
    try:
        with app.connect() as db:
            body, mime, digest = fetch(db, 'A04', URL, 10)
            if 'csv' not in mime and 'octet-stream' not in mime:
                raise ValueError('Recurso do MTE não retornou CSV')
            counts, audit = aggregate(body)
            captured = app.now()
            db.execute("DELETE FROM registros WHERE fonte_id='A04' AND id LIKE 'A04-cadastro-vigente-%'")
            for (year, uf), count in sorted(counts.items()):
                app.put_record(db, {'id': f'A04-cadastro-vigente-{year}-{uf}', 'fonte_id': 'A04', 'recurso_url': URL,
                    'titulo': f'Linhas no cadastro vigente do MTE — ação fiscal {year} · {uf}',
                    'descricao': 'Quantidade de linhas do cadastro vigente agrupadas pela UF e pelo ano da ação fiscal. Retrato da versão coletada, não série completa de fiscalizações.',
                    'ambiente': 'real', 'tipo': 'estatistica', 'tema': 'Fiscalização e trabalho escravo',
                    'ano': year, 'uf': uf, 'precisao': 'uf', 'valor': count, 'unidade': 'linhas_cadastro_vigente_mte',
                    'metadados': {'snapshot_sha256': digest, 'coletado_em_cadastro': captured, 'auditoria': audit,
                        'significado_ano': 'ano_da_acao_fiscal', 'referencia_territorial': 'uf_informada_no_cadastro',
                        'cobertura_anual_completa': False,
                        'nota_cobertura': 'Retrato do cadastro vigente na coleta: anos indicam a ação fiscal; não abrangem todas as fiscalizações do ano.',
                        'metodo': 'Contagem de linhas do arquivo oficial, sem dados individuais; ID validado como único na versão coletada.',
                        'limite': 'Cadastro administrativo de empregadores por trabalho análogo à escravidão. Não equivale a tráfico de pessoas, número de vítimas, resgates ou todas as fiscalizações. Não comparar como série anual completa.'}})
            resource(db, 'A04', URL, 'Cadastro vigente de empregadores do MTE — CSV', 'csv_importado')
            message = app.dumps(audit) + f'; {len(counts)} células UF/ano fiscal; retrato do cadastro vigente. SHA256: {digest}'
            db.execute('UPDATE coletas SET fim=?,situacao=?,mensagem=?,linhas=? WHERE id=?', (app.now(), 'sucesso', message, len(counts), run))
        print(message)
    except Exception as exc:
        with app.connect() as db:
            db.execute('UPDATE coletas SET fim=?,situacao=?,mensagem=? WHERE id=?', (app.now(), 'falhou', str(exc), run))
        raise
