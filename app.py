import os, sys, tempfile, threading, re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent
from PySide6.QtCore import QObject
from PySide6.QtGui import QColor, QGuiApplication, QDesktopServices
from PySide6.QtWidgets import *

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
# Keep user API keys outside the source code and in a per-user writable config folder.
CONFIG_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "AURA AI"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
USER_ENV_FILE = CONFIG_DIR / ".env"
# In development, allow a project-local .env. In packaged builds, require the
# user's own configuration instead of accidentally inheriting a bundled developer key.
if not getattr(sys, "frozen", False):
    load_dotenv(APP_DIR / ".env")
load_dotenv(USER_ENV_FILE, override=True)
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
try:
    import keyboard
except Exception:
    keyboard = None
try:
    import sounddevice as sd, soundfile as sf
    AUDIO_OK = True
except Exception:
    AUDIO_OK = False
try:
    import pyttsx3
    TTS_OK = True
except Exception:
    TTS_OK = False
try:
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_SDK_OK = True
except Exception:
    ElevenLabs = None
    ELEVENLABS_SDK_OK = False
try:
    import numpy as np
except Exception:
    np = None
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None
try:
    from docx import Document
except Exception:
    Document = None

CSS = """
QWidget { color:#F2F4FF; font-family:'Segoe UI'; font-size:10pt; }
QFrame#panel { background:rgba(18,21,36,190); border:1px solid rgba(160,170,255,100); border-radius:20px; }
QLabel#brand {font-size:15pt;font-weight:700;} QLabel#muted {color:#AAB2D0;font-size:9pt;}
QLabel#orb {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #785DFF,stop:1 #42DCE9);border-radius:13px;min-width:34px;max-width:34px;min-height:34px;max-height:34px;font-weight:800;}
QPushButton {background:rgba(255,255,255,14);border:1px solid rgba(255,255,255,28);border-radius:10px;padding:8px 10px;}
QPushButton:hover {background:rgba(120,93,255,100);} QPushButton#primary {background:#765DF5;font-weight:700;}
QPushButton#mic {background:rgba(66,220,233,25);border-color:rgba(66,220,233,100);}
QLineEdit,QTextEdit,QComboBox {background:rgba(5,8,18,145);border:1px solid rgba(160,170,220,60);border-radius:11px;padding:9px;selection-background-color:#765DF5;}
QTextEdit#chat {background:rgba(5,8,18,82);border-color:rgba(160,170,220,30);}
QCheckBox {color:#B9C1DE;spacing:6px;}
"""

def extract_file(path):
    p = Path(path); ext = p.suffix.lower()
    try:
        if ext in {".txt",".md",".srt",".vtt",".csv",".json",".py",".js",".html",".css"}:
            return p.read_text(encoding="utf-8", errors="replace")[:35000]
        if ext == ".pdf" and PdfReader:
            return "\n".join(pg.extract_text() or "" for pg in PdfReader(str(p)).pages[:35])[:35000]
        if ext == ".docx" and Document:
            return "\n".join(x.text for x in Document(str(p)).paragraphs)[:35000]
        return f"File selected: {p.name}. Text extraction is not supported for this file type."
    except Exception as e: return f"Could not read file: {e}"

class AskWorker(QThread):
    ok = Signal(str); error = Signal(str)
    def __init__(self, prompt, model, image=None, audio=None, attachment="", parent=None):
        super().__init__(parent); self.prompt=prompt; self.model=model; self.image=image; self.audio=audio; self.attachment=attachment
    def run(self):
        try:
            key=os.getenv("GEMINI_API_KEY","").strip()
            if not key or key == "put_your_gemini_api_key_here":
                raise RuntimeError("Gemini API key missing. Add GEMINI_API_KEY to .env and restart AURA.")
            client=genai.Client(api_key=key)
            content=["You are AURA, a helpful Windows desktop assistant. Be accurate, clear, practical, and honest about uncertainty.\n\nUser request:\n"+(self.prompt or "Please analyze the attached input.")]
            if self.attachment: content.append("Attached document text:\n"+self.attachment)
            if self.image and Path(self.image).exists():
                content.append(types.Part.from_bytes(data=Path(self.image).read_bytes(), mime_type="image/png"))
            if self.audio and Path(self.audio).exists():
                content.append("Understand the spoken request in this audio and answer it naturally.")
                content.append(types.Part.from_bytes(data=Path(self.audio).read_bytes(), mime_type="audio/wav"))
            result=client.models.generate_content(model=self.model, contents=content)
            self.ok.emit((result.text or "").strip() or "Gemini returned an empty response.")
        except Exception as e: self.error.emit(f"{type(e).__name__}: {e}")

