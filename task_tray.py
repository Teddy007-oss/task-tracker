#!/usr/bin/env python3
"""
Task Tray — a lightweight Kanban board for Ubuntu GNOME.

Lives permanently in the system tray using AyatanaAppIndicator3.
Clicking the tray icon allows opening the board or quitting.
The board window features three equal columns: Tasks, In Progress, Finished.
Supports drag and drop between columns (moving forward to the next pane),
adding tasks, clearing finished tasks, and celebratory desktop notifications.
Tasks persist to ~/.local/share/task-tray/tasks.json atomically.

Run:
    python3 task_tray.py
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

# Prefer AyatanaAppIndicator3 (modern GNOME/Ubuntu), fall back to AppIndicator3
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

gi.require_version("Notify", "0.7")
from gi.repository import Gtk, Gdk, Gio, GLib, Notify, Pango, GdkPixbuf

import json
import os
import random
import shutil
import subprocess
import sys
import uuid

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

APP_ID = "com.github.tasktray"
APP_NAME = "Task Tray"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "task-tray")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

# Candidate locations for custom application icon
CUSTOM_ICON_CANDIDATES = [
    os.path.join(APP_DIR, "icon.png"),
    os.path.join(DATA_DIR, "icon.png"),
    os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps/task-tray.png"),
    os.path.expanduser(
        "~/Downloads/los-angeles-california-elon-musk-arrives-to-the-10th-annual-breakthrough-prize-ceremony-at.webp"
    ),
]

# Columns configuration: (status_id, display_title, empty_placeholder)
COLUMNS = [
    ("todo", "Tasks", "No tasks"),
    ("in_progress", "In Progress", "No tasks in progress"),
    ("done", "Finished", "No finished tasks"),
]

VALID_STATUSES = {col[0] for col in COLUMNS}

# Tasks can only advance forward to the next pane
NEXT_PANE = {
    "todo": "in_progress",
    "in_progress": "done",
}

# Symbolic icon fallbacks for the top bar if no custom icon is found
PREFERRED_ICONS = [
    "checkbox-symbolic",
    "task-due-symbolic",
    "view-list-symbolic",
    "emblem-default-symbolic",
]

# Random celebratory messages when a task is moved to Finished
CONGRATS_MESSAGES = [
    "🎉 Boom! Task crushed!",
    "🔥 You absolute legend!",
    "✅ Nailed it. Onto the next!",
    "🚀 Look at you go!",
    "💪 Crushed it like a pro!",
    "🌟 Another one bites the dust!",
    "🏆 Champion move right there!",
    "🥳 That's how it's done!",
    "⚡ Fast and flawless!",
    "🎯 Bullseye! Task complete!",
    "😎 Too easy for you.",
    "🍾 Pop the confetti — done!",
]

# Minimal CSS: border and padding on tiles only
CSS_DATA = b"""
.task-tile {
    border: 1px solid alpha(currentColor, 0.25);
    border-radius: 4px;
    padding: 8px;
}
"""

TARGET_ENTRY = Gtk.TargetEntry.new("text/plain", Gtk.TargetFlags.SAME_APP, 0)


# --------------------------------------------------------------------------
# Persistence & Migration
# --------------------------------------------------------------------------

def ensure_data_dir():
    """Make sure ~/.local/share/task-tray exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_tasks():
    """
    Load tasks from disk. Returns a list of dicts: {id, title, status}.
    Auto-migrates old tasks without status to 'todo'.
    """
    ensure_data_dir()
    if not os.path.exists(TASKS_FILE):
        return []

    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                migrated = False
                valid_tasks = []
                for item in data:
                    if isinstance(item, dict) and "title" in item:
                        task = dict(item)
                        if "id" not in task or not task["id"]:
                            task["id"] = str(uuid.uuid4())
                            migrated = True
                        # Auto-migrate old tasks lacking valid status to 'todo'
                        if task.get("status") not in VALID_STATUSES:
                            task["status"] = "todo"
                            migrated = True
                        valid_tasks.append(task)
                if migrated:
                    save_tasks(valid_tasks)
                return valid_tasks
    except (json.JSONDecodeError, OSError):
        # Corrupted or unreadable file — start fresh rather than crashing
        pass
    return []


