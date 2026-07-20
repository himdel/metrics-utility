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

### Performance testing framework for collectors and rollups
- **Repo**: ansible/metrics-service
- **Commits**: 1d760f4 (#97)
- **What happened**: A performance test framework was added under `metrics_service/tools/performance_tests/`. The `collection_rollup_benchmark_hourly.py` script (332 lines) benchmarks the full metrics pipeline: runs all snapshot collectors once, then runs hourly collectors once per hour for a simulated 24-hour period, then triggers the daily rollup. It tracks wall-clock time and peak RSS memory (via a background `PeakMemoryMonitor` thread polling every 50ms using `psutil`). Test improvements over iterations: replaced in-memory Python loops with database aggregation queries (`Sum`/`Count`), added warm-up calls before baseline measurement, added failed-hours tracking with `*` markers in output, removed gc.disable()/enable() calls, and captured elapsed time even on rollup failure. Results are documented in `RESULTS.md` with small/medium/large dataset runs. `USAGE.md` documents test setup and data expectations.
- **Insight**: The test design mirrors the actual production pipeline (snapshot once, hourly collection 24x, daily rollup) rather than testing collectors in isolation. The `PeakMemoryMonitor` background thread approach (polling RSS every 50ms) captures memory spikes that instantaneous before/after measurements would miss. The `psutil` dependency was added to dev deps in #114 specifically for this.

### Benchmark expanded to report all 12 AWX source tables and fix non-monotonic scaling
- **Repo**: ansible/metrics-service
- **Commits**: d7880ad (#123)
- **What happened**: The benchmark script was updated in two ways: (1) The large dataset previously used non-monotonic scaling dimensions (J=2000, T=500, H=8, where H *decreased* from the medium dataset's H=20), confounding medium-to-large comparisons. Updated to J=2000, T=100, H=40 so all dimensions scale monotonically. (2) The source table reporting was expanded from 4 tables (main_jobevent, main_jobhostsummary, main_host, main_job) to all 12 tables touched by collectors: main_jobevent, main_jobhostsummary, main_host, main_unifiedjob, main_job, main_unifiedjobtemplate, main_inventory, main_organization, main_credential, main_credentialtype, main_unifiedjob_credentials, main_executionenvironment. Table count queries were extracted into a `_TABLE_COUNT_QUERIES` dict and a `_count()` helper, and the `print_source_table_counts()` function was extracted for reusability.
- **Insight**: Non-monotonic scaling dimensions in benchmarks produce misleading results -- if one dimension shrinks while others grow, it's impossible to attribute performance changes to the total dataset size. The expanded source table reporting ensures the benchmark captures the full scope of data that collectors query, making the results more representative of real-world performance.

### API benchmark added for end-to-end collection pipeline testing
- **Repo**: ansible/metrics-service
- **Commits**: e66794b (#150)
- **What happened**: A new `benchmark_api.py` was added under `metrics_service/tools/performance_tests/` that triggers the full collection + rollup pipeline via `POST /api/v1/tasks/schedule_immediate/` and polls `TaskExecution` for completion. Duration is measured from `started_at` to `completed_at` on the execution record (actual execution time, not queue wait). The old `http_benchmark.py` (GET-endpoint latency tests) was replaced. Documentation was restructured: `USAGE.md` became `BENCHMARK_INTERNAL.md`, `RESULTS.md` became `RESULTS_INTERNAL.md`, and new `BENCHMARK_AAP_DEV.md` and `RESULTS_API.md` were added. Results show API benchmark comparable or faster than internal benchmark at small/medium/large scales (e.g., medium: 19.8s API vs 61.4s internal for hourly collection).
- **Insight**: The API benchmark mirrors real-world usage (tasks submitted via REST API, executed by dispatcherd) while the internal benchmark calls collector functions directly. The API benchmark being faster at medium scale (18.3s vs 60.3s for hourly tasks) suggests dispatcherd's worker pool provides better parallelism than the serial internal benchmark. Having both benchmarks validates that the API layer adds negligible overhead.

### Jenkins pipeline benchmark for containerized AIO deployments
- **Repo**: ansible/metrics-service
- **Commits**: a470adf (#173)
- **What happened**: A `benchmark_manage.py` script was added that runs the full collection + rollup pipeline via `manage.py shell` inside the container, for use against Jenkins/production deployments where `ALLOWED_HOSTS=[]` blocks HTTP API access. Step-by-step instructions (`BENCHMARK_JENKINS.md`) and results (`RESULTS_JENKINS.md`) were added. Results across three scales on a containerized AIO Jenkins deployment: Small (5.9s total), Medium (12.1s), Large (20.0s). SonarCloud coverage was configured to exclude `tools/performance_tests/`.
- **Insight**: Having both API-based (`benchmark_api.py`) and manage.py-based (`benchmark_manage.py`) benchmarks covers two deployment scenarios: API benchmarks require network access and configured ALLOWED_HOSTS, while manage.py benchmarks work in locked-down environments. The manage.py approach calls collector functions directly via Django shell, bypassing the dispatcherd worker pool.

### Benchmark script enhanced with memory tracking and output table sizing
- **Repo**: ansible/metrics-service
- **Commits**: 7846d82 (#190)
- **What happened**: `benchmark_manage.py` was significantly expanded (~200 lines added): (1) Each collector now reports peak RSS (MB) alongside duration, using a background thread polling `psutil` every 50ms. (2) Output table sizes: row counts and serialized JSON size for `HourlyMetricsCollection` and `DailyMetricsSummary` are reported. (3) Source table counts: row counts for all AWX tables touched by collectors, directly queried from the AWX DB. (4) Per-hour job breakdown showing how many jobs finished in each of the 24 hours. (5) `main_jobevent_service` was removed from hourly collectors (events disabled for this release). New scaled-up benchmark results files were added.
- **Insight**: Adding memory tracking per collector helps identify which collectors are memory-intensive at scale, enabling targeted optimization. The per-hour job breakdown helps correlate slow collector hours with job activity spikes, making performance debugging more targeted.

### Scaled-up benchmark results at production-like scales
- **Repo**: ansible/metrics-service
- **Commits**: 7846d82 (#190), f10fb0a (#192)
- **What happened**: Benchmark results were collected at four production-like scales on Jenkins AIO deployments: Scale 1 (2,500 jobs x 5 templates), Scale 2 (25,000 x 5), Scale 3 (250,000 x 5), Scale 4 (25,000 x 50). Results documented in `RESULTS_JENKINS_SCALED_UP.md` and `BENCHMARK_JENKINS_SCALED_UP.md`. In #192, benchmarks were re-run with the updated `benchmark_manage.py` script and two additional scales (3 and 4) were added.
- **Insight**: Running benchmarks at multiple scales (3 orders of magnitude difference in job count) reveals non-linear behavior in collectors. Having documented results at known scales provides a baseline for performance regression detection.

### OCP benchmark results: 1.5-2x slower than containerized AIO
- **Repo**: ansible/metrics-service
- **Commits**: 932467a (#206)
- **What happened**: The `benchmark_manage.py` script was run against OCP Jenkins deployments (via `oc exec`) across all four scales. Results documented in `RESULTS_JENKINS_SCALED_UP_OCP.md` and `BENCHMARK_JENKINS_SCALED_UP_OCP.md` (step-by-step runbook for reproducing on OCP, including kubeconfig setup, DB user provisioning, and base64 file transfer since OCP containers lack `tar`). OCP is consistently ~1.5-2x slower in wall-clock time due to cluster network round-trip between metrics-tasks pod and postgres pod (vs localhost in containerized AIO). Memory usage is essentially identical across environments. The benchmark script also gained `django.setup()` before model imports, required for OCP (where the script runs outside `manage.py`) but harmless in containerized environments.
- **Insight**: OCP benchmarks confirmed the network latency hypothesis: the collection pipeline is I/O-bound (DB queries), so the pod-to-pod network hop adds a constant overhead per query. Memory being identical confirms the pipeline doesn't buffer differently based on latency. The `django.setup()` addition is a reminder that scripts run via `oc exec` / `python -c` don't have the Django environment set up by `manage.py`.

### Performance benchmark results moved to handbook
- **Repo**: ansible/metrics-service
- **Commits**: f9c6e49 (#227)
- **What happened**: All 20 benchmark results and documentation files were deleted from `metrics_service/tools/performance_tests/`: 5 `BENCHMARK_*.md` runbooks, 5 `RESULTS_*.md` files, and 10 `results_*_*.txt` raw output files (totaling ~3,700 lines). These were moved to the ansible/handbook repository (PR #1430). The benchmark scripts themselves (`benchmark_manage.py`, `benchmark_api.py`, `collection_rollup_benchmark_hourly.py`) remain in the repo.
- **Insight**: Results files are point-in-time artifacts that belong in documentation/runbook repositories, not in the code repo. Keeping benchmark scripts in the code repo ensures they stay in sync with the codebase, while results are published separately where they can be updated independently and are discoverable by stakeholders who don't browse the code repo.

### Dashboard performance tests: API latency and collection throughput
- **Repo**: ansible/metrics-service
- **Commits**: 17b611b (#224)
- **What happened**: Performance benchmarks were added under `metrics_service/tools/performance_tests/benchmark_dashboard/`. Two scripts: (1) `benchmark_dashboard_api.py` (~258 lines) tests API endpoint latency for dashboard reports with configurable data volumes, measuring response times across filter combinations. (2) `benchmark_dashboard_collection.py` (~442 lines) tests dashboard data collection throughput, including initial backfill and incremental sync, measuring wall-clock time and memory via the existing `PeakMemoryMonitor` pattern. A `fill_data.py` script generates synthetic dashboard data at configurable scales. A consolidated `README.md` documents setup, usage, and expected results.
- **Insight**: Adding separate benchmarks for the dashboard collection pipeline (vs the existing anonymized rollup pipeline benchmarks) acknowledges that these are fundamentally different workloads: the dashboard path does batched cursor-paginated reads from the AWX DB and writes to the local DB, while the rollup path does hourly CSV extraction and JSON aggregation. Each needs its own performance baseline.

### Performance test scripts for events enabled, with job/event limits and richer test data
- **Repo**: ansible/metrics-utility
- **Commits**: 66f0441 (#451)
- **What happened**: The `tools/anonymized_tests/run.py` script (655 lines, new) was created to run the full anonymized rollup pipeline including events, replacing `run_no_events.py` which had events disabled. The script orchestrates: DB data generation, collector runs (unified_jobs, job_host_summary_service, execution_environments, credentials_service, table_metadata, controller_version_service, feature_flags_service, main_jobevent_service), rollup computation, and result validation. The `helpers.py` module was expanded (~500 lines added) with richer DB fill functions that create more realistic event data: multiple organizations, projects, inventories, hosts, job templates, and jobs with varied statuses. Event data now includes diverse event types (runner_on_ok, runner_on_failed, runner_on_skipped, etc.) with realistic event_data JSON containing module names, collection references, role names, and warnings/deprecations. The `fill_perf_db_data.py` was updated with `_insert_data_all()` that creates 4 organizations, multiple templates per org, and varied job outcomes. The `ansible.builtin` collection was added to the whitelist in `collections.json`.
- **Insight**: Performance testing of the events pipeline requires realistically structured event data (multiple orgs, varied event types, nested event_data JSON with collection/role/module references) -- synthetic data with uniform structure doesn't exercise the aggregation, grouping, and anonymization code paths that matter at scale.

### Performance test tools consolidated from metrics-service into metrics-utility
- **Repo**: ansible/metrics-utility
- **Commits**: 5faa1bb (#433)
- **What happened**: Performance test tools (`benchmark_api.py`, `benchmark_manage.py`, `collection_rollup_benchmark_hourly.py`, `benchmark_dashboard_api.py`, `benchmark_dashboard_collection.py`, `fill_data.py`) were moved from the metrics-service repo into `tools/service_perf/` and `tools/dashboard_perf/` in metrics-utility. Path resolution was updated to find `../metrics-service` as a sibling repo for Django settings/imports. The `tools/service_tasks/` directory was moved back to metrics-service since those scripts talk to the service API directly.
- **Insight**: Performance test tools that exercise the metrics-utility library (via the service) belong in the utility repo since they need to evolve alongside collector changes -- but scripts that interact with the service API belong in the service repo.

### Perf harness: realistic events data and indirect node scale tiers
- **Repo**: ansible/metrics-utility
- **Commits**: 44d165c (#484)
- **What happened**: Two improvements to the `tools/anonymized_db_perf_data/` perf harness: (1) The `events` field in synthetic indirect node audit records was populated with realistic Ansible collection module names from three collections with `event_query.yml` in `ee-supported-rhel9`: `cisco.intersight`, `microsoft.ad`, and `vmware.vmware`. Previously `events` was `[]`, causing all synthetic records to fall into the `_no_collection`/`_no_module` buckets, making the test data useless for analytics. (2) `indirect_count` was added to each dataset tier in `run_all_dataset_sizes.py`: small=1K, medium=100K, large=1M. These align with realistic deployment accumulation over weeks, months, and year-plus of indirect node collection. The indirect node collector does a full-table scan with no date filter, so its relevant scale is total accumulated rows rather than rows per time window.
- **Insight**: Performance test data must exercise the code paths that matter at scale -- uniform empty-events data never hits the collection/module grouping and aggregation paths, making the benchmark results unrepresentative of real-world performance. Scale tiers for accumulation-based collectors (no date pruning) should reflect total row count, not per-window row count.

## Superseded / Semi-Obsolete

### http_benchmark.py (GET-endpoint latency tests)
- **Repo**: ansible/metrics-service
- Replaced by `benchmark_api.py` in e66794b (#150). The old HTTP benchmark only tested endpoint response time, not the full collection+rollup pipeline.
