import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from motor.core import AgnosticDatabase

from app.apps.feed.models.post import Post
from app.apps.feed.schemas.post import (
    PaginatedPosts,
    PollDurations,
    PollOptionResult,
    PostInput,
    PostOutput,
    PostsListParams,
    PostUserInfo,
    VotingTypes,
)
from app.core.date import utcnow
from app.core.neo4j import Base
from app.schemas.users import User


class PostRepository(Base):
    def __init__(self, neo4j_db, mongo_db: AgnosticDatabase, user: User):
        self.mongo_db = mongo_db
        self.user = user

        super().__init__(neo4j_db)
        self.neo4j_db = neo4j_db

    async def create_post(self, post_data: PostInput) -> PostOutput:
        post = Post.from_input(post_data, await self.get_user_info())

        cypher = f"""
        MATCH (u:USER)
        WHERE u.user_id = $user_id
        CREATE (p:POST:{post_data.post_type} {{
            {post.get_cypher_fields()}
        }})
        CREATE (p)-[r:CREATED_BY]->(u)
        RETURN ID(p) AS id, p, labels(p)[1] AS type
        """

        result = await self.neo4j_db.write_transaction(
            self.neo4j_executor, cypher, json.loads(post.json())
        )
        result = self.process_raw_graph(result, "p")
        post_node = Post.parse_obj(result[0])
        return post_node.to_output()

    async def get_post(self, post_id: int) -> PostOutput | None:
        cypher = """
        MATCH (p:POST) WHERE ID(p) = $post_id
        RETURN ID(p) AS id, p, labels(p)[1] AS type
        """
        params = {"post_id": post_id}
        result = await self.neo4j_db.read_transaction(
            self.neo4j_executor, cypher, params
        )
        if not result:
            return None

        result = Post.parse_obj(self.process_raw_graph(result, "p")[0])
        return result.to_output()

    async def list_posts(self, params: PostsListParams) -> PaginatedPosts:
        cypher = """
        MATCH (pc:POST)
        WITH count(pc) AS total
        MATCH (p:POST)
        WITH p, total
        ORDER BY p.created_at DESC
        RETURN ID(p) AS id, p, labels(p)[1] AS type, total
        SKIP $offset LIMIT $limit
        """
        query_params = {"offset": params.offset, "limit": params.limit}
        result = await self.neo4j_db.read_transaction(
            self.neo4j_executor, cypher, query_params
        )
        posts = []
        count = 0
        if result:
            result = self.process_raw_graph(result, "p")
            count = result[0]["total"]
            posts = [
                Post.parse_obj(post_node).to_output() for post_node in result
            ]
        return PaginatedPosts(data=posts, count=count)

    async def update_post(
        self, post_id: int, post_data: PostInput
    ) -> PostOutput | None:
        post = Post.from_input(post_data, await self.get_user_info())

        cypher = f"""
        MATCH (p:POST:{post_data.post_type})
        WHERE
        ID(p) = $post_id AND
        p.user_id = $user_id
        SET p += $update_params
        RETURN ID(p) AS id, p, labels(p)[1] AS type
        """

        update_params = {
            "post_id": post_id,
            "user_id": str(self.user.id),
            "update_params": json.loads(post.json()),
        }
        result = await self.neo4j_db.write_transaction(
            self.neo4j_executor, cypher, update_params
        )
        if not result:
            return None

        result = self.process_raw_graph(result, "p")
        post_node = Post.parse_obj(result[0])
        return post_node.to_output()

    async def delete_post(self, post_id: int) -> None:
        cypher = """
        MATCH (p:POST)
        WHERE
        ID(p) = $post_id AND
        p.user_id = $user_id
        OPTIONAL MATCH (c:COMMENT)-[r1:BELONGS_TO]->(p)
        DETACH DELETE p, c
        RETURN p
        """
        params = {"post_id": post_id, "user_id": str(self.user.id)}

        result = await self.neo4j_db.write_transaction(
            self.neo4j_executor, cypher, params
        )
        if not result:
            raise HTTPException(status_code=404, detail="Post not found")

    async def like_post(self, post_id: int) -> None:
        # Remove the previous like
        cypher = """
        MATCH (u:USER) -[pr:LIKE]-> (p:POST)
        WHERE
        ID(p) = $post_id AND
        u.user_id = $user_id
        DELETE pr
        SET p.likes_count = (p.likes_count - 1)
        """
        params = {"post_id": post_id, "user_id": str(self.user.id)}
        await self.neo4j_db.write_transaction(
            self.neo4j_executor, cypher, params
        )

        # Create new one
        cypher = """
        MATCH (p:POST), (u:USER)
        WHERE
        ID(p) = $post_id AND
        u.user_id = $user_id
        CREATE (u) -[r:LIKE {created_at: $created_at}] -> (p)
        SET p.likes_count = (p.likes_count + 1)
        """
        params |= {"created_at": utcnow().timestamp()}
        await self.neo4j_db.write_transaction(
            self.neo4j_executor, cypher, params
        )

    async def vote_post(
        self, post_id: int, vote_options: list[str]
    ) -> PostOutput:
        cypher = """
        MATCH (p:POST:POLL)
        WHERE ID(p) = $post_id
        RETURN ID(p) AS id, p, labels(p)[1] AS type
        """
        query_params: dict[str, Any] = {"post_id": post_id}
        result = await self.neo4j_db.read_transaction(
            self.neo4j_executor, cypher, query_params
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Poll not found",
            )
        result = self.process_raw_graph(result, "p")[0]
        await self.poll_expiration_checker(
            poll_created_at=result.get("created_at", 0),
            poll_duration=result.get("duration", 0),
        )
        await self.poll_options_checker(
            poll_options=result.get("options"),
            selected_options=vote_options,
            poll_voting_type=result.get("voting_type", None),
        )

        cypher = """
        MATCH (u:USER {user_id: $user_id}), (p:POST:POLL)
        WHERE ID(p) = $post_id
        OPTIONAL MATCH (u)-[pr:VOTED]->(p)
        RETURN pr
        """
        query_params |= dict(user_id=str(self.user.id))
        if await self.neo4j_db.read_transaction(
            self.neo4j_executor, cypher, query_params
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Already voted",
            )

        cypher = """
        MATCH (u:USER {user_id: $user_id}), (p:POST:POLL)
        WHERE ID(p) = $post_id
        OPTIONAL MATCH (u)-[pr:VOTED]->(p)
        DELETE pr

        // Create a new VOTED relationship with new properties
        CREATE (u)-[r:VOTED {
            selected_options: $selected_options, created_at: $created_at
        }]->(p)

        // Return the post details
        RETURN ID(p) AS id, p, labels(p)[1] AS type
        """
        query_params |= {
            "user_id": str(self.user.id),
            "selected_options": vote_options,
            "created_at": utcnow().timestamp(),
        }
        final_result = await self.neo4j_db.write_transaction(
            self.neo4j_executor, cypher, query_params
        )
        post = Post.parse_obj(self.process_raw_graph(final_result, "p")[0])
        return post.to_output()

    @staticmethod
    async def poll_expiration_checker(
        poll_created_at: float, poll_duration: PollDurations
    ) -> None:
        created_at_datetime = datetime.fromtimestamp(poll_created_at)
        expiration_date = created_at_datetime + timedelta(days=poll_duration)
        current_time = utcnow()
        if current_time >= expiration_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The poll was expired",
            )

    @staticmethod
    async def poll_options_checker(
        poll_options: list[str],
        selected_options: list[str],
        poll_voting_type: VotingTypes,
    ) -> None:
        if (
            poll_voting_type == VotingTypes.SINGLE_VOTE
            and len(selected_options) != 1
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Single vote type requires exactly one option to be"
                    " selected."
                ),
            )
        elif (
            poll_voting_type == VotingTypes.MULTI_VOTE and not selected_options
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Multi-vote type requires at least one option to be"
                    " selected."
                ),
            )
        if set(selected_options) > set(poll_options):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The selected options are not exist in this poll.",
            )

    async def get_user_info(self) -> PostUserInfo:
        if personal_info := await self.mongo_db.personal.find_one(
            {"user_id": self.user.id}
        ):
            display_name = (
                personal_info["name"] + " " + personal_info["family"]
            )
            headline = personal_info.get("headline")
            avatar = personal_info.get("image_AVATAR", None)
        elif company_info := await self.mongo_db.companies.find_one(
            {"user_id": self.user.id}
        ):

            display_name = company_info["company_name"]
            headline = None
            avatar = company_info.get("image_AVATAR", None)
        else:
            raise HTTPException(status_code=404, detail="User not found.")

        return PostUserInfo(
            user_id=str(self.user.id),
            user_display_name=display_name,
            user_headline=headline,
            user_avatar=avatar,
        )

    async def poll_options_process(
        self, post_node: dict
    ) -> list[PollOptionResult]:
        # Create PollOptionResult instances for each option in the post_node
        return_options = [
            PollOptionResult(title=opt, count=0, chosen=False)
            for opt in post_node["options"]
        ]

        # Define the Cypher query to get counts of each selected option and
        # check which are chosen
        cypher = """
        MATCH (:USER)-[v:VOTED]->(p:POST:POLL)
        WHERE ID(p) = $post_id
        UNWIND v.selected_options AS option
        WITH option, count(option) AS count
        OPTIONAL MATCH (uc:USER)-[vc:VOTED]->(pc)
        WHERE ID(pc) = $post_id AND uc.user_id = $user_id
        RETURN collect({
            option: option, count: count
        }) AS optionsCount, vc.selected_options AS chosen
        """
        params = {
            "post_id": post_node.get("id", 0),
            "user_id": str(self.user.id),
        }

        # Execute the Cypher query using a read transaction
        result = await self.neo4j_db.read_transaction(
            self.neo4j_executor, cypher, params
        )

        if result:
            # Create a dictionary for quick option count lookup
            options_count_dict = {
                op["option"]: op["count"] for op in result[0]["optionsCount"]
            }
            # Create a set for quick 'chosen' lookup
            chosen_titles = (
                set(result[0]["chosen"]) if result[0].get("chosen") else set()
            )

            # Update return_options based on the results
            for element in return_options:
                element.count = options_count_dict.get(element.title, 0)
                element.chosen = element.title in chosen_titles

        return return_options
