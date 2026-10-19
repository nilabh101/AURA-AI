import os, sys, tempfile, threading, html, re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent
from PySide6.QtCore import QObject
from PySide6.QtGui import QColor, QGuiApplication, QTextCursor
from PySide6.QtWidgets import *

load_dotenv()
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
    from pypdf import PdfReader
except Exception:
    PdfReader = None
try:
    from docx import Document
except Exception:
    Document = None

CSS = """
QWidget { color:#F2F4FF; font-family:'Segoe UI'; font-size:10pt; }
QFrame#panel { background:rgba(18,21,36,232); border:1px solid rgba(160,170,255,100); border-radius:20px; }
QLabel#brand {font-size:15pt;font-weight:700;} QLabel#muted {color:#AAB2D0;font-size:9pt;}
QLabel#orb {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #785DFF,stop:1 #42DCE9);border-radius:13px;min-width:34px;max-width:34px;min-height:34px;max-height:34px;font-weight:800;}
QPushButton {background:rgba(255,255,255,14);border:1px solid rgba(255,255,255,28);border-radius:10px;padding:8px 10px;}
QPushButton:hover {background:rgba(120,93,255,100);} QPushButton#primary {background:#765DF5;font-weight:700;}
QPushButton#mic {background:rgba(66,220,233,25);border-color:rgba(66,220,233,100);}
QLineEdit,QTextEdit,QComboBox {background:rgba(5,8,18,145);border:1px solid rgba(160,170,220,60);border-radius:11px;padding:9px;selection-background-color:#765DF5;}
QTextEdit#chat {background:rgba(5,8,18,105);border-color:rgba(160,170,220,30);padding:12px; selection-background-color:#765DF5;}
QPushButton {min-height:18px;}
QPushButton#primary {padding-left:14px;padding-right:14px;}
QLabel#muted {padding-top:1px;padding-bottom:1px;}
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

class HotkeyBridge(QObject):
    restore=Signal()

class Aura(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AURA AI")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(460,750); self.setMinimumSize(400,560); self.drag=None; self.compact=False
        self.image_path=None; self.attachment=""; self.workers=[]
        self.mode_prompt="Help with the user's request."
        self.build()
        self.setStyleSheet(CSS)
        shadow=QGraphicsDropShadowEffect(self); shadow.setBlurRadius(34); shadow.setOffset(0,7); shadow.setColor(QColor(0,0,0,150)); self.panel.setGraphicsEffect(shadow)
        self.move_corner()
        self.bridge=HotkeyBridge(); self.bridge.restore.connect(self.toggle_visible)
        if keyboard:
            try: keyboard.add_hotkey("ctrl+space", lambda: self.bridge.restore.emit())
            except Exception: self.status("Global shortcut unavailable; try tray controls.")
        self.setup_tray()
        self.say("AURA", "Hey! I'm AURA. Ask a question, attach a document, capture your screen, or tap Talk.")
        if not os.getenv("GEMINI_API_KEY","").strip(): self.status("Add your Gemini API key to .env")

    def build(self):
        outer=QVBoxLayout(self); outer.setContentsMargins(1,1,1,1)
        self.panel=QFrame(); self.panel.setObjectName("panel"); outer.addWidget(self.panel)
        v=QVBoxLayout(self.panel); v.setContentsMargins(15,13,15,13); v.setSpacing(9)
        top=QHBoxLayout(); orb=QLabel("A"); orb.setObjectName("orb"); orb.setAlignment(Qt.AlignmentFlag.AlignCenter); top.addWidget(orb)
        col=QVBoxLayout(); col.setSpacing(0); title=QLabel("AURA AI"); title.setObjectName("brand"); sub=QLabel("YOUR DESKTOP COPILOT"); sub.setObjectName("muted"); col.addWidget(title); col.addWidget(sub); top.addLayout(col); top.addStretch()
        self.compact_btn=QPushButton("-"); self.compact_btn.setFixedSize(32,31); self.compact_btn.clicked.connect(self.toggle_compact); top.addWidget(self.compact_btn)
        hide=QPushButton("X"); hide.setFixedSize(32,31); hide.clicked.connect(self.hide); top.addWidget(hide); v.addLayout(top)
        self.status_label=QLabel("Ready"); self.status_label.setObjectName("muted"); v.addWidget(self.status_label)
        row=QHBoxLayout(); self.mode=QComboBox(); self.mode.addItems(["General assistant","Study & notes","Creator studio","Editing assistant","Quick concise answers","Interview practice","Explain a concept","Code helper"]); self.mode.currentTextChanged.connect(self.set_mode); row.addWidget(self.mode,1)
        pres=QPushButton("Presentation mode"); pres.clicked.connect(self.presentation); row.addWidget(pres); v.addLayout(row)
        self.chat=QTextEdit(); self.chat.setObjectName("chat"); self.chat.setReadOnly(True); v.addWidget(self.chat,1)
        row=QHBoxLayout()
        self.screen=QPushButton("Screen"); self.screen.clicked.connect(self.capture_screen); row.addWidget(self.screen)
        self.attach=QPushButton("+ Attach"); self.attach.clicked.connect(self.attach_file); row.addWidget(self.attach)
        clear=QPushButton("Clear"); clear.clicked.connect(self.clear_chat); row.addWidget(clear); v.addLayout(row)
        self.file_label=QLabel("No attachment"); self.file_label.setObjectName("muted"); self.file_label.setWordWrap(True); v.addWidget(self.file_label)
        self.input=QTextEdit(); self.input.setPlaceholderText("Message AURA (Ctrl+Enter to send)"); self.input.setFixedHeight(74); self.input.installEventFilter(self); v.addWidget(self.input)
        bottom=QHBoxLayout(); self.talk=QPushButton("Talk"); self.talk.setObjectName("mic"); self.talk.clicked.connect(self.voice); bottom.addWidget(self.talk)
        self.speak_check=QCheckBox("Speak replies"); self.speak_check.setChecked(True); bottom.addWidget(self.speak_check)
        self.short_check=QCheckBox("Short answers"); self.short_check.setToolTip("Ask AURA to use short, conversational phrases"); bottom.addWidget(self.short_check)
        v.addLayout(bottom)
        voice_row=QHBoxLayout(); voice_row.addWidget(QLabel("Voice"))
        self.voice_choice=QComboBox(); self.voice_choice.setMinimumWidth(150); self.voice_choice.addItems(["Clear / default", "Voice 2", "Voice 3"]); self.voice_choice.setToolTip("Select an installed Windows text-to-speech voice")
        self._voice_ids=[]; self._load_voices(); voice_row.addWidget(self.voice_choice,1)
        self.test_voice_btn=QPushButton("Test voice"); self.test_voice_btn.clicked.connect(lambda: self.speak("Hi! I'm AURA. How can I help you?")); voice_row.addWidget(self.test_voice_btn)
        v.addLayout(voice_row)
        send_row=QHBoxLayout(); send_row.addStretch()
        self.send=QPushButton("Ask Gemini"); self.send.setObjectName("primary"); self.send.clicked.connect(self.ask); send_row.addWidget(self.send); v.addLayout(send_row)
        foot=QLabel("Gemini API | Ctrl + Space restores hidden AURA"); foot.setObjectName("muted"); foot.setAlignment(Qt.AlignmentFlag.AlignCenter); v.addWidget(foot)

    def move_corner(self):
        s=QGuiApplication.primaryScreen()
        if s:
            r=s.availableGeometry(); self.move(r.right()-self.width()-22,r.bottom()-self.height()-22)
    def setup_tray(self):
        self.tray=None
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self.tray=QSystemTrayIcon(self); self.tray.setToolTip("AURA AI")
        menu=QMenu(); a=menu.addAction("Show AURA"); a.triggered.connect(self.show_focus)
        b=menu.addAction("Hide AURA"); b.triggered.connect(self.hide)
        menu.addSeparator(); q=menu.addAction("Quit"); q.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(menu); self.tray.show()
    def status(self,s): self.status_label.setText(s)
    def _markdown_html(self, text):
        """Render common Markdown safely for the chat view."""
        text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        out = []
        in_code = False
        code_lines = []
        in_list = False

        def inline(value):
            value = html.escape(value, quote=False)
            value = re.sub(r"`([^`]+)`", r'<code style="background:#25283A;color:#B9ACFF;padding:2px 4px;border-radius:4px; font-family:Consolas,monospace;">\1</code>', value)
            value = re.sub(r"\*\*(.+?)\*\*", r'<b>\1</b>', value)
            value = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r'<i>\1</i>', value)
            value = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r'<i>\1</i>', value)
            value = re.sub(r"\[([^\]]+)\]\((https?://[^ )]+)\)", r'<a href="\2" style="color:#8DDFF0;">\1</a>', value)
            return value

        for line in lines:
            if line.strip().startswith("```"):
                if in_code:
                    code = html.escape("\n".join(code_lines))
                    out.append('<pre style="background:#090B13;color:#D8DDF5;padding:10px;border-radius:8px;white-space:pre-wrap;font-family:Consolas,monospace;">' + code + '</pre>')
                    code_lines = []
                    in_code = False
                else:
                    if in_list:
                        out.append('</ul>'); in_list = False
                    in_code = True
                continue
            if in_code:
                code_lines.append(line)
                continue
            stripped = line.strip()
            if not stripped:
                if in_list:
                    out.append('</ul>'); in_list = False
                continue
            heading = re.match(r'^(#{1,3})\s+(.+)$', stripped)
            bullet = re.match(r'^\s*[-*+]\s+(.+)$', line)
            numbered = re.match(r'^\s*\d+[.)]\s+(.+)$', line)
            if heading:
                if in_list:
                    out.append('</ul>'); in_list = False
                level = len(heading.group(1))
                size = {1:'17px',2:'15px',3:'13px'}[level]
                out.append(f'<p style="margin:10px 0 5px;font-size:{size};font-weight:700;color:#F2F4FF;">{inline(heading.group(2))}</p>')
            elif bullet or numbered:
                if not in_list:
                    out.append('<ul style="margin:3px 0 8px;padding-left:20px;">'); in_list = True
                item = (bullet or numbered).group(1)
                out.append(f'<li style="margin:3px 0;">{inline(item)}</li>')
            else:
                if in_list:
                    out.append('</ul>'); in_list = False
                out.append(f'<p style="margin:4px 0 7px;line-height:1.4;">{inline(stripped)}</p>')
        if in_code:
            out.append('<pre style="background:#090B13;color:#D8DDF5;padding:10px;border-radius:8px;white-space:pre-wrap;font-family:Consolas,monospace;">' + html.escape("\n".join(code_lines)) + '</pre>')
        if in_list:
            out.append('</ul>')
        return ''.join(out)

    def say(self,who,text):
        color = "#9B8BFF" if who == "AURA" else "#53DCE8"
        cursor = self.chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f'<p style="margin:8px 0 4px;color:{color};font-weight:700;">{html.escape(who)}</p>')
        cursor.insertHtml(self._markdown_html(text))
        cursor.insertHtml('<p style="margin:0 0 10px;"></p>')
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()

    def set_mode(self,m):
        self.mode_prompt={
            "Study & notes":"Act as a patient tutor. Explain step by step with examples.",
            "Creator studio":"Act as a creative producer for short videos, YouTube, hooks, and scripts.",
            "Editing assistant":"Help edit video, audio, photos, reels, and written content. Give practical editing steps, recommend useful cuts, pacing, captions, transitions, sound design, and export settings. Ask which editing app only if needed.",
            "Quick concise answers":"Answer conversationally in short, clear phrases. Lead with the answer, use simple words, avoid long explanations, and give no more than 3 bullets unless asked for detail.",
            "Interview practice":"Act as an interviewer. Ask one question at a time and give constructive feedback.",
            "Explain a concept":"Explain simply first, then deepen with an example and recap.",
            "Code helper":"Give runnable code, explain where it goes, and avoid fake functionality.",
            "General assistant":"Help with the user's request."
        }.get(m,"Help with the user's request.")
    def ask(self):
        prompt=self.input.toPlainText().strip()
        if self.short_check.isChecked():
            prompt = "Keep your response short, clear, and conversational. Use simple phrases and no more than 3 bullets unless detail is requested.\n\n" + prompt
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
    def capture_screen(self):
        self.hide(); QTimer.singleShot(650,self._capture)
    def _capture(self):
        try:
            screen=QGuiApplication.primaryScreen()
            if not screen: raise RuntimeError("No screen available")
            pix=screen.grabWindow(0); fd,path=tempfile.mkstemp(prefix="aura_screen_",suffix=".png"); os.close(fd); pix.save(path,"PNG")
            self.image_path=path; self.file_label.setText("Screenshot captured — Gemini can inspect it")
            self.show_focus(); self.status("Screenshot captured — suggesting next steps...")
            self.input.setPlainText("Analyze this screenshot and suggest the 3 most useful next actions I should take based on what is visible. Be specific, concise, and do not assume anything that cannot be seen.")
            QTimer.singleShot(150, self.ask)
        except Exception as e: self.show_focus(); self.status("Screenshot failed: "+str(e))
    def voice(self):
        if not AUDIO_OK:
            self.say("AURA","Voice recording dependencies are missing. Run install.ps1 and restart."); return
        self.talk.setEnabled(False); self.talk.setText("Listening..."); self.status("Listening for up to 8 seconds...")
        w=RecordWorker(); w.started_recording.connect(lambda:self.status("Listening...")); w.finished_path.connect(self.voice_ready); w.error.connect(self.voice_error); self.workers.append(w); w.start()
    def voice_ready(self,path):
        self.talk.setText("Talk"); self.talk.setEnabled(True); self.say("YOU","[Voice message]"); self.status("Sending audio to Gemini...")
        w=AskWorker("Understand the spoken request in this audio and answer naturally.",os.getenv("GEMINI_MODEL",MODEL),audio=path,parent=self)
        w.ok.connect(self.answer); w.error.connect(self.failed); w.finished.connect(self.enable); self.workers.append(w); w.start()
    def voice_error(self,msg): self.talk.setText("Talk"); self.talk.setEnabled(True); self.status("Microphone unavailable"); self.say("AURA",msg)
    def _speech_text(self, text):
        """Remove Markdown and code from the spoken version of an answer."""
        text = re.sub(r"```.*?```", " Code block omitted. ", text or "", flags=re.S)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
        text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.M)
        text = re.sub(r"\*\*(.*?)\*\*|__(.*?)__", lambda m: m.group(1) or m.group(2) or "", text)
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)|(?<!_)_([^_]+)_(?!_)", lambda m: m.group(1) or m.group(2) or "", text)
        text = re.sub(r"\[([^\]]+)\]", r"\1", text)
        text = re.sub(r"[>#~]", "", text)
        text = re.sub(r"\n{2,}", ". ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _load_voices(self):
        """Offer up to three real voices installed on this Windows computer."""
        if not TTS_OK:
            self.voice_choice.setEnabled(False)
            self.voice_choice.setToolTip("Install pyttsx3 / Windows speech voices to enable voice selection")
            return
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            engine.stop()
            self._voice_ids = [getattr(v, "id", "") for v in voices[:3]]
            labels = []
            for i, voice in enumerate(voices[:3]):
                name = getattr(voice, "name", "") or f"Windows voice {i+1}"
                labels.append(name[:28])
            if labels:
                self.voice_choice.clear()
                self.voice_choice.addItems(labels)
            else:
                self.voice_choice.clear(); self.voice_choice.addItem("System default")
        except Exception:
            self._voice_ids = []
            self.voice_choice.clear(); self.voice_choice.addItem("System default")

    def speak(self,text):
        if not TTS_OK: return
        clean = self._speech_text(text)
        if not clean: return
        selected = self.voice_choice.currentIndex() if hasattr(self, "voice_choice") else 0
        voice_id = self._voice_ids[selected] if getattr(self, "_voice_ids", []) and selected < len(self._voice_ids) else None
        def run():
            try:
                engine=pyttsx3.init()
                if voice_id:
                    engine.setProperty("voice", voice_id)
                engine.setProperty("rate", 165)
                engine.setProperty("volume", 0.9)
                engine.say(clean[:3500]); engine.runAndWait(); engine.stop()
            except Exception: pass
        threading.Thread(target=run,daemon=True).start()
    def clear_chat(self): self.chat.clear(); self.say("AURA","Conversation cleared. What would you like to work on?"); self.status("Ready")
    def presentation(self):
        self.hide()
        if self.tray: self.tray.showMessage("AURA AI","Hidden for presentation. Press Ctrl+Space to restore.",QSystemTrayIcon.MessageIcon.Information,2200)
    def toggle_visible(self): self.hide() if self.isVisible() else self.show_focus()
    def show_focus(self): self.show(); self.raise_(); self.activateWindow(); self.input.setFocus()
    def toggle_compact(self):
        self.compact=not self.compact
        for x in [self.status_label,self.mode,self.chat,self.screen,self.attach,self.file_label,self.input,self.talk,self.speak_check,self.short_check,self.voice_choice,self.test_voice_btn,self.send]: x.setVisible(not self.compact)
        self.resize(260,68) if self.compact else self.resize(460,750)
        self.compact_btn.setText("+" if self.compact else "-")
        if self.compact: self.move_corner()
        else: self.move_corner()
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
    def closeEvent(self,e): e.ignore(); self.hide()

def main():
    app=QApplication(sys.argv); app.setApplicationName("AURA AI"); app.setQuitOnLastWindowClosed(False)
    w=Aura(); w.show(); sys.exit(app.exec())
if __name__=="__main__": main()
