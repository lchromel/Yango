import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)

CAR, COLOR = range(2)


def load_tokens_from_file() -> None:
    candidate_paths = [
        Path.home() / "Desktop" / "tokens.txt",
        Path(__file__).resolve().parent / "tokens.txt",
    ]

    try:
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
                    } and env_value:
                        os.environ.setdefault(env_key, env_value)
                    continue

                # Raw token fallback format.
                if line.startswith("sk-"):
                    os.environ.setdefault("OPENAI_API_KEY", line)
                elif ":" in line and len(line) > 20:
                    os.environ.setdefault("TELEGRAM_BOT_TOKEN", line)
    except Exception as exc:
        LOGGER.warning("Failed to load tokens from token files: %s", exc)


load_tokens_from_file()

CAMERA_ANGLES = [
    "extreme low-angle front 3/4 tracking shot, ultra-wide lens, near-wheel perspective, aggressive sense of speed",
    "very low rear 3/4 chase angle, ultra-wide cinematic lens, dramatic body distortion from perspective, hero scale",
    "ground-level side tracking shot, ultra-wide lens, camera almost touching the road, kinetic premium ad look",
    "off-center front quarter shot from inches above the surface, exaggerated wide-angle perspective, bold commercial framing",
    "sweeping low-angle pass-by shot, ultra-wide lens, dynamic foreground stretch, cinematic automotive hero energy",
    "front bumper-level tracking shot, super-wide lens, towering perspective, foreground asphalt stretching dramatically",
    "diagonal curbside angle from road edge, ultra-wide lens, strong leading lines, exaggerated motion perspective",
    "high-to-low descending drone-like angle, wide cinematic lens, dramatic subject isolation with deep environmental context",
    "rear quarter launch shot from just above the pavement, super-wide lens, intense vanishing lines, forceful ad composition",
    "tight near-fender perspective, ultra-wide lens, bodywork dominating the frame, aggressive cinematic distortion",
]

LIGHTING_STYLES = [
    "clear early-morning sunlight, crisp shadows, clean reflective highlights, premium Fujifilm GFX100 realism",
    "clean late-morning commercial daylight, sculpted reflections on bodywork, controlled contrast, crisp Fujifilm GFX100 clarity",
    "bright midday sun with hard-edged shadows, hot reflective highlights, dry premium realism",
    "soft late-afternoon daylight before sunset, balanced contrast, precise highlights, atmospheric Fujifilm polish",
    "cool blue-hour ambient light with sharp practical highlights, premium contrast, atmospheric cinematic realism",
    "early-evening city glow before full night, reflective building light, moody contrast, expensive Fujifilm finish",
]

SHOT_PACING = [
    "frozen split-second hero frame with sharp car detail and environmental motion around it",
    "high-energy rolling shot with strong directional flow and premium ad precision",
    "controlled cinematic glide with a poised commercial feel and rich environmental depth",
    "explosive action frame with dynamic momentum and dramatic spatial separation",
]

COMPOSITION_STYLES = [
    "bold asymmetrical framing with strong negative space and exaggerated foreground",
    "deep leading lines pulling the eye into the car, with layered background depth",
    "hero-centered composition with architectural or terrain lines guiding attention into the subject",
    "off-balance ad composition with dramatic perspective stretch and cinematic scale",
]

DUBAI_BASELINE = (
    "Use Dubai as the default world reference for every scene: premium UAE roads, warm sun, slight atmospheric haze, "
    "clean modern architecture, refined landscaping, pale concrete, glossy glass, desert light, upscale visual tone. "
    "Even when the user gives a short location, interpret it through realistic Dubai surroundings unless they explicitly name another place. "
    "Roads, pavement, and driving surfaces should look dry, clean, and warm-weather realistic, never rain-soaked."
)


@dataclass
class PromptRequest:
    car: str
    color: str
    location_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    vehicle_profile: Optional[str] = None
    car_with_year: Optional[str] = None
    preferred_angle: Optional[str] = None
    preferred_angle_label: Optional[str] = None


def get_car_descriptor(request: PromptRequest) -> str:
    return (request.car_with_year or request.car).strip()


