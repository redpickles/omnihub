# Coding & Documentation Guidelines

## 1. Project Memory (`ai_state.md`)
Maintain `ai_state.md` in the project root as compact working memory for a future AI instance with zero conversation history.

- **Session Start:** Read `ai_state.md` if present. Verify relevant claims against the current code and project state before relying on them. If missing, create it when useful.
- **Verification:** Check relevant repository status and existing changes before editing. Preserve unrelated user changes. Treat the current user request as authoritative over stale notes. Memory is context, not proof.
- **Focus:** Prioritize costly-to-rediscover information: purpose, architecture, current status, constraints, important decisions, non-obvious gotchas, and immediate next steps.
- **Size Limits:** Keep `ai_state.md` under 800 words and 120 lines. If complex recipes, testing setups, or schemas push it over this limit, move those details into standalone files in `docs/` and reference them from `ai_state.md`.
- **Maintenance:** Remove obsolete tasks, resolved bugs, superseded decisions, and details easily rediscovered from code. Put important long-term details that do not fit in appropriate documentation and reference them here.
- **Session End:** After meaningful development work, update the file as needed without waiting for the user to ask. Avoid needless rewrites when nothing meaningful changed.

## 2. Code Organization
- Prefer modular files with clear responsibilities over monolithic files mixing unrelated functionality.
- Avoid excessive fragmentation, unnecessary abstractions, and arbitrary file-size limits. Split code when it improves maintainability or separates independently understandable functionality.
- Follow existing project patterns and keep dependencies clear.
- Before editing, inspect relevant files and necessary dependencies. Avoid dumping directory trees or reading unrelated code.
- Avoid unrelated refactoring during feature work.

## 3. Human Documentation (`README.md`)
- Check whether `README.md` exists; create it if missing and the project would benefit from one.
- Keep it accurate and useful for human users and developers. Cover purpose, features, setup, configuration, and usage as relevant.
- Update it when code changes introduce undocumented functionality, change setup or behavior, or make existing documentation inaccurate.
- Avoid duplicating `ai_state.md` or documenting implementation details that belong elsewhere.
- Do not make documentation changes merely to create activity or satisfy a checklist.

## 4. Version Control & Commit Messages
- **Never create commits automatically.** Leave all committing to the user unless explicitly instructed otherwise. Do not commit, stage, amend, or alter the Git index.
- After each successful, meaningful code update, provide a suggested commit message as plain text that the user can copy and use. Do not provide Git commands.
- Use concise, descriptive commit messages in the imperative mood (e.g., `Fix image loading on startup`) unless the project has an established convention.
- Base the message on changes actually made, not intended changes. Do not suggest a commit message for unsuccessful or unapplied changes.
- If multiple independent changes were made, suggest separate commit messages when that improves clarity.

## 5. Verification & Session Wrap-up
- Inspect relevant source files, configuration, entrypoints, and existing changes before editing or documenting behavior.
- Never invent details or claim functionality works without evidence.
- Run relevant tests, builds, or checks when appropriate. Clearly distinguish verified behavior from untested changes and explain important failures or environmental blockers.
- Never modify application code solely to update documentation.
- Before finishing meaningful development work, review both documentation files (`README.md` and `ai_state.md`) and update them as needed.
- Enforce the `ai_state.md` size limit (under 800 words and 120 lines). Offload deep technical details or recipes to standalone reference files if needed.
- Leave the project state accurate: summarize meaningful changes, record unresolved issues or blockers, and identify next actions only when genuine follow-up work remains.

## 6. Versioning
- Define the version number in exactly one place (e.g., `package.json`, `pyproject.toml`, a `VERSION` file, or a single constant). Reference it from everywhere else—never duplicate it across files, docs, or UI strings. Duplicated versions drift and become wrong.
- Bump the version only for significant feature additions or breaking changes. Do not bump for minor bug fixes, refactors, documentation changes, or routine maintenance.
- When bumping, update the single source of truth and any derived references (badges, changelogs) in the same change.