"""Historical energy analytics. Run: python -m streamlit run dashboard/app.py"""

import logging
import sys
from importlib import reload
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from dashboard import data as dashboard_data

# A running Streamlit session can retain the module imported before a code update.
# Refresh it only when its public interface is incomplete; never load or fit a model.
_DATA_EXPORTS = ("LABELS", "MODEL", "forecast_table", "load_results", "representative_origin", "select_forecast")
if any(not hasattr(dashboard_data, name) for name in _DATA_EXPORTS):
    reload(dashboard_data)

from dashboard.data import LABELS, MODEL, forecast_table, load_results, representative_origin, select_forecast


st.set_page_config(page_title="Irish Energy Forecast AI", layout="wide")
NAVY, TEAL, BLUE, CORAL = "#172B4D", "#128C80", "#3979C6", "#E87C67"
COLORS = {"Observed": NAVY, "Random Forest": TEAL, "Previous day": "#74849A",
          "Previous week": BLUE, "Ridge": "#A84C3E", "HistGradientBoosting": NAVY}
SECTIONS = ["Overview", "Forecast Explorer", "Model Performance", "Methodology"]
logger = logging.getLogger(__name__)


@st.cache_data(ttl=60, show_spinner="Loading historical results…")
def cached_results():
    return load_results(ROOT)


def metric_cards(items, key):
    """Keep native metrics; scoped container queries enforce a 4 / 2 / 1 layout."""
    with st.container(key="kpi_layout"):
        grid = st.grid(4, min_column_width=160, gap="small", key=key)
        for label, value, help_text in items:
            grid.metric(label, value, help=help_text, border=True)


def color_encoding(field, names):
    return alt.Color(field, scale=alt.Scale(domain=names, range=[COLORS[n] for n in names]),
                     legend=alt.Legend(title=None, orient="bottom", labelColor=NAVY))


def chart_style(chart):
    return chart.configure_view(stroke=None).configure_axis(
        labelColor=NAVY, titleColor=NAVY, gridColor="#E0E7EF", labelFontSize=12,
        titleFontSize=12, titlePadding=12, domain=False, tickColor="#D4DFEA",
    )


def workflow():
    st.subheader("From public data to a 24-hour forecast")
    st.html("""<div class="workflow-layout"><ol class="workflow" aria-label="Machine learning workflow">
      <li><span>01 · DATA</span><strong>Hourly OPSD demand</strong><p>Historical observations in UTC</p></li>
      <li><span>02 · PREPARE</span><strong>Past demand + calendar</strong><p>Complete examples; no imputation</p></li>
      <li><span>03 · TRAIN</span><strong>24 direct regressors</strong><p>Training origins from 2015–2018</p></li>
      <li><span>04 · SELECT</span><strong>Validation in 2019</strong><p>Choose using validation MAE</p></li>
      <li><span>05 · INSPECT</span><strong>Saved test forecasts</strong><p>January–June 2020, held out</p></li>
    </ol></div>""")
    st.caption("The diagram describes the completed experiment. This dashboard only reads its saved results.")


