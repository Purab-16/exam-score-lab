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

2026-10-28: #28 and #29 written (`api/Dockerfile`, `web/Dockerfile`, `docker-compose.yml`, `requirements-api.txt`, `.github/workflows/ci.yml`). Docker verified locally the same day: both images build (api 964 MB, web 337 MB), `docker compose up --wait` reports both healthy, containers run as non-root, and the full browser test passes against the stack. #26: the local repository and baseline commit are done, pushing to GitHub waits for the owner's go-ahead (repository name, public or private). #30 needs Railway and Vercel accounts.

| # | Type | Problem / Idea | Plan |
|---|---|---|---|
| 26 | Fix | Not a git repository. | Initialize git only with the owner's approval. Every git/gh command needs approval. Local repo and baseline commit `aeb4d30` done on 2026-10-28. Pushing to GitHub is still pending. |
| 28 | Feature | Hard to run on another machine. | `Dockerfile` for the API and the web app, and a `docker-compose.yml` to run both. |
| 29 | Feature | No CI. | GitHub Actions workflow: Python tests (`pytest`) and frontend lint, type check and build on every push and PR. |
| 30 | Feature | No live demo. | Deploy the API (Railway or Render) and the web app (Vercel), and add the link to the README. |

## Phase 7: Security, performance and image size - IN PROGRESS (steps 0 to 5 done, step 6 needs accounts)

