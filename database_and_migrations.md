# Database and Migrations

> Default repo: metrics-service

## Learnings
### System auditor field added via dedicated migration
- **Commits**: fd6745d (#10)
- **What happened**: Migration `0004_add_is_system_auditor.py` added a `is_system_auditor` BooleanField (default False) to the User model. A separate migration `0005_user_organization.py` added a ForeignKey from User to Organization. These were kept as separate migrations rather than squashed.
- **Insight**: Keeping schema changes as small, focused migrations (one field per migration) is the Django convention. It makes rollbacks safer and debugging easier. The `is_system_auditor` field is a simple boolean rather than using Django's groups/permissions system, which is pragmatic for a service with just two special roles (superuser and auditor).

### Migration history was rewritten to clean up task model evolution
- **Commits**: c6947ce (#14)
- **What happened**: The task model went through several iterations (adding fields, then removing them) during the core-to-tasks extraction. Migration 0006 (which removed fields from the Task model) was deleted, and migration 0004's dependency was updated to reference the initial migration instead of a later one. The Task model was recreated as a fresh `0001_initial.py` in `apps/tasks/migrations/`.
- **Insight**: Rewriting migration history during development is acceptable before a service is in production, but it means anyone who ran the old migrations needs to reset their database. The team chose a clean migration chain over preserving upgrade path from the early experimental state.

### is_system_task flag added to Task model
- **Commits**: edb4626 (#25)
- **What happened**: Migration `0002_add_system_task_flag.py` added `is_system_task` BooleanField (default False) to the Task model, and `0003_add_task_description.py` added a `description` TextField. These support the task groups system where system-defined tasks are distinguished from user-created ones.
- **Insight**: The `is_system_task` flag is a lightweight alternative to a separate "system task" model. It keeps the schema simple but requires careful filtering in queries and API views to prevent users from modifying system tasks.

### Organization extra_field changed from nullable to default empty string
- **Commits**: da91648 (#29)
- **What happened**: Migration `0006_alter_team_options_alter_organization_extra_field.py` changed `Organization.extra_field` from `CharField(null=True, blank=True)` to `CharField(blank=True, default="")`. The same migration also updated Team model options.
- **Insight**: Following Django's recommendation to avoid `null=True` on string-based fields. With `null=True`, a CharField can have two "empty" states (NULL and ""), which complicates filtering and comparison. Using `default=""` ensures a single canonical empty value.

### Setting model and ConfigurationChange model added for config management
- **Commits**: f4b136e (#31), c8e5f0d (#36)
- **What happened**: Migration 0007 created a `ConfigurationChange` model with `setting_key`, `old_value`, `new_value`, `changed_at`, `source` (choices: api/management_command/reload/system), `ip_address`, and `changed_by` FK. Migration 0008 then created the `Setting` model. In c8e5f0d (#36), migration 0010 removed the `source` field from `Setting` (it was deemed unnecessary since the model already tracked changes via the audit trail).
- **Insight**: The `ConfigurationChange` model was created in the same PR as `Setting` but serves a different purpose -- `ConfigurationChange` is a full audit log while `Setting` is the current state with just one previous value. The `source` field was removed quickly, suggesting it was over-engineered for the initial use case.

### AWX database connection added to DATABASES dict
- **Commits**: 0854775 (#40)
- **What happened**: A second database entry `awx` was added to the `DATABASES` dict in `defaults.py`, configurable via `METRICS_SERVICE_DATABASES__awx__HOST` etc. This enables Django's `connections["awx"]` API for cross-database queries against the AWX/Controller database.
- **Insight**: Django's multi-database support requires explicit `DATABASES` entries. The AWX database is read-only from this service's perspective (used for metrics collection), so no migrations or ORM models are needed for it -- raw SQL via `connection.cursor()` is used by the metrics-utility collectors.

### Migration history rewritten again during retrofit prep
- **Commits**: 5fb6ead (#73)
- **What happened**: Core app migrations 0004-0010 were deleted and the initial migration (`0001_initial.py`) was rewritten to reflect the simplified models (thin DAB wrappers without custom fields like `is_system_auditor`, `extra_field`, or `Setting`). Tasks app migrations 0002-0004 were also deleted and folded into a rewritten `0001_initial.py`. The Setting model got a fresh `0001_initial.py` under its new home at `apps/dynamic_settings/migrations/`.
- **Insight**: This is the second migration history rewrite (first was in c6947ce #14). Since the service isn't in production yet, rewriting migrations is acceptable and produces a cleaner migration chain. However, anyone with an existing development database must recreate it from scratch. The rewrite was necessary because the model changes (removing fields, moving Setting to a new app) would have produced a confusing migration chain.

### Setting model moved to dedicated dynamic_settings app with its own migration
- **Commits**: 5fb6ead (#73)
- **What happened**: The `Setting` model was extracted from `apps/core/models.py` into a new `apps/dynamic_settings/models.py`. A fresh `0001_initial.py` migration was created under `apps/dynamic_settings/migrations/`. The model retained all its fields (`setting_key`, `current_value`, `previous_value`, `last_modified_by`) and indexes but with `app_label = "dynamic_settings"`.
- **Insight**: Moving a model between apps requires either a multi-step migration (create in new app, migrate data, remove from old app) or a full migration rewrite. Since there was no production data to preserve, the rewrite approach was simpler. The `ConfigurationChange` model (from migration 0007) was not carried over, suggesting it was deemed unnecessary.

### HourlyMetricsCollection and DailyMetricsSummary models added
- **Commits**: 3a58426 (#79)
- **What happened**: Two new models were added to `apps/tasks/models.py` for the metrics pipeline. `HourlyMetricsCollection` has a unique constraint on `(collector_type, collection_timestamp)` to prevent duplicate hourly entries, with indexes on `(collector_type, collection_timestamp)`, `collection_timestamp`, and `status`. `DailyMetricsSummary` has a unique `summary_date` field and stores `hourly_collection_ids` as a JSONField mapping collector types to lists of `HourlyMetricsCollection` IDs. Both models inherit from `CommonModel` and `AuditableModel`. The tasks app migration `0001_initial.py` was rewritten to include these models.
- **Insight**: Using JSONField for `hourly_collection_ids` instead of a M2M relationship is an intentional denormalization. It avoids an extra join table and allows the daily summary to store references even after hourly collections are cleaned up (no cascading deletes). The trade-off is that there's no database-level referential integrity between daily summaries and hourly collections.

### Tasks app migrations squashed for the third time
- **Commits**: 0fa64ff (#140)
- **What happened**: Seven migrations (0002 through 0008) were deleted and folded into a rewritten `0001_initial.py`. The squashed migration includes all models as of March 2026: `Task`, `TaskExecution`, `HourlyMetricsCollection` (with expanded `COLLECTOR_TYPE_CHOICES` including `controller_version` and `table_metadata`), `DailyMetricsSummary`, and `AnonymizedMetricsPayload`. The PR description notes that `squashmigrations` output was breaking, so they used `rm` + `makemigrations` instead.
- **Insight**: This is the third migration rewrite for the tasks app (first in #14, second in #73, third here). The `squashmigrations` command produces migrations with `RunSQL` and `RunPython` operations that can be fragile. The delete-and-regenerate approach is simpler and works because the service hasn't reached production yet. Each rewrite requires all developers to recreate their databases (`pytest --create-db`).

### close_old_connections() needed for scheduler database access
- **Commits**: 59a6366 (#158)
- **What happened**: The `UnifiedTaskScheduler` added `close_old_connections()` calls before any ORM access in its three main methods. Without this, APScheduler threads could hold stale database connections that had been closed server-side during idle periods.
- **Insight**: Django's request/response cycle handles connection cleanup automatically, but long-lived threads must call `close_old_connections()` before each ORM access batch. This is a well-known Django pattern for background workers but easy to forget.

### AnonymizedMetricsPayload gained new status choices and unique constraint
- **Commits**: 4e2a18e (#175)
- **What happened**: Two new migrations were added: one altering `AnonymizedMetricsPayload.status` to add `"unavailable"` and `"failed"` choices (distinguishing between config issues and actual send errors), and another adding a unique constraint on active payloads per daily summary to prevent duplicate payload creation.
- **Insight**: Adding status choices via migration is necessary because Django validates field choices at the model level. The `"unavailable"` status (Segment not configured) vs `"failed"` (actual send error) distinction enables the health check to differentiate between configuration issues and service failures.

### Never manually close Django's singleton database connection -- let Django manage lifecycle
- **Commits**: 258547a (#194)
- **What happened**: Multiple locations (`_collect_data`, `FilterOptionsViewSet.list()`, `FilterOptionsViewSet.retrieve()`) had `finally` blocks calling `.close()` on the raw psycopg connection obtained via `get_db_connection("awx")`. Since `get_db_connection()` returns `connections[db_name].connection` (Django's singleton), closing it invalidated the connection for all concurrent tasks in the same worker process. Django's connection wrapper still thought the connection was alive and skipped reconnection. The fix: removed all manual `.close()` calls; added `close_old_connections()` at entry points (`run_with_lock()`, `HealthView`) where no locks are held.
- **Insight**: Django's `connections[alias].connection` is a process-wide singleton. The only safe way to clean up stale connections is `close_old_connections()`, and only at boundaries where no connections are actively holding locks or cursors. The `get_db_connection()` docstring now explicitly warns: "DO NOT CLOSE the returned connection."

## Superseded / Semi-Obsolete

### Core app migrations 0004-0010
- These migrations (adding `is_system_auditor`, `user_organization`, `alter_organization_extra_field`, `configurationchange`, `setting`, etc.) were deleted in 5fb6ead (#73) when the core models were simplified to thin DAB wrappers and the Setting model was moved to `apps/dynamic_settings/`.

### Tasks app migrations 0002-0004
- The `add_system_task_flag`, `add_task_description`, and `auto_20251125_1020` migrations were folded into a rewritten `0001_initial.py` in 5fb6ead (#73). Then migrations 0002-0008 were squashed again in 0fa64ff (#140) into a new `0001_initial.py`.

### SELECT 1 probe for dead connection detection before ensure_connection()
- **Repo**: ansible/metrics-service
- **Commits**: 33db88a (#273)
- See [bugs_and_pitfalls.md](bugs_and_pitfalls.md#stale-psycopg3-connections-not-detected-by-djangos-ensure_connection) for the full entry. Summary: `get_db_connection()` returned stale psycopg3 connections after server-side disconnects. A `SELECT 1` probe was added before `ensure_connection()` to detect and close dead connections. `close_old_connections()` was not viable because it closes ALL connections including ones holding advisory locks.

### Stale advisory lock cleanup via pg_terminate_backend
- **Repo**: ansible/metrics-service
- **Commits**: a6bb3ad (#277)
- **What happened**: After a network partition, PostgreSQL sessions can remain alive for hours (TCP keepalive default is 7200s), holding advisory locks that block task execution. The scheduler's `_periodic_database_sync` now runs `_cleanup_stale_advisory_locks()` every 30s. It joins `pg_locks` with `pg_stat_activity` to find sessions that are idle beyond `STUCK_TASK_TIMEOUT_SECONDS` and hold advisory locks matching known `TASK_LOCKS` names (computed via `hashtext(name)::bigint % 2**63`). Matching sessions are terminated with `pg_terminate_backend()`. The cleanup is scoped to known lock names to avoid terminating sessions from other applications.
- **Insight**: Advisory locks are tied to PostgreSQL sessions, not transactions. When a worker process dies but its session persists (due to TCP keepalive), the lock blocks all subsequent task attempts. The only way to release it is to terminate the stale session. Always scope cleanup to known lock IDs to avoid collateral damage.
