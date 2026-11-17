"""Unit tests for Grafana API evidence checks; no live service required."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'verify.py'
spec = importlib.util.spec_from_file_location('lab_verify', MODULE)
lab_verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab_verify)


class GrafanaProvisioningTests(unittest.TestCase):
    def test_dashboard_and_prometheus_datasource_provisioned(self):
        def fake_get(url, timeout=5, headers=None):
            self.assertIn('Authorization', headers)
            self.assertTrue(headers['Authorization'].startswith('Basic '))
            if '/api/dashboards/uid/' in url:
                return {'dashboard': {
                    'uid': 'ephemeral-monitoring-lab', 'title': 'Ephemeral Lab',
                    'panels': [{}, {}, {}, {}]}}
            return {'uid': 'prometheus', 'type': 'prometheus'}

        with patch.object(lab_verify, 'get_json', side_effect=fake_get):
            proof = lab_verify.check_grafana_provisioning('http://127.0.0.1:13000')
        self.assertEqual(proof['dashboard_panels'], 4)
        self.assertEqual(proof['datasource_uid'], 'prometheus')

    def test_missing_dashboard_fails(self):
        with patch.object(lab_verify, 'get_json', return_value={'dashboard': {}}):
            with self.assertRaisesRegex(RuntimeError, 'dashboard was not provisioned'):
                lab_verify.check_grafana_provisioning('http://127.0.0.1:13000')

    def test_incorrect_datasource_fails(self):
        responses = [
            {'dashboard': {'uid': 'ephemeral-monitoring-lab', 'panels': [{}, {}, {}, {}]}},
            {'uid': 'wrong', 'type': 'prometheus'},
        ]
        with patch.object(lab_verify, 'get_json', side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, 'datasource was not provisioned'):
                lab_verify.check_grafana_provisioning('http://127.0.0.1:13000')


if __name__ == '__main__':
    unittest.main()
