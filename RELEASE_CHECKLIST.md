# AURA AI — First Public Release Checklist

## Before packaging
- [ ] Confirm README matches the latest code and dependencies.
- [ ] Ensure `.env` is ignored by Git and never staged.
- [ ] Choose and add a LICENSE file.
- [ ] Add a privacy notice and support contact.
- [ ] Review Google Gemini and ElevenLabs terms, costs, and key permissions.

## Windows build
- [ ] Build using Python 3.11 on Windows.
- [ ] Run ` .\packaging\build-windows.ps1`.
- [ ] Confirm no personal `.env` is copied to `dist`.
- [ ] Test on a clean Windows 10/11 machine without Python installed.
- [ ] Test first launch with missing keys and follow setup instructions.
- [ ] Test valid/invalid Gemini key and network failure.
- [ ] Test ElevenLabs voice list, selected voice, and failed-synthesis fallback.
- [ ] Test microphone permissions and voice request.
- [ ] Test screen capture and TXT/MD/PDF/DOCX attachments.
- [ ] Test X button and tray exit; confirm process ends in Task Manager.
- [ ] Check Windows SmartScreen/signing expectations; do not claim the app is signed unless it is.

## Publish
- [ ] Zip the complete `dist\AURA-AI` folder.
- [ ] Create a GitHub Release with a version (e.g. `v0.1.0`).
- [ ] Upload the ZIP and add release notes and SHA-256 checksum.
- [ ] Verify the release download from a separate browser/session.
- [ ] Publish the `docs` folder with GitHub Pages.
- [ ] Only then announce that downloads are available.
