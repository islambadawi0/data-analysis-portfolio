from pathlib import Path
import shutil
import subprocess
import sys

import py7zr

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
COMPETITION = "kkbox-churn-prediction-challenge"
FILES = [
    "train.csv.7z",
    "train_v2.csv.7z",
    "transactions.csv.7z",
    "transactions_v2.csv.7z",
    "members_v3.csv.7z",
]


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    if shutil.which("kaggle") is None:
        sys.exit("Kaggle CLI is not installed. Run `pip install kaggle` and configure your Kaggle API token locally.")
    for filename in FILES:
        csv_file = filename.removesuffix(".7z")
        if not (RAW / csv_file).is_file():
            archive = RAW / filename
            if not archive.is_file():
                print(f"Downloading {filename} ...")
                subprocess.run([
                    "kaggle", "competitions", "download", "-c", COMPETITION,
                    "-f", filename, "-p", str(RAW),
                ], check=True)
            if not archive.is_file():
                sys.exit(f"Expected archive was not downloaded: {archive}. Confirm that you accepted the competition rules and the file name is still current.")
            print(f"Extracting {filename} ...")
            with py7zr.SevenZipFile(archive, mode="r") as bundle:
                bundle.extractall(path=RAW)
    missing = [name.removesuffix(".7z") for name in FILES if not (RAW / name.removesuffix(".7z")).is_file()]
    if missing:
        sys.exit("Missing extracted competition files: " + ", ".join(missing))
    print("Verified the real KKBox competition labels, transactions, and member data.")
    print("Source: https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge/data")
    print("Raw dataset files remain local and are not committed to GitHub.")


if __name__ == "__main__":
    main()
