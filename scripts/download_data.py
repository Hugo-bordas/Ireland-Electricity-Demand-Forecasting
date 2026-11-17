"""Télécharger la version historique OPSD sans modifier les données."""

import hashlib
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BASE_URL = "https://data.open-power-system-data.org/time_series/2020-10-06"
CSV_NAME = "time_series_60min_singleindex.csv"


def download(filename):
    """Écrire d'abord un fichier temporaire pour éviter les CSV incomplets."""
    destination = RAW / filename
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"Téléchargement : {BASE_URL}/{filename}")
    try:
        with urlopen(f"{BASE_URL}/{filename}", timeout=60) as response:
            with temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    try:
        metadata = json.loads(download("datapackage.json").read_text())
        download("README.md")
        resource = next(item for item in metadata["resources"] if item["path"] == CSV_NAME)
        csv_path = RAW / CSV_NAME
        if not csv_path.exists():
            download(CSV_NAME)
        # OPSD fournit une empreinte SHA-256 dans ses métadonnées.
        digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        if digest != resource["hash"]:
            raise ValueError("Empreinte SHA-256 incorrecte : supprimer le CSV et relancer.")
        print(f"CSV vérifié : {csv_path} ({csv_path.stat().st_size:,} octets)")
    except (URLError, OSError, ValueError, KeyError, StopIteration) as error:
        raise SystemExit(f"Téléchargement impossible : {error}") from error


if __name__ == "__main__":
    main()
