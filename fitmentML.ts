/**
 * lib/fitmentML.ts
 * ─────────────────
 * React Native helper to call the Fitment ML Engine API.
 * Drop this file into your Expo project at lib/fitmentML.ts
 *
 * Usage:
 *   import { generateDailyPlan, markWorkoutComplete } from '../lib/fitmentML';
 */

const ML_BASE_URL = process.env.EXPO_PUBLIC_ML_API_URL || 'http://localhost:8000';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface UserOnboarding {
  goal: 'lose_weight' | 'build_muscle' | 'stay_active' | 'improve_stamina';
  gender: 'Male' | 'Female' | 'Other';
  age: number;
  height_cm: number;
  weight_kg: number;
  diet_type: 'standard' | 'vegetarian' | 'vegan' | 'jain' | 'eggetarian';
  activity_level: 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active';
  equipment: 'no_equipment' | 'dumbbells' | 'full_gym';
  frequency: number; // 3-6
  region: 'indian' | 'western' | 'global';
}

export interface Exercise {
  id: string;
  name: string;
  muscle: string;
  sets: number;
  reps: number;
  rest_sec: number;
  instructions: string;
  home_alt: string;
  calories_est: number;
  category: string;
}

export interface Workout {
  date: string;
  split_name: string;
  split_emoji: string;
  persona: string;
  muscle_groups: string[];
  exercises: Exercise[];
  total_exercises: number;
  estimated_minutes: number;
  calories_burned: number;
  training_style: string;
}

export interface MealItem {
  food_id: string;
  name: string;
  name_hi: string;
  quantity: number;
  unit: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface Meal {
  key: string;
  label: string;
  time: string;
  emoji: string;
  items: MealItem[];
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  logged: boolean;
}

export interface DietPlan {
  date: string;
  meals: Meal[];
  totals: { calories: number; protein_g: number; carbs_g: number; fat_g: number };
  targets: { calories: number; protein_g: number; carbs_g: number; fat_g: number };
  food_ids_used: string[];
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function post(endpoint: string, body: object) {
  const res = await fetch(`${ML_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`ML API error ${res.status}: ${endpoint}`);
  return res.json();
}

async function get(endpoint: string) {
  const res = await fetch(`${ML_BASE_URL}${endpoint}`);
  if (!res.ok) throw new Error(`ML API error ${res.status}: ${endpoint}`);
  return res.json();
}

// ── Main functions ────────────────────────────────────────────────────────────

/**
 * Generate both workout and diet plan for today in a single call.
 * Call this every morning when the app opens.
 */
export async function generateDailyPlan(
  user: UserOnboarding,
  userId: string,
  options?: { injuries?: string[]; fasting?: string; forceWorkout?: boolean }
) {
  const data = await post('/api/plan/daily', {
    user,
    user_id: userId,
    injuries: options?.injuries || [],
    fasting: options?.fasting || null,
    force_workout: options?.forceWorkout || false,
  });
  return data as {
    success: boolean;
    profile: any;
    workout: { rest_day: boolean; workout: Workout | null; nudges?: any[] };
    diet: DietPlan;
    calorie_streak: { calorie_streak_days: number };
  };
}

/**
 * Get the user's fitness profile (BMR, TDEE, persona, macros).
 */
export async function getProfile(user: UserOnboarding) {
  const data = await post('/api/profile', user);
  return data.profile;
}

/**
 * Generate only today's workout.
 */
export async function generateWorkout(
  user: UserOnboarding,
  userId: string,
  injuries: string[] = []
) {
  const data = await post('/api/workout/generate', {
    user, user_id: userId, injuries,
  });
  return data as {
    success: boolean;
    rest_day: boolean;
    workout: Workout | null;
    progressive_nudges: any[];
  };
}

/**
 * Generate only today's diet plan.
 */
export async function generateDiet(
  user: UserOnboarding,
  userId: string,
  fasting?: string
) {
  const data = await post('/api/diet/generate', {
    user, user_id: userId, fasting: fasting || null,
  });
  return data.diet as DietPlan;
}

/**
 * Mark today's workout as complete (saves to history for freshness).
 * Call this when user finishes the workout.
 */
export async function markWorkoutComplete(userId: string, workout: Workout) {
  return post('/api/workout/complete', { user_id: userId, workout });
}

/**
 * Save today's diet history (call at end of day or when logging is done).
 */
export async function saveDietHistory(userId: string, diet: DietPlan) {
  return post('/api/diet/complete', { user_id: userId, diet });
}

/**
 * Get an alternative exercise (e.g. if user dislikes one or is injured).
 */
export async function swapExercise(
  exerciseId: string,
  equipment: string,
  excludeIds: string[] = []
) {
  const data = await post('/api/swap/exercise', {
    exercise_id: exerciseId,
    equipment,
    exclude_ids: excludeIds,
  });
  return data.alternative as Exercise;
}

/**
 * Get 3 alternative meal items for a food swap.
 */
export async function swapMealItem(
  foodId: string,
  category: string,
  dietType: string,
  region: string,
  excludeIds: string[] = []
) {
  const data = await post('/api/swap/meal', {
    food_id: foodId, category, diet_type: dietType,
    region, exclude_ids: excludeIds,
  });
  return data.alternatives;
}

/**
 * ── EXAMPLE USAGE IN YOUR COMPONENT ──────────────────────────────
 *
 * // In app/(tabs)/index.tsx (Home screen)
 *
 * import { generateDailyPlan } from '../../lib/fitmentML';
 * import { useAuthStore } from '../../store/authStore';
 *
 * const HomeScreen = () => {
 *   const { user, profile } = useAuthStore();
 *   const [workout, setWorkout] = useState(null);
 *   const [diet, setDiet] = useState(null);
 *   const [loading, setLoading] = useState(true);
 *
 *   useEffect(() => {
 *     (async () => {
 *       try {
 *         const plan = await generateDailyPlan(profile, user.id);
 *         setWorkout(plan.workout.workout);
 *         setDiet(plan.diet);
 *       } catch (err) {
 *         console.error(err);
 *       } finally {
 *         setLoading(false);
 *       }
 *     })();
 *   }, []);
 *
 *   // ... render workout and diet cards
 * };
 *
 * ── COMPLETE ONBOARDING → FIRST PLAN ──────────────────────────────
 *
 * // In app/(auth)/onboarding/7.tsx (last step)
 *
 * const handleFinish = async () => {
 *   setIsSubmitting(true);
 *   const collectedStats: UserOnboarding = {
 *     goal: onboardingStore.goal,
 *     gender: onboardingStore.gender,
 *     age: onboardingStore.age,
 *     height_cm: onboardingStore.height,
 *     weight_kg: onboardingStore.weight,
 *     diet_type: onboardingStore.diet,
 *     activity_level: onboardingStore.activity,
 *     equipment: onboardingStore.equipment,
 *     frequency: onboardingStore.frequency,
 *     region: selectedRegion,
 *   };
 *
 *   // 1. Save profile to Supabase
 *   await supabase.from('profiles').update(collectedStats).eq('id', user.id);
 *
 *   // 2. Generate first plan from ML engine
 *   const plan = await generateDailyPlan(collectedStats, user.id);
 *
 *   // 3. Save plan to Supabase for offline access
 *   await supabase.from('daily_plans').upsert({
 *     user_id: user.id,
 *     date: plan.diet.date,
 *     workout: plan.workout.workout,
 *     diet: plan.diet,
 *   });
 *
 *   // 4. Navigate to dashboard
 *   router.replace('/(tabs)');
 * };
 */
