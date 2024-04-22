from fastapi import APIRouter

from app.apps.feed.api import comment as comment_api
from app.apps.feed.api import post as post_api

router = APIRouter()

router.include_router(post_api.router, prefix="/post")
router.include_router(comment_api.router, prefix="/comment")
