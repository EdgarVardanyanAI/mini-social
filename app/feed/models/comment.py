from pydantic.tools import parse_obj_as
from typing import Self

from app.apps.feed.schemas.comment import (
    CommentInput,
    CommentOutput,
    CommentUserInfo,
)
from app.core.neo4j import CreatedUpdatedAt


class Comment(CreatedUpdatedAt, CommentUserInfo):
    post_id: int
    parent_id: int | None = None
    content: str

    @classmethod
    def from_input(
        cls, comment_input: CommentInput, user_info: CommentUserInfo
    ) -> Self:
        _comment_dict = comment_input.dict() | user_info.dict()
        return cls.parse_obj(_comment_dict)

    def to_output(self) -> CommentOutput:
        _comment_dict = self.dict()
        return parse_obj_as(CommentOutput, _comment_dict)
