# metrics-utility

Patterns, conventions, and gotchas specific to `ansible/metrics-utility`.
### Custom ManagementUtility replaces Django's default command discovery
- **Repo**: ansible/metrics-utility
- **Commits**: 8ab89cc, 22b3072, 03a5640
- **What happened**: metrics-utility uses a custom `ManagementUtility` subclass that overrides `fetch_command()` to load commands from `metrics_utility.management.commands` instead of Django's app-based command discovery. During development, command dispatch was temporarily hardcoded to a single command (22b3072) then restored to dynamic lookup (03a5640). The utility also customizes help text to show only metrics-utility commands.
- **Insight**: The custom ManagementUtility exists because metrics-utility is not a standard Django app -- it needs to provide its own commands without being listed in `INSTALLED_APPS`.

### build_report command with --force and --month options
- **Repo**: ansible/metrics-utility
- **Commits**: 6e60790 (#9), 958e924 (#11), 6a6aaa0 (#12)
- **What happened**: The `build_report` command generates XLSX reports from previously collected data. By default it generates a report for the previous month and skips if the report file already exists. PR #12 added `--force` to overwrite existing reports. PR #11 added graceful handling when no data exists for the requested month. The `--month` option accepts `YYYY-MM` format.
- **Insight**: The skip-if-exists default behavior is designed for cron usage where the command runs daily but should only generate one report per month.

### Three report types with different data sources and purposes
- **Repo**: ansible/metrics-utility
- **Commits**: 6e60790 (#9), 9272f1d (#17), 8ec8cdf (#23), f388cae (#24)
- **What happened**: The report system evolved to support three types: `CCSP` (original, jobhost summary data from tarballs, single managed-nodes sheet), `CCSPv2` (adds content usage from jobevents, plus end-user details for NA Direct partners), and `RENEWAL_GUIDANCE` (reads from Controller DB directly, deduplicates hosts using hardware facts, detects ephemeral hosts). Each type composes different dataframe engines and report classes via factory patterns.
- **Insight**: The three report types serve fundamentally different audiences: CCSP for basic billing, CCSPv2 for partner (NA Direct) billing with collection/role/module details, and RENEWAL_GUIDANCE for Red Hat renewal teams needing accurate managed node counts.

### pyarrow dependency removed in favor of pure pandas
- **Repo**: ansible/metrics-utility
- **Commits**: eeb35bd (#14)
- **What happened**: The `pyarrow` import was removed from `extractor_directory.py` (it had already been commented out). The `setup.cfg` dependencies were cleaned up accordingly. Data reading uses `pandas` with CSV format throughout instead of Parquet.
- **Insight**: Removing pyarrow reduced the dependency footprint significantly -- pyarrow is a large native library that was unnecessary since the pipeline uses CSV, not Parquet.

### Exit codes standardized: success=0, failure=1
- **Repo**: ansible/metrics-utility
- **Commits**: 34c711c (#18)
- **What happened**: The gather command previously called `exit(0)` for both success and all error cases, and `exit(-1)` for missing AWX modules. PR #18 standardized this: `exit(0)` on success, `exit(1)` on any error (bad config, upload failure, no data collected). A `NoAnalyticsCollected` exception was added to properly signal when no data was gathered, which also triggers `exit(1)`.
- **Insight**: Return code correctness matters for cron-based automation -- operators need `$?` to detect collection failures and trigger alerts.

### Verbose debug output via --verbose flag and debug_utils module
- **Repo**: ansible/metrics-utility
- **Commits**: a93b6bf (#66)
- **What happened**: A `debug_utils.py` module was added at the project root with `print_debug(text)` and `print_data(df, caption)` functions that only produce output when `--verbose` is in `sys.argv`. `print_data` drops a hardcoded list of noisy columns (timestamps, IDs, variables) before displaying dataframes with `pprint`. A `set_ccspv2_vars()` helper was also added for setting all CCSPv2 env vars programmatically (useful for IDE debugging). The debug calls were wired into the dataframe engines at key aggregation points (before/after groupby, after outer join) to trace the data pipeline.
- **Insight**: The `--verbose` flag with strategic print points at each aggregation step makes it possible to trace billing data through the multi-stage merge pipeline without modifying code -- essential for debugging incorrect report values.

### Data generator script for creating test tarballs at scale
- **Repo**: ansible/metrics-utility
- **Commits**: 0320d20 (#91)
- **What happened**: A `generator.py` script was added that creates synthetic test data tarballs by multiplying and randomizing real collected data. It loads existing tarballs (via `SOURCE_DATA_PATH` glob), concatenates CSVs by type, then applies transformation rules: `rule_multiply` (repeat rows to reach target size), `rule_hostname` (randomize hostnames), `rule_ids` (sequential IDs), `rule_dates` (random dates in range), and `rule_crop` (trim to exact count). Each CSV type has separate `SIZE` and `UNIQUE_SIZE` env vars (e.g., `MAIN_JOBHOSTSUMMARY_SIZE=10000`, `MAIN_JOBHOSTSUMMARY_UNIQUE_SIZE=2000`). The output is saved as properly structured tarballs under `OUTPUT_DATA_PATH/Y/M/D/`. The script reuses the extraction Base class from the report pipeline, which required making the CSV selection logic pluggable via `csv_enabled()` method override.
- **Insight**: Separating "unique size" (number of distinct hosts) from "total size" (total rows including duplicates) in the generator mirrors how real Controller data looks -- the same host appears in multiple job runs, and reports need to correctly deduplicate.

### Makefile added for common development commands
- **Repo**: ansible/metrics-utility
- **Commits**: 0320d20 (#91)
- **What happened**: A `Makefile` was added with targets: `help` (list targets), `sync` (uv sync), `test` (uv run pytest -s -v), `coverage` (pytest with --cov), `lint` (ruff check), and `fix` (ruff check --fix + ruff format). This provides consistent entry points for development tasks.
- **Insight**: The `make fix` target (ruff check --fix + ruff format) is the standard pre-commit cleanup command referenced in CLAUDE.local.md.

### Dead code removal via vulture: report_renewal_guidance_v2, base_command, Collection factories
- **Repo**: ansible/metrics-utility
- **Commits**: 5341400 (#112)
- **What happened**: Running `vulture` (a dead code detector) identified several unused code paths that were removed: (1) `report_renewal_guidance_v2.py` (434 lines) -- an entire report class that was never wired into the factory and appears to have been a copy-paste draft of CCSPv2 for renewal guidance. (2) `base_command.py` -- a custom `BaseCommand` that was never imported; actual commands use Django's `django.core.management.base.BaseCommand` directly. (3) Leftover `self.extension = 'parquet'` attributes in all three extractors (directory, S3, controller_db) -- remnants from a removed Parquet support path. (4) `Base.get_logger()` static method in the dataframe engine. (5) Unused conftest helper functions in test files. Debug utility functions (`print_debug`, `print_data`, `set_ccspv2_vars`) were initially removed but restored since they are used interactively for debugging.
- **Insight**: Running `vulture` periodically catches dead code that accumulates from refactoring (like the parquet extension attribute surviving three extractors) and abandoned features (like the never-wired ReportRenewalGuidanceV2).

### RENEWAL_GUIDANCEv2 report type fully removed as dead code
- **Repo**: ansible/metrics-utility
- **Commits**: 5341400 (#112), b487ac2 (#131)
- **What happened**: PR #112 removed the `report_renewal_guidance_v2.py` file (434 lines) that was never wired into the factory. PR #131 completed the cleanup by removing the `RENEWAL_GUIDANCEv2` branch from both the dataframe engine factory and report factory. The dataframe factory's `RENEWAL_GUIDANCEv2` branch had been using CCSP dataframe engines (jobhost summary + content usage) instead of the DB host metric engine that `RENEWAL_GUIDANCE` uses -- meaning even if someone set `REPORT_TYPE=RENEWAL_GUIDANCEv2`, the report would have received wrong data. The removal of the report factory branch was safe because it just delegated to `_get_report_renewal_guidance()` (same as regular `RENEWAL_GUIDANCE`).
- **Insight**: Dead code that composes wrong engine types is worse than simply unused -- it could silently produce incorrect reports if accidentally activated.

### Dev scripts use `gtime` on macOS for GNU time compatibility
- **Repo**: ansible/metrics-utility
- **Commits**: 38e2849 (#125)
- **What happened**: The performance benchmarking scripts (`run-ccsp2-build`, `run-ccsp2-gather`, `run-perf`, `run-renewal`) used `/usr/bin/time --format=...` for memory/CPU/time reporting, which requires GNU time. On macOS, `/usr/bin/time` is the BSD version (no `--format`), and GNU time is installed as `gtime` via `brew install gnu-time`. The fix added `TIME=\`command -v gtime >/dev/null 2>&1 && echo 'gtime' || echo '/usr/bin/time'\`` to auto-detect and use the correct binary.
- **Insight**: When shell scripts depend on GNU-specific tool options, use `command -v` to detect the platform-appropriate binary name rather than hardcoding a path that only works on Linux.

### build_report --until defaults to today when --since is provided
- **Repo**: ansible/metrics-utility
- **Commits**: fd79f40 (#127)
- **What happened**: When `--since` was provided to `build_report` without `--until`, the report would fail or produce unexpected results because `opt_until` was `None`. The fix defaults `--until` to today (midnight UTC) when `--since` is provided but `--until` is not, with an info log message. When `--since` is absent, `--until` remains `None` (the `--month` flow handles dates differently). This only applies to the build_report command (gather already handled this differently via `_handle_datelike`).
- **Insight**: When a command accepts a date range via `--since`/`--until`, providing a sensible default for the missing end bound (today) prevents confusing errors and matches user expectations.

### Dead parquet code removed from ExtractorDirectory
- **Repo**: ansible/metrics-utility
- **Commits**: b487ac2 (#131)
- **What happened**: Three methods (`mapping`, `read_parquet_file`, `read_parquet_files`) were removed from `ExtractorDirectory`. These were inherited from an S3-based extractor design and referenced `self.s3` which only exists in `S3Handler`, meaning they would crash with `AttributeError` if called. The leftover `# Read parquet in memory in batches` comment was also corrected to `# Read tarball in memory in batches`. Additionally, `logging.warn()` (deprecated) was updated to `logging.warning()`.
- **Insight**: Methods referencing instance attributes from a different class hierarchy (`self.s3` in a non-S3 class) are guaranteed-dead code -- they would crash if called.

### MetricsException base class unifies all custom exceptions
- **Repo**: ansible/metrics-utility
- **Commits**: 7bde0de (#150)
- **What happened**: All custom exception classes (`BadShipTarget`, `MissingRequiredEnvVar`, `BadRequiredEnvVar`, etc.) previously each defined their own `__init__` with `self.name = message`. A `MetricsException` base class was created with the shared `__init__`, and all 9 exception classes were changed to simple `pass` subclasses. This enabled catching all metrics-specific errors with a single `except MetricsException` in `ManagementUtility.run_subcommand()`, replacing the long exception tuples in each command's `handle()`.
- **Insight**: A shared exception base class is essential when multiple commands need the same error-handling behavior -- it eliminates the need to enumerate every exception subclass in every try/except block.

### `help` and `help_texts` moved from constructor to class-level attributes
- **Repo**: ansible/metrics-utility
- **Commits**: 9e038d9 (#156)
- **What happened**: Both `build_report` and `gather` commands defined `self.help_texts = {...}` inside `__init__`. This was moved to a class-level attribute `help_texts = {...}`, and the `__init__` method was removed entirely from both commands (the super().__init__() call was the only remaining content). The `help = '...'` Django attribute was also moved to class level, fixing the earlier shadowing issue from #128/#141.
- **Insight**: Django command attributes that are constant (`help`, `help_texts`) belong at class level, not in `__init__` -- class-level is cleaner, doesn't require calling `super().__init__()`, and avoids accidentally shadowing Django's own `help` attribute.

### `build_report` now shows ENVIRONMENT section in `--help` output
- **Repo**: ansible/metrics-utility
- **Commits**: 54175a4 (#162)
- **What happened**: The `build_report` command's `create_parser()` was overridden to use `RawDescriptionHelpFormatter` and add an `epilog` listing key environment variables (`METRICS_UTILITY_REPORT_TYPE`, `METRICS_UTILITY_SHIP_TARGET`, `METRICS_UTILITY_SHIP_PATH`, `METRICS_UTILITY_DEDUPLICATOR`) with their descriptions and valid values. This makes `manage.py build_report --help` self-documenting for env var configuration.
- **Insight**: Django management commands can document env vars in `--help` output by overriding `create_parser()` with `RawDescriptionHelpFormatter` + `epilog` -- this is more discoverable than README-only documentation.

### Code cleanup: unified os.getenv, removed dead code, separated get_install_type
- **Repo**: ansible/metrics-utility
- **Commits**: bb5134f (#187)
- **What happened**: A batch cleanup across 16 files: (1) All `os.environ.get(key)` calls were replaced with `os.getenv(key)` using ast-grep, and `os.getenv(key, None)` calls had the redundant `None` default dropped. (2) Dead code was removed from `S3Handler` (unused `self.s3`/`self.s3_bucket`/`self.s3_client` assignments in `__init__`, and an unused `list_subdirs` method) and from `collector.py` (commented-out license check code). (3) The `get_install_type()` function was extracted from the `config` collector into its own standalone function. (4) `validate_ship_path` was fixed to not mutate the global `VALID_SHIP_TARGET_GATHER` set -- it was adding `'controller_db'` to the set, which would persist across calls. (5) `f'{val}'` patterns were simplified to just `val` where the f-string was unnecessary.
- **Insight**: Batch cleanups with ast-grep can unify coding patterns (like `os.environ.get` vs `os.getenv`) across an entire codebase in one pass -- but always check for side effects like the mutable global set that was being modified in `validate_ship_path`.

### FutureWarning suppressed and duplicate report messages consolidated
- **Repo**: ansible/metrics-utility
- **Commits**: c879d29 (#200)
- **What happened**: The `logger.py` module was updated to suppress `FutureWarning` from pandas/openpyxl when running via `manage.py` (detected by checking `sys.argv[0].endswith('manage.py')`). The duplicate "Report generated into:" message was removed from `ReportSaverDirectory` -- this message was being emitted by both the saver and the calling command, resulting in two log lines for a single report generation.
- **Insight**: When multiple layers of the stack log the same event (report saved), consolidate the logging to a single point -- duplicate messages confuse operators into thinking the report was generated twice.

### Makefile uses `CONTAINER_ENGINE` variable for Docker/Podman compatibility
- **Repo**: ansible/metrics-utility
- **Commits**: 0be6cd0 (#198)
- **What happened**: The Makefile's `compose`, `clean`, and `psql` targets previously hardcoded `docker` as the container engine. A `CONTAINER_ENGINE ?= docker` variable was added at the top, and all `docker compose` calls were changed to `${CONTAINER_ENGINE} compose`. This enables Podman users to run `make compose CONTAINER_ENGINE=podman`.
- **Insight**: Using a `CONTAINER_ENGINE` variable with a default of `docker` is a low-effort way to support both Docker and Podman without breaking existing workflows.

### Dev scripts (run-*-gather, run-renewal) now require `make compose` instead of starting their own containers
- **Repo**: ansible/metrics-utility
- **Commits**: 0799a24 (#245)
- **What happened**: The `run-ccsp2-gather` and `run-renewal` scripts previously contained inline logic to start a PostgreSQL container if one wasn't running, using `podman run` with hardcoded schema volumes. After `conf_setting` data was added to the Docker Compose setup (#242), this inline DB startup no longer produced the correct test data. Both scripts were simplified to just check `pg_isready -h localhost` and exit with an error message if the DB isn't running, directing the user to run `make compose` first. This removed ~25 lines of Podman container management code from each script.
- **Insight**: When test data requirements evolve (e.g., adding conf_setting rows), ad-hoc container startup in individual scripts diverges from the canonical `make compose` setup -- it's better to require the single source of truth than to maintain parallel DB initialization paths.

### Library instants redesigned: relative_to parameter, truncation to period boundaries
- **Repo**: ansible/metrics-utility
- **Commits**: 184c585 (#267)
- **What happened**: The `library/instants.py` module was redesigned from simple "N units ago from now" functions to period-boundary-aware helpers. Previous functions like `last_day()`, `last_week()` just subtracted timedeltas from `now()`. The new versions: (1) `this_*()` functions return the *start* of the current period (e.g., `this_hour()` returns current hour with minutes/seconds zeroed). (2) `last_*()` functions return the start of the *previous* period relative to an optional `relative_to` parameter (defaulting to the corresponding `this_*()` boundary). (3) `*_ago(n)` functions subtract N periods from the boundary. (4) `last_month()` and `months_ago()` handle year boundaries correctly using total-months arithmetic. (5) An `iso()` helper was added for datetime-to-string conversion. The debug logging was removed entirely.
- **Insight**: Period-boundary-aware datetime helpers (truncating to start-of-hour/day/week/month) are essential for billing and metrics collection where time ranges must align to period boundaries -- raw timedelta subtraction from `now()` produces non-aligned timestamps that cause off-by-one errors in aggregation.

### `anonymized_rollups/__init__.py` and `library/anonymize/` added as package entry points
- **Repo**: ansible/metrics-utility
- **Commits**: dbb7426 (#278)
- **What happened**: The `metrics_utility/anonymized_rollups/` package received an `__init__.py` with explicit `__all__` exports for all rollup classes and functions. A new `metrics_utility/library/anonymize/` package was added with an `anonymized_rollups_processor()` function that wraps `compute_anonymized_rollup()` -- this provides a clean library-level entry point for the metrics service to call anonymized rollup processing without importing CLI-specific code.
- **Insight**: Adding a library-level wrapper (`library.anonymize.anonymized_rollups_processor`) around the CLI-level rollup code follows the library's design principle of exposing a simple, parameter-driven API that the external service can call without knowing about the internal module structure.

### Library `tempdir` utility: timestamped names, cleanup control, and auto-cwd
- **Repo**: ansible/metrics-utility
- **Commits**: a1b2e88 (#280)
- **What happened**: The library's `tempdir()` context manager was enhanced from a simple stub: (1) directory names now include a UTC timestamp in `YYYY-MM-DD-HHMMSS+ZZZZ` format (with optional prefix), making it easy to identify when a temp directory was created; (2) a `cleanup=True/False` parameter controls whether the directory is deleted on exit (using `tempfile.TemporaryDirectory(delete=cleanup)`), enabling inspection of intermediate files during debugging; (3) the context manager automatically changes the working directory to the temp dir and restores the original on exit (even on exceptions). The `copy_table` function's `output_dir` parameter was also given a default of `'.'` (current directory) instead of `None`, so it works naturally when called from within a tempdir. Comprehensive tests cover directory creation, cwd change/restore, cleanup/preserve behavior, and exception safety.
- **Insight**: A tempdir utility that auto-cwd's and supports `cleanup=False` is essential for debugging collector pipelines -- when something goes wrong in a gather run, you can preserve the temp directory to inspect intermediate CSV files without modifying the code.

### Anonymized rollup collector failures now logged and continued instead of aborting
- **Repo**: ansible/metrics-utility
- **Commits**: 983daa9 (#283)
- **What happened**: The `compute_anonymized_rollup()` function previously called each collector (`execution_environments`, `unified_jobs`, `job_host_summary_service`, `main_jobevent_service`) directly, meaning any single collector failure would crash the entire rollup pipeline. Each collector call was wrapped in a `try/except Exception` that logs the error and falls back to an empty list (`[]`), allowing the remaining collectors to still run and produce partial rollup data. The function was also added to `anonymized_rollups/__init__.py` exports.
- **Insight**: In a multi-collector pipeline where each collector is independent, individual failures should be logged and continued rather than aborting the entire pipeline -- partial rollup data (e.g., jobs without events) is more valuable than no data at all.

### Library entry point added for `compute_anonymized_rollup_from_raw_data`
- **Repo**: ansible/metrics-utility
- **Commits**: de0a10c (#305)
- **What happened**: A `metrics_utility/library/anonymize/compute_from_raw_data.py` module was added that re-exports `compute_anonymized_rollup_from_raw_data` from the CLI-side `anonymized_rollups` package, providing a library-level entry point for the metrics service. This follows the existing pattern where `library/anonymize/anonymized_rollups_processor.py` wraps `compute_anonymized_rollup`.
- **Insight**: The library's `anonymize/` package now provides two entry points: `anonymized_rollups_processor` (for DB-connected rollups) and `compute_anonymized_rollup_from_raw_data` (for pre-collected CSV file rollups) -- both are re-exports from CLI code, keeping the library as a thin API surface.

### `anonymize_rollups()` signature: new rollups added as keyword-only arguments
- **Repo**: ansible/metrics-utility
- **Commits**: 7db682c (#357), a06338f (#362), 675c61a (#399)
- **What happened**: As new rollup types were added (`feature_flags_rollup`, `task_executions_rollup`), they were added to `anonymize_rollups()` as keyword-only arguments with defaults (`feature_flags_rollup=None`, `task_executions_rollup=None`). The `salt` positional parameter was also removed in #399 (since anonymization no longer hashes values). Initially `feature_flags_rollup` was a positional argument (#357), but was quickly changed to keyword-only (#362) to avoid breaking existing callers. The `compute_anonymized_rollup_from_raw_data()` function and `load_anonymized_rollup_data()` function were also removed from `anonymized_rollups.py` and relocated to test helpers, since the production pipeline uses a different entry point.
- **Insight**: When extending a function's signature with new optional parameters, always use keyword-only arguments (after `*`) to avoid breaking existing callers that pass positional arguments -- positional arguments are fragile when the parameter list grows.

### `library/anonymize/` re-export module removed
- **Repo**: ansible/metrics-utility
- **Commits**: 7db682c (#357)
- **What happened**: The `metrics_utility/library/anonymize/` package (which had `anonymized_rollups_processor.py` and `compute_from_raw_data.py` re-exporting CLI-side functions) was removed entirely. These re-exports had been added in #278 and #305 to provide library-level entry points for the metrics service, but the production code path no longer uses them -- the service calls the rollup functions directly.
- **Insight**: Re-export modules that exist solely to provide a "nicer" import path add maintenance burden without value if no external consumer uses that path -- remove them when the actual call sites are identified.

### Candlepin v2: mTLS billing with CandlepinStore abstraction and cert lifecycle
- **Repo**: ansible/metrics-utility
- **Commits**: 7833eda (#363)
- **What happened**: A major feature added Candlepin v2 billing support with mTLS certificate-based authentication for CRC ingress uploads. The implementation spans multiple new modules: (1) `library/candlepin/client.py` -- a `CandlepinClient` for interacting with the Candlepin API (check-in, cert regeneration, consumer registration, org discovery via `GET /users/{username}/owners`). (2) `library/candlepin/lifecycle.py` -- certificate parsing, renewal checks (configurable via `METRICS_UTILITY_CANDLEPIN_RENEWAL_DAYS`), and orchestration. (3) `library/candlepin/store.py` -- a `CandlepinStore` ABC with two implementations: `LocalCandlepinStore` (filesystem at `/var/lib/awx/candlepin-certs`, atomic writes with 0600 perms) and `DBCandlepinStore` (reads from AWX `conf_setting` using `Setting.objects.filter()` + `decrypt_field()`, writes are stubbed). The store factory `get_candlepin_store()` is controlled by `METRICS_UTILITY_CANDLEPIN_STORAGE=local|db` (default: local). (4) `management/commands/candlepin_manage.py` -- a CLI command for manual registration and lifecycle management. (5) `package_crc.py` gained `_get_cert_ingress_url()` which prepends `cert.` to the hostname for mTLS endpoints. The data flow is: AWX Controller registers with Candlepin and stores the cert in `conf_setting` -> metrics-utility reads and decrypts it via DBCandlepinStore -> caches locally in LocalCandlepinStore -> all subsequent uploads use local files. Registration and lifecycle are enabled by default (`METRICS_UTILITY_CANDLEPIN_REGISTRATION_ENABLED` and `METRICS_UTILITY_CANDLEPIN_LIFECYCLE_ENABLED` default to True). The PR also added `cryptography>=44.0.1` as a dependency (excluding CVE-2024-12797). RHSM CA is auto-detected from `/etc/rhsm/ca/` when `METRICS_UTILITY_CANDLEPIN_CA` is unset.
- **Insight**: The CandlepinStore abstraction (local filesystem default, DB opt-in) enables standalone deployments to run the full Candlepin lifecycle without an active AWX database connection -- the DB-first path reads from Controller's `conf_setting` and caches locally, so subsequent runs work offline.

### Pandas 3.0 compatibility: NaN-as-float breaks None identity checks
- **Repo**: ansible/metrics-utility
- **Commits**: 7833eda (#363)
- **What happened**: The `uv.lock` regeneration during the Candlepin v2 work upgraded pandas from 2.3.3 to 3.0.3, which introduced several breaking changes: (1) Missing values in string-dtype columns are now `float('nan')` instead of `None`, breaking `if x is None` guards in `extract_collection_name()`, `extract_role_name()`, and `stringify()`. Fix: replace with `if not isinstance(x, str)` or `isinstance(v, str)`. (2) The compound serial deduplication in `ccsp.py` was critically broken -- `compute_serial()` returns `None` for no-serial hosts, which pandas 3.0 stores as `float('nan')`. Since `bool(float('nan'))` is `True`, all no-serial hosts were grouped into a single `serial_to_hosts[nan]` bucket and merged into one managed-node entry. Fix: `if serial is not None and not pd.isna(serial)`. (3) Deprecated frequency alias `'H'` renamed to `'h'`. (4) openpyxl minimum bumped to `>=3.1.5` (pandas 3.0 requirement). (5) `pandas.read_excel` now returns `pd.NaT` instead of `float NaN` for null timedelta cells.
- **Insight**: The pandas None-to-NaN change is a silent data corruption risk -- `bool(float('nan'))` is `True`, so truthy checks on serial numbers that were previously `None` (falsy) now incorrectly match, causing deduplication to merge unrelated hosts. Always use `pd.isna()` or `is not None and not pd.isna()` for pandas nullable checks.

### IndirectManagedNodesAnonymizedRollup tags indirect node records
- **Repo**: ansible/metrics-utility
- **Commits**: 87c6925 (#446)
- **What happened**: A new `IndirectManagedNodesAnonymizedRollup` class was added to process indirect managed node audit data collected from the Controller database. It follows the `BaseAnonymizedRollup` pattern: sets `rollup_name = 'indirect_managed_nodes'`, `collector_names = ['main_indirectmanagednodeaudit']`, and in `prepare()` injects `managed_node_type = INDIRECT` constant on all records, converts ID columns to strings, handles NaN-to-None conversion, and serializes timestamps to ISO format. The class was registered in `anonymized_rollups/__init__.py` with explicit `__all__` export.
- **Insight**: New rollup types follow a consistent pattern: subclass `BaseAnonymizedRollup`, set `rollup_name` and `collector_names`, implement `prepare()` to transform the DataFrame, and register in `__init__.py` -- making it straightforward to add new collector types.

### cleanup_glob extracted to shared test utility with empty dir removal
- **Repo**: ansible/metrics-utility
- **Commits**: eb853d8 (#448)
- **What happened**: Four test files (`test_directory_gather.py`, `test_gather_ranges.py`, `test_jobhostsummary_gather.py`, `test_json_schema.py`) each had their own inline `cleanup_glob` fixture that only removed tar.gz files but left empty parent directories behind (e.g., `test_data/data/2025/06/`). A shared `cleanup_glob(file_glob)` function was extracted to `test/util.py` that removes matching files AND their empty parent directories via `os.removedirs()`. The `test_json_schema.py` fixture was also fixed to add a missing `yield` (it was only cleaning before tests, not after). All four test files were updated to import and call the shared helper.
- **Insight**: Test cleanup functions that only remove files but leave empty directories accumulate directory cruft over time -- `os.removedirs()` walks up and removes each empty parent, providing a clean slate without hardcoding directory paths.

### IndirectManagedNodesAnonymizedRollup: dedup via merge(), privacy via base(), full pipeline integration
- **Repo**: ansible/metrics-utility
- **Commits**: fd9f206 (#453), f5786a0 (#457)
- **Superseded by**: #464/#475 -- see "Indirect nodes collector v2" entry below
- **What happened**: The `IndirectManagedNodesAnonymizedRollup` class (added in #446) was significantly redesigned across two PRs. (1) PR #453 changed `prepare()` from storing all records as dicts to extracting only unique `host_remote_id` values, returning `{indirect_node_ids: [...], indirect_nodes_total: N}`. A `merge()` method was added that deduplicates host IDs across 24 hourly collections using set union, enabling accurate daily billing counts. The rollup was also integrated into `anonymize_rollups()` as a keyword-only parameter `indirect_managed_nodes_rollup`, and `flatten_json_report()` was updated to extract `rollup_period_indirect_managed_nodes_total` into the statistics section. (2) PR #457 added a `base()` method that strips `indirect_node_ids` from the final payload for privacy, returning only `{indirect_nodes_total: N}`. It also renamed the statistic key to `rollup_period_indirect_managed_nodes_all_total`, wired the collector into `compute_anonymized_rollup()` in the test helpers, added SQL test data (`main_indirectmanagednodeaudit.sql`), and added gather-to-json integration test coverage. The CI workflow was updated to create the `main_indirectmanagednodeaudit` table.
- **Insight**: The three-method pattern (`prepare()` extracts and deduplicates per-hour, `merge()` deduplicates across hours, `base()` strips PII before transmission) is a clean separation for rollup types where per-collection granularity is needed for accuracy but sensitive identifiers must not leave the system. **Note**: The host_remote_id-based deduplication was replaced in #475 with host_name-based grouping by collection, since host_remote_id is always NULL for indirect managed nodes.

### Filter option collectors: plain SQL snapshots for dashboard cache tables
- **Repo**: ansible/metrics-utility
- **Commits**: b3224a7 (#455)
- **What happened**: Four new collector functions (`fetch_organizations`, `fetch_job_templates`, `fetch_projects`, `fetch_labels`) were added to `library/collectors/dashboard/filter_options.py`. These are intentionally NOT time-windowed DataFrame collectors -- they return plain `[{id, name}, ...]` dicts from full-table snapshots (`SELECT id, name FROM main_organization ORDER BY name`). Each has a corresponding `get_*_query()` function that returns `(sql, params)` tuples following the `dashboard/queries.py` convention. A shared `_fetch_id_name()` helper handles cursor execution and dict construction. All eight functions are exported from `dashboard/__init__.py`. 24 tests validate both query structure and fetch behavior with mock cursors.
- **Insight**: Not all collectors need to be time-windowed DataFrame collectors -- full-table snapshots for small reference tables (orgs, templates, projects, labels) are a valid pattern when the goal is populating local cache tables to remove runtime Controller DB dependency from filter dropdowns.

### Indirect nodes collector v2: daily slicing by job.finished with collection grouping
- **Repo**: ansible/metrics-utility
- **Commits**: b5d87d7 (#464), 8ae73e6 (#465), a5acc07 (#475)
- **What happened**: The `main_indirectmanagednodeaudit` collector and its rollup were significantly redesigned across three PRs. (1) PR #464 briefly converted the collector from hourly time-windowed (`daily_slicing` with `since`/`until` on `created`) to a daily full-table snapshot (`until_slicing`, no date filter), simplifying `merge()` to a pass-through. (2) PR #465 added tests for NULL join references and orphaned records (deleted foreign keys produce NULL via LEFT JOIN). (3) PR #475 superseded the snapshot approach: the collector was converted back to `daily_slicing` but now filters by `main_unifiedjob.finished` (not `created`) using `date_where()`, matching the pattern used by other daily collectors. The version was bumped to `2.0`. The rollup was completely rewritten: `prepare()` now parses the `events` JSON column via `_extract_collection_names()` (using `DataframeContentUsage.extract_collection_name()` to extract two-part Ansible collection names like `cisco.ios`), groups by `(organization_name, collection_name)` using a `||` separator key, and counts unique `host_name` values per group (not `host_remote_id`, which is always NULL for indirect nodes). `merge()` was restored to union host name sets across batches. `base()` strips all PII: removes `host_names` and `organization_name`, collapses org-level groups into collection-level totals with re-deduplication of hosts across orgs. A new `indirect_nodes_by_collection` array was added to `flatten_json_report()`.
- **Insight**: The snapshot approach (#464) was abandoned because AWX deletes `IndirectManagedNodeAudit` records after a configurable retention period (default 7 days) -- snapshot collectors produce inconsistent results across customers with different retention settings and cause double-counting when summing daily totals. Filtering by `job.finished` aligns the collector with calendar-day boundaries. Grouping by Ansible collection name (extracted from the `events` JSON) provides usage visibility per collection without exposing customer-identifiable data (collection names are public Galaxy labels).

### AWX schema extraction script strips pg-version-dependent output for stable diffs
- **Repo**: ansible/metrics-utility
- **Commits**: a33aadc (#461)
- **What happened**: The `tools/docker/latest.sql` AWX schema dump was updated to current `devel` and a local extraction script (`tools/docker/extract-awx-schema.sh`) plus a weekly CI workflow were added. The script strips five categories of pg-version-dependent output to keep diffs stable across PostgreSQL upgrades: (1) `-- Dumped from/by pg_dump version` comments, (2) `\restrict`/`\unrestrict` security directives (pg18+), (3) `SET transaction_timeout` (pg18+), (4) named NOT NULL constraints like `CONSTRAINT foo_not_null NOT NULL` back to plain `NOT NULL` (pg18+), and (5) consecutive blank lines left by the removals. The script validates the AWX repo is on `devel` and up to date with `origin/devel` (overridable with `--force`), uses `podman-compose` or `docker compose` auto-detection via `COMPOSE_CMD`, and has a 30-second retry budget for postgres readiness. The schema update revealed new `*_old` text columns from AWX migration 0185 (text-to-jsonb conversion) -- none are used by metrics-utility.
- **Insight**: Stripping pg-version-dependent output from schema dumps is essential for maintaining a reviewable `latest.sql` -- without it, upgrading the development PostgreSQL version produces a massive diff that obscures actual schema changes from AWX migrations.

### Schemas moved into metrics_utility package for pip installability
- **Repo**: ansible/metrics-utility
- **Commits**: 14ee699 (#444), 154b633 (#447)
- **What happened**: JSON schemas were moved from the top-level `schemas/` directory to `metrics_utility/schemas/` so they are included when the package is installed via pip. Changes: (1) `pyproject.toml` `package-data` updated to include `*.jsonschema` files. (2) `test_json_schema.py` switched from `pathlib.Path(request.config.rootpath).joinpath('schemas')` to `importlib.resources.files('metrics_utility.schemas')` for loading schemas, removing the `request` fixture parameter dependency. (3) The schema-review GitHub Actions workflow path filter updated to `metrics_utility/schemas/**`. (4) The standalone `tools/validator/validate.py` needed a follow-up fix (#447) to update its `SCHEMAS_DIR` from `Path(__file__) / ... / 'schemas'` to `Path(__file__) / ... / 'metrics_utility' / 'schemas'` -- it was missed in the initial move because the validator is a standalone tool, not part of the package.
- **Insight**: When moving package data files, update ALL consumers -- not just the package code and tests, but also standalone tools and CI workflows that reference the old path. Using `importlib.resources` instead of filesystem paths makes schema loading work regardless of how the package is installed.

### Dead code removal: by_organizations and by_collections from indirect node rollup
- **Repo**: ansible/metrics-utility
- **Commits**: e99260c (#479)
- **What happened**: `prepare()` and `merge()` were computing two midway aggregations (`by_organizations` and `by_collections`) that `base()` never read -- `base()` rebuilds its own collection summary directly from `groups`. The `_aggregate_by_key` helper existed solely to produce these fields. Removed the dead fields, the helper, and the three tests that covered only the removed behavior (-115 lines).
- **Insight**: When `base()` re-aggregates from raw groups at output time, midway aggregation structures computed in `prepare()`/`merge()` are dead code -- they add processing cost and test maintenance without producing any output.

### Module-level breakdown added to indirect nodes anonymized payload
- **Repo**: ansible/metrics-utility
- **Commits**: bc77d54 (#482)
- **What happened**: A new `indirect_nodes_by_module` array was added to the anonymized payload alongside the existing `indirect_nodes_by_collection`. Each entry contains a full FQCN (e.g., `cisco.ios.ios_command`) and a `host_count`. The implementation adds a parallel `module_groups` structure through `prepare()`, `merge()`, and `base()`. A `_parse_events()` helper was extracted from `_extract_collection_names()` to share JSON parsing logic with the new `_extract_module_names()`. The full FQCNs are already present in the `events` column -- the existing code was stripping them to collection prefix, this PR retains the full name in a parallel structure. No SQL changes, no collector changes. Module-level host counts can exceed collection-level counts for the same collection (a host touched by two modules appears in both module entries but only once in the collection total).
- **Insight**: When the raw data already contains the full FQCN and you need both collection-level and module-level breakdowns, adding a parallel grouping structure (same key pattern, same prepare/merge/base lifecycle) is cleaner than trying to derive one from the other. The `_parse_events()` extraction is a good refactor that eliminates duplicated JSON-parsing/type-checking logic.

### Segment filters properties whose key contains "name" -- field rename required
- **Repo**: ansible/metrics-utility
- **Commits**: 44d165c (#484), 0b85f12 (#485)
- **What happened**: Segment downstream destinations silently drop any property whose key contains the substring `name`. This caused `collection_name` and `module_name` fields to be silently dropped from the anonymized payload. Fix: rename `collection_name` to `collection` and `module_name` to `module` in all Segment-bound output. PR #484 applied this to the indirect nodes rollup (`by_collection` and `by_module` arrays, plus internal group dicts). PR #485 applied the same rename to the events modules rollup (`module_stats`, `collection_stats`, `role_stats`), using a `_normalize_stats_item()` helper that renames at output time in `base()` so internal DataFrame column names remain unchanged.
- **Insight**: Segment's property-name filtering is a silent data loss hazard -- fields are simply absent in downstream destinations with no error or warning. Always verify that Segment payload field names don't contain reserved substrings like "name" before shipping. The rename-at-output-time pattern (keeping internal names stable, renaming in base()) minimizes blast radius of the schema change.

### Events rollup reshaped: direct event counters replace inferred task outcomes
- **Repo**: ansible/metrics-utility
- **Commits**: daefa84 (#480)
- **What happened**: The `EventModulesAnonymizedRollup` was fundamentally restructured. The old approach inferred task outcomes (success, failed, unreachable, skipped) from event sequences, which was error-prone due to loops, block/rescue, and retries. The new approach counts Ansible event types directly: one counter per known event type (`runner_on_ok_total`, `runner_on_failed_total`, `runner_on_unreachable_total`, `runner_on_async_ok_total`, `runner_on_async_failed_total`, `runner_item_on_ok_total`, `runner_item_on_failed_total`, `runner_retry_total`, `ignore_errors_total`). Key changes: (1) canonical event types extracted to `metrics_utility/event_types.py` as a `RUNNER_EVENTS` frozenset shared by both the collector and rollup. (2) `ignore_errors` extraction in the SQL collector now checks both `event_data.ignore_errors` (for runner_on_failed) and `event_data.res._ansible_ignore_errors` (for runner_item_on_failed), since ansible-core stores them differently. (3) `playbook_on_stats` events removed from collection (high volume, redundant with runner-level counters). (4) `event_data_length` (via `octet_length(e.event_data)`) added for performance modeling. (5) `unique_hosts_total` removed (performance risk at scale). (6) `processed_events_total` renamed to `collected_events_total`.
- **Insight**: Counting raw event types rather than inferring task outcomes avoids misclassification caused by Ansible's complex execution model (loops produce both task-level and item-level events, block/rescue emits additional events, retries add runner_retry events). The separation of sync/async/item event counters lets consumers aggregate however they need without double-counting.

### `anonymize_rollups()` accepts `**kwargs` for backwards compatibility
- **Repo**: ansible/metrics-utility
- **Commits**: a0a82b3 (#513)
- **What happened**: The `anonymize_rollups()` function signature was extended to accept `**kwargs`, allowing callers to pass unknown keyword arguments without raising `TypeError`. This was needed because the metrics-service may pass new rollup parameters (added in newer service versions) to an older metrics-utility library version that doesn't yet know about those parameters. Without `**kwargs`, upgrading the service before the library would crash at the anonymization step.
- **Insight**: When a library function's signature is extended over time with new keyword-only parameters (as `anonymize_rollups()` has been with `feature_flags_rollup`, `task_executions_rollup`, `indirect_managed_nodes_rollup`), adding `**kwargs` as a catch-all ensures forwards compatibility -- the caller can pass parameters the library doesn't understand yet without crashing. This is especially important in cross-repo dependencies where the two sides may be deployed at different versions.

### Private collections filtered from indirect nodes anonymized payload
- **Repo**: ansible/metrics-utility
- **Commits**: a8fa4c1 (#496)
- **What happened**: The `anonymize_data()` function was extended to filter `indirect_nodes_by_collection` and `indirect_nodes_by_module` against the `collections.json` whitelist. For modules, `DataframeContentUsage.extract_collection_name()` derives the collection prefix from the FQCN before checking the whitelist. The `_load_known_collections()` function was refactored from `anonymized_rollups.py` and `events_modules_anonymized_rollup.py` into a shared `load_known_collections()` helper in `helpers.py`, eliminating duplication.
- **Insight**: Centralizing the collections.json loading into `helpers.py` ensures all rollup types use the same loader with the same error handling (returns empty dict on FileNotFoundError/JSONDecodeError). When multiple rollup types need the same reference data, extract the loader to a shared module rather than duplicating the file path resolution and error handling.

### Segment payload contract defined as TypedDict, OpenAPI schema generated from it
- **Repo**: ansible/metrics-utility
- **Commits**: cc6ae56 (#511)
- **What happened**: A new `metrics_utility/anonymized_rollups/types.py` module defines the full anonymized daily rollup Segment payload as nested `TypedDict` classes (`AnonymizedPayload` at the top, with `Statistics`, `JobsByJobType`, `ModuleStats`, `IndirectNodesByCollection`, etc.). `AnonymizedPayload` is exported from `anonymized_rollups/__init__.py`, and `flatten_json_report()` and `anonymize_rollups()` got their return type annotations changed from `dict[str, Any]` to `AnonymizedPayload`. Fields that only appear when event data exists (`module_stats`, `collection_stats`, `role_stats`, and several event-derived `Statistics` keys) are marked `NotRequired` -- matching the existing runtime behavior of omitting event fields when `collected_events_total == 0`. Shared field groups are composed via TypedDict inheritance (`JobStatsFields` + `HostSummaryFields` -> `JobsByJobType`). Two tools were added under `tools/`: `generate_segment_schema.py` emits an OpenAPI 3.1.0 schema (using pydantic `TypeAdapter(...).json_schema()` with `ref_template='#/components/schemas/{model}'`), and `validate_segment_contract.py` validates a rollup JSON file against the types in strict mode. Both wrap the TypedDict with `with_config(ConfigDict(extra='forbid'))` so unexpected keys are rejected. `pydantic>=2.9` and `pyyaml>=6.0` were added as dev-only dependencies.
- **Insight**: The TypedDict is the single source of truth for the aap-metrics <-> Analytics Segment contract, and the OpenAPI schema is generated from it rather than hand-maintained -- so the shared reference can never drift from the code that actually produces the payload. `NotRequired` encodes the "present only when events collected" behavior directly into the type, and `extra='forbid'` strict validation surfaces unexpected/typo'd keys that would otherwise be silently accepted. pydantic is only a dev dependency here because it is used solely by the schema/validation tooling, not by the runtime rollup path.

### Indirect managed nodes merged into the 'Usage by collections' report sheet
- **Repo**: ansible/metrics-utility
- **Commits**: c00f979 (#558)
- **What happened**: For the GA of indirect node reporting in AAP 2.7, the 'Usage by collections' sheet (both CCSP and CCSPv2) now folds in indirect managed node data. `Base._build_indirect_collections_long()` normalizes each INDIRECT job-host-summary row -- whose `events` list holds fully-qualified content names like `cisco.ios.ios_command` -- into per-collection "long" rows by exploding the list (one row per collection, dedup via a set), using `DataframeContentUsage.extract_collection_name()` to derive the collection. Those rows are concatenated onto the direct content-usage frame (restricted to the shared `COLLECTIONS_LONG_COLUMNS`) before the group-by. `_build_data_section_usage_by_collections()` gained an `indirects=None` parameter, so it is a no-op preserving direct-only behavior when no indirect data is passed. The report classes only pass indirects when `'indirectly_managed_nodes'` is in the optional sheets, matching the 'Usage by organizations' gating. Known imprecision: an indirect row's `task_runs` is attributed to *every* collection in its events list (the audit data doesn't break task counts down per collection) and `duration` is set to 0 -- host counts (the sheet's real purpose) stay accurate.
- **Insight**: Indirect audit data records a host's collection usage as a flat `events` list without per-collection task/duration breakdown, so exploding it into per-collection rows preserves the host counts that the sheet is about while knowingly over-counting task_runs per collection -- an acceptable trade documented in the code.
