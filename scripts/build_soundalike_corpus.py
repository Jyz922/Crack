"""Build the soundalike evaluation corpus (workstream 04) from one table.

Writes corpus/soundalike_items.jsonl (per-item metadata), and the blind/gold
pair corpus/soundalike_blind.jsonl / corpus/soundalike_gold.jsonl in the format
crack.corpus.load_blind / load_gold expect. Items come from the drafts in
docs/soundalike/design.md ("Seed positives", "Hard negatives").

Labels here are the AUTHORING labels. They are not yet validated: the
acceptance rule is blind double labelling by two people, dropping any item
either labeller reads differently (see docs/soundalike/labelling/README.md).

Slices:
  seed       original drafts; the instructor's >= 20 / >= 20 counts come from here
  known      widely circulated, published or SemEval-derived puns (likely in LLM
             training data) and the negatives built from them; reported separately
  test_text  the three instructor test texts and their negatives; not counted

Negative types: A pun word used literally; B target substituted (canonical
spelling, no second reading); C context-word swap removing the second sense;
D both soundalikes present literally; E template-matched non-pun.

    py -3.11 scripts/build_soundalike_corpus.py
"""
from __future__ import annotations

import json
from pathlib import Path

from crack.l1_surface import route_genre

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"

# id, text, pun_word, target_word, mechanism, slice, sense_a (pun word), sense_b (target), note
POSITIVES = [
    ("S01", "The cheesemaker finally found a whey to retire early.", "whey", "way", "sound_substitution", "seed", "watery liquid left after curdling milk", "a method or means", ""),
    ("S02", "The bakers went on strike because they knead more money.", "knead", "need", "sound_substitution", "seed", "to work dough with the hands", "to require", ""),
    ("S03", "The cobbler put his heart and sole into every boot.", "sole", "soul", "sound_substitution", "seed", "the bottom part of a shoe", "a person's inner spirit", "idiom-based"),
    ("S04", "The seafood chef pulled a mussel lifting the crate.", "mussel", "muscle", "sound_substitution", "seed", "an edible shellfish", "body tissue that can be strained", ""),
    ("S05", "The breakfast thief turned out to be a cereal killer.", "cereal", "serial", "sound_substitution", "known", "a breakfast grain food", "repeated in a series (serial killer)", "folk"),
    ("S06", "The window installer said the job was a real pane.", "pane", "pain", "sound_substitution", "seed", "a sheet of window glass", "something annoying (a real pain)", ""),
    ("S07", "The fisherman said his new rod was the reel deal.", "reel", "real", "sound_substitution", "seed", "a spool on a fishing rod", "genuine (the real deal)", ""),
    ("S08", "The magician got so mad he pulled his hare out.", "hare", "hair", "sound_substitution", "known", "a rabbit-like animal", "hair on the head (pull one's hair out)", "published (Kao et al.)"),
    ("S09", "The jeweler's rabbit only accepts 24-carrot gold.", "carrot", "karat", "sound_substitution", "seed", "an orange root vegetable", "a unit of gold purity", ""),
    ("S10", "The baker's garden is full of self-rising flours.", "flours", "flowers", "sound_substitution", "seed", "ground grain used in baking", "plants that bloom", ""),
    ("S11", "Before dinner the salad chef said, \"Lettuce pray.\"", "lettuce", "let us", "sound_substitution", "known", "a leafy salad vegetable", "let us (an invitation to pray)", "folk; multi-word target"),
    ("S12", "The textile worker said she was dyeing to try the new colors.", "dyeing", "dying", "sound_substitution", "seed", "colouring fabric", "eager (dying to try)", ""),
    ("S13", "The weatherman admitted he mist the forecast again.", "mist", "missed", "sound_substitution", "seed", "light fog", "failed to get right", ""),
    ("S14", "The undertaker is never at his best in the mourning.", "mourning", "morning", "sound_substitution", "seed", "grieving for the dead", "early part of the day", ""),
    ("S15", "The campers were nervous; it was a tents situation.", "tents", "tense", "sound_substitution", "known", "portable shelters", "nervous and strained", "folk; imperfect soundalike"),
    ("S16", "The pirate captain always told his crew to seas the day.", "seas", "seize", "sound_substitution", "seed", "large bodies of salt water", "to grab (seize the day)", ""),
    ("S17", "The orca's breakup song was one long whale.", "whale", "wail", "sound_substitution", "seed", "a large sea mammal", "a long mournful cry", ""),
    ("S18", "The young dockworkers gave in to pier pressure.", "pier", "peer", "sound_substitution", "known", "a platform built out over water", "a person of the same age (peer pressure)", "folk"),
    ("S19", "The royal guard slept all day because he worked the knight shift.", "knight", "night", "sound_substitution", "seed", "a mounted soldier of noble rank", "the time of darkness (night shift)", ""),
    ("S20", "The frog parked in a fire lane and got toad.", "toad", "towed", "sound_substitution", "seed", "a frog-like amphibian", "hauled away by a tow truck", ""),
    ("S21", "Old carpenters never die, they just get board.", "board", "bored", "sound_substitution", "known", "a flat piece of wood", "weary from lack of interest", "SemEval 'never die' template"),
    ("S22", "The shepherd whispered to his flock, \"I only have eyes for ewe.\"", "ewe", "you", "sound_substitution", "seed", "a female sheep", "the person addressed", "function-word target"),
    ("S23", "\"I'm halfway up a mountain,\" Tom alleged.", "alleged", "a ledge", "sound_substitution", "known", "claimed without proof", "a narrow shelf of rock", "SemEval het_1; Tom Swifty"),
    ("S25", "When the church bought gas for their annual barbecue, proceeds went from the sacred to the propane.", "propane", "profane", "sound_substitution", "known", "a gas fuel", "secular, the opposite of sacred", "SemEval item"),
    ("S26", "The bread came out flat, but at yeast it was cheap.", "yeast", "least", "sound_substitution", "seed", "a fungus that makes bread rise", "at least (anyway)", "imperfect soundalike"),
    ("S27", "The fish choir couldn't carry a tuna.", "tuna", "tune", "sound_substitution", "seed", "a large ocean fish", "a melody (carry a tune)", "imperfect; extra syllable"),
    ("S28", "The fired stir-fry cook was told to take a long wok.", "wok", "walk", "sound_substitution", "seed", "a round cooking pan", "to leave (take a long walk)", "pronunciation-variant dependent"),
    ("S29", "The nudist beach was clothed for the winter.", "clothed", "closed", "sound_substitution", "seed", "wearing clothes", "not open", "imperfect soundalike"),
    ("S30", "The quarry owner never takes his workers for granite.", "granite", "granted", "sound_substitution", "seed", "a hard igneous rock", "taken for granted (unappreciated)", "imperfect soundalike"),
    # Spares drafted 2026-10-21 so the seed slice stays >= 20 after labellers drop items.
    ("S31", "The beekeeper's sign on the hive said, \"Bee right back.\"", "bee", "be", "sound_substitution", "seed", "a honey-making insect", "be (be right back)", "spare"),
    ("S32", "The vineyard owner said this year's harvest tasted grape.", "grape", "great", "sound_substitution", "seed", "a fruit used for wine", "very good", "spare; imperfect soundalike"),
    ("S33", "The fishmonger told the greedy customer not to be so shellfish.", "shellfish", "selfish", "sound_substitution", "seed", "edible sea creatures with shells", "caring only about oneself", "spare; imperfect soundalike"),
    ("S34", "The retired tailor says life is sew much calmer now.", "sew", "so", "sound_substitution", "seed", "to stitch with needle and thread", "so (very)", "spare"),
]

