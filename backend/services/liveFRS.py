"""Live-camera bridge from tracked person ROIs to the isolated FRS service."""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

import numpy as np

from services.frsClient import RemoteFRSClient
from services.personRecognition import detect_face_evidence_candidates

logger = logging.getLogger(__name__)
_client: RemoteFRSClient | None = None
_client_lock = threading.Lock()


def enabled() -> bool:
    return bool(os.getenv("FRS_REMOTE_URL", "").strip())


def _get_client() -> RemoteFRSClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = RemoteFRSClient(
                base_url=os.getenv("FRS_REMOTE_URL", ""),
                token=os.getenv("FRS_INTERNAL_TOKEN", ""),
                timeout_seconds=float(os.getenv("FRS_REQUEST_TIMEOUT_SECONDS", "3")),
                jpeg_quality=int(os.getenv("FRS_JPEG_QUALITY", "92")),
                failure_threshold=int(os.getenv("FRS_FAILURE_THRESHOLD", "3")),
                recovery_seconds=float(os.getenv("FRS_RECOVERY_SECONDS", "10")),
            )
        return _client


def _tracked_regions(frame: np.ndarray, tracked_persons: Any) -> list[tuple[str, list[int], np.ndarray]]:
    height, width = frame.shape[:2]
    boxes = getattr(tracked_persons, "xyxy", None) if tracked_persons is not None else None
    track_ids = getattr(tracked_persons, "tracker_id", None) if tracked_persons is not None else None
    regions: list[tuple[str, list[int], np.ndarray]] = []
    if boxes is None or track_ids is None:
        return [("untracked", [0, 0, width, height], frame)]
    for index in range(len(tracked_persons)):
        x1, y1, x2, y2 = (float(value) for value in boxes[index][:4])
        person_width, person_height = max(0.0, x2 - x1), max(0.0, y2 - y1)
        rx1 = max(0, int(x1 - person_width * 0.18)); ry1 = max(0, int(y1 - person_height * 0.10))
        rx2 = min(width, int(x2 + person_width * 0.18)); ry2 = min(height, int(y1 + person_height * 0.62))
        if rx2 - rx1 >= 24 and ry2 - ry1 >= 24:
            regions.append((str(track_ids[index]), [rx1, ry1, rx2, ry2], frame[ry1:ry2, rx1:rx2]))
    return regions


def match_live_faces(*, user_id: int, frame: np.ndarray, camera_id: str, timestamp: float, tracked_persons: Any = None) -> list[dict[str, Any]]:
    """Return confirmed remote watchlist matches without breaking camera flow."""
    if not enabled() or frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        return []
    matches: list[dict[str, Any]] = []
    client = _get_client()
    for track_id, region_box, region in _tracked_regions(frame, tracked_persons):
        try:
            candidates = detect_face_evidence_candidates(
                region,
                minimum_face_size=int(os.getenv("FRS_MIN_FACE_SIZE", "40")),
                minimum_detection_score=float(os.getenv("FRS_MIN_DETECTOR_CONFIDENCE", "0.70")),
                minimum_blur_score=float(os.getenv("FRS_MIN_BLUR", "20")),
                max_faces=2,
            )
            for candidate in candidates:
                x1, y1, x2, y2 = candidate["box"]
                crop = region[y1:y2, x1:x2]
                result = client.observe(
                    user_id=int(user_id), camera_id=str(camera_id), track_id=track_id,
                    timestamp=float(timestamp), face_image=crop,
                    detector_confidence=float(candidate.get("detection_score", 1.0)),
                )
                if result.get("confirmed") and result.get("identity_id"):
                    matches.append({
                        "remote_identity_id": str(result["identity_id"]),
                        "remote_similarity": float(result.get("similarity") or 0.0),
                        "tracker_id": track_id,
                        "box": [x1 + region_box[0], y1 + region_box[1], x2 + region_box[0], y2 + region_box[1]],
                        "detection_score": float(candidate.get("detection_score", 0.0)),
                    })
        except Exception as exc:
            logger.warning("Remote FRS unavailable; camera processing continues | camera_id=%s error=%s", camera_id, type(exc).__name__)
            break
    return matches
