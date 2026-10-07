# Documentation of anonymized rollups

The source-derived Segment payload contract, including the metrics-service
production wrapper and the current Segment chunk envelope, is maintained in
[`docs/report-definitions/segment-payload.yaml`](../../docs/report-definitions/segment-payload.yaml)
with its [JSON Schema](../../docs/report-definitions/segment-payload.schema.json).

## 1. Collectors and Rollups

Each collector type has an associated anonymized rollup class that processes the collected data. Collectors are located in `metrics_utility/library/collectors/controller/`, and their corresponding rollup classes are in `metrics_utility/anonymized_rollups/`.

### Collector Types

Collectors fall into three categories:

- **Since-until collectors (time-series)**: These collectors require `since` and `until` parameters and collect data for a specific time range. They run hourly to collect incremental data. But they can be configured to run whatever we want.
- **Snapshot collectors**: These collectors do not require time parameters and collect a point-in-time snapshot of the current state. They run once per day (or whever we want).
- **Daily time-range collectors**: These use a since/until window for the previous day and run once per day.

### Collector List

#### Hourly Time-Series Collectors (since-until)

1. **`unified_jobs`**
   - **Collector**: `metrics_utility/library/collectors/controller/unified_jobs_dashboard.py` in metrics-service (the registry key remains `unified_jobs`)
   - **Rollup**: `metrics_utility/anonymized_rollups/jobs_anonymized_rollup.py` (`JobsAnonymizedRollup`)
   - **Description**: Collects unified job data including job status, duration, execution environment, inventory, organization, ansible version, installed collections, and job template information. Filters jobs by `finished` timestamp within the time range.

2. **`job_host_summary_service`**
   - **Collector**: `metrics_utility/library/collectors/controller/job_host_summary_service.py`
   - **Rollup**: `metrics_utility/anonymized_rollups/jobhostsummary_anonymized_rollup.py` (`JobHostSummaryAnonymizedRollup`)
   - **Description**: Collects job host summary data including task execution statistics (ok, failed, skipped, unreachable, etc.) per job and host. Uses partition-optimized queries for better performance.

3. **`credentials_service`**
   - **Collector**: `metrics_utility/library/collectors/controller/credentials_service.py`
   - **Rollup**: `metrics_utility/anonymized_rollups/credentials_anonymized_rollup.py` (`CredentialsAnonymizedRollup`)
   - **Description**: Collects credential usage data showing which credential types are used in jobs within the time range.

4. **`main_jobevent_service`**
   - **Collector**: `metrics_utility/library/collectors/controller/main_jobevent_service.py`
   - **Rollup**: `metrics_utility/anonymized_rollups/events_modules_anonymized_rollup.py` (`EventModulesAnonymizedRollup`)
   - **Description**: Collects job event data including module usage, collection usage, role usage, and event statistics. This is the largest collector and uses partition-optimized queries.

#### Snapshot Collectors

5. **`execution_environments`**
   - **Collector**: `metrics_utility/library/collectors/controller/execution_environments.py`
   - **Rollup**: `metrics_utility/anonymized_rollups/execution_environments_anonymized_rollup.py` (`ExecutionEnvironmentsAnonymizedRollup`)
   - **Description**: Collects execution environment statistics including count of default and custom execution environments.

6. **`table_metadata`**
   - **Collector**: `metrics_utility/library/collectors/controller/table_metadata.py`
   - **Rollup**: `metrics_utility/anonymized_rollups/table_metadata_anonymized_rollup.py` (`TableMetadataAnonymizedRollup`)
   - **Description**: Collects database table metadata including row counts and table sizes for various system tables. It is used for estimation of how many rows customer can have, and how large those tables are in terms of disc size.

7. **`controller_version_service`**
   - **Collector**: `metrics_utility/library/collectors/controller/controller_version_service.py`
   - **Rollup**: `metrics_utility/anonymized_rollups/controller_version_anonymized_rollup.py` (`ControllerVersionAnonymizedRollup`)
   - **Description**: Collects controller version information showing which versions of the controller are running.

8. **`feature_flags_service`**
   - **Collector**: `metrics_utility/library/collectors/controller/feature_flags_service.py`
   - **Rollup**: `metrics_utility/anonymized_rollups/feature_flags_anonymized_rollup.py` (`FeatureFlagsAnonymizedRollup`)
   - **Description**: Produces the list of enabled platform feature-flag names.

#### Daily Time-Range Collectors (since-until)

9. **`task_executions_service`**
   - **Collector**: `metrics_utility/library/collectors/service/task_executions_service.py`
   - **Rollup**: `metrics_utility/anonymized_rollups/task_executions_anonymized_rollup.py` (`TaskExecutionsAnonymizedRollup`)
   - **Description**: Aggregates collector execution counts and durations from the metrics-service database.

