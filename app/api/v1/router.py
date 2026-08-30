"""Registers all v1 endpoint routers under a single APIRouter."""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

# Endpoint routers are wired in here as each feature is implemented, e.g.:
# from app.api.v1.endpoints import auth, exercises, favorites, sessions, users
# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(exercises.router, prefix="/exercises", tags=["exercises"])
