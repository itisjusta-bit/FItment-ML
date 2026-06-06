"""
Generate synthetic_profiles.csv — 5000 user profiles for training
the Fitness Persona Classifier.
Run: python data/generate_profiles.py
"""
import numpy as np
import pandas as pd
import os

np.random.seed(42)
N = 5000

GOALS      = ['lose_weight','build_muscle','stay_active','improve_stamina']
GENDERS    = ['Male','Female','Other']
DIETS      = ['standard','vegetarian','vegan','jain','eggetarian']
ACTIVITIES = ['sedentary','light','moderate','active','very_active']
EQUIPMENT  = ['no_equipment','dumbbells','full_gym']
REGIONS    = ['indian','western','global']

# ── Persona mapping rules ──────────────────────────────────────────────────────
# 0: Lean Beginner        1: Home Warrior        2: Gym Newbie
# 3: Intermediate Gym     4: Advanced Athlete    5: Busy Professional
# 6: Weight Loss Focus    7: Senior Fit          8: Female Toner

def assign_persona(row):
    g  = row['goal']
    eq = row['equipment']
    ac = row['activity_level']
    ag = row['age']
    bmi= row['bmi']
    ge = row['gender']
    fr = row['frequency']

    # Senior (40+, any) → Persona 7
    if ag >= 40 and g in ['stay_active','improve_stamina']:
        return 7
    # Female toner
    if ge == 'Female' and g in ['stay_active','lose_weight'] and eq in ['no_equipment','dumbbells'] and bmi < 30:
        return 8
    # Weight loss focus (high BMI)
    if g == 'lose_weight' and bmi >= 27:
        return 6
    # Advanced athlete
    if g in ['build_muscle','improve_stamina'] and ac == 'very_active' and eq == 'full_gym' and fr >= 5:
        return 4
    # Intermediate gym
    if g == 'build_muscle' and eq == 'full_gym' and ac in ['active','very_active'] and ag < 40:
        return 3
    # Gym newbie
    if g == 'build_muscle' and eq == 'full_gym' and ac in ['sedentary','light','moderate']:
        return 2
    # Home warrior
    if g in ['build_muscle','lose_weight'] and eq == 'dumbbells':
        return 1
    # Busy professional
    if ac in ['sedentary','light'] and g == 'stay_active':
        return 5
    # Lean beginner (default)
    return 0

rows = []
for _ in range(N):
    gender   = np.random.choice(GENDERS, p=[0.50, 0.45, 0.05])
    age      = int(np.random.choice(range(16, 65), p=np.array([
        0.5 if 16<=x<25 else (0.8 if 25<=x<35 else (0.5 if 35<=x<45 else 0.3))
        for x in range(16, 65)], dtype=float) / sum([
        0.5 if 16<=x<25 else (0.8 if 25<=x<35 else (0.5 if 35<=x<45 else 0.3))
        for x in range(16, 65)])))

    if gender == 'Male':
        height = float(np.random.normal(174, 8))
        weight = float(np.random.normal(72, 14))
    elif gender == 'Female':
        height = float(np.random.normal(161, 7))
        weight = float(np.random.normal(58, 11))
    else:
        height = float(np.random.normal(168, 9))
        weight = float(np.random.normal(65, 12))

    height = max(145, min(210, round(height, 1)))
    weight = max(40,  min(150, round(weight, 1)))
    bmi    = round(weight / ((height/100)**2), 1)

    goal     = np.random.choice(GOALS, p=[0.35, 0.35, 0.15, 0.15])
    diet     = np.random.choice(DIETS, p=[0.40, 0.30, 0.08, 0.05, 0.17])
    activity = np.random.choice(ACTIVITIES, p=[0.15, 0.25, 0.30, 0.20, 0.10])
    equipment= np.random.choice(EQUIPMENT, p=[0.30, 0.35, 0.35])
    frequency= int(np.random.choice([3,4,5,6], p=[0.30, 0.35, 0.25, 0.10]))
    region   = np.random.choice(REGIONS, p=[0.65, 0.20, 0.15])

    row = {
        'goal': goal, 'gender': gender, 'age': age,
        'height_cm': height, 'weight_kg': weight, 'bmi': bmi,
        'diet_type': diet, 'activity_level': activity,
        'equipment': equipment, 'frequency': frequency, 'region': region,
    }
    row['persona'] = assign_persona(row)
    rows.append(row)

df = pd.DataFrame(rows)
out = os.path.join(os.path.dirname(__file__), 'synthetic_profiles.csv')
df.to_csv(out, index=False)
print(f"Generated {len(df)} profiles → {out}")
print("Persona distribution:")
print(df['persona'].value_counts().sort_index().to_string())