10. **`indirect_managed_nodes`**
    - **Collector**: `metrics_utility/library/collectors/controller/main_indirectmanagednodeaudit.py`
    - **Rollup**: `metrics_utility/anonymized_rollups/indirect_managed_nodes_anonymized_rollup.py` (`IndirectManagedNodesAnonymizedRollup`)
    - **Description**: Aggregates indirect managed nodes by collection/module and strips organization and hostname values in `base()`.

## 2. Rollup Flow

The anonymized rollup process follows a multi-stage flow:

### Hourly Collection

1. **Collection**: Hourly collectors collect one-hour windows (e.g., 10:00-11:00); daily time-range collectors collect the previous full day. This is important, because otherwise we will
not be able to compute data for whole day because of performance.

The data are then processed in batches (see prepare and merge below). Each batch computes basicaly hourly aggregate, which is much much smaller than raw data - it looks like json data with summaries, total counts, total durations...

Those summaries are updated with each batch (result of two hourly aggregates are then aggregated together - this is call rollups - rollups are basicaly hierarchical aggregates). Then this result is again aggregated with another hour and up until whole day.

The daily rollup is sent to the analytics team, who is then further aggregating our daily rollups into monthly and yearly rolups, but this is not part of our metrics utility.

2. **Prepare**: The raw dataframe from the collector is passed to the rollup's `prepare()` method, which:
   - Filters and preprocesses the data (e.g., filtering out unfinished jobs)
   - Performs initial aggregations
   - Returns a serializable dictionary or list (not a dataframe)

3. **Merge**: The result from `prepare()` is merged with the partial daily rollup using the `merge()` method:
   - The partial daily rollup is initially empty (None) for the first hour
   - Each subsequent hour's prepared data is merged into the accumulating daily rollup
   - Both the partial rollup and prepared data are serializable (JSON-compatible) structures
   - The merge operation combines these structures appropriately (e.g., concatenating lists, summing counts)

### Daily Base Processing

4. **Base**: After all hours for the day have been processed, the complete daily rollup is passed to the `base()` method, which:
   - Performs final aggregations and statistics computation if needed
   - Usualy quite short
   - Returns a dictionary with a `json` key containing the final rollup data

### Final Merging

5. **Combination**: All rollup results from `base()` are combined in `anonymized_rollups.py`:
   - Each rollup's `json` output is collected
   - All rollups are merged together using `anonymize_rollups()` function
   - The combined data is flattened into a single structure
   - Sensitive data is anonymized (see section 3)

In production, metrics-service stores the component `base()` results in
`DailyMetricsSummary.aggregated_metrics`, then adds `summary_metadata`,
`dashboard_telemetry`, and `analytics_usage` after `anonymize_rollups()` returns.
The complete source-to-Segment contract is in the linked
[`segment-payload.yaml`](../../docs/report-definitions/segment-payload.yaml).

## 3. Anonymization

After all rollups are merged, the data goes through anonymization:

1. **Content whitelist**: `EventModulesAnonymizedRollup` classifies event-content names using `collections.json`. During final anonymization, module/collection/role statistic entries with `collection_source == 'Custom'` are removed, and installed-collection and indirect collection/module summaries are retained only for known public collections.

2. **Aggregation boundary**: Job, host, and event rollups emit grouped totals rather than raw records. Host IDs may exist in the intermediate daily rollup to calculate unique-host totals, but `flatten_json_report()` does not copy them to the final payload.

   The intermediate event rollup also contains a map keyed by playbook name; the final payload reduces it to `rollup_period_playbooks_total`, a count, and does not include the playbook-name keys.

3. **Sanitization**: Rollup preparation converts NumPy values to native JSON values and replaces NaN/infinity with `None`.

The anonymization ensures that no sensitive customer data (like custom module names, collection names, or job template names) is exposed in the final output.

## 4. Message Splitting

The final anonymized rollup JSON is split into multiple messages for transmission to Segment.com:

1. **Top-level Key Splitting**: Each top-level key in the JSON dictionary becomes a separate message chunk. For example:
   - `statistics` → one chunk
   - `module_stats` → one or more chunks (if it's a list)
   - `jobs_by_job_type` → one or more chunks (if it's a list)

2. **Array Splitting**: If a top-level key contains an array (list), that array is split into multiple chunks if it exceeds the per-event size budget:
   - Maximum complete event size: 32 KiB of JSON (with event-envelope overhead and a safety margin reserved from the data budget)
   - Each chunk contains as many array items as can fit within the size limit
   - Items are never split across chunks

3. **Size Calculation**: The size of each chunk is calculated as compact JSON UTF-8 bytes. Segment request batches are capped at 475,000 bytes.

4. **Dictionary Handling**: If a top-level key contains a dictionary (not a list), it is sent as a single chunk and cannot be split. An oversized dictionary is logged and then fails complete-event size validation; dictionary contents are not divided into smaller objects.

The splitting logic is implemented in `metrics_utility/library/storage/segment.py` in the `_split_into_chunks()` method.

## 5. Testing

To test the anonymized rollup system, use the `run_no_events.py` script:

**Location**: `tools/anonymized_tests/run_no_events.py`

See more in the file itself

