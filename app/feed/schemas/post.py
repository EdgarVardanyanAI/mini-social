from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.base import ListWithCountResponse, Model


class VotingTypes(str, Enum):
    SINGLE_VOTE = "SINGLE_VOTE"
    MULTI_VOTE = "MULTI_VOTE"


class PostTypes(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    POLL = "POLL"


class PollDurations(int, Enum):
    ONE_DAY = 1
    THREE_DAYS = 3
    ONE_WEEK = 7
    TWO_WEEKS = 14


class PollOption(Model):
    title: str  # TODO Validate uniqueness


class PollSettings(Model):
    voting_type: VotingTypes
    duration: PollDurations
    options: list[PollOption] = Field(min_items=1)


class PollOptionResult(PollOption):
    count: int = 0
    chosen: bool = False


class RevealedPollSettings(PollSettings):
    options: list[PollOptionResult]


class TextPostInput(Model):
    class Config:
        extra = "forbid"

    post_type: Literal[PostTypes.TEXT] = Field(PostTypes.TEXT)
    content: str = Field(default_factory=str)


class ImagePostInput(TextPostInput):
    post_type: Literal[PostTypes.IMAGE] = Field(PostTypes.IMAGE)
    image_url: str  # TODO FileReferenceIn


class VideoPostInput(TextPostInput):
    post_type: Literal[PostTypes.VIDEO] = Field(PostTypes.VIDEO)
    video_url: str  # TODO FileReferenceIn


class PollPostInput(TextPostInput):
    post_type: Literal[PostTypes.POLL] = Field(PostTypes.POLL)
    poll_settings: PollSettings


PostInput = Annotated[
    TextPostInput | ImagePostInput | VideoPostInput | PollPostInput,
    Field(discriminator="post_type"),
]


class PostUserInfo(BaseModel):
    # TODO Signal: when user data changes, these have to change as well
    user_id: str
    user_display_name: str
    user_headline: str | None
    user_avatar: str | None


class TextPostOutput(TextPostInput, PostUserInfo):
    class Config:
        extra = "allow"

    id: int
    likes_count: int = 0
    comments_count: int = 0
    created_at: datetime
    updated_at: datetime


class ImagePostOutput(ImagePostInput, TextPostOutput):
    post_type: Literal[PostTypes.IMAGE] = Field(PostTypes.IMAGE)


class VideoPostOutput(VideoPostInput, TextPostOutput):
    post_type: Literal[PostTypes.VIDEO] = Field(PostTypes.VIDEO)


class PollPostOutput(PollPostInput, TextPostOutput):
    post_type: Literal[PostTypes.POLL] = Field(PostTypes.POLL)
    poll_settings: RevealedPollSettings


PostOutput = Annotated[
    TextPostOutput | ImagePostOutput | VideoPostOutput | PollPostOutput,
    Field(discriminator="post_type"),
]


class PaginatedPosts(ListWithCountResponse):
    data: list[PostOutput]


class PostsListParams:  # TODO inherit from base pagination from core_zenoa
    def __init__(self, offset: int = 0, limit: int = 20):
        self.offset = offset
        self.limit = limit