# id, text, pair_id, neg_type, word (soundalike present), literal sense, note
NEGATIVES = [
    ("N01", "The cheesemaker drained the whey before pressing the curds.", "S01", "A", "whey", "watery liquid left after curdling milk", ""),
    ("N02", "The cheesemaker finally found a way to retire early.", "S01", "B", "way", "a method or means", ""),
    ("N03", "The bakers knead the dough for ten minutes before shaping it.", "S02", "A", "knead", "to work dough with the hands", ""),
    ("N04", "The bakers went on strike because they need more money.", "S02", "B", "need", "to require", ""),
    ("N05", "The cobbler glued a new sole onto every boot.", "S03", "C", "sole", "the bottom part of a shoe", ""),
    ("N06", "The seafood chef pulled a mussel from the crate of shellfish.", "S04", "C", "mussel", "an edible shellfish", ""),
    ("N07", "The breakfast thief turned out to be a cereal lover.", "S05", "C", "cereal", "a breakfast grain food", ""),
    ("N08", "The window installer said the cracked pane was a real problem.", "S06", "C", "pane", "a sheet of window glass", ""),
    ("N09", "The fisherman said his new rod came with a spare reel.", "S07", "C", "reel", "a spool on a fishing rod", ""),
    ("N10", "The hare ran rapidly across the field.", "S08", "A", "hare", "a rabbit-like animal", "Kao et al. non-pun"),
    ("N11", "The jeweler's rabbit nibbled a carrot behind the shop.", "S09", "A", "carrot", "an orange root vegetable", ""),
    ("N12", "The baker's pantry is full of self-rising flour.", "S10", "C", "flour", "ground grain used in baking", ""),
    ("N13", "Before dinner the salad chef said, \"Let us pray.\"", "S11", "B", "let us", "an invitation to pray", ""),
    ("N14", "Before dinner the salad chef washed the lettuce.", "S11", "A", "lettuce", "a leafy salad vegetable", ""),
    ("N15", "The textile worker spent the morning dyeing wool indigo blue.", "S12", "A", "dyeing", "colouring fabric", ""),
    ("N16", "The weatherman said a light mist will cover the valley at dawn.", "S13", "A", "mist", "light fog", ""),
    ("N17", "The undertaker wore black throughout the mourning period.", "S14", "A", "mourning", "grieving for the dead", ""),
    ("N18", "The undertaker is never at his best in the morning.", "S14", "B", "morning", "early part of the day", ""),
    ("N19", "The campers were nervous; they had only two tents.", "S15", "C", "tents", "portable shelters", ""),
    ("N20", "The pirate captain sailed the seven seas for twenty years.", "S16", "A", "seas", "large bodies of salt water", ""),
    ("N21", "The orca's hunting trip ended with one long chase after a whale.", "S17", "A", "whale", "a large sea mammal", ""),
    ("N22", "The young dockworkers tied the ferry to the pier.", "S18", "A", "pier", "a platform built out over water", ""),
    ("N23", "The royal guard was made a knight after the battle.", "S19", "A", "knight", "a mounted soldier of noble rank", ""),
    ("N24", "The frog parked in a fire lane and got a ticket.", "S20", "C", "frog", "an amphibian", ""),
    ("N25", "Old carpenters never die, they just train apprentices.", "S21", "E", "carpenters", "woodworkers", "SemEval template, no pun"),
    ("N26", "The carpenter cut the board into four shelves.", "S21", "A", "board", "a flat piece of wood", ""),
    ("N27", "The shepherd sheared the old ewe last.", "S22", "A", "ewe", "a female sheep", ""),
    ("N28", "\"I'm halfway up a mountain,\" Tom said.", "S23", "E", "Tom", "a person's name", "Tom Swifty template, no pun"),
    ("N29", "\"I'm standing on a ledge,\" Tom said.", "S23", "B", "ledge", "a narrow shelf of rock", "design: D-like"),
    ("N30", "She needs to knead the dough longer before it rises.", "S02", "D", "knead", "to work dough with the hands", "both soundalikes literal; design pair 24"),
    ("N31", "When the church bought gas for their annual barbecue, the propane cost more than expected.", "S25", "C", "propane", "a gas fuel", ""),
    ("N32", "The bread came out flat, but at least it was cheap.", "S26", "B", "least", "at least (anyway)", ""),
    ("N33", "The fish choir couldn't carry a tune.", "S27", "B", "tune", "a melody", ""),
    ("N34", "The cook stir-fried the vegetables in a hot wok.", "S28", "A", "wok", "a round cooking pan", ""),
    ("N35", "The nudist beach was closed for the winter.", "S29", "B", "closed", "not open", ""),
    ("N36", "The quarry owner cut the granite into kitchen counters.", "S30", "A", "granite", "a hard igneous rock", ""),
    ("N37", "The beekeeper's sign on the hive said, \"Be right back.\"", "S31", "B", "be", "to exist (be right back)", "spare"),
    ("N38", "The vineyard owner said this year's grape harvest was large.", "S32", "A", "grape", "a fruit used for wine", "spare"),
    ("N39", "The fishmonger told the customer the shellfish was fresh today.", "S33", "A", "shellfish", "edible sea creatures with shells", "spare"),
    ("N40", "The retired tailor still likes to sew curtains for friends.", "S34", "A", "sew", "to stitch with needle and thread", "spare"),
]

