# Docker and Deployment

### Docker Compose environment for local development with PostgreSQL and MinIO
- **Repo**: ansible/metrics-utility
- **Commits**: b6879b0 (#71), be761a3 (#52)
- **What happened**: A `tools/docker/docker-compose.yaml` was created with four services: (1) `postgres` initialized with the AWX schema dump (`latest.sql`) and role definitions (`roles.sql`), (2) `minio` for S3-compatible storage, (3) `minio-setup` that creates buckets, users, and extracts access keys to a shared tmpfs volume, (4) `metrics-utility` that syncs the source code into a tmpfs (to avoid polluting the source dir), patches the DB hostname, installs dependencies with uv, and runs gather. The AWX schema files were moved from `metrics_utility/test/test_data/schemas/awx/` to `tools/docker/` to co-locate them with the compose file. The metrics-utility container uses `quay.io/fedora/python-311` and copies source to tmpfs because uv had trouble installing when a pre-existing `.venv` was present.
- **Insight**: The tmpfs trick (copy source to tmpfs, build there) works around uv/pip issues with pre-existing virtual environments in mounted volumes, and avoids polluting the host source tree with build artifacts.

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

### Docker Compose simplified: profiles, static credentials, no shared volumes
- **Repo**: ansible/metrics-utility
- **Commits**: 744d061 (#84)
- **What happened**: The Docker Compose setup was significantly simplified: (1) the deprecated `version: '3.8'` key was removed, (2) MinIO setup switched from dynamically extracting credentials via `mc admin user svcacct add` to static credentials via `mc admin accesskey create local mynewuser --access-key myuseraccesskey --secret-key myusersecretkey`, eliminating the `minio_config` shared volume and `source /tmp/minio_env.sh` pattern, (3) the `metrics-utility` and `metrics-utility-env` containers were made non-default via Docker Compose `profiles` (`pytest` and `env` respectively), so `docker compose up` only starts the infrastructure (postgres, minio), (4) MinIO data was moved from a named volume (`minio_data`) to tmpfs to fix issues when running the second time, (5) tmpfs permissions were changed to `uid=1001` to fix `uv run pytest: permission denied`.
- **Insight**: Using static MinIO access keys instead of dynamically generating them removed an entire coordination layer (shared volume, env file sourcing, shell parsing) -- simpler is better for dev infrastructure.

### roles.sql extended to create `metrics_service` user and database
- **Repo**: ansible/metrics-utility
- **Commits**: 5f436cb (#279)
- **What happened**: The `tools/docker/roles.sql` init script (which creates the `myuser` PostgreSQL role and `awx` database for the Docker Compose development environment) was extended to also create a `metrics_service` user and database. This enables developers to run the metrics service against the same Docker Compose PostgreSQL instance without additional setup.
- **Insight**: When the development Docker Compose environment serves multiple services (CLI and metrics service), adding their database users and databases to the shared init script reduces setup friction for developers working across both codebases.

