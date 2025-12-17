from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"


def run_py(script_name: str, args: list[str]) -> None:
    script_path = SRC_DIR / script_name
    print(f"Running {script_path} ...")
    cmd = [sys.executable, str(script_path)] + args
    subprocess.run(cmd, check=True)


def main() -> int:
    main_args = ["--days", "1", "--nights", "1", "--adults", "2,4", "--max-hotels", "20"]
    run_py("main.py", main_args)
    run_py("filter_leads.py", [])
    print("Done. Check data/amadeus_rates.csv and data/leads.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())