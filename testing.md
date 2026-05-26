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

### Test paths migrated from hardcoded /awx_devel to relative paths
- **Repo**: ansible/metrics-utility
- **Commits**: edfe31c (#74)
- **What happened**: All CCSP/CCSPv2 tests had hardcoded paths like `/awx_devel/awx-dev/metrics-utility/metrics_utility/test/test_data` for both `METRICS_UTILITY_SHIP_PATH` and output file paths. These were changed to relative paths (`./metrics_utility/test/test_data`). Test files were also renamed from `complex_test_CCSPv2.py` to `test_complex_CCSPv2.py` so pytest autodiscovery would find them (pytest requires `test_` prefix by default). Snapshot definition JSON files also had their paths updated.
- **Insight**: Tests with hardcoded absolute paths from a specific developer's environment silently pass in that environment but fail everywhere else -- use relative paths and ensure files follow pytest's `test_` naming convention for discovery.

### CI pytest workflow with PostgreSQL and MinIO services
- **Repo**: ansible/metrics-utility
- **Commits**: b6879b0 (#71), e37e7c2 (#72), edfe31c (#74)
- **What happened**: A complete CI test infrastructure was built in three steps: (1) PR #71 created a `docker-compose.yaml` in `tools/docker/` with PostgreSQL (initialized from AWX schema dump), MinIO (S3-compatible storage), and a metrics-utility runner container. The AWX schema files were moved from `metrics_utility/test/test_data/schemas/awx/` to `tools/docker/`. (2) PR #72 created a `pytest.yml` GitHub Actions workflow that installs PostgreSQL and MinIO natively (not via Docker) on the runner, imports the schema, creates MinIO buckets/users, and runs pytest with S3 credentials via env vars. (3) PR #74 actually enabled pytest execution (it was commented out as `env # pytest` in PR #72) and fixed all the paths. The workflow uses `timeout-minutes` on wait steps to avoid hanging if services fail to start.
- **Insight**: The CI was built incrementally -- first docker-compose for local dev, then native services in GitHub Actions (faster than Docker-in-Docker), then actually enabling the test runner after paths were fixed -- reflecting the reality that CI test infrastructure often needs multiple iterations to get right.

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

### prepare() moved from test/util.py to test/conftest.py for correct import ordering
- **Repo**: ansible/metrics-utility
- **Commits**: 55e15a5 (#132)
- **What happened**: The `prepare()` call (which sets up `sys.path` to include `mock_awx/`) was originally at module level in `metrics_utility/test/util.py`. This caused issues because `prepare()` needs to run before any test module imports code that transitively imports `awx` -- but `util.py` is only imported when a test actually uses its helpers. Moving it to `metrics_utility/test/conftest.py` ensures it runs as the very first thing when pytest collects any test in the test directory, before any test modules are imported.
- **Insight**: Module-level side effects that must happen before other imports belong in `conftest.py`, not in utility modules -- conftest is loaded by pytest before test modules are collected, guaranteeing import ordering.

### Renewal guidance unit tests: query methods and interval calculations
- **Repo**: ansible/metrics-utility
- **Commits**: 3e559cf (#130), 01a23c6 (#138)
- **What happened**: Two sets of unit tests were added for the `ReportRenewalGuidance` class: (1) PR #130 tests `df_managed_nodes_query` and `df_deleted_managed_nodes_query` methods with mocked dataframes, verifying correct filtering of deleted/non-deleted/ephemeral hosts. It uses a `generate_renewal_guidance_dataframe()` helper in `test/util.py` that creates 10 hardcoded test hosts covering each scenario (non-deleted, deleted, ephemeral boundary cases). (2) PR #138 tests the `get_intervals()` sliding window method that generates time intervals for ephemeral host classification. The tests validate window count, window progression (each starts 1 day after the previous), boundary precision (microsecond-level), and edge cases (single day, range smaller than interval, year boundary crossing).
- **Insight**: Testing the renewal guidance report's query/filtering and interval logic with mocked data (rather than full integration tests) enables fast, deterministic validation of the complex ephemeral classification logic.

### Shared test fixtures extracted to root conftest.py for renewal guidance tests
- **Repo**: ansible/metrics-utility
- **Commits**: 4cfb21f (#139), 3e559cf (#130)
- **What happened**: Fixtures that were initially defined locally in individual test files (`fixed_now`, `setup_processed_dataframe`) were extracted to `metrics_utility/test/conftest.py` so they could be shared across `test_renewal_guidance_query_methods.py` and the new `test_build_spreadsheet_method.py`. The `setup_processed_dataframe` fixture mocks `DBDataframeHostMetric`'s extractor to provide consistent data for all renewal guidance tests. The `test_build_spreadsheet_method.py` adds mock-heavy tests for the `build_spreadsheet()` method, verifying that sheets are created, dedup is called, and ephemeral-related sheets are conditionally included.
- **Insight**: When multiple test files need the same mock data setup, promote fixtures to the nearest shared conftest.py early to avoid duplicated fixture definitions that drift apart.

### Parameter validation tests for build_report and gather date/ephemeral arguments
- **Repo**: ansible/metrics-utility
- **Commits**: f2b5a83 (#128)
- **What happened**: Comprehensive parameter validation was added for `--since`, `--until`, `--month`, and `--ephemeral` arguments. New exception classes were introduced (`DateFormatError`, `MissingRequiredParameter`, `BadParameter`). A `handle_month()` helper was extracted from `build_report._handle_month()` into `helpers.py` with strict `strptime('%Y-%m')` validation (previously used the permissive `dateutil.parser.parse`). Regex patterns (`SINCE_AND_UNTIL_BUILD_PATTERN`, `SINCE_AND_UNTIL_GATHER_PATTERN`, `ALLOWED_EPHEMERAL_PATTERN`) enforce format constraints. The `build_report` command's `handle` method was split into `handle` (catches exceptions, logs, exits) and `_handle` (actual logic), matching the gather command's existing pattern. A `test_extra_params_validation.py` test file validates error messages for invalid inputs. `--until` now defaults to today when `--since` is provided without `--until`.
- **Insight**: Splitting command `handle` into a public wrapper (exception handling + exit codes) and private `_handle` (logic) enables tests to call `_handle` directly and assert on raised exceptions rather than catching `SystemExit`.

### `temporary_env` context manager now supports key removal via None values
- **Repo**: ansible/metrics-utility
- **Commits**: 75a83bc (#129)
- **What happened**: The `temporary_env` helper in `test/util.py` was updated to support removing env vars by passing `None` as the value. Previously it just called `os.environ.update(new_env)`, which doesn't remove keys. Now it iterates the dict: keys with `None` values are removed via `os.environ.pop(k, None)`, and others are set normally. This was needed for S3 env var validation tests that need to ensure certain vars are unset.
- **Insight**: A test utility for env var manipulation should support both setting and unsetting variables -- use `None` as a sentinel for "remove this key" to keep the API simple.

### Test data SQL scripts for host_metrics and job_host_summary added for Docker/CI
- **Repo**: ansible/metrics-utility
- **Commits**: 77490ef (#133), d26e163 (#143)
- **What happened**: SQL scripts were added to populate test databases with realistic data: (1) PR #133 added `tools/docker/main_hostmetric.sql` with 10 sample rows for the `main_hostmetric` table, loaded both in Docker Compose (via init scripts) and CI (via `cat ... | psql`). A `make populate_host_metrics` target was added for manual use. The Docker Compose init scripts were renamed with numeric prefixes (`init-0-roles.sql`, `init-1-schema.sql`, `init-2-hostmetric.sql`) to ensure execution order. (2) PR #143 added `tools/docker/main_jobhostsummary.sql` with a PL/pgSQL block that creates a full hierarchy (organization, inventory, instance, hosts, unified job template, project, job template, unified jobs, main jobs, and job host summaries) -- all inter-referencing entities needed for the gather collector's SQL queries. A `make populate_job_host` target was added.
- **Insight**: Test data SQL scripts that create the full entity hierarchy (org -> inventory -> host -> job template -> job -> job_host_summary) are essential for integration-testing the gather collector, which joins across all these tables.

### Gather integration test validates collected CSV content row-by-row
- **Repo**: ansible/metrics-utility
- **Commits**: 0816f67 (#144), e65b320 (#145)
- **What happened**: An integration test was added that runs gather with `--ship --since=2025-06-12 --until=2025-06-14` against test data, then opens the produced tarball, finds `job_host_summary.csv`, and compares each line against expected values. The test validates column headers, row count, and exact field values (host names, org names, timestamps). The SQL test data script had to be updated from `NOW()` to fixed timestamps (#145) because `NOW()` produced timestamps outside the gather time window, causing empty CSVs.
- **Insight**: Gather integration tests that validate CSV content line-by-line require fixed timestamps in test data -- any use of `NOW()` or dynamic timestamps in SQL scripts will cause the test to be flaky or empty depending on when it runs.

### Test conftest helpers promoted from ccspv_reports to root test directory
- **Repo**: ansible/metrics-utility
- **Commits**: 8164b5f (#159)
- **What happened**: The `validate_sheet_tab_names`, `validate_sheet_columns`, `normalize_column`, `validate_column`, and `cleanup` fixtures were moved from `metrics_utility/test/ccspv_reports/conftest.py` to `metrics_utility/test/conftest.py` so they could be shared with the new renewal guidance integration test. The ccspv_reports conftest was deleted entirely. This was needed because the renewal guidance test validates XLSX output the same way as CCSP tests.
- **Insight**: When a new test category needs the same validation helpers as an existing one, promote shared fixtures to the nearest common conftest.py -- don't duplicate them across sibling directories.

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

### Broken test tarballs moved to separate directory
- **Repo**: ansible/metrics-utility
- **Commits**: fb2e0a5 (#158)
- **What happened**: Test data tarballs that were intentionally broken (missing config.json, empty CSVs, corrupt data) were mixed in with valid test data under `test/test_data/data/`. The `test_empty_data_for_CCSP_and_CCSPv2.py` test used these broken tarballs but they could interfere with other tests. They were moved to `test/ccspv_reports/empty-data/data/` with a README explaining their purpose.
- **Insight**: Intentionally broken test data should be isolated in a clearly labeled directory -- mixing it with valid test data risks other tests accidentally reading corrupt files.

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

### CCSP deduplication integration test with numbered test cases
- **Repo**: ansible/metrics-utility
- **Commits**: afc880a (#166)
- **What happened**: A comprehensive CCSPv2 deduplication integration test was added (`test_complex_CCSPv2_with_canonical_facts.py`, ~2500 lines) that validates dedup behavior across numbered test cases (1.1-5.x). Each case represents a specific dedup scenario: (1) ansible_host dedup, (2) serial-based dedup, (3) multi-region hosts, (4) NAT scenarios, (5) edge cases. The test uses input CSV files with carefully crafted canonical_facts (product_serial, machine_id, ansible_host, ansible_port) and validates the output XLSX cell-by-cell using dict comparisons per sheet. A conftest fixture mocks `validation.now` to make report dates deterministic.
- **Insight**: Numbering dedup test cases (1.1, 2.3, 3.1...) with descriptive names in comments makes it possible to trace a failing assertion back to the specific dedup scenario it represents, which is critical when the test file is thousands of lines long.

### Collector unit tests using mock for ProgrammingError scenarios
- **Repo**: ansible/metrics-utility
- **Commits**: 376352b (#172)
- **What happened**: Unit tests were added for `main_indirectmanagednodeaudit_table` using `unittest.mock` to mock `_copy_table` and `get_optional_collectors`. The tests cover: successful execution, collector not in optional list, `ProgrammingError` when table doesn't exist (AAP 2.4), query format verification, and specific error message content. Mock objects with `isoformat()` methods stand in for datetime parameters.
- **Insight**: Collector functions that run raw SQL against potentially missing tables need mock-based unit tests that simulate `ProgrammingError` -- these can't be tested in integration because CI always has the full schema.

### Service collector integration tests validate CSV content per collector type
- **Repo**: ansible/metrics-utility
- **Commits**: 0c851b4 (#214)
- **What happened**: Integration tests were added for the new service collectors (`unified_jobs`, `job_host_summary_service`, `main_jobevent_service`, `execution_environments`) in `test_gather_jobs_events_summaries_service.py`. Each test runs gather with the appropriate collector enabled via `METRICS_UTILITY_OPTIONAL_COLLECTORS`, then opens the produced tarballs, finds the specific CSV by filename, and compares header and row values against expected data. A `validate_csv_in_tarballs()` helper iterates through tarballs to find the matching CSV, supports skipping auto-generated columns (like IDs) via `skip_columns_names`, and provides detailed assertion messages showing expected vs actual values per cell. The `SafeTarFile` context manager from existing gather tests was reused.
- **Insight**: When testing multiple collector types that each produce separate tarballs, a shared `validate_csv_in_tarballs()` helper that searches across tarballs by CSV filename avoids duplicating the tarball-opening and CSV-parsing boilerplate per test.

### Anonymized rollup unit tests validate aggregation logic with crafted DataFrames
- **Repo**: ansible/metrics-utility
- **Commits**: 6f8c0a8 (#215)
- **What happened**: Unit tests were added for all four anonymized rollup classes under `metrics_utility/test/library/`. The event modules test (`test_events_modules_anonymized_rollups.py`, ~355 lines) creates a detailed DataFrame with specific event types (runner_on_ok, runner_on_failed, runner_on_skipped, etc.) and validates the two-phase aggregation: task-level collapse (success/failure/skip classification) then module-level and collection-source-level statistics. The jobs test validates duration/waiting time calculations and template-level aggregations. Tests use string timestamps that get coerced by `pd.to_datetime(..., utc=True)` in `prepare_data()`, and guard against negative durations (where finished < started).
- **Insight**: Anonymized rollup tests benefit from hand-crafted DataFrames with known expected aggregation results rather than loading from CSV files -- this makes the test assertions self-documenting and independent of external test data files.

### End-to-end anonymized rollup test: gather -> rollup -> anonymize -> validate JSON
- **Repo**: ansible/metrics-utility
- **Commits**: 2e9e826 (#239), 6ea3a3f (#247)
- **What happened**: An integration test (`test_from_gather_to_json.py`) was added that runs the full anonymized rollup pipeline: (1) runs `gather` with service collectors against the mock DB, (2) calls `compute_anonymized_rollup_from_raw_data()` on the collected tarballs, (3) validates the resulting JSON structure and values. The test uses `pytest.approx` for float comparisons in duration/timing fields, validates that unfinished jobs (where `finished` is null) are filtered out before duration computation, and checks that the anonymization correctly hashes unknown-source module/collection names while preserving known ones. The `save_rollups` parameter was added to `compute_anonymized_rollup_from_raw_data()` so tests can skip writing rollup files to disk.
- **Insight**: End-to-end integration tests for the rollup pipeline are essential because the pipeline spans multiple stages (collect -> extract -> aggregate -> anonymize) with different data formats at each boundary -- unit tests on individual rollup classes miss format mismatches between stages.

### Library storage integration tests for Directory and S3
- **Repo**: ansible/metrics-utility
- **Commits**: eaf3748 (#246)
- **What happened**: Integration tests were added for `StorageDirectory` and `StorageS3` in `metrics_utility/test/library/`. The directory test validates `put()` (with dict=, filename=, and fileobj= modes), `get()` (context manager yielding temp path), `exists()`, `remove()`, and `glob()`. The S3 test uses the existing MinIO instance from CI and validates the same operations against real S3-compatible storage. Both tests use `pytest.raises` to verify error cases (e.g., put with no data arguments). The S3 test uses a pid-based prefix to avoid conflicts with other tests using the same MinIO bucket.
- **Insight**: Using a pid-based S3 key prefix (`test-{os.getpid()}/`) prevents test data collisions when the same MinIO bucket is shared across multiple test suites running in CI.

### Collector helper functions tested with mock database connection
- **Repo**: ansible/metrics-utility
- **Commits**: d005629 (#242)
- **What happened**: Unit tests were added for the new database helper functions (`get_config_and_settings_from_db`, `get_last_entries_from_db`, `get_controller_version_from_db`, `datetime_hook`) in `test_automation_controller_billing_helpers.py`. The tests mock `django.db.connection` to simulate various database responses: successful retrieval, empty results, and `DatabaseError` exceptions. The `datetime_hook` tests verify that datetime strings in JSON are correctly parsed to `datetime` objects with UTC timezone. An integration test validates that all helper functions work together with realistic data.
- **Insight**: When replacing ORM calls with raw SQL, the new code paths need their own unit tests since the ORM layer's error handling (e.g., returning None for missing rows) is no longer provided automatically -- each edge case (empty results, missing keys, database errors) must be explicitly handled and tested.

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

