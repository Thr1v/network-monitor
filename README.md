# Network Monitor

Docker-based monitoring stack for network devices using Grafana, Prometheus and SNMP Exporter.

## Stack

- Grafana - dashboards and visual frontend
- Prometheus - metrics storage and querying
- SNMP Exporter - polls switches, firewalls and network devices over SNMP

## Data flow

```text
Switch / Firewall / Network Device
        ↓ SNMP
SNMP Exporter
        ↓ Prometheus scrape
Prometheus
        ↓ datasource
Grafana

Backup process for docker:

# Backup Grafana data
docker run --rm \
  -v network-monitor_grafana-data:/data \
  -v "$PWD/backups:/backup" \
  ubuntu \
  tar -czf /backup/grafana-data-backup.tar.gz /data

# Backup Prometheus data
docker run --rm \
  -v network-monitor_prometheus-data:/data \
  -v "$PWD/backups:/backup" \
  ubuntu \
  tar -czf /backup/prometheus-data-backup.tar.gz /data

