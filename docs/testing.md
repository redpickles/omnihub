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

## Covered by the current run (fourth total box, selectable + copyable)

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
