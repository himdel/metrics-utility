# Settings and Configuration

> Default repo: metrics-service

## Learnings

### Environment variable naming went through three iterations in two days
- **Commits**: dd5603f, be51903, 5e05775
- **What happened**: Initial commit used `MY_SERVICE_` prefix (e.g., `MY_SERVICE_DB_HOST`). Commit be51903 renamed to lowercase `metrics_service_` (e.g., `metrics_service_DB_HOST`). The very next commit (5e05775) fixed the casing to uppercase `METRICS_SERVICE_` (e.g., `METRICS_SERVICE_DB_HOST`) -- but only partially, leaving some env vars still lowercase (e.g., `metrics_service_REDIS_URL`, `metrics_service_ALLOWED_HOSTS`).
- **Insight**: Environment variable naming conventions should be established before the first commit. The inconsistent casing (`METRICS_SERVICE_` vs `metrics_service_`) persisted across docker-compose, k8s manifests, and Python settings files, creating a confusing mix. Convention should be ALL_CAPS for env vars.

### Database defaults to SQLite for development, PostgreSQL for Docker/production
- **Commits**: dd5603f
- **What happened**: `defaults.py` checks `METRICS_SERVICE_DB_ENGINE` env var, defaulting to `django.db.backends.sqlite3`. A separate conditional block enables PostgreSQL when the engine env var is explicitly set to `django.db.backends.postgresql`, providing different defaults for host/port/user.
- **Insight**: The dual-database-default pattern (SQLite for bare-metal dev, PostgreSQL for everything else) reduces friction for new developers but means the two environments can diverge in behavior (e.g., SQLite doesn't enforce foreign keys the same way).

### Dynaconf settings file (config/settings.yaml) committed with real-ish credentials
- **Commits**: dd5603f
- **What happened**: `config/settings.yaml` was committed with database password `dabing`, email password `your_email_password`, and other placeholder secrets. While labeled as examples, these were in a non-`.example` file that would be loaded by default.
- **Insight**: Configuration files with placeholder credentials should either be `.example` files (git-tracked) or loaded from environment/secrets only. Committing them risks developers running with insecure defaults in production.

### Port 55432 used as default PostgreSQL port
- **Commits**: dd5603f, 5e05775
- **What happened**: Both the docker-compose and the settings defaults use port `55432` for PostgreSQL, not the standard `5432`. Docker maps `55432:5432` externally.
- **Insight**: Using a non-standard external port (55432) avoids conflicts with any local PostgreSQL instance on the developer's machine. The container itself runs on standard 5432 internally.

### PostgreSQL became the default database for all environments
- **Commits**: cb58dc0 (#11)
- **What happened**: The settings defaults were changed from SQLite-with-optional-PostgreSQL to PostgreSQL-always. The `DATABASES` config in `defaults.py` was simplified to always use `django.db.backends.postgresql` with default host `127.0.0.1`, port `55432`, user `metrics_service`, password `metrics_service`. The conditional block that checked `METRICS_SERVICE_DB_ENGINE` was removed entirely.
- **Insight**: This was a deliberate decision to eliminate the SQLite/PostgreSQL divergence. All developers must now run PostgreSQL locally (via Docker or native install). The `.env.example` file was added to document the required env vars. This prevents bugs where code works on SQLite but fails on PostgreSQL (e.g., JSONField behavior, transaction handling).

### DAB oauth2_provider and feature_flags apps disabled due to conflicts
- **Commits**: cb58dc0 (#11)
- **What happened**: Two DAB apps were commented out in the `DAB_APPS` list: `ansible_base.oauth2_provider` ("Disabled due to model conflicts") and `ansible_base.feature_flags` ("Disabled due to missing 'flags' module"). They had been enabled in the defaults but caused errors during startup.
- **Insight**: DAB apps can have implicit dependencies on specific database state, other DAB apps, or third-party packages that aren't always available. The team's approach of commenting out problematic apps with explanatory comments is pragmatic but the feature flags app being disabled meant the project needed its own feature flag mechanism (which was later built as `apps/dynamic_settings/`).

### development.py settings deleted and recreated multiple times
- **Commits**: cb58dc0 (#11), c6947ce (#14), d85322e (#18), da91648 (#29)
- **What happened**: The `metrics_service/settings/development.py` file was deleted in cb58dc0 as part of "consolidating settings," then recreated in the same commit's later squashed commits, then deleted and recreated again in c6947ce. In da91648, it was refactored from using `from .defaults import *` (wildcard import) to explicitly importing each setting by name from `defaults`.
- **Insight**: The wildcard import (`from .defaults import *`) was flagged by Sonar as a code quality issue, leading to the explicit import pattern. However, explicitly listing 20+ settings is verbose and fragile -- any new setting in `defaults.py` must be manually added to `development.py`. This was likely later resolved by Dynaconf's layering.

### Redis removed as a dependency for development
- **Commits**: d85322e (#18)
- **What happened**: Redis cache configuration was removed from the development settings. The cache backend was switched to Django's local memory cache (`django.core.cache.backends.locmem.LocMemCache`) for development. Redis references were removed from docker-compose, `.env.example`, and settings files.
- **Insight**: Redis was premature infrastructure for the development environment. The service doesn't currently use caching in a way that requires Redis, and removing it reduces the setup burden for developers. Redis can be re-added when actually needed.

### Dynaconf integration replaced split_settings in a two-phase rollout
- **Commits**: 8b4aa31 (#26), f4b136e (#31)
- **What happened**: Phase 1 (8b4aa31) introduced Dynaconf by replacing `split_settings.tools.include` and `dynamic_config` imports with DAB's `factory()` call. The settings `__init__.py` was rewritten to create a `DYNACONF` object using `factory(module_name=__name__, app_name="METRICS_SERVICE", ...)` with validators, environment-aware sections, and a loading order: `defaults.py` -> `/etc/ansible-automation-platform/settings.yaml` -> `config/settings.yaml` -> env vars. A `ConfigView` was added for runtime config viewing/reloading via API. Phase 2 (f4b136e) replaced the `ConfigView` with a RESTful `SettingView` backed by a new `Setting` DB model, adding change tracking and rollback capability. The `ConfigView` allowed arbitrary config updates via `DYNACONF.merge()`, which was replaced by guarded `DYNACONF.set()` with validation that keys already exist.
- **Insight**: The two-phase approach was intentional -- Phase 1 established the Dynaconf plumbing while Phase 2 added persistence and auditability. The PR #26 description explicitly noted "Configuration/Settings changes will not persist after an app restart. That work will come in via a later PR." Splitting infra from business logic into separate PRs made each reviewable.

### Environment switcher changed from METRICS_SERVICE_ENV to METRICS_SERVICE_MODE
- **Commits**: 8b4aa31 (#26)
- **What happened**: The Dynaconf integration changed the environment switching variable from `METRICS_SERVICE_ENV` to `METRICS_SERVICE_MODE`. A comment in the code explicitly notes "Factory uses METRICS_SERVICE_MODE as the env_switcher (not METRICS_SERVICE_ENV)". The `development.py` settings file was deleted since Dynaconf handles environment sections in `config/settings.yaml`.
- **Insight**: The rename from `_ENV` to `_MODE` aligns with Dynaconf convention and distinguishes the settings layer selector from the deployment environment. This also means `DJANGO_SETTINGS_MODULE` becomes just `metrics_service.settings` (no `.development` suffix) since Dynaconf handles the mode internally.

### Dynaconf validators enforce production security but skip in development
- **Commits**: 8b4aa31 (#26)
- **What happened**: Multiple Dynaconf `Validator` objects were added to ensure `SECRET_KEY` is not any of the three default values (from `defaults.py`, from the YAML default section, or from the YAML production section). Database settings (`DATABASES.default.NAME`, `HOST`, `USER`, `PASSWORD`) must exist. However, validation is skipped in development mode via `export(__name__, DYNACONF, validation=not is_development)`.
- **Insight**: The conditional validation means production deployments fail fast if secrets aren't configured, while development "just works" with defaults. The three separate validators for `SECRET_KEY` (one per possible default value source) show how multiple config sources create multiple bad-default scenarios.

### config/settings.yaml restructured with environment sections
- **Commits**: 8b4aa31 (#26)
- **What happened**: The YAML config was restructured from flat lowercase keys (e.g., `secret_key`, `databases.default.engine`) to Dynaconf environment sections (`default:`, `development:`, `production:`) with uppercase Django-style keys (e.g., `SECRET_KEY`, `DATABASES.default.ENGINE`). Email config and OAuth2/JWT settings were removed. The production section explicitly sets `SECRET_KEY: 'PRODUCTION-SECRET-KEY-NOT-SET'` to force override.
- **Insight**: Using uppercase keys in YAML matching Django's convention eliminates case translation bugs. The production section's invalid-sentinel approach (setting `SECRET_KEY` to a clearly-wrong value) combines with the validator to ensure production configs are explicitly set.

### Database env var naming switched to Dynaconf dunder notation
- **Commits**: 8b4aa31 (#26)
- **What happened**: `.env.example` changed database env vars from flat naming (`METRICS_SERVICE_DB_HOST`, `METRICS_SERVICE_DB_PORT`) to Dynaconf nested dunder notation (`METRICS_SERVICE_DATABASES__default__HOST`, `METRICS_SERVICE_DATABASES__default__PORT`). Port default also changed from 55432 to 5432.
- **Insight**: Dunder notation (`__`) lets Dynaconf automatically build nested dicts that Django expects for `DATABASES`. The flat `DB_HOST` style required custom parsing code; dunder notation eliminates that entirely. However, the env var names are now longer and harder to type.

### FEATURE_FLAGS renamed to FEATURE_ENABLED to avoid AAP naming conflict
- **Commits**: c8e5f0d (#36)
- **What happened**: The settings dict was renamed from `FEATURE_FLAGS` to `FEATURE_ENABLED` across defaults.py, test.py, and task_groups.py. The `TaskGroup` class attribute `enabled_flag` was renamed to `enabled_setting`. The commit message says "changing feature flag to feature enable ... to avoid confusion with the actual feature flag in Ansible."
- **Insight**: AAP already has a "feature flags" concept (from `ansible_base.feature_flags` which was disabled earlier). Using the same term in this service created confusion about which feature flag system was being referenced. The rename to `FEATURE_ENABLED` distinguishes this service's runtime toggles from AAP's feature flags system.

### Feature toggles became DB-driven with Django settings fallback
- **Commits**: c8e5f0d (#36)
- **What happened**: The `task_groups.py` module added `get_feature_enabled_from_db()` which queries the `Setting` model first, then falls back to `getattr(settings, "FEATURE_ENABLED", {})`. The enable/disable functions (`enable_task_group`, `disable_task_group`) were changed from placeholder stubs ("Would enable task group") to real implementations that create/update `Setting` DB rows with `get_or_create()`. A `set_feature_enabled()` helper and `get_feature_enabled_status()` reporting function were also added.
- **Insight**: The DB-first-with-settings-fallback pattern means feature toggles can be changed at runtime via API without restart, but still have sane defaults from `settings.py` for fresh deployments. The `get_feature_enabled_status()` function reports the source (database/django_settings/default) for each toggle, which is valuable for debugging.

### Dynaconf @json format for list-type env vars
- **Commits**: 2e4cea6 (#47), 6059d8c (#45)
- **What happened**: `.env.example` changed from comma-separated lists (`METRICS_SERVICE_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0`) to Dynaconf `@json` format (`METRICS_SERVICE_ALLOWED_HOSTS='@json ["localhost", "127.0.0.1", "0.0.0.0"]'`). The docker-compose.yml also switched to JSON array format for `ALLOWED_HOSTS`.
- **Insight**: Comma-separated strings require custom parsing and don't work for values that themselves contain commas. Dynaconf's `@json` prefix provides unambiguous list/dict typing directly in env vars. The trade-off is slightly more verbose env var syntax.

### Centralized logging with configurable log level via env var
- **Commits**: 7d50113 (#51)
- **What happened**: A `METRICS_SERVICE_LOG_LEVEL` environment variable was added (defaulting to `INFO`), read via `os.environ.get()` in `defaults.py`. All four logger definitions (`ansible_base`, `metrics_service`, `django`, root) were changed from hardcoded levels (`INFO`/`DEBUG`/`WARNING`) to use the single `LOG_LEVEL` variable. The `run_dispatcherd` command had redundant logging setup removed.
- **Insight**: A single env var controlling all loggers is practical for deployment simplicity -- operators don't need to know the internal logger hierarchy. The trade-off is loss of per-component log level control (e.g., you can't set Django to WARNING while keeping metrics_service at DEBUG). The `os.environ.get()` approach is used instead of Dynaconf because this runs at settings module load time.

### DEVELOPER_MODE_ENABLED feature gate for production safety
- **Commits**: dbf6fb1 (#65)
- **What happened**: A `DEVELOPER_MODE_ENABLED` setting was added (default `False`) to `defaults.py`, overridable via `METRICS_SERVICE_DEVELOPER_MODE_ENABLED`. A `DeveloperModeRequired` DRF permission class in `apps/core/permissions.py` checks this setting and returns 403 when disabled. A `require_developer_mode` decorator (using `functools.wraps`) does the same for plain Django views. Both `TaskViewSet` and `TaskExecutionViewSet` switched from `permission_classes = [AllowAny]` (which was marked "Temporary for dashboard access") to `[DeveloperModeRequired]`. The dashboard view also gained the decorator. Test settings set `DEVELOPER_MODE_ENABLED = True`.
- **Insight**: This is a clean pattern for gating debug/development endpoints in production: a single boolean setting controls access, checked at two layers (DRF permissions for API, decorator for views). The previous `AllowAny` permission on task endpoints was a security risk that persisted for months.

### DEBUG explicitly disabled for production environments
- **Commits**: 7b39f53 (#56)
- **What happened**: `METRICS_SERVICE_DEBUG` was changed to `false` in `.env.example`, and `DEBUG = False` was set in `defaults.py`. Previously, DEBUG had been left as `True` or configurable, making it easy to accidentally run with debug mode enabled.
- **Insight**: Django's `DEBUG = True` exposes stack traces, SQL queries, and other sensitive information. Defaulting to `False` in the base settings file means production is safe by default, and developers must explicitly enable it locally.

### dispatcherd config now always reads DB settings from Django DATABASES
- **Commits**: 0e15cbd (#66)
- **What happened**: The `config/dispatcherd.yaml` had its hardcoded database credentials removed and replaced with a comment saying "Database config is injected at runtime from Django settings." A new `_load_config_with_django_db()` function in `dispatcherd_config.py` loads the YAML file, then overwrites `brokers.pg_notify.config` with values from `django.conf.settings.DATABASES["default"]`.
- **Insight**: This resolves the long-running problem of dispatcherd's database config being out of sync with Django's. Now `METRICS_SERVICE_DATABASES__default__*` env vars flow through Dynaconf -> Django settings -> dispatcherd config, providing a single source of truth. The YAML file still controls non-DB settings like channel names and queue routing.

### URL prefix env var for gateway routing
- **Commits**: 2efdae3 (#69), a64071c (#70)
- **What happened**: A `METRICS_SERVICE_URL_PREFIX` env var was added (read via `os.getenv()` in the dashboard view) to prefix the API base URL when the service runs behind a gateway. If set (e.g., `METRICS_SERVICE_URL_PREFIX=metrics-service`), the dashboard's API calls go to `/<prefix>/api/v1/` instead of `/api/v1/`. The first attempt (#69) used `METRICS_URL_PREFIX`, renamed in #70 to follow the `METRICS_SERVICE_*` convention.
- **Insight**: This was a stopgap solution for gateway routing. The proper fix came in 52c8fb5 (#75) with `ServicePrefixMiddleware` which handles prefix routing at the Django middleware level, making the env var approach unnecessary for most cases.

### Per-app settings.py files using Dynaconf merge markers
- **Commits**: 52c8fb5 (#75)
- **What happened**: A new `apps/core/settings.py` was created following the Dynaconf convention for per-app settings. It uses merge markers like `MIDDLEWARE = ["dynaconf_merge_unique", ...]` and `REST_FRAMEWORK__DEFAULT_AUTHENTICATION_CLASSES = "@insert 0 apps.core.authentication.ServiceJWTAuthentication"` to extend lists/dicts from `defaults.py` without overwriting them.
- **Insight**: The `@insert 0` Dynaconf marker allows prepending to a list (putting JWT auth first), while `dynaconf_merge_unique` appends without duplicates. This pattern lets each app declare its own middleware, authentication classes, etc. without modifying the central settings file.

### Segment write key moved from task parameter to Django setting
- **Commits**: 1acd7b2 (#72)
- **What happened**: The `segment_write_key` parameter was removed from all task functions (`_send_to_segment`, `full_process`, `full_process_anonymize`, `send_to_segment`, `test_segment_track`, `debug_segment_messages`) and their metadata definitions. Instead, `_send_to_segment()` now reads it from `getattr(settings, "METRICS_SERVICE_SEGMENT_WRITE_KEY", None)` via Django settings. A default value (`test-segment-write-key-change-in-production`) was added to `config/settings.yaml`, and a Dynaconf `Validator` was added to ensure production doesn't use the default value.
- **Insight**: Secrets like API write keys should come from settings/environment, not task parameters. Passing secrets as task parameters means they'd be logged in task execution records and visible in the API. Using Django settings with Dynaconf allows the value to come from environment variables (`METRICS_SERVICE_SEGMENT_WRITE_KEY`) or production config files, with validation preventing the default from reaching production.

### Settings restructured from metrics_service/settings/ package to framework-managed single file
- **Commits**: 911dd60 (#77)
- **What happened**: The `metrics_service/settings/` package (containing `__init__.py` with Dynaconf factory, `defaults.py`, `development.py`, `test.py`) was replaced by a single `metrics_service/settings.py` file. This file contains Django framework defaults (INSTALLED_APPS, MIDDLEWARE, DATABASES with SQLite default, LOGGING, etc.) and the Dynaconf instrumentation that loads settings in order: `apps/settings/defaults.py` -> each `apps/*/settings.py` -> `apps/settings/{mode}.py` -> `settings.local.py` -> DAB settings -> standard paths -> env vars -> post hooks. The `DJANGO_SETTINGS_MODULE` changed from `metrics_service.settings.test` to just `metrics_service.settings`. Environment-specific overrides moved to `apps/settings/test.py`, `apps/settings/development.py`, `apps/settings/production.py`. The `config/settings.yaml` was removed. A `settings.local.py.example` was added for local development overrides. `django-cors-headers` was removed since CORS is handled at the gateway level.
- **Insight**: The framework pattern separates "things the framework manages" (in `metrics_service/settings.py`, marked DO NOT EDIT) from "things the project customizes" (in `apps/settings/`). This enables the copier template to update framework files without conflicting with project customizations. The loading order is critical: framework defaults are intentionally overridable (e.g., the SQLite default in `metrics_service/settings.py` is overridden by PostgreSQL in `apps/settings/defaults.py`).

### DEVELOPER_MODE_ENABLED replaced by METRICS_SERVICE_MODE check
- **Commits**: 7db9971 (#87)
- **What happened**: The `DEVELOPER_MODE_ENABLED` setting and all references to it were removed. Instead, the `DeveloperModeRequired` permission class (renamed conceptually to development mode) now checks `settings.MODE == "development"`. The dashboard's `require_developer_mode` decorator was renamed to `require_development_mode` with the same MODE-based check. Test settings no longer need `DEVELOPER_MODE_ENABLED = True` since `METRICS_SERVICE_MODE=test` is already set and doesn't match "development". Tests that need dashboard/task API access now mock `settings.MODE` to return `"development"`.
- **Insight**: Using the existing `MODE` setting (which already distinguishes development/test/production) to gate debug endpoints eliminates a separate boolean flag. This is cleaner because there's a single source of truth for "what environment am I in." The trade-off is that test mode can't access debug endpoints without mocking, which is arguably correct behavior.

### URL_PREFIX setting added for dashboard API URL generation
- **Commits**: 7db9971 (#87), 85aed7f (#91)
- **What happened**: PR #87 introduced `URL_PREFIX = None` in `apps/settings/defaults.py` and changed the dashboard view from `os.getenv("METRICS_SERVICE_URL_PREFIX")` to `settings.URL_PREFIX`, adding slash handling (`if prefix and prefix != "/": root_url = f"/{prefix}/{root_url}".replace("//", "/")`). PR #91 further refined this by adding a `url_for()` helper function that sanitizes slashes using `re.sub(r"/+", "/", f"/{prefix}/{path}")` and treats `None` as `/api/` prefix. The setting's docstring was updated from "example: metrics-service" to "example: /api/metrics/; None means /api/" to clarify it's a URL path prefix, not a slug.
- **Insight**: This is the third iteration of URL prefix handling (#69 introduced it as env var, #70 renamed it, #87 made it a setting, #91 fixed the interpretation). The key insight from #91 is that the prefix should be treated as an actual URL path segment (like `/api/metrics/`), not a slug (like `metrics-service`). The `url_for()` helper with slash normalization handles edge cases where users might include or omit leading/trailing slashes.

### Per-app settings files established as standard pattern
- **Commits**: 911dd60 (#77), 3a58426 (#79)
- **What happened**: The settings restructuring created `apps/tasks/settings.py` with task-specific settings (`DISPATCHERD_ENABLED = True`, `SEGMENT_WRITE_KEY`). This file is automatically loaded by the Dynaconf instrumentation in `metrics_service/settings.py` which iterates `LOADED_APPS` and calls `DYNACONF.load_file(f"{app}.settings")` for each app. The loading order means later apps can override earlier apps' settings, and environment-specific files (`apps/settings/{mode}.py`) override all app settings.
- **Insight**: Per-app settings files follow the "apps own their configuration" principle. Settings declared in `apps/tasks/settings.py` stay with the tasks app and are version-controlled alongside the code that uses them. Dynaconf merge markers (`@merge_unique`, `dynaconf_merge`) ensure app-level settings extend rather than replace base settings.

### Environment variable cleanup standardized on METRICS_SERVICE_MODE
- **Commits**: 7db9971 (#87)
- **What happened**: `METRICS_SERVICE_MODE` (already introduced by the framework retrofit in #77) became the authoritative environment selector, replacing `DEVELOPER_MODE_ENABLED`. The `TEST_DB_NAME` variable was removed (tests use whatever the settings resolve to). The `settings.local.py.example` was updated to comment out all defaults so it serves as documentation rather than active overrides. The `.gitignore` entry for `.env` was removed (the file is no longer used; `settings.local.py` replaces it).
- **Insight**: Consolidating environment configuration to a single `METRICS_SERVICE_MODE` variable simplifies deployment. Operators set one variable (development/test/production) and get the appropriate behavior, rather than managing separate boolean flags for each feature.

### init-default-settings enhanced with overwrite and remove capabilities
- **Commits**: e137d39 (#92)
- **What happened**: `init-default-settings` now recreates settings that haven't been changed by the user (no `previous_value` set). Settings changed by the user are preserved. Added `--overwrite` flag to force-reset all settings to defaults. Added complementary `remove-default-settings` with `--all-known` (removes even user-changed settings) and `--all-settings` (deletes everything).
- **Insight**: The `previous_value` field on the Setting model serves as a change-tracking flag: if null, the setting hasn't been modified by the user and can be safely reset. This allows re-running `init-default-settings` on upgrades to apply new defaults without overwriting user customizations.

### SEGMENT_WRITE_KEY loaded from file for Konflux secrets management
- **Commits**: 6b4f17c (#137)
- **What happened**: A new secrets management pattern was introduced for loading `SEGMENT_WRITE_KEY` from a file instead of (or in addition to) environment variables. The `_load_segment_write_key_from_file()` function reads from a configurable path (default: `/etc/ansible-automation-platform/metrics/segment-write-key`, overridable via `METRICS_SERVICE_SEGMENT_WRITE_KEY_FILE`). The file content is expected to be base64-encoded. The function respects precedence: it does NOT overwrite if the key is already set via `METRICS_SERVICE_SEGMENT_WRITE_KEY` env var or Dynaconf. The `_decode_segment_key()` helper tries base64 decoding and falls back to using the raw value if decoding fails. This runs at settings module load time (called immediately after `load_envvars`). Comprehensive unit tests were added covering base64 decode, file-not-found, empty file, directory path, and OSError scenarios.
- **Insight**: In Konflux deployments, build-time secrets (like Segment write keys) are injected as files rather than environment variables. The base64 encoding adds a layer that prevents accidental log exposure. The precedence order (env var > Dynaconf setting > file) ensures operators can always override the file-based key. This is the beginning of a pattern that will be iterated on -- Konflux pipeline secrets management for API keys.

### Production validators temporarily disabled for tech preview deployment
- **Commits**: 6b4f17c (#137)
- **What happened**: Four production validators were commented out (with "Optional until gateway APIs are implemented" comments): `RESOURCE_SERVER__SECRET_KEY`, `ANSIBLE_BASE_JWT_KEY`, `SEGMENT_WRITE_KEY`, and `ALLOWED_HOSTS`. A test was added to assert these settings do NOT have validators, ensuring they stay optional. The PR description says "Temp removing validators as TP wont support gateway correction."
- **Insight**: For the tech preview (TP) release, the service will deploy without the AAP gateway integration (no JWT auth, no resource server). Disabling validators prevents the service from failing to start in environments where gateway config isn't available yet. The test asserting the absence of validators is a clever way to prevent someone from accidentally re-enabling them before gateway support is ready.

### ALLOWED_HOSTS validator added for production then immediately disabled
- **Commits**: 531b608 (#129), 6b4f17c (#137)
- **What happened**: In #129, a production validator was added requiring `ALLOWED_HOSTS` to be a non-empty list. In #137 (one week later), this validator was commented out along with three others for the tech preview deployment.
- **Insight**: The rapid add-then-disable cycle reflects the tension between security hardening (validating all production settings) and deployment pragmatism (the tech preview environment isn't fully configured yet). The commented-out validators serve as documentation of what will be enforced once gateway integration is complete.

### SEGMENT_WRITE_KEY base64 encoding removed in favor of plaintext
- **Commits**: 1b38f9f (#141)
- **What happened**: The `_decode_segment_key()` helper (which tried base64 decoding and fell back to raw value) was removed entirely. The `_read_segment_key_from_path()` function now reads the file content as plaintext with `.strip()`. The `base64` import was removed from `metrics_service/settings.py`. Tests were updated to use plaintext keys and test whitespace stripping instead of base64 decoding.
- **Insight**: The base64 encoding layer introduced in #137 was an unnecessary complication. Since the key is injected by the build pipeline, the pipeline can write it as plaintext directly. Removing the decode/fallback logic eliminates a source of confusion (which encoding is my key in?) and simplifies debugging. This is the second iteration of the Segment key file pattern (added in #137, simplified here).

### SEGMENT_TEST_MODE for separating test data from production in Segment
- **Commits**: 4b078d3 (#147)
- **What happened**: A new `SEGMENT_TEST_MODE` setting was added to `apps/tasks/settings.py` (default `False`), overridable via `METRICS_SERVICE_SEGMENT_TEST_MODE`. When enabled, `_process_single_payload()` appends `"_Test"` to the Segment event name (e.g., `"Controller Metrics Daily Rollup"` becomes `"Controller Metrics Daily Rollup_Test"`). Tests were added covering enabled, disabled, and absent setting scenarios.
- **Insight**: Separating test traffic from production in analytics systems by modifying event names is a practical pattern. It avoids creating separate Segment sources or write keys for testing. The suffix approach means test data can be filtered out on the analytics side.

### PostgreSQL session parameters normalized from Dynaconf env vars to psycopg2 options string
- **Commits**: fbfefeb (#149)
- **What happened**: A post-Dynaconf-export normalization step was added to `metrics_service/settings.py` that scans `DATABASES[*].OPTIONS` for common PostgreSQL session parameters (`datestyle`, `search_path`, `timezone`, `application_name`) and converts them to psycopg2's `-c key=value` format in `OPTIONS.options`. This allows setting `METRICS_SERVICE_DATABASES__awx__OPTIONS__datestyle=iso, mdy` instead of the psycopg2-specific `METRICS_SERVICE_DATABASES__awx__OPTIONS__options=-c datestyle=iso,mdy`.
- **Insight**: Dynaconf's dunder notation creates nested dicts naturally, but psycopg2 needs session parameters as a `-c key=value` formatted string in `OPTIONS.options`, not as individual keys in `OPTIONS`. The normalization bridge makes the env var interface user-friendly while producing the format psycopg2 expects. Spaces are stripped from values to prevent quoting issues.

### STATIC_ROOT set to fixed writable path for production
- **Commits**: 520fd11 (#155)
- **What happened**: `apps/settings/production.py` added `STATIC_ROOT = "/var/lib/ansible-automation-platform/metrics/staticfiles"` to override the default `BASE_DIR`-relative path. The init entrypoint script (`scripts/entrypoint-init.sh`) was updated to run `collectstatic --noinput --clear`.
- **Insight**: When the package is installed into `site-packages`, the default `BASE_DIR`-relative `STATIC_ROOT` points into a potentially read-only location. A fixed writable path ensures WhiteNoise can serve static files regardless of the install method. Running `collectstatic` in the init script (rather than at build time) ensures it picks up static files from all installed packages.

### ServicePrefixMiddleware updated to derive prefix from URL_PREFIX setting
- **Commits**: 35620f8 (#157)
- **What happened**: `ServicePrefixMiddleware.__init__()` was refactored to check `settings.URL_PREFIX` first, deriving both `api_prefix` and `service_prefix` from it (e.g., `URL_PREFIX="/api/metrics"` yields `api_prefix="/api/metrics"`, `service_prefix="/metrics"`). The previous behavior of deriving from `ROOT_URLCONF` is now the fallback when `URL_PREFIX` is unset. Tests were added covering the URL_PREFIX path, the fallback path, trailing slash handling, and non-`/api/` prefix edge cases.
- **Insight**: This is the fourth and most complete iteration of URL prefix handling. Earlier versions (#69/#70 used an env var, #87 made it a setting, #91 refined interpretation). This version makes the middleware directly configurable via `URL_PREFIX`, which is the correct layer since the middleware is what actually rewrites request paths. The `api_prefix.startswith("/api/")` check handles edge cases where the prefix might not follow the `/api/<service>` convention.

### Feature flag precedence order clarified and DASHBOARD_COLLECTION removed from defaults
- **Commits**: fc2815a (no PR number), 8007509 (#189), babf061 (#199)
- **What happened**: The `get_feature_enabled_from_db()` function's lookup order was formalized, then expanded in #199 to five tiers: (1) `Setting` row in dynamic_settings, (2) `settings.FEATURE_ENABLED[name]` if that key exists (includes Dynaconf env var overrides), (3) `settings.FEATURE_<name>_ENABLED` top-level attribute (set by installer via `settings.yaml`), (4) DAB `AAPFlag` `FEATURE_<name>_ENABLED`, (5) the `default` parameter. Tier 3 was added because the installer writes top-level keys like `FEATURE_DASHBOARD_COLLECTION_ENABLED: True` directly into `settings.yaml`, which Dynaconf surfaces as a settings attribute but not inside the `FEATURE_ENABLED` dict. A `sync_flag_values_from_settings()` function was also added to propagate installer overrides to AAPFlag rows so the Gateway UI reflects the installer's intent.
- **Insight**: When multiple configuration sources exist, explicit precedence documentation is critical. The five-tier order ensures: runtime API changes (Setting) > Dynaconf env var overrides (FEATURE_ENABLED dict) > installer intent (top-level attr) > platform defaults (AAPFlag) > code defaults. Each source has a clear owner and override path. Omitting a key from `FEATURE_ENABLED` lets it fall through to the installer/AAPFlag/default path, useful for flags that should be platform-managed by default.

### METRICS_COLLECTION feature flag added for local collection control
- **Commits**: 68a2039 (#191)
- **What happened**: New `METRICS_COLLECTION` flag (default: true) added. The system now has three flags: `METRICS_COLLECTION` (local collection), `ANONYMIZED_DATA_COLLECTION` (anonymization + upstream send), `DASHBOARD_COLLECTION` (dashboard reports).
- **Insight**: See `task_system.md` for the full feature flag evolution arc. Each flag gates a specific pipeline subset and can be toggled independently.

### Production startup validation re-enabled with actionable error messages
- **Commits**: 956923d (#193)
- **What happened**: The `validation=False` in `metrics_service/settings.py` was changed back to `validation=True`. All four production validators that had been commented out in #137 were uncommented and enhanced with actionable error messages specifying exactly which environment variable to set: `RESOURCE_SERVER__SECRET_KEY` ("Set METRICS_SERVICE_RESOURCE_SERVER__SECRET_KEY"), `ANSIBLE_BASE_JWT_KEY` ("Set METRICS_SERVICE_ANSIBLE_BASE_JWT_KEY"), `SEGMENT_WRITE_KEY` (explains both env var and file path options), and `ALLOWED_HOSTS` (explains comma-separated and JSON array formats with examples). The test was flipped from asserting validators are absent (`test_optional_production_settings_have_no_validators`) to asserting validators are present (`test_required_production_settings_have_validators`). SonarCloud was updated to exclude `**/settings/**` from both sources and coverage.
- **Insight**: This is the conclusion of the validation saga that spanned 5 PRs: #26 (added validators), #129 (added ALLOWED_HOSTS validator), #137 (commented out all four), #143 (nuclear option: validation=False), #193 (re-enabled with proper messages). The key difference from earlier attempts is actionable error messages: instead of generic "must be set", each validator now tells the operator exactly which env var to export and in what format. This turns a startup crash into a clear remediation instruction. The validators only run in production mode (development/test have no validators registered), so local development is unaffected.

### Feature flags now persist through DAB migrations via post_migrate signal
- **Commits**: db116c4 (#184)
- **What happened**: DAB's feature_flags app purges/reloads flags on every migration, deleting task-owned flags. A `feature_flags.yaml` defines the flags, and `TasksConfig.ready()` connects `load_task_feature_flags` to `post_migrate` of `FeatureFlagsConfig`, re-seeding after every DAB purge cycle.
- **Insight**: When a third-party framework owns a model and purges/reloads it during migrations, application-specific records need a re-seeding mechanism. Using `post_migrate` connected to the framework's app ensures correct ordering.

### Dashboard endpoint moved from /dashboard/ to /api/dashboard/
- **Commits**: db116c4 (#184)
- **What happened**: Dashboard URL changed from `/dashboard/` to `/api/dashboard/`. A redirect from `/api/v1/feature_flags/` to `/api/v1/feature_flags/states/` was added.
- **Insight**: Placing the dashboard under `/api/` ensures it's covered by the same middleware and prefix handling as the REST API, simplifying gateway routing.

### load_task_feature_flags called from init-default-settings for pre-migrated environments
- **Commits**: 8007509 (#189)
- **What happened**: The `init-default-settings` management command now calls `load_task_feature_flags()` directly after `initialize_default_settings()`. The function was updated to return `bool` (True on success, False on failure) and log failures at WARNING level instead of using `logger.exception` (which logs at ERROR). If flag seeding fails, the command still succeeds but prints a warning message instead of the normal success message.
- **Insight**: In production Kubernetes deployments, the DB is pre-migrated before the service starts, so the `post_migrate` signal (which normally seeds AAPFlags) never fires during `init-default-settings`. Calling `load_task_feature_flags()` explicitly ensures flags are seeded regardless of whether a migration has run. The non-fatal failure handling prevents flag seeding issues from blocking service startup.

### Feature flag precedence expanded to five tiers with installer top-level attribute
- **Commits**: babf061 (#199)
- **What happened**: The `get_feature_enabled_from_db()` lookup order was expanded from four to five tiers by adding a check for `settings.FEATURE_<name>_ENABLED` (top-level attribute set by the installer via `settings.yaml`) between the `FEATURE_ENABLED` dict check and the AAPFlag check. Full order: (1) `Setting` row, (2) `settings.FEATURE_ENABLED[name]`, (3) `settings.FEATURE_<name>_ENABLED` top-level attr, (4) AAPFlag, (5) default. A new `sync_flag_values_from_settings()` function propagates installer overrides to AAPFlag rows so the Gateway UI reflects the installer's intent.
- **Insight**: The installer convention of writing `FEATURE_DASHBOARD_COLLECTION_ENABLED: True` directly into `settings.yaml` (as a top-level key, not inside the `FEATURE_ENABLED` dict) means Dynaconf surfaces it as a direct settings attribute. Without explicit handling in the precedence chain, this installer intent was invisible to the feature flag system. The sync function ensures the Gateway's AAPFlag rows match.

## Superseded / Semi-Obsolete

### Database defaults to SQLite for development
- Superseded by cb58dc0 (#11), which made PostgreSQL the default for all environments. SQLite is no longer supported.

### split_settings-based settings composition
- The initial `settings/__init__.py` used `split_settings.tools.include` to compose settings from multiple files. This was replaced in 8b4aa31 (#26) by Dynaconf's settings layering system using DAB's `factory()`.

### Wildcard import in development.py
- The `from .defaults import *` pattern in `development.py` was replaced in da91648 (#29) with explicit imports, then the entire file was deleted in 8b4aa31 (#26) when Dynaconf took over environment switching via `METRICS_SERVICE_MODE`.

### ConfigView for runtime config management
- The `ConfigView` added in 8b4aa31 (#26) with `DYNACONF.merge()` was replaced in f4b136e (#31) by the `SettingView` with DB-backed change tracking and rollback.

### FEATURE_FLAGS naming
- Renamed to `FEATURE_ENABLED` in c8e5f0d (#36) to avoid confusion with AAP's feature flags system.

### Manual URL prefix via METRICS_SERVICE_URL_PREFIX env var
- The `os.getenv("METRICS_SERVICE_URL_PREFIX")` approach from 2efdae3 (#69) / a64071c (#70) was superseded by `settings.URL_PREFIX` in 7db9971 (#87), then refined with proper prefix interpretation in 85aed7f (#91). The `ServicePrefixMiddleware` from 52c8fb5 (#75) handles gateway-level prefix routing.

### DEVELOPER_MODE_ENABLED setting
- Removed in 7db9971 (#87). Development-mode gating now uses `settings.MODE == "development"` instead of a separate boolean flag.

### Segment write key as task parameter
- Removed from task parameters in 1acd7b2 (#72). Now read from Django settings via `settings.METRICS_SERVICE_SEGMENT_WRITE_KEY`, with Dynaconf validation preventing the default value in production. Extended in 6b4f17c (#137) to also support loading from a file path for Konflux deployments.

### metrics_service/settings/ as a Python package
- Replaced in 911dd60 (#77) by a single `metrics_service/settings.py` framework-managed file. Project settings moved to `apps/settings/`.

### config/settings.yaml
- Removed in 911dd60 (#77). YAML-based settings overrides replaced by `apps/settings/{mode}.py` Python files and environment variables.

### SEGMENT_WRITE_KEY file content expected as base64-encoded
- The base64 encoding pattern from 6b4f17c (#137) was removed in 1b38f9f (#141). The file is now read as plaintext with `.strip()`. The `_decode_segment_key()` helper was deleted.

### Conditional Dynaconf validation (skip in development, enforce in production)
- The validation=True-but-skip-in-development approach from 8b4aa31 (#26) evolved through several iterations (production validators commented out in #137), was fully disabled in c7a06f1 (#143) with `validation=False`, and finally re-enabled in 956923d (#193) with `validation=True` and proper error messages on all four production validators. See the "Production startup validation re-enabled" learning above for the full arc.

### SEGMENT_WRITE_KEY default value in apps/tasks/settings.py
- The hardcoded `SEGMENT_WRITE_KEY = "test-segment-write-key-change-in-production"` was commented out in e3b9969 (#144). The key must now be set via environment variables or file mount.

### Dynaconf validation turned off until gateway is fully implemented
- Validation was disabled in c7a06f1 (#143) with `validation=False` because tech preview deployments lacked gateway configuration. Superseded by 956923d (#193) which re-enabled `validation=True` with all four production validators uncommented and enhanced with actionable error messages. The full validation saga: added (#26) -> conditional by environment (#77) -> validators commented out (#137) -> validation=False (#143) -> validation=True with proper messages (#193).

### Production validators for RESOURCE_SERVER__SECRET_KEY, ANSIBLE_BASE_JWT_KEY, SEGMENT_WRITE_KEY, ALLOWED_HOSTS
- Commented out in 6b4f17c (#137) for tech preview deployment. Superseded by 956923d (#193) which uncommented all four validators and added actionable error messages specifying which environment variables to set.

### Feature flags simplified to single ANONYMIZED_DATA_COLLECTION toggle
- The decision in e137d39 (#92) to remove `METRICS_COLLECTION_ENABLED` and make collection always-on was partially reversed in 68a2039 (#191). A new `METRICS_COLLECTION` flag (default: true) was added to gate local collection independently. The system now has three flags: `METRICS_COLLECTION`, `ANONYMIZED_DATA_COLLECTION`, and `DASHBOARD_COLLECTION`.

### ServicePrefixMiddleware derived prefix from ROOT_URLCONF only
- The middleware originally derived the service name from `settings.ROOT_URLCONF` only. In 35620f8 (#157), it was updated to use `settings.URL_PREFIX` when set, with ROOT_URLCONF as fallback.
