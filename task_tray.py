#!/usr/bin/env python3
"""
Task Tray — a lightweight GNOME top-bar task tracker.

Lives permanently in the system tray using AppIndicator3. Click the icon to
see your tasks; click a task to mark it done (it's removed immediately and
you get a fun congratulatory notification). Tasks persist to a JSON file in
~/.local/share/task-tray/tasks.json between sessions.

Run:
    python3 task_tray.py

See the accompanying README / chat instructions for installing dependencies
and setting up autostart.
"""

import gi
gi.require_version("Gtk", "3.0")

# Prefer AyatanaAppIndicator3 (modern GNOME/Ubuntu), fall back to the older
# AppIndicator3 name if that's what's installed.
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

gi.require_version("Notify", "0.7")
from gi.repository import Gtk, Notify, GLib, GdkPixbuf

import json
import os
import random
import uuid

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

APP_ID = "task-tray"
APP_NAME = "Task Tray"

DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "task-tray")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

# Symbolic icon shown in the top bar. "checkbox-symbolic" isn't shipped by
# every icon theme, so we fall back to a couple of safe, near-universal
# GNOME/Adwaita symbolic names if it's missing.
PREFERRED_ICONS = [
    "checkbox-symbolic",
    "task-due-symbolic",
    "view-list-symbolic",
    "emblem-default-symbolic",
]

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

# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


def ensure_data_dir():
    """Make sure ~/.local/share/task-tray exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_tasks():
    """Load tasks from disk. Returns a list of dicts: {id, title}."""
    ensure_data_dir()
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable file — start fresh rather than crashing.
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
        print(f"[task-tray] Failed to save tasks: {e}")


# --------------------------------------------------------------------------
# Main application
# --------------------------------------------------------------------------


class TaskTrayApp:
    def __init__(self):
        Notify.init(APP_NAME)

        self.tasks = load_tasks()

        self.indicator = AppIndicator3.Indicator.new(
            APP_ID,
            self._pick_icon(),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title(APP_NAME)

        self.menu = Gtk.Menu()
        self.indicator.set_menu(self.menu)
        self.rebuild_menu()

    # ---------------------------------------------------------------- icon

    def _pick_icon(self):
        """Pick the first icon name that actually exists in the current
        icon theme, so we don't end up with a blank/broken tray icon."""
        theme = Gtk.IconTheme.get_default()
        for name in PREFERRED_ICONS:
            if theme.has_icon(name):
                return name
        # Last resort — always present on Linux.
        return "utilities-terminal"

    # ---------------------------------------------------------------- menu

    def rebuild_menu(self):
        """Clear and redraw the dropdown menu from self.tasks."""
        for child in self.menu.get_children():
            self.menu.remove(child)

        if self.tasks:
            for task in self.tasks:
                item = Gtk.MenuItem(label=f"☐  {task['title']}")
                item.connect("activate", self.on_task_clicked, task["id"])
                self.menu.append(item)
        else:
            empty_item = Gtk.MenuItem(label="✨ All done! Add a new task")
            empty_item.set_sensitive(False)
            self.menu.append(empty_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        add_item = Gtk.MenuItem(label="➕ Add task…")
        add_item.connect("activate", self.on_add_task)
        self.menu.append(add_item)

        clear_item = Gtk.MenuItem(label="🗑 Clear all")
        clear_item.connect("activate", self.on_clear_all)
        clear_item.set_sensitive(bool(self.tasks))
        self.menu.append(clear_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_quit)
        self.menu.append(quit_item)

        self.menu.show_all()

    # --------------------------------------------------------------- tasks

    def on_task_clicked(self, _widget, task_id):
        """Mark a task done: remove it, persist, notify, redraw."""
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if task is None:
            return

        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        save_tasks(self.tasks)
        self.rebuild_menu()
        self.notify_done(task["title"])

    def notify_done(self, title):
        message = random.choice(CONGRATS_MESSAGES)
        notification = Notify.Notification.new(message, f'"{title}" — completed', "checkbox-checked-symbolic")
        notification.set_urgency(Notify.Urgency.NORMAL)
        try:
            notification.show()
        except GLib.Error as e:
            print(f"[task-tray] Notification failed: {e}")

    def on_add_task(self, _widget):
        dialog = AddTaskDialog()
        response = dialog.run()
        title = dialog.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and title:
            self.tasks.append({"id": str(uuid.uuid4()), "title": title})
            save_tasks(self.tasks)
            self.rebuild_menu()

    def on_clear_all(self, _widget):
        if not self.tasks:
            return

        confirm = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Clear all tasks?",
        )
        confirm.format_secondary_text(
            f"This will permanently remove all {len(self.tasks)} task(s)."
        )
        response = confirm.run()
        confirm.destroy()

        if response == Gtk.ResponseType.YES:
            self.tasks = []
            save_tasks(self.tasks)
            self.rebuild_menu()

    def on_quit(self, _widget):
        Notify.uninit()
        Gtk.main_quit()


# --------------------------------------------------------------------------
# Add-task dialog
# --------------------------------------------------------------------------


class AddTaskDialog(Gtk.Dialog):
    """A tiny modal dialog with a single text entry for adding a task.
    Pressing Enter in the entry submits the dialog, just like clicking OK."""

    def __init__(self):
        super().__init__(title="Add a new task", transient_for=None, flags=0)
        self.set_default_size(360, 100)
        self.set_border_width(10)

        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        self.set_default_response(Gtk.ResponseType.OK)

        box = self.get_content_area()
        box.set_spacing(8)

        label = Gtk.Label(label="What do you need to get done?")
        label.set_halign(Gtk.Align.START)
        box.add(label)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("e.g. Finish sensor calibration report")
        self.entry.set_activates_default(True)  # Enter key triggers OK
        box.add(self.entry)

        self.show_all()

    def get_text(self):
        return self.entry.get_text()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main():
    app = TaskTrayApp()
    Gtk.main()


if __name__ == "__main__":
    main()
