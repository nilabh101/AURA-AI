# AURA AI — Gemini Edition

## Included
- Translucent, always-on-top, draggable PySide6 floating UI
- Compact mode and Presentation Mode
- Ctrl+Space show/hide shortcut plus system tray controls when Windows exposes a tray
- Gemini chat, screenshot analysis, document text extraction (TXT, Markdown, PDF, DOCX, SRT/VTT and code/text files)
- Click-to-talk: records up to 8 seconds and sends WAV audio to Gemini
- Optional local spoken replies via Windows text-to-speech
- Study, creator, interview, concept explanation, and code-helper modes

## Windows 11 setup
1. Install Python 3.11.
2. Extract these files into your existing AURA AI project folder, replacing `app.py`, `requirements.txt`, `.env.example`, `install.ps1`, and `run.ps1`. Keep your `.env` private.
3. Open PowerShell in the project folder and run:
   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\install.ps1
   ```
4. Create a free API key at https://aistudio.google.com/app/apikey and paste it into `.env` as `GEMINI_API_KEY=...`.
5. Run ` .\run.ps1 `.

## Notes
- Gemini free-tier quotas, model access, and regional availability can change; confirm the current limits in Google AI Studio. Free does not mean unlimited.
- Audio is sent to Google's API when Talk is used. Windows may ask for microphone permission.
- If Ctrl+Space fails, use the system tray menu or close/hide controls; global hotkeys may be blocked by permissions or another app.
- Test the app and microphone before using it during a presentation.
