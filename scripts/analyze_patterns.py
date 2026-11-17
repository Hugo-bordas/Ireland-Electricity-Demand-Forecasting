"""Analyser les lacunes et le calendrier : python -m scripts.analyze_patterns."""

import pandas as pd

# Cet import configure aussi le backend matplotlib et son cache local.
from scripts.explore_data import CSV_PATH, LOAD_COLUMN, ROOT, load_data, plt
from scripts.preprocessing import validate_hourly_index


def missing_runs(load):
    """Une séquence contient des heures manquantes consécutives, bornes incluses."""
    validate_hourly_index(load.to_frame())
    missing = load.isna()
    groups = missing.ne(missing.shift()).cumsum()
    rows = []
    for _, run in load[missing].groupby(groups[missing]):
        rows.append({
            "start_utc": run.index.min(),
            "end_utc": run.index.max(),
            "hours": len(run),
            "at_boundary": run.index.min() == load.index.min()
                           or run.index.max() == load.index.max(),
        })
    return pd.DataFrame(rows, columns=["start_utc", "end_utc", "hours", "at_boundary"])


def demand_profile(load, groups):
    """Moyennes observées et effectifs, sans remplir les NaN."""
    result = load.groupby(groups).agg(["size", "count", "mean", "median", "std"])
    result = result.rename(columns={"size": "hours", "count": "observed",
                                    "mean": "mean_mw", "median": "median_mw", "std": "std_mw"})
    result["missing"] = result["hours"] - result["observed"]
    result["missing_pct"] = 100 * result["missing"] / result["hours"]
    return result


def save_figure(fig, path):
    fig.text(0.01, 0.01, "Source : OPSD 2020-10-06 / ENTSO-E Transparency. Calendrier UTC.",
             fontsize=8)
    fig.tight_layout(rect=(0, 0.045, 1, 0.94))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_profiles(profiles, destination):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    settings = [
        ("hour", "Heure de la journée (UTC)", list(range(0, 24, 3)), None),
        ("weekday", "Jour de la semaine (UTC)", list(range(7)),
         ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]),
        ("month", "Mois", list(range(1, 13)),
         ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]),
        ("year", "Année (2020 : janvier à septembre)", list(range(2015, 2021)), None),
    ]
    for ax, (name, label, ticks, ticklabels) in zip(axes.flat, settings):
        profile = profiles[name].dropna(subset=["mean_mw"])
        ax.plot(profile.index, profile["mean_mw"], marker="o", markersize=3)
        ax.set(xlabel=label, ylabel="Demande moyenne observée (MW)")
        ax.set_xticks(ticks)
        if ticklabels:
            ax.set_xticklabels(ticklabels)
        ax.grid(alpha=0.3)
    fig.suptitle("Profils moyens de demande, 2015 à septembre 2020\n"
                 "Valeurs renseignées uniquement ; effectifs disponibles dans les CSV", fontsize=12)
    save_figure(fig, destination)


def plot_missing(monthly, runs, destination):
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    positions = list(range(len(monthly)))
    axes[0].bar(positions, monthly["missing_pct"], color="#b35035")
    ticks = positions[::6]
    axes[0].set_xticks(ticks, monthly.index.strftime("%Y-%m")[::6], rotation=40, ha="right")
    axes[0].set(ylabel="Mesures manquantes (%)", title="Lacunes par mois (mois UTC du fichier)")
    axes[0].text(0.01, 0.92, "Déc. 2014 : une seule ligne, manquante (100 %)",
                 transform=axes[0].transAxes, fontsize=9)
    axes[1].bar(range(1, len(runs) + 1), runs["hours"], color="#416b8c")
    axes[1].set(xlabel="Séquence manquante, par ordre chronologique",
                ylabel="Durée (heures)", xticks=range(1, len(runs) + 1))
    axes[1].set_title("Durée des séquences consécutives ; dates dans missing_runs.csv")
    for ax in axes:
        ax.grid(axis="y", alpha=0.3)
    save_figure(fig, destination)


