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
DEFAULT_DATA_ROOT = Path("/app/data") if Path("/app/data").exists() else ROOT
DATA_ROOT = Path(os.getenv("YANGO_DATA_DIR", os.getenv("RAILWAY_VOLUME_MOUNT_PATH", str(DEFAULT_DATA_ROOT)))).expanduser()
PERSISTENT_OUTPUT_ROOT = DATA_ROOT / "output" if DATA_ROOT != ROOT else ROOT / "output"
EPHEMERAL_OUTPUT_ROOT = ROOT / "output"
OUTPUT_DIR = EPHEMERAL_OUTPUT_ROOT / "banners"
PERSISTENT_GENERATED_DIR = PERSISTENT_OUTPUT_ROOT / "generated"
TEMP_GENERATED_DIR = EPHEMERAL_OUTPUT_ROOT / "generated"
GENERATED_DIR = TEMP_GENERATED_DIR
ZIP_DIR = EPHEMERAL_OUTPUT_ROOT / "archives"
UNCROP_DIR = EPHEMERAL_OUTPUT_ROOT / "uncrop"
UPSCALE_DIR = EPHEMERAL_OUTPUT_ROOT / "upscaled"
VIDEO_DIR = EPHEMERAL_OUTPUT_ROOT / "videos"
DEFAULT_PACKSHOT_VIDEO = ROOT / "assets" / "video" / "packshot.mp4"
IMAGE_LIBRARY_FILE = PERSISTENT_OUTPUT_ROOT / "image_library.json"
IMAGE_LIBRARY_LOCK = threading.Lock()
VIDEO_LIBRARY_FILE = EPHEMERAL_OUTPUT_ROOT / "video_library.json"
VIDEO_LIBRARY_LOCK = threading.Lock()
BRAND_LOGO_TEXT = "YANGO"
BRAND_LOGO_TEXT_BY_KEY = {
    "yango": "YANGO",
    "yango-drive": "YANGO DRIVE",
}
UNCROP_TARGET_WIDTH = 3200
UNCROP_TARGET_HEIGHT = 2472
UNCROP_MIN_HORIZONTAL_MARGIN = 262
UNCROP_MIN_VERTICAL_MARGIN = 202
UNCROP_PREPROCESS_TARGET_MAX_SIDE = 1376
MAGNIFIC_SCALE_FACTORS = (2, 4, 8, 16)
THREE_D_ASPECT_RATIO = "4:3"
THREE_D_STYLE_REFERENCE_PATHS = [
    ROOT / "assets" / "style-references" / "3d" / "safety-vest.jpeg",
    ROOT / "assets" / "style-references" / "3d" / "car-seat.jpeg",
    ROOT / "assets" / "style-references" / "3d" / "side-mirror.jpeg",
    ROOT / "assets" / "style-references" / "3d" / "driving-licence.jpeg",
    ROOT / "assets" / "style-references" / "3d" / "steering-wheel.jpeg",
    ROOT / "assets" / "style-references" / "3d" / "traffic-light.png",
    ROOT / "assets" / "style-references" / "3d" / "fingerprint-lock.png",
]
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

SUPER_APP_VISUAL_GUIDE = """
Urban Fashion x Documentary Realism for ride-hailing performance visuals.
- Always write the final prompt in English and return only the prompt text.
- The result must be a believable commercial photo shoot, not an illustration.
- Use one or two main characters only, with one clear scenario-driven action.
- Characters should look local to the selected country unless the situation explicitly requires otherwise.
- No posing and no eye contact with the camera.
- Fashion should be bold, confident, modern global street fashion, with clothing matching the country climate and scenario time of day.
- No traditional, ethnic, folkloric, ceremonial clothing, and no ethnic patterns.
- If a phone appears, it must be red. Do not mention phone brand, model, or interface.
- Exterior locations must be described through architecture and nearby surfaces, not generic labels like street, alley, road, market, or sidewalk.
- Exterior spaces need a building surface, a transition element, and maintained lived-in details.
- Background people, if present, must be turned away, in profile, blurred, or cropped, never staring at the main characters.
- Use warm color grading, natural light or flash, texture-focused realism, and cropped asymmetrical composition.
- Do not show logos, branding, app UI, watermarks, or text.
"""

THREE_D_VISUAL_GUIDE = """
Premium tactile 3D object render style for Yango Perf asset generation.
- Always write the final prompt in English and return only the prompt text.
- The final prompt must be optimized for Nano Banana 2 / Gemini image generation.
- Create a single hero object or a small tightly related object set, not a full scene.
- Use a bold solid Yango-red background with a subtle studio gradient, no props unless requested.
- Use high-end 3D product-render realism: rounded bevels, thick edges, soft imperfections, realistic material grain, tiny stitching, mesh, rubber, brushed metal, glass, holographic film, LED diffusion, or fabric weave when relevant.
- Composition should be close, cropped, asymmetrical, floating or isolated, with the object filling most of the frame and a strong premium commercial silhouette.
- Lighting uses warm golden rim light from one side, soft large studio key light, clean shadows, and refined specular highlights.
- Camera uses macro/product perspective, low or three-quarter angle, shallow but controlled depth of field, no fisheye distortion.
- No people, no hands, no logos, no UI, no watermarks, no readable text unless the user explicitly asks for text.
- If the user asks for a document, card, licence, sign, label, or screen, keep text minimal, generic, and mostly unreadable unless exact text is requested.
- Avoid cartoon, toy-like plastic, flat vector, low-poly, cluttered background, photoreal street photography, and generic stock imagery.
"""

COMPOSITION_RULES = {
    "inside the car": (
        "Interior back-seat car composition with a wide editorial photo feel. "
        "Camera is inside the rear passenger area, angled across the back seat so the side window, door panel, roof liner, headrests, seat belts, and upholstery frame the subject. "
        "Passenger(s) sit naturally in the back seat, relaxed or mid-gesture, and every visible passenger must wear a clearly visible, physically correct seat belt. "
        "Use believable fashion/lifestyle styling and local city details visible through the window. "
        "Use warm natural daylight, realistic car-interior shadows, slight wide-angle perspective, layered foreground objects when appropriate, and no visible driver."
    ),
    "near the car": (
        "Exterior lifestyle composition beside the selected vehicle, shot wide enough to clearly show the side profile of the car or a clean rear 3/4 side view, plus the street, pavement, architecture, and local neighborhood context. "
        "The character must be outside and next to the car, close to the side doors or rear quarter, walking past it, waiting beside it, holding belongings, checking a phone, or interacting near the closed vehicle. "
        "All car doors and trunk must be fully closed; do not show anyone entering, exiting, leaning into, sitting in, or standing by an open door. "
        "The car side must remain readable, with visible side panels, windows, door handles, wheels, and realistic reflections, while the human action leads the story. "
        "Use low-to-eye-level editorial framing, natural sunlight, real street shadows, lots of environmental detail, and a candid ride-hailing moment rather than a posed car ad."
    ),
    "getting into the car": (
        "Getting-into-the-car transition moment focused on the open rear passenger door only. "
        "Show the character stepping into, leaning into, sitting down through, or just exiting the rear door; the open door frame, rear seat, wheel, door interior, and car body should create strong foreground structure. "
        "Use low exterior angles near the rear wheel or a view from inside the back seat looking toward the open door, with believable body movement, bags or phone when relevant, and local street context beyond the car. "
        "Do not use the front door; avoid static posing beside a closed vehicle."
    ),
    "passenger with driver": (
        "Interior ride-hailing interaction with both driver and passenger visible in the same frame when physically plausible. "
        "Frame from inside the car or through an open side door/window so the driver is in the front seat and the passenger(s) are in the back seat, sharing a natural conversation, greeting, laugh, or route moment. "
        "Every visible person inside the car must wear a clearly visible, physically correct seat belt. "
        "Use dashboard/seat/door elements to create depth, allow slight foreground blur from steering wheel or door frame, and keep the mood candid, warm, and documentary rather than posed. "
        "The driver must remain clearly the driver, with hands or posture oriented toward driving, while the passenger remains clearly in the rear passenger area."
    ),
    "window": (
        "Window-focused exterior car composition shot from outside along the side of the vehicle. "
        "Frame the passenger through the rear side window, with the window opening, glass edge, B/C pillar, door handle, and car body forming the main graphic structure. "
        "The passenger is inside the back seat, leaning on the window line, resting an arm on the lowered glass, looking out, or using a phone; a clearly visible, physically correct seat belt and interior should remain visible. "
        "Use realistic glass reflections of trees/buildings/sky, shallow depth between exterior street and interior passenger, and a close editorial crop that makes the window frame the subject. "
        "Do not make it a fully interior shot or a wide full-car exterior; the window and reflections must dominate the composition."
    ),
    "near the moto": (
        "Layered exterior lifestyle composition near the selected motorcycle. "
        "Place the hero in the foreground or midground walking, waiting, carrying personal items, checking a phone, or moving past the motorcycle, while the motorcycle and driver remain nearby as ride-hailing context. "
        "The motorcycle should be visible but not necessarily full-frame; it can sit behind or beside the hero, with the driver waiting, adjusting gear, or preparing the pickup. "
        "Use strong local street depth, market or neighborhood architecture, textured pavement, warm daylight, candid movement, and editorial foreground/background layering. "
        "Do not make this a driver-only shot, product-only motorcycle shot, or car-related scene."
    ),
    "driver": (
        "Motorcycle driver-only street editorial composition. "
        "Show one driver with the selected motorcycle in a full side or low 3/4 view, either seated on the bike, hands on or near the handlebars, adjusting gear, waiting at the curb, or preparing to ride. "
        "The motorcycle must be clearly readable as a whole object with visible wheels, tank/body, handlebar, mirror, and seat, while the driver remains the only rider. "
        "Use strong local architecture, market streets, textured walls, pavement, warm natural light, and optional blurred foreground passerby for depth and candid realism. "
        "Do not add a passenger, do not crop into only a portrait, and do not turn it into a product-only motorcycle shot."
    ),
}

