"""
test_engine.py — Integration test for all 10 user scenarios
Run: python test_engine.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.profiler          import build_profile
from engine.workout_generator import generate_workout
from engine.diet_generator    import generate_diet
from engine.freshness_engine  import get_freshness_context

PASS = "✅"
FAIL = "❌"

SCENARIOS = [
    {"name":"Young Male Gym Beginner (Muscle Gain)","user":{"goal":"build_muscle","gender":"Male","age":21,"height_cm":175,"weight_kg":65,"diet_type":"standard","activity_level":"sedentary","equipment":"full_gym","frequency":4,"region":"indian"},"injuries":[]},
    {"name":"Female Weight Loss (Dumbbells)","user":{"goal":"lose_weight","gender":"Female","age":28,"height_cm":160,"weight_kg":72,"diet_type":"vegetarian","activity_level":"moderate","equipment":"dumbbells","frequency":4,"region":"indian"},"injuries":[]},
    {"name":"Advanced Gym Athlete (5 days)","user":{"goal":"build_muscle","gender":"Male","age":25,"height_cm":180,"weight_kg":82,"diet_type":"standard","activity_level":"very_active","equipment":"full_gym","frequency":5,"region":"western"},"injuries":[]},
    {"name":"Senior (Age 48, Stay Active)","user":{"goal":"stay_active","gender":"Male","age":48,"height_cm":170,"weight_kg":78,"diet_type":"vegetarian","activity_level":"light","equipment":"no_equipment","frequency":3,"region":"indian"},"injuries":[]},
    {"name":"Vegan Female, Weight Loss, No Equipment","user":{"goal":"lose_weight","gender":"Female","age":24,"height_cm":163,"weight_kg":58,"diet_type":"vegan","activity_level":"moderate","equipment":"no_equipment","frequency":3,"region":"indian"},"injuries":[]},
    {"name":"Jain Diet, Muscle Gain, Dumbbells","user":{"goal":"build_muscle","gender":"Male","age":30,"height_cm":172,"weight_kg":68,"diet_type":"jain","activity_level":"active","equipment":"dumbbells","frequency":4,"region":"indian"},"injuries":[]},
    {"name":"Knee Injury — Lower Body Excluded","user":{"goal":"stay_active","gender":"Female","age":35,"height_cm":165,"weight_kg":62,"diet_type":"eggetarian","activity_level":"moderate","equipment":"dumbbells","frequency":3,"region":"indian"},"injuries":["knee"]},
    {"name":"Navratri Fasting Mode","user":{"goal":"stay_active","gender":"Female","age":29,"height_cm":158,"weight_kg":55,"diet_type":"vegetarian","activity_level":"light","equipment":"no_equipment","frequency":3,"region":"indian"},"injuries":[],"fasting":"navratri"},
    {"name":"Non-Veg, Stamina Goal, Full Gym","user":{"goal":"improve_stamina","gender":"Male","age":22,"height_cm":177,"weight_kg":70,"diet_type":"standard","activity_level":"active","equipment":"full_gym","frequency":5,"region":"global"},"injuries":[]},
    {"name":"Busy Professional (Sedentary, 3 days)","user":{"goal":"stay_active","gender":"Male","age":33,"height_cm":174,"weight_kg":80,"diet_type":"standard","activity_level":"sedentary","equipment":"dumbbells","frequency":3,"region":"indian"},"injuries":[]},
]

def test_scenario(s, idx):
    print(f"\n  [{idx+1}] {s['name']}")
    errors = []
    fasting = s.get('fasting')

    # Profile
    try:
        profile = build_profile(s['user'])
        p = profile['persona']
        t = profile['targets']
        print(f"       Persona : {p['persona_name']} ({p['confidence']}%)")
        print(f"       Targets : {t['calories']} kcal | P:{t['protein_g']}g C:{t['carbs_g']}g F:{t['fat_g']}g")
        assert 1000 <= t['calories'] <= 6000
    except Exception as e:
        errors.append(f"Profile: {e}"); return errors

    # Workout
    try:
        workout = generate_workout(profile=profile, day_index=idx % s['user']['frequency'],
                                   injuries=s.get('injuries',[]), history_exercise_ids=[])
        n = len(workout['exercises'])
        print(f"       Workout : {workout['split_name']} | {n} ex | ~{workout['estimated_minutes']}min | ~{workout['calories_burned']}kcal")
        assert n >= 3, f"Too few: {n}"
        if 'knee' in s.get('injuries',[]):
            leg_muscles = {'legs','glutes','calves','hamstrings'}
            blocked = [e['name'] for e in workout['exercises'] if e['muscle'] in leg_muscles]
            if blocked:
                errors.append(f"Knee injury not respected: {blocked}")
            else:
                print(f"       Injury  : Knee respected — no lower body ✅")
    except Exception as e:
        errors.append(f"Workout: {e}")

    # Diet
    try:
        diet = generate_diet(profile=profile, fasting=fasting, yesterday_food_ids=[])
        total  = diet['totals']['calories']
        target = diet['targets']['calories']
        diff   = abs(total - target)
        n_meals= len(diet['meals'])
        n_foods= sum(len(m['items']) for m in diet['meals'])
        # Fasting allows wider gap (limited food options)
        gap_limit = 700 if fasting else 400
        print(f"       Diet    : {n_meals} meals | {n_foods} foods | {total} kcal (target {target}, diff {diff}){' [FASTING]' if fasting else ''}")
        assert n_meals == 5, f"Expected 5 meals, got {n_meals}"
        assert diff < gap_limit, f"Calorie gap {diff} > {gap_limit}"

        # Vegan check
        if s['user']['diet_type'] == 'vegan':
            non_vegan_tags = ['non_veg','egg']
            for meal in diet['meals']:
                for item in meal['items']:
                    if any(t in item.get('tags',[]) for t in non_vegan_tags):
                        errors.append(f"Vegan violated: {item['name']}")
    except Exception as e:
        errors.append(f"Diet: {e}")

    return errors

def run_all():
    print("\n" + "="*60)
    print("  Fitment ML Engine — Integration Tests (10 Scenarios)")
    print("="*60)
    passed, failed = 0, 0
    for i, s in enumerate(SCENARIOS):
        errs = test_scenario(s, i)
        if errs:
            failed += 1
            for e in errs: print(f"       {FAIL} {e}")
        else:
            passed += 1
            print(f"       {PASS} All checks passed")
    print("\n" + "="*60)
    print(f"  Results: {PASS} {passed} passed  |  {FAIL} {failed} failed")
    print("="*60 + "\n")
    if failed > 0: sys.exit(1)

if __name__ == '__main__':
    run_all()
