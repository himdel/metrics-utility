# Bugs and Pitfalls

> Default repo: metrics-service

## Learnings

### Environment variable casing inconsistency persisted across multiple files
- **Commits**: be51903, 5e05775
- **What happened**: When renaming from `my_service` to `metrics_service`, the env vars were initially lowercased (`metrics_service_DB_HOST`) instead of uppercased (`METRICS_SERVICE_DB_HOST`). A follow-up commit fixed the most important ones but left several still lowercase (e.g., `metrics_service_REDIS_URL`, `metrics_service_ALLOWED_HOSTS` in docker-compose.yml and k8s manifests).
- **Insight**: A find-and-replace renaming operation across a codebase is error-prone when the original naming was ALL_CAPS and the new name is mixed_case. The inconsistency means some env vars work and others silently don't, since `metrics_service_FOO` and `METRICS_SERVICE_FOO` are different variables.

### Sonar fix introduced copy-paste bug in "Result Data" label
- **Commits**: cc2ac77, 5b12d74 (#7)
- **What happened**: When extracting `_show_dependencies` and `_show_dependents` helper methods from `show_task`, the "Result Data" label was accidentally changed to "Task Data" (duplicating the label from two lines above). Fixed one commit later.
- **Insight**: Method extraction refactors that are done to satisfy code complexity metrics (Sonar) without careful review can introduce bugs. The fix was trivial but the bug was a classic copy-paste error.

### Docker port variable used wrong casing
- **Commits**: be51903
- **What happened**: `docker-compose.yml` used `${metrics_service_PORT:-8000}` instead of `${METRICS_SERVICE_PORT:-8000}` for the port mapping. Shell variables are case-sensitive, so this would only work if the lowercase version was set.
- **Insight**: Docker Compose variable interpolation (`${VAR}`) is case-sensitive. Using inconsistent casing between documentation and actual config means the documented env vars won't work.

### Dockerfile referenced non-existent paths
- **Commits**: dd5603f
- **What happened**: The initial Dockerfile had `COPY requirements/requirements.in /tmp/requirements.in` but the repo had `requirements.txt` at the root, not `requirements/requirements.in`. The Docker build would fail at this step.
- **Insight**: Template Dockerfiles must be tested with `docker build` before the initial commit. This was fixed two days later in e0bfd65.

### Exception chaining missing (bare raise from)
- **Commits**: 5b12d74 (#7)
- **What happened**: Multiple `except` blocks in `manage_tasks.py` raised new `CommandError` exceptions without chaining from the original exception. The ruff fix added `from e` to preserve the exception chain (e.g., `raise CommandError(f"Invalid JSON data: {e}") from e`).
- **Insight**: Python's exception chaining (`raise X from Y`) preserves the traceback of the original exception. Without it, the original traceback is lost, making debugging harder. Ruff's `B904` rule catches this automatically.

### CodeQL workflow was actually a copy of the pytest workflow
- **Commits**: 7e90a26 (#15), cc53a70 (#16)
- **What happened**: A file named `codeql.yml` was committed but its contents were a complete copy of the pytest workflow. Reverted 5 minutes later.
- **Insight**: Copy-paste error in CI workflow creation. See `ci_cd.md` for the full entry.

### PostgreSQL port mapping mismatch in CI
- **Commits**: cb58dc0 (#11), e9ff8c9 (#27)
- **What happened**: The initial pytest workflow mapped PostgreSQL port `55432:55432` but the PostgreSQL container internally listens on 5432 by default, not 55432. This was eventually fixed in e9ff8c9 to use the standard `5432:5432` mapping. Meanwhile, the Django test settings used `METRICS_SERVICE_DB_PORT: 5432` (the internal port), which worked because GitHub Actions services expose ports on localhost.
- **Insight**: The non-standard port 55432 was used in docker-compose to avoid conflicts with local PostgreSQL, but in CI there's no local PostgreSQL to conflict with. Using standard ports in CI is simpler and less error-prone. The mismatch between the port mapping (`55432:55432`) and the Django env var (`5432`) worked accidentally because Docker network routing still connected to the container's 5432 internal port.

### Sonar-driven refactoring of task validation created unnecessary complexity
- **Commits**: da91648 (#29)
- **What happened**: The `validate_task_groups()` function in `task_groups.py` was refactored from a simple inline loop into two extracted helper functions (`_validate_task_id` and `_validate_required_fields`) to satisfy Sonar's complexity/cognitive-complexity metrics. The refactored code is more lines and arguably harder to follow than the original inline validation.
- **Insight**: Code complexity metrics (Sonar's cognitive complexity) can incentivize extracting functions that don't need extraction. Simple validation loops don't benefit from being split into multiple functions when the original is clear and self-contained.

### Organization model extra_field changed from null=True to default=""
- **Commits**: da91648 (#29)
- **What happened**: The `extra_field` on `Organization` was changed from `CharField(max_length=100, null=True, blank=True)` to `CharField(max_length=100, blank=True, default="")`. This required a new migration.
- **Insight**: This follows the Django convention that CharField should use `default=""` instead of `null=True`, because having two possible "empty" values (NULL and "") for a text field is confusing. Sonar likely flagged this as a code smell.

### GitHub Actions workflow permissions missing on initial creation
- **Commits**: f848024 (#24), e5eba36 (#30)
- **What happened**: The sync-requirements workflow was created without explicit permissions in f848024. A follow-up commit e5eba36 (next day, different author) had to add `permissions: contents: write` and `pull-requests: write` because the workflow needed to commit changes and comment on PRs.
- **Insight**: GitHub Actions workflows that write to the repo or interact with PRs need explicit permissions. This is easy to miss because permissions errors only surface at runtime, not during PR review. Always test CI workflows that do write operations on a real push/PR before merging.

### dispatcherd use_django_db broke local testing and was reverted next day
- **Commits**: 6059d8c (#45), 3a8f7d5 (#48)
- **What happened**: `config/dispatcherd.yaml` changed to `use_django_db: true`, reverted next day because it didn't work for local development testing.
- **Insight**: See `docker_and_deployment.md` for the full three-iteration saga of dispatcherd DB config. The PR was titled just "Fix" with no description, making it hard to find later.

### Django signals on Task model caused widespread test failures
- **Commits**: a044bd7 (#54)
- **What happened**: The `post_save` signal added in edb4626 (#25) automatically routes newly saved Task objects to dispatcherd. In tests, `Task.objects.create()` triggered this signal, causing failures because dispatcherd wasn't running. Five test files needed refactoring to use `_create_task_safely()` which sets `_skip_signals = True` before saving.
- **Insight**: Adding Django signals to models creates implicit side effects that affect every code path that creates/saves the model, including tests. The `_skip_signals` convention is a pragmatic workaround, but it means tests don't exercise the actual save behavior. A better pattern might be to check for a "testing" mode or use a factory function that explicitly opts into or out of signals.

### metrics-utility collector import paths changed with temporary aliases
- **Commits**: 10581e9 (#42)
- **What happened**: When upgrading to `metrics-utility==0.7.20251112`, the import paths changed from `metrics_utility.library.collectors` to `metrics_utility.library.collectors.controller`. The collector function names also changed (e.g., `anonymous` became `job_host_summary`), requiring `as` aliases to maintain backward compatibility. A TODO comment was added: "The AS is just a filler till this is corrected with a later PR."
- **Insight**: Dependency upgrades that change public APIs create confusing alias layers. The aliases mean the code says `anonymous` but actually calls `job_host_summary` -- a debugging nightmare. The TODO suggests this was a quick fix to unblock the Django upgrade, with a proper refactor planned later.

### Recurring task dependent tasks never triggered due to status reset ordering
- **Commits**: e43d59d (#59)
- **What happened**: In `execute_db_task()`, `handle_post_execution()` was called *after* the recurring task status was reset from "completed" to "pending". Since `handle_post_execution` checks `task.status == 'completed'` to trigger dependent tasks, they would never fire for recurring tasks. The fix moved `handle_post_execution()` before the status reset.
- **Insight**: State machine bugs where operations happen in the wrong order relative to a status change are subtle and hard to catch in code review. The fix is a simple line reorder, but discovering the bug requires understanding the full call chain and what each function checks.

### Immediate tasks submitted multiple times due to missing tracking before execution
- **Commits**: 3100514 (#64)
- **What happened**: The unified scheduler's periodic DB sync found pending immediate tasks and executed them, but didn't add them to `_db_task_jobs` tracking dict until after execution. The next polling cycle would see the same pending task (not yet completed by dispatcherd) and submit it again, causing duplicates. The fix was a single line: `self._db_task_jobs[task.id] = f"db_immediate_{task.id}"` added before the execution call.
- **Insight**: When switching from an event-driven architecture (signals, triggered once) to a polling architecture (periodic check), you must track what you've already processed *before* processing it, not after. The polling loop doesn't know whether a previous iteration already handled a given item unless it checks a tracking set.

### URL prefix env var named inconsistently, fixed in follow-up PR
- **Commits**: 2efdae3 (#69), a64071c (#70)
- **What happened**: PR #69 added a `METRICS_URL_PREFIX` env var to the dashboard view so the API base URL could include a gateway prefix. PR #70 (two days later, same author) renamed it to `METRICS_SERVICE_URL_PREFIX` for consistency with the project's env var naming convention (`METRICS_SERVICE_*`). The fix was a one-line change.
- **Insight**: The project's Dynaconf convention is that all env vars use the `METRICS_SERVICE_` prefix. A raw `os.getenv("METRICS_URL_PREFIX")` bypass doesn't follow this convention and would confuse operators. This was the kind of quick fix that should have been caught in code review -- naming consistency is a systematic concern, not a one-off decision.

### dispatcherd YAML had hardcoded database credentials instead of using Django settings
- **Commits**: 0e15cbd (#66)
- **What happened**: `config/dispatcherd.yaml` had hardcoded `dbname`, `user`, `password`, `host`, `port` values. A new `_load_config_with_django_db()` function was added to `dispatcherd_config.py` that loads the YAML config file but overrides the database broker section with values from `django.conf.settings.DATABASES["default"]`. This is the third iteration of solving the dispatcherd DB config problem (after `use_django_db: true` which was reverted, and explicit YAML values which hardcoded credentials).
- **Insight**: The correct solution combines both approaches: load non-DB config from the YAML file (channels, queue routing, logging) but always inject DB connection from Django settings. This way, `METRICS_SERVICE_DATABASES__default__*` env vars work correctly through Dynaconf -> Django settings -> dispatcherd config, providing a single source of truth for database configuration.

### SettingSerializer referenced non-existent view after retrofit
- **Commits**: d180ae8 (#74)
- **What happened**: After the platform-service-framework retrofit (#73), `SettingSerializer` was still a `HyperlinkedModelSerializer` with `extra_kwargs = {"url": {"view_name": "api:v1:settings-detail"}}`. But the dynamic_settings API uses a singleton pattern without individual detail endpoints, so the referenced view didn't exist. The fix changed it to a plain `ModelSerializer` and removed the `url` field entirely.
- **Insight**: When migrating from `HyperlinkedModelSerializer` to app-owned URL patterns, every serializer that references a `view_name` must be audited. The retrofit changed URL namespacing but didn't catch this serializer, causing runtime errors when the `url` field was rendered. Singleton/non-CRUD resources shouldn't use `HyperlinkedModelSerializer` since they lack detail endpoints.

### Framework validation workflow too strict, removed immediately
- **Commits**: 00e68ad (#84), 5be118c (#88)
- **What happened**: PR #84 added a `framework-validation.yml` GitHub Actions workflow that runs the platform-service-framework's CLI validator, which compares repo files against the framework template. PR #88 (the very next business day, different author) deleted the workflow because it compared files like `.gitignore`, `manage.py`, `pyproject.toml`, and `settings.local.py` against the template and failed on any differences. Since the service had legitimately customized these files, the validator was impractical.
- **Insight**: Framework compliance validators that do exact file-content comparison are too brittle for real services. Any service-specific customization causes false failures. Validation should check structural patterns (presence of required files, import paths) rather than file identity.

### Dockerfile labels referenced wrong product name (metrics-utility instead of metrics-service)
- **Commits**: 4b2bc5e (#94), 7c8c0c0 (#99)
- **What happened**: Labels had `com.redhat.component="metrics-utility"` from copy-paste. Fixed in #94, then the CPE regressed back to `metrics_utility` in #99 during Konflux label reformatting.
- **Insight**: See `docker_and_deployment.md` for the full label evolution. Labels don't affect build/runtime behavior, so errors aren't caught by CI. Each label field should be reviewed independently during updates.

### AppConfig.ready() writing to database causes RuntimeWarning on every Django invocation
- **Commits**: e137d39 (#92)
- **What happened**: `DynamicSettingsConfig.ready()` was initializing default feature flag settings by writing to the database. Django emits a `RuntimeWarning` about this: "Accessing the database during app initialization is discouraged." The `ready()` method runs on every Django invocation -- not just server start, but also management commands, `shell`, `migrate`, tests, etc. This caused unnecessary DB writes and warnings during migrations and test runs.
- **Insight**: `AppConfig.ready()` is for signal registration and lightweight setup, not database writes. Use an explicit management command (like `init-default-settings`) for DB initialization. This ensures initialization happens exactly when intended (in entrypoints, after migrations) rather than on every Django process start.

### DRF router registration order caused URL conflict for /tasks/executions/
- **Commits**: e137d39 (#92)
- **What happened**: In `apps/tasks/v1/urls.py`, `TaskViewSet` was registered before `TaskExecutionViewSet`. Since `TaskViewSet` used a catch-all pattern (`r""`), DRF's router matched `/tasks/executions/` as a TaskViewSet detail view with `pk='executions'` instead of routing to `TaskExecutionViewSet`. The fix was to register `TaskExecutionViewSet` before `TaskViewSet`. Two tests had been skipped (via `@pytest.mark.skip`) to work around this bug rather than fixing it.
- **Insight**: DRF routers match patterns in registration order, so more specific patterns must be registered first. This is the router equivalent of the "most specific route first" rule in URL configuration. The skipped tests were actually correct and identifying a real bug.

### generic_collect_metrics status not reset on update_or_create
- **Commits**: 1580ff2 (#109)
- **What happened**: When re-collecting metrics for a previously processed time slot, `update_or_create` only set `raw_data` in `defaults` but not `status="collected"`. If the record already existed with `status="processed"`, the update kept the old status. The daily rollup then couldn't see the re-collected data because it filters by `status="collected"`.
- **Insight**: Django's `update_or_create` applies `defaults` on both create and update, but only for the fields listed in `defaults`. Omitting state machine fields like `status` means they retain their previous value on update, which can break downstream processes that filter by state.

### DailyMetricsRollup missing base() call after merge
- **Commits**: 35c3db5 (#138)
- **What happened**: The daily metrics rollup was merging hourly rollup JSON via `rollup_processor.merge()` but never calling `rollup_processor.base()` on the merged result. The `base()` method performs post-merge cleanup and extra computation that some collectors require. The function was refactored: `_merge_rollup_json` and `_aggregate_collector_rollups` were consolidated into a single `_merge_collects` function that calls `merge()` in a loop, then `base()` on the result, extracting the `"json"` key from the base output. Tests were updated to assert `base()` is called and the `"json"` key is extracted.
- **Insight**: The rollup API contract is `merge(json, json) -> json` followed by `base(merged) -> {"json": result}`. Missing the `base()` call meant collectors that need post-processing (e.g., computing derived fields from merged data) would produce incomplete rollups. This bug could go unnoticed because the merged data still looks valid -- it's just missing the final transformations that `base()` provides.

### Titlecased task names in logs made them harder to search
- **Commits**: 26614c4 (#113)
- **What happened**: The `task_execution_wrapper` in `apps/tasks/utils.py` was calling `.title()` on task names in error messages (e.g., `f"{task_name.title()} task failed: ..."`). This was changed to use the raw task name (e.g., `f"{task_name} task failed: ..."`).
- **Insight**: Titlecasing identifiers in log messages breaks grep-based log searching. If a task is named `cleanup_old_tasks`, searching for that string in logs won't find the titlecased `Cleanup_Old_Tasks` variant. Log messages should use the canonical identifier exactly as it appears in code and configuration.

### Retry of hourly collection collected wrong hour because it used timezone.now()
- **Commits**: da19df3 (#160)
- **What happened**: If a collector task failed and was retried hours later, `timezone.now()` shifted the "previous hour" calculation, silently collecting the wrong time window.
- **Insight**: Time-sensitive tasks must capture their target time window at dispatch time, not execution time. See `metrics_collection.md` "Collection timestamps pinned at dispatch time" for the fix pattern.

### Task execution records stuck in "pending" because execution_id not propagated
- **Commits**: d81dfb3 (#162)
- **What happened**: `submit_task_to_dispatcher` created a `TaskExecution` record but only passed `task_id` (not `execution_id`) in the dispatcherd kwargs. The worker received `execution_id=None` and never updated the execution record. Fix: capture the execution object and pass `execution_id=execution.id` in kwargs.
- **Insight**: When creating a tracking record in one process and updating it in another, the record's ID must be explicitly passed across the boundary. This is easy to miss when the "create" and "update" happen in different functions with different authors.

### Cron schedule collision: cleanup and rollup both ran at 2:00 AM
- **Commits**: d24e7dc (#163)
- **What happened**: `daily_task_cleanup` (deletes old TaskExecution records) and `daily_metrics_rollup` (writes to TaskExecution via FK) both ran at `0 2 * * *`. When simultaneous, cleanup could delete records that rollup was actively referencing, causing integrity errors. Cleanup moved to 5:00 AM. A test was added to verify all cron expressions are unique across all task groups.
- **Insight**: When multiple cron tasks touch overlapping database records, schedule collisions can cause data integrity failures. Adding a test that asserts cron expression uniqueness across all task groups prevents future collisions.

### ANONYMIZED_DATA_COLLECTION flag had overly broad scope
- **Commits**: d3fb802 (#168)
- **What happened**: The flag was applied to the entire collection pipeline (12 tasks) instead of just the 2 anonymization/send tasks. Operators who opted out had permanent data gaps.
- **Insight**: Feature flag scoping must match the flag's name. See `task_system.md` for the full feature flag evolution arc (single flag -> overly broad -> three independent flags).

### Segment send failures were silent -- no error status, no health signal
- **Commits**: 4e2a18e (#175)
- **What happened**: `send_to_segment` returned bare strings, failed payloads were always marked "retry" (never "failed"), and the health endpoint didn't check payload status.
- **Insight**: Silent failures in data pipelines are worse than crashes. See `metrics_collection.md` "Segment send failures made observable" for the fix. Rule: every external integration needs structured error returns, finite retry with escalation, and health check integration.

### Dispatcherd max workers reduced to 1 was a band-aid; real fix was atomic claims and advisory locks
- **Commits**: 9a0feaa (#148), ccf9494 (#167)
- **What happened**: Workers reduced from 4 to 1 as band-aid for race conditions (#148), then restored to 4 with proper atomic claims, advisory locks, and retry delays (#167).
- **Insight**: See `task_system.md` "Workers restored to 4 with atomic task claiming and advisory locks" for the full arc. Reducing concurrency is a valid emergency measure but should always be treated as temporary.

### Stale task.save() after submit_task overwrote atomic attempts increment
- **Commits**: 4892777 (#187)
- **What happened**: `submit_task_to_dispatcher()` called `task.save()` after `submit_task()`, overwriting the worker's atomic `F("attempts") + 1` increment with stale in-memory `attempts=0`. Tasks appeared stuck at 0/3 attempts despite failing.
- **Insight**: When using Django's `F()` expressions for atomic field updates, any subsequent bare `save()` on the same model instance will overwrite the atomic update with the stale in-memory value. See `task_system.md` for the full fix (narrowing all saves to `update_fields=[...]`).

### post_migrate signal connected to class instead of instance -- handler never called
- **Commits**: 8007509 (#189)
- **What happened**: `TasksConfig.ready()` was connecting `load_task_feature_flags` to the `post_migrate` signal using `sender=FeatureFlagsConfig` (the class). But Django's `post_migrate` dispatches with `sender=<AppConfig instance>`, and signal dispatch matches by `id()`. Since `id(class) != id(instance)`, the handler was never called, meaning task-specific AAPFlags were never seeded after migrations. The fix: use `django_apps.get_app_config("dab_feature_flags")` to get the live instance.
- **Insight**: Django signals match senders by identity (`id()`), not by type or equality. When using `sender=` with `post_migrate`, you must pass the live AppConfig instance (from `django.apps.apps.get_app_config()`), not the AppConfig class itself. This is a subtle Django signal pitfall that produces no error -- the handler simply never fires.

### Dashboard HTML template vulnerable to XSS via template literals
- **Commits**: 4892777 (#187)
- **What happened**: The dashboard's inline JavaScript used ES6 template literals (backtick strings) to render task data (names, function names, error messages, cron expressions) directly into HTML without escaping. Any user-controlled data stored in task fields could inject arbitrary HTML/JavaScript. The fix introduced an `html` tagged template literal function that auto-escapes all interpolated values via `escapeHtml()` (replacing `&`, `<`, `>`, `"`, `'`), with a `RawHtml` wrapper class for values that are intentionally HTML (like nested `html` calls). All ~30 template literal usages in `dashboard.html` were converted from plain backtick strings to `html` tagged templates.
- **Insight**: The tagged template literal pattern (`html\`...\``) is an elegant solution for HTML escaping in client-side JavaScript -- it provides automatic escaping by default with explicit opt-in for raw HTML via a wrapper class. This is the same pattern used by libraries like lit-html. The dashboard's single-file architecture (all JS inline in the HTML template) made this a localized fix rather than requiring a framework-level change.

### Dashboard cleanup task schedule collision at 5:00 AM
- **Commits**: 4892777 (#187)
- **What happened**: `cleanup_dashboard_reports_old_data` was scheduled at `0 5 * * *`, colliding with `daily_task_cleanup` at the same time. This is the same class of bug as the earlier collision between cleanup and rollup at 2:00 AM (#163). The fix moved dashboard cleanup to 5:30 AM. The existing test that verifies no two tasks share the same cron expression caught this.
- **Insight**: The cron uniqueness test added in #163 proved its value here. Without it, another schedule collision would have been introduced. Any new task added to task_groups.py should be checked against the existing schedule.

### Shared Django DB connection manually closed in finally blocks -- broke concurrent tasks
- **Commits**: 258547a (#194)
- **What happened**: `_collect_data()` in dashboard_reports and `FilterOptionsViewSet.list()`/`.retrieve()` had `finally` blocks that called `db_connection.close()` on the raw psycopg connection returned by `get_db_connection("awx")`. This connection is Django's singleton object (`connections["awx"].connection`), shared across all tasks in the same worker process. When one task closed it, any concurrent task using the same connection got `psycopg.OperationalError: the connection is closed`. Django's wrapper didn't know the raw socket was dead, so `ensure_connection()` was skipped on the next call. The fix removed all manual `close()` calls and added `close_old_connections()` at safe boundaries (in `run_with_lock()` before acquiring advisory locks, and in `HealthView.get()` before `ensure_connection()`).
- **Insight**: Never manually close a raw connection obtained from Django's `connections[]` API -- it is a singleton shared across the process. Django manages connection lifecycle; manual closing creates race conditions between concurrent tasks. Call `close_old_connections()` only at task entry points (before any locks are held), not inside utility functions like `get_db_connection()`, because it closes ALL connections including those holding advisory locks.

### close_old_connections() placed in get_db_connection() broke advisory locks
- **Commits**: 258547a (#194)
- **What happened**: An intermediate fix tried adding `close_old_connections()` inside `get_db_connection()` to handle stale connections. But `close_old_connections()` closes ALL Django connections, including the default connection that `run_with_lock()` uses to hold PostgreSQL advisory locks. This caused lock release failures. The final fix moved `close_old_connections()` to `run_with_lock()` (before lock acquisition, when no locks are held) and explicitly documented in `get_db_connection()` that it must NOT call `close_old_connections()`.
- **Insight**: `close_old_connections()` is a global operation that affects ALL database connections, not just one. It must only be called at safe boundaries where no connections are actively in use (e.g., at the very start of a task, before acquiring any locks). The iterative fix process (5 squashed commits) shows how tricky Django connection lifecycle management is in concurrent worker environments.

### Scheduler spammed skip logs every 30s for disabled feature flag tasks
- **Commits**: babf061 (#199)
- **What happened**: When a feature flag like `DASHBOARD_COLLECTION` was disabled, the 30-second `_periodic_database_sync` loop would: (1) find the task via `Task.immediate_tasks()` (still `status="pending"` in DB), (2) call `_execute_database_task` which checked the flag and logged an INFO "Skipping task..." message, (3) call `_remove_database_task` to remove from in-memory tracking, but leave the DB row as `status="pending"`. Next cycle, the task was rediscovered and the loop repeated indefinitely. The fix gates task pickup behind a feature flag check *before* adding to the scheduler, so disabled tasks are silently bypassed. The skip log in `_execute_database_task` was downgraded from INFO to DEBUG as a safety net.
- **Insight**: In polling-based architectures, if you remove an item from the in-memory tracking set without changing its DB state, the next poll will rediscover it. The correct approach for feature-flag-disabled tasks is to not pick them up at all, rather than picking them up and then skipping them. This also means the task automatically starts when the flag is re-enabled -- no manual `init-system-tasks` needed.

## Superseded / Semi-Obsolete

### Django signals on Task model caused widespread test failures
- The `_skip_signals` workaround from a044bd7 (#54) is no longer needed. Signals were removed entirely in 85d2cbb (#57) because they don't work across process boundaries.

### dispatcherd config hardcoded database credentials
- The hardcoded credentials in `config/dispatcherd.yaml` (from the `use_django_db` revert in 3a8f7d5 #48) were replaced in 0e15cbd (#66) with runtime injection from Django settings via `_load_config_with_django_db()`.

### URL prefix env var named inconsistently, fixed in follow-up PR
- The `METRICS_URL_PREFIX` -> `METRICS_SERVICE_URL_PREFIX` rename from #69/#70 was superseded by #87 which moved URL prefix to a Django setting (`settings.URL_PREFIX`), and then by #91 which added proper prefix interpretation as an actual URL path prefix with slash sanitization.

### Dispatcherd max workers reduced from 4 to 1 as a band-aid
- Workers 4->1 (#148), then 1->4 (#167) with real fixes. See the main entries above and `task_system.md`.
