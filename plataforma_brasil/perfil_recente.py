"""Transcrição verificável de perfis por instituição dos relatórios oficiais recentes."""
import re

import app
from collectors import fetch, resource
from enrichment import extract_pdf

REPORTS = {
    2024: ('1bi7SLUXzkYTKDeGXGo6YKKR6ixz_7PdA', 20),
    2025: ('1VMYovTGkM56sqMhUHB3z0Wv78aKA0xQf', 23),
}

# Seleções editoriais conferidas nas páginas, conservadas por grupo institucional.
GROUPS = {
    2024: [
        {'id': 'disque100', 'nome': 'Disque 100', 'unidade': 'registros_disque100_com_perfil',
         'evidencia': '43,48% (n=30) das vítimas são do sexo masculino, 2,90% (n=2) do sexo feminino e 53,62% (n=37) não tiveram o gênero informado, totalizando 69 registros.',
         'categorias': [('Masculino', 30), ('Feminino', 2), ('Não informado', 37)], 'total': 69,
         'limite': 'Registros do Disque 100; Ligue 180 voltou a operar separadamente em 2024. Não equivale aos canais combinados de 2021–2023 nem identifica meio digital.'},
        {'id': 'sus', 'nome': 'Ministério da Saúde · SUS', 'unidade': 'possiveis_vitimas_notificadas_sus',
         'evidencia': '62,8% (n=191) de mulheres e 37,2% (n=113) de homens, totalizando 304 vítimas.',
         'categorias': [('Feminino', 191), ('Masculino', 113)], 'total': 304,
         'limite': 'Valor conforme relatório de 2024. O relatório seguinte informa 340 notificações preliminares em 2024; versões e critérios precisam de reconciliação antes de comparar.'},
    ],
    2025: [
        {'id': 'disque100', 'nome': 'Disque 100', 'unidade': 'denuncias_disque100_com_registro_vitima',
         'evidencia': '49,5% (n=237), seguido do masculino, com 26,7% (n=128), de um total de 479 denúncias com registro de vítima. Chama atenção, contudo, que 23,8% (n=114) dos registros não apresentam informação sobre o gênero.',
         'categorias': [('Feminino', 237), ('Masculino', 128), ('Não informado', 114)], 'total': 479,
         'limite': 'Denúncias com registro de vítima; não são pessoas únicas nem têm meio digital identificado. Ligue 180 é apresentado separadamente.'},
        {'id': 'sus', 'nome': 'Ministério da Saúde · SUS', 'unidade': 'notificacoes_sus_possiveis_vitimas',
         'evidencia': '51,5% (n=223) são do sexo feminino e 48,5% (n=210) do sexo masculino, totalizando 433 notificações.',
         'categorias': [('Feminino', 223), ('Masculino', 210)], 'total': 433,
         'limite': 'Notificações preliminares do SUS, sujeitas a revisão; não correspondem necessariamente a pessoas únicas ou casos com canal digital.'},
    ],
}


def extract_groups(year, text):
    _, page_no = REPORTS[year]
    pages = text.split('\f')
    if len(pages) < page_no:
        raise ValueError('PDF não contém a página esperada')
    page = re.sub(r'\s+', ' ', pages[page_no - 1]).strip()
    result = []
    for group in GROUPS[year]:
        if group['evidencia'] not in page:
            raise ValueError(f'Trecho de {year}/{group["nome"]} não corresponde à publicação; revisão necessária')
        if sum(v for _, v in group['categorias']) != group['total']:
            raise ValueError('Categorias não conferem com o total')
        result.append(group)
    return result


def collect():
    # Baixa e valida ambos antes de substituir qualquer ficha já existente.
    with app.connect() as db:
        documents = []
        for year, (ident, page) in REPORTS.items():
            download = f'https://drive.google.com/uc?export=download&id={ident}'
            url = f'https://drive.google.com/file/d/{ident}/view'
            body, _, digest = fetch(db, 'A01', download, 10)
            groups = extract_groups(year, extract_pdf(body))
            documents.append((year, page, url, digest, groups))
        for year, page, url, digest, groups in documents:
            db.execute("DELETE FROM registros WHERE fonte_id='A01' AND id LIKE ?", (f'A01-perfil-{year}-%',))
            for group in groups:
                for index, (category, value) in enumerate([*group['categorias'], ('Total', group['total'])]):
                    app.put_record(db, {'id': f'A01-perfil-{year}-{group["id"]}-{index}', 'fonte_id': 'A01',
                        'recurso_url': url, 'titulo': f'Perfil por sexo/gênero — {group["nome"]} · {category} · {year}',
                        'descricao': group['evidencia'], 'ambiente': 'real', 'tipo': 'estatistica',
                        'tema': 'Perfil em registros institucionais', 'ano': year, 'precisao': 'pais',
                        'valor': value, 'unidade': group['unidade'],
                        'metadados': {'snapshot_sha256': digest, 'significado_ano': 'ano_referencia_documental',
                            'perfil_institucional': True, 'instituicao': group['nome'], 'grupo_perfil': group['id'],
                            'tabela': 'Texto do relatório nacional',
                            'observacao': {'categoria': category, 'pagina': page, 'total': category == 'Total'},
                            'trecho_fonte': group['evidencia'], 'limite': group['limite'],
                            'nao_somar_total_com_componentes': True}})
            resource(db, 'A01', url, f'Relatório nacional sobre tráfico de pessoas — Dados {year}', 'pdf_examinado')
            db.execute('INSERT INTO coletas(fonte_id,inicio,fim,situacao,mensagem,linhas) VALUES (?,?,?,?,?,?)',
                ('A01', app.now(), app.now(), 'extraido_parcialmente',
                 f'Perfis do Disque 100 e SUS do relatório de {year}; página {page}; SHA256 {digest}',
                 sum(len(g['categorias']) + 1 for g in groups)))
    print('Perfis de 2024 e 2025 importados por instituição; confira as limitações das fontes.')
