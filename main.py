"""
gesture_module.py
─────────────────
Handles:
  - MediaPipe Hands initialisation
  - Hand landmark drawing
  - Gesture classification: thumbsup / thumbsdown / none

Usage:
    from modules.gesture_module import create_hands, detect_gesture, mp_draw, mp_hands
"""

import mediapipe as mp

# ── MediaPipe setup ───────────────────────────────────────────────────────────
mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils


def create_hands(
    max_num_hands:           int   = 1,
    min_detection_confidence: float = 0.7,
    min_tracking_confidence:  float = 0.5,
):
    """Create and return a MediaPipe Hands solution instance.

    Call `.close()` on the returned object when done to free resources.

    Args:
        max_num_hands:            Maximum number of hands to detect.
        min_detection_confidence: Minimum confidence for initial detection.
        min_tracking_confidence:  Minimum confidence for subsequent tracking.

    Returns:
        mediapipe.solutions.hands.Hands
    """
    return mp_hands.Hands(
        max_num_hands=max_num_hands,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )


def detect_gesture(hand_landmarks) -> str:
    """Classify the current hand pose into one of three gestures.

    Logic:
      - "thumbsup"   : all four fingers folded AND thumb tip is clearly
                       above the thumb MCP joint (lower y value in image coords).
      - "thumbsdown" : all four fingers folded AND thumb tip is clearly
                       below the thumb MCP joint.
      - "none"       : fingers are open, or thumb position is ambiguous.

    Landmark indices used:
        2  = THUMB_MCP  (base knuckle)
        4  = THUMB_TIP
        8  = INDEX_TIP   (y > INDEX_PIP  → finger folded)
        12 = MIDDLE_TIP
        16 = RING_TIP
        20 = PINKY_TIP

    Args:
        hand_landmarks: mediapipe NormalizedLandmarkList

    Returns:
        "thumbsup" | "thumbsdown" | "none"
    """
    lm = hand_landmarks.landmark

    thumb_tip = lm[4].y
    thumb_mcp = lm[2].y

    # All four fingers must be folded (tip y > pip y  in image space)
    fingers_folded = all(lm[tip].y > lm[tip - 2].y for tip in [8, 12, 16, 20])

    if fingers_folded:
        if thumb_tip < thumb_mcp - 0.04:   # thumb pointing up
            return "thumbsup"
        if thumb_tip > thumb_mcp + 0.04:   # thumb pointing down
            return "thumbsdown"

    return "none"