class RecordWorker(QThread):
    finished_path=Signal(str); error=Signal(str); started_recording=Signal()
    def run(self):
        if not AUDIO_OK:
            self.error.emit("Voice dependencies are missing. Run install.ps1 again."); return
        try:
            import sounddevice as sd, soundfile as sf
            self.started_recording.emit()
            rate=16000
            data=sd.rec(int(8*rate), samplerate=rate, channels=1, dtype="float32")
            sd.wait()
            fd,path=tempfile.mkstemp(prefix="aura_voice_",suffix=".wav"); os.close(fd)
            sf.write(path,data,rate); self.finished_path.emit(path)
        except Exception as e: self.error.emit(f"Microphone error: {e}")

class VoiceListWorker(QThread):
    voices_ready = Signal(list)
    failed = Signal(str)
    def run(self):
        key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not key:
            self.failed.emit("Add ELEVENLABS_API_KEY to .env to load online voices."); return
        if not ELEVENLABS_SDK_OK:
            self.failed.emit("ElevenLabs SDK missing. Run the install command in the setup steps."); return
        try:
            client = ElevenLabs(api_key=key)
            response = client.voices.get_all()
            voices = []
            for voice in getattr(response, "voices", []) or []:
                voice_id = getattr(voice, "voice_id", None)
                name = getattr(voice, "name", None)
                if voice_id and name:
                    voices.append({"id": voice_id, "name": name})
            self.voices_ready.emit(voices)
        except Exception as e:
            self.failed.emit(f"Could not load ElevenLabs voices: {type(e).__name__}: {e}")

class SpeechWorker(QThread):
    finished_speech = Signal(str)
    failed = Signal(str)
    def __init__(self, text, voice_id, parent=None):
        super().__init__(parent); self.text = text; self.voice_id = voice_id
    def run(self):
        key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not key or not self.voice_id or not ELEVENLABS_SDK_OK:
            self.failed.emit("ElevenLabs is not configured; using local voice."); return
        try:
            client = ElevenLabs(api_key=key)
            # PCM output avoids temporary audio files and is suitable for sounddevice playback.
            audio = client.text_to_speech.convert(
                voice_id=self.voice_id,
                model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
                output_format="pcm_24000",
                text=self.text[:4500],
                voice_settings={"stability": 0.55, "similarity_boost": 0.75, "style": 0.2, "use_speaker_boost": True},
            )
            raw = b"".join(audio)
            if not raw: raise RuntimeError("ElevenLabs returned empty audio.")
            if np is None: raise RuntimeError("numpy is unavailable for PCM playback.")
            import sounddevice as sd
            samples = np.frombuffer(raw, dtype=np.int16)
            sd.play(samples, samplerate=24000, blocking=True)
            self.finished_speech.emit("Online voice finished.")
        except Exception as e:
            self.failed.emit(f"ElevenLabs playback failed: {type(e).__name__}: {e}")

class HotkeyBridge(QObject):
    restore=Signal()

