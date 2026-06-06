"""
engine/workout_generator.py
────────────────────────────
Generates a fresh daily workout plan based on:
  - Fitness persona
  - Available equipment
  - Training split (by frequency)
  - Session history (for freshness)
  - Injury flags
"""
import os, json, random
from datetime import datetime, date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX_PATH = os.path.join(BASE, 'data', 'exercises.json')

_exercises = None

def _load_exercises():
    global _exercises
    if _exercises is None:
        with open(EX_PATH, 'r') as f:
            _exercises = json.load(f)
    return _exercises

# ── Training splits ───────────────────────────────────────────────────────────
SPLITS = {
    3: [
        {'name': 'Full Body A', 'emoji': '💪', 'muscles': ['chest','back','legs','core']},
        {'name': 'Full Body B', 'emoji': '🏋️', 'muscles': ['shoulders','back','legs','arms']},
        {'name': 'Full Body C', 'emoji': '⚡', 'muscles': ['chest','legs','core','arms']},
    ],
    4: [
        {'name': 'Push Day',  'emoji': '🔥', 'muscles': ['chest','shoulders','triceps']},
        {'name': 'Pull Day',  'emoji': '💪', 'muscles': ['back','biceps']},
        {'name': 'Leg Day',   'emoji': '🦵', 'muscles': ['legs','glutes','calves']},
        {'name': 'Upper Body','emoji': '⚡', 'muscles': ['chest','back','shoulders','arms']},
    ],
    5: [
        {'name': 'Chest Day',    'emoji': '💪', 'muscles': ['chest','triceps']},
        {'name': 'Back Day',     'emoji': '🏋️', 'muscles': ['back','biceps']},
        {'name': 'Leg Day',      'emoji': '🦵', 'muscles': ['legs','glutes','hamstrings','calves']},
        {'name': 'Shoulder Day', 'emoji': '⚡', 'muscles': ['shoulders']},
        {'name': 'Arms Day',     'emoji': '🔥', 'muscles': ['biceps','triceps','core']},
    ],
    6: [
        {'name': 'Push A',  'emoji': '🔥', 'muscles': ['chest','shoulders','triceps']},
        {'name': 'Pull A',  'emoji': '💪', 'muscles': ['back','biceps']},
        {'name': 'Leg A',   'emoji': '🦵', 'muscles': ['legs','glutes']},
        {'name': 'Push B',  'emoji': '⚡', 'muscles': ['chest','shoulders','triceps']},
        {'name': 'Pull B',  'emoji': '🏋️', 'muscles': ['back','biceps','core']},
        {'name': 'Leg B',   'emoji': '🔥', 'muscles': ['legs','hamstrings','calves']},
    ],
}

# Low-impact split for seniors / joint issues
LOW_IMPACT_SPLIT = [
    {'name': 'Upper Body (Low Impact)', 'emoji': '💪', 'muscles': ['chest','back','arms','shoulders']},
    {'name': 'Lower Body (Low Impact)', 'emoji': '🦵', 'muscles': ['legs','glutes','calves']},
    {'name': 'Core & Mobility',         'emoji': '🧘', 'muscles': ['core']},
]

# Persona → difficulty cap
PERSONA_DIFFICULTY = {
    0: 1,  # Lean Beginner
    1: 2,  # Home Warrior
    2: 2,  # Gym Newbie
    3: 3,  # Intermediate Gym
    4: 3,  # Advanced Athlete
    5: 2,  # Busy Professional
    6: 2,  # Weight Loss Focus
    7: 1,  # Senior Fit
    8: 2,  # Female Toner
}

# Persona → number of exercises per session
PERSONA_EXERCISE_COUNT = {
    0: 5, 1: 6, 2: 6, 3: 7, 4: 8,
    5: 5, 6: 6, 7: 5, 8: 6,
}

# Persona → sets and reps style
PERSONA_SETS_STYLE = {
    0: ('endurance',  3, [15, 20]),
    1: ('hypertrophy',3, [12, 15]),
    2: ('hypertrophy',3, [10, 12]),
    3: ('hypertrophy',4, [8,  12]),
    4: ('strength',   5, [5,   8]),
    5: ('endurance',  3, [12, 15]),
    6: ('endurance',  3, [15, 20]),
    7: ('endurance',  3, [12, 18]),
    8: ('toning',     3, [15, 20]),
}

# Equipment mapped to exercise equipment tags
EQUIP_MAP = {
    'no_equipment': ['none', 'bodyweight'],
    'dumbbells':    ['none', 'bodyweight', 'dumbbells'],
    'full_gym':     ['none', 'bodyweight', 'dumbbells', 'gym', 'pullup_bar'],
}

# Injury → blocked muscle groups
INJURY_BLOCKS = {
    'knee':     ['legs', 'calves', 'hamstrings', 'glutes'],
    'back':     ['back', 'deadlift'],
    'shoulder': ['shoulders', 'chest'],
    'wrist':    ['chest', 'triceps', 'biceps', 'arms'],
    'neck':     ['shoulders'],
}


def get_todays_split(persona_id: int, frequency: int, day_index: int,
                     injuries: list = None) -> dict:
    """Returns today's workout split based on day index."""
    if persona_id == 7 or (injuries and len(injuries) > 2):
        split_list = LOW_IMPACT_SPLIT
    else:
        split_list = SPLITS.get(min(frequency, 6), SPLITS[4])
    return split_list[day_index % len(split_list)]


