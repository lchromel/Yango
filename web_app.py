import json
import os
import shlex
import shutil
import subprocess
import tempfile
import textwrap
import urllib.request
import urllib.error
import base64
import binascii
import hmac
import re
import threading
import time
import zipfile
import hashlib
import uuid
import cgi
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import Iterable, Optional, Union

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from bot import (
    PromptRequest,
    classify_vehicle_profile_with_openai,
    generate_prompt_with_openai,
    infer_car_with_year_with_openai,
    infer_vehicle_profile_from_keywords,
)


HOST = os.getenv("HOST", "0.0.0.0")
try:
    PORT = int(os.getenv("PORT", "8080"))
except ValueError:
    PORT = 8080
ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output" / "banners"
GENERATED_DIR = ROOT / "output" / "generated"
ZIP_DIR = ROOT / "output" / "archives"
UNCROP_DIR = ROOT / "output" / "uncrop"
VIDEO_DIR = ROOT / "output" / "videos"
DEFAULT_PACKSHOT_VIDEO = ROOT / "assets" / "video" / "packshot.mp4"
IMAGE_LIBRARY_FILE = ROOT / "output" / "image_library.json"
IMAGE_LIBRARY_LOCK = threading.Lock()
VIDEO_LIBRARY_FILE = ROOT / "output" / "video_library.json"
VIDEO_LIBRARY_LOCK = threading.Lock()
WEB_APP_BASIC_AUTH_USERNAME = os.getenv("WEB_APP_BASIC_AUTH_USERNAME", "").strip()
WEB_APP_BASIC_AUTH_PASSWORD = os.getenv("WEB_APP_BASIC_AUTH_PASSWORD", "")
AUTH_COOKIE_NAME = "drive_perf_auth"
HEADLINE_ITALIC_FONT_CANDIDATES = [
    ROOT / "assets" / "fonts" / "YangoGroupHeadline-HeavyItalic.ttf",
]

BANNER_SIZE_MAP = {
    "1200x1200": (1200, 1200),
    "1200x1350": (1200, 1350),
    "1200x628": (1200, 628),
    "1080x1920": (1080, 1920),
}

BADGE_LAYOUT_BY_SIZE = {
    "1200x628": {
        "x": 914.82373046875,
        "y": 396.5033264160156,
        "w": 264.9485779882407,
        "h": 152.60372516282246,
        "radius": 19.819,
        "padding": 14.006,
        "gap": 11.279,
        "top_font_size": 45.116,
        "bottom_font_size": 95.349,
    },
    "1200x1200": {
        "x": 752.45068359375,
        "y": 505.1037292480469,
        "w": 378.0260082370387,
        "h": 219.16941789846555,
        "radius": 28.339,
        "padding": 20.027,
        "gap": 16.128,
        "top_font_size": 64.51,
        "bottom_font_size": 136.337,
    },
    "1200x1350": {
        "x": 752.45068359375,
        "y": 646.3955078125,
        "w": 378.0260082370387,
        "h": 219.16941789846555,
        "radius": 28.339,
        "padding": 20.027,
        "gap": 16.128,
        "top_font_size": 64.51,
        "bottom_font_size": 136.337,
    },
    "1080x1920": {
        "x": 583.751220703125,
        "y": 906.2279052734375,
        "w": 439.02736480896954,
        "h": 254.22379678045627,
        "radius": 32.873,
        "padding": 23.231,
        "gap": 18.708,
        "top_font_size": 74.832,
        "bottom_font_size": 158.151,
    },
}

CENTER_BADGE_Y_ADJUST_BY_SIZE = {
    "1200x628": 0,
    "1200x1350": -56,
    "1080x1920": 24,
}

RIGHT_BADGE_Y_ADJUST_BY_SIZE = {
    "1200x628": -24,
    "1200x1200": -40,
    "1200x1350": -48,
    "1080x1920": -20,
}

CENTER_BADGE_SPACING_LOCK_BY_SIZE = {
    # Keep center spacing stable and independent from right-align tuning.
    "1200x1200": -24,
    "1200x1350": -32,
    "1080x1920": 24,
}

ANGLE_RULES = {
    "Front 3/4": (
        "Front 3/4: front corner must be dominant, visible front fascia + one side plane, "
        "foreshortening toward rear, vehicle heading aligned with lane direction. "
        "Not a pure side profile."
    ),
    "Rear 3/4": (
        "Rear 3/4: rear corner must be dominant, visible rear fascia + one side plane, "
        "foreshortening toward front, vehicle heading aligned with lane direction. "
        "Not a pure side profile."
    ),
    "Front 3/4 Low Angle": (
        "Front 3/4 Low Angle: low near-ground front-corner dominance, visible front fascia + side plane, "
        "strong foreground depth, lane-consistent heading. Not a pure side profile."
    ),
    "Rear 3/4 Low Angle": (
        "Rear 3/4 Low Angle: low near-ground rear-corner dominance, visible rear fascia + side plane, "
        "strong depth, lane-consistent heading. Not a pure side profile."
    ),
    "Clean Side Profile": (
        "Clean Side Profile: true side profile, parallel camera-to-vehicle geometry, "
        "car aligned with lane flow, minimal 3/4 distortion."
    ),
    "Centered Front Shot": (
        "Centered Front Shot: symmetrical frontal composition from lane centerline, "
        "front fascia dominant, heading straight along lane direction."
    ),
    "Rear Light Hero Shot": (
        "Rear Light Hero Shot: rear-biased hero framing emphasizing taillight signature, "
        "rear corner readable, lane-consistent heading, not a pure side profile."
    ),
    "Dynamic Tracking Shot": (
        "Dynamic Tracking Shot: camera movement coherent with vehicle path, strong directional flow, "
        "car heading aligned with lane direction, non-static cinematic motion."
    ),
}


def is_basic_auth_enabled() -> bool:
    return bool(WEB_APP_BASIC_AUTH_USERNAME and WEB_APP_BASIC_AUTH_PASSWORD)


def is_request_authorized(authorization_header: str) -> bool:
    if not is_basic_auth_enabled():
        return True

    header_value = str(authorization_header or "").strip()
    if not header_value.startswith("Basic "):
        return False

    encoded = header_value[6:].strip()
    if not encoded:
        return False

    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False

    username, separator, password = decoded.partition(":")
    if not separator:
        return False

    return hmac.compare_digest(username, WEB_APP_BASIC_AUTH_USERNAME) and hmac.compare_digest(
        password, WEB_APP_BASIC_AUTH_PASSWORD
    )


def _build_auth_cookie_value() -> str:
    digest = hashlib.sha256(
        f"{WEB_APP_BASIC_AUTH_USERNAME}:{WEB_APP_BASIC_AUTH_PASSWORD}".encode("utf-8")
    ).hexdigest()
    return digest


def _parse_cookie_header(cookie_header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for chunk in str(cookie_header or "").split(";"):
        part = chunk.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def is_request_authorized_by_cookie(cookie_header: str) -> bool:
    if not is_basic_auth_enabled():
        return True
    cookies = _parse_cookie_header(cookie_header)
    auth_cookie = cookies.get(AUTH_COOKIE_NAME, "")
    if not auth_cookie:
        return False
    return hmac.compare_digest(auth_cookie, _build_auth_cookie_value())


def _ensure_output_directories() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    UNCROP_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)


