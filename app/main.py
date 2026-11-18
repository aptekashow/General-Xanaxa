import sys
import shutil
import traceback
import numpy as np
import soundfile as sf
import lameenc
import torch
import torchaudio
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QUrl, Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QPlainTextEdit, QFileDialog,
    QMessageBox, QDialog, QLineEdit, QTextEdit, QDialogButtonBox,
    QFrame, QListWidget, QListWidgetItem, QStackedWidget, QButtonGroup, QSplashScreen
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.core.engine import VoiceEngine
from app.services.profiles import ProfileManager
from app.services.history import HistoryManager
from app.paths import APP_DATA_DIR, get_model_path, set_model_path, resource_path


OUTPUT_DIR = APP_DATA_DIR / "audio" / "generated"


class Worker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, function):
        super().__init__()
        self.function = function

    def run(self):
        try:
            result = self.function()
            self.succeeded.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


class AddProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить голос")
        self.setMinimumWidth(520)
        self.audio_path = ""

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Название голосового профиля"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Мой голос")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Аудиозапись с образцом голоса"))
        audio_row = QHBoxLayout()
        self.audio_label = QLabel("Файл не выбран")
        self.audio_label.setWordWrap(True)
        browse = QPushButton("Выбрать аудио")
        browse.clicked.connect(self.choose_audio)
        audio_row.addWidget(self.audio_label, 1)
        audio_row.addWidget(browse)
        layout.addLayout(audio_row)

        layout.addWidget(QLabel("Точная расшифровка того, что произнесено в записи"))
        self.reference_edit = QTextEdit()
        self.reference_edit.setPlaceholderText(
            "Введи текст образца максимально точно, включая слова и окончания."
        )
        self.reference_edit.setMinimumHeight(130)
        layout.addWidget(self.reference_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Создать профиль")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать запись голоса",
            "",
            "Аудиофайлы (*.wav *.flac *.ogg *.mp3);;Все файлы (*.*)"
        )
        if path:
            self.audio_path = path
            self.audio_label.setText(Path(path).name)

    def accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Нет названия", "Укажи название профиля.")
            return
        if not self.audio_path:
            QMessageBox.warning(self, "Нет аудио", "Выбери аудиозапись.")
            return
        if not self.reference_edit.toPlainText().strip():
            QMessageBox.warning(self, "Нет текста", "Введи расшифровку записи.")
            return
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Генерал Ксанакса")
        self.setWindowIcon(QIcon(str(resource_path("assets/icon.ico"))))
        self.resize(920, 700)

        self.engine = VoiceEngine()
        self.profiles = ProfileManager()
        self.history = HistoryManager()
        self.worker = None
        self.last_output = None

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self.build_ui()
        self.refresh_profiles()
        self.refresh_history()

    def build_ui(self):
        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)

        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # Left navigation
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(228)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        side.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_icon = QLabel("✦")
        brand_icon.setObjectName("brandIcon")
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_icon.setFixedSize(42, 42)
        brand_text = QVBoxLayout()
        brand_name = QLabel("Генерал Ксанакса")
        brand_name.setObjectName("brandName")
        brand_caption = QLabel("AI VOICE STUDIO")
        brand_caption.setObjectName("brandCaption")
        brand_text.addWidget(brand_name)
        brand_text.addWidget(brand_caption)
        brand_row.addWidget(brand_icon)
        brand_row.addLayout(brand_text, 1)
        side.addLayout(brand_row)
        side.addSpacing(28)

        nav_caption = QLabel("РАБОЧЕЕ ПРОСТРАНСТВО")
        nav_caption.setObjectName("navCaption")
        side.addWidget(nav_caption)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        nav_items = [
            ("◈", "Озвучивание"),
            ("♬", "Голосовые профили"),
            ("◷", "История"),
            ("⚙", "Настройки"),
        ]
        for index, (glyph, label) in enumerate(nav_items):
            button = QPushButton(f"{glyph}    {label}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav_group.addButton(button, index)
            self.nav_buttons.append(button)
            side.addWidget(button)

        side.addStretch()

        local_note = QFrame()
        local_note.setObjectName("localNote")
        local_layout = QVBoxLayout(local_note)
        local_layout.setContentsMargins(12, 12, 12, 12)
        local_title = QLabel("●  ЛОКАЛЬНАЯ РАБОТА")
        local_title.setObjectName("localTitle")
        local_desc = QLabel("Голосовые данные и синтез остаются на этом компьютере.")
        local_desc.setObjectName("localDesc")
        local_desc.setWordWrap(True)
        local_layout.addWidget(local_title)
        local_layout.addWidget(local_desc)
        side.addWidget(local_note)

        shell.addWidget(sidebar)

        # Main content area
        content = QWidget()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 24, 30, 24)
        content_layout.setSpacing(18)

        topbar = QHBoxLayout()
        heading_box = QVBoxLayout()
        self.page_title = QLabel("Озвучивание")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("Создавайте речь выбранным голосом")
        self.page_subtitle.setObjectName("pageSubtitle")
        heading_box.addWidget(self.page_title)
        heading_box.addWidget(self.page_subtitle)
        topbar.addLayout(heading_box)
        topbar.addStretch()

        self.status_label = QLabel("●  Готово к работе")
        self.status_label.setObjectName("status")
        topbar.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignVCenter)
        content_layout.addLayout(topbar)

        self.pages = QStackedWidget()
        self.pages.setObjectName("pages")
        content_layout.addWidget(self.pages, 1)

        # Page 1: Synthesis
        synth_page = QWidget()
        synth_layout = QVBoxLayout(synth_page)
        synth_layout.setContentsMargins(0, 0, 0, 0)
        synth_layout.setSpacing(16)

        voice_card = QFrame()
        voice_card.setObjectName("panel")
        voice_layout = QVBoxLayout(voice_card)
        voice_layout.setContentsMargins(18, 16, 18, 16)
        voice_heading = QHBoxLayout()
        voice_label_box = QVBoxLayout()
        voice_label = QLabel("АКТИВНЫЙ ГОЛОС")
        voice_label.setObjectName("sectionLabel")
        voice_hint = QLabel("Выберите профиль, которым будет озвучен текст")
        voice_hint.setObjectName("mutedText")
        voice_label_box.addWidget(voice_label)
        voice_label_box.addWidget(voice_hint)
        voice_heading.addLayout(voice_label_box)
        voice_heading.addStretch()
        voice_layout.addLayout(voice_heading)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumHeight(46)
        voice_layout.addWidget(self.profile_combo)
        synth_layout.addWidget(voice_card)

        text_card = QFrame()
        text_card.setObjectName("panel")
        text_layout = QVBoxLayout(text_card)
        text_layout.setContentsMargins(18, 16, 18, 16)
        text_header = QHBoxLayout()
        text_title = QLabel("ТЕКСТ ДЛЯ ОЗВУЧИВАНИЯ")
        text_title.setObjectName("sectionLabel")
        text_header.addWidget(text_title)
        text_header.addStretch()
        self.char_label = QLabel("0 символов")
        self.char_label.setObjectName("mutedText")
        text_header.addWidget(self.char_label)
        text_layout.addLayout(text_header)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("textEditor")
        self.text_edit.setPlaceholderText(
            "Напишите текст, который нужно произнести выбранным голосом..."
        )
        self.text_edit.setMinimumHeight(190)
        self.text_edit.textChanged.connect(self.update_char_count)
        text_layout.addWidget(self.text_edit)
        synth_layout.addWidget(text_card, 1)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        self.synthesize_button = QPushButton("▶   Создать речь")
        self.synthesize_button.setObjectName("primary")
        self.synthesize_button.setMinimumHeight(48)
        self.synthesize_button.clicked.connect(self.synthesize)

        self.play_button = QPushButton("Прослушать")
        self.play_button.setMinimumHeight(48)
        self.play_button.clicked.connect(self.play_audio)

        self.save_button = QPushButton("Сохранить WAV")
        self.save_button.setMinimumHeight(48)
        self.save_button.clicked.connect(self.save_audio)

        self.mp3_button = QPushButton("Сохранить MP3")
        self.mp3_button.setMinimumHeight(48)
        self.mp3_button.clicked.connect(self.save_mp3)

        actions.addWidget(self.synthesize_button, 2)
        actions.addWidget(self.play_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.mp3_button)
        synth_layout.addLayout(actions)

        self.output_label = QLabel("Здесь появится путь к готовой аудиозаписи.")
        self.output_label.setObjectName("output")
        self.output_label.setWordWrap(True)
        synth_layout.addWidget(self.output_label)
        self.pages.addWidget(synth_page)

        # Page 2: Voice profiles
        profiles_page = QWidget()
        profiles_layout = QVBoxLayout(profiles_page)
        profiles_layout.setContentsMargins(0, 0, 0, 0)
        profiles_card = QFrame()
        profiles_card.setObjectName("panel")
        profiles_card_layout = QVBoxLayout(profiles_card)
        profiles_card_layout.setContentsMargins(20, 20, 20, 20)
        profiles_title = QLabel("Ваши голосовые профили")
        profiles_title.setObjectName("cardTitle")
        profiles_hint = QLabel(
            "Создавайте профили из собственных аудиозаписей. "
            "Для каждого образца укажите точную расшифровку."
        )
        profiles_hint.setObjectName("mutedText")
        profiles_hint.setWordWrap(True)
        profiles_card_layout.addWidget(profiles_title)
        profiles_card_layout.addWidget(profiles_hint)
        profiles_card_layout.addSpacing(12)

        self.profile_list = QListWidget()
        self.profile_list.setObjectName("dataList")
        self.profile_list.setMinimumHeight(220)
        self.profile_list.currentRowChanged.connect(self.select_profile_from_list)
        profiles_card_layout.addWidget(self.profile_list, 1)

        profile_actions = QHBoxLayout()
        self.add_profile_button = QPushButton("+  Добавить голос")
        self.add_profile_button.setObjectName("primary")
        self.add_profile_button.setMinimumHeight(46)
        self.add_profile_button.clicked.connect(self.add_profile)
        self.delete_profile_button = QPushButton("Удалить выбранный")
        self.delete_profile_button.setMinimumHeight(46)
        self.delete_profile_button.clicked.connect(self.delete_profile)
        profile_actions.addWidget(self.add_profile_button)
        profile_actions.addWidget(self.delete_profile_button)
        profiles_card_layout.addLayout(profile_actions)
        profiles_layout.addWidget(profiles_card, 1)
        self.pages.addWidget(profiles_page)

        # Page 3: History
        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_card = QFrame()
        history_card.setObjectName("panel")
        history_card_layout = QVBoxLayout(history_card)
        history_card_layout.setContentsMargins(20, 20, 20, 20)
        history_header = QHBoxLayout()
        history_title = QLabel("Недавние записи")
        history_title.setObjectName("cardTitle")
        history_header.addWidget(history_title)
        history_header.addStretch()
        self.clear_history_button = QPushButton("Очистить историю")
        self.clear_history_button.clicked.connect(self.clear_history)
        history_header.addWidget(self.clear_history_button)
        history_card_layout.addLayout(history_header)

        history_hint = QLabel("Дважды щёлкните по записи, чтобы прослушать её.")
        history_hint.setObjectName("mutedText")
        history_card_layout.addWidget(history_hint)
        self.history_list = QListWidget()
        self.history_list.setObjectName("dataList")
        self.history_list.itemDoubleClicked.connect(self.open_history_item)
        history_card_layout.addWidget(self.history_list, 1)
        history_layout.addWidget(history_card, 1)
        self.pages.addWidget(history_page)

        # Page 4: Settings
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_card = QFrame()
        settings_card.setObjectName("panel")
        settings_card_layout = QVBoxLayout(settings_card)
        settings_card_layout.setContentsMargins(20, 20, 20, 20)
        settings_title = QLabel("Настройки экспорта")
        settings_title.setObjectName("cardTitle")
        settings_card_layout.addWidget(settings_title)
        settings_desc = QLabel(
            "Выберите качество MP3. Настройка применяется при следующем экспорте."
        )
        settings_desc.setObjectName("mutedText")
        settings_desc.setWordWrap(True)
        settings_card_layout.addWidget(settings_desc)
        settings_card_layout.addSpacing(12)

        bitrate_label = QLabel("Битрейт MP3")
        bitrate_label.setObjectName("sectionLabel")
        settings_card_layout.addWidget(bitrate_label)
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItem("128 kbps — компактный файл", 128)
        self.bitrate_combo.addItem("192 kbps — сбалансированное качество", 192)
        self.bitrate_combo.addItem("320 kbps — максимальное качество", 320)
        self.bitrate_combo.setCurrentIndex(1)
        self.bitrate_combo.setMinimumHeight(44)
        settings_card_layout.addWidget(self.bitrate_combo)

        settings_card_layout.addSpacing(24)
        local_model_title = QLabel("Локальная модель")
        local_model_title.setObjectName("sectionLabel")
        settings_card_layout.addWidget(local_model_title)
        model_note = QLabel(
            "Синтез выполняется на этом компьютере с использованием "
            "установленной модели Qwen3-TTS и доступного GPU."
        )
        model_note.setObjectName("mutedText")
        model_note.setWordWrap(True)
        settings_card_layout.addWidget(model_note)
        settings_card_layout.addSpacing(12)
        self.model_path_label = QLabel(f"Путь: {get_model_path()}")
        self.model_path_label.setObjectName("mutedText")
        self.model_path_label.setWordWrap(True)
        settings_card_layout.addWidget(self.model_path_label)
        self.model_path_button = QPushButton("Выбрать папку модели Qwen3-TTS")
        self.model_path_button.setMinimumHeight(42)
        self.model_path_button.clicked.connect(self.choose_model_folder)
        settings_card_layout.addWidget(self.model_path_button)
        settings_card_layout.addStretch()
        settings_layout.addWidget(settings_card, 1)
        self.pages.addWidget(settings_page)

        self.nav_group.idClicked.connect(self.navigate)
        self.nav_buttons[0].setChecked(True)
        self.pages.setCurrentIndex(0)

        content_layout.addStretch(0)
        shell.addWidget(content, 1)

        self.setStyleSheet("""
            QWidget#appRoot, QWidget#contentArea {
                background: #10131d;
                color: #e8eaf2;
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QFrame#sidebar {
                background: #151927;
                border-right: 1px solid #252b3b;
            }
            QLabel#brandIcon {
                background: #6658e8;
                color: white;
                border-radius: 13px;
                font-size: 22pt;
                font-weight: 700;
            }
            QLabel#brandName {
                color: #ffffff;
                font-size: 12pt;
                font-weight: 700;
            }
            QLabel#brandCaption, QLabel#navCaption {
                color: #777f98;
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QPushButton#navButton {
                text-align: left;
                color: #aeb5c9;
                background: transparent;
                border: 0;
                border-radius: 9px;
                padding: 13px 12px;
                font-weight: 600;
            }
            QPushButton#navButton:hover {
                color: #ffffff;
                background: #22283a;
            }
            QPushButton#navButton:checked {
                color: #ffffff;
                background: #302b59;
                border-left: 3px solid #887cff;
                padding-left: 9px;
            }
            QFrame#localNote {
                background: #1c2432;
                border: 1px solid #2d394c;
                border-radius: 11px;
            }
            QLabel#localTitle {
                color: #82dfb0;
                font-size: 8pt;
                font-weight: 700;
            }
            QLabel#localDesc, QLabel#mutedText {
                color: #929bb1;
                font-size: 9pt;
            }
            QLabel#pageTitle {
                color: #ffffff;
                font-size: 23pt;
                font-weight: 700;
            }
            QLabel#pageSubtitle {
                color: #929bb1;
                font-size: 10pt;
            }
            QLabel#status {
                color: #9de4bc;
                background: #1c332d;
                border: 1px solid #285342;
                border-radius: 18px;
                padding: 8px 13px;
                font-size: 9pt;
                font-weight: 600;
            }
            QFrame#panel {
                background: #191f2e;
                border: 1px solid #2b3347;
                border-radius: 15px;
            }
            QLabel#sectionLabel {
                color: #a9a2ff;
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#cardTitle {
                color: #f3f4fa;
                font-size: 15pt;
                font-weight: 700;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget {
                background: #111624;
                color: #edf0f8;
                border: 1px solid #343d53;
                border-radius: 9px;
                padding: 10px;
                selection-background-color: #5145bd;
            }
            QPlainTextEdit#textEditor {
                font-size: 11pt;
                line-height: 1.4;
            }
            QComboBox::drop-down {
                border: 0;
                width: 28px;
            }
            QListWidget#dataList {
                padding: 8px;
            }
            QListWidget::item {
                padding: 11px;
                border-radius: 7px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background: #302b59;
                color: white;
            }
            QPushButton {
                background: #293147;
                color: #e8eaf2;
                border: 1px solid #39445c;
                border-radius: 9px;
                padding: 10px 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #35405b;
                border-color: #596584;
            }
            QPushButton:disabled {
                background: #242a39;
                color: #747d93;
                border-color: #30384b;
            }
            QPushButton#primary {
                background: #6658e8;
                color: white;
                border: 1px solid #7669f0;
            }
            QPushButton#primary:hover {
                background: #776bf0;
            }
            QLabel#output {
                color: #a8b0c4;
                padding: 5px 2px;
            }
        """)

    def choose_model_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку Qwen3-TTS-12Hz-0.6B-Base",
            str(get_model_path().parent)
        )
        if not folder:
            return
        selected = Path(folder)
        if not (selected / "config.json").is_file():
            QMessageBox.warning(
                self,
                "Это не папка модели",
                "В выбранной папке не найден config.json. Выберите корневую папку модели Qwen3-TTS."
            )
            return
        set_model_path(selected)
        self.model_path_label.setText(f"Путь: {selected}")
        QMessageBox.information(
            self,
            "Путь сохранён",
            "Путь к модели сохранён. Он будет использован при следующем запуске синтеза."
        )

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        titles = [
            ("Озвучивание", "Создавайте речь выбранным голосом"),
            ("Голосовые профили", "Управляйте сохранёнными голосами"),
            ("История", "Возвращайтесь к ранее созданным записям"),
            ("Настройки", "Настройте экспорт и параметры приложения"),
        ]
        self.page_title.setText(titles[index][0])
        self.page_subtitle.setText(titles[index][1])

    def select_profile_from_list(self, row):
        if row < 0:
            return
        profile_id = self.profile_list.item(row).data(Qt.ItemDataRole.UserRole)
        index = self.profile_combo.findData(profile_id)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)

    def update_char_count(self):
        count = len(self.text_edit.toPlainText())
        self.char_label.setText(f"{count} символов")

    def refresh_profiles(self):
        previous = self.profile_combo.currentData()
        self.profile_combo.clear()

        if hasattr(self, "profile_list"):
            self.profile_list.clear()

        for profile in self.profiles.list_profiles():
            self.profile_combo.addItem(profile["name"], profile["id"])
            if hasattr(self, "profile_list"):
                item = QListWidgetItem("  " + profile["name"])
                item.setData(Qt.ItemDataRole.UserRole, profile["id"])
                self.profile_list.addItem(item)

        if previous:
            index = self.profile_combo.findData(previous)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)

        has_profiles = self.profile_combo.count() > 0
        self.synthesize_button.setEnabled(has_profiles)
        self.delete_profile_button.setEnabled(has_profiles)
        if hasattr(self, "profile_list") and self.profile_list.count():
            self.profile_list.setCurrentRow(0)

    def set_busy(self, busy, message=""):
        self.add_profile_button.setEnabled(not busy)
        self.delete_profile_button.setEnabled(not busy)
        self.synthesize_button.setEnabled(
            not busy and self.profile_combo.count() > 0
        )
        self.mp3_button.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        self.play_button.setEnabled(not busy)
        self.profile_combo.setEnabled(not busy)
        self.status_label.setText(("●  " + message) if busy else "●  Готово к работе")

    def run_task(self, function, on_success, message):
        if self.worker is not None and self.worker.isRunning():
            return

        self.set_busy(True, message)

        worker = Worker(function)
        self.worker = worker

        worker.succeeded.connect(on_success)
        worker.failed.connect(self.show_error)
        worker.finished.connect(lambda: self.task_finished(worker))
        worker.start()

    def task_finished(self, worker):
        if self.worker is worker:
            self.worker = None
        self.set_busy(False)

    def show_error(self, error):
        self.status_label.setText("Ошибка")
        QMessageBox.critical(
            self,
            "Ошибка Генерал Ксанакса",
            error[-5000:]
        )

    def add_profile(self):
        dialog = AddProfileDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = dialog.name_edit.text().strip()
        audio = dialog.audio_path
        reference = dialog.reference_edit.toPlainText().strip()

        def task():
            return self.profiles.create_profile(
                name,
                audio,
                reference,
                self.engine
            )

        def success(profile):
            self.refresh_profiles()
            index = self.profile_combo.findData(profile["id"])
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
            self.status_label.setText("Голосовой профиль создан")
            QMessageBox.information(
                self,
                "Готово",
                f"Профиль «{profile['name']}» успешно создан."
            )

        self.run_task(task, success, "Создаём голосовой профиль...")

    def delete_profile(self):
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return

        name = self.profile_combo.currentText()
        answer = QMessageBox.question(
            self,
            "Удалить голос",
            f"Удалить профиль «{name}» вместе с его файлами?"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        def task():
            self.profiles.delete_profile(profile_id)
            return True

        def success(_):
            self.refresh_profiles()
            self.status_label.setText("Профиль удалён")

        self.run_task(task, success, "Удаляем профиль...")

    def synthesize(self):
        profile_id = self.profile_combo.currentData()
        text = self.text_edit.toPlainText().strip()

        if not profile_id:
            QMessageBox.warning(self, "Нет голоса", "Сначала добавь голосовой профиль.")
            return

        if not text:
            QMessageBox.warning(self, "Нет текста", "Введи текст для озвучивания.")
            return

        output = OUTPUT_DIR / (
            "voice_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".wav"
        )

        def task():
            prompt = self.profiles.load_prompt(profile_id)
            return self.engine.synthesize(text, prompt, str(output))

        def success(path):
            self.last_output = Path(path)

            # Сохраняем завершённый синтез в журнал истории.
            self.history.add(
                text,
                self.profile_combo.currentText(),
                str(path)
            )
            self.refresh_history()

            self.output_label.setText(f"Создан файл: {path}")
            self.status_label.setText("Синтез завершён")
            self.play_audio()

        self.run_task(task, success, "Синтезируем речь...")

    def refresh_history(self):
        if not hasattr(self, "history_list"):
            return

        self.history_list.clear()
        for record in self.history.list():
            created = record.get("created_at", "")
            try:
                created = datetime.fromisoformat(created).strftime("%d.%m.%Y %H:%M")
            except ValueError:
                pass

            text = record.get("text", "").replace("\\n", " ")
            if len(text) > 75:
                text = text[:72] + "..."

            item = QListWidgetItem(
                f"{created}  |  {record.get('profile', 'Голос')}  |  {text}"
            )
            item.setData(Qt.ItemDataRole.UserRole, record.get("audio_path", ""))
            self.history_list.addItem(item)

    def open_history_item(self, item):
        path = Path(item.data(Qt.ItemDataRole.UserRole) or "")
        if not path.is_file():
            QMessageBox.warning(
                self, "Файл не найден",
                "Аудиофайл этой записи больше не существует."
            )
            return

        self.last_output = path
        self.output_label.setText(f"Выбрана запись: {path}")
        self.play_audio()

    def clear_history(self):
        answer = QMessageBox.question(
            self,
            "Очистить историю",
            "Удалить список записей? Сами WAV-файлы останутся на диске."
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self.refresh_history()

    def play_audio(self):
        if not self.last_output or not self.last_output.is_file():
            QMessageBox.information(
                self, "Нет записи", "Сначала синтезируй речь."
            )
            return

        self.player.setSource(QUrl.fromLocalFile(str(self.last_output)))
        self.player.play()

    def save_audio(self):
        if not self.last_output or not self.last_output.is_file():
            QMessageBox.information(
                self, "Нет записи", "Сначала синтезируй речь."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить аудио",
            "Генерал Ксанакса.wav",
            "WAV (*.wav)"
        )

        if path:
            if not path.lower().endswith(".wav"):
                path += ".wav"
            shutil.copy2(self.last_output, path)
            QMessageBox.information(
                self, "Сохранено", f"Файл сохранён:\n{path}"
            )



    def save_mp3(self):
        if not self.last_output or not self.last_output.is_file():
            QMessageBox.information(
                self,
                "\u041d\u0435\u0442 \u0437\u0430\u043f\u0438\u0441\u0438",
                "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0441\u0438\u043d\u0442\u0435\u0437\u0438\u0440\u0443\u0439 \u0440\u0435\u0447\u044c."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c MP3",
            "Генерал Ксанакса.mp3",
            "MP3 (*.mp3)"
        )

        if not path:
            return

        if not path.lower().endswith(".mp3"):
            path += ".mp3"

        try:
            audio, sample_rate = sf.read(
                str(self.last_output),
                dtype="float32",
                always_2d=True
            )

            # ????????? 24 ??? ? 44,1 ??? ??? ?????????
            # ???? ???? ????????? ????????? MP3.
            waveform = torch.from_numpy(audio.T.copy())

            if sample_rate != 44100:
                waveform = torchaudio.functional.resample(
                    waveform,
                    orig_freq=int(sample_rate),
                    new_freq=44100
                )

            audio = waveform.T.cpu().numpy()
            audio = np.clip(audio, -1.0, 1.0)
            pcm = (audio * 32767).astype(np.int16)

            encoder = lameenc.Encoder()
            encoder.set_bit_rate(int(self.bitrate_combo.currentData()))
            encoder.set_in_sample_rate(44100)
            encoder.set_channels(int(pcm.shape[1]))
            encoder.set_quality(2)

            mp3_data = encoder.encode(pcm.tobytes())
            mp3_data += encoder.flush()

            Path(path).write_bytes(mp3_data)

            QMessageBox.information(
                self,
                "\u0413\u043e\u0442\u043e\u0432\u043e",
                f"MP3 \u0441\u043e\u0445\u0440\u0430\u043d\u0451\u043d:\\n{path}"
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "\u041e\u0448\u0438\u0431\u043a\u0430 MP3",
                str(error)
            )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Генерал Ксанакса")
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(QIcon(str(resource_path("assets/icon.ico"))))

    splash_pixmap = QPixmap(str(resource_path("assets/splash.png")))
    splash = QSplashScreen(splash_pixmap.scaled(
        760, 470, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    ))
    splash.show()
    app.processEvents()

    window = MainWindow()
    window.show()
    splash.finish(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
