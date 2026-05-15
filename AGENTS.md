# Yango Perf Project Map

This file is for future Codex sessions. Read it first to understand the project quickly.

## Important Local Rule

- Tokens for all skills and local runs are stored in `~/Desktop/tokens.txt`.
- When a token is needed, use values from `~/Desktop/tokens.txt` first.
- If a token is missing or invalid, report it and ask for clarification.
- Do not commit token files. `tokens.txt` and `output/` are ignored by git.

## What This Project Is

Yango Perf is a small Python + static frontend tool for generating performance marketing assets:

- AI image prompts and images for Yango ride-hailing visuals.
- Yango Drive car-rental automotive visuals.
- 3D red-background object renders.
- Image edits through Gemini / Nano Banana style models.
- Banner rendering in several paid-social sizes.
- Image-to-video generation through official BytePlus ModelArk Seedance API, then local title/logo/packshot composition with ffmpeg.
- A separate Telegram bot that generates Nano Banana 2 car prompts.

There is no frontend build step. `index.html`, `styles.css`, and `app.js` are served directly by `web_app.py`.

## Main Files

- `web_app.py`: main web server and almost all backend logic. It serves static files, exposes JSON APIs, calls OpenAI/Gemini/Recraft/Kling/Clipdrop/Magnific, stores generated assets, renders banners with Pillow, and composes video overlays with ffmpeg.
- `app.js`: all browser-side state, UI rendering, uploads, API calls, image/banner/video workflows.
- `index.html`: static app shell with tabs for `Image`, `Banners`, and `Video`.
- `styles.css`: complete app styling.
- `bot.py`: Telegram conversation bot and shared prompt helpers for car prompt generation. `web_app.py` imports `PromptRequest`, vehicle classification, and prompt helpers from here.
- `assets/data/vehicles.json`: country/tariff/vehicle data used by the frontend for ride-hailing country and transport selectors.
- `assets/fonts/`: Yango and locale-specific fonts used for banner rendering.
- `assets/logos/`: Yango, Yango Drive, Yango Pro, Yandex GO logo/icon assets.
- `assets/branding/`: country/language visual branding references used by prompt generation.
- `assets/style-references/3d/`: reference images for the 3D object style.
- `assets/video/packshot.mp4`: appended to composed videos.
- `output/`: generated files, archives, uploaded media, thumbnails, videos, uncrops, and upscales. Ignored by git.
- `Dockerfile` and `railway.toml`: Railway deployment.
- `requirements.txt`: Python deps: `python-telegram-bot`, `openai`, `Pillow`.

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the web app:

```bash
python3 web_app.py
```

Default URL:

```text
http://127.0.0.1:8080
```

Optional port override:

```bash
PORT=8081 python3 web_app.py
```

Run the Telegram bot:

```bash
python3 bot.py
```

## Environment Variables

The app tries to load these from `~/Desktop/tokens.txt` first, then from local `tokens.txt` as fallback. Environment variables already set in the shell win because the loader uses `os.environ.setdefault`.

Core:

- `HOST`: web bind host, default `0.0.0.0`.
- `PORT`: web port, default `8080`.
- `YANGO_DATA_DIR`: persistent data root override.
- `RAILWAY_VOLUME_MOUNT_PATH`: Railway volume root; used if `YANGO_DATA_DIR` is absent.
- `WEB_APP_BASIC_AUTH_USERNAME`
- `WEB_APP_BASIC_AUTH_PASSWORD`

AI/image:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`, default `gpt-4.1-mini`.
- `OPENAI_IMAGE_MODEL`, default `gpt-image-2`.
- `OPENAI_IMAGE_SIZE`, default `1536x1024`.
- `OPENAI_IMAGE_QUALITY`, default `high`.
- `OPENAI_IMAGE_TIMEOUT_SECONDS`, default `480`.
- `GEMINI_API_KEY`
- `GEMINI_MODEL`, default `gemini-3.1-flash-image-preview`.
- `GEMINI_3D_ASPECT_RATIO`, default `4:3`.
- `RECRAFT_API_TOKEN` or `RECRAFT_API_KEY`.
- `RECRAFT_MODEL`, default `recraftv4`.
- `CLIPDROP_API_KEY`, needed for banner uncrop.
- `MAGNIFIC_API_KEY`, optional upscale before uncrop.
- `MAGNIFIC_TIMEOUT_SECONDS`, default `300`.
- `MAGNIFIC_POLL_INTERVAL_SECONDS`, default `5`.

Video:

- `ARK_API_KEY`, required for official BytePlus ModelArk Seedance API.
- `BYTEPLUS_ARK_API_KEY`, `BYTEPLUS_API_KEY`, or `SEEDANCE_API_KEY`, accepted as fallback key names.
- `BYTEPLUS_ARK_BASE_URL`, default `https://ark.ap-southeast.bytepluses.com/api/v3`.
- `SEEDANCE_MODEL`, default `dreamina-seedance-2-0-260128`.
- `SEEDANCE_DURATION`, default `10`; clamped to `4` through `15`.
- `SEEDANCE_RESOLUTION`, default `720p`; supports `480p`, `720p`, or `1080p`.
- `SEEDANCE_GENERATE_AUDIO`, default `true`.
- `SEEDANCE_TIMEOUT_SECONDS`, default `600`.
- `SEEDANCE_POLL_INTERVAL_SECONDS`, default `5`.
- `KLING_ACCESS_KEY`, legacy unused fallback.
- `KLING_SECRET_KEY`, legacy unused fallback.

