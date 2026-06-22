# Testing
### CCSPv2 report test pattern: subprocess + openpyxl validation
- **Repo**: ansible/metrics-utility
- **Commits**: bcac18e (#41), 647eb28 (#55)
- **What happened**: The first CCSPv2 test (PR #41) ran `manage.py build_report` via `subprocess.run` with env vars set, then validated the generated XLSX file. Initially it used `pandas.read_excel` / `pd.ExcelFile` to check sheet names and column headers. PR #55 switched to `openpyxl.load_workbook` for deeper validation: checking not just column headers but also cell values, formulas (like `=SUM(J7:J12)`), and the "Usage Reporting" sheet's non-standard header row (starts at row 6). The expected data structure changed from flat lists of column names to a list of dicts mapping column name to expected column values.
- **Insight**: openpyxl is better than pandas for XLSX report testing because it preserves formulas as strings (pandas evaluates them), allows reading specific rows, and doesn't reinterpret cell types.

### CCSP test added with shared conftest helpers
- **Repo**: ansible/metrics-utility
- **Commits**: 9685afa (#60)
- **What happened**: A CCSP report test was added alongside the existing CCSPv2 test. Common validation functions (`validate_sheet_tab_names`, `validate_sheet_columns`, `normalize_column`) and the `cleanup` fixture were extracted into `metrics_utility/test/ccspv_reports/conftest.py` to avoid duplication between the two test files.
- **Insight**: When adding a second report type test with the same validation pattern, extract shared helpers into conftest early to keep tests DRY.

### Snapshot testing framework for CCSP/CCSPv2 reports
- **Repo**: ansible/metrics-utility
- **Commits**: cb614cf (#56)
- **What happened**: A snapshot test framework was introduced under `metrics_utility/test/snapshot_tests/`. It generates reports with various env var combinations (3 sets of company names, prices, SKUs; multiple month ranges and since/until pairs) and compares them against stored reference files. A `CCSP_snapshot_generator.py` creates snapshot definition JSON files containing env vars, CLI params, and metadata. The snapshot utilities handle report generation, comparison, and storage. Reports needed to be made deterministic (no random elements) for snapshot comparison to work.
- **Insight**: Snapshot tests catch unintended changes in complex XLSX report output, but require report generation to be deterministic -- random values or timestamps in output break the pattern.

### Complex CCSPv2 test validates cell values across all content-usage sheets
- **Repo**: ansible/metrics-utility
- **Commits**: 0577e90 (#70), 438cd8b (#67)
- **What happened**: A `complex_test_CCSPv2.py` was added that validates not just sheet structure but actual cell values across all five CCSPv2 content sheets (managed nodes, usage by organizations/collections/roles/modules). The test uses a new `validate_column()` conftest helper that reads a specific column from a named sheet and compares expected values cell-by-cell. It uses `pytest.approx` for floating-point duration values. PR #67 added the complex test data tarballs with multiple organizations, hosts, collections, and roles.
- **Insight**: Cell-level validation across all sheets catches aggregation bugs (wrong sums, incorrect grouping) that sheet-structure-only tests miss -- the `validate_column` helper makes this concise without raw openpyxl boilerplate.

### CI pytest workflow with PostgreSQL and MinIO services
- **Repo**: ansible/metrics-utility
- **Commits**: b6879b0 (#71), e37e7c2 (#72), edfe31c (#74)
- **What happened**: A complete CI test infrastructure was built in three steps: (1) PR #71 created a `docker-compose.yaml` in `tools/docker/` with PostgreSQL (initialized from AWX schema dump), MinIO (S3-compatible storage), and a metrics-utility runner container. The AWX schema files were moved from `metrics_utility/test/test_data/schemas/awx/` to `tools/docker/`. (2) PR #72 created a `pytest.yml` GitHub Actions workflow that installs PostgreSQL and MinIO natively (not via Docker) on the runner, imports the schema, creates MinIO buckets/users, and runs pytest with S3 credentials via env vars. (3) PR #74 actually enabled pytest execution (it was commented out as `env # pytest` in PR #72) and fixed all the paths. The workflow uses `timeout-minutes` on wait steps to avoid hanging if services fail to start.
- **Insight**: The CI was built incrementally -- first docker-compose for local dev, then native services in GitHub Actions (faster than Docker-in-Docker), then actually enabling the test runner after paths were fixed -- reflecting the reality that CI test infrastructure often needs multiple iterations to get right.

### Test paths migrated from hardcoded /awx_devel to relative paths
- **Repo**: ansible/metrics-utility
- **Commits**: edfe31c (#74)
- **What happened**: All CCSP/CCSPv2 tests had hardcoded paths like `/awx_devel/awx-dev/metrics-utility/metrics_utility/test/test_data` for both `METRICS_UTILITY_SHIP_PATH` and output file paths. These were changed to relative paths (`./metrics_utility/test/test_data`). Test files were also renamed from `complex_test_CCSPv2.py` to `test_complex_CCSPv2.py` so pytest autodiscovery would find them (pytest requires `test_` prefix by default). Snapshot definition JSON files also had their paths updated.
- **Insight**: Tests with hardcoded absolute paths from a specific developer's environment silently pass in that environment but fail everywhere else -- use relative paths and ensure files follow pytest's `test_` naming convention for discovery.

### Gather tests for directory and S3 ship targets
- **Repo**: ansible/metrics-utility
- **Commits**: d5d1028 (#85), 968b4c8 (#88)
- **What happened**: Integration tests were added for the `gather_automation_controller_billing_data` command with both `directory` and `s3` ship targets. The directory test runs gather with `--ship --until=10m --force`, then verifies tarballs were created at the expected path using a glob. The S3 test does the same but ships to a MinIO bucket. The tests require PostgreSQL with AWX schema and (for S3) a running MinIO instance. The mock_awx DB host was made configurable via `METRICS_UTILITY_DB_HOST` env var to support both `localhost` (CI) and `postgres` (Docker Compose). The CI workflow patches mock_awx settings via `sed` to match the CI database credentials.
- **Insight**: Gather integration tests need a real database with the AWX schema, not just mock data -- the collectors run actual SQL queries against Controller tables, so the schema must exist even if the tables are empty.

### Dual-mode test execution (internal + external) for coverage
- **Repo**: ansible/metrics-utility
- **Commits**: 21f9c67 (#95)
- **What happened**: A `metrics_utility/test/util.py` module was introduced with four test runner functions: `run_build_ext`/`run_gather_ext` (subprocess-based) and `run_build_int`/`run_gather_int` (direct Python import). The `_ext` variants take `(env_dict, args_list)` and run `manage.py` as a subprocess. The `_int` variants take `(env_dict, options_dict)`, call `prepare()` to set up mock_awx, import the Command class, and call it directly within a `temporary_env` context manager. Every test was updated to run in both modes. The `prepare()` function was extracted from `manage()` in `metrics_utility/__init__.py` so tests can initialize the AWX mock environment without running the full management utility.
- **Insight**: Subprocess-based tests (`_ext`) don't contribute to pytest-cov coverage because they run in a separate process -- running the same tests via direct Python import (`_int`) captures the coverage, effectively doubling test value without writing new test logic.

### pull_request_target workflow needs explicit head ref checkout
- **Repo**: ansible/metrics-utility
- **Commits**: aefaebb (#106), e5d8a7d (#93)
- **What happened**: The pytest workflow was changed from `pull_request` to `pull_request_target` trigger (in #89/#93) so that SonarCloud could access the `CICD_ORG_SONAR_TOKEN_CICD_BOT` repository secret. However, `pull_request_target` checks out the base branch by default, not the PR branch. PR #106 fixed this by adding `ref: ${{ github.event.pull_request.head.ref }}` and `repository: ${{ github.event.pull_request.head.repo.full_name }}` to the checkout step, ensuring the PR's actual code is tested.
- **Insight**: When switching a GitHub Actions workflow from `pull_request` to `pull_request_target` to access secrets, you must explicitly configure the checkout action to use the PR head ref -- otherwise you test the base branch code, not the PR changes.

### Exhaustive empty-data test for all report type + sheet combinations
- **Repo**: ansible/metrics-utility
- **Commits**: 9978da2 (#118)
- **What happened**: A `test_empty_data_for_CCSP_and_CCSPv2.py` test was added that runs `build_report` for every combination of report type (CCSP, CCSPv2), date range (data exists, empty folder, empty CSVs, mixed), and optional sheet. This catches crashes from `None` dataframes, empty DataFrames with wrong columns, and edge cases in sheet-building code. The test uses `run_build_int` for coverage and `pytest.mark.parametrize` over sheets and date ranges. Empty test data tarballs (with `config.json` and empty CSVs) were added under `test_data/data/2025/04/`.
- **Insight**: Testing every combination of report type, date range (including empty), and optional sheet is essential because the report builders have many conditional branches that only fail on specific combinations -- a single happy-path test misses these.

### Collection coverage gap detection tested with cell-level validation
- **Repo**: ansible/metrics-utility
- **Commits**: da5075e (#115)
- **What happened**: The `test_complex_CCSPv2.py` test was extended with `validate_data_collection_status()` which validates the "Data collection status" sheet's two tables (missing gaps and raw status). The test parses the sheet by finding the first empty row (gap between tables), then uses `pandas.read_excel` with `nrows` and `skiprows` to load each table separately. The expected data includes specific gap timestamps and durations, validating that the boundary gap detection (from report interval start to first collection, and from last collection to interval end) works correctly.
- **Insight**: Testing multi-table sheets requires splitting by empty rows -- `pandas.read_excel(skiprows=N)` combined with `nrows` enables validating each table independently within a single sheet.

### Test data SQL scripts for host_metrics and job_host_summary added for Docker/CI
- **Repo**: ansible/metrics-utility
- **Commits**: 77490ef (#133), d26e163 (#143)
- **What happened**: SQL scripts were added to populate test databases with realistic data: (1) PR #133 added `tools/docker/main_hostmetric.sql` with 10 sample rows for the `main_hostmetric` table, loaded both in Docker Compose (via init scripts) and CI (via `cat ... | psql`). A `make populate_host_metrics` target was added for manual use. The Docker Compose init scripts were renamed with numeric prefixes (`init-0-roles.sql`, `init-1-schema.sql`, `init-2-hostmetric.sql`) to ensure execution order. (2) PR #143 added `tools/docker/main_jobhostsummary.sql` with a PL/pgSQL block that creates a full hierarchy (organization, inventory, instance, hosts, unified job template, project, job template, unified jobs, main jobs, and job host summaries) -- all inter-referencing entities needed for the gather collector's SQL queries. A `make populate_job_host` target was added.
- **Insight**: Test data SQL scripts that create the full entity hierarchy (org -> inventory -> host -> job template -> job -> job_host_summary) are essential for integration-testing the gather collector, which joins across all these tables.

### prepare() moved from test/util.py to test/conftest.py for correct import ordering
- **Repo**: ansible/metrics-utility
- **Commits**: 55e15a5 (#132)
- **What happened**: The `prepare()` call (which sets up `sys.path` to include `mock_awx/`) was originally at module level in `metrics_utility/test/util.py`. This caused issues because `prepare()` needs to run before any test module imports code that transitively imports `awx` -- but `util.py` is only imported when a test actually uses its helpers. Moving it to `metrics_utility/test/conftest.py` ensures it runs as the very first thing when pytest collects any test in the test directory, before any test modules are imported.
- **Insight**: Module-level side effects that must happen before other imports belong in `conftest.py`, not in utility modules -- conftest is loaded by pytest before test modules are collected, guaranteeing import ordering.

### `temporary_env` context manager now supports key removal via None values
- **Repo**: ansible/metrics-utility
- **Commits**: 75a83bc (#129)
- **What happened**: The `temporary_env` helper in `test/util.py` was updated to support removing env vars by passing `None` as the value. Previously it just called `os.environ.update(new_env)`, which doesn't remove keys. Now it iterates the dict: keys with `None` values are removed via `os.environ.pop(k, None)`, and others are set normally. This was needed for S3 env var validation tests that need to ensure certain vars are unset.
- **Insight**: A test utility for env var manipulation should support both setting and unsetting variables -- use `None` as a sentinel for "remove this key" to keep the API simple.

### Renewal guidance unit tests: query methods and interval calculations
- **Repo**: ansible/metrics-utility
- **Commits**: 3e559cf (#130), 01a23c6 (#138)
- **What happened**: Two sets of unit tests were added for the `ReportRenewalGuidance` class: (1) PR #130 tests `df_managed_nodes_query` and `df_deleted_managed_nodes_query` methods with mocked dataframes, verifying correct filtering of deleted/non-deleted/ephemeral hosts. It uses a `generate_renewal_guidance_dataframe()` helper in `test/util.py` that creates 10 hardcoded test hosts covering each scenario (non-deleted, deleted, ephemeral boundary cases). (2) PR #138 tests the `get_intervals()` sliding window method that generates time intervals for ephemeral host classification. The tests validate window count, window progression (each starts 1 day after the previous), boundary precision (microsecond-level), and edge cases (single day, range smaller than interval, year boundary crossing).
- **Insight**: Testing the renewal guidance report's query/filtering and interval logic with mocked data (rather than full integration tests) enables fast, deterministic validation of the complex ephemeral classification logic.

### Parameter validation tests for build_report and gather date/ephemeral arguments
- **Repo**: ansible/metrics-utility
- **Commits**: f2b5a83 (#128)
- **What happened**: Comprehensive parameter validation was added for `--since`, `--until`, `--month`, and `--ephemeral` arguments. New exception classes were introduced (`DateFormatError`, `MissingRequiredParameter`, `BadParameter`). A `handle_month()` helper was extracted from `build_report._handle_month()` into `helpers.py` with strict `strptime('%Y-%m')` validation (previously used the permissive `dateutil.parser.parse`). Regex patterns (`SINCE_AND_UNTIL_BUILD_PATTERN`, `SINCE_AND_UNTIL_GATHER_PATTERN`, `ALLOWED_EPHEMERAL_PATTERN`) enforce format constraints. The `build_report` command's `handle` method was split into `handle` (catches exceptions, logs, exits) and `_handle` (actual logic), matching the gather command's existing pattern. A `test_extra_params_validation.py` test file validates error messages for invalid inputs. `--until` now defaults to today when `--since` is provided without `--until`.
- **Insight**: Splitting command `handle` into a public wrapper (exception handling + exit codes) and private `_handle` (logic) enables tests to call `_handle` directly and assert on raised exceptions rather than catching `SystemExit`.

### Shared test fixtures extracted to root conftest.py for renewal guidance tests
- **Repo**: ansible/metrics-utility
- **Commits**: 4cfb21f (#139), 3e559cf (#130)
- **What happened**: Fixtures that were initially defined locally in individual test files (`fixed_now`, `setup_processed_dataframe`) were extracted to `metrics_utility/test/conftest.py` so they could be shared across `test_renewal_guidance_query_methods.py` and the new `test_build_spreadsheet_method.py`. The `setup_processed_dataframe` fixture mocks `DBDataframeHostMetric`'s extractor to provide consistent data for all renewal guidance tests. The `test_build_spreadsheet_method.py` adds mock-heavy tests for the `build_spreadsheet()` method, verifying that sheets are created, dedup is called, and ephemeral-related sheets are conditionally included.
- **Insight**: When multiple test files need the same mock data setup, promote fixtures to the nearest shared conftest.py early to avoid duplicated fixture definitions that drift apart.

### Gather integration test validates collected CSV content row-by-row
- **Repo**: ansible/metrics-utility
- **Commits**: 0816f67 (#144), e65b320 (#145)
- **What happened**: An integration test was added that runs gather with `--ship --since=2025-06-12 --until=2025-06-14` against test data, then opens the produced tarball, finds `job_host_summary.csv`, and compares each line against expected values. The test validates column headers, row count, and exact field values (host names, org names, timestamps). The SQL test data script had to be updated from `NOW()` to fixed timestamps (#145) because `NOW()` produced timestamps outside the gather time window, causing empty CSVs.
- **Insight**: Gather integration tests that validate CSV content line-by-line require fixed timestamps in test data -- any use of `NOW()` or dynamic timestamps in SQL scripts will cause the test to be flaky or empty depending on when it runs.

### Broken test tarballs moved to separate directory
- **Repo**: ansible/metrics-utility
- **Commits**: fb2e0a5 (#158)
- **What happened**: Test data tarballs that were intentionally broken (missing config.json, empty CSVs, corrupt data) were mixed in with valid test data under `test/test_data/data/`. The `test_empty_data_for_CCSP_and_CCSPv2.py` test used these broken tarballs but they could interfere with other tests. They were moved to `test/ccspv_reports/empty-data/data/` with a README explaining their purpose.
- **Insight**: Intentionally broken test data should be isolated in a clearly labeled directory -- mixing it with valid test data risks other tests accidentally reading corrupt files.

### Renewal guidance integration test: end-to-end gather + build_report
- **Repo**: ansible/metrics-utility
- **Commits**: 8164b5f (#159)
- **What happened**: A full integration test was added that (1) inserts host metric data via SQL (expanding `main_hostmetric.sql` from 10 to ~30 rows with realistic data covering deleted hosts, ephemeral hosts, and various automation patterns), (2) runs gather to collect the data, (3) runs `build_report` with `RENEWAL_GUIDANCE` report type, and (4) validates the generated XLSX output. The test is currently `@pytest.mark.skip` because it requires the host metric SQL data to be fully representative.
- **Insight**: End-to-end integration tests that span gather + build_report are valuable for renewal guidance because the report reads from the same DB as gather -- any schema mismatch or column mismatch between what gather collects and what the report expects will be caught.

### Gather test: compare CSV fields by position, ignoring auto-generated IDs
- **Repo**: ansible/metrics-utility
- **Commits**: 8164b5f (#159)
- **What happened**: The initial gather test (#144) compared full CSV lines including auto-generated database IDs. But IDs from `SERIAL` columns are not stable across test runs (they depend on insertion order and previous test runs). The fix changed the comparison to ignore the ID column by comparing fields by position, skipping the `id` field.
- **Insight**: Integration tests that validate database-generated content should not assert on auto-increment IDs -- these are not stable across runs, especially when multiple tests insert data into the same database.

### Test conftest helpers promoted from ccspv_reports to root test directory
- **Repo**: ansible/metrics-utility
- **Commits**: 8164b5f (#159)
- **What happened**: The `validate_sheet_tab_names`, `validate_sheet_columns`, `normalize_column`, `validate_column`, and `cleanup` fixtures were moved from `metrics_utility/test/ccspv_reports/conftest.py` to `metrics_utility/test/conftest.py` so they could be shared with the new renewal guidance integration test. The ccspv_reports conftest was deleted entirely. This was needed because the renewal guidance test validates XLSX output the same way as CCSP tests.
- **Insight**: When a new test category needs the same validation helpers as an existing one, promote shared fixtures to the nearest common conftest.py -- don't duplicate them across sibling directories.

### Renewal guidance integration test unskipped after data fixes
- **Repo**: ansible/metrics-utility
- **Commits**: 4e01001 (#161), d3c2e9b (#163)
- **What happened**: The renewal guidance end-to-end integration test (from #159) was initially `@pytest.mark.skip` because the host metric SQL data needed to be finalized. PR #161 unskipped it after fixing the test data (removing a host that made assertions unreliable, reducing `diff_months` from 2000 to 500 to stay within gather limits). PR #163 further fixed the SQL insertion to use `public.main_hostmetric` table explicitly and adjusted test expectations. The test validates the full pipeline: SQL data -> gather -> build_report -> XLSX validation.
- **Insight**: End-to-end integration tests that depend on specific SQL test data often need multiple iterations to get the data right -- skipping with a clear reason and unskipping in a follow-up PR is a reasonable workflow.

### Invalid/corrupted data handling test for CCSP reports
- **Repo**: ansible/metrics-utility
- **Commits**: 5c94421 (#169)
- **What happened**: A `test_invalid_data_for_CCSP_and_CCSPv2.py` test was added that runs `build_report` with intentionally broken/empty data against every combination of report type (CCSP, CCSPv2), date range, and optional sheet. Unlike the empty-data test (#118) which checks that empty-but-valid data doesn't crash, this test uses the `empty-data` directory with potentially malformed JSON, missing columns, and invalid dates, verifying the report code doesn't raise exceptions even with corrupted input.
- **Insight**: Testing with invalid/malformed data (not just empty data) catches a different class of bugs -- JSON parse errors in facts fields, missing columns during aggregation, and type errors from unexpected null values.

### Collector unit tests using mock for ProgrammingError scenarios
- **Repo**: ansible/metrics-utility
- **Commits**: 376352b (#172)
- **What happened**: Unit tests were added for `main_indirectmanagednodeaudit_table` using `unittest.mock` to mock `_copy_table` and `get_optional_collectors`. The tests cover: successful execution, collector not in optional list, `ProgrammingError` when table doesn't exist (AAP 2.4), query format verification, and specific error message content. Mock objects with `isoformat()` methods stand in for datetime parameters.
- **Insight**: Collector functions that run raw SQL against potentially missing tables need mock-based unit tests that simulate `ProgrammingError` -- these can't be tested in integration because CI always has the full schema.

### CCSP deduplication integration test with numbered test cases
- **Repo**: ansible/metrics-utility
- **Commits**: afc880a (#166)
- **What happened**: A comprehensive CCSPv2 deduplication integration test was added (`test_complex_CCSPv2_with_canonical_facts.py`, ~2500 lines) that validates dedup behavior across numbered test cases (1.1-5.x). Each case represents a specific dedup scenario: (1) ansible_host dedup, (2) serial-based dedup, (3) multi-region hosts, (4) NAT scenarios, (5) edge cases. The test uses input CSV files with carefully crafted canonical_facts (product_serial, machine_id, ansible_host, ansible_port) and validates the output XLSX cell-by-cell using dict comparisons per sheet. A conftest fixture mocks `validation.now` to make report dates deterministic.
- **Insight**: Numbering dedup test cases (1.1, 2.3, 3.1...) with descriptive names in comments makes it possible to trace a failing assertion back to the specific dedup scenario it represents, which is critical when the test file is thousands of lines long.

### Unused imports accumulated rapidly and needed cleanup
- **Repo**: ansible/metrics-service
- **Commits**: d828d60
- **What happened**: A dedicated commit removed unused imports from 7 test files in one pass: `json`, `TestCase`, `patch`, `Mock`, `ValidationError`, multiple model imports, and command class imports. These had accumulated over just a few days of development.
- **Insight**: Rapid development with copy-paste between test files leads to import bloat. Running ruff's `F401` rule (unused imports) as part of CI catches this automatically -- which is exactly what happened when ruff was later added to CI.

### Test fixtures configured Django settings via conftest.py
- **Repo**: ansible/metrics-service
- **Commits**: e64f482
- **What happened**: `tests/conftest.py` was updated to configure Django settings in test fixtures, ensuring `DJANGO_SETTINGS_MODULE` is set before any Django imports happen.
- **Insight**: With split settings, tests need to explicitly set which settings module to use. This was later handled by `pyproject.toml`'s `[tool.pytest.ini_options]` with `DJANGO_SETTINGS_MODULE`.

### Test coverage setup included both XML and HTML reports
- **Repo**: ansible/metrics-service
- **Commits**: ee93077
- **What happened**: pytest was configured to generate both XML coverage reports (for SonarCloud upload) and the default terminal output. The CI runs `uv run pytest -s -v --cov=. --cov-report=xml`.
- **Insight**: Using `--cov=.` (coverage of everything) in CI means third-party code in `.venv` could be measured too unless properly excluded. The later configuration switched to explicit module coverage (`--cov=apps --cov=metrics_service`).

### Service collector integration tests validate CSV content per collector type
- **Repo**: ansible/metrics-utility
- **Commits**: 0c851b4 (#214)
- **What happened**: Integration tests were added for the new service collectors (`unified_jobs`, `job_host_summary_service`, `main_jobevent_service`, `execution_environments`) in `test_gather_jobs_events_summaries_service.py`. Each test runs gather with the appropriate collector enabled via `METRICS_UTILITY_OPTIONAL_COLLECTORS`, then opens the produced tarballs, finds the specific CSV by filename, and compares header and row values against expected data. A `validate_csv_in_tarballs()` helper iterates through tarballs to find the matching CSV, supports skipping auto-generated columns (like IDs) via `skip_columns_names`, and provides detailed assertion messages showing expected vs actual values per cell. The `SafeTarFile` context manager from existing gather tests was reused.
- **Insight**: When testing multiple collector types that each produce separate tarballs, a shared `validate_csv_in_tarballs()` helper that searches across tarballs by CSV filename avoids duplicating the tarball-opening and CSV-parsing boilerplate per test.

### Massive test expansion in the task refactor commit
- **Repo**: ansible/metrics-service
- **Commits**: c6947ce (#14)
- **What happened**: The big refactor commit added 15+ new test files in one PR, including `test_access_control_mixin.py`, `test_api_views_extended.py`, `test_base_views_comprehensive.py`, `test_core_permissions.py`, `test_core_utils.py`, `test_dashboard_views.py`, `test_final_coverage.py`, `test_init_service_id_command.py`, `test_metrics_service_command.py`, `test_run_dispatcherd_comprehensive.py`, `test_tasks_api_comprehensive.py`, `test_tasks_views_extended.py`, and `test_urls_basic.py`. Some empty test files were also committed (`test_models_extended.py`, `test_task_management_extended.py`, `test_tasks_utils.py`).
- **Insight**: Committing empty test files suggests a "placeholder" approach to test planning, but it also creates noise. The test coverage went from minimal to 35%+ in a single commit, which makes reviewing test quality difficult. Several tests were later commented out or removed in follow-up commits within the same PR.

### Some tests committed commented out
- **Repo**: ansible/metrics-service
- **Commits**: c6947ce (#14)
- **What happened**: One of the squashed commit messages is literally "Commenting out tests." Some test classes and methods were wrapped in comments or skipped to get the CI passing, with the intention of fixing them later.
- **Insight**: Commenting out tests to get CI green is a red flag -- it hides real failures. Using `@pytest.mark.skip(reason="...")` is better because it's visible in test reports. The commented-out tests were partially restored in edb4626 (#25).

### Anonymized rollup unit tests validate aggregation logic with crafted DataFrames
- **Repo**: ansible/metrics-utility
- **Commits**: 6f8c0a8 (#215)
- **What happened**: Unit tests were added for all four anonymized rollup classes under `metrics_utility/test/library/`. The event modules test (`test_events_modules_anonymized_rollups.py`, ~355 lines) creates a detailed DataFrame with specific event types (runner_on_ok, runner_on_failed, runner_on_skipped, etc.) and validates the two-phase aggregation: task-level collapse (success/failure/skip classification) then module-level and collection-source-level statistics. The jobs test validates duration/waiting time calculations and template-level aggregations. Tests use string timestamps that get coerced by `pd.to_datetime(..., utc=True)` in `prepare_data()`, and guard against negative durations (where finished < started).
- **Insight**: Anonymized rollup tests benefit from hand-crafted DataFrames with known expected aggregation results rather than loading from CSV files -- this makes the test assertions self-documenting and independent of external test data files.

### Tests reorganized into subdirectories by domain
- **Repo**: ansible/metrics-service
- **Commits**: edb4626 (#25)
- **What happened**: Tests under `tests/unit/` were moved into subdirectories: `tests/unit/api/`, `tests/unit/core/`, `tests/unit/dashboard/`, `tests/unit/general/`, and `tests/unit/tasks/`. Each subdirectory got an `__init__.py` file. Existing test files were moved without renaming (e.g., `test_api_views.py` moved from `tests/unit/` to `tests/unit/api/`). Many new test files were added for the new service layer and task system components.
- **Insight**: The subdirectory organization mirrors the app structure, making it easy to find tests for a specific component. The 80% coverage target was achieved in this commit, with comprehensive tests for the new service layer classes.

### Library storage integration tests for Directory and S3
- **Repo**: ansible/metrics-utility
- **Commits**: eaf3748 (#246)
- **What happened**: Integration tests were added for `StorageDirectory` and `StorageS3` in `metrics_utility/test/library/`. The directory test validates `put()` (with dict=, filename=, and fileobj= modes), `get()` (context manager yielding temp path), `exists()`, `remove()`, and `glob()`. The S3 test uses the existing MinIO instance from CI and validates the same operations against real S3-compatible storage. Both tests use `pytest.raises` to verify error cases (e.g., put with no data arguments). The S3 test uses a pid-based prefix to avoid conflicts with other tests using the same MinIO bucket.
- **Insight**: Using a pid-based S3 key prefix (`test-{os.getpid()}/`) prevents test data collisions when the same MinIO bucket is shared across multiple test suites running in CI.

### End-to-end anonymized rollup test: gather -> rollup -> anonymize -> validate JSON
- **Repo**: ansible/metrics-utility
- **Commits**: 2e9e826 (#239), 6ea3a3f (#247)
- **What happened**: An integration test (`test_from_gather_to_json.py`) was added that runs the full anonymized rollup pipeline: (1) runs `gather` with service collectors against the mock DB, (2) calls `compute_anonymized_rollup_from_raw_data()` on the collected tarballs, (3) validates the resulting JSON structure and values. The test uses `pytest.approx` for float comparisons in duration/timing fields, validates that unfinished jobs (where `finished` is null) are filtered out before duration computation, and checks that the anonymization correctly hashes unknown-source module/collection names while preserving known ones. The `save_rollups` parameter was added to `compute_anonymized_rollup_from_raw_data()` so tests can skip writing rollup files to disk.
- **Insight**: End-to-end integration tests for the rollup pipeline are essential because the pipeline spans multiple stages (collect -> extract -> aggregate -> anonymize) with different data formats at each boundary -- unit tests on individual rollup classes miss format mismatches between stages.

### Collector helper functions tested with mock database connection
- **Repo**: ansible/metrics-utility
- **Commits**: d005629 (#242)
- **What happened**: Unit tests were added for the new database helper functions (`get_config_and_settings_from_db`, `get_last_entries_from_db`, `get_controller_version_from_db`, `datetime_hook`) in `test_automation_controller_billing_helpers.py`. The tests mock `django.db.connection` to simulate various database responses: successful retrieval, empty results, and `DatabaseError` exceptions. The `datetime_hook` tests verify that datetime strings in JSON are correctly parsed to `datetime` objects with UTC timezone. An integration test validates that all helper functions work together with realistic data.
- **Insight**: When replacing ORM calls with raw SQL, the new code paths need their own unit tests since the ORM layer's error handling (e.g., returning None for missing rows) is no longer provided automatically -- each edge case (empty results, missing keys, database errors) must be explicitly handled and tested.

### Test database switched from SQLite in-memory to PostgreSQL
- **Repo**: ansible/metrics-service
- **Commits**: c8e5f0d (#36)
- **What happened**: `metrics_service/settings/test.py` was rewritten to use PostgreSQL instead of SQLite in-memory (`:memory:`). The `DisableMigrations` class hack was removed, migrations now run normally against PostgreSQL, and `--reuse-db` was added to pytest default options. The test database name was changed from `test_metrics_service` to `metrics_service` in both the CI workflow and Django settings. The `TEST.NAME` is set to `None` to let Django auto-generate test database names.
- **Insight**: Running tests against SQLite was causing divergence from production behavior (e.g., different constraint handling, no LISTEN/NOTIFY). The switch to PostgreSQL with `--reuse-db` (pytest-django feature) minimizes the performance penalty by reusing the test database between runs. The `DisableMigrations` trick was needed for SQLite speed but is counterproductive with PostgreSQL since schema must match production.

### Test settings INSTALLED_APPS aligned with production
- **Repo**: ansible/metrics-service
- **Commits**: c8e5f0d (#36)
- **What happened**: The test settings `INSTALLED_APPS` was updated to include `DAB_APPS` (which was previously missing) and added several third-party apps that the test config was missing (`rest_framework.authtoken`, `drf_spectacular`, `corsheaders`, `social_django`). This aligned the test installed apps with the production `defaults.py` config.
- **Insight**: Tests running with a different set of installed apps than production can pass even when production would fail (e.g., missing URL routes, missing middleware, missing model registrations). Aligning the test `INSTALLED_APPS` prevents this class of bugs.

### _create_task_safely pattern to suppress Django signals in tests
- **Repo**: ansible/metrics-service
- **Commits**: a044bd7 (#54)
- **What happened**: Tests were refactored to use a `_create_task_safely()` helper method instead of `Task.objects.create()`. The helper creates a `Task` instance, sets `task._skip_signals = True`, then calls `task.save()`. This was applied across 5 test files (api, task_system, tasks_comprehensive, tasks_utils, tasks_views). Some tests also gained `@pytest.mark.django_db(transaction=True)` where actual DB interactions with signal-driven side effects were being tested.
- **Insight**: The `post_save` signal on the Task model (added in edb4626 #25) automatically routes tasks to dispatcherd when created. In tests, this causes failures because dispatcherd isn't running. The `_skip_signals` attribute is a convention where the signal handler checks for it and skips processing. The pattern is duplicated as a method on each test class rather than being a shared fixture/utility, which is pragmatic but introduces repetition.

### METRICS_UTILITY_AVAILABLE patching pattern for testing without optional dependency
- **Repo**: ansible/metrics-service
- **Commits**: 7b39f53 (#56)
- **What happened**: Integration tests for collector tasks patch `METRICS_UTILITY_AVAILABLE` (a module-level boolean in `tasks_collector.py`) to control whether the metrics-utility library appears available. Combined with the `None` fallback attributes for collector objects, this allows tests to exercise both the "library available" and "library not available" code paths without actually installing the dependency.
- **Insight**: For optional dependencies that may not be present in CI, defining a module-level availability flag and providing `None` fallbacks allows comprehensive testing. The flag can be patched per-test to exercise error handling paths.

### Redundant django.setup() removed from test files -- conftest handles it
- **Repo**: ansible/metrics-service
- **Commits**: 78fdf9f (#61)
- **What happened**: `tests/test_common.py` had a `setup_django_for_tests()` function that manually configured Django settings (with `settings.configure()`, `sys.path.insert`, and `django.setup()`). Both `test_coverage.py` and `test_simple.py` imported and called this function at module level. Since `conftest.py` already handles Django setup (and pytest-django sets `DJANGO_SETTINGS_MODULE`), these manual setups were redundant. The function was deleted and the import/calls removed from both test files.
- **Insight**: Having redundant Django setup code is a maintenance burden and can cause subtle issues if the manual `settings.configure()` conflicts with the pytest-django setup. When using pytest-django with `DJANGO_SETTINGS_MODULE` in `pyproject.toml`, no test file should ever call `settings.configure()` or `django.setup()` manually. The conftest.py is the single source of truth for test environment setup.

### Developer mode must be enabled in test settings
- **Repo**: ansible/metrics-service
- **Commits**: dbf6fb1 (#65)
- **What happened**: When `DEVELOPER_MODE_ENABLED` was added (defaulting to `False`) to gate the tasks API and dashboard, `DEVELOPER_MODE_ENABLED = True` was added to `test.py` settings. Without this, all task API tests would get 403 Forbidden responses and fail.
- **Insight**: Any new feature gate or permission check that defaults to restrictive must be explicitly enabled in test settings. Forgetting this causes mass test failures that are confusing because the tests "used to work." Adding a dedicated test for the disabled case (as was done with `test_developer_mode_permissions.py`) verifies the gate works without breaking the rest of the suite.

### Large test reorganization for metrics collection
- **Repo**: ansible/metrics-service
- **Commits**: 3a58426 (#79)
- **What happened**: A significant test reorganization accompanied the metrics collection feature: old test files were renamed or replaced (e.g., `test_models_edge_cases.py` -> `test_models.py`), deprecated test files were removed (e.g., `test_tasks_collector_complete_coverage.py`, `test_tasks_comprehensive.py`, `test_task_retry_bug.py`), and new comprehensive test files were added (`test_tasks_collector_advanced.py`, `test_tasks_collector_full_coverage.py`, `test_tasks_system.py`, `test_tasks_api_views.py`, `test_v1_base_serializers.py`, `test_v1_urls.py`, `test_mixins.py`). New conftest fixtures were added for task creation and scheduler mocking.
- **Insight**: The PR's 28 squashed commits show that tests were written iteratively during development, with multiple rounds of "fix tests" commits. This pattern of writing tests alongside feature code in a large PR makes it hard to review test quality. The conftest fixtures for task creation centralize what was previously duplicated across test classes.

### Tests use override_settings(MODE="development") for dev-gated endpoints
- **Repo**: ansible/metrics-service
- **Commits**: 7db9971 (#87)
- **What happened**: When `DEVELOPER_MODE_ENABLED` was replaced by `settings.MODE == "development"` for gating the tasks API and dashboard, tests switched from `DEVELOPER_MODE_ENABLED = True` in test settings to `@override_settings(MODE="development")` on individual test methods. This was necessary because `METRICS_SERVICE_MODE=test` is set in CI, and tests shouldn't globally override MODE.
- **Insight**: Using `@override_settings` per-test is more precise than setting a global test setting. It documents which tests depend on development mode and doesn't affect tests that should work in non-development mode. The test file `test_developer_mode_permissions.py` was renamed to `test_development_mode_permissions.py` to match the new terminology.

### Massive test cleanup removed 2000+ lines of obsolete tests
- **Repo**: ansible/metrics-service
- **Commits**: e137d39 (#92)
- **What happened**: Over 2000 lines of test code were removed for deleted functions, models, and classes: tests for CronManager, ServiceConfig, SystemInitializer, TaskManager services; tests for TaskDependency, TaskChain, TaskChainMembership models; tests for deleted utility functions (get_count_safely, trigger_dependent_tasks, schedule_next_occurrence); tests for deleted mixins (TimestampMixin, mark_started, mark_completed); tests for deleted task functions (collect_single_collector, full_process, etc.). Test files for removed service classes were deleted entirely. The test suite went from 842 tests with import errors to 794 passing tests with 0 skips. Also fixed multiple bugs found during cleanup: typo in Task.retry() (`cronjob_expression` -> `cron_expression`), router registration order in tasks/v1/urls.py, and `test_cron_scheduler.py` merged with `test_unified_scheduler.py` (36+17 tests -> 58 deduplicated).
- **Insight**: This demonstrates the cost of not cleaning up tests alongside code changes. The obsolete tests had accumulated over multiple PRs, creating import errors and silent failures. The router registration order bug (TaskViewSet's catch-all pattern matching `/tasks/executions/` as a detail view with pk='executions') was discovered by un-skipping tests that had been skipped to work around it.

### Dashboard collector tests use mock cursor with column description pattern
- **Repo**: ansible/metrics-utility
- **Commits**: 5b26fc3 (#341)
- **What happened**: Tests for the new dashboard collectors (`test_collectors_dashboard.py`, `test_queries_dashboard.py`) were added under `metrics_utility/test/library/dashboard/`. The collector tests mock `db.cursor()` as a context manager with `__enter__`/`__exit__` returning `mock_cursor`, then set `mock_cursor.description` to column name tuples and `mock_cursor.__iter__` to return rows. This pattern enables testing the `dict(zip(columns, row))` construction without a real database. The query tests validate SQL structure by checking for expected clauses (`WHERE`, `JOIN`, `ORDER BY`) and column names. The `dashboard_jobs` test patches the internal helper functions (`_dashboard_job_labels`, `_dashboard_job_host_summaries`) to provide controlled test data for the composition logic.
- **Insight**: When testing collectors that use `cursor.execute()` + `cursor.description` + `cursor.__iter__()` (rather than pandas `read_sql`), the mock pattern requires setting `description` as a list of single-element tuples (matching DB API 2.0 spec) and `__iter__` as an iterator over row tuples -- this mirrors how psycopg3 cursor iteration actually works.

### Gather CSV tests updated for removed columns after job_host_summary_service simplification
- **Repo**: ansible/metrics-utility
- **Commits**: 457f4a2 (#347)
- **What happened**: After removing `ansible_host_variable` and `ansible_connection_variable` columns from the `job_host_summary_service` collector, the integration test `test_gather_jobs_events_summaries_service.py` had to update all expected CSV lines. The header line lost two columns, and every data line lost two field values. The existing test for `metrics_utility_is_valid_json` and `metrics_utility_parse_yaml_field` SQL function usage was renamed from `test_job_host_summary_service_uses_yaml_json_functions` to `test_job_host_summary_service_doesnt_yaml_json_functions` and its assertions were inverted (`assert 'metrics_utility_is_valid_json' not in query`).
- **Insight**: When removing columns from a collector, update both the header and every data line in integration test CSV expectations -- the line-by-line comparison pattern means even a single missing comma will cause a mismatch.

### `utcdt()` test helper for concise UTC datetime creation
- **Repo**: ansible/metrics-utility
- **Commits**: 04e583a (#353)
- **What happened**: A `utcdt(s)` helper was added to `metrics_utility/test/util.py` that parses ISO date/datetime strings as UTC, defaulting to UTC when no timezone is given. It replaced verbose `datetime(2025, 6, 15, tzinfo=timezone.utc)` calls across 8 test files. The helper uses `datetime.fromisoformat()` and attaches `timezone.utc` when no tzinfo is present, supporting both date-only (`utcdt("2025-06-15")`) and datetime (`utcdt("2025-06-15T10:00:00")`) inputs.
- **Insight**: A one-line test utility that converts strings to timezone-aware datetimes eliminates the most common test boilerplate in a codebase where every collector and test needs UTC datetimes -- it also makes tests more readable by replacing multi-argument constructors with ISO strings.

### Massive coverage push: 25% to 89.4% with tests/coverage/ directory
- **Repo**: ansible/metrics-service
- **Commits**: 651db2b (#217)
- **What happened**: 38 test files were added under `tests/coverage/` (organized into `core/`, `tasks/`, `dashboard_reports/`, `dynamic_settings/`, `general/` subdirectories) containing 617+ targeted unit tests. Coverage improved from 25% to 89.4%, crossing the `fail_under=80` threshold in `pyproject.toml`. Key infrastructure changes: `apps/settings/test.py` defaults `DATABASES__default__HOST` to `127.0.0.1` (explicit IPv4 -- macOS resolves `localhost` to IPv6 first, which fails for Docker-mapped postgres ports); `settings.local.py` applies the same fix for local dev; `tests/coverage` added to pytest `testpaths`. Four Sonar exclusions were added for untestable boilerplate: `asgi.py`, `wsgi.py`, `test_urls.py`, and `metrics_service/settings.py`. The PR went through 13 iterative commits fixing CI hangs (mocking `time.sleep` in management command tests, restoring signal handlers after tests), lint violations (83 auto-fixes via ruff), weak assertions (removing `or True` tautologies, using specific exception types), and CodeRabbit review feedback.
- **Insight**: The IPv4-vs-IPv6 issue (`localhost` resolving to `::1` on macOS while Docker postgres only listens on `127.0.0.1`) is a common cross-platform testing pitfall. Explicitly defaulting to `127.0.0.1` in test settings avoids it. The iterative fix-up cycle (13 commits in one PR) shows the cost of a massive coverage push -- each round of CI reveals new issues (test hangs, lint violations, assertion weaknesses) that couldn't be caught locally.

### Regression tests for pandas 3.0 NaN behavior in dedup and extraction
- **Repo**: ansible/metrics-utility
- **Commits**: 3fc4c25 (#431)
- **What happened**: Two categories of tests were added for the pandas 3.0 upgrade: (1) `test_dataframe_main_jobevent.py` (~390 lines) covering `extract_collection_name`, `extract_role_name`, `prepare`, `group`, `regroup`, and the `add_raw`/`from_tarballs` integration path, with explicit `float('nan')` cases for the `isinstance(x, str)` guard. (2) Two regression tests in `TestDedupCCSP`: `test_df_to_mapping_nan_float_serials` verifies that `float('nan')` serials don't cause unrelated hosts to merge (the bug where `bool(float('nan'))` is `True`), and `test_df_to_mapping_empty_string_serials` verifies that empty strings are also filtered out. Both tests construct DataFrames with intentionally broken serial data and assert that hosts with invalid serials are not merged together and that no NaN keys appear in the mapping dict.
- **Insight**: When fixing a behavioral change in a core dependency (pandas NaN semantics), always add regression tests that use the exact problematic value (`float('nan')`) as input -- these tests document the bug and prevent reintroduction if the guard logic is refactored.

### CRC billing provider params contract test
- **Repo**: ansible/metrics-utility
- **Commits**: d55fe33 (#401)
- **What happened**: A contract test was added for `handle_crc_ship_target()` that verifies the function produces the exact dict shape (`billing_provider`, `billing_account_id`, `red_hat_org_id`) that the gather command embeds in `config.json` tarballs. The test validates both the happy path (AWS provider with all env vars set) and the error path (missing `METRICS_UTILITY_BILLING_ACCOUNT_ID` raises `MissingRequiredEnvVar`). This catches regressions where the dict keys or validation logic change.
- **Insight**: Contract tests that verify the shape of data passed between subsystems (validation output -> config.json embedding) catch integration bugs that unit tests on either side miss -- the test asserts on the dict structure, not just that the function doesn't throw.

### Comprehensive test coverage expansion across CLI pipeline
- **Repo**: ansible/metrics-utility
- **Commits**: 9b17dd8 (#405)
- **What happened**: ~1,870 lines of new tests were added across 7 files covering previously untested CLI pipeline components: `test_automation_controller_billing_helpers_pure.py` (pure-function helpers without DB), `test_dataframe_content_usage.py` (content usage dataframe engine), `test_dataframe_engine_base.py` (base dataframe engine logic: casting, merging, multipart handling), `test_extract_base.py` (tarball extraction: safe_extract security, filter_tarball_paths, CSV selection), `test_factories.py` (DataframeFactory, ExtractorFactory, ReportFactory, ReportSaverFactory), and `test_report_base.py` (report base class: sheet building, formula generation, column formatting). This significantly improved coverage of the build_report pipeline.
- **Insight**: Factory classes and base classes in the build_report pipeline had been tested only indirectly through integration tests -- adding unit tests for factories (verifying correct class selection per report type and ship target) and base classes (verifying sheet building, formulas, and column formatting) catches configuration-level bugs that integration tests miss.

### JSON schema validation tests: generate tarballs and validate against versioned schemas
- **Repo**: ansible/metrics-utility
- **Commits**: eb4bcfd (#428)
- **What happened**: Integration tests in `test_json_schema.py` were added that run `gather` to produce tarballs, extract specific files (manifest.json, config.json, data_collection_status.csv, job_host_summary.csv, total_workers_vcpu.json), and validate each against versioned JSON schemas using `jsonschema.validate()`. The manifest drives schema version selection -- `manifest.get('config.json')` returns the version string used to load `config-{version}.jsonschema`. For CSV files (data_collection_status, job_host_summary), rows are read via `csv.DictReader` and validated as JSON objects. A custom `validate_with_datetime` function extends jsonschema's type checker to recognize ISO datetime strings via `datetime.fromisoformat()`. Schema loading uses `importlib.resources.files('metrics_utility.schemas')` for pip-installable path resolution.
- **Insight**: Using `csv.DictReader` to convert CSV rows to dicts enables validating them against JSON schemas -- this bridges the gap between CSV-based collector output and JSON Schema-based contracts without converting the actual data format.

### Candlepin v2 test coverage: 2,974+ lines across 5 test files
- **Repo**: ansible/metrics-utility
- **Commits**: 7833eda (#363)
- **What happened**: The Candlepin v2 feature was delivered with comprehensive test coverage across 5 new test files totaling ~2,974 lines: `test_candlepin_client.py` (648 lines, covering check-in, cert regeneration, consumer registration, org discovery, proxy handling, TLS verification, temp PEM file lifecycle), `test_candlepin_lifecycle.py` (516 lines, covering cert validity checks including not-yet-valid certs, renewal orchestration, renewal days config validation, CA auto-detection), `test_candlepin_store.py` (351 lines, covering LocalCandlepinStore atomic writes/is_writable, DBCandlepinStore with AWX ORM mock and decrypt_field), `test_candlepin_validation.py` (699 lines, covering DB-first cert loading, AWX seeding, billing provider params, registration credential resolution), and `test_candlepin_manage.py` (361 lines, covering the management command). Additionally, `test_package_crc.py` (399 lines) was added for PackageCRC mTLS shipping. Tests mock the AWX ORM via `patch.dict(sys.modules, ...)` to inject fake `awx.main.models` and `awx.main.utils.encryption` modules, then set `decrypt_field` return values per test.
- **Insight**: When testing code that depends on AWX models and encryption (which are not available as a test dependency), mocking entire modules via `patch.dict(sys.modules, ...)` is more maintainable than trying to install AWX -- it isolates the test from AWX internals and makes the mock boundary explicit.

### IndirectManagedNodesAnonymizedRollup tested with crafted DataFrames
- **Repo**: ansible/metrics-utility
- **Commits**: 87c6925 (#446)
- **What happened**: Unit tests (109 lines) were added for `IndirectManagedNodesAnonymizedRollup` covering: `managed_node_type = INDIRECT` tagging on all records, empty DataFrame handling (returns `{}`), timestamp-to-ISO conversion, NaN-to-None conversion, ID column string conversion, and correct `rollup_name` and `collector_names` attributes. Tests follow the established pattern of constructing small DataFrames with known values and asserting on the transformed output.
- **Insight**: Rollup tests are straightforward because the `BaseAnonymizedRollup` pattern isolates each rollup's logic in `prepare()` -- a few targeted tests per rollup type are sufficient to verify the transformation without integration-level complexity.

### Subprocess test env standardized: no __pycache__, UTC timezone, UTF-8 locale
- **Repo**: ansible/metrics-utility
- **Commits**: ec24d69 (#419)
- **What happened**: Test subprocesses in `_run_ext` and snapshot tests were getting a bare env with only test-specific vars, leaving `__pycache__` dirs scattered across the tree and inheriting inconsistent locale/timezone settings. A shared `_SUBPROCESS_BASE_ENV` dict was added to `metrics_utility/test/util.py` with `PYTHONDONTWRITEBYTECODE=1`, `TZ=UTC`, and `LANG=en_US.UTF-8`. Both `_run_ext()` and `run_snapshot_definition()` now merge this base env before test-specific vars. The previously included `AWX_LOGGING_MODE=stdout` was dropped since nothing in the repo reads it (carried over from when tests ran inside the Controller container).
- **Insight**: Test subprocesses should get a minimal, controlled environment rather than inheriting the parent process's env or getting a bare env with only test vars -- this prevents locale-dependent behavior differences and stale artifacts like `__pycache__` directories.

### Mock Segment server for end-to-end Segment integration testing
- **Repo**: ansible/metrics-utility
- **Commits**: df497c3 (#409)
- **What happened**: A mock Segment HTTP server was added in Go (`tools/mock-segment-server/main.go`) that accepts any POST, returns `{"success":true}`, and stores captured requests in memory. It exposes `GET /requests` (return all captured POSTs as JSON array) and `GET /reset` (clear state). The existing `test_from_gather_to_json.py` integration test was extended to send the computed anonymized rollup JSON to the mock server via `StorageSegment(write_key='test-key', host=MOCK_SEGMENT_URL)`, then assert that the correct number of chunked track events were received with the expected event name, artifact name, and chunk metadata. The `StorageSegment` class gained a `host` setting (passed through to `analytics.host`) to allow redirecting to the mock. CI was updated to build and start the Go server before pytest, and a Docker Compose service was added for local dev. The mock server was initially written in Python but replaced with Go for reliability.
- **Insight**: Testing the full Segment shipping path (chunking, event structure, metadata) requires an actual HTTP server that captures requests -- mocking the analytics SDK at the Python level would miss chunking bugs and HTTP-level issues. Using Go for the mock server keeps it simple, fast, and dependency-free.

### Test patches for DeveloperModeRequired removed with RBAC migration
- **Repo**: ansible/metrics-service
- **Commits**: be9e010 (#253)
- **What happened**: Multiple test files that patched `apps.core.permissions.DeveloperModeRequired.has_permission` to return `True` (or used `@override_settings(MODE="development")`) for tasks API and dashboard report access were simplified. The patches were removed and tests now make plain API calls, since `IsSystemAdminOrAuditor` uses standard RBAC authentication (the test fixtures already create admin users). Dashboard-specific tests (`test_url_for_*`, `test_dashboard_view_*`) were deleted along with the `apps/dashboard/` app. The unused `api_client` and `org_member_rd` test fixtures were also removed.
- **Insight**: Switching from a mode-based permission to an RBAC-based permission simplifies tests because the test user fixtures already satisfy RBAC requirements -- no more patching or mode overriding needed for every endpoint test.

## Superseded / Semi-Obsolete

### Tests in tests/unit/ alongside tests/test_*.py
- **Repo**: ansible/metrics-service
- The early test structure had both `tests/unit/` subdirectory tests and top-level `tests/test_*.py` files. In edb4626 (#25), tests were reorganized into `tests/unit/{api,core,dashboard,general,tasks}/` subdirectories.

### SQLite in-memory test database
- **Repo**: ansible/metrics-service
- The `"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"` test config and the `DisableMigrations` class were removed in c8e5f0d (#36). Tests now use PostgreSQL with `--reuse-db`.

### _create_task_safely pattern to suppress signals
- **Repo**: ansible/metrics-service
- The `_skip_signals` workaround from a044bd7 (#54) is no longer needed after signals were removed in 85d2cbb (#57). Tests now use plain `Task.objects.create()`.

### Manual setup_django_for_tests() in test files
- **Repo**: ansible/metrics-service
- Removed in 78fdf9f (#61). The conftest.py and pytest-django handle Django setup; no test file should call `django.setup()` manually.

### DEVELOPER_MODE_ENABLED = True in test settings
- **Repo**: ansible/metrics-service
- Replaced in 7db9971 (#87) by per-test `@override_settings(MODE="development")`. Then fully eliminated in be9e010 (#253) when the tasks API switched to `IsSystemAdminOrAuditor` RBAC -- tests no longer need any mode override for task endpoint access.
