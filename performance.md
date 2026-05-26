# Performance

> Default repo: metrics-service

## Learnings

### Performance testing framework for collectors and rollups
- **Commits**: 1d760f4 (#97)
- **What happened**: A performance test framework was added under `metrics_service/tools/performance_tests/`. The `collection_rollup_benchmark_hourly.py` script (332 lines) benchmarks the full metrics pipeline: runs all snapshot collectors once, then runs hourly collectors once per hour for a simulated 24-hour period, then triggers the daily rollup. It tracks wall-clock time and peak RSS memory (via a background `PeakMemoryMonitor` thread polling every 50ms using `psutil`). Test improvements over iterations: replaced in-memory Python loops with database aggregation queries (`Sum`/`Count`), added warm-up calls before baseline measurement, added failed-hours tracking with `*` markers in output, removed gc.disable()/enable() calls, and captured elapsed time even on rollup failure. Results are documented in `RESULTS.md` with small/medium/large dataset runs. `USAGE.md` documents test setup and data expectations.
- **Insight**: The test design mirrors the actual production pipeline (snapshot once, hourly collection 24x, daily rollup) rather than testing collectors in isolation. The `PeakMemoryMonitor` background thread approach (polling RSS every 50ms) captures memory spikes that instantaneous before/after measurements would miss. The `psutil` dependency was added to dev deps in #114 specifically for this.

### Benchmark expanded to report all 12 AWX source tables and fix non-monotonic scaling
- **Commits**: d7880ad (#123)
- **What happened**: The benchmark script was updated in two ways: (1) The large dataset previously used non-monotonic scaling dimensions (J=2000, T=500, H=8, where H *decreased* from the medium dataset's H=20), confounding medium-to-large comparisons. Updated to J=2000, T=100, H=40 so all dimensions scale monotonically. (2) The source table reporting was expanded from 4 tables (main_jobevent, main_jobhostsummary, main_host, main_job) to all 12 tables touched by collectors: main_jobevent, main_jobhostsummary, main_host, main_unifiedjob, main_job, main_unifiedjobtemplate, main_inventory, main_organization, main_credential, main_credentialtype, main_unifiedjob_credentials, main_executionenvironment. Table count queries were extracted into a `_TABLE_COUNT_QUERIES` dict and a `_count()` helper, and the `print_source_table_counts()` function was extracted for reusability.
- **Insight**: Non-monotonic scaling dimensions in benchmarks produce misleading results -- if one dimension shrinks while others grow, it's impossible to attribute performance changes to the total dataset size. The expanded source table reporting ensures the benchmark captures the full scope of data that collectors query, making the results more representative of real-world performance.

### API benchmark added for end-to-end collection pipeline testing
- **Commits**: e66794b (#150)
- **What happened**: A new `benchmark_api.py` was added under `metrics_service/tools/performance_tests/` that triggers the full collection + rollup pipeline via `POST /api/v1/tasks/schedule_immediate/` and polls `TaskExecution` for completion. Duration is measured from `started_at` to `completed_at` on the execution record (actual execution time, not queue wait). The old `http_benchmark.py` (GET-endpoint latency tests) was replaced. Documentation was restructured: `USAGE.md` became `BENCHMARK_INTERNAL.md`, `RESULTS.md` became `RESULTS_INTERNAL.md`, and new `BENCHMARK_AAP_DEV.md` and `RESULTS_API.md` were added. Results show API benchmark comparable or faster than internal benchmark at small/medium/large scales (e.g., medium: 19.8s API vs 61.4s internal for hourly collection).
- **Insight**: The API benchmark mirrors real-world usage (tasks submitted via REST API, executed by dispatcherd) while the internal benchmark calls collector functions directly. The API benchmark being faster at medium scale (18.3s vs 60.3s for hourly tasks) suggests dispatcherd's worker pool provides better parallelism than the serial internal benchmark. Having both benchmarks validates that the API layer adds negligible overhead.

### Jenkins pipeline benchmark for containerized AIO deployments
- **Commits**: a470adf (#173)
- **What happened**: A `benchmark_manage.py` script was added that runs the full collection + rollup pipeline via `manage.py shell` inside the container, for use against Jenkins/production deployments where `ALLOWED_HOSTS=[]` blocks HTTP API access. Step-by-step instructions (`BENCHMARK_JENKINS.md`) and results (`RESULTS_JENKINS.md`) were added. Results across three scales on a containerized AIO Jenkins deployment: Small (5.9s total), Medium (12.1s), Large (20.0s). SonarCloud coverage was configured to exclude `tools/performance_tests/`.
- **Insight**: Having both API-based (`benchmark_api.py`) and manage.py-based (`benchmark_manage.py`) benchmarks covers two deployment scenarios: API benchmarks require network access and configured ALLOWED_HOSTS, while manage.py benchmarks work in locked-down environments. The manage.py approach calls collector functions directly via Django shell, bypassing the dispatcherd worker pool.

### Benchmark script enhanced with memory tracking and output table sizing
- **Commits**: 7846d82 (#190)
- **What happened**: `benchmark_manage.py` was significantly expanded (~200 lines added): (1) Each collector now reports peak RSS (MB) alongside duration, using a background thread polling `psutil` every 50ms. (2) Output table sizes: row counts and serialized JSON size for `HourlyMetricsCollection` and `DailyMetricsSummary` are reported. (3) Source table counts: row counts for all AWX tables touched by collectors, directly queried from the AWX DB. (4) Per-hour job breakdown showing how many jobs finished in each of the 24 hours. (5) `main_jobevent_service` was removed from hourly collectors (events disabled for this release). New scaled-up benchmark results files were added.
- **Insight**: Adding memory tracking per collector helps identify which collectors are memory-intensive at scale, enabling targeted optimization. The per-hour job breakdown helps correlate slow collector hours with job activity spikes, making performance debugging more targeted.

### Scaled-up benchmark results at production-like scales
- **Commits**: 7846d82 (#190), f10fb0a (#192)
- **What happened**: Benchmark results were collected at four production-like scales on Jenkins AIO deployments: Scale 1 (2,500 jobs x 5 templates), Scale 2 (25,000 x 5), Scale 3 (250,000 x 5), Scale 4 (25,000 x 50). Results documented in `RESULTS_JENKINS_SCALED_UP.md` and `BENCHMARK_JENKINS_SCALED_UP.md`. In #192, benchmarks were re-run with the updated `benchmark_manage.py` script and two additional scales (3 and 4) were added.
- **Insight**: Running benchmarks at multiple scales (3 orders of magnitude difference in job count) reveals non-linear behavior in collectors. Having documented results at known scales provides a baseline for performance regression detection.

## Superseded / Semi-Obsolete

### http_benchmark.py (GET-endpoint latency tests)
- Replaced by `benchmark_api.py` in e66794b (#150). The old HTTP benchmark only tested endpoint response time, not the full collection+rollup pipeline.
