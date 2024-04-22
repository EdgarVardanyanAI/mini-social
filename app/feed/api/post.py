from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from motor.core import AgnosticDatabase
from pydantic import parse_obj_as

from app.apps.feed.repository.post import PostRepository
from app.apps.feed.schemas.post import (
    PaginatedPosts,
    PostInput,
    PostOutput,
    PostsListParams,
)
from app.core import depends
from app.core.depends import UserRole
from app.schemas.users import User

router = APIRouter()


@router.post("", response_model=PostOutput)
async def create_post_api(
    post_input: PostInput,
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    post = await PostRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).create_post(post_input)
    return parse_obj_as(PostOutput, post)


@router.get("", response_model=PaginatedPosts)
async def list_posts_api(
    params: PostsListParams = Depends(),
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    return await PostRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).list_posts(params)


@router.get("/{post_id}", response_model=PostOutput)
async def get_post_api(
    post_id: int,
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    post = await PostRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).get_post(post_id)

    if not post:  # Handle the case where post is None or empty
        return JSONResponse(
            status_code=404, content={"message": "Post not found"}
        )

    return parse_obj_as(PostOutput, post)


@router.put("/{post_id}", response_model=PostOutput)
async def update_post_api(
    post_id: int,
    post_input: PostInput,
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    post = await PostRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).update_post(post_id, post_input)
    if not post:  # Handle the case where post is None or empty
        return JSONResponse(
            status_code=404, content={"message": "Post not found"}
        )

    return parse_obj_as(PostOutput, post)


@router.delete("/{post_id}", status_code=204)
async def delete_post_api(
    post_id: int,
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    await PostRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).delete_post(post_id)


@router.post("/{post_id}/like", status_code=204)
async def like_post_api(
    post_id: int,
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    await PostRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).like_post(post_id)


@router.post("/{post_id}/vote", response_model=PostOutput)
async def vote_post_api(
    post_id: int,
    vote_ids: list[str],
    mongo_db: AgnosticDatabase = Depends(depends.get_database),
    neo4j_db=Depends(depends.get_neo4j_database),
    current_user: User = Depends(
        depends.permissions([UserRole.AUTHENTICATED])
    ),
):
    post = await PostRepository(
        mongo_db=mongo_db, neo4j_db=neo4j_db, user=current_user
    ).vote_post(post_id, vote_ids)

    if not post:
        return JSONResponse(
            status_code=404, content={"message": "Post not found"}
        )

    return parse_obj_as(PostOutput, post)