def infer_vehicle_profile_from_keywords(request: PromptRequest) -> str:
    car_name = request.car.lower()

    offroad_keywords = {
        "patrol", "land cruiser", "defender", "wrangler", "bronco", "g class",
        "g-class", "gwagon", "g wagon", "prado", "jimny", "hilux", "ranger",
        "raptor", "pickup", "pickup truck", "tahoe", "suburban", "yukon",
    }
    premium_keywords = {
        "rolls", "bentley", "maybach", "s class", "s-class", "7 series", "range rover",
        "cullinan", "ghost", "phantom", "continental", "flying spur", "escalade",
    }
    sports_keywords = {
        "911", "porsche", "ferrari", "lamborghini", "mclaren", "amg gt", "r8",
        "gtr", "gt-r", "nismo", "supra", "m4", "m3", "rs3", "rs6", "huracan",
        "aventador", "urus", "corvette", "camaro", "mustang",
    }
    suv_keywords = {
        "x5", "x6", "x7", "q7", "q8", "gle", "gls", "cayenne", "model x",
        "xc90", "suv", "crossover", "sportage", "sorento", "cx-9", "cx9",
    }

    if any(keyword in car_name for keyword in offroad_keywords):
        return "offroad"
    if any(keyword in car_name for keyword in premium_keywords):
        return "premium"
    if any(keyword in car_name for keyword in sports_keywords):
        return "sports"
    if any(keyword in car_name for keyword in suv_keywords):
        return "suv"
    return "urban"


def infer_vehicle_profile(request: PromptRequest) -> str:
    if request.vehicle_profile in {"offroad", "premium", "sports", "suv", "urban"}:
        return request.vehicle_profile
    return infer_vehicle_profile_from_keywords(request)


def infer_vehicle_location_strategy(request: PromptRequest) -> str:
    profile = infer_vehicle_profile(request)

    if profile == "offroad":
        return (
            "a UAE off-road hero setting, favoring Dubai desert dunes, Al Qudra tracks, or the rocky desert roads toward Ras Al Khaimah, "
            "with terrain that suits capable 4x4 vehicles"
        )
    if profile == "premium":
        return (
            "an elite Dubai luxury setting, favoring Palm Jumeirah villas, Jumeirah beachfront drives, Dubai Marina drop-offs, "
            "or high-end residential boulevards"
        )
    if profile == "sports":
        return (
            "a high-impact Dubai performance setting, favoring Sheikh Zayed Road style city canyons, Dubai Marina boulevards, "
            "tunnel runs, or sleek waterfront roads with premium skyline presence"
        )
    if profile == "suv":
        return (
            "a premium UAE grand touring setting, favoring wide Dubai boulevards, upscale suburban roads, resort arrivals, "
            "or scenic mountain roads toward Ras Al Khaimah"
        )
    return (
        "a polished Dubai business-district setting, favoring office towers, financial center streets, corporate drop-off lanes, "
        "and clean commercial boulevards"
    )


def build_location_description(request: PromptRequest) -> str:
    strategy = infer_vehicle_location_strategy(request)

    if request.location_text and request.latitude is not None and request.longitude is not None:
        return (
            f"{request.location_text}, guided by {strategy}, matching the real-world terrain and architecture near "
            f"{request.latitude:.6f}, {request.longitude:.6f}"
        )

    if request.location_text:
        return (
            f"{request.location_text}, interpreted through {strategy}, with authentic environmental details of that place"
        )

    if request.latitude is not None and request.longitude is not None:
        return (
            f"the exact real-world surroundings near {request.latitude:.6f}, {request.longitude:.6f}, guided by {strategy}, "
            "with realistic terrain, roads, and local atmosphere"
        )

    return f"{strategy}, rendered as a realistic premium UAE location with cinematic depth"


