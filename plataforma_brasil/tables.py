"""Extratores conservadores de tabelas: somente células explícitas com esquema conhecido."""
import re

from collectors import normalize


PURPOSES = ['Remoção de órgãos', 'Trabalho escravo', 'Servidão', 'Adoção ilegal', 'Exploração sexual', 'Total']
NATIONAL = {
    1: ('Assistidos pela DPU em possível situação de tráfico', 'assistidos_dpu_possivel_trafico', 'DPU'),
    2: ('Possíveis vítimas identificadas nos CREAS', 'possiveis_vitimas_identificadas_creas', 'MDS/CREAS'),
    3: ('Perfil de vítimas segundo denúncias ao Ligue 180 e Disque 100', 'vitimas_reportadas_em_denuncias_180_100', 'Ligue 180 e Disque 100'),
    4: ('Raça/cor de possíveis vítimas segundo denúncias', 'possiveis_vitimas_reportadas_por_raca_cor', 'Ligue 180 e Disque 100'),
    5: ('Inquéritos da Polícia Federal', 'inqueritos_registrados_pf', 'Polícia Federal'),
    6: ('Processos criminais na Justiça Federal', 'processos_criminais_justica_federal', 'CNJ'),
    7: ('Processos criminais na Justiça Estadual', 'processos_criminais_justica_estadual', 'CNJ'),
    8: ('Processos autuados no MPF — tráfico interno', 'processos_autuados_mpf', 'MPF'),
    9: ('Processos autuados no MPF — tráfico internacional', 'processos_autuados_mpf', 'MPF'),
    10: ('Denúncias recebidas no Disque 100', 'denuncias_recebidas_disque100', 'Disque 100'),
    11: ('Presos por tráfico de pessoas para exploração sexual', 'presos_tipificacoes_trafico_exploracao_sexual', 'DEPEN'),
}


def national_rows(text):
    """Esquema do relatório nacional 2021–2023; gráficos e totais plurianuais são excluídos."""
    if not re.search(r'relatorio\s+nacional.{0,180}?dados\s*2021\s*[a–—-]\s*2023', normalize(text[:6000]), re.S):
        return []
    result = []
    for page_no, page in enumerate(text.split('\f'), 1):
        headings = list(re.finditer(r'Tabela\s+(\d+)\.', page, re.I))
        continuation = 'assistidos de outras nacionalidades' in normalize(page[:400])
        if continuation:
            headings.insert(0, re.match(r'', page))
        for index, heading in enumerate(headings):
            number = 1 if continuation and not heading.lastindex else int(heading[1])
            if number not in NATIONAL:
                continue
            block = page[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(page)]
            block = re.split(r'Fonte\s*:', block, maxsplit=1, flags=re.I)[0]
            title, unit, institution = NATIONAL[number]
            if number in (1, 2, 3, 4, 11):
                normalized = normalize(block)
                expected = ('mulheres', 'homens', 'total') if number in (1, 2, 3, 11) else ('branca', 'preta', 'parda', 'amarela', 'indigena', 'total')
                if not all(word in normalized for word in expected):
                    continue
                for line in block.splitlines():
                    match = re.fullmatch(r'\s*(202[123])(\*)?\s+(.+?)\s*', line)
                    if not match:
                        continue
                    cells = match[3].split()
                    if number in (1, 2):
                        if len(cells) != 5 or not all(re.fullmatch(r'\d+%', cells[i]) for i in (1, 3)):
                            continue
                        cells = [cells[i] for i in (0, 2, 4)]
                        categories = ['Mulheres', 'Homens', 'Total']
                    elif number == 3:
                        if len(cells) != 9 or not all(re.fullmatch(r'\d+%', cells[i]) for i in (1, 3, 5, 7)):
                            continue
                        cells = [cells[i] for i in (0, 2, 4, 6, 8)]
                        categories = ['Mulheres', 'Homens', 'Crianças gênero feminino', 'Crianças gênero masculino', 'Total']
                    elif number == 4:
                        categories = ['Branca', 'Preta', 'Parda', 'Amarela', 'Indígena', 'Total']
                    else:
                        categories = ['Interno · Mulheres', 'Interno · Homens', 'Internacional · Mulheres', 'Internacional · Homens', 'Total']
                    if len(cells) != len(categories) or not all(re.fullmatch(r'\d+', cell) for cell in cells):
                        continue
                    values = list(map(int, cells))
                    if sum(values[:-1]) != values[-1]:
                        continue
                    partial = bool(match[2])
                    note = ('Dados de 2023 até 20/11/2023, conforme nota da tabela.' if number == 1 else
                            'Dados de 2023 até 03/11/2023, conforme nota do relatório.' if number == 2 else
                            'Primeiro semestre de 2023; tipificações dos arts. 231 e 231-A, conforme notas da tabela.' if number == 11 else
                            'Ano assinalado com asterisco na fonte; conferir nota e abrangência na publicação.') if partial else ''
                    for category, value in zip(categories, values):
                        result.append(dict(tabela=number, titulo=title, unidade=unit, instituicao=institution,
                                           categoria=category, ano=int(match[1]), valor=value, pagina=page_no,
                                           evidencia=line.strip(), total=category == 'Total', parcial=partial, nota=note,
                                           recorte=('Outras nacionalidades' if continuation and not heading.lastindex else 'Brasileiros') if number == 1 else 'Brasil'))
                continue
            if number in (8, 9):
                if not re.search(r'2021\s+2022\s+2023', block):
                    continue
                for line in block.splitlines():
                    match = re.fullmatch(r'\s*(\S.*?)\s{2,}(\d+)\s+(\d+)\s+(\d+)\s*', line)
                    if not match or not re.search(r'\(\d{4,5}\)', match[1]):
                        continue
                    for year, value in zip((2021, 2022, 2023), match.groups()[1:]):
                        result.append(dict(tabela=number, titulo=title, unidade=unit, instituicao=institution,
                                           categoria=match[1], ano=year, valor=int(value), pagina=page_no,
                                           evidencia=line.strip(), total=False,
                                           recorte='Interno' if number == 8 else 'Internacional'))
                continue
            # Confirma a presença das seis colunas antes de aceitar linhas anuais.
            header = normalize(block[:block.find('2021')])
            if not all(word in header for word in ('remocao', 'trabalho', 'servidao', 'adocao', 'sexual', 'total')):
                continue
            scope = 'Todas as finalidades'
            for line in block.splitlines():
                scope_match = re.fullmatch(r'\s*Tráfico\s+(Interno|Internacional)\s*', line, re.I)
                if scope_match:
                    scope = scope_match[1].capitalize()
                match = re.fullmatch(r'\s*(202[123])\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*', line)
                if not match:
                    continue
                values = list(map(int, match.groups()[1:]))
                if sum(values[:-1]) != values[-1]:
                    continue
                for category, value in zip(PURPOSES, values):
                    result.append(dict(tabela=number, titulo=title, unidade=unit, instituicao=institution,
                                       categoria=category, ano=int(match[1]), valor=value, pagina=page_no,
                                       evidencia=line.strip(), total=category == 'Total', recorte=scope))
    return result


