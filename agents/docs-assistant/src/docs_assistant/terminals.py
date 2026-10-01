"""Fixed replies (no model call), in English and German.

Every turn that doesn't reach the answer agent ends in one of these, so out-of-scope, support,
smalltalk and unsafe turns read the same every time. Links stay English in both languages.
"""

from __future__ import annotations

from docs_assistant.schemas import NextStep

DISCORD = NextStep(label="Ask on Discord", url="https://discord.com/invite/Qu8szPNz2M")
BUG_REPORT = NextStep(
    label="Report a bug on GitHub",
    url="https://github.com/rhesis-ai/rhesis/issues/new?template=bug_report.md",
)
TALK_TO_US = NextStep(label="Talk to the Rhesis team", url="https://www.rhesis.ai/talk-to-us")
SUPPORT_STEPS = [DISCORD, BUG_REPORT, TALK_TO_US]

_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "help_topics": (
            "I can help with Rhesis questions, for example:\n"
            "- How do I install the Rhesis SDK?\n"
            "- What's the difference between single-turn and multi-turn metrics?\n"
            "- How do I trace my agent with Rhesis?\n"
            "- How do I self-host Rhesis with Docker Compose?"
        ),
        "smalltalk": (
            "Hi! I answer questions about Rhesis from its documentation at docs.rhesis.ai, and "
            "I link the pages I used."
        ),
        "thanks": "You're welcome! Ask me anything else about Rhesis.",
        "out_of_scope": (
            "That's outside what I can help with. I only answer questions about Rhesis, from "
            "its documentation."
        ),
        "unsafe": (
            "I can't help with that. I answer questions about Rhesis from its documentation, "
            "and I don't share my instructions."
        ),
        "support": (
            "This sounds like something the Rhesis team needs to look at, since it depends on "
            "your account or your setup rather than on the docs. These are the best places to "
            "get help:"
        ),
        "support_pages": "These docs pages may help in the meantime:",
        "empty": "Ask me a question about Rhesis, and I'll answer it from the docs.",
        "parts_capped": "You asked several questions; I've answered the first {n}.",
        "input_clipped": ("Your message was long, so I only read the first {n} characters of it."),
        "fallback": (
            "I couldn't finish checking the docs for this question, so I won't guess. "
            "Try a narrower question, or start from the pages below."
        ),
        "no_submit": (
            "I couldn't put together an answer I could check against the docs, so I won't "
            "guess. The pages below are the closest matches."
        ),
        "not_documented_help": "If you think the docs should cover this, you can reach us here:",
        "sources": "Sources",
        "related": "Related pages",
        "not_covered": "Not covered in the docs:",
        "correction": "Correction:",
        "clarify_hint": "Reply with a number, or say it in your own words.",
    },
    "de": {
        "help_topics": (
            "Ich helfe bei Fragen zu Rhesis, zum Beispiel:\n"
            "- Wie installiere ich das Rhesis SDK?\n"
            "- Was ist der Unterschied zwischen Single-Turn- und Multi-Turn-Metriken?\n"
            "- Wie trace ich meinen Agenten mit Rhesis?\n"
            "- Wie hoste ich Rhesis selbst mit Docker Compose?"
        ),
        "smalltalk": (
            "Hallo! Ich beantworte Fragen zu Rhesis anhand der Dokumentation auf "
            "docs.rhesis.ai und verlinke die Seiten, die ich dafür genutzt habe."
        ),
        "thanks": "Gern geschehen! Frag mich gern noch mehr zu Rhesis.",
        "out_of_scope": (
            "Dabei kann ich leider nicht helfen. Ich beantworte nur Fragen zu Rhesis, anhand "
            "der Dokumentation."
        ),
        "unsafe": (
            "Dabei kann ich nicht helfen. Ich beantworte Fragen zu Rhesis anhand der "
            "Dokumentation und gebe meine Anweisungen nicht weiter."
        ),
        "support": (
            "Das klingt nach etwas, das sich das Rhesis-Team ansehen muss, weil es von deinem "
            "Konto oder deinem Setup abhängt und nicht von der Dokumentation. Hier bekommst du "
            "am besten Hilfe:"
        ),
        "support_pages": "Diese Seiten der Dokumentation helfen vielleicht schon weiter:",
        "empty": "Stell mir eine Frage zu Rhesis, und ich beantworte sie anhand der Doku.",
        "parts_capped": "Du hast mehrere Fragen gestellt; ich habe die ersten {n} beantwortet.",
        "input_clipped": (
            "Deine Nachricht war lang, daher habe ich nur die ersten {n} Zeichen gelesen."
        ),
        "fallback": (
            "Ich konnte die Dokumentation für diese Frage nicht fertig prüfen und rate "
            "deshalb nicht. Versuch eine engere Frage, oder fang bei den Seiten unten an."
        ),
        "no_submit": (
            "Ich konnte keine Antwort zusammenstellen, die sich an der Dokumentation prüfen "
            "lässt, und rate deshalb nicht. Die Seiten unten passen am besten."
        ),
        "not_documented_help": (
            "Wenn du findest, dass die Doku das abdecken sollte, erreichst du uns hier:"
        ),
        "sources": "Quellen",
        "related": "Verwandte Seiten",
        "not_covered": "Nicht in der Dokumentation:",
        "correction": "Korrektur:",
        "clarify_hint": "Antworte mit einer Nummer oder in deinen eigenen Worten.",
    },
}


def language_key(language: str | None) -> str:
    """The template language for a BCP-47 code; anything without templates falls back to en."""
    primary = (language or "en").split("-", 1)[0].lower()
    return primary if primary in _TEXT else "en"


def text(key: str, language: str | None = "en", **values: object) -> str:
    return _TEXT[language_key(language)][key].format(**values)


def smalltalk(language: str | None, *, thanks: bool = False) -> str:
    opening = text("thanks" if thanks else "smalltalk", language)
    return f"{opening}\n\n{text('help_topics', language)}"


def out_of_scope(language: str | None) -> str:
    return f"{text('out_of_scope', language)}\n\n{text('help_topics', language)}"


def unsafe(language: str | None) -> str:
    return text("unsafe", language)


def support(language: str | None) -> str:
    return text("support", language)


def links(steps: list[NextStep]) -> str:
    return "\n".join(f"- [{s.label}]({s.url})" for s in steps)