def generate_workout(profile: dict, day_index: int = None,
                     injuries: list = None,
                     history_exercise_ids: list = None) -> dict:
    """
    Main entry point — generates a complete daily workout.

    Args:
        profile          : output of profiler.build_profile()
        day_index        : which day in the training week (0-based).
                           If None, derived from today's weekday.
        injuries         : list of injury strings e.g. ['knee', 'shoulder']
        history_exercise_ids: list of exercise IDs used in last 3 sessions

    Returns:
        dict with full workout plan ready for the app
    """
    exercises_db  = _load_exercises()
    persona_id    = profile['persona']['persona_id']
    frequency     = int(profile['user'].get('frequency', 4))
    equipment_key = profile['user'].get('equipment', 'no_equipment')
    injuries      = injuries or []
    history_ids   = set(history_exercise_ids or [])

    if day_index is None:
        day_index = date.today().weekday() % frequency

    # ── Get today's split ──────────────────────────────────────────
    split      = get_todays_split(persona_id, frequency, day_index, injuries)
    target_muscles = split['muscles']

    # ── Apply injury blocks ────────────────────────────────────────
    blocked_muscles = set()
    for inj in injuries:
        blocked_muscles.update(INJURY_BLOCKS.get(inj, []))
    filtered_muscles = [m for m in target_muscles if m not in blocked_muscles]
    if not filtered_muscles:
        filtered_muscles = ['core']  # fallback

    # ── Allowed equipment ──────────────────────────────────────────
    allowed_equip = EQUIP_MAP.get(equipment_key, EQUIP_MAP['no_equipment'])

    # ── Difficulty cap ─────────────────────────────────────────────
    max_diff = PERSONA_DIFFICULTY.get(persona_id, 2)

    # ── Filter exercises ───────────────────────────────────────────
    pool = []
    for ex in exercises_db:
        if ex['muscle'] not in filtered_muscles and \
           not any(s in filtered_muscles for s in ex.get('secondary', [])):
            continue
        if not any(e in allowed_equip for e in ex['equipment']):
            continue
        if ex['difficulty'] > max_diff:
            continue
        if persona_id == 7 and not ex.get('joint_friendly', True) and ex['difficulty'] > 1:
            continue
        pool.append(ex)

    # ── Apply freshness filter ─────────────────────────────────────
    fresh_pool = [e for e in pool if e['id'] not in history_ids]
    if len(fresh_pool) < 4:
        fresh_pool = pool  # fall back if not enough fresh options

    # ── Select exercises ───────────────────────────────────────────
    n_exercises = PERSONA_EXERCISE_COUNT.get(persona_id, 6)
    random.seed(int(datetime.now().strftime('%Y%m%d')) + persona_id)

    # Ensure at least one compound movement
    compounds = [e for e in fresh_pool if e['category'] == 'compound']
    isolations= [e for e in fresh_pool if e['category'] != 'compound']

    selected = []
    n_compounds = max(2, n_exercises // 2)
    n_isolation = n_exercises - n_compounds

    if compounds:
        selected += random.sample(compounds, min(n_compounds, len(compounds)))
    if isolations:
        remaining = [e for e in isolations if e not in selected]
        selected += random.sample(remaining, min(n_isolation, len(remaining)))

    if len(selected) < n_exercises:
        extras = [e for e in fresh_pool if e not in selected]
        selected += random.sample(extras, min(n_exercises - len(selected), len(extras)))

    # ── Build exercise plan ────────────────────────────────────────
    style, base_sets, reps_range = PERSONA_SETS_STYLE.get(persona_id, ('hypertrophy', 3, [10, 12]))

    plan_exercises = []
    total_calories = 0
    total_minutes  = 0

    for ex in selected:
        sets = ex['sets_range'][0] if base_sets <= ex['sets_range'][0] else base_sets
        sets = min(sets, ex['sets_range'][1])
        reps = random.randint(reps_range[0], reps_range[1])
        rest = ex['rest_sec']

        cal_est = ex.get('calories_per_set', 10) * sets
        total_calories += cal_est
        total_minutes  += (sets * 45 + (sets - 1) * rest) / 60

        plan_exercises.append({
            'id':           ex['id'],
            'name':         ex['name'],
            'muscle':       ex['muscle'],
            'category':     ex['category'],
            'sets':         sets,
            'reps':         reps,
            'rest_sec':     rest,
            'instructions': ex['instructions'],
            'home_alt':     ex.get('home_alt', ex['name']),
            'calories_est': cal_est,
        })

    total_minutes = round(total_minutes + len(selected) * 1.5)  # transition time

    return {
        'date':             date.today().isoformat(),
        'day_index':        day_index,
        'split_name':       split['name'],
        'split_emoji':      split['emoji'],
        'persona':          profile['persona']['persona_name'],
        'muscle_groups':    filtered_muscles,
        'exercises':        plan_exercises,
        'total_exercises':  len(plan_exercises),
        'estimated_minutes':total_minutes,
        'calories_burned':  round(total_calories * 1.4),
        'training_style':   style,
        'injuries_applied': injuries,
        'equipment_used':   equipment_key,
    }


if __name__ == '__main__':
    # Quick test
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from engine.profiler import build_profile

    sample_user = {
        'goal': 'build_muscle', 'gender': 'Male', 'age': 23,
        'height_cm': 175, 'weight_kg': 70, 'diet_type': 'standard',
        'activity_level': 'moderate', 'equipment': 'full_gym',
        'frequency': 4, 'region': 'indian',
    }
    prof    = build_profile(sample_user)
    workout = generate_workout(prof, day_index=0)

    print(f"\n== {workout['split_name']} {workout['split_emoji']} ==")
    print(f"Style: {workout['training_style']} | "
          f"~{workout['estimated_minutes']} min | "
          f"~{workout['calories_burned']} kcal\n")
    for i, ex in enumerate(workout['exercises'], 1):
        print(f"  {i}. {ex['name']:<28} {ex['sets']}x{ex['reps']}  rest:{ex['rest_sec']}s  [{ex['muscle']}]")
