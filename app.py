"""OmniHub — a tabbed desktop app with one tab per tool.

Tabs:
  * Folder Launcher — keep track of frequently used folders, organized by category.
    Double-click a folder to open it with Windows Explorer; right-click for extra
    actions (change category, remove entry, rename/delete categories).
    Categories are always listed in alphabetical order.
    The list is persisted to folders.json next to this script.
  * App Launcher — shortcuts to frequently used app files, with icons.
    Each app shows an icon: a .ico file with the same name as the app file
    (e.g. app-name.ico next to app-name.bat) if one exists, otherwise a favicon.ico
    in the same folder if that exists, otherwise a generic folder icon. Double-click to
    launch the app.
  * Settings — choose the data folder where apps.json and folders.json are
    stored; both files are created automatically if they don't exist.
"""

import json
import os
import struct
import tkinter as tk
import zlib
from tkinter import filedialog, messagebox, simpledialog, ttk

APP_NAME = "OmniHub"
VERSION = "1.0.1.8"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "folders.json")


def load_store():
    """Load the category store. Returns {"categories": [{"name", "entries": [...]}]}.

    Migrates the legacy flat format ({"folders": [...]}) into a single
    "Uncategorized" category.
    """
    if not os.path.exists(CONFIG_FILE):
        return {"categories": []}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"categories": []}

    if "folders" in data and "categories" not in data:
        entries = [e for e in data["folders"] if isinstance(e, dict) and e.get("path")]
        data = {
            "categories": [{"name": "Uncategorized", "entries": entries}] if entries else []
        }

    categories = data.get("categories", [])
    cleaned = []
    for cat in categories:
        if not isinstance(cat, dict) or not cat.get("name"):
            continue
        entries = [e for e in cat.get("entries", []) if isinstance(e, dict) and e.get("path")]
        cleaned.append({"name": cat["name"], "entries": entries})
    return {"categories": cleaned}


def _atomic_write(path, text):
    """Write `text` to `path` atomically (temp file + rename).

    A crash mid-write can never leave a half-written (corrupt) JSON file
    behind, because the target is only replaced once fully written.
    """
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def save_store(store):
    """Persist the category store to the config file."""
    _atomic_write(CONFIG_FILE, json.dumps(store, ensure_ascii=False, indent=2))


def sorted_categories(store):
    """Return the store's categories in alphabetical order (case-insensitive)."""
    return sorted(store["categories"], key=lambda c: c["name"].lower())


APPS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps.json")


