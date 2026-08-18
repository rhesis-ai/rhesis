"""Scope-flag detection for Reg-Advisor.

Rule-based, over the user's own words only. Four categories: wanting to evade regulation rather
than understand it, seeking a determination to rely on, live enforcement or litigation, and
clinical advice for a patient.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from reg_advisor.utils import as_text

# 1. Evasion — wanting to avoid the regime rather than understand it.
EVASION_PATTERNS: tuple[str, ...] = (
    r"\b(?:so|so that|so it)\b[^.?!]{0,40}\b(?:is ?n[o']t|not)\s+(?:a\s+)?(?:medical\s+)?device\b",
    r"\bword(?:ing)?\s+(?:the\s+)?(?:claim|intended use|label)[^.?!]{0,40}\bnot\b",
    r"\b(?:avoid|dodge|skip|escape|bypass|get around|work around|sidestep)\b[^.?!]{0,40}"
    r"\b(?:510\s?\(?k\)?|pma|de novo|ce mark|notified body|mdr|ivdr|fda|regulat\w*|"
    r"classification|conformity assessment)\b",
    r"\bsplit(?:ting)?\s+(?:the\s+|our\s+|up\s+)?(?:product|device|software)\b[^.?!]{0,40}"
    r"\b(?:class|lower|down|avoid|dodge)\b",
    r"\b(?:market|ship|sell|launch|release)\b[^.?!]{0,30}\bwithout\b[^.?!]{0,30}"
    r"\b(?:ce mark|510\s?\(?k\)?|clearance|approval|notified body|authorisation|authorization)\b",
    r"\b(?:stay|fly|keep)\b[^.?!]{0,20}\b(?:under the radar|below the radar)\b",
    r"\bhow (?:do|can) (?:i|we)\b[^.?!]{0,40}\bnot (?:be )?(?:a )?(?:regulated|device)\b",
    r"\bloophole\b",
)

# 2. A determination the user intends to rely on, rather than an explanation of a regime.
DETERMINATION_PATTERNS: tuple[str, ...] = (
    r"\b(?:are we|are you|is (?:this|it|our|my))\b[^.?!]{0,30}\bcompliant\b",
    r"\bsign(?:ing)? ?off\b",
    # Needs a readiness marker. Without one this catches "can we ship to the EU and the US from
    # the same QMS?", which is an ordinary question about how the regimes fit together.
    r"\b(?:can|may|could|are) (?:i|we)\b[^.?!]{0,20}\b(?:ship|launch|go to market|"
    r"start selling|place it on the market)\b[^.?!]{0,20}\b(?:yet|now|already|today|"
    r"next (?:month|week|quarter|year)|this (?:month|quarter|year)|in q[1-4])\b",
    r"\b(?:are|is) (?:we|it|this|the product) (?:ready|clear|ok|okay|good) to "
    r"(?:ship|launch|sell|market|go)\b",
    r"\bconfirm\b[^.?!]{0,40}\b(?:we|i|it)\b[^.?!]{0,20}\b(?:do ?n[o']t|don't|does ?n[o']t)\s+"
    r"\bneed\b",
    r"\bjust (?:tell|give) me\b[^.?!]{0,25}\b(?:yes or no|a yes or no|the answer)\b",
    r"\byes or no\b[^.?!]{0,30}\b(?:compliant|approved|cleared|regulated|need)\b",
    r"\b(?:guarantee|certify|assure)\b[^.?!]{0,30}\b(?:compliance|compliant|we are|it is)\b",
    r"\bgive me (?:a |your )?(?:definitive|final|binding)\b",
)

# 3. Live enforcement or litigation. This agent is for planning, not for responding.
#
# These require something already happening to *this* user. A bare mention of litigation or a
# recall is ordinary planning vocabulary — "we want to avoid litigation risk" is exactly the
# kind of question this agent exists to help with, and referring it away would be a bug.
ENFORCEMENT_PATTERNS: tuple[str, ...] = (
    # FDA correspondence only counts once it has arrived. "What is a Form 483?" is a question
    # about the regime; "we got a Form 483" is an event this agent must not advise on.
    r"\b(?:got|received|responding to|respond to|answer|answering|reply to|address|"
    r"came back with|issued us)\b[^.?!]{0,25}\b(?:form )?(?:483|warning letter|untitled letter)\b",
    r"\bour (?:form )?(?:483|warning letter|untitled letter)\b",
    r"\b483 (?:observation|response)\b",
    r"\b(?:this|the) (?:form )?(?:483|warning letter|untitled letter)\b[^.?!]{0,30}"
    r"\b(?:we|us|our)\b",
    r"\b(?:form )?(?:483|warning letter|untitled letter)\b[^.?!]{0,25}\b(?:we|us|our)\b",
    r"\brecall\b[^.?!]{0,30}\b(?:in progress|ongoing|underway|we (?:are|'re)|initiated)\b|"
    r"\b(?:ongoing|active|in progress) recall\b",
    r"\b(?:placed|put|listed) on (?:an )?import alert\b",
    r"\b(?:we|our product|our device|the product)\b[^.?!]{0,30}\bimport alert\b",
    r"\b(?:under|entered into|signed|subject to) a consent decree\b",
    r"\bconsent decree\b[^.?!]{0,25}\b(?:us|our|we)\b",
    r"\b(?:certificate|notified body)\b[^.?!]{0,40}\b(?:suspend\w*|withdraw\w*|revok\w*)\b",
    r"\b(?:suspend\w*|withdraw\w*|revok\w*)\b[^.?!]{0,30}\b(?:our|the|my) certificate\b",
    r"\b(?:we|our company|the company|they)\b[^.?!]{0,20}\b(?:are|is|were|was|have been|"
    r"has been|'re|'ve been)\b[^.?!]{0,15}\bsued\b",
    r"\blawsuit against (?:us|our|the company)\b",
    r"\b(?:ongoing|active|pending|current) litigation\b",
    r"\bwe (?:are|'re) in litigation\b",
    r"\b(?:served with|received) a (?:subpoena|court order)\b",
    r"\bsubpoena\w*\b[^.?!]{0,20}\b(?:us|our|the company)\b",
    r"\bfda (?:inspection|investigator)\b[^.?!]{0,30}\b(?:now|this week|on site|arrived)\b",
)

# 4. Clinical or patient-facing advice. Out of scope entirely — this agent talks to product
#    teams, not to patients.
#
# "should I take" needs a medicinal object. Without one it catches "should I take a different
# approach", which is an ordinary product question and must not be referred away.
CLINICAL_PATTERNS: tuple[str, ...] = (
    r"\b(?:should|can|do) i (?:take|stop taking|keep taking)\b[^.?!]{0,40}"
    r"\b(?:medication|medicine|drug|pills?|dose|dosage|tablets?|supplement|antibiotics?|"
    r"insulin|statins?|painkillers?)\b",
    # The lookahead matters in this domain: "my symptom checker app" is a product, not a
    # complaint, and referring its owner away would be exactly the wrong move.
    r"\bmy symptoms?\b(?!\s+(?:checker|tracker|app|application|tool|software|product|"
    r"platform|diary|logger|questionnaire|classifier))",
    r"\bdiagnose me\b",
    r"\bwhat(?:'s| is)? wrong with me\b",
    r"\bis it safe for me to\b",
    r"\bwhat (?:medication|dose|drug) should i\b",
    r"\bi (?:have|feel|am experiencing)\b[^.?!]{0,30}\b(?:pain|symptoms?|fever|rash|bleeding)\b",
    r"\bmy (?:doctor|physician|gp)\b[^.?!]{0,30}\b(?:said|told me|prescribed)\b",
)

SCOPE_FLAG_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        *EVASION_PATTERNS,
        *DETERMINATION_PATTERNS,
        *ENFORCEMENT_PATTERNS,
        *CLINICAL_PATTERNS,
    )
)


def text_suggests_scope_flag(text: object) -> bool:
    """True when the user's own words match a scope-flag rule."""
    candidate = as_text(text)
    return any(pattern.search(candidate) for pattern in SCOPE_FLAG_PATTERNS)


def first_scope_flag_text(user_messages: Sequence[str]) -> str | None:
    """The earliest user turn that matches a rule, or ``None``.

    Takes user texts rather than the whole conversation on purpose: the assistant's own referral
    copy must never re-trigger the check. Because the coordinator replays the whole conversation
    every turn, a flag raised on an earlier turn keeps matching — which is what makes referral
    sticky rather than something the user can walk back with a benign follow-up.
    """
    for message in user_messages:
        if text_suggests_scope_flag(message):
            return as_text(message)
    return None


__all__ = [
    "CLINICAL_PATTERNS",
    "DETERMINATION_PATTERNS",
    "ENFORCEMENT_PATTERNS",
    "EVASION_PATTERNS",
    "SCOPE_FLAG_PATTERNS",
    "first_scope_flag_text",
    "text_suggests_scope_flag",
]