def infer_scene_anchor(request: PromptRequest) -> str:
    haystack = " ".join(
        value.lower()
        for value in [request.location_text or "", request.car, request.color]
        if value
    )
    profile = infer_vehicle_profile(request)

    if any(keyword in haystack for keyword in {"beach", "sea", "coast", "shore", "jbr", "palm"}):
        return (
            "warm-toned asphalt or pale stone paving directly under the car, low concrete curb, a short strip of light sand beside the roadside, "
            "trimmed palm trunks entering the edge of frame, fragments of upscale beachfront facades, a narrow slice of calm Gulf water only as a background accent, "
            "bright sunlit sky with warm marine haze"
        )

    if any(keyword in haystack for keyword in {"dubai", "uae", "abu dhabi", "marina"}):
        return (
            "clean sunlit asphalt with visible lane texture, pale concrete curb close to frame, cropped beige or white facade sections, "
            "window bands, balcony edges, trimmed palm trunks, heat-softened background, clean blue sky with light haze"
        )

    if any(keyword in haystack for keyword in {"desert", "dune", "sand", "safari"}):
        return (
            "packed sand or a hard desert track under the tires, rippled golden dunes nearby, scattered stones, layered dust in the air, "
            "distant dark rocky ridgelines typical of UAE desert landscapes, bright sun-washed sky with warm haze"
        )

    if profile == "offroad":
        return (
            "packed sand, a hard desert trail, or rugged mountain-edge tarmac under the tires, wind-shaped dunes or rocky slopes nearby, "
            "layered dust in the air, sparse desert vegetation, distant Ras Al Khaimah style ridgelines, harsh clean UAE sunlight"
        )

    if profile == "premium":
        return (
            "smooth premium asphalt or luxury driveway paving, pale stone curbs, manicured palms, cropped white or beige facade planes, "
            "glass railings, entrance recesses, shadow lines across the wall, warm polished Dubai light"
        )

    if profile == "sports":
        return (
            "clean grippy asphalt with visible lane texture, sharp painted lines, sculpted curbs, cropped glossy glass surfaces or sleek retaining walls, "
            "tight architectural reflections, dramatic vanishing lines, compressed city depth without a dominant skyline"
        )

    if profile == "suv":
        return (
            "wide clean roadway or premium hillside road surface, pale curbs, resort-grade landscaping, cropped modern facade sections, "
            "structured shadows, open UAE sky, and a composed upscale touring atmosphere"
        )

    if any(keyword in haystack for keyword in {"tunnel", "underpass", "underground"}):
        return (
            "smooth marked roadway, repeating wall panels, linear ceiling lights, reflective concrete surfaces, "
            "curving lane lines, compressed vanishing point in the background"
        )

    if any(keyword in haystack for keyword in {"villa", "mansion", "compound", "residence", "palm"}):
        return (
            "smooth driveway or premium pavement, clean architectural walls close behind the car, minimalist landscaping, sculpted hedges or palms, "
            "sunlit facade details, door frames, window recesses, and tight upscale residential background"
        )

    if any(keyword in haystack for keyword in {"city", "street", "downtown", "avenue", "urban"}):
        return (
            "detailed asphalt texture, painted lane markings, curbs and sidewalks, cropped storefront glass or facade panels, "
            "street furniture, wall edges, and tight background layers rather than a wide skyline"
        )

    if profile == "urban":
        return (
            "clean office-district asphalt, pale curbs, polished glass and stone office facade sections, shaded corporate entrances, neat planters, "
            "structured sidewalks, door frames, column edges, reflected geometry, bright Dubai business-day light"
        )

    return (
        "a clearly drivable Dubai-style surface with visible ground texture, pale curbs or roadside concrete, refined local facade details, "
        "tight background depth, warm clear sky with light haze, and physically consistent surroundings"
    )


def infer_environment_fx(request: PromptRequest) -> str:
    haystack = " ".join(
        value.lower()
        for value in [request.location_text or "", request.car, request.color]
        if value
    )
    desert_keywords = {"desert", "dune", "sand", "safari"}
    tunnel_keywords = {"tunnel", "underground", "underpass"}
    city_keywords = {"city", "downtown", "street", "marina", "mall", "avenue"}
    villa_keywords = {"villa", "mansion", "residence", "compound", "palm"}
    profile = infer_vehicle_profile(request)

    if any(keyword in haystack for keyword in desert_keywords):
        return (
            "thick sand exploding from the rear wheels, airborne dust trails, textured dunes, heat haze, "
            "high-grip drift energy, realistic granular motion"
        )

    if profile == "offroad":
        return (
            "sand or fine dust reacting violently to wheel torque, textured terrain breakup, subtle stone scatter, "
            "dry heat haze, and forceful off-road momentum"
        )

    if any(keyword in haystack for keyword in tunnel_keywords):
        return (
            "streaking reflections across glossy paint, repeating tunnel lights, subtle tire haze, speed-driven motion blur "
            "only in the environment, clean sharp car details"
        )

    if profile == "premium":
        return (
            "clean architectural reflections, subtle warm air shimmer, polished surfaces, premium stillness with elegant motion, "
            "luxury campaign atmosphere"
        )

    if profile == "sports":
        return (
            "fast-moving reflections, controlled road haze, sharp light streaks, dynamic environmental compression, "
            "high-speed performance ad energy"
        )

    if any(keyword in haystack for keyword in city_keywords):
        return (
            "reflections from glass and concrete, compressed urban atmosphere, premium campaign energy, "
            "controlled motion with believable speed"
        )

    if profile == "urban":
        return (
            "clean reflections from office glass and polished concrete, subtle city air shimmer, restrained movement, "
            "high-end corporate district atmosphere"
        )

    if any(keyword in haystack for keyword in villa_keywords):
        return (
            "clean architectural reflections, warm air, sunlit premium lifestyle atmosphere"
        )

    return (
        "realistic environmental motion, cinematic atmosphere, and physically believable surface interaction"
    )


