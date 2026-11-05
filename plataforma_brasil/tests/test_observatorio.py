import csv
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import collectors
import documents


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(app, 'DATA', Path(self.temp.name))
        self.patch.start()
        app.init_db()
        with app.connect() as db:
            db.execute('INSERT INTO localidades VALUES (?,?,?,?)', ('3550308', 'São Paulo', 'SP', 'sao paulo'))
            db.execute('INSERT INTO localidades VALUES (?,?,?,?)', ('3304557', 'Rio de Janeiro', 'RJ', 'rio de janeiro'))

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def record(self, **updates):
        row = dict(id='example', fonte_id='A22', recurso_url='https://example.org/documento', titulo='Título',
                   descricao='Documento de teste, não publicado.', ambiente='ambos', tipo='documento',
                   tema='Recrutamento digital', indicadores=['M033'])
        row.update(updates)
        return row

    def test_catalog_is_complete_and_idempotent(self):
        app.init_db()
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM fontes').fetchone()[0], 59)
            catalog = app.get_catalog(db)
            self.assertEqual([len(catalog[k]) for k in ('indicadores', 'correlacoes', 'perguntas')], [34, 12, 18])
            self.assertTrue(all(i['ambientes'] for i in catalog['indicadores']))

    def test_upsert_does_not_duplicate_worlds_or_records(self):
        with app.connect() as db:
            app.put_record(db, self.record())
            app.put_record(db, self.record(titulo='Nova versão'))
            for world in ('real', 'virtual'):
                rows = app.query_records(db, {'ambiente': [world]})
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['titulo'], 'Nova versão')
            self.assertEqual(len(app.query_records(db, {})), 1)

    def test_invalid_geography_and_units_are_rejected(self):
        invalid = [dict(precisao='local_exato'), dict(latitude=-23), dict(precisao='municipio'),
                   dict(municipio_ibge='3550308', uf='RJ'), dict(tipo='estatistica'), dict(uf='XX'),
                   dict(indicadores=['M999']), dict(recurso_url='javascript:alert(1)'), dict(ambiente='falso'),
                   dict(valor=float('nan')), dict(valor=float('inf')), dict(ano=2024.5)]
        with app.connect() as db:
            for values in invalid:
                with self.subTest(values=values), self.assertRaises(ValueError):
                    app.put_record(db, self.record(**values))

    def test_foreign_record_requires_brazil_evidence(self):
        with app.connect() as db:
            with self.assertRaises(ValueError):
                app.put_record(db, self.record(origem_publicacao='Outro país'))
            app.put_record(db, self.record(origem_publicacao='Outro país', metadados={'trecho_relacao_brasil': 'Trecho documentado sobre o Brasil'}))

    def test_unknown_fields_cannot_become_sql(self):
        with app.connect() as db, self.assertRaises(ValueError):
            app.put_record(db, self.record(**{'id); DROP TABLE fontes;--': 'x'}))

    def test_map_includes_all_sources_without_inventing_observations(self):
        with app.connect() as db:
            overview = app.map_overview(db, {'ambiente': ['real']})
            self.assertEqual(len(overview['fontes']), 59)
            self.assertEqual(overview['registros'], [])
            self.assertEqual(overview['nacionais'], [])
            self.assertTrue(all(s['registros_no_filtro'] == 0 for s in overview['fontes']))

    def test_map_keeps_national_context_separate_from_local_observations(self):
        with app.connect() as db:
            app.put_record(db, self.record(id='nacional'))
            app.put_record(db, self.record(id='local', fonte_id='A02', uf='SP', municipio_ibge='3550308', municipio='São Paulo', precisao='municipio', tipo='estatistica', valor=3, unidade='registros'))
            app.put_record(db, self.record(id='outro_estado', uf='RJ', precisao='uf'))
            overview = app.map_overview(db, {'uf': ['SP'], 'ambiente': ['real']})
            self.assertEqual([r['id'] for r in overview['registros']], ['local'])
            self.assertEqual([r['id'] for r in overview['nacionais']], ['nacional'])
            self.assertEqual(len(overview['fontes']), 59)
            filtered = app.map_overview(db, {'fonte_id': ['A02'], 'uf': ['SP']})
            self.assertEqual([s['id'] for s in filtered['fontes']], ['A02'])
            self.assertEqual(filtered['registros'][0]['valor'], 3)
            self.assertEqual(filtered['nacionais'], [])

    def test_theme_filter_uses_documented_indicator_relationships(self):
        with app.connect() as db:
            app.put_record(db, self.record())
            rows = app.query_records(db, {'tema': ['Qualidade e viés']})
            self.assertEqual(len(rows), 1)
            source = next(s for s in app.map_overview(db, {'tema': ['Qualidade e viés']})['fontes'] if s['id'] == 'A22')
            self.assertIn('M033', source['indicadores'])
            self.assertEqual(source['registros_no_filtro'], 1)

    def test_document_parser_ignores_menu_and_footer_as_brazil_evidence(self):
        article = documents.Article()
        article.feed('<nav><p>' + 'Brazil menu ' * 20 + '</p></nav><main><h1>Report</h1><p>' + 'Global information without geographic reference. ' * 4 + '</p></main><footer><p>' + 'Brasil footer ' * 20 + '</p></footer>')
        self.assertEqual(documents.brazil_paragraphs(article), [])
        self.assertEqual(article.title, 'Report')

    def test_document_import_preserves_excerpt_without_inventing_counts_or_locations(self):
        article = documents.Article()
        excerpt = 'A public report explicitly describes Brazil and its institutional response. ' * 3
        article.feed('<h1>Public report</h1><p>' + excerpt + '</p>')
        result = {'body': b'fixture', 'article': article, 'paragraphs': documents.brazil_paragraphs(article)}
        with app.connect() as db:
            source = next(s for s in app.get_sources(db) if s['id'] == 'A13')
            documents.store_document(db, source, result)
            documents.store_document(db, source, result)
            rows = app.query_records(db, {})
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['tipo'], 'contexto')
            self.assertEqual(rows[0]['precisao'], 'pais')
            self.assertIsNone(rows[0]['valor'])
            self.assertIsNone(rows[0]['ano'])
            self.assertIsNone(rows[0]['latitude'])
            self.assertIn('Brazil', rows[0]['metadados']['trecho_relacao_brasil'])

    def test_restricted_sources_are_not_requested(self):
        with patch('documents.urlopen') as request:
            result = documents.download_document({'id': 'A25'}, 4)
            self.assertEqual(result['status'], 'acesso_condicionado')
            request.assert_not_called()

    def test_navigation_boilerplate_removes_only_managed_document(self):
        article = documents.Article()
        article.feed('<p>Ao compartilhar sua opinião, você nos ajuda a identificar problemas e a melhorar a navegação para você. Brasil.</p>')
        self.assertEqual(documents.brazil_paragraphs(article), [])
        with app.connect() as db:
            app.put_record(db, self.record(id='documental-A02', fonte_id='A02', situacao='extracao_documental_automatica'))
            app.put_record(db, self.record(id='dado_preservado', fonte_id='A02'))
            source = next(s for s in app.get_sources(db) if s['id'] == 'A02')
            documents.store_document(db, source, {'body': b'fixture', 'article': article, 'paragraphs': []})
            self.assertEqual([r['id'] for r in app.query_records(db, {})], ['dado_preservado'])

    def test_filters_are_bound_and_like_is_literal(self):
        with app.connect() as db:
            app.put_record(db, self.record(titulo='Valor 100%'))
            self.assertEqual(len(app.query_records(db, {'q': ['%']})), 1)
            self.assertEqual(len(app.query_records(db, {'q': ["' OR 1=1 --"]})), 0)
            self.assertEqual(len(app.query_records(db, {'indicador': ['M033']})), 1)
            self.assertEqual(len(app.query_records(db, {'indicador': ['M03']})), 0)

    def mapping(self):
        return {'id_denuncia':'id', 'data':'data', 'uf':'uf', 'municipio':'municipio', 'violacao':'violacao',
                'valores_violacao':['TRÁFICO DE PESSOAS'], 'formato_data':'%d/%m/%Y', 'periodo':'2024-S1',
                'campo_data_descricao':'Data de cadastro', 'identificador_descricao':'Protocolo conforme dicionário da fonte',
                'unidade_contagem':'denuncias_distintas_na_celula_do_recurso'}

    def csv_text(self):
        return ('id;data;uf;municipio;violacao\n'
                '1;01/01/2024;SP;São Paulo;TRÁFICO DE PESSOAS\n'
                '1;01/01/2024;SP;3550308 | SÃO PAULO;TRÁFICO DE PESSOAS\n'
                '2;02/01/2024;SP;São Paulo;TRÁFICO DE PESSOAS\n'
                '3;03/01/2024;SP;NULL;TRÁFICO DE PESSOAS\n'
                '4;03/01/2024;SP;São Paulo;OUTRA VIOLAÇÃO\n'
                '5;DATA INVALIDA;SP;São Paulo;TRÁFICO DE PESSOAS\n')

    def test_aggregation_deduplicates_and_audits_missing_not_zero(self):
        with app.connect() as db:
            groups, audit = collectors.aggregate_disque(csv.DictReader(io.StringIO(self.csv_text()), delimiter=';'), self.mapping(), db)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(next(iter(groups.values()))), 2)
        self.assertEqual(audit['linhas_excluidas_data_id_ou_local'], 2)
        self.assertEqual(audit['linhas_repetidas_na_mesma_celula'], 1)

    def test_import_replaces_same_resource_without_summing_overlaps(self):
        path = Path(self.temp.name) / 'input.csv'
        mapping_path = Path(self.temp.name) / 'map.json'
        path.write_text(self.csv_text(), encoding='utf-8')
        mapping_path.write_text(json.dumps(self.mapping()), encoding='utf-8')
        for _ in range(2):
            collectors.import_disque(path, mapping_path, 'https://www.gov.br/input.csv')
        with app.connect() as db:
            rows = app.query_records(db, {})
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['valor'], 2)
            self.assertFalse(rows[0]['metadados']['cobertura_anual_completa'])
        path.write_text('id;data;uf;municipio;violacao\n', encoding='utf-8')
        collectors.import_disque(path, mapping_path, 'https://www.gov.br/input.csv')
        with app.connect() as db:
            self.assertEqual(len(app.query_records(db, {})), 0)

    def test_failed_import_keeps_previous_version_and_logs_failure(self):
        path = Path(self.temp.name) / 'input.csv'
        mapping_path = Path(self.temp.name) / 'map.json'
        path.write_text(self.csv_text(), encoding='utf-8')
        mapping_path.write_text(json.dumps(self.mapping()), encoding='utf-8')
        collectors.import_disque(path, mapping_path, 'https://www.gov.br/input.csv')
        path.write_text('coluna_errada\nabc\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            collectors.import_disque(path, mapping_path, 'https://www.gov.br/input.csv')
        with app.connect() as db:
            self.assertEqual(len(app.query_records(db, {})), 1)
            self.assertEqual(db.execute('SELECT situacao FROM coletas ORDER BY id DESC LIMIT 1').fetchone()[0], 'falhou')

    def test_api_and_export_preserve_source_and_escape_formula(self):
        with app.connect() as db:
            app.put_record(db, self.record(titulo='=SOMETHING()', valor=None))
        server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/api/registros?ambiente=virtual') as response:
                self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
                data = json.load(response)
                self.assertEqual(data['total'], 1)
                self.assertEqual(data['registros'][0]['fonte_id'], 'A22')
            with urlopen(base + '/api/exportar.csv') as response:
                self.assertIn("'=SOMETHING()", response.read().decode('utf-8-sig'))
            for route in ('/', '/app.js', '/style.css', '/mapa.css', '/api/mapa', '/api/fontes', '/api/cobertura', '/api/analise-digital', '/api/catalogo', '/api/resumo', '/api/coletas', '/api/recursos', '/api/geografia', '/api/geografia?nivel=municipios', '/api/localidades?uf=SP', '/painel-original'):
                with self.subTest(route=route), urlopen(base + route) as response:
                    self.assertEqual(response.status, 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
