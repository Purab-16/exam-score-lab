"""Where the project's files live. Every module imports locations from here."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_PATH = ROOT / "data" / "student_habits_performance.csv"

MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "best_model.pkl"
META_PATH = MODEL_DIR / "model_meta.json"

# MLflow keeps its local tracking data in the project root (ignored by git)
MLFLOW_DB_PATH = ROOT / "mlflow.db"
