# Fix and Improvement Plan

Status of the project on 2026-10-28 and the order in which issues will be fixed and features added.

Each phase builds on the one before it. Fixes come first, then new features in the same area.

## Phase 1: Make the app run again (critical) - DONE

Done on 2026-10-28. `train.py` retrains the model and writes `model_meta.json`. The app warns on a scikit-learn version mismatch and shows a clear error instead of crashing. Held-out test RMSE 5.479, R2 0.889 (909 rows, before Phase 2 fixes).

| # | Type | Problem / Idea | Plan |
|---|---|---|---|
| 1 | Fix | `best_model.pkl` was saved with scikit-learn 1.7.2. The venv has 1.9.1 and `predict()` crashes (`SimpleImputer has no attribute _fill_dtype`). | Move training into a script (`train.py`) and retrain the model with the installed versions. |
| 2 | Fix | The Streamlit app crashes on "Predict" and in the EDA tab because of #1. | Fixed by #1. Add a clear error message in the app if the model fails to load. |
| 3 | Fix | `requirements.txt` has no version pins. | Pin exact versions (`pip freeze` of the working venv). Save the scikit-learn version next to the model and warn on mismatch. |

## Phase 2: Fix and improve the ML pipeline - DONE

Done on 2026-10-28. Shared code lives in `ml/pipeline.py` (it was `model_pipeline.py` before the layout cleanup, see #62). `train.py` compares 6 models with 5-fold CV, tunes the top 2 tunable models with Optuna, adds a 90% interval and logs to MLflow. Selected: tuned Ridge, base features (engineered features did not beat base by the 0.01 RMSE threshold). CV RMSE 5.508, held-out test RMSE 5.143, R2 0.897, interval +/- 8.60 with 91.5% test coverage. The notebook is now EDA only.

### 2a. Fixes

| # | Type | Problem / Idea | Plan |
|---|---|---|---|
| 4 | Fix | Data leakage: final model is fit on all data, then "tested" on `X_test`. | Report test metrics only from the model trained on `X_train`. Refit on all data only after evaluation, and do not re-score it. |
| 5 | Fix | `dropna()` removes 91 rows (9%). The pipeline already imputes. | Remove `dropna()`. Keep all 1,000 rows. |
| 6 | Fix | `parental_education_level` missing values are imputed with `most_frequent`. | Impute with a constant `"Unknown"` so "missing" becomes its own category. This also makes the app's "Unknown" option meaningful. |
| 7 | Fix | 36 predictions fall outside 0 to 100. | Clip in the pipeline output and report how often it happens. |
| 8 | Fix | Unused imports, `%pip install` and `import streamlit` in the notebook. | Clean the notebook. Keep it for EDA only. Training lives in `train.py`. |

### 2b. Improvements

| # | Type | Problem / Idea | Plan |
|---|---|---|---|
| 9 | Feature | Feature engineering. | Add derived features inside the pipeline: `total_screen_time = social_media_hours + netflix_hours`, `study_to_sleep_ratio`, `study_x_attendance`. Keep them only if CV improves. |
| 10 | Fix + Feature | No cross-validation and only one model tried. | 5-fold CV for Linear Regression, Ridge, Random Forest, Gradient Boosting, XGBoost and LightGBM. Pick the best by CV RMSE. Evaluate once on the held-out test set. |
| 11 | Feature | No hyperparameter tuning. | Tune the top 2 models with Optuna inside CV (training data only). |
| 12 | Feature | Prediction is a single number with no uncertainty. | Add prediction intervals (quantile models or residual-based conformal intervals), e.g. "72 ± 5". |
| 13 | Feature | Experiments are not tracked. | Log params, metrics and the model for every run with MLflow (local `mlruns/`, ignored by git). |

## Phase 3: Fix and improve the app - DONE

Done on 2026-10-28. The app now has three tabs (Single Student, Batch Prediction, Dataset Insights). Non-UI logic (ranges, what-if, tips, CSV validation) lives in `insights.py` so it can be unit tested in Phase 4. #18 was already done in Phase 1.

### 3a. Fixes

| # | Type | Problem / Idea | Plan |
|---|---|---|---|
| 14 | Fix | After the first click, every slider change re-predicts. | Use `st.form` so prediction runs only on submit. |
| 15 | Fix | Slider ranges go beyond the training data. | Limit sliders to the data min and max. Show a warning if a value is near the edge. |
| 16 | Fix | Heatmap and scatter plots use predicted score, not actual `exam_score`. | Use actual `exam_score` for EDA. Add a separate "Predicted vs Actual" plot. |
| 17 | Fix | Global SHAP is recomputed on every rerun. | Cache the explainer and global SHAP values with `st.cache_resource` / `st.cache_data`. |
| 18 | Fix | Relative file paths break when run from another folder. | Build paths from `Path(__file__).parent`. |

### 3b. New features

| # | Type | Problem / Idea | Plan |
|---|---|---|---|
| 19 | Feature | Show uncertainty. | Display the prediction interval from #12 next to the score. |
| 20 | Feature | What-if simulator. | Let the user change one habit (e.g. +2 study hours) and show the new score and the difference side by side. |
| 21 | Feature | Personal tips. | Use the student's SHAP values to list the top 3 habits pulling the score down, with a suggested change and its predicted effect (from #20). |
| 22 | Feature | Batch prediction. | Upload a CSV of students, validate the columns, predict all rows, download results as CSV. |

## Phase 4: Tests and docs - DONE

Done on 2026-10-28. 31 `pytest` tests in `tests/` (pipeline, saved model and metadata, insights, CSV validation, headless app run). README rewritten with real numbers. SHAP plots were removed from the app on request; SHAP still powers the personal tips.

| # | Type | Problem / Idea | Plan |
|---|---|---|---|
| 23 | Fix | No tests. | Add `pytest` tests: model loads, predicts on a sample row, output is within 0 to 100, input schema matches, batch CSV validation works. |
| 24 | Fix | README claims CV results and an imputer that do not exist. | Rewrite the README with the real numbers produced by `train.py` and document the new features. |
| 25 | Fix | README says Python 3.13, venv is 3.14. | State the tested Python version. |

## Phase 5: New frontend (FastAPI + Next.js) - DONE

Done on 2026-10-28. `api/` (7 endpoints, 19 tests) and `web/` (Next.js 16, three pages, light and dark mode, mobile layout). Checked in a real browser: predict, tips, what-if, stale-profile hint, batch upload and download, bad-CSV errors, charts, mobile without horizontal scroll, and a clear message when the API is down. #33: the Streamlit app and its test were removed on the owner's request, and `streamlit` was dropped from `requirements.txt`.

Streamlit reruns the whole page on every interaction and limits design control. The app moves to a FastAPI backend and a Next.js frontend. The Streamlit app stays until the new frontend reaches feature parity.

| # | Type | Problem / Idea | Plan |
|---|---|---|---|
| 27 | Feature | Model is only usable inside Streamlit. | `api/` FastAPI service reusing `ml/pipeline.py` and `ml/insights.py`: `GET /health`, `GET /meta` (model info, input ranges, category options), `POST /predict` (score, interval, edge warnings, tips), `POST /what-if`, `POST /predict/batch` (CSV upload, validation, results), `GET /insights` (data for charts). Pydantic schemas, CORS for the frontend, pytest tests with `TestClient`. |
| 31 | Feature | New UI. | `web/` Next.js (App Router, TypeScript) + Tailwind CSS + shadcn/ui + Recharts. Pages: single student (stepped form, score gauge with range, tip cards, what-if sliders), batch upload (drag and drop, error table, download), insights (interactive charts). Input limits come from `GET /meta`, not hard-coded. |
| 32 | Feature | Frontend quality. | Typed API client, loading and error states, mobile layout, dark mode, basic accessibility (labels, keyboard, contrast). |
| 33 | Fix | Two UIs to maintain. | Retire the Streamlit app once the Next.js app covers all features. |

## Phase 6: Production and deployment - IN PROGRESS

2026-10-28: #28 and #29 written (`api/Dockerfile`, `web/Dockerfile`, `docker-compose.yml`, `requirements-api.txt`, `.github/workflows/ci.yml`). Docker verified locally the same day: both images build (api 964 MB, web 337 MB), `docker compose up --wait` reports both healthy, containers run as non-root, and the full browser test passes against the stack. #26 waits for the owner's approval of the exact git commands. #30 needs Railway and Vercel accounts.

| # | Type | Problem / Idea | Plan |
|---|---|---|---|
| 26 | Fix | Not a git repository. | Initialize git only with the owner's approval. Every git/gh command needs approval. |
| 28 | Feature | Hard to run on another machine. | `Dockerfile` for the API and the web app, and a `docker-compose.yml` to run both. |
| 29 | Feature | No CI. | GitHub Actions workflow: Python tests (`pytest`) and frontend lint, type check and build on every push and PR. |
| 30 | Feature | No live demo. | Deploy the API (Railway or Render) and the web app (Vercel), and add the link to the README. |

## Phase 7: Security, performance and image size - PROPOSED (awaiting owner approval)

Only Step 0 and the project layout cleanup (#62) are done so far. The rest is not implemented yet. The measurements below were taken on 2026-10-28 against the running Docker stack:

| Finding | Measured |
|---|---|
| Security headers | None on the API. None on the web app (no CSP, HSTS, X-Frame-Options, nosniff) |
| Version leaks | `X-Powered-By: Next.js` and `server: uvicorn` |
| API docs | `/docs`, `/redoc`, `/openapi.json` are public |
| `/insights` | 191 KB uncompressed, 34 KB with gzip (82% smaller) |
| `/predict` | about 35 ms warm. Speed is not the bottleneck |
| Upload limit | Checked after the whole file is read into memory |
| `/predict/batch` | `async def` doing CPU-heavy pandas work, so it blocks the event loop |
| API image | 919 MB. `llvmlite` and `numba` (207 MB) exist only because of `shap`. A trial image without them, with tests and `.pyc` removed, was 447 MB and loaded the model and predicted correctly |
| CSV download | Echoes user columns, so a cell starting with `=`, `+`, `-` or `@` can run as a formula in Excel |

### Safety rules for this phase (set by the owner on 2026-10-28)

New features must not hurt the project later, must work well, and any damage must be revertible. So:

| Rule | How |
|---|---|
| Revertible | One git commit per step (owner approves each git command). Rolling a step back is `git revert <commit>`. A source snapshot also exists from before Phase 7. |
| Kill switches | Each new behaviour has an environment setting with a safe default: `API_ENV` (docs), `RATE_LIMIT_ENABLED`, `GZIP_ENABLED`, `CSP_MODE` (`enforce`, `report-only` or `off`). A bad feature can be switched off without a code change. |
| Additive only | API responses keep their current shape. New fields and headers are added, nothing is renamed or removed. The web app keeps working against the old and the new API. |
| Old path keeps working | The current direct stack (`docker compose up`, ports 3000 and 8000) stays as it is. The nginx proxy is an extra override file. It becomes the default only if the owner approves after seeing it work. |
| Prove before commit | Python tests, web lint, type check and build, the browser test and the Docker stack must pass before a step is committed. Each new item gets its own test. |
| Safer first | CSP is tried in `report-only` mode in the browser test first, and enforced only after zero violations. |
| No silent deletes | Nothing existing is deleted without a copy in git or the snapshot. |
| Rollback note | Every step records in this file what it changed and how to undo it. |

### Step 0: Safety net and baseline - #35 DONE, #34 waiting for git approval

| # | Item | Plan |
|---|---|---|
| 34 | Safety net | Many files change in this phase. Preferred: `git init` and a first commit (owner approves each git command), then one commit per step so any step can be reverted. Alternative without git: a full snapshot copy of the project outside the repo before each step. A snapshot of the sources (4.8 MB, 526 files, without `.venv`, `node_modules`, `.next`, `mlruns`) was taken on 2026-10-28 before any Phase 7 change. |
| 35 | Baseline audit (read-only) | DONE 2026-10-28. Results below. No code was changed. |
| 62 | Project layout cleanup | DONE 2026-10-28, before the first commit. Python code moved into `ml/` (`pipeline.py`, `insights.py`, `train.py`) with one `ml/paths.py` for all file locations. Data in `data/`, trained model and metadata in `models/`, the notebook is `notebooks/eda.ipynb`, this plan is `docs/PLAN.md`. A root `train.py` shortcut keeps `python train.py` working. The API image copies only the runtime modules (not `ml/train.py`). Checked: 50 tests, every notebook cell, training in a scratch copy (the real model was untouched), the Docker stack and the browser test (same results as before). Undo: restore `snapshot-before-restructure.tgz` from the scratchpad, made right before the move. |

Baseline results:

| Tool | Result | What it means |
|---|---|---|
| `bandit` on our Python code | No issues (749 lines) | Nothing to fix |
| `npm audit` (web) | 3 low, all through `shadcn` (a build-time CLI) and `deepmerge` | Not in the running app. Accept. The suggested `--force` fix is a breaking downgrade, so it is not applied |
| `pip-audit`, pinned `requirements.txt` | None | Direct dependencies are clean |
| `pip-audit`, full dev venv (with transitive packages) | `pillow` 12.3.0 (10 CVEs, fixed in 13.0.0), `urllib3` 2.7.0 (fixed in 2.8.0), `pip` 26.1.2 (fixed in 26.2) | Dev environment only (matplotlib, mlflow). None of them is in the API image. CI would still fail on them, so they get pinned (#61) |
| Trivy, API image | 44 HIGH in Debian OS packages (`util-linux`, `ncurses`, `systemd` libs, `perl-base`) with no fix released yet, plus 3 fixable HIGH (`msgpack`, `urllib3`, `setuptools`) | The 3 are copies bundled inside `pip` itself, not our app. Removing `pip` from the final image clears them (#49). The OS ones cannot be fixed by us: reduce exposure with non-root, `cap_drop`, `read_only` (#54), and let CI ignore unfixed ones |
| Trivy, web image | 11 HIGH, all inside `/usr/local/lib/node_modules/npm` | That is the npm CLI from the Node base image. The runtime only runs `node server.js`, so removing npm and npx from the final stage clears all of them (#54) |

### Step 1: API hardening (`api/`)

| # | Item | Plan |
|---|---|---|
| 36 | Security headers | Middleware: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Permissions-Policy`, and `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (not on docs routes). `Cache-Control: no-store` on POST routes. Run uvicorn with `--no-server-header`. |
| 37 | Compression | `GZipMiddleware(minimum_size=1024)`. The browser calls the API directly, so the web host does not compress these responses. |
| 38 | Cache headers | `Cache-Control: public, max-age=300` and an `ETag` (with 304 support) on `/meta`, `/insights`, `/template.csv`. They only change when the model is retrained. |
| 39 | Docs control | `API_ENV=production` turns off `/docs`, `/redoc` and `/openapi.json`. On locally. The Docker image sets production. |
| 40 | Body size limit | ASGI middleware rejects by `Content-Length` and by counting streamed bytes (413) before the upload is parsed. The 10,000-row limit stays. |
| 41 | Batch off the event loop | Run the pandas and prediction part in a thread pool. Acceptance: `/health` answers while a 10,000-row batch runs. |
| 42 | Rate limiting | `slowapi` (check Python 3.14 compatibility, otherwise a small custom limiter), per client IP: `/predict` and `/what-if` 60/min, `/predict/batch` 6/min, others 120/min. 429 with `Retry-After`. `--proxy-headers` so the real IP is used behind a proxy. |
| 43 | Stricter input | `extra="forbid"` on the student model and `max_length` on string fields, so unknown fields give 422 instead of being ignored. |

### Step 2: Web hardening (`web/`)

| # | Item | Plan |
|---|---|---|
| 44 | Headers | `poweredByHeader: false` and `headers()` in `next.config.ts`: CSP, HSTS, `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`. |
| 45 | CSP choice | Header-based CSP with `'unsafe-inline'` for scripts and styles, plus `connect-src 'self'` and the API origin, `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`. Reason: a nonce-based CSP forces dynamic rendering and is incompatible with Partial Prerendering (Next.js docs), and SRI does not cover the inline theme script from `next-themes`. Limit: it does not stop injected inline scripts, but the app renders no user-supplied HTML and React escapes output. |
| 46 | CSV injection guard | In the results download, text cells starting with `=`, `+`, `-`, `@`, tab or CR get a leading `'`. Numbers are untouched. |
| 47 | Typed API contract | Export the OpenAPI schema offline (`python -m api.export_openapi` writes `api/openapi.json`), generate `web/src/lib/api-types.ts` with `openapi-typescript`, replace hand-written types where possible, and let CI fail if the generated files are stale. |

### Step 3: Image slimming

| # | Item | Plan |
|---|---|---|
| 48 | Contributions without SHAP | For linear models use `coef * (x - mean)` with the mean of all 1,000 rows. This equals SHAP over all 1,000 rows exactly (max difference 0.0). SHAP stays as a lazily imported fallback for tree models. |
| 49 | Smaller API image | Remove `shap` from `requirements-api.txt`, use `pip install --no-compile`, delete test folders and `.pyc` after install, drop `NUMBA_CACHE_DIR`, and remove `pip` from the final image (`pip uninstall -y pip`, clears the 3 fixable Trivy findings). Expected: 919 MB to about 450 MB. |
| 50 | Tests | Formula equals SHAP on the full background (`requirements.txt` keeps `shap` for dev and CI). `test_requirements` still guards tree models. |
| 61 | Dev dependency fixes | Pin `pillow` 13.0.0, `urllib3` 2.8.0 and `pip` 26.2 in `requirements.txt` after checking that matplotlib and mlflow still work, so `pip-audit` is clean in CI. |

Behaviour change to accept: today the tips use SHAP with a 100-row background. With the full 1,000-row mean the tip list differs for about 50 of 300 sampled students (17%). The new values are the more accurate ones.

### Step 4: Reverse proxy and containers

| # | Item | Plan |
|---|---|---|
| 51 | nginx service | Added as an override file `docker-compose.proxy.yml`, so the current direct stack (`docker compose up`, ports 3000 and 8000) keeps working unchanged. In proxy mode: a pinned, unprivileged nginx image is the only published port (8080 locally). `/api/` goes to the API (prefix stripped), `/` goes to the web app. API and web are not published. The web app is built with `NEXT_PUBLIC_API_URL=/api`, so there is one origin: no CORS and CSP `connect-src 'self'`. |
| 52 | nginx settings | `server_tokens off`, hide `X-Powered-By`, HSTS (HTTPS only), gzip for json, js, css, csv, svg, `client_max_body_size` 6m on batch and 1m elsewhere, short client timeouts, `limit_req` with burst and `limit_conn`, 5-minute proxy cache for `/api/meta`, `/api/insights`, `/api/template.csv`, forwarded headers. The apps keep setting the other security headers (one source of truth). |
| 53 | TLS | Documented template for a VPS: Let's Encrypt with certbot, or Caddy as a simpler alternative. Needs a real domain, so it is documented but not verified locally. |
| 54 | Container hardening | In `docker-compose.yml`: `read_only: true` with tmpfs for `/tmp` and `.next/cache`, `cap_drop: [ALL]`, `no-new-privileges`, `mem_limit`, `pids_limit`, health checks. In `web/Dockerfile`, remove npm and npx from the final stage (clears all 11 Trivy findings in the web image). |

### Step 5: CI security (needs git and GitHub, every git or gh command needs approval)

| # | Item | Plan |
|---|---|---|
| 55 | Scans in CI | `pip-audit`, `npm audit --omit=dev`, Trivy image scan (fail on fixable HIGH and CRITICAL), `bandit`, `gitleaks`, `ruff`. |
| 56 | API fuzzing | `schemathesis` against the running API, driven by the OpenAPI schema. |
| 57 | Dependabot | `.github/dependabot.yml` for pip, npm, docker and github-actions. |

### Step 6: At deploy time (needs accounts)

| # | Item | Plan |
|---|---|---|
| 58 | Cloudflare | In front of the deployment: CDN, DDoS protection, WAF, TLS, Brotli. |
| 59 | Platform settings | `API_ENV=production`, `API_CORS_ORIGINS`, build-time `NEXT_PUBLIC_API_URL`, HSTS from the platform or Cloudflare. |
| 60 | Optional monitoring | Sentry for errors, `prometheus-fastapi-instrumentator` for metrics. |

### Not planned, and why

| Item | Reason |
|---|---|
| Helmet | Node and Express only. The same headers are set in the Next.js config and the API middleware. |
| Auth or API keys | No private data is stored or returned. Rate limiting covers abuse. |
| Brotli in nginx | Needs a custom nginx build. Cloudflare provides it at deploy time. |
| Kubernetes | Too much for two small services. |
| Model SHA256 check | The model comes from the same repo. Revisit if models are ever downloaded. |

### Decisions needed (defaults are used if the owner does not choose)

| # | Decision | Default |
|---|---|---|
| D1 | Reverse proxy | nginx (Caddy is the simpler alternative) |
| D2 | Docs in production | Off |
| D3 | CSP style | Header-based with `'unsafe-inline'`, keeps static pages |
| D4 | Rate limits | As in #42 |
| D5 | Accept the tip changes from #48 | Yes |
| D6 | nginx proxy as the default local setup (`localhost:8080`) | Changed by the safety rules: the direct stack stays the default. The proxy runs through the override file. Make it the default later, only with the owner's approval |
| D7 | Safety net (#34) | Git, with approval of each command |

### Order and acceptance

Order: 0, 1, 2, 3, 4, 5, 6. Step 4 depends on Steps 1 and 2 (the proxy relies on the app headers). The CSP is built from `NEXT_PUBLIC_API_URL` at build time: it allows the API origin in direct mode and only `'self'` in proxy mode.

After every step:

- `python -m pytest` passes, with new tests for each item (headers, gzip, ETag and 304, docs off in production, 413, 429, unknown field gives 422, `/health` answers during a large batch).
- `npm run lint`, `npx tsc --noEmit` and `npm run build` pass.
- The browser test passes with a `securitypolicyviolation` listener reporting zero CSP violations.
- `docker compose up --build` is healthy and `curl -I` shows the expected headers.
- From Step 4: 429 on a request burst, and 413 from nginx for a 7 MB upload.

## Verification after each phase

- `python train.py` runs end to end and prints CV and test metrics.
- `pytest` passes.
- Until Phase 5: the Streamlit app loaded and predicted without errors (it was removed in Phase 5).
- From Phase 5: the API answers `/health` and `/predict`, API tests pass, and `npm run build` succeeds for the web app.
- From Phase 6: the Docker images build and run with `docker compose up`.
- From Phase 7: the checks listed under "Order and acceptance" in Phase 7.
