# Deployment and operation

## Environments

Use separate development, staging and production databases, private buckets,
service credentials, model locks and consented datasets. The local SQLite path
is for one worker. The supplied production Compose deployment is a single host
control plane with managed persistence and separately reachable model services.
For host-level availability, use an orchestrator across failure domains; restarting
several Compose replicas on one host does not provide that guarantee.

## Build artifacts

Run from `platform/`. Build the control plane and GPU model image independently:

```bash
docker build -t furniture-ai:release-001 .
docker build -f Dockerfile.model -t furniture-ai-model:release-001 .
docker run --rm furniture-ai:release-001 furniture --help
```

The image build installs exact core dependency hashes. The separate ML dependency
lock pins Python packages and CUDA wheels. Base-image tags intentionally receive
security rebuilds; store the resolved image digest in your release record. Scan
images in your registry and rebuild locked dependencies deliberately. Do not make
production a floating `latest` deployment.

Push these images to your configured private registry, then set `FURNITURE_IMAGE`
to its returned `registry/image@sha256:...` digest. Choose a tested vLLM image
digest separately. `vllm/vllm-openai:v0.12.0` is the supplied compatibility baseline
for the `structured_outputs` request contract; vLLM has a different PyTorch/CUDA
stack from the model service. Test the host driver against both images.
See the [official v0.12.0 release](https://github.com/vllm-project/vllm/releases/tag/v0.12.0).

## Private model services

Install weights once on the model host, verify them, and mount them read-only.
Use enough disk for original weights, candidate weights and rollback copies.
Actual peak memory depends on pixels, precision, ControlNets and cache settings;
measure it on the intended device before setting concurrency.

```bash
python scripts/configure.py
python -m furniture_ai.ml.install --group all --output data/models
python -m furniture_ai.ml.install --group all --output data/models --verify
export MODEL_BIND_IP=10.0.2.10
docker compose -f compose.yml -f deployment/compose.gpu-host.yml --profile inference \
  up -d --build perception generation scoring evaluator
```

Replace the private example address with the actual GPU host interface. The default
assignments are perception GPU 0, generation GPU 1, evaluator GPU 2 and scoring CPU.
Set `PERCEPTION_GPU`, `GENERATION_GPU`, `EVALUATOR_GPU` in `.env` to match allocation.
Allow TCP 8001–8004 only from worker hosts in the network firewall. Use private TLS
endpoints or a service mesh if traffic crosses an untrusted network. Match model
and evaluator keys with the worker configuration using a secret manager.

The model service allows one request at a time and returns 429 when busy. Perception
loads detector, segmenter and depth sequentially, evicting the prior family to bound
VRAM. Model-ready checks verify installed revisions; they do not substitute for a
warm inference request. Run a real photo, a plan, a valid mask, and a crowded room
through the staging stack before admitting production traffic.

For a promoted Qwen model, update the evaluator's local `--model` mount to the
registered folder while preserving the served model alias. Update the matching
`FURNITURE_VISION_REVISION` in API/worker configuration.

## Persistence and credentials

Provision PostgreSQL 17 in the private network with TLS verification, backups,
point-in-time recovery and a dedicated database/role. Restrict inbound connections
to application hosts. Use migration credentials with schema DDL permission;
production application credentials may be restricted to the deployed schema's
tables/sequences after migration. The provided Compose configuration uses the
same DSN for simplicity; separate migration DSNs can be passed to the migration job.

Provision a private S3 bucket with public access blocked, encryption, TLS-only
bucket policy, versioning policy consistent with deletion commitments, and lifecycle
rules for temporary/orphan data. The application writes AES256 or your configured
KMS key. Give the workload identity only ListBucket/GetObject/PutObject/DeleteObject
for its application prefix and KMS permissions if enabled. Never place keys in
images, source control, or the browser. On AWS, use the instance/task workload role;
else inject short-lived AWS credentials through your secret manager.

```bash
cp deployment/production.env.example .env.production
chmod 600 .env.production
```

Edit all example values, preserving JSON syntax in `FURNITURE_ALLOWED_HOSTS`.
Provide the real database CA at an absolute path. Generate independent random
secrets with a secret manager; do not use example text as credentials. Match
`FURNITURE_PUBLIC_ORIGIN` exactly to the HTTPS browser origin. The application
refuses production with SQLite, local objects, a wildcard host, HTTP origin,
missing model revision or missing service keys.

## Start production

After configuring DNS, firewall and the private services:

```bash
export DOMAIN=design.your-domain.example
export DB_CA_FILE=/absolute/private/path/postgres-ca.pem
export FURNITURE_IMAGE=your-registry/furniture-ai@sha256:YOUR_RELEASE_DIGEST
docker compose -f deployment/compose.production.yml config --quiet
docker compose -f deployment/compose.production.yml run --rm migrate
docker compose -f deployment/compose.production.yml up -d
docker compose -f deployment/compose.production.yml exec api \
  furniture create-user --username administrator --tenant-name "Design studio"
```

Use your actual domain and digest. The gateway obtains TLS certificates; allow
ports 80/443 for ACME and clients. No API container port is publicly published.
`/metrics` is blocked at the public gateway. Use a private monitoring path and
Bearer metrics token to scrape it. Caddy persistent volumes retain certificates.
The database migration must finish successfully before API and workers start.

## Acceptance and scaling

Verify HTTPS sign-in, cross-tenant denial, decoded upload, PDF limits, an actual
complete design, export, cancellation, restart/reclaim and a restore rehearsal.
Load-test with the real input distribution; compare cold/warm model latency.

```bash
docker compose -f deployment/compose.production.yml up -d --scale api=2 --scale worker=2
docker compose -f deployment/compose.production.yml logs --tail=100 worker
```

API replicas share PostgreSQL sessions and S3, so no sticky browser session is
needed. Each API/worker process can open up to 10 PostgreSQL connections; reserve
headroom for monitoring/migrations and use a tested pooler if appropriate. Increase
workers only when downstream model replicas and database capacity support them.
Behind a private load balancer, scale each model role independently; route only to
ready replicas. Keep one in-flight generation per GPU replica unless profiling
proves a higher setting safe.

For orchestrated deployment, use the same images and commands: API Deployment,
worker Deployment with 600-second termination grace, one-GPU model Deployments,
managed PostgreSQL/S3, external secrets, readiness probes and private Services.
Use at least two API replicas across nodes, disruption budgets, bounded autoscaling
on queue age and device utilization, and a rolling strategy that drains old worker
jobs before changing model revisions. Provider URLs are deployment configuration,
so service discovery does not require application code changes. Cloud account,
region and network ownership must be supplied before provisioning those resources.

Suggested initial service objectives to validate: control-plane p95 under 500 ms
excluding upload bytes, zero cross-tenant disclosures, and bounded queue age during
the agreed peak workload. These are targets, not measurements from this delivery.
Alert on rising failed jobs, oldest pending age, repeated 429/503 responses, worker
restarts, GPU OOM and database pool saturation. Export structured logs without
request bodies. Model exceptions record operation/type; central logs should attach
the deployment revision to distinguish configuration from input failures.

## Retention, backups and recovery

Run `furniture gc` hourly using your scheduler:

```bash
docker compose -f deployment/compose.production.yml run --rm --no-deps api furniture gc
```

It removes expired sessions/rate buckets, tombstones old projects, skips active
jobs, deletes their object prefix, then removes database rows. Retention is measured
from project creation (default 30 days). Failed object cleanup is retried on the
next run; do not delete the tombstone manually. S3 versioned deletions require
bucket lifecycle handling of previous versions. Include backup retention in your
privacy commitments. Late writes from a cancelled GPU request can leave orphan
objects; periodically reconcile old storage prefixes with DB project IDs and set
appropriate orphan/old-version lifecycle cleanup before release.

Use managed PostgreSQL PITR and bucket recovery appropriate to the deployment's
RPO/RTO. Restore into isolated infrastructure, apply the matching application/model
release, validate tenant ownership and artifact hashes, then test representative
jobs. Never call a backup verified until this restore succeeds. Do not back up
plaintext session cookies or expand retention by silently retaining training exports.

## Rollback and incident handling

Stop new submissions at the gateway, drain workers, and record pending job IDs.
Restore the previous image digest, model lock and checkpoint/environment paths,
then resume. Database migration 0001 is additive for this new platform; normal
application rollback does not run a destructive downgrade. Inspect an explicit
schema rollback separately if it becomes necessary.

For leaked credentials, rotate the relevant model/metrics/storage secret. Use
`furniture reset-password --username USER` to reset an account and revoke all its
sessions. Investigate audit records using tenant/resource IDs; do not copy room
photos into incident chat logs. Dependency outages remain visible as bounded job
errors and can be retried by submitting a new job after recovery.
