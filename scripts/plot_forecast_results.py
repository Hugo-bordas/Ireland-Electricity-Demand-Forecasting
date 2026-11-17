"""Graphiques depuis les prévisions sauvegardées, sans réévaluer le test."""

import json

import pandas as pd

from scripts.explore_data import ROOT, plt
from scripts.train_forecast import PREDICTION_DIR, REPORT_DIR


FIGURES = ROOT / "reports" / "figures"
COLORS = {"DailyBaseline": "#929da5", "WeeklyBaseline": "#477cbd", "Ridge": "#b47b27",
          "RandomForest": "#2b7d78", "HistGradientBoosting": "#8663ab"}


def save(fig, filename):
    fig.text(0.01, 0.01, "OPSD / ENTSO-E Transparency. Origines et cibles en UTC.", fontsize=8)
    fig.tight_layout(rect=(0, 0.045, 1, 0.96))
    fig.savefig(FIGURES / filename, dpi=160)
    plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    selection = json.loads((REPORT_DIR / "selection.json").read_text())
    selected = selection["selected_model"]
    validation = pd.read_csv(REPORT_DIR / "validation_metrics.csv").sort_values("mae_mw")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, metric, label in zip(axes, ["mae_mw", "rmse_mw"], ["MAE", "RMSE"]):
        colors = ["#2b7d78" if name == selected else "#8797a5" for name in validation.model]
        bars = ax.barh(validation.model, validation[metric], color=colors)
        ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=9)
        ax.set_xlim(0, validation[metric].max() * 1.13)
        ax.invert_yaxis()
        ax.set(xlabel=f"{label} (MW)", title=f"Validation 2019 : {label}")
        ax.grid(axis="x", alpha=0.25)
    save(fig, "ml_validation_comparison.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, period, title in zip(axes, ["validation", "test"],
                                ["Validation 2019", "Test final janvier-juin 2020"]):
        by_horizon = pd.read_csv(REPORT_DIR / f"{period}_by_horizon.csv")
        for name, values in by_horizon.groupby("model", sort=False):
            ax.plot(values.horizon, values.mae_mw, label=name,
                    color=COLORS[name],
                    linewidth=2 if name == selected else 1.2)
        ax.set(xlabel="Horizon (heures après T)", title=title, xticks=[1, 6, 12, 18, 24])
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("MAE (MW)")
    save(fig, "ml_mae_by_horizon.png")

    predictions = pd.read_csv(PREDICTION_DIR / "test_predictions.csv",
                              parse_dates=["origin_utc", "target_utc"])
    origins = pd.DatetimeIndex(predictions.origin_utc.unique())
    # Règle fixée dans phase3_protocol.md avant le test, indépendante des erreurs.
    daily_origins = origins[(origins.hour == 23) & (origins.month == 1)][:7]
    week = predictions[predictions.origin_utc.isin(daily_origins)].sort_values("target_utc")
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(week.target_utc, week.observed_mw, label="Demande observée", color="#243746")
    ax.plot(week.target_utc, week[selected], label=f"Prévision {selected}", color=COLORS[selected])
    ax.plot(week.target_utc, week.DailyBaseline, label="Baseline veille", color=COLORS["DailyBaseline"],
            alpha=0.8, linewidth=1)
    ax.set(xlabel="Heure cible (UTC)", ylabel="Demande (MW)",
           title="Test : sept prévisions de 24 h émises à 23 h UTC, premières dates complètes de janvier")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    save(fig, "ml_test_forecasts.png")

    errors = predictions[selected] - predictions.observed_mw
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(errors, bins=60, color="#497c92", edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="#243746", linewidth=1)
    ax.set(xlabel="Erreur : prévision − observation (MW)", ylabel="Nombre de paires (origine, horizon)",
           title=f"Test final : distribution des erreurs de {selected}\n"
                 "24 horizons, origines horaires qui se chevauchent")
    save(fig, "ml_test_errors.png")
    print("Quatre graphiques sauvegardés dans reports/figures/.")


if __name__ == "__main__":
    main()
