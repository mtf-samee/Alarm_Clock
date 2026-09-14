# Alarm Clock

A multi-functional desktop alarm application built with PyQt6, featuring bundled audio assets and native Linux AppImage support. Designed for Wayland on Fedora Linux and compatible with other Linux distributions.

## Quick Start (AppImage)

The easiest way to use the application is via the pre-compiled AppImage, which includes all dependencies and default audio assets.

1. Download the latest `AlarmClock-x86_64.AppImage` from the [Releases](https://github.com/mtf-samee/Alarm_Clock/releases) page.
2. Make the file executable:
   ```bash
   chmod +x AlarmClock-x86_64.AppImage
   ```
3. Run the application:
   ```bash
   ./AlarmClock-x86_64.AppImage
   ```

## Building and Running from Source

If you prefer to run the script directly, install the required dependencies for your distribution.

### 1. Install Dependencies

**Fedora Linux:**
```bash
sudo dnf install python3-pyqt6 libnotify -y
```

**Ubuntu / Debian / Linux Mint:**
```bash
sudo apt install python3-pyqt6 libnotify-bin qt6-wayland -y
```

**Arch Linux:**
```bash
sudo pacman -S python-pyqt6 libnotify qt6-wayland
```

**openSUSE:**
```bash
sudo zypper install python3-PyQt6 libnotify-tools libQt6WaylandClient5 -y
```

### 2. Run the Application
```bash
python3 alarm_clock.py
```

## Packaging the AppImage

To build the AppImage locally, ensure PyInstaller is installed and the `appimagetool` binary is available in your project directory.

1. Clean previous build artifacts:
   ```bash
   rm -rf build dist AlarmClock-x86_64.AppImage
   ```
2. Compile with PyInstaller. The `--add-data` flag bundles the local `assets` directory containing the audio files into the temporary execution path:
   ```bash
   pyinstaller --onedir --noconsole --name=AlarmClock --add-data "assets:assets" alarm_clock.py
   ```
3. Copy compiled files to the AppDir:
   ```bash
   cp -r dist/AlarmClock/* AppDir/usr/bin/
   ```
4. Generate the AppImage:
   ```bash
   ./appimagetool-x86_64.AppImage AppDir AlarmClock-x86_64.AppImage
   ```

## Features

- **Bundled Audio Assets:** Includes a default `timer.mp3` audio asset packaged directly within the application and AppImage. Fallback logic automatically resolves FUSE extraction paths.
- **CLI / Shortcut Toggling:** Running the launch command again seamlessly toggles the backgrounded system tray instance rather than opening duplicates.
- **System Tray Integration:** Runs seamlessly in the background. Minimize/restore via the tray icon or the dedicated background button.
- **Bedside Clock Mode:** Clean, customizable fullscreen digital clock display.
- **Clock Settings:** Configure font families, colors, zoom sizes, seconds display, and countdown indicators.
- **Smart Ringing & Auto-Snooze:** Set custom ring durations (1–5 minutes) and max auto-snooze limits with fallback to missed alarm logs.
- **Missed Alarm Logging:** Critical desktop notifications that auto-dismiss after 10 seconds and persist in system notification history.
- **Input Validation:** Real-time field validation with inline constraint warnings.
- **Smart Countdown Indicator:** Live timer on the main screen showing exactly when the next active alarm will ring.
- **Gentle Wake (Fade-In):** Alarms gradually fade in volume over 2 seconds to prevent sudden jarring noises.
- **Global & Individual Sounds:** Choose a common default sound for all alarms, or assign specific tracks with individual volume levels.
- **Multiple Alarms & Repeat Toggles:** Set unlimited alarms to ring Once, Daily, Weekly, or Monthly.
- **Persistent Configuration:** Automatically saves your alarms and settings locally via JSON (`~/.config/alarm_clock/config.json`).

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `N` | Create a New Alarm |
| `D` or `Delete` | Delete Selected Alarm (with confirmation) |
| `S` | Open Bedside Clock Settings |
| `F` | Toggle Bedside Fullscreen Clock |
| `M` | Minimize to System Tray (Background Mode) |
| `Q` | Quit Application completely |
| `Space` | Snooze (When alarm is ringing) |
| `Enter` | Stop Alarm (When alarm is ringing) / Edit Selected Alarm (When in list) / Save configuration in editors |
| `Up`/`Down` | Navigate Alarm List / Adjust Snooze Time instantly (When alarm is ringing) |
| `Esc` | Exit Bedside Fullscreen |
