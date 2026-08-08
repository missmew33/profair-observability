# Deployment

## Recommended architecture

1. **Public deployment:** Streamlit demo, synthetic data only, `PROFAIR_RESTRICTED_MODE=0`.
2. **Restricted deployment:** local workstation, private VM, or access-controlled private app, `PROFAIR_RESTRICTED_MODE=1`.
3. **Search provider:** SerpAPI or Brave Search via environment secret.
4. **Outputs:** local restricted storage; only disclosure-reviewed aggregates may move to the public repository.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export PROFAIR_RESTRICTED_MODE=1
export SERPAPI_API_KEY=YOUR_KEY
streamlit run streamlit_app.py
```

## Streamlit Community Cloud

Use only for the public synthetic demo. Point the app entry file to `streamlit_app.py`. Do not enable restricted mode and do not add restricted research data.

## Private Streamlit deployment

A private VM/container may enable restricted mode. The operator is responsible for institutional data-governance approval, search-provider terms, secrets management, and access control.
