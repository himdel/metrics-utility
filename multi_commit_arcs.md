# Notable Multi-Commit Arcs

Sequences where an approach was tried, revised, and sometimes revised again across multiple PRs — showing the evolution of a decision.

## metrics-service arcs

### Validation saga
- **Files**: settings_and_configuration.md
- **Evolution**: added -> broke -> turned off -> re-enabled with proper messages (5 PRs over 3 months)

### Worker count
- **Files**: task_system.md, docker_and_deployment.md
- **Evolution**: 4 -> 1 (band-aid) -> 4 (real fix with atomic updates and advisory locks)

### Feature flag evolution
- **Files**: task_system.md
- **Evolution**: single flag -> overly broad scope -> three independent flags

### URL prefix
- **Files**: settings_and_configuration.md
- **Evolution**: env var -> renamed env var -> Django setting -> proper prefix interpretation (4 iterations)

### Secrets management
- **Files**: settings_and_configuration.md
- **Evolution**: SEGMENT_WRITE_KEY from config -> from file with base64 -> from file without base64

### CodeQL
- **Files**: ci_cd.md
- **Evolution**: created then immediately reverted (wrong file contents, 5 minutes apart)

## metrics-utility arcs

### Advisory lock saga
- **Files**: architecture.md, dependencies_and_packaging.md, bugs_and_pitfalls.md
- **Evolution**: AWX import -> `find_spec` detection for AWX vs ansible_base (#51) -> `find_spec` broke, switched to try/except (#94) -> custom `library/lock.py` with raw PostgreSQL hashtext (#259) -> django-ansible-base dep removed (#395)
- **PRs**: 4 (#51, #94, #259, #395)

### Anonymization strategy evolution
- **Files**: architecture.md, metrics_collection.md, metrics_utility.md
- **Evolution**: SHA-512 hashing of unknown values (#239) -> SHA-256 for shorter hashes (#250) -> "Unknown" replaced with literal string instead of hash (#319) -> "Unknown" renamed to "Custom" (#343) -> salt parameter and hash function removed entirely (#399)
- **PRs**: 5 (#239, #250, #319, #343, #399)

### SonarCloud CI integration
- **Files**: ci_cd.md
- **Evolution**: added with `pull_request_target` (#89/#93) -> PR head checkout fix (#106) -> dual push/PR conditional scan (#108/#109) -> per-PR dropped, reverted to `pull_request` (#318) -> PwnRequest remediation via `workflow_run` split (#321)
- **PRs**: 6 (#89, #93, #106, #108, #318, #321)

### StorageSegment chunking and delivery reliability
- **Files**: architecture.md, bugs_and_pitfalls.md
- **Evolution**: basic chunking at 32KB limit (#249) -> metadata overhead and dict-vs-list handling fixed, limit reduced to 24KB (#281) -> `use_bulk` removed, trial-serialization sizing (#372) -> `sync_mode=True` as only reliable delivery method after silent event loss (#383)
- **PRs**: 4 (#249, #281, #372, #383)

### insights-analytics-collector vendoring and cleanup
- **Files**: architecture.md, dependencies_and_packaging.md
- **Evolution**: external dependency (#5) -> vendored into `metrics_utility/base/` (#92) -> unused extension points removed (#111) -> dead code removed from base Collector (#265)
- **PRs**: 4 (#5, #92, #111, #265)

### Date parser unification
- **Files**: architecture.md, bugs_and_pitfalls.md
- **Evolution**: bare numbers accepted silently (#114 fix) -> separate parsers for gather vs build (#128) -> `_handle_datelike` extracted (#156) -> three parsers merged into one `parse_date_param` (#157)
- **PRs**: 4 (#114, #128, #156, #157)

### Library/CLI collector split
- **Files**: architecture.md, metrics_utility.md
- **Evolution**: all collectors in CLI `collectors.py` (original) -> library collectors with env-var-free interfaces (#248) -> CLI collectors replaced with thin wrappers delegating to library (#339) -> `copy_table` returns DataFrame instead of files (#327)
- **PRs**: 3 (#248, #327, #339)

### psycopg2/psycopg3 compatibility
- **Files**: dependencies_and_packaging.md, architecture.md
- **Evolution**: duck-typing `hasattr(cursor, 'copy_expert')` for COPY operations (#7) -> `UndefinedTable` exception mismatch between psycopg versions (#261) -> library `copy_table` switched to `cursor.fetchall()` + DataFrame return, dropping psycopg2 support entirely (#327)
- **PRs**: 3 (#7, #261, #327)

### Gather `--until` inclusive vs exclusive
- **Files**: bugs_and_pitfalls.md
- **Evolution**: exclusive upper bound (original) -> changed to inclusive end-of-day (#175) -> reverted back to exclusive because it broke `since == until` and conflicted with daily_slicing (#192)
- **PRs**: 2 (#175, #192)

### `self.help` shadowing Django's BaseCommand.help
- **Files**: bugs_and_pitfalls.md
- **Evolution**: refactored help text into `self.help = {...}` dict (#128) -> shadowed Django's help string, caused dict repr in `--help` -> fixed by renaming to `self.help_texts` (#141) -> moved from constructor to class-level attributes (#156)
- **PRs**: 3 (#128, #141, #156)

### Env validation ordering
- **Files**: bugs_and_pitfalls.md, settings_and_configuration.md
- **Evolution**: validation placed in `add_arguments()` (#137) -> broke `--help`, moved to `handle()` (#141) -> placed before `init_logging`, errors invisible (#141) -> moved after `init_logging` (#146)
- **PRs**: 3 (#137, #141, #146)

### Missing `__init__.py` (recurring bug)
- **Files**: bugs_and_pitfalls.md
- **Evolution**: forgot in #9 -> fixed in #10 -> forgot again in #24 -> fixed in #25 -> forgot again in #215/#239/#250 -> fixed in #278
- **PRs**: ~6

### Python version bounds
- **Files**: dependencies_and_packaging.md
- **Evolution**: `>=3.12` -> `>=3.11` (match AWX, #45) -> `>=3.11, <3.13` (upper bound, #49) -> `>=3.11` (removed upper bound for 3.13, #96) -> `>=3.12` (for PyPI library, #271)
- **PRs**: 4 (#45, #49, #96, #271)

### Dataframe engines: monolith to library
- **Files**: architecture.md
- **Evolution**: monolithic `DataframeSummarizedByOrgAndHost` -> Base class extracted, CCSPv2 engine added (#17) -> deduplication extracted as separate pipeline step (#162) -> dataframes moved to library with loading/transform split (#237)
- **PRs**: 3 (#17, #162, #237)

### Tarball naming and filtering
- **Files**: architecture.md
- **Evolution**: anonymous tarball names -> collection name added to filename (#226) -> extractors filter tarballs and files by collection name (#227) -> build report only extracts needed CSVs (#86/#91)
- **PRs**: 3-4 (#86, #91, #226, #227)

### `METRICS_UTILITY_OPTIONAL_COLLECTORS` empty string handling
- **Files**: settings_and_configuration.md, bugs_and_pitfalls.md
- **Evolution**: whitespace caused validation failure (#178) -> added `''` to VALID_COLLECTORS as workaround (#178) -> replaced with `filter(bool, ...)` for clean parsing (#263)
- **PRs**: 2 (#178, #263)

### MAX_GATHER_PERIOD: constant to configurable
- **Files**: metrics_collection.md, settings_and_configuration.md
- **Evolution**: hardcoded `timedelta(weeks=4)` in 3 places -> centralized as `MAX_GATHER_PERIOD_WEEKS = 4` class constant (#168) -> replaced with `METRICS_UTILITY_MAX_GATHER_PERIOD_DAYS` env var defaulting to 28 (#181)
- **PRs**: 2 (#168, #181)

### Anonymized rollup data structure evolution
- **Files**: architecture.md, metrics_utility.md
- **Evolution**: nested JSON structure (#239) -> flattened with `flatten_json_report()` (#250) -> flat DataFrame changed to dict with totals (#288) -> JSON round-trip verification after each batch (#331) -> field names changed from DB columns to descriptive names (#343)
- **PRs**: 5 (#239, #250, #288, #331, #343)

### `anonymize_rollups()` signature evolution
- **Files**: metrics_utility.md
- **Evolution**: basic positional params (#239) -> `feature_flags_rollup` added as positional (#357) -> changed to keyword-only (#362) -> `salt` removed (#399) -> `task_executions_rollup` added as keyword-only (#399)
- **PRs**: 4 (#357, #362, #399, plus original #239)

### Docker Compose port flip-flop
- **Files**: bugs_and_pitfalls.md
- **Evolution**: 5432 (original) -> changed to 5433 to avoid local conflicts (#274) -> reverted 15 minutes later because it broke CI (#276)
- **PRs**: 2 (#274, #276)

### `get_optional_collectors()` location
- **Files**: settings_and_configuration.md
- **Evolution**: local to `collectors.py` (original) -> moved to `metric_utils.py` (#75) -> moved back to `collectors.py` (#153) -> moved to `base/utils.py` (#185)
- **PRs**: 3 (#75, #153, #185)

### Indirect nodes collector naming and error handling
- **Files**: settings_and_configuration.md, metrics_collection.md
- **Evolution**: `indirect_nodes` with `INCLUDE_INDIRECT` module constant (#75) -> renamed to `main_indirectmanagednodeaudit`, switched to `get_optional_collectors()` (#78) -> `ProgrammingError` catch for AAP 2.4 (#172) -> `UndefinedTable` also caught for psycopg3 (#261)
- **PRs**: 4 (#75, #78, #172, #261)

### AWX imports removal from collectors
- **Files**: architecture.md, metrics_collection.md
- **Evolution**: collectors imported AWX Python modules directly (original) -> replaced with direct SQL against `conf_setting` (#242) -> `config_django` fallback collector added for fields only available via Django settings (#354) -> controller version simplified to `main_instance` only (#257)
- **PRs**: 3-4 (#242, #245, #257, #354)
