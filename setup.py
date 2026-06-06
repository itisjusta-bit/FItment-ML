"""
setup.py — One-command setup for Fitment ML Engine
Run: python setup.py
"""
import subprocess, sys, os

BASE = os.path.dirname(os.path.abspath(__file__))

def run(cmd, cwd=None):
    print(f"  → {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=cwd or BASE)
    if r.returncode != 0:
        print(f"  ✗ Failed"); sys.exit(1)

print("\n" + "="*55)
print("  🌱 Fitment ML Engine — Setup")
print("="*55 + "\n")

print("[1/4] Installing dependencies...")
run(f"{sys.executable} -m pip install flask scikit-learn pandas numpy -q")
print("  ✓ Done\n")

print("[2/4] Building data files...")
run(f"{sys.executable} data/exercises.py")
run(f"{sys.executable} data/foods_indian.py")
run(f"{sys.executable} data/generate_profiles.py")
print("  ✓ Done\n")

print("[3/4] Training Persona Classifier ML model...")
run(f"{sys.executable} models/train_persona.py")
print("  ✓ Done\n")

print("[4/4] Running integration test...")
run(f"{sys.executable} test_engine.py")
print("  ✓ Done\n")

print("="*55)
print("  ✅ Setup complete!")
print("="*55)
print("\n  Start the API server:")
print("      python api/app.py")
print("\n  API running at: http://localhost:8000\n")