def _utc_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _load_image_library_records_unlocked() -> list[dict]:
    _ensure_output_directories()
    if not IMAGE_LIBRARY_FILE.exists():
        return []
    try:
        raw = json.loads(IMAGE_LIBRARY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _save_image_library_records_unlocked(records: list[dict]) -> None:
    _ensure_output_directories()
    temp_path = IMAGE_LIBRARY_FILE.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(IMAGE_LIBRARY_FILE)


def _infer_library_kind_from_name(file_name: str) -> str:
    name = str(file_name or "").lower()
    if name.startswith("edited_"):
        return "edited"
    if name.startswith("generated_"):
        return "generated"
    return "uploaded"


def _public_image_library_record(record: dict) -> dict:
    image_url = str(record.get("image_url", "")).strip()
    banner_source_url = str(record.get("banner_source_url", "")).strip()
    return {
        "id": str(record.get("id", "")).strip(),
        "image_url": image_url,
        "banner_source_url": banner_source_url,
        "effective_banner_source_url": banner_source_url or image_url,
        "banner_ready": bool(banner_source_url),
        "kind": str(record.get("kind", "generated")).strip() or "generated",
        "created_at": str(record.get("created_at", "")).strip(),
        "label": str(record.get("label", "")).strip(),
        "prompt": str(record.get("prompt", "")).strip(),
        "car_model": str(record.get("car_model", "")).strip(),
        "color_name": str(record.get("color_name", "")).strip(),
        "original_name": str(record.get("original_name", "")).strip(),
        "edit_prompt": str(record.get("edit_prompt", "")).strip(),
        "source_image_url": str(record.get("source_image_url", "")).strip(),
    }


def list_image_library() -> list[dict]:
    with IMAGE_LIBRARY_LOCK:
        records = _load_image_library_records_unlocked()
        return [_public_image_library_record(item) for item in records]


def _upsert_image_library_record(
    image_url: str,
    *,
    kind: str,
    banner_source_url: str = "",
    prompt: str = "",
    car_model: str = "",
    color_name: str = "",
    original_name: str = "",
    edit_prompt: str = "",
    source_image_url: str = "",
    label: str = "",
) -> dict:
    normalized_image_url = str(image_url or "").strip()
    if not normalized_image_url:
        raise ValueError("image_url is required")

    with IMAGE_LIBRARY_LOCK:
        records = _load_image_library_records_unlocked()

        record = None
        for item in records:
            if str(item.get("image_url", "")).strip() == normalized_image_url:
                record = item
                break

        if record is None:
            record = {
                "id": uuid.uuid4().hex,
                "image_url": normalized_image_url,
                "created_at": _utc_timestamp(),
            }
            records.append(record)

        record["kind"] = str(kind or record.get("kind") or "generated").strip() or "generated"
        record["image_url"] = normalized_image_url
        record["banner_source_url"] = str(banner_source_url or record.get("banner_source_url") or "").strip()
        record["prompt"] = str(prompt or record.get("prompt") or "").strip()
        record["car_model"] = str(car_model or record.get("car_model") or "").strip()
        record["color_name"] = str(color_name or record.get("color_name") or "").strip()
        record["original_name"] = str(original_name or record.get("original_name") or "").strip()
        record["edit_prompt"] = str(edit_prompt or record.get("edit_prompt") or "").strip()
        record["source_image_url"] = str(source_image_url or record.get("source_image_url") or "").strip()
        if label:
            record["label"] = str(label).strip()
        elif not str(record.get("label", "")).strip():
            record["label"] = Path(urlparse(normalized_image_url).path).stem or record["kind"]

        records.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        _save_image_library_records_unlocked(records)
        return _public_image_library_record(record)


def get_image_library_record(image_url: str) -> Optional[dict]:
    normalized_image_url = str(image_url or "").strip()
    if not normalized_image_url:
        return None

    with IMAGE_LIBRARY_LOCK:
        records = _load_image_library_records_unlocked()
        for item in records:
            if str(item.get("image_url", "")).strip() == normalized_image_url:
                return dict(item)
    return None


def update_image_library_banner_source(image_url: str, banner_source_url: str) -> Optional[dict]:
    normalized_image_url = str(image_url or "").strip()
    normalized_banner_source_url = str(banner_source_url or "").strip()
    if not normalized_image_url:
        return None

    with IMAGE_LIBRARY_LOCK:
        records = _load_image_library_records_unlocked()
        for item in records:
            if str(item.get("image_url", "")).strip() != normalized_image_url:
                continue
            item["banner_source_url"] = normalized_banner_source_url
            _save_image_library_records_unlocked(records)
            return _public_image_library_record(item)
    return None


def delete_image_library_record(image_url: str) -> bool:
    normalized_image_url = str(image_url or "").strip()
    if not normalized_image_url:
        return False

    with IMAGE_LIBRARY_LOCK:
        records = _load_image_library_records_unlocked()
        filtered_records = [
            item for item in records if str(item.get("image_url", "")).strip() != normalized_image_url
        ]
        if len(filtered_records) == len(records):
            return False
        _save_image_library_records_unlocked(filtered_records)
        return True


def _load_video_library_records_unlocked() -> list[dict]:
    _ensure_output_directories()
    if not VIDEO_LIBRARY_FILE.exists():
        return []
    try:
        raw = json.loads(VIDEO_LIBRARY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _save_video_library_records_unlocked(records: list[dict]) -> None:
    _ensure_output_directories()
    temp_path = VIDEO_LIBRARY_FILE.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(VIDEO_LIBRARY_FILE)


def _public_video_library_record(record: dict) -> dict:
    return {
        "id": str(record.get("id", "")).strip(),
        "video_url": str(record.get("video_url", "")).strip(),
        "base_video_url": str(record.get("base_video_url", "")).strip(),
        "created_at": str(record.get("created_at", "")).strip(),
        "source_image_url": str(record.get("source_image_url", "")).strip(),
        "prompt": str(record.get("prompt", "")).strip(),
        "label": str(record.get("label", "")).strip(),
        "headlines": [
            str(item or "").strip()
            for item in record.get("headlines", [])
            if str(item or "").strip()
        ],
    }


def _list_selectable_video_library_records(records: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    seen_source_urls: set[str] = set()
    for item in sorted(records, key=lambda entry: str(entry.get("created_at", "")), reverse=True):
        if not isinstance(item, dict):
            continue
        source_url = str(item.get("base_video_url") or item.get("video_url") or "").strip()
        if not source_url or source_url in seen_source_urls:
            continue
        seen_source_urls.add(source_url)
        normalized_item = dict(item)
        normalized_item["video_url"] = source_url
        normalized_item["base_video_url"] = source_url
        normalized.append(normalized_item)
    return normalized


def list_video_library() -> list[dict]:
    with VIDEO_LIBRARY_LOCK:
        records = _load_video_library_records_unlocked()
        selectable_records = _list_selectable_video_library_records(records)
        return [_public_video_library_record(item) for item in selectable_records]


def _upsert_video_library_record(
    video_url: str,
    *,
    base_video_url: str = "",
    source_image_url: str = "",
    prompt: str = "",
    headlines: Optional[list[str]] = None,
    label: str = "",
) -> dict:
    normalized_video_url = str(video_url or "").strip()
    if not normalized_video_url:
        raise ValueError("video_url is required")

    with VIDEO_LIBRARY_LOCK:
        records = _load_video_library_records_unlocked()

        record = None
        for item in records:
            if str(item.get("video_url", "")).strip() == normalized_video_url:
                record = item
                break

        if record is None:
            record = {
                "id": uuid.uuid4().hex,
                "video_url": normalized_video_url,
                "created_at": _utc_timestamp(),
            }
            records.append(record)

        cleaned_headlines = [
            str(item or "").strip() for item in (headlines or []) if str(item or "").strip()
        ]
        record["video_url"] = normalized_video_url
        record["base_video_url"] = str(base_video_url or record.get("base_video_url") or normalized_video_url).strip()
        record["source_image_url"] = str(source_image_url or record.get("source_image_url") or "").strip()
        record["prompt"] = str(prompt or record.get("prompt") or "").strip()
        record["headlines"] = cleaned_headlines or record.get("headlines") or []
        if label:
            record["label"] = str(label).strip()
        elif not str(record.get("label", "")).strip():
            record["label"] = Path(urlparse(normalized_video_url).path).stem or "video"

        records.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        _save_video_library_records_unlocked(records)
        return _public_video_library_record(record)


def delete_video_library_record(video_url: str) -> bool:
    normalized_video_url = str(video_url or "").strip()
    if not normalized_video_url:
        return False

    with VIDEO_LIBRARY_LOCK:
        records = _load_video_library_records_unlocked()
        filtered_records = [
            item
            for item in records
            if str(item.get("video_url", "")).strip() != normalized_video_url
            and str(item.get("base_video_url", "")).strip() != normalized_video_url
        ]
        if len(filtered_records) == len(records):
            return False
        _save_video_library_records_unlocked(filtered_records)
        return True


def get_video_library_record(video_url: str) -> Optional[dict]:
    normalized_video_url = str(video_url or "").strip()
    if not normalized_video_url:
        return None

    with VIDEO_LIBRARY_LOCK:
        records = _load_video_library_records_unlocked()
        for item in records:
            if str(item.get("video_url", "")).strip() == normalized_video_url or str(
                item.get("base_video_url", "")
            ).strip() == normalized_video_url:
                return dict(item)
    return None


def load_tokens_from_file() -> None:
    candidate_paths = [
        Path.home() / "Desktop" / "tokens.txt",
        ROOT / "tokens.txt",
    ]

    for tokens_path in candidate_paths:
        if not tokens_path.exists():
            continue

        for raw_line in tokens_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            key = None
            value = None
            if "=" in line:
                key, value = line.split("=", 1)
            elif ":" in line:
                key, value = line.split(":", 1)

            if key is not None and value is not None:
                env_key = key.strip().upper()
                env_value = value.strip().strip("\"'")
                if env_key in {
                    "TELEGRAM_BOT_TOKEN",
                    "OPENAI_API_KEY",
                    "OPENAI_MODEL",
                    "GEMINI_API_KEY",
                    "GEMINI_MODEL",
                    "RECRAFT_API_KEY",
                    "RECRAFT_API_TOKEN",
                    "RECRAFT_MODEL",
                    "RECRAFT_SIZE",
                    "KLING_ACCESS_KEY",
                    "KLING_SECRET_KEY",
                    "REPLICATE_API_TOKEN",
                    "REPLICATE_MODEL",
                    "CLIPDROP_API_KEY",
                } and env_value:
                    os.environ.setdefault(env_key, env_value)
                continue

            # Raw token fallback format.
            if line.startswith("sk-"):
                os.environ.setdefault("OPENAI_API_KEY", line)
            elif ":" in line and len(line) > 20:
                os.environ.setdefault("TELEGRAM_BOT_TOKEN", line)


load_tokens_from_file()


def call_openai(
    car_model: str,
    color_name: str,
    color_hex: str,
    preferred_angle_label: str,
) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    angle_label = preferred_angle_label.strip()
    angle_rules = ANGLE_RULES.get(angle_label, "")

    request = PromptRequest(
        car=car_model,
        color=color_name,
        location_text=None,
        preferred_angle=angle_rules or None,
        preferred_angle_label=angle_label or None,
    )

    try:
        request.car_with_year = infer_car_with_year_with_openai(request)
    except Exception:
        request.car_with_year = request.car

    try:
        request.vehicle_profile = classify_vehicle_profile_with_openai(request)
    except Exception:
        request.vehicle_profile = infer_vehicle_profile_from_keywords(request)

    # Keep color hex available if needed by future prompt logic.
    _ = color_hex
    return generate_prompt_with_openai(request)


def _fallback_edit_suggestions(car_model: str) -> list[str]:
    _ = car_model.strip() or "car"
    return [
        "stylish emirati man in a clean white polo, tapered trousers, premium sneakers, silver watch, walking toward the car with key fob in hand",
        "indian woman in a modern casual look: cropped blazer, wide-leg jeans, sleek sneakers, statement earrings, approaching the car with a small shoulder bag",
        "european couple in elevated casual outfits: man in unstructured blazer with chinos, woman in a minimalist co-ord set, both walking toward the car together",
        "fashion-forward filipino man in relaxed luxury: short-sleeve knit polo, pleated trousers, loafers, sunglasses, approaching the car with a leather weekender",
    ]


def _contains_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text or ""))


def _translate_suggestions_to_english_with_openai(suggestions: list[str]) -> list[str]:
    if not os.getenv("OPENAI_API_KEY"):
        return []
    if not suggestions:
        return []

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    system_prompt = (
        "You translate short UI suggestion lines into English. "
        "Output valid JSON only."
    )
    user_prompt = (
        "Translate each line to natural English and keep meaning. "
        "Keep action as approaching/walking toward the car, never getting into the car. "
        "Keep concise, concrete clothing/accessory details, no poetry. "
        "Return strict JSON array of strings only.\n\n"
        f"LINES:\n{json.dumps(suggestions, ensure_ascii=False)}"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
        out = [str(item).strip(" .") for item in parsed if isinstance(item, str) and item.strip()]
        return out
    except Exception:
        return []


def generate_edit_suggestions_with_openai(car_model: str, base_prompt: str) -> list[str]:
    if not os.getenv("OPENAI_API_KEY"):
        return _fallback_edit_suggestions(car_model)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    car = car_model.strip() or "car"
    base = base_prompt.strip() or ""
    system_prompt = (
        "You generate concise image-edit suggestion lines for a Dubai car ad workflow. "
        "English only. Never use Russian or any non-English language. "
        "Output must be valid JSON only."
    )
    user_prompt = (
        "Generate 4 short image-edit suggestion lines in English for UI chips. "
        "Each line must include only character styling details: who they are, what exactly they wear, accessories/items they carry, "
        "and the action of approaching the car / walking toward the car. "
        "Characters should be realistic Dubai residents with varied national backgrounds. "
        "Make suggestions more interesting than single generic people: at least one line should feature a stylish couple. "
        "Use elevated casual fashion only: polished casual and modern street-luxury, never formal eveningwear. "
        "Imply lifestyle through styling only, "
        "but do not explicitly say phrases like going to dinner, going to theatre, date night, event, etc. "
        "Never use actions like getting into the car, sitting in the car, opening the door, entering the vehicle. "
        "No poetic lines. No abstract style commentary. Only concrete wardrobe and object details. "
        "Do not include instructions about composition, motion, location, background, or camera. "
        "Do not start with verbs like Add/Create/Insert. "
        "Format each item as one lowercase line, around 14-26 words. "
        "CRITICAL: keep location/environment unchanged from the base generation. "
        f"car: {car}. "
        f"base prompt (location source): {base}. "
        "Return strict JSON array of 4 strings only."
    )

    def _request_suggestions() -> list[str]:
        response = client.chat.completions.create(
            model=model,
            temperature=0.8,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        suggestions = json.loads(raw)
        if not isinstance(suggestions, list):
            raise ValueError("Suggestions are not a list")
        return suggestions

    try:
        suggestions = _request_suggestions()
        cleaned: list[str] = []
        for item in suggestions:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if not text:
                continue
            text = text.strip(" .")
            lowered = text.lower()
            banned_actions = (
                "getting into",
                "gets into",
                "get into",
                "sits in",
                "sitting in",
                "steps into",
                "entering the car",
                "enters the car",
                "opens the door",
            )
            if any(token in lowered for token in banned_actions):
                text = re.sub(
                    r"\b(getting into|get into|gets into|sits in|sitting in|steps into|entering the car|enters the car|opens the door)\b",
                    "approaching the car",
                    text,
                    flags=re.IGNORECASE,
                )
            cleaned.append(text)
        if cleaned:
            cleaned = cleaned[:4]
            if any(_contains_cyrillic(line) for line in cleaned):
                # One retry with an explicit hard constraint.
                suggestions = _request_suggestions()
                cleaned = []
                for item in suggestions:
                    if not isinstance(item, str):
                        continue
                    text = item.strip().strip(" .")
                    if not text:
                        continue
                    lowered = text.lower()
                    banned_actions = (
                        "getting into",
                        "gets into",
                        "get into",
                        "sits in",
                        "sitting in",
                        "steps into",
                        "entering the car",
                        "enters the car",
                        "opens the door",
                    )
                    if any(token in lowered for token in banned_actions):
                        text = re.sub(
                            r"\b(getting into|get into|gets into|sits in|sitting in|steps into|entering the car|enters the car|opens the door)\b",
                            "approaching the car",
                            text,
                            flags=re.IGNORECASE,
                        )
                    cleaned.append(text)
                cleaned = cleaned[:4]
            if any(_contains_cyrillic(line) for line in cleaned):
                translated = _translate_suggestions_to_english_with_openai(cleaned)
                if translated:
                    cleaned = translated[:4]
            # Final hard guard: never return non-English/cyrillic lines to UI.
            if any(_contains_cyrillic(line) for line in cleaned):
                return _fallback_edit_suggestions(car_model)
            return cleaned
    except Exception:
        pass

    return _fallback_edit_suggestions(car_model)


def generate_video_prompt_with_openai(
    car_model: str,
    image_url: str,
    color_name: str = "",
    base_prompt: str = "",
) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    car = str(car_model or "").strip() or "car"
    color = str(color_name or "").strip() or "unspecified"
    image = str(image_url or "").strip()
    base = str(base_prompt or "").strip()
    if not image:
        raise RuntimeError("image_url is required")
    image_data_url = _image_input_data_url_from_url(image)

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You write premium cinematic vehicle-video prompts for Kling 3.0. "
                    "Output only one final prompt in English. "
                    "The prompt must be production-ready and based on the reference image plus the provided car model. "
                    "Preserve the visible car identity, color family, body style, and premium tone from the image. "
                    "Write exactly six scenes labeled Scene 1 through Scene 6, then finish with one Style line. "
                    "Each scene must be 1-2 sentences and specify camera placement, movement, motion feel, environment, lighting, and emotional tone. "
                    "Keep the video realistic, expensive, and commercially strong. "
                    "No markdown, no bullet points, no JSON, no explanations."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Create a Kling 3.0 video generation prompt for this car photo. "
                            f"Car model: {car}. "
                            f"Color name: {color}. "
                            "Build a high-end automotive commercial with six scenes. "
                            "Favor a modern premium city world unless the image clearly suggests another environment. "
                            "Vary the scenes across: ultra-low tracking shot, macro detail shot, side tracking shot, interior cabin shot, aerial or drone hero motion, and final hero stop. "
                            "Keep the car moving in most scenes and keep the world physically believable. "
                            "Prefer bright daylight or refined city light by default, not golden hour, unless the reference image strongly suggests otherwise. "
                            f"Base image prompt for context: {base or 'not provided'}"
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url,
                    },
                ],
            },
        ],
    )
    prompt = (response.output_text or "").strip()
    if not prompt:
        raise RuntimeError("OpenAI returned an empty video prompt")
    return prompt


def _closest_video_aspect_ratio_for_image(image_url: str) -> str:
    try:
        raw = _read_image_bytes_from_url(image_url)
        with Image.open(BytesIO(raw)) as image:
            width, height = image.size
    except Exception:
        return "16:9"

    if width <= 0 or height <= 0:
        return "16:9"

    target = width / height
    candidates = {
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "1:1": 1.0,
        "4:5": 4 / 5,
        "5:4": 5 / 4,
    }
    return min(candidates, key=lambda key: abs(candidates[key] - target))


