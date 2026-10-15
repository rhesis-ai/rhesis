"""Answers to the onboarding profile questions: the user's job role and how they found Rhesis.

Stored as these keys on ``user.job_role`` / ``user.referral_source``; the labels live in the
frontend (``constants/user-profile.ts``). There is no DB constraint, so adding an option is
just a change here and there.
"""

from enum import Enum


class JobRole(str, Enum):
    ENGINEER = "engineer"
    DATA_SCIENTIST = "data_scientist"
    QA = "qa"
    PRODUCT_MANAGER = "product_manager"
    DOMAIN_EXPERT = "domain_expert"
    COMPLIANCE_RISK = "compliance_risk"
    LEADERSHIP = "leadership"
    RESEARCHER = "researcher"
    STUDENT = "student"
    OTHER = "other"


class ReferralSource(str, Enum):
    GOOGLE_SEARCH = "google_search"
    AI_ASSISTANT = "ai_assistant"
    GITHUB = "github"
    LINKEDIN = "linkedin"
    FRIEND_COLLEAGUE = "friend_colleague"
    EVENT_CONFERENCE = "event_conference"
    BLOG_ARTICLE = "blog_article"
    OTHER = "other"
