from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from profair_observability.admissibility.batch import PIPELINE_VERSION, run_batch
from profair_observability.admissibility.engine import AdmissibilityEngine
from profair_observability.admissibility.privacy import restricted_mode_enabled
from profair_observability.admissibility.schema import RetrievedSource, RetrievalStatus
from profair_observability.admissibility.search import (
    BraveSearchProvider,
    SerpAPISearchProvider,
)

st.set_page_config(page_title="ProFair Evidence-Admissibility", layout="wide")


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, ""))


def _synthetic_demo() -> pd.DataFrame:
    rows = [
        {
            "person_id": "SYN_001",
            "full_name": "Alex Morgan",
            "org_search_target": "Northstar Mobility",
            "primary_fair": "Synthetic Fair A",
            "preliminary_classification": "",
        },
        {
            "person_id": "SYN_002",
            "full_name": "Jordan Lee",
            "org_search_target": "Helio Systems",
            "primary_fair": "Synthetic Fair A",
            "preliminary_classification": "",
        },
        {
            "person_id": "SYN_003",
            "full_name": "Sam Rivera",
            "org_search_target": "Arcadia Labs",
            "primary_fair": "Synthetic Fair B",
            "preliminary_classification": "",
        },
    ]
    sources = {
        "SYN_001": [
            RetrievedSource(
                query='"Alex Morgan" "Northstar Mobility"',
                provider="synthetic",
                rank=1,
                requested_url="https://northstarmobility.example/team",
                final_url="https://northstarmobility.example/team",
                retrieval_status=RetrievalStatus.FULL_TEXT_RETRIEVED.value,
                full_text=(
                    "Alex Morgan is a woman and member of the "
                    "Northstar Mobility leadership team."
                ),
                page_title="Northstar Mobility team",
                content_sha256="synthetic-1",
            )
        ],
        "SYN_002": [
            RetrievedSource(
                query='"Jordan Lee" "Helio Systems"',
                provider="synthetic",
                rank=1,
                requested_url="https://news.example/profile",
                final_url="https://news.example/profile",
                retrieval_status=RetrievalStatus.FULL_TEXT_RETRIEVED.value,
                full_text=(
                    "Jordan Lee works with Helio Systems on "
                    "international markets."
                ),
                page_title="Synthetic professional profile",
                content_sha256="synthetic-2",
            )
        ],
        "SYN_003": [],
    }
    engine = AdmissibilityEngine(
        trusted_official_domains={"northstarmobility.example"}
    )
    return pd.DataFrame(
        [
            engine.evaluate(row, sources[row["person_id"]]).to_flat_dict()
            for row in rows
        ]
    )


def _zip_directory(path: Path) -> bytes:
    archive_path = path / "profair_audit_output.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in path.rglob("*"):
            if item.is_file() and item != archive_path:
                zf.write(item, item.relative_to(path))
    return archive_path.read_bytes()


st.title("ProFair Evidence-Admissibility")
st.caption(f"Pre-release audit application · pipeline {PIPELINE_VERSION}")
restricted = restricted_mode_enabled()
if restricted:
    st.warning(
        "RESTRICTED MODE is enabled. Uploaded names and organisations may "
        "be sent to the configured search provider. Use only in an approved "
        "private/local environment."
    )
else:
    st.info(
        "PUBLIC DEMO MODE. Direct-identifier upload and live evidence "
        "retrieval are disabled. This deployment can safely demonstrate "
        "the method with synthetic data only."
    )

with st.expander("Methodological guards", expanded=False):
    st.markdown(
        """
- Names and preliminary screening labels are **not gender evidence**.
- Search snippets locate candidate pages but never support primary admission.
- Identity resolution precedes attribute evidence.
- Identity is resolved only by one `ACCEPTED` source or two independent `ACCEPTED_PROVISIONAL` sources.
- `A_i^(B)=1` requires one qualifying official/institutional source or two independent concordant professional sources.
- A supplied organisation domain is primary only when `organisation_domain_status=VERIFIED`; discovered domains remain candidates until verified.
- Photographs, appearance, voice, and clothing are excluded.
- Explicit non-binary/alternative self-description is preserved outside the binary denominator.
- Technical search failures are flagged separately and are **not** converted into `Not Classified` analytical cases.
"""
    )

public_tab, restricted_tab = st.tabs(
    ["Synthetic demonstration", "Restricted audit runner"]
)
with public_tab:
    st.subheader("Synthetic demonstration")
    st.write("No real people or restricted research records are used in this tab.")
    if st.button("Run synthetic demonstration", type="primary"):
        demo = _synthetic_demo()
        st.dataframe(demo, width="stretch")
        st.metric("Admissible synthetic cases", int(demo["A_i_B"].sum()))

