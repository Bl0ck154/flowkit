"""FastAPI router for video review endpoints."""
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request

from agent.config import BASE_DIR
from agent.utils.slugify import slugify
from agent.models.review import (
    VideoReview,
    SceneReview,
    RegenerateAfterReviewRequest,
    RegenerateAfterReviewResponse,
    SceneRegenDecision,
    SceneScoreInput,
    ReviewSheetsRequest,
    ReviewSheetInfo,
    ReviewSheetsResponse,
    ReviewSubmitRequest,
)
from agent.services.video_reviewer import (
    review_video,
    review_scene_video,
    prepare_review_sheets,
    score_review_answer,
)
from agent.db.crud import (
    get_video,
    get_scene,
    get_project,
    get_project_characters,
    list_scenes,
    create_request,
    list_requests,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["reviews"])


@router.post("/{vid}/review", response_model=VideoReview)
async def review_video_endpoint(
    vid: str,
    project_id: str = Query(..., description="Project ID"),
    mode: str = Query("light", description="Review mode: light (4fps) or deep (8fps)"),
    orientation: Optional[str] = Query(None, description="Orientation: VERTICAL or HORIZONTAL (auto-detected if omitted)"),
    scene_ids: Optional[str] = Query(None, description="Comma-separated scene IDs to review (omit for all)"),
):
    """Review all scene videos in a video using AI vision frame analysis."""
    if mode not in ("light", "deep"):
        raise HTTPException(400, "mode must be 'light' or 'deep'")
    if orientation and orientation.upper() not in ("VERTICAL", "HORIZONTAL"):
        raise HTTPException(400, "orientation must be 'VERTICAL' or 'HORIZONTAL'")

    video = await get_video(vid)
    if not video:
        raise HTTPException(404, "Video not found")

    # Use video-level orientation first, then fall back to scene auto-detect
    if not orientation:
        if video.get("orientation"):
            orientation = video["orientation"]
        else:
            orientation = await _detect_orientation(vid)
    else:
        orientation = orientation.upper()

    parsed_scene_ids = [s.strip() for s in scene_ids.split(",") if s.strip()] if scene_ids else None
    logger.info("Starting %s review for video %s (project %s, %s, scenes=%s)", mode, vid, project_id, orientation, len(parsed_scene_ids) if parsed_scene_ids else "all")
    try:
        result = await review_video(vid, project_id, mode=mode, orientation=orientation, scene_ids=parsed_scene_ids)
    except Exception as e:
        logger.exception("Review failed for video %s: %s", vid, e)
        raise HTTPException(500, f"Review failed: {e}")

    return result


@router.post("/{vid}/review-regenerate", response_model=RegenerateAfterReviewResponse)
async def review_and_regenerate_endpoint(vid: str, body: RegenerateAfterReviewRequest):
    """Review scene videos, then enqueue REGENERATE_VIDEO for bad scenes.

    Bounded: at most ``max_regenerations`` regen requests are ever enqueued
    per scene. The worker queue picks the new requests up; regeneration goes
    through the same provider path as the original generation.

    When ``body.scores`` is provided (agent-scored review), the
    CLI/SDK review is skipped and the VideoReview is computed from those
    scores instead.
    """
    if body.mode not in ("light", "deep"):
        raise HTTPException(400, "mode must be 'light' or 'deep'")
    if body.max_regenerations < 0:
        raise HTTPException(400, "max_regenerations must be >= 0")

    video = await get_video(vid)
    if not video:
        raise HTTPException(404, "Video not found")

    orientation = (body.orientation or video.get("orientation") or "VERTICAL").upper()
    if orientation not in ("VERTICAL", "HORIZONTAL"):
        raise HTTPException(400, "orientation must be 'VERTICAL' or 'HORIZONTAL'")

    if body.scores is not None:
        review = _review_from_scores(
            vid, body.project_id, body.mode, orientation, body.scores)
    else:
        try:
            review = await review_video(
                vid, body.project_id, mode=body.mode,
                orientation=orientation, scene_ids=body.scene_ids)
        except Exception as e:
            logger.exception("Review failed for video %s: %s", vid, e)
            raise HTTPException(500, f"Review failed: {e}")

    decisions = await _decide_regenerations(review, body, vid, orientation)
    return RegenerateAfterReviewResponse(review=review, decisions=decisions)


