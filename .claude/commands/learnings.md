Update the learnings files with knowledge from new commits in the upstream repos.

## Overview

Learnings are stored as topic-based markdown files on the `_learnings` branch of `himdel/metrics-utility`. Each file covers a specific area (task system, settings, Docker, etc.) — see `README.md` on that branch for the full index.

Learnings are shared across repos — the same topic file can have entries from multiple repos. If a repo warrants its own dedicated topic, create a new topic file for it.

## Environment

This skill expects three separate checkouts to already exist:
- **`ansible/metrics-utility`** on `devel` — upstream checkout, source of commits
- **`ansible/metrics-service`** on `devel` — upstream checkout, source of commits
- **`himdel/metrics-utility`** on `_learnings` — where learnings files are read and written

The user provides or confirms the paths to these checkouts.

## Steps

Process each upstream repo as a complete pass, in this order:
1. `ansible/metrics-utility`
2. `ansible/metrics-service`

For each upstream repo, run steps 1–5 below before moving to the next repo. This way the second repo's agents naturally deduplicate against what the first repo already wrote.

### 1. Find new commits

- Read `README.md` in the learnings checkout — the "Last commit processed" table has one row per repo
- Find the row for this upstream repo to get its last processed commit hash
- In the upstream checkout, list new commits on the **devel branch only** — never include commits from unmerged feature branches:
  - If the repo has no row yet, this is a first run: `git log --oneline --reverse --no-merges devel`
  - Otherwise: `git log --oneline --reverse --no-merges <last_hash>..devel`
- If no new commits, report "learnings are up to date for <repo>" and skip to the next repo

### 2. Bulk-fetch PR data

- Extract PR numbers from commit messages (pattern: `(#N)`)
- Fetch all needed PRs in ONE call: `gh pr list -R <upstream_repo> --state merged --limit 100 --json number,title,body`
- Save to a temp file

### 3. Process new commits

Launch an agent per batch of ~15 commits. For each batch, spawn an agent with this prompt structure:

```
You are extracting learnings from git history. Process these commits from
<UPSTREAM_REPO> and UPDATE the existing learnings files in <LEARNINGS_PATH>.

## Repo: <UPSTREAM_REPO>

## Commits to process: [list them]

## Rules:
- To read diffs and source, use `git -C <UPSTREAM_PATH> show <hash>` etc.
- You CAN read and write learnings files in <LEARNINGS_PATH>
- You CAN read the PR data temp file
- Read existing learnings files BEFORE writing — append, don't overwrite
- Do NOT update README.md — only the consolidation step (step 4) touches it
- Skip trivial dependabot bumps
- For large diffs, skip lockfiles, focus on meaningful changes
- Include `- **Repo**: <UPSTREAM_REPO>` in each entry

## What to extract:
- Architecture decisions and WHY they were made
- Bugs/pitfalls and their root causes
- Configuration patterns (Dynaconf, feature flags, env vars)
- Deployment/Docker patterns
- Testing patterns
- If something REVERSES or SUPERSEDES an earlier decision, move the old learning
  to the "Superseded / Semi-Obsolete" section

## Learnings entry format:
### Title
- **Repo**: <UPSTREAM_REPO>
- **Commits**: abc1234 (#PR)
- **What happened**: Description
- **Insight**: One-sentence takeaway

## Context: [include relevant context about what the commits cover]
```

Process batches **sequentially** (oldest first) so later commits can supersede earlier ones. Never run batches in parallel — they write to the same files and will clobber each other.

### 4. Consolidation

- Read all learnings files in the learnings checkout
- Check for duplicates across files (same learning in multiple places) — keep the canonical one, replace others with cross-references
- Update `README.md` if new topic files were created
- Review `multi_commit_arcs.md` — add new arcs (an approach tried, revised, revised again across 3+ PRs) and update existing ones if new commits extended them. Arcs go under the appropriate section (cross-repo, metrics-service, or metrics-utility), in roughly chronological order by when the arc starts
- Update or add this repo's row in the "Last commit processed" table (format: `| <repo> | <short_hash> | <date> | <subject> |`)
- Report what was added

### 5. Commit and push

- Stage all modified learnings files in the learnings checkout
- Commit with message: `learnings - <repo> - from <prev_hash> to <new_hash>`
- Push `_learnings` to `himdel/metrics-utility`

## Topic files

See `README.md` on the `_learnings` branch for the full index of topic files. This includes per-repo files (`metrics_utility.md`, `metrics_service.md`) for repo-specific patterns, and cross-cutting topic files for shared concerns.

Create new topic files only if a commit clearly doesn't fit any existing one. Update the README index when adding new files.

## Ordering

Entries within each topic file must be in **chronological order by commit date**, interleaving entries from different repos as needed. When adding entries from the second repo, look up commit dates (`git log -1 --format=%ai <hash>`) and insert them at the correct position relative to existing entries.

## Full reprocessing (rare)

If you ever need to reprocess one repo from scratch, strip the other repo's entries first, process clean, then reconcile by merging both sets back in chronological order. Keep the other repo's tracking table row so it doesn't get re-processed.