def pick_action(request: PromptRequest) -> str:
    haystack = " ".join(
        value.lower()
        for value in [request.location_text or "", request.car, request.color]
        if value
    )
    desert_keywords = {"desert", "dune", "sand", "safari"}
    city_keywords = {"city", "downtown", "street", "marina", "mall", "avenue"}
    profile = infer_vehicle_profile(request)

    if any(keyword in haystack for keyword in desert_keywords):
        return "high-speed drift through sand, dramatic dust plume, wheels turned aggressively"

    if profile == "offroad":
        return "confident off-road charge, suspension loaded, dust and sand trailing behind, rugged hero movement"

    if profile == "premium":
        return "slow composed roll-in, refined stance, understated movement, luxury flagship ad energy"

    if profile == "sports":
        return "high-speed tracking run, aggressive corner entry, planted stance, precision performance hero energy"

    if any(keyword in haystack for keyword in city_keywords):
        return "slow premium roll-by, composed stance, subtle wheel motion, luxury ad energy"

    if profile == "urban":
        return "clean executive roll-by, subtle motion, composed stance, sharp office-district commercial ad energy"

    return "dynamic cornering shot, controlled speed, confident hero movement"


def build_prompt(request: PromptRequest) -> str:
    location_description = build_location_description(request)
    scene_anchor = infer_scene_anchor(request)
    action = pick_action(request)
    environment_fx = infer_environment_fx(request)
    camera_angle = request.preferred_angle.strip() if request.preferred_angle else random.choice(CAMERA_ANGLES)
    lighting_style = random.choice(LIGHTING_STYLES)
    shot_pacing = random.choice(SHOT_PACING)
    composition_style = random.choice(COMPOSITION_STYLES)

    return "\n".join(
        [
            "Prompt Structure",
            "",
            "FORMAT + MEDIUM",
            (
                '"Ultra-realistic cinematic automotive advertisement frame for Nano Banana 2, '
                'high-end Fujifilm GFX100 commercial photography, premium action still, vertical 9:16"'
            ),
            "",
            "SUBJECT",
            f'"a {request.color.strip()} {get_car_descriptor(request)} as the hero vehicle, clean body lines, premium spec"',
            "",
            "CAMERA + FRAMING",
            f'"{camera_angle}, {composition_style}, {shot_pacing}, full cinematic framing, close enough to exaggerate scale, crisp hero focus, 9:16 composition"',
            "",
            "SCENE + SETTING",
            (
                f'"set in {location_description}, grounded in realistic Dubai visual language, cinematic road context, believable environment, strong sense of place, '
                f'{environment_fx}, visible scene details at close photographic scale: {scene_anchor}, clearly visible lane markings or road guidance lines aligned with vehicle direction"'
            ),
            "",
            "MICRO-DETAILS",
            (
                '"sharp reflections on paint, realistic tire tread, detailed rims, subtle dust particles, '
                'defined panel gaps, clear glass reflections, natural surface texture, high realism, '
                'painted lane-line texture with slight wear and crisp edges"'
            ),
            "",
            "EXPRESSION + ACTION",
            f'"{action}, visually powerful hero shot, premium automotive campaign mood"',
            "",
            "LIGHTING",
            f'"{lighting_style}, natural highlights on bodywork, realistic shadows, cinematic atmosphere"',
            "",
            "NEGATIVE CUES",
            (
                '"no cartoon look, no CGI feel, no safe boring angle, no extra vehicles stealing focus, no warped wheels, '
                'no deformed body panels, no fake reflections, no text, no watermark, no blurred main subject, '
                'no car floating, no car standing in water, no impossible terrain contact, no puddles, no wet asphalt, '
                'no rainwater, no standing water on the road"'
            ),
        ]
    )


