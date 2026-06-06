"""
engine/diet_generator.py
─────────────────────────
Generates a fresh daily Indian meal plan based on:
  - Calorie and macro targets (from profiler)
  - Diet type (veg / vegan / jain / eggetarian / non_veg)
  - Region preference (indian / western / global)
  - Festival/fasting mode
  - Daily freshness (yesterday's meals excluded)
"""
import os, json, random
from datetime import date, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOOD_PATH = os.path.join(BASE, 'data', 'foods_indian.json')

_foods = None

def _load_foods():
    global _foods
    if _foods is None:
        with open(FOOD_PATH, 'r') as f:
            _foods = json.load(f)
    return _foods

# ── Meal time labels ──────────────────────────────────────────────────────────
MEAL_CONFIG = [
    {'key': 'breakfast',     'label': 'Breakfast',      'time': '7:30 AM',  'emoji': '🌅', 'category': 'breakfast'},
    {'key': 'mid_morning',   'label': 'Mid-Morning',    'time': '10:30 AM', 'emoji': '🍎', 'category': 'snack'},
    {'key': 'lunch',         'label': 'Lunch',          'time': '1:00 PM',  'emoji': '🍽️', 'category': 'lunch'},
    {'key': 'evening_snack', 'label': 'Evening Snack',  'time': '5:30 PM',  'emoji': '🥜', 'category': 'snack'},
    {'key': 'dinner',        'label': 'Dinner',         'time': '8:00 PM',  'emoji': '🌙', 'category': 'dinner'},
]

# Diet type → allowed food diet_types
DIET_FILTER = {
    'standard':    ['veg','vegan','eggetarian','non_veg'],
    'vegetarian':  ['veg','vegan'],
    'vegan':       ['vegan'],
    'jain':        ['jain'],
    'eggetarian':  ['veg','vegan','eggetarian'],
    'non_veg':     ['veg','vegan','eggetarian','non_veg'],
}

# Fasting food filter
FASTING_TAGS = {
    'navratri':   ['fasting_food'],
    'ekadashi':   ['fasting_food'],
    'ramadan':    ['veg', 'non_veg'],
    'default':    ['fasting_food', 'light'],
}

# Region preference boost (foods from these regions get priority)
REGION_PRIORITY = {
    'indian':  ['north', 'south', 'east', 'west', 'all', 'punjab', 'coastal'],
    'western': ['all'],
    'global':  ['all', 'north', 'south'],
}

def _filter_foods(category: str, diet_type: str, region: str,
                  fasting: str = None, exclude_ids: set = None) -> list:
    """Return valid foods for a meal slot."""
    foods = _load_foods()
    allowed_diets  = DIET_FILTER.get(diet_type, DIET_FILTER['standard'])
    priority_regions = REGION_PRIORITY.get(region, REGION_PRIORITY['indian'])
    exclude_ids    = exclude_ids or set()

    pool = []
    for f in foods:
        if f['id'] in exclude_ids:
            continue
        if f['category'] != category:
            continue
        if not any(d in allowed_diets for d in f['diet_types']):
            continue
        if fasting and fasting in FASTING_TAGS:
            required = FASTING_TAGS[fasting]
            if not any(t in f.get('tags', []) for t in required):
                continue
        pool.append(f)

    # Sort: regional foods first
    priority = [f for f in pool if any(r in f.get('region', []) for r in priority_regions)]
    others   = [f for f in pool if f not in priority]
    return priority + others


def _select_foods_for_target(category: str, cal_target: int,
                              diet_type: str, region: str,
                              fasting: str = None,
                              exclude_ids: set = None,
                              seed: int = 42) -> list:
    """
    Greedily select 1-3 foods that together hit the calorie target ±80 kcal.
    Returns list of selected food items with quantities.
    """
    random.seed(seed)
    pool = _filter_foods(category, diet_type, region, fasting, exclude_ids)
    if not pool:
        return []

    random.shuffle(pool)
    selected = []
    remaining_cal = cal_target

    # Primary item (40-60% of meal calories)
    primary_target = cal_target * random.uniform(0.45, 0.60)
    primary_pool   = sorted(pool, key=lambda f:
                     abs(_serving_cal(f) - primary_target))
    primary = primary_pool[0]
    qty, serving_cal = _best_qty(primary, primary_target)
    selected.append(_make_item(primary, qty))
    remaining_cal -= serving_cal
    exclude_ids = (exclude_ids or set()) | {primary['id']}

    # Secondary item if calories remain (>80 kcal)
    if remaining_cal > 80:
        secondary_pool = [f for f in pool if f['id'] not in exclude_ids]
        random.shuffle(secondary_pool)
        if secondary_pool:
            secondary = sorted(secondary_pool,
                               key=lambda f: abs(_serving_cal(f) - remaining_cal))[0]
            qty2, cal2 = _best_qty(secondary, remaining_cal)
            selected.append(_make_item(secondary, qty2))
            remaining_cal -= cal2

    return selected


def _serving_cal(food: dict) -> float:
    return food['cal_per_100g'] * food['serving_size'] / 100


def _best_qty(food: dict, target_cal: float):
    """Find the best serving multiplier (0.5x, 1x, 1.5x, 2x)."""
    base_cal = _serving_cal(food)
    best_qty = 1.0
    best_diff = abs(base_cal - target_cal)
    for q in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        diff = abs(base_cal * q - target_cal)
        if diff < best_diff:
            best_diff = diff
            best_qty  = q
    return best_qty, base_cal * best_qty


