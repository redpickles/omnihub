# AI State — Launcher Hub (swiss-army)

Last updated: 2026-10-13 · Session focus: Settings tab (configurable data folder) + README refresh. **Version 1.0.1.1.**

## 1. Project Overview

A single-window Python desktop app ("Launcher Hub") with three tabs:

- **Folder Launcher** — frequently used folders organized by category, opened via Windows Explorer.
- **App Launcher** — shortcuts to app files (`.exe`/`.bat`/`.cmd`/`.lnk`) shown as an Android-home-screen-style icon grid; double-click launches, drag reorders.
- **Settings** — choose the data folder where `apps.json` and `folders.json` are stored; both are created automatically if missing.

All tabs persist their data to JSON files in the data folder and survive restarts.

## 2. Tech Stack & File Map

- **Python 3.13** with **Tcl/Tk 8.6.15** (bundled). **Stdlib only** — `tkinter`, `json`, `os`, `struct`, `zlib`. No pip packages, no third-party dependencies, ever.
- **Windows-only** (`os.startfile` launches files/folders with Explorer).
- Project root: `D:\_Apps\swiss-army`

| File | Purpose |
|---|---|
| `app.py` (~1200 lines) | The entire application: persistence, settings, icon engine, all three tabs, dialogs |
| `swiss-army.bat` | Launcher: uses `venv\Scripts\python.exe` if present, else system `python`; `pause` only on `errorlevel 1` so a clean close doesn't leave a cmd window |
| `settings.json` | App settings (`{"data_folder": ...}`); created when the user first browses; absent = default data folder is the app directory |
| `apps.json` | App Launcher data (lives in the **data folder**) |
| `folders.json` | Folder Launcher data (lives in the **data folder**) |
| `README.md` | User-facing docs, current as of v1.0.1.1 |
| `swiss-army.ico` | App icon (exists but not yet applied as the window icon) |
| `.gitignore` | Generic multi-language ignore file; `venv/`, `__pycache__/` ignored |
| `venv/` | Virtual environment (no packages installed in it) |

## 3. System Mental Model & Architecture

Everything lives in `app.py`. Layering, top to bottom:

