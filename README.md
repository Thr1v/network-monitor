# Network Monitor

Self-hosted network and Windows server monitoring with **Grafana, Prometheus, SNMP Exporter, Blackbox Exporter and Windows Exporter**. It provides dashboards for switch traffic/errors, website availability, server resource health, and network reachability. The Docker stack runs on the monitoring PC; Windows servers expose metrics through a small Windows service on each host.

> **Repository scope:** This repository contains the Docker stack, Prometheus and Blackbox configurations, alert rules, Grafana provisioning and dashboards. The database and additional locally developed features on the author's PC are **not committed, packaged or deployed by this repository**. Do not expect them to appear after cloning or pulling. No live server monitoring is active until targets are configured and exporters installed.

## What it monitors

| Component | Measurements | Collection method |
| --- | --- | --- |
| Switches / interfaces | SNMP reachability, traffic, errors, discards | SNMP Exporter (`snmp-switches`) |
| Websites | HTTP success | Blackbox Exporter (`website-checks`) |
| Windows servers / PCs | CPU, physical RAM, free/used drive capacity, disk IO, network throughput, NIC errors/discards | `windows_exporter` (`windows-servers`) |
| Windows machines with supported GPUs | 3D engine activity, dedicated GPU memory and optional GPU temperature | Optional `gpu` collector in `windows_exporter` |
| Servers and other pingable network devices | ICMP response, round-trip time, failed probes and observed availability | Blackbox Exporter (`icmp-ping`) |

The **Network Overview** dashboard is the existing SNMP dashboard. New dashboards are **Windows Server Health & Connectivity** and **Network Reachability & Dropouts**. They are provisioned automatically from `grafana/dashboards/`. Dashboards show *No data* until relevant targets emit metrics; a missing GPU is not assumed healthy/idle.

### Architecture

```text
Switches --SNMP------------------------> SNMP Exporter ---+
Websites --HTTP-----------------------> Blackbox Exporter -+
Servers / gateways --ICMP-------------> Blackbox Exporter -+--> Prometheus --> Grafana
Windows servers/PCs --TCP 9182-------> windows_exporter ---+
```

Prometheus holds time-series data in its Docker volume and evaluates alert rules. Grafana reads the Prometheus datasource and shows dashboards. **Prometheus alert rules alone do not send emails:** configure a supported notification path (for example Grafana-managed alerts/contact points or Alertmanager) separately.

## Requirements

- Docker Engine with Compose (for example Docker Desktop on Windows, using Linux containers).
- Network reachability from the Docker containers to switches, websites and each Windows host.
- Windows servers/PCs with `windows_exporter` installed as a Windows service, and inbound **TCP 9182** allowed **only from the monitoring host** or an appropriate trusted monitoring subnet. Do not expose this endpoint to the internet.
- For ping monitoring: ICMP permitted by the target firewall, Docker/network policy that permits ICMP from the Blackbox container, and the container's `NET_RAW` capability (included in `docker-compose.yml`).
- Existing SNMP configuration in `snmp-exporter/snmp.yml` matching the `public_v2` auth module currently named in `prometheus/prometheus.yml`. Replace default/public SNMP community settings for production; use scoped SNMPv3 where available.

## Getting started (PowerShell on the monitoring PC)

1. Clone/download the repository. Open a PowerShell window **in the repository directory**.
2. Configure environment variables. Do not overwrite your existing `.env` if you already run this stack:

   ```powershell
   # First installation ONLY:
   Copy-Item .env.example .env
   notepad .env
   ```

   Edit Grafana credentials, ports, data retention and SMTP placeholders to match the local deployment. `.env` is intentionally Git-ignored. The existing Docker Compose configuration has SMTP enabled, so valid SMTP settings are needed for working email notifications.

3. Check the existing SNMP module/auth settings if you want to retain switch monitoring. Do **not** replace `snmp-exporter/snmp.yml` with an empty file: the repository currently relies on its generated module definitions.
4. Run:

   ```powershell
  docker compose config --quiet
   docker compose up -d
  docker compose ps
   ```

5. Open Grafana at `http://localhost:3000` (or the configured `GRAFANA_PORT`). Prometheus is bound to `127.0.0.1` at `http://localhost:9090` (or your configured port); use **Status > Target health** to inspect scrape results. The exporter containers are also bound to localhost, rather than publicly exposed.

### Add a Windows server / PC