def _make_item(food: dict, qty: float) -> dict:
    base_cal = _serving_cal(food)
    scale    = base_cal * qty / 100
    return {
        'food_id':     food['id'],
        'name':        food['name'],
        'name_hi':     food.get('name_hi', ''),
        'quantity':    round(qty, 2),
        'unit':        f"{qty}x {food['serving_name']}",
        'calories':    round(base_cal * qty),
        'protein_g':   round(food['protein']  * food['serving_size'] * qty / 100, 1),
        'carbs_g':     round(food['carbs']    * food['serving_size'] * qty / 100, 1),
        'fat_g':       round(food['fat']      * food['serving_size'] * qty / 100, 1),
        'category':    food['category'],
        'tags':        food.get('tags', []),
    }


def generate_diet(profile: dict,
                  fasting: str = None,
                  yesterday_food_ids: list = None) -> dict:
    """
    Main entry point — generates a complete daily meal plan.

    Args:
        profile            : output of profiler.build_profile()
        fasting            : festival fasting mode e.g. 'navratri', 'ekadashi'
        yesterday_food_ids : list of food IDs from yesterday (for freshness)

    Returns:
        dict with full meal plan ready for the app
    """
    targets     = profile['targets']
    diet_type   = profile['user'].get('diet_type', 'standard')
    region      = profile['user'].get('region', 'indian')
    exclude_ids = set(yesterday_food_ids or [])
    date_seed   = int(date.today().strftime('%Y%m%d'))

    meals       = []
    total_cal   = 0
    total_prot  = 0
    total_carbs = 0
    total_fat   = 0

    used_food_ids = set()

    for i, mc in enumerate(MEAL_CONFIG):
        meal_target_cal = targets['meal_calories'][mc['key']]
        seed = date_seed + i * 100 + profile['persona']['persona_id']

        items = _select_foods_for_target(
            category=mc['category'],
            cal_target=meal_target_cal,
            diet_type=diet_type,
            region=region,
            fasting=fasting,
            exclude_ids=exclude_ids | used_food_ids,
            seed=seed,
        )

        if not items:
            # Fallback: try without fasting restriction
            items = _select_foods_for_target(
                category=mc['category'],
                cal_target=meal_target_cal,
                diet_type=diet_type,
                region=region,
                fasting=None,
                exclude_ids=used_food_ids,
                seed=seed,
            )

        meal_cal   = sum(it['calories']  for it in items)
        meal_prot  = sum(it['protein_g'] for it in items)
        meal_carbs = sum(it['carbs_g']   for it in items)
        meal_fat   = sum(it['fat_g']     for it in items)

        total_cal   += meal_cal
        total_prot  += meal_prot
        total_carbs += meal_carbs
        total_fat   += meal_fat

        for it in items:
            used_food_ids.add(it['food_id'])

        meals.append({
            'key':        mc['key'],
            'label':      mc['label'],
            'time':       mc['time'],
            'emoji':      mc['emoji'],
            'items':      items,
            'calories':   meal_cal,
            'protein_g':  round(meal_prot, 1),
            'carbs_g':    round(meal_carbs, 1),
            'fat_g':      round(meal_fat, 1),
            'target_cal': meal_target_cal,
            'logged':     False,
        })

    return {
        'date':           date.today().isoformat(),
        'persona':        profile['persona']['persona_name'],
        'diet_type':      diet_type,
        'region':         region,
        'fasting_mode':   fasting,
        'meals':          meals,
        'totals': {
            'calories':  round(total_cal),
            'protein_g': round(total_prot, 1),
            'carbs_g':   round(total_carbs, 1),
            'fat_g':     round(total_fat, 1),
        },
        'targets': {
            'calories':  targets['calories'],
            'protein_g': targets['protein_g'],
            'carbs_g':   targets['carbs_g'],
            'fat_g':     targets['fat_g'],
        },
        'food_ids_used': list(used_food_ids),
    }


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from engine.profiler import build_profile

    sample_user = {
        'goal': 'lose_weight', 'gender': 'Female', 'age': 26,
        'height_cm': 162, 'weight_kg': 65, 'diet_type': 'vegetarian',
        'activity_level': 'moderate', 'equipment': 'dumbbells',
        'frequency': 4, 'region': 'indian',
    }
    prof = build_profile(sample_user)
    diet = generate_diet(prof)

    print(f"\n== Daily Meal Plan ({diet['diet_type']}, {diet['region']}) ==")
    print(f"Target: {diet['targets']['calories']} kcal | "
          f"P:{diet['targets']['protein_g']}g  "
          f"C:{diet['targets']['carbs_g']}g  "
          f"F:{diet['targets']['fat_g']}g\n")
    for meal in diet['meals']:
        print(f"  {meal['emoji']} {meal['label']} ({meal['time']}) — {meal['calories']} kcal")
        for it in meal['items']:
            print(f"      • {it['name']} ({it['unit']}) — {it['calories']} kcal")
    print(f"\nActual totals: {diet['totals']['calories']} kcal | "
          f"P:{diet['totals']['protein_g']}g  "
          f"C:{diet['totals']['carbs_g']}g  "
          f"F:{diet['totals']['fat_g']}g")
