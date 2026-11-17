# Third-party software and data

## Original code

The MIT license in `LICENSE` applies to original project code. No third-party
source tree or binary wheel is vendored in the publication candidate. Dependencies
are installed separately and retain their own copyright and license notices.

## Python dependencies

The following are the principal licenses recorded in the installed distributions
during the audit. This is an acknowledgement, not a replacement for each package's
full notices. Binary wheels can bundle other components and licenses, particularly
NumPy/SciPy numerical libraries. If distributing an environment or binary bundle
later, preserve all bundled notices rather than relying on this summary.

| Package | Principal license / notices | Upstream |
| --- | --- | --- |
| NumPy | BSD-3-Clause plus bundled 0BSD, MIT, Zlib and CC0 notices | https://numpy.org/doc/stable/license.html |
| pandas | BSD-3-Clause | https://github.com/pandas-dev/pandas/blob/main/LICENSE |
| SciPy | BSD-3-Clause and bundled library notices | https://github.com/scipy/scipy/blob/main/LICENSE.txt |
| scikit-learn | BSD-3-Clause | https://github.com/scikit-learn/scikit-learn/blob/main/COPYING |
| matplotlib | PSF-based license | https://matplotlib.org/stable/project/license.html |
| joblib | BSD-3-Clause | https://github.com/joblib/joblib/blob/main/LICENSE.txt |
| Streamlit | Apache-2.0 | https://github.com/streamlit/streamlit/blob/develop/LICENSE |
| Altair | BSD-3-Clause | https://github.com/vega/altair/blob/main/LICENSE |
| FastAPI | MIT | https://github.com/fastapi/fastapi/blob/master/LICENSE |
| Pydantic | MIT | https://github.com/pydantic/pydantic/blob/main/LICENSE |
| Starlette | BSD-3-Clause | https://github.com/Kludex/starlette/blob/main/LICENSE.md |
| Uvicorn | BSD-3-Clause | https://github.com/Kludex/uvicorn/blob/main/LICENSE.md |
| HTTPX | BSD-3-Clause | https://github.com/encode/httpx/blob/master/LICENSE.md |

Exact pinned versions are in `requirements*.txt`. These files also identify
the transitive numerical/plotting packages used by the recorded ML experiment.
API/UI transitive dependencies are resolved by the installer; this repository
does not claim a cross-platform, fully locked dependency graph.

## OPSD / ENTSO-E data

Attribution: Open Power System Data (2020), *Data Package Time series*, version
2020-10-06, https://doi.org/10.25832/time_series/2020-10-06. Primary measurements:
ENTSO-E Transparency. No endorsement is implied.

This source edition includes no third-party measurements, trained model binaries,
per-origin forecast exports, figures or screenshots. Aggregate evaluation metrics
and experiment configuration describe the author's local experiment. The code
license does not grant rights over the underlying data. See `data/SOURCES.md` and
`docs/PUBLICATION_SCOPE.md` for the scope and source links.
