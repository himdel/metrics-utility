# Architecture

> Default repo: metrics-service

## Learnings

### Repo bootstrapped from a template service called "my-service"
- **Commits**: dd5603f, be51903
- **What happened**: The initial commit contained a complete Django service skeleton named `my_service` with placeholder models (Animal, Organization, Team, User) and example tasks. The very next day, commit be51903 renamed everything from `my_service`/`my-service` to `metrics_service`/`metrics-service`, and removed unused template files (`settings.yaml.example`, `.github/template.yml`).
- **Insight**: The repo originated from an internal AAP service template; the template included example/placeholder code (Animal model, sample tasks like `send_notification_email`) that was carried forward rather than stripped out immediately.

### DAB integration uses try/except ImportError fallbacks everywhere
- **Commits**: dd5603f
- **What happened**: `apps/core/models.py` wraps all Django-Ansible-Base (DAB) imports in `try/except ImportError` blocks and provides simple fallback base classes (`CommonModel`, `NamedCommonModel`, `AbstractDABUser`, etc.) when DAB is not installed. A `DAB_AVAILABLE` boolean gates conditional behavior throughout the models.
- **Insight**: This pattern allows the service to boot and run basic functionality without the full DAB dependency chain, but it creates two code paths that can drift apart -- every model feature must work with and without DAB.

### Settings loaded via split_settings with DAB dynamic config
- **Commits**: dd5603f
- **What happened**: `metrics_service/settings/__init__.py` uses `split_settings.tools.include` to compose settings from `defaults.py`, `{environment}.py`, DAB's `dynamic_settings.py`, and `post_load.py` in a specific order. The environment is determined by `METRICS_SERVICE_ENV` (defaulting to `development`).
- **Insight**: The split-settings + DAB dynamic_config approach means settings load order matters -- later files override earlier ones, and DAB's dynamic_settings can override app defaults. This was later replaced by Dynaconf in later commits (not in this batch).

### Permission registry registration disabled early due to content type issues
- **Commits**: 141801c
- **What happened**: The task system commit commented out all `permission_registry.register(...)` calls with the note "Temporarily disabled due to DAB content type issues - can be re-enabled once system is stable."
- **Insight**: DAB's permission registry requires content types to be correctly set up, which can fail during early development when models are in flux. Disabling it unblocks development but means RBAC is effectively non-functional.

