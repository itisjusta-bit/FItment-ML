"""
api/app.py
───────────
Flask API for the Fitment ML Engine.
Exposes endpoints for the React Native app to call.

Endpoints:
  POST /api/profile            → Build full fitness profile
  POST /api/workout/generate   → Generate today's workout
  POST /api/diet/generate      → Generate today's meal plan
  POST /api/plan/daily         → Generate both in one call
  POST /api/workout/complete   → Mark workout done, save history
  POST /api/diet/complete      → Save today's diet history
  GET  /api/persona/all        → List all 9 personas
  GET  /api/exercises          → Full exercise database
  GET  /api/foods              → Full food database
  POST /api/swap/exercise      → Get alternative exercise
  POST /api/swap/meal          → Get alternative meal
  GET  /api/health             → Health check
"""
import os, sys, json
from flask import Flask, request, jsonify

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from engine.profiler          import build_profile, PERSONA_NAMES, PERSONA_DESCRIPTIONS
from engine.workout_generator import generate_workout, _load_exercises
from engine.diet_generator    import generate_diet, _load_foods
from engine.freshness_engine  import (
    get_freshness_context, save_workout_session, save_diet_session,
    get_progressive_overload_nudges
)

app = Flask(__name__)


def _err(msg: str, code: int = 400):
    return jsonify({'success': False, 'error': msg}), code

def _ok(data: dict):
    return jsonify({'success': True, **data})


# ── Health check ──────────────────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health():
    return _ok({'status': 'running', 'service': 'Fitment ML Engine v1.0'})


# ── Profile ───────────────────────────────────────────────────────────────────
@app.route('/api/profile', methods=['POST'])
def profile():
    """
    Build complete fitness profile from onboarding data.
    Body: { goal, gender, age, height_cm, weight_kg,
            diet_type, activity_level, equipment, frequency, region }
    """
    body = request.get_json()
    if not body:
        return _err('Request body required')

    required = ['goal', 'gender', 'age', 'height_cm', 'weight_kg',
                 'activity_level', 'equipment', 'frequency']
    for field in required:
        if field not in body:
            return _err(f'Missing field: {field}')

    try:
        prof = build_profile(body)
        return _ok({'profile': prof})
    except FileNotFoundError as e:
        return _err(str(e), 503)
    except Exception as e:
        return _err(str(e), 500)


# ── Workout generate ──────────────────────────────────────────────────────────
@app.route('/api/workout/generate', methods=['POST'])
def workout_generate():
    """
    Generate today's workout plan.
    Body: {
      user: { ...onboarding fields },
      user_id: "uuid",             ← for history tracking
      injuries: [],                ← optional
      day_index: null              ← optional, auto from history
    }
    """
    body    = request.get_json() or {}
    user    = body.get('user')
    user_id = body.get('user_id', 'anonymous')
    injuries= body.get('injuries', [])

    if not user:
        return _err('user object required')

    try:
        prof = build_profile(user)
        ctx  = get_freshness_context(user_id, int(user.get('frequency', 4)))

        # Check rest recommendation
        rest_rec = ctx['rest_recommendation']
        if rest_rec['should_rest'] and not body.get('force_workout'):
            return _ok({
                'rest_day':    True,
                'message':     rest_rec['reason'],
                'consecutive': rest_rec['consecutive_days'],
                'workout':     None,
            })

        workout = generate_workout(
            profile=prof,
            day_index=ctx['smart_day_index'],
            injuries=injuries,
            history_exercise_ids=ctx['recent_exercise_ids'],
        )

        nudges = get_progressive_overload_nudges(user_id, workout)

        return _ok({
            'workout':           workout,
            'progressive_nudges': nudges,
            'rest_day':          False,
            'day_index':         ctx['smart_day_index'],
            'calorie_streak':    ctx['calorie_streak'],
        })
    except Exception as e:
        return _err(str(e), 500)


# ── Diet generate ─────────────────────────────────────────────────────────────
@app.route('/api/diet/generate', methods=['POST'])
def diet_generate():
    """
    Generate today's meal plan.
    Body: {
      user: { ...onboarding fields },
      user_id: "uuid",
      fasting: null               ← e.g. 'navratri', 'ekadashi'
    }
    """
    body    = request.get_json() or {}
    user    = body.get('user')
    user_id = body.get('user_id', 'anonymous')
    fasting = body.get('fasting')

    if not user:
        return _err('user object required')

    try:
        prof = build_profile(user)
        ctx  = get_freshness_context(user_id, int(user.get('frequency', 4)))
        diet = generate_diet(
            profile=prof,
            fasting=fasting,
            yesterday_food_ids=ctx['yesterday_food_ids'],
        )
        return _ok({'diet': diet})
    except Exception as e:
        return _err(str(e), 500)


