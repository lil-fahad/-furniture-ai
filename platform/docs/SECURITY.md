# Security and privacy

Authentication uses Argon2 password hashes, timing-resistant checks for nonexistent
accounts, rate-limited login attempts and hashed opaque session tokens. Cookies
are HttpOnly, SameSite=Strict, and Secure in production. Mutating requests require
an exact allowed Origin. Role assignment and password reset are administrative CLI
operations; public API inputs cannot change tenant membership or roles.

All project, asset, job, export and feedback lookups are tenant-scoped. Unknown
and other-tenant IDs return the same 404 shape. API responses expose authorized
artifact URLs, not storage keys or signed cross-tenant URLs. Project tombstones
immediately revoke artifact access and invalidate active job leases. Database
audits contain action/resource IDs, not images, raw prompts or passwords.

Uploads have both whole-request and decoded-image bounds, including chunked
requests. The decoder checks actual format, strips metadata and normalizes pixels.
PDF rasterization has subprocess CPU/memory/time/page bounds. Storage paths are
generated internally and checked against traversal. Source filenames do not become
filesystem paths. External URL upload is unsupported, limiting the SSRF surface.

Providers use deployment-configured endpoints, service Bearer keys, TLS verification
when HTTPS, bounded response bodies and timeouts. Redirects and environment proxy
inheritance are disabled for inference calls. Neither uploaded text nor VLM output
can choose a network destination, execute code or create a supplier purchase link.
Structured schemas reject extra fields, nonfinite values and invalid geometry.

The browser uses same-origin assets and a restrictive CSP with no inline scripts,
no third-party CDN, no framing, and no client-side storage of credentials. Its
rendering uses DOM text nodes for untrusted text. API responses disable caching.
Container workloads drop capabilities and run without root; deployment examples
use read-only root filesystems, bounded temporary storage and no public model ports.

Inference weights are local safetensors at pinned revisions. The research CubiCasa
adapter additionally checks a supplied digest and restricts loading to weight
tensors. Training resume state is a trusted internal artifact, not an uploaded
user input. Model promotion checks inventory digests, evaluation binding and
training-rights metadata; operators must protect release artifacts and approvals.

Resource limits exist at upload, image, project, queue, rate, geometry-search,
provider-body, inference-concurrency and retry layers. PostgreSQL handles shared
limits; SQLite is explicitly not a multiworker production substitute. Set ingress
connection limits and capacity from load tests because bounded per-request buffers
can still consume significant aggregate memory under many simultaneous requests.

Project retention and user-consented training exports are separate lifecycle
processes. Feedback consent defaults false. Maintain an export/deletion ledger and
document what model unlearning can and cannot accomplish. Keep private images,
weights, datasets, credentials and evaluation artifacts out of Git. Use managed
secret rotation, least-privilege storage/database identities and tested recovery.

Production readiness also requires a review of actual IAM/firewall configuration,
dependency vulnerabilities, data agreements, and independent penetration/load
tests of the deployed environment. The code tests provide evidence for their
specific assertions, not a blanket security certification.
