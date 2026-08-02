# Verity Admin Dashboard

Light-only administration dashboard for the fake-news detection browser
extension.

## Current status

This is a front-end prototype. The metrics are clearly marked preview data and
the database explorer is read-only UI. It is not connected to production
databases, authentication, billing, or admin APIs yet.

## Included sections

- Product overview and trust metrics
- Extension product signals: highlight usage, star rating, uninstalls, and
  7-day return rate (preview data until the analytics API is connected)
- Analysis history and filters
- Users and feedback placeholders
- Source credibility management
- CRED-1 dataset version and unknown-domain policy visibility
- AI pipeline performance and cost
- System health
- PostgreSQL, Redis, and Qdrant explorer UI
- Settings and audit placeholder

## Local development

Requires Node.js 22.13 or newer.

```bash
npm install
npm run dev
```

Create a production build with:

```bash
npm run build
```

Create the static build used by GitHub Pages with:

```bash
npm run build:github
```

The repository workflow publishes the `out/` directory to:

`https://duong-xuan-ngan.github.io/check-fake-news-extension/`
