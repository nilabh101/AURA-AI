import os
import sys
import base64
import threading
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QComboBox, QFileDialog, QMessageBox,
    QCheckBox
)

try:
    import keyboard
except ImportError:
    keyboard = None

load_dotenv(Path(__file__).with_name(".env"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


class Signals(QObject):
    result = Signal(str)
    status = Signal(str)


class AuraAI(QWidget):
    def __init__(self):
        super().__init__()
        self.client = None
        self.screenshot_path = None
        self._hotkey_registered = False
        self.signals = Signals()
        self.signals.result.connect(self.on_result)
        self.signals.status.connect(self.set_status)

        self.setWindowTitle("AURA AI")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Window
        )
        self.resize(470, 690)
        self.setMinimumSize(390, 500)
        self.setStyleSheet("""
            QWidget { background:#151821; color:#F2F4F8; font-size:13px; }
            QLabel#brand { font-size:24px; font-weight:700; }
            QLabel#muted { color:#AAB2C5; }
            QTextEdit, QComboBox {
                background:#202531; border:1px solid #343B4B;
                border-radius:9px; padding:9px; selection-background-color:#6478F7;
            }
            QPushButton {
                background:#6478F7; color:white; border:0;
                border-radius:8px; padding:10px; font-weight:600;
            }
            QPushButton:hover { background:#7889FF; }
            QPushButton:disabled { background:#3A4050; color:#9AA2B4; }
            QPushButton#secondary { background:#2B3140; }
            QPushButton#secondary:hover { background:#383F50; }
            QCheckBox { color:#D8DCE6; spacing:8px; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        brand = QLabel("AURA AI")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch()
        self.presentation_btn = QPushButton("Presentation mode")
        self.presentation_btn.setObjectName("secondary")
        self.presentation_btn.clicked.connect(self.presentation_mode)
        header.addWidget(self.presentation_btn)
        root.addLayout(header)

        tagline = QLabel("Your on-screen study and creator companion")
        tagline.setObjectName("muted")
        root.addWidget(tagline)

        self.mode = QComboBox()
        self.mode.addItems([
            "Study & Notes", "Video & Creator", "Interview Practice",
            "Explain a Concept", "General Assistant"
        ])
        root.addWidget(self.mode)

        root.addWidget(QLabel("What should AURA help with?"))
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText(
            "Ask a question, paste notes/transcript, or describe what's on screen..."
        )
        self.prompt.setMinimumHeight(105)
        root.addWidget(self.prompt)

        row = QHBoxLayout()
        self.capture_btn = QPushButton("Capture screen")
        self.capture_btn.clicked.connect(self.capture_screen)
        row.addWidget(self.capture_btn)
        self.attach_btn = QPushButton("Attach file")
        self.attach_btn.setObjectName("secondary")
        self.attach_btn.clicked.connect(self.attach_file)
        row.addWidget(self.attach_btn)
        root.addLayout(row)

        self.capture_label = QLabel("No screenshot attached")
        self.capture_label.setObjectName("muted")
        root.addWidget(self.capture_label)

        self.include_screen = QCheckBox("Include captured screenshot with my question")
        self.include_screen.setChecked(True)
        root.addWidget(self.include_screen)

        actions = QHBoxLayout()
        self.ask_btn = QPushButton("Ask AURA")
        self.ask_btn.clicked.connect(self.ask_ai)
        actions.addWidget(self.ask_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("secondary")
        self.clear_btn.clicked.connect(self.clear_all)
        actions.addWidget(self.clear_btn)
        root.addLayout(actions)

        root.addWidget(QLabel("AURA's response"))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Responses and error messages appear here.")
        root.addWidget(self.output, 1)

        footer = QHBoxLayout()
        self.status = QLabel("Ready")
        self.status.setObjectName("muted")
        footer.addWidget(self.status, 1)
        self.hotkey_label = QLabel("Ctrl + Space")
        self.hotkey_label.setObjectName("muted")
        footer.addWidget(self.hotkey_label)
        root.addLayout(footer)

        self.register_hotkey()

    def register_hotkey(self):
        if keyboard is None:
            self.hotkey_label.setText("Hotkey unavailable")
            return
        try:
            keyboard.add_hotkey("ctrl+space", self.toggle_from_hotkey)
            self._hotkey_registered = True
        except Exception:
            self.hotkey_label.setText("Hotkey unavailable")

    def toggle_from_hotkey(self):
        # Schedule all UI work on the Qt main thread.
        QTimer.singleShot(0, self.toggle_visibility)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def presentation_mode(self):
        # Explicit user-controlled hiding; does not attempt to evade monitoring.
        self.hide()
        self.signals.status.emit(
            "Hidden for presentation. Use Ctrl + Space or the taskbar to reopen."
        )

    def capture_screen(self):
        self.hide()
        self.set_status("Capturing screen in a moment...")
        QTimer.singleShot(700, self.finish_capture)

    def finish_capture(self):
        try:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                raise RuntimeError("No display was detected.")
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                raise RuntimeError("Screenshot capture returned an empty image.")
            path = Path(__file__).with_name("aura_capture.png")
            if not pixmap.save(str(path), "PNG"):
                raise RuntimeError("Could not save screenshot.")
            self.screenshot_path = str(path)
            self.capture_label.setText("Screenshot captured: aura_capture.png")
            self.show()
            self.raise_()
            self.activateWindow()
            self.set_status("Screenshot ready. Review it before sending.")
        except Exception as exc:
            self.show()
            self.set_status(f"Capture failed: {exc}")

    def attach_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach notes or transcript", "",
            "Documents (*.txt *.md *.pdf *.docx *.srt *.vtt);;All files (*.*)"
        )
        if not path:
            return
        suffix = Path(path).suffix.lower()
        try:
            if suffix in (".txt", ".md", ".srt", ".vtt"):
                content = Path(path).read_text(encoding="utf-8", errors="replace")
                self.prompt.setPlainText(
                    self.prompt.toPlainText().strip() +
                    ("\n\n" if self.prompt.toPlainText().strip() else "") +
                    f"Attached file: {Path(path).name}\n\n{content[:50000]}"
                )
                self.set_status(f"Loaded text from {Path(path).name}")
            elif suffix == ".pdf":
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(path)
                    content = "\n".join(page.extract_text() or "" for page in reader.pages)
                    self.prompt.setPlainText(
                        self.prompt.toPlainText().strip() +
                        ("\n\n" if self.prompt.toPlainText().strip() else "") +
                        f"Attached PDF: {Path(path).name}\n\n{content[:50000]}"
                    )
                    self.set_status(f"Extracted text from {Path(path).name}")
                except ImportError:
                    QMessageBox.information(
                        self, "PDF support", "Install PDF support with: pip install pypdf"
                    )
            elif suffix == ".docx":
                try:
                    from docx import Document
                    doc = Document(path)
                    content = "\n".join(p.text for p in doc.paragraphs)
                    self.prompt.setPlainText(
                        self.prompt.toPlainText().strip() +
                        ("\n\n" if self.prompt.toPlainText().strip() else "") +
                        f"Attached document: {Path(path).name}\n\n{content[:50000]}"
                    )
                    self.set_status(f"Extracted text from {Path(path).name}")
                except ImportError:
                    QMessageBox.information(
                        self, "DOCX support", "Install Word support with: pip install python-docx"
                    )
            else:
                QMessageBox.information(
                    self, "Unsupported file type",
                    "For this first build, attach a TXT, MD, SRT, VTT, PDF or DOCX file."
                )
        except Exception as exc:
            QMessageBox.warning(self, "Could not open file", str(exc))

    def ask_ai(self):
        prompt = self.prompt.toPlainText().strip()
        if not prompt and not (self.screenshot_path and self.include_screen.isChecked()):
            self.set_status("Enter a question or attach content first.")
            return
        if not os.getenv("OPENAI_API_KEY"):
            QMessageBox.warning(
                self, "API key missing",
                "Set OPENAI_API_KEY in the .env file, then restart AURA."
            )
            return

        self.ask_btn.setEnabled(False)
        self.output.setPlainText("Thinking...")
        self.set_status("Sending request...")
        mode = self.mode.currentText()
        screenshot = self.screenshot_path if self.include_screen.isChecked() else None
        threading.Thread(
            target=self.call_ai, args=(mode, prompt, screenshot), daemon=True
        ).start()

    def call_ai(self, mode, prompt, screenshot):
        instructions = {
            "Study & Notes": (
                "Act as a careful study tutor. Create clear notes, explain hard ideas, "
                "identify key concepts, and create practice questions. Distinguish source "
                "facts from your own explanation. Do not invent citations or facts."
            ),
            "Video & Creator": (
                "Act as a video-editing and creator assistant. From supplied transcripts, "
                "find strong hooks, clip-worthy moments, suggested cuts, and short-form ideas. "
                "Only give timestamps when they exist in the provided material. If looking at "
                "a screenshot, describe visible controls and suggest safe next steps."
            ),
            "Interview Practice": (
                "Act as an interview coach for preparation and practice. Give constructive "
                "feedback, improve clarity, and use STAR structure where useful. Do not "
                "provide covert real-time answers intended to misrepresent a candidate's skills."
            ),
            "Explain a Concept": (
                "Explain step by step using plain language, an example, and a short recap. "
                "Ask a clarifying question if the visible context is insufficient."
            ),
            "General Assistant": "Be useful, accurate, concise, and transparent about uncertainty."
        }
        try:
            content = []
            if prompt:
                content.append({"type": "input_text", "text": prompt})
            if screenshot and os.path.exists(screenshot):
                raw = Path(screenshot).read_bytes()
                encoded = base64.b64encode(raw).decode("ascii")
                content.append({
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{encoded}"
                })
            from openai import OpenAI
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            response = client.responses.create(
                model=MODEL,
                instructions=instructions[mode],
                input=[{"role": "user", "content": content}]
            )
            answer = response.output_text or "The model returned no text."
        except Exception as exc:
            answer = f"Request failed: {exc}"
        self.signals.result.emit(answer)

    def on_result(self, answer):
        self.output.setPlainText(answer)
        self.ask_btn.setEnabled(True)
        self.set_status("Ready")

    def set_status(self, message):
        self.status.setText(message)

    def clear_all(self):
        self.prompt.clear()
        self.output.clear()
        self.screenshot_path = None
        self.capture_label.setText("No screenshot attached")
        self.set_status("Cleared")

    def closeEvent(self, event):
        if keyboard is not None and self._hotkey_registered:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AURA AI")
    window = AuraAI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
