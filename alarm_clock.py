#!/usr/bin/env python3
import datetime
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
from PyQt6.QtCore import QEvent, QTime, QTimer, QUrl, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


def resource_path(relative_path):
  try:
    base_path = sys._MEIPASS
  except Exception:
    base_path = os.path.abspath(".")
  return os.path.join(base_path, relative_path)


CONFIG_DIR = os.path.expanduser("~/.config/alarm_clock")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
BACKUP_FILE = os.path.join(CONFIG_DIR, "config.json.bak")


def calculate_next_trigger(alarm):
  now = datetime.datetime.now()
  h, m = map(int, alarm["time"].split(":"))
  target_time = datetime.time(h, m)
  candidate = datetime.datetime.combine(now.date(), target_time)

  if alarm["repeat_type"] == "none" or alarm["repeat_type"] == "daily":
    if candidate <= now:
      candidate += datetime.timedelta(days=1)
    return candidate.isoformat()

  elif alarm["repeat_type"] == "weekly":
    days = alarm["repeat_days"]
    if not days:
      if candidate <= now:
        candidate += datetime.timedelta(days=1)
      return candidate.isoformat()

    for i in range(8):
      test_date = candidate + datetime.timedelta(days=i)
      if test_date.weekday() in days and test_date > now:
        return test_date.isoformat()

  elif alarm["repeat_type"] == "monthly":
    target_day = alarm["repeat_date"]
    for i in range(100):
      test_date = candidate + datetime.timedelta(days=i)
      if test_date.day == target_day and test_date > now:
        return test_date.isoformat()

  return candidate.isoformat()


class ConfigManager:

  def __init__(self):
    self.config = {
        "sound_dir": (
            resource_path("assets")
            if hasattr(sys, "_MEIPASS")
            else os.path.expanduser("~/Music")
        ),
        "use_common_sound": True,
        "common_sound_file": "timer.mp3",
        "bedside_settings": {
            "font_family": "Monospace",
            "font_color": "#00ffff",
            "font_size": 80,
            "show_seconds": True,
            "show_countdown": True,
        },
        "alarms": [],
    }
    self.load()

  def load(self):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
      self.save()
      return

    try:
      with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
        self.config.update(data)
        if "bedside_settings" not in self.config:
          self.config["bedside_settings"] = {
              "font_family": "Monospace",
              "font_color": "#00ffff",
              "font_size": 80,
              "show_seconds": True,
              "show_countdown": True,
          }
    except Exception:
      if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, "r") as f:
          self.config.update(json.load(f))

  def save(self):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
      shutil.copy(CONFIG_FILE, BACKUP_FILE)
    with open(CONFIG_FILE, "w") as f:
      json.dump(self.config, f, indent=4)


class AudioManager:

  def __init__(self, config_manager):
    self.config = config_manager
    self.player = QMediaPlayer()
    self.audio_output = QAudioOutput()
    self.player.setAudioOutput(self.audio_output)
    self.fade_timer = QTimer()
    self.fade_timer.timeout.connect(self._fade_step)
    self.target_volume = 1.0
    self.current_volume = 0.0

  def play(self, sound_file, volume=1.0, fade_in=False):
    if not sound_file:
      sound_file = self.config.config.get("common_sound_file") or "timer.mp3"
    path = (
        sound_file
        if os.path.isabs(sound_file)
        else os.path.join(self.config.config["sound_dir"], sound_file)
    )
    if not os.path.exists(path):
      path = resource_path(os.path.join("assets", sound_file))
    if not os.path.exists(path):
      path = resource_path(os.path.join("assets", "timer.mp3"))
    if not os.path.exists(path):
      return

    self.player.setSource(QUrl.fromLocalFile(path))
    self.player.setLoops(QMediaPlayer.Loops.Infinite)

    if fade_in:
      self.target_volume = volume
      self.current_volume = 0.0
      self.audio_output.setVolume(self.current_volume)
      self.player.play()
      self.fade_timer.start(100)
    else:
      self.audio_output.setVolume(volume)
      self.player.play()

  def _fade_step(self):
    self.current_volume += self.target_volume / 20.0
    if self.current_volume >= self.target_volume:
      self.current_volume = self.target_volume
      self.fade_timer.stop()
    self.audio_output.setVolume(self.current_volume)

  def stop(self):
    self.fade_timer.stop()
    self.player.stop()

  def pause(self):
    self.fade_timer.stop()
    self.player.pause()


class NotificationManager:

  @staticmethod
  def send_missed(start_time, end_time):
    try:
      msg = f"Alarm set for {start_time} ended at {end_time}"
      subprocess.Popen([
          "notify-send",
          "-a",
          "Alarm Clock",
          "-u",
          "critical",
          "-t",
          "10000",
          "MISSED ALARM",
          msg,
      ])
    except FileNotFoundError:
      pass


