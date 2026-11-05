from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import perfil_recente
from analise_digital import overview


def report(year):
    page = perfil_recente.REPORTS[year][1]
    text = '\n'.join(group['evidencia'] for group in perfil_recente.GROUPS[year])
    return '\f' * (page - 1) + text


class PerfilRecenteTests(unittest.TestCase):
    def test_page_and_evidence_are_required(self):
        groups = perfil_recente.extract_groups(2025, report(2025))
        self.assertEqual(groups[0]['total'], 479)
        with self.assertRaises(ValueError):
            perfil_recente.extract_groups(2025, report(2025).replace('n=237', 'n=238'))
        with self.assertRaises(ValueError):
            perfil_recente.extract_groups(2024, 'texto insuficiente')

    def test_import_is_idempotent_and_failure_preserves_prior_version(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, 'DATA', Path(tmp)):
            app.init_db()
            with patch('perfil_recente.fetch', side_effect=lambda db, source, url, limit: (b'2024' if '1bi7' in url else b'2025', 'application/pdf', 'digest')), patch('perfil_recente.extract_pdf', side_effect=lambda body: report(int(body.decode()))):
                perfil_recente.collect()
                perfil_recente.collect()
            with app.connect() as db:
                rows = overview(db)['perfil_institucional_recente']
                self.assertEqual(len(rows), 14)
                self.assertEqual(next(r['valor'] for r in rows if r['ano'] == 2025 and r['metadados']['grupo_perfil'] == 'disque100' and r['metadados']['observacao']['categoria'] == 'Feminino'), 237)
                self.assertTrue(all(r['ambiente'] == 'real' for r in rows))
            with patch('perfil_recente.fetch', side_effect=lambda db, source, url, limit: (b'2024' if '1bi7' in url else b'2025', 'application/pdf', 'digest')), patch('perfil_recente.extract_pdf', side_effect=lambda body: report(2024) if body == b'2024' else 'relatório inválido'):
                with self.assertRaises(ValueError):
                    perfil_recente.collect()
            with app.connect() as db:
                self.assertEqual(len(overview(db)['perfil_institucional_recente']), 14)


if __name__ == '__main__':
    unittest.main()
