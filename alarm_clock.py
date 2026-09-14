#!/usr/bin/env python3
import sys
import os
import json
import uuid
import datetime
import shutil
import subprocess
import fcntl
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QDialog,
                             QListWidget, QListWidgetItem, QLineEdit,
                             QMessageBox, QCheckBox, QComboBox, QFileDialog,
                             QSpinBox, QSystemTrayIcon, QMenu, QSlider, QStyle, QGroupBox)
from PyQt6.QtCore import Qt, QTimer, QTime, QUrl
from PyQt6.QtGui import QFont, QIcon, QAction, QShortcut, QKeySequence
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

CONFIG_DIR = os.path.expanduser("~/.config/alarm_clock")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
BACKUP_FILE = os.path.join(CONFIG_DIR, "config.json.bak")

def calculate_next_trigger(alarm):
    now = datetime.datetime.now()
    h, m = map(int, alarm['time'].split(':'))
    target_time = datetime.time(h, m)
    candidate = datetime.datetime.combine(now.date(), target_time)

    if alarm['repeat_type'] == 'none' or alarm['repeat_type'] == 'daily':
        if candidate <= now:
            candidate += datetime.timedelta(days=1)
        return candidate.isoformat()

    elif alarm['repeat_type'] == 'weekly':
        days = alarm['repeat_days']
        if not days:
            if candidate <= now: candidate += datetime.timedelta(days=1)
            return candidate.isoformat()

        for i in range(8):
            test_date = candidate + datetime.timedelta(days=i)
            if test_date.weekday() in days and test_date > now:
                return test_date.isoformat()

    elif alarm['repeat_type'] == 'monthly':
        target_day = alarm['repeat_date']
        for i in range(100):
            test_date = candidate + datetime.timedelta(days=i)
            if test_date.day == target_day and test_date > now:
                return test_date.isoformat()

    return candidate.isoformat()

