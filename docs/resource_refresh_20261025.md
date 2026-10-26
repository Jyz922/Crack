# Lexical resource refresh — October 25, 2026

The local checkout was synchronized with `origin/main` at
`7ed6381e959592282475deb12054b3a4e6c0c3c8` before this change. Git reported it
was already current. Work is on `codex/resource-refresh-20261025`.

## Active resources

| Purpose | Before | After | Official source |
|---|---|---|---|
| Pronunciation lookup | NLTK CMUdict, bundled README 0.7a | cmusphinx/cmudict commit `74790861f652b15e4ac49015a90074ad62a27690`, October 24, 2025 | https://github.com/cmusphinx/cmudict |
| Sense inventory and morphology | Princeton WordNet 3.0 | Open English Wordnet 2025, official release dated December 31, 2025 | https://en-word.net/downloads |
| Articulatory features | PanPhon 0.22.2 | Unchanged: latest published release checked October 25, 2026, released June 12, 2025 | https://pypi.org/project/panphon/ |
| Historical sense frequencies | WordNet 3.0 SemCor-derived counts | Retained, checksum-verified and matched by exact lemma sense key | https://wordnet.princeton.edu/ |
| Word acquisition ratings | Kuperman AoA | Retained with original provenance; no unvalidated replacement | `scripts/fetch_aoa.py` |

Current lookup data is distinct from historical frequency evidence. OEWN names
and offsets can move: `cat.n.01`, for example, changes semantic category between
the two inventories. Joining count evidence by synset name would be incorrect.
The adapter delegates historical count lookup using the exact lemma sense key.
As in the original WordNet API, an unattested key has count zero. This does not
establish current usage frequency or observed balanced usage.

The official OEWN 2025 WNDB zip has files whose headers still say 2023. The
download page identifies the release as 2025. CRACK preserves all upstream
files, pins the zip and individual-file SHA-256 values, and reports the release
identity from the manifest. It adds only the standard lexical-category label
file needed by NLTK. The archive does not supply frequency counts.

## Setup, provenance and cache compatibility

```bash
pip install -e ".[test,web]"
python scripts/fetch_lexical_resources.py
python scripts/fit_phonetic_calibration.py
pytest -q -m "not live"
```

The committed calibration already matches this snapshot; regenerating it is
optional for an ordinary install. Downloads and extracted files are verified
against `src/crack/resource_data/manifest.json`; cached data stays untracked.
The setup command also prepares the historical count reference before offline
tests disable network access. Missing or modified active data raises a setup error rather than falling back
to old lookup data. Attribution and CMU's license ship with the source package.
The web build command now explicitly installs the resources.

Run fingerprints include the manifest, resource versions and download hashes,
phonetic calibration checksum, and AoA checksum. Resuming predictions from
different lexical resources is rejected. Runtime scoring also refuses a
calibration file generated for another CMU snapshot.

## Offline results

The full offline suite passes: **564 passed, 10 live tests deselected**. Added tests cover
checksum rejection, no partial installation on a bad download, current versus
historical inventories, correct sense-key count matching, old-calibration
rejection, and resource-aware resume invalidation.

The six required **raw** phonetic scores are unchanged. Calibrated scores change
because the dictionary supplies a different random-pair population:

| Pair | Raw similarity | Old calibrated | New calibrated |
|---|---:|---:|---:|
| cat / cad | 0.9943 | 0.9774 | 0.9774 |
| cat / cash | 0.9540 | 0.8193 | 0.8196 |
| drum / drama | 0.8897 | 0.5949 | 0.6049 |
| knight / night | 1.0000 | 1.0000 | 1.0000 |
| bat / pat | 0.9943 | 0.9774 | 0.9774 |
| pat / pit | 0.9655 | 0.8645 | 0.8647 |

139 texts were run through local L1–L3 before and after the migration:

| Corpus | Items | Changed shortlists | Changed sense counts | Changed soundalike outputs |
|---|---:|---:|---:|---:|
| Original project corpus | 60 | 15 | 51 | 26 |
| Soundalike corpus | 79 | 17 | 61 | 20 |

Soundalike-output changes include recalibrated numerical scores, not just
different proposed words. These counts measure changes in local evidence,
not changes in joke-detection accuracy. Full before/after evidence is in
[local_comparison.json](evaluations/resource_refresh_20261025/local_comparison.json).

The local finder still supplies 2/35 annotated target alternatives and flags
4/35 annotated pun words. It fires on 9/43 negatives, compared with 10/43
before. On SemEval's 1,098 target-annotated heterographic puns, target recall
remains 2/1,098. New dictionaries alone do not solve the missing-neighbor-search
limitation.

## Limits of this update

The initial migration checks above were offline. Subsequent user live reruns
scored 71/79 on soundalikes and 53/60 on the original corpus, with one execution
failure in the latter. See [the live comparison](resource_refresh_live_20261025.md).
The October 23 score of 73/79 belongs to the earlier dictionaries and must not
be advertised as the accuracy of this resource refresh. Single stochastic
reruns do not isolate a causal dictionary effect.

Existing corpus labels were not silently changed. Independent double labeling,
better target retrieval and newer external robustness benchmarks remain
separate work. Existing prompt templates and LLM models are unchanged.
