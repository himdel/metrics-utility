# Performance

### Build report skips unnecessary CSV extraction based on requested sheets
- **Repo**: ansible/metrics-utility
- **Commits**: 5cc7fb5 (#86), 0320d20 (#91)
- **What happened**: The `process_tarballs()` method was optimized to only read CSV files that are needed by the report sheets configured in `METRICS_UTILITY_OPTIONAL_CCSP_REPORT_SHEETS`. A `CSV_SHEETS` dict maps each CSV type to the sheets that need it (e.g., `main_jobevent` is only needed for `usage_by_collections`, `usage_by_roles`, `usage_by_modules`, `usage_by_organizations`). The `csv_enabled()` method checks if any of the CSV's dependent sheets are in the requested sheet list. Previously, all four CSV types were always extracted and parsed regardless of which sheets were requested.
- **Insight**: For large datasets with millions of jobevent rows, skipping jobevent CSV parsing when only generating a `managed_nodes` sheet provides a major speedup -- the optimization is especially important as the number of collected CSV types grows (now four: job_host_summary, main_host, main_indirectmanagednodeaudit, main_jobevent).

### Job host summary SQL optimized with CTE to avoid repeated host variable parsing
- **Repo**: ansible/metrics-utility
- **Commits**: 97fb590 (#151)
- **What happened**: The job_host_summary collector's SQL query originally joined `main_host` directly in the main SELECT and parsed host variables (JSON/YAML `ansible_host`, `ansible_connection`) for every `main_jobhostsummary` row. When a host appeared in many job runs, the same variables were re-parsed for each row. The fix introduced two CTEs: `filtered_hosts` (gets DISTINCT host IDs matching the time window) and `hosts_variables` (parses variables once per unique host). The main query then joins against `hosts_variables` instead of `main_host`, parsing each host's variables exactly once regardless of how many job host summary rows reference it.
- **Insight**: When a query joins to a table for expensive per-row computation (like YAML/JSON parsing), and the join key has many duplicates, extracting the computation into a CTE with DISTINCT eliminates redundant work proportional to the duplication factor.

### Tarball filtering by collection name avoids extracting unneeded data
- **Repo**: ansible/metrics-utility
- **Commits**: 3b28731 (#227)
- **What happened**: Building on the tarball naming change (#226), the extraction pipeline now filters at two levels: (1) `filter_tarball_paths()` uses regex to skip tarballs whose filename suffix doesn't match any requested collection, and (2) `_safe_extract()` accepts an `enabled_set` parameter to skip extracting CSV/JSON files whose basename doesn't match. Each dataframe engine passes its needed collections (e.g., `DataframeContentUsage` requests `['main_jobevent']` only). This means a CCSPv2 report building the `managed_nodes` sheet no longer downloads or extracts jobevent tarballs, and vice versa. The optimization is backward-compatible: tarballs without collection name suffixes (pre-0.7.0 format) are always included.
- **Insight**: Two-level filtering (skip tarballs by filename, then skip files within tarballs by basename) provides a significant I/O reduction -- especially for S3 where each skipped tarball avoids a network download. This extends the earlier sheet-based CSV filtering (#86) to also filter at the tarball level.

### Anonymized rollup event processing optimized: early filtering, vectorized extraction, column pruning
- **Repo**: ansible/metrics-utility
- **Commits**: 07cd17c (#250)
- **What happened**: The `EventModulesAnonymizedRollup.prepare()` was optimized in several ways: (1) Event filtering by type (`runner_on_ok`, `runner_on_failed`, etc.) was moved to the start of `prepare()`, before any column assignments, reducing the DataFrame size before expensive operations. (2) Collection name extraction was changed from `apply(extract_collection_name)` (row-by-row Python) to `str.extract(regex, expand=False)` (vectorized), which is significantly faster on large DataFrames. (3) After all column assignments, the DataFrame is pruned to only the columns needed for aggregation, freeing memory from unused source columns. (4) The `collections.json` lookup is now loaded once in `__init__` instead of re-read from disk in every `prepare()` call. (5) Some grouping operations were moved into the `prepare()` phase so they run per-batch before merging, rather than on the full merged DataFrame.
- **Insight**: For large event datasets, vectorized pandas string operations (`str.extract`) are orders of magnitude faster than `apply()` with a Python function -- and early filtering + column pruning compound the savings by reducing the data volume before subsequent operations.

### Service event query optimized with hourly range-based partition pruning and CROSS JOIN LATERAL
- **Repo**: ansible/metrics-utility
- **Commits**: f9ee5d9 (#284)
- **What happened**: The `main_jobevent_service` collector previously built a literal `(job_id, job_created) IN (VALUES ...)` clause with potentially 100K+ timestamp/ID pairs. This was replaced with a two-pronged approach: (1) `job_created` timestamps are truncated to hourly boundaries, consecutive hours are grouped into ranges, and these ranges form `OR` clauses (e.g., `job_created >= '10:00' AND job_created < '13:00'`) that PostgreSQL's partition pruning can use as literal values. (2) A separate `job_id IN (...)` clause filters by unique job IDs. Additionally, the `event_data` JSON parsing was moved from inline `replace(e.event_data, ...)::jsonb` repeated in every SELECT column to a single `CROSS JOIN LATERAL (SELECT replace(e.event_data, ...)::jsonb AS event_data) AS ed`, computing the expensive JSON cast once per row instead of once per column.
- **Insight**: PostgreSQL partition pruning requires literal timestamp values in WHERE clauses -- it cannot prune from joins or subqueries. Grouping timestamps into hourly ranges (matching partition boundaries) reduces 100K literals to ~100 range conditions while still enabling pruning. The CROSS JOIN LATERAL pattern avoids redundant per-column computation of expensive casts. **Supersedes** the literal VALUES-based approach from #214.

### Event type filtering pushed to SQL WHERE clause instead of pandas
- **Repo**: ansible/metrics-utility
- **Commits**: 1444b50 (#311)
- **What happened**: The `main_jobevent_service` collector previously fetched all event types from the database and filtered to relevant ones (`runner_on_ok`, `runner_on_failed`, `runner_on_skipped`, etc.) during pandas processing in `EventModulesAnonymizedRollup.prepare()`. The filter was moved to the SQL WHERE clause as `e.event IN ('runner_on_ok', ...)`, reducing the number of rows transferred from the database and parsed into DataFrames.
- **Insight**: Filtering by event type at the SQL level rather than after extraction avoids transferring irrelevant rows (like `playbook_on_start`, `debug`, etc.) that can represent a significant fraction of the jobevent table. Always push filtering as close to the data source as possible.

### Event batch processing restructured: task categorization moved to prepare phase, host_ids as sets
- **Repo**: ansible/metrics-utility
- **Commits**: 26aa64a (#312)
- **What happened**: The `EventModulesAnonymizedRollup` was restructured to move task status categorization (clean_success, success_with_reruns, failed, etc.) from `base()` (after all batches merged) into `prepare()` (per-batch). This means status booleans are computed on smaller DataFrames and then summed during merge, rather than being computed once on the full merged DataFrame. Additionally, the aggregation was changed from per-host tracking (`host_id` column with `nunique()`) to a `host_ids` set column that gets unioned during aggregation via `lambda x: set().union(...)`. The categorical column casting in `base()` was removed since early aggregation in `prepare()` already reduces cardinality. A two-level groupby was added in `prepare()`: first by (job, host, task, module, collection) then by (job, task, module, collection), aggregating host data into sets.
- **Insight**: Moving categorization to `prepare()` enables pre-aggregation per batch, reducing the DataFrame size before the final `base()` merge. Using `host_ids` as sets instead of relying on `nunique()` after concatenation preserves correct host counts across batches -- `nunique()` after `pd.concat` would double-count hosts that appear in multiple batches for the same task.