TEST_POSITIVES = [
    ("T1", "When the band broke up, it wasn’t drama — it was just drum!", "drum", "drama", "sound_pair", "VALID_SOUNDALIKE_JOKE", "a percussion instrument", "emotional conflict between people", "team decision: sound_pair counts"),
    ("T2", "Why did the cat stop dating the cad? Because she realized he was only purr-suing her for his own gain!", "purr-suing", "pursuing", "sound_substitution", "VALID_SOUNDALIKE_JOKE", "purring like a cat", "romantically chasing", "cat/cad is an in-text hard negative"),
    ("T3", "Why did the cat start working at a bank? Because she wanted to turn her cat-nap into cash.", "cat-nap", "cat + nap", "resegmentation", "VALID_COMPOUND_SPLIT_JOKE", "a short light sleep", "the cat's own nap", "resegmentation, not a cat/cash soundalike"),
]
TEST_NEGATIVES = [
    ("TN1", "The drummer quit the band after months of drama with the manager.", "T1", "D", "drama", "emotional conflict", "drummer/drama literal"),
    ("TN2", "Her cat hissed at the cad who kept bothering her.", "T2", "D", "cad", "a dishonourable man", "cat/cad literal"),
    ("TN3", "The cat fell asleep next to the cash drawer at the bank.", "T3", "D", "cash", "money", "cat/cash literal"),
]


