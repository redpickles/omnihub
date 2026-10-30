# AI Project State

Last updated: 2026-10-30 · **v1.0.1.8** · single-window Tk desktop app · project root `D:\_Apps\omnihub`.
Deep detail (schemas, icon engine, dialog/internals, Tk gotchas, venv) lives in `docs/architecture.md` — read it alongside this file.

## Project Overview

OmniHub is one Tk window with four tabs, all persisting to JSON in a configurable data folder across restarts:

- **Folder Launcher** — frequently used folders by category, opened via Windows Explorer.
- **App Launcher** — app-file shortcuts (`.exe`/`.bat`/`.cmd`/`.lnk`/`.html`) as an Android-home icon grid; double-click launches, drag reorders.
- **Tools** — stacked-panel utilities: **KB → Bytes** (value × 1024, live result, copy icon) and **Mini Simple Spreadsheet** (3-col × 5 editable rows + live bold column-sum row, click-select on sums, "Clear all" button).
- **Settings** — choose the data folder holding `apps.json`/`folders.json` (auto-created if missing).

## Stack & Architecture

- **Python 3.13.15 + Tcl/Tk 8.6.15.** **Stdlib only** — `tkinter`, `json`, `os`, `struct`, `zlib`. No pip packages, ever.
- **Windows-only** (`os.startfile` launches via Explorer).

| File | Purpose |
|---|---|
| `app.py` (~1631 lines) | The whole app: persistence, settings, icon engine, four tabs, dialogs |
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

- **Current status:** feature-complete — all four tabs working; Tools tab now has two panels. HEAD is `ee2b561` (docs); the spreadsheet tool + v1.0.1.8 bump are **uncommitted**.
- **Known gaps:** folder entries aren't validated at load time — a missing folder surfaces only when you try to open it.

## Decisions & Gotchas

- **Destructive actions confirm** via `messagebox.askyesno(APP_NAME, ...)`.
- **Dialog pattern:** details in `docs/architecture.md` (`tk.Toplevel` + `_safe_grab()` + focus, cancel = `None`); in-place mutation helpers return a success flag; the caller persists and refreshes.
- **Tk gotchas** (Treeview `open=True`, `parent()` returns `''`, `selection()` returns item IDs): see `docs/architecture.md`.
- `APP_NAME = "OmniHub"`; `VERSION = "1.0.1.8"` on adjacent lines (app.py:24-25) — the single source of truth. `README.md`'s H1 duplicates it and must be bumped in the same change.
- **venv is a local artifact** (git-ignored): recreation recipe in `docs/architecture.md`; never copy from another project.

## Latest Session Delta

- Added **Mini Simple Spreadsheet** to `ToolsTab` (`app.py`): `_add_mini_spreadsheet_tool` + helpers `_update_spread_sums` / `_select_spread_sum` / `_clear_spreadsheet` / `_copy_selected_sum`.
- Design: 18 fixed 96×26 `tk.Frame` boxes in a ttk grid (`pack_propagate(False)`, `padx/pady=(0,2)` → exactly 2px gaps between rows **and** columns, input boxes == sum boxes); 15 editable `tk.Entry` cells with signed-number validation (`_validate_signed_number`, lone `-` allowed mid-typing, KB validator unchanged); sum row = bold `tk.Label`s updated by StringVar traces; click toggles a single light-blue selection (`_select_spread_sum`); **Ctrl+C copies the selected total** (`<Control-c>`/`<Control-C>`/`<Key>` bound on the top window — Windows sends lowercase, non-Latin layouts match neither name, so `_copy_selected_sum` guards on charcode 3); "Clear all" `ttk.Button` top-right wipes vars → sums 0. `_SPREAD_*` constants tune size/colors.
- Verified headlessly: `py_compile` + smoke test (sum math incl. `-2.5`, uniform box/gap pixels, entry==label widths, validator edges, selection toggle/move, guard via faithful fake events, Clear all). Ctrl+C key-event facts (charcode 3 always arrives, `<Key>` fires for every keystroke, names are case-dependent) confirmed via bpo-46052 + Tk debug; details in `docs/architecture.md`.
- Version bumped 1.0.1.7 → 1.0.1.8 (`VERSION` + README H1 in the same change); README Tools section documents the tool.

## Immediate Next Actions

1. Optionally validate folder entries at load time in `load_store()` (flag/drop missing paths) — `app.py`.
2. Add more Tools-panel tools under `ToolsTab._build_ui()` when needed.