1. **Persistence & settings (module-level functions)**
   - `load_settings()` / `save_settings()` → `settings.json`, which **always lives next to `app.py`** (it's the bootstrap file — the app must find its config before it knows the data folder). Default when absent/corrupt: `{"data_folder": <script dir>}`.
   - `set_data_folder(folder)` re-points the global `CONFIG_FILE`/`APPS_FILE` at the data folder and **creates `folders.json`/`apps.json` if missing** — existing files are never overwritten. Called at startup in `main()` and after every Settings browse.
   - `load_store()` / `save_store()` → `folders.json`; `load_apps()` / `save_apps()` → `apps.json`. Loaders are **tolerant**: missing file, bad JSON, or malformed entries → empty store. The app never crashes on corrupt config.
   - `load_store()` migrates the legacy flat format (`{"folders": [...]}`) into a single "Uncategorized" category.
2. **Icon engine** — `_parse_ico()` reads ICO directory entries; `load_ico_image(ico_path, size, background)` picks the decodable entry closest to `size`: **PNG-compressed entries** (bitcount 0, blob starts with `\x89PNG`) via `_png_to_photoimage()` (from-scratch PNG decoder: zlib IDAT decompression, scanline filters None/Sub/Up/Average/Paeth, color types 0/2/4/6 at 8/16 bits) or **classic 32-bit DIBs** via `_dib_to_photoimage()` (BGRA, bottom-up rows). **PhotoImage has no alpha channel**, so transparent pixels are flattened onto a caller-supplied `background` RGB tuple; the App tab passes the grid's real background (`_bg_rgb()` via `winfo_rgb`). `folder_icon()` draws the generic fallback pixel by pixel.
3. **`MainApp`** — a `ttk.Notebook` with three tabs: `FolderLauncherApp`, `AppLauncherTab`, `SettingsTab`. Holds references to the first two; `_reload_tabs()` calls their `reload()` methods when the data folder changes.
4. **Folder Launcher tab (`FolderLauncherApp`)**
   - `ttk.Treeview`: categories (bold, top level, inserted with `open=True`) → folder entries (name + path columns).
   - `_locate(item_id)` maps a Treeview item ID to `(category_index, entry_index)`; every action goes through it.
   - All mutations: mutate in-memory store → `save_store()` → `_refresh_tree()`.
   - Dialogs: `_CategoryPickerDialog`, `_DestinationDialog` + `delete_category_with_migration()`, `CategoryManagerDialog` (reuses an already-open instance).
   - `reload()` destroys any open CategoryManagerDialog first — it holds a reference to the old store object.
5. **App Launcher tab (`AppLauncherTab`)**
   - Scrollable `tk.Canvas` hosting a responsive grid of cells: 48px icon on top, word-wrapped name label below (`_wrap_name()`, max 2 lines + ellipsis). Column count follows window width; mouse-wheel scrolling bound per cell.
   - Interactions: **click = select** (`SELECT_BG`), **drag = reorder** (4px press-move threshold; live reflow with `DRAG_BG` highlight; order saved on release), **double-click = launch**, **right-click = menu** (Open / Rename… / Remove, with confirmation).
   - Icons cached in `self._images` keyed by path — **Tk garbage-collects unreferenced PhotoImages**.
6. **Settings tab (`SettingsTab`)** — shows the data folder path + **Browse…** button. On browse: `save_settings()` → `set_data_folder()` (creates missing data files) → `on_change()` callback → both tabs reload from disk.

**Data flow:** load settings at startup → set data folder (create files if missing) → load JSON → build UI → refresh view. Every user mutation = mutate in-memory structure → save JSON → rebuild the view. No undo, no event bus; views are rebuilt from scratch on each change.

## 4. Data Schemas

`settings.json` (next to `app.py`):
```json
{"data_folder": "D:\\_Apps\\swiss-army"}
```

`folders.json` (in the data folder):
```json
{
  "categories": [
    {"name": "System", "entries": [{"name": "Downloads", "path": "C:\\Users\\hanze\\Downloads"}]}
  ]
}
```
- `name` is display-only (defaults to basename of path); `path` is the source of truth. Duplicates rejected case-insensitively on add.

`apps.json` (in the data folder):
```json
{"apps": [{"name": "PNG 2 ICO", "path": "D:\\_Apps\\PNG2ICOjs\\PNG2ICO.bat"}]}
```
- `name` is freely renamable; `path` drives launching and icon lookup (`.ico` twin with the same base name in the same directory).

## 5. Implicit Rules & Quirks

Adopted patterns that aren't obvious from the config files:

- **Stdlib only.** If a feature needs a library, reimplement it (see the hand-rolled PNG decoder) rather than adding a dependency.
- **Bootstrap vs data separation:** `settings.json` always lives next to `app.py`; the data files live in the configurable data folder. Never move settings into the data folder.
- **Tolerant loading, eager saving.** Corrupt config degrades to empty; every mutation saves immediately (no dirty-state tracking).
- **Creating ≠ overwriting:** `set_data_folder` only creates missing data files; existing ones are preserved.
- **Case-insensitive dedupe** on add (`path.lower()` comparison).
- **Destructive actions confirm** via `messagebox.askyesno(APP_NAME, ...)`.
- **Dialog pattern:** `tk.Toplevel` + `grab_set()` + `focus_set()`, result returned via `wait_window()`; cancel = `None`; callers check for `None` before acting.
- **In-place mutation helpers** return a success flag; the caller persists and refreshes (e.g. `delete_category_with_migration`).
- **Tk gotchas encoded in comments:** Treeview items insert **closed** by default on Tk 8.6.15 (must pass `open=True`); `tree.parent()` returns `''` not `None` for top-level items; `tree.selection()` returns **string item IDs**, not list indices (use `tree.index(id)`); `PhotoImage` is RGB-only (flatten alpha onto a background).
- **Keep PhotoImages referenced** (`self._images`) or Tk silently drops them.
- `APP_NAME = "Folder Launcher"` is used as the title for **all** messageboxes/dialogs — it predates the app being renamed to "Launcher Hub".
- The `.bat` launcher only `pause`s on failure (`if errorlevel 1 pause`) so a clean exit doesn't strand a console window.

## 6. Current Status & Roadmap

### ✅ Functional
- Folder Launcher: full CRUD for folders and categories, category-deletion migration dialog, alphabetical display, expanded-by-default categories, persistence, legacy-format migration.
- App Launcher: add/rename/remove (with confirmation), drag-to-reorder with live reflow, double-click launch, right-click menu, responsive scrollable icon grid, word-wrapped labels, PNG + DIB `.ico` decoding.
- Settings tab: browse for the data folder, choice persisted in `settings.json`, auto-creation of missing `apps.json`/`folders.json`, both tabs reload after a folder change.
- `swiss-army.bat`: venv-aware launcher, no lingering console window on clean exit.
- README.md current as of v1.0.1.1.

### 🚧 Half-baked / Known Gaps
- **No tests** of any kind; nothing guards against regressions in the icon decoders or persistence loaders.
- Window icon not set: `swiss-army.ico` exists but `main()` never calls `root.iconbitmap(...)`.
- No version constant in code — the version lives only in README.md.
- Cosmetic: antialiased icon edges can show a faint mismatch against the selection highlight (inherent to RGB-only PhotoImage; flattening happens at load time, before selection).
- Folder entries aren't validated at load time — a missing folder is only reported when you try to open it.

### 🎯 Next Actions
1. **Create `D:\_Apps\swiss-army\test_app.py`** — headless smoke tests (`tk.Tk()` + `root.withdraw()`) covering `load_store`, `load_apps`, `load_settings`, `set_data_folder`, `_decode_png`, `_wrap_name`, and `_parse_ico` entry selection.
2. **Open `D:\_Apps\swiss-army\app.py`** — add `VERSION = "1.0.1.1"` near `APP_NAME`, call `root.iconbitmap(...)` in `main()`, and consider renaming `APP_NAME` to `"Launcher Hub"` (affects every dialog title).
3. Optionally validate folder entries at load time in `load_store()` (flag or drop missing paths) — file: `D:\_Apps\swiss-army\app.py`.
