# AI Project State

Last updated: 2026-11-09 · **v0.7.8.8** · single-window Tk desktop app · project root `D:\_Apps\omnihub`.
Deep detail (schemas, icon engine, dialogs, tab internals, Tk gotchas, venv) lives in `docs/architecture.md`; the headless-testing recipe and what each run covered in `docs/testing.md`.

## Project Overview

One Tk window, five tabs, all persisting to JSON in a configurable data folder across restarts:

- **Folder Launcher** — frequently used folders by category, opened via Windows Explorer.
- **App Launcher** — app-file shortcuts (`.exe`/`.bat`/`.cmd`/`.lnk`/`.html`) as an Android-home icon grid; double-click launches, drag reorders.
- **Tools** — panel utilities: **KB → Bytes** (× 1024, live, copy icon), **Mini Simple Spreadsheet** (click-selectable, Ctrl+C-copyable totals, "Clear all"), **Slash Reverser** (path in, every `/` ⇄ `\` swapped live, click selects all, copy icon beside the output). The spreadsheet and the reverser sit **side by side** in one shared row.
- **Settings** — choose the data folder.
- **About** — app name, version, and last updated date (e.g. `OmniHub v0.7.8.8` / `updated 2026-11-09`).

## Stack & Architecture

- **Python 3.13.15 + Tcl/Tk 8.6.15. Stdlib only** — `tkinter`, `json`, `os`, `struct`, `zlib`. No pip packages, ever. **Windows-only** (`os.startfile`).

| File | Purpose |
|---|---|
| `app.py` (~1900 lines) | The whole app: persistence, settings, icon engine, five tabs, dialogs |
| `omnihub.bat` | Launcher: activates/creates `venv/`, installs `requirements.txt`, `pause` only on failure |
| `settings.json` | `{"data_folder": ...}`, **next to `app.py`**, git-**ignored**; absent/corrupt → default `data/` |
| `apps.json` / `folders.json` | Tab data, in the data folder |
| `.gitignore` | Also ignores `venv/`, `__pycache__/`, `data/`, `settings.json` |

Everything in `app.py`, top to bottom; per-part detail in `docs/architecture.md`:

1. **Persistence** — `load_settings()`/`save_settings()` ↔ `settings.json`; `set_data_folder()` repoints the data-file globals and creates missing files (**never overwrites, never makes the folder**).
2. **Icon engine** — hand-parsed `.ico` → `PhotoImage`; alpha flattened onto a caller-supplied background RGB.
3. **`MainApp`** — `ttk.Notebook`, five tabs, fixed `geometry("800x520")` (Tools needs 800 wide for the side-by-side row); `_reload_tabs()` re-runs `reload()` on data-folder change.
4. **Folder Launcher** — `ttk.Treeview` categories → entries; every action routes through `_locate(item_id)`.
5. **App Launcher** — scrollable `tk.Canvas` icon grid; click selects, drag reorders, double-click launches; icons cached in `self._images`.
6. **Tools** — `ToolsTab`: panels stacked in `self.panels`; `self._tool_row` holds the spreadsheet (left) and the Slash Reverser (right). Shared helpers `_make_copy_button` / `_copy_value` / `_draw_copy_icon(canvas, accent)` / `_bind_tooltip`.
7. **Settings** — data-folder path + **Browse…** → `set_data_folder()` → `on_change()` reloads data tabs.
8. **About** — `AboutTab`, two centered labels: `f"{APP_NAME} v{VERSION}"` (bold) + `f"updated {LAST_UPDATED}"`.

**Startup (`main()`):** root stays `withdraw()`n until the data folder resolves — missing default bootstrapped with `os.makedirs`; missing configured folder prompts for an **existing** one (cancel → default); a stale folder is never recreated.

**Data flow:** load settings → set data folder → load JSON → build UI → refresh; every mutation = mutate → save → rebuild (no undo, no event bus).

## Status & Constraints

- **Current status:** feature-complete. HEAD `96dd807`; everything under **Latest Session Delta** is uncommitted.
- **Known gaps:** folder entries aren't validated at load time — a missing folder surfaces only when you open it. Paths longer than the reverser's output box clip visually; copy still yields the full value.

## Decisions & Gotchas

- **Destructive actions confirm** via `messagebox.askyesno(APP_NAME, ...)`.
- **Dialog pattern:** `tk.Toplevel` + `_safe_grab()` + focus, cancel = `None`; mutation helpers return a success flag, the caller persists/refreshes (see `docs/architecture.md`).
- **Tk/Python gotchas** (Treeview quirks, headless sizing and window-relative geometry asserts, Ctrl+C event names, `event_generate` only reaching **mapped** widgets, `selection_range()` on an unfocused entry giving focus up, `maketrans` positional pairing, `tk.Entry`'s 60-char default widening the window): `docs/architecture.md`, `docs/testing.md`.
- `APP_NAME`/`VERSION`/`LAST_UPDATED` (app.py:25-27) are the single source of truth; the About tab renders the latter two (bump `LAST_UPDATED` with `VERSION`). `README.md`'s H1 duplicates `VERSION` and must be bumped in the same change.
- **venv is a local artifact** (git-ignored): recreation recipe in `docs/architecture.md`; never copy from another project.

## Latest Session Delta

- **Version reset → 0.7.8.8** as SSOT: new `LAST_UPDATED = "2026-11-09"` constant beside `VERSION` (app.py top); README H1 bumped in the same change.
- **About tab** (5th, after Settings): `AboutTab` class (just before `MainApp`), two centered `ttk.Label`s in a `pack(expand=True)` frame — `f"{APP_NAME} v{VERSION}"` (Segoe UI 16 bold) and `f"updated {LAST_UPDATED}"`. Headless-checked (py_compile, tab order, label texts).
- Earlier, still uncommitted: **Slash Reverser** tool (`_SLASH_TRANS`, per-keystroke, copy icon), `self._tool_row` spreadsheet-left/reverser-right, window **700→800** wide, KB copy button shared via `_make_copy_button`/`_copy_value`/`_draw_copy_icon`. Gotcha: `_select_all_on_click` must **not** return `break` (Tk's own click handling provides focus + caret); `_select_all_path` needs `focus_set()` before `selection_range()`.

## Immediate Next Actions

1. Optionally validate folder entries at load time in `load_store()` (flag/drop missing paths) — `app.py`.
2. Add Tools panels: stack under `self.panels`, or extend `self._tool_row` if it fits.
