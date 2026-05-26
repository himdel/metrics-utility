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

### S3 ship target requires bucket configuration env vars
- **Repo**: ansible/metrics-utility
- **Commits**: 1e86f8c
- **What happened**: The `s3` ship target requires: `METRICS_UTILITY_SHIP_PATH` (S3 key prefix, e.g. `metrics-utility/shipped_data`), `METRICS_UTILITY_BUCKET_NAME`, `METRICS_UTILITY_BUCKET_ENDPOINT`, `METRICS_UTILITY_BUCKET_ACCESS_KEY`, `METRICS_UTILITY_BUCKET_SECRET_KEY`. Optional: `METRICS_UTILITY_BUCKET_REGION` (needed for AWS S3 but not for S3-compatible stores like MinIO). The `SHIP_PATH` for S3 is a key prefix rather than a filesystem path, reusing the same env var name for consistency across ship targets.
- **Insight**: The S3 adapter supports any S3-compatible object storage (not just AWS), so `BUCKET_ENDPOINT` is required rather than assuming AWS, and `BUCKET_REGION` is optional.

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

### S3 env var error handling: report missing vars individually, warn about surplus vars
- **Repo**: ansible/metrics-utility
- **Commits**: 75a83bc (#129)
- **What happened**: The S3 ship target validation was improved in two ways: (1) Instead of a single generic "missing one of..." error message, each missing S3 env var (`METRICS_UTILITY_BUCKET_NAME`, `BUCKET_ENDPOINT`, `BUCKET_ACCESS_KEY`, `BUCKET_SECRET_KEY`, `SHIP_PATH`) is listed individually with a description (e.g., "METRICS_UTILITY_BUCKET_NAME - name of S3 bucket"). (2) New `handle_not_s3()` and `handle_not_crc()` functions were added that emit warnings when S3 or CRC env vars are set but the ship target doesn't use them (e.g., setting `METRICS_UTILITY_BUCKET_NAME` when `SHIP_TARGET=directory`). Similarly, `handle_crc_ship_target()` now warns if `METRICS_UTILITY_SHIP_PATH` is set (which CRC doesn't use). The validation functions also had the unused `ship_target` parameter removed from their signatures.
- **Insight**: Listing each missing env var individually with its purpose makes misconfiguration much easier to fix than a generic "missing one of these five vars" message; warning about surplus env vars catches copy-paste configuration errors.