MOTO_COMPOSITION_RULES = {
    "passenger with driver": (
        "Motorcycle passenger-with-driver exterior hero-shot. "
        "Show the selected motorcycle in side or low 3/4 profile with the driver seated in front, hands on the handlebars, and one passenger seated directly behind, physically balanced and already ready to ride. "
        "Both people should feel naturally placed on the bike; helmets should appear when locally plausible, and the passenger may hold a helmet, backpack, delivery bag, or rear grip. "
        "Use a low-to-eye-level editorial street frame with the motorcycle body, handlebar, mirror, fuel tank, and seat clearly readable, plus strong local architecture or market/street context behind them. "
        "Do not show a car interior, car doors, a standing passenger beside the bike, or an impossible seating arrangement."
    ),
}

TUKTUK_COMPOSITION_RULES = {
    "near the tuk tuk": (
        "Wide street/fashion lifestyle composition near the selected tuk-tuk. "
        "Place the hero in the foreground or midground walking past, waiting beside, approaching, or just leaving the tuk-tuk, carrying market bags, flowers, personal items, or a phone when relevant. "
        "Keep the tuk-tuk clearly identifiable nearby or behind the hero, ideally with an open side entrance/canopy/cabin visible and the driver waiting inside or beside it as ride-hailing context. "
        "Use busy local market streets, fruit stands, storefronts, pedestrians, textured pavement, warm daylight or evening shop light, and layered foreground/background movement. "
        "The human story leads, the tuk-tuk anchors the scene; do not make it an inside-tuk-tuk shot, driver-only portrait, or clean product shot."
    ),
    "inside tuk tuk": (
        "Inside-the-tuk-tuk passenger composition from within the small cabin or just outside the open side. "
        "Frame passenger(s) seated on the rear bench while the driver is visible in the front/foreground or partially cropped, separated by the tuk-tuk frame, railings, canopy, and compact cabin structure. "
        "Use the open side, small windows, metal bars, vinyl bench, low roof, dashboard/handlebar area, and street visible through the openings to create depth. "
        "The feeling should be cramped, tactile, wide-angle, documentary, and close, with local traffic, shops, pedestrians, or evening street light visible outside. "
        "Do not make it a car interior, do not place passengers in car-style seats, and do not turn it into a clean exterior shot."
    ),
    "driver": (
        "Tuk-tuk driver-focused editorial composition from outside the vehicle, looking through the front windshield, side opening, or metal cabin frame. "
        "Show the driver seated at the controls with hands on the handlebar/steering controls, ready to move or waiting in traffic; the tuk-tuk windshield, canopy, front frame, mirrors, dashboard, and cabin structure should dominate the foreground. "
        "Use realistic glass reflections, street lights or warm shop light when appropriate, layered background traffic/pedestrians, and a candid nighttime or busy-street atmosphere. "
        "A rear passenger may be softly visible only as secondary context, but the driver must be the clear subject. "
        "Do not turn it into a car/motorcycle scene or a clean exterior product shot."
    ),
}

VEHICLE_TYPE_RULES = {
    "car": (
        "Use the selected car model exactly, with the selected color and latest body-year appended. "
        "For interior scenes, passengers are in the back seat and the driver is never visible unless the composition explicitly asks for driver interaction. "
        "Whenever any person is inside the car, every visible occupant must wear a clearly visible, physically correct seat belt."
    ),
    "moto": (
        "Use the selected motorcycle color. A driver is present unless the selected composition explicitly focuses only on the motorcycle context. "
        "Only include a passenger when the selected composition asks for one, and keep all motorcycle seating physically plausible."
    ),
    "tuktuk": (
        "Use the selected tuk-tuk color. Follow the selected tuk-tuk composition for whether the scene shows a passenger, driver, or exterior pickup context. "
        "Keep the vehicle clearly recognizable as a tuk-tuk, not a car or motorcycle."
    ),
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
    PERSISTENT_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    UNCROP_DIR.mkdir(parents=True, exist_ok=True)
    UPSCALE_DIR.mkdir(parents=True, exist_ok=True)
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


def _infer_library_kind_from_url(image_url: str) -> str:
    path = urlparse(str(image_url or "").strip()).path.lower()
    if "/generated/uploaded/" in path:
        return "uploaded"
    return _infer_library_kind_from_name(Path(path).name)


def _normalize_image_country_bucket(country: str, *, fallback: str = "other") -> str:
    value = str(country or "").strip()
    if not value:
        value = fallback
    safe_value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()
    return safe_value or fallback


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
        "country": str(record.get("country", "")).strip(),
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
    country: str = "",
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
        record["country"] = str(country or record.get("country") or "").strip()
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
                    "KLING_ACCESS_KEY",
                    "KLING_SECRET_KEY",
                    "REPLICATE_API_TOKEN",
                    "REPLICATE_MODEL",
                    "RECRAFT_API_TOKEN",
                    "RECRAFT_API_KEY",
                    "RECRAFT_MODEL",
                    "CLIPDROP_API_KEY",
                    "MAGNIFIC_API_KEY",
                } and env_value:
                    os.environ.setdefault(env_key, env_value)
                continue

            # Raw token fallback format.
            if line.startswith("sk-"):
                os.environ.setdefault("OPENAI_API_KEY", line)
            elif ":" in line and len(line) > 20:
                os.environ.setdefault("TELEGRAM_BOT_TOKEN", line)


load_tokens_from_file()


def _normalize_brand_key(brand: str) -> str:
    normalized = str(brand or "").strip().lower().replace("_", "-")
    if normalized in {"drive", "yango drive", "yango-drive"}:
        return "yango-drive"
    return "yango"


def _brand_logo_text(brand: str) -> str:
    return BRAND_LOGO_TEXT_BY_KEY.get(_normalize_brand_key(brand), BRAND_LOGO_TEXT)


def _default_vehicle_color(vehicle_type: str) -> str:
    vehicle_type = (vehicle_type or "car").strip().lower()
    if vehicle_type in {"moto", "tuktuk"}:
        return "red"
    return "white"


def _vehicle_color_for_prompt(vehicle_type: str, color_name: str = "") -> str:
    color = (color_name or "").strip()
    if color:
        return color
    return _default_vehicle_color(vehicle_type)


def _normalize_vehicle_for_prompt(vehicle_model: str, vehicle_type: str, color_name: str = "") -> str:
    vehicle_type = (vehicle_type or "car").strip().lower()
    vehicle_color = _vehicle_color_for_prompt(vehicle_type, color_name)
    if vehicle_type == "moto":
        return f"{vehicle_color} motorcycle"
    if vehicle_type == "tuktuk":
        return f"{vehicle_color} tuk-tuk"

    request = PromptRequest(car=vehicle_model, color="")
    try:
        car_with_year = infer_car_with_year_with_openai(request)
    except Exception:
        car_with_year = vehicle_model
    return f"{vehicle_color} {car_with_year}".strip()


