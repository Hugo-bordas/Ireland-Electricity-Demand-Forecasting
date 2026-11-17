"""Créer la table de variables ; lancer avec python -m scripts.prepare_data."""

from scripts.explore_data import CSV_PATH, LOAD_COLUMN, ROOT, load_data
from scripts.preprocessing import prepare_features


def main():
    frame = load_data(CSV_PATH).rename(columns={LOAD_COLUMN: "demand_mw"})
    prepared = prepare_features(frame)
    destination = ROOT / "data" / "processed"
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "irish_demand_features.csv"
    prepared.to_csv(path, index_label="utc_timestamp")
    complete = prepared.notna().all(axis=1)
    summary = "\n".join([
        "Préparation : horizon de 1 heure, timestamps cibles en UTC.",
        f"Lignes conservées : {len(prepared)}",
        f"Cibles manquantes : {prepared['demand_mw'].isna().sum()}",
        f"Lignes avec cible et toutes les variables renseignées : {complete.sum()}",
        "Aucune imputation ; aucune ligne supprimée.",
        "Les variables retardées et glissantes utilisent au plus la demande à t-1.",
        "\nValeurs manquantes par colonne :",
        prepared.isna().sum().to_string(),
    ])
    (ROOT / "reports" / "preparation.txt").write_text(summary + "\n", encoding="utf-8")
    print(summary)
    print(f"\nTable : {path}")


if __name__ == "__main__":
    main()