class SetupWizard(QDialog):
    """First-run API setup. Keys are saved locally, never inserted into Python source."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set up AURA AI")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        self.setMinimumSize(520, 500)
        self.resize(580, 590)
        self.setModal(True)
        self.setStyleSheet(CSS + " QDialog { background:#121524; } QLabel { background:transparent; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)
        heading = QLabel("Welcome to AURA AI")
        heading.setStyleSheet("font-size:20pt;font-weight:700;color:#F2F4FF;")
        root.addWidget(heading)
        intro = QLabel("Let's connect your AI provider. Your API keys are stored locally in your Windows user profile, not written into the app's Python code.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        root.addWidget(intro)

        root.addWidget(QLabel("1. Gemini API key (required)"))
        help_gemini = QLabel('<a href="https://aistudio.google.com/apikey">Get a Gemini API key from Google AI Studio</a>')
        help_gemini.setOpenExternalLinks(True)
        root.addWidget(help_gemini)
        self.gemini_key = QLineEdit()
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key.setPlaceholderText("Paste your Gemini API key")
        self.gemini_key.setText(os.getenv("GEMINI_API_KEY", ""))
        root.addWidget(self.gemini_key)

        root.addWidget(QLabel("2. ElevenLabs API key (optional)"))
        help_eleven = QLabel('<a href="https://elevenlabs.io/app/settings/api-keys">Get an ElevenLabs API key for online voices</a>')
        help_eleven.setOpenExternalLinks(True)
        root.addWidget(help_eleven)
        self.eleven_key = QLineEdit()
        self.eleven_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.eleven_key.setPlaceholderText("Optional — leave blank to use Windows voice")
        self.eleven_key.setText(os.getenv("ELEVENLABS_API_KEY", ""))
        root.addWidget(self.eleven_key)

        note = QLabel("AURA needs internet access for Gemini. API providers may charge for usage; check your account's limits and billing. To change keys later, edit the local settings file and restart AURA.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        root.addWidget(note)
        buttons = QHBoxLayout()
        self.cancel_btn = QPushButton("Exit setup")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_btn)
        buttons.addStretch()
        self.save_btn = QPushButton("Save keys and launch AURA")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self.save_keys)
        buttons.addWidget(self.save_btn)
        root.addLayout(buttons)

    def save_keys(self):
        gemini = self.gemini_key.text().strip()
        if not gemini:
            QMessageBox.warning(self, "Gemini key required", "Paste your Gemini API key to use AURA.")
            self.gemini_key.setFocus()
            return
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            lines = [f'GEMINI_API_KEY="{gemini.replace(chr(34), chr(92)+chr(34))}"']
            eleven = self.eleven_key.text().strip()
            if eleven:
                lines.append(f'ELEVENLABS_API_KEY="{eleven.replace(chr(34), chr(92)+chr(34))}"')
            # Keep model/custom settings from an existing user config where possible.
            existing = {}
            if USER_ENV_FILE.exists():
                for line in USER_ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
                    if "=" in line and not line.lstrip().startswith("#"):
                        k, v = line.split("=", 1)
                        if k.strip() not in {"GEMINI_API_KEY", "ELEVENLABS_API_KEY"}:
                            existing[k.strip()] = v.strip()
            lines.extend(f"{k}={v}" for k, v in existing.items())
            USER_ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.environ["GEMINI_API_KEY"] = gemini
            if eleven:
                os.environ["ELEVENLABS_API_KEY"] = eleven
            else:
                os.environ.pop("ELEVENLABS_API_KEY", None)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Could not save setup", f"AURA could not save your local settings:\n{e}")


class Aura(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AURA AI")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        initial_w = min(460, max(320, available.width() - 24)) if available else 460
        initial_h = min(680, max(420, available.height() - 40)) if available else 680
        self.resize(initial_w, initial_h)
        # Compact mode is smaller than the normal window, so don't enforce
        # the normal window's minimum size while compact mode is active.
        self.normal_minimum_size = (320, 420)
        self.setMinimumSize(*self.normal_minimum_size)
        self.drag=None; self.compact=False
        self.monitoring=False; self.monitor_busy=False; self.monitor_timer=QTimer(self); self.monitor_timer.setInterval(8000); self.monitor_timer.timeout.connect(self._monitor_tick); self._last_monitor_capture=0
        self.image_path=None; self.attachment=""; self.workers=[]; self.online_voices={}; self.current_speech=None; self._closing=False
        self.mode_prompt="Help with the user's request."
        self.build()
        self.setStyleSheet(CSS)
        self.setWindowOpacity(0.94)
        shadow=QGraphicsDropShadowEffect(self); shadow.setBlurRadius(34); shadow.setOffset(0,7); shadow.setColor(QColor(0,0,0,150)); self.panel.setGraphicsEffect(shadow)
        self.move_corner()
        self.bridge=HotkeyBridge(); self.bridge.restore.connect(self.toggle_visible)
        if keyboard:
            try: keyboard.add_hotkey("ctrl+space", lambda: self.bridge.restore.emit())
            except Exception: self.status("Global shortcut unavailable; try tray controls.")
        self.setup_tray()
        if os.getenv("ELEVENLABS_API_KEY", "").strip(): QTimer.singleShot(300, self.load_online_voices)
        self.say("AURA", "Hey! I'm AURA. Ask a question, attach a document, capture your screen, or tap Talk.")
        if not os.getenv("GEMINI_API_KEY","").strip(): self.status("Add your Gemini API key to .env")

    def build(self):
        # Keep the panel directly in the window layout. Wrapping the whole
        # assistant in a QScrollArea caused collapsed/minimized sizing on some PCs.
        outer=QVBoxLayout(self); outer.setContentsMargins(1,1,1,1)
        self.panel=QFrame(); self.panel.setObjectName("panel")
        outer.addWidget(self.panel)
        v=QVBoxLayout(self.panel); v.setContentsMargins(15,13,15,13); v.setSpacing(9)
        top=QHBoxLayout(); orb=QLabel("A"); orb.setObjectName("orb"); orb.setAlignment(Qt.AlignmentFlag.AlignCenter); top.addWidget(orb)
        col=QVBoxLayout(); col.setSpacing(0); title=QLabel("AURA AI"); title.setObjectName("brand"); sub=QLabel("YOUR DESKTOP COPILOT"); sub.setObjectName("muted"); col.addWidget(title); col.addWidget(sub); top.addLayout(col); top.addStretch()
        self.compact_btn=QPushButton("-"); self.compact_btn.setFixedSize(32,31); self.compact_btn.clicked.connect(self.toggle_compact); top.addWidget(self.compact_btn)
        hide=QPushButton("X"); hide.setFixedSize(32,31); hide.setToolTip("Exit AURA completely"); hide.clicked.connect(self.exit_app); top.addWidget(hide); v.addLayout(top)
        self.status_label=QLabel("Ready"); self.status_label.setObjectName("muted"); v.addWidget(self.status_label)
        opacity_row=QHBoxLayout(); self.opacity_label=QLabel("Opacity"); opacity_row.addWidget(self.opacity_label); self.opacity_slider=QSlider(Qt.Orientation.Horizontal); self.opacity_slider.setRange(55,100); self.opacity_slider.setValue(94); self.opacity_slider.setMaximumWidth(130); self.opacity_slider.valueChanged.connect(lambda n:self.setWindowOpacity(n/100)); opacity_row.addWidget(self.opacity_slider)
        self.monitor_btn=QPushButton("Start screen watch"); self.monitor_btn.setCheckable(True); self.monitor_btn.setToolTip("Explicitly monitor the screen using periodic screenshots. Click again to stop."); self.monitor_btn.clicked.connect(self.toggle_monitoring); opacity_row.addWidget(self.monitor_btn); v.addLayout(opacity_row)
        row=QHBoxLayout(); self.mode=QComboBox(); self.mode.addItems(["General assistant","Study & notes","Creator studio","Interview practice","Explain a concept","Code helper"]); self.mode.currentTextChanged.connect(self.set_mode); row.addWidget(self.mode,1)
        self.presentation_btn=QPushButton("Presentation mode"); self.presentation_btn.clicked.connect(self.presentation); row.addWidget(self.presentation_btn); v.addLayout(row)
        self.chat=QTextEdit(); self.chat.setObjectName("chat"); self.chat.setReadOnly(True); v.addWidget(self.chat,1)
        row=QHBoxLayout()
        self.screen=QPushButton("Screen"); self.screen.clicked.connect(self.capture_screen); row.addWidget(self.screen)
        self.attach=QPushButton("ï¼‹ Attach"); self.attach.clicked.connect(self.attach_file); row.addWidget(self.attach)
        self.clear_btn=QPushButton("Clear"); self.clear_btn.clicked.connect(self.clear_chat); row.addWidget(self.clear_btn); v.addLayout(row)
        self.file_label=QLabel("No attachment"); self.file_label.setObjectName("muted"); self.file_label.setWordWrap(True); v.addWidget(self.file_label)
        self.input=QTextEdit(); self.input.setPlaceholderText("Message AURA (Ctrl+Enter to send)"); self.input.setFixedHeight(74); self.input.installEventFilter(self); v.addWidget(self.input)
        bottom=QHBoxLayout(); self.talk=QPushButton("Talk"); self.talk.setObjectName("mic"); self.talk.clicked.connect(self.voice); bottom.addWidget(self.talk)
        self.speak_check=QCheckBox("Speak replies"); self.speak_check.setChecked(True); bottom.addWidget(self.speak_check); bottom.addStretch()
        self.send=QPushButton("Ask Gemini"); self.send.setObjectName("primary"); self.send.clicked.connect(self.ask); bottom.addWidget(self.send); v.addLayout(bottom)
        voice_row=QHBoxLayout()
        self.voice_label=QLabel("Voice")
        voice_row.addWidget(self.voice_label)
        self.voice_choice=QComboBox(); self.voice_choice.addItem("Local Windows voice", "local"); self.voice_choice.addItem("ElevenLabs — configured voice", "configured"); self.voice_choice.setToolTip("Online voices are loaded from your ElevenLabs account."); voice_row.addWidget(self.voice_choice, 1)
        self.refresh_voices_btn=QPushButton("Load online voices"); self.refresh_voices_btn.clicked.connect(self.load_online_voices); voice_row.addWidget(self.refresh_voices_btn)
        self.test_voice_btn=QPushButton("Test voice"); self.test_voice_btn.clicked.connect(self.test_voice); voice_row.addWidget(self.test_voice_btn)
        v.addLayout(voice_row)
        self.footer=QLabel("Gemini API | Ctrl + Space restores hidden AURA"); self.footer.setObjectName("muted"); self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter); v.addWidget(self.footer)

    def _normal_size(self):
        screen=QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        if not screen: return (460,680)
        r=screen.availableGeometry()
        return (min(460,max(320,r.width()-24)), min(680,max(420,r.height()-40)))
    def move_corner(self):
        screen=QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        if screen:
            r=screen.availableGeometry()
            w=min(self.width(),r.width()); h=min(self.height(),r.height())
            self.resize(w,h)
            x=max(r.left(),min(self.x(),r.right()-w+1))
            y=max(r.top(),min(self.y(),r.bottom()-h+1))
            if self.x()<r.left() or self.y()<r.top() or self.x()+w>r.right()+1 or self.y()+h>r.bottom()+1:
                self.move(max(r.left(),r.right()-w-18),max(r.top(),r.bottom()-h-18))
    def setup_tray(self):
        self.tray=None
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self.tray=QSystemTrayIcon(self); self.tray.setToolTip("AURA AI")
        menu=QMenu(); a=menu.addAction("Show AURA"); a.triggered.connect(self.show_focus)
        b=menu.addAction("Hide AURA"); b.triggered.connect(self.hide)
        menu.addSeparator(); q=menu.addAction("Exit AURA completely"); q.triggered.connect(self.exit_app)
        self.tray.setContextMenu(menu); self.tray.show()
    def status(self,s): self.status_label.setText(s)
    def say(self,who,text):
        text=(text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")
        color="#9B8BFF" if who=="AURA" else "#53DCE8"
        self.chat.append(f'<p style="margin:8px 0 3px;color:{color};font-weight:700">{who}</p><p style="margin:0 0 12px;line-height:1.45">{text}</p>')
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
    def set_mode(self,m):
        self.mode_prompt={
            "Study & notes":"Act as a patient tutor. Explain step by step with examples.",
            "Creator studio":"Act as a creative producer for short videos, YouTube, hooks, and scripts.",
            "Interview practice":"Act as an interviewer. Ask one question at a time and give constructive feedback.",
            "Explain a concept":"Explain simply first, then deepen with an example and recap.",
            "Code helper":"Give runnable code, explain where it goes, and avoid fake functionality.",
            "General assistant":"Help with the user's request."
        }.get(m,"Help with the user's request.")
    def ask(self):
        prompt=self.input.toPlainText().strip()
        if not prompt and not self.image_path and not self.attachment:
            self.status("Type a message or attach something"); return
        self.input.clear(); self.say("YOU",prompt or "Analyze the attachment.")
        self.send.setEnabled(False); self.talk.setEnabled(False); self.status("Thinking with Gemini...")
        w=AskWorker(self.mode_prompt+"\n\n"+prompt,os.getenv("GEMINI_MODEL",MODEL),self.image_path,None,self.attachment,self)
        w.ok.connect(self.answer); w.error.connect(self.failed); w.finished.connect(self.enable); self.workers.append(w); w.start()
        self.image_path=None; self.attachment=""; self.file_label.setText("No attachment")
    def answer(self,text):
        self.say("AURA",text); self.status("Ready")
        if self.speak_check.isChecked(): self.speak(text)
    def failed(self,text): self.say("AURA","I couldn't complete that request.\n"+text); self.status("Check API key / connection")
    def enable(self): self.send.setEnabled(True); self.talk.setEnabled(True)
    def attach_file(self):
        path,_=QFileDialog.getOpenFileName(self,"Attach file",str(Path.home()),"Documents (*.txt *.md *.pdf *.docx *.srt *.vtt *.csv *.json *.py *.js *.html *.css);;All files (*.*)")
        if path: self.attachment=extract_file(path); self.file_label.setText("Attached: "+Path(path).name); self.status("File attached")
    def toggle_monitoring(self, checked):
        self.monitoring=bool(checked)
        self.monitor_btn.setText("Stop screen watch" if self.monitoring else "Start screen watch")
        if self.monitoring:
            self.monitor_timer.start()
            self.status("Screen watch ON — periodic screenshots every 8 seconds")
            QTimer.singleShot(250, self._monitor_tick)
        else:
            self.monitor_timer.stop(); self.monitor_busy=False
            self.status("Screen watch stopped")

    def _monitor_tick(self):
        if not self.monitoring or self.monitor_busy or self._closing:
            return
        # Capture only while the user has explicitly enabled monitoring.
        self.monitor_busy=True
        self.hide()
        QTimer.singleShot(350, self._capture_for_monitor)

    def _capture_for_monitor(self):
        try:
            screen=QGuiApplication.primaryScreen()
            if not screen: raise RuntimeError("No screen available")
            pix=screen.grabWindow(0)
            fd,path=tempfile.mkstemp(prefix="aura_watch_",suffix=".png"); os.close(fd)
            if not pix.save(path,"PNG"): raise RuntimeError("Could not save screenshot")
            self.show(); self.raise_()
            self.image_path=path
            self.say("AURA","Checking the screen for a visible question…")
            self.status("Analysing screen snapshot…")
            prompt=("You are monitoring a user's screen with their explicit permission. Inspect this screenshot for a clearly visible question, MCQ, fill-in-the-blank, or task they may want help with. If a question is visible, answer it clearly and concisely; for MCQs state the best option and why. If no actionable question/task is visible, respond with exactly NO_ACTION. Do not infer hidden content. This is a single screenshot, not continuous video.")
            w=AskWorker(prompt,os.getenv("GEMINI_MODEL",MODEL),self.image_path,None,"",self)
            w.ok.connect(self._monitor_answer); w.error.connect(self._monitor_error)
            w.finished.connect(self._monitor_finished); self.workers.append(w); w.start()
        except Exception as e:
            self.show(); self.monitor_busy=False; self.status("Screen watch capture failed: "+str(e)[:100])

    def _monitor_answer(self,text):
        if (text or "").strip() != "NO_ACTION":
            self.say("AURA · SCREEN",text)
            if self.speak_check.isChecked(): self.speak(text)
            self.status("Screen question found — watching continues")
        else:
            self.status("No question detected — watching continues")

    def _monitor_error(self,text):
        self.status("Screen analysis failed: "+str(text)[:100])

    def _monitor_finished(self):
        if self.image_path and Path(self.image_path).name.startswith("aura_watch_"):
            try: Path(self.image_path).unlink(missing_ok=True)
            except Exception: pass
            self.image_path=None
        self.monitor_busy=False
        if self.monitoring and not self._closing:
            self.status("Screen watch ON — next check in about 8 seconds")

    def capture_screen(self):
        self.hide(); QTimer.singleShot(650,self._capture)
    def _capture(self):
        try:
            screen=QGuiApplication.primaryScreen()
            if not screen: raise RuntimeError("No screen available")
            pix=screen.grabWindow(0); fd,path=tempfile.mkstemp(prefix="aura_screen_",suffix=".png"); os.close(fd); pix.save(path,"PNG")
            self.image_path=path; self.file_label.setText("Screenshot ready - ask Gemini about it"); self.show_focus(); self.status("Screenshot captured")
        except Exception as e: self.show_focus(); self.status("Screenshot failed: "+str(e))
    def voice(self):
        if not AUDIO_OK:
            self.say("AURA","Voice recording dependencies are missing. Run install.ps1 and restart."); return
        self.talk.setEnabled(False); self.talk.setText("â— Listening..."); self.status("Listening for up to 8 secondsâ€¦")
        w=RecordWorker(); w.started_recording.connect(lambda:self.status("Listening...")); w.finished_path.connect(self.voice_ready); w.error.connect(self.voice_error); self.workers.append(w); w.start()
    def voice_ready(self,path):
        self.talk.setText("ðŸŽ™ Talk"); self.talk.setEnabled(True); self.say("YOU","[Voice message]"); self.status("Sending audio to Gemini...")
        w=AskWorker("Understand the spoken request in this audio and answer naturally.",os.getenv("GEMINI_MODEL",MODEL),audio=path,parent=self)
        w.ok.connect(self.answer); w.error.connect(self.failed); w.finished.connect(self.enable); self.workers.append(w); w.start()
    def voice_error(self,msg): self.talk.setText("Talk"); self.talk.setEnabled(True); self.status("Microphone unavailable"); self.say("AURA",msg)
    def _speech_text(self, text):
        text = re.sub(r"```.*?```", " code omitted ", text or "", flags=re.S)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"!\[[^]]*\]\([^)]*\)|\[([^]]+)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"[#>*_~]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:4500]

    def load_online_voices(self):
        if not os.getenv("ELEVENLABS_API_KEY", "").strip():
            self.status("Add ELEVENLABS_API_KEY to .env for online voices")
            return
        self.refresh_voices_btn.setEnabled(False); self.status("Loading ElevenLabs voices...")
        worker = VoiceListWorker(self); worker.voices_ready.connect(self._voices_loaded); worker.failed.connect(self._voices_failed)
        worker.finished.connect(lambda: self.refresh_voices_btn.setEnabled(True)); self.workers.append(worker); worker.start()

    def _voices_loaded(self, voices):
        self.online_voices = {v["id"]: v["name"] for v in voices}
        self.voice_choice.blockSignals(True)
        current = self.voice_choice.currentData()
        self.voice_choice.clear(); self.voice_choice.addItem("Local Windows voice", "local")
        configured = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
        if configured:
            self.voice_choice.addItem("ElevenLabs — configured voice", configured)
        for voice in voices:
            self.voice_choice.addItem("ElevenLabs — " + voice["name"], voice["id"])
        # Prefer a real ElevenLabs voice after loading. Keeping the initial
        # "local" selection here made replies use Windows speech even though
        # online voices had loaded successfully.
        preferred = configured if configured and self.voice_choice.findData(configured) >= 0 else None
        if preferred is None and voices:
            preferred = voices[0]["id"]
        index = self.voice_choice.findData(preferred) if preferred else -1
        if index < 0:
            index = self.voice_choice.findData("local")
        if index >= 0:
            self.voice_choice.setCurrentIndex(index)
        self.voice_choice.blockSignals(False)
        if voices:
            self.status(f"Loaded {len(voices)} ElevenLabs voices — selected {self.voice_choice.currentText()}")
        else:
            self.status("No voices returned by ElevenLabs; using local voice")

    def _voices_failed(self, message):
        self.status(message[:120]); self.say("AURA", message)

    def test_voice(self):
        sample = "Good evening. AURA is online. All systems are ready. How may I assist you?"
        if self.voice_choice.currentData() == "local":
            self.speak(sample); self.status("Testing local Windows voice")
        else:
            self.speak(sample); self.status("Testing selected online voice")

    def speak(self,text):
        text = self._speech_text(text)
        if not text: return
        voice_id = self.voice_choice.currentData() if hasattr(self, "voice_choice") else "local"
        if voice_id != "local" and os.getenv("ELEVENLABS_API_KEY", "").strip() and ELEVENLABS_SDK_OK:
            # If online synthesis fails, automatically fall back to the Windows voice.
            worker = SpeechWorker(text, str(voice_id), self)
            worker.failed.connect(lambda msg, spoken=text: (self.status("ElevenLabs failed; local fallback: " + msg[:100]), self._speak_local(spoken)) if not self._closing else None)
            worker.finished_speech.connect(lambda msg: self.status("Ready"))
            self.current_speech = worker; self.workers.append(worker); worker.start()
        else:
            self._speak_local(text)

    def _speak_local(self, text):
        if not TTS_OK: self.status("No local TTS installed; install pyttsx3"); return
        def run():
            try:
                engine=pyttsx3.init(); engine.setProperty("rate",165)
                # Use selected Windows voice if a local voice ID was chosen by the user later.
                engine.say(text[:4500]); engine.runAndWait(); engine.stop()
            except Exception as e:
                QTimer.singleShot(0, lambda: self.status("Local voice failed: " + str(e)[:90]))
        threading.Thread(target=run,daemon=True).start()
    def clear_chat(self): self.chat.clear(); self.say("AURA","Conversation cleared. What would you like to work on?"); self.status("Ready")
    def presentation(self):
        self.hide()
        if self.tray: self.tray.showMessage("AURA AI","Hidden for presentation. Press Ctrl+Space to restore.",QSystemTrayIcon.MessageIcon.Information,2200)
    def toggle_visible(self): self.hide() if self.isVisible() else self.show_focus()
    def show_focus(self): self.show(); self.move_corner(); self.raise_(); self.activateWindow(); self.input.setFocus()
    def toggle_compact(self):
        self.compact = not self.compact

        hidden_in_compact = [
            self.status_label, self.opacity_label, self.opacity_slider,
            self.monitor_btn, self.mode, self.presentation_btn, self.chat,
            self.screen, self.attach, self.clear_btn, self.file_label,
            self.input, self.talk, self.speak_check, self.send,
            self.voice_label, self.voice_choice, self.refresh_voices_btn,
            self.test_voice_btn, self.footer,
        ]

        for widget in hidden_in_compact:
            widget.setVisible(not self.compact)

        if self.compact:
            # Explicitly constrain both the top-level window and its panel.
            self.panel.setMinimumSize(0, 0)
            self.panel.setMaximumSize(260, 68)
            self.panel.setFixedSize(258, 66)
            self.setFixedSize(260, 68)
            self.compact_btn.setText("+")
            self.compact_btn.setToolTip("Expand AURA")
        else:
            # Release compact constraints before restoring the normal layout.
            self.setMinimumSize(*self.normal_minimum_size)
            self.setMaximumSize(16777215, 16777215)
            self.panel.setMinimumSize(0, 0)
            self.panel.setMaximumSize(16777215, 16777215)
            self.panel.setMinimumSize(0, 0)
            width, height = self._normal_size()
            self.resize(width, height)
            self.compact_btn.setText("-")
            self.compact_btn.setToolTip("Minimize AURA to its compact bar")

        if self.panel.layout():
            self.panel.layout().invalidate()
            self.panel.layout().activate()
        if self.layout():
            self.layout().invalidate()
            self.layout().activate()

        self.move_corner()

    def eventFilter(self,obj,event):
        if obj is self.input and event.type()==QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.ask(); return True
        return super().eventFilter(obj,event)
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton and e.position().y()<60: self.drag=e.globalPosition().toPoint()-self.frameGeometry().topLeft(); e.accept()
        else: super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        if self.drag is not None and e.buttons() & Qt.MouseButton.LeftButton: self.move(e.globalPosition().toPoint()-self.drag); e.accept()
        else: super().mouseMoveEvent(e)
    def mouseReleaseEvent(self,e): self.drag=None; super().mouseReleaseEvent(e)
    def exit_app(self):
        """Stop audio, unregister shortcuts, close the tray icon, and exit."""
        if self._closing:
            return
        self._closing = True
        self.monitor_timer.stop(); self.monitoring=False
        self.status("Shutting down AURA...")
        try:
            if AUDIO_OK:
                import sounddevice as sd
                sd.stop()
        except Exception:
            pass
        try:
            if keyboard:
                keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        try:
            if self.tray:
                self.tray.hide()
        except Exception:
            pass
        # Wait briefly for background QThreads so the app doesn't leave a
        # running Python process behind or destroy live QThread objects.
        for worker in list(self.workers):
            try:
                if worker.isRunning():
                    worker.requestInterruption()
                    worker.wait(1200)
            except Exception:
                pass
        self.close()
        QApplication.instance().quit()

    def closeEvent(self, e):
        # Closing the window now means exit, not hide-to-tray.
        if not self._closing:
            self._closing = True
            self.monitor_timer.stop(); self.monitoring=False
            try:
                if AUDIO_OK:
                    import sounddevice as sd
                    sd.stop()
            except Exception:
                pass
            try:
                if keyboard:
                    keyboard.unhook_all_hotkeys()
            except Exception:
                pass
            try:
                if self.tray:
                    self.tray.hide()
            except Exception:
                pass
        e.accept()
        QApplication.instance().quit()

def main():
    app=QApplication(sys.argv)
    app.setApplicationName("AURA AI")
    app.setQuitOnLastWindowClosed(True)

    # A first-run setup is required unless the per-user config contains a key.
    # This avoids a developer .env or inherited environment variable skipping setup.
    user_key = ""
    if USER_ENV_FILE.exists():
        for line in USER_ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                user_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not user_key or user_key == "put_your_gemini_api_key_here":
        setup = SetupWizard()
        screen = QGuiApplication.primaryScreen()
        if screen:
            setup.adjustSize()
            geo = screen.availableGeometry()
            setup.move(geo.center().x() - setup.width() // 2,
                       geo.center().y() - setup.height() // 2)
        if setup.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)

    w=Aura()
    w.show()
    w.raise_()
    w.activateWindow()
    sys.exit(app.exec())
if __name__=="__main__": main()

