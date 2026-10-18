# AI State — OmniHub

Last updated: 2026-10-17 · **v1.0.1.7.** Single-window Tk desktop app.

## 1. Project Overview

OmniHub is a single-window Tk app with four tabs, all persisting to JSON in a data folder across restarts:

- **Folder Launcher** — frequently used folders by category, opened via Windows Explorer.
- **App Launcher** — app-file shortcuts (`.exe`/`.bat`/`.cmd`/`.lnk`) as an Android-home icon grid; double-click launches, drag reorders.
- **Tools** — stacked-panel utilities; ships with **KB → Bytes** (value × 1024, live result, copy icon).
- **Settings** — choose the data folder holding `apps.json`/`folders.json` (auto-created if missing).

## 2. Stack & File Map

- **Python 3.13 + Tcl/Tk 8.6.15** (bundled). **Stdlib only** — `tkinter`, `json`, `os`, `struct`, `zlib`. No pip packages, ever.
- **Windows-only** (`os.startfile` launches via Explorer).
- Project root: `D:\_Apps\omnihub`.

| File | Purpose |
|---|---|
| `app.py` (~1520 lines) | The whole app: persistence, settings, icon engine, four tabs, dialogs |
| `omnihub.bat` | Launcher: activate `venv/` if present, else create it + `pip install -r requirements.txt`; `pause` on failure |
| `settings.json` | `{"data_folder": ...}`; lives **next to `app.py`** (bootstrap). Absent/corrupt → default `data/` subdir |
| `apps.json` / `folders.json` | App/Folder Launcher data (data folder; **git-ignored**) |
| `README.md` | User docs |
| `omnihub.ico` | Window icon (set in `main()`) |
| `.gitignore` | Ignores `venv/`, `__pycache__/`, `data/` |

## 3. Architecture

Everything lives in `app.py`, top to bottom:

1. **Persistence & settings** — `load_settings()`/`save_settings()` ↔ `settings.json`, which **always lives next to `app.py`**. Default when absent/corrupt: `{"data_folder": <script dir>}`. `set_data_folder(folder)` re-points `CONFIG_FILE`/`APPS_FILE` and **creates `folders.json`/`apps.json` if missing** (never overwrites); a missing folder raises `OSError` on save. Loaders (`load_store`/`load_apps`) are **tolerant** (missing/bad → empty store; never crash); `load_store()` migrates the legacy flat format into one "Uncategorized" category. All savers use `_atomic_write()` (temp + `os.replace`).
   - **Schemas:** `folders.json` = `{"categories": [{"name", "entries": [{"name", "path"}]}]}` (`name` display-only → basename; `path` is truth; duplicates rejected case-insensitively). `apps.json` = `{"apps": [{"name", "path"}]}` (`name` freely renamable; `path` drives launch + icon lookup via a same-dir `.ico` twin).
2. **Icon engine** — `load_ico_image()` picks the decodable ICO entry closest to the requested size (**PNG-compressed** via a hand-rolled decoder, or **32-bit DIB**). Interlaced PNGs → fallback. PhotoImage is RGB-only, so alpha flattens onto a caller-supplied `background` RGB (`_bg_rgb()` via `winfo_rgb`).
3. **`MainApp`** — `ttk.Notebook` with **four** tabs; `_reload_tabs()` re-runs each tab's `reload()` when the data folder changes.
4. **Folder Launcher** — `ttk.Treeview`: categories (bold, `open=True`) → folder entries. `_locate(item_id)` maps an item ID → `(category_index, entry_index)`; all actions route through it. Dialogs: `_CategoryPickerDialog`, `_DestinationDialog`, `delete_category_with_migration()`, `CategoryManagerDialog` (a `reload()` destroys any open instance — it holds the old store ref).
5. **App Launcher** — scrollable `tk.Canvas` responsive grid: 48px icon + word-wrapped name (`_wrap_name()`, 2 lines + ellipsis). Click = select, drag = reorder (4px threshold, live reflow), double-click = launch, right-click = menu. Icons cached in `self._images` (Tk GCs unreferenced PhotoImages).
6. **Settings** — shows data folder + **Browse…**; on browse: `save_settings()` → `set_data_folder()` → `on_change()` → both tabs reload.

**Data flow:** load settings → set data folder → load JSON → build UI → refresh; every mutation = mutate → save → rebuild (no undo, no event bus).

## 4. Implicit Rules & Quirks

- **Destructive actions confirm** via `messagebox.askyesno(APP_NAME, ...)`.
- **Dialog pattern:** `tk.Toplevel` + `grab_set()` (via `_safe_grab()`) + `focus_set()`, result via `wait_window()`; cancel = `None`; callers check.
- **In-place mutation helpers** return a success flag; caller persists and refreshes.
- **Tk gotchas:** Treeview items insert **closed** by default on 8.6.15 (pass `open=True`); `tree.parent()` returns `''` not `None`; `tree.selection()` returns string item IDs not indices (use `tree.index(id)`).
- `APP_NAME = "OmniHub"`; `VERSION = "1.0.1.7"` lives next to it.
- `.bat` launcher only `pause`s on failure (`if errorlevel 1 pause`).
- **venv is a local artifact** (git-ignored). If recreating, use `python -m venv --clear venv` from the project root — a venv copied from another project keeps that project's path in `activate.bat`/`pyvenv.cfg` and activates the wrong interpreter.

## 5. Status

### ✅ Functional
All features complete — Folder Launcher, App Launcher, Tools (KB→Bytes), Settings.

### 🚧 Known Gaps
- Folder entries aren't validated at load time — a missing folder surfaces only when you try to open it.

## Latest Session Delta
- Rewrote `omnihub.bat`: activate `venv/` if present, else create it + install `requirements.txt`, then run `app.py`.
- Recreated `venv/` (copied from `folder-launcher` with a wrong hardcoded `VIRTUAL_ENV`); activation now resolves to `D:\_Apps\omnihub\venv`.
- Regenerated `requirements.txt` (empty — stdlib-only); prior file had a stray `zxcvbn==4.5.0` from system pip.
- Bumped 1.0.1.6 → 1.0.1.7 (`app.py`, `ai_state.md`).
- Fixed `omnihub.bat` crash — parens in an `echo` inside the `if (...)` block errored CMD; removed them.

## Immediate Next Actions
1. Optionally validate folder entries at load time in `load_store()` (flag/drop missing paths) — `app.py`.
2. Add more Tools-panel tools under `ToolsTab._build_ui()` when needed.