def _review_from_scores(
    vid: str, project_id: str, mode: str, orientation: str,
    scores: list[SceneScoreInput],
) -> VideoReview:
    """Compute a VideoReview from agent-submitted scores.

    Same validation, severity rules, CRITICAL caps, and overall computation
    as every other reviewer backend.
    """
    from agent.services.video_reviewer import _verdict

    scene_reviews = []
    for s in scores:
        try:
            scene_reviews.append(score_review_answer(
                s.scene_id,
                {"dimensions": s.dimensions.model_dump(),
                 "errors": [e.model_dump() for e in s.errors],
                 "usable_segments": [sg.model_dump() for sg in s.usable_segments]},
                s.n_frames, s.fps,
            ))
        except Exception as e:
            raise HTTPException(400, f"Invalid score for scene {s.scene_id}: {e}")
    if not scene_reviews:
        raise HTTPException(400, "scores must not be empty")
    overall = sum(r.overall_score for r in scene_reviews) / len(scene_reviews)
    return VideoReview(
        video_id=vid, project_id=project_id, mode=mode, orientation=orientation,
        overall_score=overall, verdict=_verdict(overall),
        scene_reviews=scene_reviews,
        scenes_reviewed=len(scene_reviews), scenes_skipped=0,
    )


async def _decide_regenerations(
    review: VideoReview, body: RegenerateAfterReviewRequest,
    vid: str, orientation: str,
) -> list[SceneRegenDecision]:
    """Enqueue REGENERATE_VIDEO for bad/critical scenes, bounded per scene."""
    bad = {v.strip().lower() for v in body.bad_verdicts}
    decisions: list[SceneRegenDecision] = []
    for sr in review.scene_reviews:
        if sr.verdict.lower() not in bad and not sr.has_critical_errors:
            decisions.append(SceneRegenDecision(
                scene_id=sr.scene_id, verdict=sr.verdict,
                regenerated=False, reason="verdict acceptable"))
            continue

        past = [r for r in await list_requests(scene_id=sr.scene_id)
                if r.get("type") == "REGENERATE_VIDEO"]
        if len(past) >= body.max_regenerations:
            decisions.append(SceneRegenDecision(
                scene_id=sr.scene_id, verdict=sr.verdict,
                regenerated=False,
                reason=f"bound reached ({len(past)} >= {body.max_regenerations})"))
            continue

        scene = await get_scene(sr.scene_id)
        if not scene or not scene.get(
                f"{'vertical' if orientation == 'VERTICAL' else 'horizontal'}_image_media_id"):
            decisions.append(SceneRegenDecision(
                scene_id=sr.scene_id, verdict=sr.verdict,
                regenerated=False, reason="no scene image to regenerate from"))
            continue

        req = await create_request(
            "REGENERATE_VIDEO", orientation=orientation, scene_id=sr.scene_id,
            video_id=vid, project_id=body.project_id, provider=body.provider)
        decisions.append(SceneRegenDecision(
            scene_id=sr.scene_id, verdict=sr.verdict,
            regenerated=True, request_id=req["id"]))
    return decisions


