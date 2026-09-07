# Verification evidence

Verified in the engineering environment with Python 3.12 and CPU PyTorch 2.8:

* API tests: cookie/Origin behavior, cross-tenant project/asset/job denial,
  optimistic revisions, idempotency, upload/mask bounds and metadata stripping,
  deletion and purge, required metric geometry, and redacted invalid input.
* Worker/pipeline tests: expired-lease fencing, cancellation fencing, transient
  dependency failure, checkpoint reuse, artifact authorization and export.
* Layout tests: deterministic proposals, correct piece set and dimensions,
  collision/room containment, reserved zones and specified walkway connectivity.
* ML tests: real gradient optimization on synthetic ranking pairs, custom layout
  gradients, masked segmentation/depth objectives, multi-positive contrastive
  signs, safe checkpoint corruption detection, split isolation, metric sample
  counts and evaluation-to-weight binding. These are software tests, not trained
  furniture-model quality benchmarks.
* Browser exercise: real Chromium/Playwright login, image upload, queued analysis,
  cancellation and mobile viewport; no uncaught JavaScript errors and no horizontal
  overflow. Model inference was not simulated in the browser. The agent-browser
  daemon could not start in this execution environment, so the actual browser
  check ran through Playwright with a child application server.
* Alembic migration creation/application on local SQLite; module/CLI imports and lint.

Real PostgreSQL claim/idempotency concurrency tests are included and executed by
the GitHub workflow. The local execution sandbox could not run PostgreSQL under
a required non-root OS identity; local runs therefore explicitly skip those tests
when `TEST_POSTGRES_URL` is absent. Check the pull request's actual CI results
before calling this requirement verified.

Not executed here: complete foundation-model download and GPU inference, domain
fine-tuning, human-held-out quality benchmarks, Docker image execution, cloud
deployment, production load/security tests or disaster recovery. No measured
quality lift, latency capacity, successful cloud deployment or complete production
certification is asserted. Required release targets are in `EVALUATION.md`.
