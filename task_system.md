# Task System

> Default repo: metrics-service

## Learnings
### Initial task system was a simple function registry with hardcoded scheduling
- **Commits**: dd5603f
- **What happened**: The first version of `apps/core/tasks.py` defined three placeholder task functions (`cleanup_old_data`, `send_notification_email`, `process_user_data`) and a `TASK_FUNCTIONS` dict mapping names to callables. Scheduling was a simple `SCHEDULED_TASKS` dict with interval-in-seconds values. No database persistence.
- **Insight**: The `TASK_FUNCTIONS` registry pattern (string name -> callable) was established from day one and survived all subsequent refactors. This registry is the contract between the scheduling layer and the execution layer.

### Database-driven task system added with Task, TaskExecution, TaskChain models
- **Commits**: 141801c
- **What happened**: Added `Task` model with status tracking, priority, cron expressions, retry logic, and timeout. Added `TaskDependency` for DAG-style dependencies, `TaskExecution` for execution history, `TaskChain` + `TaskChainMembership` for named workflows. Also added `execute_db_task()` as a bridge function that looks up a DB task, runs its referenced function from `TASK_FUNCTIONS`, and updates status.
- **Insight**: The architecture creates a two-layer system: DB-defined tasks reference function names that must exist in the `TASK_FUNCTIONS` registry. This decouples scheduling/tracking (DB) from execution (Python functions), but means a DB task with a typo in `function_name` will fail at runtime, not at definition time.

### Recurring tasks create new Task rows for each occurrence
- **Commits**: 141801c
- **What happened**: `schedule_next_occurrence()` handles recurring tasks by creating a *new* `Task` object with `name=f"{task.name} (Next)"` and the computed next run time. The old task stays in `completed` status.
- **Insight**: This "clone a new row per occurrence" approach means the Task table grows linearly with recurring executions. It preserves full history but requires cleanup (which was later added as `cleanup_old_tasks`).

### TaskScheduler was a polling-based service
- **Commits**: 141801c
- **What happened**: `TaskScheduler` class used a `while self.running: sleep(poll_interval)` loop to poll for ready tasks and submit them to the dispatcher. Also had `cleanup_stale_tasks()` to mark timed-out tasks as failed.
- **Insight**: This polling approach was a pragmatic starting point but was later replaced by APScheduler integration for cron-based scheduling (in commits outside this batch).

