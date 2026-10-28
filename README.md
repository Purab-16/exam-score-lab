# 🎓 Student Exam Score Predictor

Predict a student's final exam score (0 to 100) from their demographics, study habits, lifestyle and environment, and get concrete tips on which habits to change.

The project has four parts:

- **`ml/`**: the model code. `python train.py` compares 6 models with cross-validation, tunes the best ones, and saves the winner.
- **`api/`**: FastAPI service that serves predictions, tips, what-if, batch CSV and chart data.
- **`web/`**: Next.js web app (Tailwind CSS, shadcn/ui, Recharts) on top of the API.
- **`notebooks/eda.ipynb`**: exploratory data analysis only.

---

## 📊 Dataset

`data/student_habits_performance.csv`: **1,000 students**, 14 input features and 1 target.

| Group | Features |
|---|---|
| Demographics | `age` (17 to 24), `gender` (Female, Male, Other) |
| Academic | `study_hours_per_day` (0 to 8.3), `attendance_percentage` (56 to 100), `parental_education_level` (High School, Bachelor, Master) |
| Lifestyle | `sleep_hours` (3.2 to 10), `social_media_hours` (0 to 7.2), `netflix_hours` (0 to 5.4), `exercise_frequency` (0 to 6 days/week), `diet_quality` (Poor, Fair, Good) |
| Environment | `internet_quality` (Poor, Average, Good), `extracurricular_participation` (Yes, No), `part_time_job` (Yes, No), `mental_health_rating` (1 to 10) |
| **Target** | `exam_score` (0 to 100) |

`parental_education_level` is missing for 91 students. These rows are kept, and the missing value becomes its own `"Unknown"` category.

---

## 🤖 Model

### Pipeline

Defined in `ml/pipeline.py` and shared by training and the app:

- **Numeric features**: median imputation, then `StandardScaler`.
- **Categorical features**: missing values become `"Unknown"`, then `OneHotEncoder(handle_unknown="ignore")`.
- **Optional engineered features**: `total_screen_time`, `study_to_sleep_ratio`, `study_x_attendance`. They are kept only if they improve CV RMSE by at least 0.01.
- **Output** is clipped to 0 to 100.

### How the model is chosen

1. Split 80/20 into train (800) and a held-out test set (200). The test set is used once, at the end.
2. 5-fold CV on the train set for 6 models, each with and without engineered features.
3. Tune the 2 best tunable models with Optuna (30 trials each, CV on the train set only).
4. Pick the lowest CV RMSE.
5. Build a 90% prediction interval from out-of-fold residuals.
6. Refit on all 1,000 rows and save `models/best_model.pkl` and `models/model_meta.json`.

### Results (5-fold CV on the train set)

| Model | Features | CV RMSE | CV R² |
|---|---|---|---|
| 🏆 **Ridge (tuned, alpha 12.4)** | base | **5.508 ± 0.487** | **0.895** |
| Ridge | base | 5.518 | 0.894 |
| Linear Regression | base | 5.520 | 0.894 |
| Gradient Boosting (tuned) | engineered | 5.665 | 0.889 |
| XGBoost | base | 6.118 | 0.870 |
| LightGBM | engineered | 6.166 | 0.868 |
| Random Forest | engineered | 6.491 | 0.854 |

The relationship between habits and score is mostly linear, so a regularised linear model wins.

### Held-out test set (200 students, never seen during training or tuning)

| Metric | Value |
|---|---|
| RMSE | **5.14** |
| R² | **0.897** |
| 90% interval | ± 8.6 points |
| Interval coverage on test | 91.5% |

Exact numbers for the current model are always in `models/model_meta.json`.

---

## 🖥️ The Web App

Three pages, with light and dark mode and a mobile layout:

| Page | What it does |
|---|---|
| 🧑‍🎓 **Predict** (`/`) | Four-step profile form. Shows the score on a gauge with a 90% likely range, warns if an input is at the edge of the training data, lists up to 3 **personal tips** (habits pulling the score down, with the predicted gain of one change), and a **what-if simulator** that updates as you move the sliders. |
| 📂 **Batch** (`/batch`) | Drag and drop a CSV of students, see row-level errors or validated predictions with ranges, download the results. A template CSV is provided. |
| 📊 **Insights** (`/insights`) | Interactive charts: score distribution, correlation of each habit with the score, habit vs score scatter, average score by group, and predicted vs actual. |

Tips use SHAP values to find which habits pull a student's score below average, then use the model to estimate the effect of one realistic change. They show association, not guaranteed cause and effect.

### Batch CSV format

One row per student with these columns (extra columns such as `student_id` are kept in the output):

```
age, gender, study_hours_per_day, social_media_hours, netflix_hours, part_time_job,
attendance_percentage, sleep_hours, diet_quality, exercise_frequency,
parental_education_level, internet_quality, mental_health_rating, extracurricular_participation
```