@router.post("/{vid}/scenes/{sid}/review", response_model=SceneReview)
async def review_scene_endpoint(
    vid: str,
    sid: str,
    project_id: str = Query(..., description="Project ID"),
    mode: str = Query("light", description="Review mode: light (4fps) or deep (8fps)"),
    orientation: Optional[str] = Query(None, description="Orientation: VERTICAL or HORIZONTAL (auto-detected if omitted)"),
):
    """Review a single scene video using AI vision frame analysis."""
    if mode not in ("light", "deep"):
        raise HTTPException(400, "mode must be 'light' or 'deep'")
    if orientation and orientation.upper() not in ("VERTICAL", "HORIZONTAL"):
        raise HTTPException(400, "orientation must be 'VERTICAL' or 'HORIZONTAL'")

    scene = await get_scene(sid)
    if not scene:
        raise HTTPException(404, "Scene not found")
    if scene.get("video_id") != vid:
        raise HTTPException(404, "Scene does not belong to this video")

    # Use video-level orientation first, then fall back to scene auto-detect
    if not orientation:
        video = await get_video(vid)
        if video and video.get("orientation"):
            orientation = video["orientation"]
        else:
            orientation = await _detect_orientation(vid)
    else:
        orientation = orientation.upper()

    characters = await get_project_characters(project_id)

    logger.info("Starting %s review for scene %s (%s)", mode, sid, orientation)
    try:
        result = await review_scene_video(scene, characters, mode=mode, orientation=orientation, project_id=project_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Review failed for scene %s: %s", sid, e)
        raise HTTPException(500, f"Review failed: {e}")

    return result


async def _detect_orientation(video_id: str) -> str:
    """Auto-detect orientation from scene video status fields."""
    scenes = await list_scenes(video_id)
    for scene in scenes:
        if scene.get("horizontal_video_status") == "COMPLETED" and scene.get("horizontal_video_url"):
            return "HORIZONTAL"
        if scene.get("vertical_video_status") == "COMPLETED" and scene.get("vertical_video_url"):
            return "VERTICAL"
    # Fallback: check image status
    for scene in scenes:
        if scene.get("horizontal_image_status") == "COMPLETED":
            return "HORIZONTAL"
        if scene.get("vertical_image_status") == "COMPLETED":
            return "VERTICAL"
    return "VERTICAL"


@router.post("/{vid}/review-sheets", response_model=ReviewSheetsResponse)
async def review_sheets_endpoint(vid: str, body: ReviewSheetsRequest):
    """Build contact sheets for agent self-review — no AI CLI needed.

    Extracts frames and tiles them into contact sheets persisted under the
    project's ``review/sheets/`` dir, then returns the sheet paths plus the
    rubric prompt the reviewer should answer. The agent (Muse, Codex, or
    agy) reads the sheets with its own vision, scores each scene, and
    submits via ``POST .../review-submit``.
    """
    if body.mode not in ("light", "deep"):
        raise HTTPException(400, "mode must be 'light' or 'deep'")

    video = await get_video(vid)
    if not video:
        raise HTTPException(404, "Video not found")
    project = await get_project(body.project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    orientation = (body.orientation or video.get("orientation") or "VERTICAL").upper()
    if orientation not in ("VERTICAL", "HORIZONTAL"):
        raise HTTPException(400, "orientation must be 'VERTICAL' or 'HORIZONTAL'")

    name = project["name"] if isinstance(project, dict) else project.name
    persist = BASE_DIR / "output" / slugify(name) / "review" / "sheets"
    persist.mkdir(parents=True, exist_ok=True)

    scenes = await list_scenes(vid)
    if body.scene_ids:
        wanted = set(body.scene_ids)
        scenes = [s for s in scenes if s["id"] in wanted]
    characters = await get_project_characters(body.project_id)

    infos: list[ReviewSheetInfo] = []
    skipped = 0
    for scene in sorted(scenes, key=lambda s: s.get("display_order", 0)):
        try:
            info = await prepare_review_sheets(
                scene, characters, body.mode, orientation, persist)
        except (ValueError, RuntimeError) as e:
            logger.warning("Skipping scene %s for review sheets: %s", scene["id"], e)
            skipped += 1
            continue
        infos.append(ReviewSheetInfo(**info))

    return ReviewSheetsResponse(
        video_id=vid, project_id=body.project_id, mode=body.mode,
        orientation=orientation, sheets=infos, scenes_skipped=skipped,
    )


@router.post("/{vid}/review-submit", response_model=VideoReview)
async def review_submit_endpoint(vid: str, body: ReviewSubmitRequest):
    """Submit the agent\u2019s per-scene hand scores; the server computes the review.

    Accepts the same JSON shape a CLI reviewer returns (dimensions, errors,
    usable_segments) and applies identical validation, severity rules,
    CRITICAL caps, and overall computation. Feed the result into
    ``POST .../review-regenerate`` via its ``scores`` field to auto-regenerate
    bad scenes.
    """
    if body.mode not in ("light", "deep"):
        raise HTTPException(400, "mode must be 'light' or 'deep'")

    video = await get_video(vid)
    if not video:
        raise HTTPException(404, "Video not found")

    orientation = (body.orientation or video.get("orientation") or "VERTICAL").upper()
    if orientation not in ("VERTICAL", "HORIZONTAL"):
        raise HTTPException(400, "orientation must be 'VERTICAL' or 'HORIZONTAL'")

    return _review_from_scores(vid, body.project_id, body.mode, orientation, body.scores)
