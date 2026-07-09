"""Subagent component factories."""

from dr_rhesis.agents.critic import SafetyCritic, create_safety_critic
from dr_rhesis.agents.gathering import GatheringBrain, create_gathering_brain
from dr_rhesis.agents.router import IntentRouter, create_intent_router
from dr_rhesis.agents.summary import SummaryWriter, create_summary_writer

__all__ = [
    "GatheringBrain",
    "IntentRouter",
    "SafetyCritic",
    "SummaryWriter",
    "create_gathering_brain",
    "create_intent_router",
    "create_safety_critic",
    "create_summary_writer",
]
