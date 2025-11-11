"""
Rhesis Entities Module.

This module providess the entity classes for interacting with the Rhesis API.
"""

from dotenv import load_dotenv

from .base_collection import BaseCollection
from .base_entity import BaseEntity
from .behavior import Behavior, Behaviors
from .category import Categories, Category
from .prompt import Prompt, Prompts
from .status import Status, Statuses
from .test import Test, Tests
from .test_set import TestSet, TestSets
from .topic import Topic, Topics

load_dotenv("/Users/arek/Desktop/rhesis/.env")
__all__ = [
    "BaseEntity",
    "BaseCollection",
    "Behavior",
    "Behaviors",
    "Category",
    "Categories",
    "Prompt",
    "Prompts",
    "Status",
    "Statuses",
    "Test",
    "Tests",
    "TestSet",
    "TestSets",
    "Topic",
    "Topics",
]
