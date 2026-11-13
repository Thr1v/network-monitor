"""Validation for Prometheus, Blackbox, and provisioning configuration."""
import re
import unittest
from pathlib import Path
from common import ROOT, load_yaml


class ConfigurationTests(unittest.TestCase):
    def test_all_committed_yaml_files_are_valid(self):
        # Includes generated SNMP configuration: formatting errors can break exporter startup.
        candidates = list(ROOT.rglob('*.yml')) + list(ROOT.rglob('*.yaml'))
        candidates = [p for p in candidates if '.venv' not in p.parts and 'node_modules' not in p.parts]
        self.assertTrue(candidates, 'No YAML files found')
        for path in candidates:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNotNone(load_yaml(path.relative_to(ROOT)))

    def test_prometheus_expected_scrape_jobs(self):
        config = load_yaml('prometheus/prometheus.yml')
        jobs = {j['job_name']: j for j in config['scrape_configs']}
        for name in ('prometheus', 'snmp-switches', 'website-checks', 'windows-servers', 'icmp-ping'):
            self.assertIn(name, jobs)
        self.assertEqual(jobs['windows-servers']['metrics_path'], '/metrics')
        self.assertEqual(jobs['icmp-ping']['metrics_path'], '/probe')

    def test_file_discovery_and_labels(self):
        jobs = {j['job_name']: j for j in load_yaml('prometheus/prometheus.yml')['scrape_configs']}
        expected = {
            'windows-servers': '/etc/prometheus/targets/windows-servers.local.yml',
            'icmp-ping': '/etc/prometheus/targets/ping-targets.local.yml',
        }
        for job, filename in expected.items():
            with self.subTest(job=job):
                paths = [p for entry in jobs[job].get('file_sd_configs', []) for p in entry.get('files', [])]
                self.assertIn(filename, paths)
                self.assertTrue((ROOT / 'prometheus' / 'targets' / Path(filename).name.replace('.local.', '.example.')).exists())

    def test_icmp_module_is_defined_in_blackbox(self):
        blackbox = load_yaml('blackbox/blackbox.yml')
        modules = blackbox.get('modules', {})
        self.assertEqual(modules['icmp_ipv4']['prober'], 'icmp')
        self.assertEqual(modules['http_2xx']['prober'], 'http')
        jobs = {j['job_name']: j for j in load_yaml('prometheus/prometheus.yml')['scrape_configs']}
        self.assertIn('icmp_ipv4', jobs['icmp-ping']['params']['module'])
        self.assertIn('http_2xx', jobs['website-checks']['params']['module'])
        self.assertEqual(jobs['icmp-ping']['relabel_configs'][-1]['replacement'], 'network-blackbox-exporter:9115')

    def test_discovery_templates_have_correct_shapes(self):
        for filename, expect_port in [('windows-servers.example.yml', True), ('ping-targets.example.yml', False)]:
            with self.subTest(file=filename):
                data = load_yaml('prometheus/targets/' + filename)
                self.assertIsInstance(data, list)
                self.assertGreater(len(data), 0)
                for group in data:
                    self.assertIn('host', group['labels'])
                    self.assertIn('location', group['labels'])
                    self.assertTrue(group['targets'])
                    for target in group['targets']:
                        self.assertEqual(target.endswith(':9182'), expect_port, target)

    def test_rule_names_are_unique(self):
        rules = list((ROOT / 'prometheus' / 'rules').glob('*.yml'))
        self.assertTrue(rules, 'No Prometheus alert rules')
        names = set()
        for path in rules:
            for group in load_yaml(path.relative_to(ROOT)).get('groups', []):
                for rule in group.get('rules', []):
                    name = rule.get('alert') or rule.get('record')
                    self.assertTrue(name, f'Unnamed rule in {path}')
                    self.assertNotIn(name, names, f'Duplicate rule: {name}')
                    names.add(name)
                    self.assertTrue(str(rule.get('expr', '')).strip(), name)


if __name__ == '__main__':
    unittest.main()