def plot_monthly_trends(load, destination):
    # Une courbe par année permet de comparer les mêmes mois entre années.
    means = load.resample("MS").mean().dropna()
    fig, ax = plt.subplots(figsize=(11, 5))
    for year, values in means.groupby(means.index.year):
        ax.plot(values.index.month, values, marker="o", markersize=3, label=str(year))
    ax.set(xlabel="Mois (UTC)", ylabel="Demande moyenne observée (MW)",
           xticks=range(1, 13), title="Moyennes mensuelles par année ; 2020 s'arrête en septembre")
    ax.grid(alpha=0.3)
    ax.legend(title="Année", ncols=3)
    save_figure(fig, destination)


def main():
    frame = load_data(CSV_PATH)
    validate_hourly_index(frame)
    load = frame[LOAD_COLUMN]
    reports = ROOT / "reports"
    tables = reports / "tables"
    figures = reports / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    runs = missing_runs(load)
    runs.to_csv(tables / "missing_runs.csv", index=False)
    profiles = {}
    groups = {"hour": load.index.hour, "weekday": load.index.dayofweek,
              "month": load.index.month, "year": load.index.year}
    for name, group in groups.items():
        profiles[name] = demand_profile(load, group)
        profiles[name].index.name = name
        profiles[name].to_csv(tables / f"profile_{name}.csv")
    monthly = demand_profile(load, pd.Grouper(freq="MS"))
    monthly.to_csv(tables / "monthly_summary.csv")
    plot_profiles(profiles, figures / "calendar_profiles.png")
    plot_missing(monthly, runs, figures / "missing_values.png")
    plot_monthly_trends(load, figures / "monthly_trends.png")

    longest = runs.sort_values("hours", ascending=False).iloc[0]
    missing_total = int(load.isna().sum())
    lines = [
        "Analyse de la demande irlandaise, calendrier UTC",
        f"Lignes : {len(load)} ; mesures renseignées : {load.count()}.",
        f"Valeurs manquantes : {missing_total} ({100 * load.isna().mean():.2f} %).",
        f"Séquences manquantes : {len(runs)} ; aux bornes : {runs['at_boundary'].sum()}.",
        f"Plus longue séquence : {longest['start_utc']} à {longest['end_utc']} inclus, "
        f"{longest['hours']} heures ({100 * longest['hours'] / missing_total:.2f} % des lacunes).",
        "\nRépartition annuelle (2014 ne contient qu'une heure, manquante) :",
        profiles["year"].to_string(float_format=lambda value: f"{value:.2f}"),
        "\nMois comportant des lacunes :",
        monthly.loc[monthly["missing"] > 0, ["hours", "observed", "missing", "missing_pct"]]
               .to_string(float_format=lambda value: f"{value:.2f}"),
    ]
    for name in ("hour", "weekday", "month"):
        profile = profiles[name]["mean_mw"]
        lines.append(f"\nProfil {name} : minimum moyen au groupe {profile.idxmin()} "
                     f"({profile.min():.2f} MW), maximum au groupe {profile.idxmax()} "
                     f"({profile.max():.2f} MW).")
    weekend = load.groupby(load.index.dayofweek >= 5).mean()
    lines.extend([
        f"\nMoyenne lundi-vendredi : {weekend.loc[False]:.2f} MW ; "
        f"weekend : {weekend.loc[True]:.2f} MW.",
        "\nLes moyennes excluent les valeurs manquantes. Aucune imputation.",
        "2020 est incomplète : les moyennes annuelles ne couvrent pas les mêmes mois.",
        "Ces profils sont descriptifs ; ils ne démontrent aucune cause des variations ou lacunes.",
        "Les agrégats de tout le jeu servent à l'exploration, pas de variables pour un modèle.",
    ])
    report = "\n".join(lines)
    (reports / "patterns.txt").write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
