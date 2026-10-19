# AURA AI — Windows desktop MVP

A floating Windows assistant for study notes, transcript analysis, screen explanations, and interview practice.

## Features in this starter
- Always-on-top floating window
- Global `Ctrl + Space` toggle (may require accessibility permission or elevated privileges on some systems)
- Manual screen capture with a review step
- Optional screenshot + prompt sent to the AI model
- TXT, MD, SRT, VTT, PDF and DOCX text import
- Presentation mode hides the assistant on demand
- Clear, visible AI errors rather than fake responses

## Requirements
- Windows 10/11
- Python 3.11 recommended
- An OpenAI API key and API access; API billing is separate from ChatGPT subscriptions

## Setup
1. Extract this folder.
2. Open PowerShell in the extracted `AuraAI` folder.
3. Run `Set-ExecutionPolicy -Scope Process Bypass` if PowerShell blocks local scripts.
4. Run `.un.ps1`.
5. When Notepad opens `.env`, replace the placeholder with your API key and save.
6. Run `.un.ps1` again.

Alternatively, install manually:
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python app.py
```

## Important limitations
- Screen capture is manual. Review the captured screenshot before asking the model to analyze it.
- This MVP does not automatically detect lecture highlights, record audio, monitor all apps, or automatically detect screen sharing.
- Presentation mode is an explicit privacy control, not a way to evade exam proctoring or secretly receive live interview answers.
- The screenshot is saved locally as `aura_capture.png` until cleared or overwritten. Delete it if you no longer need it.
- Never share your `.env` file or commit it to GitHub.
