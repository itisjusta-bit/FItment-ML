"""
Train the Fitness Persona Classifier.
Run: python models/train_persona.py

Saves:
  models/persona_model.pkl
  models/scaler.pkl
  models/label_encoders.pkl
  models/metrics.pkl
"""
import os, sys, pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, 'data')
MODEL_DIR= os.path.dirname(os.path.abspath(__file__))

PERSONA_NAMES = {
    0: 'Lean Beginner',
    1: 'Home Warrior',
    2: 'Gym Newbie',
    3: 'Intermediate Gym',
    4: 'Advanced Athlete',
    5: 'Busy Professional',
    6: 'Weight Loss Focus',
    7: 'Senior Fit',
    8: 'Female Toner',
}

CAT_FEATURES = ['goal', 'gender', 'diet_type', 'activity_level', 'equipment', 'region']
NUM_FEATURES = ['age', 'height_cm', 'weight_kg', 'bmi', 'frequency']

def train():
    print("=" * 60)
    print("  Fitment — Persona Classifier Training")
    print("=" * 60)

    # ── Step 1: Generate data if missing ──────────────────────────
    csv_path = os.path.join(DATA_DIR, 'synthetic_profiles.csv')
    if not os.path.exists(csv_path):
        print("\nGenerating synthetic profiles...")
        sys.path.insert(0, DATA_DIR)
        import generate_profiles  # noqa
        print("Done.\n")

    df = pd.read_csv(csv_path)
    print(f"Loaded: {len(df)} profiles, {df['persona'].nunique()} personas")

    # ── Step 2: Encode categoricals ───────────────────────────────
    encoders = {}
    df_enc   = df.copy()
    for col in CAT_FEATURES:
        le = LabelEncoder()
        df_enc[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    # ── Step 3: Feature matrix ────────────────────────────────────
    feature_cols = CAT_FEATURES + NUM_FEATURES
    X = df_enc[feature_cols].values
    y = df['persona'].values

    scaler  = StandardScaler()
    X_scaled= scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y)
    print(f"Train: {len(X_train)} | Test: {len(X_test)}\n")

    # ── Step 4: Train models ──────────────────────────────────────
    print("Training Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=12,
        min_samples_split=4, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)

    print("Training Gradient Boosting...")
    gb = GradientBoostingClassifier(
        n_estimators=150, max_depth=5,
        learning_rate=0.1, random_state=42)
    gb.fit(X_train, y_train)

    # ── Step 5: Evaluate ──────────────────────────────────────────
    for name, mdl in [("Random Forest", rf), ("Gradient Boosting", gb)]:
        preds = mdl.predict(X_test)
        acc   = accuracy_score(y_test, preds)
        cv    = cross_val_score(mdl, X_scaled, y, cv=5, scoring='accuracy')
        print(f"\n{name}:")
        print(f"  Test Accuracy  : {acc*100:.2f}%")
        print(f"  CV Accuracy    : {cv.mean()*100:.2f}% ± {cv.std()*100:.2f}%")

    # Use RF as best model
    best_preds = rf.predict(X_test)
    acc = accuracy_score(y_test, best_preds)
    print(f"\nSelected: Random Forest  (Acc: {acc*100:.2f}%)")
    print("\nPer-persona accuracy:")
    for pid, pname in PERSONA_NAMES.items():
        mask  = y_test == pid
        if mask.sum() == 0:
            continue
        p_acc = accuracy_score(y_test[mask], best_preds[mask])
        print(f"  [{pid}] {pname:<22} → {p_acc*100:.1f}%  (n={mask.sum()})")

    # Feature importance
    fi = pd.Series(rf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\nTop Feature Importances:")
    for feat, imp in fi.head(8).items():
        print(f"  {feat:<20} {imp:.4f}")

    # ── Step 6: Save artifacts ────────────────────────────────────
    with open(os.path.join(MODEL_DIR, 'persona_model.pkl'), 'wb') as f:
        pickle.dump(rf, f)
    with open(os.path.join(MODEL_DIR, 'scaler.pkl'), 'wb') as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODEL_DIR, 'label_encoders.pkl'), 'wb') as f:
        pickle.dump(encoders, f)
    with open(os.path.join(MODEL_DIR, 'metrics.pkl'), 'wb') as f:
        pickle.dump({
            'accuracy': round(acc * 100, 2),
            'feature_cols': feature_cols,
            'persona_names': PERSONA_NAMES,
        }, f)

    print("\n✅ Saved: persona_model.pkl, scaler.pkl, label_encoders.pkl, metrics.pkl")
    print("✅ Training complete!\n")
    return acc

if __name__ == '__main__':
    train()
