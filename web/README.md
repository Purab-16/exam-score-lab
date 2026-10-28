# Exam Score Lab (web)

Next.js 16 front end for the exam score model. It talks to the FastAPI service in `../api`.

Stack: Next.js App Router, TypeScript, Tailwind CSS 4, shadcn/ui (Base UI), Recharts, SWR, next-themes.

## Run

Start the API first (from the project root): `uvicorn api.main:app --reload`. Then:

```bash
npm install
npm run dev        # http://localhost:3000
```

To point at another API, copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_URL`. The value is baked in at build time.

## Pages

| Route | What it does |
|---|---|
| `/` | Four-step profile form, score gauge with 90% range, personal tips, what-if simulator |
| `/batch` | CSV upload with row-level validation errors, results table, CSV download |
| `/insights` | Interactive charts of the dataset and predicted vs actual |

## Code map

| Path | Purpose |
|---|---|
| `src/lib/api.ts` | Typed API client and response types |
| `src/lib/hooks.ts` | SWR hooks for `/meta` and `/insights`, debounce |
| `src/components/fields.tsx` | Slider and select fields driven by `/meta` (no hard-coded ranges) |
| `src/components/predictor/` | Form, score gauge, tips, what-if |
| `src/components/batch/` | Batch upload |
| `src/components/insights/` | Charts |
| `src/app/globals.css` | Theme tokens for light and dark mode |

## Checks

```bash
npm run lint
npx tsc --noEmit
npm run build
```