def build_openai_input(request: PromptRequest) -> str:
    location_parts = []
    if request.location_text:
        location_parts.append(f"text location: {request.location_text}")
    if request.latitude is not None and request.longitude is not None:
        location_parts.append(
            f"coordinates: {request.latitude:.6f}, {request.longitude:.6f}"
        )

    location_line = "; ".join(location_parts) if location_parts else "location not provided"
    return (
        "Create one detailed structured image prompt for Nano Banana 2.\n"
        "The image should match a premium realistic automotive commercial aesthetic: cinematic, expensive, believable, "
        "like luxury car advertising, with dynamic movement when appropriate.\n"
        f"{DUBAI_BASELINE}\n"
        "Use this exact section format and section order:\n"
        "Prompt Structure\n"
        "FORMAT + MEDIUM\n"
        "SUBJECT\n"
        "CAMERA + FRAMING\n"
        "SCENE + SETTING\n"
        "MICRO-DETAILS\n"
        "EXPRESSION + ACTION\n"
        "LIGHTING\n"
        "NEGATIVE CUES\n\n"
        "Requirements:\n"
        "- Output only the final prompt text, no explanations.\n"
        "- Keep it concise but richly visual.\n"
        "- Make it highly specific and usable as a direct generation prompt.\n"
        "- Always include the car with the latest body-year format in the prompt (example: Porsche Macan 2024), not just the model name alone.\n"
        "- Always use Fujifilm GFX100 camera language in the visual setup.\n"
        "- The visual language should feel like premium Fujifilm GFX100 automotive photography: crisp, dimensional, refined, high-end, and natural rather than synthetic.\n"
        "- Anchor the scene in recognizable Dubai visual logic by default: UAE road finishes, clean premium streets, warm sun, desert haze, Gulf coastline, palms, modern villas or towers when context fits.\n"
        "- Choose the exact Dubai/UAE sub-location based on the vehicle type when the user gives a broad or generic location.\n"
        "- Premium luxury cars should gravitate toward Palm Jumeirah, Jumeirah beachfront roads, Dubai Marina arrivals, luxury villas, and elite boulevards.\n"
        "- Sports cars should gravitate toward dramatic city corridors, waterfront boulevards, tunnels, skyline roads, and high-impact premium urban routes.\n"
        "- Off-road vehicles and capable 4x4s should gravitate toward desert dunes, Al Qudra, rugged desert tracks, or mountain roads toward Ras Al Khaimah.\n"
        "- SUVs and grand touring vehicles should gravitate toward wide upscale boulevards, premium suburban roads, resorts, or scenic UAE roads.\n"
        "- Regular non-premium everyday cars should gravitate toward clean Dubai office districts, corporate streets, business parks, and polished commercial building zones.\n"
        "- Prioritize realistic physics, believable reflections, correct proportions, premium ad look.\n"
        "- Infer the best environment and action from the user data.\n"
        "- First imagine the correct Dubai setting internally, then describe only what the camera actually sees in the shot, as if captioning a finished photo.\n"
        "- Expand short locations into concrete visible scene details at close photographic scale, not broad regional descriptions.\n"
        "- Do not stop at generic labels like 'Dubai street' or 'beach road'; explicitly describe the surface under the car, curb edges, wall materials, facade sections, window bands, columns, shadows, nearby vegetation, and only small visible slices of distant background.\n"
        "- Favor cropped architectural details over full buildings, and facade fragments over skyline panoramas.\n"
        "- Keep the background local and physically close to the car. Avoid describing entire districts, giant towers in full, or wide panoramic city views unless the framing explicitly requires it.\n"
        "- For Dubai beach or sea-adjacent scenes, keep the car on a coastal road, promenade lane, paved pull-off, or dry sand access area near the beach, not inside the water.\n"
        "- Be specific about what is around the car: road material, ground texture, nearby objects, horizon, architecture, terrain, and atmosphere.\n"
        "- Always include visible road markings (lane lines, edge lines, arrows, or guidance paint appropriate to the road type) and ensure they align with car heading.\n"
        "- The car must always be on a clearly drivable physical surface such as asphalt, concrete, packed sand, gravel, or a road shoulder.\n"
        "- Never place the car in the sea, in deep water, floating, or on an impossible surface unless the user explicitly asks for that.\n"
        "- Roads and pavement must always be dry: no puddles, no wet road, no rain residue, no reflective water patches.\n"
        "- For the initial image generation, avoid the wet-road advertising trope entirely: no glossy rain sheen, no mirror-like wet asphalt, no fresh-rain pavement.\n"
        "- Make the camera angle unusual, bold, and commercially powerful. Avoid generic eye-level views.\n"
        "- Prefer super-wide or ultra-wide cinematic lens language, low angles, chase angles, near-ground perspectives, and striking compositions.\n"
        "- Vary the framing, camera placement, movement style, and composition every time so the result does not feel repetitive.\n"
        "- If user provides a preferred camera angle, prioritize it while keeping the shot dynamic and cinematic.\n"
        "- Preferred angle must be followed strictly. Do not switch to another angle family.\n"
        "- Enforce angle consistency between SUBJECT and CAMERA + FRAMING.\n"
        "- If preferred angle is Rear 3/4, show clear rear-corner dominance with visible rear fascia and side plane; do not output a pure side profile.\n"
        "- If preferred angle is Front 3/4, show clear front-corner dominance with visible front fascia and side plane; do not output a pure side profile.\n"
        "- If preferred angle is Clean Side Profile, keep true side profile and avoid 3/4 corner dominance.\n"
        "- Enforce geometric consistency across sections: FORMAT + MEDIUM, CAMERA + FRAMING, and EXPRESSION + ACTION must describe one coherent shot style.\n"
        "- Vehicle heading must align with road direction and lane perspective in normal road scenes; do not place the car sideways across lanes unless explicit drift/off-road behavior is requested.\n"
        "- Lane markings must run in perspective consistent with vehicle travel direction; avoid center lines visually perpendicular to car heading in non-intersection scenes.\n"
        "- For side-tracking shots, describe camera moving parallel to the car path, with car orientation matching lane flow.\n"
        "- Do not mix contradictory camera instructions (for example static close-up vs high-speed chase) in the same prompt.\n"
        "- Do not use sunset or orange golden-hour lighting. Prefer early morning, late morning, midday, late afternoon before sunset, or blue-hour / early evening light.\n"
        "- Build atmosphere from the environment: in desert scenes include realistic sand spray and dust plumes from the wheels; in tunnels use light streaks and reflections; in city scenes use rich reflections and premium urban mood.\n"
        "- Wheel dust or sand plumes must appear only when terrain supports it (desert, dusty shoulders, gravel, off-road surfaces). Avoid dust trails on clean city asphalt or polished driveways.\n"
        "- Make the image feel like a standout automotive ad, not a plain catalog shot.\n"
        "- If the location suggests desert, dunes, city streets, villas, highways, or tunnels, lean into that naturally.\n"
        "- Keep the main subject strictly the car.\n\n"
        f"User data:\nCar: {get_car_descriptor(request)}\nColor: {request.color}\nLocation: {location_line}\nPreferred angle label: {request.preferred_angle_label or 'auto'}\nPreferred angle instructions: {request.preferred_angle or 'auto'}"
    )