def _walk_json_values(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk_json_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_json_values(item)


def _extract_kling_task_id(payload: dict) -> str:
    for key, value in _walk_json_values(payload):
        if str(key).lower() in {"task_id", "taskid"} and isinstance(value, str) and value.strip():
            return value.strip()
    for key, value in _walk_json_values(payload):
        if str(key).lower() == "id" and isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_kling_status(payload: dict) -> str:
    for key, value in _walk_json_values(payload):
        if str(key).lower() in {"status", "state", "task_status"} and isinstance(value, str):
            return value.strip().lower()
    return ""


def _extract_kling_video_url(payload: dict) -> str:
    preferred_keys = {
        "video_url",
        "video",
        "play_url",
        "download_url",
        "result_url",
        "url",
        "src",
    }
    for key, value in _walk_json_values(payload):
        key_name = str(key).lower()
        if key_name not in preferred_keys:
            continue
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            lower = value.lower()
            if any(ext in lower for ext in (".mp4", ".mov", ".webm", "video")):
                return value
    for _key, value in _walk_json_values(payload):
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            lower = value.lower()
            if any(ext in lower for ext in (".mp4", ".mov", ".webm")):
                return value
    return ""


def _get_kling_task_payload(task_id: str) -> dict:
    base_url = _kling_api_base_url().rstrip("/")
    headers = _kling_headers()
    candidates = [
        f"{base_url}/v1/videos/image2video/{task_id}",
        f"{base_url}/v1/videos/{task_id}",
    ]
    last_error: Optional[Exception] = None
    for url in candidates:
        try:
            return _request_json(url, "GET", headers)
        except RuntimeError as exc:
            last_error = exc
            if "HTTP 404" in str(exc):
                continue
            raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("Kling task query failed")


def _save_generated_video_local(remote_url: str) -> str:
    _ensure_output_directories()
    raw = _download_remote_bytes(remote_url)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parsed = urlparse(remote_url)
    ext = Path(parsed.path).suffix.lower()
    if ext not in {".mp4", ".mov", ".webm"}:
        ext = ".mp4"
    file_name = f"video_{stamp}{ext}"
    file_path = VIDEO_DIR / file_name
    file_path.write_bytes(raw)
    return f"/output/videos/{file_name}"


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _generate_kling_api_token() -> str:
    access_key = os.getenv("KLING_ACCESS_KEY", "").strip()
    secret_key = os.getenv("KLING_SECRET_KEY", "").strip()
    if not access_key:
        raise RuntimeError("KLING_ACCESS_KEY is not set")
    if not secret_key:
        raise RuntimeError("KLING_SECRET_KEY is not set")

    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + 1800,
        "nbf": now - 5,
    }
    header_segment = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_segment = _base64url_encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _kling_headers() -> dict:
    api_token = _generate_kling_api_token()
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }


def _chunk_scene_prompts(scene_prompts: list[str], max_chunks: int) -> list[str]:
    if max_chunks <= 0:
        return []
    if len(scene_prompts) <= max_chunks:
        return scene_prompts[:]

    grouped: list[str] = []
    total = len(scene_prompts)
    start = 0
    for chunk_index in range(max_chunks):
        next_start = round((chunk_index + 1) * total / max_chunks)
        items = scene_prompts[start:next_start]
        start = next_start
        if not items:
            continue
        grouped.append(" ".join(items))
    return grouped


def _truncate_kling_shot_prompt(text: str, limit: int = 500) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    truncated = cleaned[:limit].rsplit(" ", 1)[0].strip(" ,;:-")
    return truncated or cleaned[:limit].strip()


def _build_kling_multi_prompt(prompt: str, total_duration: int) -> Optional[list[dict[str, Union[str, int]]]]:
    text = str(prompt or "").strip()
    if not text or total_duration <= 0:
        return None

    style_match = re.search(r"Style:\s*(.+)$", text, flags=re.IGNORECASE | re.DOTALL)
    style_suffix = ""
    if style_match:
        style_text = style_match.group(1).strip()
        if style_text:
            style_suffix = f" Style: {style_text}"
        text = text[:style_match.start()].strip()

    matches = list(re.finditer(r"Scene\s*(\d+)\s*:\s*", text, flags=re.IGNORECASE))
    if len(matches) < 2:
        return None

    scenes: list[str] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        scene_text = text[start:end].strip()
        if scene_text:
            scenes.append(re.sub(r"\s+", " ", scene_text))

    if len(scenes) < 2:
        return None

    max_shots = min(6, total_duration)
    shot_prompts = _chunk_scene_prompts(scenes[:6], max_shots)
    if len(shot_prompts) < 2:
        return None

    base_duration = total_duration // len(shot_prompts)
    remainder = total_duration % len(shot_prompts)
    if base_duration < 1:
        return None

    multi_prompt: list[dict[str, Union[str, int]]] = []
    for index, scene_text in enumerate(shot_prompts):
        scene_duration = base_duration + (1 if index < remainder else 0)
        if scene_duration < 1:
            scene_duration = 1
        full_prompt = _truncate_kling_shot_prompt(f"{scene_text}{style_suffix}".strip())
        multi_prompt.append(
            {
                "index": index + 1,
                "prompt": full_prompt,
                "duration": str(scene_duration),
            }
        )

    return multi_prompt


def _kling_api_base_url() -> str:
    return "https://api-singapore.klingai.com"


def _normalize_kling_mode(raw_mode: str) -> str:
    _ = raw_mode
    return "pro"


def _normalize_kling_duration(raw_duration: str) -> str:
    try:
        duration = int(raw_duration or "5")
    except (TypeError, ValueError):
        duration = 5
    if duration >= 15:
        return "15"
    if duration >= 10:
        return "10"
    return "5"


def _kling_create_image_to_video_task(image_url: str, prompt: str) -> dict:
    headers = _kling_headers()
    base_url = _kling_api_base_url()
    duration = _normalize_kling_duration(os.getenv("KLING_DURATION", "5"))
    multi_prompt = _build_kling_multi_prompt(prompt, int(duration))
    negative_prompt = os.getenv("KLING_NEGATIVE_PROMPT", "").strip()
    payload = {
        "model_name": "kling-v3",
        "prompt": str(prompt or "").strip(),
        "image": _image_base64_from_url(image_url),
        "duration": duration,
        "aspect_ratio": _closest_video_aspect_ratio_for_image(image_url),
        "mode": _normalize_kling_mode("pro"),
        "sound": "on",
    }
    if multi_prompt:
        payload["multi_shot"] = True
        payload["shot_type"] = "customize"
        payload["multi_prompt"] = multi_prompt
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    return _request_json(f"{base_url}/v1/videos/image2video", "POST", headers, payload)


def _resolve_output_url_to_path(url: str) -> Path:
    value = str(url or "").strip()
    if not value.startswith("/"):
        raise RuntimeError("Expected local output URL")
    path = (ROOT / value.lstrip("/")).resolve()
    output_root = (ROOT / "output").resolve()
    if not str(path).startswith(str(output_root)):
        raise RuntimeError("Resolved path is outside output directory")
    return path


def _ffmpeg_binary() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg is not installed")
    return path


def _ffprobe_binary() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise RuntimeError("ffprobe is not installed")
    return path


def _run_subprocess(args: list[str]) -> None:
    completed = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or "Subprocess failed")


def _probe_video_metadata(path: Path) -> dict:
    ffprobe = _ffprobe_binary()
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or "ffprobe failed")
    return json.loads(completed.stdout or "{}")


def _video_dimensions_and_duration(path: Path) -> tuple[int, int, float]:
    meta = _probe_video_metadata(path)
    streams = meta.get("streams") or []
    width = 0
    height = 0
    duration = 0.0
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        if str(stream.get("codec_type", "")).lower() != "video":
            continue
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        duration = float(stream.get("duration") or 0.0)
        break
    if duration <= 0:
        fmt = meta.get("format") if isinstance(meta, dict) else None
        if isinstance(fmt, dict):
            duration = float(fmt.get("duration") or 0.0)
    if width <= 0 or height <= 0 or duration <= 0:
        raise RuntimeError("Could not read video dimensions or duration")
    return width, height, duration


def _escape_drawtext_value(value: str) -> str:
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def _ffmpeg_drawtext_path(path: Path) -> str:
    return _escape_drawtext_value(str(path.resolve()))


def _prepare_video_headline_text(text: str, width: int, height: int) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    headline_font_path = ROOT / "assets" / "fonts" / "YangoGroupHeadline-Heavy.ttf"
    font_size = max(36, int(round(width * (74 / 1024))))
    max_width = max(220, int(round(width * (682.215 / 1024))))
    img = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(img)
    font = _load_font(headline_font_path, font_size)
    wrapped = _wrap_text_by_width(draw, raw.upper(), font, max_width)
    return wrapped.strip()


def _headline_segments(headlines: list[str], main_duration: float) -> list[tuple[float, float, str]]:
    cleaned = [str(item or "").strip() for item in headlines if str(item or "").strip()]
    if not cleaned or main_duration <= 0:
        return []
    segments: list[tuple[float, float, str]] = []
    cursor = 0.0
    for text in cleaned:
        if cursor >= main_duration:
            break
        end = min(main_duration, cursor + 5.0)
        if end - cursor <= 0:
            break
        segments.append((cursor, end, text))
        cursor = end
    return segments


def _build_logo_overlay_filter(width: int, height: int) -> str:
    logo_font = ROOT / "assets" / "fonts" / "YangoGroupHeadline-HeavyItalic.ttf"
    logo_font_size = max(28, int(round(width * (52.833 / 1024))))
    logo_x = int(round(width * (48 / 1024)))
    logo_y = int(round(height * (48 / 576)))
    return (
        "drawtext="
        f"fontfile='{_ffmpeg_drawtext_path(logo_font)}':"
        "text='YANGO DRIVE':"
        f"fontsize={logo_font_size}:"
        "fontcolor=white@0.58:"
        f"x={logo_x}:y={logo_y}"
    )


def _build_title_overlay_filters(width: int, height: int, main_duration: float, headlines: list[str], temp_dir: Path) -> list[str]:
    filters: list[str] = [_build_logo_overlay_filter(width, height)]
    if main_duration <= 0:
        return filters

    headline_font = ROOT / "assets" / "fonts" / "YangoGroupHeadline-Heavy.ttf"
    headline_font_size = max(36, int(round(width * (74 / 1024))))
    title_x = int(round(width * (48 / 1024)))
    bottom_padding = int(round(height * (48 / 576)))
    line_spacing = int(round(-headline_font_size * 0.08))
    for index, (start, end, text) in enumerate(_headline_segments(headlines, main_duration)):
        prepared = _prepare_video_headline_text(text, width, height)
        if not prepared:
            continue
        text_file = temp_dir / f"title_{index + 1}.txt"
        text_file.write_text(prepared, encoding="utf-8")
        filters.append(
            "drawtext="
            f"fontfile='{_ffmpeg_drawtext_path(headline_font)}':"
            f"textfile='{_ffmpeg_drawtext_path(text_file)}':"
            "reload=0:"
            f"fontsize={headline_font_size}:"
            "fontcolor=white:"
            f"line_spacing={line_spacing}:"
            f"x={title_x}:y=h-th-{bottom_padding}:"
            f"enable='between(t,{start:.3f},{end:.3f})'"
        )
    return filters


def _compose_video_with_titles_and_packshot(base_video_local_url: str, headlines: list[str], packshot_path: Optional[Path] = None) -> str:
    ffmpeg = _ffmpeg_binary()
    base_video_path = _resolve_output_url_to_path(base_video_local_url)
    if not base_video_path.exists():
        raise RuntimeError("Base video file not found")

    width, height, duration = _video_dimensions_and_duration(base_video_path)
    packshot_file = packshot_path or DEFAULT_PACKSHOT_VIDEO
    use_packshot = packshot_file.exists() and duration > 2.1
    packshot_duration = 2.0 if use_packshot else 0.0
    main_duration = max(0.1, duration - packshot_duration)

    with tempfile.TemporaryDirectory(prefix="drive_perf_video_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        main_video = temp_dir / "main.mp4"
        filter_chain = ",".join(_build_title_overlay_filters(width, height, main_duration, headlines, temp_dir)) or "null"
        _run_subprocess(
            [
                ffmpeg,
                "-y",
                "-i",
                str(base_video_path),
                "-an",
                "-t",
                f"{main_duration:.3f}",
                "-vf",
                filter_chain,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(main_video),
            ]
        )

        final_source = main_video
        if use_packshot:
            packshot_video = temp_dir / "packshot.mp4"
            _run_subprocess(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(packshot_file),
                    "-an",
                    "-t",
                    "2.000",
                    "-vf",
                    f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(packshot_video),
                ]
            )

            final_output = temp_dir / "final.mp4"
            _run_subprocess(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(main_video),
                    "-i",
                    str(packshot_video),
                    "-filter_complex",
                    "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
                    "-map",
                    "[outv]",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(final_output),
                ]
            )
            final_source = final_output

        _ensure_output_directories()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_name = f"video_final_{stamp}.mp4"
        final_path = VIDEO_DIR / final_name
        shutil.copyfile(final_source, final_path)
        return f"/output/videos/{final_name}"


def remix_video_titles(base_video_url: str, headlines: Optional[list[str]] = None) -> str:
    return _compose_video_with_titles_and_packshot(base_video_url, headlines or [])


def generate_video_with_kling(image_url: str, prompt: str, headlines: Optional[list[str]] = None) -> tuple[str, str, str]:
    prediction = _kling_create_image_to_video_task(image_url=image_url, prompt=prompt)
    timeout_seconds = int(os.getenv("KLING_TIMEOUT_SECONDS", "240") or "240")
    poll_interval = float(os.getenv("KLING_POLL_INTERVAL_SECONDS", "5") or "5")
    started = time.time()
    task_id = _extract_kling_task_id(prediction)
    if not task_id:
        raise RuntimeError("Kling task id is missing")

    while time.time() - started < timeout_seconds:
        payload = _get_kling_task_payload(task_id)
        status = _extract_kling_status(payload)
        video_url = _extract_kling_video_url(payload)
        if video_url:
            raw_local_video_url = _save_generated_video_local(video_url)
            final_video_url = _compose_video_with_titles_and_packshot(raw_local_video_url, headlines or [])
            return video_url, raw_local_video_url, final_video_url
        if status in {"failed", "canceled", "cancelled"}:
            error_detail = str(payload.get("message") or payload.get("error") or status).strip()
            raise RuntimeError(f"Kling generation failed: {error_detail}")
        time.sleep(max(1.0, poll_interval))

    raise RuntimeError("Kling generation timed out")