def overview(data):
    st.header("Overview")
    st.write("A 24-hour demand forecast for Ireland, built from public electricity data and evaluated chronologically.")
    score = data["test_metrics"].set_index("model").loc[MODEL]
    metric_cards([
        ("Test MAE", f"{score.mae_mw:.2f} MW", "Mean absolute error across all saved test origins and horizons."),
        ("Test RMSE", f"{score.rmse_mw:.2f} MW", "Root mean squared error; larger misses receive more weight."),
        ("Forecast horizon", "24 hours", "24 independent predictions issued from one origin."),
        ("Test forecast origins", f"{data['completion']['n_origins']:,}", "Complete historical origins retained for the test."),
    ], "overview_kpis")
    st.caption("Final historical test · January–June 2020 · Lower error is better")
    left, right = st.columns(2, gap="medium")
    with left, st.container(border=True):
        st.subheader("The data")
        st.write("Hourly demand from January 2015 to September 2020. Open Power System Data, based on ENTSO-E Transparency.")
        st.markdown("[Explore the OPSD source](https://data.open-power-system-data.org/time_series/2020-10-06)")
        with st.expander("Coverage and missing values"):
            st.write("The source contains 50,401 hourly rows and 564 missing demand values. Examples with incomplete inputs "
                     "or any missing target were excluded without automatic imputation.")
    with right, st.container(border=True):
        st.subheader("The model")
        st.write("Random Forest, with one independent regressor for each of the next 24 hours.")
        st.write("Selected on validation MAE in 2019, before opening the final test.")
        with st.expander("Why this model?"):
            st.write("It achieved the lowest validation MAE among the three ML approaches. HistGradientBoosting had a "
                     "slightly better validation RMSE. Selection followed the metric defined before evaluation.")
    workflow()
    with st.expander("Chronological split and retained examples"):
        splits = data["splits"][["period", "candidates", "kept"]].copy()
        splits["Period"] = splits.period.map({"train": "Training · 2015–2018", "validation": "Validation · 2019",
                                             "test": "Test · Jan–Jun 2020"})
        splits["Excluded"] = splits.candidates - splits.kept
        st.dataframe(splits.rename(columns={"candidates": "Candidate origins", "kept": "Retained origins"})[
            ["Period", "Candidate origins", "Retained origins", "Excluded"]], hide_index=True, width="stretch")


def forecast_chart(forecast, include_baseline):
    """Style the original saved values; wide tooltips show both series at one target hour."""
    names = {"observed_mw": "Observed", MODEL: "Random Forest"}
    if include_baseline:
        names["DailyBaseline"] = "Previous day"
    wide = forecast.copy()
    wide["Target (UTC)"] = wide.target_utc.dt.strftime("%d %b %Y, %H:%M UTC")
    wide["Origin (UTC)"] = wide.origin_utc.dt.strftime("%d %b %Y, %H:%M UTC")
    long = wide.rename(columns=names).melt(id_vars=["target_utc", "horizon"],
        value_vars=list(names.values()), var_name="Series", value_name="Demand (MW)")
    x = alt.X("target_utc:T", title="Target date and time (UTC)", scale=alt.Scale(type="utc"),
              axis=alt.Axis(format="%d %b %H:%M", labelAngle=-25, tickCount=6, labelOverlap=True))
    hover = alt.selection_point(fields=["target_utc"], nearest=True, on="pointerover", empty=False)
    lines = alt.Chart(long).mark_line(strokeWidth=2.5).encode(
        x=x, y=alt.Y("Demand (MW):Q", scale=alt.Scale(zero=False)),
        color=color_encoding("Series:N", list(names.values())),
        strokeDash=alt.StrokeDash("Series:N", legend=None,
            scale=alt.Scale(domain=list(names.values()), range=[[1, 0], [7, 4]] + ([[3, 3]] if include_baseline else []))),
    )
    hit = alt.Chart(wide).mark_point(opacity=0, size=100).encode(
        x=x, y=alt.Y("observed_mw:Q", title="Demand (MW)")
    ).add_params(hover)
    tooltips = [alt.Tooltip("Target (UTC):N"), alt.Tooltip("Origin (UTC):N"),
                alt.Tooltip("horizon:Q", title="Horizon (h)"),
                alt.Tooltip("observed_mw:Q", title="Observed (MW)", format=".2f"),
                alt.Tooltip(f"{MODEL}:Q", title="Predicted (MW)", format=".2f"),
                alt.Tooltip("absolute_error_mw:Q", title="Absolute error (MW)", format=".2f")]
    rule = alt.Chart(wide).mark_rule(color=BLUE, strokeWidth=1, opacity=0.6).encode(
        x=x, tooltip=tooltips).transform_filter(hover)
    return chart_style(alt.layer(lines, hit, rule).properties(height=350))


