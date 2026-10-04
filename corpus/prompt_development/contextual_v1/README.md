# Contextual-wordplay development cases v1

Twenty-four new project-authored cases for L6 given a target and two proposed
readings. Six word families form the 12-case development split; six other
families form the 12-case confirmation split. Each family has an intended
wordplay case and a literal control with an incidental second-domain cue.

Input files contain the text, genre, target, proposed meanings and exact quotes.
Annotation files separately contain expectations and rationale. All bytes and
family assignments are frozen in `manifest.json` before model inference.

These are provisional synthetic annotations. Independent human review is
pending. The confirmation split is separate by family and is run once after
the prompt is frozen; its outcomes do not guide revisions in this experiment.
It is not an independently human-labeled benchmark. No age expectations are
supplied, and these cases do not assess candidate retrieval or end-to-end CRACK.

Examples are never loaded into production prompts. Keep failures; publish a new
version rather than editing these files or replacing hard cases. The existing
60-item corpus and its gold remain separate and unchanged.

See the [fixed protocol](../../../experiments/contextual_wordplay/protocol.md)
and [comparison runner](../../../scripts/compare_contextual_wordplay.py).
