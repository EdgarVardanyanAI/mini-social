from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import ListWithCountResponse, Model


class CommentUserInfo(BaseModel):
    # TODO Signal: when user data changes, these have to change as well
    user_id: str
    user_display_name: str
    user_avatar: str | None


class CommentInput(Model):
    post_id: int
    parent_id: int | None = None
    content: str


class CommentOutput(CommentInput, CommentUserInfo):
    id: int
    created_at: datetime


class PaginatedComments(ListWithCountResponse):
    data: list[CommentOutput]


class CommentsListParams:  # TODO inherit from base pagination from core_zenoa
    def __init__(self, post_id: int, offset: int = 0, limit: int = 20):
        self.post_id = post_id
        self.offset = offset
        self.limit = limit
