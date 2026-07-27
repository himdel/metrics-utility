# Docker and Deployment
### Docker Compose environment for local development with PostgreSQL and MinIO
- **Repo**: ansible/metrics-utility
- **Commits**: b6879b0 (#71), be761a3 (#52)
- **What happened**: A `tools/docker/docker-compose.yaml` was created with four services: (1) `postgres` initialized with the AWX schema dump (`latest.sql`) and role definitions (`roles.sql`), (2) `minio` for S3-compatible storage, (3) `minio-setup` that creates buckets, users, and extracts access keys to a shared tmpfs volume, (4) `metrics-utility` that syncs the source code into a tmpfs (to avoid polluting the source dir), patches the DB hostname, installs dependencies with uv, and runs gather. The AWX schema files were moved from `metrics_utility/test/test_data/schemas/awx/` to `tools/docker/` to co-locate them with the compose file. The metrics-utility container uses `quay.io/fedora/python-311` and copies source to tmpfs because uv had trouble installing when a pre-existing `.venv` was present.
- **Insight**: The tmpfs trick (copy source to tmpfs, build there) works around uv/pip issues with pre-existing virtual environments in mounted volumes, and avoids polluting the host source tree with build artifacts.

### Docker Compose simplified: profiles, static credentials, no shared volumes
- **Repo**: ansible/metrics-utility
- **Commits**: 744d061 (#84)
- **What happened**: The Docker Compose setup was significantly simplified: (1) the deprecated `version: '3.8'` key was removed, (2) MinIO setup switched from dynamically extracting credentials via `mc admin user svcacct add` to static credentials via `mc admin accesskey create local mynewuser --access-key myuseraccesskey --secret-key myusersecretkey`, eliminating the `minio_config` shared volume and `source /tmp/minio_env.sh` pattern, (3) the `metrics-utility` and `metrics-utility-env` containers were made non-default via Docker Compose `profiles` (`pytest` and `env` respectively), so `docker compose up` only starts the infrastructure (postgres, minio), (4) MinIO data was moved from a named volume (`minio_data`) to tmpfs to fix issues when running the second time, (5) tmpfs permissions were changed to `uid=1001` to fix `uv run pytest: permission denied`.
- **Insight**: Using static MinIO access keys instead of dynamically generating them removed an entire coordination layer (shared volume, env file sourcing, shell parsing) -- simpler is better for dev infrastructure.

### Docker images switched from quay.io to mirror.gcr.io
- **Repo**: ansible/metrics-utility
- **Commits**: fe15447 (#124)
- **What happened**: All Docker images in docker-compose.yaml, run-ccsp2-gather, and run-renewal were changed from `quay.io/cloudservices/*` (e.g., `quay.io/cloudservices/postgres`, `quay.io/cloudservices/minio:latest`, `quay.io/fedora/python-311`) to `mirror.gcr.io/*` equivalents (e.g., `mirror.gcr.io/postgres`, `mirror.gcr.io/minio/minio`, `mirror.gcr.io/python`). This eliminated the need for `docker login quay.io` and provides more up-to-date container images. A `make compose` target was also added as a shortcut for `docker compose -f tools/docker/docker-compose.yaml up`.
- **Insight**: Using `mirror.gcr.io` instead of `quay.io/cloudservices` removes the authentication requirement for pulling development containers, reducing setup friction for new contributors.

### Docker Compose init scripts use numeric prefixes for execution order
- **Repo**: ansible/metrics-utility
- **Commits**: 77490ef (#133)
- **What happened**: When adding a `main_hostmetric.sql` init script for PostgreSQL, the init scripts in Docker Compose were renamed from `init-roles.sql`/`init-schema.sql` to `init-0-roles.sql`/`init-1-schema.sql`/`init-2-hostmetric.sql`. PostgreSQL's Docker image executes init scripts in alphabetical order, so numeric prefixes ensure roles are created before schema, and schema before data inserts.
- **Insight**: PostgreSQL Docker init scripts execute alphabetically -- use numeric prefixes (0, 1, 2...) to enforce dependency order when adding new init scripts.

### Initial Dockerfile was minimal and non-functional
- **Repo**: ansible/metrics-service
- **Commits**: dd5603f, e0bfd65
- **What happened**: The initial Dockerfile was just 9 lines: base image, pip upgrade, copy requirements, pip install. No WORKDIR, no ENTRYPOINT, no health check, no proper user setup, and it referenced `requirements/requirements.in` which didn't exist at that path. Commit e0bfd65 replaced it with a proper Dockerfile (~50 lines) with WORKDIR, env vars, system deps (gcc, postgresql-devel, openldap-devel), non-root user (UID 1001), health check, and entrypoint.
- **Insight**: Template Dockerfiles need to be tested with `docker build` before committing. The initial version would have failed immediately.

### Kubernetes manifests carried forward from template with minimal changes
- **Repo**: ansible/metrics-service
- **Commits**: dd5603f, be51903, 5e05775, cc2ac77
- **What happened**: K8s manifests were renamed from `my-service` to `metrics-service` but otherwise kept template defaults. Commit cc2ac77 added security improvements: `automountServiceAccountToken: false`, tagged image version (`metrics-service:1.0.0` instead of just `metrics-service`), and ephemeral storage limits.
- **Insight**: The Sonar-driven fixes (cc2ac77) caught real security issues in the k8s manifests: auto-mounting service account tokens is a security risk, and untagged images make deployments non-reproducible.

### Docker entrypoint handles migration and service initialization
- **Repo**: ansible/metrics-service
- **Commits**: e0bfd65
- **What happened**: `scripts/docker-entrypoint.sh` was added to wait for the database (polling `manage.py check --database default`), run migrations, initialize DAB ServiceID (checking if it exists first), and optionally collect static files in production.
- **Insight**: The entrypoint's database-readiness check via `manage.py check --database default` is more reliable than raw `pg_isready` because it tests through Django's connection layer. The ServiceID idempotency check prevents errors on container restart.

### setuptools_scm version file workaround in Docker
- **Repo**: ansible/metrics-service
- **Commits**: e0bfd65, 2a1c481 (#9)
- **What happened**: Commit e0bfd65 added `RUN echo '__version__ = "0.1.0"' > /app/metrics_service/_version.py` because setuptools_scm couldn't generate the version file due to permission issues in Docker (non-root user, no git repo). Commit 2a1c481 removed this workaround entirely by simplifying `_version.py`.
- **Insight**: setuptools_scm requires a `.git` directory to work, which isn't available in Docker builds (unless you COPY it in, which bloats the image). Hardcoding the version or using a different versioning approach is necessary for containerized builds.

### OAuth2 resource registration commented out due to import issues
- **Repo**: ansible/metrics-service
- **Commits**: e0bfd65
- **What happened**: `apps/core/resource_api.py` had its `OAuth2Application` and `OAuth2AccessToken` resource registrations commented out because they caused import errors. The `try/except ImportError` block was already there but apparently wasn't catching the actual error.
- **Insight**: DAB's OAuth2 provider models may not be available during migrations or initial setup, and the `try/except ImportError` pattern doesn't catch all failure modes (e.g., `AppRegistryNotReady`).

### Docker switched from pip to uv for dependency management
- **Repo**: ansible/metrics-service
- **Commits**: d85322e (#18)
- **What happened**: The Dockerfile was updated to install `uv` via pip and use it for dependency management inside the container, replacing the direct `pip install -r requirements.txt` approach. The `scripts/docker-entrypoint.sh` was recreated (after being deleted in c6947ce) with proper database readiness checks and migration handling.
- **Insight**: Using uv inside Docker provides the same dependency resolution as development, ensuring consistency. However, installing uv via pip inside the container adds an extra layer -- Konflux later needed its own requirements files approach.

### Docker compose simplified to remove Redis and unneeded services
- **Repo**: ansible/metrics-service
- **Commits**: d85322e (#18)
- **What happened**: The docker-compose.yml was cleaned up to remove Redis container references, simplify the PostgreSQL service configuration, and update the metrics-service container setup. The `.env.example` was updated to remove the Redis URL variable.
- **Insight**: Removing unused infrastructure from docker-compose reduces startup time and resource usage for developers. The Redis service was added from the template but never used by the application.

### Konflux onboarding required parallel requirements file management
- **Repo**: ansible/metrics-service
- **Commits**: c31e746 (#21)
- **What happened**: Onboarding to Konflux (Red Hat's CI/CD platform) required adding Tekton pipeline configurations (`.tekton/metrics-service-pull-request.yaml` and `push.yaml`, ~640 lines each), plus `requirements-build.txt`, `requirements-pinned.txt`, `rpms.in.yaml`, `rpms.lock.yaml`, and `ubi.repo` files. The Tekton pipelines use hermetic builds with prefetch-input that reads from `requirements-build.txt`. The Dockerfile was updated to reference `Dockerfile.backend`.
- **Insight**: Konflux's hermetic build system cannot use uv.lock directly -- it requires pip-format requirements files with hashes. This created a parallel dependency management burden: uv.lock for development, requirements-pinned.txt/requirements-build.txt for Konflux builds. This mismatch was the motivation for the sync-requirements system added later in f848024 (#24).

### Docker removed uv in favor of plain pip for container builds
- **Repo**: ansible/metrics-service
- **Commits**: 6059d8c (#45)
- **What happened**: The Dockerfile was updated to remove `pip install uv` and the `UV_SYSTEM_PYTHON=1` env var. Dependency installation switched from `uv pip install` to plain `pip install --no-cache-dir -r requirements-build.txt`. The `docker-compose.yml` command changed from `uv run python manage.py ...` to `python manage.py metrics_service run`. The entrypoint script (`docker-entrypoint.sh`) also replaced all `uv run python` calls with plain `python`. The `uv` package was also removed from `pyproject.toml` dependencies.
- **Insight**: Having `uv` as both a development tool and a runtime container dependency created unnecessary complexity. The container only needs pip to install from the pre-built `requirements-build.txt` (which is generated from `uv.lock` by the sync-requirements system). Removing uv from the container reduces image size and attack surface.

### Separate dispatcherd container merged into main service
- **Repo**: ansible/metrics-service
- **Commits**: 6059d8c (#45)
- **What happened**: The `metrics-dispatcher` service was removed from `docker-compose.yml`. Previously there were two containers: one running `runserver` and another running `run_dispatcherd`. Now the single `metrics-service-app` container runs `python manage.py metrics_service run` which starts Django + dispatcherd + APScheduler in the same process. The `CMD` in Dockerfile was updated to match.
- **Insight**: Running all three components (web server, task worker, scheduler) in a single container simplifies the Docker development setup. The `metrics_service run` management command already manages all three as threads/subprocesses. For production Kubernetes deployments, separate containers may still be needed for scaling independently.

### PostgreSQL image switched to GCR mirror
- **Repo**: ansible/metrics-service
- **Commits**: 6059d8c (#45)
- **What happened**: `docker-compose.yml` changed the PostgreSQL image from `postgres:15` to `mirror.gcr.io/postgres:15`.
- **Insight**: Using the GCR mirror avoids Docker Hub rate limiting issues that can affect CI and development environments. The image content is identical.

### dispatcherd config use_django_db quickly reverted to explicit connection
- **Repo**: ansible/metrics-service
- **Commits**: 6059d8c (#45), 3a8f7d5 (#48)
- **What happened**: Commit 6059d8c changed `config/dispatcherd.yaml` from explicit database connection parameters (host, port, user, password) to `use_django_db: true`, which would have dispatcherd reuse Django's database connection. The very next day, commit 3a8f7d5 (titled simply "Fix") reverted this back to explicit connection parameters because `use_django_db` didn't work for local development testing.
- **Insight**: The `use_django_db` approach is cleaner in theory (single source of truth for database config) but dispatcherd may run in a different process or thread context where Django's connection isn't available. The explicit config duplicates the connection details but is more reliable. This is a case where DRY (Don't Repeat Yourself) loses to operational reliability.

### K8s manifests standardized to port 5432
- **Repo**: ansible/metrics-service
- **Commits**: 6059d8c (#45)
- **What happened**: Kubernetes configmaps and deployments were updated from port 55432 to 5432, consistent with the earlier docker-compose and CI changes.
- **Insight**: This completes the port standardization that started with the Dynaconf introduction. All environments (local dev, Docker, CI, k8s) now use port 5432 for PostgreSQL.

### roles.sql extended to create `metrics_service` user and database
- **Repo**: ansible/metrics-utility
- **Commits**: 5f436cb (#279)
- **What happened**: The `tools/docker/roles.sql` init script (which creates the `myuser` PostgreSQL role and `awx` database for the Docker Compose development environment) was extended to also create a `metrics_service` user and database. This enables developers to run the metrics service against the same Docker Compose PostgreSQL instance without additional setup.
- **Insight**: When the development Docker Compose environment serves multiple services (CLI and metrics service), adding their database users and databases to the shared init script reduces setup friction for developers working across both codebases.

### SQLite references removed from codebase
- **Repo**: ansible/metrics-service
- **Commits**: 597fd34 (#62)
- **What happened**: The `apps/tasks/apps.py` had a vendor-conditional query (`connection.vendor == "sqlite"` / `"postgresql"` / else MySQL) for checking if the tasks table exists. This was simplified to only the PostgreSQL query. A test that asserted the database engine could be either PostgreSQL or SQLite was updated to assert only PostgreSQL.
- **Insight**: With PostgreSQL as the only supported database (since cb58dc0 #11), keeping SQLite/MySQL code paths was dead code that could mislead developers into thinking those databases were supported. Removing them makes the codebase's database requirements explicit.

### Kubernetes manifests removed as unused template leftovers
- **Repo**: ansible/metrics-service
- **Commits**: d72f17e (#68)
- **What happened**: The entire `manifests/base/apps/metrics-service/k8s/` directory was deleted: configmaps.yaml, deployments.yaml, services.yaml, secrets.yaml, serviceaccounts.yaml, roles.yaml, rolebindings.yaml, and the kustomization.yaml that tied them together. The README section referencing these manifests was also removed.
- **Insight**: These manifests were carried over from the service template and had never been updated for the actual service requirements. They contained stale configuration: mixed-case env vars (`metrics_service_REDIS_URL` and `METRICS_SERVICE_DB_HOST` in the same file), references to removed Redis, the old `METRICS_SERVICE_ENV` instead of `METRICS_SERVICE_MODE`, and hardcoded credentials. Real Kubernetes deployment for AAP is handled by the operator, not by hand-managed manifests in the service repo.

### Dockerfile labels corrected from metrics-utility to metrics-service
- **Repo**: ansible/metrics-service
- **Commits**: 4b2bc5e (#94)
- **What happened**: The Dockerfile `LABEL` directives were updated from `com.redhat.component="metrics-utility"` / `name="metrics-utility"` / `cpe="cpe:/a:redhat:metrics_utility:..."` to the correct `metrics-service` values. The labels had been copied from the metrics-utility project and never updated.
- **Insight**: Container labels affect Red Hat certification scanning and vulnerability tracking. Wrong CPE identifiers can cause security advisories to be associated with the wrong product. Labels should be verified when creating a new service repo from an existing project.

### Dockerfile rebuilt for source-only builds and SBOM compliance
- **Repo**: ansible/metrics-service
- **Commits**: e09243d (#95)
- **What happened**: The Dockerfile was significantly expanded to build all Python dependencies from source (no binary wheels). `PIP_NO_BINARY=:all:` was set as an environment variable. System dependencies were expanded to include `gcc`, `gcc-c++`, `make`, `python3.12-devel`, `postgresql-devel`, `libpq-devel`, `openldap-devel`, `openssl-devel`, `libffi-devel`, `rust`, `cargo`, and `redhat-rpm-config`. The `pip install` command was updated to use `--no-binary :all:`. Dev requirements installation was removed from the production image. Cachi2 hermetic build support was added (`if [ -f /cachi2/cachi2.env ]; then source /cachi2/cachi2.env; fi`). In `pyproject.toml`, `psycopg[binary]` changed to `psycopg[c]` (C extension built from source) and `psycopg2-binary` changed to `psycopg2` (source build). Tekton pipeline configs were updated to disable binary wheels during prefetch.
- **Insight**: Red Hat's SBOM (Software Bill of Materials) compliance requires that all components in a container image be traceable to source code. Binary wheels like `psycopg2-binary` contain pre-compiled C code that can't be verified by SBOM tools. Building from source is slower but provides full provenance. The Rust toolchain is needed because the `cryptography` package builds its Rust components from source.

### django-ansible-base pin relaxed and switched to uv git source
- **Repo**: ansible/metrics-service
- **Commits**: e09243d (#95)
- **What happened**: `django-ansible-base` was changed from `==2025.10.20` to `>=2025.12.12` in `pyproject.toml`, while `[tool.uv.sources]` was updated from `rev = "devel"` (branch) to a specific commit hash. The comment explains: "Use `uv sync` so `[tool.uv.sources]` applies; plain `pip install .` will use latest from PyPI."
- **Insight**: The dual pin approach (minimum version in `pyproject.toml` + specific commit in `[tool.uv.sources]`) serves two audiences: development uses the git commit via `uv sync`, while production builds use the PyPI version via `pip install`. This avoids the issue where a `devel` branch reference in `uv.lock` conflicts with `requirements-pinned.txt`.

### Rapid Dockerfile iteration for Konflux source-only builds (7 PRs in 4 days)
- **Repo**: ansible/metrics-service
- **Commits**: 095d0f0 (#98), 7c8c0c0 (#99), 400b419 (#100), 4672f09 (#102), 204de50 (#103), 72c8a74 (#104)
- **What happened**: Between Feb 12-16, seven PRs iterated on the Dockerfile and requirements to get Konflux hermetic builds working. The sequence was: (1) #98 removed the global `PIP_NO_BINARY=:all:` from the Dockerfile to unblock builds, (2) #99 updated labels to the `ansible-automation-platform-tech-preview/metrics-service-rhel9` format for Konflux certification, (3) #100 re-added `--no-binary :all:` as a directive in `requirements-build.txt` instead of a Dockerfile env var (so Cachi2 prefetch respects it), (4) #102 was the same change re-applied (appears to have been reverted/rebased), (5) #103 added `packaging>=20.0` as a dependency because setuptools-scm needed it during source builds, (6) #104 was the comprehensive fix that replaced the blanket `--no-binary :all:` with targeted `--no-binary` for only cryptography/psycopg packages, introduced `requirements-build-extra.txt` for build-time deps (pytest-runner, setuptools-scm, wheel), added a `Dockerfile.dev` for fast local builds using binary wheels, added Hermeto/Cachi2 offline install handling with django-ansible-base git URL rewriting to local tarballs, removed `-e .` from requirements-build.txt (incompatible with hermetic builds), and pinned version to `1.0.0` in pyproject.toml.
- **Insight**: The blanket `--no-binary :all:` approach failed because many packages (Django, pandas, numpy) are painful or impossible to build from source in a hermetic environment. The targeted approach (source-only for crypto/psycopg, binaries for everything else) was the pragmatic solution. The `Dockerfile.dev` split acknowledges that production compliance requirements (source builds, SBOM traceability) shouldn't slow down local development. The Hermeto git URL rewriting (`sed` to convert `git+https://` to `file:///cachi2/deps/pip/`) is a fragile but necessary workaround for hermetic builds that can't fetch from the network.

### Dockerfile labels updated for Konflux tech-preview naming
- **Repo**: ansible/metrics-service
- **Commits**: 7c8c0c0 (#99)
- **What happened**: Labels changed from `com.redhat.component="metrics-service"` / `name="metrics-service"` to `com.redhat.component="ansible-automation-platform-tech-preview-metrics-service-rhel9"` / `name="ansible-automation-platform-tech-preview/metrics-service-rhel9"`. Notably, the CPE label was set to `cpe:/a:redhat:metrics_utility:1.0::rhel9` (using metrics_utility, not metrics_service).
- **Insight**: Konflux label requirements follow the AAP naming convention for tech-preview components. The CPE still referencing `metrics_utility` (after the previous fix in #94 changed it to `metrics-service`) suggests either an intentional alignment with the parent product's CPE or another copy-paste oversight.

### Docker entrypoint split into init container script
- **Repo**: ansible/metrics-service
- **Commits**: 120e333 (#115)
- **What happened**: The monolithic `docker-entrypoint.sh` (which did database readiness waiting, migrations, init-default-settings, init-service-id, init-system-tasks, and collectstatic) was split. Database readiness, migrations, and all `init-*` commands moved to a new `scripts/init.sh`. The entrypoint was reduced to just `collectstatic` (with a FIXME noting it should move to build time) plus `exec "$@"`. The entrypoint also switched from bash to sh (`#!/bin/sh`).
- **Insight**: This split is the prerequisite for running separate init/web/dispatcher/scheduler containers. Init tasks (migrations, seeding) should run once before any service starts, not on every container restart. The bash-to-sh switch reduces the runtime dependency (Alpine/UBI images may not have bash).

### Docker-compose split into 4 containers (init + web + dispatcher + scheduler)
- **Repo**: ansible/metrics-service
- **Commits**: 83b2d93 (#117)
- **What happened**: The single `metrics-service` container in docker-compose was replaced by four containers: `metrics-service-init` (runs `scripts/init.sh`, exits), `metrics-service-web` (runs `runserver`), `metrics-service-dispatcher` (runs `run_dispatcherd`), and `metrics-service-scheduler` (runs `run_task_scheduler`). All three service containers use `depends_on: metrics-service-init: condition: service_completed_successfully` to ensure init finishes first. Each container gets only the env vars it needs (e.g., dispatcher gets `awx` DB config, web doesn't). The Procfile was deleted. Collectstatic moved from the entrypoint to the Dockerfile build (`RUN python manage.py collectstatic --noinput --clear`), making the entrypoint a pure passthrough (`exec "$@"`). All containers use `Dockerfile.dev` for faster local builds. Bind mount excludes `.venv` and uses tmpfs for egg-info.
- **Insight**: This reverses the earlier consolidation (#45) that merged dispatcher into a single container. The four-container architecture mirrors production Kubernetes deployments: init container for one-time setup, separate scaling for web/dispatcher/scheduler. The `service_completed_successfully` condition ensures clean ordering. Moving collectstatic to build time eliminates a runtime step that could fail and is idempotent anyway. The per-container env var scoping (dispatcher gets AWX DB, web doesn't) follows the principle of least privilege.

### Production Docker architecture: Nginx + Gunicorn + multi-container orchestration
- **Repo**: ansible/metrics-service
- **Commits**: 531b608 (#129)
- **What happened**: A massive overhaul (-2950/+1522 lines) that established the production Docker architecture. Key changes: (1) The Dockerfile was rewritten for production with Nginx for TLS termination/reverse proxy, pre-built binary wheels (no more source compilation), and Gunicorn as the WSGI server. Build tools (gcc, rust, cargo, etc.) were removed from the production image, replaced by just `nginx`. (2) Three production docker-compose files were added: `docker-compose.production.yml` (multi-container: init, web, dispatcherd, scheduler), `docker-compose.prod.single.yml` (single container for simpler deployments). (3) Per-container entrypoint scripts were added: `entrypoint-init.sh`, `entrypoint-web.sh` (starts Nginx + Gunicorn), `entrypoint-dispatcherd.sh`, `entrypoint-scheduler.sh`. (4) Nginx config includes TLS termination (8443), HTTP (8080), WebSocket support, security headers, and proxying to Gunicorn on 127.0.0.1:8000. (5) Self-signed cert generation script (`generate-certs.sh`) for development/testing. (6) `whitenoise` middleware added for static file serving. (7) A `metrics_service/cli.py` entry point was added (like `aap-eda-manage`) providing `metrics-service run/dispatcherd/scheduler/init-*` subcommands. (8) Management command gained `--gunicorn-workers` and `--dispatcher-workers` arguments. (9) ALLOWED_HOSTS parsing enhanced to handle both JSON arrays and comma-separated lists. (10) `.dockerignore` added for build efficiency.
- **Insight**: The architecture splits into "all-in-one" (default Dockerfile entrypoint starts Nginx + runs CMD) and "split" (docker-compose overrides with per-service entrypoints). Non-privileged ports (8080/8443/8000) allow running as UID 1001. The `cli.py` entry point (registered as `[project.scripts] metrics-service`) provides a Python-interpreter-agnostic command, avoiding the `python` vs `python3.12` ambiguity in entrypoint scripts.

### Red Hat certification compliance: licenses directory and reDOS fix
- **Repo**: ansible/metrics-service
- **Commits**: 9805267 (#130)
- **What happened**: Added a `licenses/` directory containing the Apache 2.0 LICENSE file, and `COPY --chown=root:root licenses /licenses` in both `Dockerfile` and `Dockerfile.dev`. This satisfies the Red Hat preflight `HasLicense` check. Also: the `url_for()` function in dashboard views was refactored from `re.sub(r"/+", "/", ...)` to a string-split-and-join approach to avoid potential reDOS (regular expression denial of service) from unsanitized input. Test settings switched `SECRET_KEY` to read from an env var with a hardcoded fallback, avoiding SAST (static analysis security testing) hardcoded-secret findings.
- **Insight**: Red Hat container certification has specific requirements: `/licenses` directory must exist and contain license files, and preflight checks verify this. The reDOS fix is notable -- the original `re.sub(r"/+", "/", path)` regex was flagged by security scanners even though it's not actually exploitable (the pattern has no backtracking), but replacing it with `str.split("/")/join` is both safer and clearer.

### Docker entrypoint scripts refined with venv detection and base image pinning
- **Repo**: ansible/metrics-service
- **Commits**: a52e7a9 (#131)
- **What happened**: Cleanup and hardening of Docker configurations. The `Dockerfile.dev` base image was pinned to a specific version (`ubi9/python-312:9-1739552823`) instead of `latest` for reproducibility. RUN commands were chained for fewer layers. Entrypoint scripts were updated to check for virtualenv presence before executing (`if [ -d "$VENV" ]`) for compatibility between dev (venv) and production (system Python) environments. The test-nginx-setup.sh (274 lines) was deleted as it was a development artifact. The `metrics_service/cli.py` gained Django management command handling for `makemigrations`, `migrate`, `createsuperuser`, and `shell`.
- **Insight**: Pinning base images to specific digests/versions is important for reproducible builds but creates a maintenance burden (manual updates). The venv detection pattern in entrypoint scripts solves the dev/prod discrepancy where `Dockerfile.dev` uses `uv` with a virtualenv but production installs packages system-wide.

### Dispatcherd max workers reduced to 1, then restored to 4
- **Repo**: ansible/metrics-service
- **Commits**: 9a0feaa (#148), ccf9494 (#167)
- **What happened**: In #148, workers were reduced from 4 to 1 as a band-aid for concurrency bugs. In #167, the real fix was applied (atomic task claiming, advisory locks, retry delays) and workers were restored to 4.
- **Insight**: Reducing concurrency is a valid emergency measure but should always be treated as temporary. The underlying bugs needed proper fixes at the database and application level.

### Supervisord added for per-container process management
- **Repo**: ansible/metrics-service
- **Commits**: cf7819a (#161)
- **What happened**: Entrypoint scripts for web, dispatcherd, and scheduler containers were rewritten to use supervisord for process management. New `scripts/supervisord/supervisord_{web,dispatcherd,scheduler}.conf` files were added. The monolithic bash entrypoint scripts (100+ lines each) were reduced to just launching supervisord. The old `entrypoint-init.sh` and `generate-certs.sh` scripts were removed. Docker-compose files were updated for readability.
- **Insight**: Supervisord provides automatic process restart, health monitoring, and clean signal handling that custom bash scripts can't reliably achieve. Each container now has a supervisord config that defines the exact processes to run (e.g., web container runs nginx + gunicorn via supervisord). This is the standard pattern for containers that need to run multiple processes.

### Default dispatcherd workers changed to 4 in Dockerfile
- **Repo**: ansible/metrics-service
- **Commits**: 4892777 (#187)
- **What happened**: The Dockerfile CMD was updated from `--workers 1` to `--workers 4` for the `metrics_service run` command. This aligns the container default with the `dispatcherd.yaml` max_workers setting (restored to 4 in #167 after the atomic claims fix).
- **Insight**: The Dockerfile had been left at 1 worker from the band-aid fix in #148. With the proper concurrency fixes in place (#167: atomic claims, advisory locks, retry delays), 4 workers is the intended production configuration.

### Production startup validation re-enabled with actionable error messages
- **Repo**: ansible/metrics-service
- **Commits**: 956923d (#193)
- See [settings_and_configuration.md](settings_and_configuration.md#production-startup-validation-re-enabled-with-actionable-error-messages) for the full entry. Summary: Dynaconf `validation=True` re-enabled after being disabled in #143. All four production validators uncommented with actionable error messages specifying exact env vars to set. This concluded a 5-PR validation saga (#26 -> #129 -> #137 -> #143 -> #193).

### Compose environments merged: metrics-service containers added behind profiles
- **Repo**: ansible/metrics-utility
- **Commits**: 5faa1bb (#433)
- **What happened**: The metrics-utility Docker Compose file was expanded to include metrics-service containers behind Docker Compose profiles. Key changes: (1) A YAML anchor `x-metrics-service` defines the shared build/volume/env config for service containers, with `&metrics-service-env` for environment inheritance. (2) Five new service containers were added: `metrics-service-init` (profile: `service`), `metrics-service-web` (profile: `service`), `metrics-service-dispatcher` (profile: `service`), `metrics-service-scheduler` (profile: `service`), and `metrics-service-pytest` (profile: `pytest-svc`). (3) The Makefile was significantly simplified: `CONTAINER_ENGINE ?= docker` was replaced by `COMPOSE_CMD ?= $(shell command -v podman-compose 2>/dev/null || echo "docker compose")` for automatic podman/docker detection. Separate `pcompose`/`pclean`/`ppsql` targets were removed. New targets: `compose-pytest`, `compose-env`, `compose-service`, `compose-pytest-svc`. (4) Performance test tools were moved from metrics-service into `tools/{service_perf,dashboard_perf}` with path resolution updated to find `../metrics-service` as a sibling repo. (5) The metrics-utility pytest container replaced `rsync` (not available in mirror.gcr.io/python) with `tar` for file copying, removed unsupported `uid=` from tmpfs, and replaced `sed` patching of mock_awx settings with env vars. (6) Mock server URLs now use env vars (`MOCK_SEGMENT_URL`, `MOCK_PROMETHEUS_URL`) for container networking. (7) Coverage target enhanced with `--cov-branch` and `--cov-report=xml`.
- **Insight**: Auto-detecting podman-compose vs docker-compose via `command -v` eliminates the need for separate targets per container engine and works transparently for both Docker and Podman users. YAML anchors keep 5+ service definitions DRY while allowing per-container overrides.

### MinIO replaced by SeaweedFS for S3-compatible dev/CI storage
- **Repo**: ansible/metrics-utility
- **Commits**: c4fcac6 (#488)
- **What happened**: MinIO was replaced by SeaweedFS in both the Docker Compose file and CI workflow. SeaweedFS runs in `weed mini` mode (single binary bundling master+volume+filer+S3 gateway). Key differences: (1) Zero setup -- no separate `mc` (MinIO client) container, no user/bucket/permission creation steps. Credentials and bucket are configured via env vars directly on the SeaweedFS container (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`). (2) S3 endpoint port changed from 9000 to 8333. (3) Uses of the `mc` CLI were replaced by `awscli`'s `aws` command. (4) The healthcheck uses `curl -s` without `-f` because the S3 endpoint returns 403 for unauthenticated requests (curl -f treats 4xx as failure). (5) The `minio-setup` init container (which created buckets, users, and access keys) was eliminated entirely. No Python code or tests were modified -- boto3 is provider-agnostic.
- **Insight**: SeaweedFS's `weed mini` mode eliminates the init-container dance required by MinIO (alias setup, bucket creation, user/policy/key creation). For dev/CI environments where S3 is just a storage backend, the simpler setup reduces compose complexity and startup time. The provider-agnostic nature of boto3 means the application code is unaffected by the swap.

## Superseded / Semi-Obsolete

### MinIO used for S3-compatible storage in dev/CI
- **Repo**: ansible/metrics-utility
- Superseded by c4fcac6 (#488) which replaced MinIO with SeaweedFS. The MinIO setup required a separate `mc` init container for bucket/user/key creation; SeaweedFS handles this via env vars with zero setup.

### Separate Makefile targets for docker vs podman (pcompose, pclean, ppsql)
- **Repo**: ansible/metrics-utility
- Superseded by 5faa1bb (#433) which replaced `CONTAINER_ENGINE ?= docker` and separate `pcompose`/`pclean`/`ppsql` targets with auto-detected `COMPOSE_CMD ?= $(shell command -v podman-compose 2>/dev/null || echo "docker compose")`. The unified targets now work with both Docker and Podman without user intervention. **Supersedes** the `CONTAINER_ENGINE` variable from #198.

### Requirements.txt-based dependency management
- **Repo**: ansible/metrics-service
- The initial Dockerfile used `pip install -r requirements.txt`. This was replaced by UV-based dependency management (commit ee93077), then by UV inside the container (d85322e), and finally back to plain pip from `requirements-build.txt` (6059d8c #45).

### docker-entrypoint.sh deleted and recreated
- **Repo**: ansible/metrics-service
- The entrypoint script was deleted in c6947ce (#14) as part of the task refactor, then recreated in d85322e (#18) with improved database readiness checking.

### UV as container runtime dependency
- **Repo**: ansible/metrics-service
- UV was added to the Docker container in d85322e (#18) and removed in 6059d8c (#45). UV is now a development-only tool; the container uses plain pip with `requirements-build.txt`.

### Single container for all services (web + dispatcher + scheduler)
- **Repo**: ansible/metrics-service
- The combined single-container approach from 6059d8c (#45) was reversed in 83b2d93 (#117), splitting docker-compose back to 4 containers: init, web, dispatcher, scheduler. The single container was convenient for development but doesn't reflect production deployment topology.

### Monolithic docker-entrypoint.sh with migrations and init tasks
- **Repo**: ansible/metrics-service
- The entrypoint that handled database waiting, migrations, and all init commands was split in 120e333 (#115). Init logic moved to `scripts/init.sh` for use by the init container; the entrypoint became a passthrough.

### collectstatic in docker-entrypoint.sh
- **Repo**: ansible/metrics-service
- Moved from the entrypoint to the Dockerfile build step (`RUN python manage.py collectstatic`) in 83b2d93 (#117). Static files are collected at build time, not on every container start.

### Dockerfile labels as metrics-service (simple naming)
- **Repo**: ansible/metrics-service
- Updated to the full Konflux tech-preview format (`ansible-automation-platform-tech-preview-metrics-service-rhel9`) in 7c8c0c0 (#99).

### Global --no-binary :all: for source-only builds
- **Repo**: ansible/metrics-service
- The blanket source-only approach from e09243d (#95) was replaced by targeted `--no-binary` for only cryptography/psycopg packages in 72c8a74 (#104). Building Django, pandas, numpy from source was impractical in hermetic builds.

### Procfile for process management
- **Repo**: ansible/metrics-service
- Deleted in 83b2d93 (#117) when docker-compose switched to separate containers with explicit commands.

### Source-only builds in production Dockerfile
- **Repo**: ansible/metrics-service
- The production Dockerfile was rewritten in 531b608 (#129) to use pre-built binary wheels (`--prefer-binary --only-binary :all:`) instead of building from source. Build tools (gcc, rust, cargo, etc.) were removed. This reverses the SBOM-compliance source-only approach from e09243d (#95) and 72c8a74 (#104). The Konflux/Tekton pipeline configs (`.tekton/`) were also deleted, suggesting a shift in the build pipeline approach.

### Separate requirements files for Konflux builds
- **Repo**: ansible/metrics-service
- All legacy requirements files (`dev-requirements.txt`, `requirements-build.txt`, `requirements-build-extra.txt`, `requirements-pinned.txt`, `requirements.txt`, `REQUIREMENTS.md`, `rpms.in.yaml`, `rpms.lock.yaml`) were deleted in 531b608 (#129). The sync-requirements workflow and script were also removed. Dependencies are now installed directly from `pyproject.toml` via `pip install .` in the production Dockerfile.

### psycopg[c] and psycopg2 (source builds) for SBOM compliance
- **Repo**: ansible/metrics-service
- Reverted to `psycopg[binary]` and `psycopg2-binary` in 531b608 (#129) since the production Dockerfile now uses binary wheels.

### Dockerfile with source-compilation build tools
- **Repo**: ansible/metrics-service
- The production Dockerfile no longer includes gcc, rust, cargo, openssl-devel, etc. as of 531b608 (#129). Only runtime dependencies (nginx) are installed.

### Kubernetes manifests in manifests/
- **Repo**: ansible/metrics-service
- Removed in d72f17e (#68). The template-origin k8s manifests were never updated for the actual service and contained stale configuration. AAP operator handles real Kubernetes deployment.

### Standalone docker-compose removed, unified compose adopted
- **Repo**: ansible/metrics-service
- **Commits**: ff6e9fb (#266)
- **What happened**: The standalone `docker-compose.yml` in metrics-service (which never had AWX DB support) was removed. All dev workflows now use the unified compose in `../metrics-utility/` via Makefile targets: `make compose-service` (runs the service), `make compose-pytest-svc` (runs service tests). Performance test tools were moved to metrics-utility's `tools/` directory. The `Dockerfile.dev` was cleaned up significantly: added `.venv/bin` to `PATH` (broken since 531b608 introduced the venv but never updated PATH), set `VIRTUAL_ENV`, made `.venv` writable for `uv sync`, and removed unused `supervisord` and `entrypoint-*.sh` COPYs (compose services now use inline `manage.py` commands). A `.coderabbit.yaml` was added to disable the UBI9 "avoid :latest" lint rule. The Makefile gained `help`, `test`, `coverage`, `lint`, `fix` targets.
- **Insight**: A unified compose file in the library repo (metrics-utility) that supports both library and service development via profiles eliminates the need for each repo to maintain its own compose file. The service repo only needs Makefile targets that delegate to the shared compose. This ensures consistent database setup (roles, schemas) across both repos. **Extends** the unified compose work in metrics-utility #433.
