# OmniHub — Deep Architecture Reference

Companion to `ai_state.md`. Details too verbose for working memory but costly to re-derive.

## Persistence

- `load_settings()`/`save_settings()` ↔ `settings.json`, which **always lives next to `app.py`** (`SETTINGS_FILE` is derived from `os.path.abspath(__file__)`, so it follows the script, not the CWD).
- Default when absent/corrupt: `{"data_folder": default_data_folder()}` = `<script dir>\data`.
- `set_data_folder(folder)` sets the `CONFIG_FILE`/`APPS_FILE` globals and creates `folders.json`/`apps.json` there if missing — **never overwrites**, and **never creates the folder itself** (`OSError` if a caller passes a nonexistent path).
- Loaders `load_store()`/`load_apps()` are tolerant: missing or malformed JSON → empty store, never a crash. `load_store()` also migrates the legacy flat `folders.json` into a single "Uncategorized" category.
- All savers go through `_atomic_write()` (temp file + `os.replace`) so a crash can't leave half-written JSON.

## Schemas

`folders.json`:

```json
{"categories": [{"name": "...", "entries": [{"name": "...", "path": "..."}]}]}
```

- `name` is **display-only** and falls back to the path basename; `path` is the truth used for launch/open.
- Duplicate paths are rejected **case-insensitively**.
- Categories are always listed in alphabetical order and start expanded.

`apps.json`:

```json
{"apps": [{"name": "...", "path": "..."}]}
```

- `name` is freely renamable; `path` drives both launch and icon lookup, which looks for a **same-basename `.ico` twin** in the same directory (`foo.bat` ↔ `foo.ico`).

## Icon Engine

Tk's `PhotoImage` cannot display `.ico`, so the ICO container is parsed by hand:

- `load_ico_image(ico_path, size, background)` returns a `PhotoImage` built from the decodable entry whose size is closest to the requested one.
- Supported entry encodings: **PNG-compressed** (decoded by a hand-rolled zlib/`struct` PNG reader) and **32-bit DIB**.
- Interlaced PNGs are not supported → fall back to another entry / generic folder icon.
- `PhotoImage` is RGB-only, so alpha is flattened onto a caller-supplied `background` RGB. `AppLauncherTab._bg_rgb()` obtains it via `winfo_rgb`, which is why the icon must be built after the tab's widget exists.
- The generic folder fallback icon is drawn pixel by pixel.

## Dialog Pattern

- `tk.Toplevel` + `grab_set()` (wrapped by `_safe_grab()`, which tolerates an unmapped window) + `focus_set()`; the result is read with `wait_window()`.
- Cancel means `None`; every caller checks for it.
- In-place mutation helpers return a success flag; the caller persists and refreshes.

## Folder Launcher Internals

- Built on `ttk.Treeview`: categories (bold, `open=True`) with folder entries as children.
- `_locate(item_id)` maps a Treeview item ID → `(category_index, entry_index)`; every action routes through it, so nothing else may assume positional indices.
- `CategoryManagerDialog` is destroyed by `reload()` because it holds a reference to the store it was built from; otherwise it would mutate a stale copy.

## Tk 8.6.15 Gotchas

- Treeview items insert **closed** by default — pass `open=True` or children stay hidden.
- `tree.parent()` returns `''`, not `None`, for root items.
- `tree.selection()` returns **string item IDs**, not indices — use `tree.index(id)`.
- `root.iconbitmap()` may raise `TclError` on an unsupported `.ico`; it is wrapped in `try/except` in `main()`.

## venv Notes

- The venv is a local artifact (git-ignored) and needs no packages: `requirements.txt` is intentionally empty because the app is stdlib-only.
- If recreating, run `python -m venv --clear venv` from the project root. A venv copied from another project keeps that project's path in `activate.bat`/`pyvenv.cfg` and silently activates the wrong interpreter.
- Verified environment: Python 3.13.15, Tk 8.6.15.