### access_qs() stub pattern for RBAC readiness
- **Commits**: ad01618, 2a1c481 (#9)
- **What happened**: Every model (User, Organization, Team, Animal, Task) got an identical `access_qs` classmethod that just returns all objects, with a comment saying "in production this would implement proper RBAC." In commit 2a1c481, this was extracted into a reusable `AccessControlMixin`.
- **Insight**: The views call `Model.access_qs(request.user)` uniformly, so when real RBAC is wired up, only the mixin needs to change. This is a good preparatory pattern but carries the risk of shipping "return everything" to production if not replaced.

### Base classes introduced to reduce API boilerplate
- **Commits**: 2a1c481 (#9)
- **What happened**: Created `BaseViewSet` (extending `AnsibleBaseDjangoAppApiView + ModelViewSet`), `UserManagementMixin` (generic add/remove user actions), `BaseModelSerializer` (extending `HyperlinkedModelSerializer` with auto read-only fields), and `CountFieldMixin`. All existing viewsets and serializers were refactored to inherit from these.
- **Insight**: Extracting common patterns into base classes early establishes a consistent API layer, but the base classes here do a lot of implicit things (auto-setting `read_only_fields` in `__init__`, auto-setting `created_by` in `perform_create`) that can surprise developers who don't read the base class code.

### Boilerplate cleanup removed Animal model, health app, Team API, and placeholder code
- **Commits**: 32c5dab (#12), c6947ce (#14)
- **What happened**: Commit 32c5dab removed the Animal model, TeamViewSet/AnimalViewSet, and the health check app (`apps/health/`), plus placeholder tests and example scripts. The PR was explicitly meant to be merged before the RBAC PR (#10). In the bigger refactor (c6947ce), the Animal model was fully removed from the core app along with its migration, and tasks were moved from `apps/core/tasks.py` to a dedicated `apps/tasks/` app. The `apps/core/models.py` was gutted of task-related models, which moved to `apps/tasks/models.py`.
- **Insight**: The cleanup was deferred too long -- the template boilerplate (Animal, health checks) survived through multiple feature PRs before being removed. Cleaning up template code should be the very first PR after forking a template.

### DAB try/except ImportError fallbacks removed in favor of hard dependency
- **Commits**: fd6745d (#10)
- **What happened**: The `apps/core/models.py` was rewritten to remove all `try/except ImportError` blocks and the `DAB_AVAILABLE` boolean gate. All DAB imports (`AbstractDABUser`, `AbstractOrganization`, `CommonModel`, `AnsibleResourceField`, etc.) became unconditional direct imports. The fallback base classes (simple `CommonModel`, `NamedCommonModel`, etc.) were deleted entirely.
- **Insight**: The team decided DAB is a hard requirement, not optional. This eliminated the dual code path problem noted in the previous batch, simplifying the codebase significantly. The `resource = AnsibleResourceField(...)` declarations on models also became unconditional.

### Task system extracted from apps/core into dedicated apps/tasks app
- **Commits**: c6947ce (#14)
- **What happened**: Task models (`Task`, `TaskExecution`, `TaskChain`, etc.), task functions, and management commands were moved from `apps/core/` to a new `apps/tasks/` app. This included creating `apps/tasks/models.py`, `apps/tasks/tasks.py`, `apps/tasks/utils.py`, `apps/tasks/admin.py`, and new API endpoints under `apps/api/v1/tasks/`. The `apps/tasks/apps.py` was set up as a proper Django app config.
- **Insight**: Separating the task system from the core app was necessary as it grew to hundreds of lines. The extraction followed the domain-driven pattern where each concern gets its own app. This also enabled cleaner test organization under `tests/unit/tasks/`.

### Service layer introduced for management command decomposition
- **Commits**: edb4626 (#25)
- **What happened**: A new `apps/core/services/` package was created with six service classes: `TaskManager`, `CronManager`, `SystemInitializer`, `ProcessManager`, `OutputFormatter`, and `ServiceConfig`. These were extracted from the monolithic `metrics_service` management command to decompose its 900+ lines into focused service objects.
- **Insight**: The service layer pattern keeps management commands thin (they delegate to service objects), making the logic testable in isolation. Each service has a single responsibility: `ProcessManager` handles subprocess lifecycle, `CronManager` handles scheduling, etc.

### Dashboard app added for task monitoring UI
- **Commits**: c6947ce (#14)
- **What happened**: A new `apps/dashboard/` app was added with a single-page HTML template (`dashboard.html`, ~1000 lines of inline HTML/CSS/JS) that displays real-time task status, execution history, and system metrics. The dashboard communicates with the API endpoints under `/api/v1/tasks/` via JavaScript fetch calls.
- **Insight**: The dashboard is a monolithic HTML file with all JS/CSS inline, rather than using a proper frontend build system. This is pragmatic for a demo/monitoring tool but will be hard to maintain as it grows. It was enhanced further in edb4626 (#25) to ~1400 lines.

### Unified metrics_service management command as single entry point
- **Commits**: c6947ce (#14), edb4626 (#25)
- **What happened**: A single `metrics_service` management command (`apps/core/management/commands/metrics_service.py`) was created that can run the full service (Django server + dispatcherd + task scheduler in parallel threads), initialize service IDs, init system tasks, and manage task groups. In edb4626 this grew to 900+ lines before being refactored into the service layer.
- **Insight**: The "one command to rule them all" pattern (`python manage.py metrics_service run`) is convenient for development but the monolithic command became a complexity sink. The subsequent service layer extraction was necessary to make it manageable.

### Setting model provides DB-backed configuration with audit trail
- **Commits**: f4b136e (#31)
- **What happened**: A `Setting` model was added to `apps/core/models.py` inheriting from `CommonModel`, `AuditableModel`, and `AccessControlMixin`. It stores `setting_key` (unique), `current_value`, `previous_value`, and `last_modified_by` (FK to User). The `access_qs` classmethod restricts visibility to superusers and system auditors. The model uses DB indexes on `(setting_key, -modified)` and `(last_modified_by, -modified)`. Supporting utility functions `log_setting_change()` and `rollback_configuration_change()` in `apps/core/utils.py` handle change tracking with sensitive value redaction.
- **Insight**: This architecture creates a dual-layer config system: Dynaconf manages Django settings (env vars, YAML files), while the Setting model tracks runtime changes with who/what/when audit fields. Rollback is implemented by re-setting the Dynaconf value to the previous stored value, which only works for the current process lifetime since DB-tracked changes are not reloaded from files.

### Health check app re-introduced for Kubernetes probes
- **Commits**: e486eb4 (#41)
- **What happened**: A new `apps/health/` app was created (the previous `apps/health/` was removed in 32c5dab during boilerplate cleanup). The new version has a single `health_check` view that calls `connection.ensure_connection()` to verify database connectivity, returning 200 with `{"status": "ok"}` or 503 with error details. It uses a plain Django function view with `@require_GET` rather than a DRF viewset.
- **Insight**: The health check was removed during boilerplate cleanup because the original was template code, then re-added when the service needed real Kubernetes probes. Using a plain Django view (not DRF) is intentional -- health checks should have minimal dependencies and no authentication, so the DRF auth middleware is bypassed.

### Prometheus metrics integration via django-prometheus
- **Commits**: e486eb4 (#41)
- **What happened**: `django_prometheus` was added as the first entry in `INSTALLED_APPS` (before `django.contrib.admin`) and its `PrometheusBeforeMiddleware`/`PrometheusAfterMiddleware` were placed as the first and last middleware respectively. The `/metrics` endpoint is exposed via `include("django_prometheus.urls")`. No authentication is required on the metrics endpoint.
- **Insight**: Placing `django_prometheus` first in `INSTALLED_APPS` and wrapping the middleware stack ensures all HTTP requests are measured. The unauthenticated `/metrics` endpoint follows the standard Prometheus pattern where metrics scraping is secured at the network/ingress level rather than application level.

### Cross-service data collection via Django multi-database connections
- **Commits**: 0854775 (#40)
- **What happened**: The metrics collection tasks (`collect_config_metrics`, `collect_anonymous_metrics`, etc.) were changed from accepting a `db` connection string parameter to using Django's `connections` API. Each task now calls `connections[db_name]` where `db_name` defaults to `"awx"`, and the AWX database is configured in `DATABASES` settings. The connection object is passed directly to metrics-utility collectors.
- **Insight**: Using Django's database routing (`DATABASES` dict + `connections[]`) for cross-service data access is cleaner than raw connection strings -- it gets connection pooling, SSL config, and lifecycle management for free. The `awx` database entry in settings can be overridden with `METRICS_SERVICE_DATABASES__awx__HOST` etc. via Dynaconf.

### run_task.py as standalone task runner for CLI testing
- **Commits**: e36eb1e (#49)
- **What happened**: A standalone `run_task.py` script was created at the repo root that sets up Django, imports `TASK_FUNCTIONS` and `TASK_METADATA`, and provides `list_available_tasks()`, `show_task_help()`, and `run_task()` functions. Tasks are run directly without DB persistence or scheduling -- the results are just printed to stdout. Usage: `uv run ./run_task.py collect_all_metrics '{"database": "awx"}'`.
- **Insight**: This fills a gap between the full management command (`metrics_service run`) and manual Django shell testing. By bypassing the Task model and signals, it allows quick iteration on task function logic without dealing with the scheduling/persistence layers. The script uses `sys.path.insert(0, ...)` and `django.setup()` manually since it runs outside the management command framework.

### Retrofit prep: massive cleanup and app restructuring before platform-service-framework alignment
- **Commits**: 5fb6ead (#73)
- **What happened**: A large preparatory refactor (-7927/+1642 lines) that removed unused components and reorganized the app structure: (1) Removed Django admin interface entirely (all `admin.py` files deleted); (2) Removed DRF Spectacular/OpenAPI schema support; (3) Removed `ansible_base.authentication` and `ansible_base.oauth2_provider` integration; (4) Removed OAuth2/social-auth/channels dependencies; (5) Created `apps/dynamic_settings/` as a dedicated app for the `Setting` model (moved from `apps/core/`); (6) Moved services layer and `metrics_service` management command from `apps/core/` to `apps/tasks/`; (7) Moved `StatusTrackingMixin` and `TimestampMixin` to `apps/tasks/mixins.py`; (8) Moved User/Team/Org viewsets and serializers into `apps/core/v1/` with proper sub-packages; (9) Removed `apps/api/` entirely -- each app now owns its own `v1/` API directory; (10) Deleted unused utility functions and ~38 tests for dead code.
- **Insight**: This commit is the transition from "monolithic core app with central API" to "each domain app owns its own API layer." The new structure (`apps/core/v1/viewsets/user.py`, `apps/tasks/v1/views.py`, `apps/dynamic_settings/v1/viewsets.py`) follows the platform-service-framework convention where apps are self-contained. Removing the centralized `apps/api/` app eliminated circular dependency risks and made it clearer which app owns which endpoints.

### Core models simplified to thin wrappers over DAB abstract models
- **Commits**: 5fb6ead (#73)
- **What happened**: The `apps/core/models.py` monolith (~423 lines) was replaced by a `apps/core/models/` package with three tiny files: `user.py` (17 lines, extends `AbstractDABUser`), `organization.py` (12 lines, extends `AbstractOrganization`), and `team.py` (14 lines, extends `AbstractTeam`). All custom fields (`is_system_auditor`, `extra_field`, `access_qs`, etc.) were removed. The models now define only custom Meta permissions and minimal method stubs. The old migrations (0004-0010) were deleted and the initial migration was rewritten.
- **Insight**: The previous models had accumulated custom fields and methods that duplicated DAB functionality. Reducing them to thin wrappers makes the service fully dependent on DAB's model features (RBAC, audit trail, etc.) and avoids maintaining parallel implementations. This required rewriting the migration history, acceptable because the service hadn't been deployed to production yet.

### Base viewsets split: core app uses DAB patterns, tasks app keeps custom patterns
- **Commits**: 5fb6ead (#73)
- **What happened**: Two different `BaseViewSet` classes emerged. `apps/core/v1/viewsets/base.py` uses `ModelViewSet + AnsibleBaseView` with `permission_registry.is_registered()` for RBAC filtering -- following the platform-service-framework pattern. `apps/tasks/v1/base_views.py` retains the custom `AnsibleBaseDjangoAppApiView` base with `log_task_execution` logging and custom error handling. The `UserViewSet` got a `me` action and uses `visible_users()` for RBAC filtering, with a guard for when RBAC isn't set up.
- **Insight**: Having two BaseViewSet patterns reflects the different maturity levels of the apps. Core follows the standardized DAB pattern; tasks retains custom logic that hasn't been migrated yet. This dual-pattern is acceptable during a gradual retrofit but should converge eventually.

### Platform-service-framework retrofit: middleware, views, URL restructuring
- **Commits**: 52c8fb5 (#75)
- **What happened**: Major changes to align with platform-service-framework patterns: (1) `ServicePrefixMiddleware` added for gateway prefix routing -- handles `/api/<service>/v1/...` -> `/api/v1/...` (no SCRIPT_NAME) and `/<service>/...` -> `/...` (with SCRIPT_NAME). Patches `get_full_path()` for correct DRF template URLs. (2) `APIRootViewMiddleware` intercepts 404s on `/`-terminated paths and serves a dynamic endpoint index if child routes exist. (3) `APIRootView` dynamically discovers and lists API endpoints via URL introspection (`get_resolver()`), showing only direct children. (4) Health check moved from `apps/health/` to `apps/core/views/health.py` (class-based `HealthView` with DRF `AnsibleBaseView`), plus a new `PingView`. (5) Custom `ServiceBrowsableAPIRenderer` handles breadcrumb URLs correctly with the service prefix. (6) URL paths changed from `/v1/...` to `/api/v1/...`. (7) `apps/core/settings.py` created as a Dynaconf-merge app settings file for model references, middleware injection, RBAC role definitions, and JWT config.
- **Insight**: The two-middleware approach elegantly handles the dual-access pattern that AAP gateway requires: the same service must be accessible both with a prefix (behind the gateway) and without (direct access). The `ServicePrefixMiddleware` rewrites the path before Django's URL resolver sees it, making the URL configuration prefix-unaware. The `APIRootViewMiddleware` replaces hard-coded index endpoints with dynamic URL introspection, so adding new endpoints automatically makes them discoverable.

### Resource registry changed to is_provider=True for Organization and Team
- **Commits**: 52c8fb5 (#75)
- **What happened**: In `resource_api.py`, the resource list was restructured. Organization and Team changed from `is_provider=False` (consumer) to `is_provider=True` (provider), while User changed from `is_provider=True` to `is_provider=False`. `ParentResource` was added for Team->Organization relationship. The serializer types (`OrganizationType`, `TeamType`) were removed in favor of `serializer=None`. The `service_metadata()` function and `RoleDefinition` registration were removed.
- **Insight**: The `is_provider` flag determines whether the resource registry syncs resources FROM this service to the gateway (provider) or FROM the gateway to this service (consumer). Switching Organization/Team to provider and User to consumer means this service defines its own org/team hierarchy but accepts user identity from the gateway. This is the correct pattern for a service that manages its own resources but authenticates via the gateway.

### Per-app settings file pattern established for Dynaconf
- **Commits**: 52c8fb5 (#75)
- **What happened**: A new `apps/core/settings.py` was created containing model references (`AUTH_USER_MODEL`, `ANSIBLE_BASE_ORGANIZATION_MODEL`, `ANSIBLE_BASE_TEAM_MODEL`), resource registry config, RBAC model registry, REST framework authentication and renderer classes, middleware additions (using `dynaconf_merge_unique`), and managed role definitions. This file uses Dynaconf merge markers to extend lists/dicts defined in `defaults.py`.
- **Insight**: Moving model-specific settings into the app that owns them follows the Dynaconf layering philosophy: `defaults.py` defines framework-level settings, then each `apps/*/settings.py` adds app-specific configuration. The `dynaconf_merge_unique` marker for `MIDDLEWARE` ensures the middleware is appended rather than replacing the existing list.

### LOADED_APPS mechanism for dynamic URL loading
- **Commits**: dab7fc1 (#76), b04c0fa (#78)
- **What happened**: A `LOADED_APPS` setting was introduced, populated at runtime by filtering `INSTALLED_APPS` for entries starting with `apps.` that have a corresponding directory. The main `urls.py` iterates through `LOADED_APPS`, importing each app's `urls.py` and appending patterns. Apps now own their full URL paths (e.g., `path("api/v1/tasks/", ...)` in `apps/tasks/urls.py` instead of being mounted at `path("api/", include("apps.tasks.urls"))`). A new `apps/urls.py` file loads before individual apps for service-level URL customizations (e.g., Prometheus). PR #78 consolidated the documentation (which had been duplicated across every app's urls.py) into the main `urls.py`.
- **Insight**: The LOADED_APPS pattern eliminates manual URL registration when adding new apps -- any app in `project_applications` with a `urls.py` is automatically included. The loading order (DAB -> API root overrides -> `apps/urls.py` -> individual apps -> debug URLs) is documented in `metrics_service/urls.py`, which is marked as framework-managed ("DO NOT EDIT").

### Settings restructured to match platform-service-framework pattern
- **Commits**: 911dd60 (#77)
- **What happened**: The settings system was fundamentally restructured. The `metrics_service/settings/` package (with `__init__.py`, `defaults.py`, `development.py`, `test.py`) was replaced by a single `metrics_service/settings.py` file containing framework defaults and Dynaconf instrumentation. Project-level defaults moved to `apps/settings/defaults.py`. Environment-specific overrides moved to `apps/settings/{development,production,test}.py`. The `config/settings.yaml` was removed entirely. The loading order became: `metrics_service/settings.py` (framework) -> `apps/settings/defaults.py` -> each `apps/*/settings.py` -> `apps/settings/{mode}.py` -> `settings.local.py` -> `/etc/...` YAML -> env vars. Validators moved from a central file to environment-specific files (e.g., production validators in `apps/settings/production.py`).
- **Insight**: The split between "framework-managed" (`metrics_service/settings.py`) and "project-editable" (`apps/settings/`) is the key architectural decision. Framework files are marked with "DO NOT EDIT" and can be auto-updated by copier. Dynaconf `post_hook` decorators allow deferred settings computation (e.g., wrapping middleware with Prometheus).

### Platform-service-framework retrofit completed with copier integration
- **Commits**: 00e68ad (#84)
- **What happened**: The final framework integration added: `.copier-answers.yml` (tracking template source and version), `.protected_files.yaml` (listing framework-managed files like `metrics_service/`, `manage.py`, `LICENSE`), `framework-update.yml` workflow (for automated template updates), and `framework-validation.yml` workflow (for PR validation against template). RBAC service URLs (`rbac_service_urls`) were added to the API. The `pyproject.toml` gained poe task runner configuration with `validate` and `update` tasks for framework management. Debug toolbar URL handling was moved from `urls.py` to `settings.py` (loaded via Dynaconf when DEBUG is true).
- **Insight**: The copier-based template approach means the service can receive upstream framework updates automatically. The `.protected_files.yaml` defines which files the framework fully owns vs. which the project can customize. This creates a clear boundary but requires discipline to not modify protected files.

### Threads-to-processes migration for metrics_service run command
- **Commits**: 0c14d9c (#85)
- **What happened**: The `metrics_service run` management command was rewritten to spawn three separate OS processes (Django runserver, dispatcherd, task scheduler) instead of managing them via threads and the `ProcessManager` service class. The `ProcessManager` class (341 lines) was deleted entirely. The new approach uses `subprocess.Popen` with `selectors.DefaultSelector` for non-blocking I/O multiplexing of stdout from all three processes. Signal handlers (`SIGINT`, `SIGTERM`) terminate all child processes with a 3-second grace period before SIGKILL. The `--check-interval` argument was added for configuring the scheduler's DB polling interval.
- **Insight**: The thread-based approach had issues with infinite loops in tests, complex shutdown coordination, and output interleaving. The process-based approach is simpler conceptually (each service is a separate process with its own stdin/stdout) and more robust (process termination is OS-level, not cooperative). The `selectors` module provides cross-platform non-blocking I/O without threading overhead.

### HourlyMetricsCollection and DailyMetricsSummary models for metrics pipeline
- **Commits**: 3a58426 (#79)
- **What happened**: Two new models added to `apps/tasks/models.py` for the two-tier metrics pipeline: `HourlyMetricsCollection` (raw hourly data with unique constraint on collector_type + timestamp) and `DailyMetricsSummary` (daily aggregation with JSONField for hourly collection IDs instead of M2M).
- **Insight**: See `database_and_migrations.md` for schema details. The two-tier model separates collection from processing -- hourly collections can fail independently (missing hours tracked in daily summary).

### Health endpoint status vocabulary aligned with AAP platform constants
- **Repo**: ansible/metrics-service
- **Commits**: 2853e28 (#205)
- **What happened**: The health endpoint (`GET /health/`) was changed from returning custom status strings (`"healthy"` / `"unhealthy"`) to using shared constants from `ansible_base.lib.constants` (`STATUS_GOOD` / `STATUS_DEGRADED`). This aligns metrics-service with the rest of the AAP platform (gateway, EDA, controller) which all use `"good"` / `"degraded"` / `"failed"` from the same constants module. All inline status string literals in the view were replaced with constant imports. Tests in both `test_health.py` and `test_health_metrics.py` were updated to assert `"good"` instead of `"healthy"`.
- **Insight**: When multiple services expose health endpoints consumed by the same orchestrator or monitoring system, they must speak the same status vocabulary. Using shared constants from a common library (DAB) prevents drift and makes the status values a contract rather than a convention. The HTTP status codes (200 for good, 503 for degraded) were already correct and unchanged.

### Task subdirectory structure established (simple/, collectors/, cleanup/)
- **Commits**: e137d39 (#92)
- **What happened**: Task functions were reorganized from flat files in `apps/tasks/` into subdirectories: `apps/tasks/simple/` (hello_world), `apps/tasks/collectors/` (all metrics collection: collect_hourly_metrics, collect_snapshot_metrics, daily_metrics_rollup, daily_anonymize_and_prepare, send_anonymized_to_segment), `apps/tasks/cleanup/` (cleanup_old_tasks, cleanup_metrics_data). Each subdirectory has its own `__init__.py` exporting the task functions.
- **Insight**: The subdirectory structure groups tasks by concern rather than having all task functions in a single flat namespace. This mirrors the CLAUDE.md documentation about the task system layers and makes it easy to find related tasks. Adding a new task category means adding a new subdirectory.

### CLI entry point added: metrics-service command
- **Commits**: 531b608 (#129), a52e7a9 (#131)
- **What happened**: A `metrics_service/cli.py` was added providing a standalone `metrics-service` command (registered via `[project.scripts]` in pyproject.toml). It maps subcommands to Django management commands: `metrics-service run` -> `metrics_service run`, `metrics-service dispatcherd` -> `run_dispatcherd`, `metrics-service scheduler` -> `run_task_scheduler`, plus all `init-*` subcommands. In #131, additional Django commands were added: `makemigrations`, `migrate`, `createsuperuser`, `shell`. The CLI uses two routing strategies: `_DJANGO_COMMAND_MAP` for commands that map directly to Django management commands, and `_METRICS_SERVICE_SUBCOMMANDS` for commands routed through the `metrics_service` management command.
- **Insight**: The CLI entry point solves the Python interpreter ambiguity in container entrypoint scripts. Instead of `python3.12 manage.py metrics_service run` (which requires knowing the exact Python version), containers use `metrics-service run`. Since it's registered as a pip console_script, it automatically uses the correct Python from the environment.

### Feature flag initialization on app startup
- **Commits**: 3a58426 (#79)
- **What happened**: `DynamicSettingsConfig.ready()` was added to automatically initialize default feature flag settings in the database when Django starts. It checks if the `dynamic_settings_setting` table exists (via raw SQL to `pg_tables`) before attempting initialization, handling the case where migrations haven't run yet. The `initialize_default_settings()` function creates `Setting` rows for `METRICS_COLLECTION_ENABLED` and `ANONYMIZED_DATA_COLLECTION` if they don't exist, using values from Django's `FEATURE_ENABLED` dict as defaults.
- **Insight**: Auto-initializing DB-backed settings on startup ensures they're always visible in the admin/API without requiring a manual management command. The table-existence check via raw SQL is necessary because `ready()` runs before migrations in some scenarios. Wrapping in try/except for `OperationalError`/`ProgrammingError` prevents the app from crashing when the database isn't ready.

### Feature flag precedence formalized with five-tier lookup
- **Commits**: fc2815a (no PR number), 8007509 (#189), 68a2039 (#191), babf061 (#199)
- **What happened**: The `get_feature_enabled_from_db()` lookup order was formalized and expanded to five tiers: Setting row -> `settings.FEATURE_ENABLED[name]` -> `settings.FEATURE_<name>_ENABLED` top-level attr (installer convention) -> DAB `AAPFlag` -> default parameter. Three flags: `METRICS_COLLECTION` (local collection, default true), `ANONYMIZED_DATA_COLLECTION` (anonymization+send, default true), `DASHBOARD_COLLECTION` (dashboard reports, default false). A `sync_flag_values_from_settings()` function propagates installer overrides to AAPFlag rows for Gateway UI consistency.
- **Insight**: See `settings_and_configuration.md` for the full feature flag precedence details and the evolution from single flag to three independent flags.

## Superseded / Semi-Obsolete

### Animal model and related API endpoints
- The Animal model was removed in 32c5dab (#12) and c6947ce (#14). It was template placeholder code from the initial repo setup.

### split_settings approach for settings composition
- Replaced in 8b4aa31 (#26) by Dynaconf, using DAB's `factory()` for settings management.

### Monolithic apps/core/models.py
- The single-file models.py (~423 lines with Setting, User, Organization, Team, custom fields) was split into `apps/core/models/` package (thin DAB wrappers) and `apps/dynamic_settings/models.py` (Setting) in 5fb6ead (#73).

### Centralized apps/api/ package
- The `apps/api/` package with central serializers, views, and URL routing was removed in 5fb6ead (#73). Each app now owns its own `v1/` API directory.

### apps/health/ as separate app
- The standalone health check app was removed in 52c8fb5 (#75). Health and ping views were consolidated into `apps/core/views/`.

### Service layer in apps/core/services/
- Moved to `apps/tasks/services/` in 5fb6ead (#73) for better separation of concerns -- the service layer depends on the tasks app.

### Kubernetes manifests in manifests/
- Removed in d72f17e (#68). The k8s manifests were template leftovers with stale config (mixed-case env vars, Redis references, old port numbers).

### Django admin interface
- Removed in 5fb6ead (#73). All `admin.py` files were deleted and `django.contrib.admin` was removed from settings and URL routing.

### DRF Spectacular / OpenAPI schema
- Removed in 5fb6ead (#73). OpenAPI documentation will be provided by `ansible_base.api_documentation` instead.

### DAB authentication and oauth2_provider integration
- Both `ansible_base.authentication` and `ansible_base.oauth2_provider` were removed in 5fb6ead (#73). The service uses JWT from the gateway (via `ansible_base.jwt_consumer`) rather than being its own OAuth provider.

### metrics_service/settings/ as a package with __init__.py, defaults.py, development.py, test.py
- Replaced in 911dd60 (#77) by the platform-service-framework pattern: a single `metrics_service/settings.py` for framework defaults, with project settings in `apps/settings/`.

### config/settings.yaml for Dynaconf overrides
- Removed in 911dd60 (#77). Settings are now layered through Python files (`apps/settings/defaults.py`, `apps/settings/{mode}.py`) and environment variables, not YAML.

### ProcessManager service class for subprocess lifecycle management
- The `ProcessManager` class (341 lines, in `apps/tasks/services/process_manager.py`) was deleted in 0c14d9c (#85). The thread-based service management was replaced by direct `subprocess.Popen` with selectors-based I/O multiplexing.

### Framework validation workflow
- Added in 00e68ad (#84) and removed in 5be118c (#88). The template-comparison validator was too strict for a service with legitimate customizations.

### Tekton/Konflux pipelines in .tekton/
- The `.tekton/metrics-service-pull-request.yaml` and `.tekton/metrics-service-push.yaml` Tekton pipeline configs (640+ lines each) were deleted in 531b608 (#129) as part of the production Docker overhaul. The hermetic build approach with Cachi2/Hermeto prefetch was replaced by a simpler `pip install .` from `pyproject.toml`.

### Feature flag initialization in AppConfig.ready()
- Removed in e137d39 (#92). The `DynamicSettingsConfig.ready()` method that auto-initialized feature flags was moved to the `init-default-settings` management command because `ready()` runs on every Django invocation and caused RuntimeWarning about database access during app initialization.

### Service layer classes in apps/tasks/services/ (CronManager, ServiceConfig, SystemInitializer, TaskManager)
- These were added in edb4626 (#25) for management command decomposition, then deleted in e137d39 (#92) as dead code after subsequent refactors replaced their functionality.

### Monolithic tasks_collector.py (1453 lines)
- Deleted in e137d39 (#92). Replaced by the `apps/tasks/collectors/` subdirectory with specialized modules.

### Automation Dashboard backend added as dashboard_reports app
- **Commits**: 150617a (#169)
- **What happened**: A major new `apps/dashboard_reports/` app was added (58 files, +9794 lines) providing the backend for the Automation Dashboard feature. Key components: (1) **Models**: `JobData`, `JobLabel`, `JobHostSummary` for AWX job records; `SubscriptionCost` (singleton) for cost configuration; `TemplateMetadata` for per-template time estimates; `FilterSet` for user-saved filter configs. (2) **AWX data collection tasks**: `collect_dashboard_reports_initial_data` (historical backfill), `collect_dashboard_reports_data` (incremental), `cleanup_dashboard_reports_old_data` -- registered under a new `DASHBOARD_COLLECTION_ENABLED` feature flag with a `DASHBOARD_COLLECTION_GROUP` in task_groups. (3) **REST API**: report aggregates, real-time filter options (organizations, projects, labels, templates), subscription cost admin, template metadata admin -- all under `/api/v1/dashboard_reports/`. (4) **Admin permission set**: `BaseAdminViewSet` using `IsSystemAdminOrAuditor` for admin-only endpoints (replacing the generic `DeveloperModeRequired`). (5) **SQL injection protection**: `_build_where_clause` escapes special characters in search strings. (6) **Atomic job sync**: `_sync_jobs_atomically` wraps all job data persistence in a transaction to prevent partial writes. The app reads from the secondary AWX database (configured via `METRICS_SERVICE_DATABASES__awx__*`) and writes to the metrics-service DB.
- **Insight**: This is the first app that exposes data directly to an end-user UI (AAP-UI) rather than sending anonymized data to Red Hat. The architectural patterns differ from the metrics collection pipeline: it uses direct SQL queries against AWX (not metrics-utility library calls), stores denormalized copies of AWX data (not rollups), and serves real-time filter queries (not batch processing). The feature flag (`DASHBOARD_COLLECTION_ENABLED`, default false) ensures the AWX database queries don't run unless explicitly enabled. The `IsSystemAdminOrAuditor` permission replaces the development-mode gate, indicating this is a production-ready endpoint.

### Feature flag architecture expanded to three-tier lookup with YAML definitions
- **Commits**: d3fb802 (#168), db116c4 (#184)
- **What happened**: Feature flags evolved: #168 split `METRICS_COLLECTION_GROUP` to scope `ANONYMIZED_DATA_COLLECTION` correctly; #184 added `feature_flags.yaml`, `post_migrate` signal for re-seeding after DAB purge, and three-tier lookup.
- **Insight**: The system bridges three mechanisms: `Setting` model (runtime API-togglable), DAB `AAPFlag` (survives migrations via post_migrate), Django settings (env var fallback). See `settings_and_configuration.md` for precedence details and `task_system.md` for the feature flag evolution arc.

### Debug tooling for anonymization pipeline
- **Commits**: 26614c4 (#113)
- **What happened**: Debug scripts added under `tools/tasks/`: `run_anon.sh` (full pipeline), `dump_hourly.py`, `dump_daily_anonymized.py`. `run_task.py` moved from `scripts/` to `tools/tasks/`.
- **Insight**: Provides end-to-end pipeline validation without real deployment or Segment credentials. See `metrics_collection.md` for how these scripts fit into the anonymization pipeline.
