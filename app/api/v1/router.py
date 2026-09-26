"""Versioned public endpoint registration."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, exercises, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])

api_router.include_router(exercises.router, prefix="/exercises", tags=["exercises"])
