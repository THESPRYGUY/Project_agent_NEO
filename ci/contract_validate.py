import json, sys, glob, os

REQUIRED_FIELDS = ["owners", "capabilities", "lifecycle", "hitl_triggers"]
FAILS = []
STRICT = os.getenv("STRICT_RELEASE", "0") == "1"
STRICT_FAILS = []

for path in glob.glob("_out/**/Agent_Manifest.json", recursive=True) + glob.glob("**/Agent_Manifest.json", recursive=True):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for field in REQUIRED_FIELDS:
            if field not in data or not data[field]:
                FAILS.append(f"{path}: missing or empty '{field}'")
        if STRICT:
            owners = data.get("owners") or []
            for owner in owners:
                if isinstance(owner, dict) and owner.get("REQUIRED_replace") is True:
                    STRICT_FAILS.append(
                        f"{path}: owner placeholder (REQUIRED_replace=true) must be replaced before release"
                    )
    except Exception as e:
        FAILS.append(f"{path}: error {e}")

if FAILS or STRICT_FAILS:
    print("CONTRACT VIOLATIONS:")
    for msg in FAILS + STRICT_FAILS:
        print(" -", msg)
    sys.exit(1)
print("contract-validate: OK")
