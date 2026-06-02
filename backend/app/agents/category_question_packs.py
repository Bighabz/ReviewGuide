"""
Category question packs (Outcome 4, conversational engine roadmap).

Curated specialist question sets for the top ~20 product categories. When the
clarifier knows the category, the matching pack is injected into the question-
generation prompt as the authoritative example — so a mattress shopper always
gets "How do you usually sleep?" and realistic mattress price brackets, not
whatever the LLM improvises. Unlisted categories keep the generic expert
framing and generalize via the LLM.

Each pack:
    aliases:          strings the category slot may arrive as (singular forms,
                      synonyms); the pack key itself always matches
    use_case:         the lead question a specialist in that department asks
    features:         the category's most differentiating spec/preference
                      question; multi_select=True when several answers can
                      apply at once
    budget_brackets:  realistic price brackets for that category's market

The clarifier still runs its LLM call (for contextual intro/closing and to skip
already-answered slots) — the pack anchors WHAT gets asked, not whether.
"""
from typing import Any, Dict, Optional

CATEGORY_QUESTION_PACKS: Dict[str, Dict[str, Any]] = {
    "laptops": {
        "aliases": ["laptop", "notebook", "notebooks", "ultrabook", "macbook"],
        "use_case": {
            "question": "What will you mainly use it for?",
            "options": ["Student / everyday", "Gaming", "Creative / video editing", "Business / office"],
        },
        "features": {
            "question": "What performance level do you need?",
            "options": ["Just the basics", "Mid-range power", "High-end specs", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $500", "$500–$800", "$800–$1,200", "$1,200+"],
    },
    "phones": {
        "aliases": ["phone", "smartphone", "smartphones", "iphone", "android phone", "cell phone", "mobile phone"],
        "use_case": {
            "question": "What matters most to you day to day?",
            "options": ["Camera", "Battery life", "Gaming / performance", "Just the basics"],
        },
        "features": {
            "question": "Do you have a platform preference?",
            "options": ["iPhone / iOS", "Android / Samsung", "Android / Pixel", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $300", "$300–$600", "$600–$1,000", "$1,000+"],
    },
    "tvs": {
        "aliases": ["tv", "television", "televisions", "smart tv", "oled tv", "4k tv"],
        "use_case": {
            "question": "What will you watch most?",
            "options": ["Movies & shows", "Sports", "Gaming", "Everyday TV"],
        },
        "features": {
            "question": "What size are you thinking?",
            "options": ["43–50 inch", "55–65 inch", "75 inch or larger", "Not sure yet"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $400", "$400–$800", "$800–$1,500", "$1,500+"],
    },
    "headphones": {
        "aliases": ["headphone", "earbuds", "earbud", "earphones", "headsets", "headset"],
        "use_case": {
            "question": "Where will you use them most?",
            "options": ["Commute & travel", "Gym & runs", "At a desk", "Studio"],
        },
        "features": {
            "question": "Which features matter to you?",
            "options": ["Noise cancelling", "Wireless", "Over-ear", "In-ear", "No strong preference"],
            "multi_select": True,
        },
        "budget_brackets": ["Under $100", "$100–$250", "$250–$400", "$400+"],
    },
    "mattresses": {
        "aliases": ["mattress", "bed", "beds"],
        "use_case": {
            "question": "How do you usually sleep?",
            "options": ["Side sleeper", "Back sleeper", "Stomach sleeper", "It varies"],
        },
        "features": {
            "question": "How firm do you like it?",
            "options": ["Soft", "Medium", "Firm", "Not sure"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $500", "$500–$1,000", "$1,000–$2,000", "$2,000+"],
    },
    "bikes": {
        "aliases": ["bike", "bicycle", "bicycles", "ebike", "e-bike", "mountain bike", "road bike"],
        "use_case": {
            "question": "What kind of riding will you mostly do?",
            "options": ["Road", "Trails & mountain", "Commuting", "Casual rides"],
        },
        "features": {
            "question": "Any frame or drivetrain preference?",
            "options": ["Lightweight frame", "Full suspension", "Electric assist", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $500", "$500–$1,000", "$1,000–$2,500", "$2,500+"],
    },
    "monitors": {
        "aliases": ["monitor", "computer monitor", "gaming monitor", "display", "displays"],
        "use_case": {
            "question": "What will you use it for most?",
            "options": ["Office work", "Gaming", "Creative / color work", "General use"],
        },
        "features": {
            "question": "What size and shape suits your desk?",
            "options": ["24–27 inch", "27–32 inch", "Ultrawide", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $200", "$200–$400", "$400–$800", "$800+"],
    },
    "coffee machines": {
        "aliases": ["coffee machine", "coffee maker", "coffee makers", "espresso machine", "espresso machines", "coffee"],
        "use_case": {
            "question": "How do you like your coffee?",
            "options": ["Espresso drinks", "Drip / filter coffee", "Pods / convenience", "Cold brew"],
        },
        "features": {
            "question": "Which features matter to you?",
            "options": ["Built-in grinder", "Milk frother", "Programmable", "No strong preference"],
            "multi_select": True,
        },
        "budget_brackets": ["Under $100", "$100–$300", "$300–$700", "$700+"],
    },
    "vacuums": {
        "aliases": ["vacuum", "vacuum cleaner", "vacuum cleaners", "robot vacuum", "stick vacuum"],
        "use_case": {
            "question": "What are you mostly cleaning?",
            "options": ["Carpet", "Hard floors", "Pet hair", "A mix of everything"],
        },
        "features": {
            "question": "What style fits your home?",
            "options": ["Cordless stick", "Robot", "Upright", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $150", "$150–$300", "$300–$600", "$600+"],
    },
    "air purifiers": {
        "aliases": ["air purifier", "air purifiers", "hepa purifier", "air cleaner"],
        "use_case": {
            "question": "What's the main concern?",
            "options": ["Allergies", "Pet dander", "Smoke & odors", "General air quality"],
        },
        "features": {
            "question": "How big is the space?",
            "options": ["Small room", "Medium room", "Large room / open plan", "Not sure"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $100", "$100–$250", "$250–$500", "$500+"],
    },
    "strollers": {
        "aliases": ["stroller", "pushchair", "pram", "prams", "baby stroller"],
        "use_case": {
            "question": "How will you mostly use it?",
            "options": ["Everyday errands", "Travel", "Jogging", "Newborn + toddler"],
        },
        "features": {
            "question": "Which features matter to you?",
            "options": ["Lightweight / compact fold", "Car-seat compatible", "All-terrain wheels", "No strong preference"],
            "multi_select": True,
        },
        "budget_brackets": ["Under $200", "$200–$500", "$500–$900", "$900+"],
    },
    "watches": {
        "aliases": ["watch", "smartwatch", "smartwatches", "wristwatch", "apple watch"],
        "use_case": {
            "question": "What's it mainly for?",
            "options": ["Fitness & health tracking", "Everyday style", "Dress / occasions", "Outdoor / adventure"],
        },
        "features": {
            "question": "What type are you drawn to?",
            "options": ["Smartwatch", "Mechanical / automatic", "Classic quartz", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $200", "$200–$500", "$500–$1,500", "$1,500+"],
    },
    "cameras": {
        "aliases": ["camera", "mirrorless camera", "dslr", "point and shoot", "digital camera"],
        "use_case": {
            "question": "What will you shoot most?",
            "options": ["Travel & family", "Vlogging / video", "Wildlife & sports", "Professional work"],
        },
        "features": {
            "question": "What style of camera?",
            "options": ["Compact / point-and-shoot", "Mirrorless", "DSLR", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $500", "$500–$1,000", "$1,000–$2,500", "$2,500+"],
    },
    "keyboards": {
        "aliases": ["keyboard", "mechanical keyboard", "gaming keyboard", "wireless keyboard"],
        "use_case": {
            "question": "What's it mainly for?",
            "options": ["Typing & work", "Gaming", "Programming", "A mix of everything"],
        },
        "features": {
            "question": "Which features matter to you?",
            "options": ["Mechanical switches", "Low-profile / quiet", "Wireless", "No strong preference"],
            "multi_select": True,
        },
        "budget_brackets": ["Under $50", "$50–$100", "$100–$200", "$200+"],
    },
    "desks": {
        "aliases": ["desk", "standing desk", "computer desk", "office desk", "gaming desk"],
        "use_case": {
            "question": "How will you use it?",
            "options": ["Home office", "Gaming setup", "Small space", "Shared / family use"],
        },
        "features": {
            "question": "What style works for you?",
            "options": ["Standing / height-adjustable", "Fixed height", "Corner / L-shaped", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $200", "$200–$400", "$400–$800", "$800+"],
    },
    "chairs": {
        "aliases": ["chair", "office chair", "office chairs", "gaming chair", "desk chair", "ergonomic chair"],
        "use_case": {
            "question": "How long are you sitting per day?",
            "options": ["2–4 hours", "4–8 hours", "8+ hours", "It varies"],
        },
        "features": {
            "question": "Which features matter to you?",
            "options": ["Lumbar support", "Breathable mesh", "Headrest", "No strong preference"],
            "multi_select": True,
        },
        "budget_brackets": ["Under $150", "$150–$350", "$350–$700", "$700+"],
    },
    "grills": {
        "aliases": ["grill", "bbq", "barbecue", "smoker", "smokers", "pellet grill", "gas grill"],
        "use_case": {
            "question": "What do you cook most?",
            "options": ["Burgers & weeknight basics", "Low & slow BBQ", "Pizza & high heat", "A bit of everything"],
        },
        "features": {
            "question": "What fuel type do you prefer?",
            "options": ["Gas", "Charcoal", "Pellet / smoker", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $200", "$200–$500", "$500–$1,000", "$1,000+"],
    },
    "luggage": {
        "aliases": ["suitcase", "suitcases", "carry-on", "carry on", "travel bag", "travel bags"],
        "use_case": {
            "question": "What kind of traveler are you?",
            "options": ["Carry-on only", "Checked bags", "Business trips", "Family trips"],
        },
        "features": {
            "question": "Which features matter to you?",
            "options": ["Hard shell", "Lightweight", "Expandable", "No strong preference"],
            "multi_select": True,
        },
        "budget_brackets": ["Under $100", "$100–$250", "$250–$500", "$500+"],
    },
    "running shoes": {
        "aliases": ["running shoe", "runners", "sneakers", "trainers", "jogging shoes"],
        "use_case": {
            "question": "What kind of running do you do?",
            "options": ["Road running", "Trail running", "Treadmill / gym", "Walking & casual"],
        },
        "features": {
            "question": "What feel do you want underfoot?",
            "options": ["Max cushion", "Stability support", "Lightweight / racing", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $80", "$80–$130", "$130–$180", "$180+"],
    },
    "tablets": {
        "aliases": ["tablet", "ipad", "ipads", "android tablet", "e-reader", "kindle"],
        "use_case": {
            "question": "What will you mainly use it for?",
            "options": ["Streaming & browsing", "Note-taking & study", "Drawing / creative work", "For the kids"],
        },
        "features": {
            "question": "Any platform preference?",
            "options": ["Apple iPad", "Android", "With keyboard & stylus", "No strong preference"],
            "multi_select": False,
        },
        "budget_brackets": ["Under $200", "$200–$500", "$500–$900", "$900+"],
    },
}


def get_category_pack(category: str) -> Optional[Dict[str, Any]]:
    """Return the question pack for a category, or None when no pack matches.

    Matching is forgiving: case/whitespace-insensitive, singular/plural tolerant,
    and checks each pack's aliases. "best gaming laptop" style compound categories
    match when a pack key or alias appears inside the category string.
    """
    if not category or not isinstance(category, str):
        return None
    cat = category.lower().strip()
    if not cat:
        return None

    # Exact key/alias match (including simple plural/singular flip)
    candidates = {cat}
    if cat.endswith("s"):
        candidates.add(cat[:-1])
    else:
        candidates.add(cat + "s")

    for key, pack in CATEGORY_QUESTION_PACKS.items():
        names = {key, key.rstrip("s")} | {a.lower() for a in pack.get("aliases", [])}
        if candidates & names:
            return pack

    # Word-boundary match for compound categories ("gaming laptop", "noise
    # cancelling headphones"). Whole words only — a plain substring check would
    # send "headphones" to the phones pack ("phones" is a suffix of "headphones").
    cat_words = set(cat.split())
    for key, pack in CATEGORY_QUESTION_PACKS.items():
        names = [key, key.rstrip("s")] + [a.lower() for a in pack.get("aliases", [])]
        for name in names:
            name_words = name.split()
            if len(name_words) == 1:
                # Single-word name must match a whole word (plural-tolerant)
                if {name, name + "s", name.rstrip("s")} & cat_words:
                    return pack
            else:
                # Multi-word name must appear as a contiguous word sequence
                if f" {name} " in f" {cat} ":
                    return pack

    return None


def format_pack_hint(pack: Dict[str, Any]) -> str:
    """Render a pack as prompt text the clarifier injects into its question-
    generation prompt. The pack is authoritative for question text, options,
    multi-select flags, and budget brackets."""
    features = pack["features"]
    features_type = "multi_select" if features.get("multi_select") else "single_select"
    return f"""
CURATED QUESTION SET for this category — use these questions and options EXACTLY (only adapt wording if the conversation already covers part of an answer):
- use_case question: "{pack['use_case']['question']}" with options {pack['use_case']['options']}
- features question: "{features['question']}" with options {features['options']} and "type": "{features_type}"
- budget question options: {pack['budget_brackets']}
"""
