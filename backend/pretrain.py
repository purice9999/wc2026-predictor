"""
Pre-trains and caches the model during Render's build step.
At runtime, load_or_train() finds .cache/*.pkl and skips training → fast startup.
"""
import sys
import os

# Ensure we run from backend/ so relative cache paths resolve correctly
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.services.model_service import load_or_train, load_or_train_calibrator

print("=== Pre-training: DC + Elo + XGBoost ===")
dc, elo, xgb = load_or_train(settings, force_retrain=False)
print(f"Models ready: DC={dc is not None}, Elo={elo is not None}, XGB={xgb is not None}")

print("=== Pre-training: Isotonic calibrator ===")
calibrator = load_or_train_calibrator(dc, settings, force_retrain=False)
print(f"Calibrator ready: {calibrator is not None}")

print("=== Pre-training complete — cache saved to .cache/ ===")
