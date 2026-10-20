# Teaching CRACK to Hear Soundalike Puns

The literature and the local verification runs point to one design for Project 2: **use a deterministic phonetic module to find and score soundalikes, and let CRACK's existing anchoring, resolution and distinctness layers decide whether a soundalike creates incongruity.** Do not let the LLM decide what sounds alike. Past systems show that phonetic and contextual signals only work together. Jaech et al. recovered pun targets 68.0% of the time when they combined a phone-edit model with a language model, against 20.0% for phonetics alone and 9.3% for the language model alone ([Jaech et al. 2016](https://aclanthology.org/N16-1079.pdf)). Most LLMs name the heterographic alternative word poorly: mention ratios run from 0.11 to 0.55, with only GPT-4-Turbo (0.90) and Claude-3-Opus (0.84) above that range ([Xu et al. 2024](https://arxiv.org/html/2404.13599v2)). When they get it wrong, they typically "force" sound links between words that are not phonetically close ([Zangari et al. 2025](https://arxiv.org/html/2509.12158v2)). The recommended similarity measure is a weighted Levenshtein distance over CMUdict phones, with substitution costs taken from PanPhon articulatory features using weights aligned by feature name. It ranks the six required pairs knight/night 1.000 > cat/cad = bat/pat 0.994 > pat/pit 0.966 > cat/cash 0.954 > drum/drama 0.890. The scale is compressed, though: random same-length word pairs average about 0.72 to 0.73, so the raw scores need calibration before anyone thresholds them. The installed PanPhon library also has a weight-misalignment bug that under-weights vowel tenseness, which affects pat/pit. Two further problems need attention. SemEval-2017 heterographic detection scores are shortcut-prone: always answering "pun" already gets F1 0.833, against the 2017 winner's 0.8439. And two of the three instructor test texts are weak or ambiguous jokes. All of this can be added to CRACK without extra LLM requests. The work is new local modules feeding L2–L4, a widened L4 response contract, and a new soundalike classification in L0-post. This report drafts that design only; nothing in the repository was changed.

## Six findings should shape Project 2 before any code is written

The table states the conclusions the team most needs, including the uncomfortable ones, with a confidence level for each. "High" means multiple primary sources or a locally reproduced computation agree. "Medium" means one primary source or an inference from consistent evidence. "Low" means a design judgment that still needs data.

