from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from motor.core import AgnosticDatabase
from pydantic import parse_obj_as

from app.apps.feed.repository.comment import CommentRepository
from app.apps.feed.schemas.comment import (
    CommentInput,
    CommentOutput,
    CommentsListParams,
    PaginatedComments,
)
from app.core import depends
from app.core.depends import UserRole
from app.schemas.users import User

router = APIRouter()


@router.post("", response_model=CommentOutput)
async def create_comment_api(
    comment_input: CommentInput,
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    return await CommentRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).create_comment(comment_input)


@router.get("", response_model=PaginatedComments)
async def list_comments_api(
    params: CommentsListParams = Depends(),
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    return await CommentRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).list_comments(params)


@router.delete("/{comment_id}")
async def delete_comment_api(
    comment_id: int,
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    await CommentRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).delete_comment(comment_id)