class ConfigManager:
    def __init__(self):
        self.config = {
            "sound_dir": os.path.expanduser("~/Music"),
            "use_common_sound": False,
            "common_sound_file": "",
            "alarms": []
        }
        self.load()

    def load(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if not os.path.exists(CONFIG_FILE):
            self.save()
            return

        try:
            with open(CONFIG_FILE, 'r') as f:
                self.config.update(json.load(f))
        except Exception:
            if os.path.exists(BACKUP_FILE):
                with open(BACKUP_FILE, 'r') as f:
                    self.config.update(json.load(f))

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if os.path.exists(CONFIG_FILE):
            shutil.copy(CONFIG_FILE, BACKUP_FILE)
        with open(CONFIG_FILE, 'w') as f:
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
        if not sound_file: return
        path = sound_file if os.path.isabs(sound_file) else os.path.join(self.config.config["sound_dir"], sound_file)
        if not os.path.exists(path): return

        self.player.setSource(QUrl.fromLocalFile(path))

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
    def send(title, message):
        try:
            subprocess.Popen(['notify-send', '-a', 'Alarm Clock', '-u', 'critical', title, message])
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

    def browse_sound(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Audio File", self.config.config["sound_dir"], "Audio Files (*.wav *.mp3 *.ogg *.flac)")
        if file:
            self.sound_edit.setText(file)

    def toggle_test_sound(self):
        if self.audio.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
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
        h, m = self.alarm['time'].split(':')
        self.hr_combo.setCurrentText(h)
        self.min_combo.setCurrentText(m)
        self.label_edit.setText(self.alarm['label'])
        self.repeat_combo.setCurrentText(self.alarm['repeat_type'])

        if self.alarm['repeat_type'] == 'weekly':
            for i, chk in enumerate(self.day_checks):
                chk.setChecked(i in self.alarm['repeat_days'])
        elif self.alarm['repeat_type'] == 'monthly':
            self.day_spin.setValue(self.alarm.get('repeat_date', 1))

        self.sound_edit.setText(self.alarm['sound'])
        self.vol_slider.setValue(int(self.alarm.get('volume', 1.0) * 100))
        self.snooze_spin.setValue(self.alarm.get('snooze_duration', 5))

    def save(self):
        time_str = f"{self.hr_combo.currentText()}:{self.min_combo.currentText()}"

        days = []
        if self.repeat_combo.currentText() == "weekly":
            days = [i for i, chk in enumerate(self.day_checks) if chk.isChecked()]

        new_alarm = {
            "id": self.alarm['id'] if self.alarm else str(uuid.uuid4()),
            "time": time_str,
            "label": self.label_edit.text() or "Alarm",
            "active": True,
            "repeat_type": self.repeat_combo.currentText(),
            "repeat_days": days,
            "repeat_date": self.day_spin.value(),
            "sound": self.sound_edit.text(),
            "volume": self.vol_slider.value() / 100.0,
            "snooze_duration": self.snooze_spin.value()
        }
        new_alarm['next_trigger'] = calculate_next_trigger(new_alarm)

        self.alarm = new_alarm
        self.accept()

    def closeEvent(self, event):
        self.audio.stop()
        try:
            self.audio.player.playbackStateChanged.disconnect(self.on_playback_state_changed)
        except TypeError:
            pass
        super().closeEvent(event)

class RingDialog(QDialog):
    def __init__(self, alarm, audio, config, parent=None):
        super().__init__(parent)
        self.alarm = alarm
        self.audio = audio
        self.config = config
        self.snoozed = False
        self.snooze_duration = self.alarm.get('snooze_duration', 5)
        self.setWindowTitle("ALARM RINGING")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setup_ui()

        snd = self.alarm['sound']
        if not snd or self.config.config["use_common_sound"]:
            snd = self.config.config["common_sound_file"]

        self.audio.play(snd, self.alarm.get('volume', 1.0), fade_in=True)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        lbl_time = QLabel(self.alarm['time'])
        lbl_time.setFont(QFont("Monospace", 48, QFont.Weight.Bold))
        lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_time)

        lbl_label = QLabel(self.alarm['label'])
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
        self.snooze_spin = QSpinBox()
        self.snooze_spin.setRange(1, 120)
        self.snooze_spin.setValue(self.snooze_duration)
        self.snooze_spin.setFont(QFont("Sans", 14))
        self.snooze_spin.valueChanged.connect(self.on_snooze_edit)

        self.btn_snooze = QPushButton("Snooze (Space)")
        self.btn_snooze.setFont(QFont("Sans", 16))
        self.btn_snooze.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_snooze.clicked.connect(self.snooze)

        snz_layout.addWidget(QLabel("Snooze for (min):"))
        snz_layout.addWidget(self.snooze_spin)
        snz_layout.addWidget(self.btn_snooze)
        layout.addLayout(snz_layout)

    def keyPressEvent(self, event):
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QSpinBox, QComboBox)):
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_Space:
            self.snooze()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.stop()
        else:
            super().keyPressEvent(event)

    def on_snooze_edit(self):
        self.audio.pause()
        self.snooze_duration = self.snooze_spin.value()
        self.btn_snooze.setText(f"Snooze ({self.snooze_duration}m)")

    def stop(self):
        self.audio.stop()
        self.accept()

    def snooze(self):
        self.snooze_duration = self.snooze_spin.value()
        self.audio.stop()
        self.snoozed = True
        self.accept()

    def closeEvent(self, event):
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
        layout = QVBoxLayout(central)

        self.lbl_countdown = QLabel("No active alarms")
        self.lbl_countdown.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        self.lbl_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_countdown)

        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Add Alarm (N)")
        btn_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_add.clicked.connect(self.add_alarm)

        btn_edit = QPushButton("Edit Selected")
        btn_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_edit.clicked.connect(self.edit_alarm)

        btn_del = QPushButton("Delete Selected")
        btn_del.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_del.clicked.connect(self.delete_alarm)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_del)
        layout.addLayout(btn_layout)

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
        self.chk_common.setChecked(self.config_manager.config["use_common_sound"])
        self.edit_common = QLineEdit(self.config_manager.config["common_sound_file"])
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

        layout.addWidget(global_group)

        btn_tray = QPushButton("Run in Background / Minimize (M)")
        btn_tray.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_tray.clicked.connect(self.hide)
        layout.addWidget(btn_tray)

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
        if key == Qt.Key.Key_N:
            QTimer.singleShot(0, self.add_alarm)
        elif key == Qt.Key.Key_M:
            self.hide()
        elif key == Qt.Key.Key_Q:
            QApplication.instance().quit()
        else:
            super().keyPressEvent(event)

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
            key=lambda x: x[1].get('next_trigger', '9999-12-31') if x[1]['active'] else '9999-12-31'
        )

        for orig_idx, alarm in sorted_alarms:
            item = QListWidgetItem()
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(5, 5, 5, 5)

            chk_active = QCheckBox()
            chk_active.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            chk_active.setChecked(alarm['active'])
            chk_active.toggled.connect(lambda state, idx=orig_idx: self.toggle_active(idx, state))

            bold_font = QFont()
            bold_font.setBold(True)
            lbl_time = QLabel(alarm['time'])
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

        self.update_countdown()

    def toggle_active(self, index, state):
        alarm = self.config_manager.config["alarms"][index]
        alarm['active'] = state
        if state:
            alarm['next_trigger'] = calculate_next_trigger(alarm)
        self.config_manager.save()
        self.refresh_list()

    def get_selected_original_index(self):
        item = self.list_widget.currentItem()
        if not item: return -1
        return item.data(Qt.ItemDataRole.UserRole)

    def add_alarm(self):
        dlg = AlarmDialog(self.config_manager, self.audio, parent=self)
        if dlg.exec():
            self.config_manager.config["alarms"].append(dlg.alarm)
            self.config_manager.save()
            self.refresh_list()

    def edit_alarm(self):
        idx = self.get_selected_original_index()
        if idx < 0: return
        alarm = self.config_manager.config["alarms"][idx]
        dlg = AlarmDialog(self.config_manager, self.audio, alarm, parent=self)
        if dlg.exec():
            self.config_manager.config["alarms"][idx] = dlg.alarm
            self.config_manager.save()
            self.refresh_list()

    def delete_alarm(self):
        idx = self.get_selected_original_index()
        if idx < 0: return
        del self.config_manager.config["alarms"][idx]
        self.config_manager.save()
        self.refresh_list()

    def browse_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Base Sound Directory", self.edit_sound_dir.text())
        if dir_path:
            self.edit_sound_dir.setText(dir_path)

    def browse_common_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Common Audio File", self.edit_sound_dir.text(), "Audio Files (*.wav *.mp3 *.ogg *.flac)")
        if file:
            self.edit_common.setText(file)

    def save_globals(self):
        self.config_manager.config["sound_dir"] = self.edit_sound_dir.text()
        self.config_manager.config["use_common_sound"] = self.chk_common.isChecked()
        self.config_manager.config["common_sound_file"] = self.edit_common.text()
        self.config_manager.save()
        QMessageBox.information(self, "Settings Saved", "Global settings updated successfully.")
        self.setFocus()

    def update_countdown(self):
        active_alarms = [a for a in self.config_manager.config["alarms"] if a['active']]
        if not active_alarms:
            self.lbl_countdown.setText("No active alarms")
            self.tray_icon.setToolTip("Alarm Clock - No active alarms")
        else:
            now = datetime.datetime.now()
            next_alarm = min(active_alarms, key=lambda a: a['next_trigger'])
            trigger_dt = datetime.datetime.fromisoformat(next_alarm['next_trigger'])
            diff = trigger_dt - now

            if diff.total_seconds() > 0:
                hours, rem = divmod(diff.seconds, 3600)
                minutes, seconds = divmod(rem, 60)
                days = diff.days

                time_str = f"{days}d " if days > 0 else ""
                time_str += f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
                self.lbl_countdown.setText(f"Next alarm in: {time_str}")
                self.tray_icon.setToolTip(f"Next alarm in: {time_str}")
            else:
                self.lbl_countdown.setText("Alarm ringing soon...")
                self.tray_icon.setToolTip("Alarm ringing soon...")

    def check_alarms(self):
        self.update_countdown()
        now = datetime.datetime.now().isoformat()

        for alarm in self.config_manager.config["alarms"]:
            if alarm['active'] and alarm.get('next_trigger', '') <= now:
                if self.isHidden():
                    NotificationManager.send("ALARM", alarm['label'])

                ring_dlg = RingDialog(alarm, self.audio, self.config_manager, self)
                ring_dlg.exec()

                if ring_dlg.snoozed:
                    snooze_dt = datetime.datetime.now() + datetime.timedelta(minutes=ring_dlg.snooze_duration)
                    alarm['next_trigger'] = snooze_dt.isoformat()
                else:
                    if alarm['repeat_type'] == 'none':
                        alarm['active'] = False
                    else:
                        alarm['next_trigger'] = calculate_next_trigger(alarm)

                self.config_manager.save()
                self.refresh_list()

if __name__ == "__main__":
    os.makedirs(CONFIG_DIR, exist_ok=True)
    lock_file = os.path.join(CONFIG_DIR, "alarm_clock.lock")
    lock_fp = open(lock_file, 'w')
    try:
        fcntl.lockf(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("Alarm Clock is already running.")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName("Alarm Clock")
    app.setDesktopFileName("alarm-clock.desktop")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
