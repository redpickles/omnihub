# AI Project State

Last updated: 2026-11-17 · **v0.7.9.0** · single-window Tk desktop app · project root `D:\Han\Apps\Utils\omnihub`.
Schemas, icon engine, dialogs, tab internals, backup format, Tk gotchas and the venv recipe: `docs/architecture.md`. Headless-testing recipe and per-run coverage: `docs/testing.md`.

## Project Overview

One Tk window, five tabs, all persisting to JSON in a configurable data folder across restarts:

- **Folder Launcher** — frequently used folders by category, opened in Explorer; the context menu also copies a path or manages entries.
- **App Launcher** — app-file shortcuts (`.exe`/`.bat`/`.cmd`/`.lnk`/`.html`) as an Android-home icon grid; double-click launches, drag reorders.
- **Tools** — stacked utility panels: **KB → Bytes**, **Mini Simple Spreadsheet**, **Slash Reverser** (the last two side by side in one row).
- **Settings** — choose the data folder; **Export data…** / **Import data…** move everything (data files + app icons) through one dated `.zip`.
- **About** — app name + version and the last updated date, both rendered from `VERSION` / `LAST_UPDATED`.

## Stack & Architecture

- **Python 3.13.15 + Tcl/Tk 8.6.15. Stdlib only** — `tkinter`, `json`, `os`, `struct`, `zlib`, `zipfile`. No pip packages, ever. **Windows-only** (`os.startfile`).

| File | Purpose |
|---|---|
| `app.py` (~2070 lines) | The whole app: persistence, settings, icon engine, five tabs, dialogs |
| `backup.py` (~245 lines) | Export/import archive format: manifest, icon collection, restore. **Never imports `app.py`** — the caller injects everything |
| `omnihub.bat` | Launcher: activates/creates `venv/`, installs `requirements.txt`, `pause` only on failure |
| `settings.json` | `{"data_folder": ...}`, **next to `app.py`**, git-**ignored**; absent/corrupt → default `data/` |
| `apps.json` / `folders.json` | Tab data, in the data folder |

Mostly `app.py` top to bottom, plus standalone `backup.py`; per-part detail in `docs/architecture.md`:

1. **Persistence** — `load_settings()`/`save_settings()` ↔ `settings.json`; `set_data_folder()` repoints the data-file globals and creates missing ones (**never overwrites, never makes the folder**); `same_path()` compares normalized paths.
2. **Icon engine** — hand-parsed `.ico` → `PhotoImage`, alpha flattened onto a caller-supplied background. `resolve_icon_path(app_path)` is the **only** place the twin-then-`favicon.ico` rule lives (grid renderer and backups both use it).
3. **`MainApp`** — `ttk.Notebook`, five tabs, fixed `geometry("800x520")` (Tools needs the width); `_reload_tabs()` re-runs `reload()` on data-folder change.
4. **Folder Launcher** — `ttk.Treeview` categories → entries; every action routes through `_locate(item_id)`; `_populate_menu` rebuilds the right-click menu per row.
5. **App Launcher** — scrollable `tk.Canvas` icon grid; click selects, drag reorders, double-click launches; `PhotoImage`s cached in `self._images` (cleared on `reload()`).
6. **Tools** — panels stacked in `self.panels`; `self._tool_row` places the spreadsheet (left) and the reverser (right); copy buttons share `_make_copy_button` / `_copy_value` / `_draw_copy_icon` / `_bind_tooltip`.
7. **Settings** — **Browse…** → `set_data_folder()` → `on_change()`; **Export data…** / **Import data…** hand the whole archive to `backup.py` (format, safety rules and dialog flow in `docs/architecture.md`).
8. **About** — `AboutTab`, two centered labels: `f"{APP_NAME} v{VERSION}"` (bold) + `f"updated {LAST_UPDATED}"`.

**Startup (`main()`):** root stays `withdraw()`n until the data folder resolves — the default is bootstrapped with `os.makedirs`, a missing configured folder prompts for an **existing** one (cancel → default) and is never recreated.

**Data flow:** load settings → set data folder → load JSON → build UI → refresh. Every mutation = mutate → save → rebuild (no undo, no event bus).

## Status & Constraints

- **Current status:** feature-complete; see **Latest Session Delta** for what's uncommitted.
- **Known gaps:** folder paths aren't validated at load time — a deleted folder surfaces only when opened. Long paths clip visually in the reverser's output box; copying still yields the full value.

## Decisions & Gotchas

- **Destructive actions confirm** via `messagebox.askyesno(APP_NAME, ...)`.
- **Dialog pattern:** `tk.Toplevel` + `_safe_grab()` + focus, cancel returns `None`; mutation helpers return a success flag and the caller persists/refreshes.
- **Tk/Python gotchas** (Treeview quirks, `event_generate` reaching only **mapped** widgets, `Menu.index("end")` being the last index, …): `docs/architecture.md`.
- `APP_NAME`/`VERSION`/`LAST_UPDATED` (app.py:31-33) are the single source of truth; bump `LAST_UPDATED` with `VERSION`, and `README.md`'s H1 with it.
- **venv is a local artifact** (git-ignored): recreation recipe in `docs/architecture.md`; never copy from another project.

## Latest Session Delta

Uncommitted since HEAD `de2136c`; checks for both features in `docs/testing.md`.

- **Backup — `backup.py` plus Settings "Export data…" / "Import data…"** — one dated `.zip`: manifest, both data JSONs, `settings.json` (reference only) and every app icon with its recorded path. Import writes only where the target folder exists, skips identical icons, refuses path tricks, and reports skips.
- **Folder Launcher "Copy to clipboard" context item** (`copy_path`) — copies the selected entry's path; category rows and no selection do nothing; confirms in the status line rather than a dialog.
- Version → **0.7.9.0** with `LAST_UPDATED = "2026-11-17"`; README H1 and About examples bumped in the same change.

## Immediate Next Actions

1. Optionally validate folder entries at load time in `load_store()` (flag/drop missing paths) — `app.py`.
2. Add Tools panels: stack under `self.panels`, or extend `self._tool_row` if it fits.
