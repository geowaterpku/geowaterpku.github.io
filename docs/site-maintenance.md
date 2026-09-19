# GeoWater site maintenance

## Editing and publishing

Root HTML files remain the editorial source. Do not manually edit `_site` or generated `assets/built-*.css` files. The deployment workflow builds `_site`, validates it, and publishes that directory. Daily Paper Radar, Scholar and visitor-map refresh workflows are preserved.

```sh
python -m pip install -r site-tools/requirements.txt
python site-tools/build.py
python site-tools/validate.py
python -m pip install playwright==1.57.0
python -m playwright install chromium
python site-tools/browser-test.py
```

Use a pull request for subsequent changes to run browser regression checks. The quality workflow checks 320, 390, 768 and 1366 pixel viewports, mobile navigation, profile identity placement, publication filters, date folding, radar controls and no-JavaScript navigation. Screenshots and JSON reports are uploaded as workflow artifacts.

## Single sources of truth

- `publications.html`: all publication titles, authors, journal links, years and figures. The build derives stable paper anchors, the homepage recent-publication list and the searchable bibliography from this source. No exact publication date is inferred from the year.
- `site-tools/build.py`: shared navigation, build-time presentation transformations, verified dataset entry points, and explicit featured-paper selections.
- `assets/site-ui.css`: shared visual and responsive rules.
- `assets/site-ui.js`: progressive navigation, bibliography search/folding and selectable citation text. No scientific content replacement or runtime CSS injection.
- `assets/paper-radar.js`: date-window/search controls and expandable AI guides. Data remains in `assets/data/paper-radar.json`, maintained by the existing workflow.
- Existing `nav.js` is retained as a compatibility source for legacy style refinements. Its style literals are extracted at build time; it is not loaded by the generated site. Existing source-page style sheets are combined into one content-hashed sheet per page. Migrate compatibility rules into named page styles as future page designs are reviewed.

## Research content safeguards

All bibliography titles and author strings are regression-checked against the source. Submission and preprint status is displayed without converting a manuscript into a published paper. Original recruitment and historical news text is retained in expandable sections. New homepage updates are labelled recent publications, not invented dated lab events.

Course syllabi, detailed application rules, GRDR and MizuRoute access links were not invented. Where a verified public entry point is not available, the site offers an enquiry link. Dataset repositories remain authoritative for licenses and versions; no blanket open license is assigned.

## Data-entry sources checked for this release

- GRADES: https://www.reachhydro.org/home/records/grades — legacy release and hydroDL upgrade notice.
- MERIT-Basins: https://www.reachhydro.org/home/params/merit-basins — hydrography downloads and version compatibility.
- MERIT-Hydro-Vectors: https://www.reachhydro.org/home/params/global-drainage-density — variable-drainage-density data portal.
- GRADES-hydroDL: https://www.reachhydro.org/home/records/grades-hydrodl
- GRFR: https://www.reachhydro.org/home/records/grfr
- GSHA publication: https://essd.copernicus.org/articles/16/1559/2024/ — lists https://doi.org/10.5281/zenodo.8090704 and https://doi.org/10.5281/zenodo.10433905.
- SHIFT publication: https://essd.copernicus.org/articles/16/3873/2024/ — lists data https://doi.org/10.5281/zenodo.11835133 and code https://doi.org/10.5281/zenodo.13311752.

## Release verification and rollback

`build-info.json` and each page's `geowater-build` meta tag identify the deployed revision. Successful commit creation is not by itself proof of deployment; confirm the Pages workflow and public build marker. Revert the optimization commit through GitHub to restore the previous deployment pipeline; never force-push over concurrent data refreshes.