def generate_prompt_with_openai(request: PromptRequest) -> str:
    if OpenAI is None:
        raise RuntimeError("OpenAI package is not installed.")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You write structured prompts for image generation systems. "
                    "Your task is to produce polished, high-performance prompts for realistic automotive visuals. "
                    "Every result must feel like a striking premium car advertisement with unusual camera placement, "
                    "cinematic atmosphere, and physically believable environmental interaction. "
                    "By default, ground every scene in realistic Dubai and UAE visual language unless the user explicitly requests another city or country. "
                    "Choose more specific Dubai or UAE sub-locations based on the vehicle class so the setting feels naturally matched to the car. "
                    "For ordinary non-premium cars, prefer polished office districts and corporate streets instead of generic residential roads. "
                    "Inject noticeable variation into shot design, perspective, and composition from one response to the next. "
                    "Use premium Fujifilm GFX100 visual language, avoid sunset and golden-hour orange light, and keep all roads dry with no puddles or wet surfaces. "
                    "Primary generation must never depict rain-soaked asphalt, glossy wet-road sheen, reflective water patches, or a fresh-rain look. "
                    "Use wheel dust/sand plumes only when terrain logically supports it (desert, gravel, dusty off-road), and avoid dust trails on clean city roads. "
                    "Always include the vehicle with latest body-year naming (e.g., Porsche Macan 2024) in the final prompt. "
                    "Maintain strict geometric consistency: car heading aligned with lane direction in normal road scenes, "
                    "camera direction coherent with motion, and no contradictory framing instructions. "
                    "Never place the car sideways across the road unless explicit drift/off-road action is requested. "
                    "Always include visible road markings or guidance lines appropriate to the road type, and align them with the lane perspective. "
                    "If a preferred angle is provided, follow it exactly and do not drift to a different angle family (for example rear 3/4 must not become clean side profile). "
                    "Think of the place first, then describe the frame like a photographer describing what is literally visible nearby, with close architectural details and local surfaces instead of broad skyline descriptions."
                ),
            },
            {
                "role": "user",
                "content": build_openai_input(request),
            },
        ],
    )

    prompt = (response.output_text or "").strip()
    if not prompt:
        raise RuntimeError("OpenAI returned an empty response.")

    if is_low_detail_prompt(prompt):
        LOGGER.info("OpenAI returned low-detail prompt, running refinement pass.")
        refined = refine_prompt_with_openai(client=client, model=model, draft=prompt, request=request)
        if refined and not is_low_detail_prompt(refined):
            return refined

        LOGGER.warning("Refinement still low-detail, using structured fallback template.")
        return build_prompt(request)

    return prompt


