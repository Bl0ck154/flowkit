"""Pydantic models for video review results."""
from pydantic import BaseModel, Field
from typing import Literal, Optional


class SegmentScore(BaseModel):
    time_range: str
    score: float


class VideoError(BaseModel):
    # Closed on purpose. `has_critical_errors`, the character_consistency cap
    # and `_fix_guide` all branch on this exact string, so a severity outside
    # the set is not a cosmetic oddity — it silently disables all three.
    # Reviews are computed and returned, never read back from storage, so
    # narrowing the type cannot break a load of old data.
    severity: Literal["CRITICAL", "HIGH", "MINOR"]
    time_range: str
    description: str

    def format(self) -> str:
        return f"[{self.severity}] {self.time_range}: {self.description}"


class DimensionScores(BaseModel):
    character_consistency: float
    prompt_adherence: float
    motion_quality: float
    visual_fidelity: float
    temporal_coherence: float
    composition: float


class SceneReview(BaseModel):
    scene_id: str
    overall_score: float
    verdict: str  # excellent / good / acceptable / poor / unusable
    dimensions: DimensionScores
    errors: list[VideoError]
    usable_segments: list[SegmentScore]
    fix_guide: str
    frames_analyzed: int
    fps_used: float
    has_critical_errors: bool = False


class VideoReview(BaseModel):
    video_id: str
    project_id: str
    mode: str  # light / deep
    orientation: str
    overall_score: float
    verdict: str
    scene_reviews: list[SceneReview]
    scenes_reviewed: int
    scenes_skipped: int  # no video yet


class SceneScoreInput(BaseModel):
    """One scene's raw reviewer answer, as the agent scores it by hand.

    Same JSON shape a CLI reviewer returns: dimensions, errors,
    usable_segments. The server applies the identical validation, severity
    rules, CRITICAL caps, and overall computation as every other backend.
    """
    scene_id: str
    dimensions: DimensionScores
    errors: list[VideoError] = Field(default_factory=list)
    usable_segments: list[SegmentScore] = Field(default_factory=list)
    n_frames: int = 0
    fps: float = 4.0


class RegenerateAfterReviewRequest(BaseModel):
    """Review a video, then enqueue REGENERATE_VIDEO requests for bad scenes.

    Regeneration is bounded: at most ``max_regenerations`` REGENERATE_VIDEO
    requests are ever enqueued per scene (counted across all past runs).
    """
    project_id: str
    mode: str = "light"  # light (4fps) | deep (8fps)
    orientation: Optional[str] = None  # VERTICAL | HORIZONTAL (auto if omitted)
    scene_ids: Optional[list[str]] = None
    max_regenerations: int = 1
    provider: Optional[str] = None  # provider for the regen requests
    bad_verdicts: list[str] = Field(default_factory=lambda: ["poor", "unusable"])
    # Assistant-scored review: when present, the CLI/SDK review is skipped and
    # the VideoReview is computed from these scores instead.
    scores: Optional[list[SceneScoreInput]] = None


class SceneRegenDecision(BaseModel):
    scene_id: str
    verdict: str
    regenerated: bool
    request_id: Optional[str] = None
    reason: Optional[str] = None


class ReviewSheetsRequest(BaseModel):
    """Build contact sheets for agent self-review — no AI CLI involved."""
    project_id: str
    mode: str = "light"  # light (4fps) | deep (8fps)
    orientation: Optional[str] = None  # VERTICAL | HORIZONTAL (auto if omitted)
    scene_ids: Optional[list[str]] = None


class ReviewSheetInfo(BaseModel):
    scene_id: str
    sheets: list[str]  # absolute paths to contact sheet images
    n_frames: int
    fps: float
    timestamped: bool
    prompt: str  # the rubric prompt the reviewer should answer
    scene_prompt: str = ""
    video_prompt: str = ""
    character_names: list[str] = Field(default_factory=list)


class ReviewSheetsResponse(BaseModel):
    video_id: str
    project_id: str
    mode: str
    orientation: str
    sheets: list[ReviewSheetInfo]
    scenes_skipped: int = 0  # no fetchable video


class ReviewSubmitRequest(BaseModel):
    """Submit the agent\u2019s hand scores; the server computes the review."""
    project_id: str
    mode: str = "light"
    orientation: Optional[str] = None
    scores: list[SceneScoreInput]


class RegenerateAfterReviewResponse(BaseModel):
    review: VideoReview
    decisions: list[SceneRegenDecision]

