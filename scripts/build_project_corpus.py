"""Build the blind and gold JSONL files for the 60-item curated corpus."""

import json
from pathlib import Path

# 25 curated jokes with their genres, terms, senses, and developmental expectations
jokes = [
    {
        "id": "J01",
        "text": "Why don't skeletons fight? Because they have no guts.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "guts",
        "sense_a": "internal organs or viscera",
        "sense_b": "courage, bravery, or fortitude",
        "expected_age_verdict": {"6": "PARTIALLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J02",
        "text": "Autobiography: when your car starts telling you about its life.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_COMPOUND_SPLIT_JOKE",
        "genre": "DEFINITIONAL_ONELINER",
        "ambiguous_term": "autobiography",
        "sense_a": "a written account of one's own life",
        "sense_b": "auto (car) + biography (life story)",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J03",
        "text": "Why do elephants have a trunk? Because they don't have pockets to put stuff in.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "trunk",
        "sense_a": "the elongated nose of an elephant",
        "sense_b": "a large storage chest or luggage compartment",
        "expected_age_verdict": {"6": "PARTIALLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J04",
        "text": "Danny: You look awful, Gerry. What's wrong? Gerry: I've got a bad case of shingles. Danny: What did the doctor prescribe? Gerry: Aluminum siding.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DIALOGUE_MISUNDERSTANDING",
        "ambiguous_term": "shingles",
        "sense_a": "a painful viral skin condition",
        "sense_b": "flat rectangular tiles used to cover a roof",
        "expected_age_verdict": {"8": "SENSE_B_TOO_ADVANCED", "10": "PARTIALLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J05",
        "text": "Why do cows wear bells? Because their horns don't work.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "horns",
        "sense_a": "the bony pointed protrusions on an animal head",
        "sense_b": "an auditory warning signaling device on a vehicle",
        "expected_age_verdict": {"6": "PARTIALLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J06",
        "text": "Explain: to make the plain exit.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_COMPOUND_SPLIT_JOKE",
        "genre": "DEFINITIONAL_ONELINER",
        "ambiguous_term": "explain",
        "sense_a": "to clarify or make understandable",
        "sense_b": "ex (out) + plain (flat land)",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J07",
        "text": "Patient: Doctor, I keep thinking I'm a pair of curtains. Doctor: Pull yourself together!",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DIALOGUE_MISUNDERSTANDING",
        "ambiguous_term": "pull yourself together",
        "sense_a": "idiom meaning to regain emotional self-control",
        "sense_b": "physically drawing curtains closed side by side",
        "expected_age_verdict": {"6": "PARTIALLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J08",
        "text": "Why are trees like friendly dogs? Because they both have plenty of bark.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "bark",
        "sense_a": "the rough protective outer covering of a tree trunk",
        "sense_b": "the vocal acoustic sound emitted by a canine",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J09",
        "text": "Why do vampires love baseball? Because every player carries a wooden bat.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "bat",
        "sense_a": "a wooden club used to hit a baseball",
        "sense_b": "a nocturnal flying mammal",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J10",
        "text": "Why are fish so smart? Because they always live in schools.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "school",
        "sense_a": "an educational institution for learning",
        "sense_b": "a large swimming group of fish",
        "expected_age_verdict": {"6": "PARTIALLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J11",
        "text": "Customer: How was your blind date last night? Friend: Terrible, it was dried up and had a hard seed inside.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DIALOGUE_MISUNDERSTANDING",
        "ambiguous_term": "date",
        "sense_a": "a social romantic meeting between two individuals",
        "sense_b": "the sweet dried oblong fruit of a date palm",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J12",
        "text": "Why did the young lawyer pass the bar exam so easily? Because she spent every evening at the neighborhood bar.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "bar",
        "sense_a": "the legal profession qualification examination",
        "sense_b": "an establishment serving alcoholic beverages",
        "expected_age_verdict": {"8": "SENSE_B_TOO_ADVANCED", "10": "PARTIALLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J13",
        "text": "Mushroom: what a crowded family desperately needs when their tiny house runs out of living room.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_COMPOUND_SPLIT_JOKE",
        "genre": "DEFINITIONAL_ONELINER",
        "ambiguous_term": "mushroom",
        "sense_a": "an umbrella-shaped edible fungus",
        "sense_b": "mush (much) + room (spatial capacity)",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J14",
        "text": "Why was the electrician always reading newspapers? Because he wanted to keep in touch with current events.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "current",
        "sense_a": "present-day contemporary news events",
        "sense_b": "the flow of electric charge through a conductor",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J15",
        "text": "What did the blue ocean say to the friendly sailor standing on the shore? Nothing, it merely waved.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "wave",
        "sense_a": "a gesture of greeting made with a moving hand",
        "sense_b": "a ridge of water moving along the ocean surface",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J16",
        "text": "Camp Counselor: Did anyone bring a match to light the campfire? Camper: No, but I brought my boxing shorts for the championship match.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DIALOGUE_MISUNDERSTANDING",
        "ambiguous_term": "match",
        "sense_a": "a wooden stick tipped with combustible chemical for fire",
        "sense_b": "a competitive athletic sports contest",
        "expected_age_verdict": {"6": "PARTIALLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J17",
        "text": "Why was the postal mailbox overflowing with wisdom? Because it contained every letter in the alphabet.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "letter",
        "sense_a": "a written paper message sent through the mail",
        "sense_b": "a typographic symbol of the phonetic alphabet",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J18",
        "text": "Kidnap: the peaceful hour in the afternoon when a noisy toddler finally falls asleep.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_COMPOUND_SPLIT_JOKE",
        "genre": "DEFINITIONAL_ONELINER",
        "ambiguous_term": "kidnap",
        "sense_a": "an unlawful felony wherein a person is abducted",
        "sense_b": "kid (child) + nap (short daytime sleep)",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J19",
        "text": "Why was the school principal impressed by the optometrist office? Because every room was filled with bright pupils.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "pupil",
        "sense_a": "the dark circular opening in the center of the eye iris",
        "sense_b": "an intelligent school student in a classroom",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J20",
        "text": "The mattress company experienced soaring retail profits because spring had finally arrived.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DECLARATIVE",
        "ambiguous_term": "spring",
        "sense_a": "the temperate season following winter",
        "sense_b": "an elastic coiled metal wire providing mechanical support",
        "expected_age_verdict": {"6": "PARTIALLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J21",
        "text": "We couldn't imagine making a dog from wood bark.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DECLARATIVE",
        "ambiguous_term": "bark",
        "sense_a": "the vocal acoustic noise of a canine",
        "sense_b": "the outer wooden layer of a tree branch",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J22",
        "text": "The teacher said it was the annual sports day. I asked if I can skip.",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DECLARATIVE",
        "ambiguous_term": "skip",
        "sense_a": "to bound lightly hopping on alternate feet",
        "sense_b": "to omit or intentionally bypass an event",
        "expected_age_verdict": {"6": "PARTIALLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J23",
        "text": "The fishermen are calculating the net loss.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DECLARATIVE",
        "ambiguous_term": "net",
        "sense_a": "a mesh woven fabric used for catching aquatic fish",
        "sense_b": "financial remainder value after deductions",
        "expected_age_verdict": {"8": "SENSE_B_TOO_ADVANCED", "10": "PARTIALLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J24",
        "text": "How many stories were in the library building?",
        "target_ages": [6, 8, 10],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DECLARATIVE",
        "ambiguous_term": "stories",
        "sense_a": "narrative fictional book accounts",
        "sense_b": "horizontal floor levels of an architectural building",
        "expected_age_verdict": {"6": "PARTIALLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "J25",
        "text": "The dump was so full it had to refuse more refuse.",
        "target_ages": [8, 10, 12],
        "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DECLARATIVE",
        "ambiguous_term": "refuse",
        "sense_a": "to decline or reject acceptance",
        "sense_b": "discarded municipal waste and garbage",
        "expected_age_verdict": {"8": "SENSE_B_TOO_ADVANCED", "10": "PARTIALLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    }
]

# 25 strictly matched de-joked negative versions (D01-D25)
dejoked = [
    {
        "id": "D01",
        "text": "Why don't skeletons fight? Because they are dead bone structures lacking muscles.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "muscles",
        "sense_a": "anatomical tissue facilitating bodily movement",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D02",
        "text": "Autobiography: a non-fiction book that an author publishes documenting their personal life history.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DEFINITIONAL_ONELINER",
        "ambiguous_term": "autobiography",
        "sense_a": "biographical account of someone written by oneself",
        "sense_b": "",
        "expected_age_verdict": {"8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D03",
        "text": "Why do elephants have a trunk? Because the car's trunk was already full.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "trunk",
        "sense_a": "storage compartment of an automobile",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D04",
        "text": "Danny: You look unwell, Gerry. What's wrong? Gerry: I've got shingles. Danny: What did the doctor prescribe? Gerry: Antiviral prescription ointment.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DIALOGUE_MISUNDERSTANDING",
        "ambiguous_term": "shingles",
        "sense_a": "viral medical skin rash condition",
        "sense_b": "",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D05",
        "text": "Why do dairy cows wear bells? Because their bells jingle to help farmers locate them in pasture.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "bells",
        "sense_a": "acoustic ringing instrument hung from a collar",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D06",
        "text": "Explain: to define words and ideas clearly so listeners understand.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DEFINITIONAL_ONELINER",
        "ambiguous_term": "explain",
        "sense_a": "to clarify concept or logic",
        "sense_b": "",
        "expected_age_verdict": {"8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D07",
        "text": "Patient: Doctor, I feel anxious before speaking. Doctor: Pull yourself together and take deep breaths.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DIALOGUE_MISUNDERSTANDING",
        "ambiguous_term": "pull yourself together",
        "sense_a": "regain emotional composure",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D08",
        "text": "Why do oak trees grow thick bark? Because the rough bark seals moisture and shields tree layers.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "bark",
        "sense_a": "botanical bark of tree",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D09",
        "text": "Why do baseball hitters grip a bat? Because the wooden bat transfers kinetic power to the baseball.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "bat",
        "sense_a": "baseball club instrument",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D10",
        "text": "Why do marine salmon swim in schools? Because a large school offers collective protection against predators.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "school",
        "sense_a": "group of swimming fish",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D11",
        "text": "Customer: What is the current calendar date today? Friend: Today is the twentieth of October.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DIALOGUE_MISUNDERSTANDING",
        "ambiguous_term": "date",
        "sense_a": "calendar day of month",
        "sense_b": "",
        "expected_age_verdict": {"8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D12",
        "text": "Why did the defense attorney study court precedent? Because she needed to represent her client before the judge.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "attorney",
        "sense_a": "legal lawyer representative",
        "sense_b": "",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D13",
        "text": "Mushroom: an earthy organism with a rounded cap that sprouts in moist soil and decaying timber.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DEFINITIONAL_ONELINER",
        "ambiguous_term": "mushroom",
        "sense_a": "fungus plant structure",
        "sense_b": "",
        "expected_age_verdict": {"8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D14",
        "text": "Why did the electrical technician replace the breaker? Because the alternating current exceeded safe amperage limits.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "current",
        "sense_a": "electrical flow of charge",
        "sense_b": "",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D15",
        "text": "What happened to the coastline during the stormy weather? A towering water wave pounded the concrete pier.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "wave",
        "sense_a": "ocean water swell",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D16",
        "text": "Camp Counselor: Did anyone bring matches for the fire? Camper: Yes, I carry safety matches in my backpack.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DIALOGUE_MISUNDERSTANDING",
        "ambiguous_term": "match",
        "sense_a": "combustible fire starting stick",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D17",
        "text": "Why was the metal mail carrier sack packed? Because the postal worker collected eighty paper letters.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "letter",
        "sense_a": "postal correspondence message",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D18",
        "text": "Kidnap: an unlawful felony wherein a victim is seized against their will for ransom.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DEFINITIONAL_ONELINER",
        "ambiguous_term": "kidnap",
        "sense_a": "abduction crime",
        "sense_b": "",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D19",
        "text": "Why did the eye surgeon examine the cornea? To measure light entering the pupil of the patient.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "QA_RIDDLE",
        "ambiguous_term": "pupil",
        "sense_a": "ocular anatomical aperture",
        "sense_b": "",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D20",
        "text": "The mattress company experienced soaring retail profits because seasonal discounts had arrived.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "profits",
        "sense_a": "financial business gain",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D21",
        "text": "We couldn't imagine making a dog from bricks and cement.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "cement",
        "sense_a": "mineral building adhesive",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D22",
        "text": "The teacher said it was the annual sports day. I asked what time it started.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "sports",
        "sense_a": "athletic games",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D23",
        "text": "The fishermen are calculating how many fish they caught.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "fishermen",
        "sense_a": "individuals catching fish",
        "sense_b": "",
        "expected_age_verdict": {"8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D24",
        "text": "How many stories were in the library building? I think five floors.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "floors",
        "sense_a": "architectural storeys",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "D25",
        "text": "The dump was so full it had to close early for the day.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "dump",
        "sense_a": "municipal landfill site",
        "sense_b": "",
        "expected_age_verdict": {"8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    }
]

# 10 definite, unambiguous non-jokes (N01-N10)
nonjokes = [
    {
        "id": "N01",
        "text": "The elephant used its trunk to pick up leaves.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "trunk",
        "sense_a": "elongated nasal proboscis of an elephant",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "N02",
        "text": "The steep river bank was covered with green moss and wet stones.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "bank",
        "sense_a": "sloping land bordering a river channel",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "N03",
        "text": "The baseball player swung the wooden bat and sprinted toward first base.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "bat",
        "sense_a": "wooden sports bat for hitting a ball",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "N04",
        "text": "She folded the handwritten letter and slipped it into the postage envelope.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "letter",
        "sense_a": "written postal correspondence message",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "N05",
        "text": "The guard dog barked loudly as soon as strangers approached the fence gate.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "barked",
        "sense_a": "vocal canine sound",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "N06",
        "text": "He bought a package of sweet dried dates at the grocery store for dessert.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "dates",
        "sense_a": "sweet edible palm fruit",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "N07",
        "text": "The librarian stacked the history books neatly onto the oak shelves.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "shelves",
        "sense_a": "horizontal planks used to hold objects",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "N08",
        "text": "The laboratory technician calibrated the digital microscope before starting the experiment.",
        "target_ages": [8, 10, 12],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "microscope",
        "sense_a": "optical magnifying instrument for scientific analysis",
        "sense_b": "",
        "expected_age_verdict": {"8": "PARTIALLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE", "12": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "N09",
        "text": "A sudden rain shower passed over the valley during the early afternoon.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "shower",
        "sense_a": "brief rainfall precipitation",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    },
    {
        "id": "N10",
        "text": "The passengers waited quietly at the platform for the morning commuter train.",
        "target_ages": [6, 8, 10],
        "gold_label": "ONE_SENSE_ONLY",
        "genre": "DECLARATIVE",
        "ambiguous_term": "train",
        "sense_a": "railway locomotive and attached passenger cars",
        "sense_b": "",
        "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}
    }
]

def main() -> None:
    all_items = jokes + dejoked + nonjokes
    print(f"Total items: {len(all_items)} (25 jokes + 25 de-joked pairs + 10 non-jokes)")

    corpus_dir = Path(__file__).resolve().parents[1] / "corpus"
    blind_path = corpus_dir / "joke_corpus_blind.jsonl"
    gold_path = corpus_dir / "joke_corpus_gold.jsonl"

    with blind_path.open("w", encoding="utf-8") as fb:
        for item in all_items:
            blind_entry = {
                "id": item["id"],
                "text": item["text"],
                "target_ages": item["target_ages"]
            }
            fb.write(json.dumps(blind_entry, ensure_ascii=False) + "\n")

    with gold_path.open("w", encoding="utf-8") as fg:
        for item in all_items:
            gold_entry = {
                "id": item["id"],
                "gold_label": item["gold_label"],
                "genre": item["genre"],
                "ambiguous_term": item["ambiguous_term"],
                "sense_a": item["sense_a"],
                "sense_b": item["sense_b"],
                "expected_age_verdict": item["expected_age_verdict"]
            }
            fg.write(json.dumps(gold_entry, ensure_ascii=False) + "\n")

    print(f"Successfully wrote {blind_path} and {gold_path}")


if __name__ == "__main__":
    main()
