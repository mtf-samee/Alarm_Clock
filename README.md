# Alarm Clock

A multi-functional desktop alarm application built with PyQt6. Designed for Wayland on Fedora Linux.

## Requirements

You need `python3-pyqt6` for the application logic and `libnotify` for native Wayland desktop notifications.

```bash
sudo dnf install python3-pyqt6 libnotify -y
```

## Usage

Start the application by running the Python script:

```bash
python3 alarm_clock.py
```

## Features

- **CLI / Shortcut Toggling:** Running the launch command again will seamlessly toggle the backgrounded system tray instance rather than opening duplicates.
- **System Tray Integration:** Run seamlessly in the background. Minimize/restore via the tray icon or the dedicated background button.
- **Smart Countdown Indicator:** Live timer on the main screen showing exactly when the next active alarm will ring.
- **Gentle Wake (Fade-In):** Alarms gradually fade in volume over 2 seconds to prevent sudden jarring noises.
- **On-the-Fly Snooze Editing:** When the alarm rings, adjust the snooze time instantly via dropdown or Up/Down arrows. Doing so pauses the sound.
- **Global & Individual Sounds:** Choose a common default sound for all alarms, or assign specific tracks with individual volume levels.
- **Multiple Alarms & Repeat Toggles:** Set unlimited alarms to ring Once, Daily, Weekly, or Monthly.
- **Persistent Configuration:** Automatically saves your alarms and settings locally via JSON.
- **Native Notifications:** Uses `libnotify` for Wayland native alerts when running in the background.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `N`      | Create a New Alarm |
| `M`      | Minimize to System Tray (Background Mode) |
| `Q`      | Quit the Application completely |
| `Space`  | Snooze (When alarm is ringing) |
| `Enter`  | Stop Alarm (When alarm is ringing) / Save configuration in editors |
| `Up`/`Down`| Adjust Snooze Time instantly (When alarm is ringing) |
