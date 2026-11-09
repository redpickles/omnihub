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

- `name` is freely renamable; `path` drives both launch and icon lookup, which looks for a **same-basename `.ico` twin** in the same directory (`foo.bat` ↔ `foo.ico`), and if that's absent falls back to a **`favicon.ico`** in the same directory (`_icon_for` in `app.py`), else the generic folder icon.

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

## Mini Simple Spreadsheet Internals (Tools tab)

- One `ttk.Frame table` holds 19 fixed-size `tk.Frame` boxes placed on the ttk grid: rows 0–4 × cols 0–2 are editable `tk.Entry` cells, row `_SPREAD_ROWS` (the sixth row) holds the three column-sum `tk.Label`s plus the **grand-total** label at column `_SPREAD_COLS`. All four totals live in the same lists — `_spread_sum_vars` / `_spread_sum_labels` / `_spread_sum_bg`, index `_SPREAD_COLS` being the grand total (aliased by `self._spread_grand_var` / `_spread_grand_label`) — so selection and Ctrl+C treat it exactly like a column sum. `pack_propagate(False)` keeps every box exactly `_SPREAD_CELL_W` × `_SPREAD_CELL_H` (96×26), so input and total boxes match; `padx/pady=(0, 2)` leaves exactly a 2px gap between rows **and** columns.
- Colors: `_SPREAD_BG` `#f5f5f5` (unselected column sums, matches the KB tool's result), `_SPREAD_SELECTED_BG` `#b6d7f0` (any total while selected), `_SPREAD_GRAND_BG` `#f9fcb2` (grand total's **default**). `_spread_sum_bg[cell]` remembers each cell's own default, so deselecting restores `#f9fcb2` on the grand total instead of the shared gray.
- Validation `_validate_signed_number`: empty, optional leading `-`, digits, at most one `.`. A lone `-` is accepted so negatives can start mid-typing; such cells are skipped by the sums until they parse.
- Sums: only the 15 input StringVars carry a `write` trace → `_update_spread_sums` recomputes the three column totals (unparsable cells skipped) and the grand total, writing `_spread_sum_vars` / `_spread_grand_var` with `_format_number` (whole numbers drop `.0`, otherwise `%g`). Sum vars carry **no** trace, so the callback can't recurse. The grand total adds the three **float** column totals and formats once — rounding in the display strings can never make it disagree with the sum boxes.
- Selection: all four total labels bind `<Button-1>` → `_select_spread_sum(cell)` with `cell` 0–3 tracked in `self._spread_selected`; clicking the selected cell deselects, clicking another moves.
- Copy: `_copy_selected_sum` (bound per the keyboard gotchas above) copies `self._spread_sum_vars[self._spread_selected]`, which resolves index `_SPREAD_COLS` to the grand total.
- `_clear_spreadsheet` only blanks the 15 input vars; the write traces reset the sums and the grand total to 0.

## Slash Reverser + Copy-Button Helpers (Tools tab)

