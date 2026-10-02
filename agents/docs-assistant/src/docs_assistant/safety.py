"""Cheap checks that run before and after the models.

Before: empty input, clipping, prompt-injection attempts, and plain greetings or thanks. A hit
ends the turn in a fixed reply with no model call. Triage still catches paraphrases these
patterns miss.

After: a reply that repeats long runs of our own instructions is swapped for the fixed decline,
and internal tool status words never reach the user.

The injection patterns target commands aimed at this assistant, not the topic. Rhesis is a
testing platform, so "how do I test my chatbot for prompt injection?" or "how do I set the system
prompt of my endpoint?" are real docs questions and must not trip.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

INJECTION_PATTERNS: tuple[str, ...] = (
    # Override commands: "ignore your rules", "disregard all previous instructions".
    r"\b(?:ignore|disregard|forget|override|bypass)\b[^.?!\n]{0,30}"
    r"\b(?:previous|prior|above|earlier|preceding|all|your|system)\b[^.?!\n]{0,20}"
    r"\b(?:instructions?|rules|prompts?|guidelines|guardrails|restrictions|directives)\b",
    # Asking for this assistant's own prompt. Needs "your", so a question about the system
    # prompt of the user's app or endpoint doesn't trip.
    r"\b(?:print|show|reveal|repeat|output|display|dump|leak|share|recite|give me|tell me|"
    r"what (?:is|are|was|were))\b[^.?!\n]{0,20}\byour\b[^.?!\n]{0,20}"
    r"\b(?:system prompt|initial prompt|hidden prompt|prompt|instructions|rules|guidelines)\b",
    r"\brepeat\b[^.?!\n]{0,20}\b(?:everything|all|the text|the words|what(?:'s| is| was)?)\b"
    r"[^.?!\n]{0,20}\b(?:above|before this|so far)\b",
    r"\b(?:text|everything|words) above this (?:line|message)\b",
    # Role-play jailbreaks aimed at this assistant.
    r"\byou are now\b[^.?!\n]{0,30}\b(?:dan|unrestricted|unfiltered|jailbroken|no longer)\b",
    r"\b(?:pretend|act|behave)\b[^.?!\n]{0,30}\b(?:no|without)\s+(?:rules|restrictions|"
    r"filters|limits|guidelines)\b",
    r"\b(?:enable|enter|activate|switch to)\s+(?:developer|dev|god|jailbreak|dan)\s+mode\b",
    r"</?\s*(?:system|instructions?)\s*>",
    # German.
    r"\b(?:ignoriere|vergiss|missachte)\b[^.?!\n]{0,30}\b(?:anweisungen|regeln|vorgaben|prompt)\b",
    r"\b(?:zeig|zeige|gib|nenne|wiederhole)\b[^.?!\n]{0,20}\bdein(?:e|en)?\b[^.?!\n]{0,20}"
    r"\b(?:systemprompt|system-prompt|prompt|anweisungen|regeln)\b",
)
INJECTION = tuple(re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS)

# A message about testing for these attacks ("a test where the user says 'ignore previous
# instructions'") is a docs question. The regex steps aside and triage decides.
TESTING_TOPIC = re.compile(
    r"\b(?:tests?|testing|test sets?|metrics?|red[- ]?team\w*|adversarial|attacks?|penelope|"
    r"polyphemus|garak|evaluat\w+|detect\w*|scenarios?|prompt injections?|jailbreaks?)\b",
    re.IGNORECASE,
)

# Whole-message greetings, thanks and "what can you do". Anything longer goes to triage, so
# "hi, how do I install the SDK?" is still answered.
_GREETING = (
    r"(?:hi|hello|hey|hiya|howdy|yo|hallo|moin|servus|gr[üu](?:ß|ss) (?:gott|dich)|"
    r"good (?:morning|afternoon|evening|day)|guten (?:morgen|tag|abend))"
)
_THANKS = (
    r"(?:thanks|thank you|thank u|thx|ty|cheers|much appreciated|danke|vielen dank|"
    r"danke sch[öo]n|merci)"
)
_ABOUT = (
    r"(?:what can you do|what do you do|what are you|who are you|how can you help(?: me)?|"
    r"what can i ask(?: you)?|help|was kannst du|wer bist du|was machst du|"
    r"wie kannst du (?:mir )?helfen)"
)
_TAIL = r"[\s!.,?:;)(\-]*"
_NAME = r"(?:\s+(?:there|all|team|bot|assistant|rhesis))?"
GREETING = re.compile(
    rf"^\s*(?:{_GREETING}{_NAME}{_TAIL}(?:{_ABOUT}{_TAIL})?|{_ABOUT}{_TAIL})$", re.IGNORECASE
)
THANKS = re.compile(
    rf"^\s*(?:{_THANKS}(?:\s+(?:a lot|so much|very much))?{_NAME}{_TAIL})+$", re.IGNORECASE
)
SHORT_MESSAGE = 60

# Words that only appear in German, for the rare fixed reply sent before triage runs.
_GERMAN = re.compile(
    r"\b(?:hallo|moin|servus|danke|guten|wie|ich|du|dein\w*|bitte|ignoriere|vergiss|"
    r"anweisungen|zeig\w*|kannst|bist|wer|und|nicht|ist|das|der|die|mit)\b",
    re.IGNORECASE,
)

STATUS_WORDS = ("ACCEPTED", "REJECTED", "BUDGET_EXHAUSTED", "NOT_FOUND")
_STATUS_LINE = re.compile(rf"^.*\b(?:{'|'.join(STATUS_WORDS)})\b.*$\n?", re.MULTILINE)

# How much of our own instructions a reply may repeat before it counts as a leak.
LEAK_NGRAM = 8
LEAK_MIN_HITS = 3


@dataclass(frozen=True)
class Precheck:
    kind: Literal["empty", "unsafe", "smalltalk", "thanks"]
    language: str


def clip(message: str, limit: int) -> tuple[str, bool]:
    """The message cut to `limit` characters, and whether it was cut."""
    message = message.strip()
    return (message[:limit], True) if len(message) > limit else (message, False)


def looks_like_injection(message: str) -> bool:
    return any(p.search(message) for p in INJECTION) and not TESTING_TOPIC.search(message)


def guess_language(message: str) -> str:
    words = re.findall(r"\w+", message)
    german = len(_GERMAN.findall(message))
    return "de" if words and german / len(words) >= 0.2 else "en"


def precheck(message: str) -> Precheck | None:
    """A fixed-reply verdict, or None when the message should go to triage."""
    if not message.strip():
        return Precheck("empty", "en")
    language = guess_language(message)
    if looks_like_injection(message):
        return Precheck("unsafe", language)
    if len(message) <= SHORT_MESSAGE:
        if THANKS.match(message):
            return Precheck("thanks", language)
        if GREETING.match(message):
            return Precheck("smalltalk", language)
    return None


def strip_status_lines(text: str) -> str:
    """Drop any line carrying an internal tool status word."""
    return _STATUS_LINE.sub("", text).strip()


def _shingles(text: str, n: int = LEAK_NGRAM) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def leaks_prompt(reply: str, prompts: list[str]) -> bool:
    """True when the reply repeats several long word runs from any of our prompts."""
    reply_shingles = _shingles(reply)
    return any(len(reply_shingles & _shingles(p)) >= LEAK_MIN_HITS for p in prompts)
