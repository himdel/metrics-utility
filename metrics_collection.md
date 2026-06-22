# Metrics Collection
### Initial host_metric command used raw SQL, replaced by ORM in second commit
- **Repo**: ansible/metrics-utility
- **Commits**: 8ab89cc, 22b3072
- **What happened**: The first commit had a `host_metric` command using raw SQL queries (`SELECT ... FROM main_hostmetric`) with manual cursor management. The second commit replaced this with Django ORM queries using `HostMetric.objects.filter().values()`. It also added `_get_existing_columns()` to gracefully handle columns that don't exist in older Controller versions (using `FieldDoesNotExist` exception).
- **Insight**: Using the ORM with dynamic column detection made the tool forward/backward compatible across Controller versions with different model schemas.

### host_metric command removed when billing feature was introduced
- **Repo**: ansible/metrics-utility
- **Commits**: 755110d (#5)
- **What happened**: The `host_metric` command (the original and only command) was removed as part of the billing feature PR. The commit message explicitly states "Host summary command is no longer relevant, remove." The billing data collection superseded the simple host metric export.
- **Insight**: The initial host_metric command was a prototype/proof-of-concept; the real product requirement was the billing data collection pipeline.

### Billing data collected via PostgreSQL COPY for performance
- **Repo**: ansible/metrics-utility
- **Commits**: 755110d (#5)
- **What happened**: The billing collector uses `COPY (SELECT ...) TO STDOUT WITH CSV HEADER` via psycopg's cursor to stream CSV data from the database. A custom `CsvFileSplitter` (extending the base class from `insights_analytics_collector`) handles writing to files, with logic to remove the `_split0` suffix when only one file is produced.
- **Insight**: PostgreSQL COPY is significantly faster than row-by-row fetching for bulk data export, which matters for billing data that can span millions of job host summaries.

### Dynamic date intervals support both absolute and relative formats
- **Repo**: ansible/metrics-utility
- **Commits**: 755110d (#5), 6357e51 (#8)
- **What happened**: The `--since` and `--until` arguments support ISO dates (`2023-12-21`), relative days (`2d` = 2 days ago), and relative minutes (`10m` = 10 minutes ago). The `10m` format was added in PR #8 to support the recommended cron pattern `--until=10m` which gives fresh records time to be fully inserted. When `--since` is omitted, the collector uses the last-collected timestamp (with a 4-week horizon cap).
- **Insight**: The `--until=10m` pattern (collect up to 10 minutes ago) accounts for database write latency and prevents collecting partially-inserted records.

### Credential validation moved from collector to individual Package classes
- **Repo**: ansible/metrics-utility
- **Commits**: c29ffd3 (#16), eeb35bd (#14)
- **What happened**: The `_is_shipping_configured()` check in the base `Collector` class originally validated CRC credentials (checking `AUTOMATION_ANALYTICS_URL`, `REDHAT_USERNAME`, `REDHAT_PASSWORD`). This was removed in favor of each `Package` subclass implementing `is_shipping_configured()` with validation specific to its shipping mode (service account vs userpass vs directory). The old centralized check was replaced with a comment: "This check is already done in each Package class".
- **Insight**: Shipping configuration validation belongs in the Package classes (strategy pattern) because each shipping target has completely different credential requirements.

### ansible_host variable replaces host_name for billing accuracy
- **Repo**: ansible/metrics-utility
- **Commits**: c29ffd3 (#16)
- **What happened**: The job_host_summary collector was extended to also collect `ansible_host` and `ansible_connection` from `main_host.variables` (joined via `host_id`). In the dataframe engine, if `ansible_host_variable` is present and non-null for a row, it replaces `host_name` for billing purposes. This is because `host_name` in Controller is the inventory hostname (which may be an alias), while `ansible_host` is the actual target being automated.
- **Insight**: For billing (counting unique managed nodes), `ansible_host` is the correct identifier because multiple inventory entries with different names can point to the same actual host.

### jobevent collector added for content usage analysis
- **Repo**: ansible/metrics-utility
- **Commits**: 9272f1d (#17)
- **What happened**: A new `main_jobevent` collector was added that captures per-task event data (task actions, resolved roles/collections, durations). The collector is gated by `METRICS_UTILITY_OPTIONAL_COLLECTORS` and scopes events to job host summaries within the time window using a CTE. The `event_data` JSONB field is accessed after replacing Unicode escape sequences (`\u` -> `\u`) to prevent PostgreSQL JSON parse errors.
- **Insight**: The jobevent collector uses a CTE joining against `main_jobhostsummary` to scope which events to collect, rather than filtering jobevents directly by timestamp -- this ensures consistency with the billing data boundary.

### indirect_nodes collector added for indirectly managed network devices
- **Repo**: ansible/metrics-utility
- **Commits**: 81e93b5 (#75)
- **What happened**: A new `indirect_nodes` collector was registered with `@register('indirect_nodes', '1.0', ...)` querying `main_indirectmanagednodeaudit`. This table tracks nodes managed indirectly (e.g., network devices managed through a jump host). The collector is gated by `INCLUDE_INDIRECT` which checks `'indirect_nodes' in METRICS_UTILITY_OPTIONAL_COLLECTORS`. The query joins against `main_unifiedjob`, `main_inventory`, `main_organization`, and `main_unifiedjobtemplate` to get the same organizational context as direct nodes. The `optional_collectors()` function was moved from `collectors.py` to `metric_utils.py` to make it importable by both collectors and dataframe engines.
- **Insight**: The `optional_collectors()` function was originally local to `collectors.py`, but the indirect nodes feature needed to check it from the dataframe engine too, forcing it into a shared `metric_utils.py` module -- an example of feature work revealing hidden coupling.

### main_host collector added for inventory scope with limit_slicing
- **Repo**: ansible/metrics-utility
- **Commits**: 7a8bea5 (#78)
- **What happened**: A new `main_host` collector was registered with `@register('main_host', '1.0', ..., fnc_slicing=limit_slicing)` querying the `main_host` table joined with `main_inventory`, `main_organization`, and `main_unifiedjob`. Unlike other collectors that use `daily_slicing` (partitioning by modification timestamp), `main_host` uses a new `limit_slicing` function that always yields today's date as both since and until -- because inventory is a point-in-time snapshot, not an event stream. The collector extracts `host_name`, `host_id`, inventory/org context, `last_automation` date, `ansible_host_variable`, `canonical_facts` (product serial, machine UUID), and `facts` (ansible_connection). It reuses the `yaml_and_json_parsing_functions()` helper (extracted from job_host_summary) for parsing host variables that may be JSON or YAML. Gated by `'main_host' in get_optional_collectors()`.
- **Insight**: Inventory data requires fundamentally different slicing than event data -- you can only capture the current state, not historical states, so `limit_slicing` always stores a fresh snapshot into today's partition regardless of collection frequency.

### Unreachable hosts filtered from managed node count
- **Repo**: ansible/metrics-utility
- **Commits**: db4eeea (#79)
- **What happened**: The `DataframeJobhostSummaryUsage` engine was updated to filter out hosts where all tasks were in `unreachable`/`dark` state. A `sum_reachable_columns` function sums `failures`, `ok`, `skipped`, `ignored`, and `rescued` (excluding `dark`), and rows with `reachable_task_runs == 0` are removed. This only applies to `DIRECT` managed nodes (not indirect).
- **Insight**: Ansible's `dark` counter represents hosts that could not be reached at all -- counting them as managed nodes would inflate billing numbers for hosts that were never actually automated.

### MAX_GATHER_PERIOD_WEEKS constant replaces hardcoded 4-week limits
- **Repo**: ansible/metrics-utility
- **Commits**: 2ac3131 (#168)
- **What happened**: The 4-week maximum gather period was hardcoded as `timedelta(weeks=4)` in three places: `_calculate_collection_interval()` (twice), `Collection.since` property, and `daily_slicing()`. All were replaced with `Collector.MAX_GATHER_PERIOD_WEEKS = 4` class constant. The `since-until` difference check now uses this constant. Progress logging was also added: the collector now logs `Progress info: Now gathering {collection.key}` at `WARNING` level whenever it starts collecting a new collector type, and logs the original and final since-until intervals. The gather command was simplified to just log `Analytics collected` on success instead of listing individual tarball paths.
- **Insight**: Centralizing the 4-week maximum as a class constant enables subclasses or future config to adjust it without hunting through multiple files, and the progress logging helps operators monitor long-running collections.

### main_host collector expanded with additional facts for deduplication
- **Repo**: ansible/metrics-utility
- **Commits**: afc880a (#166)
- **What happened**: The `main_host` collector SQL was expanded to collect significantly more ansible facts: `ansible_host` (from host variables), `host_name`, `ansible_port` (with integer validation), `ansible_virtualization_type`, `ansible_virtualization_role`, `ansible_system_vendor`, `ansible_product_name`, `ansible_architecture`, `ansible_processor`, `ansible_form_factor`, `ansible_bios_vendor`, `ansible_bios_version`, and `ansible_board_serial`. The `compute_serial` function was made safer by using `.get()` instead of direct dict access for `ansible_product_serial` and `ansible_machine_id`, preventing `KeyError` when fact keys are missing. A `host_names_before_dedup` column was added to track original hostnames when dedup is enabled.
- **Insight**: Collecting additional hardware and system facts enables more sophisticated deduplication strategies and provides richer infrastructure visibility in reports -- but the collector SQL must use safe access patterns (`.get()`) since any fact key may be absent on any given host.

### Progress logging now skips disabled collectors instead of logging all
- **Repo**: ansible/metrics-utility
- **Commits**: f15bd74 (#185)
- **What happened**: The base `Collector._gather_csv_collections()` previously logged `Progress info: Now gathering {collection.key}` for every registered collector, even disabled ones. The fix checks whether each collector is enabled (via `get_optional_collectors()` and `METRICS_UTILITY_DISABLE_JOB_HOST_SUMMARY_COLLECTOR`) and logs either "Now gathering" or "Skipping {key} because it is not enabled" accordingly. The destination path is now also logged at debug level in `PackageDirectory` and `PackageS3` after successful shipping.
- **Insight**: Progress logging should distinguish between enabled and disabled collectors -- logging "Now gathering X" for a disabled collector is misleading and makes operators think data collection is happening when it is not.

### `total_workers_vcpu` JSON collector switched from Kubernetes API to Prometheus
- **Repo**: ansible/metrics-utility
- **Commits**: 429816e (#165), 0be6cd0 (#198)
- **What happened**: A `total_workers_vcpu` collector was added as the first JSON-format collector for SaaS vCPU counting. It is gated by `'total_workers_vcpu' in get_optional_collectors()` and uses `limit_slicing`. Originally (#165), when `METRICS_UTILITY_USAGE_BASED_BILLING_ENABLED` was `true`, it used the `kubernetes` Python library to query `CoreV1Api.list_node()` and sum CPU capacity across nodes. In #198, this was replaced with Prometheus PromQL queries: the collector now uses a `PrometheusClient` (authenticated via Kubernetes service account token) to query `max_over_time(sum(machine_cpu_cores)[59m59s:5m])` for the previous hour. The env var was also renamed from `METRICS_UTILITY_USAGE_BASED_BILLING_ENABLED` to `METRICS_UTILITY_USAGE_BASED_METERING_ENABLED`. A new `METRICS_UTILITY_PROMETHEUS_URL` env var was added (defaults to the in-cluster OpenShift monitoring endpoint). The collector also now records a CPU timeline (5-minute intervals) for the previous hour in the output JSON. A `KubernetesClient` class was extracted for service account token retrieval and CA cert path handling.
- **Insight**: Prometheus provides historical vCPU data with time-series granularity (previous hour's max), while the Kubernetes API only provides instantaneous values -- Prometheus is the better data source when you need representative billing data that isn't sensitive to momentary fluctuations. **Supersedes** the Kubernetes API approach from #165.

### Service-oriented collectors filter by job.finished instead of jobhostsummary.modified
- **Repo**: ansible/metrics-utility
- **Commits**: 0c851b4 (#214)
- **What happened**: Four new collectors were added for the metrics service: `unified_jobs` (full job data with EE images, content types, installed collections), `job_host_summary_service` (host summaries filtered by `job.finished`), `main_jobevent_service` (events with full event_data), and `execution_environments` (EE inventory snapshot via `limit_slicing`). Unlike the existing `job_host_summary` collector that filters by `jobhostsummary.modified`, the service variant uses `job.finished` as the time boundary -- this ensures jobs, their host summaries, and their events all share the same time window for consistent aggregation. The `main_jobevent_service` collector uses a two-phase approach: first queries finished job IDs, then builds a literal `(job_id, job_created) IN (VALUES ...)` clause to scope the event query, avoiding an expensive join on the large jobevent table.
- **Insight**: When collectors need to feed into cross-entity aggregations (jobs + summaries + events), filtering all by the same field (`job.finished`) ensures consistency -- using different timestamps per entity type (e.g., `jobhostsummary.modified`) would cause entities from the same job run to appear in different time slices.

### collections.json maps Ansible collection names to source types
- **Repo**: ansible/metrics-utility
- **Commits**: cc0788f (#225)
- **What happened**: A `collections.json` file was added under `metrics_utility/anonymized_rollups/` containing ~3750 Ansible collection names mapped to their source type (`community`, `validated`, or `certified`). The data is aggregated from both Ansible Galaxy (community collections) and Automation Hub (certified and validated collections) using shell scripts in `tools/collections/` that paginate through the respective APIs and merge results. The anonymized rollup code uses this mapping to classify module usage by collection source.
- **Insight**: Collection source classification (community vs certified vs validated) requires a static lookup table built from Galaxy/Hub APIs because the source type is not embedded in the collection namespace -- the same `namespace.name` format is used across all sources.

### `job_id` and `host_id` columns added to `main_jobevent_service` collector
- **Repo**: ansible/metrics-utility
- **Commits**: 2a9cdd7 (#235)
- **What happened**: The `main_jobevent_service` collector previously only exposed `e.job_id AS job_remote_id` and `e.host_id AS host_remote_id` (aliased columns). The raw `e.job_id` and `e.host_id` columns were added alongside the aliased versions. This provides both the raw foreign keys and the aliased versions for different consumers: the rollup code can use the raw IDs for joins while the remote service uses the aliased names.
- **Insight**: When a collector's SQL SELECT aliases columns for one consumer (`job_remote_id` for the metrics service), also expose the raw column if other code paths (like rollups joining against job data) need the original name -- aliasing alone hides the column from consumers expecting the original name.

### Config collector decoupled from AWX Python imports via direct DB queries
- **Repo**: ansible/metrics-utility
- **Commits**: d005629 (#242), 0799a24 (#245)
- **What happened**: The `config` collector previously imported `get_license()` from `awx.conf.license`, `get_awx_version()` from `awx.main.utils`, and read `django.conf.settings` attributes (INSTALL_UUID, SYSTEM_UUID, TOWER_URL_BASE, etc.). All were replaced with `get_config_and_settings_from_db()` which reads the `conf_setting` table in one query, `get_controller_version_from_db()` which tries conf_setting keys (AWX_VERSION, TOWER_VERSION, VERSION) then falls back to `main_instance.version`, and a local `datetime_hook()` function. Similarly, `daily_slicing()` and `_get_last_entries()` replaced their `awx.conf.models.Setting` ORM calls with `get_last_entries_from_db()` raw SQL. Mock DB data was updated to include `conf_setting` rows matching the mock license info.
- **Insight**: Reading Controller settings via direct SQL against `conf_setting` rather than Django ORM/settings removes the runtime dependency on AWX Python packages -- the collectors now only need a database connection and the AWX schema, not the AWX codebase itself.

### `main_host_daily` collector added for time-bounded host collection
- **Repo**: ansible/metrics-utility
- **Commits**: 2afe3c7 (#209)
- **What happened**: The existing `main_host` collector uses `limit_slicing` (always collects ALL enabled hosts as a full snapshot). For deployments with very large host inventories, this produces excessive data when run daily. A new `main_host_daily` collector was added alongside `main_host`, using `daily_slicing` and filtering hosts by `created` OR `modified` within the since/until window. The shared SQL was extracted into a `_main_host_query(where)` function that both collectors call with different WHERE clauses (`main_host` uses `enabled='t'`, `main_host_daily` uses date filters). `DataframeInventoryScope` was updated to request both `main_host` and `main_host_daily` collections, using `main_host_daily` as a fallback when `main_host` is empty. A `date_where(field, since, until)` utility was added to `library/collectors/util.py` for building date range SQL clauses. The recommended pattern is: daily cronjob with `main_host_daily` for incremental changes, weekly cronjob with `main_host` (and `DISABLE_JOB_HOST_SUMMARY_COLLECTOR=true`) for full snapshots.
- **Insight**: When a full-table collector becomes too expensive for daily runs, adding a time-filtered variant alongside the original (rather than replacing it) lets operators choose the tradeoff between completeness and performance via `METRICS_UTILITY_OPTIONAL_COLLECTORS`.

### Collector architecture evolved from individual files to registry-based generic functions
- **Repo**: ansible/metrics-service
- **Commits**: 3a58426 (#79), e137d39 (#92), 1580ff2 (#109)
- **What happened**: The collector system went through three iterations: (1) In #79, individual hourly collector tasks were created (collect_job_host_summary_hourly, collect_host_metrics_hourly, collect_main_host_hourly) plus a unified `collect_single_collector`. (2) In #92, the legacy collector system was removed (full_process, full_process_anonymize, send_to_segment_task, etc.) and tasks were reorganized into `apps/tasks/collectors/` subdirectory. (3) In #109, the individual collector files were replaced by two generic functions: `collect_hourly_metrics` (for time-series data like job_host_summary_service, unified_jobs, credentials_service) and `collect_snapshot_metrics` (for point-in-time data like execution_environments, config). Each uses a registry dict mapping `collector_type` to `(collector_func, rollup_processor_class)` with lazy imports.
- **Insight**: The registry-based approach is the right pattern for a system with many collectors that share identical logic. Adding a new collector means adding one entry to the registry dict and one task config in `task_groups.py`. The lazy import pattern (`def _get_hourly_collectors()`) is essential because importing metrics_utility at module level would break task registration for simple tasks that don't need the library.

### MAP-REDUCE pipeline: hourly collect, daily rollup, anonymize, send
- **Repo**: ansible/metrics-service
- **Commits**: 1580ff2 (#109), 05dc0c9 (#112)
- **What happened**: The metrics pipeline follows a MAP-REDUCE pattern: (1) MAP: Hourly collectors run on cron (XX:00, XX:05, XX:10, XX:15) gathering raw metrics into `HourlyMetricsCollection` records. Daily snapshot collectors run once (1:00, 1:30, 1:35, 1:40 AM). (2) REDUCE: `daily_metrics_rollup` (2:00 AM) reads all hourly collections for the day, processes through rollup classes (`prepare(dataframe)->json`, `merge(json,json)->json`), and creates a `DailyMetricsSummary`. (3) ANONYMIZE: `daily_anonymize_and_prepare` (3:00 AM) extracts rollups from the daily summary, passes them to `anonymize_rollups()`, and creates an `AnonymizedMetricsPayload`. (4) SEND: `send_anonymized_to_segment` (4:00 AM) transmits the payload to Segment.
- **Insight**: The staggered cron schedule (hourly collectors at minutes 00/05/10/15, then daily processing at 1:00-4:00 AM) prevents resource contention. Each stage is independent and idempotent -- if one fails, it can be retried without affecting others. The rollup `merge()` function enables incremental daily aggregation.

### Current collector types and their scheduling
- **Repo**: ansible/metrics-service
- **Commits**: 1580ff2 (#109), 05dc0c9 (#112), a125cb4 (#124)
- **What happened**: The collector registry after #112 contains:
  - **Hourly collectors**: `job_host_summary_service` (XX:00), `unified_jobs` (XX:10), `credentials_service` (XX:15). Note: `job_events`/`main_jobevent_service` is available in registry but not scheduled (too slow).
  - **Daily snapshot collectors**: `execution_environments` (1:00 AM), `config` (1:30 AM), `controller_version_service` (1:35 AM), `table_metadata` (1:40 AM).
  - **Removed**: `main_host` (not in anonymized chain), `main_jobevent` (too slow for production), `host_metrics` (renamed to main_jobevent).
  In #124, the `controller_version_service` and `table_metadata` collectors (partially added in #112) were completed by adding them to the `HourlyMetricsCollection.COLLECTOR_TYPE_CHOICES` model field (with a migration), and adding example entries to the `TASK_METADATA` for `collect_snapshot_metrics`.
- **Insight**: The switch from `job_host_summary` to `job_host_summary_service` variant was for partition pruning optimization in the AWX database. The `_service` variants use table partitioning to query only relevant data, significantly reducing query time for large deployments. Adding new collector types requires changes in multiple places: the registry, the model choices (with migration), the task groups schedule, and the task metadata examples. Missing any one of these (as happened with #112 missing the migration and examples) causes partial functionality.

### Anonymization passes 4 rollup types plus empty events_modules
- **Repo**: ansible/metrics-service
- **Commits**: 1580ff2 (#109), 05dc0c9 (#112)
- **What happened**: The `daily_anonymize_and_prepare` task extracts rollups from `DailyMetricsSummary` and passes them to `anonymize_rollups()` as named parameters: `jobs_rollup` (unified_jobs), `job_host_summary_rollup` (job_host_summary_service), `credentials_rollup` (credentials_service), `table_metadata_rollup` (table_metadata), `controller_version_rollup` (controller_version_service), plus `config_data` and a `salt` for anonymization. An empty dict is passed for `events_modules_rollup` since main_jobevent is disabled.
- **Insight**: The anonymization API (`anonymize_rollups()`) comes from the metrics-utility library. The service is responsible for collecting and rolling up the data; the library handles the anonymization logic. Keeping these responsibilities separate means the service doesn't need to know anonymization details, and the library doesn't need to know about scheduling or storage.

### `table_metadata` and `controller_version_service` collectors added for infrastructure telemetry
- **Repo**: ansible/metrics-utility
- **Commits**: 3d86b71 (#328), c225bdf (#329)
- **What happened**: Two new collectors were added for infrastructure-level telemetry: (1) `table_metadata` queries PostgreSQL system catalogs (`pg_class`, `pg_namespace`, `pg_inherits`, `pg_stat_user_tables`) to collect estimated row counts and byte sizes (total, table, indexes) for `main_jobevent` (partitioned), `main_unifiedjob`, and `main_jobhostsummary`. For the partitioned `main_jobevent`, it sums across all partitions via `pg_inherits`. (2) `controller_version_service` queries `main_instance` for distinct controller versions from enabled instances. Both use `limit_slicing` (point-in-time snapshot). PR #329 fixed the row count estimation: `pg_class.reltuples` (updated by ANALYZE, can be stale or -1 for never-analyzed tables) was replaced with `pg_stat_user_tables.n_live_tup` (updated by the statistics collector, more current). Corresponding rollup classes (`TableMetadataAnonymizedRollup`, `ControllerVersionAnonymizedRollup`) were added that use snapshot-style merging (always replace with new data, no accumulation). The `credentials_service` collector was also updated to filter `credential_type__managed = true` only, avoiding exposure of custom credential type names.
- **Insight**: For table metadata collection, `pg_stat_user_tables.n_live_tup` is more reliable than `pg_class.reltuples` for row count estimation -- `reltuples` can be -1 for never-analyzed tables and is only updated by ANALYZE/VACUUM, while `n_live_tup` is maintained by the statistics collector continuously.

### Anonymized rollups support running without events collectors
- **Repo**: ansible/metrics-utility
- **Commits**: 3d86b71 (#328)
- **What happened**: The anonymized rollup pipeline was updated to handle the case where event collectors (`main_jobevent_service`) are disabled or produce no data. When events data is empty, event-related fields (`module_stats`, `collection_name_stats`, `modules_used_per_playbook_total`, warnings/deprecations counts) are omitted from the final JSON rather than being populated with zeros or empty structures. The `flatten_json_report()` function checks for empty events data and conditionally includes event-derived statistics. A `test_all_no_events.py` test validates the complete rollup pipeline with events disabled.
- **Insight**: Supporting the no-events case is important because events collection is the most expensive collector (querying the potentially huge `main_jobevent` table) and some deployments disable it via `METRICS_UTILITY_OPTIONAL_COLLECTORS` -- the rollup pipeline must produce valid output with the remaining data rather than crashing on missing fields.

### Dashboard jobs collector: structured dict output for metrics-service API
- **Repo**: ansible/metrics-utility
- **Commits**: 5b26fc3 (#341)
- **What happened**: A `dashboard_jobs` collector was added under `library/collectors/dashboard/` that returns `{'count': int, 'results': [AWXJobType]}` -- a paginated-style response designed for direct API consumption. Each job result includes nested `labels` (list of label IDs) and `host_summaries` (list of `{id, host_name, host_id}` dicts) collected via separate sub-queries. The SQL WHERE clause filters by `uj.modified` (not `uj.finished`), excludes `sync` jobs, and includes only `failed`/`successful` status. The collector uses `%s` parameterized placeholders (via a shared `get_where_clause` function) rather than f-string interpolation.
- **Insight**: The dashboard collector uses `modified` as the time boundary (not `finished` like service collectors or `created` like indirect nodes) because dashboard consumers want to see the most recently updated jobs, including jobs whose metadata changed after completion.

### `controller_version_service` restricted to control/hybrid nodes
- **Repo**: ansible/metrics-utility
- **Commits**: b7037cf (#350)
- **What happened**: The `controller_version_service` collector query was updated to add `AND node_type IN ('control', 'hybrid')` to the WHERE clause, filtering out execution-only nodes and hop nodes. Previously it selected all enabled instances with non-empty versions, which could include execution nodes running a different version.
- **Insight**: Controller version should only reflect control plane nodes (control/hybrid) -- execution nodes may run different software versions and don't represent the Controller version for reporting purposes.

### `execution_environment_id` added to `unified_jobs` collector for collection caching
- **Repo**: ansible/metrics-utility
- **Commits**: b7037cf (#350)
- **What happened**: The `unified_jobs` collector gained a new `main_unifiedjob.execution_environment_id` column in its SELECT. This integer ID is used downstream by `JobsAnonymizedRollup._get_collection_cache_key()` as a stable cache key for parsed installed collections data -- all jobs sharing the same execution environment have identical installed collections, so the EE ID avoids redundant JSON parsing. The test data was also updated with actual `execution_environment_image` values.
- **Insight**: Adding a foreign key ID column to a collector can dramatically improve downstream processing performance -- using it as a cache key is both faster (integer comparison vs string hashing) and more reliable (stable ID vs non-deterministic JSON serialization order) than hashing the payload.

### Anonymization pipeline fixups: config handling, Segment metadata, debug tooling
- **Repo**: ansible/metrics-service
- **Commits**: 26614c4 (#113)
- **What happened**: Multiple fixes to the anonymization data flow: (1) `config` data was being mixed into the anonymized payload instead of only staying in the DB -- detached so the config collection ID doesn't get associated with the daily rollup. The `daily_anonymize_and_prepare` function no longer adds `config` to the anonymized data (it was already in the daily summary). (2) `daily_metrics_rollup` now pops `config` from `collections_by_type` before merging, handling it separately. (3) `collect_snapshot_metrics` gained an optional `collection_timestamp` parameter for debugging (overrides the default yesterday-23:00). (4) `send_to_segment` was moved from `utils.py` to `send_anonymized_to_segment.py` and enhanced with `segment_meta` parameter for `timestamp` and `message_id` metadata. (5) The date was dropped from the Segment event name (was `"Controller Metrics Daily Rollup 2026-03-18"`, now just `"Controller Metrics Daily Rollup"`). (6) Debug scripts were added under `tools/tasks/`: `run_anon.sh` runs the full anonymized workflow (24x hourly, snapshot, rollup, anonymize, send), `dump_hourly.py` and `dump_daily_anonymized.py` dump data for inspection.
- **Insight**: The config data leak into payloads was a subtle bug -- config was supposed to be stored in the DB for the daily summary but not transmitted in the anonymized payload. The debug tooling (`run_anon.sh` with dump scripts) is valuable for end-to-end pipeline testing without a real deployment. Removing the date from the event name makes Segment event analysis easier (events group by name, not by date).

### Segment integration: send_to_segment moved and enhanced with metadata
- **Repo**: ansible/metrics-service
- **Commits**: 26614c4 (#113), 4b078d3 (#147)
- **What happened**: The `send_to_segment()` function was moved from `apps/tasks/utils.py` to `apps/tasks/collectors/send_anonymized_to_segment.py` (collocated with its only caller). It gained a `segment_meta` parameter that passes `timestamp` and `message_id` to `StorageSegment.put()`. The message_id uses `str(payload.created)` which is hashed on the Segment side with the chunk index. In #147, `SEGMENT_TEST_MODE` was added to conditionally append `"_Test"` to event names.
- **Insight**: Moving `send_to_segment` out of the general utils into the specific module that uses it follows the principle of colocation. The `segment_meta` with timestamp and message_id enables idempotent delivery and deduplication on the analytics side.

### All collectors unified on `date_where()` for SQL date interpolation
- **Repo**: ansible/metrics-utility
- **Commits**: 04e583a (#353)
- **What happened**: Six collectors manually interpolated since/until timestamps into SQL with f-string patterns like `f"field >= '{since.isoformat()}' AND field < '{until.isoformat()}'"`. All were refactored to use the shared `date_where(field, since, until)` utility from `library/collectors/util.py`. The utility was also enhanced with runtime validation that since/until are timezone-aware datetime instances, catching naive datetimes or wrong types early rather than silently generating incorrect SQL. A `utcdt()` test helper was added to `test/util.py` that parses ISO date/datetime strings as UTC, replacing verbose `datetime(..., tzinfo=timezone.utc)` calls across 8 test files.
- **Insight**: When multiple collectors share the same date-filtering SQL pattern, centralizing it into a validated utility function not only reduces duplication but enables adding type checks (timezone-aware datetimes) that prevent subtle bugs across all callers at once.

### `config_django` collector: Django-based fallback for config collection
- **Repo**: ansible/metrics-utility
- **Commits**: 5829c26 (#354)
- **What happened**: The `config` collector (introduced in #242) reads config data via direct SQL against the `conf_setting` table. However, some config fields (like `AUTHENTICATION_BACKENDS`, `LOG_AGGREGATOR_*` settings) are not stored in `conf_setting` and were previously read from `django.conf.settings` in the pre-#242 code. A new `config_django` collector was added that restores the Django-based approach: it imports `get_license()`, `get_awx_version()`, and reads `django.conf.settings` directly, with all AWX/Django imports deferred to runtime. The CLI's `cli_config` now tries `config_django` first and falls back to the DB-based `config` collector on failure. The `config.py` collector also replaced `django.utils.dateparse.parse_datetime` with `datetime.fromisoformat` to drop its Django dependency.
- **Insight**: When a collector was refactored to remove framework dependencies (#242), some fields that only exist as in-memory settings (not persisted to DB) were silently lost -- adding a framework-based fallback collector with try/except ensures completeness when the framework is available while maintaining standalone capability.

### Collection timestamps pinned at dispatch time for retry correctness
- **Repo**: ansible/metrics-service
- **Commits**: da19df3 (#160)
- **What happened**: Hourly and snapshot collectors computed their target time window from `timezone.now()` at execution time. If a task was retried hours later, it would collect data for the wrong time window. A `_inject_dispatch_timestamps()` helper was added to `cron_scheduler.py` that stamps `hour_timestamp` or `collection_timestamp` into `task_data` when the scheduler creates the execution task. Retries use the same `task_data`, so they always operate on the originally intended window. Additionally, `IntegrityError` from duplicate writes is caught and returns success (the data is already there).
- **Insight**: Time-sensitive collection tasks must freeze their target timestamp at dispatch time, not execution time. The pattern: inject the computed timestamp into `task_data` at creation, and have the collector read from `task_data` first, falling back to computing from `now()` only when no timestamp is present.

### `feature_flags_service` collector reads enabled flags from `dab_feature_flags_aapflag`
- **Repo**: ansible/metrics-utility
- **Commits**: 7db682c (#357)
- **What happened**: A `feature_flags_service` collector was added under `library/collectors/controller/` that queries the `dab_feature_flags_aapflag` table for enabled feature flags (where `condition = 'boolean' AND value = 'True'`). The corresponding `FeatureFlagsAnonymizedRollup` is a snapshot-style rollup that returns the list of flag names -- it always replaces with the latest data during merge (no accumulation). The rollup output is included in the flattened anonymized report as `feature_flags: [list of flag names]`. The Docker Compose init scripts were extended with `dab_feature_flags.sql` to provide test data.
- **Insight**: Snapshot-style collectors (feature flags, controller version, table metadata) use a "replace, don't merge" strategy in their rollup's `merge()` method because they capture point-in-time state -- accumulating historical snapshots would be meaningless.

### `task_executions_service` collector: observability for the collector pipeline itself
- **Repo**: ansible/metrics-utility
- **Commits**: 7db682c (#357)
- **What happened**: A new `library/collectors/service/` package was created with `task_executions_service`, the first collector that queries the metrics-service database (not the Controller DB). It reads from `tasks_taskexecution` to track how well the collector pipeline is running: per-collector-type execution counts, durations, and missing execution detection. The `TaskExecutionsAnonymizedRollup` computes expected vs actual executions per collector type (hourly collectors expect 24/day, snapshot collectors expect 1/day) and reports `executions_missing_total` when runs were skipped. This also restructured the rollup pipeline: `compute_anonymized_rollup_from_raw_data()` and `load_anonymized_rollup_data()` were moved out of `anonymized_rollups.py` into separate test helpers, since they were only used by tests -- the production pipeline uses a different entry point.
- **Insight**: Self-observability collectors that monitor the pipeline itself (expected vs actual executions, durations) provide the recipient of anonymized reports with data quality signals -- if `executions_missing_total > 0`, the corresponding collector data for that period may be incomplete.

### Daily collectors added as third collector type
- **Repo**: ansible/metrics-service
- **Commits**: e8ae871 (#165)
- **What happened**: A new `collect_daily_metrics` function was added for collectors that need explicit `since/until` time boundaries covering the previous full day. The first daily collector is `task_executions_service` (pipeline observability from the metrics-service's own DB, not AWX). A `feature_flags_service` snapshot collector was also added. Both use the existing `generic_collect_metrics` infrastructure.
- **Insight**: The collector taxonomy is now three types: hourly (24x/day, 1-hour windows at XX:00/05/10/15), snapshot (1x/day, no time window at 1:00-1:45 AM), and daily (1x/day, full-day window at 1:50 AM). All three feed into the same daily rollup pipeline. The daily type queries the service's own DB rather than AWX, showing the collector framework's flexibility.

### Advisory locks prevent parallel collector execution
- **Repo**: ansible/metrics-service
- **Commits**: ccf9494 (#167)
- **What happened**: Each collector task now acquires a PostgreSQL advisory lock via `run_with_lock()`. `TASK_LOCKS` maps task functions to lock IDs -- currently, any hourly collector blocks any other hourly collector. If the lock cannot be acquired, the task fails and is automatically retried with a delay (default 600 seconds). Locking is applied in `execute_db_task` for tasks listed in `TASK_LOCKS`, so direct invocations (e.g., `run_task.py`) run without contention.
- **Insight**: Advisory locks are the correct tool for preventing logical conflicts between background tasks that operate on shared data. Database-level locking (rather than application-level flags) is robust against process crashes -- if a worker dies, the lock is automatically released.

### Segment send failures made observable with structured results and health checks
- **Repo**: ansible/metrics-service
- **Commits**: 4e2a18e (#175)
- **What happened**: `send_to_segment` was changed from returning bare strings to returning `create_task_result()` dicts. A new `"unavailable"` status distinguishes missing config from actual errors. `_handle_failed_send` now marks payloads as `"failed"` when `retry_count >= max_retries` instead of infinite retries. The health endpoint checks the most recent `AnonymizedMetricsPayload` and returns unhealthy when it's failed. New `AnonymizedMetricsPayload` status choices: `"unavailable"` added; a unique constraint on active payloads per summary was added.
- **Insight**: Every external integration point needs three things: structured error returns (not bare strings), finite retry with escalation to visible failure, and health check integration. Without these, production failures are invisible.

### Segment send changed from fixed cron to jittered one-time task
- **Repo**: ansible/metrics-service
- **Commits**: 8d4ae7e (#183)
- **What happened**: The `send_to_segment_daily` cron entry (3:30 AM) was removed. Instead, `daily_anonymize_and_prepare` now creates a one-time `send_anonymized_to_segment` Task inside the same atomic transaction as the payload, scheduled at `now + jitter` (0-239 minutes, seeded by installation UUID). The jitter is deterministic: same installation always gets the same offset, but different installations spread across 4 hours.
- **Insight**: Fixed cron schedules cause thundering herd when many installations fire simultaneously. Deterministic jitter (seeded by a stable per-installation UUID) spreads load while keeping the schedule predictable for debugging. Creating the send task inside the anonymization transaction ensures sends are only scheduled when anonymization succeeds.

### METRICS_COLLECTION feature flag added for local collection control
- **Repo**: ansible/metrics-service
- **Commits**: 68a2039 (#191)
- See [settings_and_configuration.md](settings_and_configuration.md#metrics_collection-feature-flag-added-for-local-collection-control) for the full entry. Summary: `METRICS_COLLECTION_GROUP` changed from always-enabled to gated by `METRICS_COLLECTION` flag (default true). The system now has three flags: `METRICS_COLLECTION`, `ANONYMIZED_DATA_COLLECTION`, `DASHBOARD_COLLECTION`. See `task_system.md` for the full feature flag evolution arc.

### Segment StorageSegment use_bulk parameter removed -- not supported by target Segment instance
- **Repo**: ansible/metrics-service
- **Commits**: e16a862 (#195)
- **What happened**: The `send_to_segment` function was passing `use_bulk=data_size > 24 * 1024` to `StorageSegment()` to enable bulk mode for large payloads (>24KB). This was removed because the target Segment instance does not support bulk mode. The corresponding test (`test_send_to_segment_bulk_mode`) was also deleted.
- **Insight**: Feature flags and conditional behavior for external service capabilities should be validated against the actual target service early. The bulk mode was added speculatively but never worked in practice.

### Segment send jitter changed from deterministic (service_id-seeded) to truly random
- **Repo**: ansible/metrics-service
- **Commits**: f7e2265 (#201)
- **What happened**: The `daily_anonymize_and_prepare` task previously computed the jitter offset for `send_anonymized_to_segment` scheduling using `random.Random(seed)` where the seed was derived from `service_id()` (installation UUID). This meant the same installation always sent data at the same time each day, which leaked identifiable timing information. Changed to `random.randint(1, 240)` (truly random per invocation, offset shifted to 1-240 to prevent scheduling in the past). A `random_offset()` function was extracted for testability, with a test verifying the offset is independent of the installation UUID. The test now freezes `timezone.now()` to avoid flaky scheduled_time assertions.
- **Insight**: Deterministic jitter (seeded by a stable identifier) is good for spreading server load but bad when the timing itself becomes a fingerprint. If the same customer always sends at the same time, that time becomes an identifier. Truly random jitter per invocation eliminates the timing correlation while still achieving the load-spreading goal.

### Anonymization salt parameter removed -- dead code
- **Repo**: ansible/metrics-service
- **Commits**: 5e6c8f6 (#215)
- **What happened**: The `salt` parameter was removed from `daily_anonymize_and_prepare()`. Previously, the function accepted an optional `salt` kwarg (auto-generated via `generate_salt()` if not provided) and passed it to `anonymize_rollups()`. The salt was also removed from the `TASK_METADATA` examples and the test fixture `mock_anonymize_rollups`. The corresponding `generate_salt()` import remained (used elsewhere for `user_id`). The docstring and module-level comment about "salt-based hashing" were updated. Also, `logger.error(f"...")` was changed to `logger.exception(...)` for better traceback capture.
- **Insight**: The salt was removed from the metrics-utility library's `anonymize_rollups()` API first (PR #399 in metrics-utility), and this service-side change followed to clean up the now-dead parameter. When a library removes a parameter, all callers must be updated simultaneously to avoid runtime errors.

### `unified_jobs_dashboard` collector and batched backfill for dashboard_jobs
- **Repo**: ansible/metrics-utility
- **Commits**: b36d893 (#392)
- **What happened**: A `unified_jobs_dashboard` collector was added that extends `unified_jobs` with dashboard-specific fields: `project_id`, `project_name`, `launched_by_id/username` (from `auth_user` join), `label_ids` (via `STRING_AGG` subquery), and `num_hosts` (via `COUNT` subquery). The `dashboard_jobs` collector gained cursor-based pagination support via optional `after_id` and `batch_size` parameters for incremental backfill. New query helpers (`get_min_max_job_id_query`, `get_jobs_batch_query`, `get_job_labels_for_ids_query`, `get_job_host_summaries_for_ids_query`) enable the batched path. A `_JOBS_BASE_SQL` constant was extracted to share the SELECT/JOIN fragment between `get_jobs_query` and `get_jobs_batch_query`, preventing schema drift between the two paths. Partial batch args (`after_id` without `batch_size` or vice versa) now raise `ValueError` instead of silently falling back to full-window queries.
- **Insight**: When adding a batched/paginated variant of an existing query, extract the shared SQL fragment into a constant (`_JOBS_BASE_SQL`) -- otherwise the two paths drift apart when columns are added, causing the dict-building loop to produce different schemas silently.

### Dashboard collection merged into hourly collectors via post_collect_hook
- **Repo**: ansible/metrics-service
- **Commits**: bd760f5 (#210)
- **What happened**: The standalone 6-hourly `daily_dashboard_collection` task was eliminated. Dashboard data now flows through the existing `collect_hourly_metrics` pipeline: `generic_collect_metrics` gained a `post_collect_hook` parameter (and a `post_collect_hook_factory` field in the collector registry). For the `unified_jobs` collector, when `DASHBOARD_COLLECTION` is enabled, the hook serializes job rows and creates a one-off `sync_dashboard_job_records` task via `update_or_create` (safe on retry/concurrent runs). The `unified_jobs_dashboard` collector (from metrics-utility) replaces `unified_jobs` to include dashboard-specific fields (project, launched_by, labels, num_hosts). Initial backfill uses cursor-paginated batches of `BACKFILL_BATCH_SIZE` (default 5,000), with retry resuming from `MAX(job_id)` of already-synced records. Hook exceptions are swallowed (logged + `TaskExecution(status="failed")`) so dashboard failures cannot abort the anonymization rollup pipeline. Records are chunked at 500 per sync task to bound `task_data` blob size. Cleanup retention defaults to `DASHBOARD_COLLECTION.INITIAL_BACKFILL_DAYS`.
- **Insight**: Routing dashboard sync through the existing hourly collector pipeline (via a hook) eliminates a separate DB connection and cron schedule, keeping total Controller DB calls per hour unchanged at 2. The hook pattern is extensible: any collector can register a `post_collect_hook_factory` in the registry to run additional processing on collected data. The key design decision is that hook failures are swallowed, not propagated -- ensuring the primary rollup pipeline is never disrupted by dashboard-specific issues.

### Dashboard test fix: _collect_jobs mocks updated for batch-pagination refactor
- **Repo**: ansible/metrics-service
- **Commits**: 99d80d2 (#244)
- **What happened**: Four tests were still mocking `_collect_jobs` after `_collect_data` was refactored to use `_get_job_id_range` + `_process_batches` (in #210). Without a mock for `_get_job_id_range`, the comparison `while after_id < max_id` raised `TypeError` on `MagicMock` objects. Fixed by patching `_get_job_id_range` to return `(None, None)` instead.
- **Insight**: When refactoring a function's internals (splitting it into sub-functions), all existing mocks for the original function must be audited -- mocks that targeted the old call chain will produce type errors or incorrect behavior on the new sub-function boundaries.

### StorageSegment `host` parameter for mock/test redirection
- **Repo**: ansible/metrics-utility
- **Commits**: df497c3 (#409)
- **What happened**: `StorageSegment` gained a `host` setting that sets `analytics.host` before sending, allowing redirection to a mock Segment server for integration testing. When `host` is `None` (default), the SDK uses its default endpoint (`https://api.segment.io`). The `put()` method now sets `analytics.host = self.host or None` alongside the existing `analytics.sync_mode = True`.
- **Insight**: Adding a `host` override to the Segment storage class is a minimal, non-invasive change that enables full end-to-end testing of the Segment shipping pipeline without modifying the SDK or using monkey-patching.

## Superseded / Semi-Obsolete

### Individual collector files (collect_job_host_summary_hourly.py, etc.)
- **Repo**: ansible/metrics-service
- Replaced in 1580ff2 (#109) by `collect_hourly_metrics` and `collect_snapshot_metrics` with registry-based design. No more individual files per collector type.

### main_host collector (metrics-service)
- **Repo**: ansible/metrics-service
- Removed in 1580ff2 (#109). Not part of the anonymized data chain.

### Inline collection in daily_metrics_rollup (_collect_main_host_data, _collect_config_data, etc.)
- **Repo**: ansible/metrics-service
- Removed in 1580ff2 (#109). All collection now happens via scheduled collector tasks; the rollup only merges pre-collected data.

### _merge_rollup_json and _aggregate_collector_rollups as separate functions
- **Repo**: ansible/metrics-service
- Consolidated into a single `_merge_collects` function in 35c3db5 (#138). The key change was adding the missing `rollup_processor.base()` call after merging.

### Config data included in anonymized payload
- **Repo**: ansible/metrics-service
- The config snapshot was incorrectly mixed into the anonymized data in daily_anonymize_and_prepare. Fixed in 26614c4 (#113) by removing the `anonymized_data["config"] = metrics.get("config", {})` line. Config data stays in the DB (DailyMetricsSummary) but is not transmitted.

### Date included in Segment event name
- **Repo**: ansible/metrics-service
- The event name was `f"Controller Metrics Daily Rollup {todays_date}"` (including the date). Changed to just `"Controller Metrics Daily Rollup"` in 26614c4 (#113).

### Deterministic jitter for send_to_segment (seeded by service_id)
- **Repo**: ansible/metrics-service
- The deterministic jitter from 8d4ae7e (#183) was replaced in f7e2265 (#201) with truly random jitter. The original approach used `random.Random(seed)` where seed came from the installation UUID, meaning the same installation always sent at the same time -- leaking identifiable timing information.

### Salt parameter in anonymize_rollups() / daily_anonymize_and_prepare()
- **Repo**: ansible/metrics-service
- The `salt` parameter was removed in 5e6c8f6 (#215), following the library-side removal in metrics-utility PR #399. The salt was no longer used by the anonymization logic.

### send_to_segment function in apps/tasks/utils.py
- **Repo**: ansible/metrics-service
- Moved to `apps/tasks/collectors/send_anonymized_to_segment.py` in 26614c4 (#113) and enhanced with `segment_meta` parameter for timestamp and message_id.
