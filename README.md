# Version 1.0.1.8

# OmniHub

A tabbed Python desktop app with one tab per tool.

## Tabs

### Folder Launcher
Keep track of your frequently used folders — organized by category — and open them with Windows Explorer.

- **Categories** — each folder lives under a category, so related folders stay grouped (e.g. *Work*, *Personal*, *Projects*). Categories are always listed in alphabetical order and start expanded.
- **Add folder…** — pick a folder via a dialog, then choose its category from a dropdown (or create a new one).
- **Manage categories…** — a dedicated dialog for full category management:
  - **New…** — create an empty category
  - **Rename…** — rename the selected category
  - **Delete** — delete a category; if it has folders, choose where they go (another category, *Uncategorized*, or delete them)
- **Double-click** any folder to open it in Windows Explorer.
- **Right-click** for quick actions, depending on what you click:
  - Folder entries: Open in Explorer / Change category… / Remove entry
  - Categories: Rename category… / Delete category
- Your list is persisted automatically in `folders.json` (in the data folder — see Settings), so it survives restarts.
- Old flat-format `folders.json` files are migrated automatically into an *Uncategorized* category.

### App Launcher
Shortcuts to frequently used app files, laid out as a grid of icons like an Android home screen: icon on top, label below.

- **Add app…** — browse for an app file (`*.exe`, `*.bat`, `*.cmd`, `*.lnk`, `*.html`, or any file); it's added to the grid and persisted in `apps.json`. HTML files open in your default browser when launched.
- **Click** an icon to select it; **double-click** to launch it.
- **Drag** an icon over another to reorder the grid — the new order is saved automatically.
- **Right-click** for quick actions: Open / Rename… / Remove (asking for confirmation).
- **Icons** — if a `.ico` file with the same name as the app file sits next to it (e.g. `app-name.ico` next to `app-name.bat`), it's used as the icon; otherwise a `favicon.ico` in the same folder is used as a fallback (e.g. one shared `favicon.ico` for a whole folder of apps); otherwise a generic folder icon is shown.

#### Creating icons

Save a `.ico` file with the same base name next to the app file (e.g. `app-name.ico` beside `app-name.bat`). If an app has no same-name icon, a `favicon.ico` placed in the same folder is used instead — handy when you want one shared icon for every app in a folder.

- **Size** — 48×48 is ideal: it matches the display size exactly, so no scaling happens. Other sizes also work (the app scales to 48×48), and multi-size `.ico` files automatically use the entry closest to 48px.
- **Format** — both classic 32-bit RGBA icons and modern PNG-compressed icons (what most tools produce today) are supported. Only decodable entries are read; anything else falls back to the generic folder icon.

**Designing in Photoshop**

1. Set *Image → Mode* to **8 Bits/Channel** (not 16-bit, not Indexed Color).
2. Keep a **transparent background** — don't flatten onto an opaque layer; that drops the alpha channel.
3. Photoshop can't save `.ico` directly: *File → Save As → PNG*, then convert it:

```
magick icon.png icon.ico
```

Or open the PNG in GIMP and use *File → Export As* with the `.ico` format.

### Tools
Small, self-contained utility tools, added one at a time.

- **KB → Bytes** — enter a number of kilobytes and get the byte count instantly. Type a value and the result updates live (value × 1024); click the copy icon to the right of the result to copy it to the clipboard.
- **Mini Simple Spreadsheet** — a small 3-column × 6-row grid of equal-size cells with a slim 2px gap between rows and columns. Type numbers into the top five rows (digits, an optional leading `-` for negatives, and at most one decimal point); the sixth row shows each column's total live, in bold, followed by a **fourth total box** (pale yellow `#f9fcb2`) that adds the three column totals together and updates live as you type. Total cells can't be edited — clicking one simply **selects** it (light blue; click again to deselect, or click another total to move the selection), and pressing **Ctrl+C** copies the selected total to the clipboard, **including the grand total**. A deselected box returns to its own color: gray for the three column sums, pale yellow for the grand total. A **Clear all** button at the top-right of the spreadsheet empties every editable cell.

### Settings
Choose where your data is stored.

- **Data folder** — `apps.json` and `folders.json` live here. Pick a folder with **Browse…**; the choice is remembered in `settings.json`. If either data file doesn't exist in the folder, it's created automatically (existing files are never overwritten).
- The default data folder is the `data` subdirectory next to the app.
- If the configured data folder no longer exists at startup, you're prompted to pick an existing one; cancelling reverts to the default (`data` subdirectory next to the app). A stale folder is never recreated silently.

## Requirements

- Python 3.x (uses only the standard library — `tkinter`, `json`, `os`, `struct`, `zlib`)
- Windows (`os.startfile` opens folders with Explorer)
- A virtual environment is provided in `venv/`; no system-wide packages are installed.

## Run

```
venv\Scripts\python.exe app.py
```

Or just double-click **omnihub.bat**. It uses the bundled `venv/` automatically; if that folder is missing it creates one (`python -m venv`), upgrades pip, installs `requirements.txt`, then launches. It only keeps the console window open if the app fails to start.


