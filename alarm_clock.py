#!/usr/bin/env python3
import sys
import os
import json
import uuid
import datetime
import shutil
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QDialog, 
                             QListWidget, QListWidgetItem, QLineEdit, 
                             QFileDialog, QMessageBox, QCheckBox, QComboBox,
                             QTimeEdit, QSpinBox)
from PyQt6.QtCore import Qt, QTimer, QTime, QUrl
from PyQt6.QtGui import QFont, QShortcut, QKeySequence
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
        self.audio_output.setVolume(1.0)

    def play(self, sound_file):
        if not sound_file: return
        path = os.path.join(self.config.config["sound_dir"], sound_file)
        if not os.path.exists(path): return
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def stop(self):
        self.player.stop()

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
        self.setup_ui()
        if self.alarm:
            self.populate()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setFont(QFont("Monospace", 24))
        layout.addWidget(self.time_edit)

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

        snd_layout = QHBoxLayout()
        self.sound_edit = QLineEdit()
        self.sound_edit.setPlaceholderText("sound.wav")
        btn_test = QPushButton("Test")
        btn_test.clicked.connect(lambda: self.audio.play(self.sound_edit.text()))
        snd_layout.addWidget(self.sound_edit)
        snd_layout.addWidget(btn_test)
        layout.addWidget(QLabel("Sound file (in sound dir):"))
        layout.addLayout(snd_layout)

        snz_layout = QHBoxLayout()
        snz_layout.addWidget(QLabel("Snooze (minutes):"))
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

    def toggle_repeat_widgets(self, mode):
        self.weekly_widget.setVisible(mode == "weekly")
        self.monthly_widget.setVisible(mode == "monthly")

    def populate(self):
        h, m = map(int, self.alarm['time'].split(':'))
        self.time_edit.setTime(QTime(h, m))
        self.label_edit.setText(self.alarm['label'])
        self.repeat_combo.setCurrentText(self.alarm['repeat_type'])
        
        if self.alarm['repeat_type'] == 'weekly':
            for i, chk in enumerate(self.day_checks):
                chk.setChecked(i in self.alarm['repeat_days'])
        elif self.alarm['repeat_type'] == 'monthly':
            self.day_spin.setValue(self.alarm.get('repeat_date', 1))
            
        self.sound_edit.setText(self.alarm['sound'])
        self.snooze_spin.setValue(self.alarm.get('snooze_duration', 5))

    def save(self):
        time_str = self.time_edit.time().toString("HH:mm")
        
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
            "snooze_duration": self.snooze_spin.value()
        }
        new_alarm['next_trigger'] = calculate_next_trigger(new_alarm)
        
        self.alarm = new_alarm
        self.accept()

class RingDialog(QDialog):
    def __init__(self, alarm, audio, parent=None):
        super().__init__(parent)
        self.alarm = alarm
        self.audio = audio
        self.snoozed = False
        self.setWindowTitle("ALARM")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setup_ui()
        self.audio.play(self.alarm['sound'])

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

        btn_stop = QPushButton("STOP")
        btn_stop.setFont(QFont("Sans", 16, QFont.Weight.Bold))
        btn_stop.clicked.connect(self.stop)
        
        btn_snooze = QPushButton(f"Snooze ({self.alarm.get('snooze_duration', 5)}m)")
        btn_snooze.setFont(QFont("Sans", 16))
        btn_snooze.clicked.connect(self.snooze)

        layout.addWidget(btn_stop)
        layout.addWidget(btn_snooze)

    def stop(self):
        self.audio.stop()
        self.accept()

    def snooze(self):
        self.audio.stop()
        self.snoozed = True
        self.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.audio = AudioManager(self.config_manager)
        
        self.setWindowTitle("Alarm Clock")
        self.resize(500, 400)
        
        self.setup_ui()
        self.refresh_list()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_alarms)
        self.timer.start(1000)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Add Alarm")
        btn_add.clicked.connect(self.add_alarm)
        btn_edit = QPushButton("Edit Selected")
        btn_edit.clicked.connect(self.edit_alarm)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(self.delete_alarm)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_del)
        layout.addLayout(btn_layout)

        dir_layout = QHBoxLayout()
        self.edit_sound_dir = QLineEdit(self.config_manager.config["sound_dir"])
        btn_dir_save = QPushButton("Save Sound Dir")
        btn_dir_save.clicked.connect(self.save_sound_dir)
        dir_layout.addWidget(QLabel("Sound Directory:"))
        dir_layout.addWidget(self.edit_sound_dir)
        dir_layout.addWidget(btn_dir_save)
        layout.addLayout(dir_layout)

    def refresh_list(self):
        self.list_widget.clear()
        for i, alarm in enumerate(self.config_manager.config["alarms"]):
            item = QListWidgetItem()
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(5, 5, 5, 5)
            
            chk_active = QCheckBox()
            chk_active.setChecked(alarm['active'])
            chk_active.toggled.connect(lambda state, idx=i: self.toggle_active(idx, state))
            
            lbl_info = QLabel(f"{alarm['time']} - {alarm['label']} ({alarm['repeat_type']})")
            
            h_layout.addWidget(chk_active)
            h_layout.addWidget(lbl_info)
            h_layout.addStretch()
            
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def toggle_active(self, index, state):
        alarm = self.config_manager.config["alarms"][index]
        alarm['active'] = state
        if state:
            alarm['next_trigger'] = calculate_next_trigger(alarm)
        self.config_manager.save()

    def add_alarm(self):
        dlg = AlarmDialog(self.config_manager, self.audio, parent=self)
        if dlg.exec():
            self.config_manager.config["alarms"].append(dlg.alarm)
            self.config_manager.save()
            self.refresh_list()

    def edit_alarm(self):
        idx = self.list_widget.currentRow()
        if idx < 0: return
        alarm = self.config_manager.config["alarms"][idx]
        dlg = AlarmDialog(self.config_manager, self.audio, alarm, parent=self)
        if dlg.exec():
            self.config_manager.config["alarms"][idx] = dlg.alarm
            self.config_manager.save()
            self.refresh_list()

    def delete_alarm(self):
        idx = self.list_widget.currentRow()
        if idx < 0: return
        del self.config_manager.config["alarms"][idx]
        self.config_manager.save()
        self.refresh_list()

    def save_sound_dir(self):
        self.config_manager.config["sound_dir"] = self.edit_sound_dir.text()
        self.config_manager.save()

    def check_alarms(self):
        now = datetime.datetime.now().isoformat()
        
        for alarm in self.config_manager.config["alarms"]:
            if alarm['active'] and alarm.get('next_trigger', '') <= now:
                NotificationManager.send("ALARM", alarm['label'])
                
                ring_dlg = RingDialog(alarm, self.audio, self)
                ring_dlg.exec()
                
                if ring_dlg.snoozed:
                    # Calculate snooze target
                    snooze_dt = datetime.datetime.now() + datetime.timedelta(minutes=alarm.get('snooze_duration', 5))
                    alarm['next_trigger'] = snooze_dt.isoformat()
                else:
                    if alarm['repeat_type'] == 'none':
                        alarm['active'] = False
                    else:
                        alarm['next_trigger'] = calculate_next_trigger(alarm)
                        
                self.config_manager.save()
                self.refresh_list()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Alarm Clock")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
