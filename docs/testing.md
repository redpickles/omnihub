# Headless Verification (Tools tab)

Recipe for checking Tk widgets without opening a visible window, plus what the
current checks cover. Stdlib only; run from the project root.

## Environment

- Verified: Python 3.13.15, Tcl/Tk 8.6.15, Windows.
- Syntax check first: `python -m py_compile app.py`.

## Build a tab in isolation

```python
import sys, tkinter as tk
from tkinter import ttk
sys.path.insert(0, r"D:\_Apps\omnihub")
import app as appmod

root = tk.Tk()
root.withdraw()                      # never shows a window
parent = ttk.Frame(root)             # stands in for the notebook tab
tab = appmod.ToolsTab(parent)
root.update_idletasks()
root.update()                        # needed before geometry asserts
```

Notes:

- Importing `app.py` is safe: `main()` runs only under `__main__`.
- With `withdraw()`, the root's own size reads 1×1, but fixed `pack_propagate(False)`
  cells still reported their real pixel size after `update()` in this project's
  runs (96×26 with exact 2px gaps), so grid geometry asserts worked directly.
  `deiconify()` is only needed when you must measure layout-dependent, non-fixed sizes.
- Set cell values through the Python `StringVar` handles (`tab._spread_vars[i].set(...)`),
  then call `update_idletasks()` before reading derived values.

## Covered by the current run (path box click selects all)

- A `<Button-1>` binding exists on `path_entry` (read back with `entry.bind("<Button-1>")`); the KB `bytes_entry` has none.
- With focus on another widget and a path in the box, a synthesized click (`<Button-1>` + `<ButtonRelease-1>`, `-x`/`-y` inside the box) leaves `selection_present()` true, `selection_get()` equal to the whole path, and `focus_get()` on the entry. The path and the converted output are unchanged by the click.
- Clicking **near the start** and **near the end** of the box both select everything (no caret placement).
- Follow-up input replaces the whole path: `<KeyPress-X>` → `X`; `<<Paste>>` with `D:/…` on the clipboard → that path, and the output flipped back; `<KeyPress-BackSpace>` → empty, and the output went empty too.
- Clicking an **empty** box raises nothing and leaves no selection; output stays empty.
- Regression: KB `2` → `2048`; spreadsheet column sum `1.5 + 3` → `4.5`.
- Visually confirmed by window screenshot: the click paints the blue selection on the path.

### Follow-up run (caret visibility fix)

- Clicking an **empty** box now focuses the entry (`focus_get() is path_entry`) and leaves no selection, with `index("insert") == 0`; window screenshot shows the caret bar in the empty box. Before the fix, `focus_get()` was **not** the entry after an empty click — an unfocused Entry draws no caret, which is what "the cursor doesn't show" was.
- Clicking a box **with** text: focus stays on the entry, selection covers the whole path, output converts (`D:\a\b\c` → `D:/a/b/c`); the screenshot shows the selection band and **no caret** — Tk draws no caret while text is selected.
- Isolated Tk probes (`probe_focus2.py`): click alone → focus on the entry, caret at the click index, no selection; `selection_range()` without focus → focus leaves the entry; `focus_set()` then `selection_range()` → focus stays.
- The 24 checks in `check_select_all.py` all pass after the handler stopped returning `break`.

Caveat: caret **visibility** can only be judged from a screenshot, and the caret blinks (~530 ms), so a single shot may catch the off phase — the empty-box shot caught it, a later text-without-selection shot did not and was not treated as evidence either way.

