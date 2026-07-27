"""
Garak to Rhesis taxonomy mapping.

This module maps Garak probe modules to Rhesis categories, topics,
and default detectors, and resolves Garak ``quality:*`` tags to
``Garak (...)`` behavior names.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

FALLBACK_BEHAVIOR = "Garak (Security Probing)"

# Maps ``quality:*`` tag suffixes to human-readable behavior names.
# Priority order: ContentSafety > other Behavioral > Robustness > Security.
# Within a tier the first alphabetical tag wins.
_QUALITY_TAG_TO_BEHAVIOR: Dict[str, str] = {
    "quality:Behavioral:ContentSafety:HateHarassment": "Garak (Hate & Harassment)",
    "quality:Behavioral:ContentSafety:LegalGoodsServices": "Garak (Legal Goods & Services)",
    "quality:Behavioral:ContentSafety:Profanity": "Garak (Profanity)",
    "quality:Behavioral:ContentSafety:Sexual": "Garak (Sexual Content)",
    "quality:Behavioral:ContentSafety:Toxicity": "Garak (Toxicity)",
    "quality:Behavioral:ContentSafety:Unauthorized": "Garak (Unauthorized Content)",
    "quality:Behavioral:ContentSafety:Violence": "Garak (Violence)",
    "quality:Behavioral:DeliberativeMisinformation": "Garak (Deliberate Misinformation)",
    "quality:Robustness:GenerativeMisinformation": "Garak (Generative Misinformation)",
    "quality:Security:Adversarial": "Garak (Adversarial)",
    "quality:Security:Confidentiality": "Garak (Confidentiality)",
    "quality:Security:ExtractionInversion": "Garak (Extraction & Inversion)",
    "quality:Security:Integrity": "Garak (Integrity)",
    "quality:Security:PromptStability": "Garak (Prompt Stability)",
}

_TIER_ORDER = [
    "quality:Behavioral:ContentSafety:",
    "quality:Behavioral:",
    "quality:Robustness:",
    "quality:Security:",
]


def resolve_behavior(tags: Optional[List[str]]) -> str:
    """Pick one ``Garak (...)`` behavior name from a probe's tag list.

    Selects the highest-priority ``quality:*`` tag using the tier order
    (ContentSafety > Behavioral > Robustness > Security), breaking ties
    alphabetically within a tier.  Returns ``FALLBACK_BEHAVIOR`` when no
    ``quality:*`` tag is present.
    """
    if not tags:
        return FALLBACK_BEHAVIOR

    quality_tags = sorted(t for t in tags if t in _QUALITY_TAG_TO_BEHAVIOR)
    if not quality_tags:
        return FALLBACK_BEHAVIOR

    for prefix in _TIER_ORDER:
        for tag in quality_tags:
            if tag.startswith(prefix):
                return _QUALITY_TAG_TO_BEHAVIOR[tag]

    return FALLBACK_BEHAVIOR


@dataclass
class GarakMapping:
    """Mapping from Garak module to Rhesis taxonomy."""

    category: str
    topic: str
    default_detector: str
    description: str


class GarakTaxonomy:
    """
    Taxonomy mapping for Garak probes to Rhesis entities.

    Maps Garak probe modules to Rhesis categories, topics, and default
    detectors. Behaviors are resolved from probe-level ``quality:*`` tags
    via :func:`resolve_behavior`, not from the module mapping.
    """

    MODULE_MAPPINGS: Dict[str, GarakMapping] = {
        "atkgen": GarakMapping(
            category="Harmful",
            topic="Automatic Red-Team",
            default_detector="garak.detectors.perspective.Toxicity",
            description="Automatic Red-Team (atkgen) adversarial prompt generation",
        ),
        "dan": GarakMapping(
            category="Harmful",
            topic="Jailbreak",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="DAN (Do Anything Now) jailbreak prompts",
        ),
        "encoding": GarakMapping(
            category="Harmful",
            topic="Encoding Bypass",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Encoding-based attack prompts (Base64, ROT13, etc.)",
        ),
        "promptinject": GarakMapping(
            category="Harmful",
            topic="Prompt Injection",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Prompt injection attack patterns",
        ),
        "continuation": GarakMapping(
            category="Harmful",
            topic="Continuation Attack",
            default_detector="garak.detectors.continuation.Continuation",
            description="Continuation-based elicitation attacks",
        ),
        "misleading": GarakMapping(
            category="Harmful",
            topic="Misinformation",
            default_detector="garak.detectors.misleading.MisleadingClaim",
            description="Misleading and misinformation prompts",
        ),
        "lmrc": GarakMapping(
            category="Harmful",
            topic="Language Model Risk",
            default_detector="garak.detectors.lmrc.Lmrc",
            description="LMRC (Language Model Risk Cards) test prompts",
        ),
        "realtoxicityprompts": GarakMapping(
            category="Harmful",
            topic="Toxicity",
            default_detector="garak.detectors.perspective.Toxicity",
            description="RealToxicityPrompts dataset probes",
        ),
        "malwaregen": GarakMapping(
            category="Harmful",
            topic="Malware Generation",
            default_detector="garak.detectors.malwaregen.MalwareGenDetector",
            description="Malware code generation prompts",
        ),
        "packagehallucination": GarakMapping(
            category="Harmful",
            topic="Hallucination",
            default_detector="garak.detectors.packagehallucination.PackageHallucination",
            description="Package/library hallucination probes",
        ),
        "gcg": GarakMapping(
            category="Harmful",
            topic="Adversarial Suffix",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Greedy Coordinate Gradient adversarial suffixes",
        ),
        "av_spam_scanning": GarakMapping(
            category="Harmful",
            topic="Known Bad Patterns",
            default_detector="garak.detectors.knownbadsignatures.EICAR",
            description="Known malicious content signatures (AV/spam scanning)",
        ),
        "suffix": GarakMapping(
            category="Harmful",
            topic="Suffix Attack",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Suffix-based jailbreak attacks",
        ),
        "tap": GarakMapping(
            category="Harmful",
            topic="Tree of Attacks",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Tree of Attacks with Pruning (TAP) prompts",
        ),
        "xss": GarakMapping(
            category="Harmful",
            topic="XSS",
            default_detector="garak.detectors.xss.XSSDetector",
            description="Cross-site scripting (XSS) generation probes",
        ),
        "snowball": GarakMapping(
            category="Harmful",
            topic="Factual Errors",
            default_detector="garak.detectors.snowball.SnowballDetector",
            description="Snowball factual error probes",
        ),
        "donotanswer": GarakMapping(
            category="Harmful",
            topic="Refusal Bypass",
            default_detector="garak.detectors.perspective.Toxicity",
            description="Do Not Answer dataset probes",
        ),
        "glitch": GarakMapping(
            category="Harmful",
            topic="Glitch Tokens",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Glitch token exploitation probes",
        ),
        "goodside": GarakMapping(
            category="Harmful",
            topic="Goodside Attacks",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Riley Goodside-style prompt injections",
        ),
        "leakreplay": GarakMapping(
            category="Harmful",
            topic="Data Leakage",
            default_detector="garak.detectors.leakreplay.LeakReplayDetector",
            description="Training data leakage/replay probes",
        ),
        "base64": GarakMapping(
            category="Harmful",
            topic="Base64 Encoding",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Base64 encoded attack payloads",
        ),
        "ansiescape": GarakMapping(
            category="Harmful",
            topic="ANSI Escape Injection",
            default_detector="garak.detectors.ansiescape.ANSI",
            description="ANSI escape sequence injection attacks",
        ),
        "apikey": GarakMapping(
            category="Harmful",
            topic="API Key Leakage",
            default_detector="garak.detectors.apikey.APIKey",
            description="Probes that attempt to extract API keys from model output",
        ),
        # NOTE: "audio" and "fileformats" are intentionally absent -- they are
        # excluded from probe enumeration (see GarakProbeService.EXCLUDED_MODULES)
        # because they operate on binary payloads and have no meaningful text
        # representation in Rhesis.
        "badchars": GarakMapping(
            category="Harmful",
            topic="Bad Characters",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Imperceptible Unicode character perturbation attacks",
        ),
        "divergence": GarakMapping(
            category="Harmful",
            topic="Training Data Leakage",
            default_detector="garak.detectors.divergence.Repetitive",
            description="Probes that cause training data memorization/divergence",
        ),
        "doctor": GarakMapping(
            category="Harmful",
            topic="Medical Advice",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Probes for inappropriate medical or clinical advice generation",
        ),
        "dra": GarakMapping(
            category="Harmful",
            topic="Decomposed Roleplay Attack",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Decomposed Roleplay Attack (DRA) jailbreak prompts",
        ),
        "exploitation": GarakMapping(
            category="Harmful",
            topic="Code Exploitation",
            default_detector="garak.detectors.exploitation.ExploitDetector",
            description="Probes for exploit code and vulnerability generation",
        ),
        "fitd": GarakMapping(
            category="Harmful",
            topic="Foot In The Door",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Foot-in-the-door social engineering attack probes",
        ),
        "grandma": GarakMapping(
            category="Harmful",
            topic="Social Engineering",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Grandma/roleplay social engineering jailbreak attacks",
        ),
        "latentinjection": GarakMapping(
            category="Harmful",
            topic="Latent Prompt Injection",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Latent/hidden prompt injection attack probes",
        ),
        "phrasing": GarakMapping(
            category="Harmful",
            topic="Phrasing Attack",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Phrasing-based jailbreak and bypass attack probes",
        ),
        "sata": GarakMapping(
            category="Harmful",
            topic="Suffix Attack",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Structured Adversarial Text Attack (SATA) probes",
        ),
        "smuggling": GarakMapping(
            category="Harmful",
            topic="ASCII Smuggling",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="ASCII/Unicode smuggling prompt injection attacks",
        ),
    }

    DEFAULT_MAPPING = GarakMapping(
        category="Harmful",
        topic="Security Testing",
        default_detector="garak.detectors.mitigation.MitigationBypass",
        description="Garak security probe",
    )

    @classmethod
    def get_mapping(cls, module_name: str) -> GarakMapping:
        """
        Get the Rhesis taxonomy mapping for a Garak module.

        Args:
            module_name: Name of the Garak probe module

        Returns:
            GarakMapping with category, topic, and detector
        """
        return cls.MODULE_MAPPINGS.get(module_name, cls.DEFAULT_MAPPING)