def is_low_detail_prompt(text: str) -> bool:
    normalized = text.lower()
    words = re.findall(r"\b[\w-]+\b", normalized)
    if len(words) < 180:
        return True

    generic_markers = [
        "close-up shot",
        "high-resolution image",
        "urban dubai street setting",
        "static, parked",
        "digital photograph, high-resolution image",
    ]
    if any(marker in normalized for marker in generic_markers):
        return True

    required_sections = [
        "FORMAT + MEDIUM",
        "SUBJECT",
        "CAMERA + FRAMING",
        "SCENE + SETTING",
        "MICRO-DETAILS",
        "EXPRESSION + ACTION",
        "LIGHTING",
        "NEGATIVE CUES",
    ]
    for section in required_sections:
        if section.lower() not in normalized:
            return True

    return False


def refine_prompt_with_openai(client: OpenAI, model: str, draft: str, request: PromptRequest) -> str:
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You rewrite weak automotive prompts into elite ad-grade prompts. "
                    "Output only the rewritten prompt.\n"
                    "Hard requirements:\n"
                    "- Keep section order exactly: PROMPT STRUCTURE, FORMAT + MEDIUM, SUBJECT, CAMERA + FRAMING, "
                    "SCENE + SETTING, MICRO-DETAILS, EXPRESSION + ACTION, LIGHTING, NEGATIVE CUES.\n"
                    "- Remove generic or flat phrasing.\n"
                    "- Make camera dynamic and non-static (near-ground chase, diagonal energy, motion cues).\n"
                    "- SCENE + SETTING and MICRO-DETAILS must be deeply specific and photographic, with close visible architecture/material details.\n"
                    "- Dubai realism, dry roads, no puddles, no sunset/golden-hour orange.\n"
                    "- Always use Fujifilm GFX100 camera language.\n"
                    "- Dust/sand plumes only when terrain is dusty (desert, gravel, off-road), never on clean urban roads.\n"
                    "- Keep motion geometry coherent: vehicle heading follows lane direction, camera movement matches shot type, and no sideways-across-road placement in standard road scenes.\n"
                    "- Respect requested camera angle exactly; do not rewrite rear/front 3/4 into side profile unless explicitly requested.\n"
                    "- Ensure visible road markings/guidance lines are present and perspective-consistent.\n"
                    "- Remove contradictory camera statements across sections.\n"
                    "- Do not include car color hex codes.\n"
                ),
            },
            {
                "role": "user",
                "content": (
                    "Rewrite this prompt into a richer version with stronger dynamic composition and environmental detail.\n\n"
                    f"Car: {request.car}\nColor: {request.color}\nPreferred angle label: {request.preferred_angle_label or 'auto'}\nPreferred angle instructions: {request.preferred_angle or 'auto'}\n\n"
                    f"Draft prompt:\n{draft}"
                ),
            },
        ],
    )
    return (response.output_text or "").strip()


