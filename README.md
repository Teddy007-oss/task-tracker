# Task Tray

A lightweight, plain Kanban board for Ubuntu GNOME that lives in your top bar.

Features three equal columns (**Tasks**, **In Progress**, **Finished**), native GTK drag-and-drop between columns, quick task entry, single-instance window management, celebratory completion notifications, custom application icon, and atomic JSON persistence.

---

## 1. Required APT Packages (Ubuntu / Debian)

Install the required GTK 3, AppIndicator, notification, and Python GI packages:

```bash
sudo apt update
sudo apt install -y \
  gir1.2-gtk-3.0 \
  gir1.2-ayatanaappindicator3-0.1 \
  gir1.2-notify-0.7 \
  python3-gi
```

> **Note on older Ubuntu releases:** If `gir1.2-ayatanaappindicator3-0.1` is unavailable on your release, install the legacy package instead:
> ```bash
> sudo apt install -y gir1.2-appindicator3-0.3
> ```
> The script automatically falls back to whichever library is installed.

### GNOME Shell Extension (Top Bar Tray Support)

Standard GNOME Shell requires the AppIndicator extension to display tray icons in the top bar:

```bash
sudo apt install -y gnome-shell-extension-appindicator
```

If not already active, enable the extension using the **Extensions** app (or log out and back in).

---

## 2. Installation & Running

Put `task_tray.py` and `icon.png` in your desired location (e.g., `~/task-tray/`):

```bash
mkdir -p ~/task-tray
cp task_tray.py icon.png ~/task-tray/
chmod +x ~/task-tray/task_tray.py
```

Run the application:

```bash
python3 ~/task-tray/task_tray.py
```

- When launched, the board window opens and the custom icon appears in your top bar tray and window titlebar.
- If launched again while already running, it brings the existing window to the front (single instance).

---

## 3. Features & Usage

- **Top Bar Tray Icon**:
  - Displays your custom application icon in the top bar tray.
  - Clicking the icon shows a minimal menu: **Open board** and **Quit**.
  - **Open board** presents the Kanban board window.
  - **Quit** cleanly closes the application.
- **Three Equal Columns**:
  - **Tasks**, **In Progress**, and **Finished**.
  - Each column header shows its title and real-time task count (e.g. `Tasks (3)`).
  - Empty columns display a clean placeholder text.
- **Strict Forward-Only Progression**:
  - Tasks cannot be cancelled once inputted.
  - Tasks can only advance forward to the next pane (**Tasks** → **In Progress** → **Finished**).
  - Backward moves and skipping panes are prohibited.
- **Add Tasks**:
  - An entry and **Add** button sit at the top of the **Tasks** column.
  - Type your task and press **Enter** (or click **Add**) to append it to **Tasks**.
- **Clear Finished**:
  - The **Finished** column includes a **Clear finished** button to remove all completed tasks once they reach the end.
- **Celebratory Desktop Notifications**:
  - Moving a task to **Finished** triggers a celebratory desktop notification with a fun message (e.g., `"🎉 Boom! Task crushed!"`).
- **Window Management**:
  - Closing the window (via the `×` titlebar button) hides it to the tray without quitting.
  - The app remains running in the background until **Quit** is selected from the tray icon menu.
- **Single Instance**:
  - Launching `python3 task_tray.py` again focuses and unhides the existing window rather than spawning duplicate processes.

---

## 4. Data Persistence & Migration

- Tasks are stored in:
  ```
  ~/.local/share/task-tray/tasks.json
  ```
- Each task record format:
  ```json
  {
    "id": "e81d7637-ef86-455c-a5b6-7f41cf134bb8",
    "title": "Calibrate sensors",
    "status": "todo"
  }
  ```
  Allowed statuses: `todo`, `in_progress`, `done`.
- **Atomic saves**: Every change writes to a temporary file before replacing `tasks.json`, guarding against data corruption.
- **Auto-migration**: Legacy task files with `{id, title}` entries are automatically migrated to `status: "todo"` on startup.

---

## 5. Autostart on Login

To launch Task Tray automatically when logging into GNOME:

```bash
mkdir -p ~/.config/autostart
cp task-tray.desktop ~/.config/autostart/
```

Update the paths in `~/.config/autostart/task-tray.desktop` to match your script location:

```bash
sed -i "s|/home/YOUR_USERNAME/task-tray/task_tray.py|$HOME/task-tray/task_tray.py|" ~/.config/autostart/task-tray.desktop
sed -i "s|/home/YOUR_USERNAME/task-tray/icon.png|$HOME/task-tray/icon.png|" ~/.config/autostart/task-tray.desktop
```
