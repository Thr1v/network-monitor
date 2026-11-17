"""No-cloud-cost unit checks for the isolated GitHub Actions infrastructure lab."""
import json
from pathlib import Path
import unittest
import yaml

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parent


def read_yaml(path):
    return yaml.safe_load(path.read_text(encoding='utf-8'))


class EphemeralLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = read_yaml(LAB / 'docker-compose.yml')
        cls.prometheus = read_yaml(LAB / 'prometheus.yml')
        cls.dashboard = json.loads((LAB / 'grafana/dashboards/ephemeral-lab.json').read_text())

    def test_three_service_stack(self):
        self.assertEqual(set(self.compose['services']), {'grafana', 'prometheus', 'node-exporter'})

    def test_pinned_images_and_no_prod_data_mounts(self):
        for name, service in self.compose['services'].items():
            self.assertRegex(service['image'], r':v?\d+\.\d+\.\d+$', name)
            self.assertNotIn('privileged', service, name)
            for mount in service.get('volumes', []):
                self.assertNotIn('network-monitor_grafana-data', str(mount))
                self.assertNotIn('/etc/prometheus/targets', str(mount))

    def test_ports_are_loopback_only(self):
        for name in ('grafana', 'prometheus'):
            for port in self.compose['services'][name]['ports']:
                self.assertTrue(port.startswith('127.0.0.1:'), port)
        self.assertNotIn('ports', self.compose['services']['node-exporter'])

    def test_only_local_lab_metrics(self):
        jobs = {job['job_name']: job for job in self.prometheus['scrape_configs']}
        self.assertEqual(set(jobs), {'prometheus', 'node-exporter'})
        target = jobs['node-exporter']['static_configs'][0]['targets']
        self.assertEqual(target, ['node-exporter:9100'])
        self.assertNotIn('file_sd_configs', jobs['node-exporter'])

    def test_grafana_datasource_and_dashboard(self):
        ds = read_yaml(LAB / 'grafana/provisioning/datasources/prometheus.yml')['datasources'][0]
        self.assertEqual(ds['url'], 'http://prometheus:9090')
        self.assertEqual(ds['uid'], 'prometheus')
        provider = read_yaml(LAB / 'grafana/provisioning/dashboards/dashboards.yml')['providers'][0]
        self.assertEqual(provider['options']['path'], '/var/lib/grafana/dashboards')
        self.assertEqual(self.dashboard['uid'], 'ephemeral-monitoring-lab')
        self.assertGreaterEqual(len(self.dashboard['panels']), 4)
        self.assertTrue(all(p['targets'][0].get('expr') for p in self.dashboard['panels']))

    def test_no_production_secrets_in_lab(self):
        text = (LAB / 'docker-compose.yml').read_text()
        for forbidden in ('GRAFANA_ADMIN_PASSWORD}', 'SMTP_PASSWORD', '172.20.', '172.31.', '.env', 'SNMP_COMMUNITY'):
            self.assertNotIn(forbidden, text)

    def test_actions_visible_stages_and_protected_pr_path(self):
        # YAML 1.1 may parse 'on:' as true; this test only checks job structure.
        workflow = read_yaml(REPO / '.github/workflows/ephemeral-lab.yml')
        self.assertEqual(set(workflow['jobs']), {'validate', 'deploy', 'replace', 'quality-gate'})
        self.assertIn('pull_request', workflow.get('on', workflow.get(True, {})))
        self.assertEqual(workflow['jobs']['replace']['needs'], ['validate', 'deploy'])
        self.assertIn('always()', workflow['jobs']['quality-gate']['if'])


if __name__ == '__main__':
    unittest.main()
