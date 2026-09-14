# Alarm Clock

A multi-functional desktop alarm application built with PyQt6. Designed for Wayland on Fedora Linux and compatible with other Linux distributions.

## Requirements

### Fedora Linux
```bash
sudo dnf install python3-pyqt6 libnotify -y
```

### Ubuntu / Debian / Linux Mint
```bash
sudo apt install python3-pyqt6 libnotify-bin qt6-wayland -y
```

### Arch Linux
```bash
sudo pacman -S python-pyqt6 libnotify qt6-wayland
```

### openSUSE
```bash
sudo zypper install python3-PyQt6 libnotify-tools libQt6WaylandClient5 -y
```

## Usage

Start the application by running the Python script:

```bash
python3 alarm_clock.py
```

## Features

- **CLI / Shortcut Toggling:** Running the launch command again will seamlessly toggle the backgrounded system tray instance rather than opening duplicates.
- **System Tray Integration:** Run seamlessly in the background. Minimize/restore via the tray icon or the dedicated background button.
- **Bedside Clock Mode:** Clean, customizable fullscreen digital clock display (`F`).
- **Clock Settings:** Configure font families, colors, zoom sizes, seconds display, and countdown indicators (`S`).
- **Smart Ringing & Auto-Snooze:** Set custom ring durations (1–5 minutes) and max auto-snooze limits with fallback to missed alarm logs.
- **Missed Alarm Logging:** Critical desktop notifications that auto-dismiss after 10 seconds and persist in system notification history.
- **Input Validation:** Real-time field validation with inline constraint warnings.
- **Smart Countdown Indicator:** Live timer on the main screen showing exactly when the next active alarm will ring.
- **Gentle Wake (Fade-In):** Alarms gradually fade in volume over 2 seconds to prevent sudden jarring noises.
- **Global & Individual Sounds:** Choose a common default sound for all alarms, or assign specific tracks with individual volume levels.
- **Multiple Alarms & Repeat Toggles:** Set unlimited alarms to ring Once, Daily, Weekly, or Monthly.
- **Persistent Configuration:** Automatically saves your alarms and settings locally via JSON.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `N`      | Create a New Alarm |
| `D` or `Delete` | Delete Selected Alarm (with confirmation) |
| `S`      | Open Bedside Clock Settings |
| `F`      | Toggle Bedside Fullscreen Clock |
| `M`      | Minimize to System Tray (Background Mode) |
| `Q`      | Quit Application completely |
| `Space`  | Snooze (When alarm is ringing) |
| `Enter`  | Stop Alarm (When alarm is ringing) / Edit Selected Alarm (When in list) / Save configuration in editors |
| `Up`/`Down`| Navigate Alarm List / Adjust Snooze Time instantly (When alarm is ringing) |
| `Esc`    | Exit Bedside Fullscreen |
