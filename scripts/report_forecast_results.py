"""Compte rendu reproductible à partir des métriques déjà enregistrées."""

import json

import pandas as pd

from scripts.train_forecast import REPORT_DIR


def metric_table(frame):
    rows = ["| Méthode | MAE (MW) | RMSE (MW) |", "| --- | ---: | ---: |"]
    for row in frame.itertuples():
        rows.append(f"| {row.model} | {row.mae_mw:.2f} | {row.rmse_mw:.2f} |")
    return "\n".join(rows)


def main():
    selection = json.loads((REPORT_DIR / "selection.json").read_text())
    splits = pd.read_csv(REPORT_DIR / "split_counts.csv")
    validation = pd.read_csv(REPORT_DIR / "validation_metrics.csv")
    test = pd.read_csv(REPORT_DIR / "test_metrics.csv")
    selected = selection["selected_model"]
    test_selected = test.set_index("model").loc[selected]
    split_rows = ["| Période | Candidates | Conservées | Frontière | Historique court | Variables absentes | Cibles absentes |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in splits.itertuples():
        split_rows.append(f"| {row.period} | {row.candidates} | {row.kept} | {row.boundary_24h} | "
                          f"{row.insufficient_history} | {row.missing_features} | {row.missing_targets} |")
    baseline_rows = []
    for baseline in ("DailyBaseline", "WeeklyBaseline"):
        baseline_mae = test.set_index("model").loc[baseline, "mae_mw"]
        gain = 100 * (1 - test_selected.mae_mw / baseline_mae)
        baseline_rows.append(f"Écart de MAE par rapport à {baseline} sur le test : {gain:.2f} % "
                             "(positif = amélioration).")
    best_validation = validation.sort_values(["mae_mw", "rmse_mw", "model"]).iloc[0].model
    report = f"""# Résultats Machine Learning, phase 3

## Données et exemples

Le fichier réel OPSD a été vérifié avant modification : 50 401 lignes,
564 mesures manquantes, 21 séquences dont une de 395 heures. La phase 2 donne
46 540 lignes complètes et ses 15 tests initiaux passent.

Les nouveaux exemples sont des origines T avec 24 cibles T+1 à T+24. Ils ne
correspondent donc pas aux lignes complètes du tableau à un horizon de phase 2.
Les exemples sont exclus sur les variables et sur l'ensemble des 24 cibles.
Les raisons ci-dessous sont exclusives, selon la priorité documentée.

{chr(10).join(split_rows)}

Le fichier `split_counts.csv` contient également les premières et dernières dates
d'origine et de cible. Les journaux détaillés, avec drapeaux pouvant se recouper,
sont conservés dans `data/processed/phase3/*_exclusions.csv`.

## Modèles et variables

Ridge, RandomForestRegressor et HistGradientBoostingRegressor ont chacun été
entraînés sur 24 horizons, soit 72 régresseurs au total, uniquement sur 2015-2018.
Les deux baselines utilisent la veille et la semaine précédente à l'heure cible.
Toutes les méthodes sont comparées sur les mêmes origines, sans imputation.

Les 11 variables avant encodage sont le calendrier UTC cible (heure, jour, mois,
weekend), y(T), y(T-24), y(T-168), les moyennes sur [T-23,T] et [T-167,T],
ainsi que y(T+h-24) et y(T+h-168). Aucune variable ne requiert de demande après T.
Ridge dispose d'un encodage du calendrier et d'une standardisation ajustés sur
l'entraînement uniquement. Les paramètres exacts sont dans `training_config.json`.

## Validation 2019

{metric_table(validation)}

Le modèle ML sélectionné est **{selected}**, selon la plus faible MAE en validation.
La méthode la mieux classée en incluant les baselines est {best_validation}.
Une seule configuration par famille a été essayée. Le modèle sélectionné n'a pas
été réentraîné sur 2019. La sélection et l'empreinte du modèle ont été figées avant
l'ouverture du test.

L'écart de MAE entre Random Forest et HistGradientBoosting sur validation est
faible ; HistGradientBoosting obtient le meilleur RMSE de validation. Le choix
de Random Forest respecte la métrique principale annoncée, sans établir une
supériorité générale ou statistiquement démontrée.

## Test final, janvier à juin 2020

{metric_table(test)}

{chr(10).join(baseline_rows)}

Seuls le modèle sélectionné et les deux baselines ont été évalués sur ce test,
une fois dans cette expérience. `test_evaluation_started.json` et
`test_completion.json` consignent l'ouverture et la fin de cette évaluation.
`selection.json` reste la photographie de la sélection avant le test.
Les MAE et RMSE par horizon figurent dans les CSV `*_by_horizon.csv`.

## Graphiques et réutilisation

- `reports/figures/ml_validation_comparison.png` : MAE et RMSE de validation.
- `reports/figures/ml_mae_by_horizon.png` : MAE de validation et du test par horizon.
- `reports/figures/ml_test_forecasts.png` : sept prévisions quotidiennes de 24 heures
  issues des premières origines complètes de janvier à 23 h UTC, choisies selon
  une règle fixée avant de voir les erreurs.
- `reports/figures/ml_test_errors.png` : distribution des erreurs du modèle sélectionné.

Les trois familles de modèles sont sauvegardées dans `models/phase3/`, avec
les 24 régresseurs, le schéma des variables et les métadonnées. Les dépendances
sont fixées dans `requirements.txt`. `scripts.predict_forecast` peut produire
24 prévisions à partir d'un historique qui s'arrête à T, sans cible future.
Les prévisions complètes de validation et de test sont conservées localement
dans `data/processed/phase3/` ; les graphiques les relisent sans nouvel entraînement.

## Limites et difficultés

La comparaison repose sur une seule validation annuelle et une seule configuration
par famille. Le test de janvier-juin 2020 ne représente ni une année entière ni les
conditions récentes ; les résultats ne démontrent pas une performance future stable.
La longue lacune de juillet-août 2020 est hors du test demandé. L'exclusion des
exemples incomplets réduit la couverture et ne mesure pas la robustesse aux lacunes.

Les origines successives se chevauchent : les erreurs ne sont pas indépendantes.
Chaque nouvelle origine reçoit les observations réelles devenues disponibles ;
ce n'est pas une prévision de six mois émise en janvier. On suppose y(T) disponible,
ce qui laisse le délai réel de publication à prendre en compte. Les mesures OPSD
sont historiques : leurs révisions éventuelles n'ont pas été simulées en temps réel.
Les changements d'heure civile, jours fériés et météo ne sont pas modélisés.

L'installation en ligne a échoué sur la résolution DNS. scikit-learn et ses
dépendances ont pu être installés depuis le cache local ; la cohérence des
dépendances est vérifiée. Aucun changement des données source n'a été nécessaire.
Un avertissement joblib sur la détection des cœurs physiques du Mac a entraîné
un repli sur les cœurs logiques, sans interrompre les calculs. Les paramètres
Random Forest limitent le parallélisme à deux tâches et les pools numériques
sont limités à deux threads.

Les tests temporels vérifient l'alignement des 24 horizons, les baselines,
l'invariance des variables lorsqu'on modifie ou retire le futur, les NaN,
les frontières des périodes, la standardisation sur l'entraînement et la sortie
de prédiction après sauvegarde/rechargement. Leur résultat réel est consigné
dans `test_results.txt`.

Aucun dashboard, aucune API et aucune publication GitHub n'ont été réalisés.
Le protocole détaillé et fixé avant entraînement est dans `reports/phase3_protocol.md`.
"""
    (REPORT_DIR / "results.md").write_text(report, encoding="utf-8")
    print(REPORT_DIR / "results.md")


if __name__ == "__main__":
    main()