def _save_generated_image_bytes(image_bytes: bytes, *, prefix: str = "generated") -> str:
    _ensure_output_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{prefix}_{stamp}.png"
    file_path = GENERATED_DIR / file_name
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.save(file_path, format="PNG", optimize=True)
    return f"/output/generated/{file_name}"


def _gemini_generate_image_bytes(
    *,
    parts: list[dict],
    aspect_ratio: Optional[str] = None,
) -> bytes:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-image-preview")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload: dict = {"contents": [{"parts": parts}]}
    generation_config: dict = {"responseModalities": ["IMAGE"]}
    if aspect_ratio:
        generation_config["imageConfig"] = {"aspectRatio": aspect_ratio}
    payload["generationConfig"] = generation_config

    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    response = _request_json(url, "POST", headers, payload)
    candidates = response.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") if isinstance(candidate, dict) else None
        cand_parts = (content or {}).get("parts") if isinstance(content, dict) else None
        if not isinstance(cand_parts, list):
            continue
        for part in cand_parts:
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict):
                continue
            data = inline.get("data")
            if data:
                return base64.b64decode(data)

    raise RuntimeError("Gemini returned no image data")


def generate_image_with_recraft(prompt: str) -> tuple[str, str]:
    api_key = os.getenv("RECRAFT_API_TOKEN") or os.getenv("RECRAFT_API_KEY")
    if not api_key:
        raise RuntimeError("RECRAFT_API_TOKEN (or RECRAFT_API_KEY) is not set")

    model = os.getenv("RECRAFT_MODEL", "recraftv4")
    size = "16:9"

    client = OpenAI(api_key=api_key, base_url="https://external.api.recraft.ai/v1")
    try:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            n=1,
            response_format="b64_json",
        )
    except Exception:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            n=1,
        )
    if not response.data:
        raise RuntimeError("Recraft returned no image data")

    image = response.data[0]
    image_url = getattr(image, "url", "") or ""
    b64_json = getattr(image, "b64_json", "") or ""

    if b64_json:
        _ensure_output_directories()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"generated_{stamp}.png"
        file_path = GENERATED_DIR / file_name
        raw = base64.b64decode(b64_json)
        img = Image.open(BytesIO(raw)).convert("RGB")
        img.save(file_path, format="PNG", optimize=True)
        return image_url, f"/output/generated/{file_name}"

    if image_url:
        local_url = _save_generated_image_local(image_url)
        return image_url, local_url

    raise RuntimeError("Recraft returned neither b64_json nor image URL")


def _request_json(url: str, method: str, headers: dict, payload: Optional[dict] = None) -> dict:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    return json.loads(raw or "{}")


def edit_image_with_gemini(source_image_url: str, edit_prompt: str) -> str:
    # Direct Gemini image editing (Nano Banana family).
    source_image = _fetch_image_from_url(source_image_url).convert("RGB")
    buf = BytesIO()
    source_image.save(buf, format="PNG")
    image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    image_bytes = _gemini_generate_image_bytes(
        parts=[
            {"text": edit_prompt},
            {"inline_data": {"mime_type": "image/png", "data": image_b64}},
        ]
    )
    return _save_generated_image_bytes(image_bytes, prefix="edited")


