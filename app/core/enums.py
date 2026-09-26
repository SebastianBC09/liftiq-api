"""Domain values shared by persistence and request/response schemas."""

from enum import StrEnum


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class TrainingGoal(StrEnum):
    STRENGTH = "strength"
    HYPERTROPHY = "hypertrophy"
    TECHNIQUE = "technique"
    GENERAL_FITNESS = "general_fitness"


class RevocationReason(StrEnum):
    ROTATED = "rotated"
    LOGOUT = "logout"
    REUSE = "reuse"


class MuscleGroup(StrEnum):
    CHEST = "chest"
    BACK = "back"
    LEGS = "legs"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    CORE = "core"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