def call_openai(
    car_model: str,
    color_name: str = "",
    color_hex: str = "",
    preferred_angle_label: str = "",
    *,
    service: str = "Ride-hailing",
    style: str = "Photo",
    country: str = "",
    transport_label: str = "",
    transport_code: str = "",
    basic_class: str = "",
    vehicle_type: str = "car",
    composition: str = "",
    model_description: str = "",
    face_reference_image_url: str = "",
    situation_description: str = "",
) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    _ = color_hex, preferred_angle_label
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    vehicle_type = (vehicle_type or "car").strip().lower()
    vehicle_color = _vehicle_color_for_prompt(vehicle_type, color_name)
    vehicle_descriptor = _normalize_vehicle_for_prompt(car_model, vehicle_type, vehicle_color)
    composition_key = (composition or "").strip().lower()
    composition_rules = {}
    if vehicle_type == "moto":
        composition_rules = MOTO_COMPOSITION_RULES
    elif vehicle_type == "tuktuk":
        composition_rules = TUKTUK_COMPOSITION_RULES
    composition_rule = composition_rules.get(
        composition_key,
        COMPOSITION_RULES.get(composition_key, "Use a cropped, asymmetrical documentary composition."),
    )
    vehicle_rule = VEHICLE_TYPE_RULES.get(vehicle_type, VEHICLE_TYPE_RULES["car"])

    user_prompt = f"""
Create one final image-generation prompt for a Yango Perf Super App ride-hailing visual.

Selected inputs:
- Service: {service or "Ride-hailing"}
- Style: {style or "Photo"}
- Country: {country or "not specified"}
- Transport tariff: {transport_label or "not specified"}
- Tariff class: {basic_class or "not specified"}
- Tariff code: {transport_code or "not specified"}
- Vehicle type: {vehicle_type}
- Vehicle color rule: {vehicle_color}
- Vehicle to use: {vehicle_descriptor}
- Composition: {composition or "not specified"}
- Hero/model description: {model_description or "not provided"}
- Face reference image: {"provided" if face_reference_image_url else "not provided"}
- Situation description: {situation_description or "not provided"}

Composition rule:
{composition_rule}

Vehicle rule:
{vehicle_rule}

Face reference rule:
{"Use the provided reference image only for the hero/model's facial features: face shape, eyes, nose, mouth, skin tone, expression, and other face identity traits. Do not copy clothing, accessories, pose, lighting, background, camera angle, body shape, age cues beyond the face, or any non-facial detail from the reference image." if face_reference_image_url else "No face reference image is provided, so create the hero/model from the written description only."}

Country localization:
The scene must feel specifically local to {country or "the selected country"} through architecture, materials, climate, demographics, and small real-life details.

Output format:
Main character(s) and action: 1-2 sentences
Clothing and appearance: 2-3 sentences
Location and surroundings / interior: 2-3 sentences
Time and atmosphere: 1 sentence
Background elements: 0-1 sentence
Photography style and angle: 1 sentence

Final check before answering:
- Correct selected vehicle is used.
- Car models include latest body-year naming.
- Vehicle color follows the selected color rule exactly.
- Impossible car-only compositions are not used for motorcycle or tuk-tuk.
- If a face reference image is provided, the prompt explicitly says to take only facial features from the reference image and not clothing, accessories, pose, background, or other non-facial details.
- If a phone appears, it is red.
- No logos, no app UI, no text, no watermark.
- The word illustration is not used.
"""

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You generate strict, production-ready image prompts for realistic ride-hailing campaign visuals. "
                    "If the user inputs conflict with the guide, the guide wins. Return only the final prompt text.\n\n"
                    f"--- GUIDE START ---\n{SUPER_APP_VISUAL_GUIDE}\n--- GUIDE END ---"
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
    )

    prompt = (response.output_text or "").strip()
    if not prompt:
        raise RuntimeError("OpenAI returned an empty response.")
    return prompt


def call_yango_drive_openai(
    car_model: str,
    color_name: str,
    color_hex: str,
    preferred_angle_label: str,
    *,
    country: str = "",
    city: str = "",
) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    angle_label = preferred_angle_label.strip()
    angle_rules = ANGLE_RULES.get(angle_label, "")
    location_parts = [part for part in [city.strip(), country.strip()] if part]
    location_text = ", ".join(location_parts) or None

    request = PromptRequest(
        car=car_model,
        color=color_name,
        location_text=location_text,
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

    _ = color_hex
    return generate_prompt_with_openai(request)


def _mime_type_for_image_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _image_data_url_from_path(path: Path) -> str:
    raw = path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{_mime_type_for_image_path(path)};base64,{encoded}"


def _three_d_reference_paths() -> list[Path]:
    return [path for path in THREE_D_STYLE_REFERENCE_PATHS if path.exists()]


def generate_three_d_prompt_with_openai(description: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    request = str(description or "").strip()
    if not request:
        raise RuntimeError("Description is required")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    content: list[dict] = [
        {
            "type": "input_text",
            "text": (
                "Create one final image-generation prompt for Nano Banana 2.\n\n"
                f"User description:\n{request}\n\n"
                "Use the attached images only as style references. Do not copy their exact objects unless the user asks for the same object. "
                "Extract the shared visual language: bold red studio background, premium tactile 3D realism, cropped isolated object composition, "
                "warm rim light, detailed materials, bevels, texture, and polished commercial product-render finish.\n\n"
                "Return only the final prompt text."
            ),
        }
    ]
    for path in _three_d_reference_paths():
        content.append({"type": "input_image", "image_url": _image_data_url_from_path(path)})

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You write strict production-ready prompts for AI image generators. "
                    "Optimize every answer specifically for Nano Banana 2 / Gemini image generation. "
                    "Return only the final prompt text.\n\n"
                    f"--- 3D STYLE GUIDE START ---\n{THREE_D_VISUAL_GUIDE}\n--- 3D STYLE GUIDE END ---"
                ),
            },
            {"role": "user", "content": content},
        ],
    )

    prompt = (response.output_text or "").strip()
    if not prompt:
        raise RuntimeError("OpenAI returned an empty 3D prompt")
    return prompt


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
    if not value.startswith("/output/"):
        raise RuntimeError("Expected local output URL")
    path = _resolve_public_file_path(value)
    if not _is_allowed_output_path(path):
        raise RuntimeError("Resolved path is outside output directory")
    return path


def _is_allowed_output_path(path: Path) -> bool:
    resolved = path.resolve()
    output_roots = {
        str(PERSISTENT_OUTPUT_ROOT.resolve()),
        str(EPHEMERAL_OUTPUT_ROOT.resolve()),
    }
    return any(str(resolved).startswith(root) for root in output_roots)


def _resolve_public_file_path(path: str) -> Path:
    value = unquote(str(path or "").strip())
    if value.startswith("/output/"):
        relative_path = value.removeprefix("/output/")
        if relative_path.startswith("generated/"):
            persistent_path = (PERSISTENT_OUTPUT_ROOT / relative_path).resolve()
            temp_path = (EPHEMERAL_OUTPUT_ROOT / relative_path).resolve()
            local_path = persistent_path if persistent_path.exists() else temp_path
        else:
            local_path = (EPHEMERAL_OUTPUT_ROOT / relative_path).resolve()
        if not _is_allowed_output_path(local_path):
            raise RuntimeError("Resolved path is outside output directory")
        return local_path
    return (ROOT / value.lstrip("/")).resolve()


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


def _build_logo_overlay_filter(width: int, height: int, brand: str = "yango") -> str:
    logo_font = ROOT / "assets" / "fonts" / "YangoGroupHeadline-HeavyItalic.ttf"
    logo_font_size = max(28, int(round(width * (52.833 / 1024))))
    logo_x = int(round(width * (48 / 1024)))
    logo_y = int(round(height * (48 / 576)))
    logo_text = _brand_logo_text(brand)
    return (
        "drawtext="
        f"fontfile='{_ffmpeg_drawtext_path(logo_font)}':"
        f"text='{_escape_drawtext_value(logo_text)}':"
        f"fontsize={logo_font_size}:"
        "fontcolor=white@0.58:"
        f"x={logo_x}:y={logo_y}"
    )


def _build_title_overlay_filters(
    width: int,
    height: int,
    main_duration: float,
    headlines: list[str],
    temp_dir: Path,
    brand: str = "yango",
) -> list[str]:
    filters: list[str] = [_build_logo_overlay_filter(width, height, brand=brand)]
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


def _compose_video_with_titles_and_packshot(
    base_video_local_url: str,
    headlines: list[str],
    packshot_path: Optional[Path] = None,
    brand: str = "yango",
) -> str:
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
        filter_chain = ",".join(
            _build_title_overlay_filters(width, height, main_duration, headlines, temp_dir, brand=brand)
        ) or "null"
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


def remix_video_titles(base_video_url: str, headlines: Optional[list[str]] = None, brand: str = "yango") -> str:
    return _compose_video_with_titles_and_packshot(base_video_url, headlines or [], brand=brand)


def generate_video_with_kling(
    image_url: str,
    prompt: str,
    headlines: Optional[list[str]] = None,
    brand: str = "yango",
) -> tuple[str, str, str]:
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
            final_video_url = _compose_video_with_titles_and_packshot(raw_local_video_url, headlines or [], brand=brand)
            return video_url, raw_local_video_url, final_video_url
        if status in {"failed", "canceled", "cancelled"}:
            error_detail = str(payload.get("message") or payload.get("error") or status).strip()
            raise RuntimeError(f"Kling generation failed: {error_detail}")
        time.sleep(max(1.0, poll_interval))

    raise RuntimeError("Kling generation timed out")


def _save_generated_image_bytes(image_bytes: bytes, *, prefix: str = "generated", country: str = "") -> str:
    _ensure_output_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:8]
    file_name = f"{prefix}_{stamp}_{unique_suffix}.png"
    bucket = _normalize_image_country_bucket(country, fallback="other")
    target_dir = GENERATED_DIR / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file_name
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.save(file_path, format="PNG", optimize=True)
    return f"/output/generated/{bucket}/{file_name}"


def _persist_image_for_library(image_url: str, *, country: str = "") -> str:
    normalized_url = str(image_url or "").strip()
    if not normalized_url:
        raise ValueError("image_url is required")

    raw = _read_image_bytes_from_url(normalized_url)
    source_name = Path(urlparse(normalized_url).path).name
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", source_name).strip("._") or ""
    if not safe_name:
        safe_name = f"saved_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    safe_name = f"{Path(safe_name).stem or 'saved'}.png"

    _ensure_output_directories()
    bucket = _normalize_image_country_bucket(country, fallback="other")
    target_dir = PERSISTENT_GENERATED_DIR / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / safe_name
    if not file_path.exists():
        image = Image.open(BytesIO(raw)).convert("RGB")
        image.save(file_path, format="PNG", optimize=True)
    return f"/output/generated/{bucket}/{safe_name}"