def classify_vehicle_profile_with_openai(request: PromptRequest) -> str:
    if OpenAI is None:
        raise RuntimeError("OpenAI package is not installed.")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "Classify the vehicle into exactly one category for automotive advertising scene selection. "
                    "Allowed labels only: offroad, premium, sports, suv, urban. "
                    "Return only one label and nothing else."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Vehicle: {request.car}\n"
                    "Rules:\n"
                    "- offroad: rugged 4x4s, pickups, off-road focused SUVs\n"
                    "- premium: flagship luxury sedans and ultra-luxury SUVs\n"
                    "- sports: sports cars, performance coupes/sedans, supercars, muscle cars\n"
                    "- suv: premium family SUVs, crossovers, grand touring SUVs\n"
                    "- urban: ordinary everyday cars, regular sedans, hatchbacks, compact cars\n"
                ),
            },
        ],
    )
    profile = (response.output_text or "").strip().lower()
    if profile not in {"offroad", "premium", "sports", "suv", "urban"}:
        raise RuntimeError(f"Unexpected vehicle profile from OpenAI: {profile!r}")
    return profile


def infer_car_with_year_with_openai(request: PromptRequest) -> str:
    if OpenAI is None:
        raise RuntimeError("OpenAI package is not installed.")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You normalize car model names for automotive prompts. "
                    "Return only one line in this exact style: '<Brand Model> <latest_body_year>'. "
                    "Example: 'Porsche Macan 2024'. "
                    "Do not add any extra words."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Vehicle: {request.car}\n"
                    "Task: determine the latest body/facelift generation year and append it."
                ),
            },
        ],
    )
    value = (response.output_text or "").strip()
    # Basic sanity: at least one 4-digit year in the output.
    if not re.search(r"\b(19|20)\d{2}\b", value):
        raise RuntimeError(f"Unexpected vehicle-year format from OpenAI: {value!r}")
    return value


async def enrich_vehicle_profile(request: PromptRequest) -> PromptRequest:
    try:
        request.car_with_year = await asyncio.to_thread(infer_car_with_year_with_openai, request)
    except Exception as exc:
        LOGGER.warning("OpenAI car year enrichment failed, using original model: %s", exc)
        request.car_with_year = request.car

    try:
        profile = await asyncio.to_thread(classify_vehicle_profile_with_openai, request)
        request.vehicle_profile = profile
    except Exception as exc:
        fallback_profile = infer_vehicle_profile_from_keywords(request)
        LOGGER.warning(
            "OpenAI vehicle classification failed, using keyword fallback: %s", exc
        )
        request.vehicle_profile = fallback_profile
    return request


async def build_final_prompt(request: PromptRequest) -> tuple[str, bool]:
    request = await enrich_vehicle_profile(request)
    try:
        prompt = await asyncio.to_thread(generate_prompt_with_openai, request)
        return prompt, True
    except Exception as exc:
        LOGGER.warning("OpenAI prompt generation failed, using fallback template: %s", exc)
        return build_prompt(request), False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Напиши марку и модель машины. Пример: Nissan Patrol или Audi RS3."
    )
    return CAR


async def collect_car(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["car"] = update.message.text.strip()
    await update.message.reply_text("Теперь укажи цвет машины.")
    return COLOR


async def collect_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    request = PromptRequest(
        car=context.user_data["car"],
        color=update.message.text.strip(),
    )
    prompt, from_openai = await build_final_prompt(request)
    source_note = "" if from_openai else "\n\n(OpenAI недоступен, использован локальный шаблон.)"
    await update.message.reply_text(
        "Готово. Ниже структурированный промт для Nano Banana 2:\n\n"
        f"{prompt}{source_note}",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Диалог остановлен. Запусти /start, чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def build_application():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Environment variable TELEGRAM_BOT_TOKEN is required.")

    application = ApplicationBuilder().token(token).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_car)],
            COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_color)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conversation)
    application.add_handler(CommandHandler("cancel", cancel))
    return application


def main() -> None:
    application = build_application()
    LOGGER.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
