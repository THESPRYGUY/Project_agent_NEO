"""Quick verification script to test the intake flow fixes."""

import json
from pathlib import Path

def check_generated_repo():
    """Check if generated repos exist and contain required files."""
    project_root = Path(__file__).resolve().parents[1]
    repos_dir = project_root / "generated_repos"
    
    if not repos_dir.exists():
        print("❌ generated_repos directory does not exist")
        return False
    
    repo_folders = [d for d in repos_dir.iterdir() if d.is_dir()]
    
    if not repo_folders:
        print("ℹ️  No repos generated yet - this is expected on first run")
        return True
    
    print(f"✅ Found {len(repo_folders)} generated repo(s):")
    
    for repo_dir in repo_folders:
        print(f"\n  📁 {repo_dir.name}")
        
        # Check for essential files
        essential_files = [
            "README.md",
            "neo_agent_config.json",
            "01_README+Directory-Map_v2.json",
            "INTEGRITY_REPORT.json"
        ]
        
        for filename in essential_files:
            file_path = repo_dir / filename
            if file_path.exists():
                print(f"    ✓ {filename}")
            else:
                print(f"    ✗ {filename} (missing)")
        
        # Count JSON pack files
        json_files = list(repo_dir.glob("*.json"))
        print(f"    📊 Total JSON files: {len(json_files)}")
        
        # Check integrity report
        integrity_path = repo_dir / "INTEGRITY_REPORT.json"
        if integrity_path.exists():
            try:
                with integrity_path.open("r", encoding="utf-8") as f:
                    report = json.load(f)
                checks = report.get("checks", {})
                print(f"    📋 Integrity checks:")
                for check_name, passed in checks.items():
                    symbol = "✓" if passed else "✗"
                    print(f"      {symbol} {check_name}: {passed}")
            except Exception as e:
                print(f"    ⚠️  Could not parse integrity report: {e}")
    
    return True


def check_profile_state():
    """Check if agent profile preserves state."""
    project_root = Path(__file__).resolve().parents[1]
    profile_path = project_root / "agent_profile.json"
    
    if not profile_path.exists():
        print("\nℹ️  No agent_profile.json found - this is expected on first run")
        return True
    
    print("\n✅ Agent profile exists:")
    
    try:
        with profile_path.open("r", encoding="utf-8") as f:
            profile = json.load(f)
        
        # Check identity
        identity = profile.get("identity", {})
        if identity.get("agent_id"):
            print(f"  ✓ Agent ID: {identity.get('agent_id')}")
        
        # Check business function
        business_function = profile.get("business_function", "")
        if business_function:
            print(f"  ✓ Business Function: {business_function}")
        
        # Check role
        role = profile.get("role", {})
        if isinstance(role, dict) and role.get("code"):
            print(f"  ✓ Role Code: {role.get('code')}")
            print(f"  ✓ Role Title: {role.get('title')}")
        
        # Check NAICS
        naics = profile.get("classification", {}).get("naics") or profile.get("naics", {})
        if isinstance(naics, dict) and naics.get("code"):
            print(f"  ✓ NAICS: {naics.get('code')} - {naics.get('title')}")
        
        return True
    except Exception as e:
        print(f"  ⚠️  Could not parse profile: {e}")
        return False


def main():
    print("=" * 60)
    print("Intake Flow Verification")
    print("=" * 60)
    
    check_generated_repo()
    check_profile_state()
    
    print("\n" + "=" * 60)
    print("Verification complete!")
    print("=" * 60)
    print("\nTo test the intake flow:")
    print("  1. Run: python -m neo_agent.intake_app")
    print("  2. Open: http://127.0.0.1:5000")
    print("  3. Fill out the form and click 'Generate Agent Profile'")
    print("  4. Check generated_repos/ for a new folder")
    print("  5. Re-run this script to see the results")


if __name__ == "__main__":
    main()
