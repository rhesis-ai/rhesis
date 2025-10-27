from typing import Dict, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel


class EmojiReaction(BaseModel):
    """Schema for individual emoji reaction by a user

    Note: The emoji itself is stored as the dictionary key in the Comment.emojis field.
    This schema represents the user data associated with each emoji reaction.
    """

    user_id: UUID = Field(..., description="User ID who reacted with this emoji")
    user_name: str = Field(..., description="User's display name")

    model_config = ConfigDict(from_attributes=True)


class CommentEmojis(RootModel[Dict[str, List[EmojiReaction]]]):
    """Schema for emoji reactions on a comment

    Structure: {emoji_character: [list_of_user_reactions]}

    Example:
    {
        "🚀": [
            {"user_id": "uuid1", "user_name": "John"},
            {"user_id": "uuid2", "user_name": "Jane"}
        ],
        "👍": [
            {"user_id": "uuid3", "user_name": "Bob"}
        ]
    }

    Note: The emoji character (e.g., "🚀", "👍", "❤️") is the dictionary key.
    Each emoji key maps to a list of EmojiReaction objects representing users who reacted.
    """

    root: Dict[str, List[EmojiReaction]] = Field(
        default_factory=dict,
        description="Map of emoji character to list of users who reacted with it. "
        "The emoji itself (e.g., '🚀', '👍', '❤️') is the dictionary key.",
    )
