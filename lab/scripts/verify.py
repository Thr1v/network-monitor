#!/usr/bin/env python3
"""HTTP integration test: Grafana, Prometheus, and real Linux runner metrics.

Uses standard library only. Test runs inside the GitHub-hosted VM (not the
container), accessing ports bound to loopback. Writes evidence JSON if requested.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen


def get_json(url, timeout=5):
    with urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f'{url}: HTTP {response.status}')
        return json.load(response)


def query(prometheus, expr):
    url = f'{prometheus}/api/v1/query?' + urlencode({'query': expr})
    data = get_json(url)
    if data.get('status') != 'success':
        raise RuntimeError(f'Query failed: {expr}: {data}')
    return data['data']['result']


def check(grafana, prometheus):
    health = get_json(f'{grafana}/api/health')
    if health.get('database') != 'ok':
        raise RuntimeError(f'Grafana database not healthy: {health}')
    ready = get_json(f'{prometheus}/api/v1/status/buildinfo')
    if ready.get('status') != 'success':
        raise RuntimeError('Prometheus API not ready')
    targets = query(prometheus, 'up{job="node-exporter"}')
    if len(targets) != 1 or float(targets[0]['value'][1]) != 1.0:
        raise RuntimeError(f'Node exporter target is not UP: {targets}')
    observations = {}
    for metric in (
        'node_cpu_seconds_total{job="node-exporter"}',
        'node_memory_MemTotal_bytes{job="node-exporter"}',
        'node_filesystem_size_bytes{job="node-exporter"}',
        'node_network_receive_bytes_total{job="node-exporter"}',
    ):
        results = query(prometheus, metric)
        if not results:
            raise RuntimeError(f'Missing host metrics: {metric}')
        observations[metric] = len(results)
    return {'grafana_database': 'ok', 'prometheus': 'ready',
            'node_exporter': 'UP', 'metrics_series': observations,
            'runner_name': os.getenv('RUNNER_NAME', 'local')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--grafana', default='http://127.0.0.1:13000')
    parser.add_argument('--prometheus', default='http://127.0.0.1:19090')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout
    last_error = 'No attempts yet'
    while time.monotonic() < deadline:
        try:
            result = check(args.grafana, args.prometheus)
            result['verified_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            print(json.dumps(result, indent=2))
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            return 0
        except Exception as error:
            last_error = str(error)
            print(f'Waiting for monitoring stack: {last_error}', file=sys.stderr)
            time.sleep(5)
    print(f'FAIL: no healthy metrics before timeout: {last_error}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