class AlarmDialog(QDialog):

  def __init__(self, config, audio, alarm=None, parent=None):
    super().__init__(parent)
    self.config = config
    self.audio = audio
    self.alarm = alarm
    self.setWindowTitle("Edit Alarm" if alarm else "New Alarm")
    self.audio.player.playbackStateChanged.connect(self.on_playback_state_changed)
    self.setup_ui()
    if self.alarm:
      self.populate()

  def setup_ui(self):
    layout = QVBoxLayout(self)

    time_layout = QHBoxLayout()
    self.hr_combo = QComboBox()
    self.hr_combo.addItems([f"{i:02d}" for i in range(24)])
    self.hr_combo.setFont(QFont("Monospace", 24))

    self.min_combo = QComboBox()
    self.min_combo.addItems([f"{i:02d}" for i in range(60)])
    self.min_combo.setFont(QFont("Monospace", 24))

    colon_lbl = QLabel(":")
    colon_lbl.setFont(QFont("Monospace", 24, QFont.Weight.Bold))

    time_layout.addStretch()
    time_layout.addWidget(self.hr_combo)
    time_layout.addWidget(colon_lbl)
    time_layout.addWidget(self.min_combo)
    time_layout.addStretch()
    layout.addLayout(time_layout)

    self.label_edit = QLineEdit()
    self.label_edit.setPlaceholderText("Alarm Label (e.g., Wake up)")
    layout.addWidget(self.label_edit)

    self.repeat_combo = QComboBox()
    self.repeat_combo.addItems(["none", "daily", "weekly", "monthly"])
    self.repeat_combo.currentTextChanged.connect(self.toggle_repeat_widgets)
    layout.addWidget(self.repeat_combo)

    self.weekly_widget = QWidget()
    week_layout = QHBoxLayout(self.weekly_widget)
    self.day_checks = []
    for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
      chk = QCheckBox(d)
      self.day_checks.append(chk)
      week_layout.addWidget(chk)
    layout.addWidget(self.weekly_widget)

    self.monthly_widget = QWidget()
    month_layout = QHBoxLayout(self.monthly_widget)
    month_layout.addWidget(QLabel("Day of month:"))
    self.day_spin = QSpinBox()
    self.day_spin.setRange(1, 31)
    month_layout.addWidget(self.day_spin)
    layout.addWidget(self.monthly_widget)

    vol_layout = QHBoxLayout()
    vol_layout.addWidget(QLabel("Volume:"))
    self.vol_slider = QSlider(Qt.Orientation.Horizontal)
    self.vol_slider.setRange(0, 100)
    self.vol_slider.setValue(100)
    vol_layout.addWidget(self.vol_slider)
    layout.addLayout(vol_layout)

    snd_layout = QHBoxLayout()
    self.sound_edit = QLineEdit()
    self.sound_edit.setPlaceholderText("sound.wav or Absolute Path")

    btn_browse = QPushButton("Browse")
    btn_browse.clicked.connect(self.browse_sound)

    self.btn_test = QPushButton("Test")
    self.btn_test.clicked.connect(self.toggle_test_sound)

    snd_layout.addWidget(self.sound_edit)
    snd_layout.addWidget(btn_browse)
    snd_layout.addWidget(self.btn_test)

    layout.addWidget(QLabel("Individual Sound File:"))
    layout.addLayout(snd_layout)

    snz_layout = QHBoxLayout()
    snz_layout.addWidget(QLabel("Default Snooze (minutes):"))
    self.snooze_spin = QSpinBox()
    self.snooze_spin.setRange(1, 60)
    self.snooze_spin.setValue(5)
    snz_layout.addWidget(self.snooze_spin)
    layout.addLayout(snz_layout)

    ring_dur_layout = QHBoxLayout()
    ring_dur_layout.addWidget(QLabel("Ring Duration:"))
    self.ring_dur_combo = QComboBox()
    self.ring_dur_combo.addItems([
        "1 minute",
        "2 minutes",
        "3 minutes",
        "4 minutes",
        "5 minutes",
    ])
    self.ring_dur_combo.setCurrentText("1 minute")
    ring_dur_layout.addWidget(self.ring_dur_combo)
    layout.addLayout(ring_dur_layout)

    auto_s_layout = QHBoxLayout()
    self.auto_snooze_chk = QCheckBox("Auto Snooze")
    self.auto_snooze_chk.setChecked(False)

    self.auto_snooze_limit_spin = QSpinBox()
    self.auto_snooze_limit_spin.setRange(1, 20)
    self.auto_snooze_limit_spin.setValue(3)

    auto_s_layout.addWidget(self.auto_snooze_chk)
    auto_s_layout.addWidget(QLabel("Max Auto-Snoozes:"))
    auto_s_layout.addWidget(self.auto_snooze_limit_spin)
    auto_s_layout.addStretch()
    layout.addLayout(auto_s_layout)

    btn_layout = QHBoxLayout()
    btn_save = QPushButton("Save")
    btn_save.clicked.connect(self.save)
    btn_cancel = QPushButton("Cancel")
    btn_cancel.clicked.connect(self.reject)
    btn_layout.addWidget(btn_save)
    btn_layout.addWidget(btn_cancel)
    layout.addLayout(btn_layout)

    self.toggle_repeat_widgets("none")

    now = datetime.datetime.now()
    self.hr_combo.setCurrentText(f"{now.hour:02d}")
    self.min_combo.setCurrentText(f"{now.minute:02d}")

  def keyPressEvent(self, event):
    if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
      self.save()
    elif event.key() == Qt.Key.Key_Escape:
      self.reject()
    else:
      super().keyPressEvent(event)

  def browse_sound(self):
    file, _ = QFileDialog.getOpenFileName(
        self,
        "Select Audio File",
        self.config.config["sound_dir"],
        "Audio Files (*.wav *.mp3 *.ogg *.flac)",
    )
    if file:
      self.sound_edit.setText(file)

  def toggle_test_sound(self):
    if (
        self.audio.player.playbackState()
        == QMediaPlayer.PlaybackState.PlayingState
    ):
      self.audio.stop()
    else:
      vol = self.vol_slider.value() / 100.0
      snd = self.sound_edit.text()
      if not snd and self.config.config["use_common_sound"]:
        snd = self.config.config["common_sound_file"]
      self.audio.play(snd, vol, fade_in=False)

  def on_playback_state_changed(self, state):
    if state == QMediaPlayer.PlaybackState.PlayingState:
      self.btn_test.setText("Stop")
    else:
      self.btn_test.setText("Test")

  def toggle_repeat_widgets(self, mode):
    self.weekly_widget.setVisible(mode == "weekly")
    self.monthly_widget.setVisible(mode == "monthly")

  def populate(self):
    h, m = self.alarm["time"].split(":")
    self.hr_combo.setCurrentText(h)
    self.min_combo.setCurrentText(m)
    self.label_edit.setText(self.alarm["label"])
    self.repeat_combo.setCurrentText(self.alarm["repeat_type"])

    if self.alarm["repeat_type"] == "weekly":
      for i, chk in enumerate(self.day_checks):
        chk.setChecked(i in self.alarm["repeat_days"])
    elif self.alarm["repeat_type"] == "monthly":
      self.day_spin.setValue(self.alarm.get("repeat_date", 1))

    self.sound_edit.setText(self.alarm["sound"])
    self.vol_slider.setValue(int(self.alarm.get("volume", 1.0) * 100))
    self.snooze_spin.setValue(self.alarm.get("snooze_duration", 5))

    dur_min = self.alarm.get("ring_duration_minutes", 1)
    self.ring_dur_combo.setCurrentText(
        f"{dur_min} minute" if dur_min == 1 else f"{dur_min} minutes"
    )

    self.auto_snooze_chk.setChecked(self.alarm.get("auto_snooze", False))
    self.auto_snooze_limit_spin.setValue(
        self.alarm.get("auto_snooze_limit", 3)
    )

  def save(self):
    time_str = f"{self.hr_combo.currentText()}:{self.min_combo.currentText()}"

    days = []
    if self.repeat_combo.currentText() == "weekly":
      days = [i for i, chk in enumerate(self.day_checks) if chk.isChecked()]

    text = self.ring_dur_combo.currentText()
    try:
      ring_dur_min = int("".join(filter(str.isdigit, text)))
    except ValueError:
      ring_dur_min = 1

    new_alarm = {
        "id": self.alarm["id"] if self.alarm else str(uuid.uuid4()),
        "time": time_str,
        "label": self.label_edit.text() or "Alarm",
        "active": True,
        "repeat_type": self.repeat_combo.currentText(),
        "repeat_days": days,
        "repeat_date": self.day_spin.value(),
        "sound": self.sound_edit.text(),
        "volume": self.vol_slider.value() / 100.0,
        "snooze_duration": self.snooze_spin.value(),
        "ring_duration_minutes": ring_dur_min,
        "auto_snooze": self.auto_snooze_chk.isChecked(),
        "auto_snooze_limit": self.auto_snooze_limit_spin.value(),
        "auto_snooze_current": (
            self.alarm.get("auto_snooze_current", 0) if self.alarm else 0
        ),
    }
    new_alarm["next_trigger"] = calculate_next_trigger(new_alarm)

    self.alarm = new_alarm
    self.accept()

  def closeEvent(self, event):
    self.audio.stop()
    try:
      self.audio.player.playbackStateChanged.disconnect(
          self.on_playback_state_changed
      )
    except TypeError:
      pass
    super().closeEvent(event)


