"""
engine/freshness_engine.py
───────────────────────────
Tracks workout and diet history to ensure:
  - No exercise repeated within 3 sessions
  - No exact meal repeated on consecutive days
  - Progressive overload nudges
  - Smart rest day detection
"""
import os, json
from datetime import date, timedelta
from collections import defaultdict

BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE, 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(user_id: str, kind: str) -> str:
    return os.path.join(CACHE_DIR, f"{user_id}_{kind}.json")


def _load(user_id: str, kind: str) -> dict:
    path = _cache_path(user_id, kind)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def _save(user_id: str, kind: str, data: dict):
    with open(_cache_path(user_id, kind), 'w') as f:
        json.dump(data, f, indent=2)


# ── Workout history ───────────────────────────────────────────────────────────

def save_workout_session(user_id: str, workout: dict):
    """Save completed workout to history."""
    history = _load(user_id, 'workout_history')
    today   = date.today().isoformat()
    history[today] = {
        'exercise_ids': [e['id'] for e in workout['exercises']],
        'split_name':   workout['split_name'],
        'day_index':    workout['day_index'],
    }
    # Keep only last 30 days
    dates = sorted(history.keys(), reverse=True)[:30]
    history = {d: history[d] for d in dates}
    _save(user_id, 'workout_history', history)


def get_recent_exercise_ids(user_id: str, n_sessions: int = 3) -> list:
    """Return exercise IDs used in the last n sessions."""
    history = _load(user_id, 'workout_history')
    dates   = sorted(history.keys(), reverse=True)[:n_sessions]
    ids     = []
    for d in dates:
        ids.extend(history[d].get('exercise_ids', []))
    return list(set(ids))


def get_last_day_index(user_id: str) -> int:
    """Return the day_index from the last session (to continue the split)."""
    history = _load(user_id, 'workout_history')
    if not history:
        return -1
    latest_date = max(history.keys())
    return history[latest_date].get('day_index', -1)


def get_progressive_overload_nudges(user_id: str, workout: dict) -> list:
    """
    Returns nudges for exercises where weight should be increased.
    Compares sets/reps against last 3 sessions.
    """
    history = _load(user_id, 'workout_history')
    nudges  = []

    dates = sorted(history.keys(), reverse=True)[:3]
    recent_ids = []
    for d in dates:
        recent_ids.extend(history[d].get('exercise_ids', []))
    repeat_count = defaultdict(int)
    for eid in recent_ids:
        repeat_count[eid] += 1

    for ex in workout.get('exercises', []):
        if repeat_count[ex['id']] >= 3:
            nudges.append({
                'exercise_id': ex['id'],
                'exercise_name': ex['name'],
                'message': f"You've done {ex['name']} 3+ times — try adding 2.5kg or 2 reps today! 💪",
                'type': 'progressive_overload',
            })

    return nudges


# ── Diet history ──────────────────────────────────────────────────────────────

def save_diet_session(user_id: str, diet: dict):
    """Save today's diet food IDs to history."""
    history = _load(user_id, 'diet_history')
    today   = date.today().isoformat()
    history[today] = {
        'food_ids': diet.get('food_ids_used', []),
        'calories': diet['totals']['calories'],
    }
    dates = sorted(history.keys(), reverse=True)[:14]
    history = {d: history[d] for d in dates}
    _save(user_id, 'diet_history', history)


def get_yesterday_food_ids(user_id: str) -> list:
    """Return food IDs from yesterday to avoid repetition."""
    history   = _load(user_id, 'diet_history')
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return history.get(yesterday, {}).get('food_ids', [])


def get_calorie_streak(user_id: str) -> dict:
    """Returns how many consecutive days the user hit calorie targets."""
    history = _load(user_id, 'diet_history')
    streak  = 0
    for i in range(30):
        d = (date.today() - timedelta(days=i)).isoformat()
        if d in history:
            streak += 1
        else:
            break
    return {'calorie_streak_days': streak}


# ── Smart day index ───────────────────────────────────────────────────────────

def get_smart_day_index(user_id: str, frequency: int) -> int:
    """
    Intelligently picks today's day index based on:
    - Last session's day index
    - Whether user trained yesterday
    """
    history  = _load(user_id, 'workout_history')
    today    = date.today().isoformat()
    yesterday= (date.today() - timedelta(days=1)).isoformat()

    if today in history:
        return history[today]['day_index']

    last_idx = get_last_day_index(user_id)
    if last_idx == -1:
        return 0

    # If user trained yesterday, advance to next day
    if yesterday in history:
        return (last_idx + 1) % frequency

    # User skipped — continue from where they left off
    return (last_idx + 1) % frequency


# ── Rest day recommendation ───────────────────────────────────────────────────

def should_rest_today(user_id: str, frequency: int) -> dict:
    """
    Returns whether today should be a rest day based on
    consecutive training days.
    """
    history = _load(user_id, 'workout_history')
    dates   = sorted(history.keys(), reverse=True)

    consecutive = 0
    for i in range(len(dates)):
        expected = (date.today() - timedelta(days=i)).isoformat()
        if expected in history:
            consecutive += 1
        else:
            break

    max_consecutive = {3: 2, 4: 2, 5: 3, 6: 3}.get(frequency, 2)
    needs_rest = consecutive >= max_consecutive

    return {
        'should_rest':       needs_rest,
        'consecutive_days':  consecutive,
        'reason': (
            f"You've trained {consecutive} days in a row — "
            "rest day recommended for muscle recovery!" if needs_rest
            else None
        )
    }


# ── Full freshness context ────────────────────────────────────────────────────

def get_freshness_context(user_id: str, frequency: int) -> dict:
    """
    Returns everything needed to generate fresh daily plans.
    Call this before generate_workout() and generate_diet().
    """
    return {
        'recent_exercise_ids':  get_recent_exercise_ids(user_id, n_sessions=3),
        'yesterday_food_ids':   get_yesterday_food_ids(user_id),
        'smart_day_index':      get_smart_day_index(user_id, frequency),
        'rest_recommendation':  should_rest_today(user_id, frequency),
        'calorie_streak':       get_calorie_streak(user_id),
    }


if __name__ == '__main__':
    ctx = get_freshness_context('test_user_001', frequency=4)
    print("Freshness context:")
    for k, v in ctx.items():
        print(f"  {k}: {v}")
