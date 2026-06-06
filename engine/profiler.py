"""
engine/profiler.py
──────────────────
Calculates BMR, TDEE, macro targets and classifies user into a
Fitness Persona using the trained ML model.
"""
import os, sys, pickle
import numpy as np

BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE, 'models')

# ── Constants ─────────────────────────────────────────────────────────────────
ACTIVITY_MULTIPLIERS = {
    'sedentary':   1.2,
    'light':       1.375,
    'moderate':    1.55,
    'active':      1.725,
    'very_active': 1.9,
}

GOAL_CALORIE_DELTA = {
    'lose_weight':     -450,
    'build_muscle':    +300,
    'stay_active':       0,
    'improve_stamina': -100,
}

GOAL_MACRO_SPLIT = {
    'lose_weight':     {'protein': 0.35, 'carbs': 0.40, 'fat': 0.25},
    'build_muscle':    {'protein': 0.30, 'carbs': 0.50, 'fat': 0.20},
    'stay_active':     {'protein': 0.25, 'carbs': 0.50, 'fat': 0.25},
    'improve_stamina': {'protein': 0.20, 'carbs': 0.60, 'fat': 0.20},
}

MEAL_DISTRIBUTION = {
    'breakfast':    0.25,
    'mid_morning':  0.10,
    'lunch':        0.35,
    'evening_snack':0.10,
    'dinner':       0.20,
}

PERSONA_NAMES = {
    0: 'Lean Beginner',      1: 'Home Warrior',
    2: 'Gym Newbie',         3: 'Intermediate Gym',
    4: 'Advanced Athlete',   5: 'Busy Professional',
    6: 'Weight Loss Focus',  7: 'Senior Fit',
    8: 'Female Toner',
}

PERSONA_DESCRIPTIONS = {
    0: 'Starting your fitness journey with bodyweight training and basic nutrition.',
    1: 'Consistent home training with dumbbells, building strength and endurance.',
    2: 'Learning gym fundamentals — compound movements and balanced nutrition.',
    3: 'Intermediate lifter focused on progressive overload and optimal macros.',
    4: 'High-performance training with advanced programming and precise nutrition.',
    5: 'Efficient workouts for a busy schedule — maximum results in minimum time.',
    6: 'Cardio-focused training with calorie-deficit nutrition for sustainable fat loss.',
    7: 'Joint-friendly, low-impact training to stay strong, mobile and healthy.',
    8: 'Toning and sculpting with light weights, flexibility and balanced nutrition.',
}

# ── Lazy-load ML artifacts ────────────────────────────────────────────────────
_model    = None
_scaler   = None
_encoders = None
_feature_cols = None

def _load_model():
    global _model, _scaler, _encoders, _feature_cols
    if _model is not None:
        return
    mp = os.path.join(MODEL_DIR, 'persona_model.pkl')
    if not os.path.exists(mp):
        raise FileNotFoundError(
            "persona_model.pkl not found. Run: python models/train_persona.py")
    with open(mp, 'rb') as f:
        _model = pickle.load(f)
    with open(os.path.join(MODEL_DIR, 'scaler.pkl'), 'rb') as f:
        _scaler = pickle.load(f)
    with open(os.path.join(MODEL_DIR, 'label_encoders.pkl'), 'rb') as f:
        _encoders = pickle.load(f)
    with open(os.path.join(MODEL_DIR, 'metrics.pkl'), 'rb') as f:
        m = pickle.load(f)
        _feature_cols = m['feature_cols']

# ── BMR / TDEE ────────────────────────────────────────────────────────────────
def calc_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """Harris-Benedict Revised (Mifflin-St Jeor)."""
    if gender.lower() in ('male', 'm'):
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    elif gender.lower() in ('female', 'f'):
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    else:
        male   = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
        female = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
        return (male + female) / 2

def calc_tdee(bmr: float, activity_level: str) -> float:
    return bmr * ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)

def calc_targets(tdee: float, goal: str) -> dict:
    cal_target = max(1200, tdee + GOAL_CALORIE_DELTA.get(goal, 0))
    split = GOAL_MACRO_SPLIT.get(goal, GOAL_MACRO_SPLIT['stay_active'])
    protein_g = round((cal_target * split['protein']) / 4, 0)
    carbs_g   = round((cal_target * split['carbs'])   / 4, 0)
    fat_g     = round((cal_target * split['fat'])     / 9, 0)
    return {
        'calories':  round(cal_target),
        'protein_g': int(protein_g),
        'carbs_g':   int(carbs_g),
        'fat_g':     int(fat_g),
        'meal_calories': {
            k: round(cal_target * v)
            for k, v in MEAL_DISTRIBUTION.items()
        }
    }

# ── Persona Classifier ────────────────────────────────────────────────────────
def classify_persona(user: dict) -> dict:
    """
    Input: user dict with keys:
      goal, gender, age, height_cm, weight_kg,
      diet_type, activity_level, equipment, frequency, region
    Output: persona dict
    """
    _load_model()

    bmi = round(user['weight_kg'] / ((user['height_cm'] / 100) ** 2), 1)

    cat_cols = ['goal','gender','diet_type','activity_level','equipment','region']
    num_cols = ['age','height_cm','weight_kg','bmi','frequency']

    row = []
    for col in cat_cols:
        le  = _encoders[col]
        val = str(user.get(col, ''))
        if val in le.classes_:
            row.append(le.transform([val])[0])
        else:
            row.append(0)
    for col in num_cols:
        if col == 'bmi':
            row.append(bmi)
        else:
            row.append(float(user.get(col, 0)))

    X      = np.array([row])
    X_sc   = _scaler.transform(X)
    pid    = int(_model.predict(X_sc)[0])
    proba  = _model.predict_proba(X_sc)[0]

    return {
        'persona_id':    pid,
        'persona_name':  PERSONA_NAMES[pid],
        'description':   PERSONA_DESCRIPTIONS[pid],
        'confidence':    round(float(proba[pid]) * 100, 1),
        'bmi':           bmi,
    }

# ── Full user profile ─────────────────────────────────────────────────────────
def build_profile(user: dict) -> dict:
    """
    Returns complete fitness profile:
    persona + BMR + TDEE + calorie target + macro targets
    """
    bmr     = calc_bmr(user['weight_kg'], user['height_cm'],
                        user['age'], user['gender'])
    tdee    = calc_tdee(bmr, user['activity_level'])
    targets = calc_targets(tdee, user['goal'])
    persona = classify_persona(user)

    return {
        'user':     user,
        'bmr':      round(bmr),
        'tdee':     round(tdee),
        'targets':  targets,
        'persona':  persona,
    }


if __name__ == '__main__':
    sample = {
        'goal': 'build_muscle', 'gender': 'Male', 'age': 22,
        'height_cm': 175, 'weight_kg': 68,
        'diet_type': 'standard', 'activity_level': 'moderate',
        'equipment': 'full_gym', 'frequency': 4, 'region': 'indian',
    }
    profile = build_profile(sample)
    print("== Fitness Profile ==")
    print(f"BMR   : {profile['bmr']} kcal")
    print(f"TDEE  : {profile['tdee']} kcal")
    print(f"Target: {profile['targets']['calories']} kcal")
    print(f"Macros: P={profile['targets']['protein_g']}g  "
          f"C={profile['targets']['carbs_g']}g  "
          f"F={profile['targets']['fat_g']}g")
    print(f"Persona: [{profile['persona']['persona_id']}] "
          f"{profile['persona']['persona_name']} "
          f"({profile['persona']['confidence']}% confidence)")
