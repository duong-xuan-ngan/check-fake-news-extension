# SnapCheck Chrome extension

`extension/` is the unpacked Chrome extension directory. Its generated `content.js` /
`content.css` (content script) and `options.js` / `options.css` / `options.html` (options
page) are built from `../extension-src`.

Build it with `npm install && npm run build:dev` (development) or `npm run build`
(production) from `extension-src`, then load this directory through `chrome://extensions`
with Developer mode enabled. The backend must be available at the configured
`VITE_API_BASE` (development default `http://localhost:8000`, from the root `.env`;
production reads `production/.env`).

The extension requires a Google OAuth client id (`VITE_GOOGLE_CLIENT_ID`, inlined at build
time) matching the backend's `GOOGLE_CLIENT_ID`.
