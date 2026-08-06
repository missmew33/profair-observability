# Public release checklist

- [ ] Replace `missmew33` in repository URLs.
- [ ] Confirm project name and licence.
- [ ] Run the full validation protocol.
- [ ] Freeze algorithm version and weights.
- [ ] Confirm no direct identifiers or raw administrative data are tracked.
- [ ] Run `git status` and inspect every staged file.
- [ ] Run `ruff check .`.
- [ ] Run `pytest`.
- [ ] Build with `python -m build`.
- [ ] Create a tagged release.
- [ ] Archive the release and add the DOI to `CITATION.cff`.
- [ ] Cite the exact software version used in the thesis.
