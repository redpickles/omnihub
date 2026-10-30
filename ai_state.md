# AI Project State

Last updated: 2026-10-30 · **v1.0.1.7** · single-window Tk desktop app · project root `D:\_Apps\omnihub`.
Deep detail (schemas, icon engine, dialog/internals, Tk gotchas, venv) lives in `docs/architecture.md` — read it alongside this file.

## Project Overview

OmniHub is one Tk window with four tabs, all persisting to JSON in a configurable data folder across restarts:

- **Folder Launcher** — frequently used folders by category, opened via Windows Explorer.
- **App Launcher** — app-file shortcuts (`.exe`/`.bat`/`.cmd`/`.lnk`/`.html`) as an Android-home icon grid; double-click launches, drag reorders.
- **Tools** — stacked-panel utilities; ships with **KB → Bytes** (value × 1024, live result, copy icon).
- **Settings** — choose the data folder holding `apps.json`/`folders.json` (auto-created if missing).

## Stack & Architecture

- **Python 3.13.15 + Tcl/Tk 8.6.15.** **Stdlib only** — `tkinter`, `json`, `os`, `struct`, `zlib`. No pip packages, ever.
- **Windows-only** (`os.startfile` launches via Explorer).

| File | Purpose |
|---|---|
| `app.py` (~1520 lines) | The whole app: persistence, settings, icon engine, four tabs, dialogs |
| `omnihub.bat` | Launcher: activate `venv/` if present, else create it + `pip install -r requirements.txt`; `pause` only on failure |
| `settings.json` | `{"data_folder": ...}`; lives **next to `app.py`** (bootstrap, **git-tracked** unlike the data files). Absent/corrupt → default `data/` subdir |
| `apps.json` / `folders.json` | App/Folder Launcher data (data folder; **git-ignored**) |
| `README.md` | User docs · `omnihub.ico` window icon (set in `main()`) |
| `.gitignore` | Ignores `venv/`, `__pycache__/`, `data/` |

Everything lives in `app.py`, top to bottom:

1. **Persistence & settings** — `load_settings()`/`save_settings()` ↔ `settings.json`. `set_data_folder(folder)` re-points the `CONFIG_FILE`/`APPS_FILE` globals and creates missing data files, **never overwriting, never making the folder**. Loaders are tolerant (missing/bad → empty store, never crash); `load_store()` migrates the legacy flat format into "Uncategorized"; savers use `_atomic_write()`. Schemas and rules: `docs/architecture.md`.
2. **Icon engine** — `load_ico_image()` picks the decodable ICO entry closest to the requested size (PNG-compressed via a hand-rolled decoder, or 32-bit DIB). PhotoImage is RGB-only, so alpha flattens onto a caller-supplied `background` RGB (`_bg_rgb()` via `winfo_rgb`).
3. **`MainApp`** — `ttk.Notebook` with **four** tabs; `_reload_tabs()` re-runs each tab's `reload()` when the data folder changes.
4. **Folder Launcher** — `ttk.Treeview`: categories → folder entries. `_locate(item_id)` maps an item ID → `(category_index, entry_index)`; all actions route through it. Dialogs: `_CategoryPickerDialog`, `_DestinationDialog`, `delete_category_with_migration()`, `CategoryManagerDialog`.
5. **App Launcher** — scrollable `tk.Canvas` responsive grid: 48px icon + word-wrapped name (`_wrap_name()`, 2 lines + ellipsis). Click = select, drag = reorder (4px threshold, live reflow), double-click = launch, right-click = menu. Icons cached in `self._images` (Tk GCs unreferenced PhotoImages).
6. **Settings** — shows data folder + **Browse…**; on browse: `save_settings()` → `set_data_folder()` → `on_change()` → both tabs reload.

**Startup (`main()`):** the root is `withdraw()`n until the data folder is resolved — a missing default is bootstrapped with `os.makedirs`, a missing configured folder prompts the user to pick an **existing** one (cancel reverts to the default); a stale folder is never recreated silently.

**Data flow:** load settings → set data folder → load JSON → build UI → refresh; every mutation = mutate → save → rebuild (no undo, no event bus).

## Status & Constraints

- **Current status:** feature-complete — all four tabs working. HEAD `7627036` added `.html` to the App Launcher.
- **Known gaps:** folder entries aren't validated at load time — a missing folder surfaces only when you try to open it.

## Decisions & Gotchas

- **Destructive actions confirm** via `messagebox.askyesno(APP_NAME, ...)`.
- **Dialog pattern:** `tk.Toplevel` + `grab_set()` (via `_safe_grab()`) + `focus_set()`, result via `wait_window()`; cancel = `None`; callers check. In-place mutation helpers return a success flag; the caller persists and refreshes.
- **Tk gotchas** (Treeview `open=True`, `parent()` returns `''`, `selection()` returns item IDs): see `docs/architecture.md`.
- `APP_NAME = "OmniHub"`; `VERSION = "1.0.1.7"` on adjacent lines (app.py:24-25) — the single source of truth. `README.md`'s H1 duplicates it and must be bumped in the same change.
- **venv is a local artifact** (git-ignored): recreate with `python -m venv --clear venv` from the project root, never copy from another project.

## Latest Session Delta

- No code changes. Ported `ai_state_old.md` into this file, **verifying every claim against the current tree** (app.py, README.md, `.gitignore`, git log).
- Corrections while porting: the settings default is `<script dir>\data`, not `<script dir>`; and a missing data folder is handled by the `main()` startup prompt, not by an `OSError` on save.
- Split deep technical detail out into `docs/architecture.md` to keep this file inside its size budget.

## Immediate Next Actions

1. Optionally validate folder entries at load time in `load_store()` (flag/drop missing paths) — `app.py`.
2. Add more Tools-panel tools under `ToolsTab._build_ui()` when needed.
3. `ai_state_old.md` is now a redundant untracked duplicate — delete it once the user has reviewed `ai_state.md`.
