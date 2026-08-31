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

### CredentialType data migration fixed: namespace field instead of kind
- **Repo**: ansible/awx
- **Commits**: fd847862a7, 01293f1b45
- **What happened**: Migration `0204_squashed_deletions.py` had a RunPython step that incorrectly used `filter(kind='github_app').update(kind='github_app_lookup')` to rename the GitHub App credential type. The `kind` field is not unique across credential types (e.g., multiple types share `kind='cloud'`), so this could rename the wrong rows. The fix changed the filter/update to use the `namespace` field instead, which is unique. A follow-up commit also added `migrations.RunPython.noop` reverse operations to migrations 0201, 0202, and 0204 to make them reversible.
- **Insight**: When writing data migrations that update credential type rows, always filter by `namespace` (unique) rather than `kind` (non-unique). The `namespace` field on `main_credentialtype` is the stable identifier for credential type lookups.

### Workload identity credentials: `internal` flag added to CredentialType inputs JSON
- **Repo**: ansible/awx
- **Commits**: 57f9eb093a (#16286), ff68d6196d (#16348)
- **What happened**: Workload identity credential support was added, allowing credentials to resolve JWT tokens at runtime via OIDC. A new `internal` boolean attribute was added to the JSON schema for CredentialType `inputs.fields[]` entries -- fields marked `internal: true` are resolved from runtime context (not user-provided). The feature is gated by `FEATURE_OIDC_WORKLOAD_IDENTITY_ENABLED` (defaults to False). No new DB columns were added; the `internal` flag lives inside the existing `inputs` JSONField on `main_credentialtype`. A `context` cached_property was added to the `Credential` model (Python-only, not persisted).
- **Insight**: No structural schema change to `main_credentialtype`, but the `inputs` JSON content shape has expanded. If our collectors parse the `inputs` JSON field, they should tolerate the new `internal` attribute. The feature flag means OIDC credential types may or may not exist in `main_credentialtype` depending on the deployment.

### CredentialType.description now populated from plugin_description
- **Repo**: ansible/awx
- **Commits**: 7c75788b0a (#16364)
- **What happened**: The `description` column on `main_credentialtype` was previously empty for most managed credential types. The `_setup_tower_managed_defaults()` method now propagates `plugin_description` from credential plugins into `CredentialType.description`, and updates existing records if they lack a description. No schema change -- the `description` column already existed.
- **Insight**: The `description` column on `main_credentialtype` will now be populated for managed credential types. If our `credentials_service` collector exposes this field, downstream consumers will start seeing richer data.

### Plugin registry DB sync moved from app.ready() to dispatcher startup
- **Repo**: ansible/awx
- **Commits**: d5e5ea3670 (#16483)
- **What happened**: `CredentialType.setup_tower_managed_defaults()` (which syncs managed credential type rows to the database) was moved from Django's `app.ready()` (runs in every process) to the dispatcher's startup task (runs once per deployment). In-memory registries (`ManagedCredentialType.registry`, `InventorySourceOptions.injectors`) are now lazily loaded via a `LazyLoadDict` class. No schema change, but the timing of when `main_credentialtype` rows are synced from plugins to the database has changed.
- **Insight**: If our collectors run before the dispatcher has started (e.g., during initial deployment), managed credential type rows may not yet exist in `main_credentialtype`. The lazy-load pattern also means web workers no longer perform DB writes at startup, which removes a source of intermittent `RuntimeWarning` and startup contention.

### Instance health check: nodes with zero cpu/memory no longer marked READY
- **Repo**: ansible/awx
- **Commits**: f25e436bef (#16511)
- **What happened**: `Instance.save_health_check_data()` now treats `cpu=0` or `memory=0` as an error condition, preventing the node from transitioning to READY state. Previously, zero values with no errors would allow the node to become READY. No schema change -- the `cpu`, `memory`, `errors`, and `node_state` columns on `main_instance` are unchanged.
- **Insight**: Our `controller_version_service` collector filters `main_instance` by `enabled=True` and `node_type IN ('control', 'hybrid')`. Nodes with zero cpu/memory will now remain offline (not READY), which could affect the version data we collect if such nodes were previously included. No schema impact, but behavioral change in what data appears in `main_instance`.

### AWX migration 0205: AlterModelOptions for ordering on InstanceGroup and workflow nodes
- **Repo**: ansible/awx
- **Commits**: 670dfeed25 (#16298)
- **What happened**: Migration `0205_add_ordering_to_instancegroup_and_workflow_nodes.py` adds `ordering = ('pk',)` to the Meta class of `InstanceGroup`, `WorkflowJobTemplateNode`, and `WorkflowJobNode`. This is a Django `AlterModelOptions` operation that only affects default queryset ordering -- no columns, indexes, or constraints are created.
- **Insight**: `AlterModelOptions` migrations do not change the database schema at the PostgreSQL level. They only update Django's internal state. None of these three tables are in our tracked collector dependencies.

### AWX migration 0206: composite index on main_jobhostsummary (host_id, id DESC)
- **Repo**: ansible/awx
- **Commits**: 41545cfcf0 (#16530)
- **What happened**: Migration `0206_jobhostsummary_host_id_idx.py` adds a composite index named `main_jobhostsumm_host_id_desc` on `main_jobhostsummary(host_id, id DESC)`. This supports the `with_latest_summary_id()` correlated subquery (introduced when `last_job_host_summary_id` was deprecated in d1b3ae53ae #16332) that finds the latest JobHostSummary per host via `WHERE host_id=X ORDER BY id DESC LIMIT 1`. Without this index, PostgreSQL had to scan and sort rows; with it, the query uses an index-only top-1 scan. The same commit also makes `.distinct()` conditional in the HostList API -- it is now only applied when `host_filter` is set, since without it the RBAC subquery on a direct FK cannot produce duplicates.
- **Insight**: This index directly affects `main_jobhostsummary`, one of our dependent tables. The index is read-only infrastructure (no column changes), but it signals that AWX is committed to the `with_latest_summary_id()` query pattern as the replacement for the deprecated `main_host.last_job_host_summary_id` FK. Our collectors that join to `main_jobhostsummary` should align with this pattern rather than relying on the stale FK column.

### AWX migration 0207: skip_tags converted from CharField(1024) to TextField on Job and JobTemplate
- **Repo**: ansible/awx
- **Commits**: 9acf3d1887 (#16552)
- **What happened**: Migration `0207_alter_skip_tags_to_textfield.py` changes the `skip_tags` column from `CharField(max_length=1024)` to `TextField(blank=True, default='')` on both `main_job` and `main_jobtemplate`. The `max_length` constraint is removed entirely. This was a bug fix -- `job_tags` was already a TextField while `skip_tags` was artificially limited to 1024 characters, causing silent truncation for users with many tags.
- **Insight**: Both `main_job` and `main_jobtemplate` are in our dependent tables list. At the PostgreSQL level, `CharField` and `TextField` are both stored as `text` -- the only difference is the `CHECK (char_length(skip_tags) <= 1024)` constraint, which this migration drops. No data migration is needed. If our collectors SELECT `skip_tags`, values may now exceed 1024 characters.

### RBAC role definitions updated via post-migrate signal (no numbered migration)  [SUPERSEDED — reverted by #16597]
- **Repo**: ansible/awx
- **Commits**: 64dc097914 (#16545); reverted by 85891b8d30 (#16597)
- **What happened**: The `member_organization` permission was added to six specialized Organization *Admin role definitions (Project, Credential, Inventory, NotificationTemplate, WorkflowJobTemplate, ExecutionEnvironment). Instead of a numbered migration, the fix modifies the `_dab_rbac.py` migration helper and connects `setup_managed_role_definitions` to the `dab_post_migrate` signal in `apps.py`, so existing installs get the fix applied automatically on upgrade. A new setting `ANSIBLE_BASE_ALLOW_TEAM_ORG_MEMBER = True` was also added. No schema changes -- this only affects data in DAB RBAC permission/role definition tables, none of which are in our dependent tables.
- **Insight**: AWX is shifting toward post-migrate signal handlers for RBAC definition sync rather than numbered migrations. This pattern means role definition changes won't appear as numbered migrations in the migration chain, but will be applied on every startup. Our collectors are unaffected since we don't read from DAB RBAC tables.

### AWX migration 0206 made idempotent: AddIndex wrapped in SeparateDatabaseAndState + CREATE INDEX IF NOT EXISTS
- **Repo**: ansible/awx
- **Commits**: d759ff160e (#16585)
- **What happened**: Migration `0206_jobhostsummary_host_id_idx.py` (originally added in 41545cfcf0 #16530) used a plain `migrations.AddIndex` for the `main_jobhostsumm_host_id_desc` composite index on `main_jobhostsummary(host_id, id DESC)`. That fails during upgrade if the index already exists -- customers on 2.6 may have created it manually via `awx-manage create_host_summary_index` (AAP-87549) or a KCS raw-SQL workaround, so the upgrade errored with `relation "main_jobhostsumm_host_id_desc" already exists`. The fix wraps the operation in `migrations.SeparateDatabaseAndState`: the `database_operations` run `RunSQL("CREATE INDEX IF NOT EXISTS ... ON main_jobhostsummary (host_id, id DESC)")` (with `DROP INDEX IF EXISTS` reverse), while `state_operations` keep the original `AddIndex` so Django's model state stays consistent. Forward-port of tower#7895 (stable-2.7).
- **Insight**: This affects `main_jobhostsummary`, one of our dependent tables, but only the migration mechanics -- no column, type, or constraint change; the index name and shape are identical to #16530. The pattern to remember: when a schema object may already exist on some upgrade paths, wrap the migration in `SeparateDatabaseAndState` with idempotent raw SQL (`IF NOT EXISTS`) in `database_operations` and the ORM operation in `state_operations` so Django's migration state stays accurate without re-issuing the failing DDL.

### AWX RBAC cleanup no longer deletes JWT-managed role definitions (no schema change)
- **Repo**: ansible/awx
- **Commits**: 693a5820ae (#16590)
- **What happened**: `setup_managed_role_definitions()` in `awx/main/migrations/_dab_rbac.py` deletes "unexpected" managed `RoleDefinition` rows (those not created by the current setup run). It was also deleting JWT-managed roles such as Platform Auditor, which CASCADE-deleted their user/team assignments. The fix adds `.exclude(name__in=settings.ANSIBLE_BASE_JWT_MANAGED_ROLES)` so JWT-managed roles are preserved during cleanup.
- **Insight**: Not schema-relevant to our collectors -- this only touches DAB RBAC role-definition/assignment tables, none of which are in our dependent tables list. Noted for completeness only.

### AWX migration 0208: data-only fix for system_auditor -> Platform Auditor assignments
- **Repo**: ansible/awx
- **Commits**: d6675e67e0 (#16582)
- **What happened**: Migration `0208_fix_system_auditor_migration.py` is a `RunPython` (reverse = `noop`) data migration that corrects a bug in the earlier `0192` (`migrate_to_new_rbac`) where a stale loop variable (`role.members` instead of `old_system_auditor.members`) meant some old `system_auditor` members never received the new `Platform Auditor` role. The migration reads legacy `Role` members (`singleton_name='system_auditor'`) and creates any missing `RoleUserAssignment` rows for the `Platform Auditor` `RoleDefinition`. It only *adds* missing assignments, never removes. The same commit also fixes the loop-variable bug in `_dab_rbac.py::migrate_to_new_rbac`. No DDL -- no columns, tables, indexes, or constraints created.
- **Insight**: Pure data migration touching DAB RBAC tables (`RoleUserAssignment`, `RoleDefinition`) and the legacy `main` `Role` model -- none of which are in our dependent tables list. No schema impact on our collectors. Pattern worth noting: corrective data migrations use `RunPython.noop` as the reverse and are written to be additive-only when they can't safely distinguish bug-caused from legitimate rows.

### AWX #16597: revert of member_organization RBAC role-definition change and post-migrate reverse-sync skip
- **Repo**: ansible/awx
- **Commits**: 85891b8d30 (#16597)
- **What happened**: Reverts two prior commits -- 64dc097914 (#16545, which added `member_organization` to six Organization *Admin role definitions via a `dab_post_migrate` signal handler and added the `ANSIBLE_BASE_ALLOW_TEAM_ORG_MEMBER` setting) and 78a55b25ec (#16561, "skip reverse sync during post-migrate role definition setup", which only touched `apps.py`). The revert removes the signal wiring in `apps.py`, the `_dab_rbac.py` changes, the `ANSIBLE_BASE_ALLOW_TEAM_ORG_MEMBER` setting in `defaults.py`, and related tests. No migration files involved -- neither the original changes nor the revert alter DB schema.
- **Insight**: No schema impact -- all changes are in RBAC role-definition data (DAB tables) and settings, none in our dependent tables. The 64dc097914 learning below is now superseded by this revert. RBAC definition sync via post-migrate signals continues to be an area of churn in AWX; watch for it to be re-applied later.

### AWX #16584: DAB RBAC role-assignment events recorded in activity stream (no schema change)
- **Repo**: ansible/awx
- **Commits**: efed57ce8a (#16584)
- **What happened**: Adds activity-stream recording for new-side DAB RBAC role assignment/unassignment events (`record_role_assignment_activity_stream`), and wraps the legacy-mirroring writes in `rbac.py` / `models/__init__.py` (`sync_members_to_new_rbac`, `sync_parents_to_new_rbac`, `give_creator_permissions`, `user_is_system_auditor` setter) with `disable_activity_stream()` so mirrored writes aren't double-recorded. Changes are confined to `signals.py`, `models/rbac.py`, and `models/__init__.py` -- no migration files, no model field/table changes.
- **Insight**: Python/signal-only behavior change with no DDL. It writes more rows into `main_activitystream` (RBAC assignment events), but `main_activitystream` is not in our dependent tables list, so none of our collectors are affected.

### AWX schema dump refresh adds DAB RBAC global-assignment unique indexes
- **Repo**: ansible/metrics-utility
- **Commits**: 77f8f05 (#535)
- **What happened**: The `tools/docker/latest.sql` test-fixture schema dump was refreshed to AWX `devel` (3ab18fd) by the weekly extraction workflow. The only delta was two new partial unique indexes on DAB RBAC tables: `unique_global_team_assignment` on `dab_rbac_roleteamassignment (team_id, role_definition_id) WHERE object_role_id IS NULL` and `unique_global_user_assignment` on `dab_rbac_roleuserassignment (user_id, role_definition_id) WHERE object_role_id IS NULL`. Neither table is read by any metrics-utility collector, so the change is inert for us (PR noted it as "irrelevant, just updating the schema").
- **Insight**: Automated schema-dump refreshes surface upstream AWX/DAB DDL changes as reviewable diffs; most (like these DAB RBAC global-assignment unique indexes) touch tables no collector reads and are safe no-ops, but the diff is the checkpoint where you confirm that.

### AWX #16616: unify activity-stream format for old/new role-assignment APIs (no schema change)
- **Repo**: ansible/awx
- **Commits**: 882d2df (#16616)
- **What happened**: Follow-up to AAP-82996. The old role API (`/api/v2/users/<pk>/roles/`) fired legacy-format activity-stream entries via the `Role.members` `m2m_changed` signal, while the new API (`/api/v2/role_user_assignments/`) fired new-format entries. This change skips `activity_stream_associate` for `Role_members` changes and lets the mirrored `RoleUserAssignment` creation fire the new-format `record_role_assignment_activity_stream` handler instead. Changes are confined to `models/rbac.py` and `signals.py` -- no migration files, no model field/table changes.
- **Insight**: Python/signal-only change with no DDL. It normalizes the *content* of rows written to `main_activitystream`, but that table is not in our dependent tables list, so none of our collectors are affected.

### AWX #16118: move to new DAB RBAC queryset patterns (no schema change)
- **Repo**: ansible/awx
- **Commits**: 7765376 (#16118)
- **What happened**: Removes the `ResourceMixin` class and migrates all callers from the old RBAC queryset API (`accessible_objects`/`accessible_pk_qs`) to the DAB RBAC API (`access_qs`/`access_ids_qs`), using permission strings (`view`, `change`, `use`) instead of role field names. Also restores a UNION (instead of OR) in `TeamAccess.filtered_queryset` to avoid a 48x slowdown at scale (AAP-83319). Touches `access.py`, serializers, views, `utils/common.py`, and `mixins.py` (drops `ResourceMixin`) plus several model files -- but only to remove the mixin base class; no `models.` field definitions, `class Meta` index/constraint changes, or migration files.
- **Insight**: Pure query-layer/access-control refactor with no DDL. None of our dependent tables gain or lose columns/indexes. Query-shape changes here are internal to AWX's RBAC filtering and do not affect the raw tables our collectors read.

### AWX migration graph re-parented for 2.6 backport: 0206 re-parented, 0207_merge added, 0207/0208 renumbered to 0208/0209
- **Repo**: ansible/awx
- **Commits**: d1fdad7 (#16612)
- **What happened**: Migration-graph plumbing only (no DDL, no operations). To let `0206_jobhostsummary_host_id_idx` be backported to stable-2.6 (where `0204`/`0205` do not exist), it was re-parented from `0205_add_ordering_to_instancegroup_and_workflow_nodes` to `0203_remove_team_of_teams`. A new empty merge migration `0207_merge_0205_0206.py` (`operations = []`, depends on both `0205` and `0206`) converges the now-forked graph. The two following migrations were renumbered to sit after the merge point: `0207_alter_skip_tags_to_textfield` → `0208_alter_skip_tags_to_textfield`, and `0208_fix_system_auditor_migration` → `0209_fix_system_auditor_migration`. Final graph: `0205` and `0206` (both children of `0203`/`0204`) → `0207_merge` → `0208_skip_tags` → `0209_sys_auditor`. This mirrors the gateway backport pattern (AAP-80663) and keeps devel identical to stable-2.7 through the merge point. Only dependency strings and filenames changed; the migrations' actual operations are untouched.
- **Insight**: The migration numbers referenced in two earlier learnings shifted: "AWX migration 0207: skip_tags → TextField" (#16552) is now **0208**, and "AWX migration 0208: system_auditor fix" (#16582) is now **0209**. No schema effect on any table -- re-parenting/merge migrations are graph bookkeeping. Pattern to remember: to make a schema migration backportable to a branch that lacks intervening migrations, re-parent it to an older common ancestor and add an empty `operations = []` merge migration depending on both forks to reconverge the linear history.

### AWX migration 0210: drop dead Host.last_job and last_job_host_summary FK columns from main_host
- **Repo**: ansible/awx
- **Commits**: 3d1ca5a (#16529)
- **What happened**: Completes the deprecation started in #16332. Migration `0210_remove_host_last_job_fields.py` (`RemoveField` for `last_job` and `last_job_host_summary`) **drops** the `last_job_id` and `last_job_host_summary_id` FK columns from `main_host`. The FK definitions are removed from the `Host` model (`inventory.py`); `HostSerializer` now exposes `last_job`/`last_job_host_summary` as `SerializerMethodField`s backed by `Host.latest_summary` (i.e. derived from `main_jobhostsummary`) rather than the FK columns. Also removed: the now-unused `JobHostSummary.latest_for_host`/`latest_job_for_host` classmethods (callers switched to `host.latest_summary`), the stale-FK signal comments, and -- critically -- the `UPDATE main_host SET last_job_host_summary_id = NULL ...` step in `cleanup_jobs._pre_delete_job_host_summaries`, which would otherwise crash referencing the now-dropped column. Depends on `0209_fix_system_auditor_migration`.
- **Insight**: **Directly affects `main_host`, one of our dependent tables** -- the `last_job_id` and `last_job_host_summary_id` columns no longer exist. Any collector still SELECTing `main_host.last_job_id` (e.g. for a `last_automation` date) will break and must instead derive the latest job from `main_jobhostsummary` (join `host_id`, take max `id`/latest, read `job_id`). This is the drop the earlier #16332 deprecation warned would come; the grace period is over. Verify our `main_host` collector before consuming AWX 2.7/devel schemas.

## Superseded / Semi-Obsolete

### `last_job_host_summary_id` and `last_job_id` on main_host deprecated -- no longer written to  [SUPERSEDED — columns dropped by #16529]
- **Repo**: ansible/awx
- **Commits**: d1b3ae53ae (#16332); columns removed by 3d1ca5a (#16529, migration 0210)
- **What happened**: The `playbook_on_stats` wrapup path previously bulk-updated `last_job_id` and `last_job_host_summary_id` on every host touched by a job. In scale lab testing this query had a median execution time of 75 seconds due to index churn on `main_host` (90:1 dead-to-live tuple ratio). #16332 removed all writes to these FK columns and switched reads to `JobHostSummary.latest_for_host(host_id)` / `host.latest_summary`, leaving the columns in place as stale/dead weight. **They have now been dropped** by migration 0210 (#16529) -- see "AWX migration 0210: drop dead Host.last_job ... FK columns" in the active section above.
- **Insight**: Superseded by the actual column drop in #16529. The takeaway stands: denormalized FK columns written on every job completion become bottlenecks at scale, and once AWX deprecates such a column it will eventually drop it -- collectors must migrate to the replacement query pattern (`main_jobhostsummary` latest-per-host) before the drop lands.

### Core app migrations 0004-0010
- These migrations (adding `is_system_auditor`, `user_organization`, `alter_organization_extra_field`, `configurationchange`, `setting`, etc.) were deleted in 5fb6ead (#73) when the core models were simplified to thin DAB wrappers and the Setting model was moved to `apps/dynamic_settings/`.

### Tasks app migrations 0002-0004
- The `add_system_task_flag`, `add_task_description`, and `auto_20251125_1020` migrations were folded into a rewritten `0001_initial.py` in 5fb6ead (#73). Then migrations 0002-0008 were squashed again in 0fa64ff (#140) into a new `0001_initial.py`.

### AWX member_organization RBAC role-definition change (64dc097914 / #16545)
- **Repo**: ansible/awx
- Reverted by 85891b8d30 (#16597). The post-migrate-signal approach for adding `member_organization` to Organization *Admin role definitions (and the `ANSIBLE_BASE_ALLOW_TEAM_ORG_MEMBER` setting) was backed out. Full entry retained above under "RBAC role definitions updated via post-migrate signal" with the SUPERSEDED marker. No schema impact either way -- DAB RBAC tables only, none in our dependent tables.

### SELECT 1 probe for dead connection detection before ensure_connection()
- **Repo**: ansible/metrics-service
- **Commits**: 33db88a (#273)
- See [bugs_and_pitfalls.md](bugs_and_pitfalls.md#stale-psycopg3-connections-not-detected-by-djangos-ensure_connection) for the full entry. Summary: `get_db_connection()` returned stale psycopg3 connections after server-side disconnects. A `SELECT 1` probe was added before `ensure_connection()` to detect and close dead connections. `close_old_connections()` was not viable because it closes ALL connections including ones holding advisory locks.

### Stale advisory lock cleanup via pg_terminate_backend
- **Repo**: ansible/metrics-service
- **Commits**: a6bb3ad (#277)
- **What happened**: After a network partition, PostgreSQL sessions can remain alive for hours (TCP keepalive default is 7200s), holding advisory locks that block task execution. The scheduler's `_periodic_database_sync` now runs `_cleanup_stale_advisory_locks()` every 30s. It joins `pg_locks` with `pg_stat_activity` to find sessions that are idle beyond `STUCK_TASK_TIMEOUT_SECONDS` and hold advisory locks matching known `TASK_LOCKS` names (computed via `hashtext(name)::bigint % 2**63`). Matching sessions are terminated with `pg_terminate_backend()`. The cleanup is scoped to known lock names to avoid terminating sessions from other applications.
- **Insight**: Advisory locks are tied to PostgreSQL sessions, not transactions. When a worker process dies but its session persists (due to TCP keepalive), the lock blocks all subsequent task attempts. The only way to release it is to terminate the stale session. Always scope cleanup to known lock IDs to avoid collateral damage.