def save_tasks(tasks):
    """Persist tasks to disk atomically (write to temp file, then rename)."""
    ensure_data_dir()
    tmp_path = TASKS_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, TASKS_FILE)
    except OSError as e:
        print(f"[{APP_ID}] Failed to save tasks: {e}")


def apply_css():
    """Apply minimal styling for task tiles."""
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS_DATA)
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


def get_custom_icon_path():
    """Return the absolute path to a custom icon file if one exists."""
    for path in CUSTOM_ICON_CANDIDATES:
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def ensure_desktop_and_dock_integration(icon_path):
    """
    Register the desktop file and hicolor icon caches so GNOME Shell
    and Ubuntu Dock display the custom icon for running windows.
    """
    if not icon_path or not os.path.exists(icon_path):
        return

    script_path = os.path.abspath(__file__)
    abs_icon = os.path.abspath(icon_path)

    # 1. Install to ~/.local/share/icons/hicolor
    try:
        pix = GdkPixbuf.Pixbuf.new_from_file(abs_icon)
        for size in [16, 24, 32, 48, 64, 128, 256, 512]:
            icon_dir = os.path.expanduser(f"~/.local/share/icons/hicolor/{size}x{size}/apps")
            os.makedirs(icon_dir, exist_ok=True)
            scaled = pix.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
            scaled.savev(os.path.join(icon_dir, f"{APP_ID}.png"), "png", [], [])
            scaled.savev(os.path.join(icon_dir, "task-tray.png"), "png", [], [])

        hicolor_dir = os.path.expanduser("~/.local/share/icons/hicolor")
        subprocess.run(["gtk-update-icon-cache", "-f", "-t", hicolor_dir], capture_output=True)
    except Exception as e:
        print(f"[{APP_ID}] Icon cache update notice: {e}")

    # 2. Install desktop entries in ~/.local/share/applications
    desktop_content = f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Comment=Simple Kanban board for Ubuntu GNOME with top bar tray icon
