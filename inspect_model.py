from pathlib import Path
import sys
import joblib

BASE_DIR = Path(__file__).resolve().parent

sys.path.append(str(BASE_DIR / "ML"))
sys.path.append(str(BASE_DIR / "ML" / "Model"))

model_path = BASE_DIR / "ML" / "Model" / "artifacts" / "command_model.joblib"

print("Loading:", model_path)

model = joblib.load(model_path)

print(type(model))
print(model.keys())

print(type(model["model"]))
print(type(model["scaler"]))
print(type(model["label_encoder"]))