with restricted_tab:
    if not restricted:
        st.error(
            "Restricted audit is disabled in public mode. Run locally/private "
            "with `PROFAIR_RESTRICTED_MODE=1`."
        )
    else:
        uploaded = st.file_uploader("Upload restricted audit CSV", type=["csv"])
        provider_name = st.selectbox(
            "Search provider",
            ["SerpAPI", "Brave Search"],
        )
        max_cases = st.number_input(
            "Maximum cases for this run",
            min_value=1,
            max_value=1000,
            value=30,
            step=1,
        )
        max_queries = st.slider("Maximum queries per person", 1, 8, 5)
        max_urls = st.slider("Maximum candidate URLs per person", 1, 15, 8)
        trusted_text = st.text_area(
            "Trusted official domains (optional, one per line)",
            help=(
                "Only add domains whose official/institutional status has "
                "been independently established."
            ),
        )
        allow_auto = st.checkbox(
            "Allow high-confidence automatic official-domain typing",
            value=False,
            help=(
                "Keep OFF during pre-release validation unless explicitly "
                "testing this rule."
            ),
        )

        df: pd.DataFrame | None = None
        if uploaded is not None:
            try:
                uploaded_bytes = uploaded.getvalue()
                if not uploaded_bytes:
                    st.error(
                        "The uploaded CSV is empty. Please select the original "
                        "N=150 CSV again."
                    )
                else:
                    df = pd.read_csv(io.BytesIO(uploaded_bytes))
                    st.write(f"Loaded {len(df):,} rows.")
                    if "organisation_domain_status" not in df.columns:
                        st.info(
                            "No organisation_domain_status column is present. "
                            "Organisation domains discovered in this run will "
                            "remain candidates and will not become primary "
                            "official evidence automatically."
                        )
                    preview_cols = [
                        column
                        for column in [
                            "audit_case_id",
                            "person_id",
                            "primary_fair",
                            "priority",
                            "organisation_domain",
                            "organisation_domain_status",
                        ]
                        if column in df.columns
                    ]
                    if preview_cols:
                        st.dataframe(df[preview_cols].head(20), width="stretch")
            except (
                pd.errors.EmptyDataError,
                pd.errors.ParserError,
                UnicodeDecodeError,
            ) as exc:
                st.error(f"Could not parse the uploaded CSV: {exc}")
                df = None

        run_disabled = df is None or df.empty
        if st.button(
            "Run restricted evidence audit",
            type="primary",
            disabled=run_disabled,
        ):
            assert df is not None
            run_df = df.head(int(max_cases)).copy()
            trusted_domains = {
                line.strip().lower()
                for line in trusted_text.splitlines()
                if line.strip()
            }
            try:
                if provider_name == "SerpAPI":
                    provider = SerpAPISearchProvider(
                        api_key=_secret("SERPAPI_API_KEY")
                    )
                else:
                    provider = BraveSearchProvider(
                        api_key=_secret("BRAVE_SEARCH_API_KEY")
                    )
            except ValueError as exc:
                st.error(str(exc))
                st.stop()

            progress_bar = st.progress(0.0)
            status = st.empty()

            def update_progress(
                position: int,
                total: int,
                person_id: str,
            ) -> None:
                progress_bar.progress(position / total)
                status.write(f"Processing {position}/{total}: {person_id}")

            with tempfile.TemporaryDirectory(prefix="profair_audit_") as temp:
                out_dir = Path(temp)
                results, decisions, manifest = run_batch(
                    run_df,
                    provider=provider,
                    output_dir=out_dir,
                    max_queries=max_queries,
                    max_urls_per_person=max_urls,
                    trusted_official_domains=trusted_domains,
                    allow_auto_official_high=allow_auto,
                    progress=update_progress,
                    checkpoint_every=1,
                )
                status.success("Audit run completed.")
                st.dataframe(results, width="stretch")

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("A=1", int(results["A_i_B"].sum()))
                c2.metric(
                    "Woman",
                    int((results["final_category"] == "Woman").sum()),
                )
                c3.metric(
                    "Man",
                    int((results["final_category"] == "Man").sum()),
                )
                c4.metric(
                    "Indeterminate / NC",
                    int(
                        results["final_category"]
                        .isin(["Indeterminate", "Not Classified"])
                        .sum()
                    ),
                )
                technical = int(
                    (results["processing_status"] == "TECHNICAL_FAILURE").sum()
                )
                c5.metric("Technical failures", technical)

                candidate_mask = results[
                    "candidate_organisation_domains"
                ].astype(str).str.len() > 0
                if candidate_mask.any():
                    st.subheader("Organisation domains requiring verification")
                    domain_cols = [
                        column
                        for column in [
                            "audit_case_id",
                            "person_id",
                            "org_search_target",
                            "candidate_organisation_domains",
                        ]
                        if column in results.columns
                    ]
                    st.dataframe(
                        results.loc[candidate_mask, domain_cols],
                        width="stretch",
                    )

                partial = int(
                    (
                        results["processing_status"]
                        == "PARTIAL_SEARCH_FAILURE"
                    ).sum()
                )
                if technical or partial:
                    st.warning(
                        f"Search-layer issues recorded: {technical} technical "
                        f"failure(s), {partial} partial search failure(s). "
                        "These are preserved in provenance and must not be "
                        "interpreted as substantive non-classification."
                    )

                st.download_button(
                    "Download results CSV",
                    data=results.to_csv(index=False).encode("utf-8-sig"),
                    file_name="admissibility_results.csv",
                    mime="text/csv",
                )
                st.download_button(
                    "Download run manifest",
                    data=json.dumps(
                        manifest,
                        ensure_ascii=False,
                        indent=2,
                    ).encode("utf-8"),
                    file_name="run_manifest.json",
                    mime="application/json",
                )
                st.download_button(
                    "Download full audit bundle",
                    data=_zip_directory(out_dir),
                    file_name="profair_audit_output.zip",
                    mime="application/zip",
                )
