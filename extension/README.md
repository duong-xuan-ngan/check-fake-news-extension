# VeriFact Chrome extension

`extension/` is the unpacked Chrome extension directory. Its generated `content.js` is built from `../extension-src`.

Build it with `npm install && npm run build` from `extension-src`, then load this directory through `chrome://extensions` with Developer mode enabled. The backend must be available at the configured `VITE_API_BASE` (development default `http://localhost:8000`, from the root `.env`; production reads `production/.env`).
