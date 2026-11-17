"""Explorer la demande électrique irlandaise horaire, sans imputation."""

import os
from datetime import timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# Garder le cache matplotlib dans le projet, y compris en environnement restreint.
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))

import matplotlib

matplotlib.use("Agg")  # Enregistrer un PNG sans ouvrir de fenêtre graphique.
import matplotlib.pyplot as plt
import pandas as pd


IRISH_CSV = ROOT / "data" / "irish" / "irish_demand_hourly.csv"
CSV_PATH = IRISH_CSV if IRISH_CSV.is_file() else ROOT / "data" / "raw" / "time_series_60min_singleindex.csv"
LOAD_COLUMN = "IE_load_actual_entsoe_transparency"


def load_data(path):
    """Charger uniquement la date UTC et la demande réelle en MW."""
    frame = pd.read_csv(path, usecols=["utc_timestamp", LOAD_COLUMN])
    frame["utc_timestamp"] = pd.to_datetime(frame["utc_timestamp"], utc=True)
    if frame["utc_timestamp"].isna().any():
        raise ValueError("Des horodatages sont manquants.")
    if frame["utc_timestamp"].duplicated().any():
        raise ValueError("Des horodatages sont dupliqués.")
    if frame.empty:
        raise ValueError("Le CSV ne contient aucune ligne.")
    return frame.set_index("utc_timestamp").sort_index()


def summarize(frame):
    load = frame[LOAD_COLUMN]
    valid = load.dropna()
    if valid.empty:
        raise ValueError("Aucune valeur de demande disponible pour l'Irlande.")
    expected = pd.date_range(frame.index.min(), frame.index.max(), freq="h")
    absent_hours = len(expected.difference(frame.index))
    if not frame.index.isin(expected).all():
        raise ValueError("Des horodatages ne suivent pas la grille horaire UTC.")
    inside = load.loc[valid.index.min():valid.index.max()]
    return "\n".join([
        "Exploration OPSD : demande réelle en Irlande (MW)",
        "Version source : 2020-10-06 ; heures en UTC (début d'intervalle).",
        f"Période du fichier : {frame.index.min()} → {frame.index.max()}",
        f"Période avec demande disponible : {valid.index.min()} → {valid.index.max()}",
        f"Nombre de lignes : {len(frame)}",
        f"Demandes renseignées : {valid.size}",
        f"Demandes manquantes : {load.isna().sum()} ({load.isna().mean():.2%})",
        f"Valeurs manquantes entre première et dernière demande : {inside.isna().sum()}",
        f"Heures absentes de l'index du fichier : {absent_hours}",
        f"Valeurs nulles ou négatives à examiner : {(valid <= 0).sum()}",
        "\nStatistiques descriptives (valeurs renseignées, MW) :",
        valid.describe().to_string(),
        "\nAucune valeur manquante n'a été remplacée.",
    ])


def plot_demand(frame, destination):
    """Afficher les variations horaires sur les sept premiers jours renseignés."""
    load = frame[LOAD_COLUMN]
    start = load.first_valid_index()
    week = load.loc[(load.index >= start) & (load.index < start + timedelta(days=7))]
    # Les heures absentes restent des trous dans la courbe.
    week = week.reindex(pd.date_range(start, periods=168, freq="h"))
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(week.index, week, linewidth=1)
    ax.set(title="Demande électrique en Irlande — première semaine disponible",
           xlabel="Date (UTC)", ylabel="Demande (MW)")
    ax.grid(alpha=0.3)
    fig.text(0.01, 0.01, "Source : OPSD 2020-10-06 / ENTSO-E Transparency", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(destination, dpi=150)
    plt.close(fig)


def main():
    if not CSV_PATH.exists():
        raise SystemExit("CSV absent. Exécuter d'abord : python scripts/download_data.py")
    try:
        frame = load_data(CSV_PATH)
        summary = summarize(frame)
        reports = ROOT / "reports"
        figures = reports / "figures"
        figures.mkdir(parents=True, exist_ok=True)
        plot_demand(frame, figures / "irish_demand.png")
        (reports / "exploration.txt").write_text(summary + "\n", encoding="utf-8")
        print(summary)
        print(f"\nGraphique : {figures / 'irish_demand.png'}")
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Exploration impossible : {error}") from error


if __name__ == "__main__":
    main()