def load_apps():
    """Load the app shortcuts from apps.json. Returns a list of {name, path}."""
    if not os.path.exists(APPS_FILE):
        return []
    try:
        with open(APPS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        apps = data.get("apps", [])
        return [a for a in apps if isinstance(a, dict) and a.get("path")]
    except (json.JSONDecodeError, OSError):
        return []


def save_apps(apps):
    """Persist the app shortcuts to apps.json."""
    _atomic_write(APPS_FILE, json.dumps({"apps": apps}, ensure_ascii=False, indent=2))


SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


def default_data_folder():
    """The default data folder: the `data` subdirectory next to this script."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_settings():
    """Load app settings. Returns {"data_folder": <str>}.

    The data folder defaults to the `data` subdirectory next to this script,
    which is where the data files live out of the box.
    """
    default = default_data_folder()
    if not os.path.exists(SETTINGS_FILE):
        return {"data_folder": default}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"data_folder": default}
    folder = data.get("data_folder")
    if isinstance(folder, str) and folder.strip():
        return {"data_folder": folder}
    return {"data_folder": default}


def save_settings(settings):
    """Persist app settings to settings.json."""
    _atomic_write(SETTINGS_FILE, json.dumps(settings, ensure_ascii=False, indent=2))


def set_data_folder(folder):
    """Point CONFIG_FILE/APPS_FILE at `folder`, creating the data files if
    they don't exist there yet.

    `folder` must already exist; callers guarantee this (the startup prompt
    and the Settings tab both use a directory picker, and the default is the
    app's own directory). A missing folder is never created silently.
    """
    global CONFIG_FILE, APPS_FILE
    CONFIG_FILE = os.path.join(folder, "folders.json")
    APPS_FILE = os.path.join(folder, "apps.json")
    if not os.path.exists(CONFIG_FILE):
        save_store({"categories": []})
    if not os.path.exists(APPS_FILE):
        save_apps([])


# ---------------------------------------------------------------------------
# Icon loading (stdlib only)
#
# Tk's PhotoImage cannot display .ico files, so we parse the ICO container
# ourselves and build a PhotoImage from the raw 32-bit pixels it contains.
# The generic folder fallback is drawn pixel by pixel.

def _parse_ico(data):
    """Return (width, height, bitcount, blob) for each image in an ICO file."""
    _, _, count = struct.unpack_from("<HHH", data, 0)
    entries = []
    for i in range(count):
        w, h, _colors, _reserved, _planes, bitcount, size, offset = (
            struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
        )
        entries.append((w or 256, h or 256, bitcount, data[offset:offset + size]))
    return entries


def _dib_to_photoimage(blob, size, background=(255, 255, 255)):
    """Build a PhotoImage from a 32-bit DIB (BITMAPINFOHEADER + BGRA pixels).

    Icon DIBs store rows bottom-up; this also scales to the requested size
    with nearest-neighbor sampling. PhotoImage has no alpha channel, so
    transparent pixels are flattened onto `background`.
    """
    if len(blob) < 40:
        return None
    w, _h_total, _planes, bitcount, compression = struct.unpack_from("<iiHHI", blob, 4)
    if w <= 0 or bitcount != 32 or compression != 0:
        return None
    data = blob[40:]
    mask_row = (w + 7) // 8
    if mask_row % 2:
        mask_row += 1
    stride = w * 4                      # row width in bytes
    if len(data) % (stride + mask_row) == 0:  # standard icon DIB (color rows + zero mask)
        h, stride = len(data) // (stride + mask_row), stride + mask_row
    elif len(data) % stride == 0:       # no mask stored
        h = len(data) // stride
    else:
        return None
    img = tk.PhotoImage(width=size, height=size)
    hex_cache = {}  # (r, g, b) -> "#rrggbb"; icons reuse few colors
    for y in range(size):
        src_y = h - 1 - int(y * h / size)  # DIB rows are bottom-up
        for x in range(size):
            src_x = int(x * w / size)
            o = src_y * stride + src_x * 4
            b, g, r, a = data[o], data[o + 1], data[o + 2], data[o + 3]
            if a < 255:  # flatten transparency onto the background color
                br, bg_c, bb = background
                r = (r * a + br * (255 - a)) // 255
                g = (g * a + bg_c * (255 - a)) // 255
                b = (b * a + bb * (255 - a)) // 255
            color = hex_cache.get((r, g, b))
            if color is None:
                color = f"#{r:02x}{g:02x}{b:02x}"
                hex_cache[(r, g, b)] = color
            img.put(color, (x, y))
    return img


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _paeth(a, b, c):
    """PNG Paeth predictor (used to unfilter scanlines)."""
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _decode_png(data):
    """Decode a PNG into (width, height, pixels).

    pixels is a list of rows of (r, g, b, a) tuples. Only the color types
    ICOs actually use are supported: 8/16-bit grayscale, RGB, gray+alpha,
    and RGBA. Returns None on anything it cannot handle.
    """
    if data[:8] != PNG_SIGNATURE:
        return None
    width = height = bitdepth = colortype = None
    idat = b""
    pos = 8
    while pos + 8 <= len(data):
        length, ctype = struct.unpack_from(">I4s", data, pos)
        if ctype == b"IHDR":
            (width, height, bitdepth, colortype, _compression, _filter, interlace) = (
                struct.unpack_from(">IIBBBBB", data, pos + 8)
            )
        elif ctype == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        elif ctype == b"IEND":
            break
        pos += 12 + length
    if width is None or height is None:
        return None
    if interlace != 0:  # Adam7 interlaced scanlines are not supported
        return None
    if bitdepth not in (8, 16) or colortype not in (0, 2, 4, 6):
        return None
    try:
        raw = zlib.decompress(idat)
    except zlib.error:
        return None
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colortype]
    bpp = (bitdepth // 8) * channels
    stride = (width * bitdepth * channels + 7) // 8
    if len(raw) < height * (stride + 1):
        return None
    prev = b"\x00" * stride
    rows = []
    for y in range(height):
        line = raw[y * (stride + 1):(y + 1) * (stride + 1)]
        ftype, cur = line[0], bytearray(line[1:])
        if ftype == 1:  # Sub
            for x in range(bpp, stride):
                cur[x] = (cur[x] + cur[x - bpp]) & 0xFF
        elif ftype == 2:  # Up
            for x in range(stride):
                cur[x] = (cur[x] + prev[x]) & 0xFF
        elif ftype == 3:  # Average
            for x in range(stride):
                left = cur[x - bpp] if x >= bpp else 0
                cur[x] = (cur[x] + (left + prev[x]) // 2) & 0xFF
        elif ftype == 4:  # Paeth
            for x in range(stride):
                left = cur[x - bpp] if x >= bpp else 0
                upleft = prev[x - bpp] if x >= bpp else 0
                cur[x] = (cur[x] + _paeth(left, prev[x], upleft)) & 0xFF
        elif ftype != 0:  # None
            return None
        rows.append(bytes(cur))
        prev = bytes(cur)
    pixels = []
    for row in rows:
        px = []
        for x in range(width):
            if bitdepth == 8:
                s = [row[x * channels + i] for i in range(channels)]
            else:  # 16-bit samples are big-endian; the high byte is enough
                s = [row[x * 2 * channels + 2 * i] for i in range(channels)]
            if colortype == 0:    # grayscale
                r = g = b, a = s[0], 255
            elif colortype == 2:  # RGB
                r, g, b, a = s[0], s[1], s[2], 255
            elif colortype == 4:  # grayscale + alpha
                r = g = b, a = s[0], s[1]
            else:                  # RGBA
                r, g, b, a = s
            px.append((r, g, b, a))
        pixels.append(px)
    return width, height, pixels


def _png_to_photoimage(blob, size, background=(255, 255, 255)):
    """Build a PhotoImage from a PNG-encoded ICO entry.

    PhotoImage has no alpha channel, so transparent pixels are flattened
    onto `background`.
    """
    decoded = _decode_png(blob)
    if decoded is None:
        return None
    w, h, pixels = decoded
    br, bg_c, bb = background
    img = tk.PhotoImage(width=size, height=size)
    hex_cache = {}  # (r, g, b) -> "#rrggbb"; icons reuse few colors
    for y in range(size):
        src_y = int(y * h / size)  # nearest-neighbor scaling
        for x in range(size):
            src_x = int(x * w / size)
            r, g, b, a = pixels[src_y][src_x]
            if a < 255:  # flatten transparency onto the background color
                r = (r * a + br * (255 - a)) // 255
                g = (g * a + bg_c * (255 - a)) // 255
                b = (b * a + bb * (255 - a)) // 255
            color = hex_cache.get((r, g, b))
            if color is None:
                color = f"#{r:02x}{g:02x}{b:02x}"
                hex_cache[(r, g, b)] = color
            img.put(color, (x, y))
    return img


def load_ico_image(ico_path, size, background=(255, 255, 255)):
    """Load a .ico file into a tk.PhotoImage. Returns None on failure.

    `background` is the (r, g, b) color transparent pixels are flattened
    onto, since PhotoImage cannot store alpha.
    """
    try:
        with open(ico_path, "rb") as f:
            data = f.read()
        entries = _parse_ico(data)
        if not entries:
            return None
        # Prefer decodable images closest to the requested size. Modern ICOs
        # often store PNG-compressed entries (bitcount 0); classic DIB entries
        # must be 32-bit for us to handle.
        def decodable(e):
            _w, _h, bitcount, blob = e
            return blob[:8] == PNG_SIGNATURE if bitcount == 0 else bitcount == 32

        candidates = [e for e in entries if decodable(e)]
        if not candidates:
            return None
        candidates.sort(key=lambda e: abs(e[0] - size))
        _w, _h, _bitcount, blob = candidates[0]
        if blob[:8] == PNG_SIGNATURE:
            return _png_to_photoimage(blob, size, background)
        return _dib_to_photoimage(blob, size, background)
    except Exception:
        return None


def folder_icon(size=32):
    """A generic folder icon drawn pixel by pixel."""
    img = tk.PhotoImage(width=size, height=size)
    outline, fill, top = "#c08a2d", "#f7c856", "#ffdd85"
    tab = (int(size * 0.1), int(size * 0.13), int(size * 0.5), int(size * 0.32))
    body = (int(size * 0.06), int(size * 0.3), int(size * 0.94), int(size * 0.87))
    for y in range(size):
        for x in range(size):
            color = ""
            if tab[0] <= x < tab[2] and tab[1] <= y < tab[3]:
                color = outline if (x == tab[0] or y == tab[1]) else top
            elif body[0] <= x < body[2] and body[1] <= y < body[3]:
                edge = x == body[0] or x == body[2] - 1 or y == body[3] - 1
                color = outline if edge else fill
            img.put(color, (x, y))
    return img


def _safe_grab(widget):
    """grab_set() that tolerates an unmapped window.

    Tk raises TclError if the grab is requested before the Toplevel has been
    mapped; ignoring that keeps the dialog usable instead of crashing.
    """
    try:
        widget.grab_set()
    except tk.TclError:
        pass


class _DestinationDialog(tk.Toplevel):
    """Ask where the entries of a deleted category should go."""

    DELETE = "__delete__"

    def __init__(self, parent, options, count):
        super().__init__(parent)
        self.title("Move folders to…")
        self.geometry("340x280")
        self.transient(parent)
        self.result = None

        ttk.Label(
            self,
            text=f"The category you're deleting has {count} folder(s).\nWhere should they go?",
            padding=(12, 8, 12, 0),
        ).pack(fill="x", anchor="w")

        frame = ttk.Frame(self, padding=(12, 4))
        frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(frame, exportselection=False)
        for opt in options:
            self.listbox.insert("end", opt)
        self.listbox.insert("end", "(Delete these folders)")
        self.listbox.pack(fill="both", expand=True)

        buttons = ttk.Frame(self, padding=(12, 8))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="OK", command=self._ok).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")

        self.listbox.selection_set(0)
        _safe_grab(self)
        self.focus_set()

    def _ok(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == self.listbox.size() - 1:
            self.result = self.DELETE
        else:
            self.result = self.listbox.get(idx)
        self.destroy()

    def wait_for_result(self):
        self.wait_window()
        return self.result


def delete_category_with_migration(parent, store, cat):
    """Ask where a category's entries go, then remove the category.

    Returns True if the deletion went ahead, False if the user cancelled.
    The store is mutated in place; the caller persists and refreshes.
    """
    if cat["entries"]:
        remaining = [c["name"] for c in store["categories"] if c is not cat]
        options = list(remaining)
        if not any(n.lower() == "uncategorized" for n in options):
            options.append("Uncategorized")
        result = _DestinationDialog(parent, options, len(cat["entries"])).wait_for_result()
        if result is None:  # cancelled
            return False
    else:
        if not messagebox.askyesno(APP_NAME, f"Delete category '{cat['name']}'?"):
            return False
        result = _DestinationDialog.DELETE

    store["categories"].remove(cat)
    if result != _DestinationDialog.DELETE:
        target = next(
            (c for c in store["categories"] if c["name"].lower() == result.lower()),
            None,
        )
        if target is None:  # "Uncategorized" was offered but doesn't exist yet
            target = {"name": "Uncategorized", "entries": []}
            store["categories"].append(target)
        for entry in cat["entries"]:
            if not any(e["path"].lower() == entry["path"].lower() for e in target["entries"]):
                target["entries"].append(entry)
    return True


class _CategoryPickerDialog(tk.Toplevel):
    """Let the user pick an existing category, or create a new one."""

    NEW = "(New category…)"

    def __init__(self, parent, categories, default=None):
        super().__init__(parent)
        self.title("Choose a category")
        self.geometry("360x190")
        self.transient(parent)
        self.result = None

        ttk.Label(
            self,
            text="Which category should this folder go in?",
            padding=(12, 8, 12, 4),
        ).pack(fill="x", anchor="w")

        frame = ttk.Frame(self, padding=(12, 0))
        frame.pack(fill="both", expand=True)

        values = [self.NEW] + sorted(categories, key=str.lower)
        self.combo = ttk.Combobox(frame, values=values, state="readonly")
        self.combo.pack(fill="x", pady=(0, 4))
        if default in values:
            self.combo.current(values.index(default))
        else:
            self.combo.current(0)

        self.new_entry = ttk.Entry(frame)
        self.new_entry.pack(fill="x")
        self.new_entry.configure(state="disabled")
        self.combo.bind("<<ComboboxSelected>>", self._on_combo_select)

        buttons = ttk.Frame(self, padding=(12, 8))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="OK", command=self._ok).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")

        self._on_combo_select()  # sync entry state with the initial selection
        _safe_grab(self)
        if self.combo.get() == self.NEW:
            self.new_entry.focus_set()
        else:
            self.focus_set()

    def _on_combo_select(self, event=None):
        if self.combo.get() == self.NEW:
            self.new_entry.configure(state="normal")
            self.new_entry.focus_set()
        else:
            self.new_entry.configure(state="disabled")
            self.new_entry.delete(0, "end")

    def _ok(self):
        choice = self.combo.get()
        if choice == self.NEW:
            name = self.new_entry.get().strip()
            if not name:
                messagebox.showwarning(APP_NAME, "Category name cannot be empty.")
                return
            self.result = name
        else:
            self.result = choice
        self.destroy()

    def wait_for_result(self):
        self.wait_window()
        return self.result


class CategoryManagerDialog(tk.Toplevel):
    """Manage categories: add, rename, and delete (listed alphabetically)."""

    def __init__(self, parent, store, on_change):
        super().__init__(parent)
        self.store = store
        self.on_change = on_change
        self.title("Manage Categories")
        self.geometry("380x420")
        self.transient(parent)

        toolbar = ttk.Frame(self, padding=(8, 8))
        toolbar.pack(fill="x")
        for text, cmd in (
            ("New…", self.add_category),
            ("Rename…", self.rename_category),
            ("Delete", self.delete_category),
        ):
            ttk.Button(toolbar, text=text, command=cmd).pack(side="left", padx=(0, 6))

        frame = ttk.Frame(self, padding=(8, 4))
        frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(frame, exportselection=False)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        bottom = ttk.Frame(self, padding=(8, 8))
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Close", command=self.destroy).pack(side="right")

        self._refresh()

    # ------------------------------------------------------------- helpers

    def _refresh(self):
        self._display = sorted_categories(self.store)
        self.listbox.delete(0, "end")
        for cat in self._display:
            count = len(cat["entries"])
            self.listbox.insert("end", f"{cat['name']}  ({count})")

    def _selected_index(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def _after_change(self):
        save_store(self.store)
        self._refresh()
        self.on_change()

    # ------------------------------------------------------------- actions

    def add_category(self):
        name = simpledialog.askstring("New category", "Category name:", parent=self)
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showwarning(APP_NAME, "Category name cannot be empty.")
            return
        if any(c["name"].lower() == name.lower() for c in self.store["categories"]):
            messagebox.showinfo(APP_NAME, f"A category named '{name}' already exists.")
            return
        self.store["categories"].append({"name": name, "entries": []})
        self._after_change()

    def rename_category(self):
        idx = self._selected_index()
        if idx is None:
            return
        cat = self._display[idx]
        old = cat["name"]
        name = simpledialog.askstring(
            "Rename category", "Category name:", initialvalue=old, parent=self
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showwarning(APP_NAME, "Category name cannot be empty.")
            return
        if any(c["name"].lower() == name.lower() for c in self.store["categories"] if c is not cat):
            messagebox.showinfo(APP_NAME, f"A category named '{name}' already exists.")
            return
        cat["name"] = name
        self._after_change()

    def delete_category(self):
        idx = self._selected_index()
        if idx is None:
            return
        cat = self._display[idx]
        if not delete_category_with_migration(self, self.store, cat):
            return
        self._after_change()

class FolderLauncherApp:
    """The Folder Launcher tab: frequently used folders, organized by category."""

    def __init__(self, parent):
        self.parent = parent
        self.store = load_store()
        self._build_ui()
        self._refresh_tree()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        toolbar = ttk.Frame(self.parent, padding=(8, 8))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Add folder…", command=self.add_folder).pack(side="left")
        self.remove_btn = ttk.Button(
            toolbar, text="Remove selected", command=self.remove_selected, state="disabled"
        )
        self.remove_btn.pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Manage categories…", command=self.manage_categories).pack(
            side="left", padx=(8, 0)
        )

        list_frame = ttk.Frame(self.parent, padding=(8, 4))
        list_frame.pack(fill="both", expand=True)

        columns = ("path",)
        self.tree = ttk.Treeview(list_frame, columns=columns, show="tree", selectmode="browse")
        self.tree.heading("#1", text="Name")
        self.tree.heading("path", text="Path")
        self.tree.column("#1", width=180, anchor="w")
        self.tree.column("path", width=420, anchor="w")
        self.tree.tag_configure("category", font=("Segoe UI", 9, "bold"))

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-Button-1>", self.open_selected)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right-click context menu (populated per item type in _show_menu)
        self.menu = tk.Menu(self.parent, tearoff=0)
        self.tree.bind("<Button-3>", self._show_menu)

        self.status = ttk.Label(self.parent, padding=(8, 4))
        self.status.pack(fill="x")

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for cat in sorted_categories(self.store):
            # open=True: categories start expanded (Treeview inserts them closed).
            cat_id = self.tree.insert(
                "", "end", text=cat["name"], values=(), tags=("category",), open=True
            )
            for entry in cat["entries"]:
                self.tree.insert(
                    cat_id, "end", text=entry["name"], values=(entry["path"],), tags=("entry",)
                )
        total = sum(len(c["entries"]) for c in self.store["categories"])
        self.status.configure(
            text=f"{total} folder(s) in {len(self.store['categories'])} category(ies) · "
                 "double-click a folder to open it"
        )

    def reload(self):
        """Re-read the store from disk (used when the data folder changes)."""
        top = self.parent.winfo_toplevel()
        for child in top.winfo_children():
            if isinstance(child, CategoryManagerDialog) and child.winfo_exists():
                child.destroy()  # it holds a reference to the old store
        self.store = load_store()
        self._refresh_tree()

    def _on_select(self, event=None):
        has_selection = bool(self.tree.selection())
        self.remove_btn.configure(state="normal" if has_selection else "disabled")

    # ------------------------------------------------------------- helpers

    def _selected_item(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _locate(self, item_id):
        """Return (category_index, entry_index) for an item, or (cat_index, None) for a category.

        Note: Treeview.parent() returns '' (not None) for top-level items.
        """
        parent = self.tree.parent(item_id)
        if not parent:  # a category row
            name = self.tree.item(item_id, "text")
            entry_index = None
        else:  # an entry row; its parent is the category
            name = self.tree.item(parent, "text")
            entry_index = self.tree.index(item_id)
        cat_index = next(
            i for i, c in enumerate(self.store["categories"]) if c["name"] == name
        )
        return cat_index, entry_index

    # ------------------------------------------------------------- actions

    def add_folder(self):
        path = filedialog.askdirectory(title="Choose a folder to add")
        if not path:
            return
        path = os.path.normpath(path)
        for cat in self.store["categories"]:
            for entry in cat["entries"]:
                if entry["path"].lower() == path.lower():
                    messagebox.showinfo(APP_NAME, "That folder is already in your list.")
                    return

        categories = [c["name"] for c in self.store["categories"]]
        default = categories[0] if categories else None
        category = _CategoryPickerDialog(self.parent, categories, default=default).wait_for_result()
        if category is None:  # cancelled
            return

        cat = next(
            (c for c in self.store["categories"] if c["name"].lower() == category.lower()),
            None,
        )
        if cat is None:
            cat = {"name": category, "entries": []}
            self.store["categories"].append(cat)

        name = os.path.basename(path.rstrip("\\/")) or path
        cat["entries"].append({"name": name, "path": path})
        save_store(self.store)
        self._refresh_tree()

    def remove_selected(self, event=None):
        item_id = self._selected_item()
        if item_id is None:
            return
        cat_index, entry_index = self._locate(item_id)
        if entry_index is None:
            messagebox.showinfo(
                APP_NAME, "Select a folder (not a category) to remove it."
            )
            return
        del self.store["categories"][cat_index]["entries"][entry_index]
        save_store(self.store)
        self._refresh_tree()

    def change_category(self, event=None):
        item_id = self._selected_item()
        if item_id is None:
            return
        cat_index, entry_index = self._locate(item_id)
        if entry_index is None:
            messagebox.showinfo(
                APP_NAME, "Select a folder (not a category) to change its category."
            )
            return
        current = self.store["categories"][cat_index]
        others = [c["name"] for c in self.store["categories"] if c is not current]
        result = _CategoryPickerDialog(self.parent, others).wait_for_result()
        if result is None:  # cancelled
            return
        target = next(
            (c for c in self.store["categories"] if c["name"].lower() == result.lower()),
            None,
        )
        if target is None:
            target = {"name": result, "entries": []}
            self.store["categories"].append(target)
        entry = current["entries"].pop(entry_index)
        target["entries"].append(entry)
        save_store(self.store)
        self._refresh_tree()

    def open_selected(self, event=None):
        item_id = self._selected_item()
        if item_id is None:
            return
        cat_index, entry_index = self._locate(item_id)
        if entry_index is None:
            return  # a category row was double-clicked; nothing to open
        path = self.store["categories"][cat_index]["entries"][entry_index]["path"]
        if not os.path.isdir(path):
            messagebox.showwarning(APP_NAME, f"Folder no longer exists:\n{path}")
            return
        # Opens with the default handler — Windows Explorer on Windows.
        os.startfile(path)

    def rename_category(self, event=None):
        item_id = self._selected_item()
        if item_id is None:
            return
        cat_index, entry_index = self._locate(item_id)
        if entry_index is not None:
            messagebox.showinfo(APP_NAME, "Select a category to rename it.")
            return
        old_name = self.store["categories"][cat_index]["name"]
        new_name = simpledialog.askstring(
            APP_NAME, "Rename category:", initialvalue=old_name, parent=self.parent
        )
        if new_name is None:  # cancelled
            return
        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning(APP_NAME, "Category name cannot be empty.")
            return
        if any(
            c["name"].lower() == new_name.lower()
            for i, c in enumerate(self.store["categories"])
            if i != cat_index
        ):
            messagebox.showinfo(APP_NAME, f"A category named '{new_name}' already exists.")
            return
        self.store["categories"][cat_index]["name"] = new_name
        save_store(self.store)
        self._refresh_tree()

    def delete_category(self, event=None):
        item_id = self._selected_item()
        if item_id is None:
            return
        cat_index, entry_index = self._locate(item_id)
        if entry_index is not None:
            messagebox.showinfo(APP_NAME, "Select a category to delete it.")
            return
        cat = self.store["categories"][cat_index]
        if not delete_category_with_migration(self.parent, self.store, cat):
            return
        save_store(self.store)
        self._refresh_tree()

    def manage_categories(self):
        # Reuse an already-open dialog instead of opening a second one.
        top = self.parent.winfo_toplevel()
        for child in top.winfo_children():
            if isinstance(child, CategoryManagerDialog) and child.winfo_exists():
                child.lift()
                child.focus_set()
                return
        CategoryManagerDialog(self.parent, self.store, self._refresh_tree)

    def _show_menu(self, event):
        row = self.tree.identify_row(event.y)  # item under the cursor
        if not row:
            return
        self.tree.selection_set(row)
        self._populate_menu(row)
        self.menu.post(event.x_root, event.y_root)

    def _populate_menu(self, row):
        """Fill the context menu with the actions relevant to the item type."""
        _, entry_index = self._locate(row)
        self.menu.delete(0, "end")
        if entry_index is not None:  # a folder entry
            self.menu.add_command(label="Open in Explorer", command=self.open_selected)
            self.menu.add_command(label="Change category…", command=self.change_category)
            self.menu.add_command(label="Remove entry", command=self.remove_selected)
        else:  # a category
            self.menu.add_command(label="Rename category…", command=self.rename_category)
            self.menu.add_command(label="Delete category", command=self.delete_category)


class AppLauncherTab:
    """The App Launcher tab: shortcuts to frequently used app files.

    Laid out as a grid of icons like an Android home screen: icon on top,
    label below. Click to select, drag to reorder, double-click to launch,
    right-click for options.
    """

    ICON_SIZE = 48
    CELL_W = 76
    CELL_H = 96
    SELECT_BG = "#d8e6f5"
    DRAG_BG = "#bcd6f0"

    def __init__(self, parent):
        self.parent = parent
        self.apps = load_apps()
        self._images = {}  # keep PhotoImages alive (Tk GCs unreferenced images)
        self._selected = None
        self._drag = None
        self.cells = []
        self._build_ui()
        self._refresh_grid()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        toolbar = ttk.Frame(self.parent, padding=(8, 8))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Add app…", command=self.add_app).pack(side="left")
        self.remove_btn = ttk.Button(
            toolbar, text="Remove selected", command=self.remove_selected, state="disabled"
        )
        self.remove_btn.pack(side="left", padx=(8, 0))

        list_frame = ttk.Frame(self.parent, padding=(8, 4))
        list_frame.pack(fill="both", expand=True)

        # Scrollable canvas hosting the icon grid.
        self.canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas)
        self._default_bg = self.inner.cget("background")  # for restoring selection
        self.inner.bind("<B1-Motion>", self._on_drag)
        self.inner.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", self._relayout)

        self.menu = tk.Menu(self.parent, tearoff=0)
        self.menu.add_command(label="Open", command=self.open_selected)
        self.menu.add_command(label="Rename…", command=self.rename_selected)
        self.menu.add_command(label="Remove", command=self.remove_selected)

        self.status = ttk.Label(self.parent, padding=(8, 4))
        self.status.pack(fill="x")

    def _bind_wheel(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)  # X11 scroll up/down
        widget.bind("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        up = getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4
        down = getattr(event, "delta", 0) < 0 or getattr(event, "num", 0) == 5
        if up:
            self.canvas.yview_scroll(-1, "units")
        elif down:
            self.canvas.yview_scroll(1, "units")

    def _relayout(self, event=None):
        """Re-flow the grid so the column count follows the window width."""
        cols = max(1, self.canvas.winfo_width() // (self.CELL_W + 8))
        for i, cell in enumerate(self.cells):
            cell.grid(row=i // cols, column=i % cols, padx=4, pady=6)
        self.inner.configure(width=cols * (self.CELL_W + 8))

    def _refresh_grid(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.cells = []
        if not self.apps:
            hint = tk.Label(
                self.inner, text="No apps yet — click 'Add app…' to get started.", padx=16, pady=16
            )
            hint.grid(row=0, column=0)
        for i, app in enumerate(self.apps):
            cell = tk.Frame(self.inner, width=self.CELL_W, height=self.CELL_H)
            cell.pack_propagate(False)
            icon = tk.Label(cell, image=self._icon_for(app["path"]), borderwidth=0, takefocus=0)
            icon.pack(pady=(10, 2))
            label = tk.Label(
                cell,
                text=self._wrap_name(app["name"]),
                width=10,
                anchor="center",
                justify="center",
                takefocus=0,
            )
            label.pack()
            for w in (cell, icon, label):
                w.bind("<Button-1>", self._on_press)
                w.bind("<B1-Motion>", self._on_drag)
                w.bind("<ButtonRelease-1>", self._on_release)
                w.bind("<Double-Button-1>", lambda e, i=i: self.open_selected())
                w.bind("<Button-3>", lambda e, i=i: self._show_menu(e, i))
                self._bind_wheel(w)
            self.cells.append(cell)
        self._selected = None
        self.remove_btn.configure(state="disabled")
        self._relayout()
        self.status.configure(
            text=f"{len(self.apps)} app(s) · drag to reorder, double-click to launch"
        )

    def reload(self):
        """Re-read the app list from disk (used when the data folder changes)."""
        self.apps = load_apps()
        self._images.clear()
        self._selected = None
        self._drag = None
        self._refresh_grid()

    def _bg_rgb(self):
        """The grid's background color as an (r, g, b) tuple of 0-255 values."""
        r, g, b = self.inner.winfo_rgb(self._default_bg)
        return r // 257, g // 257, b // 257

    @staticmethod
    def _wrap_name(name, width=10, max_lines=2):
        """Word-wrap `name` into at most max_lines of ~width characters each.

        tk.Label has no built-in wrapping, so newlines are inserted manually;
        any line that doesn't fit its width is truncated with an ellipsis
        (this also covers a single long word, which can't be wrapped).
        """
        words = name.split()
        lines, line = [], ""
        for word in words:
            if not line or len(line) + 1 + len(word) <= width:
                line = word if not line else line + " " + word
            else:
                lines.append(line)
                line = word
                if len(lines) >= max_lines:
                    break  # `line` would become a (max_lines+1)-th line
        if line and len(lines) < max_lines:
            lines.append(line)
        for i, l in enumerate(lines):
            if len(l) > width:
                lines[i] = l[: max(width - 1, 0)] + "…"
        return "\n".join(lines)

    def _icon_for(self, path):
        """Icon for an app: its .ico twin, else a favicon.ico in the same folder,
        else the folder icon.

        PhotoImage has no alpha channel, so transparent pixels are flattened
        onto the grid's background color to stay invisible against it.
        """
        if path in self._images:
            return self._images[path]
        base = os.path.splitext(os.path.basename(path))[0]
        folder = os.path.dirname(path)
        img = None
        # Prefer an .ico twin named after the app file; fall back to a shared
        # favicon.ico in the same folder when the twin is missing.
        for candidate in (os.path.join(folder, base + ".ico"), os.path.join(folder, "favicon.ico")):
            if os.path.isfile(candidate):
                img = load_ico_image(candidate, self.ICON_SIZE, background=self._bg_rgb())
                if img is not None:
                    break
        if img is None:
            img = folder_icon(self.ICON_SIZE)
        self._images[path] = img
        return img

    def _select(self, index):
        self._selected = index
        for i, cell in enumerate(self.cells):
            bg = self.SELECT_BG if i == index else self._default_bg
            for w in (cell,) + tuple(cell.winfo_children()):
                w.configure(background=bg)
        self.remove_btn.configure(state="normal" if index is not None else "disabled")

    # ------------------------------------------------------ drag to reorder

    def _cell_of(self, widget):
        """Index of the cell containing `widget`, or None."""
        for i, cell in enumerate(self.cells):
            if widget is cell or widget in cell.winfo_children():
                return i
        return None

    def _cell_at(self, x_root, y_root):
        """Index of the cell under the given root coordinates, or None."""
        for i, cell in enumerate(self.cells):
            if not cell.winfo_exists():
                continue
            x, y = cell.winfo_rootx(), cell.winfo_rooty()
            if x <= x_root < x + cell.winfo_width() and y <= y_root < y + cell.winfo_height():
                return i
        return None

    def _set_cell_bg(self, index, bg):
        cell = self.cells[index]
        for w in (cell,) + tuple(cell.winfo_children()):
            w.configure(background=bg)

    def _on_press(self, event):
        index = self._cell_of(event.widget)
        self._drag = None if index is None else {
            "index": index, "x": event.x_root, "y": event.y_root, "active": False
        }

    def _on_drag(self, event):
        drag = self._drag
        if drag is None:
            return
        if not drag["active"]:
            if abs(event.x_root - drag["x"]) < 4 and abs(event.y_root - drag["y"]) < 4:
                return  # barely moved — still just a click
            drag["active"] = True
        target = self._cell_at(event.x_root, event.y_root)
        if target is not None and target != drag["index"]:
            app = self.apps.pop(drag["index"])
            self.apps.insert(target, app)
            # Swap the two cells' grid slots so the icons visibly follow the
            # new order (and cells[i] stays in sync with apps[i]).
            a, b = drag["index"], target
            cols = max(1, self.canvas.winfo_width() // (self.CELL_W + 8))
            self.cells[a].grid(row=b // cols, column=b % cols, padx=4, pady=6)
            self.cells[b].grid(row=a // cols, column=a % cols, padx=4, pady=6)
            self.cells[a], self.cells[b] = self.cells[b], self.cells[a]
            drag["index"] = target
        self._set_cell_bg(drag["index"], self.DRAG_BG)

    def _on_release(self, event):
        drag, self._drag = self._drag, None
        if drag is None:
            return
        index = drag["index"]
        if drag["active"]:
            save_apps(self.apps)
            self._refresh_grid()
        self._select(index)

    # ------------------------------------------------------------- actions

    def add_app(self):
        path = filedialog.askopenfilename(
            title="Choose an app file",
            parent=self.parent,
            filetypes=[
                ("All supported", "*.exe;*.bat;*.cmd;*.lnk;*.html"),
                ("Executables", "*.exe"),
                ("Batch files", "*.bat;*.cmd"),
                ("Shortcuts", "*.lnk"),
                ("Web pages", "*.html"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        path = os.path.normpath(path)
        if any(a["path"].lower() == path.lower() for a in self.apps):
            messagebox.showinfo(APP_NAME, "That app is already in your list.")
            return
        self.apps.append({"name": os.path.basename(path), "path": path})
        save_apps(self.apps)
        self._refresh_grid()

    def rename_selected(self, event=None):
        if self._selected is None:
            return
        current = self.apps[self._selected]["name"]
        name = simpledialog.askstring(
            APP_NAME, "Rename app:", initialvalue=current, parent=self.parent
        )
        if name is None:  # cancelled
            return
        name = name.strip()
        if not name:
            messagebox.showwarning(APP_NAME, "App name cannot be empty.")
            return
        self.apps[self._selected]["name"] = name
        save_apps(self.apps)
        self._refresh_grid()

    def remove_selected(self, event=None):
        if self._selected is None:
            return
        name = self.apps[self._selected]["name"]
        if not messagebox.askyesno(APP_NAME, f"Remove '{name}' from your apps?"):
            return
        del self.apps[self._selected]
        save_apps(self.apps)
        self._refresh_grid()

    def open_selected(self, event=None):
        if self._selected is None:
            return
        path = self.apps[self._selected]["path"]
        if not os.path.isfile(path):
            messagebox.showwarning(APP_NAME, f"File no longer exists:\n{path}")
            return
        os.startfile(path)

    def _show_menu(self, event, index):
        self._select(index)
        self.menu.post(event.x_root, event.y_root)


class SettingsTab:
    """The Settings tab: choose where the data files are stored.

    apps.json and folders.json live in the data folder; both are created
    automatically if they don't exist there.
    """

    def __init__(self, parent, settings, on_change):
        self.parent = parent
        self.settings = settings
        self.on_change = on_change
        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.parent, padding=(8, 8))
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Data folder", padding=(0, 0, 0, 4)).pack(anchor="w")

        row = ttk.Frame(frame)
        row.pack(fill="x")
        self.path_label = ttk.Label(row, text=self.settings["data_folder"], anchor="w")
        self.path_label.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self.browse).pack(side="right")

        ttk.Label(
            frame,
            text="apps.json and folders.json are stored in this folder. "
                 "They're created automatically if they don't exist.",
            padding=(0, 8, 0, 0),
            justify="left",
        ).pack(anchor="w")

    def browse(self):
        folder = filedialog.askdirectory(title="Choose the data folder", parent=self.parent)
        if not folder:
            return
        folder = os.path.normpath(folder)
        self.settings["data_folder"] = folder
        save_settings(self.settings)
        set_data_folder(folder)  # creates apps.json / folders.json if missing
        self.path_label.configure(text=folder)
        self.on_change()


class ToolsTab:
    """The Tools tab: small, self-contained utility tools.

    Holds independent stacked panels, one per tool:

    * KB → Bytes — numbers-only input, live × 1024 result, copy button.
    * Mini Simple Spreadsheet — a 3-column grid: five editable rows plus a
      sixth row of live, bold, non-editable totals — the three column sums
      and a fourth grand-total box (pale yellow `#f9fcb2`) that adds them
      up. Clicking any total selects it (no editing possible); Ctrl+C copies
      the selected total to the clipboard; a "Clear all" button empties the
      grid.

    Tools are stacked as independent panels so more can be added later
    without restructuring the tab.
    """

    _SPREAD_ROWS = 5  # editable rows; the sixth row holds the column sums
    _SPREAD_COLS = 3
    _SPREAD_CELL_W = 96  # fixed cell size in px (inputs and sums match)
    _SPREAD_CELL_H = 26
    _SPREAD_BG = "#f5f5f5"  # sum cell color (matches the KB tool's result)
    _SPREAD_SELECTED_BG = "#b6d7f0"  # sum cell color while selected
    _SPREAD_GRAND_BG = "#f9fcb2"  # grand-total cell color (always, never selected)

    def __init__(self, parent):
        self.parent = parent
        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.parent, padding=(8, 8))
        frame.pack(fill="both", expand=True)

        # One panel per tool; add more panels below this one.
        self.panels = ttk.Frame(frame)
        self.panels.pack(fill="x")

        self._add_bytes_to_kb_tool()
        self._add_mini_spreadsheet_tool()

    def _add_bytes_to_kb_tool(self):
        panel = ttk.LabelFrame(self.panels, text="KB → Bytes", padding=(10, 8))
        panel.pack(fill="x")

        row = ttk.Frame(panel)
        row.pack(fill="x")

        ttk.Label(row, text="Enter KB:").pack(side="left")

        self._bytes_var = tk.StringVar(value="")
        vcmd = self.parent.register(self._validate_bytes)
        self.bytes_entry = tk.Entry(
            row,
            textvariable=self._bytes_var,
            width=14,
            validate="key",
            validatecommand=(vcmd, "%P"),
        )
        self.bytes_entry.pack(side="left", padx=(6, 0))
        self._bytes_var.trace_add("write", self._update_result)

        ttk.Label(row, text="× 1024 =").pack(side="left", padx=(10, 0))

        self.result_var = tk.StringVar(value="0")
        self.result_label = tk.Label(
            row,
            textvariable=self.result_var,
            width=18,
            anchor="w",
            relief="sunken",
            borderwidth=1,
            background="#f5f5f5",
        )
        self.result_label.pack(side="left", padx=(4, 0))

        self._copy_btn = tk.Frame(row, width=30, height=30, takefocus=0)
        self._copy_btn.pack(side="left", padx=(10, 0))
        self._copy_btn.pack_propagate(False)
        self._copy_canvas = tk.Canvas(
            self._copy_btn,
            width=24,
            height=24,
            highlightthickness=0,
            background=self._copy_btn.cget("background"),
            takefocus=0,
        )
        self._copy_canvas.pack(side="left")
        self._copy_canvas.bind("<Button-1>", self._copy_answer)
        self._copy_canvas.bind(
            "<Enter>", lambda e: self._copy_canvas.configure(cursor="hand2")
        )
        self._copy_canvas.bind(
            "<Leave>", lambda e: self._copy_canvas.configure(cursor="")
        )
        self._draw_copy_icon()
        self._bind_tooltip(self._copy_canvas, "Copy to clipboard")

    def _add_mini_spreadsheet_tool(self):
        panel = ttk.LabelFrame(
            self.panels, text="Mini Simple Spreadsheet", padding=(10, 8)
        )
        panel.pack(fill="x", pady=(10, 0))

        # "Clear all" hugs the top-right corner of the panel, opposite the
        # panel's label text.
        head = ttk.Frame(panel)
        head.pack(fill="x")
        self._clear_btn = ttk.Button(
            head, text="Clear all", command=self._clear_spreadsheet
        )
        self._clear_btn.pack(side="right")

        table = ttk.Frame(panel)
        table.pack(fill="both", expand=True)

        # Five editable rows of signed-number cells. Each cell lives in a
        # fixed-size box, so input boxes and sum boxes are exactly equal;
        # padx/pady=(0, 2) leaves only a 2px gap between rows and columns.
        vcmd = self.parent.register(self._validate_signed_number)
        self._spread_vars = []
        self._spread_entries = []
        self._spread_boxes = []
        for r in range(self._SPREAD_ROWS):
            for c in range(self._SPREAD_COLS):
                var = tk.StringVar(value="")
                var.trace_add("write", self._update_spread_sums)
                box = tk.Frame(
                    table, width=self._SPREAD_CELL_W, height=self._SPREAD_CELL_H
                )
                box.grid(row=r, column=c, padx=(0, 2), pady=(0, 2))
                box.pack_propagate(False)
                entry = tk.Entry(
                    box,
                    textvariable=var,
                    validate="key",
                    validatecommand=(vcmd, "%P"),
                )
                entry.pack(fill="both", expand=True)
                self._spread_boxes.append(box)
                self._spread_entries.append(entry)
                self._spread_vars.append(var)

        # Sixth row: live totals. Labels, not Entries — totals can never be
        # edited, so clicking one just selects it (light blue). The fourth
        # cell is the grand total: the three column sums added together, on
        # its own pale-yellow background. All four are selectable and
        # Ctrl+C-able; `_spread_sum_bg` remembers each cell's own default
        # color so deselecting restores that one instead of the shared gray.
        self._spread_sum_vars = []
        self._spread_sum_labels = []
        self._spread_sum_bg = []
        for c in range(self._SPREAD_COLS):
            var = tk.StringVar(value="0")
            box = tk.Frame(
                table, width=self._SPREAD_CELL_W, height=self._SPREAD_CELL_H
            )
            box.grid(row=self._SPREAD_ROWS, column=c, padx=(0, 2), pady=(0, 2))
            box.pack_propagate(False)
            label = tk.Label(
                box,
                textvariable=var,
                anchor="c",
                relief="sunken",
                borderwidth=1,
                background=self._SPREAD_BG,
                font=("Segoe UI", 10, "bold"),
            )
            label.pack(fill="both", expand=True)
            label.bind(
                "<Button-1>", lambda e, cell=c: self._select_spread_sum(cell)
            )
            self._spread_boxes.append(box)
            self._spread_sum_vars.append(var)
            self._spread_sum_labels.append(label)
            self._spread_sum_bg.append(self._SPREAD_BG)

        # Grand total: same fixed box and gap, one column further right, wired
        # exactly like the column sums (click to select, Ctrl+C to copy) — the
        # only difference is its own default background color.
        self._spread_grand_var = tk.StringVar(value="0")
        box = tk.Frame(
            table, width=self._SPREAD_CELL_W, height=self._SPREAD_CELL_H
        )
        box.grid(
            row=self._SPREAD_ROWS, column=self._SPREAD_COLS, padx=(0, 2), pady=(0, 2)
        )
        box.pack_propagate(False)
        label = tk.Label(
            box,
            textvariable=self._spread_grand_var,
            anchor="c",
            relief="sunken",
            borderwidth=1,
            background=self._SPREAD_GRAND_BG,
            font=("Segoe UI", 10, "bold"),
        )
        label.pack(fill="both", expand=True)
        label.bind(
            "<Button-1>",
            lambda e, cell=self._SPREAD_COLS: self._select_spread_sum(cell),
        )
        self._spread_boxes.append(box)
        self._spread_sum_vars.append(self._spread_grand_var)
        self._spread_sum_labels.append(label)
        self._spread_sum_bg.append(self._SPREAD_GRAND_BG)
        self._spread_grand_label = label

        self._spread_selected = None

        # Ctrl+C anywhere in the window copies the selected total box to the
        # clipboard. Bound on the top window so the event is caught no
        # matter which widget currently holds keyboard focus. A plain Ctrl+C
        # on Windows sends the lowercase virtual event <Control-c> (the
        # uppercase <Control-C> only arrives with Shift), and non-Latin
        # keyboard layouts can match neither name — so every <Key> event is
        # bound too, and the handler checks for the Ctrl+C character code 3.
        top = self.parent.winfo_toplevel()
        top.bind("<Control-c>", self._copy_selected_sum)
        top.bind("<Control-C>", self._copy_selected_sum)
        top.bind("<Key>", self._copy_selected_sum)

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _validate_bytes(new):
        """Allow an empty field, digits, and at most one decimal point."""
        if new == "":
            return True
        if new.count(".") > 1:
            return False
        return new.replace(".", "", 1).isdigit()

    @staticmethod
    def _validate_signed_number(new):
        """Spreadsheet cells: empty, an optional leading minus, digits, and
        at most one decimal point. A lone "-" is accepted while typing so
        negatives can start with the minus; such cells are skipped by the
        sum until they parse as numbers."""
        if new.startswith("-"):
            new = new[1:]
        if new == "":
            return True
        if new.count(".") > 1:
            return False
        return new.replace(".", "", 1).isdigit()

    @staticmethod
    def _format_number(n):
        """Show whole numbers without a trailing .0; compact otherwise."""
        if n == int(n):
            return str(int(n))
        return f"{n:g}"

    def _update_result(self, *args):
        text = self._bytes_var.get()
        if text == "":
            self.result_var.set("")
            return
        try:
            value = float(text)
        except ValueError:
            return
        self.result_var.set(self._format_number(value * 1024))

    def _draw_copy_icon(self, accent=False):
        c = self._copy_canvas
        c.delete("all")
        if accent:
            back_fill, back_outline = "#8bc34a", "#4caf50"
            front_fill, front_outline, line = "#e8f5e9", "#2e7d32", "#2e7d32"
        else:
            back_fill, back_outline = "#c5c5c5", "#8a8a8a"
            front_fill, front_outline, line = "#ffffff", "#3a3a3a", "#3a3a3a"
        # Rear document: a box offset up-and-to-the-right.
        c.create_rectangle(10, 4, 18, 14, outline=back_outline, fill=back_fill, width=1.5)
        # Front document: same size, offset down-and-to-the-left — the classic
        # "copy" glyph.
        c.create_rectangle(
            6, 8, 14, 18, outline=front_outline, fill=front_fill, width=2
        )
        # Two lines of "text" on the front document.
        c.create_line(8, 12, 12, 12, fill=line, width=1.5, capstyle="round")
        c.create_line(8, 15, 11, 15, fill=line, width=1.5, capstyle="round")

    def _bind_tooltip(self, widget, text):
        """Show a small stdlib tooltip near `widget` on hover."""
        label = tk.Label(
            self.parent.winfo_toplevel(),
            text=text, relief="solid", borderwidth=1,
            background="#ffffd0", foreground="#222222",
            font=("Segoe UI", 8),
        )
        state = {"id": None}

        def show():
            state["id"] = None
            x = widget.winfo_rootx() + widget.winfo_width() + 4
            y = widget.winfo_rooty()
            label.place(x=x, y=y, anchor="w")

        def schedule_show():
            label.place_forget()
            state["id"] = widget.after(400, show)

        def hide():
            if state["id"] is not None:
                widget.after_cancel(state["id"])
            state["id"] = None
            label.place_forget()

        widget.bind("<Enter>", lambda e: schedule_show())
        widget.bind("<Leave>", lambda e: hide())

    def _copy_answer(self, event=None):
        value = self.result_var.get().strip()
        if not value:
            return
        top = self.parent.winfo_toplevel()
        try:
            top.clipboard_clear()
            top.clipboard_append(value)
        except tk.TclError:
            return
        top.update_idletasks()
        self._draw_copy_icon(accent=True)
        self._copy_canvas.after(350, self._draw_copy_icon)

    # ------------------------------------------ mini simple spreadsheet

    def _update_spread_sums(self, *args):
        """Trace callback: recompute the column sums and the grand total.

        The grand total adds the columns' float totals (not their rounded
        display strings), so it always equals what the sum boxes show.
        """
        grand_total = 0.0
        for c in range(self._SPREAD_COLS):
            total = 0.0
            for r in range(self._SPREAD_ROWS):
                text = self._spread_vars[r * self._SPREAD_COLS + c].get()
                if text:
                    try:
                        total += float(text)
                    except ValueError:
                        pass
            grand_total += total
            self._spread_sum_vars[c].set(self._format_number(total))
        self._spread_grand_var.set(self._format_number(grand_total))

    def _select_spread_sum(self, cell):
        """Toggle a total cell's selection; totals can't be edited, only selected.

        Clicking selects (light blue background); clicking the selected cell
        again deselects it. Clicking another total moves the selection. Each
        cell restores its own default color from `_spread_sum_bg` (the grand
        total is paler yellow), so deselecting never flattens it to gray.
        """
        label = self._spread_sum_labels[cell]
        if self._spread_selected == cell:
            self._spread_selected = None
            label.configure(background=self._spread_sum_bg[cell])
        else:
            if self._spread_selected is not None:
                self._spread_sum_labels[self._spread_selected].configure(
                    background=self._spread_sum_bg[self._spread_selected]
                )
            self._spread_selected = cell
            label.configure(background=self._SPREAD_SELECTED_BG)

    def _clear_spreadsheet(self):
        """Empty every editable cell; the write traces reset the sums to 0."""
        for var in self._spread_vars:
            var.set("")

    def _copy_selected_sum(self, event):
        """Ctrl+C handler: copy the selected total box's value to the clipboard.

        Proceeds only for Ctrl+C: the typed character code 3 (which Windows
        reports on every keyboard layout) or events without a keysym (named
        bindings / synthetic events). Other keystrokes — including Enter and
        Backspace, whose char is not code 3 — are ignored.
        """
        if self._spread_selected is None:
            return
        if event is not None:
            if event.char:
                if event.char != "\x03":
                    return
            elif event.keysym not in ("", None):
                return
        value = self._spread_sum_vars[self._spread_selected].get().strip()
        if not value:
            return
        top = self.parent.winfo_toplevel()
        try:
            top.clipboard_clear()
            top.clipboard_append(value)
        except tk.TclError:
            return
        top.update_idletasks()


class MainApp:
    """The main window: a notebook with one tab per app."""

    def __init__(self, root: tk.Tk, settings):
        root.title("OmniHub")
        root.geometry("700x520")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)

        folder_tab = ttk.Frame(notebook)
        notebook.add(folder_tab, text="Folder Launcher")
        self.folder_app = FolderLauncherApp(folder_tab)

        apps_tab = ttk.Frame(notebook)
        notebook.add(apps_tab, text="App Launcher")
        self.apps_tab = AppLauncherTab(apps_tab)

        tools_tab = ttk.Frame(notebook)
        notebook.add(tools_tab, text="Tools")
        self.tools_tab = ToolsTab(tools_tab)

        settings_tab = ttk.Frame(notebook)
        notebook.add(settings_tab, text="Settings")
        SettingsTab(settings_tab, settings, self._reload_tabs)

    def _reload_tabs(self):
        """Re-read both tabs' data after the data folder changes."""
        self.folder_app.reload()
        self.apps_tab.reload()


def main():
    root = tk.Tk()
    root.withdraw()  # stay hidden while the data folder is resolved
    settings = load_settings()
    folder = settings["data_folder"]
    if not os.path.isdir(folder):
        if folder == default_data_folder():
            # First run (no settings.json yet): bootstrap the app's own
            # data folder.
            os.makedirs(folder, exist_ok=True)
        else:
            # The configured data folder is gone (deleted or moved). Ask the
            # user to pick an existing one; on cancel, revert to the default.
            # A stale folder is never recreated silently.
            messagebox.showinfo(
                APP_NAME,
                f"The data folder no longer exists:\n{folder}\n\n"
                "Please choose an existing folder where your data should be stored.",
            )
            chosen = filedialog.askdirectory(title="Choose the data folder", parent=root)
            if chosen:
                settings["data_folder"] = os.path.normpath(chosen)
            else:  # cancelled — revert to the default data folder
                settings["data_folder"] = default_data_folder()
                os.makedirs(settings["data_folder"], exist_ok=True)
            save_settings(settings)
    set_data_folder(settings["data_folder"])  # creates the data files if missing
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "omnihub.ico")
    if os.path.isfile(icon):
        try:
            root.iconbitmap(icon)
        except tk.TclError:  # e.g. unsupported .ico on this Tk build
            pass
    MainApp(root, settings)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
