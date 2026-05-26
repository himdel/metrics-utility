# Dependencies and Packaging

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

### Entry point defined as console_scripts in setup.cfg
- **Repo**: ansible/metrics-utility
- **Commits**: 8ab89cc, 22b3072
- **What happened**: The `metrics-utility` CLI entry point is defined in `setup.cfg` under `[options.entry_points]` as `console_scripts = metrics-utility = metrics_utility:manage`. Package discovery uses `find:` with `include = *`.
- **Insight**: The entry point calls `metrics_utility.manage()` which handles AWX environment setup before delegating to Django's management command infrastructure.

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

### Version switched from hardcoded string to dynamic `importlib.metadata.version`
- **Repo**: ansible/metrics-utility
- **Commits**: 55b0248 (#188)
- **What happened**: The metrics-utility version was previously hardcoded as `'0.6.1dev'` in two places: the `config` collector (embedded in config.json tarballs) and the `ManagementUtility` (for `--version` output). Both were replaced with `importlib.metadata.version('metrics-utility')`, which reads the version from the installed package metadata (ultimately from `setup.cfg`). The `pyproject.toml` was also updated to use `dynamic = ["version"]` instead of `version = "0.1.0"`, deferring to `setup.cfg` for the actual version. Additional project metadata (authors, license, classifiers, URLs, console_scripts entry point) was added to `pyproject.toml`.
- **Insight**: Using `importlib.metadata.version()` eliminates the need to manually update version strings in code -- the single source of truth is `setup.cfg`, and the runtime reads it automatically via installed package metadata.

### Library published to PyPI with date-based versioning and package scoping
- **Repo**: ansible/metrics-utility
- **Commits**: 56b5e35 (#271)
- **What happened**: A `pypi-release.yml` workflow was added for weekly PyPI releases using PyPI trusted publisher (no API tokens). The versioning scheme transforms the `setup.cfg` base version (e.g., `0.7.0dev`) to `0.7.YYYYMMDD` for each release. Package scoping was tightened in both `pyproject.toml` (`[tool.setuptools] packages`) and `setup.cfg` (`[options.packages.find]`) to include only `metrics_utility*` and exclude `tools*`, `workers*`, `mock_awx*`, `docs*`, etc. Package data patterns (`*.json`, `*.sql`, `*.txt`) were explicitly listed. The `requires-python` was raised from `>=3.11` to `>=3.12`.
- **Insight**: When a repo contains both a CLI tool and a library published as a package, explicit package inclusion/exclusion lists are critical -- without them, development-only directories (tools, mock_awx) would ship in the published package, bloating it and potentially leaking test data.

### Segment dependency made optional with try/except ImportError
- **Repo**: ansible/metrics-utility
- **Commits**: cf644cb (#270)
- **What happened**: The `segment-analytics-python` package is listed in `pyproject.toml` as a dependency but is not installed in the Controller image (only the metrics service needs it). The `import segment.analytics` at module level was wrapped in `try/except ImportError` with a `SEGMENT_AVAILABLE` boolean flag. This prevents `ImportError` at import time when the library storage module is loaded in environments without the segment package.
- **Insight**: Dependencies that are only used by one deployment context (metrics service) but whose code is importable in another context (Controller) must use lazy/conditional imports -- otherwise the library cannot be imported at all in the context that doesn't need that dependency.

### django-ansible-base dependency fully removed after library.lock replaced it
- **Repo**: ansible/metrics-utility
- **Commits**: 9201e26 (#395)
- **What happened**: The `django-ansible-base>=2025.1.3` dev dependency was removed from `pyproject.toml`, along with all its transitive dependencies from `uv.lock` (cryptography, cffi, pycparser, djangorestframework, django-crum, dynaconf, inflection). This dependency had been kept as a dev dependency after #259 replaced its `advisory_lock` with a custom `library.lock` implementation, but was no longer imported or used anywhere. Removing it eliminated 135 lines from `uv.lock`.
- **Insight**: After replacing functionality from an external dependency with a custom implementation, remove the dependency promptly -- leaving it as a dev dependency creates unnecessary install time, transitive dependency conflicts, and the false impression that it is still needed. **Completes** the replacement started in #259.

