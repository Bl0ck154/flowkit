"""Pydantic models for TTS endpoints."""
from pydantic import BaseModel, Field
from typing import Optional, Literal


class TTSGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    instruct: Optional[str] = Field(None, max_length=200)
    ref_audio: Optional[str] = Field(None, max_length=500)
    ref_text: Optional[str] = None
    speed: float = Field(1.0, ge=0.5, le=3.0)
    provider: Optional[str] = Field(
        None,
        description="'local' (default) or a media provider name — "
                    "a provider job (kind=audio) is queued for an external worker",
    )


class TTSGenerateResponse(BaseModel):
    audio_path: str
    duration: Optional[float] = None
    sample_rate: int = 24000


class NarrateVideoRequest(BaseModel):
    project_id: str
    orientation: Literal["HORIZONTAL", "VERTICAL"] = "HORIZONTAL"
    speed: float = Field(1.0, ge=0.5, le=3.0)
    instruct: Optional[str] = Field(None, max_length=200)
    ref_audio: Optional[str] = Field(None, max_length=500)  # Path to voice template WAV
    ref_text: Optional[str] = None   # Transcript of ref_audio (auto-resolved from template)
    template: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")  # Voice template name
    mix: bool = True
    sfx_volume: float = Field(0.4, ge=0.0, le=2.0)
    from_scene: Optional[int] = Field(None, ge=0)  # Start display_order (inclusive)
    to_scene: Optional[int] = Field(None, ge=0)    # End display_order (inclusive)


class SceneNarrationResult(BaseModel):
    scene_id: str
    display_order: int
    narrator_text: Optional[str] = None
    audio_path: Optional[str] = None
    duration: Optional[float] = None
    status: str  # COMPLETED, SKIPPED, FAILED
    error: Optional[str] = None


class NarrateVideoResponse(BaseModel):
    video_id: str
    project_id: str
    scenes: list[SceneNarrationResult]
    scenes_narrated: int
    scenes_skipped: int
    scenes_failed: int
    total_narration_duration: Optional[float] = None


class VoiceTemplateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)  # Sample text to generate voice template
    instruct: str = Field(..., max_length=200)  # Voice design: "male, low pitch, young adult"
    name: str = Field("voice_template_1", pattern=r"^[a-zA-Z0-9_-]{1,64}$")  # Template name for saving
    speed: float = Field(1.0, ge=0.5, le=3.0)


class VoiceTemplateResponse(BaseModel):
    name: str
    audio_path: str
    text: str
    instruct: str
    duration: Optional[float] = None
    sample_rate: int = 24000


class VoiceTemplateListItem(BaseModel):
    name: str
    audio_path: str
    duration: Optional[float] = None
