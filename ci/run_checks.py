from __future__ import annotations

import subprocess
import sys


def main() -> int:
    print("Running tests...\n")
    cp = subprocess.run([sys.executable, "-m", "pytest", "-q"], text=True)
    if cp.returncode == 0:
        print("\nPASS: All tests green.")
    else:
        print("\nFAIL: Some tests failed. See output above for details.")
    return cp.returncode


if __name__ == "__main__":
    raise SystemExit(main())

