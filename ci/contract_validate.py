import json, sys, glob

REQUIRED_FIELDS = ["owners", "capabilities", "lifecycle", "hitl_triggers"]
FAILS = []

for path in glob.glob("_out/**/Agent_Manifest.json", recursive=True) + glob.glob("**/Agent_Manifest.json", recursive=True):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for field in REQUIRED_FIELDS:
            if field not in data or not data[field]:
                FAILS.append(f"{path}: missing or empty '{field}'")
    except Exception as e:
        FAILS.append(f"{path}: error {e}")

if FAILS:
    print("CONTRACT VIOLATIONS:")
    for msg in FAILS:
        print(" -", msg)
    sys.exit(1)
print("contract-validate: OK")
