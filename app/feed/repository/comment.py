import json

from fastapi import HTTPException
from motor.core import AgnosticDatabase

from app.apps.feed.models.comment import Comment
from app.apps.feed.schemas.comment import (
    CommentInput,
    CommentOutput,
    CommentsListParams,
    CommentUserInfo,
    PaginatedComments,
)
from app.core.neo4j import Base
from app.schemas.users import User


class CommentRepository(Base):
    def __init__(self, neo4j_db, mongo_db: AgnosticDatabase, user: User):
        self.mongo_db = mongo_db
        self.user = user

        super().__init__(neo4j_db)
        self.neo4j_db = neo4j_db

    async def create_comment(
        self, comment_data: CommentInput
    ) -> CommentOutput | None:
        comment = Comment.parse_obj(
            comment_data.dict() | (await self.get_user_info()).dict()
        )

        cypher = f"""
        MATCH (p:POST), (u:USER)
        WHERE ID(p) = $post_id AND u.user_id = $user_id
        CREATE (c:COMMENT {{
            {comment.get_cypher_fields()}
        }})
        CREATE (c)-[r1:BELONGS_TO]->(p)<-[r2:COMMENTED_ON]-(u),
               (c)-[r3:COMMENT_BY]->(u)
        SET p.comments_count = (p.comments_count + 1)
        RETURN ID(c) AS id, c
        """
        result = await self.neo4j_db.write_transaction(
            self.neo4j_executor, cypher, json.loads(comment.json())
        )

        if comment_data.parent_id:
            params = {
                "parent_id": comment_data.parent_id,
                "child_id": result[0]["id"],
            }
            cypher = """
            MATCH (pc:COMMENT), (cc:COMMENT)
            WHERE ID(pc) = $parent_id AND ID(cc) = $child_id
            CREATE (cc)-[r:REPLY_ON]->(pc)
            """
            await self.neo4j_db.write_transaction(
                self.neo4j_executor, cypher, params
            )

        return Comment.parse_obj(
            self.process_raw_graph(result, "c")[0]
        ).to_output()

    async def list_comments(
        self, params: CommentsListParams
    ) -> PaginatedComments:
        cypher = """
        MATCH (c:COMMENT)
        WITH count(c) AS total
        MATCH (c:COMMENT)-[r1:BELONGS_TO]->(p:POST)
        WHERE ID(p) = $post_id
        WITH c, total
        ORDER BY c.created_at DESC
        RETURN ID(c) AS id, c, total
        SKIP $offset LIMIT $limit
        """
        query_params = {
            "post_id": params.post_id,
            "offset": params.offset,
            "limit": params.limit,
        }
        result = await self.neo4j_db.read_transaction(
            self.neo4j_executor, cypher, query_params
        )
        comments = []
        count = 0
        if result:
            count = result[0]["total"]
            comments = [
                Comment.parse_obj(comment).to_output()
                for comment in self.process_raw_graph(result, "c")
            ]
        return PaginatedComments(data=comments, count=count)

    async def find_parent_id(self, comment_node_id: int) -> int | None:
        cypher = """
        MATCH (cc)-[r:REPLY_ON]->(pc)
        WHERE ID(cc) = $child_id
        RETURN ID(pc) AS parent_id
        """
        query_params = {"child_id": comment_node_id}
        # Execute the query in a read transaction
        result = await self.neo4j_db.read_transaction(
            self.neo4j_executor, cypher, query_params
        )
        try:
            return result[0].get("parent_id", 0)
        except Exception:
            return None

    async def delete_comment(self, comment_id: int):
        cypher = """
        MATCH (c:COMMENT)-[r1:BELONGS_TO]->(p:POST)
        WHERE ID(c) = $comment_id AND c.user_id = $user_id
        OPTIONAL MATCH (c)<-[r:REPLY_ON]-(cc:COMMENT)
        DETACH DELETE c, cc
        SET p.comments_count = (p.comments_count - 1)
        RETURN c
        """

        params = {"comment_id": comment_id, "user_id": str(self.user.id)}
        result = await self.neo4j_db.write_transaction(
            self.neo4j_executor, cypher, params
        )
        if not result:
            raise HTTPException(status_code=404, detail="Comment not found")

    async def get_user_info(self) -> CommentUserInfo:
        if personal_info := await self.mongo_db.personal.find_one(
            {"user_id": self.user.id}
        ):
            display_name = (
                personal_info["name"] + " " + personal_info["family"]
            )
            avatar = personal_info.get("image_AVATAR", None)
        elif company_info := await self.mongo_db.companies.find_one(
            {"user_id": self.user.id}
        ):

            display_name = company_info["company_name"]
            avatar = company_info.get("image_AVATAR", None)
        else:
            raise HTTPException(status_code=404, detail="User not found.")

        return CommentUserInfo(
            user_id=str(self.user.id),
            user_display_name=display_name,
            user_avatar=avatar,
        )
