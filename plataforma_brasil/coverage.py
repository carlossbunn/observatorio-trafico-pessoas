"""Cobertura real da base; não confunde catálogo, descoberta e extração."""
from collections import Counter

import app


def canonical_url(url):
    from enrichment import OLD_NETP, NEW_NETP
    return url.replace(OLD_NETP, NEW_NETP).split('#')[0]


def overview(db):
    records = app.query_records(db, {})
    resources = [dict(r) for r in db.execute('SELECT * FROM recursos')]
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='investigacoes' AND type='table'").fetchone()
    audits = [dict(r) for r in db.execute('SELECT * FROM investigacoes')] if exists else []
    sources = []
    for source in app.get_sources(db):
        rows = [r for r in records if r['fonte_id'] == source['id']]
        documents = [r for r in rows if r['tipo'] == 'documento']
        stats = [r for r in rows if r['tipo'] == 'estatistica']
        pdfs = {}
        for resource in resources:
            if resource['fonte_id'] == source['id'] and resource['formato'] in ('pdf', 'pdf_examinado'):
                key = canonical_url(resource['url'])
                previous = pdfs.get(key)
                if not previous or resource['formato'] == 'pdf_examinado':
                    pdfs[key] = resource
        source_audits = {canonical_url(a['url']): a for a in audits if a['fonte_id'] == source['id']}
        files = []
        for key, resource in sorted(pdfs.items()):
            audit = source_audits.get(key)
            doc = next((r for r in documents if key in {canonical_url(url) for url in [r['recurso_url'], r['metadados'].get('url_original', ''), *r['metadados'].get('urls_alternativas', [])]}), None)
            extracted = doc is not None or resource['formato'] == 'pdf_examinado'
            files.append({'titulo': resource['titulo'], 'url': resource['url'],
                          'situacao': 'examinado_parcialmente' if extracted else audit['situacao'] if audit else 'nao_examinado',
                          'detalhe': doc['metadados'].get('escopo_extrator', 'Extração documental parcial') if doc else audit['detalhe'] if audit else 'Download e extração pendentes; pertinência ao Brasil ainda deve ser verificada.',
                          'registros_extraidos': sum(r['metadados'].get('documento_id') == doc['id'] for r in stats) if doc else 0,
                          'tabelas_extraidas': doc['metadados'].get('tabelas_com_celulas_extraidas', []) if doc else []})
        years = set()
        for row in rows:
            if row['ano']:
                years.add(row['ano'])
            for period in row['metadados'].get('periodos_referencia', []):
                years.update(range(period['inicio'], period['fim'] + 1))
        missing = Counter(field for row in rows for field, info in row['disponibilidade'].items()
                          if info['situacao'] in ('nao_extraido', 'nao_localizado_na_parte_examinada'))
        examined = sum(f['situacao'] == 'examinado_parcialmente' for f in files)
        pending = len(files) - examined
        issues = []
        if not rows:
            issues.append('Sem registros importados')
        elif not stats:
            issues.append('Conteúdo documental/contextual; sem série estatística importada')
        if pending:
            issues.append(f'{pending} PDFs ainda não examinados com sucesso')
        if examined:
            issues.append('Extração de tabelas parcial; outras tabelas e formatos podem permanecer pendentes')
        if any(r['metadados'].get('cobertura_anual_completa') is False for r in rows):
            issues.append('Período parcial; não equivale a cobertura anual completa')
        sources.append({'id': source['id'], 'nome': source['nome'], 'escopo': source['escopo'],
                        'registros': len(rows), 'estatisticas': len(stats), 'documentos': len(documents),
                        'anos': sorted(years), 'unidades': sorted({r['unidade'] for r in stats}),
                        'ufs': sorted({r['uf'] for r in rows if r['uf']}),
                        'municipios': len({r['municipio_ibge'] for r in rows if r['municipio_ibge']}),
                        'pdfs': len(files), 'pdfs_examinados': examined, 'pdfs_pendentes': pending,
                        'campos_pendentes': dict(missing), 'pendencias': issues, 'arquivos': files,
                        'ultima_coleta': source['ultima_coleta'],
                        'situacao': 'fora_do_recorte' if source['escopo'] == 'fora_do_recorte' else 'dados_parciais' if stats else 'somente_documental' if rows else 'sem_dados'})
    indicators = []
    for indicator in app.get_catalog(db).get('indicadores', []):
        linked = [r for r in records if indicator['ID'] in r['indicadores']]
        stat_count = sum(r['tipo'] == 'estatistica' for r in linked)
        indicators.append({'id': indicator['ID'], 'nome': indicator['Indicador em português'],
                           'registros': len(linked), 'estatisticas': stat_count,
                           'fontes_com_registros': sorted({r['fonte_id'] for r in linked}),
                           'fontes_previstas': [s.strip() for s in indicator.get('Fontes IDs', '').split(';') if s.strip()],
                           'situacao': 'com_observacoes_vinculadas' if stat_count else 'somente_documental' if linked else 'sem_registros_vinculados'})
    return {'gerado_em': app.now(), 'resumo': {'fontes': len(sources), 'fontes_com_registros': sum(s['registros'] > 0 for s in sources),
            'fontes_com_estatisticas': sum(s['estatisticas'] > 0 for s in sources),
            'pdfs': sum(s['pdfs'] for s in sources), 'pdfs_examinados': sum(s['pdfs_examinados'] for s in sources),
            'pdfs_pendentes': sum(s['pdfs_pendentes'] for s in sources),
            'indicadores': len(indicators), 'indicadores_com_registros': sum(i['registros'] > 0 for i in indicators)},
            'fontes': sources, 'indicadores': indicators,
            'nota': 'Anos incluem publicação e períodos de referência; não comprovam série anual completa. PDFs deduplicados por URL, incluindo a migração conhecida do MJSP. Examinado não significa extração integral.'}