Telegram:

- `TELEGRAM_BOT_TOKEN`

## Output And Persistence

At startup, `web_app.py` computes:

- `ROOT`: repo root.
- `DATA_ROOT`: `YANGO_DATA_DIR`, else `RAILWAY_VOLUME_MOUNT_PATH`, else `/app/data` if present, else repo root.
- `PERSISTENT_OUTPUT_ROOT`: `DATA_ROOT/output` when `DATA_ROOT != ROOT`, otherwise `ROOT/output`.
- `EPHEMERAL_OUTPUT_ROOT`: always `ROOT/output`.

Generated images are normally saved under `output/generated/<bucket>/`.

Image library metadata:

- `PERSISTENT_OUTPUT_ROOT/image_library.json`
- stores generated/uploaded image records and cached uncrop source URLs.

Video library metadata:

- `EPHEMERAL_OUTPUT_ROOT/video_library.json`
- stores uploaded/generated videos and base video references.

Public `/output/...` URLs are resolved through `Handler.translate_path()` and `_resolve_public_file_path()`, so backend-generated local URLs can be served as static files.

## Web API Routes

GET:

- `/health`: returns `{"status": "ok"}` and bypasses basic auth.
- `/api/library-images`: returns stored image library records.
- `/api/library-videos`: returns stored video library records.

POST:

- `/api/generate-image`: main image generation route. Branches by service/style:
  - Ride-hailing Photo: OpenAI prompt via `call_openai()`, image via OpenAI Images.
  - Ride-hailing 3D: OpenAI prompt via `generate_three_d_prompt_with_openai()`, image via Gemini.
  - Yango Drive: OpenAI prompt via `call_yango_drive_openai()`, image via Recraft.
- `/api/regenerate-image`: generates a new OpenAI image from an edited prompt.
- `/api/edit-image`: Gemini image edit from source image and edit prompt.
- `/api/upload-image`: accepts multipart `image` or JSON `imageData`, stores it, adds to image library.
- `/api/render-banners`: uncrops source image if needed, then renders banner PNGs.
- `/api/create-banners-zip`: zips rendered banner URLs.
- `/api/delete-library-image`: removes an image record from the library.
- `/api/generate-video-prompt`: creates a Seedance 2.0 prompt from the selected/generated image.
- `/api/generate-video`: submits image-to-video to official BytePlus ModelArk Seedance API, saves raw video, composes titles/logo/packshot.
- `/api/remix-video`: recomposes titles/logo/packshot on a saved base video.
- `/api/upload-video`: stores uploaded video and adds it to the video library.
- `/api/delete-library-video`: removes a video record from the library.

## Frontend Flow

`app.js` keeps one large `state` object. Important fields:

- `activeTab`: `image`, `banner`, or `video`.
- `selectedService`: `ride-hailing` or `yango-drive`.
- `selectedImageStyle`: `photo`, `3d`, or `edit`.
- `selectedCountry`, `selectedTransportLabel`, `selectedComposition`: ride-hailing controls.
- `driveCountry`, `driveCity`, `selectedCarModel`, `customCarModel`, `colorLabel`, `selectedAngle`, `driveWish`: Yango Drive controls.
- `imageUrl`, `bannerSourceImageUrl`, `basePromptText`, `editPromptText`: generated or selected image state.
- `imageLibrary`, `videoLibrary`: loaded from backend.
- `bannerLayout`, `bannerBrand`, `bannerLogoVariant`, `bannerTextSets`, `bannerImageOverrides`: banner rendering state.
- `videoPromptText`, `videoHeadlines`, `videoBrand`, `videoResultUrl`: video state.

Key frontend functions:

- `fetchVehicleData()`: loads `assets/data/vehicles.json`.
- `fetchImageLibrary()` / `fetchVideoLibrary()`: load saved assets.
- `generatePrompt()`: validates UI and posts `/api/generate-image`.
- `generateEditedSourceImage()`: edit-mode cleanup through `/api/edit-image`.
- `buildRenderPayload()`: constructs `/api/render-banners` payload.
- `createBanners()`: calls `/api/render-banners`.
- `generateVideoPrompt()` and `generateVideoFromPrompt()`: video prompt/Kling flows.
- `renderUiState()`: central re-render and control visibility update.

## Banner Rendering Notes

Banner sizes are defined in `BANNER_SIZE_MAP` in `web_app.py` and mirrored in `BANNER_SIZES` in `app.js`:

- `1200x1200`
- `1200x1350`
- `1200x1500`
- `1200x628`
- `1080x1920`

Backend render path:

