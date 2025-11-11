import json, glob, sys
REQUIRED = ["owners","capabilities","lifecycle","hitl_triggers"]
OWNER_ROLES = ["CAIO","CPA","TeamLead"]
OWNER_EMAILS = ["caio@glitch.inc","cpa@glitch.inc","teamlead@glitch.inc"]  # placeholders (REQUIRED to replace)
CAPS = ["plan","build","evaluate","research"]
LIFECYCLE = {"states":["dev","staging","prod"],"promotion_rules":"gated","notes":"HITL for legal/reg/fin"}
HITL = {"required_for":["legal","regulatory","financial","prod_cutover"],"approvers":["CAIO","TeamLead"]}
def patch(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    changed = False
    if not data.get("owners"):
        data["owners"] = [{"role": r, "email": e, "REQUIRED_replace": True} for r, e in zip(OWNER_ROLES, OWNER_EMAILS)]
        changed = True
    if not data.get("capabilities"):
        data["capabilities"] = CAPS; changed = True
    if not data.get("lifecycle"):
        data["lifecycle"] = LIFECYCLE; changed = True
    if not data.get("hitl_triggers"):
        data["hitl_triggers"] = HITL; changed = True
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return changed
changed_files = 0
paths = glob.glob("_out/**/Agent_Manifest.json", recursive=True) + glob.glob("**/Agent_Manifest.json", recursive=True)
for p in paths:
    try:
        if patch(p): changed_files += 1
    except Exception as e:
        print("error:", p, e, file=sys.stderr)
print("changed_files=", changed_files)