def explorer(data):
    st.header("Forecast Explorer")
    st.write("Inspect any complete 24-hour forecast from the historical test. No predictions are generated live.")
    predictions = data["predictions"]
    origins = pd.DatetimeIndex(predictions.origin_utc.unique()).sort_values()
    days = sorted(set(origins.date))
    default_origin = representative_origin(predictions)
    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            day = st.selectbox("Forecast origin date (UTC)", days, index=days.index(default_origin.date()),
                               format_func=lambda d: d.strftime("%d %B %Y"), key="origin_date")
        with right:
            available = origins[origins.date == day]
            hours = available.hour.tolist()
            hour = st.selectbox("Forecast origin time (UTC)", hours,
                index=hours.index(default_origin.hour) if default_origin.hour in hours else 0,
                format_func=lambda h: f"{h:02d}:00 UTC", key="origin_hour")
            origin = available[available.hour == hour][0]
        st.caption(f"{len(origins):,} complete origins available, including high-error forecasts.")
    forecast = select_forecast(predictions, origin)
    global_mae = data["test_metrics"].set_index("model").loc[MODEL, "mae_mw"]
    metric_cards([
        ("MAE · selected 24 hours", f"{forecast.absolute_error_mw.mean():.2f} MW", "Only the 24 target hours selected above."),
        ("Largest absolute error", f"{forecast.absolute_error_mw.max():.2f} MW", "Largest miss within this forecast."),
        ("Overall test MAE", f"{global_mae:.2f} MW", "All retained test origins and all 24 horizons; unchanged by this selection."),
        ("Predicted hours", str(len(forecast)), "Every saved forecast includes horizons 1 through 24."),
    ], "forecast_kpis")
    st.caption("Selected MAE covers only these 24 hours. Overall test MAE covers the full historical evaluation.")
    st.subheader("Observed vs predicted demand")
    st.caption(f"Origin: {origin:%d %b %Y, %H:%M} UTC · Targets: "
               f"{forecast.target_utc.min():%d %b %H:%M} to {forecast.target_utc.max():%d %b %H:%M} UTC")
    baseline = st.checkbox("Show previous-day baseline", value=False)
    st.altair_chart(forecast_chart(forecast, baseline), width="stretch")
    st.caption("Solid navy: observed demand. Dashed teal: Random Forest. Hover near a target hour to compare values.")
    table = forecast_table(forecast)
    st.download_button("Download this forecast (CSV)", table.to_csv(index=False).encode("utf-8"),
                       file_name=f"irish_forecast_{origin:%Y%m%d_%H%M}_UTC.csv", mime="text/csv")
    with st.expander("Hourly values and errors"):
        st.caption("Signed error = prediction − observation. The CSV contains these same rows and columns, without rounding.")
        st.dataframe(table, hide_index=True, width="stretch")
    with st.expander("How the initial example is chosen"):
        st.write(f"The initial origin is {default_origin:%d %b %Y, %H:%M} UTC. Its 24-hour MAE is closest to the "
                 "median MAE across saved origins; chronological order breaks ties. This only sets the opening example. "
                 "All forecasts, including poor ones, remain available and no evaluation score is changed.")