| # | Finding | Consequence for the design | Confidence |
|---|---|---|---|
| 1 | **SemEval heterographic detection rewards shortcuts.** Always predicting "pun" gives F1 0.833. A rule of "≥9 tokens OR contains 'Tom'" gives F1 0.806. The 2017 winner scored 0.8439. "Tom" appears in 225 positives and 0 negatives ([notes' analysis of the SemEval archive](https://alt.qcri.org/semeval2017/task7/data/uploads/semeval2017_task7.tar.xz); [Miller et al. 2017](https://aclanthology.org/S17-2005.pdf)). Fine-tuned RoBERTa drops from 92.5 F1 on PunEval to about 64–66 on new data ([Zangari et al. 2025](https://arxiv.org/html/2509.12158v1)). | Never report a SemEval detection number without the all-pun and length/template baselines. The primary test should be minimal-pair hard negatives. | High |
| 2 | **LLMs detect soundalike puns well but name the soundalike target poorly**, and they invent sound links ([Xu et al. 2024](https://arxiv.org/html/2404.13599v2); [Loakman et al. 2025](https://arxiv.org/pdf/2507.13335v2)). Constraining an LLM to phonetically retrieved candidates raised Qwen-2.5-7B heterographic F1 from 37.47 to 59.18 ([Su et al. 2026, PunGraph](https://arxiv.org/html/2609.16557)). | The phonetic module proposes and verifies alternates. L4 may only choose among verified alternates, or propose one that local code then verifies. | High |
| 3 | **A soundalike is not a pun.** "knight" alone has 34 CMUdict neighbours at phone edit distance 1 (notes' local run). Adding a phonetic cue to an LLM prompt raised recall but also false positives on non-jokes ([Thaniserikaran & Harikrishnan 2026](https://aclanthology.org/2026.chum-1.6.pdf)). | Keep the principle in ARCHITECTURE.md that soundalike spellings alone do not establish wordplay. Add a positive path that requires verified phonetics plus two distinctly anchored readings, plus L5 and L6. | High |
| 4 | **The installed PanPhon 0.22.2 misaligns its feature weights.** It zips 22 weights (CSV order) against 24 features (table order), so `tense` gets 0.125 instead of 0.25. The library cost for æ/ɪ is 1.25; the correctly aligned cost is 1.5 ([distance.py](https://raw.githubusercontent.com/dmort27/panphon/master/panphon/distance.py); [feature_weights.csv](https://raw.githubusercontent.com/dmort27/panphon/master/panphon/data/feature_weights.csv); reproduced locally). | Build the weight vector by feature name, and say so in the submission. | High (reproduced) |
| 5 | **Similarity scores are compressed.** A voicing contrast costs 0.017 of a maximal substitution, so cat/cad scores 0.994. Random 3-phone CMUdict pairs average 0.735 (95th percentile 0.886). drum/drama (0.890) sits just below the 99th percentile of random 5-phone pairs (0.900) (verification run below). | Threshold on calibrated similarity, not raw similarity. Report the ranking and the calibrated value side by side. | High for the compression; Medium for the specific percentiles (one seeded sample) |
| 6 | **The test texts are not clean examples.** "drum" next to "drama" is a juxtaposition, not a substitution, and a "humdrum" reading competes with it. "cat-nap into cash" is more naturally a cat + catnap resegmentation than a cat→cash pun. Only "purr-suing" is a textbook soundalike pun. | Report design-time expectations honestly. Do not tune the system until these three come out positive. | Medium (judgment) |

## Two decades of systems show phonetics finds targets while context decides puns

The SemEval-2017 Task 7 heterographic track is the field's shared benchmark: 1,780 contexts, 1,271 of them puns, with at most one pun per text ([Miller et al. 2017](https://aclanthology.org/S17-2005.pdf)). Its history is a warning about what phonetics actually contributes. **Only one 2017 system, Idiom Savant, computed phonetic distance at all.** It took CMUdict phonemes with stress stripped (the authors found coarser representations worked better), computed three Levenshtein variants (phoneme units, concatenated phoneme string, and characters as an out-of-vocabulary fallback), and kept the best similarity ratio (len_shorter − d)/len_shorter. It then flagged a pun when substituting a soundalike turned a rare n-gram into a frequent idiom ("a jab well done" → "a job well done"). That won detection with F1 0.8439 ([Doogan et al. 2017](https://aclanthology.org/S17-2011.pdf)). The best location system, UWaterloo (F1 0.7964, 0.8492 after post-submission features), used no phonetic algorithm at all. It used a hand-compiled list of 2,167 similar-sounding words, plus NPMI association, IDF and position features ([Vechtomova 2017](https://aclanthology.org/S17-2071.pdf)). Systems that used spelling edit distance or broad Datamuse "sounds like" queries did worse. Duluth's edit-distance-1 rule could not even reach office/orifice ([Pedersen 2017](https://aclanthology.org/S17-2070.pdf)). Interpretation, which requires recovering the target's WordNet sense, was essentially unsolved: best F1 0.0771 against a most-frequent-sense baseline of 0.0708 ([Miller et al. 2017](https://aclanthology.org/S17-2005.pdf)).

The most principled phonetic model is still Jaech, Koncel-Kedziorski and Ostendorf's noisy channel, T* = argmax_T p(P|T)·p(T). Here p(P|T) is a phone-edit transducer whose substitution probabilities were learned by EM from 1,182 pun/target pairs in Hempelmann's dissertation, and p(T) is a Reddit trigram language model. Its lexicon allowed multi-word targets ("no bell" → "Nobel"). It recovered 68.0% of targets (MRR 0.729), against 29.3% when the same language model used Hempelmann's hand-built cost table, which pruned true targets before the language model could act ([Jaech et al. 2016](https://aclanthology.org/N16-1079.pdf); [Hempelmann 2003](https://docs.lib.purdue.edu/dissertations/AAI3113812)). That result supports Project 2's design in two ways. A graded, non-binary phone cost beats a crude one, and phonetic evidence has to be combined with contextual fit.

Kao, Levy and Goodman supply the semantic criterion that matches the instructor's wording, "the difference in pronunciation is compatible with different parts of the text." **Ambiguity** is the entropy of P(m|w) over the two meanings. **Distinctiveness** is the symmetric KL divergence between the distributions of context words that support each meaning. Ambiguity separated puns from non-puns (t(159.48) = 7.89, p < .0001), and within puns only distinctiveness tracked funniness (r = .28). The journal version found no significant difference between identical and near homophones in funniness, ambiguity or distinctiveness. In other words, the semantic test holds up even when the phonetic match is imperfect ([Kao et al. 2016](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5042108/fullTextXML)). Kao's model takes the soundalike pair as given and never computes phonetic similarity, which is the gap Project 2's new components fill.

Neural work after 2019 raised SemEval numbers, but phonetics contributed little to the gains. The pronunciation-attentive PCPR model beat its own no-pronunciation ablation by only +1.0 F1 on heterographic detection (95.22 vs 94.19) and +2.0 on location (92.28 vs 90.23). Most of its jump over earlier systems came from BERT, under 10-fold cross-validation on the test set ([Zhou et al. 2020](https://ar5iv.labs.arxiv.org/html/2004.14457)). The LLM-era studies settle the division of labour. Frontier models recognize heterographic puns about as well as homographic ones ([Xu et al. 2024](https://arxiv.org/html/2404.13599v2)). They are worse at explaining them, and they hallucinate phonetic links ([Loakman et al. 2025](https://arxiv.org/pdf/2507.13335v2)). They also over-label altered non-puns: GPT-4o scored 0.33 accuracy on PunBreak items where the pun word was replaced by a nonsense soundalike ([Zangari et al. 2025](https://arxiv.org/html/2509.12158v1)). Their underlying phonological knowledge is shallow: in PhonologyBench, syllable counting was about 55% for Claude-3-Sonnet and 23% for GPT-4, against 90% for humans ([Suvarna et al. 2024](https://arxiv.org/html/2404.02456v1)). PunGraph, the closest recent analogue to this project, builds a phonetic-semantic graph and offers an LLM a short list of retrieved candidates only when the LLM's own guess has low IPA similarity. Retrieval misses still caused 19% of the remaining heterographic failures for the small model ([Su et al. 2026](https://arxiv.org/html/2609.16557)). One caveat applies to every model-based number above. CRACK currently runs OpenAI `gpt-6-luna`, which none of these studies tested, so its target-naming accuracy is unknown until it is measured on project data.

## A name-aligned PanPhon edit distance scores the six required pairs

### Formulas, from pronunciation lookup to word-level similarity

The method has five steps. Every formula below is either from the cited code or paper, or is the team's own definition, marked as such.

**Step 1: grapheme to phoneme.** Look each word up in CMUdict (ARPAbet, 39 phones, stress digits 0/1/2). Words CMUdict lacks go to g2p_en, which runs number normalization, then part-of-speech heteronym choice, then the CMUdict lookup, then a neural network for out-of-vocabulary words ([g2p_en](https://github.com/Kyubyong/g2p); [CMUdict](https://github.com/cmusphinx/cmudict)). Strip stress, but map AH0 → ə and AH1/AH2 → ʌ so reduced vowels survive. Then convert ARPAbet to IPA with a fixed table (AA ɑ, AE æ, AH ʌ/ə, IH ɪ, R ɹ, SH ʃ, and so on). The notes' local run confirmed CMUdict's first entries for all ten words: cat K AE1 T, cad K AE1 D, cash K AE1 SH, drum D R AH1 M, drama D R AA1 M AH0, knight = night N AY1 T, bat B AE1 T, pat P AE1 T, pit P IH1 T. When a word has several pronunciations, score every pair and keep the maximum (wok/walk is 0.960 for wɑk/wɔk and 1.000 for wɑk/wɑk in the verification run).

**Step 2: phone features.** PanPhon maps each IPA segment to a vector of 24 features, each valued +1, 0 or −1: syl, son, cons, cont, delrel, lat, nas, strid, voi, sg, cg, ant, cor, distr, lab, hi, lo, back, round, velaric, tense, long, hitone, hireg ([PanPhon repo](https://github.com/dmort27/panphon); [Mortensen et al. 2016](https://aclanthology.org/C16-1328.pdf)). The paper says "21 features"; cite the 0.22.2 code. One trap: PanPhon's parser splits diphthongs and untied affricates (aɪ → a + ɪ, tʃ → t + ʃ). Build one vector per ARPAbet phone instead of re-parsing the IPA string.

**Step 3: graded phone-to-phone distance (the non-binary requirement).** The team's definition, built from PanPhon's weights aligned by feature name:

```
δ(a, b) = Σ_f w_f · |a_f − b_f|  /  (2 · Σ_f w_f)          ∈ [0, 1],   Σ_f w_f = 7.25
weights: syl 1, son 1, cons 1, cont 0.5, delrel/lat/nas/ant/cor/lab/hi/lo/back/round/velaric/tense 0.25,
         strid/voi/sg/cg/distr/long 0.125, hitone/hireg 0
```

For the submission, the library formulas being replaced are, verbatim from `panphon/distance.py` ([source](https://raw.githubusercontent.com/dmort27/panphon/master/panphon/distance.py)):

```
unweighted_substitution_cost(v1,v2) = Σ |f1 − f2| / 2  /  len(v1)          (len = 24)
unweighted_insertion_cost(v) = unweighted_deletion_cost(v) = Σ (0.5 if x==0 else 1) / len(v)
hamming_substitution_cost(v1,v2) = mean(f1 ≠ f2);  hamming indel = 1
weighted_substitution_cost(v1,v2) = Σ w · |f1 − f2|   (zip(weights, v1, v2); range 0 … 14.5)
weighted_insertion_cost = weighted_deletion_cost = Σ w = 7.25
*_div_maxlen(s,t) = distance / max(len(segs_s), len(segs_t))
min_edit_distance: d[i][j] = min(d[i−1][j] + del(s_i), d[i−1][j−1] + sub(s_i,t_j), d[i][j−1] + ins(t_j))
```

The library's `weighted_substitution_cost` zips the 22-entry weight list, in the CSV order (…round, tense, long, velaric), against 24-entry vectors in table order (…round, velaric, tense, long, hitone, hireg). As a result `tense` receives 0.125, `long` receives 0.25, and the two tone features are dropped. The tone features are irrelevant for English. The tense misweighting is not: it lowers tense/lax vowel contrasts such as æ/ɪ, i/ɪ and u/ʊ (verified locally in the notes and again in this run).

Phone distances from the verification run show the gradation the instructor asked for. A voicing change is almost free, a place-and-manner change costs more, and a consonant against a vowel costs most:

| Contrast | Features that differ | δ (custom, 0–1) | PanPhon unweighted_sub | PanPhon weighted_sub (library) |
|---|---|---|---|---|
| t/d | voi | 0.0172 | 0.0417 | 0.25 |
| b/p | voi | 0.0172 | 0.0417 | 0.25 |
| ʌ/ɑ | delrel, lo | 0.0517 | 0.0625 | 0.75 |
| æ/ɪ | hi, lo, tense | 0.1034 | 0.125 | 1.25 (aligned: 1.5) |
| t/ʃ | cont, strid, ant, distr | 0.1379 | 0.1667 | 2.0 |
| m/ə | many (consonant vs vowel) | 0.4828 | n/a | n/a |

**Step 4: word-level weighted Levenshtein.** Use the same Wagner–Fischer recurrence as PanPhon, with substitution cost δ and a constant insertion/deletion cost of 0.5. That is half a maximal substitution, matching PanPhon's own 7.25 : 14.5 ratio:

```
D[0][0] = 0;  D[i][0] = 0.5·i;  D[0][j] = 0.5·j
D[i][j] = min( D[i−1][j] + 0.5,  D[i][j−1] + 0.5,  D[i−1][j−1] + δ(a_i, b_j) )
sim(a, b) = 1 − D[n][m] / max(n, m)
```

A provably bounded alternative uses PanPhon's raw weighted distance: sim = 1 − D_raw / ((n+m)·Σw). Deleting everything and inserting everything costs (n+m)·Σw, so this can never leave [0,1]. Indel = 0.5 is a design choice with no published consensus. Raising it to 1.0 changes only drum/drama, from 0.890 to 0.790.

**Step 5: calibration.** Because minimal pairs crowd into 0.95–1.0, the team should report a calibrated score anchored on the random-pair mean μ_L for the longer word's phone length L:

```
sim_cal(a, b) = (sim − μ_L) / (1 − μ_L)          (0 ≈ a typical random pair, 1 = identical)
```

The verification run sampled 1,500 random CMUdict pairs per length (seed 0). It found μ₃ = 0.735, μ₄ = 0.719 and μ₅ = 0.730, with 95th percentiles of 0.886, 0.847 and 0.851 and 99th percentiles of 0.934, 0.900 and 0.900. The final system should fit thresholds on labelled homophone, near-homophone and unrelated pairs. These sampled values are a starting point, not a validated calibration.

### Results for the six required pairs

The raw-similarity columns below match the notes' recorded values and were reproduced in this run by re-executing `wlev_fixed.py` and a PanPhon check in a scratch environment. The ALINE columns come from the notes; they were not re-run here, because abydos 0.5.0 needs source patches to import on current numpy. The calibrated column is from the verification run above.

| Pair | IPA | PanPhon feature_edit /maxlen (dist) | PanPhon weighted raw / maxlen (dist) | **Custom WLev sim** | Calibrated sim_cal | Bounded library sim 1−D/((n+m)·7.25) | ALINE local (notes) | ALINE global (notes) |
|---|---|---|---|---|---|---|---|---|
| knight/night | naɪt / naɪt | 0 | 0 / 0 | **1.000** | 1.000 | 1.000 | 1.000 | 1.000 |
| cat/cad | kæt / kæd | 0.0139 | 0.25 / 0.083 | **0.994** | 0.978 | 0.994 | 0.882 | 0.882 |
| bat/pat | bæt / pæt | 0.0139 | 0.25 / 0.083 | **0.994** | 0.978 | 0.994 | 0.882 | 0.882 |
| pat/pit | pæt / pɪt | 0.0417 | 1.25 / 0.417 | **0.966** | 0.870 | 0.971 (misaligned weights) | 0.941 | 0.941 |
| cat/cash | kæt / kæʃ | 0.0556 | 2.0 / 0.667 | **0.954** | 0.827 | 0.954 | 0.835 | 0.835 |
| drum/drama | dɹʌm / dɹɑmə | 0.1958 | 8.0 / 1.6 | **0.890** | 0.591 | 0.877 | 0.870 | 0.796 |

Every PanPhon-based column gives the expected order: identical, then single-voicing, then vowel change, then place/manner change, then an extra syllable plus a vowel change. ALINE gets one ordering wrong ([Kondrak 2000](https://aclanthology.org/A00-2038.pdf); [abydos](https://raw.githubusercontent.com/chrislit/abydos/master/abydos/distance/_aline.py)). It scores pat/pit (0.941) above cat/cad (0.882), because its saliences make a vowel height change (salience 5) cheaper than voicing (salience 10). That suits cognate alignment, where vowels drift, but not puns. Local ALINE also ignores drama's trailing ə. That makes ALINE a useful cited comparison, but not the primary metric. Bailey and Hahn found that simple featural measures predict human consonant-similarity judgments better than confusability measures, which supports a PanPhon-style feature distance ([Bailey & Hahn 2005](https://orca.cardiff.ac.uk/3259/)).

For the submission's "why adequate" sentence: a feature-weighted edit distance is the standard, citable way to make phone substitution costs graded. It is deterministic and runs on a laptop, and it reproduces the intuitive ordering of all six pairs. A learned confusion model in the style of Jaech would be better, but it needs the Hempelmann training pairs, which the team does not have. Hixon et al.'s data-driven substitution matrix is the related-work citation for that alternative ([Hixon et al. 2011](https://www.cs.hunter.cuny.edu/~epstein/papers/Phonemic%20Similarity%20Metrics%20to%20Compare%20Pronunciation%20Methods.pdf)).

## Soundalike handling slots into CRACK's L1–L4 and L0-post without new model calls

### What CRACK does today, and what must change

CRACK v1.0.0 explicitly targets "homographic wordplay (one spelling with multiple meanings) and compound resegmentation." Its L4 prompt forbids replacing split parts "with differently spelled soundalikes" (`src/crack/prompts/l4_anchoring.md`, line 34). `ScopeLabel.OUT_OF_SCOPE_HOMOPHONE` and `MainClassification.OUT_OF_SCOPE_HOMOPHONE` exist, and `detection_status_for` maps them to `OUT_OF_SCOPE`. However, `_l0_post_layer` only sets `is_homophone` when a previous final verdict already carried that scope, so in practice nothing produces it. The repo's own `docs/web_examples.md` records that the "impasta" demo was removed after the live check picked `fake` as a homographic target, and states that "the detector's general handling of sound-based jokes" remains a limitation. The 60-item project corpus and the SemEval files in `corpus/` contain no heterographic items (zero `het_` IDs).

Three structural facts constrain the design. First, L1's tokenizer regex `[A-Za-z]+(?:['’][A-Za-z]+)?` splits "purr-suing" into `purr`, `suing` and "cat-nap" into `cat`, `nap` (checked on the test texts). The hyphenated forms these jokes depend on therefore never reach L2's `compound_splits`, which works on single tokens. Second, L4's validation requires `target_term` to be a supplied shortlist term, with distinct source quotes for each reading. This closed-set, quote-validated contract is exactly the "LLM proposes, phonetics verifies" guard the literature recommends, so it should be extended rather than bypassed. Third, `CandidateEntry` and `L4Result` use `extra="forbid"`, so every new field needs an explicit schema change and a contract-version bump: `RESPONSE_CONTRACT_VERSION` is "6" and `CANDIDATE_SEARCH_VERSION` is "4".

**Proposed ARCHITECTURE.md change.** The current sentence, "The occurrence of two soundalike spellings alone does not establish homophone wordplay or override a validated homographic target," should stay; it is correct and supported by finding 3. Add a positive rule after it: *"A soundalike finding becomes wordplay only when (1) the phonetic module verifies the surface/alternate pair at calibrated similarity ≥ τ_verify, (2) L4 anchors each reading to a different source span, with the alternate's reading supported by context the surface word does not explain, and (3) L5 resolution and L6 distinctness pass. The final class is then VALID_SOUNDALIKE_JOKE with scope SOUNDALIKE. OUT_OF_SCOPE_HOMOPHONE is reserved for soundalike mechanisms the phonetic module cannot represent (G2P failure, alternates longer than three words, or the module disabled)."* The README's scope sentence and layer table should change to match.

### Component decomposition, existing and new

This table answers the instructor's requirements 1 and 2. For existing layers, the "evidence" column is what the repo reports. For new components it is the verification-run result or the expected behaviour, labelled as such.

| Component | Status | Goal | Method | Why the method is adequate | Evidence so far |
|---|---|---|---|---|---|
| L0-pre input check | Existing, unchanged | Reject unusable input | Unicode normalization; 3–500 chars; non-ASCII ratio ≤ 0.15 | Cheap gate; the em dash in test text 1 gives a ratio of 0.017, so it passes | Repo tests |
| L1 surface/genre | Existing, **modified** | Tokenize and route the genre | Regex; add `hyphen_groups` recording hyphenated spans from the raw text | Hyphenated coinages carry the pun in two of the three test texts, and the current regex destroys them | Verified: the current tokenizer splits "purr-suing" and "cat-nap" |
| L2 senses + SemCor + AoA | Existing, **modified** | Supply dictionary readings and AoA | WordNet/SemCor/Kuperman; add senses and AoA for each verified *alternate* (source `soundalike:<alt>`) | L4 can only anchor readings it is shown, and the alternate word ("pursuing", "drama") is not in the text | Repo |
| **P0 Pronunciation lexicon** | New | Map words and spans to phones | CMUdict (stress stripped, AH0 → ə) + g2p_en fallback + ARPAbet→IPA table; max over pronunciations | The standard in Idiom Savant, Jaech and CHum 2026; correct on all ten target words | Verified for all six pairs' words |
| **P1 Sound similarity** (instructor component b) | New | Score how alike two utterances sound, with non-binary phone costs | Weighted Levenshtein with name-aligned PanPhon feature δ, indel 0.5, sim = 1 − d/max(n,m), then sim_cal | Graded, citable, deterministic, laptop-fast; reproduces the intuitive order of all six pairs | Six-pair table above |
| **P2 Soundalike finder** (instructor component a) | New | Find utterances in the text that sound like another word or phrase | (i) pairs of content words within the text; (ii) lexicon neighbours via a phone deletion index (k ≤ 2) with a frequency floor; (iii) hyphen merge/split; (iv) DP resegmentation of 1–3-token windows; (v) optional curated list union | k = 1 misses drum/drama and catnap/kidnap (both distance 2); multi-word targets are where simpler systems failed | Notes' run: index of 114,160 pronunciations, 696,752 keys at k = 1, built in 1.5 s |
| L3 candidate ranking | Existing, **modified** | Shortlist candidates for L4 | Keep `0.7·contrast + 0.3·balance` for homographs; add soundalike entries whose contrast compares the surface word's and the alternate's lexnames, carrying `phonetic_sim`/`phonetic_sim_cal`; stays age-free | Puts both mechanisms into one comparable shortlist without letting phonetics alone promote a term | Design |
| L4 LLM anchoring | Existing, **modified** | Choose a target and anchor both readings with exact quotes | Widened prompt and contract: `alternate_form`, relations `sound_substitution` and `sound_pair`; local check that the alternate is supplied or verifies at sim_cal ≥ τ_verify | Keeps LLM judgment where LLMs are strong (contextual readings) and removes it where they are weak (naming soundalikes) | Literature: Xu 2024, PunGraph 2026 |
| L5 resolution | Existing, prompt input extended | Check that the two readings resolve coherently | Genre branches unchanged; prompt receives mechanism, surface, alternate and phonetic score; optional local LM substitution test as a diagnostic | Thresholds are calibrated for homographs, so new evidence is added without changing their weights | Repo: thresholds 0.46/0.60/0.60/0.25 |
| L6 distinctness + age | Existing, small change | Require materially different readings; give age estimates | Unchanged gate; age prompt names the alternate and allows a "phonological" wordplay barrier | Soundalike readings are usually lexically distinct; children's comprehension depends on hearing the alternate | Repo |
| L7/L8 local age checks | Existing, small change | Validate age estimates and cite AoA | Add the alternate word's AoA to the lookup payload, since L7 validates citations against that payload | Without this, any citation for the alternate word is rejected as absent | Repo code path |
| L0-post final class | Existing, **modified** | Combine evidence into class and scope | New `ScopeLabel.SOUNDALIKE`, `MainClassification.VALID_SOUNDALIKE_JOKE` → PUN; label chosen from L4's relation | Makes soundalike detection a first-class positive, not an out-of-scope bucket | Design |

### New modules and their interfaces (drafted, not written to the repo)

The proposed files sit under `src/crack/` so that the existing registry and layer contracts stay intact. All are local and make zero provider calls.

```python
# src/crack/phonetics/lexicon.py
def pronunciations(word: str) -> list[tuple[str, ...]]          # ARPAbet, stress stripped except AH0->"AH0"
def span_phones(tokens: list[str]) -> list[tuple[str, ...]]     # concatenation over a 1-3 token span
def to_feature_vectors(arpabet: tuple[str, ...]) -> list[list[int]]  # one PanPhon vector per ARPAbet phone
# returns source flag per lookup: "cmudict" | "g2p_en"

# src/crack/phonetics/similarity.py
def phone_distance(a: list[int], b: list[int]) -> float          # δ in [0,1], name-aligned weights
def weighted_levenshtein(p, q, indel: float = 0.5) -> tuple[float, list[tuple[int|None, int|None]]]
@dataclass class SoundScore: sim: float; sim_cal: float; distance: float; pron_pair: tuple; alignment: list
def sound_similarity(x: str | list[str], y: str | list[str]) -> SoundScore   # max over pronunciation pairs

# src/crack/phonetics/index.py
class PhoneDeletionIndex:
    @classmethod
    def build(cls, k: int = 2, min_zipf: float = 3.0) -> "PhoneDeletionIndex"
    def neighbours(self, phones: tuple[str, ...], k: int = 2) -> list[str]  # unverified; caller scores with sound_similarity

# src/crack/phonetics/calibration.py   (+ data/phonetic_calibration.json: mu_L, p95_L, p99_L by phone length)
def calibrate(sim: float, length: int) -> float

# src/crack/l3_soundalikes.py
def find_soundalikes(l1: L1Result, text: str, settings: Settings) -> list[SoundalikeCandidate]
```

The schema additions in `schema.py`:

```python
class Alternate(BaseModel):            # extra="forbid"
    form: str                          # spelled as normal words, e.g. "pursuing", "let us"
    phones: list[str]
    sim: float; sim_cal: float
    source: Literal["in_text", "lexicon", "hyphen_merge", "resegmentation", "curated_list", "llm_verified"]

class SoundalikeCandidate(BaseModel):
    surface: str                       # exact source substring, e.g. "purr-suing"
    char_span: tuple[int, int]
    mechanism: Literal["sound_pair", "sound_substitution"]
    alternates: list[Alternate]        # top 3 by sim_cal, after frequency floor

CandidateEntry.soundalike_alternates: list[Alternate] = []     # new explicit field
L1Result.hyphen_groups: list[str] = []
L4Result.alternate_form: str | None = None                      # 11th response key; contract version "7"
AnchorRelation.SOUND_SUBSTITUTION = "sound_substitution"        # surface evokes an absent alternate
AnchorRelation.SOUND_PAIR = "sound_pair"                        # both soundalikes present, juxtaposed
```

New settings go in `config.py`, with values fitted on the dev split rather than invented: `PHONETIC_TAU_RETRIEVE` (recall stage; the notes suggest raw 0.6–0.75), `PHONETIC_TAU_VERIFY` (decision stage, on sim_cal), `SOUNDALIKE_MAX_CANDIDATES` (default 4 terms × 3 alternates) and `PHONETIC_INDEL` (0.5).

### Layer-by-layer modifications

**L1 (`l1_surface.py`).** Add a second regex pass over the raw text for `[A-Za-z]+(?:-[A-Za-z]+)+`, and store the matches in `hyphen_groups`. Do not change `tokens`, so homograph behaviour stays byte-identical.

**L2 (`l2_senses.py`, `layers.run_l2`).** After `retrieve`, call `find_soundalikes` and append `senses_for(alt.form, term=surface, source=f"soundalike:{alt.form}")` for each alternate. Hyphen groups also go through `compound_splits` on the joined form ("catnap" → cat + nap), which lets the existing resegmentation machinery handle test text 3 without any phonetics. Add AoA lookups for alternates.

**L3 (`l3_candidates.py`).** Add `_soundalike(term, surface_senses, alt_senses, alternates)`, which reuses `_entry`. Contrast is 1 if the surface word's and the alternate's top lexnames differ, and balance uses the same smoothed counts. Score components gain `phonetic_sim`, `phonetic_sim_cal` and `soundalike=1.0`. Ordering within contrast ties uses sim_cal. The ranking stays age-free, as the module docstring requires. Soundalike entries get their own budget so they cannot push homograph candidates out of the default top 8.

**L4 (`l4_anchoring.py`, `prompts/l4_anchoring.md`, `validation.py`).** `_anchor_shortlist` adds each candidate's `soundalike_alternates` (form, sim_cal, mechanism) and the alternates' dictionary senses to `candidate_details`. The prompt gains a "Soundalike assessment" section with these rules: (a) a soundalike reading is valid only for a supplied alternate or one the model spells as ordinary words in `alternate_form`; (b) one quote must anchor the surface word's reading and a *different* quote must anchor the alternate's reading (for example "stop dating the cad" for *pursuing*, "the cat" for *purr*); (c) sharing a sound is not evidence. Line 34's prohibition stays for compound splits and gets a pointer to the new section. `validate_l4_response` gains these checks: for `sound_*` relations, `alternate_form` must be non-empty and must either match a supplied alternate or re-score locally at sim_cal ≥ τ_verify (otherwise `ModelResponseError`, which keeps the "no corrective request" policy); `sound_pair` requires both forms to occur in the text; and the existing distinct-quote rule applies. This stays one request.

**L5/L6 prompts.** Add the mechanism block to the prompt variables. Leave thresholds and weights unchanged, so homograph regressions stay comparable. An optional local diagnostic, not a gate until it is validated, implements the dual-support test the notes propose: target support Δ = log p_LM(s[p→t]) − log p_LM(s); a supporter-set Jaccard below 0.5 between the context words that best support each reading (a cheap proxy for Kao distinctiveness); and He et al.'s S_ratio = S_local/S_global > 1, where S(c) = −log[p(w_p|c)/p(w_a|c)] ([He et al. 2019](https://arxiv.org/pdf/1904.06828)). The notes flag this four-part test as their own proposal, not a published method.

**L0-post (`runner._l0_post_layer`, `l0_scope.py`, `decisions.py`, `enums.py`).** Add `has_soundalike` to `LayerEvidence`, set when L4 PASS has a `sound_*` relation. Insert a `SOUNDALIKE` row into `assign_scope_label`. The order is the open decision below: a single L4 choice means only one mechanism can be PASS, so the order matters only for diagnostics. In `detection_decision`, return `VALID_SOUNDALIKE_JOKE` for sound relations, and add that label to `detection_status_for`'s PUN set and to the "decided" set in `_l0_post_layer`. Bump `CANDIDATE_SEARCH_VERSION` to "5" and `RESPONSE_CONTRACT_VERSION` to "7", so `--resume` refuses old records.

**Call budget.** A completed positive still uses three LLM requests (L4, L5, L6). The phonetic work is local. Runtime cost is a one-time index build (seconds at k = 1; the notes estimate tens of seconds at k = 2, not measured) and, if adopted, a small local LM for the diagnostic.

## The three test texts exercise three different mechanisms

Everything in this section is a **design-time expectation, not a measured result**. The phonetic numbers are real outputs of the verification run, using the same method as `wlev_fixed.py`. The stage outcomes are predictions about a system that does not exist yet.

### "When the band broke up, it wasn't drama — it was just drum!"

| Stage | Expected behaviour |
|---|---|
| L0-pre / L1 | 59 chars; non-ASCII ratio 0.017 passes. DECLARATIVE. Tokens end `…wasn't, drama, it, was, just, drum`; the dash is dropped. |
| P2 finder | **In-text pair drum/drama: sim 0.890, sim_cal 0.591.** Lexicon/merge candidates: "just drum" ↔ *humdrum* 0.831 (drum ↔ humdrum 0.786); band ↔ *banned* 1.000 (an identical homophone with no contextual support). |
| L3 | Homograph candidates (band, broke up, drum, drama) plus a soundalike entry for drum with alternates {drama (in text), humdrum}. |
| L4 (expected) | Target `drum`, `sound_pair` with `drama`. Reading A, *drum* the percussion instrument, anchored by "the band". Reading B, *drama* as interpersonal conflict, anchored by "broke up". The punchline swaps the expected word for a near-soundalike that fits the band frame. |
| L5 / L6 | Declarative branch (threshold 0.25): borderline. The incongruity is a near-miss correction, not a double meaning of one word. L6 should pass, since the readings are distinct. |
| Expected outcome | Low-confidence PUN or RESOLUTION_FAIL. Both are defensible. |

There are three problems with this text. It is a juxtaposition joke: both soundalikes appear, so it does not test target recovery at all. The phonetic link is the weakest of the six pairs: its raw 0.890 falls between the 95th (0.851) and 99th (0.900) percentiles of random 5-phone pairs, so about 1–5% of random word pairs score as high. And the lexicon search will surface a competing reading, "it was just humdrum," which is arguably the more natural joke (the breakup was boring, not dramatic) and which only the merge path finds. A second risk is mechanism confusion. "broke up" is itself a WordNet multiword expression with literal (shatter) and idiomatic (disband) senses, so the existing homograph path could pick `broke up`, and the system would return VALID_HOMOGRAPH_JOKE for the wrong reason. The team should agree a gold label and gold mechanism before running this text, and should report all three findings.

### "Why did the cat stop dating the cad? Because she realized he was only purr-suing her for his own gain!"

| Stage | Expected behaviour |
|---|---|
| L0-pre / L1 | 102 chars, all ASCII. QA_RIDDLE (starts with "Why", contains "?"). Tokens contain `purr`, `suing` separately; the new `hyphen_groups` records `purr-suing`. |
| P2 finder | **Hyphen merge: purr-suing ↔ *pursuing* sim 1.000.** The phones are identical once stress is stripped (CMUdict purr P ER1, pursuing P ER0 S UW1 IH0 NG). Parts: purr (cat sound), suing (legal action); suing ↔ pursuing 0.900. **In-text pair cat/cad: sim 0.994.** |
| L4 (expected) | Target `purr-suing`, `sound_substitution`, alternate `pursuing`. *Pursuing* (romantically chasing) is anchored by "stop dating the cad". *Purr* (a cat's sound) is anchored by "the cat". |
| L5 / L6 | QA branch: answer relevance and agent fit should be high. L6 should find the meanings distinct. |
| Expected outcome | VALID_SOUNDALIKE_JOKE, with high design-time confidence. |

This is the cleanest test text and the best demonstration of instructor component (a). It also contains a built-in hard negative: cat/cad is the most similar in-text pair (0.994), yet cad simply means a dishonourable man and creates no incongruity. The design is right if it scores cat/cad, reports it, and does not select it. The text also has a third reading ("suing her for his own gain," a lawsuit for profit). CRACK's two-sense contract cannot represent a triple pun, so the third reading belongs in `reasoning`, and the limitation should be noted in the write-up.

### "Why did the cat start working at a bank? Because she wanted to turn her cat-nap into cash."

| Stage | Expected behaviour |
|---|---|
| L0-pre / L1 | 90 chars. QA_RIDDLE. Tokens contain `cat`, `nap`; `hyphen_groups` records `cat-nap`. |
| L2 (existing path, now reachable) | The joined form "catnap" (CMUdict K AE1 T N AE2 P) produces a compound split cat + nap through the existing `compound_splits`, if WordNet lists *catnap* as a lemma, which the team should check. |
| P2 finder | **In-text pair cat/cash: sim 0.954, sim_cal 0.827.** Lexicon neighbour catnap ↔ *kidnap* 0.980 (phone distance 2, so only the k = 2 index finds it). Split comparisons: catnap ↔ cash 0.727; nap ↔ cash 0.822. |
| L4 (expected) | Most likely `resegmentation` on `cat-nap`: the whole word means a short sleep, and the part "cat" is literally the protagonist. A `sound_substitution` reading via *kidnap* (ransom for cash) is a risk, because "working at a bank" does not support it. |
| Expected outcome | VALID_COMPOUND_SPLIT_JOKE, or a NON_PUN-type finding. VALID_SOUNDALIKE_JOKE via cat→cash is **not** expected. |

The instructor's framing suggests cat→cash, but both words are literal and co-referent: the cat wants cash, at a bank. Neither one evokes the other's meaning, so the pair fails the distinct-support test even though it scores 0.954. The honest submission reports the cat/cash similarity, as required, and explains why the mechanism is resegmentation, or the joke is weak, rather than a soundalike. If the instructor insists cat→cash is the pun, it is better described as alliteration-driven word association than as heterographic wordplay. The catnap/kidnap neighbour is the over-detection hazard to watch, because LLMs are documented to accept forced sound links ([Zangari et al. 2025](https://arxiv.org/html/2509.12158v2)).

## Minimal-pair data and honest baselines decide whether the extension works

### Seed positives (29) with phonetic scores and contamination flags

Items 1–25 (excluding 24) are the notes' drafts. Items P26–P30 are new drafts added here so that the set includes **imperfect** soundalikes: 19 of the notes' 24 pairs are identical homophones (sim 1.000), which would leave the graded metric almost untested. The sim values are verification-run outputs. "Folk" marks a widely circulated pun likely to be in LLM training data; keep those items as a separate "known" slice ([Zangari et al. 2025](https://arxiv.org/html/2509.12158v1)).

| # | Pun → target | Positive | sim | Flag |
|---|---|---|---|---|
| 1 | whey → way | The cheesemaker finally found a whey to retire early. | 1.000 | |
| 2 | knead → need | The bakers went on strike because they knead more money. | 1.000 | |
| 3 | sole → soul | The cobbler put his heart and sole into every boot. | 1.000 | idiom-based |
| 4 | mussel → muscle | The seafood chef pulled a mussel lifting the crate. | 1.000 | |
| 5 | cereal → serial | The breakfast thief turned out to be a cereal killer. | 1.000 | folk |
| 6 | pane → pain | The window installer said the job was a real pane. | 1.000 | |
| 7 | reel → real | The fisherman said his new rod was the reel deal. | 1.000 | |
| 8 | hare → hair | The magician got so mad he pulled his hare out. | 1.000 | published ([Kao et al.](https://escholarship.org/content/qt04j190sw/qt04j190sw_noSplash_4bd8b44a420e610268d1745e8a48a158.pdf)) |
| 9 | carrot → karat | The jeweler's rabbit only accepts 24-carrot gold. | 0.986 | |
| 10 | flours → flowers | The baker's garden is full of self-rising flours. | 1.000 | |
| 11 | lettuce → let us | Before dinner the salad chef said, "Lettuce pray." | 0.993 | folk; multi-word target |
| 12 | dyeing → dying | The textile worker said she was dyeing to try the new colors. | 1.000 | |
| 13 | mist → missed | The weatherman admitted he mist the forecast again. | 1.000 | |
| 14 | mourning → morning | The undertaker is never at his best in the mourning. | 1.000 | |
| 15 | tents → tense | The campers were nervous; it was a tents situation. | 0.900 | folk |
| 16 | seas → seize | The pirate captain always told his crew to seas the day. | 1.000 | |
| 17 | whale → wail | The orca's breakup song was one long whale. | 1.000 | |
| 18 | pier → peer | The young dockworkers gave in to pier pressure. | 1.000 | folk |
| 19 | knight → night | The royal guard slept all day because he worked the knight shift. | 1.000 | |
| 20 | toad → towed | The frog parked in a fire lane and got toad. | 1.000 | |
| 21 | board → bored | Old carpenters never die, they just get board. | 1.000 | SemEval shortcut template |
| 22 | ewe → you | The shepherd whispered to his flock, "I only have eyes for ewe." | 1.000 | function-word target |
| 23 | alleged → a ledge | "I'm halfway up a mountain," Tom alleged. | 0.917 | SemEval het_1; Tom Swifty template |
| 25 | propane → profane | When the church bought gas for their annual barbecue, proceeds went from the sacred to the propane. | 0.989 | SemEval item |
| P26 | yeast → least | The bread came out flat, but at yeast it was cheap. | 0.929 | new draft |
| P27 | tuna → tune | The fish choir couldn't carry a tuna. | 0.875 | new draft; extra syllable like drum/drama |
| P28 | wok → walk | The fired stir-fry cook was told to take a long wok. | 0.960 / 1.000 | new draft; depends on pronunciation variant |
| P29 | clothed → closed | The nudist beach was clothed for the winter. | 0.994 | new draft; pair from [Jaech et al.](https://aclanthology.org/N16-1079.pdf) |
| P30 | granite → granted | The quarry owner never takes his workers for granite. | 0.926 | new draft; pair from [Jaech et al.](https://aclanthology.org/N16-1079.pdf) |

The three instructor test texts form a separate slice and should not be counted in the 20.

### Hard negatives (39), typed by construction

Every negative is a minimal edit of a positive and contains a word with a soundalike, so P2 will fire on it. A correct system has to reject each one at L4–L6. The types follow the notes: **A** the pun word used literally; **B** the target substituted (canonical spelling, no second reading); **C** a context-word swap that removes the second sense ([Kao et al.](https://escholarship.org/content/qt04j190sw/qt04j190sw_noSplash_4bd8b44a420e610268d1745e8a48a158.pdf); [JOKER 2023](https://openreview.net/pdf/e286b85ce5de0d4a9dff894b9204fea796711d69.pdf)); **D** both soundalikes present literally; **E** a template-matched non-pun ([Zangari et al. 2025](https://arxiv.org/html/2509.12158v1)). Items marked "new" are drafted here; the rest are from the notes.

| Pair | Negative | Type |
|---|---|---|
| 1 | The cheesemaker drained the whey before pressing the curds. | A |
| 1 | The cheesemaker finally found a way to retire early. | B |
| 2 | The bakers knead the dough for ten minutes before shaping it. | A |
| 2 | The bakers went on strike because they need more money. | B |
| 3 | The cobbler glued a new sole onto every boot. | C |
| 4 | The seafood chef pulled a mussel from the crate of shellfish. | C |
| 5 | The breakfast thief turned out to be a cereal lover. | C |
| 6 | The window installer said the cracked pane was a real problem. | C |
| 7 | The fisherman said his new rod came with a spare reel. | C |
| 8 | The hare ran rapidly across the field. | A (Kao non-pun) |
| 9 | The jeweler's rabbit nibbled a carrot behind the shop. | A |
| 10 | The baker's pantry is full of self-rising flour. | C |
| 11 | Before dinner the salad chef said, "Let us pray." | B |
| 11 | Before dinner the salad chef washed the lettuce. | A |
| 12 | The textile worker spent the morning dyeing wool indigo blue. | A |
| 13 | The weatherman said a light mist will cover the valley at dawn. | A |
| 14 | The undertaker wore black throughout the mourning period. | A |
| 14 | The undertaker is never at his best in the morning. | B |
| 15 | The campers were nervous; they had only two tents. | C |
| 16 | The pirate captain sailed the seven seas for twenty years. | A |
| 17 | The orca's hunting trip ended with one long chase after a whale. | A |
| 18 | The young dockworkers tied the ferry to the pier. | A |
| 19 | The royal guard was made a knight after the battle. | A |
| 20 | The frog parked in a fire lane and got a ticket. | C |
| 21 | Old carpenters never die, they just train apprentices. | E |
| 21 | The carpenter cut the board into four shelves. | A |
| 22 | The shepherd sheared the old ewe last. | A |
| 23 | "I'm halfway up a mountain," Tom said. | E |
| 23 | "I'm standing on a ledge," Tom said. | D-like |
| 24 | She needs to knead the dough longer before it rises. | D (check that annotators do not read it as wordplay) |
| 25 | When the church bought gas for their annual barbecue, the propane cost more than expected. | C |
| P26 | The bread came out flat, but at least it was cheap. (new) | B |
| P27 | The fish choir couldn't carry a tune. (new) | B |
| P28 | The cook stir-fried the vegetables in a hot wok. (new) | A |
| P29 | The nudist beach was closed for the winter. (new) | B |
| P30 | The quarry owner cut the granite into kitchen counters. (new) | A |
| test 1 | The drummer quit the band after months of drama with the manager. (new; drummer/drama 0.890) | D |
| test 2 | Her cat hissed at the cad who kept bothering her. (new; cat/cad 0.994) | D |
| test 3 | The cat fell asleep next to the cash drawer at the bank. (new; cat/cash 0.954) | D |

Kao et al. found that their context-swap "de-puns" were rated funnier than plain non-puns. Any type C or D item can therefore remain an "almost pun." Two people should label every negative blind, and any item either of them reads as wordplay should be dropped ([Kao et al.](https://escholarship.org/content/qt04j190sw/qt04j190sw_noSplash_4bd8b44a420e610268d1745e8a48a158.pdf)). The notes found no published agreement rates for these negative types, so the team should measure its own (for example, Cohen's κ on 50 items). Store each item as `{id, text, label, pair_id, neg_type, pun_word, target_word, mechanism}`.

### Evaluation plan

Evaluate at four levels, each with a baseline that exposes shortcuts.

| Level | Data | Metric | Baseline that must be beaten |
|---|---|---|---|
| Phonetic metric (P1) | The six pairs; the 29 seed pairs; random-pair sample; optionally the PunGraph near-homophone table (760,311 pairs, [PunGraph repo](https://github.com/ysu132/PunGraph)) | Ordering of the six pairs; separation of homophone/near-homophone pairs from random pairs (ROC-AUC); ablation of binary costs (CHum-style 0/0.5/1, [Thaniserikaran & Harikrishnan 2026](https://aclanthology.org/2026.chum-1.6.pdf)) vs PanPhon graded vs ALINE | A binary phone match, which shows directly why non-binary costs matter |
| Candidate finding (P2) | Seed positives; SemEval het subtask-3 gold (target lemma = text before "%" in the second sense list, e.g. `office%1:06:00::`) | Recall@k of the gold target among retrieved alternates; mean alternates per item (PunGraph found about 30 candidates add noise) | k = 1 retrieval; last-word location baseline 0.5704 ([Miller et al. 2017](https://aclanthology.org/S17-2005.pdf)) |
| Detection (full pipeline) | Minimal-pair set (29 positives / 39 negatives); SemEval het 1,780, or the PunEval splits with no shared pun words ([punintended repo](https://github.com/alezanga/punintended)); PunBreak's 100 heterographic items | P/R/F1, balanced accuracy, **TNR per negative type**, paired accuracy (both members of a pair correct); coverage and accuracy over all items, matching CRACK's reporting | Always-pun (F1 0.833 on SemEval); "≥9 tokens OR Tom" (0.806); current CRACK with phonetics disabled; LLM-only alternate without verification |
| Regression | The existing 60-item project corpus | Exact classification and binary accuracy | The current 55/60 exact and 56/60 binary (README, October 4) must not drop |

Report SemEval results with Tom Swifty and "Old X never die" items split out, since those templates are almost always puns ([notes' archive analysis](https://alt.qcri.org/semeval2017/task7/data/uploads/semeval2017_task7.tar.xz); [Zangari et al. 2025](https://arxiv.org/html/2509.12158v1)). The repo's `scripts/prepare_semeval.py` builds only the homographic split, so it needs a heterographic option. With 29 positives, one flipped item moves accuracy by about 3 points, so the team should report counts, not just percentages.

## Build the phonetic core first and the LLM contract second

The first priority is the part that produces the submission's required numbers and nothing else depends on. Implement `phonetics/lexicon.py`, `phonetics/similarity.py` and `phonetics/calibration.py` with unit tests asserting the six-pair values above (to 3 decimals) and the name-aligned weight vector (tense = 0.25). This delivers the formulas, the six-pair table and the non-binary phone-cost evidence even if the rest slips. The second priority is the narrowest finder that covers all three test texts: in-text content-word pairs plus hyphen merge/split. That requires the `L1Result.hyphen_groups` change and the L2 hyphen-joined `compound_splits` call. The third is the contract work: `Alternate`/`SoundalikeCandidate` schemas, the L3 soundalike entries, the L4 prompt section with its validation checks, the new enums, and the L0-post mapping, with both version constants bumped together. That stage turns phonetic evidence into a VALID_SOUNDALIKE_JOKE and should land with offline tests that mock the provider, in the style of the existing `tests/test_l4.py`. The fourth is data: the 29/39 minimal-pair file, the heterographic SemEval preparation, and the evaluation script. Lexicon-neighbour search (the k ≤ 2 deletion index with a frequency floor, which needs a word-frequency dependency) comes fifth, because only unseen-target cases such as catnap/kidnap need it. The sixth stage is optional: LM noisy-channel re-ranking, DP resegmentation beyond hyphens, the curated-list union, and the dual-support diagnostic. Build these only if the evaluation shows L4 picking wrong alternates.

Seven decisions need a team answer before coding starts.

| Decision | Options | Recommendation |
|---|---|---|
| May L4 propose an alternate not in the supplied list? | Closed set only / free proposal verified locally | Free proposal with local verification at τ_verify. It keeps one request and recovers retrieval misses, which were 19% of failures in PunGraph |
| Does an in-text juxtaposition (drum/drama) count as soundalike wordplay? | Yes, as `sound_pair` / No, out of scope | Yes, but report it as a separate mechanism, because it does not test target recovery |
| Primary metric for the submission | Custom weighted Levenshtein / ALINE / bounded library score | Custom weighted Levenshtein as primary, with ALINE and the bounded score as comparison columns |
| Thresholds τ_retrieve, τ_verify | Fixed from the notes / fitted | Fit on a dev split of seed pairs plus random pairs. Start retrieval at raw ≥ 0.75 and verification at sim_cal around the random-pair 99th percentile, then tune |
| Separate shortlist budget for soundalikes | Share the top 8 / separate 4 × 3 | Separate, so homograph regressions stay comparable |
| Local language model for the diagnostic | None / distilgpt2 / masked-LM pseudo-likelihood ([Salazar et al. 2020](https://aclanthology.org/2020.acl-main.240)) | Defer. Add it only as a diagnostic after the core works |
| Dialect | CMUdict American only / add variants | Document the limit. CMUdict is American English, so pairs that depend on dialect mergers such as cot/caught are scored by CMUdict's listed pronunciations only |

## Conclusion

The research changes what "adding sound" to CRACK means. It is less a new detector than a new evidence source that CRACK's existing skepticism can audit. CRACK already refuses unquoted evidence, closed-set violations and retries for a favourable answer. Those same rules, extended to a phonetically verified `alternate_form`, are what the heterographic literature identifies as the fix for LLMs' weakest skill. The most informative experiment is therefore not SemEval F1, which a constant predictor nearly matches, but TNR on minimal-pair negatives that contain a real soundalike and no joke. The instructor's own test texts already include one such pair: cat/cad, the closest pair in any of the three texts and not a pun.

Two results should temper expectations. The phonetic metric is sound in its ranking but compressed in scale, and drum/drama scores no higher than the top 1–5% of random word pairs, so threshold choices will drive both false positives and misses more than the choice of metric will. And the test texts show that sound-based jokes often mix mechanisms (juxtaposition, resegmentation, alliteration), so a system that labels the mechanism correctly matters more than one that just says "pun." A design that reports the cat/cash score of 0.954 and still declines to call it the pun is the strongest evidence that the extension models incongruity rather than phonetic overlap.

*Verification note: phonetic values were reproduced on 2026-10-19 in a scratch virtual environment (panphon 0.22.2, cmudict) by running a copy of `/home/claude/research_notes/Phonetic pun detection design/wlev_fixed.py` plus small extensions for the test-text spans, the seed pairs and the random-pair calibration (1,500 pairs per length, seed 0). ALINE values are taken from the notes and were not re-run. The CRACK clone at `/home/claude/jyz922/crack` was only read; `git status` shows no changes.*