class BedsideSettingsDialog(QDialog):

  def __init__(self, config_manager, parent=None):
    super().__init__(parent)
    self.config = config_manager
    self.setWindowTitle("Bedside Clock Settings")
    self.setMinimumWidth(350)
    self.setup_ui()

  def setup_ui(self):
    layout = QVBoxLayout(self)
    settings = self.config.config["bedside_settings"]

    self.font_combo = QComboBox()
    self.font_combo.addItems(["Monospace", "Sans", "Serif", "Arial", "Courier"])
    self.font_combo.setCurrentText(settings.get("font_family", "Monospace"))
    layout.addWidget(QLabel("Font Family:"))
    layout.addWidget(self.font_combo)

    self.color_combo = QComboBox()
    self.color_combo.addItems([
        "#00ffff",
        "#ffffff",
        "#00ff00",
        "#ff00ff",
        "#ff5500",
        "#ffff00",
    ])
    self.color_combo.setCurrentText(settings.get("font_color", "#00ffff"))
    layout.addWidget(QLabel("Font Color:"))
    layout.addWidget(self.color_combo)

    self.size_spin = QSpinBox()
    self.size_spin.setRange(30, 200)
    self.size_spin.setValue(settings.get("font_size", 80))
    layout.addWidget(QLabel("Font Size (Zoom):"))
    layout.addWidget(self.size_spin)

    self.chk_seconds = QCheckBox("Show Seconds")
    self.chk_seconds.setChecked(settings.get("show_seconds", True))
    layout.addWidget(self.chk_seconds)

    self.chk_countdown = QCheckBox("Show Next Alarm Countdown")
    self.chk_countdown.setChecked(settings.get("show_countdown", True))
    layout.addWidget(self.chk_countdown)

    btn_layout = QHBoxLayout()
    btn_save = QPushButton("Save")
    btn_save.clicked.connect(self.save)
    btn_cancel = QPushButton("Cancel")
    btn_cancel.clicked.connect(self.reject)
    btn_layout.addWidget(btn_save)
    btn_layout.addWidget(btn_cancel)
    layout.addLayout(btn_layout)

  def keyPressEvent(self, event):
    if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
      self.save()
    elif event.key() == Qt.Key.Key_Escape:
      self.reject()
    else:
      super().keyPressEvent(event)

  def save(self):
    settings = self.config.config["bedside_settings"]
    settings["font_family"] = self.font_combo.currentText()
    settings["font_color"] = self.color_combo.currentText()
    settings["font_size"] = self.size_spin.value()
    settings["show_seconds"] = self.chk_seconds.isChecked()
    settings["show_countdown"] = self.chk_countdown.isChecked()
    self.config.save()
    self.accept()


