"""Check provisioned Grafana dashboards, including Grafana v2 schema dashboards."""
import json
import unittest
from common import ROOT, load_yaml


def referenced_elements(node):
    if isinstance(node, dict):
        if node.get('kind') == 'ElementReference':
            name = node.get('name')
            if name:
                yield name
        for value in node.values():
            yield from referenced_elements(value)
    elif isinstance(node, list):
        for value in node:
            yield from referenced_elements(value)


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = sorted((ROOT / 'grafana/dashboards').glob('*.json'))

    def test_dashboards_exist_and_parse(self):
        self.assertTrue(self.files, 'No Grafana JSON dashboards found')
        for f in self.files:
            with self.subTest(file=f.name):
                parsed = json.loads(f.read_text(encoding='utf-8-sig'))
                self.assertIsInstance(parsed, dict)
                title = parsed.get('title') or parsed.get('spec', {}).get('title')
                self.assertTrue(title, f'No dashboard title: {f}')

    def test_dashboard_ids_unique(self):
        seen = set()
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
            uid = data.get('uid') or data.get('metadata', {}).get('name')
            self.assertTrue(uid, f'Missing dashboard UID in {f}')
            self.assertNotIn(uid, seen, f'Duplicate dashboard identifier {uid}')
            seen.add(uid)

    def test_panel_references_are_valid(self):
        for f in self.files:
            with self.subTest(file=f.name):
                data = json.loads(f.read_text(encoding='utf-8-sig'))
                if 'spec' in data and 'elements' in data['spec']:
                    elements = data['spec']['elements']
                    self.assertTrue(elements, 'No dashboard elements')
                    references = list(referenced_elements(data['spec'].get('layout', {})))
                    self.assertTrue(references, 'No panels referenced by the layout')
                    self.assertEqual(len(references), len(set(references)), 'Duplicate element in layout')
                    for element in references:
                        self.assertIn(element, elements, f'Layout refers to missing panel: {element}')
                else:
                    self.assertTrue(data.get('panels'), 'No dashboard panels')

    def test_panel_queries_are_nonempty(self):
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
            if 'spec' in data and 'elements' in data['spec']:
                for key, element in data['spec']['elements'].items():
                    spec = element.get('spec', {})
                    query_group = spec.get('data', {}).get('spec', {})
                    for query in query_group.get('queries', []):
                        q = query.get('spec', {}).get('query', {}).get('spec', {})
                        # Some data sources use raw query objects rather than PromQL expr.
                        if 'expr' in q:
                            self.assertTrue(str(q['expr']).strip(), f'{f.name}:{key} has empty PromQL')
            else:
                for panel in data.get('panels', []):
                    for query in panel.get('targets', []):
                        if 'expr' in query:
                            self.assertTrue(str(query['expr']).strip(), f'{f.name} has empty PromQL')

    def test_prometheus_datasource_is_provisioned(self):
        sources = load_yaml('grafana/provisioning/datasources/prometheus.yml')['datasources']
        self.assertTrue(any(source.get('type') == 'prometheus' and source.get('uid') == 'prometheus'
                            for source in sources))
        providers = load_yaml('grafana/provisioning/dashboards/dashboards.yml')['providers']
        self.assertTrue(any(p['type'] == 'file' and p['options'].get('path') == '/var/lib/grafana/dashboards'
                            for p in providers))


if __name__ == '__main__':
    unittest.main()