def campaign_rows(text):
    result = []
    for page_no, page in enumerate(text.split('\f'), 1):
        if not re.search(r'13\.1\s', page) or 'material' not in normalize(page):
            continue
        # Não interpreta X como quantidade nem espaços vazios como zero.
        for line in page.splitlines():
            match = re.fullmatch(r'\s*(\d{1,2})\s{2,}(Folders|Cartilhas|Cartazes|Faixas|Banners|Vídeos)\s{2,}X\s{2,}(\d+(?:\.\d{3})*)\s*', line, re.I)
            if match:
                result.append(dict(linha=int(match[1]), categoria=match[2], valor=int(match[3].replace('.', '')),
                                   pagina=page_no, evidencia=line.strip()))
    return result


def employment_motivation_rows(text):
    """Seção 10 NETP: extrai apenas linha completa e somável, não preenche células vazias."""
    result = []
    for page_no, page in enumerate(text.split('\f'), 1):
        cleaned = normalize(page.replace('\u200b', ''))
        if not re.search(r'\b10\s*[.\-–—]\s*motivacoes para migrar', cleaned):
            continue
        header = cleaned.split('oferta de trabalho', 1)[0]
        words = ('remocao de orgaos', 'trabalho em condicoes', 'servidao', 'adocao', 'exploracao', 'total')
        if not all(word in header for word in words):
            continue
        first = next((line for line in header.splitlines() if all(word in line for word in ('remocao de orgaos', 'trabalho em condicoes', 'qualquer tipo', 'adocao', 'exploracao'))), '')
        if not first or [first.find(word) for word in ('remocao de orgaos', 'trabalho em condicoes', 'qualquer tipo', 'adocao', 'exploracao')] != sorted(first.find(word) for word in ('remocao de orgaos', 'trabalho em condicoes', 'qualquer tipo', 'adocao', 'exploracao')):
            continue
        matches = re.findall(r'^[ \t]*(oferta de trabalho[ \t]{2,}(?:\d+[ \t]+){5}\d+)[ \t]*$', cleaned, re.M)
        if len(matches) != 1:
            continue
        evidence = matches[0].strip()
        values = [int(x) for x in re.findall(r'\d+', evidence)]
        if len(values) != 6 or sum(values[:-1]) != values[-1]:
            continue
        for category, value in zip(PURPOSES, values):
            result.append({'categoria': category, 'valor': value, 'pagina': page_no,
                           'evidencia': evidence, 'total': category == 'Total'})
    return result