Click-synthesis notes: `event_generate` on an **unmapped** widget does nothing — these checks need `deiconify()` + `update()` first (that also corrected the old `docs/architecture.md` claim that `<Button-1>` can't be synthesized; a bare `<Key>`/`<KeyPress>` **without** a keysym is still a no-op, so key presses are synthesized as `<KeyPress-X>`).

## Covered in an earlier run (Slash Reverser, + spreadsheet/KB regression)

- Conversion both ways: `D:\Games\MUGEN\Ikemen_GO-v0.99.0-16x9` → `D:/Games/MUGEN/Ikemen_GO-v0.99.0-16x9` and back; `\\server\share\dir` → `//server/share/dir`; mixed `C:\a/b\c` → `C:/a\b/c`; text with no separators and `""` are unchanged. A 68-char path converts exactly.
- Widgets: output is a `tk.Label`, input a `tk.Entry`; the reverser's copy canvas is a **different** canvas from the KB tool's (`_slash_copy_canvas is not _copy_canvas`) and has a real `<Button-1>` binding.
- Copy: `_copy_value(canvas, getter)` puts `D:/Games/MUGEN/Ikemen_GO-v0.99.0-16x9` on the clipboard; an **empty** output leaves a `SENTINEL` clipboard value untouched. The KB tool still shows `2048` for `2` and still copies through the same helper.
- Geometry (window-relative, `WIN_W = 800`): output box x=446 vs grid right x=320 (to the right of the grid), y=178 below the KB tool, right edge 740 < 800 (inside the window), width 294px ≥ the 234px the 37-char sample needs in Segoe UI 9. Setting a 68-char path leaves `winfo_width()` at 800 — it cannot grow the window.
- Spreadsheet regression: sums `12`/`2.25`/`7` → grand `21.25`; Clear all → four `0`s; Ctrl+C on the selected grand box copies `0`.

Geometry notes for this run: positions were compared **relative to the toplevel** (`winfo_rootx()` minus the toplevel's `winfo_rootx()`) — raw `winfo_rootx()` is a *screen* coordinate and comparing it against the window width gave a false failure. `root.deiconify()` + `update()` were required before any `winfo_width()` read (a `withdraw()`n root reports 1×1 for panels too). The sample-width assertion uses `tkinter.font.Font.measure`, not a hand-picked constant.

## Covered in an earlier run (fourth total box, selectable + copyable)

- The grand total is the 4th total cell: `len(_spread_sum_vars) == len(_spread_sum_labels)
  == len(_spread_sum_bg) == 4`, `_spread_sum_vars[3] is _spread_grand_var`,
  `_spread_sum_labels[3] is _spread_grand_label`, `_spread_sum_bg == ["#f5f5f5"]*3 + ["#f9fcb2"]`,
  `len(_spread_boxes) == 19`.
- Geometry: grand box `96×26`, `x=294` vs `sum box[2].x == 196` → exactly the 2px gap, same `y`;
  default background `#f9fcb2`, font `{Segoe UI} 10 bold`, and a real `<Button-1>` binding.
- Math: inputs `1.5/-2/(empty)`, `3/0.25/-`, blank row, `10/(empty)/7`, `-2.5/4/0`
  → totals `12`, `2.25`, `7`, grand `21.25` (float column totals added, formatted once).
- Selecting the grand box paints it `#b6d7f0` and moves the selection away from a
  column sum, which is restored to `#f5f5f5`; deselecting the grand box returns it to
  `#f9fcb2` (not the shared gray).
- Copy: with the grand box selected, the Ctrl+C handler (`event.char == "\x03"`) puts
  `21.25` on the clipboard; after Clear all it puts `0`. A normal keystroke (`char == "a"`)
  leaves the clipboard untouched.
- The KB → Bytes panel is untouched: `2` still shows `2048`.

Note: the Ctrl+C assertion calls `_copy_selected_sum` with a faithful fake event
object (`char = "\x03"`), because `event_generate` cannot synthesize real control-character
chars — see the keyboard gotchas in `docs/architecture.md`.

## Covered in the earlier session (same tool, different run)

Sum math including negatives and `-2.5`; uniform box/gap pixels; `entry == label`
widths; signed-number validator edge cases; selection toggle/move; the Ctrl+C
copy guard (`event.char == "\x03"`) exercised with faithful synthetic events;
Clear all. Ctrl+C key-event facts were confirmed against bpo-46052 and Tk debug
(see `docs/architecture.md`).