Empty cells are allowed and filled the same way as in training. Unknown categories or non-numeric values are reported with their spreadsheet row number. Values outside the training range give a warning. Limit: 10,000 rows.

---

## 🚀 Running Locally

Tested with **Python 3.14.3** on Windows. Library versions are pinned in `requirements.txt`.

### 1. Install

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### 2. Train

```bash
python train.py                 # about 35 seconds
python train.py --trials 10     # faster, less tuning
python train.py --no-mlflow     # skip experiment tracking
```

`models/best_model.pkl` must be loaded with the same scikit-learn version it was trained with. If you change library versions, re-run `python train.py`. `GET /meta` reports `sklearn_version_matches`, and a test fails on a mismatch.

### 3. Run the API and the web app

Needs Node.js 20 or newer for the web app. Use two terminals, both started from the project folder.

```bash
# Terminal 1: API on http://127.0.0.1:8000 (docs at /docs)
uvicorn api.main:app --reload
```

```bash
# Terminal 2: web app on http://localhost:3000
cd web
npm install
npm run dev
```

The web app calls the API at `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`, see `web/.env.example`). The API accepts browser requests from the origins in `API_CORS_ORIGINS` (default `http://localhost:3000,http://127.0.0.1:3000`).

#### API endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | Status and model name |
| GET | `/meta` | Model info, input ranges, category options, what-if habits |
| POST | `/predict` | Score, 90% range, inputs at the training edge, personal tips |
| POST | `/what-if` | Score before and after a set of habit changes |
| POST | `/predict/batch` | Predictions for an uploaded CSV, or 422 with row-level errors |
| GET | `/template.csv` | Example CSV for batch upload |
| GET | `/insights` | Data for the dataset charts |

### Or run everything with Docker

Needs Docker Desktop (or Docker Engine) running.

```bash
docker compose up --build
```

Web: http://localhost:3000 · API: http://localhost:8000/docs

- `api/Dockerfile` installs only `requirements-api.txt` (no training tools), runs as a non-root user and reads `PORT` if the host sets it.
- `web/Dockerfile` builds a Next.js standalone server. `NEXT_PUBLIC_API_URL` is a build argument because it is baked into the browser bundle.

### 4. Run the tests

```bash
python -m pytest            # 50 Python tests: pipeline, saved model, insights, API, requirement pins
cd web && npm run lint && npm run build
```

GitHub Actions (`.github/workflows/ci.yml`) runs the Python tests, the web lint, type check and build, and then builds both Docker images and smoke-tests the stack, on every push to `main` and every pull request.

### 5. View experiments (optional)

Every training run is logged to MLflow.

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Then open http://127.0.0.1:5000.

---

## 📁 Project Structure

```
.
├── README.md
├── ml/                          # the model code (no web or API code)
│   ├── pipeline.py              #   features, preprocessing, clipping
│   ├── train.py                 #   CV, tuning, interval, MLflow, saves the model
│   ├── insights.py              #   ranges, what-if, tips, SHAP, CSV validation
│   └── paths.py                 #   where data and model files live
├── data/
│   └── student_habits_performance.csv
├── models/                      # output of training, read by the API
│   ├── best_model.pkl           #   trained pipeline
│   └── model_meta.json          #   versions, CV leaderboard, test metrics, interval
├── notebooks/
│   └── eda.ipynb                # exploratory analysis only
├── api/                         # FastAPI service (main.py, schemas.py, Dockerfile)
├── web/                         # Next.js app (src/app pages, src/components, src/lib/api.ts)
├── tests/                       # pytest suite
├── docs/
│   └── PLAN.md                  # fix and improvement roadmap
├── train.py                     # shortcut so `python train.py` works (runs ml/train.py)
├── docker-compose.yml           # API + web together
├── requirements.txt             # everything: training, API, tests
├── requirements-api.txt         # API runtime only (used by the Docker image)
├── pytest.ini
└── .github/workflows/ci.yml     # CI
```

Where to look when you want to:

| I want to | Go to |
|---|---|
| Change the model or how it trains | `ml/pipeline.py`, `ml/train.py` |
| Change tips, what-if or CSV checks | `ml/insights.py` |
| Add or change an API endpoint | `api/main.py`, `api/schemas.py` |
| Change a page or a chart | `web/src/app/`, `web/src/components/` |
| Replace the dataset | `data/` (then run `python train.py`) |
| See the plan and history | `docs/PLAN.md` |

---

## ⚠️ Limitations

- The dataset is small (1,000 students) and appears synthetic, so results may not transfer to real students.
- Predictions are less reliable for inputs near or outside the training range.
- Tips and what-if results describe what the model learned from correlations, not proven causes.
