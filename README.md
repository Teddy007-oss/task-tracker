# Task Tray

A lightweight task tracker that lives permanently in the GNOME top bar.

## 1. Install dependencies (Ubuntu)

GNOME 40+ / Ubuntu 22.04+ (uses Ayatana AppIndicator — this is the modern,
actively-maintained fork; the script auto-detects it):

```bash
sudo apt update
sudo apt install -y \
  gir1.2-gtk-3.0 \
  gir1.2-ayatanaappindicator3-0.1 \
  gir1.2-notify-0.7 \
  python3-gi
```

If `gir1.2-ayatanaappindicator3-0.1` isn't found on your version of Ubuntu
(older releases), use the legacy package instead — the script falls back to
it automatically:

```bash
sudo apt install -y gir1.2-appindicator3-0.3
```

### GNOME Shell extension (important!)

Vanilla GNOME Shell hides tray icons (AppIndicators) unless you have the
**AppIndicator and KStatusNotifierItem Support** extension installed:

```bash
sudo apt install -y gnome-shell-extension-appindicator
```

Then log out and back in (or restart GNOME Shell with `Alt+F2` → `r` on
Xorg), and enable the extension via the **Extensions** app if it isn't
already on.

## 2. Get the files

Put `task_tray.py` somewhere permanent, e.g.:

```bash
mkdir -p ~/task-tray
cp task_tray.py ~/task-tray/
chmod +x ~/task-tray/task_tray.py
```

## 3. Run it

```bash
python3 ~/task-tray/task_tray.py
```

You should see an icon appear in the top bar. Click it to see the menu.

Tasks are stored at:

```
~/.local/share/task-tray/tasks.json
```

## 4. Autostart on login

Copy the provided `.desktop` file into your autostart folder, editing the
`Exec` line to match where you put the script:

```bash
mkdir -p ~/.config/autostart
cp task-tray.desktop ~/.config/autostart/
```

Then edit `~/.config/autostart/task-tray.desktop` and replace
`/home/YOUR_USERNAME/task-tray/task_tray.py` with the actual path, e.g.:

```bash
sed -i "s|/home/YOUR_USERNAME/task-tray/task_tray.py|$HOME/task-tray/task_tray.py|" ~/.config/autostart/task-tray.desktop
```

Log out and back in — Task Tray will now start automatically and sit in the
top bar every session.

## 5. Usage

- **Click the tray icon** — opens the menu with all current tasks.
- **Click a task** — marks it done: it's instantly removed and you get a
  fun congratulatory notification (e.g. "🔥 You absolute legend!").
- **➕ Add task…** — opens a small dialog; type your task and press **Enter**
  (or click OK) to add it.
- **🗑 Clear all** — asks for confirmation, then wipes every task.
- **Quit** — exits the app (it won't reappear until you run it again, unless
  autostart is set up).
- When there are no tasks left, the menu shows **"✨ All done! Add a new
  task"**.

## Notes

- Tasks persist between sessions in
  `~/.local/share/task-tray/tasks.json` (plain JSON, easy to back up or
  inspect: `cat ~/.local/share/task-tray/tasks.json`).
- The tray icon auto-selects a symbolic icon that actually exists in your
  current icon theme (tries `checkbox-symbolic` first, with sensible
  fallbacks), so it won't render as a broken/blank icon on themes that lack
  that specific name.
- Writes to disk are atomic (write-then-rename), so a crash mid-save won't
  corrupt your task list.
