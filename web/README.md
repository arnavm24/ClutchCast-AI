# ClutchCast AI — Web App

The production front end, live at [clutchcast-ai.vercel.app](https://clutchcast-ai.vercel.app). Next.js (App Router) + Tailwind + framer-motion. No Python at runtime.

## How data flows

- **Historical games** are precomputed: `python src/export_web_data.py` (run from the repo root) writes `public/data/` — the browse index, per-game timelines/players/insights, model leaderboard + calibration, and the champion model bundle.
- **The model runs in TypeScript.** `src/lib/model.ts` executes the champion MLP from exported weights; `src/lib/features.ts` ports the 85-feature engineering pipeline. Verify parity with PyTorch after re-exporting: `node scripts/parity.ts`.
- **Today's games**: NBA CDN first (fetched from the visitor's browser — the CDN blocks datacenter IPs), then the `/api/today` proxy, then ESPN's open scoreboard as final fallback.
- **Live games** (`/live/[id]`): play-by-play fetched in the browser, win probability computed client-side every 10 seconds; `/api/live/[id]` is the server fallback.

## Develop

```bash
npm install
npm run dev
```

## Ship

```bash
npm run build
node scripts/parity.ts
vercel deploy --prod --yes
```

After retraining models or analyzing new games, re-run `python src/export_web_data.py` from the repo root before building.
