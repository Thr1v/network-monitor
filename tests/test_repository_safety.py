"""Guardrails: local credentials, target inventories and databases stay out of Git."""
import subprocess
import unittest
from pathlib import PurePosixPath
from common import ROOT


class SafetyTests(unittest.TestCase):
    def test_private_assets_are_not_tracked(self):
        # Inspect the Git index only; local operational files are not read or uploaded.
        result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT,
                                capture_output=True, check=True)
        files = [name.decode('utf-8') for name in result.stdout.split(b'\0') if name]
        forbidden_suffixes = {'.db', '.sqlite', '.sqlite3', '.pfx', '.p12', '.pem', '.key'}
        for name in files:
            path = PurePosixPath(name)
            with self.subTest(file=name):
                self.assertNotEqual(path.name, '.env', 'Production environment file tracked')
                self.assertNotIn(path.suffix.lower(), forbidden_suffixes,
                                 'Private data/certificate tracked')
                self.assertFalse(name.startswith(('backups/', 'secrets/', 'local-data/')),
                                 'Local data tracked')
                self.assertFalse(name.startswith('prometheus/targets/')
                                 and path.name.endswith(('.local.yml', '.local.yaml')),
                                 'Operational target inventory is tracked: use .example.yml')


if __name__ == '__main__':
    unittest.main()
