# AURA AI Website

Static, responsive landing page for [AURA AI](https://github.com/nilabh101/AURA-AI). Built with plain HTML, CSS, and JavaScript; no build step required.

## Preview locally

Open `index.html` in a browser, or run a local server from this folder:

```powershell
py -m http.server 8080
```

Then open http://localhost:8080.

## Publish on GitHub Pages

1. Copy `website/` into the root of the `nilabh101/AURA-AI` repository.
2. Commit and push the files.
3. On GitHub, open **Settings → Pages**.
4. Under **Build and deployment**, choose **Deploy from a branch**.
5. Select `main` and `/ (root)` if publishing files at repository root, or `/website` only if your Pages UI offers that folder. Recommended: put the website files at the repository root or use a `/docs` folder. For this kit, copying `index.html`, `styles.css`, `script.js`, and `assets/` into a root-level `docs/` folder and selecting `/docs` is a clean approach.
6. Save and wait for the Pages deployment workflow to complete. GitHub will show the actual live URL in Settings → Pages.

The site links to the existing GitHub repository. It does not claim a downloadable binary is available; add a release/download link only after publishing a tested release artifact.