def _download_remote_bytes(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def _save_generated_image_local(remote_url: str) -> str:
    _ensure_output_directories()
    raw = _download_remote_bytes(remote_url)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"generated_{stamp}.png"
    file_path = GENERATED_DIR / file_name
    image = Image.open(BytesIO(raw)).convert("RGB")
    image.save(file_path, format="PNG", optimize=True)
    return f"/output/generated/{file_name}"


def _read_image_bytes_from_url(url: str) -> bytes:
    parsed = urlparse(url)

    if url.startswith("/"):
        local_path = ROOT / unquote(url.lstrip("/"))
        if not local_path.exists():
            raise FileNotFoundError(f"Local image not found: {local_path}")
        return local_path.read_bytes()

    if parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"}:
        local_path = ROOT / unquote(parsed.path.lstrip("/"))
        if not local_path.exists():
            raise FileNotFoundError(f"Local image not found: {local_path}")
        return local_path.read_bytes()

    return _download_remote_bytes(url)


def _image_input_data_url_from_url(url: str) -> str:
    raw = _read_image_bytes_from_url(url)
    image = Image.open(BytesIO(raw)).convert("RGB")
    buf = BytesIO()
    image.save(buf, format="PNG", optimize=True)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _image_base64_from_url(url: str) -> str:
    raw = _read_image_bytes_from_url(url)
    image = Image.open(BytesIO(raw)).convert("RGB")
    buf = BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _encode_multipart_form_data(fields: list[tuple[str, str]], files: list[tuple[str, str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----CodexBoundary{uuid.uuid4().hex}"
    body = BytesIO()

    for name, value in fields:
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.write(str(value).encode("utf-8"))
        body.write(b"\r\n")

    for field_name, file_name, file_content, content_type in files:
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(
            (
                f'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        body.write(file_content)
        body.write(b"\r\n")

    body.write(f"--{boundary}--\r\n".encode("utf-8"))
    return body.getvalue(), boundary


def uncrop_image_with_clipdrop(source_image_url: str, *, padding: int = 500) -> str:
    clipdrop_key = os.getenv("CLIPDROP_API_KEY")
    if not clipdrop_key:
        raise RuntimeError("CLIPDROP_API_KEY is not set")

    raw = _read_image_bytes_from_url(source_image_url)
    source_hash = hashlib.sha256(raw).hexdigest()[:20]
    _ensure_output_directories()
    file_name = f"uncrop_{source_hash}_{padding}.png"
    file_path = UNCROP_DIR / file_name
    if file_path.exists():
        return f"/output/uncrop/{file_name}"

    fields = [
        ("extend_left", str(padding)),
        ("extend_right", str(padding)),
        ("extend_up", str(padding)),
        ("extend_down", str(padding)),
    ]
    files = [
        ("image_file", "source.png", raw, "image/png"),
    ]
    data, boundary = _encode_multipart_form_data(fields, files)
    request = urllib.request.Request(
        "https://clipdrop-api.co/uncrop/v1",
        data=data,
        method="POST",
        headers={
            "x-api-key": clipdrop_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            uncropped_raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Clipdrop uncrop failed: HTTP {exc.code} {detail}") from exc

    img = Image.open(BytesIO(uncropped_raw)).convert("RGB")
    img.save(file_path, format="PNG", optimize=True)
    return f"/output/uncrop/{file_name}"


def _save_uploaded_data_url(data_url: str, original_name: str = "") -> str:
    match = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", data_url, re.DOTALL)
    if not match:
        raise ValueError("Invalid image data URL")

    mime_type = match.group(1).lower()
    b64_part = match.group(2)
    ext_map = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    ext = ext_map.get(mime_type, "png")

    raw = base64.b64decode(b64_part)
    image = Image.open(BytesIO(raw)).convert("RGB")

    _ensure_output_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(original_name).stem if original_name else "upload"
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_") or "upload"
    file_name = f"{safe_stem}_{stamp}.{ext}"
    file_path = GENERATED_DIR / file_name
    image.save(file_path, format="PNG", optimize=True)
    return f"/output/generated/{file_name}"


def _save_uploaded_file_bytes(file_bytes: bytes, original_name: str = "") -> str:
    if not file_bytes:
        raise ValueError("Uploaded image is empty")

    image = Image.open(BytesIO(file_bytes)).convert("RGB")
    _ensure_output_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(original_name).stem if original_name else "upload"
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_") or "upload"
    file_name = f"{safe_stem}_{stamp}.png"
    file_path = GENERATED_DIR / file_name
    image.save(file_path, format="PNG", optimize=True)
    return f"/output/generated/{file_name}"


def _save_uploaded_video_bytes(file_bytes: bytes, original_name: str = "") -> str:
    if not file_bytes:
        raise ValueError("Uploaded video is empty")

    _ensure_output_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(original_name).stem if original_name else "upload"
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_") or "upload"
    ext = Path(original_name).suffix.lower() if original_name else ""
    if ext not in {".mp4", ".mov", ".webm"}:
        ext = ".mp4"
    file_name = f"{safe_stem}_{stamp}{ext}"
    file_path = VIDEO_DIR / file_name
    file_path.write_bytes(file_bytes)
    return f"/output/videos/{file_name}"


def create_banners_zip(banner_urls: Iterable[str]) -> str:
    _ensure_output_directories()
    files: list[Path] = []
    for url in banner_urls:
        path_str = str(url or "").strip()
        if not path_str.startswith("/"):
            continue
        local_path = (ROOT / path_str.lstrip("/")).resolve()
        # Safety: allow only project output files
        if not str(local_path).startswith(str((ROOT / "output").resolve())):
            continue
        if local_path.exists() and local_path.is_file():
            files.append(local_path)

    if not files:
        raise ValueError("No banner files found to archive")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"banners_{stamp}.zip"
    zip_path = ZIP_DIR / zip_name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=file_path.name)
    return f"/output/archives/{zip_name}"


def _load_font(path: Path, size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    try:
        return ImageFont.truetype(str(path), size=size)
    except Exception:
        return ImageFont.load_default()


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    max_width: int,
    start_size: int,
    min_size: int,
) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    size = start_size
    while size >= min_size:
        font = _load_font(font_path, size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
        size -= 2
    return _load_font(font_path, min_size)


def _fit_font_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    start_size: int,
    max_width: int,
    min_size: int = 8,
) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    text_value = str(text or "").strip()
    if not text_value:
        return _load_font(font_path, max(min_size, start_size))
    return _fit_font(
        draw=draw,
        text=text_value,
        font_path=font_path,
        max_width=max(1, int(max_width)),
        start_size=max(1, int(start_size)),
        min_size=max(1, int(min_size)),
    )


def _draw_price_badge(
    canvas: Image.Image,
    *,
    size_key: str,
    top_text: str,
    bottom_text: str,
    text_align: str,
    headline_font_path: Path,
    badge_fill_hex: str = "#E3FF74",
    shift_right_px: int = 0,
    shift_up_px: int = 0,
    y_shift: int = 0,
    target_bottom_y: Optional[int] = None,
) -> None:
    spec = BADGE_LAYOUT_BY_SIZE.get(size_key)
    if not spec:
        return
    top_value = str(top_text or "").strip()
    bottom_value = str(bottom_text or "").strip()

    size_scale = 1.0
    if text_align == "center" and size_key in {"1200x1200", "1200x1350", "1080x1920"}:
        size_scale = 0.8

    base_badge_w = max(1, int(round(spec["w"] * size_scale)))
    base_badge_h = max(1, int(round(spec["h"] * size_scale)))
    base_padding = max(1, int(round(spec["padding"] * size_scale)))
    base_gap = max(1, int(round(spec["gap"] * size_scale)))
    base_radius = max(2, int(round(spec["radius"] * size_scale)))
    top_font_size = max(8, int(round(spec["top_font_size"] * size_scale)))
    bottom_font_size = max(8, int(round(spec["bottom_font_size"] * size_scale)))

    lines: list[dict] = []
    if top_value:
        lines.append({"text": top_value, "base_size": top_font_size, "is_bottom": False})
    if bottom_value:
        bottom_render_text = bottom_value.upper()
        bottom_start_size = bottom_font_size
        if len(bottom_value.strip()) > 10:
            bottom_start_size = int(round(bottom_font_size * 0.63))
        lines.append({"text": bottom_render_text, "base_size": max(8, bottom_start_size), "is_bottom": True})
    if not lines:
        return

    measure_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), "RGBA")
    max_text_width = max(10, base_badge_w - (base_padding * 2))
    for item in lines:
        item_font = _fit_font_to_width(
            measure_draw,
            text=item["text"],
            font_path=headline_font_path,
            start_size=int(item["base_size"]),
            max_width=max_text_width,
            min_size=8,
        )
        item_box = measure_draw.textbbox((0, 0), item["text"], font=item_font)
        item["font"] = item_font
        item["w"] = max(1, item_box[2] - item_box[0])
        item["h"] = max(1, item_box[3] - item_box[1])

    # Keep typography inside base badge height if there are multiple lines.
    if len(lines) > 1:
        min_size = 8
        while True:
            current_stack_h = sum(int(item["h"]) for item in lines) + base_gap
            if (base_padding * 2 + current_stack_h) <= base_badge_h:
                break
            changed = False
            for item in lines:
                font_size = int(getattr(item["font"], "size", min_size))
                if font_size > min_size:
                    next_font = _load_font(headline_font_path, font_size - 1)
                    box = measure_draw.textbbox((0, 0), item["text"], font=next_font)
                    item["font"] = next_font
                    item["w"] = max(1, box[2] - box[0])
                    item["h"] = max(1, box[3] - box[1])
                    changed = True
            if not changed:
                break

    scales = []
    for item in lines:
        base_size = max(1, int(item["base_size"]))
        cur_size = int(getattr(item["font"], "size", base_size))
        scales.append(float(cur_size) / float(base_size))
    content_scale = max(0.62, min(1.0, min(scales) if scales else 1.0))
    padding = max(6, int(round(base_padding * content_scale)))
    gap = 0 if len(lines) <= 1 else max(4, int(round(base_gap * content_scale)))
    content_w = max(int(item["w"]) for item in lines)
    content_h = sum(int(item["h"]) for item in lines) + (gap if len(lines) > 1 else 0)
    badge_w = max(int(round(base_badge_w * 0.62)), min(base_badge_w, content_w + (padding * 2)))
    badge_h = max(int(round(base_badge_h * 0.62)), min(base_badge_h, content_h + (padding * 2)))
    radius = max(8, int(round(base_radius * (badge_h / float(base_badge_h)))))

    fill_hex = _normalize_hex_color(badge_fill_hex, "#E3FF74")
    fill_rgb = tuple(int(fill_hex[i : i + 2], 16) for i in (1, 3, 5))
    supersample = 3
    badge_w_hi = max(1, badge_w * supersample)
    badge_h_hi = max(1, badge_h * supersample)
    radius_hi = max(2, radius * supersample)
    padding_hi = max(1, padding * supersample)
    gap_hi = max(0, gap * supersample)

    badge_img_hi = Image.new("RGBA", (badge_w_hi, badge_h_hi), (0, 0, 0, 0))
    badge_draw_hi = ImageDraw.Draw(badge_img_hi, "RGBA")
    badge_draw_hi.rounded_rectangle((0, 0, badge_w_hi, badge_h_hi), radius=radius_hi, fill=(fill_rgb[0], fill_rgb[1], fill_rgb[2], 255))

    measure_hi = ImageDraw.Draw(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), "RGBA")
    max_text_width_hi = max(10, badge_w_hi - (padding_hi * 2))
    lines_hi: list[dict] = []
    for item in lines:
        base_font_size = int(getattr(item["font"], "size", item["base_size"]))
        start_hi = max(8, int(round(base_font_size * supersample)))
        min_hi = max(8, int(round(8 * supersample)))
        hi_font = _fit_font_to_width(
            measure_hi,
            text=item["text"],
            font_path=headline_font_path,
            start_size=start_hi,
            max_width=max_text_width_hi,
            min_size=min_hi,
        )
        hi_box = measure_hi.textbbox((0, 0), item["text"], font=hi_font)
        lines_hi.append(
            {
                "text": item["text"],
                "font": hi_font,
                "w": max(1, hi_box[2] - hi_box[0]),
                "h": max(1, hi_box[3] - hi_box[1]),
            }
        )

    stack_h_hi = sum(int(item["h"]) for item in lines_hi) + (gap_hi if len(lines_hi) > 1 else 0)
    cursor_y_hi = max(0, (badge_h_hi - stack_h_hi) // 2)
    for idx, item in enumerate(lines_hi):
        text_x_hi = max(0, (badge_w_hi - int(item["w"])) // 2)
        badge_draw_hi.text((text_x_hi, cursor_y_hi), item["text"], fill="#000000", font=item["font"])
        cursor_y_hi += int(item["h"])
        if idx < len(lines_hi) - 1:
            cursor_y_hi += gap_hi

    rotate_deg = 3 if text_align == "right" else -3
    rotated_hi = badge_img_hi.rotate(rotate_deg, resample=Image.Resampling.BICUBIC, expand=True)
    rotated = rotated_hi.resize(
        (
            max(1, int(round(rotated_hi.width / supersample))),
            max(1, int(round(rotated_hi.height / supersample))),
        ),
        Image.Resampling.LANCZOS,
    )
    shift_x_pct = max(0.0, min(100.0, float(shift_right_px or 0)))
    shift_y_pct = max(0.0, min(100.0, float(shift_up_px or 0)))

    if size_key == "1200x628":
        if text_align == "right":
            # For right text alignment in 1200x628: badge starts bottom-left.
            draw_x = 32.0
        else:
            # In 1200x628 badge is fixed to the right-side text composition anchor.
            draw_x = float(spec["x"])
    else:
        # Badge horizontal movement must stay inside text content bounds, not full banner bounds.
        text_left = 80.0
        text_width = 1040.0
        if size_key == "1080x1920":
            text_width = 920.0
        min_x = text_left
        max_x = max(min_x, (text_left + text_width) - float(badge_w))
        span_x = max(0.0, max_x - min_x)
        draw_x = min_x + (span_x * (shift_x_pct / 100.0))
    center_x = draw_x + (badge_w / 2.0)
    paste_x = int(round(center_x - (rotated.width / 2.0)))
    center_extra_y = 0
    if text_align == "center" and size_key in CENTER_BADGE_SPACING_LOCK_BY_SIZE:
        center_extra_y = int(CENTER_BADGE_SPACING_LOCK_BY_SIZE.get(size_key, 0))
    elif text_align == "left" and size_key == "1200x1350":
        # For 1200x1500 composition only: left align spacing should match right align spacing.
        center_extra_y = int(RIGHT_BADGE_Y_ADJUST_BY_SIZE.get(size_key, 0))
    elif text_align == "center":
        center_extra_y = int(CENTER_BADGE_Y_ADJUST_BY_SIZE.get(size_key, 0))
    elif text_align == "right":
        center_extra_y = int(RIGHT_BADGE_Y_ADJUST_BY_SIZE.get(size_key, 0))
    if target_bottom_y is not None:
        paste_y = int(round(float(target_bottom_y) - float(rotated.height)))
    else:
        paste_y = int(round(float(spec["y"]) + float(y_shift) + float(center_extra_y)))
    if size_key == "1200x628" and text_align == "right":
        # Bottom-left default anchor for right align composition.
        paste_y = int(round(float(canvas.height - rotated.height - 32)))
    text_top_min_by_size = {
        "1200x1200": 80,
        "1200x1350": 80,
        "1080x1920": 80,
        "1200x628": 32,
    }
    min_y = int(text_top_min_by_size.get(size_key, 0))
    up_span = max(0, paste_y - min_y)
    paste_y -= int(round(up_span * (shift_y_pct / 100.0)))
    paste_x = max(0, min(int(canvas.width - rotated.width), paste_x))
    paste_y = max(min_y, min(int(canvas.height - rotated.height), paste_y))
    canvas.alpha_composite(rotated, (paste_x, paste_y))


def _measure_wrapped_height(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    wrap_width: int,
    line_height_ratio: float,
) -> int:
    wrapped = _wrap_text_by_width(draw, text, font, wrap_width)
    return _measure_multiline_with_ratio(draw, text=wrapped, font=font, line_height_ratio=line_height_ratio)


def _wrap_text_by_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    max_width: int,
) -> str:
    paragraphs = text.splitlines() or [text]
    all_lines: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            all_lines.append("")
            continue

        current: list[str] = []
        for word in words:
            candidate = " ".join([*current, word])
            visible_candidate = _strip_inline_style_markers(candidate)
            candidate_box = draw.textbbox((0, 0), visible_candidate, font=font)
            width = max(1, candidate_box[2] - candidate_box[0])
            if width <= max_width or not current:
                current.append(word)
            else:
                all_lines.append(" ".join(current))
                current = [word]
        if current:
            all_lines.append(" ".join(current))

    return "\n".join(all_lines)


def _strip_inline_style_markers(text: str) -> str:
    return str(text or "").replace("**", "").replace("//", "")


def _parse_style_segments(
    line: str,
    *,
    highlighted: bool = False,
    italic: bool = False,
) -> tuple[list[tuple[str, bool, bool]], bool, bool]:
    source = str(line or "")
    if "**" not in source and "//" not in source:
        return [(source, highlighted, italic)], highlighted, italic
    parts = re.split(r"(\*\*|//)", source)
    segments: list[tuple[str, bool, bool]] = []
    for part in parts:
        if part == "**":
            highlighted = not highlighted
            continue
        if part == "//":
            italic = not italic
            continue
        if part:
            segments.append((part, highlighted, italic))
    return segments, highlighted, italic


def _normalize_hex_color(value: str, default: str = "#E3FF74") -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if not text.startswith("#"):
        text = f"#{text}"
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.upper()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", text):
        r, g, b = text[1], text[2], text[3]
        return f"#{r}{r}{g}{g}{b}{b}".upper()
    return default


def _get_highlight_fill(fill, highlight_hex: str = "#E3FF74"):
    safe_hex = _normalize_hex_color(highlight_hex, "#E3FF74")
    rgb = tuple(int(safe_hex[i : i + 2], 16) for i in (1, 3, 5))
    if isinstance(fill, tuple):
        if len(fill) == 4:
            return (rgb[0], rgb[1], rgb[2], fill[3])
        if len(fill) == 3:
            return (rgb[0], rgb[1], rgb[2])
    return safe_hex


def _resolve_italic_font_for_base(
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
) -> Optional[Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]]:
    if not isinstance(font, ImageFont.FreeTypeFont):
        return None
    base_path = str(getattr(font, "path", "") or "")
    base_name = Path(base_path).name
    if base_name == "YangoGroupHeadline-HeavyItalic.ttf":
        return font
    if base_name != "YangoGroupHeadline-Heavy.ttf":
        return None
    size = int(getattr(font, "size", 0) or 0)
    if size <= 0:
        return None
    for candidate in HEADLINE_ITALIC_FONT_CANDIDATES:
        if candidate.exists():
            return _load_font(candidate, size)
    return None


def _measure_styled_line_width(
    draw: ImageDraw.ImageDraw,
    *,
    segments: list[tuple[str, bool, bool]],
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    italic_font: Optional[Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]] = None,
) -> int:
    total = 0
    for segment_text, _, is_italic in segments:
        if not segment_text:
            continue
        segment_font = italic_font if is_italic and italic_font is not None else font
        segment_box = draw.textbbox((0, 0), segment_text, font=segment_font)
        seg_w = max(1, segment_box[2] - segment_box[0])
        if is_italic and italic_font is None:
            seg_h = max(1, segment_box[3] - segment_box[1])
            seg_w += int(round(seg_h * 0.26))
        total += seg_w
    return total


def _draw_text_segment(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    text: str,
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    fill,
    italic: bool,
    italic_font: Optional[Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]] = None,
    alpha_draw: Optional[ImageDraw.ImageDraw] = None,
) -> int:
    if not text:
        return 0
    text_font = italic_font if italic and italic_font is not None else font
    text_box = draw.textbbox((0, 0), text, font=text_font)
    text_w = max(1, text_box[2] - text_box[0])
    text_h = max(1, text_box[3] - text_box[1])
    if not italic or italic_font is not None:
        if alpha_draw is not None:
            alpha_draw.text((x, y), text, fill=fill, font=text_font)
        else:
            draw.text((x, y), text, fill=fill, font=text_font)
        return text_w

    slant = 0.26
    skew_px = int(round(text_h * slant))
    mask = Image.new("L", (text_w, text_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.text((0, 0), text, fill=255, font=text_font)
    skewed = Image.new("L", (text_w + skew_px, text_h), 0)
    for row in range(text_h):
        shift = int(round((text_h - row - 1) * slant))
        strip = mask.crop((0, row, text_w, row + 1))
        skewed.paste(strip, (shift, row))
    layer = Image.new("RGBA", (text_w + skew_px, text_h), (0, 0, 0, 0))
    if isinstance(fill, tuple):
        if len(fill) == 4:
            rgba = fill
        elif len(fill) == 3:
            rgba = (fill[0], fill[1], fill[2], 255)
        else:
            rgba = (255, 255, 255, 255)
    else:
        rgb = Image.new("RGBA", (1, 1), fill).getpixel((0, 0))
        rgba = rgb if len(rgb) == 4 else (rgb[0], rgb[1], rgb[2], 255)
    paint = Image.new("RGBA", (text_w + skew_px, text_h), rgba)
    paint.putalpha(skewed)
    layer.alpha_composite(paint)
    canvas.alpha_composite(layer, (x, y))
    return text_w + skew_px


def _draw_multiline_with_ratio(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    text: str,
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    fill,
    line_height_ratio: float,
    box_width: Optional[int] = None,
    align: str = "left",
    highlight_hex: str = "#E3FF74",
) -> None:
    lines = text.split("\n")
    if not lines:
        return
    line_box = draw.textbbox((0, 0), "Ag", font=font)
    line_h = max(1, line_box[3] - line_box[1])
    step = max(1, int(round(line_h * line_height_ratio)))
    cy = y
    has_alpha = isinstance(fill, tuple) and len(fill) == 4 and fill[3] < 255
    alpha_layer = None
    alpha_draw = None
    if has_alpha:
        alpha_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        alpha_draw = ImageDraw.Draw(alpha_layer, "RGBA")
    italic_font = _resolve_italic_font_for_base(font)
    carry_highlight = False
    carry_italic = False

    for line in lines:
        segments, carry_highlight, carry_italic = _parse_style_segments(
            line,
            highlighted=carry_highlight,
            italic=carry_italic,
        )
        line_x = x
        if box_width is not None:
            line_w = _measure_styled_line_width(
                draw,
                segments=segments,
                font=font,
                italic_font=italic_font,
            )
            if align == "right":
                line_x = x + max(0, box_width - line_w)
            elif align == "center":
                line_x = x + max(0, (box_width - line_w) // 2)
        cursor_x = line_x
        for segment_text, is_highlighted, is_italic in segments:
            if not segment_text:
                continue
            segment_fill = _get_highlight_fill(fill, highlight_hex=highlight_hex) if is_highlighted else fill
            drawn_w = _draw_text_segment(
                canvas,
                draw,
                x=cursor_x,
                y=cy,
                text=segment_text,
                font=font,
                fill=segment_fill,
                italic=is_italic,
                italic_font=italic_font,
                alpha_draw=alpha_draw if has_alpha else None,
            )
            cursor_x += drawn_w
        cy += step

    if has_alpha and alpha_layer is not None:
        canvas.alpha_composite(alpha_layer)


def _measure_multiline_with_ratio(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    line_height_ratio: float,
) -> int:
    lines = text.split("\n")
    if not lines:
        return 0
    line_box = draw.textbbox((0, 0), "Ag", font=font)
    line_h = max(1, line_box[3] - line_box[1])
    step = max(1, int(round(line_h * line_height_ratio)))
    return line_h + step * max(0, len(lines) - 1)


def _layout_bottom_blocks(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    blocks: list[dict],
    valign: str = "bottom",
    highlight_hex: str = "#E3FF74",
) -> None:
    prepared: list[dict] = []
    total_h = 0
    for idx, block in enumerate(blocks):
        raw_text = block["text"]
        font = block["font"]
        ratio = block["ratio"]
        wrap_width = block.get("wrap_width", width)
        text = _wrap_text_by_width(draw, raw_text, font, wrap_width)
        block_h = _measure_multiline_with_ratio(draw, text=text, font=font, line_height_ratio=ratio)
        gap_before = block.get("gap_before", 0) if idx > 0 else 0
        total_h += gap_before + block_h
        prepared.append(
            {
                "text": text,
                "font": font,
                "ratio": ratio,
                "fill": block["fill"],
                "gap_before": gap_before,
                "height": block_h,
                "align": block.get("align", "left"),
                "wrap_width": wrap_width,
                "align_width": block.get("align_width", width),
            }
        )

    if str(valign).lower() == "top":
        cursor_y = y
    elif str(valign).lower() == "center":
        cursor_y = y + max(0, (height - total_h) // 2)
    else:
        cursor_y = y + max(0, height - total_h)
    for idx, block in enumerate(prepared):
        if idx > 0:
            cursor_y += block["gap_before"]
        _draw_multiline_with_ratio(
            canvas,
            draw,
            x=x,
            y=int(cursor_y),
            text=block["text"],
            font=block["font"],
            fill=block["fill"],
            line_height_ratio=block["ratio"],
            box_width=block.get("align_width", width),
            align=block.get("align", "left"),
            highlight_hex=highlight_hex,
        )
        cursor_y += block["height"]


def _fetch_image_from_url(url: str) -> Image.Image:
    parsed = urlparse(url)

    if url.startswith("/"):
        local_path = ROOT / unquote(url.lstrip("/"))
        if not local_path.exists():
            raise FileNotFoundError(f"Local image not found: {local_path}")
        return Image.open(local_path).convert("RGB")

    if parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"}:
        local_path = ROOT / unquote(parsed.path.lstrip("/"))
        if not local_path.exists():
            raise FileNotFoundError(f"Local image not found: {local_path}")
        return Image.open(local_path).convert("RGB")

    content = _download_remote_bytes(url)
    image = Image.open(BytesIO(content))
    return image.convert("RGB")


def _cover_resize(
    image: Image.Image,
    width: int,
    height: int,
    *,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    max_left = max(0, resized.width - width)
    max_top = max(0, resized.height - height)
    left = int(round(max_left * max(0.0, min(1.0, focus_x))))
    top = int(round(max_top * max(0.0, min(1.0, focus_y))))
    return resized.crop((left, top, left + width, top + height))


def _resize_exact(image: Image.Image, width: int, height: int) -> Image.Image:
    return image.resize((max(1, width), max(1, height)), Image.Resampling.LANCZOS)


def _draw_vertical_black_gradient(
    canvas: Image.Image,
    *,
    y: int,
    height: int,
    opacity: float,
) -> None:
    mask = Image.new("L", (1, max(1, height)))
    for i in range(mask.height):
        alpha = int(255 * opacity * (i / max(1, mask.height - 1)))
        mask.putpixel((0, i), alpha)
    mask = mask.resize((canvas.width, mask.height))
    overlay = Image.new("RGBA", (canvas.width, mask.height), "#080a09")
    canvas.paste(overlay, (0, y), mask=mask)


def _draw_horizontal_black_gradient(
    canvas: Image.Image,
    *,
    width: int,
    opacity: float,
    mode: str = "left",
) -> None:
    mask = Image.new("L", (max(1, width), 1))
    for i in range(mask.width):
        t = i / max(1, mask.width - 1)
        if mode == "right":
            t = 1 - t
            alpha = int(255 * opacity * (1 - t))
        elif mode == "center":
            # Strongest in the center, fades to both sides.
            alpha = int(255 * opacity * (1.0 - abs((t * 2.0) - 1.0)))
        else:
            alpha = int(255 * opacity * (1 - t))
        mask.putpixel((i, 0), alpha)
    mask = mask.resize((mask.width, canvas.height))
    overlay = Image.new("RGBA", (mask.width, canvas.height), "#080a09")
    if mode == "right":
        x = canvas.width - mask.width
    elif mode == "center":
        x = (canvas.width - mask.width) // 2
    else:
        x = 0
    canvas.paste(overlay, (x, 0), mask=mask)


def _normalize_text_align(value: str) -> str:
    v = str(value or "").strip().lower()
    if v in {"left", "center", "right"}:
        return v
    return "left"


def _draw_top_diagonal_gradient(canvas: Image.Image, *, height: int, align: str = "left") -> None:
    # Soft top shadow aligned with logo/text alignment.
    w = canvas.width
    h = max(1, height)
    mask = Image.new("L", (w, h), 0)
    px = mask.load()
    for y in range(h):
        ny = y / max(1, h - 1)
        for x in range(w):
            nx = x / max(1, w - 1)
            if align == "right":
                # Mirror the diagonal so the shadow stays on the right.
                diag = ((1.0 - nx) * 0.92) + (ny * 1.45)
                t = max(0.0, min(1.0, 1.0 - diag))
            elif align == "center":
                # Centered top vignette under centered logo.
                dx = abs(nx - 0.5) * 2.0
                t = max(0.0, min(1.0, 1.0 - (dx * 0.95 + ny * 1.35)))
            else:
                # Left diagonal (default).
                diag = (nx * 0.92) + (ny * 1.45)
                t = max(0.0, min(1.0, 1.0 - diag))
            alpha = int((t ** 1.45) * 190)
            px[x, y] = alpha
    overlay = Image.new("RGBA", (w, h), (8, 10, 9, 0))
    overlay.putalpha(mask)
    canvas.paste(overlay, (0, 0), overlay)


def _transform_with_scale_and_shift(
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    scale: float,
    shift_x: int,
    shift_y: int,
) -> tuple[int, int, int, int]:
    safe_scale = max(1.0, min(1.5, float(scale or 1.0)))
    sw = max(1, int(round(w * safe_scale)))
    sh = max(1, int(round(h * safe_scale)))
    cx = x + (w / 2.0)
    cy = y + (h / 2.0)
    nx = int(round(cx - (sw / 2.0) + shift_x))
    ny = int(round(cy - (sh / 2.0) + shift_y))
    return nx, ny, sw, sh


def _render_master_banner_by_size(
    *,
    bg_image: Optional[Image.Image],
    size_key: str,
    title: str,
    subtitle: str,
    disclaimer: str,
    text_align: str = "left",
    badge_enabled: bool = False,
    badge_top_text: str = "",
    badge_bottom_text: str = "",
    accent_color: str = "#E3FF74",
    badge_shift_x: int = 0,
    badge_shift_y: int = 0,
    image_scale: float = 1.0,
    image_shift_x: int = 0,
    image_shift_y: int = 0,
) -> Image.Image:
    width, height = BANNER_SIZE_MAP[size_key]
    canvas = Image.new("RGBA", (width, height), "#d9d9d9")
    draw = ImageDraw.Draw(canvas, "RGBA")

    headline_font_path = ROOT / "assets" / "fonts" / "YangoGroupHeadline-Heavy.ttf"
    headline_italic_font_path = ROOT / "assets" / "fonts" / "YangoGroupHeadline-HeavyItalic.ttf"
    text_bold_font_path = ROOT / "assets" / "fonts" / "YangoGroupText-Bold.ttf"
    text_regular_font_path = ROOT / "assets" / "fonts" / "YangoGroupText-Regular.ttf"

    default_title_text = "Drive today\ncash in fast"
    default_subtitle_text = "Join Yango, earn quickly, and drive your future"
    default_disclaimer_text = (
        "Yango is an informational service and not a transportation or taxi services provider. "
        "Transportation services are provided by third parties."
    )
    title_text = title.strip() or default_title_text
    subtitle_text = subtitle.strip() or default_subtitle_text
    disclaimer_text = disclaimer.strip() or default_disclaimer_text
    align_mode = _normalize_text_align(text_align)
    accent_hex = _normalize_hex_color(accent_color, "#E3FF74")

    if size_key == "1200x1200":
        # Updated image transform from Figma node 143:3587
        img_x, img_y, img_w, img_h = -446, -327, 2092, 1578
        img_x, img_y, img_w, img_h = _transform_with_scale_and_shift(
            x=img_x,
            y=img_y,
            w=img_w,
            h=img_h,
            scale=image_scale,
            shift_x=int(image_shift_x),
            shift_y=int(image_shift_y),
        )
        if bg_image is not None:
            canvas.paste(_resize_exact(bg_image, img_w, img_h).convert("RGBA"), (img_x, img_y))
        _draw_top_diagonal_gradient(canvas, height=368, align=align_mode)
        _draw_vertical_black_gradient(canvas, y=int(round(596.734)), height=int(round(603.266)), opacity=0.9)
        _draw_vertical_black_gradient(canvas, y=int(round(721.414)), height=int(round(478.586)), opacity=0.75)

        logo_font = _load_font(headline_italic_font_path, 113)
        title_font = _load_font(headline_font_path, 132)
        subtitle_font = _load_font(text_bold_font_path, 52)
        disclaimer_font = _load_font(text_regular_font_path, 16)
        if badge_enabled:
            title_wrap = 1033
            subtitle_wrap = 1033 if align_mode in {"center", "right"} else 1040
            current_h = (
                _measure_wrapped_height(
                    draw,
                    text=title_text.upper(),
                    font=title_font,
                    wrap_width=title_wrap,
                    line_height_ratio=0.9,
                )
                + _measure_wrapped_height(
                    draw,
                    text=subtitle_text,
                    font=subtitle_font,
                    wrap_width=subtitle_wrap,
                    line_height_ratio=1.1,
                )
                + _measure_wrapped_height(
                    draw,
                    text=disclaimer_text,
                    font=disclaimer_font,
                    wrap_width=816,
                    line_height_ratio=1.28,
                )
            )
            base_h = (
                _measure_wrapped_height(
                    draw,
                    text=default_title_text.upper(),
                    font=title_font,
                    wrap_width=title_wrap,
                    line_height_ratio=0.9,
                )
                + _measure_wrapped_height(
                    draw,
                    text=default_subtitle_text,
                    font=subtitle_font,
                    wrap_width=subtitle_wrap,
                    line_height_ratio=1.1,
                )
                + _measure_wrapped_height(
                    draw,
                    text=default_disclaimer_text,
                    font=disclaimer_font,
                    wrap_width=816,
                    line_height_ratio=1.28,
                )
            )
            current_total_h = current_h + 48 + 40
            title_top_y = max(0, int(round((height - 40) - current_total_h)))
            badge_target_bottom_y = title_top_y - 20
            badge_lift = 0
            _draw_price_badge(
                canvas,
                size_key=size_key,
                top_text=badge_top_text,
                bottom_text=badge_bottom_text,
                text_align=align_mode,
                headline_font_path=headline_font_path,
                badge_fill_hex=accent_hex,
                shift_right_px=max(0, int(badge_shift_x or 0)),
                shift_up_px=max(0, int(badge_shift_y or 0)),
                y_shift=-badge_lift,
                target_bottom_y=badge_target_bottom_y,
            )

        logo_box = draw.textbbox((0, 0), "YANGO DRIVE", font=logo_font)
        logo_w = max(1, logo_box[2] - logo_box[0])
        if align_mode == "center":
            logo_x = (width - logo_w) // 2
        elif align_mode == "right":
            logo_x = width - 80 - logo_w
        else:
            logo_x = 80
        draw.text((logo_x, 80), "YANGO DRIVE", fill="white", font=logo_font)
        _layout_bottom_blocks(
            canvas,
            draw,
            x=80,
            y=0,
            width=1040,
            height=height - 40,
            blocks=[
                {
                    "text": title_text.upper(),
                    "font": title_font,
                    "ratio": 0.9,
                    "fill": "white",
                    "gap_before": 0,
                    "wrap_width": 1033,
                    "align": align_mode,
                },
                {
                    "text": subtitle_text,
                    "font": subtitle_font,
                    "ratio": 1.1,
                    "fill": "white",
                    "gap_before": 48,
                    "wrap_width": 1033 if align_mode in {"center", "right"} else 1040,
                    "align": align_mode,
                },
                {
                    "text": disclaimer_text,
                    "font": disclaimer_font,
                    "ratio": 1.28,
                    "fill": (255, 255, 255, 77),
                    "gap_before": 40,
                    "wrap_width": 1040,
                    "align": align_mode,
                    "align_width": 1040,
                },
            ],
            highlight_hex=accent_hex,
        )

    elif size_key == "1200x1350":
        # Updated image transform from Figma node 145:427 (1200x1500 composition).
        img_x, img_y, img_w, img_h = -600, -310, 2400, 1810
        img_x, img_y, img_w, img_h = _transform_with_scale_and_shift(
            x=img_x,
            y=img_y,
            w=img_w,
            h=img_h,
            scale=image_scale,
            shift_x=int(image_shift_x),
            shift_y=int(image_shift_y),
        )
        if bg_image is not None:
            canvas.paste(_resize_exact(bg_image, img_w, img_h).convert("RGBA"), (img_x, img_y))
        _draw_top_diagonal_gradient(canvas, height=368, align=align_mode)
        _draw_vertical_black_gradient(canvas, y=int(round(height * 0.4973)), height=754, opacity=0.9)
        _draw_vertical_black_gradient(canvas, y=int(round(height * 0.6012)), height=598, opacity=0.75)

        logo_font = _load_font(headline_italic_font_path, 109)
        title_font = _load_font(headline_font_path, 132)
        subtitle_font = _load_font(text_bold_font_path, 52)
        disclaimer_font = _load_font(text_regular_font_path, 16)
        if badge_enabled:
            title_wrap = 1033
            subtitle_wrap = 1033 if align_mode in {"center", "right"} else 1040
            current_h = (
                _measure_wrapped_height(
                    draw,
                    text=title_text.upper(),
                    font=title_font,
                    wrap_width=title_wrap,
                    line_height_ratio=0.9,
                )
                + _measure_wrapped_height(
                    draw,
                    text=subtitle_text,
                    font=subtitle_font,
                    wrap_width=subtitle_wrap,
                    line_height_ratio=1.1,
                )
                + _measure_wrapped_height(
                    draw,
                    text=disclaimer_text,
                    font=disclaimer_font,
                    wrap_width=816,
                    line_height_ratio=1.28,
                )
            )
            base_h = (
                _measure_wrapped_height(
                    draw,
                    text=default_title_text.upper(),
                    font=title_font,
                    wrap_width=title_wrap,
                    line_height_ratio=0.9,
                )
                + _measure_wrapped_height(
                    draw,
                    text=default_subtitle_text,
                    font=subtitle_font,
                    wrap_width=subtitle_wrap,
                    line_height_ratio=1.1,
                )
                + _measure_wrapped_height(
                    draw,
                    text=default_disclaimer_text,
                    font=disclaimer_font,
                    wrap_width=816,
                    line_height_ratio=1.28,
                )
            )
            current_total_h = current_h + 48 + 40
            title_top_y = max(0, int(round((height - 80) - current_total_h)))
            badge_target_bottom_y = title_top_y - 20
            badge_lift = 0
            _draw_price_badge(
                canvas,
                size_key=size_key,
                top_text=badge_top_text,
                bottom_text=badge_bottom_text,
                text_align=align_mode,
                headline_font_path=headline_font_path,
                badge_fill_hex=accent_hex,
                shift_right_px=max(0, int(badge_shift_x or 0)),
                shift_up_px=max(0, int(badge_shift_y or 0)),
                y_shift=-badge_lift,
                target_bottom_y=badge_target_bottom_y,
            )

        logo_box = draw.textbbox((0, 0), "YANGO DRIVE", font=logo_font)
        logo_w = max(1, logo_box[2] - logo_box[0])
        if align_mode == "center":
            logo_x = (width - logo_w) // 2
        elif align_mode == "right":
            logo_x = width - 80 - logo_w
        else:
            logo_x = 80
        draw.text((logo_x, 80), "YANGO DRIVE", fill="white", font=logo_font)
        _layout_bottom_blocks(
            canvas,
            draw,
            x=80,
            y=0,
            width=1040,
            height=height - 80,
            blocks=[
                {
                    "text": title_text.upper(),
                    "font": title_font,
                    "ratio": 0.9,
                    "fill": "white",
                    "gap_before": 0,
                    "wrap_width": 1033,
                    "align": align_mode,
                },
                {
                    "text": subtitle_text,
                    "font": subtitle_font,
                    "ratio": 1.1,
                    "fill": "white",
                    "gap_before": 48,
                    "wrap_width": 1033 if align_mode in {"center", "right"} else 1040,
                    "align": align_mode,
                },
                {
                    "text": disclaimer_text,
                    "font": disclaimer_font,
                    "ratio": 1.28,
                    "fill": (255, 255, 255, 77),
                    "gap_before": 40,
                    "wrap_width": 1040,
                    "align": align_mode,
                    "align_width": 1040,
                },
            ],
            highlight_hex=accent_hex,
        )

    elif size_key == "1200x628":
        # Updated image transform from Figma nodes 187:2100 (center) and 187:2179 (right).
        img_x, img_y, img_w, img_h = (0, -304, 1640, 1237) if align_mode != "right" else (-440, -304, 1640, 1237)
        img_x, img_y, img_w, img_h = _transform_with_scale_and_shift(
            x=img_x,
            y=img_y,
            w=img_w,
            h=img_h,
            scale=image_scale,
            shift_x=int(image_shift_x),
            shift_y=int(image_shift_y),
        )
        if bg_image is not None:
            canvas.paste(_resize_exact(bg_image, img_w, img_h).convert("RGBA"), (img_x, img_y))
        # 1200x628: keep center alignment on the original (left) gradient profile.
        grad_mode = "right" if align_mode == "right" else "left"
        _draw_horizontal_black_gradient(canvas, width=965, opacity=0.9, mode=grad_mode)
        _draw_horizontal_black_gradient(canvas, width=766, opacity=0.75, mode=grad_mode)
        if badge_enabled:
            _draw_price_badge(
                canvas,
                size_key=size_key,
                top_text=badge_top_text,
                bottom_text=badge_bottom_text,
                text_align=align_mode,
                headline_font_path=headline_font_path,
                badge_fill_hex=accent_hex,
                shift_right_px=max(0, int(badge_shift_x or 0)),
                shift_up_px=max(0, int(badge_shift_y or 0)),
            )

        logo_font = _load_font(headline_italic_font_path, 74)
        title_font = _load_font(headline_font_path, 112)
        subtitle_font = _load_font(text_bold_font_path, 40)
        disclaimer_font = _load_font(text_regular_font_path, 13)

        top_x = 532 if align_mode == "right" else 32
        top_align = "right" if align_mode == "right" else ("center" if align_mode == "center" else "left")
        # Top text container (x=32/532 y=32 w=636 h=302) and bottom block at the bottom of the row.
        _layout_bottom_blocks(
            canvas,
            draw,
            x=top_x,
            y=32,
            width=636,
            height=235,
            valign="top",
            blocks=[
                {
                    "text": title_text.upper(),
                    "font": title_font,
                    "ratio": 0.9,
                    "fill": "white",
                    "gap_before": 0,
                    "wrap_width": 636,
                    "align": top_align,
                },
                {
                    "text": subtitle_text,
                    "font": subtitle_font,
                    "ratio": 1.1,
                    "fill": "white",
                    "gap_before": 48,
                    "wrap_width": 636,
                    "align": top_align,
                },
            ],
            highlight_hex=accent_hex,
        )
        logo_box = draw.textbbox((0, 0), "YANGO DRIVE", font=logo_font)
        logo_w = max(1, logo_box[2] - logo_box[0])
        logo_h = max(1, logo_box[3] - logo_box[1])
        bottom_padding = 32
        logo_y = height - bottom_padding - logo_h
        if align_mode == "center":
            logo_x = 32 + (636 - logo_w) // 2
        elif align_mode == "right":
            logo_x = width - 32 - logo_w
        else:
            logo_x = 32
        draw.text((logo_x, logo_y), "YANGO DRIVE", fill="white", font=logo_font)
        disclaimer_wrapped = _wrap_text_by_width(draw, disclaimer_text, disclaimer_font, 511)
        disclaimer_h = _measure_multiline_with_ratio(
            draw,
            text=disclaimer_wrapped,
            font=disclaimer_font,
            line_height_ratio=1.28,
        )
        disclaimer_y = height - bottom_padding - disclaimer_h
        _draw_multiline_with_ratio(
            canvas,
            draw,
            x=32 if align_mode == "right" else 657,
            y=disclaimer_y,
            text=disclaimer_wrapped,
            font=disclaimer_font,
            fill=(255, 255, 255, 128),
            line_height_ratio=1.28,
            box_width=511,
            align="left" if align_mode == "right" else "right",
            highlight_hex=accent_hex,
        )

    elif size_key == "1080x1920":
        # Updated image transform from Figma node 145:459
        img_x, img_y, img_w, img_h = -1099, -552, 3278, 2472
        img_x, img_y, img_w, img_h = _transform_with_scale_and_shift(
            x=img_x,
            y=img_y,
            w=img_w,
            h=img_h,
            scale=image_scale,
            shift_x=int(image_shift_x),
            shift_y=int(image_shift_y),
        )
        if bg_image is not None:
            canvas.paste(_resize_exact(bg_image, img_w, img_h).convert("RGBA"), (img_x, img_y))
        _draw_vertical_black_gradient(canvas, y=955, height=965, opacity=0.9)
        _draw_vertical_black_gradient(canvas, y=1154, height=766, opacity=0.75)

        logo_font = _load_font(headline_italic_font_path, 109)
        title_font = _load_font(headline_font_path, 132)
        subtitle_font = _load_font(text_bold_font_path, 52)
        disclaimer_font = _load_font(text_regular_font_path, 16)

        title_width = 920
        subtitle_width = 920
        disclaimer_width = 920
        title_wrapped = _wrap_text_by_width(draw, title_text.upper(), title_font, title_width)
        subtitle_wrapped = _wrap_text_by_width(draw, subtitle_text, subtitle_font, subtitle_width)
        disclaimer_wrapped = _wrap_text_by_width(draw, disclaimer_text, disclaimer_font, disclaimer_width)
        title_h = _measure_multiline_with_ratio(draw, text=title_wrapped, font=title_font, line_height_ratio=0.9)
        subtitle_h = _measure_multiline_with_ratio(draw, text=subtitle_wrapped, font=subtitle_font, line_height_ratio=1.1)
        disclaimer_h = _measure_multiline_with_ratio(draw, text=disclaimer_wrapped, font=disclaimer_font, line_height_ratio=1.28)
        logo_box = draw.textbbox((0, 0), "YANGO DRIVE", font=logo_font)
        logo_w = max(1, logo_box[2] - logo_box[0])
        logo_h = max(1, logo_box[3] - logo_box[1])

        gap_title_subtitle = 48
        gap_subtitle_logo = 80
        gap_logo_disclaimer = 150
        bottom_padding = 80
        total_h = (
            title_h
            + gap_title_subtitle
            + subtitle_h
            + gap_subtitle_logo
            + logo_h
            + gap_logo_disclaimer
            + disclaimer_h
        )
        cursor_y = height - bottom_padding - total_h
        if badge_enabled:
            base_title_wrapped = _wrap_text_by_width(draw, default_title_text.upper(), title_font, title_width)
            base_subtitle_wrapped = _wrap_text_by_width(draw, default_subtitle_text, subtitle_font, subtitle_width)
            base_disclaimer_wrapped = _wrap_text_by_width(draw, default_disclaimer_text, disclaimer_font, disclaimer_width)
            base_h = (
                _measure_multiline_with_ratio(draw, text=base_title_wrapped, font=title_font, line_height_ratio=0.9)
                + _measure_multiline_with_ratio(draw, text=base_subtitle_wrapped, font=subtitle_font, line_height_ratio=1.1)
                + _measure_multiline_with_ratio(draw, text=base_disclaimer_wrapped, font=disclaimer_font, line_height_ratio=1.28)
            )
            current_h = title_h + subtitle_h + disclaimer_h
            badge_target_bottom_y = int(round(cursor_y)) - 8
            badge_lift = 0
            _draw_price_badge(
                canvas,
                size_key=size_key,
                top_text=badge_top_text,
                bottom_text=badge_bottom_text,
                text_align=align_mode,
                headline_font_path=headline_font_path,
                badge_fill_hex=accent_hex,
                shift_right_px=max(0, int(badge_shift_x or 0)),
                shift_up_px=max(0, int(badge_shift_y or 0)),
                y_shift=-badge_lift,
                target_bottom_y=badge_target_bottom_y,
            )

        _draw_multiline_with_ratio(
            canvas,
            draw,
            x=80,
            y=int(cursor_y),
            text=title_wrapped,
            font=title_font,
            fill="white",
            line_height_ratio=0.9,
            box_width=title_width,
            align="center" if align_mode == "center" else ("right" if align_mode == "right" else "left"),
            highlight_hex=accent_hex,
        )
        cursor_y += title_h + gap_title_subtitle
        _draw_multiline_with_ratio(
            canvas,
            draw,
            x=80,
            y=int(cursor_y),
            text=subtitle_wrapped,
            font=subtitle_font,
            fill="white",
            line_height_ratio=1.1,
            box_width=subtitle_width,
            align="center" if align_mode == "center" else ("right" if align_mode == "right" else "left"),
            highlight_hex=accent_hex,
        )
        cursor_y += subtitle_h + gap_subtitle_logo
        if align_mode == "center":
            logo_x = (width - logo_w) // 2
        elif align_mode == "right":
            logo_x = width - 80 - logo_w
        else:
            logo_x = 80
        draw.text((logo_x, int(cursor_y)), "YANGO DRIVE", fill="white", font=logo_font)
        cursor_y += logo_h + gap_logo_disclaimer
        _draw_multiline_with_ratio(
            canvas,
            draw,
            x=80,
            y=int(cursor_y),
            text=disclaimer_wrapped,
            font=disclaimer_font,
            fill=(255, 255, 255, 77),
            line_height_ratio=1.28,
            box_width=disclaimer_width,
            align="center" if align_mode == "center" else ("right" if align_mode == "right" else "left"),
            highlight_hex=accent_hex,
        )

    return canvas.convert("RGB")


def render_banner_images(
    image_url: str,
    text_sets: Iterable[dict],
    layout_type: str,
    sizes: Iterable[str],
    image_scale: float = 1.0,
    image_shift_x: int = 0,
    image_shift_y: int = 0,
) -> tuple[list[dict], str]:
    _ensure_output_directories()

    source_image = None
    effective_image_url = str(image_url or "").strip()
    if image_url:
        cached_record = get_image_library_record(image_url)
        cached_banner_source_url = ""
        if cached_record is not None:
            cached_banner_source_url = str(cached_record.get("banner_source_url", "")).strip()
        try:
            if cached_banner_source_url:
                effective_image_url = cached_banner_source_url
            else:
                effective_image_url = uncrop_image_with_clipdrop(image_url, padding=650)
                update_image_library_banner_source(image_url, effective_image_url)
            source_image = _fetch_image_from_url(effective_image_url)
        except Exception:
            # Safe fallback: keep banner generation available even if uncrop fails.
            effective_image_url = str(image_url).strip()
            source_image = _fetch_image_from_url(image_url)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    normalized_layout = (layout_type or "master-red").strip() or "master-red"

    prepared_sets = list(text_sets or [])
    if not prepared_sets:
        prepared_sets = [{"title": "", "subtitle": "", "disclaimer": ""}]

    results: list[dict] = []
    for set_index, text_set in enumerate(prepared_sets):
        title = str((text_set or {}).get("title", "")).strip()
        subtitle = str((text_set or {}).get("subtitle", "")).strip()
        disclaimer = str((text_set or {}).get("disclaimer", "")).strip()
        text_align = _normalize_text_align(str((text_set or {}).get("textAlign", "left")))
        badge_enabled = bool((text_set or {}).get("badgeEnabled", False))
        badge_top_text = str((text_set or {}).get("badgeTopText", "")).strip()
        badge_bottom_text = str((text_set or {}).get("badgeBottomText", "")).strip()
        accent_color = _normalize_hex_color(str((text_set or {}).get("accentColor", "#E3FF74")).strip(), "#E3FF74")
        try:
            badge_shift_x = int((text_set or {}).get("badgeShiftX", 0) or 0)
        except (TypeError, ValueError):
            badge_shift_x = 0
        try:
            badge_shift_y = int((text_set or {}).get("badgeShiftY", 0) or 0)
        except (TypeError, ValueError):
            badge_shift_y = 0
        badge_shift_x = max(0, badge_shift_x)
        badge_shift_y = max(0, badge_shift_y)

        for size_label in sizes:
            size_key = str(size_label).strip()
            if size_key not in BANNER_SIZE_MAP:
                continue
            width, height = BANNER_SIZE_MAP[size_key]
            _ = (width, height)

            if normalized_layout in {"master-red", "performance-red"}:
                banner = _render_master_banner_by_size(
                    bg_image=source_image,
                    size_key=size_key,
                    title=title,
                    subtitle=subtitle,
                    disclaimer=disclaimer,
                    text_align=text_align,
                    badge_enabled=badge_enabled,
                    badge_top_text=badge_top_text,
                    badge_bottom_text=badge_bottom_text,
                    accent_color=accent_color,
                    badge_shift_x=badge_shift_x,
                    badge_shift_y=badge_shift_y,
                    image_scale=image_scale,
                    image_shift_x=image_shift_x,
                    image_shift_y=image_shift_y,
                )
            else:
                banner = _render_master_banner_by_size(
                    bg_image=source_image,
                    size_key=size_key,
                    title=title,
                    subtitle=subtitle,
                    disclaimer=disclaimer,
                    text_align=text_align,
                    badge_enabled=badge_enabled,
                    badge_top_text=badge_top_text,
                    badge_bottom_text=badge_bottom_text,
                    accent_color=accent_color,
                    badge_shift_x=badge_shift_x,
                    badge_shift_y=badge_shift_y,
                    image_scale=image_scale,
                    image_shift_x=image_shift_x,
                    image_shift_y=image_shift_y,
                )

            file_name = f"banner_{normalized_layout}_set{set_index + 1}_{size_key}_{now}.png"
            file_path = OUTPUT_DIR / file_name
            banner.save(file_path, format="PNG", optimize=True)
            results.append(
                {
                    "text_set_index": set_index,
                    "size": size_key,
                    "file_name": file_name,
                    "url": f"/output/banners/{file_name}",
                }
            )
    return results, effective_image_url


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self) -> None:
        if is_basic_auth_enabled():
            if is_request_authorized(self.headers.get("Authorization", "")) or is_request_authorized_by_cookie(
                self.headers.get("Cookie", "")
            ):
                self.send_header(
                    "Set-Cookie",
                    f"{AUTH_COOKIE_NAME}={_build_auth_cookie_value()}; Path=/; HttpOnly; SameSite=Lax",
                )
        super().end_headers()

    def _require_basic_auth(self) -> bool:
        if self.path == "/health":
            return True
        if is_request_authorized(self.headers.get("Authorization", "")) or is_request_authorized_by_cookie(
            self.headers.get("Cookie", "")
        ):
            return True

        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Yango", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        body = b"Authentication required"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def do_GET(self):
        if not self._require_basic_auth():
            return
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/api/library-images":
            self._send_json(HTTPStatus.OK, {"images": list_image_library()})
            return
        if self.path == "/api/library-videos":
            self._send_json(HTTPStatus.OK, {"videos": list_video_library()})
            return
        super().do_GET()

    def do_POST(self):
        if not self._require_basic_auth():
            return
        if self.path not in {
            "/api/generate-image",
            "/api/generate-video-prompt",
            "/api/generate-video",
            "/api/remix-video",
            "/api/regenerate-image",
            "/api/edit-image",
            "/api/render-banners",
            "/api/upload-image",
            "/api/upload-video",
            "/api/create-banners-zip",
            "/api/delete-library-image",
            "/api/delete-library-video",
        }:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        try:
            if self.path == "/api/upload-image":
                content_type = self.headers.get("Content-Type", "")
                if content_type.startswith("multipart/form-data"):
                    form = cgi.FieldStorage(
                        fp=self.rfile,
                        headers=self.headers,
                        environ={
                            "REQUEST_METHOD": "POST",
                            "CONTENT_TYPE": content_type,
                        },
                    )
                    image_field = form["image"] if "image" in form else None
                    if image_field is None or not getattr(image_field, "file", None):
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "image is required"})
                        return
                    file_bytes = image_field.file.read()
                    file_name = str(getattr(image_field, "filename", "") or "").strip()
                    local_url = _save_uploaded_file_bytes(file_bytes, file_name)
                    self._send_json(HTTPStatus.OK, {"image_local_url": local_url})
                    return

            if self.path == "/api/upload-video":
                content_type = self.headers.get("Content-Type", "")
                if content_type.startswith("multipart/form-data"):
                    form = cgi.FieldStorage(
                        fp=self.rfile,
                        headers=self.headers,
                        environ={
                            "REQUEST_METHOD": "POST",
                            "CONTENT_TYPE": content_type,
                        },
                    )
                    video_field = form["video"] if "video" in form else None
                    if video_field is None or not getattr(video_field, "file", None):
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "video is required"})
                        return
                    file_bytes = video_field.file.read()
                    file_name = str(getattr(video_field, "filename", "") or "").strip()
                    local_url = _save_uploaded_video_bytes(file_bytes, file_name)
                    library_video = _upsert_video_library_record(
                        local_url,
                        base_video_url=local_url,
                        label=Path(urlparse(local_url).path).stem,
                    )
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "video_local_url": local_url,
                            "library_video": library_video,
                        },
                    )
                    return

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            body = json.loads(raw.decode("utf-8"))

            if self.path == "/api/generate-image":
                car_model = str(body.get("carModel", "")).strip()
                color_name = str(body.get("colorName", "")).strip()
                color_hex = str(body.get("colorHex", "")).strip()
                preferred_angle = str(body.get("preferredAngle", "")).strip()
                if not car_model:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "carModel is required"})
                    return
                prompt = call_openai(car_model, color_name, color_hex, preferred_angle)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    image_future = executor.submit(generate_image_with_recraft, prompt)
                    suggestions_future = executor.submit(generate_edit_suggestions_with_openai, car_model, prompt)
                    image_url, local_image_url = image_future.result()
                    suggestions = suggestions_future.result()
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "image_url": image_url,
                        "image_local_url": local_image_url,
                        "prompt": prompt,
                        "edit_suggestions": suggestions,
                    },
                )
                return

            if self.path == "/api/generate-video-prompt":
                image_url = str(body.get("imageUrl", "")).strip()
                car_model = str(body.get("carModel", "")).strip()
                color_name = str(body.get("colorName", "")).strip()
                base_prompt = str(body.get("basePrompt", "")).strip()
                if not image_url:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "imageUrl is required"})
                    return
                if not car_model:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "carModel is required"})
                    return
                prompt = generate_video_prompt_with_openai(
                    car_model=car_model,
                    image_url=image_url,
                    color_name=color_name,
                    base_prompt=base_prompt,
                )
                self._send_json(HTTPStatus.OK, {"prompt": prompt})
                return

            if self.path == "/api/generate-video":
                image_url = str(body.get("imageUrl", "")).strip()
                prompt = str(body.get("prompt", "")).strip()
                headlines_raw = body.get("headlines", [])
                if not image_url:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "imageUrl is required"})
                    return
                if not prompt:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "prompt is required"})
                    return
                if not isinstance(headlines_raw, list):
                    headlines_raw = []
                headlines = [str(item or "").strip() for item in headlines_raw if str(item or "").strip()]
                video_url, raw_local_video_url, local_video_url = generate_video_with_kling(
                    image_url=image_url,
                    prompt=prompt,
                    headlines=headlines,
                )
                library_video = _upsert_video_library_record(
                    raw_local_video_url or local_video_url or video_url,
                    base_video_url=raw_local_video_url,
                    source_image_url=image_url,
                    prompt=prompt,
                    label=Path(urlparse(raw_local_video_url or local_video_url or video_url).path).stem,
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "video_url": video_url,
                        "video_local_url": local_video_url,
                        "library_video": library_video,
                    },
                )
                return

            if self.path == "/api/remix-video":
                video_url = str(body.get("videoUrl", "")).strip()
                headlines_raw = body.get("headlines", [])
                if not video_url:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "videoUrl is required"})
                    return
                if not isinstance(headlines_raw, list):
                    headlines_raw = []
                headlines = [str(item or "").strip() for item in headlines_raw if str(item or "").strip()]
                source_record = get_video_library_record(video_url)
                if not source_record:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Video not found"})
                    return
                base_video_url = str(source_record.get("base_video_url") or video_url).strip()
                remixed_video_url = remix_video_titles(base_video_url, headlines)
                library_video = _upsert_video_library_record(
                    base_video_url,
                    base_video_url=base_video_url,
                    source_image_url=str(source_record.get("source_image_url", "")).strip(),
                    prompt=str(source_record.get("prompt", "")).strip(),
                    label=Path(urlparse(base_video_url).path).stem,
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "video_local_url": remixed_video_url,
                        "library_video": library_video,
                    },
                )
                return

            if self.path == "/api/upload-image":
                image_data = str(body.get("imageData", "")).strip()
                file_name = str(body.get("fileName", "")).strip()
                if not image_data:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "imageData is required"})
                    return
                local_url = _save_uploaded_data_url(image_data, file_name)
                self._send_json(HTTPStatus.OK, {"image_local_url": local_url})
                return

            if self.path == "/api/regenerate-image":
                prompt = str(body.get("prompt", "")).strip()
                if not prompt:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "prompt is required"})
                    return
                image_url, local_image_url = generate_image_with_recraft(prompt)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "image_url": image_url,
                        "image_local_url": local_image_url,
                        "prompt": prompt,
                    },
                )
                return

            if self.path == "/api/edit-image":
                image_url = str(body.get("imageUrl", "")).strip()
                edit_prompt = str(body.get("editPrompt", "")).strip()
                if not image_url:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "imageUrl is required"})
                    return
                if not edit_prompt:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "editPrompt is required"})
                    return
                edited_local_url = edit_image_with_gemini(image_url, edit_prompt)
                self._send_json(HTTPStatus.OK, {"image_local_url": edited_local_url})
                return

            if self.path == "/api/create-banners-zip":
                banner_urls = body.get("bannerUrls", [])
                if not isinstance(banner_urls, list):
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "bannerUrls must be an array"})
                    return
                zip_url = create_banners_zip(banner_urls)
                self._send_json(HTTPStatus.OK, {"zip_url": zip_url})
                return

            if self.path == "/api/delete-library-image":
                image_url = str(body.get("imageUrl", "")).strip()
                if not image_url:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "imageUrl is required"})
                    return
                deleted = delete_image_library_record(image_url)
                if not deleted:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Image not found"})
                    return
                self._send_json(HTTPStatus.OK, {"deleted": True})
                return

            if self.path == "/api/delete-library-video":
                video_url = str(body.get("videoUrl", "")).strip()
                if not video_url:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "videoUrl is required"})
                    return
                deleted = delete_video_library_record(video_url)
                if not deleted:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Video not found"})
                    return
                self._send_json(HTTPStatus.OK, {"deleted": True})
                return

            image_url = str(body.get("imageUrl", "")).strip()
            text_sets = body.get("textSets", [])
            if not isinstance(text_sets, list):
                text_sets = []
            if not text_sets:
                text_sets = [
                    {
                        "title": str(body.get("title", "")).strip(),
                        "subtitle": str(body.get("subtitle", "")).strip(),
                        "disclaimer": str(body.get("disclaimer", "")).strip(),
                    }
                ]
            layout_type = str(body.get("layoutType", "master-red")).strip() or "master-red"
            try:
                image_scale = float(body.get("imageScale", 1.0) or 1.0)
            except (TypeError, ValueError):
                image_scale = 1.0
            # Accept both scale formats:
            # - factor: 1.0 .. 1.5
            # - percent: 100 .. 150
            if image_scale > 10:
                image_scale = image_scale / 100.0
            image_scale = max(1.0, min(1.5, image_scale))
            try:
                image_shift_x = int(body.get("imageShiftX", 0) or 0)
            except (TypeError, ValueError):
                image_shift_x = 0
            try:
                image_shift_y = int(body.get("imageShiftY", 0) or 0)
            except (TypeError, ValueError):
                image_shift_y = 0
            sizes = body.get("sizes", [])
            if not isinstance(sizes, list):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "sizes must be an array"})
                return
            if not image_url:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "imageUrl is required"})
                return

            banners, effective_image_url = render_banner_images(
                image_url=image_url,
                text_sets=text_sets,
                layout_type=layout_type,
                sizes=sizes,
                image_scale=image_scale,
                image_shift_x=image_shift_x,
                image_shift_y=image_shift_y,
            )
            if not banners:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "No supported sizes provided"})
                return
            library_image = _upsert_image_library_record(
                image_url,
                kind=_infer_library_kind_from_name(Path(urlparse(image_url).path).name),
                banner_source_url=effective_image_url,
                original_name=Path(urlparse(image_url).path).name,
            )
            self._send_json(
                HTTPStatus.OK,
                {
                    "banners": banners,
                    "source_image_url": effective_image_url,
                    "library_image": library_image,
                },
            )
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    display_host = HOST
    if HOST == "0.0.0.0":
        display_host = "127.0.0.1"
    print(f"Serving on http://{display_host}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
