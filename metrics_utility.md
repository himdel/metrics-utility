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

### Exit codes standardized: success=0, failure=1
- **Repo**: ansible/metrics-utility
- **Commits**: 34c711c (#18)
- **What happened**: The gather command previously called `exit(0)` for both success and all error cases, and `exit(-1)` for missing AWX modules. PR #18 standardized this: `exit(0)` on success, `exit(1)` on any error (bad config, upload failure, no data collected). A `NoAnalyticsCollected` exception was added to properly signal when no data was gathered, which also triggers `exit(1)`.
- **Insight**: Return code correctness matters for cron-based automation -- operators need `$?` to detect collection failures and trigger alerts.

### pyarrow dependency removed in favor of pure pandas
- **Repo**: ansible/metrics-utility
- **Commits**: eeb35bd (#14)
- **What happened**: The `pyarrow` import was removed from `extractor_directory.py` (it had already been commented out). The `setup.cfg` dependencies were cleaned up accordingly. Data reading uses `pandas` with CSV format throughout instead of Parquet.
- **Insight**: Removing pyarrow reduced the dependency footprint significantly -- pyarrow is a large native library that was unnecessary since the pipeline uses CSV, not Parquet.

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

### Dead parquet code removed from ExtractorDirectory
- **Repo**: ansible/metrics-utility
- **Commits**: b487ac2 (#131)
- **What happened**: Three methods (`mapping`, `read_parquet_file`, `read_parquet_files`) were removed from `ExtractorDirectory`. These were inherited from an S3-based extractor design and referenced `self.s3` which only exists in `S3Handler`, meaning they would crash with `AttributeError` if called. The leftover `# Read parquet in memory in batches` comment was also corrected to `# Read tarball in memory in batches`. Additionally, `logging.warn()` (deprecated) was updated to `logging.warning()`.
- **Insight**: Methods referencing instance attributes from a different class hierarchy (`self.s3` in a non-S3 class) are guaranteed-dead code -- they would crash if called.

### build_report --until defaults to today when --since is provided
- **Repo**: ansible/metrics-utility
- **Commits**: fd79f40 (#127)
- **What happened**: When `--since` was provided to `build_report` without `--until`, the report would fail or produce unexpected results because `opt_until` was `None`. The fix defaults `--until` to today (midnight UTC) when `--since` is provided but `--until` is not, with an info log message. When `--since` is absent, `--until` remains `None` (the `--month` flow handles dates differently). This only applies to the build_report command (gather already handled this differently via `_handle_datelike`).
- **Insight**: When a command accepts a date range via `--since`/`--until`, providing a sensible default for the missing end bound (today) prevents confusing errors and matches user expectations.

### Dev scripts use `gtime` on macOS for GNU time compatibility
- **Repo**: ansible/metrics-utility
- **Commits**: 38e2849 (#125)
- **What happened**: The performance benchmarking scripts (`run-ccsp2-build`, `run-ccsp2-gather`, `run-perf`, `run-renewal`) used `/usr/bin/time --format=...` for memory/CPU/time reporting, which requires GNU time. On macOS, `/usr/bin/time` is the BSD version (no `--format`), and GNU time is installed as `gtime` via `brew install gnu-time`. The fix added `TIME=\`command -v gtime >/dev/null 2>&1 && echo 'gtime' || echo '/usr/bin/time'\`` to auto-detect and use the correct binary.
- **Insight**: When shell scripts depend on GNU-specific tool options, use `command -v` to detect the platform-appropriate binary name rather than hardcoding a path that only works on Linux.

### Verbose debug output via --verbose flag and debug_utils module
- **Repo**: ansible/metrics-utility
- **Commits**: a93b6bf (#66)
- **What happened**: A `debug_utils.py` module was added at the project root with `print_debug(text)` and `print_data(df, caption)` functions that only produce output when `--verbose` is in `sys.argv`. `print_data` drops a hardcoded list of noisy columns (timestamps, IDs, variables) before displaying dataframes with `pprint`. A `set_ccspv2_vars()` helper was also added for setting all CCSPv2 env vars programmatically (useful for IDE debugging). The debug calls were wired into the dataframe engines at key aggregation points (before/after groupby, after outer join) to trace the data pipeline.
- **Insight**: The `--verbose` flag with strategic print points at each aggregation step makes it possible to trace billing data through the multi-stage merge pipeline without modifying code -- essential for debugging incorrect report values.

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

### `anonymized_rollups/__init__.py` and `library/anonymize/` added as package entry points
- **Repo**: ansible/metrics-utility
- **Commits**: dbb7426 (#278)
- **What happened**: The `metrics_utility/anonymized_rollups/` package received an `__init__.py` with explicit `__all__` exports for all rollup classes and functions. A new `metrics_utility/library/anonymize/` package was added with an `anonymized_rollups_processor()` function that wraps `compute_anonymized_rollup()` -- this provides a clean library-level entry point for the metrics service to call anonymized rollup processing without importing CLI-specific code.
- **Insight**: Adding a library-level wrapper (`library.anonymize.anonymized_rollups_processor`) around the CLI-level rollup code follows the library's design principle of exposing a simple, parameter-driven API that the external service can call without knowing about the internal module structure.