### Removed unused METRICS_UTILITY_BUCKET_ID and METRICS_UTILITY_BUCKET_KEY env vars
- **Repo**: ansible/metrics-utility
- **Commits**: b487ac2 (#131)
- **What happened**: The `build_report` command read `METRICS_UTILITY_BUCKET_ID` and `METRICS_UTILITY_BUCKET_KEY` env vars into `extra_params['s3_bucket_id']` and `extra_params['s3_bucket_key']`, but these were never used anywhere downstream. They appear to be remnants from an early S3 implementation that was replaced by `METRICS_UTILITY_BUCKET_ACCESS_KEY` and `METRICS_UTILITY_BUCKET_SECRET_KEY`. The dead reads were removed along with the README documentation for these vars.
- **Insight**: When adding new env var names to replace old ones, remove the old reads at the same time -- dead env var reads in code confuse operators into setting variables that do nothing.

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

### `MAX_GATHER_PERIOD_WEEKS` replaced by configurable `METRICS_UTILITY_MAX_GATHER_PERIOD_DAYS` env var
- **Repo**: ansible/metrics-utility
- **Commits**: 594395c (#181)
- **What happened**: The hardcoded `Collector.MAX_GATHER_PERIOD_WEEKS = 4` class constant (introduced in #168) was removed and replaced with a `METRICS_UTILITY_MAX_GATHER_PERIOD_DAYS` env var, defaulting to 28 (same effective value). A `get_max_gather_period_days()` function in `base/utils.py` reads and parses the env var. Validation in `validation.py` enforces the value is 0-3650 (max 10 years). All references to `timedelta(weeks=...)` were changed to `timedelta(days=get_max_gather_period_days())`. The unit was changed from weeks to days for finer granularity, and setting it to 0 is allowed (useful for `limit_slicing` collectors that only need today's data).
- **Insight**: Making the gather period configurable via env var (rather than a class constant) enables operators to extend or shorten the collection window without code changes -- the 4-week default was too short for some deployments that needed historical backfill. **Supersedes** the `MAX_GATHER_PERIOD_WEEKS` constant from #168.

### New env vars for vCPU collector and SaaS billing
- **Repo**: ansible/metrics-utility
- **Commits**: 429816e (#165), 0be6cd0 (#198)
- **What happened**: The `total_workers_vcpu` collector introduced several new env vars: `METRICS_UTILITY_CLUSTER_NAME` (required, identifies the cluster), `METRICS_UTILITY_USAGE_BASED_METERING_ENABLED` (when `true`, queries Prometheus for actual vCPU count; when `false` or unset, reports `total_workers_vcpu=1`), `METRICS_UTILITY_PROMETHEUS_URL` (Prometheus server URL, defaults to the in-cluster OpenShift monitoring endpoint), `METRICS_UTILITY_COLLECTOR_LOCK_SUFFIX` (appended to the advisory lock name to allow multiple collector instances on the same DB), and `METRICS_UTILITY_DISABLE_SAVE_LAST_GATHERED_ENTRIES` (when `true`, skips persisting last-gathered timestamps). Additionally, `METRICS_UTILITY_DISABLE_JOB_HOST_SUMMARY_COLLECTOR` (when `true`, disables the default `job_host_summary` collector) was added to support SaaS deployments that only need vCPU counting. Note: `METRICS_UTILITY_USAGE_BASED_BILLING_ENABLED` was renamed to `METRICS_UTILITY_USAGE_BASED_METERING_ENABLED` in #198.
- **Insight**: The SaaS billing use case required the ability to disable the default `job_host_summary` collector and run only the vCPU collector -- the existing `METRICS_UTILITY_OPTIONAL_COLLECTORS` mechanism only gates optional collectors, not the mandatory default one.

### `get_optional_collectors()` moved from collectors.py to base/utils.py
- **Repo**: ansible/metrics-utility
- **Commits**: f15bd74 (#185)
- **What happened**: The `get_optional_collectors()` function was moved from `collectors.py` to `metrics_utility/base/utils.py` so it could be imported by both `collectors.py` and the base `Collector` class without circular imports. Previously it had been moved from `collectors.py` to `metric_utils.py` (in #75), then back to `collectors.py` (in #153), and now to `base/utils.py`. The base `Collector._gather_csv_collections()` now uses it to determine which collectors are enabled for progress logging.
- **Insight**: Shared utility functions that are needed by both the collector framework (base) and the specific collectors should live in `base/utils.py` to avoid circular import issues -- this function has been moved three times, settling in the lowest-level module that both sides can import.

### New service collectors added to VALID_COLLECTORS
- **Repo**: ansible/metrics-utility
- **Commits**: 0c851b4 (#214)
- **What happened**: Four new collector names were added to `VALID_COLLECTORS` in `validation.py`: `unified_jobs`, `job_host_summary_service`, `main_jobevent_service`, and `execution_environments`. These are gated by `METRICS_UTILITY_OPTIONAL_COLLECTORS` like all other optional collectors and are intended for the metrics service use case (anonymized aggregations).
- **Insight**: Every new optional collector requires an entry in `VALID_COLLECTORS` in validation.py -- the env var validation rejects unknown collector names to catch typos early.

### METRICS_UTILITY_OPTIONAL_COLLECTORS empty string removed from VALID_COLLECTORS, parsed with filter(bool)
- **Repo**: ansible/metrics-utility
- **Commits**: aafd74c (#263)
- **What happened**: The earlier fix (#178) handled empty/whitespace `METRICS_UTILITY_OPTIONAL_COLLECTORS` by adding `''` to `VALID_COLLECTORS`. This was replaced with a cleaner approach: `get_optional_collectors()` now strips whitespace and uses `filter(bool, ...)` to remove empty strings after splitting by comma. The validation in `validation.py` similarly strips and checks for empty before splitting. This eliminates the magic empty string from the valid set.
- **Insight**: Rather than adding empty string as a "valid" sentinel value, use `filter(bool, s.split(','))` to cleanly handle the empty/whitespace case -- this removes the need for any special case in the valid values set. **Supersedes** the empty string workaround from #178.

### `main_host_daily` added to VALID_COLLECTORS for incremental host collection
- **Repo**: ansible/metrics-utility
- **Commits**: 2afe3c7 (#209)
- **What happened**: The `main_host_daily` collector was added to `VALID_COLLECTORS` in `validation.py`, enabling operators to set `METRICS_UTILITY_OPTIONAL_COLLECTORS=main_host_daily` for time-bounded host collection (daily slicing) as an alternative to the existing `main_host` (full snapshot via limit slicing). The recommended deployment pattern is to use `main_host_daily` for daily cronjobs (collecting only hosts created/modified that day) and `main_host` with `METRICS_UTILITY_DISABLE_JOB_HOST_SUMMARY_COLLECTOR=true` for weekly full snapshots.
- **Insight**: Adding `main_host_daily` alongside `main_host` gives operators a choice between completeness (full inventory snapshot) and efficiency (only recently changed hosts) via the same `METRICS_UTILITY_OPTIONAL_COLLECTORS` mechanism.

### `credentials_service`, `table_metadata`, and `controller_version` added to VALID_COLLECTORS
- **Repo**: ansible/metrics-utility
- **Commits**: 456eb0f (#319), 3d86b71 (#328)
- **What happened**: Three new collector names were added to `VALID_COLLECTORS` in `validation.py`: `credentials_service` (credential type distribution, filtered to managed credentials only), `table_metadata` (PostgreSQL table sizes and row counts for key tables), and `controller_version` (distinct controller versions from enabled instances). All are gated by `METRICS_UTILITY_OPTIONAL_COLLECTORS` and intended for the anonymized rollup pipeline. The `credentials_service` collector only collects credentials where `credential_type__managed = true`, avoiding exposure of custom credential type names in anonymized data.
- **Insight**: Infrastructure telemetry collectors (table metadata, controller version) provide deployment-level context alongside the existing application-level collectors (jobs, events, hosts), enabling the metrics service to understand both what automation is running and the scale of the infrastructure supporting it.

### `METRICS_UTILITY_DB_*` env vars extended and warned about in controller mode
- **Repo**: ansible/metrics-utility
- **Commits**: ae0878a (#359)
- **What happened**: The `mock_awx/settings/__init__.py` DB configuration was expanded to read `METRICS_UTILITY_DB_NAME`, `METRICS_UTILITY_DB_USER`, `METRICS_UTILITY_DB_PASSWORD`, and `METRICS_UTILITY_DB_PORT` (in addition to the existing `METRICS_UTILITY_DB_HOST`), with defaults matching the Docker Compose dev setup (`awx`, `myuser`, `mypassword`, `5432`). A warning was added to `metrics_utility/__init__.py`: when Controller modules are found (i.e., running inside a real Controller venv), any `METRICS_UTILITY_DB_*` env vars are logged as ignored with a message that they only take effect in standalone mode. The Makefile also gained `pcompose`, `pclean`, and `ppsql` targets for podman-compose users.
- **Insight**: When env vars only apply in one operating mode (standalone) but are ignored in another (controller venv), warn the user explicitly -- silent ignoring of configuration is a common source of confusion when operators copy configs between environments.

### `config` collector version bumped to 2.0 for nullable fields
- **Repo**: ansible/metrics-utility
- **Commits**: b7ff6f6 (#355)
- **What happened**: The `config` collector's version in the manifest was bumped from 1.0 to 2.0 because the DB-based refactoring in #242 made some config fields nullable that were previously guaranteed non-null (when read from `django.conf.settings` they always had values; when read from `conf_setting` table they can be absent). The version bump signals to tarball consumers that all config fields should be treated as nullable.
- **Insight**: When a collector refactoring changes field nullability (even unintentionally), bump the manifest version to signal the breaking change to downstream consumers -- this is especially important for the config collector whose fields are used as metadata for all other collections.

