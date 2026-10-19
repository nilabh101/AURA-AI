# AURA AI — Your Windows Desktop Copilot

AURA AI is a floating Windows desktop assistant built with Python, PySide6, Google Gemini, and optional ElevenLabs text-to-speech. It is designed to provide quick help while you study, create, code, or explore without switching away from your current task.

> **Project status:** Working personal/developer build being prepared for public release. Installer builds, clean-machine testing, privacy documentation, and release downloads should be completed before describing it as production-ready.

## Current features

- Gemini-powered chat using your own Google AI API key.
- Floating desktop window, compact mode, and `Ctrl + Space` shortcut where supported.
- Optional ElevenLabs spoken replies, with local Windows speech fallback.
- Voice input: records a short microphone clip and sends it to Gemini for interpretation.
- Screen capture: captures a screenshot when requested and submits it to Gemini with your request.
- Text extraction from supported text files, PDF, and DOCX documents.
- Focus modes for general help, study and notes, creator work, interview practice, concept explanations, and coding.
- Explicit exit from the window or system-tray menu.

Feature availability depends on OS permissions, installed dependencies, provider availability, and API account limits. AURA does not currently provide a hosted AI backend; users supply their own provider keys.

## Requirements

- Windows 10/11 (primary target; other platforms are not currently tested).
- Python 3.11 recommended for running from source.
- Google Gemini API key.
- Optional ElevenLabs API key for online voices.
- Microphone and screen-capture permissions for those features.

## Run from source

```powershell
git clone https://github.com/nilabh101/AURA-AI.git
Set-Location AURA-AI
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Add your own provider keys to `.env`:

```dotenv
GEMINI_API_KEY=your_gemini_secret_key
GEMINI_MODEL=gemini-2.5-flash
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

Then launch with `python app.py` (or the project's `run.ps1` if present). Never commit `.env`, share screenshots containing keys, or paste secrets into issue reports.

## Build a Windows app folder

The starter packaging script uses PyInstaller to create `dist\AURA-AI`. Run on Windows with Python 3.11 and a working virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
.\packaging\build-windows.ps1
```

This is an initial packaging candidate, not a signed installer. Test it on a clean Windows machine before distribution. Do not bundle your personal `.env` or API keys. Each user must add their own keys locally.

## Website

The static download site is in [`docs/`](docs/). Its download button points to GitHub Releases; it will only offer a real installer once you create and upload a release asset.

To publish using GitHub Pages:

1. Push the `docs` folder to the repository.
2. Open GitHub **Settings → Pages**.
3. Choose **Deploy from a branch** and select `main` and set the publishing folder to `/docs`.
4. Save and wait for GitHub Pages to publish the site.

## Before a public release

- Build on Windows using the documented Python version.
- Test on a clean Windows machine without Python installed.
- Test missing/invalid keys, network failure, microphone denial, screenshot flow, PDF/DOCX attachment, voice fallback, and complete exit.
- Ensure `.env`, API keys, local logs, screenshots, and temporary files are excluded from release assets.
- Publish a versioned ZIP from `dist\AURA-AI` or build a signed installer.
- Add a changelog, license decision, privacy notice, support contact, and known limitations.
- Create a GitHub Release and upload the actual build artifact.

## Privacy and security

AURA sends prompts and selected content to Google Gemini when a request is submitted. If ElevenLabs speech is used, the text to be spoken is sent to ElevenLabs. Voice recordings are sent to Gemini for interpretation. Screenshots and document text are sent when the user invokes those features and submits the request. Do not submit confidential material unless you have reviewed the providers' terms and privacy settings.

API keys are credentials. Store them locally, never commit them, and revoke/rotate them if exposed. The current bring-your-own-key model means users manage their own provider accounts, billing, limits, and data settings.

## Troubleshooting

- **Gemini authentication error:** check `GEMINI_API_KEY` in `.env` and confirm the key is active.
- **ElevenLabs voices fail to load:** check `ELEVENLABS_API_KEY`; the secret key, not a key ID, is required.
- **Windows voice plays instead:** select an ElevenLabs voice and wait for loading to complete. Online synthesis failure may trigger local fallback.
- **Microphone error:** check Windows microphone privacy settings and input-device availability.
- **App fails to start:** launch from PowerShell to see errors and confirm dependencies are installed in `.venv`.

## Technology

Python 3.11 · PySide6 / Qt · Google Gen AI SDK · ElevenLabs Python SDK (optional) · sounddevice · soundfile · NumPy · pyttsx3 · pypdf · python-docx · PyInstaller

## License

Choose and add a license before accepting outside contributions or distributing source code. Do not assume the project is open-source licensed until a `LICENSE` file is present.
