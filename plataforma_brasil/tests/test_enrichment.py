from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from documents import Article
import enrichment as enrich


def table_line(number, theme, when, where, audience, total):
    return f'{number:<6}{theme:<48}{when:<24}{where:<32}{audience:<30}{total}'


class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(app, 'DATA', Path(self.temp.name))
        self.patch.start()
        app.init_db()
        with app.connect() as db:
            db.execute('INSERT INTO localidades VALUES (?,?,?,?)', ('3518800', 'Guarulhos', 'SP', 'guarulhos'))

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_publication_reference_and_updated_dates_are_separate(self):
        article = Article()
        article.feed('<span property="rnews:datePublished">11/09/2023 17h57</span><meta property="article:modified_time" content="2026-07-21T17:16:00"><h1>Dados e estatísticas</h1><p>O Relatório Nacional — Dados 2025 reúne informações sobre o Brasil e respostas institucionais.</p>')
        result = enrich.temporal_metadata(article, 'https://example.org')
        self.assertEqual(result['ano'], 2023)
        self.assertEqual(result['metadados']['data_publicacao']['valor'], '2023-09-11')
        self.assertEqual(result['metadados']['data_atualizacao']['valor'], '2026-07-21')
        self.assertEqual(result['metadados']['periodos_referencia'][0]['inicio'], 2025)

    def test_govbr_visible_dates_with_nested_spans(self):
        article = Article()
        article.feed('<span class="documentPublished">Publicado em <span class="value">11/09/2023 17h57</span></span><span class="documentModified">Atualizado em <span class="value">21/07/2026 17h16</span></span>')
        result = enrich.temporal_metadata(article, 'https://www.gov.br/report')
        self.assertEqual(result['metadados']['data_publicacao']['valor'], '2023-09-11')
        self.assertEqual(result['metadados']['data_atualizacao']['valor'], '2026-07-21')

    def test_dateline_is_not_foundation_or_legal_year(self):
        article = Article()
        article.feed('<p>Brasília, 4 de julho de 2025 - Dados publicados pela instituição brasileira.</p><p>Fundada em 2005, atua desde 2006. A Lei 13.344/2016 é uma referência histórica da instituição.</p>')
        result = enrich.temporal_metadata(article, 'https://example.org')
        self.assertEqual(result['ano'], 2025)
        self.assertNotIn('periodos_referencia', result['metadados'])

    def test_api_example_does_not_become_reference_period(self):
        article = Article()
        article.feed('<p>For example, the following is a call for 2006 data on the GDP of Brazil.</p>')
        self.assertIsNone(enrich.temporal_metadata(article, 'https://example.org')['ano'])

    def test_pdf_exercise_and_institution_location_have_evidence(self):
        text = 'Capa\fRELATÓRIO ANUAL DE DADOS\nUnidade da Federação: MUNICÍPIO DE GUARULHOS-SP\nDados referentes ao\n     20 24\nEXERCÍCIO de:'
        reference = enrich.pdf_reference(text)
        self.assertEqual(reference['inicio'], 2024)
        self.assertEqual(reference['pagina'], 2)
        with app.connect() as db:
            location = enrich.pdf_territory(text, db)
            self.assertEqual(location['municipio_ibge'], '3518800')
            state = enrich.pdf_territory('Unidade da Federação: São Paulo-SP\n', db)
            self.assertEqual(state['precisao'], 'uf')
            self.assertNotIn('municipio_ibge', state)

    def test_national_report_period_precedes_repealed_law_year(self):
        text = 'RELATÓRIO NACIONAL\nSOBRE TRÁFICO DE PESSOAS:\nDADOS 2021 A 2023\fDados referentes aos arts. 231 e 231-A\nrevogados pela posterior Lei 13.344/2016'
        reference = enrich.pdf_reference(text)
        self.assertEqual((reference['inicio'], reference['fim']), (2021, 2023))
        self.assertEqual(reference['pagina'], 1)
        self.assertIsNone(enrich.pdf_reference('Dados referentes aos arts. 231 e 231-A revogados pela Lei 13.344/2016'))

    def test_training_rows_preserve_zero_and_never_cross_rows(self):
        text = '14. REALIZAÇÃO DE CAPACITAÇÕES E SENSIBILIZAÇÕES\n' + table_line(1, 'Orientação', '29-07 A 08-08', 'AEROPORTO', 'POPULAÇÃO AFEGÃ', 200) + '\n\n' + table_line(2, 'Capacitação', '01/08/2024', 'Sala pública', 'Equipe', 0) + '\n\n3\n\n'
        rows = enrich.training_rows(text)
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['participantes'] for r in rows], [200, 0])
        self.assertEqual(rows[0]['publico'], 'POPULAÇÃO AFEGÃ')
        self.assertNotIn('Capacitação', rows[0]['evidencia'])
        self.assertEqual(enrich.training_rows('14. REALIZAÇÃO DE CAPACITAÇÕES\n\n1\n2\nTOTAL\n'), [])

    def test_victim_table_preserves_explicit_zero_and_separates_total(self):
        text = 'Capa\fMONITORAMENTO DOS CASOS\n1-\u200b QUANTIDADE DE VÍTIMAS ATENDIDAS\nRemoção de órgãos, tecidos ou partes do corpo       0\nTrabalho em condições análogas à de escravo        37\nQualquer tipo de servidão\nAdoção ilegal        2\nTOTAL          39\n'
        rows = enrich.victim_rows(text)
        self.assertEqual([r['valor'] for r in rows], [0, 37, 2, 39])
        self.assertTrue(rows[-1]['total'])
        self.assertTrue(all(r['pagina'] == 2 for r in rows))
        self.assertEqual(enrich.victim_rows('1- QUANTIDADE DE VÍTIMAS ATENDIDAS\nTOTAL\n'), [])

    def test_pdf_import_is_idempotent_and_keeps_participant_unit(self):
        text = 'Capa\fUnidade da Federação: MUNICÍPIO DE GUARULHOS-SP\nDados referentes ao\n2024\nEXERCÍCIO de:\f14. REALIZAÇÃO DE CAPACITAÇÕES E SENSIBILIZAÇÕES\n' + table_line(1, 'Orientações', '29-07 A 08-08', 'Aeroporto', 'Público A', 200) + '\n'
        with app.connect() as db:
            source = next(s for s in app.get_sources(db) if s['id'] == 'A21')
            resource = {'titulo': 'Relatório de Dados', 'url': 'https://www.gov.br/exemplo.pdf'}
            for _ in range(2):
                enrich.save_pdf(db, source, resource, b'%PDF-fixture', resource['url'], text)
            records = app.query_records(db, {})
            self.assertEqual(len(records), 2)
            observation = next(r for r in records if r['tipo'] == 'estatistica')
            self.assertEqual(observation['valor'], 200)
            self.assertEqual(observation['unidade'], 'participantes_de_atividade_reportada')
            self.assertEqual(observation['metadados']['referencia_territorial'], 'unidade_informante')
            self.assertIsNone(observation['latitude'])
            self.assertEqual(observation['metadados']['atividade']['pagina'], 3)

    def test_404_recovers_known_mjsp_move_but_403_is_not_bypassed(self):
        url = 'https://www.gov.br/mj/' + enrich.OLD_NETP + 'relatorios-netps-2024/test.pdf'
        class Response(io.BytesIO):
            headers = {'Content-Type': 'application/pdf'}
            def geturl(self):
                return url.replace(enrich.OLD_NETP, enrich.NEW_NETP)
        with patch('enrichment.urlopen', side_effect=[HTTPError(url, 404, '', {}, None), Response(b'%PDF-fixture')]) as request:
            body, mime, resolved = enrich.fetch_link(url)
            self.assertIn(enrich.NEW_NETP, resolved)
            self.assertEqual(body, b'%PDF-fixture')
            self.assertEqual(request.call_count, 2)
        with patch('enrichment.urlopen', side_effect=HTTPError(url, 403, '', {}, None)) as request:
            with self.assertRaises(HTTPError):
                enrich.fetch_link(url)
            self.assertEqual(request.call_count, 1)

    def test_period_filter_and_availability_do_not_turn_missing_into_zero(self):
        with app.connect() as db:
            app.put_record(db, {'id': 'period', 'fonte_id': 'A01', 'recurso_url': 'https://example.org/report',
                                'titulo': 'Relatório', 'descricao': 'Fixture', 'ambiente': 'real', 'tipo': 'documento', 'tema': 'Dados oficiais',
                                'metadados': {'periodos_referencia': [{'inicio': 2021, 'fim': 2023}]}})
            rows = app.query_records(db, {'ano': ['2022']})
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]['valor'])
            self.assertEqual(rows[0]['disponibilidade']['valor']['situacao'], 'nao_aplicavel')
            self.assertEqual(rows[0]['disponibilidade']['ano']['situacao'], 'disponivel_como_periodo')
            self.assertEqual(rows[0]['disponibilidade']['data_publicacao']['situacao'], 'nao_extraido')


if __name__ == '__main__':
    unittest.main()
