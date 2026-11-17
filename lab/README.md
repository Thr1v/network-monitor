# Disposable GitHub-hosted Monitoring Lab

This is a **separate, disposable environment** that reproduces the monitoring pattern used in Network Monitor. It does not deploy to Chelmsford College or modify the local Windows/Docker monitoring PC. No IP addresses, SNMP credentials, local data volumes, database content or production targets are used.

## What the demo proves

- A change on a `feature` or `feature/*` branch triggers automated tests on a GitHub-hosted VM.
- A second, independent hosted VM starts a fresh Prometheus, Grafana and Node Exporter stack.
- The smoke test queries **real** CPU, RAM, disk and network metrics from that VM and verifies Prometheus scraping and Grafana health.
- A third hosted VM deploys the stack, removes all lab containers and volumes, creates **new** containers from the same definitions and verifies monitoring a second time.
- The four jobs appear individually in the Actions view, and a final quality gate fails if any earlier job fails.
- Evidence logs and JSON reports are attached to the run for assessment.

**Scope of immutability:** This is evidence of fresh, disposable *GitHub-owned execution VMs* and reproducible, replaceable container workloads. GitHub, not Terraform or custom IaC, provisions the underlying VM. Re-running the workflow launches new hosted VMs; the lab does **not** prove that the project itself provisioned a cloud machine with Terraform. Container image **version tags** are pinned (no `latest`), but registry tags aren't immutable digests. This is a targeted demonstration, not a fully immutable production platform.

## Run on GitHub (no Azure or Hyper-V)

1. On the existing `feature` branch, add `.github/workflows/ephemeral-lab.yml` and the complete `lab/` directory.
2. Commit and push to `feature`. **The push automatically triggers** `Ephemeral Monitoring Lab` under **Actions**; you do not need to use the manual-run button for the first run.
3. Open **Actions -> Ephemeral Monitoring Lab -> the latest run**. You will see:
   - **01 - Lab configuration tests**
   - **02 - Fresh VM: deploy & test**
   - **03 - Fresh VM: destroy & replace**
   - **04 - Reproducibility quality gate**
4. Open jobs 02 and 03 to inspect the container creation, metrics tests and recreation. Expand **Run summary** and download `ephemeral-deploy-<run-id>` and `ephemeral-replacement-<run-id>` from **Artifacts** (retained 14 days).
5. Review the pull request to `main` using the existing review process. The lab neither merges nor deploys to a persistent service. Once the workflow has been merged into `main`, GitHub will also show **Run workflow** for a manual demonstration, with a branch selector.

**Why isn't the hosted Grafana URL available?** The job exposes Grafana only on `127.0.0.1` inside its temporary runner for safety. The VM disappears when the job finishes, so Grafana is not a permanent public website. The captured API test results and action logs are the assessment evidence.

**Cost:** GitHub's *standard hosted runners are free for public repositories*. The repository is currently public. Do not move this workflow to a private repo or use larger runners without checking billing/quotas.

## Files

```text
.github/workflows/ephemeral-lab.yml   Four-stage workflow
lab/docker-compose.yml                Isolated three-service container lab
lab/prometheus.yml                    Local-only Prometheus scrape configuration
lab/grafana/...                        Auto-provisioned datasource and dashboard
lab/scripts/verify.py                 HTTP integration test and evidence writer
lab/tests/test_lab.py                  Static unit/security/architecture tests
```

## Run locally (optional, Linux Docker host)

```bash
python -m pip install PyYAML==6.0.2
python -m unittest discover -s lab/tests -p 'test_*.py' -v
docker compose -f lab/docker-compose.yml config --quiet
docker compose -f lab/docker-compose.yml up -d
python lab/scripts/verify.py --output lab-smoke-evidence.json
docker compose -f lab/docker-compose.yml down --volumes --remove-orphans
```

On a Linux machine with Docker this uses localhost ports `13000` (Grafana) and `19090` (Prometheus). Do **not** run this side-by-side with unrelated processes using those ports. The built-in Grafana password is intentionally a public **demo-only** value. This is never an appropriate production configuration.

## Screenshots to capture for the assessor

A GitHub Actions run showing all four stages green; the successful `node-exporter` metrics test under job 02; the destroy/rebuild step and differing container IDs under job 03; and the two downloadable JSON evidence files. Include a screenshot of the corresponding feature-to-main pull request and human approval separately. A failed run followed by a corrected run can also show an iterative troubleshooting approach.
