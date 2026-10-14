from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
FILE = RAW / "vehicles.csv"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    if not FILE.is_file():
        if shutil.which("kaggle") is None:
            sys.exit("Kaggle CLI is not installed. Run `pip install kaggle`, configure your Kaggle API token locally, then rerun this script.")
        subprocess.run(
            ["kaggle", "datasets", "download", "-d", "austinreese/craigslist-carstrucks-data", "-p", str(RAW), "--unzip"],
            check=True,
        )
    if not FILE.is_file():
        candidates = list(RAW.glob("*.csv"))
        sys.exit("Expected vehicles.csv was not found. Files present: " + ", ".join(p.name for p in candidates))
    print(f"Found real Craigslist listing data: {FILE}")
    print("The source file is large; it is not copied into GitHub. Use only relevant columns in downstream scripts.")


if __name__ == "__main__":
    main()