- `_add_slash_reverser_tool` builds a `Slash Reverser` `ttk.LabelFrame`. `_path_var` carries a `write` trace → `_update_reversed_path`, which sets `_slash_var` via `str.translate(self._SLASH_TRANS)`. `_SLASH_TRANS = str.maketrans("/\\", "\\/")` — **both** strings must contain both separators: two-argument `maketrans` pairs them *positionally*, so `maketrans("/", "\\")` only maps `/` → `\` and leaves backslashes untouched (that was the first-version bug). Per-character translate means mixed-separator input flips each separator individually and never touches `:`, `.` or `_`.
- Layout: the spreadsheet panel and the reverser share `self._tool_row` (a `ttk.Frame` in `self.panels`). The spreadsheet packs `side="left", fill="y"` at its natural ~416px, the reverser packs `side="left", fill="both", expand=True, padx=(10, 0)` and takes the rest. `MainApp` sizes the window to **800×520** (was 700×520): at 700 the reverser's output box is only 194px and clips a typical 37-char path (needs ~234px in Segoe UI 9); 800 gives it 294px.
- **Click-to-select-all:** `path_entry.bind("<Button-1>", self._select_all_on_click)` so a click highlights the whole path and the next keystroke or paste replaces it. The handler **must not return `break`**: Tk's own click handling is what gives the box the focus, and an unfocused `tk.Entry` draws no caret and no highlight — a `break` here made the empty box look dead (caret never appearing). The select-all is deferred one event-loop step so it lands after that handling.
- **`selection_range()` focus gotcha (measured):** calling `entry.selection_range(0, "end")` on an entry that does **not** own the focus makes the entry *give up* focus — it jumps back to the previously focused widget. So `_select_all_path` does `focus_set()` **first**, then selects. It skips the select when the box is empty: nothing to replace, and leaving the selection alone keeps the caret visible while typing.
- Tk draws **no caret while text is selected**, so after clicking a filled box there is no caret by design — it reappears the moment the selection goes (typing, arrows, Escape).
- Because the click is no longer swallowed, drag-selecting a range inside the box works again.
- Both the entry and the output label are created with `width=1`. A `tk.Entry` defaults to **60 characters**, which would request more width than the space beside the spreadsheet and silently grow the window; `width=1` keeps the *request* tiny while `fill="x"`/`fill="x", expand=True` stretches the widget to whatever the row offers. Long text is clipped at the panel edge — the copy icon still hands over the full value.
- `_make_copy_button(parent, get_value, padx=…)` is the shared 30×30 button (24×24 `tk.Canvas` glyph, hand cursor, tooltip, click-to-copy) used by both tools; it returns the canvas. `_copy_value(canvas, get_value)` copies `get_value().strip()` (empty = no-op, no clipboard write) and flashes the glyph via `_draw_copy_icon(canvas, accent=True)`, redrawn after 350ms. `_draw_copy_icon` now takes the canvas it paints — it no longer touches a single shared `self._copy_canvas`, so each tool's icon flashes independently.

## Tk 8.6.15 Gotchas

- Treeview items insert **closed** by default — pass `open=True` or children stay hidden.
- `tree.parent()` returns `''`, not `None`, for root items.
- `tree.selection()` returns **string item IDs**, not indices — use `tree.index(id)`.
- `root.iconbitmap()` may raise `TclError` on an unsupported `.ico`; it is wrapped in `try/except` in `main()`.
- Headless testing: a `withdraw()`n root reports winfo size 1×1 — call `deiconify()` + `update()` before geometry asserts (`pack_propagate(False)` cells then measure their real pixel size).
- Keyboard shortcuts on Windows: a plain Ctrl+letter sends the lowercase-derived virtual event (`<Control-c>`; uppercase `<Control-C>` only with Shift) — bind both. Non-Latin keyboard layouts (e.g. Cyrillic) match **neither** name (bpo-46052), but the `<Key>` event always fires and `event.char` is the control character (code 3 for Ctrl+C) — a `<Key>` binding guarded on `event.char == "\x03"` is layout-proof.
- `event_generate` fires the bindings for the virtual-event name you pass, with caveats measured in this project: the target must be **mapped** (on a `withdraw()`n root, a synthesized `<KeyPress-X>` never reached the Entry), and bare `<Key>`/`<KeyPress>` without a keysym does nothing — use `<KeyPress-X>`. Mapped widgets **do** accept synthesized `<Button-1>`/`<ButtonRelease-1>` (`-x`, `-y`, `-button 1`) and `<<Paste>>`. It still cannot produce a real control-character `event.char`, so the Ctrl+C guard is exercised with a faithful fake event object.

## venv Notes

- The venv is a local artifact (git-ignored) and needs no packages: `requirements.txt` is intentionally empty because the app is stdlib-only.
- If recreating, run `python -m venv --clear venv` from the project root. A venv copied from another project keeps that project's path in `activate.bat`/`pyvenv.cfg` and silently activates the wrong interpreter.
- Verified environment: Python 3.13.15, Tk 8.6.15.