def performance(data):
    st.header("Model Performance")
    st.write("Models were selected on 2019 validation data. The final test was evaluated after selection.")
    items = []
    for period in ("validation", "test"):
        row = data[f"{period}_metrics"].set_index("model").loc[MODEL]
        for metric, label in [("mae_mw", "MAE"), ("rmse_mw", "RMSE")]:
            items.append((f"{period.title()} {label}", f"{row[metric]:.2f} MW", "Recorded Random Forest performance."))
    metric_cards(items, "performance_kpis")
    period = st.radio("Evaluation period", ["Validation · 2019", "Test · Jan–Jun 2020"],
                      horizontal=True, index=1, key="evaluation_period")
    key = "validation" if period.startswith("Validation") else "test"
    metrics = data[f"{key}_metrics"].copy()
    metrics["Method"] = metrics.model.map(LABELS)
    st.subheader("Model comparison")
    st.caption(f"{period} · MAE in MW · Lower is better · Same origins for every method")
    base = alt.Chart(metrics).encode(
        y=alt.Y("Method:N", sort=alt.SortField(field="mae_mw", order="ascending"), title=None))
    bars = base.mark_bar(cornerRadiusEnd=4, size=26).encode(
        x=alt.X("mae_mw:Q", title="Mean absolute error (MW)",
                scale=alt.Scale(domain=[0, float(metrics.mae_mw.max()) * 1.2])),
        color=alt.condition(alt.datum.model == MODEL, alt.value(TEAL), alt.value(BLUE)),
        tooltip=["Method:N", alt.Tooltip("mae_mw:Q", title="MAE (MW)", format=".2f"),
                 alt.Tooltip("rmse_mw:Q", title="RMSE (MW)", format=".2f")])
    labels = base.mark_text(align="left", dx=7, color=NAVY, fontSize=12).encode(
        x="mae_mw:Q", text=alt.Text("mae_mw:Q", format=".2f"))
    st.altair_chart(chart_style((bars + labels).properties(height=55 * len(metrics))), width="stretch")
    with st.expander("Exact MAE and RMSE values"):
        st.dataframe(metrics[["Method", "mae_mw", "rmse_mw"]].rename(
            columns={"mae_mw": "MAE (MW)", "rmse_mw": "RMSE (MW)"}).round(2), hide_index=True, width="stretch")
    st.subheader("Error by forecast horizon")
    horizons = data[f"{key}_horizons"].copy()
    horizons["Method"] = horizons.model.map(LABELS)
    names = horizons.Method.unique().tolist()
    chart = alt.Chart(horizons).mark_line(strokeWidth=2.2).encode(
        x=alt.X("horizon:Q", title="Hours after origin T", axis=alt.Axis(values=[1, 6, 12, 18, 24])),
        y=alt.Y("mae_mw:Q", title="Mean absolute error (MW)"), color=color_encoding("Method:N", names),
        tooltip=["Method:N", "horizon:Q", alt.Tooltip("mae_mw:Q", title="MAE (MW)", format=".2f")],
    ).properties(height=300)
    st.altair_chart(chart_style(chart), width="stretch")
    with st.expander("How to interpret these results"):
        st.write("MAE is the average absolute error. RMSE gives more weight to large errors. Random Forest was chosen "
                 "for the lowest validation MAE; HistGradientBoosting had a slightly better validation RMSE. "
                 "Only the selected model and the two baselines were evaluated on the final test. "
                 "Hourly origins overlap, so errors are correlated.")


def methodology(data):
    st.header("Methodology")
    st.write("A direct multi-horizon experiment with chronological separation and inputs available at the forecast origin.")
    workflow()
    with st.expander("Features and the 24-hour strategy", expanded=True):
        st.write("At origin T, one regressor predicts T+1, another predicts T+2, and so on to T+24. "
                 "Predictions are never fed into the next model. Each new origin receives the measurements available by then.")
        st.dataframe(pd.DataFrame({"Feature group": ["Target calendar", "Recent observations", "Rolling averages", "Seasonal references"],
            "Definition": ["UTC hour, weekday, month and weekend at T+h", "Demand at T, T−24 and T−168 hours",
                           "24 and 168 complete hours, ending at T", "Demand at T+h−24 and T+h−168; both at or before T"]}),
            hide_index=True, width="stretch")
        st.write("For horizon 24, the previous-day reference is demand at T. Targets are kept separate from inputs. "
                 "No future observation fills a missing feature.")
    with st.expander("Chronological split and model selection"):
        st.write("Training: 2015–2018. Validation: 2019. Test: January–June 2020. The last 24 origins of each period "
                 "are excluded to keep all targets inside the period. Incomplete examples are excluded without "
                 "imputation. Ridge preprocessing is fitted on training only.")
        st.write("Hyperparameters were fixed before evaluation. Random Forest was selected on validation MAE and "
                 "was not retrained on 2019 before the final test.")
    st.warning("Historical evaluation only. These results do not guarantee performance on recent electricity demand.")
    with st.expander("Data availability and other limitations"):
        st.markdown("""
- Demand at T is assumed to have been received. OPSD timestamps mark the start of an interval; real publication delays must be accounted for in a live service.
- Scores cover complete examples. The system does not fill missing observations or provide prediction intervals.
- One annual validation and one configuration per model were used. Small score differences do not establish a statistically reliable ranking.
- Weather, Irish public holidays and local daylight-saving time are not included. Historical measurements may also have been revised after publication.
""")
    st.caption("Source: OPSD Time series 2020-10-06 / ENTSO-E Transparency. No training or final evaluation runs in this dashboard.")


