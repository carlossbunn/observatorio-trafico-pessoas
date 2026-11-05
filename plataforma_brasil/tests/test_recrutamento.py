import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import recrutamento


class RecruitmentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(app, 'DATA', Path(self.temp.name))
        self.patch.start()
        app.init_db()
        self.file = Path(self.temp.name) / 'input.json'
        self.row = dict(id='example', titulo='Alerta', descricao='Exemplo', classificacao='alerta_geral',
                        recorte='brasil', pais='Brasil', fonte_id='A22', fonte_nome='Fonte',
                        fonte_url='https://example.org/report', trecho_evidencia='Trecho', relacao_brasil='Brasil',
                        limites='Não é oferta individual', sinais=['Contato privado'], data_publicacao='2024-01-02')

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def save(self, rows):
        self.file.write_text(json.dumps(rows), encoding='utf-8')
        recrutamento.import_file(self.file)

    def test_filters_and_idempotent_update(self):
        self.save([self.row])
        self.save([{**self.row, 'titulo': 'Atualizado'}])
        with app.connect() as db:
            self.assertEqual(recrutamento.query(db, {'classificacao': ['alerta_geral'], 'ano': ['2024']})['total'], 1)
            self.assertEqual(recrutamento.query(db, {'recorte': ['internacional']})['total'], 0)
            self.assertEqual(recrutamento.query(db, {'q': ['atualizado']})['fichas'][0]['titulo'], 'Atualizado')

    def test_invalid_batch_rolls_back_and_rejects_id_hijack(self):
        self.save([self.row])
        with self.assertRaises(ValueError):
            self.save([{**self.row, 'titulo': 'Mudou'}, {**self.row, 'id': 'new', 'fonte_url': 'javascript:alert(1)'}])
        with self.assertRaises(ValueError):
            self.save([{**self.row, 'fonte_url': 'https://other.example/'}])
        with app.connect() as db:
            self.assertEqual(recrutamento.query(db, {})['fichas'][0]['titulo'], 'Alerta')
        with self.assertRaises(ValueError):
            self.save([{**self.row, 'relacao_brasil': ''}])

    def test_international_does_not_require_brazil_and_no_table_is_empty(self):
        with app.connect() as db:
            self.assertEqual(recrutamento.query(db, {})['total'], 0)
        self.save([{**self.row, 'recorte': 'internacional', 'pais': 'Outro país', 'relacao_brasil': ''}])
        with app.connect() as db:
            self.assertEqual(recrutamento.query(db, {'recorte': ['internacional']})['total'], 1)


if __name__ == '__main__':
    unittest.main()
