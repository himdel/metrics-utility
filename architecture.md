# Architecture

### metrics-utility is a Django management command that runs inside Controller's environment
- **Repo**: ansible/metrics-utility
- **Commits**: 8ab89cc, 22b3072, 1b95f39, 03a5640
- **What happened**: The initial design requires metrics-utility to find and import AWX (Controller) modules at startup. It appends the AWX path to `sys.path`, calls `prepare_env()` and `django.setup()`, then runs a custom `ManagementUtility`. The AWX path is resolved by first checking if `awx` is already importable (e.g. in a venv), then falling back to the `AWX_PATH` env var (default `/awx_devel`).
- **Insight**: metrics-utility is not a standalone Django app -- it is a parasite that boots Controller's Django environment and directly accesses Controller's DB models and settings.

### Billing data collection built on insights_analytics_collector framework
- **Repo**: ansible/metrics-utility
- **Commits**: 755110d (#5), 6357e51 (#8)
- **What happened**: The `gather_automation_controller_billing_data` command subclasses `insights_analytics_collector.Collector`. Collectors are registered with `@register` decorators specifying name, version, format (json/csv), and a slicing function. The collector uses a PostgreSQL advisory lock (`gather_automation_controller_billing_lock`) to prevent concurrent runs. Data is exported via `COPY ... TO STDOUT WITH CSV HEADER` for performance.
- **Insight**: The billing collector reuses the same framework and advisory lock mechanism as Controller's analytics collection, but with a separate lock name to avoid conflicts.

### Package/shipping abstracted via factory pattern for multiple targets
- **Repo**: ansible/metrics-utility
- **Commits**: 6e60790 (#9)
- **What happened**: PR #9 introduced a factory pattern for packaging (`PackageFactory`) and extraction (`ExtractorFactory`), supporting `crc` (console.redhat.com) and `directory` (local filesystem) ship targets. The `_package_class()` method changed from a static method returning a single class to an instance method using the factory. A `build_report` command was added to generate XLSX reports from locally stored data.
- **Insight**: The ship target abstraction (crc vs directory) was a key architectural decision that enabled both cloud shipping and local report generation from the same collection pipeline.

### Slicing strategy evolved from trivial to daily
- **Repo**: ansible/metrics-utility
- **Commits**: 755110d (#5), 6357e51 (#8), 6e60790 (#9)
- **What happened**: The initial billing collector used `trivial_slicing` (single interval). PR #8 enabled gap-filling by loading last-collected timestamps from `AUTOMATION_ANALYTICS_LAST_ENTRIES`. PR #9 replaced `trivial_slicing` with `daily_slicing` which breaks the collection interval into day-sized chunks -- first completing the remainder of the start day, then full days.
- **Insight**: Daily slicing ensures tarball files are partitioned by day, which is important for the report builder that later reads these tarballs and aggregates by date.

### Last-gathered timestamps shared with Controller analytics via shared settings
- **Repo**: ansible/metrics-utility
- **Commits**: 6357e51 (#8)
- **What happened**: Billing collection reuses Controller's `AUTOMATION_ANALYTICS_LAST_ENTRIES` setting to track per-collector timestamps. When persisting these timestamps, the billing collector acquires the `gather_analytics_lock` (the analytics job's lock) to avoid race conditions with the analytics job that writes to the same setting. The settings are reloaded after acquiring the lock to avoid overwriting analytics timestamps.
- **Insight**: Sharing the last-entries setting with analytics was deliberate to avoid backporting changes, but requires careful dual-lock coordination to prevent data corruption.

### Local storage path scheme changed from Hive-style to plain directories
- **Repo**: ansible/metrics-utility
- **Commits**: 046c6e2 (#15)
- **What happened**: The local directory storage structure changed from `report_data/year={year}/month={month}/day={day}` (Hive partition style) to `data/{year}/{month}/{day}` (plain directory hierarchy). The `report_data` prefix was also shortened to `data`. Additionally, the report directory creation was moved to after the data-exists check, so empty directories are no longer created when there's no data.
- **Insight**: The Hive-style partition naming was unnecessary overhead since the data is read by the metrics-utility report builder (not Spark/Hive), and plain directory paths are simpler to navigate manually.

### CCSPv2 report type and dataframe engine refactoring
- **Repo**: ansible/metrics-utility
- **Commits**: 9272f1d (#17)
- **What happened**: The original monolithic `DataframeSummarizedByOrgAndHost` was renamed to `DataframeJobhostSummaryUsage` and a common `Base` class was extracted with shared logic (date iteration, dataframe casting, merge summarization). A new `DataframeContentUsage` engine was added for jobevent-based content analysis. The `DataframeEngineFactory` was updated to compose different engine combinations per report type: CCSP uses jobhost_summary only, CCSPv2 uses jobhost_summary + content_usage.
- **Insight**: The Base class extraction was driven by CCSPv2 needing the same merge/cast logic but different data sources -- classic case of extracting a template method pattern.

### RENEWAL_GUIDANCE report reads from Controller DB, not tarballs
- **Repo**: ansible/metrics-utility
- **Commits**: 8ec8cdf (#23), f388cae (#24)
- **What happened**: RENEWAL_GUIDANCE introduced a third data source pattern: `ExtractorControllerDB` reads `main_hostmetric` joined with `main_host` via raw SQL (no ORM). It uses marker-based pagination (concatenating hostname + host_id for stable ordering) to handle large datasets. Unlike the tarball extractors, it also collects `ansible_facts` (board serial, machine UUID) and host variables (ansible_host, ansible_connection) for deduplication.
- **Insight**: The renewal guidance report's deduplication requirement (matching hosts across inventories by hardware identity) forced a fundamentally different data access pattern -- reading live DB with facts rather than pre-collected CSV snapshots.

### Host deduplication via iterative multi-key matching
- **Repo**: ansible/metrics-utility
- **Commits**: f388cae (#24), 1236de5, 78bcb95
- **What happened**: The renewal guidance report deduplicates hosts by iteratively searching for matches across four keys: hostname, ansible_host variable, product serial (originally board serial, changed in 1236de5), and machine UUID. The algorithm runs configurable iterations (default 3, via `REPORT_RENEWAL_GUIDANCE_DEDUP_ITERATIONS`) to find indirect relationships -- e.g., host A shares a serial with host B, and host B shares a hostname with host C, so all three are the same managed node. A processed index set prevents double-counting.
- **Insight**: Iterative multi-key dedup is necessary because a single host can appear in multiple inventories under different names but with matching hardware identifiers, creating indirect relationship chains.

### Custom PostgreSQL functions for parsing host variables
- **Repo**: ansible/metrics-utility
- **Commits**: c29ffd3 (#16), f388cae (#24)
- **What happened**: Two PostgreSQL functions are created at query time via `prepend_query`: `metrics_utility_parse_yaml_field()` extracts values from YAML-encoded text fields using regex, and `metrics_utility_is_valid_json()` safely checks if text is valid JSON. These exist because Controller stores host variables as text that may be either JSON or YAML, requiring runtime format detection with `CASE WHEN is_valid_json THEN jsonb extraction ELSE yaml regex extraction END`.
- **Insight**: Controller's dual-format variable storage (JSON or YAML in the same text column) requires runtime format detection at the SQL level, which is handled via `CREATE OR REPLACE FUNCTION` to keep it in a single query round-trip.

### S3 storage adapter added as third ship target with ReportSaver abstraction
- **Repo**: ansible/metrics-utility
- **Commits**: 1e86f8c
- **What happened**: A new `s3` ship target was added alongside `directory` and `crc`. This required creating `S3Handler` (a shared boto3 wrapper in `base/s3_handler.py`), `ExtractorS3`, `PackageS3`, and `ReportSaverS3`. To support S3 report saving, the report saving logic was extracted from the `build_report` command into a new `ReportSaver` abstraction with a factory (`ReportSaverFactory`) producing `ReportSaverDirectory` or `ReportSaverS3`. Previously, directory creation and `report_spreadsheet.save()` were inline in the command. Ship target validation logic was also extracted from the command classes into a shared `management/validation.py` module, DRYing up the duplicate `_handle_directory_ship_target()` and `_handle_crc_ship_target()` methods that existed in both the gather and build_report commands.
- **Insight**: Adding S3 support forced two good refactors: (1) extracting report saving into its own strategy pattern (ReportSaver) since S3 needs temp-file-then-upload, and (2) centralizing ship target validation since gather and build_report previously had separate copies of the same env var handling.

### CCSPv2 report sheets became fully configurable with ccsp_summary as optional
- **Repo**: ansible/metrics-utility
- **Commits**: da636a6, b721f52
- **What happened**: The CCSPv2 report's first "Usage Reporting" summary sheet was made optional (gated behind `ccsp_summary` in `METRICS_UTILITY_OPTIONAL_CCSP_REPORT_SHEETS`), and `ccsp_summary` was added to the default sheet list. A new `jobs` sheet was added showing job template usage aggregated by organization. A `managed_nodes_by_organizations` sheet was added that creates a pivot table with organizations as columns and last-automation dates as values. An `METRICS_UTILITY_ORGANIZATION_FILTER` env var was added to filter reports to specific organizations (semicolon-separated list). The sheet_index became dynamic (starting at 0 instead of hardcoded 1) since the summary sheet might not exist.
- **Insight**: Making even the "main" summary sheet optional (via `ccsp_summary`) enabled reusing CCSPv2 as a general-purpose usage history report outside the CCSP billing domain -- the same report type serves both billing and operational analytics use cases.

### mock_awx enables running build_report without a Controller installation
- **Repo**: ansible/metrics-utility
- **Commits**: 33d428e (#51)
- **What happened**: To run `build_report` (which only reads tarballs, not the Controller DB), a `mock_awx/` directory was added that provides stub implementations of `awx.prepare_env()`, `awx.main.utils.datetime_hook`, and `awx.main.utils.get_awx_version`. When `AWX_PATH` is not set and `awx` is not importable, `metrics_utility/__init__.py` now appends `mock_awx/` to `sys.path` instead of exiting with an error. The mock `prepare_env()` just sets `DJANGO_SETTINGS_MODULE` to a minimal settings module. A convenience script `run-ccsp2-build` was also added to run CCSPv2 report generation with test data.
- **Insight**: The mock_awx pattern decouples report building from Controller, enabling development and testing without a running Controller instance -- only the gather command actually needs Controller's modules.

### advisory_lock import switched from awx to django-ansible-base for AAP 2.5
- **Repo**: ansible/metrics-utility
- **Commits**: 33d428e (#51)
- **What happened**: In AAP 2.5, `advisory_lock` moved from `awx.main.utils.pglock` to `ansible_base.lib.utils.db`. The collector now uses `importlib.util.find_spec('ansible_base')` at module level to detect which version is available: if `ansible_base` exists (2.5+), import from there; otherwise fall back to `awx.main.utils.pglock` (2.4). The `awx.main.utils` import was also moved below the `insights_analytics_collector` import to group external deps before internal ones.
- **Insight**: When a utility function moves between packages across product versions, use `importlib.util.find_spec` for runtime detection rather than version-checking -- it's more robust and doesn't require knowing exact version numbers.

### mock_awx extended to support running gather (not just build_report) without Controller
- **Repo**: ansible/metrics-utility
- **Commits**: be761a3 (#52)
- **What happened**: Previously mock_awx only supported running `build_report` without Controller (commit 33d428e). PR #52 extended it to also support running `gather_automation_controller_billing_data` standalone. This required: (1) adding `DATABASES` config to `mock_awx/settings/__init__.py` pointing to a local PostgreSQL instance, (2) mocking `awx.conf.license.get_license()` to return an `UNLICENSED` stub, (3) adding `awx.conf.models.Setting` as a Django model so the analytics framework can persist last-entry timestamps, (4) enabling debug-level logging for `awx.main.analytics` when running in standalone mode (auto-detected by mock_awx path being used). The AWX database schema (`pg_dump -s awx` output) was bundled for recreating the schema locally.
- **Insight**: Running gather standalone required mocking three additional AWX interfaces beyond what build_report needed (license, settings model, DB config), because gather actually queries the Controller database rather than just reading tarballs.

### Tarball extraction refactored into extractor_common with security hardening
- **Repo**: ansible/metrics-utility
- **Commits**: 81e93b5 (#75)
- **What happened**: The tarball extraction logic that was duplicated between `ExtractorDirectory` and `ExtractorS3` was extracted into `extractor_common.py`. The new `safe_extract()` function adds security measures missing from the originals: only extracts `.json`/`.csv` files, skips symlinks and hardlinks, enforces path traversal checks (`os.path.abspath` + prefix validation), limits max files (100) and total extracted size (1GB), and extracts chunks manually rather than trusting tar metadata sizes. A `process_tarballs()` function handles the common pattern of extracting a tarball, loading config.json, and reading CSV files for `job_host_summary`, `indirect_nodes`, and `main_jobevent`.
- **Insight**: Extracting tarball handling into a shared module was driven by adding `indirect_nodes` as a third CSV type that both extractors needed to handle -- the security hardening was done alongside to satisfy SonarCloud checks.

### Indirectly managed nodes added as new data category with device_type discrimination
- **Repo**: ansible/metrics-utility
- **Commits**: 81e93b5 (#75)
- **What happened**: A new `indirect_nodes` collector was added, querying `main_indirectmanagednodeaudit` (a Controller table for nodes managed indirectly through network devices, etc.). The collector is gated by `INCLUDE_INDIRECT` which checks if `'indirect_nodes'` is in `METRICS_UTILITY_OPTIONAL_COLLECTORS`. A `device_type` column was added to the dataframe with constants `DIRECT=0`, `INDIRECT=1` (and `EDGE=2` planned for future). In `DataframeJobhostSummaryUsage`, indirect nodes skip the `task_runs` summation (they already have a `task_runs` column from the source table). The `optional_collectors()` function was moved from `collectors.py` to a new `metric_utils.py` module to be importable by both collectors and dataframe engines.
- **Insight**: Indirect nodes reuse the same dataframe pipeline as direct nodes by adding a `device_type` discriminator column, avoiding a parallel pipeline -- but they require special handling for `task_runs` since indirect node counts come pre-aggregated from the source table.

### Inventory scope added as third dataframe engine with main_host collector
- **Repo**: ansible/metrics-utility
- **Commits**: 7a8bea5 (#78)
- **What happened**: A new `DataframeInventoryScope` engine was added alongside `DataframeJobhostSummaryUsage` and `DataframeContentUsage`. It reads from a new `main_host` collector that queries the `main_host` table (full inventory snapshot) with joins to `main_inventory`, `main_organization`, and `main_unifiedjob`. The `main_host` collector uses a new `limit_slicing` strategy (always collects today's full snapshot, unlike `daily_slicing` which partitions by modification time) because inventory state cannot be collected historically. The collector is gated by `'main_host' in get_optional_collectors()`. The indirect_nodes collector was also renamed from `indirect_nodes` to `main_indirectmanagednodeaudit` (matching the DB table name) and switched from `INCLUDE_INDIRECT` module constant to `get_optional_collectors()` for consistency. The `yaml_and_json_parsing_functions()` helper was extracted from the job_host_summary collector to be reused by main_host.
- **Insight**: The inventory scope feature required a fundamentally different slicing strategy (`limit_slicing` = full table scan per day) because inventory is a point-in-time snapshot, not an event stream -- unlike job host summaries which accumulate over time and can be sliced by modification date.

### insights-analytics-collector absorbed into metrics-utility as `metrics_utility/base/`
- **Repo**: ansible/metrics-utility
- **Commits**: 6337a3f (#92)
- **What happened**: The external dependency `RedHatInsights/insights-analytics-collector` was vendored into the repo as `metrics_utility/base/`. The code was copied from the upstream repo at commit 98dac28, then renamed: `insights_analytics_collector/` became `metrics_utility/base/`, and `tests/` became `metrics_utility/test/base/`. All imports were updated via bulk find-and-replace. The `insights-analytics-collector` dependency was removed from both `pyproject.toml` and `setup.cfg`. New dev dependencies `pytest-mock` and `pytz` were added (previously transitive through the external package). A key issue discovered during integration: `django.setup()` can only be called once, so the base test conftest that was mocking `django.conf` had to be removed since it conflicted with the mock_awx settings already loaded.
- **Insight**: Absorbing a low-activity external dependency into the main repo eliminates version coordination friction and enables direct refactoring -- the immediate benefit was removing unused extension points (Collection* subclass overrides) in the next PR (#111).

### Generator refactored: tarball-per-csv, inlined Collection classes, `pd.to_datetime` format
- **Repo**: ansible/metrics-utility
- **Commits**: 5bd05d9 (#111)
- **What happened**: Three changes in one PR: (1) The data generator was refactored to produce one tarball per CSV type per day (instead of one tarball containing all CSV types), matching how the real collector works with daily slicing. Each tarball now contains a single CSV plus `config.json` and `data_collection_status.csv`. (2) The `CollectionJSON`, `CollectionCSV`, `CollectionManifest`, and `CollectionDataStatus` classes were inlined into the base `Collector` -- the factory methods (`_collection_json_class()`, `_collection_csv_class()`, etc.) that allowed subclass overrides were removed since no subclass ever overrode them. The `slicing` decorator was also removed as unused. (3) All `pd.to_datetime(x)` calls were updated to `pd.to_datetime(x, format="ISO8601")` to avoid pandas deprecation warnings about format inference.
- **Insight**: After absorbing insights-analytics-collector (#92), unused extension points (Collection subclass factories, slicing decorator) could be removed -- the vendoring enabled simplification that wasn't possible when the base was an external package.

### Collection coverage sheet added as optional CCSPv2 report sheet
- **Repo**: ansible/metrics-utility
- **Commits**: 97010f6 (#110), da5075e (#115)
- **What happened**: A new `data_collection_status` optional sheet was added to CCSPv2 reports. It reads `data_collection_status.csv` from tarballs (which records when each collection ran and what time range it covered) and produces two tables: (1) a gap analysis showing time ranges not covered by any collection (e.g., if cron was down for 3 hours, that gap appears), and (2) a raw status log showing each collection run's timestamp, duration, and status. PR #110 built the basic sheet and refactored report code: `_init_dimensions` + per-sheet column setup was unified into `base.add_sheet(title, sheet_index, columns)`, and the "no billing data" check was changed to fail only when ALL dataframes are empty (not just `[0]`). PR #115 improved gap detection to notice gaps at the beginning and end of the report interval by inserting synthetic 0-duration "collections" at the report's `since` and `until` boundaries. Month boundaries are derived from `--month` or `--since`/`--until` params, passed through `extra_params['month_since']` and `extra_params['month_until']`.
- **Insight**: The collection coverage sheet serves as a data quality indicator -- operators can see whether their cron job covered the full billing period or if gaps exist that might undercount managed nodes.

### Build report optimization: only extract CSVs needed by requested sheets
- **Repo**: ansible/metrics-utility
- **Commits**: 5cc7fb5 (#86), 0320d20 (#91)
- **What happened**: The `process_tarballs()` method was refactored to only extract and read CSV files that are needed by the report sheets the user requested via `METRICS_UTILITY_OPTIONAL_CCSP_REPORT_SHEETS`. A `CSV_SHEETS` mapping (defined in `extract/base.py`) declares which CSVs are needed by which sheets. The extraction logic was moved from `extractor_common.py` into a new `extract/base.py` Base class, with `_safe_extract()` preserved for security. PR #91 further refactored the sheet-to-CSV mapping by extracting a `csv_enabled()` method that delegates to `sheet_enabled()`, making the logic pluggable so the data generator script could also use it with different CSV selection criteria.
- **Insight**: Skipping unnecessary CSV parsing during tarball extraction is a significant optimization for large datasets -- a CCSPv2 report requesting only `managed_nodes` no longer needs to parse potentially millions of jobevent rows.

### Exception handling unified from commands into ManagementUtility
- **Repo**: ansible/metrics-utility
- **Commits**: 7bde0de (#150)
- **What happened**: Both `build_report` and `gather` commands had duplicate try/except blocks in their `handle()` methods, each catching a slightly different set of exceptions (`MetricsException` subclasses), with inconsistent error formatting (`str(e)` vs `e.name`). The fix introduced a `MetricsException` base class that all custom exceptions inherit from (with a shared `self.name = message` in `__init__`), moved the try/except into `ManagementUtility.run_subcommand()`, and eliminated the `_handle()`/`handle()` split in the commands. Commands now just have `handle()` with the actual logic -- exceptions propagate up to `run_subcommand()` which logs and exits. This also simplified tests: they can assert `pytest.raises(MetricsException)` instead of mocking loggers and catching `SystemExit`.
- **Insight**: When multiple commands share the same exception-handling pattern, lifting it to the command dispatcher eliminates duplication and ensures consistent error formatting across all commands.

### `report_period` unified and moved inside `extra_params`
- **Repo**: ansible/metrics-utility
- **Commits**: cda736f (#149)
- **What happened**: The report system had `report_period` as a separate constructor parameter to `ReportFactory` and all Report classes, plus `report_period_range` inside `extra_params` for `--since` mode. `ReportFactory` would silently overwrite `report_period` with `report_period_range` when present. This was unified: `report_period` now lives inside `extra_params`, set to either `opt_month` (for `--month`) or `"since_date, until_date"` (for `--since`). The `report_period` constructor parameter was removed from `ReportFactory` and all Report classes. The `ship_target` parameter was also removed from `ReportFactory` as it was unused.
- **Insight**: Constructor parameters that are always derived from `extra_params` should just live inside `extra_params` -- having the same data in two places (constructor arg + dict) creates opportunities for them to diverge.

### Extractor code consolidated: `extra_params`, `get_path_prefix`, `get_report_path` moved to Base
- **Repo**: ansible/metrics-utility
- **Commits**: 4c0cafc (#153)
- **What happened**: `ExtractorDirectory` and `ExtractorS3` both had identical implementations of `extra_params` storage, `_get_path_prefix()` (data/Y/m/d), and `get_report_path()` (reports/Y/m). These were moved to the shared `extract/base.py` `Base` class. `get_report_path()` was actually identical across all three extractors (including `ExtractorControllerDB`) and only used from `build_report`, so it was moved to the `build_report` command itself as a module-level function. `get_optional_collectors()` was moved from the shared `metric_utils.py` back to `collectors.py` since only collectors use it.
- **Insight**: When refactoring shared code into a base class, check whether the method is actually used by the base class hierarchy at all -- `get_report_path` belonged in the caller, not the extractor.

### Parsing moved closer to validation: `ephemeral_days` parsed in `build_report`, not in report class
- **Repo**: ansible/metrics-utility
- **Commits**: 64aad4d (#155)
- **What happened**: Previously, `build_report` passed the raw `--ephemeral` string value (e.g., `"30days"`) to `ReportRenewalGuidance` via `extra_params['opt_ephemeral']`, and the report class called `parse_number_of_days()` on it. This was refactored so `build_report` calls `parse_number_of_days()` at the command level, storing the parsed integer (or `None`) as `extra_params['ephemeral_days']`. The report class now just reads the pre-parsed integer. The condition `if self.extra_params.get('opt_ephemeral') is not None` was simplified to `if self.ephemeral_days`.
- **Insight**: Parse user input as early as possible (at the command level), then pass parsed/typed values downstream -- this keeps report logic clean and ensures parsing errors are caught before any work begins.

### All parsers/validators consolidated into `validation.py`
- **Repo**: ansible/metrics-utility
- **Commits**: 9e038d9 (#156)
- **What happened**: `parse_date_param`, `parse_number_of_days`, `handle_month`, and `handle_datelike` were scattered between `helpers.py`, `build_report.py`, and `gather_automation_controller_billing_data.py`. They were all moved into `management/validation.py`, which already housed the env var validation logic. The `helpers.py` file was reduced to just DataFrame helper functions (parse_json_array, merge_arrays). The gather command's `_handle_datelike` method (which was a private instance method) was also extracted to the shared module. `help` and `help_texts` were moved from the constructor to class-level attributes on both commands.
- **Insight**: Grouping all validation and parsing functions in one module makes them discoverable and testable in isolation -- having them split across helpers, commands, and validation created import cycles and made it hard to find the right function.

### Three date parsers merged into one `parse_date_param`
- **Repo**: ansible/metrics-utility
- **Commits**: d8428a8 (#157)
- **What happened**: Previously there were three separate date parsing functions: `parse_date_param` (for build_report), `handle_datelike` (for gather), and `handle_validate_date_param` (for validation). They had different format support -- gather only accepted `Xd` and `Xm`, build accepted `Xd`, `Xmo`, `Xmonth`, `Xmonths`, `Xm`. The three were merged into a single `parse_date_param` that accepts all formats (`Xd/day/days`, `Xmo/mon/month/months`, `Xm/min/minute/minutes`, and ISO dates). The separate regex patterns (`SINCE_AND_UNTIL_GATHER_PATTERN`, `SINCE_AND_UNTIL_BUILD_PATTERN`) were eliminated. `dateutil.parser.parse()` was replaced with `datetime.datetime.fromisoformat()` for absolute dates, removing the `dateutil.parser` import. Validation was merged into the parser itself -- bare integers raise `UnparsableParameter` immediately. The `validate_build_extra_params` function was split into `validate_ccsp_params`, `validate_renewal_params`, and `parse_since_until` for clarity.
- **Insight**: When build and gather commands accept the same date parameter formats, having separate parsers with subtly different format support creates confusion -- a unified parser with all formats is simpler and makes both commands accept the same inputs. **Supersedes** the separate `_handle_datelike` from #156.

### Deduplication extracted as a separate pipeline step with its own factory
- **Repo**: ansible/metrics-utility
- **Commits**: 54175a4 (#162)
- **What happened**: Previously, deduplication was embedded inside `ReportRenewalGuidance`. It was extracted into a standalone pipeline step between dataframe building and report generation: `DataframeFactory.create()` -> `DedupFactory.create().run()` -> `ReportFactory.create()`. The `DataframeFactory` was refactored to return a dict of named dataframe instances (e.g., `{'job_host_summary': DataframeJobhostSummaryUsage(...), 'main_host': DataframeInventoryScope(...)}`) instead of a tuple of built dataframes. `DedupFactory` selects a deduplicator (`DedupCCSP` or `DedupRenewal`) based on `report_type` or an explicit `METRICS_UTILITY_DEDUPLICATOR` env var. New base dataframe methods were added: `empty()` (returns empty DataFrame with correct columns), `merge()` (multipart collection rollup), `dedup()` (hostname remapping + regrouping), `group()` and `regroup()`. The `build_report` command's `--help` now includes an `ENVIRONMENT` epilog section describing key env vars.
- **Insight**: Extracting deduplication from the report into a separate factory-dispatched pipeline step enables different dedup strategies (CCSP vs renewal vs experimental) to be applied to any report type without modifying report code.

### Deduplication modes expanded: hostname-only and experimental for renewal guidance
- **Repo**: ansible/metrics-utility
- **Commits**: 1b2a5a4 (#171)
- **What happened**: The renewal guidance deduplication was refactored into a class hierarchy: `BaseDedupRenewal` (shared logic: cleanup, hostname selection, record building), `DedupRenewal` (original iterative multi-key matching), `DedupRenewalHostname` (hostname-based only, mirroring CCSP logic using `ansible_host_variable || hostname`), and `DedupRenewalExperimental` (hostname dedup then serial-based dedup on top). The `DedupFactory` was updated with new modes: `renewal-hostname` and `renewal-experimental`, with report type validation (these modes only support `RENEWAL_GUIDANCE`). Common methods (`_cleanup_null_values`, `_get_latest_hostname`, `_build_deduped_record`, `stringify`) were extracted to the base class.
- **Insight**: Having multiple deduplication strategies for the same report type (controlled by `METRICS_UTILITY_DEDUPLICATOR` env var) enables customers to choose the aggressiveness of dedup -- from hostname-only (most conservative) to experimental serial-based (most aggressive) -- without code changes.

### Unified logger module replaces per-class logger instances
- **Repo**: ansible/metrics-utility
- **Commits**: 35194fb (#173)
- **What happened**: Previously, every class created its own logger via `self.logger = logging.getLogger(...)` or `logging.getLogger('awx.main.analytics')`, and the `debug_utils.py` module provided separate `print_debug`/`print_data` functions gated by `--verbose` in `sys.argv`. All of this was replaced with a single `metrics_utility/logger.py` module that exports a shared `logger` instance and a `debug()` function to enable debug-level logging. The `build_report` command's `init_logging` method (which set up a StreamHandler) was removed -- `logger.py` uses `logging.basicConfig` at import time. `debug_utils.py` was deleted entirely. The base `Collector` class no longer accepts a `logger` parameter. A CI lint check was added to `pr-checks.yml` that greps for `logging.getLogger` calls outside `logger.py` and fails the build if found.
- **Insight**: A single shared logger module with a CI enforcement check prevents the proliferation of per-class loggers that create inconsistent log formatting and make it impossible to control verbosity from one place.

### Infrastructure node summary sheet added to CCSPv2 reports
- **Repo**: ansible/metrics-utility
- **Commits**: 5c94421 (#169)
- **What happened**: A new optional `infrastructure_summary` sheet was added to CCSPv2 reports. It reads indirect managed nodes (filtered by `managed_node_type == INDIRECT`) and groups them by `infra_type`, `infra_bucket`, and `device_type` (extracted from the `facts` JSON field). The sheet renders a hierarchical display with merged cells for infrastructure type headers, showing unique and total node counts per device type. The sheet was added to `VALID_SHEETS` in validation. An `test_invalid_data_for_CCSP_and_CCSPv2.py` test was added to verify that reports handle malformed/corrupt data gracefully.
- **Insight**: The infrastructure summary sheet categorizes indirect nodes by their infrastructure type (network, storage, etc.) and device type, giving customers visibility into what kinds of indirectly managed infrastructure they have.

### vCPU collector switched from Kubernetes API to Prometheus with PrometheusClient/KubernetesClient classes
- **Repo**: ansible/metrics-utility
- **Commits**: 0be6cd0 (#198)
- **What happened**: The `total_workers_vcpu` collector was refactored from using the `kubernetes` Python library (`CoreV1Api.list_node()`) to querying Prometheus via a new `PrometheusClient` class. The client authenticates using a Kubernetes service account token (read from the mounted secret at `/var/run/secrets/kubernetes.io/serviceaccount/token`) via a new `KubernetesClient` class. The PromQL query `max_over_time(sum(machine_cpu_cores)[59m59s:5m])` computes the maximum total vCPUs over the previous hour with 5-minute resolution, collecting 59m59s to avoid overlapping with the current hour boundary. The collector now also records a CPU timeline (array of timestamp/cpu_sum pairs at 5-minute intervals) in the output JSON for auditability. The `kubernetes` Python library dependency was effectively replaced by `requests` (for Prometheus HTTP API) and raw file reads (for service account tokens).
- **Insight**: The Prometheus-based approach gives billing-grade vCPU data by using `max_over_time` over the previous hour rather than an instantaneous snapshot -- this captures peak usage and is resilient to node scaling events mid-hour. **Supersedes** the Kubernetes API approach from #165.

### Library module introduced as shared code between CLI and external service
- **Repo**: ansible/metrics-utility
- **Commits**: 5fe762a (#218)
- **What happened**: A new `metrics_utility/library/` module was created to hold code shared between the CLI (metrics-utility) and an external metrics service. The library provides stub implementations of collectors, dataframes, extractors, packaging, storage, reports, and helpers (tempdir, lock, datetime instants). Key design decisions: (1) A `@collector` decorator dynamically creates anonymous `BaseCollector` subclasses from plain functions, so each collector function becomes a class with `collector_key` and `collector_fn` properties -- initialization (param passing) is separated from `.gather()` execution so DB locks can be acquired between the two. (2) Storage classes (`StorageS3`, `StorageDirectory`, `StorageCRC`) use `storage.get()` as a context manager that downloads to a temp file, yields the path, and cleans up. (3) Dataframes have `add_csv`/`add_parquet` methods feeding into a `regroup` template method that subclasses override. (4) The library must not import anything from outside `metrics_utility/library/` (other than external dependencies) and must not read environment variables -- all configuration comes via function parameters.
- **Insight**: The `@collector` decorator pattern that creates anonymous subclasses avoids the boilerplate of defining a class per collector while preserving the two-phase init/gather separation needed for lock management -- the decorated function becomes both the constructor (returns a collector instance) and the gather logic (called by `BaseCollector.gather()`).

### Anonymized aggregation rollups as a new data processing layer
- **Repo**: ansible/metrics-utility
- **Commits**: 6f8c0a8 (#215)
- **What happened**: A new `metrics_utility/anonymized_rollups/` module was added with four rollup classes: `JobsAnonymizedRollups` (job duration, waiting time, success/failure stats grouped by template), `JobHostSummaryAnonymizedRollup` (task counts grouped by template), `EventModulesAnonymizedRollups` (module usage, collection source stats, task success/failure/skip/unreachable rates), and `ExecutionEnvironmentsAnonymizedRollups` (default vs custom EE counts). These operate on the data from the new service-oriented collectors (#214) and produce JSON aggregations rather than XLSX reports. The event modules rollup uses a two-phase aggregation: first collapsing events to one row per (job, host, task_uuid, module) to get task-level outcomes, then aggregating to per-module and per-collection-source statistics. A `collections.json` file (#225) maps collection names to their source type (community, validated, certified).
- **Insight**: Anonymized rollups represent a fundamentally different output path from the existing CCSP/renewal reports -- they produce JSON aggregations for a metrics service rather than customer-facing XLSX spreadsheets, enabling analytics without exposing customer-identifiable data.

### Service-oriented collectors added alongside existing billing collectors
- **Repo**: ansible/metrics-utility
- **Commits**: 0c851b4 (#214)
- **What happened**: Four new collectors were added for the metrics service use case: `unified_jobs` (all job data with content types, EE images, installed collections), `job_host_summary_service` (similar to existing `job_host_summary` but filtered by `job.finished` rather than `jobhostsummary.modified`), `main_jobevent_service` (events with full event_data for module/collection analysis), and `execution_environments` (EE inventory via `limit_slicing`). The `job_host_summary_service` collector uses the same CTE-based optimization as the existing collector (#151) for host variable parsing. The `main_jobevent_service` collector uses a two-phase approach: first queries job IDs finished in the window, then builds a literal `VALUES` clause for the event query to avoid a potentially expensive join. All four are gated by `METRICS_UTILITY_OPTIONAL_COLLECTORS` and added to `VALID_COLLECTORS` in validation.
- **Insight**: The service collectors filter by `job.finished` timestamp (when the job completed) rather than `jobhostsummary.modified` (when the summary was last touched) -- this ensures consistent time boundaries when correlating jobs with their events and host summaries for aggregation.

### Tarball filenames now include collection name for identification
- **Repo**: ansible/metrics-utility
- **Commits**: 97d8bc7 (#226)
- **What happened**: Tarball names were changed from `{uuid}-{since}-{until}-{index}.tar.gz` to `{uuid}-{since}-{until}-{index}-{collection_key}.tar.gz`. The implementation first creates the tarball with `-unknown` suffix, then renames it after writing the collection data (when the collection key is known). If the rename fails, the tarball keeps the `-unknown` suffix and an error is logged. The index numbering is unaffected by the suffix.
- **Insight**: Adding the collection key to tarball names makes it possible to identify what data a tarball contains without extracting it -- especially useful now that multiple collector types produce separate tarballs in the same directory.

### Tarball and file filtering by collection name at extraction time
- **Repo**: ansible/metrics-utility
- **Commits**: 3b28731 (#227)
- **What happened**: Following the tarball naming change (#226), extractors and dataframe engines now filter which tarballs to open and which files to extract based on the collection name. Each dataframe engine declares which collections it needs (e.g., `DataframeJobhostSummaryUsage` needs `['job_host_summary', 'main_indirectmanagednodeaudit']`, `DataframeContentUsage` needs `['main_jobevent']`). The `iter_batches()` method gained `collections` and `optional` parameters. `filter_tarball_paths()` in the extract Base class uses regex to match tarball filenames against the requested collections, with backward compatibility for pre-0.7.0 tarballs that lack the collection suffix. `_safe_extract()` also gained an `enabled_set` parameter to skip extracting CSV files from within the tarball that aren't needed. The `indirect_nodes` key in `needed_data` was renamed to `main_indirectmanagednodeaudit` to match the actual collector name.
- **Insight**: Filtering at two levels (which tarballs to open, and which files to extract from each tarball) provides a multiplicative optimization -- when a dataframe engine only needs `main_jobevent` data, it skips both the tarballs named `*-job_host_summary.tar.gz` and any non-jobevent CSV files inside the opened tarballs.

### AWX imports removed from collectors in favor of direct database queries
- **Repo**: ansible/metrics-utility
- **Commits**: d005629 (#242), 0799a24 (#245)
- **What happened**: The collectors module previously imported `awx.conf.license.get_license`, `awx.main.utils.datetime_hook`, `awx.main.utils.get_awx_version`, and `awx.conf.models.Setting` to read license info, Controller version, and last-gathered timestamps. All of these were replaced with direct SQL queries against the `conf_setting` table in `helpers.py`: `get_config_and_settings_from_db()` reads LICENSE and settings keys in one query, `get_controller_version_from_db()` checks conf_setting then falls back to `main_instance`, `get_last_entries_from_db()` reads AUTOMATION_ANALYTICS_LAST_ENTRIES, and a local `datetime_hook()` replaces the AWX import. The `django.conf.settings` references (INSTALL_UUID, SYSTEM_UUID, TOWER_URL_BASE, etc.) were replaced with values from the conf_setting query. PR #245 fixed the mock DB data to include `conf_setting` rows and renamed `conf_settings.sql` to `conf_setting.sql` (matching the actual table name).
- **Insight**: Removing AWX imports from collectors decouples metrics-utility from the AWX Python package at runtime -- the only dependency is the AWX database schema, which is accessed via raw SQL. This is a step toward running metrics-utility in environments where AWX Python packages are not installed.

### Library storage implementations: Directory, S3, Segment, CRC, CRCMutual
- **Repo**: ansible/metrics-utility
- **Commits**: eaf3748 (#246)
- **What happened**: The library's stub `storage.py` module was replaced with a `storage/` package containing five complete implementations: `StorageDirectory` (local filesystem), `StorageS3` (S3/MinIO via boto3), `StorageSegment` (Segment analytics, put-only), `StorageCRC` (console.redhat.com via service account OAuth), and `StorageCRCMutual` (CRC via mutual TLS). All share a common API: `put(name, *, filename=, fileobj=, dict=)`, `get(name)` (context manager yielding temp file path), `exists(name)`, `remove(name)`, `glob(pattern)`. A shared `util.py` provides `retry_with_backoff()` for transient failure handling in CRC uploads. Integration tests for Directory and S3 storage were added. The `minio` dev dependency was added to `pyproject.toml` for S3 tests.
- **Insight**: The library storage classes mirror the CLI's existing PackageDirectory/PackageS3/PackageCRC pattern but with a simpler, unified API (put/get/exists/remove/glob) that works for both tarballs and dict data -- the library can pass configuration via constructor params instead of env vars, fulfilling the library's no-env-var design constraint.

### Anonymized rollups: full pipeline from gather to anonymized JSON output
- **Repo**: ansible/metrics-utility
- **Commits**: 2e9e826 (#239), 6ea3a3f (#247)
- **What happened**: The anonymized rollups module was significantly expanded with a complete pipeline: (1) A `BaseAnonymizedRollup` class provides `merge()`, `prepare()`, `base()`, and `save_rollup()` template methods. `save_rollup()` writes rollup data (DataFrames as CSV, dicts/lists as JSON) into tarballs under `rollups/YYYY/MM/DD/rollup_name/`. (2) An `anonymized_rollups.py` orchestrator loads raw data from collector tarballs via `load_anonymized_rollup_data()`, computes all four rollups (jobs, job_host_summary, events_modules, execution_environments), and hashes sensitive fields (job template names, unknown-source module/collection names, playbook names) using SHA-512 with a configurable salt. (3) A `task_anonymized_rollups.py` provides a `task_anonymized_rollups()` function that runs gather then computes rollups, usable from the metrics service. (4) An end-to-end integration test (`test_from_gather_to_json.py`) runs gather against the mock DB, then computes rollups and validates JSON output values using `pytest.approx` for float comparisons. The `JobsAnonymizedRollup.prepare()` now filters out unfinished jobs (where `finished` is null) before computing duration metrics, preventing NaN values.
- **Insight**: The anonymization strategy is selective: only fields from "Unknown" collection sources (not in the certified/validated/community lookup) get hashed, preserving analytics value for known Ansible content while protecting proprietary module/collection names. Filtering unfinished jobs in `prepare()` rather than later avoids NaN durations from corrupting aggregation statistics.

### StorageSegment chunked data transmission for large payloads
- **Repo**: ansible/metrics-utility
- **Commits**: 6b5bbc6 (#249)
- **What happened**: `StorageSegment.put()` was enhanced to handle data exceeding Segment's size limits (32KB for regular messages, 512MB for bulk). When data exceeds the limit, it is automatically split into chunks using `_split_into_chunks()` (for lists: accumulates items until size limit; for dicts: groups key-value pairs). Each chunk is sent as a separate `analytics.track()` call with `chunk_info` metadata (chunk number, total chunks, chunk size). A `use_bulk` constructor parameter selects between regular and bulk size limits. An `event_name` parameter was added to `put()` (defaulting to `'Metrics Artifact Upload'`).
- **Insight**: Segment's 32KB per-message limit means anonymized rollup data (which can contain thousands of module/collection stats) must be chunked -- the chunking preserves reassembly metadata (chunk_number/total_chunks) so the receiving end can reconstruct the full payload.

### Library collectors: CLI collectors refactored into library with env-var-free interfaces
- **Repo**: ansible/metrics-utility
- **Commits**: cb36f4e (#248)
- **What happened**: All CLI collectors were refactored into `metrics_utility/library/collectors/`, split into `controller/` (DB-backed: config, job_host_summary, main_jobevent, unified_jobs, etc.) and `others/` (non-DB: total_workers_vcpu with PrometheusClient). Each collector function takes explicit parameters (`db=`, `since=`, `until=`, `output_dir=` or `output_file=`) instead of reading env vars. The `copy_table()` utility was moved to `library/collectors/util.py` and now supports both `output_dir` (creates CsvFileSplitter internally) and `output_file` (writes to a provided file object), plus optional `params=` for query parameters. The `CsvFileSplitter` was moved from `base/` to `library/` to stop SonarQube from flagging duplicate code. The `@collector` decorator from library creates anonymous collector classes from plain functions, separating initialization (param passing) from execution (`.gather()`).
- **Insight**: Moving collectors to the library required eliminating all env var reads and filesystem assumptions -- the library's "no env vars, params only" constraint forced a cleaner API where each collector explicitly declares its dependencies (db connection, time range, output target).

### Anonymized rollups restructured: flattened JSON output, vectorized processing, SHA-256 hashing
- **Repo**: ansible/metrics-utility
- **Commits**: 07cd17c (#250)
- **What happened**: The anonymized rollup pipeline was significantly reworked: (1) A `flatten_json_report()` function was added to transform the nested rollup structure (with `events_modules.module_stats`, `events_modules.collection_name_stats`, `jobs.by_template`, etc.) into a flat structure with top-level keys (`module_stats`, `collection_name_stats`, `jobs_by_template`, `job_host_summary`, `statistics`, `modules_used_per_playbook`). Anonymization now operates on the flattened structure. (2) Collection name extraction was vectorized using `str.extract()` with regex instead of `apply()` for performance. (3) The hash algorithm was changed from SHA-512 to SHA-256 to reduce hash output size. (4) Event filtering was moved earlier in the pipeline (before column assignment) to reduce DataFrame size. (5) A column pruning step keeps only needed columns after preparation to save memory. (6) `modules_used_per_playbook` was changed from a dict (`{playbook: count}`) to an array of `{playbook_id, modules_used}` objects. (7) Jobs that never started are now counted (not filtered out). (8) A `total_unique_hosts` and `jobs_total` statistic was added. (9) Multiple-tarball support was added and tested.
- **Insight**: The flattened JSON structure is easier for downstream consumers to process -- nested structures with varying levels of nesting created ambiguity about where to find specific fields. The SHA-512 to SHA-256 change halves hash size with acceptable collision risk for anonymization purposes. **Supersedes** the SHA-512 hashing from #239.

### Controller version read from main_instance table only, removing conf_setting fallback
- **Repo**: ansible/metrics-utility
- **Commits**: 7ef1628 (#257)
- **What happened**: `get_controller_version_from_db()` previously tried three conf_setting keys (`AWX_VERSION`, `TOWER_VERSION`, `VERSION`) with priority ordering, then fell back to the `main_instance` table. The function was simplified to only query `main_instance` (selecting `version` from the most recently seen enabled instance). The `VERSION` key was also removed from the `get_config_and_settings_from_db()` query since it was no longer needed. A `_fetch_one()` helper was extracted for simple single-value queries. The `main_instance` table was added to the Docker Compose init scripts and CI SQL import for test data.
- **Insight**: The `main_instance` table is the canonical source for the Controller version (it represents the actual running instance) -- reading from conf_setting was unreliable because those keys were not consistently populated across AWX/Controller versions. **Supersedes** the multi-key conf_setting approach from #242.

### StorageSegment made resilient to missing `segment` package with anonymous tracking
- **Repo**: ansible/metrics-utility
- **Commits**: cf644cb (#270)
- **What happened**: The `segment.analytics` import was wrapped in `try/except ImportError` with a `SEGMENT_AVAILABLE` flag, because the segment package is not installed in the Controller image (only needed by the metrics service). When segment is unavailable, `StorageSegment.put()` returns early with a debug log instead of crashing. The `write_key` check was softened from raising an exception to logging an info message. Additionally, `user_id` was replaced with `anonymous_id` (a random UUID per `put()` call) for event tracking, improving privacy. Comprehensive tests were added covering available/unavailable segment states and edge cases.
- **Insight**: Library code that runs in multiple deployment contexts (Controller image vs metrics service) must gracefully handle optional dependencies -- wrapping imports in try/except with a feature flag is the standard pattern, but the behavior change (from crash to no-op) must also be tested.

### Library published to PyPI with weekly date-based versioning
- **Repo**: ansible/metrics-utility
- **Commits**: 56b5e35 (#271)
- **What happened**: A `pypi-release.yml` GitHub Actions workflow was added that publishes the metrics-utility library to PyPI on a weekly schedule (Sundays at 2 AM UTC) or via manual trigger. The version scheme is date-based: the base version from `setup.cfg` (e.g., `0.7.0dev`) is transformed to `0.7.YYYYMMDD` (e.g., `0.7.20251111`). The workflow temporarily modifies `setup.cfg` before building, uses `uv build`, and publishes with PyPI trusted publisher (no API token in secrets). Package inclusion was refined in both `pyproject.toml` and `setup.cfg` to exclude non-library directories (`tools/`, `workers/`, `mock_awx/`, `docs/`, etc.) and include package data (`*.json`, `*.sql`, `*.txt`). `requires-python` was raised to `>=3.12`.
- **Insight**: Date-based versioning (`0.7.YYYYMMDD`) for a library published from a `devel` branch enables frequent releases without manual version bumping -- consumers always get the latest code, and the date suffix ensures monotonically increasing versions.

### Dead code removed from base Collector: is_enabled, is_dry_run, license checking
- **Repo**: ansible/metrics-utility
- **Commits**: 931e6ad (#265)
- **What happened**: Several methods and attributes were removed from the base `Collector` class: `is_enabled()` (checked license and shipping config), `is_dry_run()`, `_is_valid_license()`, `_last_gathering()`, `_save_last_gather()`, and the `licensed` constructor parameter. These were never overridden with real implementations -- `_is_valid_license` always returned `True`, `_last_gathering` always returned `None`, and `_save_last_gather` was a no-op. The `is_shipping_enabled()` method was replaced with a simple `self.ship` boolean set in `__init__`. The `is_enabled()` guard in `gather()` was removed entirely since it always returned `True`. Confusingly named methods were the root cause: `_is_shipping_configured` (underscored, dead) vs `is_shipping_configured` (public, used), and `last_gathering` (dead) vs `load_last_gathered_entries` (used).
- **Insight**: After vendoring insights-analytics-collector (#92), the abstract methods that were designed for subclass overriding but never actually overridden became pure dead code -- method pairs with nearly identical names (differing only by underscore prefix or verb form) are a strong signal of dead code.

### Advisory lock extracted from AWX/ansible_base into library/lock.py
- **Repo**: ansible/metrics-utility
- **Commits**: 2f14098 (#259)
- **What happened**: The `_pg_advisory_lock` context manager was duplicated in both `Collector` (base) and `BillingCollector` (subclass), each with slightly different implementations. The base version used `hashlib.sha512` for key hashing and managed its own `db_connection()` call, while the billing collector delegated to `awx.main.utils.pglock.advisory_lock` (with a `try/except ImportError` fallback to `ansible_base.lib.utils.db`). Both were replaced by a single `lock()` function in `metrics_utility/library/lock.py` that uses PostgreSQL's `hashtext()` for key hashing (letting the database do the hashing instead of Python) and takes an explicit `db=` parameter. The AWX/ansible_base imports for advisory_lock were removed entirely. Unit tests were added covering lock acquisition, non-reentrant behavior, and key validation.
- **Insight**: Moving the advisory lock into the library module with an explicit `db=` parameter eliminates the AWX Python package dependency for locking and makes the lock function usable by both the CLI and the external metrics service. **Supersedes** the `try/except ImportError` AWX-vs-ansible_base approach from #51 and #94.

### Anonymized rollups refactored: tarball loading replaced with direct CSV file input
- **Repo**: ansible/metrics-utility
- **Commits**: 6d8a8f1 (#272)
- **What happened**: The `compute_anonymized_rollup_from_raw_data()` function previously accepted `(salt, year, month, day, base_path)` and internally searched for tarballs via `glob.glob()`, extracted CSVs from them, and loaded dataframes. This was replaced with an `input_data` dict parameter that maps collector names to lists of CSV file paths (e.g., `{'unified_jobs': ['/path/to/file1.csv', ...], ...}`). The tarball-opening logic was removed from `load_anonymized_rollup_data()` -- it now just iterates over file paths and calls `pd.read_csv()`. A new `compute_anonymized_rollup(db, salt, since, until, ship_path)` function calls library collectors directly (passing `db=connection`), collects their output file lists, and feeds them into the rollup pipeline. The `since`/`until` parameters replaced `year`/`month`/`day` throughout, enabling sub-day time ranges (tested with a half-day rollup test). The `save_rollup()` filenames changed from `key_YYYY_MM_DD` to `key_YYYY-MM-DD_YYYY-MM-DD` (since-until range).
- **Insight**: Decoupling rollup computation from tarball discovery (passing file lists instead of a base path + glob) enables the rollups to work with data from any source -- library collectors that return file paths directly, or pre-extracted CSVs -- without the tight coupling to the tarball directory structure.

### Dataframe classes moved to library with loading/transform split
- **Repo**: ansible/metrics-utility
- **Commits**: fe12805 (#237)
- **What happened**: The five dataframe classes (`DataframeJobhostSummaryUsage`, `DataframeContentUsage`, `DataframeInventoryScope`, `DataframeCollectionStatus`, `DBDataframeHostMetric`) were moved from `metrics_utility/automation_controller_billing/dataframe_engine/` to `metrics_utility/library/dataframes/`. The monolithic stub `library/dataframes.py` was replaced with a `library/dataframes/` package. Data loading (tarball extraction, batch iteration) was split from data transformation logic: the library classes contain the pure transform logic (`merge`, `group`, `regroup`, `dedup`, `empty`, column definitions), while the CLI-side classes retain `iter_batches` and `build_dataframe` which orchestrate loading from extractors. A `BaseDataframe` provides the merge template method using `unique_index_columns`, `data_columns`, `operations`, and `cast_types` -- simpler dataframes (collection status, host metric) override `merge` with plain `pd.concat`. The `build_dataframe` method now saves results to `self.rollup` in addition to returning them. The deduplicator parameter was made explicit (passed to `dedup()` rather than read from env vars).
- **Insight**: Moving dataframes to the library required cleanly separating "how data is loaded" (extractor-specific, stays in CLI) from "how data is transformed" (pure pandas logic, goes to library) -- the library classes must not know about tarballs, S3, or extractors.

### Anonymized rollup data structure changed from flat DataFrame to dict with totals
- **Repo**: ansible/metrics-utility
- **Commits**: 0a7c054 (#288)
- **What happened**: The `EventModulesAnonymizedRollup` and `JobHostSummaryAnonymizedRollup` classes changed their internal data passing from flat DataFrames to dicts containing both a total count and the aggregated data. For events: `prepare()` now returns `{'event_total': int, 'task_summary': DataFrame}` instead of just a DataFrame. For job host summary: `prepare()` returns `{'jobhostsummary_total': int, 'aggregated': DataFrame}`. The `merge()` methods were overridden in both classes to handle the new dict structure (summing totals, concatenating DataFrames). The `base()` methods were updated to unpack the dict and include totals in the output JSON. The `BaseAnonymizedRollup.merge()` was also updated to handle `None` as the initial value (first batch). The `save_rollup()` method gained support for scalar values (int, float, str, bool) by wrapping them in a dict before JSON serialization.
- **Insight**: When a rollup needs metadata about the full input (total record count before filtering/aggregation), that metadata must be tracked alongside the data through prepare/merge/base -- adding it as a column in the DataFrame would be lost during groupby operations, so a dict wrapper is the right pattern.

### Library `anonymize` module removed from top-level library exports to fix circular import
- **Repo**: ansible/metrics-utility
- **Commits**: f9ee5d9 (#284)
- **What happened**: The `metrics_utility/library/__init__.py` previously imported and exported the `anonymize` submodule. This was removed because the `anonymize` module imports from `metrics_utility/anonymized_rollups/` which is outside the library, creating a circular import path when the library was imported from within the anonymized rollups code. The `anonymize` module is still accessible via direct import (`from metrics_utility.library.anonymize import ...`) but is no longer auto-imported when the library package is loaded.
- **Insight**: When a library submodule re-exports code from outside the library boundary, it should not be auto-imported in the library's `__init__.py` -- this creates circular import chains when the outside code also imports from the library.

### Anonymized rollups rethought: grouping by job type instead of template, new collectors added
- **Repo**: ansible/metrics-utility
- **Commits**: 456eb0f (#319)
- **What happened**: The anonymized rollup aggregation strategy was fundamentally rethought. Jobs are now grouped by `job_type` (model field: job, workflow_job, etc.) instead of by `job_template_name`, because job template names are customer-identifiable data that must be anonymized anyway. Job host summaries are also grouped by job type rather than template. New data dimensions were added: `launch_type` statistics, `ansible_version`/`controller_version` breakdowns, `forks` count, organization count, inventory count, projects by SCM type. A `credentials_service` collector was added querying `main_credential` for credential type distribution. An `installed_collections` field was added to `unified_jobs` for collection usage tracking. The rollup output format changed from saving intermediate DataFrames/CSV rollups to returning only the final JSON, dropping `save_rollup()` calls. Median and average calculations were dropped in favor of totals, min, max, and sum -- simplifying aggregation across batches. The `"Unknown"` anonymization strategy was changed from SHA-512 hashing to replacing with the literal string `"Unknown"`, preserving known collection/module names while hiding proprietary ones without hash overhead.
- **Insight**: Grouping anonymized rollups by job type rather than template name avoids the need to hash template names (which are customer-specific) while still providing useful analytics about what kinds of automation are running. Dropping medians and averages in favor of sum/min/max simplifies cross-batch merging -- medians cannot be correctly merged from pre-computed batch medians. **Supersedes** the SHA-512 hashing from #239 and the template-based grouping from #215.

### Library `copy_table` returns DataFrame instead of file list
- **Repo**: ansible/metrics-utility
- **Commits**: c638afc (#327)
- **What happened**: The library's `copy_table()` function was refactored from writing CSV files via `COPY TO STDOUT` and `CsvFileSplitter` to returning a pandas DataFrame directly. The function now uses `cursor.execute()` + `cursor.fetchall()` to get results, builds a DataFrame from the column descriptions and rows, and returns it. This was necessary because `pd.read_sql()` requires SQLAlchemy and doesn't work well with psycopg3 connections. A separate `dataframe_to_csv_files()` utility was added in `library/csv_utils.py` for callers that still need CSV output (e.g., the tarball pipeline). The `load_anonymized_rollup_data()` function was updated to accept both DataFrames and file paths (strings) in its input list, enabling a gradual migration. The AAP 2.4 vs 2.5 psycopg2/psycopg3 branching (`copy_expert` vs `cursor.copy()`) was removed entirely since the library only supports psycopg3.
- **Insight**: Returning DataFrames from collectors instead of file paths eliminates the serialize-to-CSV-then-parse-back-to-DataFrame round-trip for consumers that immediately process the data in memory (like anonymized rollups). The CSV file path is now an opt-in output format rather than the only option. **Supersedes** the AAP 2.4/2.5 psycopg branching from #248.

### Anonymized rollups: JSON serialization verification via round-trip and batch debug output
- **Repo**: ansible/metrics-utility
- **Commits**: dd2639a (#331)
- **What happened**: The `load_anonymized_rollup_data()` function was updated to JSON-serialize and deserialize the data after each `prepare()` and `merge()` call, ensuring that intermediate rollup state is always JSON-serializable. This catches serialization issues (NaN, NumPy types, sets, non-string dict keys) early rather than at final output. Batch debug output was added: each rollup's `prepare` and merged `concat` results are saved to `./out/batches/{rollup_name}/{n}_prepare.json` and `{n}_xconcat.json` files, enabling inspection of intermediate aggregation state. The `unique_hosts_total` field was moved from per-grouping aggregation to top-level only -- it's now computed from a `host_ids` list at the rollup root, not summed from sub-groupings, because summing per-grouping unique counts double-counts hosts that appear in multiple groupings. Job aggregation was changed to store template and inventory IDs instead of names, avoiding the need to anonymize names in groupings.
- **Insight**: JSON round-trip verification after each batch `prepare`/`merge` step is a defensive measure that catches serialization issues incrementally rather than at the end of a long pipeline -- this is especially important when aggregation produces intermediate types (sets, NumPy integers) that are valid Python but invalid JSON.

### CLI collectors replaced with thin wrappers around library collectors
- **Repo**: ansible/metrics-utility
- **Commits**: c887383 (#339)
- **What happened**: The ~700 lines of inline SQL and collection logic in `collectors.py` (the CLI-side collector definitions) were replaced with thin `cli_*` wrapper functions that delegate to the library collectors. Each CLI collector now follows a 3-line pattern: check if enabled, instantiate the library collector with `db=connection` and date params, and return `output.as_files(collector)` or `output.as_dict(collector)`. The `output` parameter is a `CollectorOutput` object that handles the CLI-specific concern of writing CSVs to temp directories, while the library collectors remain output-agnostic (defaulting to `DataframeOutput` or `DictOutput`). `limit_slicing` was renamed to `until_slicing` (using `until` param instead of `now()`), and `full_sync` and register descriptions were removed as unused. `bool_from_env` was unified as the standard way to read boolean env vars (replacing ad-hoc `str.lower() == 'true'` patterns).
- **Insight**: The CLI collectors are now a thin adapter layer between Django's management command framework (with `connection` and env vars) and the library's parameter-driven collectors -- this completes the CLI/library split where the library owns all SQL and data logic while the CLI owns only the environment integration.

### Dashboard collectors added to library for metrics-service consumption
- **Repo**: ansible/metrics-utility
- **Commits**: 5b26fc3 (#341)
- **What happened**: A new `metrics_utility/library/collectors/dashboard/` package was added with `dashboard_jobs` as a `@collector`-decorated function. Unlike billing collectors (which use `DataframeOutput` and produce CSVs), dashboard collectors return structured dicts with `count` and `results` lists, containing job data enriched with labels and host summaries from separate sub-queries. The collector uses the `@collector` decorator pattern (init/gather split) and takes explicit `db=`, `since=`, `until=` parameters. Three helper functions (`_dashboard_job_labels`, `_dashboard_job_host_summaries`, and the main `dashboard_jobs`) compose the results. TypedDict annotations (`AWXJobType`, `AWXJobHostSummaryType`, `DashboardJobsResultType`) document the return structure. The SQL uses `%s` parameterized placeholders (not f-string interpolation) for safe query building.
- **Insight**: Dashboard collectors represent a third output pattern alongside CSV files (billing) and JSON dicts (config): structured typed dicts with nested lists, designed for direct API consumption by the metrics service rather than file-based pipelines.

### Anonymized rollup field naming changed from DB column names to descriptive names
- **Repo**: ansible/metrics-utility
- **Commits**: e35a93b (#343)
- **What happened**: Several field names in the anonymized rollup output were renamed to be more descriptive for external consumers: `dark_total` became `unreachable_total`, `failures_total` became `failed_total`, `collections_versions` became `jobs_by_installed_collections_versions`, and `job_count` inside collection version entries expanded to include `jobs_total`, `jobs_failed_total`, `jobs_successful_total`, duration breakdowns, and template/inventory totals. The `job_type_total` field (count of distinct job types) was removed as redundant -- the `job_types` list already provides this information. A `jobs_by_controller_version` grouping was added, with controller version injected from the `controller_version_service` collector into all job groupings.
- **Insight**: When designing JSON output for external consumers, use descriptive field names (`unreachable_total`, `failed_total`) rather than DB column names (`dark`, `failures`) -- external consumers shouldn't need to know that Ansible internally calls unreachable hosts "dark".

### `Unknown` collection source renamed to `Custom` in anonymized rollups
- **Repo**: ansible/metrics-utility
- **Commits**: e35a93b (#343)
- **What happened**: Collections not found in the `collections.json` lookup (not community, validated, or certified) were previously labeled `"Unknown"` in the anonymized rollup output. This was renamed to `"Custom"` throughout: `collection_source` classification, anonymization replacement strings, and test assertions. The rationale is that unknown collections are typically customer-written custom content, not truly "unknown" -- the label `Custom` better describes what they are. **Supersedes** the `"Unknown"` string replacement from #319.
- **Insight**: Choosing semantically accurate labels for classification categories matters for downstream analytics -- `Custom` is actionable information (customer-written content), while `Unknown` implies a data quality problem.

### job_host_summary_service: ensure_functions and host variable parsing removed
- **Repo**: ansible/metrics-utility
- **Commits**: 457f4a2 (#347)
- **What happened**: The `job_host_summary_service` collector previously included CTEs for `filtered_hosts` and `hosts_variables` that joined against `main_host` to extract `ansible_host_variable` and `ansible_connection_variable` via the `metrics_utility_is_valid_json` and `metrics_utility_parse_yaml_field` custom PostgreSQL functions. These CTEs and the `ensure_functions(db)` call (which created those functions) were removed entirely. The columns `ansible_host_variable` and `ansible_connection_variable` were dropped from the collector output. This simplification was possible because the service collectors feed into anonymized rollups which don't need host variable deduplication -- only the billing/CCSP collectors need `ansible_host` for managed node counting.
- **Insight**: The service-oriented collectors can be simpler than the billing collectors because they serve different downstream needs: billing needs host variable parsing for dedup, while anonymized rollups aggregate by job type and don't need per-host identity resolution. Removing `ensure_functions` also eliminates the need for write access to the database (CREATE FUNCTION). **Extends** the custom PostgreSQL functions pattern from #16/#24.

### Installed collections cache key changed from SHA-256 hash to execution_environment_id
- **Repo**: ansible/metrics-utility
- **Commits**: b7037cf (#350)
- **What happened**: The `JobsAnonymizedRollup._process_collections_from_jobs()` method cached parsed installed collections to avoid redundant `json.loads()` calls for jobs sharing the same execution environment. The cache key was changed from `SHA-256 hash of the raw JSON string` to `execution_environment_id` (an integer from the newly added column in the `unified_jobs` collector). The hash approach was unreliable because PostgreSQL's JSONB serialization doesn't guarantee identical key ordering across rows, so the same collection set could produce different hashes. The new `_get_collection_cache_key()` returns `('ee', int(ee_id))` when available, falling back to `('raw', hash(raw))` (Python's built-in hash) for rows without an EE id. The `hashlib` import was removed entirely from this module.
- **Insight**: When caching parsed data keyed by serialized content, prefer a stable identifier (like a database ID) over hashing the serialized form -- JSON/JSONB serialization order is not guaranteed, making content hashes unreliable as cache keys. **Supersedes** the SHA-256 hash caching approach from #343.

### StorageSegment: per-chunk message_id for deduplication and ordering
- **Repo**: ansible/metrics-utility
- **Commits**: 60d7f32 (#348)
- **What happened**: `StorageSegment.put()` gained a `segment_meta` parameter (dict) that is passed through to each `analytics.track()` call as keyword arguments. When `segment_meta` contains a `message_id`, each chunk gets a unique derived `message_id` computed as `sha256(f'{message_id}_{chunk_index}')`. This enables Segment's deduplication (same message_id = same event) while ensuring chunks are individually identifiable. The `segment_meta` dict can also carry a `timestamp` for controlling event ordering. The `**segment_meta` is unpacked into the `analytics.track()` call alongside the existing `anonymous_id`, `event`, and `properties` arguments.
- **Insight**: When sending chunked data to an event pipeline with deduplication (like Segment), derive per-chunk message IDs from the parent message ID plus chunk index -- this ensures retries are idempotent (same chunk = same ID) while keeping chunks distinct from each other.

### StorageSegment: `use_bulk` removed, sync_mode enabled for reliable delivery
- **Repo**: ansible/metrics-utility
- **Commits**: 828c8c1 (#372), 4474a6c (#383)
- **What happened**: The `use_bulk` constructor parameter and `BULK_MESSAGE_LIMIT` (500MB) were removed from `StorageSegment` in #372 -- all messages now use the regular 24KB chunk limit. The chunking algorithm was also improved: instead of summing separate item sizes (which underestimates because it ignores the wrapping `{key: [...]}` structure), the new code builds a trial `{key: active_chunk[key] + [item]}` and measures the full JSON size before deciding to split. In #383, `analytics.sync_mode = True` was enabled to fix silent event loss: Segment's SDK batches `track()` calls into background HTTP POSTs that silently drop events when the batch exceeds 500KB (returning HTTP 200 with no error). sync_mode sends each `track()` as a separate blocking HTTP request, eliminating both the batch-size and background-thread race condition problems. Gzip compression was also tried but Segment silently rejects gzip-encoded bodies.
- **Insight**: When a third-party SDK silently drops data on oversized batches and provides no reliable way to estimate true per-event overhead, sync_mode (one HTTP request per event) is the only reliable approach. **Supersedes** the `use_bulk` option from #249 and extends the chunking fixes from #281.

### Anonymization simplified: salt parameter and hash function removed
- **Repo**: ansible/metrics-utility
- **Commits**: 675c61a (#399)
- **What happened**: The `hash(value, salt)` function (SHA-256 digest of `salt:value`) and the `salt` parameter were removed from `anonymize_data()` and `anonymize_rollups()`. Previously, job template names in `jobs_by_job_type/launch_type/ansible_version` were hashed with the salt. This code was removed entirely -- the current anonymization strategy replaces custom/unknown values with the literal string `"Custom"` rather than hashing them. The anonymization logic was also refactored: repetitive per-field anonymization blocks were consolidated into `_anonymize_custom_items()` (for module_stats, collection_stats, role_stats) and `_anonymize_installed_collections_versions()` helper functions. The `collections.json` loading was extracted into `_load_known_collections()`.
- **Insight**: Hashing customer-identifiable values (like job template names) was unnecessary once the rollup grouping was changed from per-template to per-job-type (#319) -- the values are no longer present in the output, so there is nothing to hash. Removing the salt simplifies the API and eliminates a parameter that callers had to manage. **Supersedes** the SHA-256 hashing from #250 and the salt-based anonymization from #239.

### `library/collectors/service/` package for metrics-service-database collectors
- **Repo**: ansible/metrics-utility
- **Commits**: 7db682c (#357)
- **What happened**: A new `metrics_utility/library/collectors/service/` package was created alongside the existing `library/collectors/controller/` package. While controller collectors query the Controller (AWX) database, service collectors query the metrics-service's own database. The first service collector is `task_executions_service`, which reads from `tasks_taskexecution` to provide pipeline self-observability. This establishes a clear separation: `controller/` collectors need a Controller DB connection, `service/` collectors need a metrics-service DB connection.
- **Insight**: Separating collectors by their database target (`controller/` vs `service/`) makes the connection requirements explicit -- a deployment running only Controller collectors doesn't need metrics-service DB credentials, and vice versa.

### `installed_collections` field renamed from `name` to `collection` in anonymized rollup output
- **Repo**: ansible/metrics-utility
- **Commits**: 264f11c (#371)
- **What happened**: The `jobs_by_installed_collections_versions` array in the anonymized rollup output previously used `name` as the field for the collection name (e.g., `{name: "ansible.builtin", version: "2.15.0"}`). This was renamed to `collection` (e.g., `{collection: "ansible.builtin", version: "2.15.0"}`). The `extract_collection_name()` function was also hardened against pandas NA values: the previous `if not x:` check was unsafe for `pd.NA` (which raises `TypeError` in boolean context), replaced with explicit `pd.isna()` checks and `str(x).strip()` normalization. A `_installed_collection_name_is_unknown()` helper was added to safely determine whether a collection name should be anonymized to "Custom", handling None, NaN, empty strings, and pd.NA.
- **Insight**: Field names in JSON output consumed by external services are part of the API contract -- renaming `name` to `collection` is clearer but requires coordinating with downstream consumers. When checking for "empty" values from pandas, `if not x:` is unsafe for `pd.NA` -- always use `pd.isna()` first.

