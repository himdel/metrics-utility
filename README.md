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
| [multi_commit_arcs.md](multi_commit_arcs.md) | Multi-commit arcs: sequences where an approach evolved across 3+ PRs |

## Notable multi-commit arcs

See [multi_commit_arcs.md](multi_commit_arcs.md) for the full list of multi-commit arcs — sequences where an approach was tried, revised, and sometimes revised again across multiple PRs.

## Last commit processed

<!-- Used by /learnings to know where to pick up. One row per repo. -->
| Repo | Commit | Date | Subject |
|------|--------|------|---------|
| metrics-utility | 87dfbcd | 2026-06-11 | Bump pre-commit from 4.5.1 to 4.6.0 (#421) |
| metrics-service | 6316a02 | 2026-06-10 | Standalone task dev dashboard (#254) |

## About the "Superseded / Semi-Obsolete" sections

Each file ends with a section listing entries that are no longer current -- earlier approaches that were replaced by later work. These are kept for historical context (understanding *why* the current approach exists often requires knowing what it replaced) but are written in a terse format without the full Commits/What happened/Insight structure.
