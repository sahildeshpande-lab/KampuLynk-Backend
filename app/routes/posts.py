from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import User
from ..models.schemas import (
    ApiResponse,
    CommentCreateRequest,
    CommentUpdateRequest,
    PostCreateRequest,
    PostReactionRequest,
    PostUpdateRequest,
    ReplyCreateRequest,
    RepostCreateRequest,
)
from ..services import post_service
from .shared import api_response, get_current_user

POST_TAG = "7] Posts"

router = APIRouter(tags=[POST_TAG])


@router.get("/feed", response_model=ApiResponse)
def get_feed(
    cursor: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return api_response("Feed fetched", post_service.list_feed(db, cursor=cursor, limit=limit))


@router.post("/posts", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = post_service.create_post(db, current_user, payload)
    return api_response("Post created", post_service.post_to_schema(db, post))


@router.get("/posts/{postId}", response_model=ApiResponse)
def get_post(postId: str, db: Session = Depends(get_db)):
    post = post_service.post_or_404(db, postId)
    return api_response("Post fetched", post_service.post_to_schema(db, post, include_comments=True))


@router.patch("/posts/{postId}", response_model=ApiResponse)
def update_post(
    postId: str,
    payload: PostUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = post_service.update_post(db, current_user, postId, payload)
    return api_response("Post updated", post_service.post_to_schema(db, post))


@router.post("/posts/{postId}/rescan", response_model=ApiResponse)
def manual_rescan_post(
    postId: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = post_service.manual_rescan_post(db, current_user, postId)
    return api_response("Post rescanned", post_service.post_to_schema(db, post))


@router.delete("/posts/{postId}", response_model=ApiResponse)
def delete_post(
    postId: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post_service.delete_post(db, current_user, postId)
    return api_response("Post archived")


@router.post("/posts/{postId}/reactions", response_model=ApiResponse)
def upsert_post_reaction(
    postId: str,
    payload: PostReactionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = post_service.upsert_post_reaction(db, current_user, postId, payload or PostReactionRequest())
    return api_response("Reaction updated", data)


@router.delete("/posts/{postId}/reactions", response_model=ApiResponse)
def delete_post_reaction(
    postId: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = post_service.delete_post_reaction(db, current_user, postId)
    return api_response("Reaction deleted", data)


@router.post("/posts/{postId}/comments", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    postId: str,
    payload: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = post_service.create_comment(db, current_user, postId, payload)
    return api_response("Comment created", post_service.comment_to_schema(comment, {}))


@router.post("/comments/{commentId}/replies", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_reply(
    commentId: str,
    payload: ReplyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = post_service.create_reply(db, current_user, commentId, payload)
    return api_response("Reply created", post_service.comment_to_schema(comment, {}))


@router.patch("/posts/{postId}/comments/{commentId}", response_model=ApiResponse)
def update_comment(
    postId: str,
    commentId: str,
    payload: CommentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = post_service.update_comment(db, current_user, postId, commentId, payload.content)
    return api_response("Comment updated", post_service.comment_to_schema(comment, {}))


@router.delete("/posts/{postId}/comments/{commentId}", response_model=ApiResponse)
def delete_comment(
    postId: str,
    commentId: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post_service.delete_comment(db, current_user, postId, commentId)
    return api_response("Comment deleted")


@router.post("/posts/{postId}/repost", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_repost(
    postId: str,
    payload: RepostCreateRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repost = post_service.create_repost(db, current_user, postId, payload or RepostCreateRequest())
    return api_response("Post reposted", {"id": repost.id, "postId": postId, "quote": repost.quote})