class RingDialog(QDialog):

  def __init__(self, alarm, audio, config, parent=None):
    super().__init__(parent)
    self.alarm = alarm
    self.audio = audio
    self.config = config
    self.snoozed = False
    self.missed = False
    self.start_time = alarm["time"]
    self.end_time = ""
    self.snooze_duration = self.alarm.get("snooze_duration", 5)
    self.ring_duration_minutes = self.alarm.get("ring_duration_minutes", 1)
    self.auto_snooze = self.alarm.get("auto_snooze", False)
    self.auto_snooze_limit = self.alarm.get("auto_snooze_limit", 3)
    self.auto_snooze_current = self.alarm.get("auto_snooze_current", 0)

    self.setWindowTitle("ALARM RINGING")
    self.setWindowFlags(
        self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
    )
    self.setup_ui()

    snd = self.alarm["sound"]
    if not snd or self.config.config["use_common_sound"]:
      snd = self.config.config["common_sound_file"]

    self.audio.play(snd, self.alarm.get("volume", 1.0), fade_in=True)

    self.timeout_timer = QTimer(self)
    self.timeout_timer.setInterval(self.ring_duration_minutes * 60000)
    self.timeout_timer.setSingleShot(True)
    self.timeout_timer.timeout.connect(self.auto_timeout)
    self.timeout_timer.start()

  def setup_ui(self):
    layout = QVBoxLayout(self)
    lbl_time = QLabel(self.alarm["time"])
    lbl_time.setFont(QFont("Monospace", 48, QFont.Weight.Bold))
    lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl_time)

    lbl_label = QLabel(self.alarm["label"])
    lbl_label.setFont(QFont("Sans", 24))
    lbl_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl_label)

    btn_stop = QPushButton("STOP (Enter)")
    btn_stop.setFont(QFont("Sans", 16, QFont.Weight.Bold))
    btn_stop.setStyleSheet("background-color: #a00; color: white;")
    btn_stop.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_stop.clicked.connect(self.stop)
    layout.addWidget(btn_stop)

    snz_layout = QHBoxLayout()

    self.snooze_combo = QComboBox()
    self.snooze_combo.setEditable(True)
    self.snooze_combo.addItems([str(i) for i in range(1, 121)])
    self.snooze_combo.setCurrentText(str(self.snooze_duration))
    self.snooze_combo.setFont(QFont("Sans", 14))

    validator = QIntValidator(1, 120, self)
    self.snooze_combo.lineEdit().setValidator(validator)

    self.validation_lbl = QLabel("Constraint: Integers only (1-120)")
    self.validation_lbl.setStyleSheet("color: #d9534f; font-size: 11px;")
    self.validation_lbl.hide()

    self.snooze_combo.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    self.snooze_combo.currentTextChanged.connect(self.on_snooze_edit)

    self.btn_snooze = QPushButton("Snooze (Space)")
    self.btn_snooze.setFont(QFont("Sans", 16))
    self.btn_snooze.setStyleSheet("padding: 6px;")
    self.btn_snooze.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.btn_snooze.clicked.connect(self.snooze)

    snz_layout.addWidget(QLabel("Snooze for (min):"))
    snz_layout.addWidget(self.snooze_combo)
    snz_layout.addWidget(self.btn_snooze)
    layout.addLayout(snz_layout)
    layout.addWidget(self.validation_lbl)

    self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    self.setFocus()

  def keyPressEvent(self, event):
    fw = QApplication.focusWidget()
    if isinstance(fw, QLineEdit):
      super().keyPressEvent(event)
      return

    key = event.key()
    if key == Qt.Key.Key_Space:
      self.snooze()
      event.accept()
    elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
      self.stop()
      event.accept()
    elif key == Qt.Key.Key_Up:
      self.snooze_up()
      event.accept()
    elif key == Qt.Key.Key_Down:
      self.snooze_down()
      event.accept()
    else:
      super().keyPressEvent(event)

  def snooze_up(self):
    try:
      val = int(self.snooze_combo.currentText())
      self.snooze_combo.setCurrentText(str(min(val + 1, 120)))
    except ValueError:
      pass

  def snooze_down(self):
    try:
      val = int(self.snooze_combo.currentText())
      self.snooze_combo.setCurrentText(str(max(val - 1, 1)))
    except ValueError:
      pass

  def on_snooze_edit(self, text):
    self.audio.pause()
    try:
      val = int(text)
      if 1 <= val <= 120:
        self.snooze_duration = val
        self.btn_snooze.setText(f"Snooze ({self.snooze_duration}m)")
        self.validation_lbl.hide()
      else:
        self.validation_lbl.setText("Constraint: Value must be between 1 and 120")
        self.validation_lbl.show()
    except ValueError:
      self.validation_lbl.setText("Constraint: Integers only (1-120)")
      self.validation_lbl.show()

  def auto_timeout(self):
    if self.auto_snooze and self.auto_snooze_current < self.auto_snooze_limit:
      self.alarm["auto_snooze_current"] = self.auto_snooze_current + 1
      self.snoozed = True
      self.audio.stop()
      self.accept()
    else:
      self.alarm["auto_snooze_current"] = 0
      self.missed = True
      self.end_time = datetime.datetime.now().strftime("%H:%M")
      self.audio.stop()
      self.accept()

  def stop(self):
    self.timeout_timer.stop()
    self.alarm["auto_snooze_current"] = 0
    self.audio.stop()
    self.accept()

  def snooze(self):
    self.timeout_timer.stop()
    self.alarm["auto_snooze_current"] = 0
    try:
      self.snooze_duration = int(self.snooze_combo.currentText())
    except ValueError:
      self.snooze_duration = 5
    self.audio.stop()
    self.snoozed = True
    self.accept()

  def closeEvent(self, event):
    self.timeout_timer.stop()
    self.alarm["auto_snooze_current"] = 0
    self.audio.stop()
    super().closeEvent(event)