def _gemini_generate_image_bytes(
    *,
    parts: list[dict],
    aspect_ratio: Optional[str] = None,
    retry_prefix: str = "",
) -> bytes:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model = os.getenv("GEMINI_MODEL", "").strip() or "gemini-3.1-flash-image-preview"
    if model == "gemini-2.5-flash-image-preview":
        model = "gemini-3.1-flash-image-preview"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }

    def request_image(request_parts: list[dict], request_aspect_ratio: Optional[str]) -> tuple[Optional[bytes], list[dict]]:
        payload: dict = {"contents": [{"parts": request_parts}]}
        generation_config: dict = {"responseModalities": ["TEXT", "IMAGE"]}
        if request_aspect_ratio:
            generation_config["imageConfig"] = {"aspectRatio": request_aspect_ratio}
        payload["generationConfig"] = generation_config

        response = _request_json(url, "POST", headers, payload)
        return _extract_gemini_image_bytes(response)

    retry_parts = [dict(part) for part in parts]
    if retry_parts and isinstance(retry_parts[0], dict) and "text" in retry_parts[0]:
        prefix = retry_prefix.strip() or (
            "Return an image as the image output. Do not call tools or functions. Do not answer with text only."
        )
        retry_parts[0]["text"] = (
            f"{prefix} "
            f"{retry_parts[0]['text']}"
        )

    attempts = [
        (parts, aspect_ratio),
        (retry_parts, None),
    ]
    debug_details = []
    for request_parts, request_aspect_ratio in attempts:
        image_bytes, attempt_details = request_image(request_parts, request_aspect_ratio)
        if image_bytes:
            return image_bytes
        debug_details.extend(attempt_details)

    suffix = f" Details: {json.dumps(debug_details, ensure_ascii=False)[:1200]}" if debug_details else ""
    raise RuntimeError(f"Gemini model {model} did not return an image.{suffix}")


def _extract_gemini_image_bytes(response: dict) -> tuple[Optional[bytes], list[dict]]:
    candidates = response.get("candidates") or []
    debug_details = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            detail = {}
            finish_reason = candidate.get("finishReason")
            if finish_reason:
                detail["finishReason"] = finish_reason
            safety_ratings = candidate.get("safetyRatings")
            if safety_ratings:
                detail["safetyRatings"] = safety_ratings
            if detail:
                debug_details.append(detail)
        content = candidate.get("content") if isinstance(candidate, dict) else None
        cand_parts = (content or {}).get("parts") if isinstance(content, dict) else None
        if not isinstance(cand_parts, list):
            continue
        for part in cand_parts:
            if not isinstance(part, dict):
                continue
            text = str(part.get("text") or "").strip()
            if text:
                debug_details.append({"text": text[:500]})
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict):
                continue
            data = inline.get("data")
            if data:
                return base64.b64decode(data), debug_details

    return None, debug_details


def generate_image_with_openai(prompt: str, *, country: str = "") -> tuple[str, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    timeout_seconds = float(os.getenv("OPENAI_IMAGE_TIMEOUT_SECONDS", "480") or "480")
    client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
    model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    size = os.getenv("OPENAI_IMAGE_SIZE", "1536x1024")
    quality = os.getenv("OPENAI_IMAGE_QUALITY", "high")
    response = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        quality=quality,
        n=1,
        output_format="png",
    )
    if not response.data:
        raise RuntimeError("OpenAI image generation returned no image data")

    image = response.data[0]
    b64_json = getattr(image, "b64_json", "") or ""
    if not b64_json:
        raise RuntimeError("OpenAI image generation returned no b64_json data")

    image_bytes = base64.b64decode(b64_json)
    local_url = _save_generated_image_bytes(image_bytes, prefix="generated", country=country)
    return local_url, local_url


def generate_image_with_recraft(prompt: str, *, country: str = "") -> tuple[str, str]:
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
        image_bytes = base64.b64decode(b64_json)
        local_url = _save_generated_image_bytes(image_bytes, prefix="generated", country=country)
        return image_url, local_url
    if image_url:
        local_url = _save_generated_image_local(image_url)
        return image_url, local_url

    raise RuntimeError("Recraft returned neither b64_json nor image URL")


def generate_image_with_openai_face_reference(
    prompt: str,
    face_reference_image_url: str,
    *,
    country: str = "",
) -> tuple[str, str]:
    reference_url = str(face_reference_image_url or "").strip()
    if not reference_url:
        return generate_image_with_openai(prompt, country=country)

    reference_image = _fetch_image_from_url(reference_url).convert("RGB")
    reference_buf = BytesIO()
    reference_image.save(reference_buf, format="PNG")
    reference_buf.seek(0)
    reference_buf.name = "face_reference.png"
    reference_prompt = (
        f"{prompt}\n\n"
        "Use the attached reference image only for the hero/model's facial features. "
        "Match face shape, eyes, nose, mouth, skin tone, expression, and other face identity traits from the reference image. "
        "Do not copy clothing, accessories, pose, lighting, background, camera angle, body shape, or any non-facial detail from the reference image."
    )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    timeout_seconds = float(os.getenv("OPENAI_IMAGE_TIMEOUT_SECONDS", "480") or "480")
    client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
    model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    size = os.getenv("OPENAI_IMAGE_SIZE", "1536x1024")
    quality = os.getenv("OPENAI_IMAGE_QUALITY", "high")
    response = client.images.edit(
        model=model,
        image=reference_buf,
        prompt=reference_prompt,
        size=size,
        quality=quality,
        n=1,
        output_format="png",
    )
    if not response.data:
        raise RuntimeError("OpenAI image generation returned no image data")

    image = response.data[0]
    b64_json = getattr(image, "b64_json", "") or ""
    if not b64_json:
        raise RuntimeError("OpenAI image generation returned no b64_json data")

    image_bytes = base64.b64decode(b64_json)
    local_url = _save_generated_image_bytes(image_bytes, prefix="generated", country=country)
    return local_url, local_url


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


def edit_image_with_gemini(
    source_image_url: str,
    edit_prompt: str,
    reference_image_url: str = "",
    aspect_ratio: str = "",
    country: str = "",
) -> str:
    # Direct Gemini image editing (Nano Banana family).
    source_image = _fetch_image_from_url(source_image_url).convert("RGB")
    buf = BytesIO()
    source_image.save(buf, format="PNG")
    image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    parts = [
        {"text": edit_prompt},
        {"inline_data": {"mime_type": "image/png", "data": image_b64}},
    ]
    if reference_image_url:
        reference_image = _fetch_image_from_url(reference_image_url).convert("RGB")
        reference_buf = BytesIO()
        reference_image.save(reference_buf, format="PNG")
        reference_b64 = base64.b64encode(reference_buf.getvalue()).decode("ascii")
        parts.append({"inline_data": {"mime_type": "image/png", "data": reference_b64}})
    image_bytes = _gemini_generate_image_bytes(
        parts=parts,
        aspect_ratio=aspect_ratio.strip() or None,
        retry_prefix=(
            "Edit the provided image and return the edited image as the image output. "
            "Do not call tools or functions. Do not answer with text only."
        ),
    )
    return _save_generated_image_bytes(image_bytes, prefix="edited", country=country)


def generate_three_d_image_with_gemini(prompt: str, *, country: str = "") -> tuple[str, str]:
    final_prompt = str(prompt or "").strip()
    if not final_prompt:
        raise RuntimeError("prompt is required")

    parts: list[dict] = [
        {
            "text": (
                "Generate a new image from this prompt. Use the attached images only as style references for the red-background "
                "premium tactile 3D render look; do not copy their exact objects unless requested in the prompt. "
                "Return the generated image as image output, not a text description.\n\n"
                f"{final_prompt}"
            )
        }
    ]
    for path in _three_d_reference_paths():
        raw = path.read_bytes()
        parts.append(
            {
                "inline_data": {
                    "mime_type": _mime_type_for_image_path(path),
                    "data": base64.b64encode(raw).decode("ascii"),
                }
            }
        )

    image_bytes = _gemini_generate_image_bytes(
        parts=parts,
        aspect_ratio=os.getenv("GEMINI_3D_ASPECT_RATIO", THREE_D_ASPECT_RATIO).strip() or THREE_D_ASPECT_RATIO,
        retry_prefix=(
            "Generate a new image and return it as image output. "
            "Use attached images only as visual style references. Do not answer with text only."
        ),
    )
    local_url = _save_generated_image_bytes(image_bytes, prefix="generated_3d", country=country or "3d")
    return local_url, local_url


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


def _local_public_path_from_url(url: str) -> Optional[Path]:
    parsed = urlparse(url)
    if url.startswith("/") or (not parsed.scheme and not url.startswith("data:")):
        return _resolve_public_file_path(url)

    if parsed.scheme in {"http", "https"} and parsed.path.startswith(("/assets/", "/output/")):
        return _resolve_public_file_path(parsed.path)

    return None


def _read_image_bytes_from_url(url: str) -> bytes:
    local_path = _local_public_path_from_url(url)
    if local_path is not None:
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