Install `windows_exporter` using the official **[Windows Exporter releases](https://github.com/prometheus-community/windows_exporter/releases)** page on **each machine** being monitored. Default collectors include CPU, memory, logical disks and networking. The GPU collector is optional and must be enabled explicitly.

Example from an elevated PowerShell or CMD prompt after downloading the official MSI (replace the MSI filename and monitoring IP):

```powershell
msiexec.exe /i "C:\Temp\windows_exporter-<VERSION>-amd64.msi" ENABLED_COLLECTORS="[defaults],gpu" REMOTE_ADDR="<MONITORING_PC_IP>" /qn /norestart
Get-Service windows_exporter
Invoke-WebRequest http://localhost:9182/metrics -UseBasicParsing | Select-Object -ExpandProperty StatusCode
```

For a machine with no supported GPU, install with the default collectors (or omit `gpu`). With a managed firewall/GPO, explicitly restrict inbound TCP 9182 to the monitoring host and verify the MSI-created rule's scope. Some Docker Desktop networks can present a different source address; confirm the actual source when troubleshooting firewall rules. Avoid publicly routable exporters.

Open `prometheus/targets/windows-servers.local.yml` (copy `windows-servers.example.yml` to that name on fresh clones) and replace the initial `[]` with entries such as:

```yaml
- targets: ["192.0.2.10:9182"]
  labels:
    host: "EXAMPLE-SERVER"
    location: "EXAMPLE-SITE"
```

`192.0.2.x` is documentation-only: use each server's real IP or resolvable DNS name. Every target **must** have a unique `host` label. The `location` label is optional but useful for filtering later. Example configurations are in `prometheus/targets/*.example.yml`.

### Add ping and dropout monitoring

Open `prometheus/targets/ping-targets.local.yml` (copy `ping-targets.example.yml` to that name on fresh clones) and replace `[]` with the devices to probe:

```yaml
- targets: ["192.0.2.10"]
  labels:
    host: "EXAMPLE-SERVER"
    location: "EXAMPLE-SITE"
- targets: ["192.0.2.1"]
  labels:
    host: "EXAMPLE-GATEWAY"
    location: "EXAMPLE-SITE"
```

The **same `host` label** for a Windows server in both target files connects its performance and ping graphs in the server dashboard. The Network Reachability dashboard can also display routers, switches, gateways and other pingable devices without `windows_exporter`.

A Blackbox ICMP probe sends one request per 30-second scrape. **Observed probe failures are not a statistically accurate network packet-loss test**. In particular, missing Prometheus samples are not counted as lost packets. For detailed loss/jitter, a multi-packet prober or Smokeping-style tool would be a separate addition.

The `.local.yml` target lists are Git-ignored; keep them local to your monitoring PC (the `.example.yml` templates are safe for Git). The target files are auto-discovered by Prometheus in approximately one minute; new/changed targets do not normally require restarting the containers. On Windows Docker Desktop, ensure the containers can reach the correct VLANs and target firewalls allow the traffic.

### Validate that it works

From the monitoring PC:

```powershell
# Confirm files/env are valid for Docker Compose
docker compose config --quiet

# Check running containers
docker compose ps
docker compose logs --tail 100 prometheus blackbox-exporter
```

Open the Prometheus targets page at `http://localhost:9090/targets` (substitute your configured port) and check `windows-servers` and `icmp-ping`. On the Prometheus **Graph** page, test:

```promql
up{job="windows-servers"}
probe_success{job="icmp-ping"}
windows_logical_disk_free_bytes{job="windows-servers"}
windows_net_bytes_received_total{job="windows-servers"}
windows_gpu_info{job="windows-servers"}
```

If the first four return data but the last does not, check whether `gpu` is enabled, the host has a supported GPU, and the driver reports WDDM performance counters. GPU sensor support depends on driver/hardware. Disk free-space performance counters may update **10–15 minutes behind** actual changes.

## Alerting

- Existing alert definitions remain in `prometheus/rules/network-alerts.yml` (targets, SNMP load/errors/discards).
- New alert definitions are in `prometheus/rules/server-health-alerts.yml`: exporter unavailable, CPU >90%, RAM >90%, disk >85% or >95%, optional GPU near its thermal warning threshold, NIC usage >85%, NIC packet errors, ICMP failure, intermittent failures and high latency (>100 ms).
- Rules are evaluated by Prometheus every 30 seconds, with `for` periods to avoid noisy transient alerts. LAN latency thresholds are intentionally conservative; tune them to your network. `up=0` denotes a **scrape problem**; `probe_success=0` denotes a **failed probe** when scraped successfully.
- View rule states at `http://localhost:9090/alerts`. An alert firing there does **not** prove Grafana email notifications have been configured. Set up a notification system explicitly.

## Project files

```text
network-monitor/
├── .env.example                       # safe example values (actual .env is local)
├── docker-compose.yml                 # monitoring services and persistent volumes
├── prometheus/
│   ├── prometheus.yml                 # scrape jobs
│   ├── rules/network-alerts.yml       # original SNMP/target alerts
│   ├── rules/server-health-alerts.yml # Windows/ICMP alerts
│   └── targets/                       # monitored host lists + example files
├── blackbox/blackbox.yml              # HTTP and ICMP probing modules
├── snmp-exporter/snmp.yml             # existing generated SNMP config
└── grafana/
    ├── provisioning/                 # datasource and dashboard loaders
    └── dashboards/
        ├── network-overview.json      # existing switch dashboard
        ├── server-health.json         # Windows health and per-server connectivity
        └── connectivity-overview.json # all ping targets/dropouts
```

## Update, maintain and back up

Before changing the stack, back up Grafana and Prometheus volumes, and save your local `.env`, real target configuration, and any custom dashboards. **Database/app features living only on your PC are not in GitHub and are not backed up by this repository.** Back those up separately.

Typical update (PowerShell, from the repo directory):

```powershell
# If you have changed tracked files locally, first commit/stash or copy those edits.
git pull --ff-only
# Review changes to target lists, Compose settings and monitoring rules.
docker compose config --quiet
docker compose pull
docker compose up -d --remove-orphans
docker compose ps
```

`docker compose down` removes containers/networks but normally preserves **named volumes**; **never run `docker compose down -v`** without a separate verified backup. For consistent volume backups, stop the writers first. Example for the default Compose project directory name `network-monitor` (check actual names with `docker volume ls`):

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
docker compose stop grafana prometheus
# These example commands use Alpine to archive the named volumes.
docker run --rm -v network-monitor_grafana-data:/src:ro -v "${PWD}/backups:/backup" alpine tar -czf /backup/grafana-data.tgz -C /src .
docker run --rm -v network-monitor_prometheus-data:/src:ro -v "${PWD}/backups:/backup" alpine tar -czf /backup/prometheus-data.tgz -C /src .
docker compose start grafana prometheus
```

To change a dashboard or alert, edit the JSON/YAML in this repository, validate syntax, commit it, then `docker compose up -d` or restart the relevant service for immediate application. Prometheus rules and Blackbox module changes require reload/restart; Grafana's file provisioning detects dashboard changes periodically. When editing the provisioned dashboard in Grafana's UI, **export the JSON back into this repository**, otherwise a restart/provisioning refresh may overwrite UI-only edits.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Windows server shows *No data* | Install `windows_exporter`, check Windows service and TCP 9182 from the monitoring host, add target to `windows-servers.local.yml`, inspect Prometheus `/targets`. |
| Ping fails but Windows metrics work | ICMP may be blocked, or Docker Linux container can't send ICMP; check `NET_RAW`, Windows firewall and network ACL. |
| Ping graph shows No data | Add matching `host` labels to `ping-targets.local.yml`; check Blackbox logs and `probe_success`. |
| GPU panel says *No data* | Enable optional GPU collector, verify Windows driver/counters, or accept that the server has no supported GPU. |
| Disk percentages appear delayed | Windows logical disk size/free counters may lag by up to 10–15 minutes. |
| Alerts show in Prometheus but no emails arrive | Prometheus rule evaluation and Grafana notification routes are separate. Configure notification rules/contact points or Alertmanager. |
| Grafana dashboard disappeared after editing in UI | These dashboards are file-provisioned. Export/commit JSON changes instead of relying on in-UI edits. |
| Existing SNMP switch monitoring fails | Keep matching `if_mib` and `public_v2` in the existing `snmp.yml`; validate device SNMP authorization/reachability. |

## Security and local-only features

Never commit `.env`, credentials, database files, personal host inventories, or locally developed applications. The repository's `.gitignore` excludes typical local database/backup paths, but **`.gitignore` does not remove files that Git already tracks**. Review `snmp-exporter/snmp.yml` and any previously committed configs for live SNMP credentials before making the repo public. Keep Grafana protected behind trusted LAN access/VPN and apply appropriate firewall rules.

Related upstream documentation: [Prometheus](https://prometheus.io/docs/introduction/overview/) · [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/) · [Windows Exporter](https://github.com/prometheus-community/windows_exporter) · [Blackbox Exporter](https://github.com/prometheus/blackbox_exporter).
