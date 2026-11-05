from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from coverage import overview
from enrichment import save_pdf, OLD_NETP, NEW_NETP
from tables import national_rows, campaign_rows, employment_motivation_rows


COVER = 'RELATÓRIO NACIONAL SOBRE TRÁFICO DE PESSOAS: DADOS 2021 A 2023\f'
TABLE = '''Tabela 10. Denúncias recebidas no Disque 100
Tráfico Interno
Ano  Remoção de órgãos  Trabalho escravo  Servidão  Adoção ilegal  Exploração sexual  Total
2021   1   1   0   6   3   11
2022   0   0   0   2   8   10
Tráfico Internacional
2021   1   3   0   7   6   17
2023   0   1   0   0   0   99
Total  1   5   0   7   7   20
Fonte: Disque 100
'''


class TableTests(unittest.TestCase):
    def test_national_rows_distinguish_scope_and_reject_inconsistent_total(self):
        rows = national_rows(COVER + TABLE)
        self.assertEqual(len(rows), 18)
        self.assertEqual([r['valor'] for r in rows if r['total']], [11, 10, 17])
        self.assertEqual(rows[-1]['recorte'], 'Internacional')
        self.assertEqual(rows[2]['valor'], 0)
        self.assertEqual(rows[0]['pagina'], 2)
        self.assertEqual(national_rows(TABLE), [])
        self.assertEqual(national_rows(COVER.replace('2023', '2024') + TABLE), [])

    def test_mpf_categories_are_not_aggregated_or_confused_with_codes(self):
        rows = national_rows(COVER + '''Tabela 8. Processos judiciais autuados no Ministério Público Federal
Assunto   2021  2022  2023
Tráfico Interno de Pessoas (5856)75 - Art. 231-A    13    4    5
Total    17    22    36
Fonte: MPF''')
        self.assertEqual([r['valor'] for r in rows], [13, 4, 5])
        self.assertEqual([r['ano'] for r in rows], [2021, 2022, 2023])

    def test_campaign_empty_cells_and_checkbox_are_not_counts(self):
        rows = campaign_rows('13.1 O que foi produzido?\nMaterial Produzido   Sim   Não   Quant.\n01   Folders   X   1.000\n02   Cartilhas   X\n03   Cartazes   X   0\n')
        self.assertEqual([r['valor'] for r in rows], [1000, 0])

    def test_employment_motivation_requires_explicit_complete_consistent_row(self):
        header = '10- MOTIVAÇÕES PARA MIGRAR\nRemoção de órgãos   Trabalho em condições   Qualquer tipo   Adoção   Exploração\n                                Total\n                                         de servidão\n'
        rows = employment_motivation_rows('Capa\f' + header + 'Oferta de trabalho    0  37  0  0  2  39\n')
        self.assertEqual([r['valor'] for r in rows], [0, 37, 0, 0, 2, 39])
        self.assertEqual(rows[-1]['pagina'], 2)
        self.assertEqual(rows[-1]['categoria'], 'Total')
        self.assertEqual(employment_motivation_rows(header + 'Oferta de trabalho   37   37\n'), [])
        self.assertEqual(employment_motivation_rows(header + 'Oferta de trabalho   0 37 0 0 2 40\n'), [])
        self.assertEqual(employment_motivation_rows(header + 'Oferta de trabalho\n0 37 0 0 2 39\n'), [])

    def test_demographic_table_continuation_and_partial_year(self):
        rows = national_rows(COVER + '''Tabela 1. Gênero de assistidos pela DPU
Assistidos Brasileiros
Ano   Mulheres   %   Homens   %   Total
2023*   9   25%   27   75%   36
\fAssistidos de Outras Nacionalidades
Ano   Mulheres   %   Homens   %   Total
2023*   5   71%   2   29%   7
Fonte: DPU
Tabela 2. Gênero de possíveis vítimas identificadas nos CREAS
Ano   Mulheres   %   Homens   %   Total
2021   200   36%   348   64%   548
Fonte: MDS''')
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[3]['recorte'], 'Outras nacionalidades')
        self.assertTrue(rows[3]['parcial'])
        self.assertIn('20/11/2023', rows[3]['nota'])
        self.assertEqual(rows[-1]['valor'], 548)
        self.assertEqual(rows[-1]['recorte'], 'Brasil')

    def test_reprocessing_and_coverage_deduplicate_migrated_urls(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, 'DATA', Path(temp)):
            app.init_db()
            with app.connect() as db:
                source = next(s for s in app.get_sources(db) if s['id'] == 'A01')
                old = 'https://www.gov.br/mj/' + OLD_NETP + 'relatorio.pdf'
                new = old.replace(OLD_NETP, NEW_NETP)
                db.execute('INSERT INTO recursos VALUES (?,?,?,?,?,?)', ('old', 'A01', old, 'Relatório', 'pdf', app.now()))
                for _ in range(2):
                    save_pdf(db, source, {'url': old, 'titulo': 'Relatório'}, b'%PDF-fixture', new, COVER + TABLE)
                rows = app.query_records(db, {})
                self.assertEqual(len(rows), 19)
                self.assertTrue(all(r['precisao'] == 'pais' for r in rows))
                self.assertEqual(len(app.query_records(db, {'ano': ['2022'], 'tipo': ['estatistica']})), 6)
                data = overview(db)
                item = next(s for s in data['fontes'] if s['id'] == 'A01')
                self.assertEqual(item['pdfs'], 1)
                self.assertEqual(item['pdfs_examinados'], 1)
                self.assertEqual(item['pdfs_pendentes'], 0)
                self.assertEqual(item['estatisticas'], 18)
                self.assertNotIn('valor', item['campos_pendentes'])
                self.assertEqual(item['arquivos'][0]['situacao'], 'examinado_parcialmente')
                self.assertEqual(item['arquivos'][0]['tabelas_extraidas'], ['10'])
                self.assertEqual(len(data['indicadores']), 34)
                save_pdf(db, source, {'url': 'https://www.gov.br/copy_of_relatorio.pdf', 'titulo': 'Cópia'}, b'%PDF-fixture', 'https://www.gov.br/copy_of_relatorio.pdf', COVER + TABLE)
                self.assertEqual(len(app.query_records(db, {})), 19)
                metadata = next(r['metadados'] for r in app.query_records(db, {}) if r['tipo'] == 'documento')
                self.assertIn(old, metadata['urls_alternativas'])
                self.assertIn('https://www.gov.br/copy_of_relatorio.pdf', metadata['urls_alternativas'])


if __name__ == '__main__':
    unittest.main()