Steps 0, 1, 2, 3, 4 and 5, the project layout cleanup (#62) and the web Dockerfile fix (#63) are done so far. Step 6 is not implemented yet (it needs accounts). The measurements below were taken on 2026-10-28 against the running Docker stack:

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

### Step 0: Safety net and baseline - DONE

| # | Item | Plan |
|---|---|---|
| 34 | Safety net | DONE 2026-10-28: local git repository created and the baseline commit `aeb4d30` made (78 files). From here on, one commit per step. Original reasoning: many files change in this phase. Preferred: `git init` and a first commit (owner approves each git command), then one commit per step so any step can be reverted. Alternative without git: a full snapshot copy of the project outside the repo before each step. A snapshot of the sources (4.8 MB, 526 files, without `.venv`, `node_modules`, `.next`, `mlruns`) was taken on 2026-10-28 before any Phase 7 change. |
| 35 | Baseline audit (read-only) | DONE 2026-10-28. Results below. No code was changed. |
| 62 | Project layout cleanup | DONE 2026-10-28, before the first commit. Python code moved into `ml/` (`pipeline.py`, `insights.py`, `train.py`) with one `ml/paths.py` for all file locations. Data in `data/`, trained model and metadata in `models/`, the notebook is `notebooks/eda.ipynb`, this plan is `docs/PLAN.md`. A root `train.py` shortcut keeps `python train.py` working. The API image copies only the runtime modules (not `ml/train.py`). Checked: 50 tests, every notebook cell, training in a scratch copy (the real model was untouched), the Docker stack and the browser test (same results as before). Undo: restore `snapshot-before-restructure.tgz` from the scratchpad, made right before the move. |
| 63 | Web Dockerfile and empty `public/` | DONE 2026-10-28. Git does not track empty folders, and `COPY .../public` failed on a fresh clone without `public/` (reproduced in a scratch copy). `web/Dockerfile` now runs `RUN mkdir -p public` in the build stage, and the `.gitkeep` placeholder was removed. Checked: the build passes without `public/`. Undo: revert the commit. |

Baseline results:

| Tool | Result | What it means |
|---|---|---|
| `bandit` on our Python code | No issues (749 lines) | Nothing to fix |
| `npm audit` (web) | 3 low, all through `shadcn` (a build-time CLI) and `deepmerge` | Not in the running app. Accept. The suggested `--force` fix is a breaking downgrade, so it is not applied |
| `pip-audit`, pinned `requirements.txt` | None | Direct dependencies are clean |
| `pip-audit`, full dev venv (with transitive packages) | `pillow` 12.3.0 (10 CVEs, fixed in 13.0.0), `urllib3` 2.7.0 (fixed in 2.8.0), `pip` 26.1.2 (fixed in 26.2) | Dev environment only (matplotlib, mlflow). None of them is in the API image. CI would still fail on them, so they get pinned (#61) |
| Trivy, API image | 44 HIGH in Debian OS packages (`util-linux`, `ncurses`, `systemd` libs, `perl-base`) with no fix released yet, plus 3 fixable HIGH (`msgpack`, `urllib3`, `setuptools`) | The 3 are copies bundled inside `pip` itself, not our app. Removing `pip` from the final image clears them (#49). The OS ones cannot be fixed by us: reduce exposure with non-root, `cap_drop`, `read_only` (#54), and let CI ignore unfixed ones |
| Trivy, web image | 11 HIGH, all inside `/usr/local/lib/node_modules/npm` | That is the npm CLI from the Node base image. The runtime only runs `node server.js`, so removing npm and npx from the final stage clears all of them (#54) |

### Step 1: API hardening (`api/`) - DONE

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

Step 1 result (2026-10-28):

- Checked: 92 Python tests (the 50 existing ones unchanged, plus 42 new in `tests/test_api_hardening.py`), the Docker stack, the browser test (same numbers as before) and a byte-for-byte comparison of 10 API responses before and after (all identical, so no response shape changed).
- Measured on the Docker stack: `/insights` 190,953 bytes down to 32,605 with gzip; `/meta` answers `304` with `If-None-Match`; a 20 MB upload gets `413` in 3 ms; `/predict` answers `429` with `Retry-After` after 60 requests a minute and `/health` is never limited; `/docs`, `/redoc` and `/openapi.json` return 404 in the Docker image; the `server:` header is gone.
- How it is built: `api/main.py` now builds the app with `create_app(settings)` (`api.main:app` still exists, so `uvicorn api.main:app` is unchanged). `api/settings.py` holds every switch. `api/middleware.py` holds the security headers, body size limit and rate limit. `/meta`, `/insights` and `/template.csv` are serialized once at startup.

Where the result differs from the plan:

| Item | Difference |
|---|---|
| #41 | Measured first: a 10,000-row batch (the maximum) takes about 0.2 s, so the old event loop blocking was brief. The change is kept because it is cheap, and a test fails if the work moves back onto the event loop. Do not expect a large speed-up. |
| #42 | A small custom limiter (`RateLimitMiddleware`) instead of `slowapi`, so there is no new dependency. `/what-if` allows 120 a minute instead of 60 because slider use can trigger many requests. `/health` is exempt. Counts are in memory, per process and per client address. |
| #43 | `STRICT_INPUT=false` turns off the unknown-field check. It is read once at import time. |
| #40 | JSON endpoints also get a 64 KB body limit, not only the upload. |
| #39 | The Docker image sets `API_ENV=production`, so `/docs` is off in Docker. `API_ENV=development docker compose up` shows it. |
| #36 | `--no-server-header` is set in the Docker command only. A local `uvicorn` run still shows the header unless the flag is added. |

Undo: revert the Step 1 commit. Or, without any code change, switch a single protection off with its setting (see the table in the README and `api/settings.py`).

### Step 2: Web hardening (`web/`) - DONE

| # | Item | Plan |
|---|---|---|
| 44 | Headers | `poweredByHeader: false` and `headers()` in `next.config.ts`: CSP, HSTS, `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`. |
| 45 | CSP choice | Header-based CSP with `'unsafe-inline'` for scripts and styles, plus `connect-src 'self'` and the API origin, `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`. Reason: a nonce-based CSP forces dynamic rendering and is incompatible with Partial Prerendering (Next.js docs), and SRI does not cover the inline theme script from `next-themes`. Limit: it does not stop injected inline scripts, but the app renders no user-supplied HTML and React escapes output. |
| 46 | CSV injection guard | In the results download, text cells starting with `=`, `+`, `-`, `@`, tab or CR get a leading `'`. Numbers are untouched. |
| 47 | Typed API contract | Export the OpenAPI schema offline (`python -m api.export_openapi` writes `api/openapi.json`), generate `web/src/lib/api-types.ts` with `openapi-typescript`, replace hand-written types where possible, and let CI fail if the generated files are stale. |

Step 2 result (2026-10-28):

- Checked: 97 Python tests (5 new in `tests/test_openapi_contract.py`), 7 web tests (`npm test`), lint, type check, production build, the Docker stack, and three browser runs (functional, CSP, extra checks).
- CSP was tried in `report-only` mode first in a real browser: 0 violations while using every page (predict, tips, what-if, dark mode, batch upload and download, insights). It was then enforced with the same result. The policy blocks a request to another site and an iframe of another site (checked in the browser). Another page cannot frame the app (the frame fails to load).
- CSV guard: in a real download, `=1+1` and `@SUM(A1)` in a text column became `'=1+1` and `'@SUM(A1)`, and the text `-5` stayed `-5`.
- All five kill switches checked on the headers each build produces: `CSP_MODE` (`enforce`, `report-only`, `off`), `HSTS_MAX_AGE=0`, `WEB_SECURITY_HEADERS=false`. A bad value fails the build with a clear message.
- npm audit is unchanged: the same 3 low findings in the build-time `shadcn` CLI. The new dev tool `openapi-typescript` added none.

Where the result differs from the plan:

| Item | Difference |
|---|---|
| #44 | HSTS defaults to one day (`max-age=86400`), not a long period, because browsers remember it and it is hard to undo. Raise it with `HSTS_MAX_AGE` once HTTPS works everywhere. No `includeSubDomains` or `preload`. |
| #45 | `CSP_MODE` and the other settings are build settings (Next.js computes headers at build time). `next dev` defaults to `report-only`, so a development quirk never blocks the page. No `upgrade-insecure-requests`, because it would break calls to `http://localhost:8000`. |
| #46 | Numbers written as text (`-5`, `+3.2`) are left alone. The header row is neutralized too. The tests use Node's built-in runner, so no test library was added. `tsconfig.json` got `allowImportingTsExtensions` so the test can import `./csv.ts`. |
| #47 | `/meta`, `/insights` and the feature names now have documented shapes (`MetaResponse`, `InsightsResponse`, `FeatureName`), so the web types for them are generated too. These models only document: the answers are still the same prebuilt JSON, and a test checks that the real answers match them (extra fields are rejected). Batch row values stay hand-typed, because the API cannot say more than "unknown". |

Undo: revert the Step 2 commit. Without a code change: build with `CSP_MODE=off` or `WEB_SECURITY_HEADERS=false`.

### Step 3: Image slimming - DONE

| # | Item | Plan |
|---|---|---|
| 48 | Contributions without SHAP | For linear models use `coef * (x - mean)` with the mean of all 1,000 rows. This equals SHAP over all 1,000 rows exactly (max difference 0.0). SHAP stays as a lazily imported fallback for tree models. |
| 49 | Smaller API image | Remove `shap` from `requirements-api.txt`, use `pip install --no-compile`, delete test folders and `.pyc` after install, drop `NUMBA_CACHE_DIR`, and remove `pip` from the final image (`pip uninstall -y pip`, clears the 3 fixable Trivy findings). Expected: 919 MB to about 450 MB. |
| 50 | Tests | Formula equals SHAP on the full background (`requirements.txt` keeps `shap` for dev and CI). `test_requirements` still guards tree models. |
| 61 | Dev dependency fixes | Pin `pillow` 13.0.0, `urllib3` 2.8.0 and `pip` 26.2 in `requirements.txt` after checking that matplotlib and mlflow still work, so `pip-audit` is clean in CI. |

Behaviour change to accept: today the tips use SHAP with a 100-row background. With the full 1,000-row mean the tip list differs for about 50 of 300 sampled students (17%). The new values are the more accurate ones.

Step 3 result (2026-10-28):

| Measure | Before | After |
|---|---|---|
| API image size | 919 MB | **447 MB** |
| API container memory | about 170 MiB | about 147 MiB |
| Time until `/health` answers | about 2.0 s | about 4.0 s |
| Trivy HIGH/CRITICAL, Python packages in the API image | 5 (from the `pip` copies) | **0** |
| Trivy HIGH/CRITICAL, Debian OS packages | 44, no fix released yet | 44, unchanged |
| `pip-audit` on the dev venv (with dependencies) | `pillow`, `urllib3`, `pip`, `gitpython`, `filelock` | **none** |

- Checked: 107 Python tests (10 new in `tests/test_explainer.py` plus extended settings and requirements tests), the Docker stack, the browser tests (functional and CSP), a training run with MLflow in a scratch copy (the real model stayed untouched), and the notebook cells with the new `pillow`.
- Exactness: the formula equals SHAP over all 1,000 training rows (largest difference 0.0), and the contributions add up to `prediction - average prediction` (difference about 1e-14). The old numbers came from SHAP's 100-row sample of the data, which is why they differed (largest difference 0.37).
- Response comparison against the original baseline: 8 of 10 responses are byte-identical. The two `/predict` answers differ **only in `tips`**. Score, range and edge warnings are the same, and tips that appear in both versions have identical gains.
- Behaviour change accepted in D5: the tip list differs for 50 of 300 sampled students (17%).

Where the result differs from the plan:

| Item | Difference |
|---|---|
| #48 | `EXPLAINER=shap` (kill switch) brings back the old SHAP path. `shap` stays in `requirements.txt` for development and the tests. The tips code and its output field were renamed from "shap" to "contribution" (internal, not in the API answer). |
| #49 | `--no-compile` makes the image 66 MB smaller but doubles the start-up time (the first import compiles each library). Measured the other way: keeping the `.pyc` files gives **511 MB and about 2.1 s**. The small image is the default. To trade size for start-up, remove `--no-compile` and the `__pycache__` removal line in `api/Dockerfile`. |
| #61 | `pip` is not pinned in `requirements.txt` (pinning pip inside the file that pip installs is awkward). The dev venv pip was upgraded to 26.2.2 by hand. Two more vulnerable packages were found and pinned: `gitpython` 3.2.1 (35 advisories) and `filelock` 4.2.1. The unused `streamlit` package (left over from the removed app, and the only thing that needed `pillow<13`) was uninstalled from the dev venv. |

Undo the dev venv changes: `pip install pillow==12.3.0 urllib3==2.7.0 gitpython==3.1.52 filelock==4.0.7 streamlit==1.59.2`. Undo the code: revert the commit. Without a code change: `EXPLAINER=shap` (needs `shap` installed).

Note on tips: with the correct average, a student close to average on a habit can get a small tip (for example +0.7 points for attendance). Adding a minimum gain would hide those. That is a product choice and was not changed.

### Step 4: Reverse proxy and containers - DONE

| # | Item | Plan |
|---|---|---|
| 51 | nginx service | Added as an override file `docker-compose.proxy.yml`, so the current direct stack (`docker compose up`, ports 3000 and 8000) keeps working unchanged. In proxy mode: a pinned, unprivileged nginx image is the only published port (8080 locally). `/api/` goes to the API (prefix stripped), `/` goes to the web app. API and web are not published. The web app is built with `NEXT_PUBLIC_API_URL=/api`, so there is one origin: no CORS and CSP `connect-src 'self'`. |
| 52 | nginx settings | `server_tokens off`, hide `X-Powered-By`, HSTS (HTTPS only), gzip for json, js, css, csv, svg, `client_max_body_size` 6m on batch and 1m elsewhere, short client timeouts, `limit_req` with burst and `limit_conn`, 5-minute proxy cache for `/api/meta`, `/api/insights`, `/api/template.csv`, forwarded headers. The apps keep setting the other security headers (one source of truth). |
| 53 | TLS | Documented template for a VPS: Let's Encrypt with certbot, or Caddy as a simpler alternative. Needs a real domain, so it is documented but not verified locally. |
| 54 | Container hardening | In `docker-compose.yml`: `read_only: true` with tmpfs for `/tmp` and `.next/cache`, `cap_drop: [ALL]`, `no-new-privileges`, `mem_limit`, `pids_limit`, health checks. In `web/Dockerfile`, remove npm and npx from the final stage (clears all 11 Trivy findings in the web image). |

Step 4 result (2026-10-28):

- Checked in a real browser in both setups (direct on 3000 and 8000, and behind nginx on 8080): the functional test, the CSP test (0 violations) and the extra checks (CSV guard, framing). Behind nginx the CSP is down to `connect-src 'self'`.
- Container hardening, checked with `docker inspect` and inside the containers: read-only root file system (writing to `/` fails), `CapEff` all zero, `no-new-privileges`, memory 512 MB and 200 processes, running as uid 1000 (nginx: uid 101). No errors in the logs. A 3 MB upload with 10,000 rows, which is spooled to the in-memory `/tmp`, worked. The API answers in the hardened direct setup are byte-identical to the Step 3 answers (10 of 10).
- nginx behind the proxy: only port 8080 answers (3000 and 8000 are refused); headers appear once and `Server: nginx` has no version; `/api/meta` goes `MISS`, `HIT`, then `304`; `/api/insights` 191 KB down to 36 KB with gzip; API answers through nginx are byte-identical; a 7 MB upload and a 2 MB JSON body get `413` from nginx in the API's JSON shape; a 5.5 MB upload passes nginx and gets the API's own `413`; a flood of 150 requests gives 46 `200` and 104 `429` with `Retry-After`, and normal use works again afterwards; the API sees the real client address (not nginx's, and not a faked `X-Forwarded-For`); after `docker restart` of the API, nginx answers a clear JSON `502` for about 4 seconds and then recovers by itself.
- Trivy HIGH/CRITICAL: web image 11 down to **0** (npm removed); nginx image 3 (Alpine `curl`, `libcurl`, `brotli-libs`) down to **0** with a patched image; API image unchanged (44 Debian packages with no fix released yet).

Where the result differs from the plan:

| Item | Difference |
|---|---|
| #51 | Safety rule applied: the proxy is the override file `docker-compose.proxy.yml`, the direct setup stays the default and was not changed in how it is used. The proxy builds its own web image (`mlproject-web-proxy`) with `NEXT_PUBLIC_API_URL=/api`, so the two setups do not overwrite each other. |
| #52 | HSTS is not set in nginx. The web app already sends it (and it only matters over HTTPS), and two copies of a header would conflict. nginx adds no security headers at all, to keep one source. `FORWARDED_ALLOW_IPS=*` is set for the API in the proxy setup only, because nothing else can reach it. |
| #53 | `nginx/tls.example.conf` and `nginx/README.md` give a template and a Caddy alternative. They could not be tested here (they need a domain and certificates). |
| #54 | Hardening is in the base `docker-compose.yml`, so it applies to the direct setup too (tested: nothing broke). `corepack` is still in the web image (it is not flagged and is part of Node). The nginx image is built from `nginx/Dockerfile`, which only upgrades 3 packages, instead of using the official image directly. |
| CI | The docker job also starts the stack behind nginx and checks `/api/health`, the page and the cache header. |

Undo: revert the Step 4 commit. Without a code change: use `docker compose up --build` (direct setup) instead of the proxy file; to loosen the hardening, delete the `read_only`, `cap_drop`, `security_opt`, `mem_limit` and `pids_limit` lines of a service in `docker-compose.yml`.

### Step 5: CI security - DONE (files written and checked locally, no GitHub run yet)

| # | Item | Plan |
|---|---|---|
| 55 | Scans in CI | `pip-audit`, `npm audit --omit=dev`, Trivy image scan (fail on fixable HIGH and CRITICAL), `bandit`, `gitleaks`, `ruff`. |
| 56 | API fuzzing | `schemathesis` against the running API, driven by the OpenAPI schema. |
| 57 | Dependabot | `.github/dependabot.yml` for pip, npm, docker and github-actions. |

Step 5 result (2026-10-28). Every tool was run on this machine with the same command CI uses, before it went into a workflow:

| Tool | Result | What came of it |
|---|---|---|
| `ruff` | 10 findings | Real fixes: `zip()` now fails loudly on unequal lengths (3), `raise ... from` keeps the original error (2), the Optuna `objective` binds its loop variables (2 findings), an unused import. `File(...)` in a FastAPI argument is an accepted idiom and is configured in `ruff.toml`. |
| `bandit` | 1 finding | A false alarm: a variable called `token` compared with `"*"` in the ETag code looked like a password. The variable was renamed, no `# nosec`. |
| `pip-audit` on `requirements.txt` with all dependencies resolved | none | |
| `npm audit --omit=dev --audit-level=high` | exit 0 | The 3 low findings in the build-time `shadcn` CLI do not fail it. |
| `gitleaks` on the 109 project files | no leaks | A planted fake key in a scratch folder was found (exit 1), so the scanner works. |
| `trivy` on all 4 images (direct and proxy setups) | exit 0 | The same command fails on the unpatched official nginx image (3 findings), and the loop in the workflow scans every image before it fails. |
| `schemathesis` against the API | 8 failures at first, then 0 on 5 seeds (717 cases each) | See below. |
| `actionlint` on both workflows | clean | |
| Dependabot file against the official schema | 0 errors | A deliberately invalid file was rejected by the same check. |

What the fuzzing found, and what was done:

| Finding | Fix |
|---|---|
| The API accepted `true`, `false` and text such as `"3.5"` or `"20"` in number fields and turned them into numbers (`study_hours_per_day: false` gave a score). | Number fields reject booleans and text (`api/schemas.py`), also for what-if changes. Numbers like `21.0` for a whole-number field still work. Kill switch: `STRICT_INPUT=false`. A blanket `strict=True` was not used, because it would have broken the web what-if (a whole number arrives as `4.0` inside the changes). |
| The error answers were documented as one shape, but the API really answers with a list of messages, a list of field details, or a single text. | `ErrorResponse` documents all three, and every route lists its `400`, `413`, `422` and `429` answers. Only the documentation changed: no answer changed. |
| `400` for a body that is not valid text was not documented. | Added. |
| Category values (for example `gender`) are checked against the dataset when the API starts. An OpenAPI file cannot say that, so "valid data was rejected" was reported. | The `positive_data_acceptance` check is skipped on purpose, with the reason written in the workflow. `GET /meta` lists the allowed values. |

Where the result differs from the plan:

| Item | Difference |
|---|---|
| #55, #56 | A new workflow `security.yml` instead of more steps in `ci.yml`, so a new advisory does not stop the build and test jobs. It also runs every Monday. Tools run as pinned pip packages or pinned Docker images (`aquasec/trivy:0.76.1`, `zricethezav/gitleaks:v8.30.1`) instead of Marketplace actions, because those exact versions could be run and checked here. |
| #55 | `gitleaks` scans the files (`dir` mode), not the git history. A history scan needs git commands, which need your approval. Add it later if you want it. Trivy only fails on findings that already have a fix (`--ignore-unfixed`); the 44 Debian findings without a fix are left out. |
| #56 | A fixed seed on pushes and pull requests so a run can be repeated, and a new seed every Monday. |
| #57 | `scikit-learn`, `numpy`, `pandas` and `joblib` are ignored, because the saved model is tied to them. |
| Not checked | A real run on GitHub. The workflows pass `actionlint` and every command was run here, but they first run when pushed. The first run may need small fixes (for example action versions or runner differences). |

Undo: revert the Step 5 commit (the two code changes in `api/schemas.py` are covered by `STRICT_INPUT`). Without a code change: add `if: false` under a job in `security.yml`, or delete the file.

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
