# AI Project State

Last updated: 2026-10-30 · **v1.0.1.8** · single-window Tk desktop app · project root `D:\_Apps\omnihub`.
Deep detail (schemas, icon engine, dialog/internals, **spreadsheet internals**, Tk gotchas, venv) lives in `docs/architecture.md`; the headless-testing recipe and its covered checks live in `docs/testing.md`. Read both alongside this file.

## Project Overview

OmniHub is one Tk window with four tabs, all persisting to JSON in a configurable data folder across restarts:

- **Folder Launcher** — frequently used folders by category, opened via Windows Explorer.
- **App Launcher** — app-file shortcuts (`.exe`/`.bat`/`.cmd`/`.lnk`/`.html`) as an Android-home icon grid; double-click launches, drag reorders.
- **Tools** — stacked-panel utilities: **KB → Bytes** (value × 1024, live result, copy icon) and **Mini Simple Spreadsheet** (3-col × 5 editable rows + a live bold row of four totals — three column sums plus a pale-yellow grand total, any click-selected and Ctrl+C-copied, "Clear all" button).
- **Settings** — choose the data folder holding `apps.json`/`folders.json` (auto-created if missing).

## Stack & Architecture

- **Python 3.13.15 + Tcl/Tk 8.6.15.** **Stdlib only** — `tkinter`, `json`, `os`, `struct`, `zlib`. No pip packages, ever.
- **Windows-only** (`os.startfile` launches via Explorer).

| File | Purpose |
|---|---|
| `app.py` (~1752 lines) | The whole app: persistence, settings, icon engine, four tabs, dialogs |
| `omnihub.bat` | Launcher: activate `venv/` if present, else create it + `pip install -r requirements.txt`; `pause` only on failure |
| `settings.json` | `{"data_folder": ...}`; **next to `app.py`**, git-tracked; absent/corrupt → default `data/` |
| `apps.json` / `folders.json` | Tab data in the data folder (git-ignored) |
| `README.md` | User docs · `omnihub.ico` icon (set in `main()`) |
| `.gitignore` | Ignores `venv/`, `__pycache__/`, `data/` |

Everything lives in `app.py`, top to bottom; deep detail per part in `docs/architecture.md`:

1. **Persistence & settings** — `load_settings()`/`save_settings()` ↔ `settings.json`; `set_data_folder()` repoints the data-file globals and creates missing files (**never overwrites, never makes the folder**).
2. **Icon engine** — hand-parsed `.ico` → `PhotoImage` (RGB-only; alpha flattened onto a caller-supplied background RGB).
3. **`MainApp`** — `ttk.Notebook`, **four** tabs; `_reload_tabs()` re-runs `reload()` on data-folder change.
4. **Folder Launcher** — `ttk.Treeview` categories → entries; `_locate(item_id)` → `(category_index, entry_index)`, every action routes through it.
5. **App Launcher** — scrollable `tk.Canvas` grid: 48px icon + wrapped name; click selects, drag reorders, double-click launches, right-click menu; icons cached in `self._images`.
6. **Settings** — data-folder path + **Browse…** → save → `set_data_folder()` → `on_change()` reloads data tabs.

**Startup (`main()`):** root stays `withdraw()`n until the data folder resolves — missing default bootstrapped with `os.makedirs`; missing configured folder prompts for an **existing** one (cancel → default); a stale folder is never recreated.

**Data flow:** load settings → set data folder → load JSON → build UI → refresh; every mutation = mutate → save → rebuild (no undo, no event bus).

## Status & Constraints

- **Current status:** feature-complete — all four tabs working; Tools tab has two panels. HEAD is `ee2b561` (docs); uncommitted: the spreadsheet tool (incl. the fourth grand-total box), the new `docs/architecture.md` spreadsheet section, `docs/testing.md`, and the v1.0.1.8 bump.
- **Known gaps:** folder entries aren't validated at load time — a missing folder surfaces only when you try to open it.

## Decisions & Gotchas

- **Destructive actions confirm** via `messagebox.askyesno(APP_NAME, ...)`.
- **Dialog pattern:** details in `docs/architecture.md` (`tk.Toplevel` + `_safe_grab()` + focus, cancel = `None`); in-place mutation helpers return a success flag; the caller persists and refreshes.
- **Tk gotchas** (Treeview quirks, headless sizing, Ctrl+C event names): `docs/architecture.md`.
- `APP_NAME = "OmniHub"`; `VERSION = "1.0.1.8"` on adjacent lines (app.py:24-25) — the single source of truth. `README.md`'s H1 duplicates it and must be bumped in the same change.
- **venv is a local artifact** (git-ignored): recreation recipe in `docs/architecture.md`; never copy from another project.

## Latest Session Delta

- Added **Mini Simple Spreadsheet** to `ToolsTab` (`app.py`): `_add_mini_spreadsheet_tool` + helpers `_update_spread_sums` / `_select_spread_sum` / `_clear_spreadsheet` / `_copy_selected_sum`.
- Version 1.0.1.7 → 1.0.1.8 in the same change (`VERSION` + README H1); README Tools section documents the tool. The later grand-total box did **not** bump it.
- Spreadsheet internals (boxes, `_SPREAD_*` colors, validation, traces, selection, Ctrl+C) now live in `docs/architecture.md`. The **fourth grand-total box** (grid column `_SPREAD_COLS`, default bg `#f9fcb2`) adds the three sums and is now wired **identically** to the column sums: `_spread_sum_vars`/`_spread_sum_labels`/`_spread_sum_bg` hold 4 entries (index `_SPREAD_COLS` = grand), `_select_spread_sum(cell)` takes 0–3, and `_spread_sum_bg[cell]` restores each cell's own default color when deselected.
- Verified headlessly (recipe + every covered check in `docs/testing.md`): totals `12`/`2.25`/`7` → grand `21.25`; grand box 96×26 at x=294 vs x=196; `<Button-1>` binding present, selecting it paints `#b6d7f0` and deselecting returns `#f9fcb2` (not gray); Ctrl+C copies the grand total (`21.25`, `0` after Clear all) and ignores ordinary keystrokes.

## Immediate Next Actions

1. Optionally validate folder entries at load time in `load_store()` (flag/drop missing paths) — `app.py`.
2. Add more Tools-panel tools under `ToolsTab._build_ui()` when needed.