1. `/api/render-banners` parses text sets, layout, brand, logo variant, sizes, image scale/shift, and per-size overrides.
2. `render_banner_images()` fetches/caches an uncropped source image.
3. `_prepare_image_for_uncrop()` may normalize/upscale through Magnific before Clipdrop.
4. `uncrop_image_with_clipdrop()` expands to `3200x2472` target.
5. `_render_master_banner_by_size()` chooses between standard and frame layouts.
6. PNGs are saved to `output/banners/`.

Supported layout families:

- Standard: `photo`, `black`, `white`.
- Frame variants: `frame`, `frame-red`, `frame-black`, `frame-white`.

Supported brands:

- `yango`
- `yango-drive`
- `yandex-go`
- `yango-pro`

Yandex GO logo variants:

- `en`
- `ar`
- `ge`
- `en-ar`
- `ru`

## Video Notes

`generate_video_with_seedance()`:

1. Builds BytePlus Ark auth from `ARK_API_KEY`, `BYTEPLUS_ARK_API_KEY`, or `SEEDANCE_API_KEY`.
2. Submits Seedance image-to-video to `https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks`.
3. Polls `GET /api/v3/contents/generations/tasks/{task_id}` until the response contains a video URL or timeout.
4. Saves raw video to `output/videos/`.
5. Calls `_compose_video_with_titles_and_packshot()`.

Video composition uses ffmpeg/ffprobe:

- Adds headline segments over the base video.
- Overlays brand logo.
- Appends the first 2 seconds of `assets/video/packshot.mp4` when available.
- Saves final video under `output/videos/`.

Video prompts are written specifically for Seedance 2.0 image-to-video:

- Start with `@Image1 as the main visual reference and first frame.`
- Treat the selected/generated image as the first-frame identity reference.
- Use a dynamic 10-second automotive commercial structure: `0-2s`, `2-4s`, `4-6s`, `6-8s`, `8-10s`.
- Include varied city-driving angles: low front tracking, side tracking, wheel macro, detail montage, and final hero reveal/orbit.
- Include subject setup, environment, action/motion, camera movement, timing, transitions, sound, and style.
- Preserve car identity, paint, proportions, wheels, road contact, and lighting consistency.
- Avoid realistic human faces, readable text, UI overlays, random logos, watermarks, and car morphing.

Docker installs `ffmpeg`; local machine also needs ffmpeg available for video rendering.

## Telegram Bot Notes

`bot.py` is a simple two-step conversation:

- `/start` asks for car make/model.
- Next message stores car.
- Next message stores color.
- Bot returns a detailed automotive prompt.
- `/cancel` exits the conversation.

OpenAI enhancement is attempted when `OPENAI_API_KEY` is available:

- infer latest car/body-year naming.
- classify vehicle profile.
- refine the final prompt.

If OpenAI fails, local keyword/template fallbacks keep the bot usable.

## Deployment

Railway uses:

- `Dockerfile`: Python 3.11 slim, installs ffmpeg and requirements, runs `python web_app.py`.
- `railway.toml`: Dockerfile builder, `/health` healthcheck, restart on failure.

For Railway production, set secrets as Railway env vars. Do not rely on local token files in production.

If a Railway Volume is mounted, use `/app/output` or `RAILWAY_VOLUME_MOUNT_PATH` so generated images and image library metadata persist. Without a volume, `output/` is ephemeral.

## Common Change Pointers

- Add or change API behavior: start in `Handler.do_POST()` in `web_app.py`, then update matching caller in `app.js`.
- Change image prompt rules: edit `SUPER_APP_VISUAL_GUIDE`, `THREE_D_VISUAL_GUIDE`, `call_openai()`, `call_yango_drive_openai()`, or `bot.py` prompt helpers.
- Change Yango Drive countries/cities: edit `DRIVE_COUNTRY_CITY_OPTIONS` in `app.js`; backend location guidance is `_drive_location_guide()` in `web_app.py`.
- Change ride-hailing countries/tariffs: edit `assets/data/vehicles.json`.
- Change banner sizes: update both `BANNER_SIZE_MAP` in `web_app.py` and `BANNER_SIZES` / active-size arrays in `app.js`.
- Change banner typography/layout: look around `_resolve_banner_typography()`, `_render_master_banner_by_size()`, `_render_figma_brand_banner_by_size()`, and related draw helpers in `web_app.py`.
- Change logos/brand options: update brand constants in both `web_app.py` and `app.js`, plus assets in `assets/logos/`.
- Change video title behavior: edit `_headline_segments()`, `_build_title_overlay_filters()`, `_build_logo_overlay_filter()`, and `_compose_video_with_titles_and_packshot()` in `web_app.py`.
- Change upload/library behavior: edit image/video library helpers near the top of `web_app.py` and library rendering functions in `app.js`.

## Quick Sanity Checks

Run the server:

```bash
python3 web_app.py
```

Healthcheck:

```bash
curl -i http://127.0.0.1:8080/health
```

Basic static app check:

```bash
curl -i http://127.0.0.1:8080/
```

Git status:

```bash
git status --short
```

There is no dedicated test suite yet. For UI changes, start the server and manually verify the affected tab/workflow in the browser.
