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
            default_detector="garak.detectors.toxicity.ToxicityDetector",
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
        "knownbadsignatures": GarakMapping(
            category="Harmful",
            topic="Known Bad Patterns",
            behavior="Compliance",
            default_detector="garak.detectors.knownbadsignatures.EICAR",
            description="Known malicious content signatures",
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
            default_detector="garak.detectors.donotanswer.DoNotAnswerDetector",
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

    @classmethod
    def get_category(cls, module_name: str) -> str:
        """Get the Rhesis category for a Garak module."""
        return cls.get_mapping(module_name).category

    @classmethod
    def get_topic(cls, module_name: str) -> str:
        """Get the Rhesis topic for a Garak module."""
        return cls.get_mapping(module_name).topic

    @classmethod
    def get_behavior(cls, module_name: str) -> str:
        """Get the Rhesis behavior for a Garak module."""
        return cls.get_mapping(module_name).behavior

    @classmethod
    def get_default_detector(cls, module_name: str) -> str:
        """Get the default Garak detector for a module."""
        return cls.get_mapping(module_name).default_detector

    @classmethod
    def list_mapped_modules(cls) -> list:
        """List all Garak modules with explicit mappings."""
        return list(cls.MODULE_MAPPINGS.keys())

    @classmethod
    def get_all_mappings(cls) -> Dict[str, GarakMapping]:
        """Get all module mappings."""
        return cls.MODULE_MAPPINGS.copy()
