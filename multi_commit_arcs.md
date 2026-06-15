# Notable Multi-Commit Arcs

Sequences where an approach was tried, revised, and sometimes revised again across multiple PRs — showing the evolution of a decision.

## Cross-repo arcs

### SonarCloud CI (parallel evolution)
- **Files**: ci_cd.md
- **Evolution**: both repos independently hit the same pitfalls with `pull_request_target` and PwnRequest vulnerabilities, arriving at similar `workflow_run`-based solutions. m-u went through 6 PRs (#89 -> #321), m-s through ~8 PRs (ee93077 -> #193).

### Collector architecture (interlocking halves)
- **Files**: architecture.md, metrics_collection.md
- **Evolution**: m-u extracted collectors from monolithic CLI code into `library/` with env-var-free interfaces (#248, #339). m-s independently evolved from individual collector files (#79) through legacy removal (#92) to a registry-based `collect_hourly`/`collect_snapshot` design (#109) that consumes the library collectors.

### Segment delivery pipeline (send side + receive side)
- **Files**: architecture.md, metrics_collection.md, bugs_and_pitfalls.md
- **Evolution**: m-u owns the send side — chunking at 32KB (#249) -> metadata fix (#281) -> trial-serialization sizing (#372) -> `sync_mode=True` (#383). m-s owns the scheduling side — fixed cron -> jittered task (#183) -> `use_bulk` removed (#195) -> truly random jitter (#201). Both repos independently removed `use_bulk` after discovering it didn't work.

## metrics-service arcs

### Serializer base classes
- **Files**: api_design.md, architecture.md
- **Evolution**: ModelSerializer (initial) -> HyperlinkedModelSerializer (ad01618) -> custom BaseModelSerializer with auto read-only fields and CountFieldMixin (#9) -> replaced by DAB's NamedCommonModelSerializer/CommonUserSerializer (#73)
- **PRs**: ~4

### Container architecture flip-flop
- **Files**: docker_and_deployment.md
- **Evolution**: separate web + dispatcher containers (initial) -> merged into single container (#45) -> split back into 4 containers (init+web+dispatcher+scheduler) (#117) -> production architecture with Nginx+Gunicorn (#129)
- **PRs**: ~4

### Scheduler evolution
- **Files**: task_system.md
- **Evolution**: polling-based TaskScheduler (141801c) -> APScheduler attempted, rolled back to polling (#25) -> CronTaskScheduler renamed to UnifiedTaskScheduler, simple_scheduler removed (#56) -> moved to separate process (#57) -> management command rewritten from threads to processes (#85)
- **PRs**: ~5

### Docker dependency management
- **Files**: docker_and_deployment.md, dependencies_and_packaging.md
- **Evolution**: pip + requirements.txt (initial) -> uv inside container (#18) -> uv removed, back to plain pip (#45), Konflux uses requirements-build.txt
- **PRs**: 3

### Pytest workflow trigger
- **Files**: ci_cd.md
- **Evolution**: initial with `pull_request_target` (ee93077) -> moved to future-workflow dir to disable (#7) -> restored with `pull_request_target` (#11) -> switched to `pull_request` (#27)
- **PRs**: ~4

### SonarCloud integration saga
- **Files**: ci_cd.md
- **Evolution**: added initially (ee93077) -> removed from pytest (#17) -> re-added via `workflow_run` pattern (#93) -> hardened with PR validation (#101) -> reorganized scan split (#127/#128/#134) -> exclusions expanded (#193)
- **PRs**: ~7-8

### URL prefix
- **Files**: settings_and_configuration.md
- **Evolution**: env var -> renamed env var -> Django setting -> proper prefix interpretation (4 iterations)

### Validation saga
- **Files**: settings_and_configuration.md
- **Evolution**: added -> broke -> turned off -> re-enabled with proper messages (5 PRs over 3 months)

### Migration history rewrites
- **Files**: database_and_migrations.md
- **Evolution**: tasks migrations rewritten during core-to-tasks extraction (#14) -> rewritten again during retrofit prep (#73) -> squashed for the third time (#140)
- **PRs**: 3

### Dispatcherd DB config
- **Files**: docker_and_deployment.md, bugs_and_pitfalls.md, settings_and_configuration.md
- **Evolution**: hardcoded YAML credentials -> `use_django_db=true` (broke, reverted next day #45/#48) -> back to hardcoded YAML -> runtime injection from Django settings via `_load_config_with_django_db` (#66)
- **PRs**: ~3

### Worker count
- **Files**: task_system.md, docker_and_deployment.md
- **Evolution**: 4 -> 1 (band-aid) -> 4 (real fix with atomic updates and advisory locks)

### Feature flag evolution
- **Files**: task_system.md, settings_and_configuration.md
- **Evolution**: single flag -> overly broad scope -> three independent flags -> FEATURE_ENABLED renamed to FEATURE, DB seeding removed in favor of env-var-driven defaults (#250)

### Settings API lifecycle
- **Files**: api_design.md, settings_and_configuration.md
- **Evolution**: ConfigView with DYNACONF.merge (#26) -> RESTful SettingView with DB persistence (#31) -> SettingSerializer broken after retrofit (#74, fixed) -> entire endpoint removed for security (#185)
- **PRs**: ~4

### Django signals for task routing
- **Files**: task_system.md, bugs_and_pitfalls.md, testing.md
- **Evolution**: post_save signal added for auto-routing (#25) -> caused widespread test failures, `_skip_signals` workaround (#54) -> signals removed entirely because cross-process (#57), replaced by APScheduler polling
- **PRs**: ~3

### Dockerfile labels
- **Files**: docker_and_deployment.md, bugs_and_pitfalls.md
- **Evolution**: copied from metrics-utility with wrong product name -> corrected to metrics-service (#94) -> updated to Konflux tech-preview format but CPE reverted to metrics_utility (#99)
- **PRs**: ~3

### Konflux hermetic builds
- **Files**: docker_and_deployment.md, dependencies_and_packaging.md
- **Evolution**: blanket `--no-binary :all:` in Dockerfile (#95) -> removed to unblock (#98) -> re-added in requirements-build.txt (#100/#102) -> targeted `--no-binary` for only crypto/psycopg with Dockerfile.dev split (#104)
- **PRs**: 7 in 4 days (#98-#104)

### Collector architecture
- **Files**: metrics_collection.md, task_system.md
- **Evolution**: individual collector files per type (#79) -> legacy system removed, tasks reorganized into subdirectory (#92) -> consolidated into two generic functions (collect_hourly/collect_snapshot) with registry-based design (#109) -> daily collector type added for service DB queries (#165) -> post_collect_hook added to registry for dashboard sync (#210)
- **PRs**: 4+

### Dashboard collection scheduling
- **Files**: metrics_collection.md, task_system.md
- **Evolution**: standalone 6-hourly `daily_dashboard_collection` cron task (initial) -> merged into hourly collector pipeline via `post_collect_hook` on unified_jobs (#210), with initial backfill via cursor-paginated batches
- **PRs**: 2+

### Secrets management
- **Files**: settings_and_configuration.md
- **Evolution**: SEGMENT_WRITE_KEY from config -> from file with base64 -> from file without base64

### CodeQL
- **Files**: ci_cd.md
- **Evolution**: created then immediately reverted (wrong file contents, 5 minutes apart)

### Task API permission evolution
- **Files**: api_design.md, settings_and_configuration.md
- **Evolution**: AllowAny (initial, marked "temporary") -> DeveloperModeRequired checking DEVELOPER_MODE_ENABLED (#65) -> DeveloperModeRequired checking settings.MODE (#87) -> IsSystemAdminOrAuditor from DAB RBAC (#253)
- **PRs**: 4 (#65, #87, #253 plus initial)

### Dashboard app lifecycle
- **Files**: architecture.md, settings_and_configuration.md
- **Evolution**: monolithic inline HTML template in apps/dashboard/ (#14) -> enhanced to ~1400 lines (#25) -> URL moved from /dashboard/ to /api/dashboard/ (#184) -> embedded app deleted, production UI externalized (#253) -> standalone tools/tasks/dashboard.html added for dev use with Basic auth and inline CORS middleware (#254)
- **PRs**: 5 (#14, #25, #184, #253, #254)

### DRF Spectacular / OpenAPI
- **Files**: api_design.md, dependencies_and_packaging.md
- **Evolution**: added initially -> removed during DAB retrofit (#73, API docs to be handled by `ansible_base.api_documentation`) -> re-added with comprehensive OpenAPI documentation and auto-sync workflow (#196)
- **PRs**: 3

### Segment send scheduling and jitter
- **Files**: metrics_collection.md
- **Evolution**: fixed cron at 3:30 AM -> jittered one-time task with deterministic seed (#183) -> `use_bulk` removed (didn't work) (#195) -> jitter changed from deterministic to truly random (timing fingerprint concern) (#201)
- **PRs**: ~3-4

### Task timeout consolidation
- **Files**: task_system.md
- **Evolution**: per-task `timeout_seconds` DB field + hardcoded `STUCK_TASK_TIMEOUT_SECONDS` constant + CLI `--timeout` flag -> stuck detection added (#211) -> exponential backoff (#220) -> all consolidated into single TASK_TIMEOUT Dynaconf setting (#218/#228)
- **PRs**: ~4

## metrics-utility arcs

### psycopg2/psycopg3 compatibility
- **Files**: dependencies_and_packaging.md, architecture.md
- **Evolution**: duck-typing `hasattr(cursor, 'copy_expert')` for COPY operations (#7) -> `UndefinedTable` exception mismatch between psycopg versions (#261) -> library `copy_table` switched to `cursor.fetchall()` + DataFrame return, dropping psycopg2 support entirely (#327)
- **PRs**: 3 (#7, #261, #327)

### Missing `__init__.py` (recurring bug)
- **Files**: bugs_and_pitfalls.md
- **Evolution**: forgot in #9 -> fixed in #10 -> forgot again in #24 -> fixed in #25 -> forgot again in #215/#239/#250 -> fixed in #278
- **PRs**: ~6

### insights-analytics-collector vendoring and cleanup
- **Files**: architecture.md, dependencies_and_packaging.md
- **Evolution**: external dependency (#5) -> vendored into `metrics_utility/base/` (#92) -> unused extension points removed (#111) -> dead code removed from base Collector (#265)
- **PRs**: 4 (#5, #92, #111, #265)

### Dataframe engines: monolith to library
- **Files**: architecture.md
- **Evolution**: monolithic `DataframeSummarizedByOrgAndHost` -> Base class extracted, CCSPv2 engine added (#17) -> deduplication extracted as separate pipeline step (#162) -> dataframes moved to library with loading/transform split (#237)
- **PRs**: 3 (#17, #162, #237)

### Python version bounds
- **Files**: dependencies_and_packaging.md
- **Evolution**: `>=3.12` -> `>=3.11` (match AWX, #45) -> `>=3.11, <3.13` (upper bound, #49) -> `>=3.11` (removed upper bound for 3.13, #96) -> `>=3.12` (for PyPI library, #271)
- **PRs**: 4 (#45, #49, #96, #271)

### SonarCloud CI integration
- **Files**: ci_cd.md
- **Evolution**: added with `pull_request_target` (#89/#93) -> PR head checkout fix (#106) -> dual push/PR conditional scan (#108/#109) -> per-PR dropped, reverted to `pull_request` (#318) -> PwnRequest remediation via `workflow_run` split (#321)
- **PRs**: 6 (#89, #93, #106, #108, #318, #321)

### Indirect nodes collector naming and error handling
- **Files**: settings_and_configuration.md, metrics_collection.md
- **Evolution**: `indirect_nodes` with `INCLUDE_INDIRECT` module constant (#75) -> renamed to `main_indirectmanagednodeaudit`, switched to `get_optional_collectors()` (#78) -> `ProgrammingError` catch for AAP 2.4 (#172) -> `UndefinedTable` also caught for psycopg3 (#261)
- **PRs**: 4 (#75, #78, #172, #261)

### `get_optional_collectors()` location
- **Files**: settings_and_configuration.md
- **Evolution**: local to `collectors.py` (original) -> moved to `metric_utils.py` (#75) -> moved back to `collectors.py` (#153) -> moved to `base/utils.py` (#185)
- **PRs**: 3 (#75, #153, #185)

### Tarball naming and filtering
- **Files**: architecture.md
- **Evolution**: anonymous tarball names -> collection name added to filename (#226) -> extractors filter tarballs and files by collection name (#227) -> build report only extracts needed CSVs (#86/#91)
- **PRs**: 3-4 (#86, #91, #226, #227)

### Advisory lock saga
- **Files**: architecture.md, dependencies_and_packaging.md, bugs_and_pitfalls.md
- **Evolution**: AWX import -> `find_spec` detection for AWX vs ansible_base (#51) -> `find_spec` broke, switched to try/except (#94) -> custom `library/lock.py` with raw PostgreSQL hashtext (#259) -> django-ansible-base dep removed (#395)
- **PRs**: 4 (#51, #94, #259, #395)

### Date parser unification
- **Files**: architecture.md, bugs_and_pitfalls.md
- **Evolution**: bare numbers accepted silently (#114 fix) -> separate parsers for gather vs build (#128) -> `_handle_datelike` extracted (#156) -> three parsers merged into one `parse_date_param` (#157)
- **PRs**: 4 (#114, #128, #156, #157)

### `self.help` shadowing Django's BaseCommand.help
- **Files**: bugs_and_pitfalls.md
- **Evolution**: refactored help text into `self.help = {...}` dict (#128) -> shadowed Django's help string, caused dict repr in `--help` -> fixed by renaming to `self.help_texts` (#141) -> moved from constructor to class-level attributes (#156)
- **PRs**: 3 (#128, #141, #156)

### Env validation ordering
- **Files**: bugs_and_pitfalls.md, settings_and_configuration.md
- **Evolution**: validation placed in `add_arguments()` (#137) -> broke `--help`, moved to `handle()` (#141) -> placed before `init_logging`, errors invisible (#141) -> moved after `init_logging` (#146)
- **PRs**: 3 (#137, #141, #146)

### Gather `--until` inclusive vs exclusive
- **Files**: bugs_and_pitfalls.md
- **Evolution**: exclusive upper bound (original) -> changed to inclusive end-of-day (#175) -> reverted back to exclusive because it broke `since == until` and conflicted with daily_slicing (#192)
- **PRs**: 2 (#175, #192)

### `METRICS_UTILITY_OPTIONAL_COLLECTORS` empty string handling
- **Files**: settings_and_configuration.md, bugs_and_pitfalls.md
- **Evolution**: whitespace caused validation failure (#178) -> added `''` to VALID_COLLECTORS as workaround (#178) -> replaced with `filter(bool, ...)` for clean parsing (#263)
- **PRs**: 2 (#178, #263)

### MAX_GATHER_PERIOD: constant to configurable
- **Files**: metrics_collection.md, settings_and_configuration.md
- **Evolution**: hardcoded `timedelta(weeks=4)` in 3 places -> centralized as `MAX_GATHER_PERIOD_WEEKS = 4` class constant (#168) -> replaced with `METRICS_UTILITY_MAX_GATHER_PERIOD_DAYS` env var defaulting to 28 (#181)
- **PRs**: 2 (#168, #181)

### Anonymization strategy evolution
- **Files**: architecture.md, metrics_collection.md, metrics_utility.md
- **Evolution**: SHA-512 hashing of unknown values (#239) -> SHA-256 for shorter hashes (#250) -> "Unknown" replaced with literal string instead of hash (#319) -> "Unknown" renamed to "Custom" (#343) -> salt parameter and hash function removed entirely (#399)
- **PRs**: 5 (#239, #250, #319, #343, #399)

### Anonymized rollup data structure evolution
- **Files**: architecture.md, metrics_utility.md
- **Evolution**: nested JSON structure (#239) -> flattened with `flatten_json_report()` (#250) -> flat DataFrame changed to dict with totals (#288) -> JSON round-trip verification after each batch (#331) -> field names changed from DB columns to descriptive names (#343)
- **PRs**: 5 (#239, #250, #288, #331, #343)

### `anonymize_rollups()` signature evolution
- **Files**: metrics_utility.md
- **Evolution**: basic positional params (#239) -> `feature_flags_rollup` added as positional (#357) -> changed to keyword-only (#362) -> `salt` removed (#399) -> `task_executions_rollup` added as keyword-only (#399)
- **PRs**: 4 (#357, #362, #399, plus original #239)

### Library/CLI collector split
- **Files**: architecture.md, metrics_utility.md
- **Evolution**: all collectors in CLI `collectors.py` (original) -> library collectors with env-var-free interfaces (#248) -> CLI collectors replaced with thin wrappers delegating to library (#339) -> `copy_table` returns DataFrame instead of files (#327)
- **PRs**: 3 (#248, #327, #339)

### StorageSegment chunking and delivery reliability
- **Files**: architecture.md, bugs_and_pitfalls.md
- **Evolution**: basic chunking at 32KB limit (#249) -> metadata overhead and dict-vs-list handling fixed, limit reduced to 24KB (#281) -> `use_bulk` removed, trial-serialization sizing (#372) -> `sync_mode=True` as only reliable delivery method after silent event loss (#383)
- **PRs**: 4 (#249, #281, #372, #383)

### AWX imports removal from collectors
- **Files**: architecture.md, metrics_collection.md
- **Evolution**: collectors imported AWX Python modules directly (original) -> replaced with direct SQL against `conf_setting` (#242) -> `config_django` fallback collector added for fields only available via Django settings (#354) -> controller version simplified to `main_instance` only (#257)
- **PRs**: 3-4 (#242, #245, #257, #354)

### Pandas version evolution and NaN compatibility
- **Files**: dependencies_and_packaging.md, bugs_and_pitfalls.md
- **Evolution**: `pandas==2.2.1` exact pin to match AWX (#45) -> relaxed to `>=2.2.3` for Python 3.13 wheels (#96) -> upgraded to `~=3.0` with four breaking-change fixes for NaN-as-float-in-string-columns, plus openpyxl bumped to `~=3.1.5` (#431)
- **PRs**: 3 (#45, #96, #431)

### Cross-repo CI testing
- **Files**: ci_cd.md
- **Evolution**: metrics-utility and metrics-service tested independently in their own CI (original) -> metrics-utility CI now also clones metrics-service@devel and runs its tests with the local metrics-utility checkout installed as editable (#427)
- **PRs**: 1 (#427), likely to be extended

### Docker Compose port flip-flop
- **Files**: bugs_and_pitfalls.md
- **Evolution**: 5432 (original) -> changed to 5433 to avoid local conflicts (#274) -> reverted 15 minutes later because it broke CI (#276)
- **PRs**: 2 (#274, #276)
