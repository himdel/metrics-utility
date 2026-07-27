# Dependencies and Packaging
### Entry point defined as console_scripts in setup.cfg
- **Repo**: ansible/metrics-utility
- **Commits**: 8ab89cc, 22b3072
- **What happened**: The `metrics-utility` CLI entry point is defined in `setup.cfg` under `[options.entry_points]` as `console_scripts = metrics-utility = metrics_utility:manage`. Package discovery uses `find:` with `include = *`.
- **Insight**: The entry point calls `metrics_utility.manage()` which handles AWX environment setup before delegating to Django's management command infrastructure.

### setuptools_scm version constraint lowered for downstream compatibility
- **Repo**: ansible/metrics-utility
- **Commits**: 11ebf8a (#2)
- **What happened**: The `pyproject.toml` build requirement was changed from `setuptools_scm[toml]>=6.2` to `>=6.0` because downstream (AAP 2.3) had setuptools 6.0.1 available. The constraint was lowered to avoid a build failure in that environment.
- **Insight**: Build-system constraints must account for the oldest supported downstream environment, not just the development environment.

### psycopg2 vs psycopg3 compatibility layer for COPY operations
- **Repo**: ansible/metrics-utility
- **Commits**: 5274bbd (#7)
- **What happened**: Controller 4.4 and below used psycopg2 (with `cursor.copy_expert()` method), while Controller 4.5+ uses psycopg3 (with `cursor.copy()` context manager). The `_copy_table` function was split into two implementations selected at runtime by checking `hasattr(cursor, 'copy_expert')`. psycopg2 writes directly to the file object, while psycopg3 reads chunks and decodes bytes.
- **Insight**: When a dependency undergoes a major version change across supported product versions, use duck-typing (`hasattr`) to select the right code path rather than version-checking.

### boto3 added as dependency for S3 support, then relaxed to unpinned
- **Repo**: ansible/metrics-utility
- **Commits**: 1e86f8c, 3b6b630
- **What happened**: S3 support (commit 1e86f8c) added `boto3~=1.34.47` to `setup.cfg` install_requires, also switching existing dependencies from exact pins (`==`) to compatible release constraints (`~=`). Shortly after (commit 3b6b630), the boto3 constraint was relaxed to just `boto3` (no version pin at all) because the pinned version caused build failures in downstream environments that had different boto3 versions available. The other deps (`insights-analytics-collector~=0.3.2`, `pandas~=2.2.1`, `openpyxl~=3.1.2`) kept their `~=` pins.
- **Insight**: boto3 is special among dependencies -- it releases very frequently and downstream environments (like AAP builds) bundle whatever version ships with their Python ecosystem, so pinning it even loosely causes unnecessary build conflicts.

### pre-commit with ruff replaces black for code formatting
- **Repo**: ansible/metrics-utility
- **Commits**: c8c5556 (#42)
- **What happened**: A `.pre-commit-config.yaml` was added with `ruff` (v0.9.2) as the sole pre-commit hook, replacing the previous `[tool.black]` configuration in `pyproject.toml`. The `pyproject.toml` was also restructured to add a `[project]` section with development dependencies (`ruff`, `pytest`, `Django`, `pre-commit`) and `requires-python = ">=3.12"`. A `uv.lock` file was added for reproducible development installs.
- **Insight**: The project moved from black (formatting only) to ruff (linting + formatting) and from pip to uv for development dependency management, reflecting the broader Python ecosystem shift toward ruff as a unified tool.

### pyproject.toml dependencies pinned to match AWX requirements, Python lowered to 3.11
- **Repo**: ansible/metrics-utility
- **Commits**: d70534f (#45)
- **What happened**: The `pyproject.toml` dependencies were changed from generic ranges (`Django>=4.0,<5.0`) to exact pins matching `awx/requirements/requirements.txt` (e.g. `django==4.2.16`, `pandas==2.2.1`, `openpyxl==3.1.2`). All imported non-stdlib dependencies were explicitly listed: `boto3`, `botocore`, `distro`, `insights-analytics-collector`, `openpyxl`, `pandas`, `requests`, `setuptools`. The `requires-python` was lowered from `>=3.12` to `>=3.11` to match AWX's supported Python version. Dev-only tools (`ruff`, `pytest`, `pre-commit`) kept unpinned `>=` constraints.
- **Insight**: Pinning development dependencies to the same versions as AWX's requirements.txt ensures metrics-utility is tested against the exact library versions it will encounter in production, preventing compatibility surprises at deployment time.

### Python version upper-bounded to <3.13 for compatibility, then removed
- **Repo**: ansible/metrics-utility
- **Commits**: 243428e (#49), f887f09 (#96)
- **What happened**: The `requires-python` in `pyproject.toml` was initially changed from `>=3.11` to `>=3.11, <3.13`, adding an upper bound to prevent uv from resolving against untested Python versions. In #96, the upper bound was removed (back to `>=3.11`) to allow Python 3.13, and `pandas` was relaxed from `==2.2.1` to `>=2.2.3` because pandas 2.2.1 didn't have Python 3.13 wheels. **#96 reverses the upper-bound decision from #49.**
- **Insight**: Python version upper bounds create maintenance burden -- they must be updated every time a new Python version is validated, and pinned dependencies (like pandas) may need relaxing simultaneously to get compatible wheels.

### django-ansible-base added as dependency for AAP 2.5 advisory_lock, then removed
- **Repo**: ansible/metrics-utility
- **Commits**: 33d428e (#51), 2f14098 (#259)
- **What happened**: `django-ansible-base>=2025.1.3` was added to `pyproject.toml` dependencies because the `advisory_lock` utility moved from `awx.main.utils.pglock` to `ansible_base.lib.utils.db` in AAP 2.5. This pulled in transitive dependencies including `cryptography`, `djangorestframework`, `django-crum`, and `django-split-settings`. PR #259 replaced both the AWX and ansible_base advisory_lock imports with a custom `lock()` function in `metrics_utility/library/lock.py` that uses PostgreSQL's `hashtext()` directly, eliminating the need for both AWX and django-ansible-base Python packages for locking.
- **Insight**: The custom lock implementation using raw PostgreSQL `hashtext()` and `pg_advisory_lock()` is simpler and has zero Python package dependencies -- the AWX/ansible_base advisory_lock was just a wrapper around the same PostgreSQL primitives. **Superseded** by #259.

### insights-analytics-collector vendored, removing external dependency
- **Repo**: ansible/metrics-utility
- **Commits**: 6337a3f (#92)
- **What happened**: The `insights-analytics-collector` package was removed from both `pyproject.toml` and `setup.cfg` dependencies. The code was copied into `metrics_utility/base/` and imports updated. New dev dependencies `pytest-mock>=3.14.0` and `pytz>=2024.2` were added to replace transitive dependencies that had come through the external package.
- **Insight**: Vendoring a low-activity external dependency reduces supply chain risk and enables direct refactoring -- but requires absorbing its transitive dev dependencies explicitly.

### pytz dev dependency removed in favor of stdlib datetime.timezone
- **Repo**: ansible/metrics-utility
- **Commits**: be5d9eb (#152)
- **What happened**: After vendoring insights-analytics-collector (#92), `pytz>=2024.2` had been added as a dev dependency. The codebase only used `pytz.utc` (passing it to `datetime.datetime` constructors). All occurrences were replaced with `datetime.timezone.utc`, and `pytz` was removed from `pyproject.toml`. This was triggered by code scanning tools flagging pytz usage as unnecessary on Python >= 3.9.
- **Insight**: Since Python 3.9, `datetime.timezone.utc` is the standard replacement for `pytz.utc` -- using pytz solely for `.utc` is unnecessary and triggers linter warnings. **Supersedes** the pytz dev dependency added in #92.

### Migration from pip + requirements.txt to UV
- **Repo**: ansible/metrics-service
- **Commits**: 6ef9f58, e64f482, 47d8fef, ee93077
- **What happened**: Over four commits in a single day (Aug 27), the dependency management evolved: requirements.txt was cleaned up (6ef9f58), test dependencies added (e64f482), `psycopg[binary]` changed to just `psycopg` (47d8fef), and finally UV was adopted with `uv.lock` generated and `[tool.uv]` section added to `pyproject.toml` (ee93077). The UV config added dev-dependencies separately from the pyproject `[project.optional-dependencies]`.
- **Insight**: The `psycopg[binary]` to `psycopg` change (47d8fef) was likely needed because the binary extra pulls in pre-compiled binaries that may not be compatible with all platforms (especially the UBI9 container). Plain `psycopg` requires `libpq-dev` at build time but is more portable.

### dispatcherd moved from optional to core dependency
- **Repo**: ansible/metrics-service
- **Commits**: ee93077
- **What happened**: `dispatcherd>=2025.5.21` was moved from `[project.optional-dependencies].dispatcherd` to the main `dependencies` list in `pyproject.toml`. The separate `[dispatcherd]` optional-dependencies group was removed.
- **Insight**: This reflects the decision that dispatcherd (the background task worker) is a core requirement, not optional. The service fundamentally needs background task processing to function.

### social-auth-app-django and django-oauth-toolkit added as core deps
- **Repo**: ansible/metrics-service
- **Commits**: ee93077
- **What happened**: `social-auth-app-django>=5.0.0,<5.5` and `django-oauth-toolkit>=2.2.0` were added to the main dependencies list.
- **Insight**: These are required by DAB's authentication and OAuth2 provider modules. Pinning social-auth to `<5.5` suggests a known incompatibility with newer versions, likely with DAB.

### Dev dependencies duplicated between pyproject.toml sections
- **Repo**: ansible/metrics-service
- **Commits**: ee93077
- **What happened**: The `[tool.uv].dev-dependencies` list largely duplicates the `[project.optional-dependencies].dev` and `[project.optional-dependencies].test` sections. For example, `pytest>=7.4` appears in both `[project.optional-dependencies].test` and `[tool.uv].dev-dependencies`.
- **Insight**: UV uses its own `dev-dependencies` key rather than reading from `[project.optional-dependencies]`. This duplication can lead to version drift if one is updated but not the other. Ideally, one source of truth should be used.

### croniter and psycopg2-binary added as dependencies
- **Repo**: ansible/metrics-service
- **Commits**: c6947ce (#14), edb4626 (#25)
- **What happened**: `croniter` 6.0.0 was added in c6947ce for cron expression parsing in the task scheduler. `psycopg2-binary` was added in edb4626 alongside the existing `psycopg` for PostgreSQL LISTEN/NOTIFY support used by dispatcherd.
- **Insight**: Having both `psycopg` and `psycopg2-binary` is intentional -- they are different drivers. `psycopg` (v3) is used by Django for ORM operations, while `psycopg2-binary` may be needed by dispatcherd or other components that haven't migrated to psycopg v3.

### Redis removed as a dependency
- **Repo**: ansible/metrics-service
- **Commits**: d85322e (#18)
- **What happened**: Redis-related packages were removed from `pyproject.toml` and the `uv.lock` was updated to drop them. The cache backend was switched to Django's local memory cache for development.
- **Insight**: Redis was carried over from the template service but never used. Removing unused dependencies reduces the attack surface and simplifies the development setup.

### Version switched from hardcoded string to dynamic `importlib.metadata.version`
- **Repo**: ansible/metrics-utility
- **Commits**: 55b0248 (#188)
- **What happened**: The metrics-utility version was previously hardcoded as `'0.6.1dev'` in two places: the `config` collector (embedded in config.json tarballs) and the `ManagementUtility` (for `--version` output). Both were replaced with `importlib.metadata.version('metrics-utility')`, which reads the version from the installed package metadata (ultimately from `setup.cfg`). The `pyproject.toml` was also updated to use `dynamic = ["version"]` instead of `version = "0.1.0"`, deferring to `setup.cfg` for the actual version. Additional project metadata (authors, license, classifiers, URLs, console_scripts entry point) was added to `pyproject.toml`.
- **Insight**: Using `importlib.metadata.version()` eliminates the need to manually update version strings in code -- the single source of truth is `setup.cfg`, and the runtime reads it automatically via installed package metadata.

### sync-requirements system bridges uv and Konflux requirements
- **Repo**: ansible/metrics-service
- **Commits**: f848024 (#24)
- **What happened**: A `sync-requirements.sh` script was added that uses `uv export --format requirements.txt` to generate `requirements-pinned.txt` (production, with hashes), `dev-requirements.txt` (dev-only, with hashes), and `requirements-build.txt` (compiled from pinned) from `uv.lock`. A pre-commit hook auto-runs this script when `pyproject.toml` or `uv.lock` changes.
- **Insight**: This system solves the dual-dependency-management problem: developers use `uv` and `uv.lock`, but Konflux hermetic builds need pip-format requirements with hashes. The `uv export` command provides the bridge, and the pre-commit hook + CI workflow ensure the files stay in sync.

### metrics-utility pinned to a specific git commit rather than a branch
- **Repo**: ansible/metrics-service
- **Commits**: edb4626 (#25)
- **What happened**: The `metrics-utility` dependency was initially pointed at a local directory, then changed to a GitHub repository pointing at the `devel` branch, and finally pinned to a specific commit hash in `pyproject.toml`, `requirements-build.txt`, and `requirements-pinned.txt`. The commit message says "Changed pyproject.toml, requirements-build.txt, and requirements-pinned.txt to point to a specific commit of metrics-utility instead of the devel branch."
- **Insight**: Pinning to a specific commit rather than a branch is essential for reproducible builds. A branch reference (`@devel`) means different builds at different times get different code, which can cause mysterious CI failures. The trade-off is that you need to manually bump the commit hash when you want new changes from metrics-utility.

### Python pinned to ==3.12 from >=3.11
- **Repo**: ansible/metrics-service
- **Commits**: c8e5f0d (#36), 10581e9 (#42)
- **What happened**: The `requires-python` was tightened from `>=3.11` to `==3.12` in c8e5f0d (noted as "Forcing python 12 as Python 14 doesn't support Django and was breaking Pytests"), then to `==3.12.*` in 10581e9.
- **Insight**: Python 3.14 likely refers to the development version, which caused test failures. The strict pin ensures CI and production use the same Python version. The `==3.12.*` form allows patch releases (3.12.x) while preventing minor version bumps.

### Segment dependency made optional with try/except ImportError
- **Repo**: ansible/metrics-utility
- **Commits**: cf644cb (#270)
- **What happened**: The `segment-analytics-python` package is listed in `pyproject.toml` as a dependency but is not installed in the Controller image (only the metrics service needs it). The `import segment.analytics` at module level was wrapped in `try/except ImportError` with a `SEGMENT_AVAILABLE` boolean flag. This prevents `ImportError` at import time when the library storage module is loaded in environments without the segment package.
- **Insight**: Dependencies that are only used by one deployment context (metrics service) but whose code is importable in another context (Controller) must use lazy/conditional imports -- otherwise the library cannot be imported at all in the context that doesn't need that dependency.

### Library published to PyPI with date-based versioning and package scoping
- **Repo**: ansible/metrics-utility
- **Commits**: 56b5e35 (#271)
- **What happened**: A `pypi-release.yml` workflow was added for weekly PyPI releases using PyPI trusted publisher (no API tokens). The versioning scheme transforms the `setup.cfg` base version (e.g., `0.7.0dev`) to `0.7.YYYYMMDD` for each release. Package scoping was tightened in both `pyproject.toml` (`[tool.setuptools] packages`) and `setup.cfg` (`[options.packages.find]`) to include only `metrics_utility*` and exclude `tools*`, `workers*`, `mock_awx*`, `docs*`, etc. Package data patterns (`*.json`, `*.sql`, `*.txt`) were explicitly listed. The `requires-python` was raised from `>=3.11` to `>=3.12`.
- **Insight**: When a repo contains both a CLI tool and a library published as a package, explicit package inclusion/exclusion lists are critical -- without them, development-only directories (tools, mock_awx) would ship in the published package, bloating it and potentially leaking test data.

### Django upgraded from 4.2 to 5.2.7 with strict pin
- **Repo**: ansible/metrics-service
- **Commits**: 10581e9 (#42)
- **What happened**: Django was upgraded from `>=4.2,<5.0` to `==5.2.7` (exact pin). The `django-ansible-base` was pinned to `==2025.10.20`, `drf-spectacular` to `>=0.26.5`, and `metrics-utility` to `==0.7.20251112` (replacing the git reference). Python requirement changed from `>=3.11` to `==3.12.*`. The Docker base image changed from `ubi9/python-311` to `ubi9/python-312`. Ruff target version changed from `py310` to `py312`. The pytest deprecation warning filter was updated from `RemovedInDjango50Warning` to `RemovedInDjango60Warning`.
- **Insight**: The jump from Django 4.2 LTS to 5.2 is a major version upgrade skipping the entire 5.0/5.1 cycle. Exact pinning (`==5.2.7`) over range pinning (`>=5.2,<6.0`) trades automatic patch updates for build reproducibility. The Python 3.12 strict pin (`==3.12.*`) prevents accidental use of 3.13+ which might have Django/DAB incompatibilities.

### metrics-utility collector imports changed for controller-specific modules
- **Repo**: ansible/metrics-service
- **Commits**: 10581e9 (#42)
- **What happened**: The metrics-utility import path changed from `metrics_utility.library.collectors` to `metrics_utility.library.collectors.controller`. The specific collector names also changed: `anonymous` became `job_host_summary` (aliased back as `anonymous`), `job_host_summary` became `main_host`, and `host_metric` became `main_jobevent`. A TODO comment was added noting these aliases are temporary.
- **Insight**: The metrics-utility library reorganized its public API between versions, moving from flat collector imports to controller-specific submodules. The `as` aliases maintain backward compatibility with the existing task function signatures, but this creates a confusing indirection layer where function names don't match their actual purpose.

### django-prometheus and segment-analytics-python added as new dependencies
- **Repo**: ansible/metrics-service
- **Commits**: 10581e9 (#42), e486eb4 (#41)
- **What happened**: `django-prometheus>=2.3.1` was added for Prometheus metrics exposition, and `backoff` + `segment-analytics-python` were added (presumably for analytics data transmission with retry logic). These were added to both `pyproject.toml` and the generated requirements files.
- **Insight**: The `segment-analytics-python` dependency signals the service will send anonymized metrics data to Segment (a customer data platform), which aligns with the `ANONYMIZATION_GROUP` tasks. The `backoff` library provides retry logic with exponential backoff for network calls.

### uv removed as a runtime dependency
- **Repo**: ansible/metrics-service
- **Commits**: 6059d8c (#45)
- **What happened**: `uv>=0.8.22` was removed from the main `dependencies` list in `pyproject.toml`. The `[tool.uv].dev-dependencies` section was moved to `[dependency-groups].dev` (PEP 735 format).
- **Insight**: UV as a runtime dependency was wrong -- it's a build/development tool, not something the application needs at runtime. Moving dev dependencies from `[tool.uv].dev-dependencies` to `[dependency-groups].dev` follows the emerging PEP 735 standard, which is tool-agnostic.

### metrics-utility version pin relaxed from exact to minimum
- **Repo**: ansible/metrics-service
- **Commits**: 4804647 (#67)
- **What happened**: `metrics-utility==0.7.20251112` was changed to `metrics-utility>=0.7.20251112` in `pyproject.toml`, and the lockfile was updated accordingly.
- **Insight**: The exact pin (`==`) was overly restrictive and required a pyproject.toml change for every metrics-utility patch. The minimum pin (`>=`) allows automatic resolution to newer versions while maintaining a known-good floor. This is appropriate for a sister project where API compatibility is maintained across patch versions.

### Major dependency removal during retrofit prep
- **Repo**: ansible/metrics-service
- **Commits**: 5fb6ead (#73)
- **What happened**: Several dependencies were removed from `pyproject.toml`: `channels`, `django-oauth-toolkit`, `django-split-settings`, `social-auth-app-django`, `drf-spectacular`. `django-extensions` was moved from dev dependencies to main dependencies. The `uv.lock` shrank by ~216 lines.
- **Insight**: The retrofit to platform-service-framework eliminated the need for many third-party packages. OAuth2 provider and social auth were removed because the service authenticates via JWT from the AAP gateway rather than being its own OAuth provider. DRF Spectacular was removed because OpenAPI docs will be provided by `ansible_base.api_documentation`. Keeping `django-split-settings` was dead weight since Dynaconf had replaced it months earlier.

### Package discovery switched to automatic in pyproject.toml
- **Repo**: ansible/metrics-service
- **Commits**: 5fb6ead (#73)
- **What happened**: `pyproject.toml` moved from explicit package listing to `[tool.setuptools.packages.find]` with `where = ["."]`. This was needed because apps were being reorganized (api app removed, dynamic_settings added, health app added) and explicit listing required manual updates on every app change.
- **Insight**: Automatic package discovery reduces maintenance burden when adding/removing apps, but means any directory with an `__init__.py` becomes a package. This is generally fine for a service repo where all directories are intentional.

### django-cors-headers removed (CORS handled at gateway)
- **Repo**: ansible/metrics-service
- **Commits**: 911dd60 (#77)
- **What happened**: `django-cors-headers` was removed from dependencies, `corsheaders` removed from `INSTALLED_APPS`, CORS middleware removed, and all `CORS_*` settings removed from defaults, development, and production configs.
- **Insight**: In the AAP architecture, CORS is handled at the gateway/proxy level, not by individual services. Having CORS middleware in the service was unnecessary overhead and potential misconfiguration risk (e.g., `CORS_ALLOW_ALL_ORIGINS: true` in development settings could leak to production).

### DAB extras expanded for platform-service-framework
- **Repo**: ansible/metrics-service
- **Commits**: 911dd60 (#77), 00e68ad (#84)
- **What happened**: The `django-ansible-base` dependency changed from `[jwt_consumer,rbac,rest_filters]` to `[rest_filters,jwt_consumer,resource_registry,rbac,feature_flags,api_documentation]`, adding `resource_registry`, `feature_flags`, and `api_documentation` extras.
- **Insight**: The expanded DAB extras reflect the full platform-service-framework integration. Each extra adds a DAB app that provides standardized functionality: `api_documentation` replaces DRF Spectacular, `resource_registry` enables cross-service resource syncing, and `feature_flags` provides the DAB-standard toggle mechanism (though the service still uses its own `apps/dynamic_settings/` for now).

### poethepoet task runner added
- **Repo**: ansible/metrics-service
- **Commits**: 00e68ad (#84)
- **What happened**: `poethepoet>=0.37.0` was added to dev dependencies, and `[tool.poe.tasks]` was configured in `pyproject.toml` with tasks for `lint`, `format`, `unit-test`, `check` (all three combined), `clean`, `validate` (runs framework validator), and `update` (runs framework template updater).
- **Insight**: The poe task runner provides convenient aliases (`uv run poe check`) for common development workflows. The `validate` and `update` tasks integrate with the platform-service-framework's copier template system, reading `.copier-answers.yml` to determine the template source and branch.

### psycopg switched from binary to source builds
- **Repo**: ansible/metrics-service
- **Commits**: e09243d (#95)
- **What happened**: `psycopg[binary]` changed to `psycopg[c]` and `psycopg2-binary` changed to `psycopg2` in `pyproject.toml`. The `[c]` extra for psycopg3 builds the C-accelerated adapter from source, while plain `psycopg2` builds from source against `libpq-devel`.
- **Insight**: Binary wheels contain pre-compiled C code that can't be traced by SBOM tools. Red Hat certification requires full source provenance. The `[c]` extra for psycopg3 is the recommended source-build path that still provides C-speed performance (unlike `[binary]` which ships pre-built binaries).

### django-ansible-base version pin relaxed with uv source override
- **Repo**: ansible/metrics-service
- **Commits**: e09243d (#95)
- **What happened**: DAB changed from `==2025.10.20` (exact pin) to `>=2025.12.12` (minimum), while `[tool.uv.sources]` was changed from `rev = "devel"` (branch) to a specific commit hash. A comment explains the dual approach: `uv sync` uses the git source, while `pip install` uses PyPI.
- **Insight**: The minimum pin in `pyproject.toml` allows production builds (via pip) to use the latest compatible PyPI release, while development (via uv) uses a specific commit from the git repo. This avoids the issue where a floating `devel` branch reference in uv causes different developers to get different versions.

### Targeted --no-binary replaces blanket source-only builds
- **Repo**: ansible/metrics-service
- **Commits**: 095d0f0 (#98), 400b419 (#100), 4672f09 (#102), 72c8a74 (#104)
- **What happened**: After #95 introduced global `--no-binary :all:` for SBOM compliance, a rapid iteration cycle (4 PRs in 2 days) discovered this was too aggressive. #98 removed it from the Dockerfile. #100/#102 moved it into `requirements-build.txt` as a pip directive (so Cachi2 would see it). #104 replaced the blanket `--no-binary :all:` with targeted directives: `--no-binary cryptography`, `--no-binary psycopg`, `--no-binary psycopg2`, `--no-binary psycopg-c`. Other packages (Django, pandas, numpy) use binary wheels.
- **Insight**: Source-only builds for every package is impractical in hermetic builds -- many packages need build toolchains (Rust for cryptography, C for numpy) that aren't available or take too long. The targeted approach provides SBOM compliance for the security-critical packages (cryptography, database drivers) while keeping builds fast for everything else.

### Build-time extra dependencies for hermetic builds
- **Repo**: ansible/metrics-service
- **Commits**: 204de50 (#103), 72c8a74 (#104)
- **What happened**: `packaging>=20.0` was added as a runtime dependency to support setuptools-scm during source builds (#103). Then #104 introduced `requirements-build-extra.txt` containing build-time-only deps (pytest-runner, setuptools-scm, wheel) so Cachi2 prefetches them. The `sync-requirements.sh` was updated to compile build requirements from both `requirements-pinned.txt` and `requirements-build-extra.txt`.
- **Insight**: Hermetic builds can't fetch packages at build time, so all build-time dependencies (not just runtime deps) must be prefetched. Packages like django-crum use pytest-runner in their setup.py, which fails in an offline build without it. The separate `requirements-build-extra.txt` keeps build deps distinct from runtime deps.

### pyproject.toml version pinned to 1.0.0 (no longer dynamic)
- **Repo**: ansible/metrics-service
- **Commits**: 72c8a74 (#104)
- **What happened**: `version` changed from `dynamic = ["version"]` (using setuptools-scm) to `version = "1.0.0"` in pyproject.toml. This was needed because hermetic builds don't have git history, so setuptools-scm can't determine the version.
- **Insight**: Dynamic versioning via setuptools-scm requires `.git` directory access, which hermetic/container builds deliberately don't have. Pinning to a static version is simpler and more reliable for container images where the image tag is the real version identifier.

### metrics-utility version bumped frequently during active development
- **Repo**: ansible/metrics-service
- **Commits**: 1580ff2 (#109), 05dc0c9 (#112), 31edf97 (#114), c946e15 (#122)
- **What happened**: metrics-utility was bumped through multiple versions in rapid succession (0.7.20260218, 0.7.20260223, 0.7.20260224, 0.7.20260301), each time to pick up new collector/rollup classes being added to the library in parallel.
- **Insight**: The frequent bumps show tight coupling between this service and the library during active feature development. The `>=` minimum pin works well -- uv.lock ensures development consistency while production builds use newer patch releases. Library bumps are often prerequisites for service-side feature work.

### Dev dependencies deduplicated from optional-dependencies to dependency-groups
- **Repo**: ansible/metrics-service
- **Commits**: 31edf97 (#114)
- **What happened**: The `[project.optional-dependencies].dev` section was removed from `pyproject.toml` entirely. Its contents were merged into `[dependency-groups].dev` (PEP-735). The rationale: uv ignores optional-dependencies by default but installs dependency-groups, and nothing pip-installs `metrics-service[dev]`. Having two independent sets of dev deps was pointless duplication. `psutil` was added to dev deps (for performance tests in #97).
- **Insight**: PEP-735 dependency-groups are the modern approach for tool-specific extras like dev dependencies. Unlike `[project.optional-dependencies]`, they're tool-aware (uv, pip-tools) and don't affect the package's public API. The deduplication eliminated the version drift risk documented in the earlier learning about dev dependency duplication.

### Legacy requirements files deleted; pip install from pyproject.toml directly
- **Repo**: ansible/metrics-service
- **Commits**: 531b608 (#129)
- **What happened**: All legacy requirements files were deleted: `dev-requirements.txt`, `requirements-build.txt`, `requirements-build-extra.txt`, `requirements-pinned.txt`, `requirements.txt`, `REQUIREMENTS.md`, `rpms.in.yaml`, `rpms.lock.yaml`. The `sync-requirements.sh` script and `sync-requirements.yml` GitHub Actions workflow were also removed. The production Dockerfile now installs directly from `pyproject.toml` via `pip install --prefer-binary .`. New production dependencies added: `gunicorn` and `whitenoise`. `psycopg[c]` reverted to `psycopg[binary]` and `psycopg2` reverted to `psycopg2-binary` since source builds are no longer needed.
- **Insight**: The entire sync-requirements bridge between uv and Konflux/pip was eliminated. With the production Dockerfile using `pip install .` directly from `pyproject.toml`, there's no need for separate pip-format requirements files. This removes a significant maintenance burden (keeping requirements files in sync with uv.lock). The revert to binary psycopg packages means faster builds at the cost of SBOM traceability -- suggesting the SBOM compliance approach may have shifted.

### gunicorn and whitenoise added as production dependencies
- **Repo**: ansible/metrics-service
- **Commits**: 531b608 (#129)
- **What happened**: `gunicorn` was added as a dependency for production WSGI serving (replacing Django's development `runserver`), and `whitenoise` was added for efficient static file serving without requiring Nginx to serve them directly.
- **Insight**: `whitenoise` is inserted as middleware (`WhiteNoiseMiddleware`) right after `SecurityMiddleware` and serves static files from `STATIC_ROOT`. This means static files are served by the Python process rather than Nginx, which is simpler to configure but slightly less performant for high-traffic scenarios. Nginx still handles TLS termination and reverse proxying.

### Package data for YAML files added to pyproject.toml
- **Repo**: ansible/metrics-service
- **Commits**: 520fd11 (#155)
- **What happened**: `[tool.setuptools.package-data]` section added: `"apps.settings" = ["*.yaml"]`. This ensures `apps/settings/dispatcherd.yaml` is included in the installed package.
- **Insight**: YAML config files in Python packages are not included by default (only `.py` files are). Without this entry, `pip install .` would miss `dispatcherd.yaml`, causing runtime failures when the dispatcherd config loader tries to read it.

### django-ansible-base dependency fully removed after library.lock replaced it
- **Repo**: ansible/metrics-utility
- **Commits**: 9201e26 (#395)
- **What happened**: The `django-ansible-base>=2025.1.3` dev dependency was removed from `pyproject.toml`, along with all its transitive dependencies from `uv.lock` (cryptography, cffi, pycparser, djangorestframework, django-crum, dynaconf, inflection). This dependency had been kept as a dev dependency after #259 replaced its `advisory_lock` with a custom `library.lock` implementation, but was no longer imported or used anywhere. Removing it eliminated 135 lines from `uv.lock`.
- **Insight**: After replacing functionality from an external dependency with a custom implementation, remove the dependency promptly -- leaving it as a dev dependency creates unnecessary install time, transitive dependency conflicts, and the false impression that it is still needed. **Completes** the replacement started in #259.

### cryptography bumped from 45.0.6 to 48.0.0 for CVE-2026-39892
- **Repo**: ansible/metrics-service
- **Commits**: 45ab55d (#216)
- **What happened**: The `cryptography` transitive dependency was bumped from 45.0.6 to 48.0.0 via `uv lock --upgrade-package cryptography`. CVE-2026-39892 affects cryptography >=45.0.0 and <46.0.7 (buffer overflow when non-contiguous Python buffers are passed to cryptography APIs like `Hash.update()`). Since `cryptography` is a transitive dependency pulled in by `django-ansible-base`, no changes to `pyproject.toml` were needed -- only `uv.lock` was updated (85 lines changed).
- **Insight**: For transitive dependencies, `uv lock --upgrade-package <pkg>` is the minimal fix: it bumps only the target package in the lockfile without touching `pyproject.toml` or other dependencies. This is preferable to a full `uv lock --upgrade` which could introduce unrelated breaking changes.

### Pandas upgraded from 2.x to 3.0 with compatible-release cap
- **Repo**: ansible/metrics-utility
- **Commits**: 3fc4c25 (#431)
- **What happened**: pandas was upgraded from `>=2.2.3` to `~=3.0` (i.e., `>=3.0.0,<4.0.0`) in `pyproject.toml`, and from `~=2.2.1` to `~=3.0` in `setup.cfg`. openpyxl was upgraded from `==3.1.2` to `~=3.1.5` because pandas 3.0 requires openpyxl >= 3.1.5. The version pin went through several iterations within the PR: initially `>=3.0.0` (too permissive), then `~=3.0` (compatible release, prevents 4.0). openpyxl similarly went from exact pin `==3.1.5` to `~=3.1.5` (allows 3.1.x patches). The `setup.cfg` pins were aligned with `pyproject.toml` for consistency, though `install_requires` in `setup.cfg` is superseded by `pyproject.toml` `[project].dependencies` and has no functional impact.
- **Insight**: When a major dependency upgrade (pandas 2.x -> 3.0) requires a transitive dependency bump (openpyxl >= 3.1.5), use compatible-release pins (`~=3.0`) rather than unbounded minimums (`>=3.0.0`) to prevent silent breakage from the next major version. The dual `pyproject.toml` / `setup.cfg` pin alignment is a consistency-only concern since only one is authoritative.

### metrics-utility lower bound bumped to >=0.8.0 (salt removal)
- **Repo**: ansible/metrics-service
- **Commits**: ff2eb2f (#229)
- **What happened**: The `metrics-utility` dependency lower bound was bumped from `>=0.7.x` to `>=0.8.0` because metrics-utility 0.8.0 removed the `salt` parameter from `anonymize_rollups()` (ansible/metrics-utility#399). The service's devel branch had already stopped passing `salt=` (#215), but the dep spec still allowed installing 0.7.x which requires the salt parameter. This ensures only the salt-free version is accepted.
- **Insight**: When a library removes a parameter from its API, the service-side dep spec must be bumped to reject the old version -- otherwise the lockfile could resolve to an incompatible release. The 0.7/2.7 maintenance branch uses the salt param consistently, so this bump only affects devel/main.

### pyasn1 pinned with compatible-release operator after initial >= mistake
- **Repo**: ansible/metrics-service
- **Commits**: 56267e9 (#368), 65c02c8 (#369)
- **What happened**: PR #368 added `"pyasn1>=0.6.4"` to `pyproject.toml` dependencies to address a transitive dependency issue. PR #369 (same day follow-up) corrected the version specifier from `>=0.6.4` to `~=0.6.4` (PEP 440 compatible release). The `>=` operator would allow pyasn1 1.0+ which could introduce breaking changes; `~=0.6.4` constrains to `>=0.6.4, <0.7.0`, staying on the 0.6.x line.
- **Insight**: Use `~=` (compatible release) rather than `>=` when pinning a dependency to a specific minor line. `>=0.6.4` is dangerously permissive for pre-1.0 packages where minor versions can contain breaking changes. The two-PR sequence (add then fix) is a common pattern when the initial version specifier isn't reviewed carefully. For pre-1.0 packages, `~=0.X.Y` is almost always the right choice.

### Coverage source narrowed from repo root to specific packages
- **Repo**: ansible/metrics-service
- **Commits**: a2ee264 (#366)
- **What happened**: In `pyproject.toml`, the `[tool.coverage.run]` source was changed from `["."]` (entire repo root) to `["apps", "metrics_service"]` (the two actual Python packages). The old config measured coverage for everything in the repo including test files, config scripts, and tools, inflating the denominator and making coverage percentages misleadingly low.
- **Insight**: Coverage `source` should list only the application packages being tested, not the repo root. Including test files and tooling in coverage measurement inflates the total lines denominator without contributing meaningful coverage data. For Django projects with a non-standard layout (app code in `apps/` rather than a single top-level package), list each package directory explicitly.

## Superseded / Semi-Obsolete

### pandas >=2.2.3 and openpyxl ==3.1.2
- **Repo**: ansible/metrics-utility
- Upgraded to `pandas~=3.0` and `openpyxl~=3.1.5` in 3fc4c25 (#431). The upgrade required code fixes for pandas 3.0's NaN-in-string-columns behavior change.

### requirements.txt as primary dependency source
- **Repo**: ansible/metrics-service
- After the UV migration (ee93077), `pyproject.toml` + `uv.lock` became the source of truth. The `requirements.txt` file was retained but was no longer the primary mechanism. The sync-requirements system (f848024) now generates pip-format requirements from uv.lock automatically.

### metrics-utility pinned to git commit
- **Repo**: ansible/metrics-service
- The git commit pin from edb4626 (#25) was replaced in 10581e9 (#42) with a proper version pin: `metrics-utility==0.7.20251112`.

### Django 4.2 LTS
- **Repo**: ansible/metrics-service
- Upgraded to Django 5.2.7 in 10581e9 (#42). The 4.2 LTS pin (`>=4.2,<5.0`) is no longer used.

### metrics-utility exact pin ==0.7.20251112
- **Repo**: ansible/metrics-service
- Relaxed to `>=0.7.20251112` in 4804647 (#67) to allow version upgrades without pyproject.toml changes.

### drf-spectacular dependency
- **Repo**: ansible/metrics-service
- Removed in 5fb6ead (#73). OpenAPI schema generation will be handled by `ansible_base.api_documentation` instead.

### django-oauth-toolkit and social-auth-app-django
- **Repo**: ansible/metrics-service
- Removed in 5fb6ead (#73). The service uses JWT from the gateway for authentication, not its own OAuth2 provider.

### django-split-settings
- **Repo**: ansible/metrics-service
- Was already unused (replaced by Dynaconf in 8b4aa31 #26) but remained in dependencies. Finally removed in 5fb6ead (#73).

### django-cors-headers
- **Repo**: ansible/metrics-service
- Removed in 911dd60 (#77). CORS is handled at the AAP gateway/proxy level, making the Django middleware unnecessary.

### psycopg[binary] and psycopg2-binary
- **Repo**: ansible/metrics-service
- Changed to `psycopg[c]` and `psycopg2` (source builds) in e09243d (#95) for SBOM compliance. Binary wheels can't be traced by Red Hat's software bill of materials tools.

### Dev dependencies duplicated between optional-dependencies and dependency-groups
- **Repo**: ansible/metrics-service
- The `[project.optional-dependencies].dev` section was removed in 31edf97 (#114). Dev deps now live only in `[dependency-groups].dev` (PEP-735). No need for two independent sets.

### Global --no-binary :all: in requirements-build.txt
- **Repo**: ansible/metrics-service
- The blanket `--no-binary :all:` from 400b419 (#100) was replaced by targeted `--no-binary` directives for only cryptography/psycopg packages in 72c8a74 (#104).

### setuptools-scm dynamic versioning
- **Repo**: ansible/metrics-service
- Replaced by static `version = "1.0.0"` in 72c8a74 (#104) because hermetic builds can't access git history.

### django-ansible-base exact pin ==2025.10.20
- **Repo**: ansible/metrics-service
- Relaxed to `>=2025.12.12` in e09243d (#95) with a specific git commit in `[tool.uv.sources]` for development builds.

### sync-requirements system (script + CI workflow + pre-commit hook)
- **Repo**: ansible/metrics-service
- The `sync-requirements.sh` script, `sync-requirements.yml` workflow, and pre-commit hook (from f848024 #24) were all deleted in 531b608 (#129). The production Dockerfile now installs directly from `pyproject.toml`, eliminating the need to bridge uv.lock to pip-format requirements.

### psycopg[c] and psycopg2 for source builds
- **Repo**: ansible/metrics-service
- Reverted to `psycopg[binary]` and `psycopg2-binary` in 531b608 (#129). Source builds are no longer required since the production Dockerfile uses binary wheels.

### requirements-build-extra.txt for hermetic build-time deps
- **Repo**: ansible/metrics-service
- Deleted in 531b608 (#129) along with all other requirements files. Build-time deps like pytest-runner and setuptools-scm are no longer needed since the production build uses binary wheels.

### metrics-utility bumped to 0.7.20260313
- **Repo**: ansible/metrics-service
- Bumped in 26614c4 (#113) for anonymization fixes (StorageSegment `segment_meta` parameter). See the consolidated version bumps entry in the main section.

### Dependabot uv ecosystem for Python dependency updates
- **Repo**: ansible/metrics-service
- **Commits**: 76f179e (#284)
- **What happened**: Added `package-ecosystem: 'uv'` entry to `.github/dependabot.yml` to enable automated Python dependency updates for `pyproject.toml` / `uv.lock`. The first batch of dependabot PRs (#288-#294) bumped: ruff 0.12.10->0.15.18, pytest-asyncio 1.1.0->1.4.0, isort 6.0.1->8.0.1, django-prometheus 2.4.1->2.5.0, croniter 6.0.0->6.2.2, SonarSource/sonarqube-scan-action 8.1.0->8.2.0, codecov/codecov-action 6.0.1->7.0.0.
- **Insight**: Dependabot's `uv` ecosystem support enables automated dependency updates for projects using uv's `pyproject.toml` + `uv.lock` workflow, complementing the `github-actions` ecosystem for CI actions. Monthly schedule keeps update frequency manageable.

### pytz removed: stdlib datetime.UTC replaces pytz.UTC/pytz.utc
- **Repo**: ansible/metrics-service
- **Commits**: e02d7c8 (#297), 250055f (#298)
- **What happened**: All remaining `pytz` usage in test files was replaced with `datetime.UTC` (stdlib, Python 3.11+). `pytz` was never a declared dependency -- it was available only transitively via `pandas 2.x`. With `pandas 3.0` (which dropped pytz), the lock file updated from `pandas 2.3.3` to `pandas 3.0.3`, and `pytz` was no longer available. Three test files across `dashboard_reports/` were updated: `test_tasks.py`, `test_models.py`, `test_report_view_data.py`.
- **Insight**: When upgrading to `pandas 3.0`, audit all test files for `import pytz` -- the migration path is `pytz.UTC` -> `datetime.UTC` and `pytz.utc` -> `datetime.UTC`. The `datetime.UTC` constant is available since Python 3.11.

### PyJWT pinned to exact version for security (AAP-78015)
- **Repo**: ansible/metrics-service
- **Commits**: 56fb4e5 (#336)
- **What happened**: `pyjwt==2.13.0` was added as an explicit exact-version pin in `pyproject.toml` (previously it was a transitive dependency via DAB). This is a security-motivated bump from 2.10.1 to 2.13.0 under AAP-78015. Unlike most dependencies which use range specifiers (`>=`), this uses an exact pin (`==`) reflecting the security requirement to control the exact JWT library version.
- **Insight**: Security-sensitive authentication libraries (JWT, crypto) should be pinned to exact versions rather than ranges, even when they arrive transitively, to ensure the specific patched version is always used and prevent accidental downgrades.