def _calculate_uncrop_extents(
    width: int,
    height: int,
    *,
    target_width: int = UNCROP_TARGET_WIDTH,
    target_height: int = UNCROP_TARGET_HEIGHT,
) -> tuple[int, int, int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive")
    target_width = max(target_width, width + (UNCROP_MIN_HORIZONTAL_MARGIN * 2))
    target_height = max(target_height, height + (UNCROP_MIN_VERTICAL_MARGIN * 2))

    horizontal_extend = target_width - width
    vertical_extend = target_height - height
    left = horizontal_extend // 2
    right = horizontal_extend - left
    up = vertical_extend // 2
    down = vertical_extend - up
    return left, right, up, down


def _select_magnific_scale_factor(width: int, height: int, *, target_max_side: int = UNCROP_PREPROCESS_TARGET_MAX_SIDE) -> Optional[int]:
    max_side = max(int(width or 0), int(height or 0))
    if max_side <= 0 or max_side >= target_max_side:
        return None
    for factor in MAGNIFIC_SCALE_FACTORS:
        if max_side * factor >= target_max_side:
            return factor
    return MAGNIFIC_SCALE_FACTORS[-1]


def _normalize_image_to_max_side(image: Image.Image, target_max_side: int) -> Image.Image:
    width, height = image.size
    max_side = max(width, height)
    if max_side <= 0 or max_side == target_max_side:
        return image.convert("RGB")
    scale = float(target_max_side) / float(max_side)
    next_size = (
        max(1, int(round(width * scale))),
        max(1, int(round(height * scale))),
    )
    return image.convert("RGB").resize(next_size, Image.Resampling.LANCZOS)


def _magnific_request_json(url: str, method: str, payload: Optional[dict] = None) -> dict:
    api_key = os.getenv("MAGNIFIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MAGNIFIC_API_KEY is not set")
    data = None
    headers = {"x-magnific-api-key": api_key}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Magnific upscale failed: HTTP {exc.code} {detail}") from exc


def _magnific_upscale_bytes(raw: bytes, *, scale_factor: int) -> bytes:
    encoded = base64.b64encode(raw).decode("ascii")
    payload = {
        "image": encoded,
        "scale_factor": f"{scale_factor}x",
        "optimized_for": "films_n_photography",
        "creativity": -2,
        "hdr": 1,
        "resemblance": 8,
        "fractality": 0,
        "engine": "automatic",
        "filter_nsfw": False,
    }
    created = _magnific_request_json("https://api.magnific.com/v1/ai/image-upscaler", "POST", payload)
    task_id = str((created.get("data") or {}).get("task_id") or "").strip()
    if not task_id:
        raise RuntimeError("Magnific upscale task id is missing")

    timeout_seconds = int(os.getenv("MAGNIFIC_TIMEOUT_SECONDS", "300") or "300")
    poll_interval = float(os.getenv("MAGNIFIC_POLL_INTERVAL_SECONDS", "5") or "5")
    started = time.time()
    while time.time() - started < timeout_seconds:
        status_payload = _magnific_request_json(
            f"https://api.magnific.com/v1/ai/image-upscaler/{task_id}",
            "GET",
        )
        data = status_payload.get("data") or {}
        status = str(data.get("status") or "").strip().upper()
        generated = data.get("generated") or []
        generated_url = str(generated[0] if generated else "").strip()
        if generated_url:
            return _download_remote_bytes(generated_url)
        if status in {"FAILED", "ERROR", "CANCELED", "CANCELLED"}:
            raise RuntimeError(f"Magnific upscale failed: {status}")
        time.sleep(max(1.0, poll_interval))

    raise RuntimeError("Magnific upscale timed out")


def _prepare_image_for_uncrop(source_image_url: str, *, country: str = "") -> tuple[str, dict]:
    raw = _read_image_bytes_from_url(source_image_url)
    with Image.open(BytesIO(raw)) as source_image:
        width, height = source_image.size
    scale_factor = _select_magnific_scale_factor(width, height)
    debug = {
        "input_url": str(source_image_url or "").strip(),
        "input_width": width,
        "input_height": height,
        "target_max_side": UNCROP_PREPROCESS_TARGET_MAX_SIDE,
        "upscaled": False,
        "normalized": False,
        "scale_factor": "",
        "output_url": str(source_image_url or "").strip(),
        "output_width": width,
        "output_height": height,
    }
    if scale_factor is None:
        if max(width, height) <= UNCROP_PREPROCESS_TARGET_MAX_SIDE:
            return str(source_image_url or "").strip(), debug
        source_hash = hashlib.sha256(raw).hexdigest()[:20]
        bucket = _normalize_image_country_bucket(country, fallback="other")
        file_name = f"normalized_{source_hash}_{UNCROP_PREPROCESS_TARGET_MAX_SIDE}.png"
        target_dir = UPSCALE_DIR / bucket
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / file_name
        output_url = f"/output/upscaled/{bucket}/{file_name}"
        if file_path.exists():
            with Image.open(file_path) as cached_image:
                out_width, out_height = cached_image.size
        else:
            with Image.open(BytesIO(raw)) as source_image:
                normalized_image = _normalize_image_to_max_side(source_image, UNCROP_PREPROCESS_TARGET_MAX_SIDE)
            normalized_image.save(file_path, format="PNG", optimize=True)
            out_width, out_height = normalized_image.size
        debug.update(
            {
                "normalized": True,
                "output_url": output_url,
                "output_width": out_width,
                "output_height": out_height,
            }
        )
        return output_url, debug

    source_hash = hashlib.sha256(raw).hexdigest()[:20]
    bucket = _normalize_image_country_bucket(country, fallback="other")
    file_name = f"magnific_{source_hash}_{scale_factor}x_{UNCROP_PREPROCESS_TARGET_MAX_SIDE}.png"
    target_dir = UPSCALE_DIR / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file_name
    output_url = f"/output/upscaled/{bucket}/{file_name}"
    if file_path.exists():
        with Image.open(file_path) as cached_image:
            out_width, out_height = cached_image.size
    else:
        upscaled_raw = _magnific_upscale_bytes(raw, scale_factor=scale_factor)
        with Image.open(BytesIO(upscaled_raw)) as upscaled_image:
            normalized_image = _normalize_image_to_max_side(upscaled_image, UNCROP_PREPROCESS_TARGET_MAX_SIDE)
        normalized_image.save(file_path, format="PNG", optimize=True)
        out_width, out_height = normalized_image.size
    debug.update(
        {
            "upscaled": True,
            "normalized": True,
            "scale_factor": f"{scale_factor}x",
            "output_url": output_url,
            "output_width": out_width,
            "output_height": out_height,
        }
    )
    return output_url, debug


def _is_cached_uncrop_current(image_url: str) -> bool:
    if not re.search(r"/uncrop/(?:[^/]+/)?uncrop_[0-9a-f]{20}_\d+_\d+_\d+_\d+\.png$", str(image_url or "").strip()):
        return False
    try:
        local_path = _resolve_public_file_path(image_url)
        if not local_path.exists():
            return False
        with Image.open(local_path) as cached_image:
            width, height = cached_image.size
            return width >= UNCROP_TARGET_WIDTH and height >= UNCROP_TARGET_HEIGHT
    except Exception:
        return False


def uncrop_image_with_clipdrop(source_image_url: str, *, country: str = "") -> str:
    clipdrop_key = os.getenv("CLIPDROP_API_KEY")
    if not clipdrop_key:
        raise RuntimeError("CLIPDROP_API_KEY is not set")

    raw = _read_image_bytes_from_url(source_image_url)
    with Image.open(BytesIO(raw)) as source_image:
        width, height = source_image.size
    extend_left, extend_right, extend_up, extend_down = _calculate_uncrop_extents(width, height)
    source_hash = hashlib.sha256(raw).hexdigest()[:20]
    _ensure_output_directories()
    file_name = f"uncrop_{source_hash}_{extend_left}_{extend_right}_{extend_up}_{extend_down}.png"
    bucket = _normalize_image_country_bucket(country, fallback="other")
    target_dir = UNCROP_DIR / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file_name
    if file_path.exists():
        return f"/output/uncrop/{bucket}/{file_name}"

    fields = [
        ("extend_left", str(extend_left)),
        ("extend_right", str(extend_right)),
        ("extend_up", str(extend_up)),
        ("extend_down", str(extend_down)),
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
    return f"/output/uncrop/{bucket}/{file_name}"


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
    target_dir = GENERATED_DIR / "uploaded"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file_name
    image.save(file_path, format="PNG", optimize=True)
    return f"/output/generated/uploaded/{file_name}"


def _save_uploaded_file_bytes(file_bytes: bytes, original_name: str = "") -> str:
    if not file_bytes:
        raise ValueError("Uploaded image is empty")

    image = Image.open(BytesIO(file_bytes)).convert("RGB")
    _ensure_output_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(original_name).stem if original_name else "upload"
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_") or "upload"
    file_name = f"{safe_stem}_{stamp}.png"
    target_dir = GENERATED_DIR / "uploaded"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file_name
    image.save(file_path, format="PNG", optimize=True)
    return f"/output/generated/uploaded/{file_name}"


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
        local_path = _resolve_public_file_path(path_str)
        # Safety: allow only project output files
        if not str(local_path).startswith(str(EPHEMERAL_OUTPUT_ROOT.resolve())):
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


def _scaled_font_size(size: int, scale: float = 1.0) -> int:
    return max(8, int(round(float(size) * float(scale or 1.0))))


def _resolve_banner_typography(language: str) -> dict:
    fonts_dir = ROOT / "assets" / "fonts"
    normalized = str(language or "general").strip().lower()
    default = {
        "headline_font_path": fonts_dir / "YangoGroupHeadline-Heavy.ttf",
        "text_bold_font_path": fonts_dir / "YangoGroupText-Bold.ttf",
        "text_regular_font_path": fonts_dir / "YangoGroupText-Regular.ttf",
        "font_scale": 1.0,
    }
    if normalized == "ethiopia":
        return {
            "headline_font_path": fonts_dir / "NotoSansEthiopic-ExtraCondensedExtraBold.ttf",
            "text_bold_font_path": fonts_dir / "NotoSansEthiopic-Bold.ttf",
            "text_regular_font_path": fonts_dir / "NotoSansEthiopic-Bold.ttf",
            "font_scale": 0.9,
        }
    if normalized == "nepal":
        return {
            "headline_font_path": fonts_dir / "NotoSansDevanagariUI-ExtraCondensedExtraBold.ttf",
            "text_bold_font_path": fonts_dir / "NotoSansDevanagari-Bold.ttf",
            "text_regular_font_path": fonts_dir / "NotoSansDevanagari-Bold.ttf",
            "font_scale": 0.9,
        }
    return default


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
    font_scale: float = 1.0,
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
    top_font_size = _scaled_font_size(int(round(spec["top_font_size"] * size_scale)), font_scale)
    bottom_font_size = _scaled_font_size(int(round(spec["bottom_font_size"] * size_scale)), font_scale)

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
        item["bbox"] = item_box
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
                    item["bbox"] = box
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
    if float(font_scale or 1.0) < 1.0:
        padding = max(padding, int(round(base_padding * 0.82)))
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
                "bbox": hi_box,
                "w": max(1, hi_box[2] - hi_box[0]),
                "h": max(1, hi_box[3] - hi_box[1]),
            }
        )

    stack_h_hi = sum(int(item["h"]) for item in lines_hi) + (gap_hi if len(lines_hi) > 1 else 0)
    cursor_y_hi = max(0, (badge_h_hi - stack_h_hi) // 2)
    for idx, item in enumerate(lines_hi):
        bbox = item.get("bbox", (0, 0, int(item["w"]), int(item["h"])))
        text_x_hi = max(0, (badge_w_hi - int(item["w"])) // 2)
        badge_draw_hi.text((text_x_hi - int(bbox[0]), cursor_y_hi - int(bbox[1])), item["text"], fill="#000000", font=item["font"])
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
    for block in blocks:
        raw_text = str(block.get("text", "") or "")
        if not raw_text.strip():
            continue
        font = block["font"]
        ratio = block["ratio"]
        wrap_width = block.get("wrap_width", width)
        text = _wrap_text_by_width(draw, raw_text, font, wrap_width)
        block_h = _measure_multiline_with_ratio(draw, text=text, font=font, line_height_ratio=ratio)
        gap_before = block.get("gap_before", 0) if prepared else 0
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
    local_path = _local_public_path_from_url(url)
    if local_path is not None:
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


def _clamp_image_rect_to_canvas(
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    canvas_w: int,
    canvas_h: int,
) -> tuple[int, int, int, int]:
    if w >= canvas_w:
        x = min(0, max(canvas_w - w, x))
    else:
        x = int(round((canvas_w - w) / 2))
    if h >= canvas_h:
        y = min(0, max(canvas_h - h, y))
    else:
        y = int(round((canvas_h - h) / 2))
    return x, y, w, h


def _render_master_banner_by_size(
    *,
    bg_image: Optional[Image.Image],
    size_key: str,
    layout_variant: str = "photo",
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
    banner_language: str = "general",
    brand: str = "yango",
) -> Image.Image:
    width, height = BANNER_SIZE_MAP[size_key]
    canvas = Image.new("RGBA", (width, height), "#d9d9d9")
    draw = ImageDraw.Draw(canvas, "RGBA")
    variant = str(layout_variant or "photo").strip().lower()
    logo_text = _brand_logo_text(brand)
    show_gradients = variant == "photo"
    main_text_fill = "#000000" if variant == "black" else "white"
    disclaimer_rgb = (0, 0, 0) if variant == "black" else (255, 255, 255)

    typography = _resolve_banner_typography(banner_language)
    headline_font_path = typography["headline_font_path"]
    headline_italic_font_path = ROOT / "assets" / "fonts" / "YangoGroupHeadline-HeavyItalic.ttf"
    text_bold_font_path = typography["text_bold_font_path"]
    text_regular_font_path = typography["text_regular_font_path"]
    banner_font_scale = float(typography.get("font_scale", 1.0) or 1.0)

    default_title_text = "Drive today\ncash in fast"
    default_subtitle_text = "Join Yango, earn quickly, and drive your future"
    default_disclaimer_text = (
        "Yango is an informational service and not a transportation or taxi services provider. "
        "Transportation services are provided by third parties."
    )
    title_text = title.strip() or default_title_text
    subtitle_text = subtitle.strip()
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
        img_x, img_y, img_w, img_h = _clamp_image_rect_to_canvas(
            x=img_x, y=img_y, w=img_w, h=img_h, canvas_w=width, canvas_h=height
        )
        if bg_image is not None:
            canvas.paste(_resize_exact(bg_image, img_w, img_h).convert("RGBA"), (img_x, img_y))
        if show_gradients:
            _draw_top_diagonal_gradient(canvas, height=368, align=align_mode)
            _draw_vertical_black_gradient(canvas, y=int(round(596.734)), height=int(round(603.266)), opacity=0.9)
            _draw_vertical_black_gradient(canvas, y=int(round(721.414)), height=int(round(478.586)), opacity=0.75)

        logo_font = _load_font(headline_italic_font_path, 113)
        title_font = _load_font(headline_font_path, _scaled_font_size(132, banner_font_scale))
        subtitle_font = _load_font(text_bold_font_path, _scaled_font_size(52, banner_font_scale))
        disclaimer_font = _load_font(text_regular_font_path, _scaled_font_size(16, banner_font_scale))
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
                font_scale=banner_font_scale,
                badge_fill_hex=accent_hex,
                shift_right_px=max(0, int(badge_shift_x or 0)),
                shift_up_px=max(0, int(badge_shift_y or 0)),
                y_shift=-badge_lift,
                target_bottom_y=badge_target_bottom_y,
            )

        logo_box = draw.textbbox((0, 0), logo_text, font=logo_font)
        logo_w = max(1, logo_box[2] - logo_box[0])
        if align_mode == "center":
            logo_x = (width - logo_w) // 2
        elif align_mode == "right":
            logo_x = width - 80 - logo_w
        else:
            logo_x = 80
        draw.text((logo_x, 80), logo_text, fill=main_text_fill, font=logo_font)
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
                    "fill": main_text_fill,
                    "gap_before": 0,
                    "wrap_width": 1033,
                    "align": align_mode,
                },
                {
                    "text": subtitle_text,
                    "font": subtitle_font,
                    "ratio": 1.1,
                    "fill": main_text_fill,
                    "gap_before": 48,
                    "wrap_width": 1033 if align_mode in {"center", "right"} else 1040,
                    "align": align_mode,
                },
                {
                    "text": disclaimer_text,
                    "font": disclaimer_font,
                    "ratio": 1.28,
                    "fill": (*disclaimer_rgb, 77),
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
        img_x, img_y, img_w, img_h = _clamp_image_rect_to_canvas(
            x=img_x, y=img_y, w=img_w, h=img_h, canvas_w=width, canvas_h=height
        )
        if bg_image is not None:
            canvas.paste(_resize_exact(bg_image, img_w, img_h).convert("RGBA"), (img_x, img_y))
        if show_gradients:
            _draw_top_diagonal_gradient(canvas, height=368, align=align_mode)
            _draw_vertical_black_gradient(canvas, y=int(round(height * 0.4973)), height=754, opacity=0.9)
            _draw_vertical_black_gradient(canvas, y=int(round(height * 0.6012)), height=598, opacity=0.75)

        logo_font = _load_font(headline_italic_font_path, 109)
        title_font = _load_font(headline_font_path, _scaled_font_size(132, banner_font_scale))
        subtitle_font = _load_font(text_bold_font_path, _scaled_font_size(52, banner_font_scale))
        disclaimer_font = _load_font(text_regular_font_path, _scaled_font_size(16, banner_font_scale))
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
                font_scale=banner_font_scale,
                badge_fill_hex=accent_hex,
                shift_right_px=max(0, int(badge_shift_x or 0)),
                shift_up_px=max(0, int(badge_shift_y or 0)),
                y_shift=-badge_lift,
                target_bottom_y=badge_target_bottom_y,
            )

        logo_box = draw.textbbox((0, 0), logo_text, font=logo_font)
        logo_w = max(1, logo_box[2] - logo_box[0])
        if align_mode == "center":
            logo_x = (width - logo_w) // 2
        elif align_mode == "right":
            logo_x = width - 80 - logo_w
        else:
            logo_x = 80
        draw.text((logo_x, 80), logo_text, fill=main_text_fill, font=logo_font)
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
                    "fill": main_text_fill,
                    "gap_before": 0,
                    "wrap_width": 1033,
                    "align": align_mode,
                },
                {
                    "text": subtitle_text,
                    "font": subtitle_font,
                    "ratio": 1.1,
                    "fill": main_text_fill,
                    "gap_before": 48,
                    "wrap_width": 1033 if align_mode in {"center", "right"} else 1040,
                    "align": align_mode,
                },
                {
                    "text": disclaimer_text,
                    "font": disclaimer_font,
                    "ratio": 1.28,
                    "fill": (*disclaimer_rgb, 77),
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
        img_x, img_y, img_w, img_h = _clamp_image_rect_to_canvas(
            x=img_x, y=img_y, w=img_w, h=img_h, canvas_w=width, canvas_h=height
        )
        if bg_image is not None:
            canvas.paste(_resize_exact(bg_image, img_w, img_h).convert("RGBA"), (img_x, img_y))
        if show_gradients:
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
                font_scale=banner_font_scale,
                badge_fill_hex=accent_hex,
                shift_right_px=max(0, int(badge_shift_x or 0)),
                shift_up_px=max(0, int(badge_shift_y or 0)),
            )

        logo_font = _load_font(headline_italic_font_path, 74)
        title_font = _load_font(headline_font_path, _scaled_font_size(112, banner_font_scale))
        subtitle_font = _load_font(text_bold_font_path, _scaled_font_size(40, banner_font_scale))
        disclaimer_font = _load_font(text_regular_font_path, _scaled_font_size(13, banner_font_scale))

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
                    "fill": main_text_fill,
                    "gap_before": 0,
                    "wrap_width": 636,
                    "align": top_align,
                },
                {
                    "text": subtitle_text,
                    "font": subtitle_font,
                    "ratio": 1.1,
                    "fill": main_text_fill,
                    "gap_before": 48,
                    "wrap_width": 636,
                    "align": top_align,
                },
            ],
            highlight_hex=accent_hex,
        )
        logo_box = draw.textbbox((0, 0), logo_text, font=logo_font)
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
        draw.text((logo_x, logo_y), logo_text, fill=main_text_fill, font=logo_font)
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
            fill=(*disclaimer_rgb, 128),
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
        img_x, img_y, img_w, img_h = _clamp_image_rect_to_canvas(
            x=img_x, y=img_y, w=img_w, h=img_h, canvas_w=width, canvas_h=height
        )
        if bg_image is not None:
            canvas.paste(_resize_exact(bg_image, img_w, img_h).convert("RGBA"), (img_x, img_y))
        if show_gradients:
            _draw_vertical_black_gradient(canvas, y=955, height=965, opacity=0.9)
            _draw_vertical_black_gradient(canvas, y=1154, height=766, opacity=0.75)

        logo_font = _load_font(headline_italic_font_path, 109)
        title_font = _load_font(headline_font_path, _scaled_font_size(132, banner_font_scale))
        subtitle_font = _load_font(text_bold_font_path, _scaled_font_size(52, banner_font_scale))
        disclaimer_font = _load_font(text_regular_font_path, _scaled_font_size(16, banner_font_scale))

        title_width = 920
        subtitle_width = 920
        disclaimer_width = 920
        has_subtitle = bool(subtitle_text.strip())
        title_wrapped = _wrap_text_by_width(draw, title_text.upper(), title_font, title_width)
        subtitle_wrapped = _wrap_text_by_width(draw, subtitle_text, subtitle_font, subtitle_width) if has_subtitle else ""
        disclaimer_wrapped = _wrap_text_by_width(draw, disclaimer_text, disclaimer_font, disclaimer_width)
        title_h = _measure_multiline_with_ratio(draw, text=title_wrapped, font=title_font, line_height_ratio=0.9)
        subtitle_h = (
            _measure_multiline_with_ratio(draw, text=subtitle_wrapped, font=subtitle_font, line_height_ratio=1.1)
            if has_subtitle
            else 0
        )
        disclaimer_h = _measure_multiline_with_ratio(draw, text=disclaimer_wrapped, font=disclaimer_font, line_height_ratio=1.28)
        logo_box = draw.textbbox((0, 0), logo_text, font=logo_font)
        logo_w = max(1, logo_box[2] - logo_box[0])
        logo_h = max(1, logo_box[3] - logo_box[1])

        gap_title_subtitle = 48
        gap_subtitle_logo = 80
        gap_logo_disclaimer = 150
        bottom_padding = 80
        total_h = (
            title_h
            + (gap_title_subtitle if has_subtitle else 0)
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
                font_scale=banner_font_scale,
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
            fill=main_text_fill,
            line_height_ratio=0.9,
            box_width=title_width,
            align="center" if align_mode == "center" else ("right" if align_mode == "right" else "left"),
            highlight_hex=accent_hex,
        )
        cursor_y += title_h
        if has_subtitle:
            cursor_y += gap_title_subtitle
            _draw_multiline_with_ratio(
                canvas,
                draw,
                x=80,
                y=int(cursor_y),
                text=subtitle_wrapped,
                font=subtitle_font,
                fill=main_text_fill,
                line_height_ratio=1.1,
                box_width=subtitle_width,
                align="center" if align_mode == "center" else ("right" if align_mode == "right" else "left"),
                highlight_hex=accent_hex,
            )
            cursor_y += subtitle_h
        cursor_y += gap_subtitle_logo
        if align_mode == "center":
            logo_x = (width - logo_w) // 2
        elif align_mode == "right":
            logo_x = width - 80 - logo_w
        else:
            logo_x = 80
        draw.text((logo_x, int(cursor_y)), logo_text, fill=main_text_fill, font=logo_font)
        cursor_y += logo_h + gap_logo_disclaimer
        _draw_multiline_with_ratio(
            canvas,
            draw,
            x=80,
            y=int(cursor_y),
            text=disclaimer_wrapped,
            font=disclaimer_font,
            fill=(*disclaimer_rgb, 77),
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
    banner_image_overrides: Optional[dict[tuple[int, str], dict]] = None,
    country: str = "",
    banner_source_url: str = "",
    brand: str = "yango",
) -> tuple[list[dict], str, str, dict]:
    _ensure_output_directories()

    source_image = None
    effective_image_url = str(image_url or "").strip()
    uncrop_warning = ""
    uncrop_debug = {
        "attempted": False,
        "used_cache": False,
        "source_kind": "",
        "input_url": effective_image_url,
        "preprocess": {},
        "output_url": "",
    }
    if image_url:
        cached_record = get_image_library_record(image_url)
        cached_banner_source_url = str(banner_source_url or "").strip()
        cached_country = ""
        if cached_record is not None:
            cached_banner_source_url = cached_banner_source_url or str(cached_record.get("banner_source_url", "")).strip()
            cached_country = str(cached_record.get("country", "")).strip()
        source_kind = str((cached_record or {}).get("kind") or _infer_library_kind_from_url(image_url)).strip()
        uncrop_debug["source_kind"] = source_kind
        if cached_record is None and source_kind == "uploaded":
            cached_record = _upsert_image_library_record(
                image_url,
                kind="uploaded",
                country="uploaded",
                original_name=Path(urlparse(image_url).path).name,
            )
        uncrop_country = "uploaded" if source_kind == "uploaded" else (country or cached_country or "other")
        try:
            prepared_image_url, preprocess_debug = _prepare_image_for_uncrop(image_url, country=uncrop_country)
            uncrop_debug["preprocess"] = preprocess_debug
            if (
                prepared_image_url == image_url
                and cached_banner_source_url
                and _is_cached_uncrop_current(cached_banner_source_url)
            ):
                effective_image_url = cached_banner_source_url
                uncrop_debug["used_cache"] = True
            else:
                uncrop_debug["attempted"] = True
                effective_image_url = uncrop_image_with_clipdrop(prepared_image_url, country=uncrop_country)
                update_image_library_banner_source(image_url, effective_image_url)
            uncrop_debug["output_url"] = effective_image_url
            source_image = _fetch_image_from_url(effective_image_url)
        except Exception as exc:
            # Safe fallback: keep banner generation available even if uncrop fails.
            uncrop_warning = str(exc) or "Clipdrop uncrop failed"
            effective_image_url = str(image_url).strip()
            uncrop_debug["output_url"] = effective_image_url
            source_image = _fetch_image_from_url(image_url)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    normalized_layout = (layout_type or "photo").strip().lower() or "photo"

    prepared_sets = list(text_sets or [])
    if not prepared_sets:
        prepared_sets = [{"title": "", "subtitle": "", "disclaimer": ""}]

    results: list[dict] = []
    for set_index, text_set in enumerate(prepared_sets):
        title = str((text_set or {}).get("title", "")).strip()
        subtitle = str((text_set or {}).get("subtitle", "")).strip()
        disclaimer = str((text_set or {}).get("disclaimer", "")).strip()
        text_align = _normalize_text_align(str((text_set or {}).get("textAlign", "left")))
        banner_language = str((text_set or {}).get("language", "general")).strip().lower() or "general"
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
            override = (banner_image_overrides or {}).get((set_index, size_key), {})
            render_image_scale = float(override.get("image_scale", image_scale))
            render_image_shift_x = int(override.get("image_shift_x", image_shift_x))
            render_image_shift_y = int(override.get("image_shift_y", image_shift_y))

            if normalized_layout not in {"photo", "black", "white"}:
                normalized_layout = "photo"
            banner = _render_master_banner_by_size(
                bg_image=source_image,
                size_key=size_key,
                layout_variant=normalized_layout,
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
                image_scale=render_image_scale,
                image_shift_x=render_image_shift_x,
                image_shift_y=render_image_shift_y,
                banner_language=banner_language,
                brand=brand,
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
    return results, effective_image_url, uncrop_warning, uncrop_debug


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def translate_path(self, path: str) -> str:
        parsed_path = urlparse(path).path
        if parsed_path.startswith("/output/"):
            return str(_resolve_public_file_path(parsed_path))
        return super().translate_path(path)

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
                    library_image = _upsert_image_library_record(
                        local_url,
                        kind="uploaded",
                        country="uploaded",
                        original_name=file_name,
                        label=Path(file_name).stem if file_name else "",
                    )
                    self._send_json(HTTPStatus.OK, {"image_local_url": local_url, "library_image": library_image})
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
                car_model = str(body.get("vehicleModel") or body.get("carModel", "")).strip()
                color_name = str(body.get("colorName", "")).strip()
                color_hex = str(body.get("colorHex", "")).strip()
                preferred_angle = str(body.get("preferredAngle", "")).strip()
                service = str(body.get("service", "Ride-hailing")).strip()
                style = str(body.get("style", "Photo")).strip()
                country = str(body.get("country", "")).strip()
                city = str(body.get("city", "")).strip()
                transport_label = str(body.get("transportLabel", "")).strip()
                transport_code = str(body.get("transportCode", "")).strip()
                basic_class = str(body.get("basicClass", "")).strip()
                vehicle_type = str(body.get("vehicleType", "car")).strip()
                composition = str(body.get("composition", "")).strip()
                model_description = str(body.get("modelDescription", "")).strip()
                face_reference_image_url = str(body.get("faceReferenceImageUrl", "")).strip()
                situation_description = str(body.get("situationDescription", "")).strip()
                if style.strip().lower() == "3d":
                    prompt_source = situation_description or model_description
                    if not prompt_source:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "description is required"})
                        return
                    prompt = generate_three_d_prompt_with_openai(prompt_source)
                    image_url, local_image_url = generate_three_d_image_with_gemini(prompt, country=country or "3d")
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "image_url": image_url,
                            "image_local_url": local_image_url,
                            "prompt": prompt,
                        },
                    )
                    return
                if style.strip().lower() in {"yango drive", "yango-drive", "drive"}:
                    if not car_model:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "vehicleModel is required"})
                        return
                    if not country:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "country is required"})
                        return
                    if not city:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "city is required"})
                        return
                    prompt = call_yango_drive_openai(
                        car_model,
                        color_name,
                        color_hex,
                        preferred_angle,
                        country=country,
                        city=city,
                    )
                    image_url, local_image_url = generate_image_with_recraft(prompt, country=country)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "image_url": image_url,
                            "image_local_url": local_image_url,
                            "prompt": prompt,
                            "brand": "yango-drive",
                        },
                    )
                    return
                if not car_model:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "vehicleModel is required"})
                    return
                if not country:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "country is required"})
                    return
                if not transport_label:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "transportLabel is required"})
                    return
                prompt = call_openai(
                    car_model,
                    color_name,
                    color_hex,
                    preferred_angle,
                    service=service,
                    style=style,
                    country=country,
                    transport_label=transport_label,
                    transport_code=transport_code,
                    basic_class=basic_class,
                    vehicle_type=vehicle_type,
                    composition=composition,
                    model_description=model_description,
                    face_reference_image_url=face_reference_image_url,
                    situation_description=situation_description,
                )
                if face_reference_image_url:
                    image_url, local_image_url = generate_image_with_openai_face_reference(
                        prompt,
                        face_reference_image_url,
                        country=country,
                    )
                else:
                    image_url, local_image_url = generate_image_with_openai(prompt, country=country)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "image_url": image_url,
                        "image_local_url": local_image_url,
                        "prompt": prompt,
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
                brand = _normalize_brand_key(str(body.get("brand", "yango-drive")).strip())
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
                    brand=brand,
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
                brand = _normalize_brand_key(str(body.get("brand", "yango-drive")).strip())
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
                remixed_video_url = remix_video_titles(base_video_url, headlines, brand=brand)
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
                library_image = _upsert_image_library_record(
                    local_url,
                    kind="uploaded",
                    country="uploaded",
                    original_name=file_name,
                    label=Path(file_name).stem if file_name else "",
                )
                self._send_json(HTTPStatus.OK, {"image_local_url": local_url, "library_image": library_image})
                return

            if self.path == "/api/regenerate-image":
                prompt = str(body.get("prompt", "")).strip()
                if not prompt:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "prompt is required"})
                    return
                image_url, local_image_url = generate_image_with_openai(prompt, country=str(body.get("country", "")).strip())
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
                reference_image_url = str(body.get("referenceImageUrl", "")).strip()
                aspect_ratio = str(body.get("aspectRatio", "")).strip()
                if not image_url:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "imageUrl is required"})
                    return
                if not edit_prompt:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "editPrompt is required"})
                    return
                edited_local_url = edit_image_with_gemini(
                    image_url,
                    edit_prompt,
                    reference_image_url,
                    aspect_ratio=aspect_ratio,
                    country=str(body.get("country", "")).strip(),
                )
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
            banner_source_url = str(body.get("bannerSourceUrl", "")).strip()
            country = str(body.get("country", "")).strip()
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
            layout_type = str(body.get("layoutType", "photo")).strip() or "photo"
            brand = _normalize_brand_key(str(body.get("brand", "yango")).strip())
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
            raw_banner_overrides = body.get("bannerImageOverrides", [])
            banner_image_overrides: dict[tuple[int, str], dict] = {}
            if isinstance(raw_banner_overrides, list):
                for raw_override in raw_banner_overrides:
                    if not isinstance(raw_override, dict):
                        continue
                    try:
                        override_set_index = int(raw_override.get("textSetIndex", raw_override.get("setIndex", 0)) or 0)
                    except (TypeError, ValueError):
                        continue
                    override_size = str(raw_override.get("size", "")).strip()
                    if override_set_index < 0 or override_size not in BANNER_SIZE_MAP:
                        continue
                    try:
                        override_scale = float(raw_override.get("imageScale", image_scale) or image_scale)
                    except (TypeError, ValueError):
                        override_scale = image_scale
                    if override_scale > 10:
                        override_scale = override_scale / 100.0
                    override_scale = max(1.0, min(1.5, override_scale))
                    try:
                        override_shift_x = int(raw_override.get("imageShiftX", image_shift_x) or 0)
                    except (TypeError, ValueError):
                        override_shift_x = image_shift_x
                    try:
                        override_shift_y = int(raw_override.get("imageShiftY", image_shift_y) or 0)
                    except (TypeError, ValueError):
                        override_shift_y = image_shift_y
                    banner_image_overrides[(override_set_index, override_size)] = {
                        "image_scale": override_scale,
                        "image_shift_x": override_shift_x,
                        "image_shift_y": override_shift_y,
                    }
            sizes = body.get("sizes", [])
            if not isinstance(sizes, list):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "sizes must be an array"})
                return
            if not image_url:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "imageUrl is required"})
                return

            banners, effective_image_url, uncrop_warning, uncrop_debug = render_banner_images(
                image_url=image_url,
                text_sets=text_sets,
                layout_type=layout_type,
                sizes=sizes,
                image_scale=image_scale,
                image_shift_x=image_shift_x,
                image_shift_y=image_shift_y,
                banner_image_overrides=banner_image_overrides,
                country=country,
                banner_source_url=banner_source_url,
                brand=brand,
            )
            if not banners:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "No supported sizes provided"})
                return
            source_record = get_image_library_record(image_url)
            source_kind = str((source_record or {}).get("kind") or _infer_library_kind_from_url(image_url)).strip()
            library_country = country or str((source_record or {}).get("country", "")).strip()
            if source_kind == "uploaded":
                library_country = "uploaded"
            elif not library_country:
                library_country = "other"
            persisted_image_url = _persist_image_for_library(image_url, country=library_country)
            banner_source_for_library = effective_image_url if _is_cached_uncrop_current(effective_image_url) else ""
            library_image = _upsert_image_library_record(
                persisted_image_url,
                kind=_infer_library_kind_from_url(persisted_image_url),
                banner_source_url=banner_source_for_library,
                country=library_country,
                original_name=Path(urlparse(persisted_image_url).path).name,
            )
            self._send_json(
                HTTPStatus.OK,
                {
                    "banners": banners,
                    "source_image_url": effective_image_url,
                    "uncrop_warning": uncrop_warning,
                    "uncrop_debug": uncrop_debug,
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
