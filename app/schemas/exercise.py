"""Validated catalog content and explicit, versioned analysis metadata."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, HttpUrl, StringConstraints, model_validator

from app.core.enums import Difficulty, MuscleGroup
from app.schemas.base import ApiModel

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Landmark = Literal[
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]


class JointRange(ApiModel):
    min: float = Field(ge=0, le=180, allow_inf_nan=False)
    max: float = Field(ge=0, le=180, allow_inf_nan=False)
    ideal: float = Field(ge=0, le=180, allow_inf_nan=False)
    landmarks: tuple[Landmark, Landmark, Landmark]

    @model_validator(mode="after")
    def validate_angle(self) -> Self:
        if not self.min <= self.ideal <= self.max:
            raise ValueError("Angle must satisfy min <= ideal <= max")
        if len(set(self.landmarks)) != len(self.landmarks):
            raise ValueError("An angle needs three distinct landmarks; the middle is the vertex")
        return self


class ExerciseContent(ApiModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    name: Text
    muscle_group: MuscleGroup
    difficulty: Difficulty
    description: Text
    instructions: list[Text] = Field(min_length=1, max_length=20)
    common_mistakes: list[Text] = Field(min_length=1, max_length=20)
    primary_muscles: list[Text] = Field(min_length=1, max_length=10)
    secondary_muscles: list[Text] = Field(default_factory=list, max_length=10)
    joint_angles: dict[str, JointRange] = Field(default_factory=dict, max_length=20)
    required_keypoints: list[Landmark] = Field(default_factory=list, max_length=33)
    analysis_supported: bool = False
    analysis_version: int | None = Field(default=None, gt=0)
    camera_view: Literal["front", "side"] | None = None
    animation_url: HttpUrl | None = None
    thumbnail_url: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_analysis(self) -> Self:
        if len(set(self.required_keypoints)) != len(self.required_keypoints):
            raise ValueError("Required keypoints must not repeat")
        required = set(self.required_keypoints)
        if any(not set(angle.landmarks) <= required for angle in self.joint_angles.values()):
            raise ValueError("Angle landmarks must be included in requiredKeypoints")
        if self.analysis_supported and (
            not self.joint_angles or self.analysis_version is None or self.camera_view is None
        ):
            raise ValueError("Supported analysis requires angles, a version, and a camera view")
        return self


class ExerciseResponse(ExerciseContent):
    id: UUID
