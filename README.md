# Learnings

Topic-based markdown files documenting architectural decisions, pitfalls, patterns, and their evolution across `ansible/metrics-utility` and `ansible/metrics-service`.

Each learning entry has these fields:
- **Repo**: which repo the commit is from (always include)
- **Commits**: the commit hashes (with PR numbers where applicable)
- **What happened**: factual description of the change
- **Insight**: the lesson or pattern worth remembering

## Index

| File | Description |
|------|-------------|
| [metrics_utility.md](metrics_utility.md) | `ansible/metrics-utility` specific patterns, conventions, gotchas |
| [metrics_service.md](metrics_service.md) | `ansible/metrics-service` specific patterns, conventions, gotchas |
| [api_design.md](api_design.md) | REST API evolution: serializers, viewsets, permissions, URL routing, endpoint discovery |
| [architecture.md](architecture.md) | App structure, DAB integration, service layer, platform-service-framework retrofit |
| [bugs_and_pitfalls.md](bugs_and_pitfalls.md) | Bugs found and fixed: race conditions, copy-paste errors, silent failures, state machine ordering |
| [ci_cd.md](ci_cd.md) | GitHub Actions workflows, SonarCloud integration, Konflux pipelines, pre-commit hooks |
| [database_and_migrations.md](database_and_migrations.md) | Migration rewrites, model additions, multi-database setup, migration squashing |
| [dependencies_and_packaging.md](dependencies_and_packaging.md) | UV migration, dependency pins, SBOM compliance, sync-requirements system, DAB extras |
| [docker_and_deployment.md](docker_and_deployment.md) | Dockerfile evolution, container architecture, Nginx/Gunicorn, supervisord, Red Hat certification |
| [metrics_collection.md](metrics_collection.md) | Collector registry, MAP-REDUCE pipeline, anonymization, Segment integration, advisory locks |
| [performance.md](performance.md) | Benchmark framework for collectors and rollups, API vs internal vs Jenkins benchmarks |
| [settings_and_configuration.md](settings_and_configuration.md) | Dynaconf, feature flags, environment variables, URL prefix, secrets management, validation |
| [task_system.md](task_system.md) | Task registry, scheduling (signals to polling to APScheduler), dispatcherd, concurrency fixes |
| [testing.md](testing.md) | Test organization, SQLite-to-PostgreSQL switch, coverage config, test patterns |

## Notable multi-commit arcs

Several learnings span many commits and PRs. These are the most instructive arcs:

- **Validation saga** (settings_and_configuration.md): added -> broke -> turned off -> re-enabled with proper messages (5 PRs over 3 months)
- **Worker count** (task_system.md, docker_and_deployment.md): 4 -> 1 (band-aid) -> 4 (real fix with atomic updates and advisory locks)
- **Feature flag evolution** (task_system.md): single flag -> overly broad scope -> three independent flags
- **URL prefix** (settings_and_configuration.md): env var -> renamed env var -> Django setting -> proper prefix interpretation (4 iterations)
- **Secrets management** (settings_and_configuration.md): SEGMENT_WRITE_KEY from config -> from file with base64 -> from file without base64
- **CodeQL** (ci_cd.md): created then immediately reverted (wrong file contents, 5 minutes apart)

## Last commit processed

<!-- Used by /learnings to know where to pick up. One row per repo. -->
| Repo | Commit | Date | Subject |
|------|--------|------|---------|
| metrics-service | f9c6e49 | 2026-05-22 | Removing all the results files as they are being moved to the handbook (#227) |

## About the "Superseded / Semi-Obsolete" sections

Each file ends with a section listing entries that are no longer current -- earlier approaches that were replaced by later work. These are kept for historical context (understanding *why* the current approach exists often requires knowing what it replaced) but are written in a terse format without the full Commits/What happened/Insight structure.
