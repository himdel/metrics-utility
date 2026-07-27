# Settings and Configuration
### AWX_PATH env var for locating Controller modules
- **Repo**: ansible/metrics-utility
- **Commits**: 1b95f39, 03a5640
- **What happened**: Initially the AWX path was hardcoded to `/awx_devel`. PR 1b95f39 introduced `AWX_PATH` env var (default `/awx_devel`). PR 03a5640 improved this to first try importing `awx` directly (works when installed in a venv), falling back to `AWX_PATH` only if the import fails. This two-step approach supports both venv installations and custom paths.
- **Insight**: Try the standard import path first before falling back to env-var-configured paths -- it makes the tool work out of the box in more deployment scenarios.

### METRICS_UTILITY_SHIP_TARGET controls where collected data goes
- **Repo**: ansible/metrics-utility
- **Commits**: 6e60790 (#9)
- **What happened**: PR #9 introduced `METRICS_UTILITY_SHIP_TARGET` env var with two values: `crc` (ship to console.redhat.com) and `directory` (store in local filesystem). Each target has its own required env vars: `crc` needs `METRICS_UTILITY_BILLING_PROVIDER`, `METRICS_UTILITY_BILLING_ACCOUNT_ID`, `METRICS_UTILITY_RED_HAT_ORG_ID`; `directory` needs `METRICS_UTILITY_SHIP_PATH`.
- **Insight**: The env-var-based configuration pattern (rather than CLI flags) was chosen because these settings are typically set once in the environment for cron-based periodic collection.

### METRICS_UTILITY_BILLING_PROVIDER gates provider-specific env vars
- **Repo**: ansible/metrics-utility
- **Commits**: 6e60790 (#9)
- **What happened**: The `_handle_crc_ship_target()` method reads `METRICS_UTILITY_BILLING_PROVIDER` and based on its value (initially only `aws`) requires additional provider-specific env vars like `METRICS_UTILITY_BILLING_ACCOUNT_ID`. Unknown providers raise `MissingRequiredEnvVar`. The billing params are injected into the config.json inside the tarball.
- **Insight**: Provider-specific configuration is validated at startup and embedded in the data payload, so downstream consumers can identify the billing context without environment access.

### Report generation configured entirely through env vars
- **Repo**: ansible/metrics-utility
- **Commits**: 6e60790 (#9)
- **What happened**: The `build_report` command reads numerous `METRICS_UTILITY_REPORT_*` env vars: `REPORT_TYPE`, `PRICE_PER_NODE`, `REPORT_SKU`, `REPORT_SKU_DESCRIPTION`, `REPORT_H1_HEADING`, `REPORT_COMPANY_NAME`, `REPORT_EMAIL`, `REPORT_RHN_LOGIN`, `REPORT_COMPANY_BUSINESS_LEADER`, `REPORT_COMPANY_PROCUREMENT_LEADER`. These are all consumed in the management command and passed as `extra_params` to the report engine.
- **Insight**: The large number of report-specific env vars reflects that reports are company-customized CCSP billing documents, not generic analytics.

### CRC shipping switched from Controller settings to dedicated env vars
- **Repo**: ansible/metrics-utility
- **Commits**: eeb35bd (#14)
- **What happened**: The CRC package shipping originally read `AUTOMATION_ANALYTICS_URL`, `REDHAT_USERNAME`, and `REDHAT_PASSWORD` from Django settings (Controller's config). PR #14 replaced these with dedicated env vars: `METRICS_UTILITY_CRC_INGRESS_URL`, `METRICS_UTILITY_CRC_SSO_URL`, `METRICS_UTILITY_SERVICE_ACCOUNT_ID`, `METRICS_UTILITY_SERVICE_ACCOUNT_SECRET`, and `METRICS_UTILITY_PROXY_URL`. This also introduced service-account OAuth authentication (SSO token exchange) as the primary auth mode instead of username/password.
- **Insight**: Decoupling from Controller's Django settings to standalone env vars was necessary for service-account (OAuth client_credentials) authentication, which is the production auth method for CRC ingress.

### CCSPv2 report adds end-user and PO env vars
- **Repo**: ansible/metrics-utility
- **Commits**: 9272f1d (#17)
- **What happened**: The CCSPv2 report type added new env vars: `METRICS_UTILITY_REPORT_PO_NUMBER`, `METRICS_UTILITY_REPORT_END_USER_COMPANY_NAME`, `METRICS_UTILITY_REPORT_END_USER_CITY`, `METRICS_UTILITY_REPORT_END_USER_STATE`, `METRICS_UTILITY_REPORT_END_USER_COUNTRY`. These are specific to the CCSPv2 (NA Direct) reporting template that requires end-user company details.
- **Insight**: Different report types (CCSP vs CCSPv2) need different sets of env vars -- CCSP needs business/procurement leaders, CCSPv2 needs end-user location details.

### METRICS_UTILITY_OPTIONAL_COLLECTORS gates expensive data collection
- **Repo**: ansible/metrics-utility
- **Commits**: 9272f1d (#17), 8ec8cdf (#23)
- **What happened**: The `main_jobevent` collector (content usage data) is gated behind `METRICS_UTILITY_OPTIONAL_COLLECTORS` env var, defaulting to `main_jobevent`. When shipping to CRC, docs recommend setting it to empty string (`""`) to disable the expensive jobevent collection. The collector checks `if 'main_jobevent' not in optional_collectors(): return None`.
- **Insight**: Optional collectors with an opt-out mechanism allow the same codebase to serve both detailed local reports (with jobevent data) and lightweight CRC uploads (without it).

### RENEWAL_GUIDANCE report uses `controller_db` ship target to read directly from DB
- **Repo**: ansible/metrics-utility
- **Commits**: 8ec8cdf (#23), f388cae (#24), 6467590 (#194)
- **What happened**: Unlike CCSP/CCSPv2 which read from collected tarballs via `directory` ship target, the RENEWAL_GUIDANCE report type uses `METRICS_UTILITY_SHIP_TARGET=controller_db` to read directly from Controller's database (the `main_hostmetric` and `main_host` tables). This required a new `ExtractorControllerDB` class that queries the DB with raw SQL and marker-based pagination. As of #194, validation enforces that `controller_db` is the only allowed ship target for RENEWAL_GUIDANCE -- using `directory` or `s3` with RENEWAL_GUIDANCE now raises a validation error during `build_report` (but not during `gather`, since gather doesn't use report_type).
- **Insight**: The `controller_db` ship target exists because renewal guidance needs host facts and host metrics that aren't collected in the normal billing tarball pipeline -- and now validation enforces this constraint at startup rather than letting it fail with a confusing error deep in the pipeline.

### Report sheet selection via METRICS_UTILITY_OPTIONAL_CCSP_REPORT_SHEETS
- **Repo**: ansible/metrics-utility
- **Commits**: 574d9eb
- **What happened**: CCSPv2 reports can include multiple optional worksheets. A new env var `METRICS_UTILITY_OPTIONAL_CCSP_REPORT_SHEETS` allows selecting which sheets to build, with a default of `managed_nodes,usage_by_organizations,usage_by_collections,usage_by_roles,usage_by_modules`. The `managed_nodes_by_organizations` sheet was added as an optional additional sheet.
- **Insight**: Making report sheets configurable via env var allows customers to customize their CCSP reports without code changes.

### METRICS_UTILITY_ORGANIZATION_FILTER for scoping CCSPv2 reports
- **Repo**: ansible/metrics-utility
- **Commits**: b721f52
- **What happened**: A new env var `METRICS_UTILITY_ORGANIZATION_FILTER` was added to limit CCSPv2 reports to specific Controller organizations. It accepts a semicolon-separated list of organization names (e.g. `"ACME;Test Org 1"`). When set, `job_host_summary_dataframe` is filtered to only include rows matching the specified organizations before building any report sheets. Events are not yet filtered (noted as a TODO in the code).
- **Insight**: Semicolon-separated rather than comma-separated was chosen because organization names can contain commas but are unlikely to contain semicolons.

### ccsp_summary added to default optional sheets, making the billing sheet skippable
- **Repo**: ansible/metrics-utility
- **Commits**: b721f52
- **What happened**: The default value of `METRICS_UTILITY_OPTIONAL_CCSP_REPORT_SHEETS` was updated to include `ccsp_summary` as the first item: `ccsp_summary,managed_nodes,usage_by_organizations,...`. This means the main "Usage Reporting" billing summary sheet is now opt-in/opt-out like all other sheets. For usage-history-only reports (non-CCSP billing), users set `METRICS_UTILITY_OPTIONAL_CCSP_REPORT_SHEETS='jobs,managed_nodes,usage_by_organizations,managed_nodes_by_organizations'` to exclude the billing summary.
- **Insight**: Adding `ccsp_summary` to the configurable sheet list (with backward-compatible default) was a low-risk way to enable non-billing use cases without creating a separate report type.

### S3 ship target requires bucket configuration env vars
- **Repo**: ansible/metrics-utility
- **Commits**: 1e86f8c
- **What happened**: The `s3` ship target requires: `METRICS_UTILITY_SHIP_PATH` (S3 key prefix, e.g. `metrics-utility/shipped_data`), `METRICS_UTILITY_BUCKET_NAME`, `METRICS_UTILITY_BUCKET_ENDPOINT`, `METRICS_UTILITY_BUCKET_ACCESS_KEY`, `METRICS_UTILITY_BUCKET_SECRET_KEY`. Optional: `METRICS_UTILITY_BUCKET_REGION` (needed for AWS S3 but not for S3-compatible stores like MinIO). The `SHIP_PATH` for S3 is a key prefix rather than a filesystem path, reusing the same env var name for consistency across ship targets.
- **Insight**: The S3 adapter supports any S3-compatible object storage (not just AWS), so `BUCKET_ENDPOINT` is required rather than assuming AWS, and `BUCKET_REGION` is optional.

### indirect_nodes added to METRICS_UTILITY_OPTIONAL_COLLECTORS, then renamed to match table
- **Repo**: ansible/metrics-utility
- **Commits**: 81e93b5 (#75), 7a8bea5 (#78)
- **What happened**: The `METRICS_UTILITY_OPTIONAL_COLLECTORS` env var gained a new recognized value: `indirect_nodes`. When included (e.g., `METRICS_UTILITY_OPTIONAL_COLLECTORS=main_jobevent,indirect_nodes`), the `indirect_nodes` collector runs and the dataframe engine processes indirect node data alongside direct nodes. The check was originally done at module load time in `metric_utils.py` via `INCLUDE_INDIRECT = ('indirect_nodes' in environs)`. In #78, the collector was renamed to `main_indirectmanagednodeaudit` (matching the DB table name) and the `INCLUDE_INDIRECT` constant was replaced with runtime `get_optional_collectors()` calls, making collector gating consistent: all optional collectors now use `'collector_name' in get_optional_collectors()`. The env var value also changed from `indirect_nodes` to `main_indirectmanagednodeaudit`.
- **Insight**: Naming optional collectors after their DB table (`main_indirectmanagednodeaudit`) rather than a shortened alias (`indirect_nodes`) makes the configuration self-documenting and consistent with `main_jobevent`.

### METRICS_UTILITY_DB_HOST for configurable mock_awx database hostname
- **Repo**: ansible/metrics-utility
- **Commits**: 968b4c8 (#88)
- **What happened**: The `mock_awx/settings/__init__.py` DB config had a hardcoded `HOST: 'localhost'` which worked in CI but not in Docker Compose (where PostgreSQL runs in a container named `postgres`). The fix introduced `METRICS_UTILITY_DB_HOST` env var with default `localhost`, used via `os.getenv('METRICS_UTILITY_DB_HOST', 'localhost')`.
- **Insight**: Database hostname must be configurable for test environments that run PostgreSQL either locally (CI) or in a container (Docker Compose) -- a single hardcoded value cannot serve both.

### Removed unused METRICS_UTILITY_BUCKET_ID and METRICS_UTILITY_BUCKET_KEY env vars
- **Repo**: ansible/metrics-utility
- **Commits**: b487ac2 (#131)
- **What happened**: The `build_report` command read `METRICS_UTILITY_BUCKET_ID` and `METRICS_UTILITY_BUCKET_KEY` env vars into `extra_params['s3_bucket_id']` and `extra_params['s3_bucket_key']`, but these were never used anywhere downstream. They appear to be remnants from an early S3 implementation that was replaced by `METRICS_UTILITY_BUCKET_ACCESS_KEY` and `METRICS_UTILITY_BUCKET_SECRET_KEY`. The dead reads were removed along with the README documentation for these vars.
- **Insight**: When adding new env var names to replace old ones, remove the old reads at the same time -- dead env var reads in code confuse operators into setting variables that do nothing.

### S3 env var error handling: report missing vars individually, warn about surplus vars
- **Repo**: ansible/metrics-utility
- **Commits**: 75a83bc (#129)
- **What happened**: The S3 ship target validation was improved in two ways: (1) Instead of a single generic "missing one of..." error message, each missing S3 env var (`METRICS_UTILITY_BUCKET_NAME`, `BUCKET_ENDPOINT`, `BUCKET_ACCESS_KEY`, `BUCKET_SECRET_KEY`, `SHIP_PATH`) is listed individually with a description (e.g., "METRICS_UTILITY_BUCKET_NAME - name of S3 bucket"). (2) New `handle_not_s3()` and `handle_not_crc()` functions were added that emit warnings when S3 or CRC env vars are set but the ship target doesn't use them (e.g., setting `METRICS_UTILITY_BUCKET_NAME` when `SHIP_TARGET=directory`). Similarly, `handle_crc_ship_target()` now warns if `METRICS_UTILITY_SHIP_PATH` is set (which CRC doesn't use). The validation functions also had the unused `ship_target` parameter removed from their signatures.
- **Insight**: Listing each missing env var individually with its purpose makes misconfiguration much easier to fix than a generic "missing one of these five vars" message; warning about surplus env vars catches copy-paste configuration errors.

### Early env var validation added to `add_arguments` via `handle_env_validation`
- **Repo**: ansible/metrics-utility
- **Commits**: 560c62d (#137)
- **What happened**: A centralized `handle_env_validation(method)` function was added that validates all env vars (`METRICS_UTILITY_REPORT_TYPE`, `METRICS_UTILITY_SHIP_TARGET`, `METRICS_UTILITY_SHIP_PATH`, `METRICS_UTILITY_OPTIONAL_COLLECTORS`, `METRICS_UTILITY_OPTIONAL_CCSP_REPORT_SHEETS`) before any command runs. It collects all errors into a list and raises a single `MissingRequiredEnvVar` with all problems joined by newlines, rather than failing on the first invalid var. Valid values are defined as constants (`VALID_REPORT_TYPES`, `VALID_SHIP_TARGET_BUILD`, `VALID_SHIP_TARGET_GATHER`, `VALID_COLLECTORS`, `VALID_SHEETS`). The validation was initially placed in `add_arguments()`, but this was later moved in #141. For `build`, `SHIP_PATH` must be an existing directory; for `gather`, a missing path only emits an info log.
- **Insight**: Collecting all env var validation errors and reporting them at once (rather than failing on the first) saves operators multiple fix-restart cycles when multiple env vars are misconfigured.

### Renewal guidance param validation: `--since` required, `--until` and `--month` forbidden
- **Repo**: ansible/metrics-utility
- **Commits**: 42464e0 (#142)
- **What happened**: The `validate_build_extra_params` function was refactored to validate parameters per report type. For `RENEWAL_GUIDANCE`: `--since` is required, `--until` and `--month` are forbidden, and `--ephemeral` is optional (validated by regex). For `CCSP`/`CCSPv2`: `--ephemeral` is forbidden, `--month` and `--since`/`--until` are mutually exclusive, and `--until` without `--since` is rejected. The previous validation used `report_type.startswith('RENEWAL_GUIDANCE')` which would have matched `RENEWAL_GUIDANCEv2` -- the fix uses exact membership checks (`report_type in {'RENEWAL_GUIDANCE'}`).
- **Insight**: Per-report-type parameter validation (what's required, what's forbidden, what's optional) is cleaner as a single function with report-type branches than as scattered helper functions -- each report type's rules are visible in one place.

### `build_report` defaults `--month` to last month when no date params provided
- **Repo**: ansible/metrics-utility
- **Commits**: 86087c4 (#147)
- **What happened**: When `build_report` was called without `--month`, `--since`, or `--until`, `handle_month(None)` already returned last month's date, but the command needed to know whether `--month` was explicitly provided (for path construction and validation). The fix simplified this: `handle_month` always computes the month (defaulting to last month when `None`), and the validation in `validate_build_extra_params` handles the conflict between `--month` and `--since`/`--until`. The `_parse_param` method was inlined since `parse_date_param` already handles `None`.
- **Insight**: When a command has a "default to last month" behavior, implement it in the month parser itself rather than in conditional logic at the call site -- this eliminates the need to track "was the param explicitly provided".

### METRICS_UTILITY_DEDUPLICATOR env var for selecting deduplication algorithm
- **Repo**: ansible/metrics-utility
- **Commits**: 54175a4 (#162), 1b2a5a4 (#171)
- **What happened**: A new `METRICS_UTILITY_DEDUPLICATOR` env var was added to explicitly select the deduplication algorithm. When unset or `None`, the deduplicator defaults based on report type (`ccsp` for CCSP/CCSPv2, `renewal` for RENEWAL_GUIDANCE). Valid values: `ccsp` (hostname-based dedup using `ansible_host_variable || host_name`), `renewal` (iterative multi-key matching), `ccsp-experimental` (serial-based dedup on top of hostname, CCSP/CCSPv2 only), `renewal-hostname` (hostname-only for renewal, RENEWAL_GUIDANCE only), `renewal-experimental` (hostname + serial dedup, RENEWAL_GUIDANCE only). The env var is read in `build_report` and passed via `extra_params['deduplicator']`.
- **Insight**: Making the deduplicator configurable via env var (rather than hardcoding per report type) allows the same report type to produce different dedup results, which is useful for comparing dedup strategies during validation and rollout.

### `infrastructure_summary` added to valid optional sheets
- **Repo**: ansible/metrics-utility
- **Commits**: 5c94421 (#169)
- **What happened**: The `VALID_SHEETS` set for CCSPv2 was updated to include `infrastructure_summary` as a valid value for `METRICS_UTILITY_OPTIONAL_CCSP_REPORT_SHEETS`. This sheet shows indirect managed nodes grouped by infrastructure type, device category, and device type.
- **Insight**: Adding new optional sheets requires updating `VALID_SHEETS` in validation.py so the env var validation doesn't reject the new sheet name.

### Environment variable naming went through three iterations in two days
- **Repo**: ansible/metrics-service
- **Commits**: dd5603f, be51903, 5e05775
- **What happened**: Initial commit used `MY_SERVICE_` prefix (e.g., `MY_SERVICE_DB_HOST`). Commit be51903 renamed to lowercase `metrics_service_` (e.g., `metrics_service_DB_HOST`). The very next commit (5e05775) fixed the casing to uppercase `METRICS_SERVICE_` (e.g., `METRICS_SERVICE_DB_HOST`) -- but only partially, leaving some env vars still lowercase (e.g., `metrics_service_REDIS_URL`, `metrics_service_ALLOWED_HOSTS`).
- **Insight**: Environment variable naming conventions should be established before the first commit. The inconsistent casing (`METRICS_SERVICE_` vs `metrics_service_`) persisted across docker-compose, k8s manifests, and Python settings files, creating a confusing mix. Convention should be ALL_CAPS for env vars.

### Database defaults to SQLite for development, PostgreSQL for Docker/production
- **Repo**: ansible/metrics-service
- **Commits**: dd5603f
- **What happened**: `defaults.py` checks `METRICS_SERVICE_DB_ENGINE` env var, defaulting to `django.db.backends.sqlite3`. A separate conditional block enables PostgreSQL when the engine env var is explicitly set to `django.db.backends.postgresql`, providing different defaults for host/port/user.
- **Insight**: The dual-database-default pattern (SQLite for bare-metal dev, PostgreSQL for everything else) reduces friction for new developers but means the two environments can diverge in behavior (e.g., SQLite doesn't enforce foreign keys the same way).

### Dynaconf settings file (config/settings.yaml) committed with real-ish credentials
- **Repo**: ansible/metrics-service
- **Commits**: dd5603f
- **What happened**: `config/settings.yaml` was committed with database password `dabing`, email password `your_email_password`, and other placeholder secrets. While labeled as examples, these were in a non-`.example` file that would be loaded by default.
- **Insight**: Configuration files with placeholder credentials should either be `.example` files (git-tracked) or loaded from environment/secrets only. Committing them risks developers running with insecure defaults in production.

### Port 55432 used as default PostgreSQL port
- **Repo**: ansible/metrics-service
- **Commits**: dd5603f, 5e05775
- **What happened**: Both the docker-compose and the settings defaults use port `55432` for PostgreSQL, not the standard `5432`. Docker maps `55432:5432` externally.
- **Insight**: Using a non-standard external port (55432) avoids conflicts with any local PostgreSQL instance on the developer's machine. The container itself runs on standard 5432 internally.

### `MAX_GATHER_PERIOD_WEEKS` replaced by configurable `METRICS_UTILITY_MAX_GATHER_PERIOD_DAYS` env var
- **Repo**: ansible/metrics-utility
- **Commits**: 594395c (#181)
- **What happened**: The hardcoded `Collector.MAX_GATHER_PERIOD_WEEKS = 4` class constant (introduced in #168) was removed and replaced with a `METRICS_UTILITY_MAX_GATHER_PERIOD_DAYS` env var, defaulting to 28 (same effective value). A `get_max_gather_period_days()` function in `base/utils.py` reads and parses the env var. Validation in `validation.py` enforces the value is 0-3650 (max 10 years). All references to `timedelta(weeks=...)` were changed to `timedelta(days=get_max_gather_period_days())`. The unit was changed from weeks to days for finer granularity, and setting it to 0 is allowed (useful for `limit_slicing` collectors that only need today's data).
- **Insight**: Making the gather period configurable via env var (rather than a class constant) enables operators to extend or shorten the collection window without code changes -- the 4-week default was too short for some deployments that needed historical backfill. **Supersedes** the `MAX_GATHER_PERIOD_WEEKS` constant from #168.

### `get_optional_collectors()` moved from collectors.py to base/utils.py
- **Repo**: ansible/metrics-utility
- **Commits**: f15bd74 (#185)
- **What happened**: The `get_optional_collectors()` function was moved from `collectors.py` to `metrics_utility/base/utils.py` so it could be imported by both `collectors.py` and the base `Collector` class without circular imports. Previously it had been moved from `collectors.py` to `metric_utils.py` (in #75), then back to `collectors.py` (in #153), and now to `base/utils.py`. The base `Collector._gather_csv_collections()` now uses it to determine which collectors are enabled for progress logging.
- **Insight**: Shared utility functions that are needed by both the collector framework (base) and the specific collectors should live in `base/utils.py` to avoid circular import issues -- this function has been moved three times, settling in the lowest-level module that both sides can import.

### New env vars for vCPU collector and SaaS billing
- **Repo**: ansible/metrics-utility
- **Commits**: 429816e (#165), 0be6cd0 (#198)
- **What happened**: The `total_workers_vcpu` collector introduced several new env vars: `METRICS_UTILITY_CLUSTER_NAME` (required, identifies the cluster), `METRICS_UTILITY_USAGE_BASED_METERING_ENABLED` (when `true`, queries Prometheus for actual vCPU count; when `false` or unset, reports `total_workers_vcpu=1`), `METRICS_UTILITY_PROMETHEUS_URL` (Prometheus server URL, defaults to the in-cluster OpenShift monitoring endpoint), `METRICS_UTILITY_COLLECTOR_LOCK_SUFFIX` (appended to the advisory lock name to allow multiple collector instances on the same DB), and `METRICS_UTILITY_DISABLE_SAVE_LAST_GATHERED_ENTRIES` (when `true`, skips persisting last-gathered timestamps). Additionally, `METRICS_UTILITY_DISABLE_JOB_HOST_SUMMARY_COLLECTOR` (when `true`, disables the default `job_host_summary` collector) was added to support SaaS deployments that only need vCPU counting. Note: `METRICS_UTILITY_USAGE_BASED_BILLING_ENABLED` was renamed to `METRICS_UTILITY_USAGE_BASED_METERING_ENABLED` in #198.
- **Insight**: The SaaS billing use case required the ability to disable the default `job_host_summary` collector and run only the vCPU collector -- the existing `METRICS_UTILITY_OPTIONAL_COLLECTORS` mechanism only gates optional collectors, not the mandatory default one.

### PostgreSQL became the default database for all environments
- **Repo**: ansible/metrics-service
- **Commits**: cb58dc0 (#11)
- **What happened**: The settings defaults were changed from SQLite-with-optional-PostgreSQL to PostgreSQL-always. The `DATABASES` config in `defaults.py` was simplified to always use `django.db.backends.postgresql` with default host `127.0.0.1`, port `55432`, user `metrics_service`, password `metrics_service`. The conditional block that checked `METRICS_SERVICE_DB_ENGINE` was removed entirely.
- **Insight**: This was a deliberate decision to eliminate the SQLite/PostgreSQL divergence. All developers must now run PostgreSQL locally (via Docker or native install). The `.env.example` file was added to document the required env vars. This prevents bugs where code works on SQLite but fails on PostgreSQL (e.g., JSONField behavior, transaction handling).

### DAB oauth2_provider and feature_flags apps disabled due to conflicts
- **Repo**: ansible/metrics-service
- **Commits**: cb58dc0 (#11)
- **What happened**: Two DAB apps were commented out in the `DAB_APPS` list: `ansible_base.oauth2_provider` ("Disabled due to model conflicts") and `ansible_base.feature_flags` ("Disabled due to missing 'flags' module"). They had been enabled in the defaults but caused errors during startup.
- **Insight**: DAB apps can have implicit dependencies on specific database state, other DAB apps, or third-party packages that aren't always available. The team's approach of commenting out problematic apps with explanatory comments is pragmatic but the feature flags app being disabled meant the project needed its own feature flag mechanism (which was later built as `apps/dynamic_settings/`).

### development.py settings deleted and recreated multiple times
- **Repo**: ansible/metrics-service
- **Commits**: cb58dc0 (#11), c6947ce (#14), d85322e (#18), da91648 (#29)
- **What happened**: The `metrics_service/settings/development.py` file was deleted in cb58dc0 as part of "consolidating settings," then recreated in the same commit's later squashed commits, then deleted and recreated again in c6947ce. In da91648, it was refactored from using `from .defaults import *` (wildcard import) to explicitly importing each setting by name from `defaults`.
- **Insight**: The wildcard import (`from .defaults import *`) was flagged by Sonar as a code quality issue, leading to the explicit import pattern. However, explicitly listing 20+ settings is verbose and fragile -- any new setting in `defaults.py` must be manually added to `development.py`. This was likely later resolved by Dynaconf's layering.

### New service collectors added to VALID_COLLECTORS
- **Repo**: ansible/metrics-utility
- **Commits**: 0c851b4 (#214)
- **What happened**: Four new collector names were added to `VALID_COLLECTORS` in `validation.py`: `unified_jobs`, `job_host_summary_service`, `main_jobevent_service`, and `execution_environments`. These are gated by `METRICS_UTILITY_OPTIONAL_COLLECTORS` like all other optional collectors and are intended for the metrics service use case (anonymized aggregations).
- **Insight**: Every new optional collector requires an entry in `VALID_COLLECTORS` in validation.py -- the env var validation rejects unknown collector names to catch typos early.

### Redis removed as a dependency for development
- **Repo**: ansible/metrics-service
- **Commits**: d85322e (#18)
- **What happened**: Redis cache configuration was removed from the development settings. The cache backend was switched to Django's local memory cache (`django.core.cache.backends.locmem.LocMemCache`) for development. Redis references were removed from docker-compose, `.env.example`, and settings files.
- **Insight**: Redis was premature infrastructure for the development environment. The service doesn't currently use caching in a way that requires Redis, and removing it reduces the setup burden for developers. Redis can be re-added when actually needed.

### Dynaconf integration replaced split_settings in a two-phase rollout
- **Repo**: ansible/metrics-service
- **Commits**: 8b4aa31 (#26), f4b136e (#31)
- **What happened**: Phase 1 (8b4aa31) introduced Dynaconf by replacing `split_settings.tools.include` and `dynamic_config` imports with DAB's `factory()` call. The settings `__init__.py` was rewritten to create a `DYNACONF` object using `factory(module_name=__name__, app_name="METRICS_SERVICE", ...)` with validators, environment-aware sections, and a loading order: `defaults.py` -> `/etc/ansible-automation-platform/settings.yaml` -> `config/settings.yaml` -> env vars. A `ConfigView` was added for runtime config viewing/reloading via API. Phase 2 (f4b136e) replaced the `ConfigView` with a RESTful `SettingView` backed by a new `Setting` DB model, adding change tracking and rollback capability. The `ConfigView` allowed arbitrary config updates via `DYNACONF.merge()`, which was replaced by guarded `DYNACONF.set()` with validation that keys already exist.
- **Insight**: The two-phase approach was intentional -- Phase 1 established the Dynaconf plumbing while Phase 2 added persistence and auditability. The PR #26 description explicitly noted "Configuration/Settings changes will not persist after an app restart. That work will come in via a later PR." Splitting infra from business logic into separate PRs made each reviewable.

### Environment switcher changed from METRICS_SERVICE_ENV to METRICS_SERVICE_MODE
- **Repo**: ansible/metrics-service
- **Commits**: 8b4aa31 (#26)
- **What happened**: The Dynaconf integration changed the environment switching variable from `METRICS_SERVICE_ENV` to `METRICS_SERVICE_MODE`. A comment in the code explicitly notes "Factory uses METRICS_SERVICE_MODE as the env_switcher (not METRICS_SERVICE_ENV)". The `development.py` settings file was deleted since Dynaconf handles environment sections in `config/settings.yaml`.
- **Insight**: The rename from `_ENV` to `_MODE` aligns with Dynaconf convention and distinguishes the settings layer selector from the deployment environment. This also means `DJANGO_SETTINGS_MODULE` becomes just `metrics_service.settings` (no `.development` suffix) since Dynaconf handles the mode internally.

### Dynaconf validators enforce production security but skip in development
- **Repo**: ansible/metrics-service
- **Commits**: 8b4aa31 (#26)
- **What happened**: Multiple Dynaconf `Validator` objects were added to ensure `SECRET_KEY` is not any of the three default values (from `defaults.py`, from the YAML default section, or from the YAML production section). Database settings (`DATABASES.default.NAME`, `HOST`, `USER`, `PASSWORD`) must exist. However, validation is skipped in development mode via `export(__name__, DYNACONF, validation=not is_development)`.
- **Insight**: The conditional validation means production deployments fail fast if secrets aren't configured, while development "just works" with defaults. The three separate validators for `SECRET_KEY` (one per possible default value source) show how multiple config sources create multiple bad-default scenarios.

### config/settings.yaml restructured with environment sections
- **Repo**: ansible/metrics-service
- **Commits**: 8b4aa31 (#26)
- **What happened**: The YAML config was restructured from flat lowercase keys (e.g., `secret_key`, `databases.default.engine`) to Dynaconf environment sections (`default:`, `development:`, `production:`) with uppercase Django-style keys (e.g., `SECRET_KEY`, `DATABASES.default.ENGINE`). Email config and OAuth2/JWT settings were removed. The production section explicitly sets `SECRET_KEY: 'PRODUCTION-SECRET-KEY-NOT-SET'` to force override.
- **Insight**: Using uppercase keys in YAML matching Django's convention eliminates case translation bugs. The production section's invalid-sentinel approach (setting `SECRET_KEY` to a clearly-wrong value) combines with the validator to ensure production configs are explicitly set.

### Database env var naming switched to Dynaconf dunder notation
- **Repo**: ansible/metrics-service
- **Commits**: 8b4aa31 (#26)
- **What happened**: `.env.example` changed database env vars from flat naming (`METRICS_SERVICE_DB_HOST`, `METRICS_SERVICE_DB_PORT`) to Dynaconf nested dunder notation (`METRICS_SERVICE_DATABASES__default__HOST`, `METRICS_SERVICE_DATABASES__default__PORT`). Port default also changed from 55432 to 5432.
- **Insight**: Dunder notation (`__`) lets Dynaconf automatically build nested dicts that Django expects for `DATABASES`. The flat `DB_HOST` style required custom parsing code; dunder notation eliminates that entirely. However, the env var names are now longer and harder to type.

### METRICS_UTILITY_OPTIONAL_COLLECTORS empty string removed from VALID_COLLECTORS, parsed with filter(bool)
- **Repo**: ansible/metrics-utility
- **Commits**: aafd74c (#263)
- **What happened**: The earlier fix (#178) handled empty/whitespace `METRICS_UTILITY_OPTIONAL_COLLECTORS` by adding `''` to `VALID_COLLECTORS`. This was replaced with a cleaner approach: `get_optional_collectors()` now strips whitespace and uses `filter(bool, ...)` to remove empty strings after splitting by comma. The validation in `validation.py` similarly strips and checks for empty before splitting. This eliminates the magic empty string from the valid set.
- **Insight**: Rather than adding empty string as a "valid" sentinel value, use `filter(bool, s.split(','))` to cleanly handle the empty/whitespace case -- this removes the need for any special case in the valid values set. **Supersedes** the empty string workaround from #178.

### FEATURE_FLAGS renamed to FEATURE_ENABLED to avoid AAP naming conflict
- **Repo**: ansible/metrics-service
- **Commits**: c8e5f0d (#36)
- **What happened**: The settings dict was renamed from `FEATURE_FLAGS` to `FEATURE_ENABLED` across defaults.py, test.py, and task_groups.py. The `TaskGroup` class attribute `enabled_flag` was renamed to `enabled_setting`. The commit message says "changing feature flag to feature enable ... to avoid confusion with the actual feature flag in Ansible."
- **Insight**: AAP already has a "feature flags" concept (from `ansible_base.feature_flags` which was disabled earlier). Using the same term in this service created confusion about which feature flag system was being referenced. The rename to `FEATURE_ENABLED` distinguishes this service's runtime toggles from AAP's feature flags system.

### Feature toggles became DB-driven with Django settings fallback
- **Repo**: ansible/metrics-service
- **Commits**: c8e5f0d (#36)
- **What happened**: The `task_groups.py` module added `get_feature_enabled_from_db()` which queries the `Setting` model first, then falls back to `getattr(settings, "FEATURE_ENABLED", {})`. The enable/disable functions (`enable_task_group`, `disable_task_group`) were changed from placeholder stubs ("Would enable task group") to real implementations that create/update `Setting` DB rows with `get_or_create()`. A `set_feature_enabled()` helper and `get_feature_enabled_status()` reporting function were also added.
- **Insight**: The DB-first-with-settings-fallback pattern means feature toggles can be changed at runtime via API without restart, but still have sane defaults from `settings.py` for fresh deployments. The `get_feature_enabled_status()` function reports the source (database/django_settings/default) for each toggle, which is valuable for debugging.

### Dynaconf @json format for list-type env vars
- **Repo**: ansible/metrics-service
- **Commits**: 2e4cea6 (#47), 6059d8c (#45)
- **What happened**: `.env.example` changed from comma-separated lists (`METRICS_SERVICE_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0`) to Dynaconf `@json` format (`METRICS_SERVICE_ALLOWED_HOSTS='@json ["localhost", "127.0.0.1", "0.0.0.0"]'`). The docker-compose.yml also switched to JSON array format for `ALLOWED_HOSTS`.
- **Insight**: Comma-separated strings require custom parsing and don't work for values that themselves contain commas. Dynaconf's `@json` prefix provides unambiguous list/dict typing directly in env vars. The trade-off is slightly more verbose env var syntax.

### `main_host_daily` added to VALID_COLLECTORS for incremental host collection
- **Repo**: ansible/metrics-utility
- **Commits**: 2afe3c7 (#209)
- **What happened**: The `main_host_daily` collector was added to `VALID_COLLECTORS` in `validation.py`, enabling operators to set `METRICS_UTILITY_OPTIONAL_COLLECTORS=main_host_daily` for time-bounded host collection (daily slicing) as an alternative to the existing `main_host` (full snapshot via limit slicing). The recommended deployment pattern is to use `main_host_daily` for daily cronjobs (collecting only hosts created/modified that day) and `main_host` with `METRICS_UTILITY_DISABLE_JOB_HOST_SUMMARY_COLLECTOR=true` for weekly full snapshots.
- **Insight**: Adding `main_host_daily` alongside `main_host` gives operators a choice between completeness (full inventory snapshot) and efficiency (only recently changed hosts) via the same `METRICS_UTILITY_OPTIONAL_COLLECTORS` mechanism.

### Centralized logging with configurable log level via env var
- **Repo**: ansible/metrics-service
- **Commits**: 7d50113 (#51)
- **What happened**: A `METRICS_SERVICE_LOG_LEVEL` environment variable was added (defaulting to `INFO`), read via `os.environ.get()` in `defaults.py`. All four logger definitions (`ansible_base`, `metrics_service`, `django`, root) were changed from hardcoded levels (`INFO`/`DEBUG`/`WARNING`) to use the single `LOG_LEVEL` variable. The `run_dispatcherd` command had redundant logging setup removed.
- **Insight**: A single env var controlling all loggers is practical for deployment simplicity -- operators don't need to know the internal logger hierarchy. The trade-off is loss of per-component log level control (e.g., you can't set Django to WARNING while keeping metrics_service at DEBUG). The `os.environ.get()` approach is used instead of Dynaconf because this runs at settings module load time.

### DEBUG explicitly disabled for production environments
- **Repo**: ansible/metrics-service
- **Commits**: 7b39f53 (#56)
- **What happened**: `METRICS_SERVICE_DEBUG` was changed to `false` in `.env.example`, and `DEBUG = False` was set in `defaults.py`. Previously, DEBUG had been left as `True` or configurable, making it easy to accidentally run with debug mode enabled.
- **Insight**: Django's `DEBUG = True` exposes stack traces, SQL queries, and other sensitive information. Defaulting to `False` in the base settings file means production is safe by default, and developers must explicitly enable it locally.

### dispatcherd config now always reads DB settings from Django DATABASES
- **Repo**: ansible/metrics-service
- **Commits**: 0e15cbd (#66)
- **What happened**: The `config/dispatcherd.yaml` had its hardcoded database credentials removed and replaced with a comment saying "Database config is injected at runtime from Django settings." A new `_load_config_with_django_db()` function in `dispatcherd_config.py` loads the YAML file, then overwrites `brokers.pg_notify.config` with values from `django.conf.settings.DATABASES["default"]`.
- **Insight**: This resolves the long-running problem of dispatcherd's database config being out of sync with Django's. Now `METRICS_SERVICE_DATABASES__default__*` env vars flow through Dynaconf -> Django settings -> dispatcherd config, providing a single source of truth. The YAML file still controls non-DB settings like channel names and queue routing.

### DEVELOPER_MODE_ENABLED feature gate for production safety
- **Repo**: ansible/metrics-service
- **Commits**: dbf6fb1 (#65)
- **What happened**: A `DEVELOPER_MODE_ENABLED` setting was added (default `False`) to `defaults.py`, overridable via `METRICS_SERVICE_DEVELOPER_MODE_ENABLED`. A `DeveloperModeRequired` DRF permission class in `apps/core/permissions.py` checks this setting and returns 403 when disabled. A `require_developer_mode` decorator (using `functools.wraps`) does the same for plain Django views. Both `TaskViewSet` and `TaskExecutionViewSet` switched from `permission_classes = [AllowAny]` (which was marked "Temporary for dashboard access") to `[DeveloperModeRequired]`. The dashboard view also gained the decorator. Test settings set `DEVELOPER_MODE_ENABLED = True`.
- **Insight**: This is a clean pattern for gating debug/development endpoints in production: a single boolean setting controls access, checked at two layers (DRF permissions for API, decorator for views). The previous `AllowAny` permission on task endpoints was a security risk that persisted for months.

### URL prefix env var for gateway routing
- **Repo**: ansible/metrics-service
- **Commits**: 2efdae3 (#69), a64071c (#70)
- **What happened**: A `METRICS_SERVICE_URL_PREFIX` env var was added (read via `os.getenv()` in the dashboard view) to prefix the API base URL when the service runs behind a gateway. If set (e.g., `METRICS_SERVICE_URL_PREFIX=metrics-service`), the dashboard's API calls go to `/<prefix>/api/v1/` instead of `/api/v1/`. The first attempt (#69) used `METRICS_URL_PREFIX`, renamed in #70 to follow the `METRICS_SERVICE_*` convention.
- **Insight**: This was a stopgap solution for gateway routing. The proper fix came in 52c8fb5 (#75) with `ServicePrefixMiddleware` which handles prefix routing at the Django middleware level, making the env var approach unnecessary for most cases.

### Per-app settings.py files using Dynaconf merge markers
- **Repo**: ansible/metrics-service
- **Commits**: 52c8fb5 (#75)
- **What happened**: A new `apps/core/settings.py` was created following the Dynaconf convention for per-app settings. It uses merge markers like `MIDDLEWARE = ["dynaconf_merge_unique", ...]` and `REST_FRAMEWORK__DEFAULT_AUTHENTICATION_CLASSES = "@insert 0 apps.core.authentication.ServiceJWTAuthentication"` to extend lists/dicts from `defaults.py` without overwriting them.
- **Insight**: The `@insert 0` Dynaconf marker allows prepending to a list (putting JWT auth first), while `dynaconf_merge_unique` appends without duplicates. This pattern lets each app declare its own middleware, authentication classes, etc. without modifying the central settings file.

### Segment write key moved from task parameter to Django setting
- **Repo**: ansible/metrics-service
- **Commits**: 1acd7b2 (#72)
- **What happened**: The `segment_write_key` parameter was removed from all task functions (`_send_to_segment`, `full_process`, `full_process_anonymize`, `send_to_segment`, `test_segment_track`, `debug_segment_messages`) and their metadata definitions. Instead, `_send_to_segment()` now reads it from `getattr(settings, "METRICS_SERVICE_SEGMENT_WRITE_KEY", None)` via Django settings. A default value (`test-segment-write-key-change-in-production`) was added to `config/settings.yaml`, and a Dynaconf `Validator` was added to ensure production doesn't use the default value.
- **Insight**: Secrets like API write keys should come from settings/environment, not task parameters. Passing secrets as task parameters means they'd be logged in task execution records and visible in the API. Using Django settings with Dynaconf allows the value to come from environment variables (`METRICS_SERVICE_SEGMENT_WRITE_KEY`) or production config files, with validation preventing the default from reaching production.

### Settings restructured from metrics_service/settings/ package to framework-managed single file
- **Repo**: ansible/metrics-service
- **Commits**: 911dd60 (#77)
- **What happened**: The `metrics_service/settings/` package (containing `__init__.py` with Dynaconf factory, `defaults.py`, `development.py`, `test.py`) was replaced by a single `metrics_service/settings.py` file. This file contains Django framework defaults (INSTALLED_APPS, MIDDLEWARE, DATABASES with SQLite default, LOGGING, etc.) and the Dynaconf instrumentation that loads settings in order: `apps/settings/defaults.py` -> each `apps/*/settings.py` -> `apps/settings/{mode}.py` -> `settings.local.py` -> DAB settings -> standard paths -> env vars -> post hooks. The `DJANGO_SETTINGS_MODULE` changed from `metrics_service.settings.test` to just `metrics_service.settings`. Environment-specific overrides moved to `apps/settings/test.py`, `apps/settings/development.py`, `apps/settings/production.py`. The `config/settings.yaml` was removed. A `settings.local.py.example` was added for local development overrides. `django-cors-headers` was removed since CORS is handled at the gateway level.
- **Insight**: The framework pattern separates "things the framework manages" (in `metrics_service/settings.py`, marked DO NOT EDIT) from "things the project customizes" (in `apps/settings/`). This enables the copier template to update framework files without conflicting with project customizations. The loading order is critical: framework defaults are intentionally overridable (e.g., the SQLite default in `metrics_service/settings.py` is overridden by PostgreSQL in `apps/settings/defaults.py`).

### Per-app settings files established as standard pattern
- **Repo**: ansible/metrics-service
- **Commits**: 911dd60 (#77), 3a58426 (#79)
- **What happened**: The settings restructuring created `apps/tasks/settings.py` with task-specific settings (`DISPATCHERD_ENABLED = True`, `SEGMENT_WRITE_KEY`). This file is automatically loaded by the Dynaconf instrumentation in `metrics_service/settings.py` which iterates `LOADED_APPS` and calls `DYNACONF.load_file(f"{app}.settings")` for each app. The loading order means later apps can override earlier apps' settings, and environment-specific files (`apps/settings/{mode}.py`) override all app settings.
- **Insight**: Per-app settings files follow the "apps own their configuration" principle. Settings declared in `apps/tasks/settings.py` stay with the tasks app and are version-controlled alongside the code that uses them. Dynaconf merge markers (`@merge_unique`, `dynaconf_merge`) ensure app-level settings extend rather than replace base settings.

### DEVELOPER_MODE_ENABLED replaced by METRICS_SERVICE_MODE check
- **Repo**: ansible/metrics-service
- **Commits**: 7db9971 (#87)
- **What happened**: The `DEVELOPER_MODE_ENABLED` setting and all references to it were removed. Instead, the `DeveloperModeRequired` permission class (renamed conceptually to development mode) now checks `settings.MODE == "development"`. The dashboard's `require_developer_mode` decorator was renamed to `require_development_mode` with the same MODE-based check. Test settings no longer need `DEVELOPER_MODE_ENABLED = True` since `METRICS_SERVICE_MODE=test` is already set and doesn't match "development". Tests that need dashboard/task API access now mock `settings.MODE` to return `"development"`.
- **Insight**: Using the existing `MODE` setting (which already distinguishes development/test/production) to gate debug endpoints eliminates a separate boolean flag. This is cleaner because there's a single source of truth for "what environment am I in." The trade-off is that test mode can't access debug endpoints without mocking, which is arguably correct behavior.

### URL_PREFIX setting added for dashboard API URL generation
- **Repo**: ansible/metrics-service
- **Commits**: 7db9971 (#87), 85aed7f (#91)
- **What happened**: PR #87 introduced `URL_PREFIX = None` in `apps/settings/defaults.py` and changed the dashboard view from `os.getenv("METRICS_SERVICE_URL_PREFIX")` to `settings.URL_PREFIX`, adding slash handling (`if prefix and prefix != "/": root_url = f"/{prefix}/{root_url}".replace("//", "/")`). PR #91 further refined this by adding a `url_for()` helper function that sanitizes slashes using `re.sub(r"/+", "/", f"/{prefix}/{path}")` and treats `None` as `/api/` prefix. The setting's docstring was updated from "example: metrics-service" to "example: /api/metrics/; None means /api/" to clarify it's a URL path prefix, not a slug.
- **Insight**: This is the third iteration of URL prefix handling (#69 introduced it as env var, #70 renamed it, #87 made it a setting, #91 fixed the interpretation). The key insight from #91 is that the prefix should be treated as an actual URL path segment (like `/api/metrics/`), not a slug (like `metrics-service`). The `url_for()` helper with slash normalization handles edge cases where users might include or omit leading/trailing slashes.

### Environment variable cleanup standardized on METRICS_SERVICE_MODE
- **Repo**: ansible/metrics-service
- **Commits**: 7db9971 (#87)
- **What happened**: `METRICS_SERVICE_MODE` (already introduced by the framework retrofit in #77) became the authoritative environment selector, replacing `DEVELOPER_MODE_ENABLED`. The `TEST_DB_NAME` variable was removed (tests use whatever the settings resolve to). The `settings.local.py.example` was updated to comment out all defaults so it serves as documentation rather than active overrides. The `.gitignore` entry for `.env` was removed (the file is no longer used; `settings.local.py` replaces it).
- **Insight**: Consolidating environment configuration to a single `METRICS_SERVICE_MODE` variable simplifies deployment. Operators set one variable (development/test/production) and get the appropriate behavior, rather than managing separate boolean flags for each feature.

### `credentials_service`, `table_metadata`, and `controller_version` added to VALID_COLLECTORS
- **Repo**: ansible/metrics-utility
- **Commits**: 456eb0f (#319), 3d86b71 (#328)
- **What happened**: Three new collector names were added to `VALID_COLLECTORS` in `validation.py`: `credentials_service` (credential type distribution, filtered to managed credentials only), `table_metadata` (PostgreSQL table sizes and row counts for key tables), and `controller_version` (distinct controller versions from enabled instances). All are gated by `METRICS_UTILITY_OPTIONAL_COLLECTORS` and intended for the anonymized rollup pipeline. The `credentials_service` collector only collects credentials where `credential_type__managed = true`, avoiding exposure of custom credential type names in anonymized data.
- **Insight**: Infrastructure telemetry collectors (table metadata, controller version) provide deployment-level context alongside the existing application-level collectors (jobs, events, hosts), enabling the metrics service to understand both what automation is running and the scale of the infrastructure supporting it.

### init-default-settings enhanced with overwrite and remove capabilities
- **Repo**: ansible/metrics-service
- **Commits**: e137d39 (#92)
- **What happened**: `init-default-settings` now recreates settings that haven't been changed by the user (no `previous_value` set). Settings changed by the user are preserved. Added `--overwrite` flag to force-reset all settings to defaults. Added complementary `remove-default-settings` with `--all-known` (removes even user-changed settings) and `--all-settings` (deletes everything).
- **Insight**: The `previous_value` field on the Setting model serves as a change-tracking flag: if null, the setting hasn't been modified by the user and can be safely reset. This allows re-running `init-default-settings` on upgrades to apply new defaults without overwriting user customizations.

### ALLOWED_HOSTS validator added for production then immediately disabled
- **Repo**: ansible/metrics-service
- **Commits**: 531b608 (#129), 6b4f17c (#137)
- **What happened**: In #129, a production validator was added requiring `ALLOWED_HOSTS` to be a non-empty list. In #137 (one week later), this validator was commented out along with three others for the tech preview deployment.
- **Insight**: The rapid add-then-disable cycle reflects the tension between security hardening (validating all production settings) and deployment pragmatism (the tech preview environment isn't fully configured yet). The commented-out validators serve as documentation of what will be enforced once gateway integration is complete.

### SEGMENT_WRITE_KEY loaded from file for Konflux secrets management
- **Repo**: ansible/metrics-service
- **Commits**: 6b4f17c (#137)
- **What happened**: A new secrets management pattern was introduced for loading `SEGMENT_WRITE_KEY` from a file instead of (or in addition to) environment variables. The `_load_segment_write_key_from_file()` function reads from a configurable path (default: `/etc/ansible-automation-platform/metrics/segment-write-key`, overridable via `METRICS_SERVICE_SEGMENT_WRITE_KEY_FILE`). The file content is expected to be base64-encoded. The function respects precedence: it does NOT overwrite if the key is already set via `METRICS_SERVICE_SEGMENT_WRITE_KEY` env var or Dynaconf. The `_decode_segment_key()` helper tries base64 decoding and falls back to using the raw value if decoding fails. This runs at settings module load time (called immediately after `load_envvars`). Comprehensive unit tests were added covering base64 decode, file-not-found, empty file, directory path, and OSError scenarios.
- **Insight**: In Konflux deployments, build-time secrets (like Segment write keys) are injected as files rather than environment variables. The base64 encoding adds a layer that prevents accidental log exposure. The precedence order (env var > Dynaconf setting > file) ensures operators can always override the file-based key. This is the beginning of a pattern that will be iterated on -- Konflux pipeline secrets management for API keys.

### Production validators temporarily disabled for tech preview deployment
- **Repo**: ansible/metrics-service
- **Commits**: 6b4f17c (#137)
- **What happened**: Four production validators were commented out (with "Optional until gateway APIs are implemented" comments): `RESOURCE_SERVER__SECRET_KEY`, `ANSIBLE_BASE_JWT_KEY`, `SEGMENT_WRITE_KEY`, and `ALLOWED_HOSTS`. A test was added to assert these settings do NOT have validators, ensuring they stay optional. The PR description says "Temp removing validators as TP wont support gateway correction."
- **Insight**: For the tech preview (TP) release, the service will deploy without the AAP gateway integration (no JWT auth, no resource server). Disabling validators prevents the service from failing to start in environments where gateway config isn't available yet. The test asserting the absence of validators is a clever way to prevent someone from accidentally re-enabling them before gateway support is ready.

### SEGMENT_WRITE_KEY base64 encoding removed in favor of plaintext
- **Repo**: ansible/metrics-service
- **Commits**: 1b38f9f (#141)
- **What happened**: The `_decode_segment_key()` helper (which tried base64 decoding and fell back to raw value) was removed entirely. The `_read_segment_key_from_path()` function now reads the file content as plaintext with `.strip()`. The `base64` import was removed from `metrics_service/settings.py`. Tests were updated to use plaintext keys and test whitespace stripping instead of base64 decoding.
- **Insight**: The base64 encoding layer introduced in #137 was an unnecessary complication. Since the key is injected by the build pipeline, the pipeline can write it as plaintext directly. Removing the decode/fallback logic eliminates a source of confusion (which encoding is my key in?) and simplifies debugging. This is the second iteration of the Segment key file pattern (added in #137, simplified here).

### SEGMENT_TEST_MODE for separating test data from production in Segment
- **Repo**: ansible/metrics-service
- **Commits**: 4b078d3 (#147)
- **What happened**: A new `SEGMENT_TEST_MODE` setting was added to `apps/tasks/settings.py` (default `False`), overridable via `METRICS_SERVICE_SEGMENT_TEST_MODE`. When enabled, `_process_single_payload()` appends `"_Test"` to the Segment event name (e.g., `"Controller Metrics Daily Rollup"` becomes `"Controller Metrics Daily Rollup_Test"`). Tests were added covering enabled, disabled, and absent setting scenarios.
- **Insight**: Separating test traffic from production in analytics systems by modifying event names is a practical pattern. It avoids creating separate Segment sources or write keys for testing. The suffix approach means test data can be filtered out on the analytics side.

### PostgreSQL session parameters normalized from Dynaconf env vars to psycopg2 options string
- **Repo**: ansible/metrics-service
- **Commits**: fbfefeb (#149)
- **What happened**: A post-Dynaconf-export normalization step was added to `metrics_service/settings.py` that scans `DATABASES[*].OPTIONS` for common PostgreSQL session parameters (`datestyle`, `search_path`, `timezone`, `application_name`) and converts them to psycopg2's `-c key=value` format in `OPTIONS.options`. This allows setting `METRICS_SERVICE_DATABASES__awx__OPTIONS__datestyle=iso, mdy` instead of the psycopg2-specific `METRICS_SERVICE_DATABASES__awx__OPTIONS__options=-c datestyle=iso,mdy`.
- **Insight**: Dynaconf's dunder notation creates nested dicts naturally, but psycopg2 needs session parameters as a `-c key=value` formatted string in `OPTIONS.options`, not as individual keys in `OPTIONS`. The normalization bridge makes the env var interface user-friendly while producing the format psycopg2 expects. Spaces are stripped from values to prevent quoting issues.

### STATIC_ROOT set to fixed writable path for production
- **Repo**: ansible/metrics-service
- **Commits**: 520fd11 (#155)
- **What happened**: `apps/settings/production.py` added `STATIC_ROOT = "/var/lib/ansible-automation-platform/metrics/staticfiles"` to override the default `BASE_DIR`-relative path. The init entrypoint script (`scripts/entrypoint-init.sh`) was updated to run `collectstatic --noinput --clear`.
- **Insight**: When the package is installed into `site-packages`, the default `BASE_DIR`-relative `STATIC_ROOT` points into a potentially read-only location. A fixed writable path ensures WhiteNoise can serve static files regardless of the install method. Running `collectstatic` in the init script (rather than at build time) ensures it picks up static files from all installed packages.

### `config` collector version bumped to 2.0 for nullable fields
- **Repo**: ansible/metrics-utility
- **Commits**: b7ff6f6 (#355)
- **What happened**: The `config` collector's version in the manifest was bumped from 1.0 to 2.0 because the DB-based refactoring in #242 made some config fields nullable that were previously guaranteed non-null (when read from `django.conf.settings` they always had values; when read from `conf_setting` table they can be absent). The version bump signals to tarball consumers that all config fields should be treated as nullable.
- **Insight**: When a collector refactoring changes field nullability (even unintentionally), bump the manifest version to signal the breaking change to downstream consumers -- this is especially important for the config collector whose fields are used as metadata for all other collections.

### ServicePrefixMiddleware updated to derive prefix from URL_PREFIX setting
- **Repo**: ansible/metrics-service
- **Commits**: 35620f8 (#157)
- **What happened**: `ServicePrefixMiddleware.__init__()` was refactored to check `settings.URL_PREFIX` first, deriving both `api_prefix` and `service_prefix` from it (e.g., `URL_PREFIX="/api/metrics"` yields `api_prefix="/api/metrics"`, `service_prefix="/metrics"`). The previous behavior of deriving from `ROOT_URLCONF` is now the fallback when `URL_PREFIX` is unset. Tests were added covering the URL_PREFIX path, the fallback path, trailing slash handling, and non-`/api/` prefix edge cases.
- **Insight**: This is the fourth and most complete iteration of URL prefix handling. Earlier versions (#69/#70 used an env var, #87 made it a setting, #91 refined interpretation). This version makes the middleware directly configurable via `URL_PREFIX`, which is the correct layer since the middleware is what actually rewrites request paths. The `api_prefix.startswith("/api/")` check handles edge cases where the prefix might not follow the `/api/<service>` convention.

### `METRICS_UTILITY_DB_*` env vars extended and warned about in controller mode
- **Repo**: ansible/metrics-utility
- **Commits**: ae0878a (#359)
- **What happened**: The `mock_awx/settings/__init__.py` DB configuration was expanded to read `METRICS_UTILITY_DB_NAME`, `METRICS_UTILITY_DB_USER`, `METRICS_UTILITY_DB_PASSWORD`, and `METRICS_UTILITY_DB_PORT` (in addition to the existing `METRICS_UTILITY_DB_HOST`), with defaults matching the Docker Compose dev setup (`awx`, `myuser`, `mypassword`, `5432`). A warning was added to `metrics_utility/__init__.py`: when Controller modules are found (i.e., running inside a real Controller venv), any `METRICS_UTILITY_DB_*` env vars are logged as ignored with a message that they only take effect in standalone mode. The Makefile also gained `pcompose`, `pclean`, and `ppsql` targets for podman-compose users.
- **Insight**: When env vars only apply in one operating mode (standalone) but are ignored in another (controller venv), warn the user explicitly -- silent ignoring of configuration is a common source of confusion when operators copy configs between environments.

### Feature flags now persist through DAB migrations via post_migrate signal
- **Repo**: ansible/metrics-service
- **Commits**: db116c4 (#184)
- **What happened**: DAB's feature_flags app purges/reloads flags on every migration, deleting task-owned flags. A `feature_flags.yaml` defines the flags, and `TasksConfig.ready()` connects `load_task_feature_flags` to `post_migrate` of `FeatureFlagsConfig`, re-seeding after every DAB purge cycle.
- **Insight**: When a third-party framework owns a model and purges/reloads it during migrations, application-specific records need a re-seeding mechanism. Using `post_migrate` connected to the framework's app ensures correct ordering.

### Dashboard endpoint moved from /dashboard/ to /api/dashboard/
- **Repo**: ansible/metrics-service
- **Commits**: db116c4 (#184)
- **What happened**: Dashboard URL changed from `/dashboard/` to `/api/dashboard/`. A redirect from `/api/v1/feature_flags/` to `/api/v1/feature_flags/states/` was added.
- **Insight**: Placing the dashboard under `/api/` ensures it's covered by the same middleware and prefix handling as the REST API, simplifying gateway routing.

### Feature flag precedence order clarified and DASHBOARD_COLLECTION removed from defaults
- **Repo**: ansible/metrics-service
- **Commits**: fc2815a (no PR number), 8007509 (#189), babf061 (#199)
- **What happened**: The `get_feature_enabled_from_db()` function's lookup order was formalized, then expanded in #199 to five tiers: (1) `Setting` row in dynamic_settings, (2) `settings.FEATURE_ENABLED[name]` if that key exists (includes Dynaconf env var overrides), (3) `settings.FEATURE_<name>_ENABLED` top-level attribute (set by installer via `settings.yaml`), (4) DAB `AAPFlag` `FEATURE_<name>_ENABLED`, (5) the `default` parameter. Tier 3 was added because the installer writes top-level keys like `FEATURE_DASHBOARD_COLLECTION_ENABLED: True` directly into `settings.yaml`, which Dynaconf surfaces as a settings attribute but not inside the `FEATURE_ENABLED` dict. A `sync_flag_values_from_settings()` function was also added to propagate installer overrides to AAPFlag rows so the Gateway UI reflects the installer's intent.
- **Insight**: When multiple configuration sources exist, explicit precedence documentation is critical. The five-tier order ensures: runtime API changes (Setting) > Dynaconf env var overrides (FEATURE_ENABLED dict) > installer intent (top-level attr) > platform defaults (AAPFlag) > code defaults. Each source has a clear owner and override path. Omitting a key from `FEATURE_ENABLED` lets it fall through to the installer/AAPFlag/default path, useful for flags that should be platform-managed by default.

### load_task_feature_flags called from init-default-settings for pre-migrated environments
- **Repo**: ansible/metrics-service
- **Commits**: 8007509 (#189)
- **What happened**: The `init-default-settings` management command now calls `load_task_feature_flags()` directly after `initialize_default_settings()`. The function was updated to return `bool` (True on success, False on failure) and log failures at WARNING level instead of using `logger.exception` (which logs at ERROR). If flag seeding fails, the command still succeeds but prints a warning message instead of the normal success message.
- **Insight**: In production Kubernetes deployments, the DB is pre-migrated before the service starts, so the `post_migrate` signal (which normally seeds AAPFlags) never fires during `init-default-settings`. Calling `load_task_feature_flags()` explicitly ensures flags are seeded regardless of whether a migration has run. The non-fatal failure handling prevents flag seeding issues from blocking service startup.

### METRICS_COLLECTION feature flag added for local collection control
- **Repo**: ansible/metrics-service
- **Commits**: 68a2039 (#191)
- **What happened**: New `METRICS_COLLECTION` flag (default: true) added. The system now has three flags: `METRICS_COLLECTION` (local collection), `ANONYMIZED_DATA_COLLECTION` (anonymization + upstream send), `DASHBOARD_COLLECTION` (dashboard reports).
- **Insight**: See `task_system.md` for the full feature flag evolution arc. Each flag gates a specific pipeline subset and can be toggled independently.

### Production startup validation re-enabled with actionable error messages
- **Repo**: ansible/metrics-service
- **Commits**: 956923d (#193)
- **What happened**: The `validation=False` in `metrics_service/settings.py` was changed back to `validation=True`. All four production validators that had been commented out in #137 were uncommented and enhanced with actionable error messages specifying exactly which environment variable to set: `RESOURCE_SERVER__SECRET_KEY` ("Set METRICS_SERVICE_RESOURCE_SERVER__SECRET_KEY"), `ANSIBLE_BASE_JWT_KEY` ("Set METRICS_SERVICE_ANSIBLE_BASE_JWT_KEY"), `SEGMENT_WRITE_KEY` (explains both env var and file path options), and `ALLOWED_HOSTS` (explains comma-separated and JSON array formats with examples). The test was flipped from asserting validators are absent (`test_optional_production_settings_have_no_validators`) to asserting validators are present (`test_required_production_settings_have_validators`). SonarCloud was updated to exclude `**/settings/**` from both sources and coverage.
- **Insight**: This is the conclusion of the validation saga that spanned 5 PRs: #26 (added validators), #129 (added ALLOWED_HOSTS validator), #137 (commented out all four), #143 (nuclear option: validation=False), #193 (re-enabled with proper messages). The key difference from earlier attempts is actionable error messages: instead of generic "must be set", each validator now tells the operator exactly which env var to export and in what format. This turns a startup crash into a clear remediation instruction. The validators only run in production mode (development/test have no validators registered), so local development is unaffected.

### Feature flag precedence expanded to five tiers with installer top-level attribute
- **Repo**: ansible/metrics-service
- **Commits**: babf061 (#199)
- **What happened**: The `get_feature_enabled_from_db()` lookup order was expanded from four to five tiers by adding a check for `settings.FEATURE_<name>_ENABLED` (top-level attribute set by the installer via `settings.yaml`) between the `FEATURE_ENABLED` dict check and the AAPFlag check. Full order: (1) `Setting` row, (2) `settings.FEATURE_ENABLED[name]`, (3) `settings.FEATURE_<name>_ENABLED` top-level attr, (4) AAPFlag, (5) default. A new `sync_flag_values_from_settings()` function propagates installer overrides to AAPFlag rows so the Gateway UI reflects the installer's intent.
- **Insight**: The installer convention of writing `FEATURE_DASHBOARD_COLLECTION_ENABLED: True` directly into `settings.yaml` (as a top-level key, not inside the `FEATURE_ENABLED` dict) means Dynaconf surfaces it as a direct settings attribute. Without explicit handling in the precedence chain, this installer intent was invisible to the feature flag system. The sync function ensures the Gateway's AAPFlag rows match.

### Inline CORS middleware for dev-only cross-origin tools
- **Repo**: ansible/metrics-service
- **Commits**: 6316a02 (#254)
- **What happened**: A `_DevCorsMiddleware` class was added inline in `apps/settings/development.py` (not as a separate module or pip dependency). It handles OPTIONS preflight requests and adds `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`, `Access-Control-Allow-Credentials`, and `Access-Control-Max-Age` headers when an `Origin` request header is present. The middleware is injected at position 0 in the middleware stack via Dynaconf's `MIDDLEWARE = "@insert 0 apps.settings.development._DevCorsMiddleware"` marker. This enables the standalone dev dashboard (`tools/tasks/dashboard.html`) to call the API from a different origin (e.g., `file://` or a local static server).
- **Insight**: Defining the CORS middleware inline in the development settings file (rather than installing `django-cors-headers`) keeps it dev-only by construction -- it only loads when `METRICS_SERVICE_MODE=development`. The middleware trusts any Origin header, which is acceptable for local development but would be a security risk in production. The `django-cors-headers` package was previously removed in 911dd60 (#77) as unnecessary since CORS is handled at the gateway level in production.

### dev.sh --init flag for quick local development bootstrap
- **Repo**: ansible/metrics-service
- **Commits**: 6316a02 (#254)
- **What happened**: The `tools/dev.sh` script was updated to support a `--init` flag. When passed, it runs `manage.py migrate`, creates an `admin/admin` superuser via `createsuperuser --noinput`, and then explicitly sets the password to `admin` via a `manage.py shell` command (because `createsuperuser --noinput` with `DJANGO_SUPERUSER_PASSWORD` sometimes doesn't set it correctly). The `2>/dev/null || true` on the createsuperuser call makes it idempotent (succeeds even if the user already exists). Without `--init`, the script prints a hint about the flag instead of the previous `echo SKIPPED: $MANAGE migrate` message.
- **Insight**: A `--init` flag for the dev script provides a one-command bootstrap (`./tools/dev.sh --init`) that handles the common "I just cloned the repo, how do I start?" scenario. Making it a flag (rather than always running) avoids unnecessary migration and user-creation overhead on subsequent runs.

### Controller retention default flipped from opt-in to default-on
- **Repo**: ansible/metrics-service
- **Commits**: 5017a78 (#363)
- **What happened**: The `USE_CONTROLLER_RETENTION` setting in `DASHBOARD_COLLECTION` was changed from `False` to `True` in `apps/settings/defaults.py`. The fallback default in `_use_controller_retention()` (in `apps/dashboard_reports/tasks.py`) was also changed from `False` to `True`: `dashboard_cfg.get("USE_CONTROLLER_RETENTION", True)`. Dashboard retention now derives from Controller's `cleanup_jobs` schedule by default instead of using the hardcoded 90-day `DEFAULT_RETENTION_DAYS` constant.
- **Insight**: When an opt-in setting has been validated in production and the static fallback is no longer the preferred behavior, flip the default. Both the `defaults.py` setting and the code-level fallback must be updated in lockstep -- if only one is changed, the other provides a stale default on a different code path. **Supersedes** the opt-in default from #340.

### SEGMENT_URL setting for mock/test Segment server redirection
- **Repo**: ansible/metrics-service
- **Commits**: a2ee264 (#366)
- **What happened**: A new `SEGMENT_URL` setting was added to `apps/tasks/settings.py`, reading from the `MOCK_SEGMENT_URL` environment variable. The `StorageSegment` constructor in `send_anonymized_to_segment.py` now accepts `host=getattr(settings, "SEGMENT_URL", "") or None`, which redirects Segment API calls to a mock server when set, or uses the default Segment endpoint when `None`. The `or None` coercion ensures an empty string (unset env var) falls back to the SDK default rather than sending to an empty host.
- **Insight**: For external service integrations, a URL override setting (read from env var) allows redirecting traffic to a mock server in CI/test without code changes. The `getattr(settings, ..., "") or None` pattern safely handles the three cases: setting present (use it), setting empty string (fall back to default), setting absent (fall back to default).

## Superseded / Semi-Obsolete

### Database defaults to SQLite for development
- **Repo**: ansible/metrics-service
- Superseded by cb58dc0 (#11), which made PostgreSQL the default for all environments. SQLite is no longer supported.

### split_settings-based settings composition
- **Repo**: ansible/metrics-service
- The initial `settings/__init__.py` used `split_settings.tools.include` to compose settings from multiple files. This was replaced in 8b4aa31 (#26) by Dynaconf's settings layering system using DAB's `factory()`.

### Wildcard import in development.py
- **Repo**: ansible/metrics-service
- The `from .defaults import *` pattern in `development.py` was replaced in da91648 (#29) with explicit imports, then the entire file was deleted in 8b4aa31 (#26) when Dynaconf took over environment switching via `METRICS_SERVICE_MODE`.

### ConfigView for runtime config management
- **Repo**: ansible/metrics-service
- The `ConfigView` added in 8b4aa31 (#26) with `DYNACONF.merge()` was replaced in f4b136e (#31) by the `SettingView` with DB-backed change tracking and rollback.

### FEATURE_FLAGS / FEATURE_ENABLED naming
- **Repo**: ansible/metrics-service
- Originally `FEATURE_FLAGS`, renamed to `FEATURE_ENABLED` in c8e5f0d (#36) to avoid confusion with AAP's feature flags system. Further renamed to `FEATURE` in b7c4b1f (#250) to shorten the Dynaconf env var prefix.

### Manual URL prefix via METRICS_SERVICE_URL_PREFIX env var
- **Repo**: ansible/metrics-service
- The `os.getenv("METRICS_SERVICE_URL_PREFIX")` approach from 2efdae3 (#69) / a64071c (#70) was superseded by `settings.URL_PREFIX` in 7db9971 (#87), then refined with proper prefix interpretation in 85aed7f (#91). The `ServicePrefixMiddleware` from 52c8fb5 (#75) handles gateway-level prefix routing.

### DEVELOPER_MODE_ENABLED setting and DeveloperModeRequired permission
- **Repo**: ansible/metrics-service
- `DEVELOPER_MODE_ENABLED` removed in 7db9971 (#87), replaced by `settings.MODE == "development"` check. The `DeveloperModeRequired` permission class (which checked `settings.MODE`) was itself deleted in be9e010 (#253) when the tasks API switched to DAB's `IsSystemAdminOrAuditor` RBAC permission. The mode-based gating approach for the tasks API is now fully superseded by role-based access control.

### Segment write key as task parameter
- **Repo**: ansible/metrics-service
- Removed from task parameters in 1acd7b2 (#72). Now read from Django settings via `settings.METRICS_SERVICE_SEGMENT_WRITE_KEY`, with Dynaconf validation preventing the default value in production. Extended in 6b4f17c (#137) to also support loading from a file path for Konflux deployments.

### metrics_service/settings/ as a Python package
- **Repo**: ansible/metrics-service
- Replaced in 911dd60 (#77) by a single `metrics_service/settings.py` framework-managed file. Project settings moved to `apps/settings/`.

### config/settings.yaml
- **Repo**: ansible/metrics-service
- Removed in 911dd60 (#77). YAML-based settings overrides replaced by `apps/settings/{mode}.py` Python files and environment variables.

### SEGMENT_WRITE_KEY file content expected as base64-encoded
- **Repo**: ansible/metrics-service
- The base64 encoding pattern from 6b4f17c (#137) was removed in 1b38f9f (#141). The file is now read as plaintext with `.strip()`. The `_decode_segment_key()` helper was deleted.

### Conditional Dynaconf validation (skip in development, enforce in production)
- **Repo**: ansible/metrics-service
- The validation=True-but-skip-in-development approach from 8b4aa31 (#26) evolved through several iterations (production validators commented out in #137), was fully disabled in c7a06f1 (#143) with `validation=False`, and finally re-enabled in 956923d (#193) with `validation=True` and proper error messages on all four production validators. See the "Production startup validation re-enabled" learning above for the full arc.

### SEGMENT_WRITE_KEY default value in apps/tasks/settings.py
- **Repo**: ansible/metrics-service
- The hardcoded `SEGMENT_WRITE_KEY = "test-segment-write-key-change-in-production"` was commented out in e3b9969 (#144). The key must now be set via environment variables or file mount.

### Dynaconf validation turned off until gateway is fully implemented
- **Repo**: ansible/metrics-service
- Validation was disabled in c7a06f1 (#143) with `validation=False` because tech preview deployments lacked gateway configuration. Superseded by 956923d (#193) which re-enabled `validation=True` with all four production validators uncommented and enhanced with actionable error messages. The full validation saga: added (#26) -> conditional by environment (#77) -> validators commented out (#137) -> validation=False (#143) -> validation=True with proper messages (#193).

### Production validators for RESOURCE_SERVER__SECRET_KEY, ANSIBLE_BASE_JWT_KEY, SEGMENT_WRITE_KEY, ALLOWED_HOSTS
- **Repo**: ansible/metrics-service
- Commented out in 6b4f17c (#137) for tech preview deployment. Superseded by 956923d (#193) which uncommented all four validators and added actionable error messages specifying which environment variables to set.

### FEATURE_ENABLED renamed to FEATURE, feature flags made env-var driven without DB seeding
- **Repo**: ansible/metrics-service
- **Commits**: b7c4b1f (#250)
- **What happened**: The `FEATURE_ENABLED` dict in `defaults.py` was renamed to `FEATURE`, shortening the Dynaconf env var prefix from `METRICS_SERVICE_FEATURE_ENABLED__<KEY>` to `METRICS_SERVICE_FEATURE__<KEY>`. The `DEFAULT_SETTINGS` dict was emptied and its seeding loop removed from `initialize_default_settings()` -- feature flags are no longer pre-seeded into the database. Instead, flags resolve at runtime with three-tier precedence: (1) DB row in `dynamic_settings_setting` (always wins), (2) env var via `METRICS_SERVICE_FEATURE__*`, (3) static default in `settings.FEATURE`. The `init-default-settings` command was repurposed as an upgrade hook: it deletes redundant `true` DB rows for FEATURE flag keys (since `true` is the static default and the DB row would block env var overrides), while preserving `false` rows (explicit opt-outs). The `--overwrite` and `--all-known` CLI flags were removed as dead code. All references across code, tests, docker-compose, CLAUDE.md, and README were updated. Tests were rewritten to validate the new behavior (no rows created, `true` rows cleaned up, `false` rows preserved).
- **Insight**: Pre-seeding feature flags into the DB on fresh installs meant that setting `METRICS_SERVICE_FEATURE__<KEY>=false` had no effect -- the DB row (tier 1) always won over the env var (tier 2). Removing the seeding lets env vars take effect on fresh installs. The upgrade hook cleans up existing `true` rows that were redundant (matching the static default) so env vars work after upgrade too. This is a significant operational improvement: operators can now toggle feature flags via env vars without DB access.

### Feature flags simplified to single ANONYMIZED_DATA_COLLECTION toggle
- **Repo**: ansible/metrics-service
- The decision in e137d39 (#92) to remove `METRICS_COLLECTION_ENABLED` and make collection always-on was partially reversed in 68a2039 (#191). A new `METRICS_COLLECTION` flag (default: true) was added to gate local collection independently. The system now has three flags: `METRICS_COLLECTION`, `ANONYMIZED_DATA_COLLECTION`, and `DASHBOARD_COLLECTION`.

### FEATURE_ENABLED naming
- **Repo**: ansible/metrics-service
- Renamed to `FEATURE` in b7c4b1f (#250) to shorten the Dynaconf env var prefix. Previously renamed from `FEATURE_FLAGS` to `FEATURE_ENABLED` in c8e5f0d (#36) to avoid confusion with AAP's feature flags system.

### ServicePrefixMiddleware derived prefix from ROOT_URLCONF only
- **Repo**: ansible/metrics-service
- The middleware originally derived the service name from `settings.ROOT_URLCONF` only. In 35620f8 (#157), it was updated to use `settings.URL_PREFIX` when set, with ROOT_URLCONF as fallback.

### METRICS_UTILITY_CANDLEPIN_ENABLED master flag disables all Candlepin functionality by default
- **Repo**: ansible/metrics-utility
- **Commits**: ef734f3 (#460)
- **What happened**: A new `METRICS_UTILITY_CANDLEPIN_ENABLED` master flag was added (default: `False`) that controls all Candlepin-related functionality. When disabled, `handle_crc_ship_target()` returns early with only billing provider params, skipping cert loading from AWX DB, cert loading from local filesystem, consumer registration, and cert lifecycle (check-in and renewal). Additionally, the two sub-flags were also changed to default to `False` for consistency: `METRICS_UTILITY_CANDLEPIN_REGISTRATION_ENABLED` (was `True`) and `METRICS_UTILITY_CANDLEPIN_LIFECYCLE_ENABLED` (was `True`). To enable full Candlepin functionality, operators must now explicitly set all three flags. The check is early in the function (before any Candlepin imports or operations), so disabled mode has minimal overhead. All Candlepin test classes were updated to set `METRICS_UTILITY_CANDLEPIN_ENABLED=true` in their autouse fixtures.
- **Insight**: When a complex subsystem has multiple feature flags, a single master flag that short-circuits the entire code path is simpler for operators than understanding the interactions between sub-flags -- especially when the subsystem should be opt-in (not opt-out). Changing all related flag defaults to match the master flag's default prevents the confusing scenario where the master is `False` but sub-flags default to `True`. **Supersedes** the default=True behavior for `CANDLEPIN_REGISTRATION_ENABLED` and `CANDLEPIN_LIFECYCLE_ENABLED` from #363.

### Framework alignment: project settings moved from protected files to apps/settings layer
- **Repo**: ansible/metrics-service
- **Commits**: 6c01004 (#267)
- **What happened**: AAP-69237 compliance required `metrics_service/settings.py` to match the platform-service-framework (PSF) template exactly. All project-specific code was moved out: (1) Segment key loading moved to `apps/core/segment.py` with a Dynaconf `@post_hook` in `apps/settings/defaults.py`. (2) `ALLOWED_HOSTS` parsing (CSV/JSON) moved to a `parse_allowed_hosts_env` post-hook. (3) JSON logging setup moved to a `setup_json_logging_for_production` post-hook. (4) WhiteNoise middleware, template dirs, dashboard collection config, and staticfiles dirs all moved to `defaults.py`. (5) PostgreSQL OPTIONS normalization removed entirely (installer now handles via `DATABASES__awx__OPTIONS__options` env var). (6) The `_mode` detection logic simplified -- `PRODUCTION=1/true/yes` fallback removed, just reads `METRICS_SERVICE_MODE`. (7) A `framework-validation.yml` workflow re-added (using `uvx ... validate` from the PSF repo). (8) `manage.py` made executable (100755) to match template. Post-hooks return dicts (not call `.set()`) which is the correct Dynaconf pattern.
- **Insight**: The PSF distinguishes between "protected files" (must match template exactly) and "editable files" (like `apps/settings/defaults.py`). Dynaconf `@post_hook` functions are the correct mechanism for project-specific settings that depend on other settings being loaded first -- they return a dict of values to set, not call `.set()` directly. `PSF-OVERRIDE` markers should only be used in protected files.

### Dynaconf post-hook pattern: return dict, do not call .set() directly
- **Repo**: ansible/metrics-service
- **Commits**: 6c01004 (#267)
- **What happened**: The initial implementation of the Segment key post-hook called `dynaconf_instance.set()` directly inside the hook. This is incorrect -- Dynaconf `@post_hook` functions must return a dict with the keys/values to set. The hook was fixed to `return {"SEGMENT_WRITE_KEY": key}` (or `return {}` when no change needed). Similarly, the ALLOWED_HOSTS parsing, which previously called `DYNACONF.set("ALLOWED_HOSTS", allowed_hosts)` inline in `settings.py`, was converted to a post-hook returning `{"ALLOWED_HOSTS": allowed_hosts}`.
- **Insight**: Dynaconf `@post_hook` functions must return a dict of values to set, not call `.set()` directly. This is a subtle API distinction that can cause silent failures if done wrong.

### DASHBOARD_COLLECTION feature flag promoted from opt-in to default-on
- **Repo**: ansible/metrics-service
- **Commits**: 13ad18b (#275)
- **What happened**: The `DASHBOARD_COLLECTION` feature flag was changed from default-off (opt-in) to default-on. Previously, `DASHBOARD_COLLECTION` was intentionally omitted from the `FEATURE` dict in `defaults.py` so it defaulted to `False` in `get_feature_enabled_from_db`. Now it's added to the dict as `"DASHBOARD_COLLECTION": True`. The `feature_flags.yaml` file (29 lines) and the entire `load_task_feature_flags` / `sync_flag_values_from_settings` machinery in `apps/tasks/apps.py` (135 lines) were deleted -- the feature flag YAML seeding approach was replaced by the simpler `FEATURE` dict + env var override pattern. The `metrics_service` management command's `--skip-feature-flag-init` argument was also removed. Opt-out is still possible via `METRICS_SERVICE_FEATURE__DASHBOARD_COLLECTION=false` env var, installer top-level attribute, or Gateway UI toggle.
- **Insight**: When a feature flag transitions from opt-in to default-on, simplify the flag management machinery. The YAML-based `AAPFlag` seeding approach (with `post_migrate` signal, `sync_flag_values_from_settings`, etc.) was over-engineered for a flag that's now just a boolean in a dict. The `FEATURE` dict + Dynaconf env var override provides the same 5-tier precedence without the complexity. **Supersedes** the feature_flags.yaml approach from #184 and the post_migrate seeding from #168.

### Event collector resource limits as Dynaconf settings
- **Repo**: ansible/metrics-service
- **Commits**: 8daf1af (#295), 7b16727 (#300)
- **What happened**: Two new settings were added to `defaults.py` for controlling event collection resource usage: `JOBEVENT_ROW_LIMIT` (max event rows per hourly run, default 200K, ~140-180MB) and `JOBEVENT_JOB_LIMIT` (max jobs processed per window, default 1K). Both are overridable via `METRICS_SERVICE_JOBEVENT_ROW_LIMIT` / `METRICS_SERVICE_JOBEVENT_JOB_LIMIT` env vars (standard Dynaconf naming). The initial row limit was 1M but was reduced to 200K in a follow-up PR based on memory profiling.
- **Insight**: For resource-bounded settings, start conservative and document the memory implications in comments (e.g., "at ~700-900 bytes/row, 200K rows is ~140-180 MB"). Having two independent limit dimensions (rows and jobs) gives operators fine-grained control without modifying code.

### Platform auditor RBAC bypass via ANSIBLE_BASE_BYPASS_ACTION_FLAGS
- **Repo**: ansible/metrics-service
- **Commits**: c99bfe5 (#302)
- **What happened**: System auditor users were getting 401 on `GET /api/v1/dashboard_reports/collection_status/` because DAB's `has_super_permission(user, 'view')` returned `False` for them. The gateway conveys auditor status via JWT `global_roles` (not `user_data`), so no user flag was set and the bypass-action-flag check found nothing. The fix: (1) Added `User.is_platform_auditor` property that queries RBAC assignments for the "Platform Auditor" `RoleDefinition` (no migration needed, role is already synced from JWT claims by `save_user_claims`). (2) Set `ANSIBLE_BASE_BYPASS_ACTION_FLAGS = {"view": "is_platform_auditor"}` in `defaults.py` (mirroring `aap_gateway_api/defaults.py`). (3) Updated `test.py` to use the same setting. Superusers bypass via `ANSIBLE_BASE_BYPASS_SUPERUSER_FLAGS` before the action-flag check fires.
- **Insight**: DAB's `IsSystemAdminOrAuditor` permission class uses `has_super_permission()` which checks `ANSIBLE_BASE_BYPASS_ACTION_FLAGS` for action-specific bypasses. Each AAP service must configure this setting identically to the gateway (e.g., `{"view": "is_platform_auditor"}`) for auditor access to work correctly. The property-based approach (`User.is_platform_auditor`) avoids adding a migration while still being compatible with `getattr(user, flag_name)` lookup in DAB.

### Dashboard retention hardcoded to 90 days with opt-in controller setting
- **Repo**: ansible/metrics-service
- **Commits**: 10eb8bf (#340)
- **What happened**: The `get_retention_days()` function (introduced in #319) reads from the Controller's active `cleanup_jobs` schedules to determine the retention window for dashboard backfill and cleanup. However, this code path was not fully tested in all deployment scenarios. It was gated behind a new `DASHBOARD_COLLECTION['USE_CONTROLLER_RETENTION']` setting (default `False`) so both initial backfill and daily cleanup use the fixed 90-day `DEFAULT_RETENTION_DAYS` constant by default. Opt-in via `METRICS_SERVICE_DASHBOARD_COLLECTION__USE_CONTROLLER_RETENTION=true` or `settings.yaml`. A `_use_controller_retention()` helper centralizes the check for both `_resolve_collection_params()` and `cleanup_dashboard_reports_old_data()`.
- **Insight**: When a dynamically-derived setting (reading from another service's DB) hasn't been validated in all environments, gate it behind an opt-in flag with a safe static default. This allows shipping the feature while providing a safe fallback. The nested Dynaconf key pattern (`DASHBOARD_COLLECTION__USE_CONTROLLER_RETENTION`) works via double-underscore for dict nesting.

### SonarQube rule python:S8572 suppressed globally for logging policy
- **Repo**: ansible/metrics-service
- **Commits**: 27c94ba (#279)
- **What happened**: SonarQube rule python:S8572 mandates `logger.exception()` over `logger.error()` in all except blocks. The team's policy is more nuanced: use `logger.exception()` (which includes traceback) for broad `except Exception` catches where the exception may be unexpected, but use `logger.error()` for expected cases (e.g., `Task.DoesNotExist`) where the traceback adds noise. The rule was suppressed globally in `sonar-project.properties` via `sonar.issue.ignore.multicriteria.e4`. Specific handlers were also split to have separate `except DoesNotExist` (logger.error) and `except Exception` (logger.exception) clauses.
- **Insight**: Blanket lint rules like "always use logger.exception in except blocks" don't fit all codebases. Expected error cases (DoesNotExist, known validation failures) should use `logger.error` to avoid log noise, while unexpected catches should use `logger.exception` to preserve the traceback. Suppressing the rule globally and documenting the policy is better than sprinkling `# noqa` comments everywhere.

### INSTALL_TYPE setting for deployment method tracking
- **Repo**: ansible/metrics-service
- **Commits**: 046e55e (#352)
- **What happened**: `INSTALL_TYPE = "containerized"` added to `apps/settings/defaults.py`, overridable via `METRICS_SERVICE_INSTALL_TYPE` env var. The operator companion PR injects `METRICS_SERVICE_INSTALL_TYPE=operator`. Used in `daily_anonymize_and_prepare` to include `install_type` in `summary_metadata`. Follows the standard Dynaconf pattern: setting name in defaults.py, prefixed env var for override.
- **Insight**: The `METRICS_SERVICE_` env var prefix is the standard Dynaconf convention for this project. New settings should follow the pattern: define in `apps/settings/defaults.py` with a reasonable default, override via `METRICS_SERVICE_<SETTING_NAME>` env var.