def main():
    st.html("""<style>
      /* Leave room for Streamlit's overlaid toolbar, including on small screens. */
      .stMainBlockContainer { max-width: 1480px; padding-top: 4.5rem; padding-bottom: 2rem; }
      [data-testid="stHeadingWithActionElements"] h1 { font-size: clamp(1.65rem, 2.4vw, 2rem); line-height: 1.3; padding-bottom: .4rem; }
      [data-testid="stHeadingWithActionElements"] h2 { font-size: 1.45rem; }
      [data-testid="stHeadingWithActionElements"] h3 { font-size: 1.1rem; }
      [data-testid="stVerticalBlock"] { gap: .85rem; }
      [data-testid="stMetric"] { background: #fff; border-color: #D9E3ED; border-radius: 12px; }
      [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { white-space: normal; overflow: visible; }
      .st-key-kpi_layout, .workflow-layout { container-type: inline-size; }
      .st-key-kpi_layout .stGrid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      @container (max-width: 759px) {
        .st-key-kpi_layout .stGrid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @container (max-width: 419px) {
        .st-key-kpi_layout .stGrid { grid-template-columns: minmax(0, 1fr); }
      }
      .workflow { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); grid-auto-rows: 1fr; gap: .7rem; padding: 0; margin: .3rem 0; list-style: none; }
      @container (max-width: 719px) {
        .workflow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .workflow li:last-child { grid-column: 1 / -1; }
      }
      @container (max-width: 419px) {
        .workflow { grid-template-columns: minmax(0, 1fr); }
      }
      .workflow li { background: #fff; border: 1px solid #D9E3ED; border-top: 3px solid #128C80; border-radius: 8px; padding: 1rem; color: #172B4D; }
      .workflow span { display: block; color: #172B4D; font-size: .72rem; font-weight: 650; margin-bottom: .6rem; }
      .workflow li:last-child { border-top-color: #E87C67; }
      [data-testid="stMarkdownContainer"] a { color: #172B4D; text-decoration: underline; }
      .workflow strong { font-size: .9rem; }
      .workflow p { font-size: .8rem; line-height: 1.45; margin: .4rem 0 0; }
    </style>""")
    st.title("Irish Energy Forecast AI")
    st.write("Machine Learning for Hourly Electricity Demand Forecasting")
    st.caption("IRELAND · HISTORICAL STUDY · 24-HOUR HORIZON · UTC")
    with st.sidebar:
        st.subheader("Energy Analytics")
        st.caption("Irish Energy Forecast AI")
        st.divider()
        section = st.radio("Navigation", SECTIONS, label_visibility="collapsed", key="navigation")
        st.divider()
        st.write("Random Forest")
        st.caption("Historical test\n\nJanuary–June 2020\n\nSaved forecasts only")
        st.divider()
        st.caption("Supported by EirGrid Group Data.")
        st.caption("Source: OPSD 2020-10-06 / ENTSO-E Transparency. No endorsement implied.")
    try:
        data = cached_results()
        {SECTIONS[0]: overview, SECTIONS[1]: explorer, SECTIONS[2]: performance,
         SECTIONS[3]: methodology}[section](data)
    except (OSError, ValueError, KeyError, TypeError):
        logger.exception("Historical dashboard artifacts could not be displayed")
        st.error("Historical results are temporarily unavailable. Please try again later.")
        st.info("The app requires its saved forecast and metric files. No model has been trained or evaluated.")
        st.stop()


if __name__ == "__main__":
    main()