# ── Daily plan (workout + diet in one call) ───────────────────────────────────
@app.route('/api/plan/daily', methods=['POST'])
def daily_plan():
    """
    Generate both workout and diet for today in a single API call.
    Body: {
      user: { ...onboarding fields },
      user_id: "uuid",
      injuries: [],
      fasting: null
    }
    """
    body    = request.get_json() or {}
    user    = body.get('user')
    user_id = body.get('user_id', 'anonymous')
    injuries= body.get('injuries', [])
    fasting = body.get('fasting')

    if not user:
        return _err('user object required')

    try:
        prof    = build_profile(user)
        ctx     = get_freshness_context(user_id, int(user.get('frequency', 4)))

        rest_rec = ctx['rest_recommendation']

        # Workout
        if rest_rec['should_rest'] and not body.get('force_workout'):
            workout_result = {'rest_day': True, 'message': rest_rec['reason'], 'workout': None}
        else:
            workout = generate_workout(
                profile=prof,
                day_index=ctx['smart_day_index'],
                injuries=injuries,
                history_exercise_ids=ctx['recent_exercise_ids'],
            )
            nudges = get_progressive_overload_nudges(user_id, workout)
            workout_result = {'rest_day': False, 'workout': workout, 'nudges': nudges}

        # Diet
        diet = generate_diet(
            profile=prof,
            fasting=fasting,
            yesterday_food_ids=ctx['yesterday_food_ids'],
        )

        return _ok({
            'profile':        prof,
            'workout':        workout_result,
            'diet':           diet,
            'calorie_streak': ctx['calorie_streak'],
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return _err(str(e), 500)


# ── Mark workout complete ─────────────────────────────────────────────────────
@app.route('/api/workout/complete', methods=['POST'])
def workout_complete():
    """
    Save completed workout to history.
    Body: { user_id: "uuid", workout: { ...workout object } }
    """
    body    = request.get_json() or {}
    user_id = body.get('user_id', 'anonymous')
    workout = body.get('workout')
    if not workout:
        return _err('workout object required')
    try:
        save_workout_session(user_id, workout)
        return _ok({'saved': True, 'message': 'Workout saved to history!'})
    except Exception as e:
        return _err(str(e), 500)


# ── Mark diet complete ────────────────────────────────────────────────────────
@app.route('/api/diet/complete', methods=['POST'])
def diet_complete():
    """
    Save today's diet to history for freshness tracking.
    Body: { user_id: "uuid", diet: { ...diet object } }
    """
    body    = request.get_json() or {}
    user_id = body.get('user_id', 'anonymous')
    diet    = body.get('diet')
    if not diet:
        return _err('diet object required')
    try:
        save_diet_session(user_id, diet)
        return _ok({'saved': True})
    except Exception as e:
        return _err(str(e), 500)


# ── Swap exercise ─────────────────────────────────────────────────────────────
@app.route('/api/swap/exercise', methods=['POST'])
def swap_exercise():
    """
    Get an alternative exercise for the same muscle group.
    Body: { exercise_id: "CH001", equipment: "no_equipment", exclude_ids: [] }
    """
    body     = request.get_json() or {}
    ex_id    = body.get('exercise_id')
    equip    = body.get('equipment', 'no_equipment')
    excludes = set(body.get('exclude_ids', []))
    excludes.add(ex_id)

    exercises = _load_exercises()
    original  = next((e for e in exercises if e['id'] == ex_id), None)
    if not original:
        return _err(f'Exercise {ex_id} not found')

    from engine.workout_generator import EQUIP_MAP
    import random
    allowed = EQUIP_MAP.get(equip, EQUIP_MAP['no_equipment'])
    pool = [e for e in exercises
            if e['muscle'] == original['muscle']
            and e['id'] not in excludes
            and any(eq in allowed for eq in e['equipment'])]

    if not pool:
        return _err('No alternative exercise found')

    alt = random.choice(pool)
    return _ok({'alternative': alt})


# ── Swap meal item ────────────────────────────────────────────────────────────
@app.route('/api/swap/meal', methods=['POST'])
def swap_meal():
    """
    Get 3 alternative foods for a meal slot.
    Body: { food_id: "LU001", category: "lunch",
            diet_type: "vegetarian", region: "indian", exclude_ids: [] }
    """
    body      = request.get_json() or {}
    food_id   = body.get('food_id')
    category  = body.get('category', 'lunch')
    diet_type = body.get('diet_type', 'standard')
    region    = body.get('region', 'indian')
    excludes  = set(body.get('exclude_ids', []))
    if food_id:
        excludes.add(food_id)

    from engine.diet_generator import _filter_foods
    import random
    pool = _filter_foods(category, diet_type, region, exclude_ids=excludes)
    if not pool:
        return _err('No alternatives found')

    alts = random.sample(pool, min(3, len(pool)))
    return _ok({'alternatives': alts})


# ── Reference data ────────────────────────────────────────────────────────────
@app.route('/api/persona/all', methods=['GET'])
def personas_all():
    data = [
        {'id': pid, 'name': name, 'description': PERSONA_DESCRIPTIONS[pid]}
        for pid, name in PERSONA_NAMES.items()
    ]
    return _ok({'personas': data})


@app.route('/api/exercises', methods=['GET'])
def exercises_list():
    muscle = request.args.get('muscle')
    equip  = request.args.get('equipment')
    exs    = _load_exercises()
    if muscle: exs = [e for e in exs if e['muscle'] == muscle]
    if equip:  exs = [e for e in exs if equip in e['equipment']]
    return _ok({'exercises': exs, 'count': len(exs)})


@app.route('/api/foods', methods=['GET'])
def foods_list():
    category  = request.args.get('category')
    diet_type = request.args.get('diet_type')
    region    = request.args.get('region')
    foods     = _load_foods()
    if category:  foods = [f for f in foods if f['category'] == category]
    if diet_type: foods = [f for f in foods if diet_type in f.get('diet_types', [])]
    if region:    foods = [f for f in foods if region in f.get('region', [])]
    return _ok({'foods': foods, 'count': len(foods)})


if __name__ == '__main__':
    print("🌱 Fitment ML Engine starting...")
    print("   Endpoints: http://localhost:8000/api/")
    app.run(host='0.0.0.0', port=8000, debug=True)
