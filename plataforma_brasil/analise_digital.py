"""Dados de perfil e território como contexto, sem atribuir canal digital a registros gerais."""
import app


def overview(db):
    records = app.query_records(db, {})
    profiles = [r for r in records if r['fonte_id'] == 'A01' and r['tipo'] == 'estatistica'
                and r['metadados'].get('tabela') == 3 and r['ano'] in (2021, 2022, 2023)]
    recent_profiles = [r for r in records if r['fonte_id'] == 'A01' and r['tipo'] == 'estatistica'
                       and r['metadados'].get('perfil_institucional') is True]
    locations = [r for r in records if r['fonte_id'] == 'A02' and r['tipo'] == 'estatistica'
                 and r['municipio_ibge'] and r['unidade'] == 'registros_administrativos_distintos_na_celula']
    modalities = [r for r in records if r['fonte_id'] == 'A01' and r['tipo'] == 'estatistica'
                  and r['metadados'].get('tabela') == 5 and r['metadados'].get('observacao', {}).get('categoria') != 'Total']
    employment = [r for r in records if r['fonte_id'] == 'A21' and r['unidade'] == 'pessoas_atendidas_oferta_trabalho_motivo_migracao']
    profiles.sort(key=lambda r: (r['ano'], r['titulo']))
    locations.sort(key=lambda r: (r['metadados'].get('periodo', ''), r['municipio']))
    return {'perfil_nacional': profiles, 'perfil_institucional_recente': recent_profiles, 'localidades_contexto': locations, 'modalidades_contexto': modalities, 'motivacoes_trabalho': employment,
            'periodos': sorted({r['metadados'].get('periodo') for r in locations if r['metadados'].get('periodo')}, reverse=True),
            'nota': 'Perfil e localização são dados gerais de tráfico, não estão vinculados a ofertas, internet ou entre si. Valores são registros administrativos na célula, não vítimas ou risco.'}
