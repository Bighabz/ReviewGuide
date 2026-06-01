"""Golden cases for the voice model bake-off.

Each case mirrors a canonical example from tone.md (the voice gospel) and
carries mock product/review data formatted exactly like the ``blog_data``
string that product_compose.py builds for the blog_article composer call:

    User asked: "<user message>"
    Product: <name> (<label>) | Rating: <r>/5 (<n> reviews) | Buy: $<p> on <merchant>: <url> ; ... | Image: <url>
      - <review snippet, no source attribution>
      - <review snippet>

Review snippets deliberately carry NO source names (no "Wirecutter says")
— same as production, where source attribution is stripped before the LLM
sees the data because VOICE_PROMPT forbids citing competitors.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class GoldenCase:
    """One bake-off scenario.

    Attributes:
        id: Short slug used in CLI ``--cases`` and report rows.
        name: Human-readable name for reports.
        source: Where in tone.md this case comes from.
        user_message: The user's message (single turn — production's blog
            call is single-turn today; history wiring is a deferred phase).
        blog_data: The full user-message payload, in production format.
        expectations: Bullet notes handed to the LLM judge.
        expects_transitional: True = transitional_reasoning must be emitted,
            False = it must be an empty string, None = either is acceptable.
    """

    id: str
    name: str
    source: str
    user_message: str
    blog_data: str
    expectations: List[str] = field(default_factory=list)
    expects_transitional: Optional[bool] = None


def _blog_data(user_message: str, *product_lines: str) -> str:
    """Assemble blog_data the way product_compose.py does (line ~843)."""
    return "\n".join([f'User asked: "{user_message}"', *product_lines])


# ---------------------------------------------------------------------------
# Case 1 — Simple purchase, fast path (tone.md Example 1)
# ---------------------------------------------------------------------------

_EARBUDS_MSG = "What's the best wireless earbuds under $100?"

CASE_EARBUDS = GoldenCase(
    id="earbuds_under_100",
    name="Wireless earbuds under $100",
    source="tone.md Example 1 (simple purchase, fast path)",
    user_message=_EARBUDS_MSG,
    blog_data=_blog_data(
        _EARBUDS_MSG,
        "Product: Soundcore Liberty 4 NC (Best Overall) | Rating: 4.4/5 (12840 reviews) | Buy: $89.99 on Amazon: https://www.amazon.com/dp/B0C3LR5H2K ; $84.95 on eBay: https://www.ebay.com/itm/4055123 | Image: https://img.example.com/liberty4nc.jpg"
        "\n  - ANC is shockingly effective for the price, kills subway and office hum"
        "\n  - App has a real EQ and adaptive ANC modes, rare under $100"
        "\n  - Case is chunky compared to AirPods but battery is 50 hours total",
        "Product: JLab JBuds ANC 3 (Best Value) | Rating: 4.2/5 (5210 reviews) | Buy: $59.99 on Amazon: https://www.amazon.com/dp/B0CJL8JBND | Image: https://img.example.com/jbudsanc3.jpg"
        "\n  - Punchy bass-forward tuning, great for the gym"
        "\n  - ANC is decent but lets voices through; fine for commute, not for flights",
        "Product: Nothing Ear (a) | Rating: 4.3/5 (3470 reviews) | Buy: $119.00 on Amazon: https://www.amazon.com/dp/B0CZHQRS9V | Image: https://img.example.com/nothingeara.jpg"
        "\n  - Distinctive transparent design, the one people ask about"
        "\n  - Sound is clean and balanced; ChatGPT integration is a gimmick",
        "Product: EarFun Air Pro 4 | Rating: 4.1/5 (2980 reviews) | Buy: $79.99 on Amazon: https://www.amazon.com/dp/B0D8XK2P4N | Image: https://img.example.com/earfunpro4.jpg"
        "\n  - aptX Lossless and multipoint at a price where neither is expected"
        "\n  - Mic quality on calls is mediocre, fine indoors only",
    ),
    expectations=[
        "Must commit to a #1 pick and a #2 pick, in order, with WHY the #1 wins for the default buyer",
        "Must NOT write a parallel survey where every product gets one paragraph of equal praise",
        "Alternatives must be positioned by who they fit, not by trashing them",
        "The Nothing Ear (a) is over the $100 budget — a strong answer either excludes it or explicitly flags the budget stretch",
        "Follow-up question must reference something specific (a product, a tradeoff, or the commute/workout/calls split)",
    ],
    expects_transitional=True,  # "under $100" is a real budget constraint
)


# ---------------------------------------------------------------------------
# Case 2 — User pushes back: the no-glazing test (tone.md Example 2)
# ---------------------------------------------------------------------------

_AIRPODS_MSG = "I'm thinking about the AirPods Max actually."

CASE_AIRPODS_PUSHBACK = GoldenCase(
    id="airpods_max_pushback",
    name="AirPods Max pushback (no-glazing test)",
    source="tone.md Example 2 (user pushes back)",
    user_message=_AIRPODS_MSG,
    blog_data=_blog_data(
        _AIRPODS_MSG,
        "Product: Apple AirPods Max | Rating: 4.5/5 (31250 reviews) | Buy: $549.00 on Amazon: https://www.amazon.com/dp/B08PZHYWJS ; $499.99 on Best Buy: https://www.bestbuy.com/site/6373460 | Image: https://img.example.com/airpodsmax.jpg"
        "\n  - Build quality and spatial audio with Apple devices are genuinely best-in-class"
        "\n  - At 384g they are heavy; some users report fatigue after 2 hours"
        "\n  - The Smart Case is widely criticized: no power button, case protects almost nothing",
        "Product: Sonos Ace | Rating: 4.3/5 (4180 reviews) | Buy: $449.00 on Amazon: https://www.amazon.com/dp/B0D14V5LJK | Image: https://img.example.com/sonosace.jpg"
        "\n  - Comfort and build rival the AirPods Max at 60 percent of the weight penalty"
        "\n  - TV Audio Swap with a Sonos soundbar is the killer feature for home use"
        "\n  - Case is compact, hard-shell, and actually protects the headphones",
        "Product: Sony WH-1000XM5 | Rating: 4.6/5 (48730 reviews) | Buy: $329.99 on Amazon: https://www.amazon.com/dp/B09XS7JWHH | Image: https://img.example.com/xm5.jpg"
        "\n  - Class-leading ANC and 30-hour battery, the default pick for most people"
        "\n  - Plastic build feels less premium than the price suggests",
    ),
    expectations=[
        "Must NOT glaze: no 'great choice', no reflexive affirmation of the user's leaning",
        "Must NOT trash the AirPods Max either — acknowledge what is genuinely good (build, spatial audio)",
        "Must surface the real downsides: $549 price, weight, the case",
        "Should offer a concrete alternative positioned by FIT (e.g. Sonos Ace for commuters / non-Apple-locked users)",
        "Follow-up should probe what actually decides it for this user (e.g. Apple ecosystem lock-in)",
    ],
    expects_transitional=None,  # no budget/use-case constraint stated; either way is defensible
)


# ---------------------------------------------------------------------------
# Case 3 — Pure taste question: the deferral test (tone.md Example 6)
# ---------------------------------------------------------------------------

_TASTE_MSG = "Do you think the Sony XM5s look better than the QC Ultras?"

CASE_TASTE_DEFERRAL = GoldenCase(
    id="xm5_vs_qc_looks",
    name="Sony XM5 vs QC Ultra looks (taste deferral)",
    source="tone.md Example 6 (no opinion on pure taste)",
    user_message=_TASTE_MSG,
    blog_data=_blog_data(
        _TASTE_MSG,
        "Product: Sony WH-1000XM5 | Rating: 4.6/5 (48730 reviews) | Buy: $329.99 on Amazon: https://www.amazon.com/dp/B09XS7JWHH | Image: https://img.example.com/xm5.jpg"
        "\n  - Soft-touch matte finish, rounded earcups, minimal stealth look"
        "\n  - Headband design no longer folds flat, divisive among travelers",
        "Product: Bose QuietComfort Ultra | Rating: 4.5/5 (21940 reviews) | Buy: $379.00 on Amazon: https://www.amazon.com/dp/B0CCZ1L489 | Image: https://img.example.com/qcultra.jpg"
        "\n  - Aluminum yoke and sharper lines, reads more business / executive"
        "\n  - Folds flat into a smaller case than the XM5",
    ),
    expectations=[
        "Must NOT fake an opinion on pure aesthetics — looks are taste, and the voice rule is humility on taste",
        "Should describe the actual visual difference (soft/rounded vs sharp/business-like) without ranking it",
        "Must hand the decision back to the user",
        "Follow-up should frame the taste question usefully (e.g. 'which energy do you want?'), not dodge it",
    ],
    expects_transitional=False,  # no constraint to frame — should be empty string
)


# ---------------------------------------------------------------------------
# Case 4 — Aspirational browsing, richer prose (tone.md Example 4)
# ---------------------------------------------------------------------------

_KYOTO_MSG = "Looking at hotels in Kyoto for a week in April."

CASE_KYOTO = GoldenCase(
    id="kyoto_hotels_april",
    name="Kyoto hotels for a week in April",
    source="tone.md Example 4 (aspirational browsing)",
    user_message=_KYOTO_MSG,
    blog_data=_blog_data(
        _KYOTO_MSG,
        "Product: Hoshinoya Kyoto | Rating: 4.8/5 (1240 reviews) | Buy: $1850.00 per night on Booking.com: https://www.booking.com/hotel/jp/hoshinoya-kyoto.html | Image: https://img.example.com/hoshinoya.jpg"
        "\n  - Ryokan-meets-resort on the Oi River, reached by private boat from Arashiyama"
        "\n  - Service consistently described as the best in Japan"
        "\n  - Books out months ahead for cherry-blossom season",
        "Product: The Thousand Kyoto | Rating: 4.6/5 (3890 reviews) | Buy: $420.00 per night on Booking.com: https://www.booking.com/hotel/jp/the-thousand-kyoto.html | Image: https://img.example.com/thousand.jpg"
        "\n  - Modern luxury two minutes' walk from Kyoto Station"
        "\n  - Practical base for day trips: Nara, Osaka, Fushimi Inari all easy",
        "Product: Tawaraya Ryokan | Rating: 4.9/5 (310 reviews) | Buy: $1100.00 per night on direct booking: https://example.com/tawaraya | Image: https://img.example.com/tawaraya.jpg"
        "\n  - Operating for over 300 years, the most traditional ryokan experience in the city"
        "\n  - No website, famously hard to book, often a wait list in April",
    ),
    expectations=[
        "April in Kyoto is cherry-blossom season — a strong answer reframes the problem around availability and price inflation",
        "Aspirational, richer prose is appropriate here — the voice can dwell on details (the boat, the service)",
        "Must still rank: a #1 pick with WHY, alternatives by fit (practical vs traditional)",
        "Follow-up should move the trip forward (dates, booking) or acknowledge the daydream stage",
    ],
    expects_transitional=True,  # "a week in April" is a real constraint that shapes the pick
)


# ---------------------------------------------------------------------------
# Case 5 — Sparse constraints (tone.md Example 3's query, without the quiz UI)
# ---------------------------------------------------------------------------

_LAPTOP_MSG = "I need a new laptop."

CASE_LAPTOP = GoldenCase(
    id="need_a_laptop",
    name="\"I need a laptop\" (sparse constraints)",
    source="tone.md Example 3 (complex purchase — production would normally clarify first)",
    user_message=_LAPTOP_MSG,
    blog_data=_blog_data(
        _LAPTOP_MSG,
        "Product: Apple MacBook Air M4 13\" (Best Overall) | Rating: 4.7/5 (8920 reviews) | Buy: $999.00 on Amazon: https://www.amazon.com/dp/B0DZD9LBTV ; $949.00 on Best Buy: https://www.bestbuy.com/site/6571369 | Image: https://img.example.com/mba-m4.jpg"
        "\n  - The default laptop for most people: silent, 15+ hour battery, fast enough for everything short of heavy video work"
        "\n  - 13\" base model has a dimmer screen than the Pro and only two ports",
        "Product: ASUS Zenbook 14 OLED | Rating: 4.4/5 (3150 reviews) | Buy: $849.99 on Amazon: https://www.amazon.com/dp/B0CSDLRJ31 | Image: https://img.example.com/zenbook14.jpg"
        "\n  - The OLED screen embarrasses laptops twice the price"
        "\n  - Best Windows value under $900; battery is good, not MacBook good",
        "Product: Lenovo ThinkPad X1 Carbon Gen 12 | Rating: 4.5/5 (1870 reviews) | Buy: $1649.00 on Lenovo: https://www.lenovo.com/x1-carbon-gen12 | Image: https://img.example.com/x1carbon.jpg"
        "\n  - The keyboard and 2.2 lb weight make it the road-warrior pick"
        "\n  - Expensive for the specs; you pay for the build, not the benchmark",
        "Product: Apple MacBook Pro 14\" M4 Pro | Rating: 4.8/5 (5240 reviews) | Buy: $1999.00 on Amazon: https://www.amazon.com/dp/B0DLHY1Q5L | Image: https://img.example.com/mbp14.jpg"
        "\n  - The pick if work means video editing, large codebases, or local AI models"
        "\n  - Overkill (in price and weight) for browsing, writing, and office work",
    ),
    expectations=[
        "The user gave NO budget, use case, or platform preference — the honest move is to commit to a default pick for most people while being explicit about what would change the answer",
        "Must NOT fact-dump four parallel product blurbs",
        "Must NOT pretend to know the user's needs (no inventing 'since you need it for work...')",
        "Follow-up question is the most important field here: it must probe the missing constraint (use case, budget, or Mac/Windows)",
    ],
    expects_transitional=False,  # bare query, no constraint to frame — should be empty string
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

GOLDEN_CASES: List[GoldenCase] = [
    CASE_EARBUDS,
    CASE_AIRPODS_PUSHBACK,
    CASE_TASTE_DEFERRAL,
    CASE_KYOTO,
    CASE_LAPTOP,
]

CASES_BY_ID = {c.id: c for c in GOLDEN_CASES}