class MainWindow(QMainWindow):

  def __init__(self):
    super().__init__()
    self.config_manager = ConfigManager()
    self.audio = AudioManager(self.config_manager)
    self.setWindowTitle("Alarm Clock")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_icon = os.path.join(script_dir, "alarm_clock.png")
    if os.path.exists(local_icon):
      app_icon = QIcon(local_icon)
      self.setWindowIcon(app_icon)
      QApplication.instance().setWindowIcon(app_icon)

    self.resize(550, 600)
    self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    self.is_bedside_mode = False

    self.setup_ui()
    self.setup_tray()
    self.refresh_list()

    self.timer = QTimer(self)
    self.timer.timeout.connect(self.check_alarms)
    self.timer.start(1000)

    self.setFocus()

  def setup_ui(self):
    central = QWidget()
    self.setCentralWidget(central)
    self.main_layout = QVBoxLayout(central)

    self.lbl_countdown = QLabel("No active alarms")
    self.lbl_countdown.setFont(QFont("Sans", 14, QFont.Weight.Bold))
    self.lbl_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.main_layout.addWidget(self.lbl_countdown)

    self.bedside_clock_widget = QWidget()
    bedside_layout = QVBoxLayout(self.bedside_clock_widget)
    bedside_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    self.lbl_bedside_time = QLabel("00:00:00")
    self.lbl_bedside_time.setAlignment(Qt.AlignmentFlag.AlignCenter)

    self.lbl_bedside_next = QLabel("Next Alarm: None")
    self.lbl_bedside_next.setAlignment(Qt.AlignmentFlag.AlignCenter)

    bedside_layout.addWidget(self.lbl_bedside_time)
    bedside_layout.addWidget(self.lbl_bedside_next)
    self.bedside_clock_widget.hide()
    self.main_layout.addWidget(self.bedside_clock_widget)

    self.list_widget = QListWidget()
    self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.list_widget.itemActivated.connect(self.edit_alarm)
    self.main_layout.addWidget(self.list_widget)

    self.btn_container = QWidget()
    btn_layout = QHBoxLayout(self.btn_container)
    btn_layout.setContentsMargins(0, 0, 0, 0)
    btn_add = QPushButton("Add Alarm (N)")
    btn_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_add.clicked.connect(self.add_alarm)

    btn_edit = QPushButton("Edit Selected")
    btn_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_edit.clicked.connect(self.edit_alarm)

    btn_del = QPushButton("Delete Selected (D)")
    btn_del.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_del.clicked.connect(self.delete_alarm)

    btn_layout.addWidget(btn_add)
    btn_layout.addWidget(btn_edit)
    btn_layout.addWidget(btn_del)
    self.main_layout.addWidget(self.btn_container)

    global_group = QGroupBox("Global Settings")
    g_layout = QVBoxLayout(global_group)

    dir_layout = QHBoxLayout()
    self.edit_sound_dir = QLineEdit(self.config_manager.config["sound_dir"])
    btn_dir_browse = QPushButton("Browse Dir")
    btn_dir_browse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_dir_browse.clicked.connect(self.browse_dir)
    dir_layout.addWidget(QLabel("Base Sound Dir:"))
    dir_layout.addWidget(self.edit_sound_dir)
    dir_layout.addWidget(btn_dir_browse)
    g_layout.addLayout(dir_layout)

    com_layout = QHBoxLayout()
    self.chk_common = QCheckBox("Use Common Default Sound")
    self.chk_common.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.chk_common.setChecked(
        self.config_manager.config["use_common_sound"]
    )
    self.edit_common = QLineEdit(
        self.config_manager.config["common_sound_file"]
    )
    btn_com_browse = QPushButton("Browse File")
    btn_com_browse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_com_browse.clicked.connect(self.browse_common_file)
    com_layout.addWidget(self.chk_common)
    com_layout.addWidget(self.edit_common)
    com_layout.addWidget(btn_com_browse)
    g_layout.addLayout(com_layout)

    btn_save_globals = QPushButton("Save Global Settings")
    btn_save_globals.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_save_globals.clicked.connect(self.save_globals)
    g_layout.addWidget(btn_save_globals)

    self.global_group_widget = global_group
    self.main_layout.addWidget(self.global_group_widget)

    ctrl_layout = QHBoxLayout()
    btn_bedside = QPushButton("Bedside Clock (F)")
    btn_bedside.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_bedside.setStyleSheet(
        "background-color: #224; color: white; font-weight: bold;"
    )
    btn_bedside.clicked.connect(self.toggle_bedside_mode)

    btn_bedside_settings = QPushButton("Clock Settings (S)")
    btn_bedside_settings.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_bedside_settings.clicked.connect(self.open_bedside_settings)

    btn_tray = QPushButton("Background (M)")
    btn_tray.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_tray.clicked.connect(self.hide)

    ctrl_layout.addWidget(btn_bedside)
    ctrl_layout.addWidget(btn_bedside_settings)
    ctrl_layout.addWidget(btn_tray)
    self.main_layout.addLayout(ctrl_layout)

  def setup_tray(self):
    QApplication.instance().setQuitOnLastWindowClosed(False)
    self.tray_icon = QSystemTrayIcon(self)
    self.tray_icon.setIcon(self.windowIcon())

    tray_menu = QMenu()
    restore_action = QAction("Show / Hide", self)
    restore_action.triggered.connect(self.toggle_window)
    quit_action = QAction("Quit Application (Q)", self)
    quit_action.triggered.connect(QApplication.instance().quit)

    tray_menu.addAction(restore_action)
    tray_menu.addSeparator()
    tray_menu.addAction(quit_action)

    self.tray_icon.setContextMenu(tray_menu)
    self.tray_icon.activated.connect(self.tray_activated)
    self.tray_icon.show()

  def keyPressEvent(self, event):
    fw = QApplication.focusWidget()
    if isinstance(fw, (QLineEdit, QSpinBox, QComboBox)):
      super().keyPressEvent(event)
      return

    key = event.key()
    count = self.list_widget.count()
    row = self.list_widget.currentRow()

    if key == Qt.Key.Key_Up:
      if count > 0:
        new_row = max(0, row - 1) if row >= 0 else 0
        self.list_widget.setCurrentRow(new_row)
      event.accept()
    elif key == Qt.Key.Key_Down:
      if count > 0:
        new_row = min(count - 1, row + 1) if row >= 0 else 0
        self.list_widget.setCurrentRow(new_row)
      event.accept()
    elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
      if count > 0 and row >= 0:
        self.edit_alarm()
      event.accept()
    elif key in (Qt.Key.Key_D, Qt.Key.Key_Delete):
      if count > 0 and row >= 0:
        self.delete_alarm()
      event.accept()
    elif key == Qt.Key.Key_N:
      QTimer.singleShot(0, self.add_alarm)
    elif key == Qt.Key.Key_M:
      self.hide()
    elif key == Qt.Key.Key_Q:
      QApplication.instance().quit()
    elif key == Qt.Key.Key_F:
      self.toggle_bedside_mode()
    elif key == Qt.Key.Key_S:
      self.open_bedside_settings()
    elif key == Qt.Key.Key_Escape and self.is_bedside_mode:
      self.toggle_bedside_mode()
    else:
      super().keyPressEvent(event)

  def toggle_bedside_mode(self):
    self.is_bedside_mode = not self.is_bedside_mode
    if self.is_bedside_mode:
      self.setStyleSheet("background-color: #000;")
      self.lbl_countdown.hide()
      self.list_widget.hide()
      self.btn_container.hide()
      self.global_group_widget.hide()
      self.bedside_clock_widget.show()
      self.showFullScreen()
    else:
      self.setStyleSheet("")
      self.lbl_countdown.show()
      self.list_widget.show()
      self.btn_container.show()
      self.global_group_widget.show()
      self.bedside_clock_widget.hide()
      self.showNormal()
      self.setFocus()

  def open_bedside_settings(self):
    dlg = BedsideSettingsDialog(self.config_manager, self)
    if dlg.exec():
      self.update_countdown()

  def tray_activated(self, reason):
    if reason == QSystemTrayIcon.ActivationReason.Trigger:
      self.toggle_window()

  def toggle_window(self):
    if self.isHidden():
      self.showNormal()
      self.activateWindow()
    else:
      self.hide()

  def refresh_list(self):
    self.list_widget.clear()
    sorted_alarms = sorted(
        enumerate(self.config_manager.config["alarms"]),
        key=lambda x: (
            x[1].get("next_trigger", "9999-12-31")
            if x[1]["active"]
            else "9999-12-31"
        ),
    )

    for orig_idx, alarm in sorted_alarms:
      item = QListWidgetItem()
      widget = QWidget()
      h_layout = QHBoxLayout(widget)
      h_layout.setContentsMargins(5, 5, 5, 5)

      chk_active = QCheckBox()
      chk_active.setFocusPolicy(Qt.FocusPolicy.NoFocus)
      chk_active.setChecked(alarm["active"])
      chk_active.toggled.connect(
          lambda state, idx=orig_idx: self.toggle_active(idx, state)
      )

      bold_font = QFont()
      bold_font.setBold(True)
      lbl_time = QLabel(alarm["time"])
      lbl_time.setFont(bold_font)

      lbl_info = QLabel(f" - {alarm['label']} ({alarm['repeat_type']})")

      h_layout.addWidget(chk_active)
      h_layout.addWidget(lbl_time)
      h_layout.addWidget(lbl_info)
      h_layout.addStretch()

      item.setSizeHint(widget.sizeHint())
      item.setData(Qt.ItemDataRole.UserRole, orig_idx)
      self.list_widget.addItem(item)
      self.list_widget.setItemWidget(item, widget)

    if self.list_widget.count() > 0 and self.list_widget.currentRow() < 0:
      self.list_widget.setCurrentRow(0)

    self.update_countdown()

  def toggle_active(self, index, state):
    alarm = self.config_manager.config["alarms"][index]
    alarm["active"] = state
    if state:
      alarm["next_trigger"] = calculate_next_trigger(alarm)
    self.config_manager.save()
    self.refresh_list()

  def get_selected_original_index(self):
    item = self.list_widget.currentItem()
    if not item:
      return -1
    return item.data(Qt.ItemDataRole.UserRole)

  def add_alarm(self):
    dlg = AlarmDialog(self.config_manager, self.audio, parent=self)
    if dlg.exec():
      self.config_manager.config["alarms"].append(dlg.alarm)
      self.config_manager.save()
      self.refresh_list()
    self.setFocus()

  def edit_alarm(self):
    idx = self.get_selected_original_index()
    if idx < 0:
      return
    alarm = self.config_manager.config["alarms"][idx]
    dlg = AlarmDialog(self.config_manager, self.audio, alarm, parent=self)
    if dlg.exec():
      self.config_manager.config["alarms"][idx] = dlg.alarm
      self.config_manager.save()
      self.refresh_list()
    self.setFocus()

  def delete_alarm(self):
    idx = self.get_selected_original_index()
    if idx < 0:
      return
    alarm = self.config_manager.config["alarms"][idx]
    reply = QMessageBox.question(
        self,
        "Confirm Deletion",
        f"Are you sure you want to delete alarm '{alarm['label']}' at"
        f" {alarm['time']}?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply == QMessageBox.StandardButton.Yes:
      del self.config_manager.config["alarms"][idx]
      self.config_manager.save()
      self.refresh_list()
    self.setFocus()

  def browse_dir(self):
    dir_path = QFileDialog.getExistingDirectory(
        self, "Select Base Sound Directory", self.edit_sound_dir.text()
    )
    if dir_path:
      self.edit_sound_dir.setText(dir_path)

  def browse_common_file(self):
    file, _ = QFileDialog.getOpenFileName(
        self,
        "Select Common Audio File",
        self.edit_sound_dir.text(),
        "Audio Files (*.wav *.mp3 *.ogg *.flac)",
    )
    if file:
      self.edit_common.setText(file)

  def save_globals(self):
    self.config_manager.config["sound_dir"] = self.edit_sound_dir.text()
    self.config_manager.config["use_common_sound"] = self.chk_common.isChecked()
    self.config_manager.config["common_sound_file"] = self.edit_common.text()
    self.config_manager.save()
    QMessageBox.information(
        self, "Settings Saved", "Global settings updated successfully."
    )
    self.setFocus()

  def update_countdown(self):
    now_dt = datetime.datetime.now()
    settings = self.config_manager.config["bedside_settings"]

    f_family = settings.get("font_family", "Monospace")
    f_color = settings.get("font_color", "#00ffff")
    f_size = settings.get("font_size", 80)

    self.lbl_bedside_time.setFont(QFont(f_family, f_size, QFont.Weight.Bold))
    self.lbl_bedside_next.setFont(QFont(f_family, int(f_size / 3.5)))

    time_fmt = "%H:%M:%S" if settings.get("show_seconds", True) else "%H:%M"
    self.lbl_bedside_time.setText(now_dt.strftime(time_fmt))
    self.lbl_bedside_time.setStyleSheet(f"color: {f_color};")
    self.lbl_bedside_next.setStyleSheet(f"color: {f_color};")

    active_alarms = [
        a for a in self.config_manager.config["alarms"] if a["active"]
    ]
    if not active_alarms:
      self.lbl_countdown.setText("No active alarms")
      if settings.get("show_countdown", True):
        self.lbl_bedside_next.setText("Next Alarm: None Set")
        self.lbl_bedside_next.show()
      else:
        self.lbl_bedside_next.hide()
      self.tray_icon.setToolTip("Alarm Clock - No active alarms")
    else:
      next_alarm = min(active_alarms, key=lambda a: a["next_trigger"])
      trigger_dt = datetime.datetime.fromisoformat(next_alarm["next_trigger"])
      diff = trigger_dt - now_dt

      if diff.total_seconds() > 0:
        hours, rem = divmod(diff.seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        days = diff.days

        time_str = f"{days}d " if days > 0 else ""
        time_str += f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

        self.lbl_countdown.setText(f"Next alarm in: {time_str}")
        if settings.get("show_countdown", True):
          self.lbl_bedside_next.setText(
              f"Next: {next_alarm['label']} ({next_alarm['time']}) in"
              f" {time_str}"
          )
          self.lbl_bedside_next.show()
        else:
          self.lbl_bedside_next.hide()
        self.tray_icon.setToolTip(f"Next alarm in: {time_str}")
      else:
        self.lbl_countdown.setText("Alarm ringing soon...")
        if settings.get("show_countdown", True):
          self.lbl_bedside_next.setText("Alarm ringing soon...")
          self.lbl_bedside_next.show()
        else:
          self.lbl_bedside_next.hide()
        self.tray_icon.setToolTip("Alarm ringing soon...")

  def check_alarms(self):
    self.update_countdown()
    now = datetime.datetime.now().isoformat()

    for alarm in self.config_manager.config["alarms"]:
      if alarm["active"] and alarm.get("next_trigger", "") <= now:
        ring_dlg = RingDialog(alarm, self.audio, self.config_manager, self)
        ring_dlg.exec()

        if ring_dlg.snoozed:
          snooze_dt = datetime.datetime.now() + datetime.timedelta(
              minutes=ring_dlg.snooze_duration
          )
          alarm["next_trigger"] = snooze_dt.isoformat()
          alarm["time"] = snooze_dt.strftime("%H:%M")
        elif ring_dlg.missed:
          NotificationManager.send_missed(ring_dlg.start_time, ring_dlg.end_time)
          if alarm["repeat_type"] == "none":
            alarm["active"] = False
          else:
            alarm["next_trigger"] = calculate_next_trigger(alarm)
            alarm["time"] = datetime.datetime.fromisoformat(
                alarm["next_trigger"]
            ).strftime("%H:%M")
        else:
          if alarm["repeat_type"] == "none":
            alarm["active"] = False
          else:
            alarm["next_trigger"] = calculate_next_trigger(alarm)

        self.config_manager.save()
        self.refresh_list()


if __name__ == "__main__":
  os.makedirs(CONFIG_DIR, exist_ok=True)
  lock_file = os.path.join(CONFIG_DIR, "alarm_clock.lock")
  pid_file = os.path.join(CONFIG_DIR, "alarm_clock.pid")

  lock_fp = open(lock_file, "w")
  try:
    fcntl.lockf(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with open(pid_file, "w") as f:
      f.write(str(os.getpid()))
  except IOError:
    try:
      with open(pid_file, "r") as f:
        pid = int(f.read().strip())
      os.kill(pid, signal.SIGUSR1)
    except Exception:
      pass
    sys.exit(0)

  app = QApplication(sys.argv)
  app.setApplicationName("Alarm Clock")
  app.setDesktopFileName("alarm-clock.desktop")
  window = MainWindow()

  def handle_toggle(signum, frame):
    QTimer.singleShot(0, window.toggle_window)

  signal.signal(signal.SIGUSR1, handle_toggle)

  wakeup_timer = QTimer()
  wakeup_timer.timeout.connect(lambda: None)
  wakeup_timer.start(100)

  window.show()
  sys.exit(app.exec())
