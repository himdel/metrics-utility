# Metrics Collection

> Default repo: metrics-service

## Learnings

### Collector architecture evolved from individual files to registry-based generic functions
- **Commits**: 3a58426 (#79), e137d39 (#92), 1580ff2 (#109)
- **What happened**: The collector system went through three iterations: (1) In #79, individual hourly collector tasks were created (collect_job_host_summary_hourly, collect_host_metrics_hourly, collect_main_host_hourly) plus a unified `collect_single_collector`. (2) In #92, the legacy collector system was removed (full_process, full_process_anonymize, send_to_segment_task, etc.) and tasks were reorganized into `apps/tasks/collectors/` subdirectory. (3) In #109, the individual collector files were replaced by two generic functions: `collect_hourly_metrics` (for time-series data like job_host_summary_service, unified_jobs, credentials_service) and `collect_snapshot_metrics` (for point-in-time data like execution_environments, config). Each uses a registry dict mapping `collector_type` to `(collector_func, rollup_processor_class)` with lazy imports.
- **Insight**: The registry-based approach is the right pattern for a system with many collectors that share identical logic. Adding a new collector means adding one entry to the registry dict and one task config in `task_groups.py`. The lazy import pattern (`def _get_hourly_collectors()`) is essential because importing metrics_utility at module level would break task registration for simple tasks that don't need the library.

### MAP-REDUCE pipeline: hourly collect, daily rollup, anonymize, send
- **Commits**: 1580ff2 (#109), 05dc0c9 (#112)
- **What happened**: The metrics pipeline follows a MAP-REDUCE pattern: (1) MAP: Hourly collectors run on cron (XX:00, XX:05, XX:10, XX:15) gathering raw metrics into `HourlyMetricsCollection` records. Daily snapshot collectors run once (1:00, 1:30, 1:35, 1:40 AM). (2) REDUCE: `daily_metrics_rollup` (2:00 AM) reads all hourly collections for the day, processes through rollup classes (`prepare(dataframe)->json`, `merge(json,json)->json`), and creates a `DailyMetricsSummary`. (3) ANONYMIZE: `daily_anonymize_and_prepare` (3:00 AM) extracts rollups from the daily summary, passes them to `anonymize_rollups()`, and creates an `AnonymizedMetricsPayload`. (4) SEND: `send_anonymized_to_segment` (4:00 AM) transmits the payload to Segment.
- **Insight**: The staggered cron schedule (hourly collectors at minutes 00/05/10/15, then daily processing at 1:00-4:00 AM) prevents resource contention. Each stage is independent and idempotent -- if one fails, it can be retried without affecting others. The rollup `merge()` function enables incremental daily aggregation.

### Current collector types and their scheduling
- **Commits**: 1580ff2 (#109), 05dc0c9 (#112), a125cb4 (#124)
- **What happened**: The collector registry after #112 contains:
  - **Hourly collectors**: `job_host_summary_service` (XX:00), `unified_jobs` (XX:10), `credentials_service` (XX:15). Note: `job_events`/`main_jobevent_service` is available in registry but not scheduled (too slow).
  - **Daily snapshot collectors**: `execution_environments` (1:00 AM), `config` (1:30 AM), `controller_version_service` (1:35 AM), `table_metadata` (1:40 AM).
  - **Removed**: `main_host` (not in anonymized chain), `main_jobevent` (too slow for production), `host_metrics` (renamed to main_jobevent).
  In #124, the `controller_version_service` and `table_metadata` collectors (partially added in #112) were completed by adding them to the `HourlyMetricsCollection.COLLECTOR_TYPE_CHOICES` model field (with a migration), and adding example entries to the `TASK_METADATA` for `collect_snapshot_metrics`.
- **Insight**: The switch from `job_host_summary` to `job_host_summary_service` variant was for partition pruning optimization in the AWX database. The `_service` variants use table partitioning to query only relevant data, significantly reducing query time for large deployments. Adding new collector types requires changes in multiple places: the registry, the model choices (with migration), the task groups schedule, and the task metadata examples. Missing any one of these (as happened with #112 missing the migration and examples) causes partial functionality.

### Anonymization passes 4 rollup types plus empty events_modules
- **Commits**: 1580ff2 (#109), 05dc0c9 (#112)
- **What happened**: The `daily_anonymize_and_prepare` task extracts rollups from `DailyMetricsSummary` and passes them to `anonymize_rollups()` as named parameters: `jobs_rollup` (unified_jobs), `job_host_summary_rollup` (job_host_summary_service), `credentials_rollup` (credentials_service), `table_metadata_rollup` (table_metadata), `controller_version_rollup` (controller_version_service), plus `config_data` and a `salt` for anonymization. An empty dict is passed for `events_modules_rollup` since main_jobevent is disabled.
- **Insight**: The anonymization API (`anonymize_rollups()`) comes from the metrics-utility library. The service is responsible for collecting and rolling up the data; the library handles the anonymization logic. Keeping these responsibilities separate means the service doesn't need to know anonymization details, and the library doesn't need to know about scheduling or storage.

### Anonymization pipeline fixups: config handling, Segment metadata, debug tooling
- **Commits**: 26614c4 (#113)
- **What happened**: Multiple fixes to the anonymization data flow: (1) `config` data was being mixed into the anonymized payload instead of only staying in the DB -- detached so the config collection ID doesn't get associated with the daily rollup. The `daily_anonymize_and_prepare` function no longer adds `config` to the anonymized data (it was already in the daily summary). (2) `daily_metrics_rollup` now pops `config` from `collections_by_type` before merging, handling it separately. (3) `collect_snapshot_metrics` gained an optional `collection_timestamp` parameter for debugging (overrides the default yesterday-23:00). (4) `send_to_segment` was moved from `utils.py` to `send_anonymized_to_segment.py` and enhanced with `segment_meta` parameter for `timestamp` and `message_id` metadata. (5) The date was dropped from the Segment event name (was `"Controller Metrics Daily Rollup 2026-03-18"`, now just `"Controller Metrics Daily Rollup"`). (6) Debug scripts were added under `tools/tasks/`: `run_anon.sh` runs the full anonymized workflow (24x hourly, snapshot, rollup, anonymize, send), `dump_hourly.py` and `dump_daily_anonymized.py` dump data for inspection.
- **Insight**: The config data leak into payloads was a subtle bug -- config was supposed to be stored in the DB for the daily summary but not transmitted in the anonymized payload. The debug tooling (`run_anon.sh` with dump scripts) is valuable for end-to-end pipeline testing without a real deployment. Removing the date from the event name makes Segment event analysis easier (events group by name, not by date).

### Segment integration: send_to_segment moved and enhanced with metadata
- **Commits**: 26614c4 (#113), 4b078d3 (#147)
- **What happened**: The `send_to_segment()` function was moved from `apps/tasks/utils.py` to `apps/tasks/collectors/send_anonymized_to_segment.py` (collocated with its only caller). It gained a `segment_meta` parameter that passes `timestamp` and `message_id` to `StorageSegment.put()`. The message_id uses `str(payload.created)` which is hashed on the Segment side with the chunk index. In #147, `SEGMENT_TEST_MODE` was added to conditionally append `"_Test"` to event names.
- **Insight**: Moving `send_to_segment` out of the general utils into the specific module that uses it follows the principle of colocation. The `segment_meta` with timestamp and message_id enables idempotent delivery and deduplication on the analytics side.

### Collection timestamps pinned at dispatch time for retry correctness
- **Commits**: da19df3 (#160)
- **What happened**: Hourly and snapshot collectors computed their target time window from `timezone.now()` at execution time. If a task was retried hours later, it would collect data for the wrong time window. A `_inject_dispatch_timestamps()` helper was added to `cron_scheduler.py` that stamps `hour_timestamp` or `collection_timestamp` into `task_data` when the scheduler creates the execution task. Retries use the same `task_data`, so they always operate on the originally intended window. Additionally, `IntegrityError` from duplicate writes is caught and returns success (the data is already there).
- **Insight**: Time-sensitive collection tasks must freeze their target timestamp at dispatch time, not execution time. The pattern: inject the computed timestamp into `task_data` at creation, and have the collector read from `task_data` first, falling back to computing from `now()` only when no timestamp is present.

### Daily collectors added as third collector type
- **Commits**: e8ae871 (#165)
- **What happened**: A new `collect_daily_metrics` function was added for collectors that need explicit `since/until` time boundaries covering the previous full day. The first daily collector is `task_executions_service` (pipeline observability from the metrics-service's own DB, not AWX). A `feature_flags_service` snapshot collector was also added. Both use the existing `generic_collect_metrics` infrastructure.
- **Insight**: The collector taxonomy is now three types: hourly (24x/day, 1-hour windows at XX:00/05/10/15), snapshot (1x/day, no time window at 1:00-1:45 AM), and daily (1x/day, full-day window at 1:50 AM). All three feed into the same daily rollup pipeline. The daily type queries the service's own DB rather than AWX, showing the collector framework's flexibility.

### Advisory locks prevent parallel collector execution
- **Commits**: ccf9494 (#167)
- **What happened**: Each collector task now acquires a PostgreSQL advisory lock via `run_with_lock()`. `TASK_LOCKS` maps task functions to lock IDs -- currently, any hourly collector blocks any other hourly collector. If the lock cannot be acquired, the task fails and is automatically retried with a delay (default 600 seconds). Locking is applied in `execute_db_task` for tasks listed in `TASK_LOCKS`, so direct invocations (e.g., `run_task.py`) run without contention.
- **Insight**: Advisory locks are the correct tool for preventing logical conflicts between background tasks that operate on shared data. Database-level locking (rather than application-level flags) is robust against process crashes -- if a worker dies, the lock is automatically released.

### Segment send changed from fixed cron to jittered one-time task
- **Commits**: 8d4ae7e (#183)
- **What happened**: The `send_to_segment_daily` cron entry (3:30 AM) was removed. Instead, `daily_anonymize_and_prepare` now creates a one-time `send_anonymized_to_segment` Task inside the same atomic transaction as the payload, scheduled at `now + jitter` (0-239 minutes, seeded by installation UUID). The jitter is deterministic: same installation always gets the same offset, but different installations spread across 4 hours.
- **Insight**: Fixed cron schedules cause thundering herd when many installations fire simultaneously. Deterministic jitter (seeded by a stable per-installation UUID) spreads load while keeping the schedule predictable for debugging. Creating the send task inside the anonymization transaction ensures sends are only scheduled when anonymization succeeds.

### Segment send failures made observable with structured results and health checks
- **Commits**: 4e2a18e (#175)
- **What happened**: `send_to_segment` was changed from returning bare strings to returning `create_task_result()` dicts. A new `"unavailable"` status distinguishes missing config from actual errors. `_handle_failed_send` now marks payloads as `"failed"` when `retry_count >= max_retries` instead of infinite retries. The health endpoint checks the most recent `AnonymizedMetricsPayload` and returns unhealthy when it's failed. New `AnonymizedMetricsPayload` status choices: `"unavailable"` added; a unique constraint on active payloads per summary was added.
- **Insight**: Every external integration point needs three things: structured error returns (not bare strings), finite retry with escalation to visible failure, and health check integration. Without these, production failures are invisible.

### METRICS_COLLECTION feature flag added for local collection control
- **Commits**: 68a2039 (#191)
- **What happened**: `METRICS_COLLECTION_GROUP` changed from always-enabled to gated by `METRICS_COLLECTION` flag (default true), allowing operators to pause local collection independently of anonymization.
- **Insight**: Completes the feature flag evolution. See `task_system.md` for the full arc (single flag -> overly broad -> three independent flags). After upgrading, `init-system-tasks` must be re-run.

### Segment StorageSegment use_bulk parameter removed -- not supported by target Segment instance
- **Commits**: e16a862 (#195)
- **What happened**: The `send_to_segment` function was passing `use_bulk=data_size > 24 * 1024` to `StorageSegment()` to enable bulk mode for large payloads (>24KB). This was removed because the target Segment instance does not support bulk mode. The corresponding test (`test_send_to_segment_bulk_mode`) was also deleted.
- **Insight**: Feature flags and conditional behavior for external service capabilities should be validated against the actual target service early. The bulk mode was added speculatively but never worked in practice.

### Anonymization salt parameter removed -- dead code
- **Repo**: ansible/metrics-service
- **Commits**: 5e6c8f6 (#215)
- **What happened**: The `salt` parameter was removed from `daily_anonymize_and_prepare()`. Previously, the function accepted an optional `salt` kwarg (auto-generated via `generate_salt()` if not provided) and passed it to `anonymize_rollups()`. The salt was also removed from the `TASK_METADATA` examples and the test fixture `mock_anonymize_rollups`. The corresponding `generate_salt()` import remained (used elsewhere for `user_id`). The docstring and module-level comment about "salt-based hashing" were updated. Also, `logger.error(f"...")` was changed to `logger.exception(...)` for better traceback capture.
- **Insight**: The salt was removed from the metrics-utility library's `anonymize_rollups()` API first (PR #399 in metrics-utility), and this service-side change followed to clean up the now-dead parameter. When a library removes a parameter, all callers must be updated simultaneously to avoid runtime errors.

### Segment send jitter changed from deterministic (service_id-seeded) to truly random
- **Repo**: ansible/metrics-service
- **Commits**: f7e2265 (#201)
- **What happened**: The `daily_anonymize_and_prepare` task previously computed the jitter offset for `send_anonymized_to_segment` scheduling using `random.Random(seed)` where the seed was derived from `service_id()` (installation UUID). This meant the same installation always sent data at the same time each day, which leaked identifiable timing information. Changed to `random.randint(1, 240)` (truly random per invocation, offset shifted to 1-240 to prevent scheduling in the past). A `random_offset()` function was extracted for testability, with a test verifying the offset is independent of the installation UUID. The test now freezes `timezone.now()` to avoid flaky scheduled_time assertions.
- **Insight**: Deterministic jitter (seeded by a stable identifier) is good for spreading server load but bad when the timing itself becomes a fingerprint. If the same customer always sends at the same time, that time becomes an identifier. Truly random jitter per invocation eliminates the timing correlation while still achieving the load-spreading goal.

## Superseded / Semi-Obsolete

### Individual collector files (collect_job_host_summary_hourly.py, etc.)
- Replaced in 1580ff2 (#109) by `collect_hourly_metrics` and `collect_snapshot_metrics` with registry-based design. No more individual files per collector type.

### main_host collector
- Removed in 1580ff2 (#109). Not part of the anonymized data chain.

### Inline collection in daily_metrics_rollup (_collect_main_host_data, _collect_config_data, etc.)
- Removed in 1580ff2 (#109). All collection now happens via scheduled collector tasks; the rollup only merges pre-collected data.

### _merge_rollup_json and _aggregate_collector_rollups as separate functions
- Consolidated into a single `_merge_collects` function in 35c3db5 (#138). The key change was adding the missing `rollup_processor.base()` call after merging.

### Config data included in anonymized payload
- The config snapshot was incorrectly mixed into the anonymized data in daily_anonymize_and_prepare. Fixed in 26614c4 (#113) by removing the `anonymized_data["config"] = metrics.get("config", {})` line. Config data stays in the DB (DailyMetricsSummary) but is not transmitted.

### Date included in Segment event name
- The event name was `f"Controller Metrics Daily Rollup {todays_date}"` (including the date). Changed to just `"Controller Metrics Daily Rollup"` in 26614c4 (#113).

### Deterministic jitter for send_to_segment (seeded by service_id)
- The deterministic jitter from 8d4ae7e (#183) was replaced in f7e2265 (#201) with truly random jitter. The original approach used `random.Random(seed)` where seed came from the installation UUID, meaning the same installation always sent at the same time -- leaking identifiable timing information.

### Salt parameter in anonymize_rollups() / daily_anonymize_and_prepare()
- The `salt` parameter was removed in 5e6c8f6 (#215), following the library-side removal in metrics-utility PR #399. The salt was no longer used by the anonymization logic.

### send_to_segment function in apps/tasks/utils.py
- Moved to `apps/tasks/collectors/send_anonymized_to_segment.py` in 26614c4 (#113) and enhanced with `segment_meta` parameter for timestamp and message_id.
