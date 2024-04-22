from pydantic import parse_obj_as
from typing import Self

from app.apps.feed.schemas.post import (
    PollDurations,
    PollOptionResult,
    PollPostInput,
    PostInput,
    PostOutput,
    PostTypes,
    PostUserInfo,
    RevealedPollSettings,
    VotingTypes,
)
from app.core.neo4j import CreatedUpdatedAt


class Post(CreatedUpdatedAt, PostUserInfo):
    content: str
    post_type: PostTypes
    image_url: str | None = None
    video_url: str | None = None

    # poll settings
    voting_type: VotingTypes | None = None
    duration: PollDurations | None = None
    options: list[str] | None = None

    # counts
    likes_count: int = 0
    comments_count: int = 0

    @classmethod
    def from_input(
        cls, post_input: PostInput, user_info: PostUserInfo
    ) -> Self:
        _post_dict = post_input.dict() | user_info.dict()
        if isinstance(post_input, PollPostInput):
            _post_dict |= post_input.poll_settings.dict() | dict(
                options=[
                    option.title for option in post_input.poll_settings.options
                ]
            )
        return cls.parse_obj(_post_dict)

    def to_output(self) -> PostOutput:
        _post_dict = self.dict()
        if self.post_type == PostTypes.POLL:
            assert (
                self.voting_type is not None
                and self.duration is not None
                and self.options is not None
            )
            _post_dict["poll_settings"] = RevealedPollSettings(
                voting_type=self.voting_type,
                duration=self.duration,
                options=[
                    PollOptionResult(title=option_title)
                    for option_title in self.options
                ],
            )

        return parse_obj_as(PostOutput, _post_dict)
