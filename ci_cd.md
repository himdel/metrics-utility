# CI/CD

> Default repo: metrics-service

## Learnings

### CI pipeline established with two workflows: pr-checks and pytest
- **Commits**: ee93077
- **What happened**: Two GitHub Actions workflows were added. `pr-checks.yml` runs on PRs and does: uv.lock freshness check (fails if `uv sync` would change it), `ruff check` with GitHub output format, and `ruff format --check`. `pytest.yml` runs on push to main and `pull_request_target`, sets up PostgreSQL, runs `uv run pytest` with coverage, and sends coverage to SonarCloud.
- **Insight**: The `uv.lock` freshness check is a good pattern -- it ensures developers run `uv sync` locally and commit the lockfile, preventing "works on my machine" dependency issues.

### pytest workflow uses pull_request_target (security consideration)
- **Commits**: ee93077
- **What happened**: The pytest workflow triggers on `pull_request_target` rather than `pull_request`. This runs the workflow in the context of the base branch, which has access to secrets (needed for SonarCloud token), but means it runs the base branch's workflow file against the PR's code.
- **Insight**: `pull_request_target` is needed when workflows require secrets (like `CICD_ORG_SONAR_TOKEN_CICD_BOT`), but it's a security risk for public repos because it runs potentially untrusted PR code with access to secrets. The workflow mitigates this by checking out the PR branch explicitly.

