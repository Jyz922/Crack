# Homepage example validation

The homepage offers four examples of same-spelling wordplay and one explicitly
labeled literal control. These are demonstration inputs, not a held-out accuracy
benchmark. Expected labels and target words are evaluation data only. Every
click still sends just the text and selected age through the ordinary pipeline;
there are no preset-specific answers, target hints or additional model calls.

## October 4, 2026 check

The configured OpenAI backend (`gpt-6-luna`) evaluated the actual homepage
definitions twice. All ten classifications and target-word checks passed.
The returned readings were also inspected.

| Example | Expected result | Target and readings | Round 1 | Round 2 |
|---|---|---|---|---|
| “I used to be a banker, but I lost interest.” | PUN | `interest`: enthusiasm / financial interest | PASS | PASS |
| “What has keys but no locks? A piano.” | PUN | `keys`: lock keys / piano keys | PASS | PASS |
| “Why don't skeletons fight? Because they have no guts.” | PUN | `guts`: internal organs / courage | PASS | PASS |
| “Why do elephants have a trunk? Because they don't have pockets to put stuff in.” | PUN | `trunk`: elephant's snout / storage container | PASS | PASS |
| “The quick brown fox jumps over the lazy dog.” | NON_PUN | Literal control; no selected punchline | PASS | PASS |

The local run is saved under
`runs/web_examples/20261005T023714.992683Z/` (UTC timestamp). This check covers
detection and target selection, not agreement with measured child comprehension.
The first `trunk` run left age-8 comprehension UNKNOWN; the second assessed it.
Both detected the wordplay correctly. The UI retains that age uncertainty.

Two earlier examples were removed because they did not give accurate demos of
the current supported mechanism. “7 ate 9” depends on `ate/eight`, while
“impasta” depends on a differently spelled soundalike. The initial live check
rejected the former and incorrectly selected `fake` as a homographic target for
the latter. Removing these presets does not repair the detector's general
handling of sound-based jokes; that semantic limitation remains. This change
does not broaden scope or alter prompts, thresholds, validation or recovery.

## Recheck the examples

This command reads the definitions directly from the homepage and makes fresh
provider requests. It checks both detection status and the selected target,
saves the complete payloads, and returns a nonzero exit status on a mismatch.

```bash
python scripts/validate_web_examples.py --repeat 2
```

Use a fresh run after changing examples, prompts or provider configuration.
Two passing rounds establish this observed regression result, not a guarantee
that future model responses will always match.
