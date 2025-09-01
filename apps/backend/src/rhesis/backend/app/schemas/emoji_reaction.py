from typing import Dict, List
from uuid import UUID

from pydantic import BaseModel, Field, RootModel


class EmojiReaction(BaseModel):
    """Schema for individual emoji reaction by a user"""

    user_id: UUID = Field(..., description="User ID who reacted with this emoji")
    user_name: str = Field(..., description="User's display name")

    class Config:
        from_attributes = True


class CommentEmojis(RootModel[Dict[str, List[EmojiReaction]]]):
    """Schema for emoji reactions on a comment"""

    root: Dict[str, List[EmojiReaction]] = Field(
        default_factory=dict, description="Map of emoji to list of users who reacted with it"
    )