def build() -> list[dict]:
    items = []
    for i, text, pun, target, mech, slc, sa, sb, note in POSITIVES:
        items.append(dict(id=i, text=text, label="VALID_SOUNDALIKE_JOKE", pair_id=None, neg_type=None,
                          pun_word=pun, target_word=target, mechanism=mech, slice=slc,
                          sense_a=sa, sense_b=sb, note=note))
    pos_slice = {p[0]: p[5] for p in POSITIVES}
    for i, text, pair, typ, word, sense, note in NEGATIVES:
        items.append(dict(id=i, text=text, label="ONE_SENSE_ONLY", pair_id=pair, neg_type=typ,
                          pun_word=word, target_word=None, mechanism=None, slice=pos_slice[pair],
                          sense_a=sense, sense_b="", note=note))
    for i, text, pun, target, mech, label, sa, sb, note in TEST_POSITIVES:
        items.append(dict(id=i, text=text, label=label, pair_id=None, neg_type=None, pun_word=pun,
                          target_word=target, mechanism=mech, slice="test_text", sense_a=sa, sense_b=sb, note=note))
    for i, text, pair, typ, word, sense, note in TEST_NEGATIVES:
        items.append(dict(id=i, text=text, label="ONE_SENSE_ONLY", pair_id=pair, neg_type=typ, pun_word=word,
                          target_word=None, mechanism=None, slice="test_text", sense_a=sense, sense_b="", note=note))
    return items


def write(items: list[dict]) -> None:
    def dump(path: Path, rows: list[dict]) -> None:
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    dump(CORPUS / "soundalike_items.jsonl", items)
    dump(CORPUS / "soundalike_blind.jsonl", [{"id": r["id"], "text": r["text"], "target_ages": []} for r in items])
    dump(CORPUS / "soundalike_gold.jsonl", [{
        "id": r["id"], "gold_label": r["label"], "genre": route_genre(r["text"]).value,
        "ambiguous_term": r["pun_word"], "sense_a": r["sense_a"], "sense_b": r["sense_b"],
        "expected_age_verdict": {},
    } for r in items])


if __name__ == "__main__":
    rows = build()
    write(rows)
    by = lambda slc, pos: sum(1 for r in rows if r["slice"] == slc and (r["neg_type"] is None) == pos)
    for slc in ("seed", "known", "test_text"):
        print(f"{slc:10s} positives={by(slc, True):2d} negatives={by(slc, False):2d}")
