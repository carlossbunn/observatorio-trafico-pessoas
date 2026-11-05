import csv
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import mte


def document(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=['ID', 'Ano da ação fiscal', 'UF', 'Trabalhadores envolvidos', 'Inclusão no Cadastro de Empregadores'], delimiter=';')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('cp1252')


class MteTests(unittest.TestCase):
    def test_counts_rows_not_workers_and_audits_missing_uf(self):
        rows = [{'ID': '1', 'Ano da ação fiscal': '2024', 'UF': 'SP', 'Trabalhadores envolvidos': '100'},
                {'ID': '2', 'Ano da ação fiscal': '2024', 'UF': 'SP', 'Trabalhadores envolvidos': '5'},
                {'ID': '3', 'Ano da ação fiscal': '2023', 'UF': '', 'Trabalhadores envolvidos': '3'}]
        counts, audit = mte.aggregate(document(rows))
        self.assertEqual(counts[(2024, 'SP')], 2)
        self.assertEqual(audit, {'linhas_total': 3, 'linhas_excluidas_ano_ou_uf': 1})
        with self.assertRaises(ValueError):
            mte.aggregate(document([rows[0], rows[0]]))
        with self.assertRaises(ValueError):
            mte.aggregate(b'coluna;inesperada\n1;2\n')

    def test_replacement_is_idempotent_and_failure_preserves_existing(self):
        rows = [{'ID': '1', 'Ano da ação fiscal': '2024', 'UF': 'SP', 'Trabalhadores envolvidos': '50'}]
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'DATA', Path(folder)):
            app.init_db()
            with patch('mte.fetch', return_value=(document(rows), 'text/csv', 'checksum')):
                mte.collect()
                mte.collect()
            with app.connect() as db:
                records = app.query_records(db, {'fonte_id': ['A04'], 'tipo': ['estatistica']})
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]['valor'], 1)
                self.assertFalse(records[0]['metadados']['cobertura_anual_completa'])
                self.assertEqual(records[0]['unidade'], 'linhas_cadastro_vigente_mte')
            with patch('mte.fetch', return_value=(b'invalido', 'text/csv', 'bad')):
                with self.assertRaises(ValueError):
                    mte.collect()
            with app.connect() as db:
                self.assertEqual(len(app.query_records(db, {'fonte_id': ['A04'], 'tipo': ['estatistica']})), 1)
                self.assertEqual(db.execute('select situacao from coletas order by id desc').fetchone()[0], 'falhou')


if __name__ == '__main__':
    unittest.main()