Exec=python3 {script_path}
Icon={abs_icon}
Terminal=false
Categories=Utility;Office;ProjectManagement;
StartupWMClass={APP_ID}
"""
    apps_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(apps_dir, exist_ok=True)
    for name in [f"{APP_ID}.desktop", "task-tray.desktop"]:
        dest = os.path.join(apps_dir, name)
        try:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(desktop_content)
        except OSError:
            pass

    try:
        subprocess.run(["update-desktop-database", apps_dir], capture_output=True)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Main Application
# --------------------------------------------------------------------------

class TaskTrayApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.tasks = []
        self.indicator = None
        self.menu = None
        self.window = None

        # Column widget tracking
        self.col_headers = {}
        self.col_tiles_boxes = {}
        self.add_entry = None
        self.clear_finished_btn = None

    def do_startup(self):
        # Set program name so Wayland app_id and X11 WM_CLASS match our desktop entry
        GLib.set_prgname(APP_ID)
        GLib.set_application_name(APP_NAME)

        Gtk.Application.do_startup(self)
        Notify.init(APP_NAME)
        apply_css()

        icon_path = get_custom_icon_path()
        if icon_path:
            ensure_desktop_and_dock_integration(icon_path)
            try:
                Gtk.Window.set_default_icon_from_file(icon_path)
            except GLib.Error:
                pass

        self.tasks = load_tasks()
        self._init_tray()

    def do_activate(self):
        """
        Called on initial start and whenever another instance is launched.
        Presents the board window.
        """
        if not self.window:
            self._create_board_window()
            # Hold application so it doesn't quit when the window is hidden
            self.hold()
        self.window.present()

    # ----------------------------------------------------------- Tray icon

    def _pick_fallback_icon(self):
        """Pick an available symbolic icon from the current icon theme."""
        theme = Gtk.IconTheme.get_default()
        for name in PREFERRED_ICONS:
            if theme.has_icon(name):
                return name
        return "utilities-terminal"

    def _init_tray(self):
        """Initialize system tray indicator and its menu."""
        custom_icon = get_custom_icon_path()
        if custom_icon:
            icon_dir = os.path.dirname(custom_icon)
            icon_name = os.path.splitext(os.path.basename(custom_icon))[0]
            self.indicator = AppIndicator3.Indicator.new_with_path(
                APP_ID,
                icon_name,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
                icon_dir,
            )
            # Full path fallback for indicators supporting direct paths
            self.indicator.set_icon_full(custom_icon, APP_NAME)
        else:
            self.indicator = AppIndicator3.Indicator.new(
                APP_ID,
                self._pick_fallback_icon(),
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
            )

        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title(APP_NAME)

        self.menu = Gtk.Menu()

        open_item = Gtk.MenuItem(label="Open board")
        open_item.connect("activate", self.on_open_board)
        self.menu.append(open_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_quit)
        self.menu.append(quit_item)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)

    def on_open_board(self, _widget):
        self.activate()

    def on_quit(self, _widget):
        Notify.uninit()
        self.quit()

    # -------------------------------------------------------- Board window

    def _create_board_window(self):
        self.window = Gtk.ApplicationWindow(application=self, title=APP_NAME)
        self.window.set_default_size(860, 540)
        self.window.set_border_width(12)
        self.window.connect("delete-event", self.on_window_delete)

        icon_path = get_custom_icon_path()
        if icon_path:
            try:
                self.window.set_icon_from_file(icon_path)
            except GLib.Error as e:
                print(f"[{APP_ID}] Failed to set window icon: {e}")

        # Three equal-width columns
        columns_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            homogeneous=True,
        )
        self.window.add(columns_box)

        for status, title, placeholder in COLUMNS:
            col_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

            # Header with title and count
            header_label = Gtk.Label()
            header_label.set_xalign(0.0)
            self.col_headers[status] = header_label
            col_box.pack_start(header_label, False, False, 0)

            # Action bar at the top of the column
            action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            action_box.set_size_request(-1, 34)

            if status == "todo":
                self.add_entry = Gtk.Entry()
                self.add_entry.set_placeholder_text("Add a task…")
                self.add_entry.connect("activate", self.on_add_task_submitted)
                action_box.pack_start(self.add_entry, True, True, 0)

                add_btn = Gtk.Button(label="Add")
                add_btn.connect("clicked", self.on_add_task_submitted)
                action_box.pack_start(add_btn, False, False, 0)
            elif status == "done":
                self.clear_finished_btn = Gtk.Button(label="Clear finished")
                self.clear_finished_btn.connect("clicked", self.on_clear_finished)
                action_box.pack_start(self.clear_finished_btn, True, True, 0)
            else:
                # In Progress column has a spacer to keep vertical alignment equal
                spacer = Gtk.Box()
                action_box.pack_start(spacer, True, True, 0)

            col_box.pack_start(action_box, False, False, 0)

            # Scrollable area for stacked tiles
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled.set_shadow_type(Gtk.ShadowType.IN)

            tiles_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            tiles_box.set_border_width(6)
            scrolled.add(tiles_box)
            col_box.pack_start(scrolled, True, True, 0)

            self.col_tiles_boxes[status] = tiles_box

            # Configure drop targets for column and scroll areas
            for drop_widget in (col_box, scrolled, tiles_box):
                drop_widget.drag_dest_set(
                    Gtk.DestDefaults.ALL, [TARGET_ENTRY], Gdk.DragAction.MOVE
                )
                drop_widget.connect("drag-data-received", self.on_drag_data_received, status)

            columns_box.pack_start(col_box, True, True, 0)

        self.refresh_board()
        self.window.show_all()

    def on_window_delete(self, window, _event):
        """Closing the window hides it while the app remains in the tray."""
        window.hide()
        return True

    # ---------------------------------------------------- Board UI Refresh

    def refresh_board(self):
        """Update column counts, empty placeholders, and tile lists."""
        for status, title, placeholder_text in COLUMNS:
            col_tasks = [t for t in self.tasks if t.get("status") == status]
            count = len(col_tasks)

            # Update column header
            header_label = self.col_headers.get(status)
            if header_label:
                header_label.set_markup(f"<b>{title}</b> ({count})")

            # Update tiles container
            tiles_box = self.col_tiles_boxes.get(status)
            if tiles_box:
                for child in tiles_box.get_children():
                    tiles_box.remove(child)

                if count == 0:
                    placeholder = Gtk.Label(label=placeholder_text)
                    placeholder.set_valign(Gtk.Align.CENTER)
                    placeholder.set_halign(Gtk.Align.CENTER)
                    placeholder.set_vexpand(True)
                    placeholder.set_hexpand(True)
                    # Allow dropping directly onto placeholder
                    placeholder.drag_dest_set(
                        Gtk.DestDefaults.ALL, [TARGET_ENTRY], Gdk.DragAction.MOVE
                    )
                    placeholder.connect(
                        "drag-data-received", self.on_drag_data_received, status
                    )
                    tiles_box.pack_start(placeholder, True, True, 24)
                else:
                    for task in col_tasks:
                        tile = self._create_task_tile(task, status)
                        tiles_box.pack_start(tile, False, False, 0)

                tiles_box.show_all()

        if self.clear_finished_btn:
            has_finished = any(t.get("status") == "done" for t in self.tasks)
            self.clear_finished_btn.set_sensitive(has_finished)

    def _create_task_tile(self, task, column_status):
        """Create a bordered tile representing a task (no cancel button)."""
        tile_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tile_box.get_style_context().add_class("task-tile")

        # Draggable event box holding task title
        drag_box = Gtk.EventBox()

        # Tasks can only be dragged if they have a next pane to advance to
        if column_status in NEXT_PANE:
            drag_box.drag_source_set(
                Gdk.ModifierType.BUTTON1_MASK, [TARGET_ENTRY], Gdk.DragAction.MOVE
            )
            drag_box.drag_source_set_icon_name("view-list-symbolic")
            drag_box.connect("drag-data-get", self.on_drag_data_get, task["id"])

        # Allow dropping over an existing tile in this column
        drag_box.drag_dest_set(
            Gtk.DestDefaults.ALL, [TARGET_ENTRY], Gdk.DragAction.MOVE
        )
        drag_box.connect(
            "drag-data-received", self.on_drag_data_received, column_status
        )

        title_label = Gtk.Label(label=task.get("title", ""))
        title_label.set_xalign(0.0)
        title_label.set_line_wrap(True)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        drag_box.add(title_label)

        tile_box.pack_start(drag_box, True, True, 0)
        return tile_box

    # ---------------------------------------------------- Task Actions

    def on_add_task_submitted(self, _widget):
        if not self.add_entry:
            return
        title = self.add_entry.get_text().strip()
        if not title:
            return

        new_task = {
            "id": str(uuid.uuid4()),
            "title": title,
            "status": "todo",
        }
        self.tasks.append(new_task)
        save_tasks(self.tasks)
        self.add_entry.set_text("")
        self.refresh_board()

    def on_clear_finished(self, _button):
        finished = [t for t in self.tasks if t.get("status") == "done"]
        if not finished:
            return
        self.tasks = [t for t in self.tasks if t.get("status") != "done"]
        save_tasks(self.tasks)
        self.refresh_board()

    # -------------------------------------------------- Drag and Drop

    def on_drag_data_get(self, _widget, _context, data, _info, _time, task_id):
        data.set_text(task_id, -1)

    def on_drag_data_received(self, _widget, context, _x, _y, data, _info, time, target_status):
        task_id = data.get_text()
        context.finish(True, False, time)
        if task_id:
            self.move_task(task_id, target_status)

    def move_task(self, task_id, target_status):
        task = next((t for t in self.tasks if t.get("id") == task_id), None)
        if not task:
            return

        current_status = task.get("status")
        # Enforce forward-only movement to the immediate next pane
        if NEXT_PANE.get(current_status) != target_status:
            return

        task["status"] = target_status
        save_tasks(self.tasks)
        self.refresh_board()

        # Notify when moved to Finished
        if target_status == "done":
            self.notify_done(task.get("title", ""))

    def notify_done(self, title):
        message = random.choice(CONGRATS_MESSAGES)
        notification = Notify.Notification.new(
            message, f'"{title}" — completed', "checkbox-checked-symbolic"
        )
        notification.set_urgency(Notify.Urgency.NORMAL)
        try:
            notification.show()
        except GLib.Error as e:
            print(f"[{APP_ID}] Notification failed: {e}")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main():
    app = TaskTrayApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
