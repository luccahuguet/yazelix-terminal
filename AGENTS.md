# Agent Guidelines

This repository is the experimental Rio-derived `yazelix-terminal` workspace.

## Scope

- Keep main Yazelix integration out of this repository until local evidence proves the terminal path is viable.
- Use Rio upstream as the implementation base and keep the fork delta reviewable.
- Treat Ghostty as the primary behavior and quality target.
- Treat WezTerm as a mature terminal-engine comparison target.
- Treat Kitty implementation code as GPL-owned reference material: use official specs and black-box behavior unless a licensing decision explicitly allows more.

## Beads

Use Beads Rust (`br`) in this repository.

- Run `br ready` and `br show <id>` before selecting work.
- Use `br update <id> --status in_progress --claim` before implementation.
- Close completed beads with `br close <id> --reason "..."`
- Run `br sync --flush-only` before committing Beads changes.
- Commit after each completed bead.

## Working Rules

- Do not push unless the maintainer explicitly asks or a pushed experiment branch is useful for preserving/shareable work.
- Prefer small, evidence-backed commits.
- If a feature is unexpectedly hard, document source paths, failure evidence, rejected approaches, and the next viable pivot, then move to another bead.
- For visual behavior, prefer screenshots or captured artifacts over log-only claims.
- Preserve Rio, Ghostty, WezTerm, and other upstream license notices when code is copied or ported.