### pytest workflow moved to "future-workflow" directory
- **Commits**: 5b12d74 (#7)
- **What happened**: The pytest workflow was moved from `.github/workflows/pytest.yml` to `.github/workflows/future-workflow/pytest.yml`, effectively disabling it. The PR comment says "Moving pytest workflow into future folder as it isn't required right now."
- **Insight**: The pytest CI wasn't ready for prime time (likely due to database/migration dependencies not being fully set up in CI). Rather than deleting it, it was parked in a subdirectory. GitHub Actions only runs workflows directly in `.github/workflows/`, so subdirectories effectively disable them.

### SonarCloud integration with custom exclusions
- **Commits**: ee93077
- **What happened**: `sonar-project.properties` was added with: coverage exclusions for test directories, code duplication sensitivity tuned high (150 tokens, 300 lines), string literal duplication rule (S1192) ignored in migrations and tests, and Python version set to 3.11/3.12.
- **Insight**: The high duplication thresholds (150 tokens, 300 lines) indicate the team expected significant structural similarity in the codebase and didn't want false positives. This is reasonable for a Django project where models/serializers/views follow repetitive patterns.

### One-logger enforcement rule in pr-checks
- **Commits**: ee93077
- **What happened**: The `pr-checks.yml` workflow includes a step called "One logger to rule them all" that greps for `logging.getLogger(` in `metrics_utility/` and fails if any file other than `logger.py` creates its own logger.
- **Insight**: This check references `metrics_utility` (a different package), suggesting it was copied from the metrics-utility repo's CI config. It would be a no-op in this repo since the directory doesn't exist, but reveals the team's pattern of enforcing a single logger factory.

### CodeQL workflow created and immediately reverted (5 minutes apart)
- **Commits**: 7e90a26 (#15), cc53a70 (#16)
- **What happened**: A `codeql.yml` workflow was created in commit 7e90a26, then reverted just 5 minutes later in cc53a70. The file named `codeql.yml` actually contained a copy of the pytest workflow (name: "Pytest tests", running pytest, not CodeQL analysis). It was likely created by mistake -- either the wrong file was committed, or the intention was to add CodeQL but the template was wrong.
- **Insight**: This is a cautionary tale about premature CI tooling adoption and not verifying file contents before merging. The file was named `codeql.yml` but contained pytest configuration, suggesting a copy-paste error. The immediate revert (same day, same author) indicates it was caught quickly, possibly because CI started running duplicate pytest jobs or because the incorrect content was noticed in review.

### pytest workflow restored and SonarCloud integration removed
- **Commits**: cb58dc0 (#11), 8481170 (#17)
- **What happened**: In cb58dc0, the pytest workflow was moved back from the `future-workflow/` directory to `.github/workflows/pytest.yml`, with PostgreSQL as a CI service. In 8481170 (same day as the CodeQL revert), the SonarCloud reporting steps were removed from the pytest workflow, keeping only the test execution. This simplified the workflow from ~90 lines to ~55 lines.
- **Insight**: Removing SonarCloud from the pytest workflow decoupled testing from code quality reporting. SonarCloud was likely failing or requiring secrets that weren't available in all PR contexts, making the workflow unreliable. Keeping CI green is more important than having integrated code quality metrics.

### pytest workflow switched from pull_request_target to pull_request
- **Commits**: e9ff8c9 (#27)
- **What happened**: The pytest workflow trigger was changed from `pull_request_target` to `pull_request`, the complex dual-checkout logic (with conditional `if: ${{ ! github.base_ref }}` steps) was simplified to a single `actions/checkout@v5` step, and explicit read-only `permissions: contents: read` was added. The PostgreSQL port was also normalized from 55432 to 5432.
- **Insight**: The switch from `pull_request_target` to `pull_request` eliminated the security risk of running untrusted PR code with access to secrets. This was possible because SonarCloud integration (which needed secrets) had been removed earlier in 8481170. Adding explicit permissions follows the principle of least privilege for GitHub Actions.

### Konflux Tekton pipelines added for Red Hat CI/CD
- **Commits**: c31e746 (#21)
- **What happened**: Two large Tekton PipelineRun YAML files (~640 lines each) were added under `.tekton/` for pull-request and push pipelines. These pipelines use hermetic builds, multi-platform support (x86_64 + arm64), source image building, and prefetch dependencies from `requirements-build.txt`. The pipelines target the `konflux-configs` branch specifically.
- **Insight**: Konflux pipelines are significantly more complex than GitHub Actions workflows, with explicit task chaining, OCI artifact storage, and enterprise scanning (SAST, SBOMs). The `prefetch-input` parameter requires pip-format requirements files, driving the need for the sync-requirements system.

### Automated dependency sync system with GitHub Actions + pre-commit
- **Commits**: f848024 (#24), e5eba36 (#30)
- **What happened**: A `sync-requirements.sh` script was added that uses `uv export` and `uv pip compile` to generate `requirements-pinned.txt`, `dev-requirements.txt`, and `requirements-build.txt` from `uv.lock`. A GitHub Actions workflow (`sync-requirements.yml`) runs this on push to devel (auto-committing changes) and on PRs (failing if files are out of sync). A pre-commit hook was also added to auto-sync locally. In e5eba36, the workflow needed `permissions: contents: write` and `pull-requests: write` added because the default permissions were insufficient.
- **Insight**: The sync-requirements system bridges the gap between uv (development) and Konflux (pip-based builds). The CI workflow has two modes: on push it auto-commits updated requirements, on PRs it fails if they're out of sync. The follow-up permissions fix (e5eba36) is a common pattern -- GitHub Actions workflows with write operations need explicit permissions that aren't obvious until the workflow fails.

### Batch of GitHub Actions dependency bumps (node20 to node24)
- **Commits**: 3a68583 (#32), d2f46f6 (#34), 9b9da8c (#33)
- **What happened**: Three dependabot PRs bumped `astral-sh/setup-uv` from 6 to 7, `actions/github-script` from 7 to 8, and `actions/setup-python` from 5 to 6, all on the same day. All three were major version bumps driven by the Node.js 20 to 24 transition in GitHub Actions.
- **Insight**: Major version bumps in GitHub Actions are often trivial (just the node runtime upgrade) but can break self-hosted runners that aren't updated. The team merges dependabot PRs promptly, which is good practice for staying current with CI infrastructure.

### CI test database name changed and --reuse-db added
- **Commits**: c8e5f0d (#36)
- **What happened**: The CI pytest workflow changed `POSTGRES_DB` from `test_metrics_service` to `metrics_service` and added `--reuse-db` to pytest options. This aligned with the broader switch from SQLite in-memory tests to PostgreSQL tests.
- **Insight**: The database name change was necessary because `--reuse-db` reuses the actual database between test runs, and the name needed to match what Django's test runner expects. This speeds up CI significantly by avoiding database recreation on every run.

### actions/checkout bumped from v5 to v6
- **Commits**: a939642 (#58)
- **What happened**: Dependabot bumped `actions/checkout` from v5 to v6 across all three workflows (`pr-checks.yml`, `pytest.yml`, `sync-requirements.yml`). This is part of the ongoing Node.js runtime upgrades in GitHub Actions.
- **Insight**: Keeping checkout action current avoids eventual deprecation warnings. The v5->v6 bump (like v4->v5 before it) is typically transparent with no breaking changes for standard usage.

### SonarCloud re-integrated via workflow_run pattern
- **Commits**: d4996ef (#93)
- **What happened**: SonarCloud scanning was re-added (it had been removed in 8481170 #17) using a two-workflow pattern. The `pytest.yml` workflow now uploads `coverage.xml` as an artifact and saves the PR number to a text file artifact. A new `sonar_checks.yml` workflow triggers on `workflow_run` completion of the pytest workflow, downloads the coverage artifact, validates the PR number against the workflow run's commit (preventing artifact substitution attacks), and runs the SonarCloud scan with PR-specific parameters. For push events (non-PR), SonarCloud runs directly in the pytest workflow. The checkout now uses `fetch-depth: 0` for full git history (required by SonarCloud for blame analysis).
- **Insight**: The `workflow_run` pattern solves the secrets-in-PRs problem: the pytest workflow runs on `pull_request` (no secrets), uploads artifacts, then the Sonar workflow runs on `workflow_run` (has secrets) and downloads them. The PR number validation step (checking that the artifact's PR number matches the actual PR for the commit) is a security measure against malicious artifact substitution.

### Framework automation workflows added
- **Commits**: 00e68ad (#84), 5be118c (#88)
- **What happened**: Two framework workflows were added in #84: `framework-update.yml` (for automated template updates from platform-service-framework) and `framework-validation.yml` (for validating files match the template). A branch protection ruleset was also added. The validation workflow was removed in #88 because it compared files like `.gitignore`, `manage.py`, and `pyproject.toml` against the template and failed on legitimate customizations.
- **Insight**: The framework-update workflow enables automated template syncing, which is valuable for keeping the service aligned with the platform. The validation workflow was too strict -- it assumed files would be identical to the template, which isn't realistic for a service that needs project-specific configuration.

### SonarCloud workflow hardened with PR state validation and HTTP error checking
- **Commits**: 8ba3c14 (#101)
- **What happened**: The `sonar_checks.yml` workflow was updated to add PR state validation (checks if the PR is still `open` before running SonarCloud scan), HTTP status code checking for GitHub API calls (failing on non-200 responses instead of silently proceeding), and early exit if the commit-to-PR association list is empty. Redundant Sonar parameters (`sonar.host.url`, `sonar.organization`, `sonar.projectKey`) were removed from `pytest.yml` since they're set via env vars. All subsequent steps are gated with `if: steps.pr_state_check.outputs.state == 'open'`.
- **Insight**: The original workflow would silently succeed on closed PRs or when the GitHub API returned errors, potentially missing legitimate scan failures. This hardening prevents wasted CI resources on closed PRs and ensures API errors are caught rather than producing confusing downstream failures.

### Makemigrations check added to PR CI
- **Commits**: e137d39 (#92)
- **What happened**: A `python manage.py makemigrations --check` step was added to the `pr-checks.yml` workflow. This detects when model changes are committed without corresponding migrations.
- **Insight**: Without this check, developers could merge model changes without migrations, which would only be discovered when someone tries to run `migrate`. The `--check` flag makes `makemigrations` exit with non-zero if any new migrations would be created, catching the oversight early.

### CodeRabbit configured to not edit PR descriptions
- **Commits**: 80a2ce6 (#116)
- **What happened**: A `.coderabbit.yaml` was added with `inheritance: true` (inherits org-level config), `reviews.high_level_summary: false` (don't put summary in PR description), and `reviews.high_level_summary_in_walkthrough: true` (put it in the walkthrough comment instead).
- **Insight**: CodeRabbit's default behavior of editing PR descriptions overwrites manually-written context. Moving the auto-generated summary to a comment preserves the author's original PR description while still providing the AI-generated overview. The `inheritance: true` means most config comes from the org level, with this repo only overriding the summary placement.

### Coverage config moved from pytest addopts to declarative pyproject sections
- **Commits**: e137d39 (#92)
- **What happened**: Coverage options (`--cov`, `--cov-report`, etc.) were removed from `[tool.pytest.ini_options].addopts` and moved to `[tool.coverage.run]` and `[tool.coverage.report]` sections in pyproject.toml. CI was updated to explicitly pass `--cov` to pytest.
- **Insight**: Having `--cov` in addopts forces coverage measurement on every pytest run, including when running a single test file during development. This is slow and can cause failures when individual tests are run (the coverage threshold won't be met). Moving to declarative config means `pytest` runs fast by default, and `pytest --cov` explicitly enables coverage when needed (CI).

### SonarCloud workflow reorganized: scan removed from pytest, dedicated to sonar_checks
- **Commits**: 24681be (#127), 1dedd90 (#128), c4add8a (#134)
- **What happened**: Three related changes reorganized SonarCloud integration. #127 expanded `sonar.sources` from just `metrics_service` to `metrics_service,apps` (so the `apps/` directory is scanned too) and simplified the coverage exclusion pattern from `metrics_service/tests/**, tests/**` to `**/tests/**`. #128 removed the on-push SonarCloud scan step from `pytest.yml` entirely -- push-based SonarCloud was duplicating the PR-based scan. #134 re-added the push-based SonarCloud scan to `pytest.yml` (gated with `if: github.event_name == 'push'`) because devel branch pushes need coverage published without the PR workflow. The PR SonarCloud workflow (`sonar_checks.yml`) was also hardened: the unreliable `commits/{sha}/pulls` API validation was replaced with direct branch/SHA/repo matching against the triggering workflow_run, and all downstream steps now gate on a `should_scan` output instead of checking PR state separately. The `octokit/request-action` dependency was removed in favor of direct curl/jq.
- **Insight**: The SonarCloud setup settled on a clear split: push events (devel/main) get scanned inline in `pytest.yml`, while PR events use the two-workflow `workflow_run` pattern in `sonar_checks.yml`. The PR validation was fragile because the `commits/{sha}/pulls` API can return empty results for recently pushed commits due to GitHub's eventual consistency -- validating branch name + SHA + repo is more reliable.

### pr-checks workflow gained PostgreSQL service for makemigrations check
- **Commits**: e941270 (#126)
- **What happened**: The `pr-checks.yml` workflow was updated to include a PostgreSQL service container (same pattern as the pytest workflow) with Dynaconf-style database env vars (`METRICS_SERVICE_DATABASES__default__HOST`, etc.) on the "Check for missing migrations" step. Previously, `makemigrations --check` ran without a database, which would fail for any migration that references database-specific features.
- **Insight**: Django's `makemigrations` needs a database connection when using PostgreSQL-specific features (like `JSONField` default validation). Adding PostgreSQL to `pr-checks` mirrors the `pytest.yml` setup and ensures the migration check runs against the same database engine as production.

### CodeRabbit configured for additional feature branches
- **Commits**: e6fff2c (#125)
- **What happened**: The `.coderabbit.yaml` was updated to add `auto_review.base_branches: [FB-Automation-Dashboard]`, enabling CodeRabbit auto-reviews on PRs targeting the `FB-Automation-Dashboard` feature branch (in addition to the default main/devel branches).
- **Insight**: For long-lived feature branches with their own PR flow, CodeRabbit needs explicit branch configuration. The `auto_review.base_branches` setting controls which target branches trigger automated code review.

### Ruff pre-commit hooks added for auto-fixing lint and format
- **Commits**: 284f919 (#151)
- **What happened**: The `.pre-commit-config.yaml` was updated to add ruff pre-commit hooks for both linting (`ruff check --fix`) and formatting (`ruff format`). The old requirements sync hook was removed. CLAUDE.md and README.md were heavily streamlined to standardize commands around `uv` and `poe`. The `CONTRIBUTING.md` governance model reference was corrected.
- **Insight**: Adding `--fix` to the ruff pre-commit hook means formatting and fixable lint issues are auto-corrected on commit, reducing CI failures from trivial style issues. Removing the requirements sync hook reflects the earlier deletion of the sync-requirements system in #129.

### SonarCloud exclusions expanded to include settings directories
- **Commits**: 956923d (#193)
- **What happened**: `sonar-project.properties` was updated to add `**/settings/**` to both `sonar.exclusions` (source scan) and `sonar.coverage.exclusions` (coverage). This excludes `apps/settings/` and `metrics_service/settings.py` from SonarCloud analysis.
- **Insight**: Settings files contain Dynaconf validators, environment-specific overrides, and configuration constants that are inherently difficult to unit test directly (they run at import time and depend on specific environment state). Excluding them from coverage requirements avoids inflating coverage targets while keeping the coverage signal meaningful for business logic.

## Superseded / Semi-Obsolete

### pytest workflow was disabled in this batch
- Moved to `future-workflow/` directory in commit 5b12d74, then restored in cb58dc0 (#11). It is now actively running in `.github/workflows/pytest.yml`.

### SonarCloud integration in pytest workflow
- SonarCloud reporting was removed from the pytest workflow in 8481170 (#17), then partially re-added in c4add8a (#134) for push events only. The full PR-based scan now lives in `sonar_checks.yml` via `workflow_run`.

### SonarCloud PR validation via commits/{sha}/pulls API
- The `commits/{sha}/pulls` approach from 8ba3c14 (#101) was replaced in c4add8a (#134) with direct branch/SHA/repo matching. The old API was unreliable due to GitHub's eventual consistency -- recently pushed commits sometimes returned empty PR lists, causing false validation failures.