### Bug: Sonar fix introduced a copy-paste error in task display
- **Commits**: cc2ac77, 5b12d74 (#7)
- **What happened**: In cc2ac77, the `show_task` command refactored to use helper methods, but the "Result Data" label was accidentally changed to "Task Data" (a copy-paste error from the line above it). This was caught and fixed in 5b12d74 where it was corrected back to "Result Data".
- **Insight**: Extracting methods from a long function can introduce copy-paste bugs in the split points. The Sonar-driven refactoring to reduce method complexity created a bug that needed a follow-up fix.

### Management command refactored from if/elif chain to action dispatch dict
- **Commits**: 5b12d74 (#7)
- **What happened**: The `manage_tasks` command's `handle()` method was refactored from a long `if/elif` chain to an `action_handlers` dictionary mapping action strings to methods, with a `_execute_action()` dispatcher. Also added proper exception chaining (`from e`).
- **Insight**: Dictionary-based dispatch is cleaner and more extensible than if/elif chains for command routing, but introduces indirection that can make debugging slightly harder.

### Task groups system introduced for organized task management
- **Commits**: edb4626 (#25)
- **What happened**: A new `apps/tasks/task_groups.py` module was created with a `TaskGroup` class that groups related tasks with feature flag controls. Three groups were defined: `SYSTEM_TASKS_GROUP` (always enabled, cleanup/hello_world), a metrics collection group, and an anonymization group. Each task config specifies `task_id`, `function`, `cron` expression, `args`, `description`, and `category`. The `init-system-tasks` management command syncs these definitions to the DB.
- **Insight**: The task groups pattern creates a declarative "source of truth" for what tasks exist and when they run, separate from the DB state. This means task definitions live in code (version-controlled, reviewable) while the DB tracks runtime state. The feature flag integration allows groups to be toggled without code changes.

### APScheduler integration attempted and rolled back to polling
- **Commits**: edb4626 (#25)
- **What happened**: The commit message explicitly says "Rolled back to poll based scheduling as the APSchedule stopped working." An APScheduler-based cron scheduler (`apps/tasks/cron_scheduler.py`, 360 lines) was created but the actual scheduling fell back to a simpler poll-based approach (`apps/tasks/simple_scheduler.py`, 248 lines) when APScheduler proved unreliable.
- **Insight**: APScheduler's in-process scheduling can be fragile when running inside Django management commands alongside other services (runserver, dispatcherd). The team kept the APScheduler code around but also built a fallback. This dual-scheduler situation was later resolved.

### is_system_task flag added to distinguish system tasks from user tasks
- **Commits**: edb4626 (#25)
- **What happened**: A new `is_system_task` BooleanField was added to the Task model (migration 0002) to mark tasks that are system-defined (created by `init-system-tasks`) vs. user-created. The dashboard was updated to show system task indicators.
- **Insight**: This distinction is important for cleanup -- system tasks should not be deleted by `cleanup_old_tasks`, and users should not be able to modify system task definitions through the API.

### dispatcherd configuration made explicit with YAML config file
- **Commits**: edb4626 (#25)
- **What happened**: A new `apps/tasks/dispatcherd_config.py` (228 lines) was created to generate dispatcherd configuration, along with a `config/dispatcherd.yaml` template. The configuration includes worker settings, task timeouts, max tasks per worker, and logging configuration. The `run_dispatcherd` command was updated to use this config.
- **Insight**: Making dispatcherd configuration explicit and code-generated (rather than relying on command-line flags) ensures consistency between the standalone `run_dispatcherd` command and the combined `metrics_service run` command.

### Django signals added for automatic task routing
- **Commits**: edb4626 (#25)
- **What happened**: A new `apps/tasks/signals.py` module was created that uses Django's `post_save` signal on the Task model to automatically route newly created tasks based on their properties (immediate/scheduled/recurring). This eliminates the need for manual task submission after creation.
- **Insight**: Signal-based task routing provides a zero-configuration experience for task creators, but introduces implicit behavior that can be hard to debug. Tasks are automatically submitted to dispatcherd just by saving a Task model instance.

### Feature enable/disable functions became real implementations
- **Commits**: c8e5f0d (#36)
- **What happened**: `enable_task_group()` and `disable_task_group()` were previously stubs that logged "Would enable task group: ..." without doing anything. In this commit, they became real implementations using `Setting.objects.get_or_create()` to persist the toggle state in the database. A new `set_feature_enabled()` generic helper was also added.
- **Insight**: The stub-to-real transition followed the pattern of getting the architecture right first (task groups, feature flags concept) and filling in the implementation later. The `get_or_create` pattern with conditional update avoids race conditions while handling both first-time and subsequent toggle changes.

### Collector tasks switched from raw connection strings to Django connections API
- **Commits**: 0854775 (#40)
- **What happened**: All four collector tasks (`collect_anonymous_metrics`, `collect_config_metrics`, `collect_job_host_summary`, `collect_host_metrics`) were refactored from accepting a `db` string parameter to using `from django.db import connections` and `connections[db_name]`. The parameter was renamed from `db` (raw connection string) to `database` (Django database alias, defaulting to `"awx"`). An AWX database entry was added to `DATABASES` in `defaults.py` so `connections["awx"]` resolves properly.
- **Insight**: Using Django's `connections` API instead of raw connection strings integrates naturally with Django's settings, connection pooling, and lifecycle management. The AWX database alias approach means operators configure the AWX connection once in settings (via `METRICS_SERVICE_DATABASES__awx__HOST` etc.) and all collector tasks use it transparently.

### CronTaskScheduler renamed to UnifiedTaskScheduler to handle both task groups and DB tasks
- **Commits**: 7b39f53 (#56)
- **What happened**: The `CronTaskScheduler` was renamed to `UnifiedTaskScheduler` and extended to handle both task group definitions (cron-scheduled) and ad-hoc database tasks (immediate, scheduled, recurring). The simple scheduler module was removed. The unified scheduler uses APScheduler for cron triggers and `DateTrigger` for one-time scheduled tasks, plus periodic DB polling (configurable `check_interval`, default 30s) to discover new tasks. A `_db_task_jobs` dict tracks task_id -> job_id mappings to avoid re-scheduling already-tracked tasks. The scheduler was moved to run as a separate process from the Django runserver because Django signals don't work across process boundaries.
- **Insight**: Unifying task group scheduling and database task scheduling into one component eliminates the dual-scheduler complexity, but introduces a hybrid approach: cron-based for known tasks, polling-based for ad-hoc DB tasks. The polling is necessary because when the scheduler runs in a separate process, Django's `post_save` signals on the Task model are invisible to it.

### Task.retry() method added with intentionally preserved attempt counter
- **Commits**: 7b39f53 (#56)
- **What happened**: A `retry()` method was added to the Task model that resets a failed task's status to "pending" without resetting `self.attempts`. The code has an explicit comment: "Do NOT reset attempts to 0 here. The attempts counter must persist across retries to properly enforce the max_attempts limit." The method also attempts to submit the task directly to dispatcherd for immediate execution.
- **Insight**: The decision to preserve the attempts counter across manual retries prevents users from bypassing `max_attempts` by calling `retry()` in a loop. This is a security/reliability design choice documented via code comments.

### METRICS_UTILITY_AVAILABLE flag with fallback attributes for testing
- **Commits**: 7b39f53 (#56)
- **What happened**: `tasks_collector.py` wraps all metrics-utility imports in try/except and sets `METRICS_UTILITY_AVAILABLE = True/False`. When the library is unavailable, fallback `None` attributes are set for `anonymized_rollups_processor`, `config`, `job_host_summary`, `main_host`, `main_jobevent`. Tests patch `METRICS_UTILITY_AVAILABLE` to control behavior without requiring the actual library installed.
- **Insight**: This fallback pattern allows the full test suite to run without the metrics-utility dependency installed, which is important because metrics-utility depends on AWX-specific packages that may not be available in CI. The `None` fallbacks prevent `AttributeError` on import while the flag guards actual usage.

### Django signals removed from task management in favor of APScheduler polling
- **Commits**: 85d2cbb (#57)
- **What happened**: The entire `apps/tasks/signals.py` module (144 lines) was deleted. The `post_save` and `post_delete` signal handlers that auto-routed tasks to dispatcherd and the scheduler were removed. The `_skip_signals` attribute on Task model instances was removed from all code paths (views, scheduler, models). Task creation via the API now just calls `super().create()` with a comment: "All tasks are now handled by APScheduler polling." The PR description says signals "won't work across process'."
- **Insight**: Signals were architecturally incompatible with the decision to run APScheduler in a separate process. Since `post_save` only fires in the process where `.save()` is called, the scheduler process never saw task creation events. DB polling is more reliable for cross-process communication, even though it adds latency (up to `check_interval` seconds). The removal also eliminated all the `_skip_signals` workarounds that had proliferated through tests and production code.

### execute_db_task ordering bug: post-execution must happen before recurring status reset
- **Commits**: e43d59d (#59)
- **What happened**: In `execute_db_task()`, the code was resetting recurring tasks to "pending" status *before* calling `handle_post_execution()`. Since `handle_post_execution` checks `task.status == 'completed'` to decide whether to trigger dependent tasks, dependent tasks would never fire for recurring tasks. The fix moved `handle_post_execution()` (and the log statement) to run *before* the recurring status reset.
- **Insight**: Order of operations matters critically in state machine code. The task goes through: running -> completed -> (post-execution triggers) -> pending (for recurring). Moving the pending reset before the trigger check silently broke a feature. This is the kind of subtle bug that is hard to catch in review because both orderings "look right" -- the issue is only apparent when you trace through what `handle_post_execution` checks.

### Duplicate immediate task execution bug fixed by tracking in _db_task_jobs
- **Commits**: 3100514 (#64)
- **What happened**: A one-line fix: before calling `self._execute_database_task(task.id)` for immediate tasks during periodic DB sync, the task ID is now added to `self._db_task_jobs` tracking dict. Without this, the scheduler's periodic sync would see the same pending immediate task on the next polling cycle and submit it again, because the task was executed but never tracked. This could cause duplicate executions and even system shutdown if dispatcherd's queue overflowed.
- **Insight**: When switching from signal-based (instant, once) to polling-based (periodic, repeated) task discovery, any task not tracked in the "already seen" set will be re-discovered and re-executed on the next poll. This is a fundamental pitfall of polling architectures: you must track what you've already processed before processing it, not after.

### Hourly and daily metrics collection pipeline
- **Commits**: 3a58426 (#79)
- **What happened**: A full metrics collection pipeline was added with three hourly collector tasks (`collect_job_host_summary_hourly`, `collect_host_metrics_hourly`, `collect_main_host_hourly`), a daily aggregation task (`daily_metrics_rollup`), a daily anonymization task (`daily_anonymize_and_prepare`), and a cleanup task (`cleanup_metrics_data`). The task groups were restructured: `METRICS_COLLECTION_GROUP` (always enabled, no feature flag) runs hourly collection and daily rollup; `ANONYMIZATION_GROUP` (controlled by `ANONYMIZED_DATA_COLLECTION` flag) runs anonymization and Segment transmission. Several deprecated functions were removed: `test_segment_track`, `debug_segment_messages`, `send_notification_email`, `process_user_data`. A unified `collect_single_collector` function replaced individual collector task functions.
- **Insight**: The design decision to always collect local metrics (even when `ANONYMIZED_DATA_COLLECTION` is opted out) prevents data gaps if the customer later opts back in. Only the anonymization and transmission tasks are gated by the opt-out flag. The hourly collectors use the `unique_together` constraint on `(collector_type, collection_timestamp)` to prevent duplicate entries when retrying.

### Task queue mapping expanded for metrics tasks
- **Commits**: 3a58426 (#79)
- **What happened**: The dispatcherd queue mapping in both `cron_scheduler.py` and `dispatcherd_config.py` was updated to include the new metrics task types. Tasks are routed to different queues based on their function name, allowing different worker configurations for I/O-bound collection tasks vs. CPU-bound aggregation tasks.
- **Insight**: Queue-based task routing allows operational tuning without code changes -- more workers can be assigned to collection queues during peak hours, while aggregation tasks run with fewer workers during off-peak.

### Management command rewritten from threads to processes
- **Commits**: 0c14d9c (#85)
- **What happened**: The `metrics_service run` command was rewritten to spawn Django, dispatcherd, and the task scheduler as three separate OS processes via `subprocess.Popen`. The thread-based `ProcessManager` service class (341 lines) was deleted. Output from all three processes is multiplexed using Python's `selectors` module for non-blocking I/O. Signal handlers (`SIGINT`/`SIGTERM`) terminate children with a 3-second grace period. A `--check-interval` argument was added for scheduler polling frequency.
- **Insight**: Threads were problematic for service management: thread termination in Python is cooperative (no way to force-kill a thread), output interleaving required locks, and infinite loop bugs were hard to diagnose. Processes provide hard isolation and OS-level termination. The `selectors.DefaultSelector` approach avoids busy-waiting while still detecting output from any process.

### Major task system cleanup: dead code removal and subdirectory reorganization
- **Commits**: e137d39 (#92)
- **What happened**: A massive cleanup (-14548/+8235 lines across 121 files) that restructured the task system. Key changes: (1) Tasks moved into subdirectories: `apps/tasks/simple/` (hello_world), `apps/tasks/collectors/` (metrics collection), `apps/tasks/cleanup/` (cleanup_old_tasks, cleanup_metrics_data). (2) Removed dead code: `TaskDependency`, `TaskChain`, `TaskChainMembership` models; `is_recurring` field (replaced by checking if `cron_expression` is non-empty); `waiting` task state; `priority` field; legacy collector system (collect_single_collector, full_process, full_process_anonymize, anonymize_data, send_to_segment_task, collect_metrics); service layer classes (CronManager, ServiceConfig, SystemInitializer, TaskManager); `metrics_service cron` subcommand. (3) Simplified task groups: `enabled_setting/default_enabled` replaced by single `feature_flag` field; `METRICS_COLLECTION_ENABLED` flag removed (collection is always enabled); only `ANONYMIZED_DATA_COLLECTION` flag remains. (4) Fixed `AppConfig.ready()` writing to DB (moved to explicit `init-default-settings` management command). (5) Added `makemigrations` check to PR CI. (6) `init-default-settings` now supports `--overwrite` and recreates unchanged settings; added corresponding `remove-default-settings` with `--all-known` and `--all-settings` flags. (7) `init-system-tasks` now recreates all tasks on each run. (8) Over 2000 lines of obsolete test code removed. (9) `run_task.py` moved to `scripts/`. (10) Merged queue-mapping logic into `dispatcherd_config.py`. (11) Coverage config moved from pytest `addopts` (which forced coverage on every run) to `[tool.coverage.*]` sections.
- **Insight**: This cleanup was necessary technical debt payoff -- the task system had accumulated unused models (TaskChain, TaskDependency), stale task functions, and two feature flag fields where one sufficed. The `AppConfig.ready()` fix is architecturally significant: `ready()` runs on every Django invocation (management commands, tests, shell), not just server start, so writing to the DB there caused warnings and unnecessary DB hits. Moving to an explicit init command is the correct pattern.

### Collector tasks consolidated into generic hourly and snapshot functions
- **Commits**: 1580ff2 (#109)
- **What happened**: The individual collector tasks (collect_job_host_summary_hourly, collect_host_metrics_hourly, collect_main_host_hourly) were replaced by two generic collector functions: `collect_hourly_metrics` and `collect_snapshot_metrics`. Each accepts a `collector_type` parameter that maps to a registry of known metrics-utility library imports. The registries use lazy imports to prevent metrics_utility from breaking unrelated task registration. Collectors were reorganized: (1) Removed `main_host` (not in anonymized chain) and `main_jobevent` (too slow, disabled). (2) Added `job_host_summary_service` (_service variant for partition pruning), `unified_jobs`, `credentials_service`, `execution_environments`. (3) Daily rollup refactored to read from HourlyMetricsCollection records rather than collecting data inline. (4) Anonymization task updated to pass rollups for 4 collector types plus empty `events_modules_rollup`. (5) The rollup expectation changed to `gather()->dataframe`, `prepare(dataframe)->json`, `merge(json,json)->json`.
- **Insight**: The registry-based approach (mapping collector_type to collector function + rollup processor) eliminates the need for individual collector files that were all identical except for imports. Adding a new collector now means just updating the registry dict. The lazy import pattern (`def _get_hourly_collectors()`) is crucial because importing metrics_utility at module level would break tasks like hello_world that don't need the library.

### Bug fix: generic_collect_metrics must reset status on update_or_create
- **Commits**: 1580ff2 (#109)
- **What happened**: The `update_or_create` call in `generic_collect_metrics` only set `raw_data` in `defaults`, omitting `status="collected"` and `error_message=""`. When a collection was already processed by daily rollup (status="processed") and re-collected, the update left status as "processed", making the new data invisible to the next rollup which filters by `status="collected"`.
- **Insight**: Django's `update_or_create` only applies `defaults` when creating a new record; on update, it sets them too, but omitting fields means they keep their old values. For state machine fields like `status`, always include them in `defaults` to ensure re-processing resets state correctly.

### Two more snapshot collectors added (controller_version_service, table_metadata)
- **Commits**: 05dc0c9 (#112)
- **What happened**: Added `controller_version_service` (ControllerVersionAnonymizedRollup) and `table_metadata` (TableMetadataAnonymizedRollup) to the snapshot collectors registry. Added corresponding scheduled tasks at 1:35 AM and 1:40 AM. Updated daily_metrics_rollup to merge these new collector types and daily_anonymize_and_prepare to pass them to `anonymize_rollups()`.
- **Insight**: This demonstrates the benefit of the registry-based collector design from #109 -- adding two new collectors was a small, clean change (57 additions across 8 files) rather than requiring new task files, new TASK_FUNCTIONS entries, and new test files for each.

### cleanup_activitystream task added for DAB audit log pruning
- **Commits**: e3b9969 (#144)
- **What happened**: A new standalone task `cleanup_activitystream` was added under `apps/tasks/cleanup/`. It deletes `ansible_base.activitystream.Entry` records older than a configurable `days_old` threshold (default: 7 days). Supports `dry_run` mode. The function returns error result dicts for invalid parameters (e.g., `days_old=0` or non-integer) instead of raising, because it runs inside `task_execution_wrapper` which converts exceptions to error dicts. Also removed the hardcoded `SEGMENT_WRITE_KEY` from `apps/tasks/settings.py`. The commit shows 10 squashed commits -- the cleanup was initially integrated into `cleanup_old_tasks`, then refactored out into its own task after several iterations.
- **Insight**: The iterative development visible in the squashed commits (first adding to cleanup_old_tasks, then handling partial success, then extracting to a standalone task) shows the value of keeping tasks single-purpose. Mixing ActivityStream cleanup with task cleanup created error handling complexity (partial success reporting) that went away once they were separated. Returning error dicts instead of raising follows the pattern established by `task_execution_wrapper`.

### Task submission changed from string module paths to registered callables
- **Commits**: 3de90fc (#153)
- **What happened**: `UnifiedTaskScheduler._execute_scheduled_task()` changed from `submit_task(f"apps.tasks.tasks.{function_name}", ...)` (string reference) to `submit_task(TASK_FUNCTIONS[function_name], ...)` (registered callable). Tests updated to assert the callable is passed rather than a string path.
- **Insight**: The original string-based submission (`"apps.tasks.tasks.hello_world"`) assumed dispatcherd would resolve the string to a callable via import, but `submit_task` actually expects a callable directly. Passing the registered callable from `TASK_FUNCTIONS` is both correct and more efficient (no runtime import resolution). This aligns the scheduler's behavior with how `execute_db_task` already worked.

### Auto-retry for failed tasks added to execute_db_task
- **Commits**: 3ee3923 (#154)
- **What happened**: After `execute_db_task()` finishes with `status == "failed"`, it now checks `task.can_retry()` (which compares `task.attempts` against `task.max_attempts`). If retryable, the task is refreshed from DB, logged as "Auto-retrying", and `task.retry()` is called (which resets status to "pending" and re-submits to dispatcherd). The change is just 6 lines in `tasks_system.py`.
- **Insight**: This closes the gap where failed tasks required manual intervention to retry. The `task.retry()` method (added earlier in #56) already existed but was never called automatically. Combined with the preserved attempt counter (also from #56), this creates bounded automatic recovery: tasks retry up to `max_attempts` times, then stay in "failed" for manual investigation. The pattern is idempotent-safe because the attempt counter persists across retries.

### Scheduled task execution refactored to be fully DB-driven
- **Commits**: 520fd11 (#155)
- **What happened**: `_execute_scheduled_task()` was completely rewritten. Instead of checking feature flags from args and submitting to dispatcherd directly, it now: (1) looks up the Task row by name from the DB (`Task.objects.filter(name=task_id, is_system_task=True)`), (2) checks task status (skips cancelled/completed), (3) re-reads `_feature_flag` from `task.task_data` (not from the APScheduler args), and (4) routes through `_execute_database_task()` instead of `submit_task()`. The `function_name` and `args` parameters became vestigial (kept for APScheduler compatibility). Added guidance message when task is missing: "run 'manage.py metrics_service init-system-tasks'". Also added `functools.wraps` to `task_execution_wrapper`, `STATIC_ROOT` for production, `collectstatic` in init entrypoint, and YAML files in package data.
- **Insight**: This change makes the DB the single source of truth for system task configuration. Previously, task args (including feature flags) were baked into the APScheduler job at scheduler start time, meaning changes to feature flags required a scheduler restart. Now, `task.task_data` is re-read from DB on every execution, so `init-system-tasks` changes take effect immediately. The trade-off is a DB query per scheduled task execution, but system tasks run at most hourly, so the overhead is negligible.

### close_old_connections() required before ORM access in scheduler threads
- **Commits**: 59a6366 (#158)
- **What happened**: The `UnifiedTaskScheduler` runs `_execute_scheduled_task`, `_periodic_database_sync`, and `_execute_database_task` in APScheduler threads, which are long-lived. Django's database connections can go stale (server-side timeout, network reset) while the thread is idle between scheduler ticks. Three `close_old_connections()` calls were added at the entry point of each method -- before any ORM access.
- **Insight**: Django automatically closes stale connections at the start and end of each HTTP request, but background threads (APScheduler, cron jobs, daemon loops) bypass the request lifecycle entirely. Any code that does ORM work from a long-lived thread must call `close_old_connections()` explicitly before accessing the database. Without this, production schedulers intermittently fail with "connection already closed" or "server closed the connection unexpectedly" errors that are nearly impossible to reproduce in development.

### init-system-tasks unconditionally deletes and recreates all system tasks
- **Commits**: 80facfd (#159)
- **What happened**: `create_system_tasks` was simplified to unconditionally delete all existing system tasks before recreating them, removing a `force` parameter that had been briefly added. The rationale: this command is only called from the init container where no tasks are running, so conditional deletion logic is unnecessary complexity.
- **Insight**: Init commands that sync "code as source of truth" to the DB should be idempotent and total -- delete everything and recreate from the definitions in code. Trying to be clever about preserving running tasks adds fragile logic for a scenario (init while tasks run) that shouldn't happen in the container-based deployment model.

### Task execution records were orphaned because execution_id was not passed to workers
- **Commits**: d81dfb3 (#162)
- **What happened**: `submit_task_to_dispatcher` created a `TaskExecution` record but never passed its ID to `execute_db_task` via dispatcherd kwargs. The worker always received `execution_id=None`, so it could never update the execution record past "pending". The fix: capture the `execution` from `TaskExecution.objects.create()` and pass `execution_id=execution.id` in the `kwargs` dict submitted to dispatcherd.
- **Insight**: When one part of the system creates a record and another part updates it, the handoff must include the record's identity. Passing just the parent task ID but not the execution ID meant the worker created its own execution record (or skipped updates entirely), leaving the original stuck in "pending" forever. This is a classic "ID not propagated across process boundary" bug.

### Cron schedule collision between cleanup and daily rollup at 2:00 AM
- **Commits**: d24e7dc (#163)
- **What happened**: `daily_task_cleanup` and `daily_metrics_rollup` both had cron expression `0 2 * * *`. When they ran simultaneously, `cleanup_old_tasks` could delete `TaskExecution` records that `daily_metrics_rollup` was actively writing to via the `DailyMetricsSummary.rollup_task_execution` foreign key. The fix moved cleanup to `0 5 * * *` (5:00 AM), one hour after the last pipeline task (`cleanup_metrics_data` at 4:00 AM). A new test was added to verify no two tasks share the same cron expression.
- **Insight**: When defining cron schedules for tasks that touch overlapping data, check for time collisions. The fix also added a test that parses all cron expressions across all task groups and asserts no duplicates, preventing future schedule collisions.

### ANONYMIZED_DATA_COLLECTION flag incorrectly gated all collection, not just anonymization
- **Commits**: d3fb802 (#168)
- **What happened**: `METRICS_COLLECTION_GROUP` had `feature_flag="ANONYMIZED_DATA_COLLECTION"`, meaning all 12 tasks (hourly collection, snapshots, rollup, cleanup, AND anonymization/sending) were disabled when a customer opted out. The intent was to stop only the 2 tasks that transmit data to Red Hat. The fix split the group: `METRICS_COLLECTION_GROUP` (no feature flag, always runs collection/rollup/cleanup) and `ANONYMIZATION_GROUP` (gated by `ANONYMIZED_DATA_COLLECTION`, contains only `daily_anonymize_and_prepare` and `send_to_segment_daily`). A new `get_all_tasks_for_init()` function was added so `init-system-tasks` writes all tasks to DB unconditionally (not just enabled ones), and `_feature_flag` in `task_data` gates execution at runtime.
- **Insight**: Feature flags must be scoped precisely to what they control. A flag named "ANONYMIZED_DATA_COLLECTION" should gate anonymization and data transmission, not local data collection. When the flag was too broad, operators who opted out and later re-enabled sending had permanent data gaps because local collection had stopped. The architectural lesson: always-collect-locally, only-gate-transmission is the correct pattern for opt-out telemetry.

### Daily collectors (collect_daily_metrics) added for time-range metrics
- **Commits**: e8ae871 (#165)
- **What happened**: A new `collect_daily_metrics` function was added for collectors that need explicit `since/until` time boundaries (unlike hourly collectors that use `hour_timestamp` or snapshot collectors that have no time window). The first daily collector is `task_executions_service`, which queries the metrics-service's own database (not AWX) for pipeline observability data. It runs at 1:50 AM, storing at yesterday 23:00 UTC so the daily rollup picks it up. A `feature_flags_service` snapshot collector was also added at 1:45 AM.
- **Insight**: The collector taxonomy is now three types: hourly (24x/day, 1-hour windows), snapshot (1x/day, no time window), and daily (1x/day, full-day window). Each maps to a `generic_collect_metrics` call with different parameters. The daily collector queries the metrics-service's own DB rather than AWX, demonstrating the collector framework's flexibility.

### Workers restored to 4 with atomic task claiming and advisory locks
- **Commits**: ccf9494 (#167)
- **What happened**: A comprehensive overhaul of the task execution system that reversed the #148 band-aid (1 worker) and addressed the root causes. Key changes: (1) `max_workers` restored from 1 to 4 in `dispatcherd.yaml`. (2) Atomic task claiming via `_claim_task()` using `select_for_update(skip_locked=True)` + `UPDATE WHERE status='pending'` so only one worker can claim a task. (3) `TaskExecution` created inside `_claim_task()` (not `submit_task_to_dispatcher`) to prevent orphaned records. (4) PostgreSQL advisory locks (`run_with_lock()`) for collector tasks -- `TASK_LOCKS` maps task functions to lock IDs so hourly collectors can't run in parallel. (5) Retry with delay: `Task.retry(delay_seconds=N)` sets `scheduled_time` into the future so locked-out tasks wait before retrying (default 600s). (6) `Task.ready_to_run()` classmethod filters pending non-recurring tasks whose `scheduled_time` has passed. (7) Removed redundant `@task_execution_wrapper` and `@task(queue=...)` decorators from all 9 task functions (execute_db_task already handles lifecycle). (8) Removed the dual APScheduler registration path -- all tasks now go through `_periodic_database_sync -> _execute_database_task -> submit_task_to_dispatcher`. (9) Task functions now return `create_task_result("error", ...)` instead of raising `ValueError`. (10) Feature flag and cancelled/completed status checks moved into `_execute_database_task`.
- **Insight**: The single-worker band-aid from #148 hid three distinct concurrency bugs: (a) no atomic claim meant two workers could claim the same task, (b) no locking meant two hourly collectors could run simultaneously and conflict, (c) immediate retry after lock failure caused thrashing. The real fix was defense in depth: atomic DB claim prevents duplicate execution, advisory locks prevent logical conflicts between collector tasks, and retry delays prevent retry storms. This is a textbook example of why reducing concurrency (1 worker) is a band-aid -- it avoids the bug without fixing the underlying race conditions.

### Segment send-to-segment changed from fixed cron to jittered one-time task
- **Commits**: 8d4ae7e (#183)
- **What happened**: The `send_to_segment_daily` cron entry (3:30 AM daily) was removed from `ANONYMIZATION_GROUP`. Instead, `daily_anonymize_and_prepare` now creates a one-time `send_anonymized_to_segment` Task inside the same atomic transaction as the payload creation, scheduled at `now + jitter`. The jitter (0-239 minutes) is derived from a stable per-installation seed: `int(UUID(service_id())) % 10^9` fed to `random.Random(seed).randint(0, 239)`. This means the same installation always gets the same offset, but different installations spread across the 4-hour window.
- **Insight**: Fixed cron schedules cause thundering herd problems when many installations share the same time. Using a deterministic seed (installation UUID) ensures the jitter is stable (same time every day for a given installation) while distributing load across the fleet. Creating the send task inside the anonymization transaction guarantees the send is only scheduled when anonymization succeeds.

### Stale save() after submit_task fixed; all saves narrowed to update_fields
- **Commits**: 4892777 (#187)
- **What happened**: A `task.save()` call after `submit_task()` in `submit_task_to_dispatcher` could overwrite the atomic `F("attempts") + 1` increment performed by the dispatcherd worker's `_claim_task`. This caused tasks to appear stuck at attempts 0/3 despite having failed -- the retry mechanism fired but the attempt counter never advanced. The fix removed the redundant save and also narrowed all remaining `task.save()` and `execution.save()` calls throughout the codebase to use `save(update_fields=[...])`, always including `"modified"`. This prevents any future stale-object writes from overwriting fields they didn't intend to touch.
- **Insight**: `save(update_fields=[...])` is the correct Django pattern when multiple processes may be updating different fields on the same model instance concurrently. Bare `save()` writes every field, creating a race condition window where a concurrent atomic update can be silently overwritten. The `"modified"` field must always be included to keep auto_now working.

### Queue routing moved from dispatcherd_config to TASK_METADATA
- **Commits**: 4892777 (#187)
- **What happened**: The hardcoded `get_queue_for_function` dict in `dispatcherd_config.py` was replaced by a `queue` field on each entry in `TASK_METADATA` (in `tasks.py`). Queue names were simplified to three: `maintenance`, `metrics`, `dashboard`. A consistency test was added to verify every `TASK_FUNCTIONS` entry has a `TASK_METADATA` entry with a `queue` value matching one of the channels in `dispatcherd.yaml`. The unused `category` field in task_groups.py task dicts was also removed -- `tasks_system.py` now reads the category from `TASK_METADATA` directly (same source as the API).
- **Insight**: Queue is a property of the function (it determines which worker pool handles it), not of the task instance or the task group definition. Having it in `TASK_METADATA` alongside the function's other metadata (category, parameters, examples) keeps routing and documentation in one place. The consistency test prevents drift between the metadata and the dispatcherd channel configuration.

### Task review Claude Code skill added for consistency checking
- **Commits**: 4892777 (#187)
- **What happened**: A `/task-review` Claude Code skill was added at `.claude/commands/task-review.md` that cross-references `TASK_FUNCTIONS`, `TASK_METADATA`, `task_groups.py`, `dispatcherd.yaml`, and collector registries to find consistency issues: missing metadata entries, unknown parameters in examples, duplicate cron times, orphaned rollup processors, missing required fields, and invalid queue values.
- **Insight**: As the task system grew (10+ task functions, 4 task groups, 3 collector registries, TASK_METADATA with parameters/examples), keeping all these in sync became a maintenance burden. An automated consistency checker catches drift that code review alone misses. The skill is used on-demand rather than in CI because it requires reading and correlating multiple files.

### METRICS_COLLECTION feature flag added to gate local collection independently
- **Commits**: 68a2039 (#191)
- **What happened**: A new `METRICS_COLLECTION` feature flag (default: true) was added to `FEATURE_ENABLED` in `defaults.py` and `DEFAULT_SETTINGS` in `utils.py`. The `METRICS_COLLECTION_GROUP` (hourly/daily collectors, rollup, cleanup_metrics_data) was changed from `feature_flag=None` (always enabled) to `feature_flag="METRICS_COLLECTION"`. This means operators can now pause local metrics collection independently of anonymization. The `ANONYMIZATION_GROUP` remains gated by `ANONYMIZED_DATA_COLLECTION`. Updated `init-system-tasks` comment to note that both metrics and anonymize tasks store `_feature_flag` in task_data for runtime checking.
- **Insight**: This completes the feature flag evolution. The flags now form a two-tier system: `METRICS_COLLECTION` controls local data gathering (hourly collectors, rollup, cleanup), while `ANONYMIZED_DATA_COLLECTION` controls anonymization and upstream transmission. Both default to true. Operators can independently disable either tier. The earlier decision (#92) to make collection always-on was reversed because some operators need to pause collection entirely (not just anonymization) for maintenance or performance reasons.

### Scheduler gates task pickup on feature flag before adding to scheduler
- **Commits**: babf061 (#199)
- **What happened**: The `_periodic_database_sync` (30s loop) and `_sync_database_tasks` (startup sync) were picking up all pending tasks regardless of feature flag state, then checking the flag in `_execute_database_task` and logging a skip. For immediate tasks with `cron: None`, this created an infinite loop: pick up -> skip -> remove from tracking -> next cycle picks up again (DB row stays pending). The fix added a `_task_feature_flag_enabled(task)` helper that reads `task.task_data["_feature_flag"]` and checks via `get_feature_enabled_from_db()`. Both sync methods now call this before adding any task to the scheduler. The skip log in `_execute_database_task` was downgraded from INFO to DEBUG.
- **Insight**: Feature flag checks should happen at the point of task discovery (the scheduler sync), not at the point of execution. This prevents disabled tasks from churning through the scheduler loop and producing noisy logs. When the flag is re-enabled, the next sync cycle automatically picks up the task -- no manual intervention needed.

### Feature flag precedence expanded to five tiers with installer settings.yaml override
- **Commits**: babf061 (#199)
- **What happened**: The `get_feature_enabled_from_db()` lookup order was expanded from four to five tiers: (1) `Setting` row, (2) `settings.FEATURE_ENABLED[name]` dict, (3) **new**: `settings.FEATURE_<name>_ENABLED` top-level attribute (set by installer via `settings.yaml`), (4) AAPFlag, (5) default. The new tier 3 was added because the installer writes `FEATURE_DASHBOARD_COLLECTION_ENABLED: True` directly into `settings.yaml`, which Dynaconf surfaces as a top-level settings attribute. Without this tier, the installer's intent was ignored because the key wasn't in the `FEATURE_ENABLED` dict.
- **Insight**: When multiple configuration sources exist (Django settings dict, top-level settings attributes, DAB flags), each source needs its own tier in the precedence chain. The installer convention of setting `FEATURE_<name>_ENABLED` as a top-level attribute (not inside `FEATURE_ENABLED` dict) required explicit handling.

### sync_flag_values_from_settings propagates installer overrides to Gateway UI
- **Commits**: babf061 (#199)
- **What happened**: A new `sync_flag_values_from_settings()` function was added to `apps/tasks/apps.py`. It reads each flag from `feature_flags.yaml`, checks for a matching top-level settings attribute (`settings.FEATURE_<name>_ENABLED`), and updates the AAPFlag DB row if the values differ. Called from `init-default-settings` (which runs during container startup). Saves without `no_reverse_sync()` so the change propagates to the Gateway resource server.
- **Insight**: The Gateway UI reads feature flag state from AAPFlag rows. If the installer sets `FEATURE_DASHBOARD_COLLECTION_ENABLED: True` in `settings.yaml` but the AAPFlag row still says `False` (from the YAML seed), the Gateway shows the wrong state. This sync function bridges the gap. It only runs during `init-default-settings` (not `AppConfig.ready()`) to avoid writing to the DB on every Django invocation.

### Stuck task detection moved into scheduler's periodic sync
- **Repo**: ansible/metrics-service
- **Commits**: e7558f7 (#211)
- **What happened**: Stuck task detection was added to `_periodic_database_sync` in `cron_scheduler.py`. On each 30-second tick, any task in "running" status whose `started_at` is older than `STUCK_TASK_TIMEOUT_SECONDS` (hardcoded to 3600) is atomically marked failed along with its `TaskExecution` record, using `transaction.atomic()`. Both `Task` and `TaskExecution` are updated with `status="failed"`, an error message, and `completed_at=now`. Tests cover: task beyond timeout (marked failed), task within timeout (left alone), task with no `started_at` (ignored), and associated execution record updates.
- **Insight**: Piggy-backing stuck task detection on the existing scheduler tick (which already queries the DB every 30s) avoids adding a separate monitoring job. The detection is simple and robust: any running task older than the timeout is assumed to have a dead worker. The `transaction.atomic()` ensures Task and TaskExecution stay in sync.

### Exponential backoff for task retries (extended retry window)
- **Repo**: ansible/metrics-service
- **Commits**: 9fcd1d2 (#220)
- **What happened**: Task retry was changed from a fixed 10-minute delay with 3 max attempts (~30 min window) to exponential backoff with 7 max attempts (~10.5 hour window). A `compute_retry_delay(base_delay, attempts)` function computes `min(base * 2^(attempts-1), 8h)`. The backoff is applied via `_schedule_retry()` which validates `retry_delay_seconds` from `task_data` (with fallback to `RETRY_BASE_DELAY_SECONDS = 600`). A `SEGMENT_MAX_ATTEMPTS = 7` constant is defined in `task_groups.py` and applied to both the `daily_anonymize_and_prepare` cron task and the dynamically created `send_anonymized_to_segment` one-time tasks. The retry logic was also extracted from inline code in `execute_claimed()` into a dedicated `_schedule_retry()` function with double `can_retry()` check (before and after `refresh_from_db()`). Several `logger.error(f"...")` calls were upgraded to `logger.exception(...)` for better traceback capture.
- **Insight**: Fixed-interval retries are insufficient for tasks that depend on external services with multi-hour outages (like Segment API downtime). Exponential backoff with a cap (8h) spreads retries out enough to survive sustained outages while still retrying frequently early on. The 7-attempt / 10.5-hour window was chosen specifically for the Segment send use case. Extracting retry logic into `_schedule_retry()` also makes it testable independently of the full execution flow.

### Task timeout consolidated into single TASK_TIMEOUT Dynaconf setting
- **Repo**: ansible/metrics-service
- **Commits**: 0b00a81 (#218), c680e42 (#228)
- **What happened**: The per-task `timeout_seconds` DB field was removed (migration 0004), the hardcoded `STUCK_TASK_TIMEOUT_SECONDS = 3600` constant was eliminated, and the `--timeout` CLI flags on `run` and `run_dispatcherd` were made no-ops (kept for compatibility). All timeout logic now uses `settings.TASK_TIMEOUT` (default 3600, overridable via `METRICS_SERVICE_TASK_TIMEOUT` env var). Both stuck task detection in `cron_scheduler.py` and dispatcherd's `default_timeout` in `dispatcherd_config.py` now read from this single setting. In #228, a module-level `STUCK_TASK_TIMEOUT_SECONDS = django_settings.TASK_TIMEOUT` constant was re-introduced for readability in the scheduler code.
- **Insight**: Consolidating timeout into a single Dynaconf setting eliminates the three-way inconsistency that was possible (DB field vs hardcoded constant vs CLI arg). The `--timeout` flag stays for backward compatibility but does nothing, avoiding breaking existing deployment scripts. The env var override (`METRICS_SERVICE_TASK_TIMEOUT`) follows the existing Dynaconf naming convention for production overrides.

### Dashboard collection merged from standalone task into hourly collector hook
- **Repo**: ansible/metrics-service
- **Commits**: bd760f5 (#210)
- **What happened**: The standalone `daily_dashboard_collection` cron task (6-hourly) was replaced by a `post_collect_hook` on the `unified_jobs` hourly collector. The collector registry gained a `post_collect_hook_factory` field. When `DASHBOARD_COLLECTION` is enabled, `_build_dashboard_sync_hook` is wired as the hook factory for the `unified_jobs` entry. The hook creates `sync_dashboard_job_records` one-time tasks (chunked at 500 records) via `update_or_create`. The `collection_status` endpoint was updated to query `hourly_unified_jobs` (the parent task) instead of the removed dashboard data task. The `collect_dashboard_reports_data` function is deprecated but retained for initial backfill only. The `TASK_LOCKS` dict was updated: `collect_dashboard_reports_data` removed, `sync_dashboard_job_records` added.
- **Insight**: Merging dashboard collection into the existing hourly pipeline eliminates a separate cron schedule and DB connection, keeping total Controller DB calls per hour at 2. The hook pattern extends the collector framework without modifying the core `generic_collect_metrics` flow. Tasks should be created via `update_or_create` (not `get_or_create`) to handle concurrent hourly runs for the same hour.

## Superseded / Semi-Obsolete

### daily_dashboard_collection cron task
- **Repo**: ansible/metrics-service
- Removed in bd760f5 (#210). Dashboard collection is now routed through the hourly `unified_jobs` collector via a `post_collect_hook`. The standalone 6-hourly task no longer exists.

### Placeholder tasks (send_notification_email, process_user_data)
- These were removed in c6947ce (#14) when the task system was extracted to `apps/tasks/`.

### Django signals for automatic task routing
- Signals added in edb4626 (#25) and removed in 85d2cbb (#57). The `post_save` signal on the Task model auto-routed tasks to dispatcherd, but this broke when APScheduler was moved to a separate process (signals don't work cross-process). The `_skip_signals` workaround pattern was also removed.

### CronTaskScheduler class name
- Renamed to `UnifiedTaskScheduler` in 7b39f53 (#56). The old class name is kept as an alias (`CronTaskScheduler = UnifiedTaskScheduler`) for backward compatibility.

### simple_scheduler.py module
- Removed in 7b39f53 (#56) when the unified scheduler replaced both the simple scheduler and the cron scheduler.

### TaskScheduler polling class
- The polling-based `TaskScheduler` was later replaced by APScheduler-based cron scheduling (`apps/tasks/cron_scheduler.py`), though APScheduler itself was temporarily rolled back to polling in edb4626 (#25). The current approach uses APScheduler.

### Raw connection string parameter for collector tasks
- The `db` parameter (raw connection string) was replaced in 0854775 (#40) with `database` (Django database alias). Collectors now use `connections[db_name]` instead of raw strings.

### Individual collector task functions (collect_anonymous_metrics, etc.)
- Replaced in 3a58426 (#79) by a unified `collect_single_collector` function and hourly-specific tasks (`collect_job_host_summary_hourly`, etc.). The older `test_segment_track` and `debug_segment_messages` debug functions were also removed. Then further consolidated in e137d39 (#92) and 1580ff2 (#109) into generic `collect_hourly_metrics` and `collect_snapshot_metrics` functions with a registry-based design.

### Legacy models: TaskDependency, TaskChain, TaskChainMembership, is_recurring, priority
- All removed in e137d39 (#92). TaskDependency and TaskChain were unused and incomplete. `is_recurring` was replaced by checking `cron_expression` non-empty. `priority` field was never used.

### Service layer classes (CronManager, ServiceConfig, SystemInitializer, TaskManager)
- Removed in e137d39 (#92). These service classes were added in edb4626 (#25) to decompose the management command but became dead code after subsequent refactors.

### METRICS_COLLECTION_ENABLED feature flag
- Removed in e137d39 (#92). Later, a new `METRICS_COLLECTION` flag (note: different name, no `_ENABLED` suffix) was added in 68a2039 (#191) to gate local collection independently. See the "METRICS_COLLECTION_GROUP always enabled (no feature flag)" superseded entry above.

### AppConfig.ready() for feature flag initialization
- Removed in e137d39 (#92). `DynamicSettingsConfig.ready()` was writing to the DB on every Django invocation, which is wrong. Replaced by explicit `init-default-settings` management command.

### metrics_service cron subcommand
- Removed in e137d39 (#92). Was no longer used; scheduling is handled by `run_task_scheduler` and `metrics_service run`.

### tasks_collector.py monolithic file
- The 1453-line `apps/tasks/tasks_collector.py` was deleted in e137d39 (#92), replaced by the subdirectory structure (`collectors/`, `cleanup/`, `simple/`).

### String-based task submission in UnifiedTaskScheduler
- `submit_task(f"apps.tasks.tasks.{function_name}", ...)` was changed to `submit_task(TASK_FUNCTIONS[function_name], ...)` in 3de90fc (#153). Then the entire direct-submit approach was replaced in 520fd11 (#155) by routing through `_execute_database_task()`.

### Feature flag checked from APScheduler args at execution time
- Feature flags were originally passed as `_feature_flag` in the APScheduler job args and checked in `_execute_scheduled_task`. In 520fd11 (#155), this was changed to re-read `_feature_flag` from the DB task's `task_data`, making changes take effect without scheduler restart. Then in ccf9494 (#167), the entire APScheduler registration path was removed -- all tasks now go through `_periodic_database_sync`, eliminating this concern entirely.

### Dual APScheduler registration path (_load_task_registry + _periodic_database_sync)
- The scheduler had two parallel paths: APScheduler cron jobs for system tasks and periodic DB polling for ad-hoc tasks. Removed in ccf9494 (#167); all tasks now go through a single `_periodic_database_sync -> _execute_database_task` path.

### task_execution_wrapper and @task decorators on task functions
- Removed in ccf9494 (#167). `execute_db_task` already handles Django setup, logging, and error handling, making these decorators redundant on all 9 task functions.

### Per-task timeout_seconds DB field
- The `timeout_seconds` field on the Task model was removed in 0b00a81 (#218). Timeout is now controlled exclusively by the `TASK_TIMEOUT` Dynaconf setting (overridable via `METRICS_SERVICE_TASK_TIMEOUT` env var). The `--timeout` CLI flag on `run` and `run_dispatcherd` commands is kept for compatibility but has no effect.

### Hardcoded STUCK_TASK_TIMEOUT_SECONDS = 3600 constant
- The hardcoded constant from e7558f7 (#211) was replaced in 0b00a81 (#218) by `django_settings.TASK_TIMEOUT`. In c680e42 (#228), a module-level `STUCK_TASK_TIMEOUT_SECONDS = django_settings.TASK_TIMEOUT` alias was added for readability.

### Fixed 10-minute retry delay with 3 max attempts
- Replaced in 9fcd1d2 (#220) by exponential backoff (`compute_retry_delay()`) with `SEGMENT_MAX_ATTEMPTS = 7`, extending the retry window from ~30 minutes to ~10.5 hours for Segment tasks.

### send_to_segment_daily as a fixed cron task
- The daily cron entry (`30 3 * * *`) was removed in 8d4ae7e (#183). Segment sending is now triggered as a one-time task with jittered timing, created inside the anonymization transaction. This prevents thundering herd across installations.

### METRICS_COLLECTION_GROUP always enabled (no feature flag)
- The decision in e137d39 (#92) to make metrics collection always-on (no feature flag) was reversed in 68a2039 (#191). A new `METRICS_COLLECTION` feature flag (default: true) now gates the collection group, allowing operators to pause local collection for maintenance or performance reasons. The `ANONYMIZED_DATA_COLLECTION` flag still independently controls the anonymization/transmission pipeline.

### collect_single_collector function and individual hourly task files
- Replaced in 1580ff2 (#109) by `collect_hourly_metrics` and `collect_snapshot_metrics` with a registry-based design. Individual files (collect_job_host_summary_hourly.py, etc.) were deleted.

### main_host and main_jobevent collectors
- `main_host` removed in 1580ff2 (#109) because it's not in the anonymized chain. `main_jobevent` disabled (too slow for production) but kept in registry for testing.

### Thread-based service management with ProcessManager
- The `ProcessManager` class and thread-based service orchestration were removed in 0c14d9c (#85). The `metrics_service run` command now spawns three OS processes directly with selectors-based I/O multiplexing.
