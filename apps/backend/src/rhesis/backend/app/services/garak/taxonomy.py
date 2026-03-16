"""
Garak to Rhesis taxonomy mapping.

This module maps Garak probe modules to Rhesis categories, topics,
behaviors, and default detectors.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class GarakMapping:
    """Mapping from Garak module to Rhesis taxonomy."""

    category: str
    topic: str
    behavior: str
    default_detector: str
    description: str


class GarakTaxonomy:
    """
    Taxonomy mapping for Garak probes to Rhesis entities.

    Maps Garak probe modules to Rhesis categories, topics, and behaviors
    to ensure proper categorization when importing probes as test sets.
    """

    # Mapping of Garak probe modules to Rhesis taxonomy
    MODULE_MAPPINGS: Dict[str, GarakMapping] = {
        "atkgen": GarakMapping(
            category="Harmful",
            topic="Automatic Red-Team",
            behavior="Robustness",
            # atkgen (formerly 'art') uses a separate model to generate adversarial prompts
            default_detector="garak.detectors.perspective.Toxicity",
            description="Automatic Red-Team (atkgen) adversarial prompt generation",
        ),
        "dan": GarakMapping(
            category="Harmful",
            topic="Jailbreak",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="DAN (Do Anything Now) jailbreak prompts",
        ),
        "encoding": GarakMapping(
            category="Harmful",
            topic="Encoding Bypass",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Encoding-based attack prompts (Base64, ROT13, etc.)",
        ),
        "promptinject": GarakMapping(
            category="Harmful",
            topic="Prompt Injection",
            behavior="Compliance",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Prompt injection attack patterns",
        ),
        "continuation": GarakMapping(
            category="Harmful",
            topic="Continuation Attack",
            behavior="Compliance",
            default_detector="garak.detectors.continuation.Continuation",
            description="Continuation-based elicitation attacks",
        ),
        "misleading": GarakMapping(
            category="Harmful",
            topic="Misinformation",
            behavior="Reliability",
            default_detector="garak.detectors.misleading.MisleadingClaim",
            description="Misleading and misinformation prompts",
        ),
        "lmrc": GarakMapping(
            category="Harmful",
            topic="Language Model Risk",
            behavior="Compliance",
            default_detector="garak.detectors.lmrc.Lmrc",
            description="LMRC (Language Model Risk Cards) test prompts",
        ),
        "realtoxicityprompts": GarakMapping(
            category="Harmful",
            topic="Toxicity",
            behavior="Compliance",
            # ToxicCommentModel is a local model that cannot be run ad hoc.
            # Using perspective.Toxicity (Google Perspective API) instead.
            default_detector="garak.detectors.perspective.Toxicity",
            description="RealToxicityPrompts dataset probes",
        ),
        "malwaregen": GarakMapping(
            category="Harmful",
            topic="Malware Generation",
            behavior="Compliance",
            default_detector="garak.detectors.malwaregen.MalwareGenDetector",
            description="Malware code generation prompts",
        ),
        "packagehallucination": GarakMapping(
            category="Harmful",
            topic="Hallucination",
            behavior="Reliability",
            default_detector="garak.detectors.packagehallucination.PackageHallucination",
            description="Package/library hallucination probes",
        ),
        "gcg": GarakMapping(
            category="Harmful",
            topic="Adversarial Suffix",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Greedy Coordinate Gradient adversarial suffixes",
        ),
        "av_spam_scanning": GarakMapping(
            category="Harmful",
            topic="Known Bad Patterns",
            behavior="Compliance",
            # Renamed from 'knownbadsignatures' in garak v0.13.3
            default_detector="garak.detectors.knownbadsignatures.EICAR",
            description="Known malicious content signatures (AV/spam scanning)",
        ),
        "suffix": GarakMapping(
            category="Harmful",
            topic="Suffix Attack",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Suffix-based jailbreak attacks",
        ),
        "tap": GarakMapping(
            category="Harmful",
            topic="Tree of Attacks",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Tree of Attacks with Pruning (TAP) prompts",
        ),
        "xss": GarakMapping(
            category="Harmful",
            topic="XSS",
            behavior="Compliance",
            default_detector="garak.detectors.xss.XSSDetector",
            description="Cross-site scripting (XSS) generation probes",
        ),
        "snowball": GarakMapping(
            category="Harmful",
            topic="Factual Errors",
            behavior="Reliability",
            default_detector="garak.detectors.snowball.SnowballDetector",
            description="Snowball factual error probes",
        ),
        "donotanswer": GarakMapping(
            category="Harmful",
            topic="Refusal Bypass",
            behavior="Compliance",
            # ToxicCommentModel is a local model that cannot be run ad hoc.
            # Using perspective.Toxicity (Google Perspective API) instead.
            default_detector="garak.detectors.perspective.Toxicity",
            description="Do Not Answer dataset probes",
        ),
        "glitch": GarakMapping(
            category="Harmful",
            topic="Glitch Tokens",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Glitch token exploitation probes",
        ),
        "goodside": GarakMapping(
            category="Harmful",
            topic="Goodside Attacks",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Riley Goodside-style prompt injections",
        ),
        "leakreplay": GarakMapping(
            category="Harmful",
            topic="Data Leakage",
            behavior="Compliance",
            default_detector="garak.detectors.leakreplay.LeakReplayDetector",
            description="Training data leakage/replay probes",
        ),
        "base64": GarakMapping(
            category="Harmful",
            topic="Base64 Encoding",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Base64 encoded attack payloads",
        ),
        # New in garak v0.13.3
        "ansiescape": GarakMapping(
            category="Harmful",
            topic="ANSI Escape Injection",
            behavior="Compliance",
            default_detector="garak.detectors.ansiescape.ANSI",
            description="ANSI escape sequence injection attacks",
        ),
        "apikey": GarakMapping(
            category="Harmful",
            topic="API Key Leakage",
            behavior="Compliance",
            default_detector="garak.detectors.apikey.APIKey",
            description="Probes that attempt to extract API keys from model output",
        ),
        # NOTE: "audio" and "fileformats" are intentionally absent — they are excluded
        # from probe enumeration (see GarakProbeService.EXCLUDED_MODULES) because they
        # operate on binary payloads and have no meaningful text representation in Rhesis.
        "badchars": GarakMapping(
            category="Harmful",
            topic="Bad Characters",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Imperceptible Unicode character perturbation attacks",
        ),
        "divergence": GarakMapping(
            category="Harmful",
            topic="Training Data Leakage",
            behavior="Compliance",
            default_detector="garak.detectors.divergence.Repetitive",
            description="Probes that cause training data memorization/divergence",
        ),
        "doctor": GarakMapping(
            category="Harmful",
            topic="Medical Advice",
            behavior="Compliance",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Probes for inappropriate medical or clinical advice generation",
        ),
        "dra": GarakMapping(
            category="Harmful",
            topic="Decomposed Roleplay Attack",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Decomposed Roleplay Attack (DRA) jailbreak prompts",
        ),
        "exploitation": GarakMapping(
            category="Harmful",
            topic="Code Exploitation",
            behavior="Compliance",
            default_detector="garak.detectors.exploitation.ExploitDetector",
            description="Probes for exploit code and vulnerability generation",
        ),
        "fitd": GarakMapping(
            category="Harmful",
            topic="Foot In The Door",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Foot-in-the-door social engineering attack probes",
        ),
        "grandma": GarakMapping(
            category="Harmful",
            topic="Social Engineering",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Grandma/roleplay social engineering jailbreak attacks",
        ),
        "latentinjection": GarakMapping(
            category="Harmful",
            topic="Latent Prompt Injection",
            behavior="Compliance",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Latent/hidden prompt injection attack probes",
        ),
        "phrasing": GarakMapping(
            category="Harmful",
            topic="Phrasing Attack",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Phrasing-based jailbreak and bypass attack probes",
        ),
        "sata": GarakMapping(
            category="Harmful",
            topic="Suffix Attack",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="Structured Adversarial Text Attack (SATA) probes",
        ),
        "smuggling": GarakMapping(
            category="Harmful",
            topic="ASCII Smuggling",
            behavior="Compliance",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="ASCII/Unicode smuggling prompt injection attacks",
        ),
    }

    # Default mapping for unknown modules
    DEFAULT_MAPPING = GarakMapping(
        category="Harmful",
        topic="Security Testing",
        behavior="Robustness",
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
            GarakMapping with category, topic, behavior, and detector
        """
        return cls.MODULE_MAPPINGS.get(module_name, cls.DEFAULT_MAPPING)
