const VEHICLE_DATA_URL = "./assets/data/vehicles.json";
const IMAGE_SERVICE = "Ride-hailing";
const IMAGE_STYLES = [
  { label: "Photo", value: "photo" },
  { label: "Edit", value: "edit" },
];
const IMAGE_REQUEST_TIMEOUT_MS = 8 * 60 * 1000;
const EDIT_CLEANUP_PROMPT = [
  "убери текстовый блок, логотип и дисклеймер обрежь все лишнее чтобы суть была крупно по центру изображения и заполняло все пространство",
].join(" ");
const COMPOSITION_PRESETS = [
  { label: "inside the car", vehicleTypes: ["car"] },
  { label: "near the car", vehicleTypes: ["car"] },
  { label: "getting into the car", vehicleTypes: ["car"] },
  { label: "passenger with driver", vehicleTypes: ["car"] },
  { label: "window", vehicleTypes: ["car"] },
  { label: "near the moto", vehicleTypes: ["moto"] },
  { label: "passenger with driver", vehicleTypes: ["moto"] },
  { label: "driver", vehicleTypes: ["moto"] },
  { label: "near the tuk tuk", vehicleTypes: ["tuktuk"] },
  { label: "inside tuk tuk", vehicleTypes: ["tuktuk"] },
  { label: "driver", vehicleTypes: ["tuktuk"] },
];

const BANNER_LAYOUTS = [
  { label: "Photo", value: "photo", disabled: false },
  { label: "Black", value: "black", disabled: false },
  { label: "White", value: "white", disabled: false },
];
const TEXT_ALIGN_OPTIONS = [
  { value: "left", icon: "./assets/icons/text-align-left.svg", alt: "Align left" },
  { value: "center", icon: "./assets/icons/text-align-center.svg", alt: "Align center" },
  { value: "right", icon: "./assets/icons/text-align-right.svg", alt: "Align right" },
];

const BANNER_SIZES = [
  { value: "1200x1200", slotClass: "slot-1200x1200" },
  { value: "1200x628", slotClass: "slot-1200x628" },
  { value: "1080x1920", slotClass: "slot-1080x1920" },
  { value: "1200x1350", slotClass: "slot-1200x1350" },
];
const BANNER_SIZE_LABELS = BANNER_SIZES.reduce((acc, item) => {
  acc[item.value] = item.value;
  return acc;
}, {});
const BRANDING_REFERENCES = {
  amharic: "./assets/branding/amharic.png",
  azerbaijani: "./assets/branding/azerbaijani.png",
  english: "./assets/branding/english.png",
  french: "./assets/branding/french.png",
  "oman-female": "./assets/branding/oman-female.png",
  oman: "./assets/branding/oman.png",
  portuguese: "./assets/branding/portuguese.png",
  spanish: "./assets/branding/spanish.png",
};
const COUNTRY_BRANDING_REFERENCE = {
  Angola: "portuguese",
  Azerbaijan: "azerbaijani",
  Benin: "french",
  Bolivia: "spanish",
  Botswana: "english",
  Cameroon: "french",
  Colombia: "spanish",
  "DR of the Congo": "french",
  Ethiopia: "amharic",
  Ghana: "english",
  Guatemala: "spanish",
  Israel: "english",
  "Ivory Coast": "french",
  Morocco: "french",
  Mozambique: "portuguese",
  Namibia: "english",
  Nepal: "english",
  Oman: "oman",
  Pakistan: "english",
  Peru: "spanish",
  "Saudi Arabia": "english",
  Senegal: "french",
  Venezuela: "spanish",
  Zambia: "english",
};
const BUSINESS_CLASS_KEYWORDS = ["business", "premier", "elite"];

const IMAGE_SHIFT_STEP_COUNT = 4;
const IMAGE_SHIFT_MAX_PX = 150;
const IMAGE_SHIFT_ONE_STEP_PX = IMAGE_SHIFT_MAX_PX / IMAGE_SHIFT_STEP_COUNT;
const IMAGE_SCALE_MIN = 100;
const IMAGE_SCALE_MAX = 150;
const IMAGE_SCALE_STEP = 3;
const BANNER_AUTO_RENDER_DEBOUNCE_MS = 550;
const CUSTOM_ACCENT_TRIGGER_WINDOW_MS = 550;
const CUSTOM_ACCENT_TRIGGER_TAP_COUNT = 3;
const VIDEO_TAB_ENABLED = false;
const ACCENT_PRESET_VALUES = {
  lime: "#E3FF74",
  red: "#FF1A1A",
};

const state = {
  vehicleData: [],
  vehicleDataLoading: false,
  vehicleDataError: "",
  selectedImageStyle: "photo",
  styleMenuOpen: false,
  selectedCountry: "",
  selectedTransportLabel: "",
  countryMenuOpen: false,
  transportMenuOpen: false,
  selectedComposition: "",
  heroDescription: "",
  situationDescription: "",
  basePromptText: "",
  editPromptText: "",
  editSourceImageUrl: "",
  editSourceStatus: "none",
  imageHistory: [],
  imageLibrary: [],
  sourceLibraryCountry: "",
  sourceLibraryCountryMenuOpen: false,
  imageUrl: "",
  bannerSourceImageUrl: "",
  videoPromptText: "",
  videoLibrary: [],
  videoLibraryOpen: false,
  videoGenerating: false,
  videoRendering: false,
  videoRenderStatus: "No video yet.",
  videoResultUrl: "",
  videoHeadlines: [
    "Drive with comfort every day",
    "",
    "",
  ],
  generating: false,
  activeTab: "image",
  sourceLibraryOpen: false,
  bannerLayout: "photo",
  bannerAccentPreset: "lime",
  bannerAccentCustomColor: ACCENT_PRESET_VALUES.lime,
  bannerTextSets: [
    {
      title: "Drive with comfort every day",
      subtitle: "Book your car in seconds and enjoy premium routes.",
      disclaimer: "Terms and conditions apply",
      textAlign: "left",
      badgeEnabled: false,
      badgeTopText: "From",
      badgeBottomText: "65 AED",
      badgeShiftX: 0,
      badgeShiftY: 0,
    },
  ],
  bannerStage: "idle",
  bannerRendering: false,
  hasRenderedBanners: false,
  renderedBanners: [],
  imageScalePercent: 100,
  imageShiftXStep: 0,
  imageShiftYStep: 0,
  activeBannerPositionKey: "",
  bannerImageOverrides: {},
};

async function fetchWithTimeout(url, options = {}, timeoutMs = IMAGE_REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      ...options,
      signal: options.signal || controller.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Request timed out. GPT Image can take several minutes, please try again.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function humanizeError(error, fallback = "Something went wrong. Please try again.") {
  const rawMessage =
    typeof error === "string"
      ? error
      : String(error?.message || error?.error || fallback || "").trim();
  const normalized = rawMessage.toLowerCase();

  if (normalized.includes("moderation_blocked") || normalized.includes("rejected by the safety system")) {
    return [
      "The request was blocked by the image safety system.",
      "Try rephrasing the description in a more neutral way and avoid subjective descriptions of people, sensitive traits, or risky situations.",
    ].join("\n\n");
  }

  if (normalized.includes("failed to fetch")) {
    return [
      "The app could not reach the server.",
      "Please check the connection and try again. If it keeps happening, the server may be restarting or the request may have timed out.",
    ].join("\n\n");
  }

  if (normalized.includes("request timed out") || normalized.includes("timed out")) {
    return "The request took too long and timed out. Image generation can take several minutes, so please try again.";
  }

  if (normalized.includes("clipdrop uncrop failed")) {
    return "The image expansion step failed. Please try again, or use another source image if this keeps happening.";
  }

  if (normalized === "render failed" || normalized.includes("banner generation failed")) {
    return fallback || "Banner generation failed. Please try again.";
  }

  if (normalized === "edit failed") {
    return fallback || "Image editing failed. Please try again.";
  }

  if (normalized === "upload failed") {
    return fallback || "Upload failed. Please try another file.";
  }

  if (normalized === "generation failed") {
    return fallback || "Image generation failed. Please try again.";
  }

  if (normalized.includes("openai_image") || normalized.includes("openai") || normalized.includes("image generation")) {
    return "Image generation failed. Please try simplifying the prompt or generating again.";
  }

  if (normalized.includes("imageurl is required")) {
    return "Please generate or upload an image first.";
  }

  if (normalized.includes("sizes must be an array") || normalized.includes("no supported sizes")) {
    return "Banner sizes were not prepared correctly. Please refresh the page and try again.";
  }

  return rawMessage || fallback;
}

function showError(error, fallback) {
  console.error(error);
  alert(humanizeError(error, fallback));
}

const SOURCE_STATUS = {
  none: "STATUS",
  uploading: "UPLOADING",
  uploaded: "ATTACHED",
  generated: "GENERATED",
  failed: "FAILED",
};

const tabImageEl = document.getElementById("tabImage");
const tabBannerEl = document.getElementById("tabBanner");
const tabVideoEl = document.getElementById("tabVideo");
const imageTabPanelEl = document.getElementById("imageTabPanel");
const bannerTabPanelEl = document.getElementById("bannerTabPanel");
const videoTabPanelEl = document.getElementById("videoTabPanel");
const imageCanvasEl = document.getElementById("imageCanvas");
const bannerCanvasEl = document.getElementById("bannerCanvas");
const videoCanvasEl = document.getElementById("videoCanvas");

const countryToggleEl = document.getElementById("countryToggle");
const countryDisplayEl = document.getElementById("countryDisplay");
const countryChevronIconEl = document.getElementById("countryChevronIcon");
const countryMenuEl = document.getElementById("countryMenu");
const styleToggleEl = document.getElementById("styleToggle");
const styleDisplayEl = document.getElementById("styleDisplay");
const styleChevronIconEl = document.getElementById("styleChevronIcon");
const styleMenuEl = document.getElementById("styleMenu");
const transportToggleEl = document.getElementById("transportToggle");
const transportDisplayEl = document.getElementById("transportDisplay");
const transportChevronIconEl = document.getElementById("transportChevronIcon");
const transportMenuEl = document.getElementById("transportMenu");
const compositionSectionEl = document.getElementById("compositionSection");
const compositionRowEl = document.getElementById("compositionRow");
const heroDescriptionInputEl = document.getElementById("heroDescriptionInput");
const situationDescriptionInputEl = document.getElementById("situationDescriptionInput");
const bannerAccentColorInput = document.getElementById("bannerAccentColorInput");
const generateBtn = document.getElementById("generateBtn");
const photoStyleOnlyEls = Array.from(document.querySelectorAll(".photo-style-only"));
const editSourceSectionEl = document.getElementById("editSourceSection");
const editUploadImageBtnEl = document.getElementById("editUploadImageBtn");
const editUploadImageInputEl = document.getElementById("editUploadImageInput");
const editSourceStatusEl = document.getElementById("editSourceStatus");
const editSelectedSourceBoxEl = document.getElementById("editSelectedSourceBox");
const editSelectedSourcePreviewEl = document.getElementById("editSelectedSourcePreview");
const editClearSourceBtnEl = document.getElementById("editClearSourceBtn");

const loaderEl = document.getElementById("loader");
const loaderLabelEl = document.getElementById("loaderLabel");
const imagePreviewFrameEl = document.getElementById("imagePreviewFrame");
const resultImageEl = document.getElementById("resultImage");
const promptInputEl = document.getElementById("promptInput");
const promptBackBtn = document.getElementById("promptBackBtn");
const promptApplyBtn = document.getElementById("promptApplyBtn");
const promptRowEl = document.querySelector(".prompt-row");
const quickActionRowEl = document.getElementById("quickActionRow");
const seatbeltActionBtn = document.getElementById("seatbeltActionBtn");
const brandingActionBtn = document.getElementById("brandingActionBtn");
const removeBackgroundPeopleActionBtn = document.getElementById("removeBackgroundPeopleActionBtn");
const topActionBtn = document.getElementById("topActionBtn");

const uploadImageInputEl = document.getElementById("uploadImageInput");
const uploadImageBtnEl = document.getElementById("uploadImageBtn");
const uploadImageStatusEl = document.getElementById("uploadImageStatus");
const videoSourceStatusEl = document.getElementById("videoSourceStatus");
const selectedSourceBoxEl = document.getElementById("selectedSourceBox");
const selectedSourcePreviewEl = document.getElementById("selectedSourcePreview");
const clearSourceBtnEl = document.getElementById("clearSourceBtn");
const sourceLibraryEl = document.getElementById("sourceLibrary");
const sourceLibraryToggleEl = document.getElementById("sourceLibraryToggle");
const sourceLibraryChevronEl = document.getElementById("sourceLibraryChevron");
const layoutTypeRowEl = document.getElementById("layoutTypeRow");
const imageScaleEl = document.getElementById("imageScale");
const imageShiftXEl = document.getElementById("imageShiftX");
const imageShiftYEl = document.getElementById("imageShiftY");
const imageShiftScopeEl = document.getElementById("imageShiftScope");
const useGlobalShiftBtnEl = document.getElementById("useGlobalShiftBtn");
const resetBannerShiftBtnEl = document.getElementById("resetBannerShiftBtn");
const textSetsWrapEl = document.getElementById("textSetsWrap");
const addTextSetBtn = document.getElementById("addTextSetBtn");
const renderBannersBtn = document.getElementById("renderBannersBtn");
const bannerSetsViewEl = document.getElementById("bannerSetsView");
const generateVideoBtnEl = document.getElementById("generateVideoBtn");
const videoRenderStatusEl = document.getElementById("videoRenderStatus");
const videoResultWrapEl = document.getElementById("videoResultWrap");
const videoResultPlayerEl = document.getElementById("videoResultPlayer");
const videoDownloadLinkEl = document.getElementById("videoDownloadLink");
const videoEmptyStateEl = document.getElementById("videoEmptyState");
const videoLibraryEl = document.getElementById("videoLibrary");
const videoLibraryToggleEl = document.getElementById("videoLibraryToggle");
const videoLibraryChevronEl = document.getElementById("videoLibraryChevron");
const uploadVideoBtnEl = document.getElementById("uploadVideoBtn");
const uploadVideoInputEl = document.getElementById("uploadVideoInput");
const videoHeadline1El = document.getElementById("videoHeadline1");
const videoHeadline2El = document.getElementById("videoHeadline2");
const videoHeadline3El = document.getElementById("videoHeadline3");
let bannerAutoRenderTimer = null;
let customAccentTapCount = 0;
let customAccentTapTimer = null;

function resetCustomAccentTapSequence() {
  customAccentTapCount = 0;
  if (customAccentTapTimer) {
    clearTimeout(customAccentTapTimer);
    customAccentTapTimer = null;
  }
}

function registerCustomAccentTap() {
  customAccentTapCount += 1;
  if (customAccentTapTimer) {
    clearTimeout(customAccentTapTimer);
  }
  customAccentTapTimer = setTimeout(() => {
    resetCustomAccentTapSequence();
  }, CUSTOM_ACCENT_TRIGGER_WINDOW_MS);

  if (customAccentTapCount >= CUSTOM_ACCENT_TRIGGER_TAP_COUNT) {
    resetCustomAccentTapSequence();
    if (bannerAccentColorInput) {
      bannerAccentColorInput.value = state.bannerAccentCustomColor || ACCENT_PRESET_VALUES.lime;
      bannerAccentColorInput.click();
    }
  }
}

function setSourceStatus(kind) {
  uploadImageStatusEl.textContent = SOURCE_STATUS[kind] || SOURCE_STATUS.none;
  if (videoSourceStatusEl) {
    videoSourceStatusEl.textContent = SOURCE_STATUS[kind] || SOURCE_STATUS.none;
  }
}

function normalizeLibraryImage(item) {
  if (!item || typeof item !== "object") return null;
  const imageUrl = String(item.image_url || "").trim();
  if (!imageUrl) return null;
  return {
    id: String(item.id || imageUrl),
    image_url: imageUrl,
    banner_source_url: String(item.banner_source_url || "").trim(),
    effective_banner_source_url: String(item.effective_banner_source_url || imageUrl).trim() || imageUrl,
    banner_ready: Boolean(item.banner_ready),
    kind: String(item.kind || "generated").trim() || "generated",
    created_at: String(item.created_at || "").trim(),
    label: String(item.label || "").trim(),
    prompt: String(item.prompt || "").trim(),
    car_model: String(item.car_model || "").trim(),
    color_name: String(item.color_name || "").trim(),
    country: String(item.country || "").trim(),
    original_name: String(item.original_name || "").trim(),
    edit_prompt: String(item.edit_prompt || "").trim(),
    source_image_url: String(item.source_image_url || "").trim(),
  };
}

function normalizeLibraryVideo(item) {
  if (!item || typeof item !== "object") return null;
  const videoUrl = String(item.video_url || "").trim();
  if (!videoUrl) return null;
  return {
    id: String(item.id || videoUrl),
    video_url: videoUrl,
    base_video_url: String(item.base_video_url || "").trim(),
    created_at: String(item.created_at || "").trim(),
    source_image_url: String(item.source_image_url || "").trim(),
    prompt: String(item.prompt || "").trim(),
    label: String(item.label || "").trim(),
    headlines: Array.isArray(item.headlines)
      ? item.headlines.map((value) => String(value || "").trim()).filter(Boolean)
      : [],
  };
}

function findLibraryImageByUrl(url) {
  const target = String(url || "").trim();
  if (!target) return null;
  return state.imageLibrary.find((item) => item.image_url === target) || null;
}

function upsertStateLibraryImage(record) {
  const image = normalizeLibraryImage(record);
  if (!image) return null;
  const index = state.imageLibrary.findIndex((item) => item.image_url === image.image_url);
  if (index >= 0) {
    state.imageLibrary[index] = image;
  } else {
    state.imageLibrary.unshift(image);
  }
  return image;
}

function findLibraryVideoByUrl(url) {
  const target = String(url || "").trim();
  if (!target) return null;
  return state.videoLibrary.find((item) => item.video_url === target) || null;
}

function getImageLibraryCountryLabel(item) {
  const country = String(item?.country || "").trim();
  if (country) return country;
  const kind = String(item?.kind || "").toLowerCase();
  if (kind === "uploaded") return "Uploaded";
  return "Other";
}

function getImageLibraryCountryOptions() {
  const seen = new Set();
  state.imageLibrary.forEach((item) => {
    const label = getImageLibraryCountryLabel(item);
    if (label) seen.add(label);
  });
  return Array.from(seen);
}

function getActiveSourceLibraryCountry(options = getImageLibraryCountryOptions()) {
  if (!options.length) return "";
  const selected = String(state.sourceLibraryCountry || "").trim();
  if (selected && options.includes(selected)) return selected;
  if (state.selectedCountry && options.includes(state.selectedCountry)) return state.selectedCountry;
  if (options.includes("Uploaded")) return "Uploaded";
  if (options.includes("Other")) return "Other";
  return options[0] || "";
}

function setSourceStatusForImage(record) {
  const kind = String(record?.kind || "").toLowerCase();
  if (kind === "uploaded") {
    setSourceStatus("uploaded");
    return;
  }
  if (kind) {
    setSourceStatus("generated");
    return;
  }
  setSourceStatus(state.imageUrl ? "generated" : "none");
}

function getCurrentCarModel() {
  return getSelectedTransport()?.model?.trim() || "";
}

function getSelectedImageStyle() {
  return IMAGE_STYLES.find((item) => item.value === state.selectedImageStyle) || IMAGE_STYLES[0];
}

function getSelectedCountryRecord() {
  return state.vehicleData.find((item) => item.country === state.selectedCountry) || null;
}

function getTransportOptions() {
  return getSelectedCountryRecord()?.tariffs || [];
}

function getSelectedTransport() {
  return getTransportOptions().find((item) => item.label === state.selectedTransportLabel) || null;
}

function isBusinessClassTransport(transport) {
  const value = `${transport?.label || ""} ${transport?.basicClass || ""}`.toLowerCase();
  return BUSINESS_CLASS_KEYWORDS.some((keyword) => value.includes(keyword));
}

function shouldUseOmanFemaleBranding() {
  const transport = getSelectedTransport();
  const text = `${transport?.label || ""} ${state.heroDescription || ""}`.toLowerCase();
  return /\bfemale\b|\bwoman\b|\bwomen\b|\bgirl\b|девуш|женщ|женск/.test(text);
}

function getBrandingReferenceUrl() {
  const transport = getSelectedTransport();
  if (!state.imageUrl || !transport) return "";
  if ((transport.vehicleType || "car") !== "car") return "";
  if (state.selectedCountry === "UAE") return "";
  if (isBusinessClassTransport(transport)) return "";

  let referenceKey = COUNTRY_BRANDING_REFERENCE[state.selectedCountry] || "english";
  if (state.selectedCountry === "Oman" && shouldUseOmanFemaleBranding()) {
    referenceKey = "oman-female";
  }
  return BRANDING_REFERENCES[referenceKey] || BRANDING_REFERENCES.english;
}

function getAvailableCompositions() {
  const vehicleType = getSelectedTransport()?.vehicleType || "car";
  return COMPOSITION_PRESETS.filter((item) => item.vehicleTypes.includes(vehicleType));
}

function applySelectedImage(record, options = {}) {
  const image = normalizeLibraryImage(record);
  if (!image) return;
  const { closeLibrary = true } = options;
  state.bannerSourceImageUrl = image.image_url;
  invalidateRenderedBanners();
  if (closeLibrary) {
    state.sourceLibraryOpen = false;
    state.sourceLibraryCountryMenuOpen = false;
  }
  setSourceStatusForImage(image);
  renderBannerSetsView();
  renderUiState();
}

async function deleteLibraryImage(imageUrl) {
  const targetUrl = String(imageUrl || "").trim();
  if (!targetUrl) return;
  try {
    const response = await fetch("/api/delete-library-image", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ imageUrl: targetUrl }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Delete failed");
    }
    state.imageLibrary = state.imageLibrary.filter((item) => item.image_url !== targetUrl);
    state.sourceLibraryCountryMenuOpen = false;
    if (state.bannerSourceImageUrl === targetUrl) {
      state.bannerSourceImageUrl = "";
      invalidateRenderedBanners();
      setSourceStatus("none");
      renderBannerSetsView();
    }
    renderUiState();
  } catch (error) {
    showError(error, "Could not delete this item.");
  }
}

function applySelectedVideo(record, options = {}) {
  const video = normalizeLibraryVideo(record);
  if (!video) return;
  const { closeLibrary = true } = options;
  if (video.source_image_url) {
    state.imageUrl = video.source_image_url;
    if (!state.bannerSourceImageUrl) {
      state.bannerSourceImageUrl = video.source_image_url;
    }
    setSourceStatus("generated");
  } else if (videoSourceStatusEl) {
    videoSourceStatusEl.textContent = SOURCE_STATUS.uploaded;
  }
  state.videoResultUrl = video.video_url;
  state.videoRenderStatus = "Saved video ready for new titles.";
  if (video.headlines.length) {
    state.videoHeadlines = [video.headlines[0] || "", video.headlines[1] || "", video.headlines[2] || ""];
  }
  if (closeLibrary) {
    state.videoLibraryOpen = false;
  }
  renderUiState();
}

async function deleteLibraryVideo(videoUrl) {
  const targetUrl = String(videoUrl || "").trim();
  if (!targetUrl) return;
  try {
    const response = await fetch("/api/delete-library-video", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ videoUrl: targetUrl }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Delete failed");
    }
    state.videoLibrary = state.videoLibrary.filter((item) => item.video_url !== targetUrl);
    if (state.videoResultUrl === targetUrl) {
      state.videoResultUrl = "";
      state.videoRenderStatus = "No video yet.";
    }
    renderUiState();
  } catch (error) {
    showError(error, "Could not delete this item.");
  }
}

function renderSourceLibrary() {
  if (!sourceLibraryEl) return;
  sourceLibraryEl.innerHTML = "";
  sourceLibraryEl.classList.toggle("hidden", !state.sourceLibraryOpen || !state.imageLibrary.length);
  if (sourceLibraryToggleEl) {
    sourceLibraryToggleEl.disabled = !state.imageLibrary.length;
    sourceLibraryToggleEl.setAttribute("aria-expanded", state.sourceLibraryOpen ? "true" : "false");
  }
  if (sourceLibraryChevronEl) {
    sourceLibraryChevronEl.src = state.sourceLibraryOpen
      ? "./assets/icons/ChevronUpM.svg"
      : "./assets/icons/ChevronDownM.svg";
  }

  if (!state.imageLibrary.length) {
    const empty = document.createElement("p");
    empty.className = "source-library-empty";
    empty.textContent = "No saved images yet.";
    sourceLibraryEl.appendChild(empty);
    return;
  }

  const options = getImageLibraryCountryOptions();
  const activeCountry = getActiveSourceLibraryCountry(options);
  state.sourceLibraryCountry = activeCountry;
  if (!options.includes(activeCountry)) {
    state.sourceLibraryCountryMenuOpen = false;
  }

  const selector = document.createElement("div");
  selector.className = "source-library-filter";

  const selectorToggle = document.createElement("button");
  selectorToggle.type = "button";
  selectorToggle.className = "source-library-filter-toggle";
  selectorToggle.setAttribute("aria-expanded", state.sourceLibraryCountryMenuOpen ? "true" : "false");
  const selectorLabel = document.createElement("span");
  selectorLabel.className = "source-library-filter-label";
  selectorLabel.textContent = activeCountry || "Choose country";
  selectorToggle.appendChild(selectorLabel);
  const selectorChevron = document.createElement("img");
  selectorChevron.className = "source-library-filter-chevron";
  selectorChevron.src = state.sourceLibraryCountryMenuOpen
    ? "./assets/icons/ChevronUpM.svg"
    : "./assets/icons/ChevronDownM.svg";
  selectorChevron.alt = "";
  selectorChevron.setAttribute("aria-hidden", "true");
  selectorToggle.appendChild(selectorChevron);
  selectorToggle.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    state.sourceLibraryCountryMenuOpen = !state.sourceLibraryCountryMenuOpen;
    renderSourceLibrary();
  });
  selector.appendChild(selectorToggle);

  const selectorMenu = document.createElement("div");
  selectorMenu.className = "source-library-filter-menu";
  selectorMenu.classList.toggle("hidden", !state.sourceLibraryCountryMenuOpen);
  options.forEach((label) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "source-library-filter-option";
    if (label === activeCountry) option.classList.add("is-active");
    option.textContent = label;
    option.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      state.sourceLibraryCountry = label;
      state.sourceLibraryCountryMenuOpen = false;
      renderSourceLibrary();
    });
    selectorMenu.appendChild(option);
  });
  selector.appendChild(selectorMenu);
  sourceLibraryEl.appendChild(selector);

  const visibleItems = state.imageLibrary.filter((item) => getImageLibraryCountryLabel(item) === activeCountry);
  if (!visibleItems.length) {
    const empty = document.createElement("p");
    empty.className = "source-library-empty";
    empty.textContent = `No saved images for ${activeCountry}.`;
    sourceLibraryEl.appendChild(empty);
    return;
  }

  const grid = document.createElement("div");
  grid.className = "source-library-grid";
  visibleItems.forEach((item) => {
    const card = document.createElement("div");
    card.className = "source-card-wrap";

    const previewBtn = document.createElement("button");
    previewBtn.type = "button";
    previewBtn.className = "source-card";
    if (state.bannerSourceImageUrl && item.image_url === state.bannerSourceImageUrl) {
      previewBtn.classList.add("is-active");
    }
    previewBtn.setAttribute("aria-label", item.car_model || item.original_name || item.label || "Saved image");

    const preview = document.createElement("img");
    preview.className = "source-card-image";
    preview.src = item.image_url;
    preview.alt = item.car_model || item.original_name || item.label || item.kind || "Saved image";
    previewBtn.appendChild(preview);
    previewBtn.addEventListener("click", () => applySelectedImage(item));

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "source-card-delete";
    deleteBtn.setAttribute("aria-label", "Delete saved image");
    const deleteGlyph = document.createElement("span");
    deleteGlyph.className = "source-card-delete-glyph";
    deleteGlyph.setAttribute("aria-hidden", "true");
    deleteBtn.appendChild(deleteGlyph);
    deleteBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      deleteLibraryImage(item.image_url);
    });

    card.appendChild(previewBtn);
    card.appendChild(deleteBtn);
    grid.appendChild(card);
  });
  sourceLibraryEl.appendChild(grid);
}

function renderVideoLibrary() {
  if (!videoLibraryEl) return;
  videoLibraryEl.innerHTML = "";
  videoLibraryEl.classList.toggle("hidden", !state.videoLibraryOpen || !state.videoLibrary.length);
  if (videoLibraryToggleEl) {
    videoLibraryToggleEl.disabled = !state.videoLibrary.length;
    videoLibraryToggleEl.setAttribute("aria-expanded", state.videoLibraryOpen ? "true" : "false");
  }
  if (videoLibraryChevronEl) {
    videoLibraryChevronEl.src = state.videoLibraryOpen
      ? "./assets/icons/ChevronUpM.svg"
      : "./assets/icons/ChevronDownM.svg";
  }

  if (!state.videoLibrary.length) {
    const empty = document.createElement("p");
    empty.className = "source-library-empty";
    empty.textContent = "No saved videos yet.";
    videoLibraryEl.appendChild(empty);
    return;
  }

  state.videoLibrary.forEach((item) => {
    const card = document.createElement("div");
    card.className = "source-card-wrap";

    const previewBtn = document.createElement("button");
    previewBtn.type = "button";
    previewBtn.className = "source-card";
    if (state.videoResultUrl && item.video_url === state.videoResultUrl) {
      previewBtn.classList.add("is-active");
    }
    previewBtn.setAttribute("aria-label", item.label || "Saved video");

    const preview = document.createElement("video");
    preview.className = "source-card-video";
    preview.src = item.video_url;
    preview.muted = true;
    preview.playsInline = true;
    preview.preload = "metadata";
    preview.setAttribute("aria-hidden", "true");
    previewBtn.appendChild(preview);
    previewBtn.addEventListener("click", () => applySelectedVideo(item));

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "source-card-delete";
    deleteBtn.setAttribute("aria-label", "Delete saved video");
    const deleteGlyph = document.createElement("span");
    deleteGlyph.className = "source-card-delete-glyph";
    deleteGlyph.setAttribute("aria-hidden", "true");
    deleteBtn.appendChild(deleteGlyph);
    deleteBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      deleteLibraryVideo(item.video_url);
    });

    card.appendChild(previewBtn);
    card.appendChild(deleteBtn);
    videoLibraryEl.appendChild(card);
  });
}

function renderSelectedSource() {
  if (!selectedSourceBoxEl || !selectedSourcePreviewEl) return;
  const selected = findLibraryImageByUrl(state.bannerSourceImageUrl);
  const hasSource = Boolean(state.bannerSourceImageUrl);
  selectedSourceBoxEl.classList.toggle("hidden", !hasSource);
  if (!hasSource) {
    selectedSourcePreviewEl.removeAttribute("src");
    return;
  }
  selectedSourcePreviewEl.src = state.bannerSourceImageUrl;
  selectedSourcePreviewEl.alt =
    selected?.car_model || selected?.original_name || selected?.label || "Selected source image";
}

function renderEditSource() {
  const isEditStyle = state.selectedImageStyle === "edit";
  if (editSourceSectionEl) {
    editSourceSectionEl.classList.toggle("hidden", !isEditStyle);
  }
  if (editSourceStatusEl) {
    editSourceStatusEl.textContent = SOURCE_STATUS[state.editSourceStatus] || SOURCE_STATUS.none;
  }
  if (editSelectedSourceBoxEl && editSelectedSourcePreviewEl) {
    const hasSource = Boolean(state.editSourceImageUrl);
    editSelectedSourceBoxEl.classList.toggle("hidden", !hasSource);
    if (hasSource) {
      editSelectedSourcePreviewEl.src = state.editSourceImageUrl;
    } else {
      editSelectedSourcePreviewEl.removeAttribute("src");
    }
  }
}

async function fetchImageLibrary() {
  try {
    const response = await fetch("/api/library-images", {
      credentials: "same-origin",
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to load saved images");
    }
    state.imageLibrary = Array.isArray(payload.images)
      ? payload.images.map((item) => normalizeLibraryImage(item)).filter(Boolean)
      : [];
    if (state.bannerSourceImageUrl) {
      const selected = findLibraryImageByUrl(state.bannerSourceImageUrl);
      if (selected) {
        setSourceStatusForImage(selected);
      } else {
        state.bannerSourceImageUrl = "";
      }
    }
    renderSourceLibrary();
    renderUiState();
  } catch (error) {
    console.error(error);
  }
}

async function fetchVideoLibrary() {
  try {
    const response = await fetch("/api/library-videos", {
      credentials: "same-origin",
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to load saved videos");
    }
    state.videoLibrary = Array.isArray(payload.videos)
      ? payload.videos.map((item) => normalizeLibraryVideo(item)).filter(Boolean)
      : [];
    if (state.videoResultUrl && !findLibraryVideoByUrl(state.videoResultUrl)) {
      state.videoResultUrl = "";
      state.videoRenderStatus = "No video yet.";
    }
    renderVideoLibrary();
    renderUiState();
  } catch (error) {
    console.error(error);
  }
}

async function fetchVehicleData() {
  state.vehicleDataLoading = true;
  state.vehicleDataError = "";
  renderImageControls();
  renderUiState();
  try {
    const response = await fetch(VEHICLE_DATA_URL, {
      credentials: "same-origin",
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error("Failed to load vehicle data");
    }
    state.vehicleData = Array.isArray(payload.countries)
      ? payload.countries
          .map((country) => ({
            country: String(country.country || "").trim(),
            tariffs: Array.isArray(country.tariffs)
              ? country.tariffs
                  .map((tariff) => ({
                    label: String(tariff.label || "").trim(),
                    basicClass: String(tariff.basicClass || "").trim(),
                    tariffCode: String(tariff.tariffCode || "").trim(),
                    model: String(tariff.model || "").trim(),
                    vehicleType: String(tariff.vehicleType || "car").trim() || "car",
                    colorName: String(tariff.colorName || "").trim(),
                    orders: Number(tariff.orders || 0),
                  }))
                  .filter((tariff) => tariff.label && tariff.model)
              : [],
          }))
          .filter((country) => country.country && country.tariffs.length)
      : [];
  } catch (error) {
    console.error(error);
    state.vehicleDataError = error.message || "Failed to load vehicle data";
  } finally {
    state.vehicleDataLoading = false;
    renderImageControls();
    renderUiState();
  }
}

function renderSelectOption(menuEl, item, isActive, onClick) {
  const option = document.createElement("button");
  option.type = "button";
  option.className = "select-option";
  option.textContent = item.label;
  if (isActive) {
    option.classList.add("is-active");
  }
  option.addEventListener("click", onClick);
  menuEl.appendChild(option);
}

function renderCountryControl() {
  if (!countryDisplayEl || !countryToggleEl || !countryMenuEl) return;
  countryDisplayEl.textContent = state.vehicleDataError
    ? "Countries unavailable"
    : state.selectedCountry || (state.vehicleDataLoading ? "Loading countries" : "Select a country");
  countryToggleEl.disabled = state.vehicleDataLoading || Boolean(state.vehicleDataError);
  countryToggleEl.setAttribute("aria-expanded", state.countryMenuOpen ? "true" : "false");
  if (countryChevronIconEl) {
    countryChevronIconEl.src = state.countryMenuOpen
      ? "./assets/icons/ChevronUpM.svg"
      : "./assets/icons/ChevronDownM.svg";
  }
  countryMenuEl.classList.toggle("hidden", !state.countryMenuOpen);
  countryMenuEl.innerHTML = "";
  state.vehicleData.forEach((country) => {
    renderSelectOption(
      countryMenuEl,
      { label: country.country },
      state.selectedCountry === country.country,
      () => {
        state.selectedCountry = country.country;
        state.sourceLibraryCountry = country.country;
        state.sourceLibraryCountryMenuOpen = false;
        state.selectedTransportLabel = "";
        state.selectedComposition = "";
        state.countryMenuOpen = false;
        state.transportMenuOpen = false;
        renderImageControls();
        renderUiState();
      }
    );
  });
}

function renderStyleControl() {
  if (!styleDisplayEl || !styleToggleEl || !styleMenuEl) return;
  const selected = getSelectedImageStyle();
  styleDisplayEl.textContent = selected.label;
  styleToggleEl.setAttribute("aria-expanded", state.styleMenuOpen ? "true" : "false");
  if (styleChevronIconEl) {
    styleChevronIconEl.src = state.styleMenuOpen
      ? "./assets/icons/ChevronUpM.svg"
      : "./assets/icons/ChevronDownM.svg";
  }
  styleMenuEl.classList.toggle("hidden", !state.styleMenuOpen);
  styleMenuEl.innerHTML = "";
  IMAGE_STYLES.forEach((style) => {
    renderSelectOption(
      styleMenuEl,
      { label: style.label },
      state.selectedImageStyle === style.value,
      () => {
        state.selectedImageStyle = style.value;
        state.styleMenuOpen = false;
        state.countryMenuOpen = false;
        state.transportMenuOpen = false;
        renderImageControls();
        renderUiState();
      }
    );
  });
}

function renderTransportControl() {
  if (!transportDisplayEl || !transportToggleEl || !transportMenuEl) return;
  const selected = getSelectedTransport();
  transportDisplayEl.textContent = selected
    ? selected.label
    : state.selectedCountry
      ? "Select a vehicle"
      : "Select a country first";
  transportToggleEl.disabled = !state.selectedCountry;
  transportToggleEl.setAttribute("aria-expanded", state.transportMenuOpen ? "true" : "false");
  if (transportChevronIconEl) {
    transportChevronIconEl.src = state.transportMenuOpen
      ? "./assets/icons/ChevronUpM.svg"
      : "./assets/icons/ChevronDownM.svg";
  }
  transportMenuEl.classList.toggle("hidden", !state.transportMenuOpen);
  transportMenuEl.innerHTML = "";
  getTransportOptions().forEach((transport) => {
    renderSelectOption(
      transportMenuEl,
      { label: transport.label },
      state.selectedTransportLabel === transport.label,
      () => {
        state.selectedTransportLabel = transport.label;
        state.transportMenuOpen = false;
        const available = getAvailableCompositions();
        state.selectedComposition = available[0]?.label || "";
        renderImageControls();
        renderUiState();
      }
    );
  });
}

function renderTabs() {
  const isImageTab = state.activeTab === "image";
  const isBannerTab = state.activeTab === "banner";
  const isVideoTab = VIDEO_TAB_ENABLED && state.activeTab === "video";
  tabImageEl.classList.toggle("is-active", isImageTab);
  tabBannerEl.classList.toggle("is-active", isBannerTab);
  if (tabVideoEl) {
    tabVideoEl.classList.toggle("is-active", isVideoTab);
    tabVideoEl.disabled = !VIDEO_TAB_ENABLED;
    tabVideoEl.setAttribute("aria-disabled", VIDEO_TAB_ENABLED ? "false" : "true");
  }
  tabImageEl.setAttribute("aria-selected", isImageTab ? "true" : "false");
  tabBannerEl.setAttribute("aria-selected", isBannerTab ? "true" : "false");
  if (tabVideoEl) {
    tabVideoEl.setAttribute("aria-selected", isVideoTab ? "true" : "false");
  }

  imageTabPanelEl.classList.toggle("is-active", isImageTab);
  bannerTabPanelEl.classList.toggle("is-active", isBannerTab);
  bannerTabPanelEl.setAttribute("aria-hidden", isBannerTab ? "false" : "true");
  if (videoTabPanelEl) {
    videoTabPanelEl.classList.toggle("is-active", isVideoTab);
    videoTabPanelEl.setAttribute("aria-hidden", isVideoTab ? "false" : "true");
  }

  imageCanvasEl.classList.toggle("is-active", isImageTab);
  bannerCanvasEl.classList.toggle("is-active", isBannerTab);
  if (videoCanvasEl) {
    videoCanvasEl.classList.toggle("is-active", isVideoTab);
  }
}

function renderTopAction() {
  if (state.activeTab === "image") {
    topActionBtn.classList.toggle("hidden", !state.imageUrl);
    topActionBtn.textContent = "Copy";
    topActionBtn.disabled = state.generating || !(state.basePromptText.trim() || state.imageUrl.trim());
    return;
  }
  if (state.activeTab === "video") {
    topActionBtn.classList.toggle("hidden", !state.videoResultUrl);
    topActionBtn.textContent = "Download";
    topActionBtn.disabled = state.videoGenerating || state.videoRendering || !state.videoResultUrl.trim();
    return;
  }
  {
    topActionBtn.classList.remove("hidden");
    topActionBtn.textContent = "Download All";
    topActionBtn.disabled = state.bannerRendering || !state.renderedBanners.length;
  }
}

function invalidateRenderedBanners(resetAutoRenderEligibility = true) {
  state.renderedBanners = [];
  if (resetAutoRenderEligibility) {
    state.hasRenderedBanners = false;
  }
}

function renderUiState() {
  const isBusy = state.generating || state.bannerRendering || state.videoGenerating || state.videoRendering;
  const isEditStyle = state.selectedImageStyle === "edit";
  loaderEl.classList.toggle("hidden", !isBusy);
  if (loaderLabelEl) {
    if (state.generating) {
      loaderLabelEl.textContent = "Generating image";
    } else if (state.videoRendering) {
      loaderLabelEl.textContent = "Generating video";
    } else if (state.videoGenerating) {
      loaderLabelEl.textContent = "Preparing video";
    } else if (state.bannerStage === "uncropping") {
      loaderLabelEl.textContent = "Uncropping";
    } else if (state.bannerStage === "creating") {
      loaderLabelEl.textContent = "Creating banners";
    } else {
      loaderLabelEl.textContent = "Working";
    }
  }
  generateBtn.disabled = state.generating || (isEditStyle ? !state.editSourceImageUrl : (!state.selectedCountry || !getSelectedTransport()));
  renderBannersBtn.disabled = state.bannerRendering || !state.bannerSourceImageUrl;
  if (generateVideoBtnEl) {
    const selectedSavedVideo = findLibraryVideoByUrl(state.videoResultUrl);
    const canRemixSavedVideo = Boolean(selectedSavedVideo);
    const canGenerateNewVideo = Boolean(state.imageUrl && getCurrentCarModel());
    generateVideoBtnEl.disabled = state.videoGenerating || state.videoRendering || !(canRemixSavedVideo || canGenerateNewVideo);
    generateVideoBtnEl.textContent = state.videoRendering ? "Generating Video..." : "Generate Video";
  }
  renderTabs();
  renderTopAction();
  renderImageControls();
  renderEditSource();
  imagePreviewFrameEl.classList.remove("hidden");
  resultImageEl.src = state.imageUrl || "";
  resultImageEl.classList.toggle("hidden", !state.imageUrl);
  promptRowEl.classList.toggle("hidden", !state.imageUrl);
  if (quickActionRowEl) {
    const brandingReferenceUrl = getBrandingReferenceUrl();
    quickActionRowEl.classList.toggle("hidden", isEditStyle || !state.imageUrl);
    if (seatbeltActionBtn) {
      seatbeltActionBtn.disabled = state.generating || !state.imageUrl;
    }
    if (brandingActionBtn) {
      brandingActionBtn.disabled = state.generating || !brandingReferenceUrl;
      brandingActionBtn.title = brandingReferenceUrl
        ? ""
        : "Branding is disabled for UAE, moto, tuk-tuk, and business class.";
    }
    if (removeBackgroundPeopleActionBtn) {
      removeBackgroundPeopleActionBtn.disabled = state.generating || !state.imageUrl;
    }
  }
  if (promptBackBtn) {
    promptBackBtn.disabled = state.generating || !state.imageHistory.length;
  }
  if (promptInputEl.value !== state.editPromptText) {
    promptInputEl.value = state.editPromptText;
  }
  if (videoRenderStatusEl) {
    videoRenderStatusEl.textContent = state.videoRenderStatus;
  }
  const videoHeadlineInputs = [videoHeadline1El, videoHeadline2El, videoHeadline3El];
  videoHeadlineInputs.forEach((input, index) => {
    if (!input) return;
    const nextValue = String(state.videoHeadlines[index] || "");
    if (input.value !== nextValue) {
      input.value = nextValue;
    }
  });
  if (videoResultWrapEl && videoResultPlayerEl && videoDownloadLinkEl) {
    const hasVideo = Boolean(state.videoResultUrl);
    videoResultWrapEl.classList.toggle("hidden", !hasVideo);
    if (videoEmptyStateEl) {
      videoEmptyStateEl.classList.toggle("hidden", hasVideo);
    }
    if (hasVideo) {
      if (videoResultPlayerEl.getAttribute("src") !== state.videoResultUrl) {
        videoResultPlayerEl.src = state.videoResultUrl;
      }
      videoDownloadLinkEl.href = state.videoResultUrl;
      videoDownloadLinkEl.classList.remove("hidden");
    } else {
      videoResultPlayerEl.removeAttribute("src");
      videoResultPlayerEl.load();
      videoDownloadLinkEl.removeAttribute("href");
      videoDownloadLinkEl.classList.add("hidden");
    }
  }
  renderSelectedSource();
  renderSourceLibrary();
  renderVideoLibrary();
}

function pushImageToHistory(url) {
  const value = String(url || "").trim();
  if (!value) return;
  const last = state.imageHistory[state.imageHistory.length - 1] || "";
  if (last === value) return;
  state.imageHistory.push(value);
}

function renderCompositions() {
  if (!compositionSectionEl || !compositionRowEl) return;
  const selectedTransport = getSelectedTransport();
  compositionSectionEl.classList.toggle("hidden", !selectedTransport);
  compositionRowEl.innerHTML = "";
  if (!selectedTransport) return;

  const available = getAvailableCompositions();
  if (!available.some((item) => item.label === state.selectedComposition)) {
    state.selectedComposition = available[0]?.label || "";
  }

  available.forEach((preset) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "angle-chip";
    chip.textContent = preset.label;
    if (state.selectedComposition === preset.label) chip.classList.add("is-active");
    chip.addEventListener("click", () => {
      state.selectedComposition = preset.label;
      renderCompositions();
    });
    compositionRowEl.appendChild(chip);
  });
}

function renderImageControls() {
  const isEditStyle = state.selectedImageStyle === "edit";
  renderStyleControl();
  photoStyleOnlyEls.forEach((element) => {
    element.classList.toggle("hidden", isEditStyle);
  });
  if (isEditStyle) {
    state.countryMenuOpen = false;
    state.transportMenuOpen = false;
    if (countryMenuEl) countryMenuEl.classList.add("hidden");
    if (transportMenuEl) transportMenuEl.classList.add("hidden");
    return;
  }
  renderCountryControl();
  renderTransportControl();
  renderCompositions();
}

function renderLayoutTypes() {
  layoutTypeRowEl.innerHTML = "";
  const row = document.createElement("div");
  row.className = "layout-accent-row";

  const layoutGroup = document.createElement("div");
  layoutGroup.className = "layout-type-group";
  BANNER_LAYOUTS.forEach((layout) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "angle-chip";
    chip.textContent = layout.label;
    if (layout.disabled) {
      chip.disabled = true;
      chip.classList.add("is-disabled");
    }
    if (state.bannerLayout === layout.value) chip.classList.add("is-active");
    chip.addEventListener("click", () => {
      if (layout.disabled) return;
      state.bannerLayout = layout.value;
      invalidateRenderedBanners();
      renderLayoutTypes();
      renderBannerSetsView();
      renderTopAction();
    });
    layoutGroup.appendChild(chip);
  });

  const accentGroup = document.createElement("div");
  accentGroup.className = "layout-accent-group";
  ["lime", "red"].forEach((key) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "accent-swatch-btn";
    const isCustomTrigger = key === "red";
    if (state.bannerAccentPreset === key || (isCustomTrigger && state.bannerAccentPreset === "custom")) {
      btn.classList.add("is-active");
    }
    const swatch = document.createElement("span");
    swatch.className = "accent-swatch-core";
    swatch.style.background = key === "lime"
      ? ACCENT_PRESET_VALUES.lime
      : state.bannerAccentPreset === "custom"
        ? state.bannerAccentCustomColor
        : ACCENT_PRESET_VALUES.red;
    btn.appendChild(swatch);
    btn.addEventListener("click", () => {
      if (isCustomTrigger) {
        state.bannerAccentPreset = "red";
        invalidateRenderedBanners();
        renderLayoutTypes();
        renderBannerSetsView();
        renderTopAction();
        registerCustomAccentTap();
        return;
      }
      resetCustomAccentTapSequence();
      state.bannerAccentPreset = key;
      invalidateRenderedBanners();
      renderLayoutTypes();
      renderBannerSetsView();
      renderTopAction();
    });
    accentGroup.appendChild(btn);
  });

  row.appendChild(layoutGroup);
  row.appendChild(accentGroup);
  layoutTypeRowEl.appendChild(row);
}

function renderShiftControls() {
  const values = getActiveImagePositionValues();
  if (imageScaleEl) imageScaleEl.value = String(values.imageScalePercent);
  if (imageShiftXEl) imageShiftXEl.value = String(values.imageShiftXStep);
  if (imageShiftYEl) imageShiftYEl.value = String(values.imageShiftYStep);
  const active = parseBannerPositionKey(state.activeBannerPositionKey);
  if (imageShiftScopeEl) {
    imageShiftScopeEl.textContent = active ? `Set ${active.setIndex + 1} · ${active.size}` : "Global";
  }
  if (resetBannerShiftBtnEl) {
    resetBannerShiftBtnEl.classList.toggle("hidden", !active);
    resetBannerShiftBtnEl.disabled = !active || !state.bannerImageOverrides[state.activeBannerPositionKey];
  }
  if (useGlobalShiftBtnEl) {
    useGlobalShiftBtnEl.classList.toggle("hidden", !active);
  }
  applySliderFill(imageScaleEl);
  applySliderFill(imageShiftXEl);
  applySliderFill(imageShiftYEl);
}

function makeBannerPositionKey(setIndex, size) {
  return `${Number(setIndex) || 0}:${String(size || "").trim()}`;
}

function parseBannerPositionKey(key) {
  const raw = String(key || "");
  const separatorIndex = raw.indexOf(":");
  if (separatorIndex < 1) return null;
  const setIndex = Number(raw.slice(0, separatorIndex));
  const size = raw.slice(separatorIndex + 1);
  if (!Number.isInteger(setIndex) || setIndex < 0 || !BANNER_SIZE_LABELS[size]) return null;
  return { setIndex, size };
}

function getGlobalImagePositionValues() {
  return {
    imageScalePercent: Number(state.imageScalePercent) || IMAGE_SCALE_MIN,
    imageShiftXStep: clampShiftStep(Number(state.imageShiftXStep) || 0),
    imageShiftYStep: clampShiftStep(Number(state.imageShiftYStep) || 0),
  };
}

function normalizeImagePositionValues(values) {
  const globalValues = getGlobalImagePositionValues();
  const rawScale = Number(values?.imageScalePercent ?? values?.scalePercent ?? globalValues.imageScalePercent);
  return {
    imageScalePercent: Math.max(IMAGE_SCALE_MIN, Math.min(IMAGE_SCALE_MAX, Number.isFinite(rawScale) ? rawScale : globalValues.imageScalePercent)),
    imageShiftXStep: clampShiftStep(Number(values?.imageShiftXStep ?? values?.xStep ?? globalValues.imageShiftXStep) || 0),
    imageShiftYStep: clampShiftStep(Number(values?.imageShiftYStep ?? values?.yStep ?? globalValues.imageShiftYStep) || 0),
  };
}

function getBannerImageOverride(key) {
  if (!key || !state.bannerImageOverrides[key]) return null;
  return normalizeImagePositionValues(state.bannerImageOverrides[key]);
}

function getActiveImagePositionValues() {
  return getBannerImageOverride(state.activeBannerPositionKey) || getGlobalImagePositionValues();
}

function setActiveBannerPosition(setIndex, size) {
  const key = makeBannerPositionKey(setIndex, size);
  if (state.activeBannerPositionKey === key) return;
  state.activeBannerPositionKey = key;
  renderShiftControls();
  renderBannerSetsView();
}

function updateActiveImagePosition(partialValues) {
  const active = parseBannerPositionKey(state.activeBannerPositionKey);
  if (!active) {
    if (Object.prototype.hasOwnProperty.call(partialValues, "imageScalePercent")) {
      state.imageScalePercent = partialValues.imageScalePercent;
    }
    if (Object.prototype.hasOwnProperty.call(partialValues, "imageShiftXStep")) {
      state.imageShiftXStep = partialValues.imageShiftXStep;
    }
    if (Object.prototype.hasOwnProperty.call(partialValues, "imageShiftYStep")) {
      state.imageShiftYStep = partialValues.imageShiftYStep;
    }
    return;
  }
  const currentValues = getBannerImageOverride(state.activeBannerPositionKey) || getGlobalImagePositionValues();
  state.bannerImageOverrides[state.activeBannerPositionKey] = normalizeImagePositionValues({
    ...currentValues,
    ...partialValues,
  });
}

function resetActiveBannerPosition() {
  if (!parseBannerPositionKey(state.activeBannerPositionKey)) return;
  delete state.bannerImageOverrides[state.activeBannerPositionKey];
}

function reindexBannerImageOverridesAfterRemove(removedSetIndex) {
  const nextOverrides = {};
  Object.entries(state.bannerImageOverrides || {}).forEach(([key, value]) => {
    const parsed = parseBannerPositionKey(key);
    if (!parsed || parsed.setIndex === removedSetIndex) return;
    const nextSetIndex = parsed.setIndex > removedSetIndex ? parsed.setIndex - 1 : parsed.setIndex;
    nextOverrides[makeBannerPositionKey(nextSetIndex, parsed.size)] = value;
  });
  state.bannerImageOverrides = nextOverrides;
  const active = parseBannerPositionKey(state.activeBannerPositionKey);
  if (!active || active.setIndex === removedSetIndex) {
    state.activeBannerPositionKey = "";
  } else if (active.setIndex > removedSetIndex) {
    state.activeBannerPositionKey = makeBannerPositionKey(active.setIndex - 1, active.size);
  }
}

function copyBannerImageOverridesToSet(fromSetIndex, toSetIndex) {
  Object.entries(state.bannerImageOverrides || {}).forEach(([key, value]) => {
    const parsed = parseBannerPositionKey(key);
    if (!parsed || parsed.setIndex !== fromSetIndex) return;
    state.bannerImageOverrides[makeBannerPositionKey(toSetIndex, parsed.size)] = { ...normalizeImagePositionValues(value) };
  });
}

function markImagePositionChanged(hadRenderedBanners) {
  renderShiftControls();
  state.renderedBanners = [];
  renderBannerSetsView();
  renderTopAction();
  if (hadRenderedBanners) {
    scheduleBannerAutoRender();
  }
}

function clampShiftStep(stepValue) {
  return Math.max(-IMAGE_SHIFT_STEP_COUNT, Math.min(IMAGE_SHIFT_STEP_COUNT, stepValue));
}

function stepToShiftPx(stepValue) {
  return Math.round(clampShiftStep(stepValue) * IMAGE_SHIFT_ONE_STEP_PX);
}

function applySliderFill(inputEl) {
  if (!inputEl) return;
  const min = Number(inputEl.min || 0);
  const max = Number(inputEl.max || 100);
  const value = Number(inputEl.value || min);
  const span = max - min || 1;
  const pct = ((value - min) / span) * 100;
  inputEl.style.setProperty("--fill", `${Math.max(0, Math.min(100, pct))}%`);
}

function autoResizeTextarea(textarea) {
  if (!textarea) return;
  textarea.style.height = "auto";
  const nextHeight = Math.max(28, textarea.scrollHeight + 8);
  textarea.style.height = `${nextHeight}px`;
}

function resolveAccentColor() {
  const preset = String(state.bannerAccentPreset || "lime").toLowerCase();
  if (preset === "custom") {
    return state.bannerAccentCustomColor || ACCENT_PRESET_VALUES.lime;
  }
  if (preset === "red") return ACCENT_PRESET_VALUES.red;
  return ACCENT_PRESET_VALUES.lime;
}

function refreshTextSetTextareaHeights() {
  const nodes = textSetsWrapEl ? textSetsWrapEl.querySelectorAll(".text-area") : [];
  nodes.forEach((node) => autoResizeTextarea(node));
}

function renderTextSetsEditor() {
  textSetsWrapEl.innerHTML = "";
  state.bannerTextSets.forEach((set, index) => {
    const card = document.createElement("div");
    card.className = "text-set-card";

    const setTitle = document.createElement("p");
    setTitle.className = "text-set-title";
    setTitle.textContent = `SET ${index + 1}`;
    const setHeader = document.createElement("div");
    setHeader.className = "text-set-header";
    setHeader.appendChild(setTitle);
    if (state.bannerTextSets.length > 1) {
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "text-set-remove-btn";
      removeBtn.textContent = "Remove";
      removeBtn.setAttribute("aria-label", `Remove set ${index + 1}`);
      removeBtn.addEventListener("click", () => {
        state.bannerTextSets.splice(index, 1);
        reindexBannerImageOverridesAfterRemove(index);
        invalidateRenderedBanners();
        renderTextSetsEditor();
        renderShiftControls();
        renderBannerSetsView();
        renderTopAction();
      });
      setHeader.appendChild(removeBtn);
    }
    card.appendChild(setHeader);

    const fields = [
      { key: "title", label: "Title" },
      { key: "subtitle", label: "Subtitle" },
      { key: "disclaimer", label: "Disclaimer" },
    ];

    fields.forEach((field) => {
      const fieldWrap = document.createElement("div");
      fieldWrap.className = "text-set-field";
      const label = document.createElement("label");
      label.className = "field-label";
      label.textContent = `${field.label}:`;
      const textarea = document.createElement("textarea");
      textarea.className = "text-area";
      textarea.rows = field.key === "subtitle" ? 2 : 1;
      textarea.value = set[field.key] || "";
      textarea.addEventListener("input", (event) => {
        autoResizeTextarea(textarea);
        state.bannerTextSets[index][field.key] = event.target.value;
        invalidateRenderedBanners();
        renderBannerSetsView();
        renderTopAction();
      });
      fieldWrap.appendChild(label);
      fieldWrap.appendChild(textarea);
      card.appendChild(fieldWrap);
    });

    const badgeToggleRow = document.createElement("div");
    badgeToggleRow.className = "badge-toggle-row";
    const badgeToggleLabel = document.createElement("label");
    badgeToggleLabel.className = "field-label";
    badgeToggleLabel.textContent = "Badge:";
    const badgeToggleBtn = document.createElement("button");
    badgeToggleBtn.type = "button";
    badgeToggleBtn.className = "badge-toggle-btn";
    badgeToggleBtn.setAttribute("aria-label", "Toggle badge");
    badgeToggleBtn.setAttribute("aria-pressed", String(Boolean(set.badgeEnabled)));
    const badgeToggleIcon = document.createElement("img");
    badgeToggleIcon.className = "badge-toggle-icon";
    badgeToggleIcon.alt = "";
    badgeToggleIcon.setAttribute("aria-hidden", "true");
    badgeToggleIcon.src = set.badgeEnabled ? "./assets/icons/badge-toggle-on.svg" : "./assets/icons/badge-toggle-off.svg";
    badgeToggleBtn.appendChild(badgeToggleIcon);
    badgeToggleBtn.addEventListener("click", () => {
      state.bannerTextSets[index].badgeEnabled = !Boolean(state.bannerTextSets[index].badgeEnabled);
      invalidateRenderedBanners();
      renderTextSetsEditor();
      renderBannerSetsView();
      renderTopAction();
    });
    badgeToggleRow.appendChild(badgeToggleLabel);
    badgeToggleRow.appendChild(badgeToggleBtn);
    card.appendChild(badgeToggleRow);

    if (set.badgeEnabled) {
      const badgeFields = [
        { key: "badgeTopText", label: "Top text" },
        { key: "badgeBottomText", label: "Bottom text" },
      ];
      const badgeFieldsRow = document.createElement("div");
      badgeFieldsRow.className = "badge-fields-row";
      badgeFields.forEach((field) => {
        const fieldWrap = document.createElement("div");
        fieldWrap.className = "text-set-field badge-field-col";
        const label = document.createElement("label");
        label.className = "field-label";
        label.textContent = `${field.label}:`;
        const textarea = document.createElement("textarea");
        textarea.className = "text-area";
        textarea.rows = 1;
        textarea.value = String(set[field.key] || "");
        textarea.addEventListener("input", (event) => {
          autoResizeTextarea(textarea);
          state.bannerTextSets[index][field.key] = event.target.value;
          invalidateRenderedBanners();
          renderBannerSetsView();
          renderTopAction();
        });
        fieldWrap.appendChild(label);
        fieldWrap.appendChild(textarea);
        badgeFieldsRow.appendChild(fieldWrap);
      });
      card.appendChild(badgeFieldsRow);

      const shiftWrap = document.createElement("div");
      shiftWrap.className = "badge-shift-wrap";
      const shiftXBlock = document.createElement("div");
      shiftXBlock.className = "shift-block";
      const shiftXLabel = document.createElement("label");
      shiftXLabel.className = "shift-label";
      shiftXLabel.textContent = "Badge X (%)";
      const shiftXInput = document.createElement("input");
      shiftXInput.type = "range";
      shiftXInput.className = "shift-slider";
      shiftXInput.min = "0";
      shiftXInput.max = "100";
      shiftXInput.step = "10";
      shiftXInput.value = String(Math.max(0, Math.min(100, Number(set.badgeShiftX) || 0)));
      applySliderFill(shiftXInput);
      shiftXInput.addEventListener("input", (event) => {
        state.bannerTextSets[index].badgeShiftX = Math.max(0, Math.min(100, Number(event.target.value) || 0));
        applySliderFill(shiftXInput);
        invalidateRenderedBanners();
        renderBannerSetsView();
        renderTopAction();
      });
      shiftXBlock.appendChild(shiftXLabel);
      shiftXBlock.appendChild(shiftXInput);

      const shiftYBlock = document.createElement("div");
      shiftYBlock.className = "shift-block";
      const shiftYLabel = document.createElement("label");
      shiftYLabel.className = "shift-label";
      shiftYLabel.textContent = "Badge Y (%)";
      const shiftYInput = document.createElement("input");
      shiftYInput.type = "range";
      shiftYInput.className = "shift-slider";
      shiftYInput.min = "0";
      shiftYInput.max = "100";
      shiftYInput.step = "10";
      shiftYInput.value = String(Math.max(0, Math.min(100, Number(set.badgeShiftY) || 0)));
      applySliderFill(shiftYInput);
      shiftYInput.addEventListener("input", (event) => {
        state.bannerTextSets[index].badgeShiftY = Math.max(0, Math.min(100, Number(event.target.value) || 0));
        applySliderFill(shiftYInput);
        invalidateRenderedBanners();
        renderBannerSetsView();
        renderTopAction();
      });
      shiftYBlock.appendChild(shiftYLabel);
      shiftYBlock.appendChild(shiftYInput);

      shiftWrap.appendChild(shiftXBlock);
      shiftWrap.appendChild(shiftYBlock);
      card.appendChild(shiftWrap);
    }

    const alignRow = document.createElement("div");
    alignRow.className = "text-align-row";
    const currentAlign = ["left", "center", "right"].includes(set.textAlign) ? set.textAlign : "left";
    TEXT_ALIGN_OPTIONS.forEach((optionDef) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "text-align-btn";
      if (currentAlign === optionDef.value) btn.classList.add("is-active");
      btn.setAttribute("aria-label", optionDef.alt);
      const icon = document.createElement("img");
      icon.className = "text-align-icon";
      icon.src = optionDef.icon;
      icon.alt = "";
      icon.setAttribute("aria-hidden", "true");
      btn.appendChild(icon);
      btn.addEventListener("click", () => {
        state.bannerTextSets[index].textAlign = optionDef.value;
        invalidateRenderedBanners();
        renderTextSetsEditor();
        renderBannerSetsView();
        renderTopAction();
      });
      alignRow.appendChild(btn);
    });
    card.appendChild(alignRow);

    textSetsWrapEl.appendChild(card);
  });

  requestAnimationFrame(() => refreshTextSetTextareaHeights());
  setTimeout(() => refreshTextSetTextareaHeights(), 120);
  setTimeout(() => refreshTextSetTextareaHeights(), 350);
}

function buildSetBannerMap() {
  const map = new Map();
  state.renderedBanners.forEach((item) => {
    const key = `${Number(item.text_set_index || 0)}:${item.size}`;
    map.set(key, item.url);
  });
  return map;
}

function makeSlot(size, url, isLoading, setIndex = 0) {
  const slot = document.createElement("div");
  const key = makeBannerPositionKey(setIndex, size);
  slot.className = `banner-slot ${BANNER_SIZES.find((s) => s.value === size)?.slotClass || ""}`;
  if (state.activeBannerPositionKey === key) slot.classList.add("is-active");
  if (state.bannerImageOverrides[key]) slot.classList.add("has-position-override");
  slot.setAttribute("tabindex", "0");
  slot.setAttribute("role", "button");
  slot.setAttribute("aria-label", `Edit image position for set ${setIndex + 1}, ${size}`);
  slot.addEventListener("click", () => setActiveBannerPosition(setIndex, size));
  slot.addEventListener("focus", () => setActiveBannerPosition(setIndex, size));
  slot.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setActiveBannerPosition(setIndex, size);
    }
  });
  if (url) {
    const img = document.createElement("img");
    img.src = url;
    img.alt = size;
    slot.appendChild(img);
  } else {
    const ph = document.createElement("div");
    ph.className = "banner-slot-placeholder";
    if (isLoading || !state.renderedBanners.length) {
      const label = document.createElement("span");
      label.className = "banner-slot-placeholder-label";
      if (state.bannerStage === "uncropping") {
        label.textContent = "Uncropping";
      } else if (state.bannerStage === "creating") {
        label.textContent = "Creating";
      } else {
        label.textContent = "Generation";
      }
      ph.appendChild(label);
      if (isLoading) {
        const dotsWrap = document.createElement("span");
        dotsWrap.className = "banner-slot-dots";
        for (let index = 1; index <= 3; index += 1) {
          const dot = document.createElement("span");
          dot.className = `dot dot-${index}`;
          dot.textContent = ".";
          dotsWrap.appendChild(dot);
        }
        ph.appendChild(dotsWrap);
      }
    } else {
      ph.textContent = "";
    }
    slot.appendChild(ph);
  }
  return slot;
}

function downloadSingleSet(setIndex) {
  const urls = state.renderedBanners
    .filter((item) => Number(item.text_set_index || 0) === setIndex)
    .map((item) => item.url)
    .filter(Boolean);
  if (!urls.length) return;
  createZipAndDownload(urls, `banners_set_${setIndex + 1}.zip`);
}

function renderBannerSetsView() {
  bannerSetsViewEl.innerHTML = "";
  const map = buildSetBannerMap();

  state.bannerTextSets.forEach((_, index) => {
    const wrap = document.createElement("section");
    wrap.className = "banner-set";

    const title = document.createElement("p");
    title.className = "banner-set-title";
    title.textContent = `SET ${index + 1}`;
    wrap.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "banner-set-grid";

    const left = document.createElement("div");
    left.className = "banner-col-left";
    left.appendChild(makeSlot("1200x1200", map.get(`${index}:1200x1200`), state.bannerRendering, index));
    left.appendChild(makeSlot("1200x628", map.get(`${index}:1200x628`), state.bannerRendering, index));

    const mid = document.createElement("div");
    mid.className = "banner-col-mid";
    mid.appendChild(makeSlot("1080x1920", map.get(`${index}:1080x1920`), state.bannerRendering, index));

    const right = document.createElement("div");
    right.className = "banner-col-right";
    right.appendChild(makeSlot("1200x1350", map.get(`${index}:1200x1350`), state.bannerRendering, index));

    const actions = document.createElement("div");
    actions.className = "banner-set-actions";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "banner-download-btn";
    btn.textContent = "Download";
    btn.disabled = !state.renderedBanners.some((item) => Number(item.text_set_index || 0) === index);
    btn.addEventListener("click", () => downloadSingleSet(index));
    actions.appendChild(btn);
    right.appendChild(actions);

    grid.appendChild(left);
    grid.appendChild(mid);
    grid.appendChild(right);
    wrap.appendChild(grid);
    bannerSetsViewEl.appendChild(wrap);
  });
}

async function createZipAndDownload(bannerUrls, fileName) {
  const response = await fetch("/api/create-banners-zip", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bannerUrls }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "ZIP creation failed");
  const zipUrl = payload.zip_url || "";
  if (!zipUrl) throw new Error("ZIP URL missing");

  const a = document.createElement("a");
  a.href = zipUrl;
  a.download = fileName || "banners.zip";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function downloadAllBanners() {
  const urls = state.renderedBanners.map((item) => item.url).filter(Boolean);
  if (!urls.length) {
    alert("CREATE BANNERS FIRST");
    return;
  }
  try {
    topActionBtn.disabled = true;
    await createZipAndDownload(urls, "banners_all.zip");
  } catch (error) {
    showError(error, "Could not download the banners.");
  } finally {
    renderTopAction();
  }
}

async function uploadCustomImage(file) {
  const formData = new FormData();
  formData.append("image", file, file.name || "upload.png");

  const response = await fetch("/api/upload-image", {
    method: "POST",
    credentials: "same-origin",
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Upload failed");
  return payload.image_local_url || "";
}

async function uploadCustomVideo(file) {
  const formData = new FormData();
  formData.append("video", file, file.name || "upload.mp4");

  const response = await fetch("/api/upload-video", {
    method: "POST",
    credentials: "same-origin",
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Upload failed");
  return {
    videoUrl: String(payload.video_local_url || "").trim(),
    libraryVideo: normalizeLibraryVideo(payload.library_video),
  };
}

async function generatePrompt() {
  if (state.selectedImageStyle === "edit") {
    await generateEditedSourceImage();
    return;
  }

  const selectedTransport = getSelectedTransport();
  if (!state.selectedCountry) {
    alert("PLEASE SELECT COUNTRY");
    return;
  }
  if (!selectedTransport) {
    alert("PLEASE SELECT VEHICLE");
    return;
  }
  const currentCarModel = selectedTransport.model;

  const previousImageUrl = state.imageUrl;
  state.generating = true;
  state.basePromptText = "";
  state.editPromptText = "";
  state.videoPromptText = "";
  state.videoRenderStatus = "No video yet.";
  state.videoResultUrl = "";
  state.imageUrl = "";
  state.renderedBanners = [];
  setSourceStatus("uploading");
  renderUiState();
  renderBannerSetsView();

  try {
    const response = await fetchWithTimeout("/api/generate-image", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service: IMAGE_SERVICE,
        style: getSelectedImageStyle().label,
        country: state.selectedCountry,
        transportLabel: selectedTransport.label,
        transportCode: selectedTransport.tariffCode,
        basicClass: selectedTransport.basicClass,
        vehicleModel: selectedTransport.model,
        vehicleType: selectedTransport.vehicleType,
        colorName: selectedTransport.colorName,
        composition: state.selectedComposition,
        modelDescription: state.heroDescription,
        situationDescription: state.situationDescription,
        carModel: currentCarModel,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Generation failed");

    state.imageUrl = payload.image_local_url || payload.image_url || "";
    state.bannerSourceImageUrl = state.imageUrl;
    state.basePromptText = payload.prompt || "";
    state.editPromptText = "";
    if (!state.imageUrl) throw new Error("No image returned");
    if (previousImageUrl && previousImageUrl !== state.imageUrl) {
      pushImageToHistory(previousImageUrl);
    }
    setSourceStatus("generated");
  } catch (error) {
    showError(error, "Something went wrong. Please try again.");
    setSourceStatus("failed");
  } finally {
    state.generating = false;
    renderUiState();
  }
}

async function generateEditedSourceImage() {
  if (!state.editSourceImageUrl) {
    alert("UPLOAD SOURCE IMAGE FIRST");
    return;
  }

  const previousImageUrl = state.imageUrl;
  state.generating = true;
  state.basePromptText = EDIT_CLEANUP_PROMPT;
  state.editPromptText = "";
  state.videoPromptText = "";
  state.videoRenderStatus = "No video yet.";
  state.videoResultUrl = "";
  state.imageUrl = "";
  invalidateRenderedBanners();
  setSourceStatus("uploading");
  renderUiState();
  renderBannerSetsView();

  try {
    const response = await fetchWithTimeout("/api/edit-image", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        imageUrl: state.editSourceImageUrl,
        editPrompt: EDIT_CLEANUP_PROMPT,
        aspectRatio: "3:2",
        country: state.selectedCountry,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Edit failed");
    const editedUrl = payload.image_local_url || "";
    if (!editedUrl) throw new Error("Edited image URL missing");
    if (previousImageUrl && previousImageUrl !== editedUrl) {
      pushImageToHistory(previousImageUrl);
    }
    state.imageUrl = editedUrl;
    state.bannerSourceImageUrl = editedUrl;
    setSourceStatus("generated");
  } catch (error) {
    showError(error, "Image editing failed. Please try again.");
    setSourceStatus("failed");
  } finally {
    state.generating = false;
    renderBannerSetsView();
    renderUiState();
  }
}

function buildRenderPayload() {
  const selectedLibraryImage = findLibraryImageByUrl(state.bannerSourceImageUrl);
  const bannerImageOverrides = Object.entries(state.bannerImageOverrides || {})
    .map(([key, values]) => {
      const parsed = parseBannerPositionKey(key);
      if (!parsed) return null;
      const normalized = normalizeImagePositionValues(values);
      return {
        textSetIndex: parsed.setIndex,
        size: parsed.size,
        imageScale: normalized.imageScalePercent / 100,
        imageShiftX: stepToShiftPx(normalized.imageShiftXStep),
        imageShiftY: -stepToShiftPx(normalized.imageShiftYStep),
      };
    })
    .filter(Boolean);
  return {
    imageUrl: state.bannerSourceImageUrl,
    bannerSourceUrl: selectedLibraryImage?.banner_source_url || "",
    country: state.selectedCountry,
    imageScale: (Number(state.imageScalePercent) || 100) / 100,
    imageShiftX: stepToShiftPx(Number(state.imageShiftXStep) || 0),
    // UX rule: moving Y slider right should move image up.
    imageShiftY: -stepToShiftPx(Number(state.imageShiftYStep) || 0),
    textSets: state.bannerTextSets.map((set) => ({
      title: String(set.title || "").trim(),
      subtitle: String(set.subtitle || "").trim(),
      disclaimer: String(set.disclaimer || "").trim(),
      textAlign: String(set.textAlign || "left").trim().toLowerCase(),
      badgeEnabled: Boolean(set.badgeEnabled),
      badgeTopText: String(set.badgeTopText || "").trim(),
      badgeBottomText: String(set.badgeBottomText || "").trim(),
      accentColor: resolveAccentColor(),
      badgeShiftX: Math.max(0, Math.min(100, Number(set.badgeShiftX) || 0)),
      badgeShiftY: Math.max(0, Math.min(100, Number(set.badgeShiftY) || 0)),
    })),
    layoutType: state.bannerLayout,
    sizes: ["1200x1200", "1200x1350", "1200x628", "1080x1920"],
    bannerImageOverrides,
  };
}

function scheduleBannerAutoRender() {
  if (bannerAutoRenderTimer) {
    clearTimeout(bannerAutoRenderTimer);
    bannerAutoRenderTimer = null;
  }
  if (!state.bannerSourceImageUrl || state.bannerRendering || !state.hasRenderedBanners) {
    return;
  }
  bannerAutoRenderTimer = setTimeout(() => {
    bannerAutoRenderTimer = null;
    if (!state.bannerSourceImageUrl || state.bannerRendering || !state.hasRenderedBanners) {
      return;
    }
    createBanners();
  }, BANNER_AUTO_RENDER_DEBOUNCE_MS);
}

async function createBanners() {
  if (!state.bannerSourceImageUrl) {
    alert("UPLOAD OR GENERATE IMAGE FIRST");
    return;
  }

  if (bannerAutoRenderTimer) {
    clearTimeout(bannerAutoRenderTimer);
    bannerAutoRenderTimer = null;
  }

  state.bannerRendering = true;
  state.bannerStage = "uncropping";
  state.renderedBanners = [];
  renderBannerSetsView();
  renderTopAction();
  renderBannersBtn.textContent = "Uncropping...";

  try {
    // Step 1: uncrop runs on backend before banners render.
    state.bannerStage = "uncropping";
    renderBannerSetsView();
    renderBannersBtn.textContent = "Uncropping...";

    // Step 2: banner composition.
    state.bannerStage = "creating";
    renderBannerSetsView();
    renderBannersBtn.textContent = "Creating...";

    const response = await fetch("/api/render-banners", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildRenderPayload()),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Render failed");
    state.renderedBanners = (payload.banners || []).filter((item) => item && item.url && item.size);
    state.hasRenderedBanners = state.renderedBanners.length > 0;
    upsertStateLibraryImage(payload.library_image);
  } catch (error) {
    showError(error, "Something went wrong. Please try again.");
  } finally {
    state.bannerRendering = false;
    state.bannerStage = "idle";
    renderBannersBtn.textContent = "Create Banners";
    renderBannerSetsView();
    renderTopAction();
  }
}

async function generateVideoPrompt() {
  const currentCarModel = getCurrentCarModel();
  if (!state.imageUrl) {
    alert("GENERATE OR UPLOAD IMAGE FIRST");
    return;
  }
  if (!currentCarModel) {
    alert("PLEASE SELECT VEHICLE");
    return;
  }

  state.videoGenerating = true;
  renderUiState();

  try {
    const response = await fetch("/api/generate-video-prompt", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        imageUrl: state.imageUrl,
        carModel: currentCarModel,
        colorName: "",
        basePrompt: state.basePromptText,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Video prompt generation failed");
    state.videoPromptText = String(payload.prompt || "").trim();
    if (!state.videoPromptText) {
      throw new Error("Empty video prompt returned");
    }
  } catch (error) {
    showError(error, "Video prompt generation failed. Please try again.");
  } finally {
    state.videoGenerating = false;
    renderUiState();
  }
}

async function ensureVideoPromptReady() {
  const current = String(state.videoPromptText || "").trim();
  if (current) return current;
  await generateVideoPrompt();
  return String(state.videoPromptText || "").trim();
}

async function generateVideoFromPrompt() {
  const currentCarModel = getCurrentCarModel();
  const selectedSavedVideo = findLibraryVideoByUrl(state.videoResultUrl);
  if (selectedSavedVideo) {
    state.videoRendering = true;
    state.videoRenderStatus = "Rebuilding titles on saved video...";
    renderUiState();
    try {
      const response = await fetch("/api/remix-video", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          videoUrl: selectedSavedVideo.video_url,
          headlines: state.videoHeadlines,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Video remix failed");
      state.videoResultUrl = String(payload.video_local_url || "").trim();
      state.videoRenderStatus = state.videoResultUrl ? "Video ready." : "Video remixed.";
      if (!state.videoResultUrl) {
        throw new Error("Video URL missing");
      }
      const savedVideo = normalizeLibraryVideo(payload.library_video);
      if (savedVideo) {
        state.videoLibrary = [savedVideo, ...state.videoLibrary.filter((item) => item.video_url !== savedVideo.video_url)];
      }
    } catch (error) {
      state.videoRenderStatus = "Video generation failed.";
      showError(error, "Video generation failed. Please try again.");
    } finally {
      state.videoRendering = false;
      renderUiState();
    }
    return;
  }

  if (!state.imageUrl) {
    alert("GENERATE OR UPLOAD IMAGE FIRST");
    return;
  }
  if (!currentCarModel) {
    alert("PLEASE ENTER CAR MODEL");
    return;
  }

  const prompt = await ensureVideoPromptReady();
  if (!prompt) {
    alert("GENERATE VIDEO PROMPT FIRST");
    return;
  }

  state.videoRendering = true;
  state.videoRenderStatus = "Submitting to Kling 3.0...";
  state.videoResultUrl = "";
  renderUiState();

  try {
    const response = await fetch("/api/generate-video", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        imageUrl: state.imageUrl,
        prompt,
        headlines: state.videoHeadlines,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Video generation failed");
    state.videoResultUrl = String(payload.video_local_url || payload.video_url || "").trim();
    state.videoRenderStatus = state.videoResultUrl ? "Video ready." : "Video generated.";
    if (!state.videoResultUrl) {
      throw new Error("Video URL missing");
    }
    const savedVideo = normalizeLibraryVideo(payload.library_video);
    if (savedVideo) {
      state.videoLibrary = [savedVideo, ...state.videoLibrary.filter((item) => item.video_url !== savedVideo.video_url)];
    }
  } catch (error) {
    state.videoRenderStatus = "Video generation failed.";
    showError(error, "Video generation failed. Please try again.");
  } finally {
    state.videoRendering = false;
    renderUiState();
  }
}

function setActiveTab(tab) {
  if (tab === "video" && !VIDEO_TAB_ENABLED) {
    state.activeTab = "image";
    renderUiState();
    return;
  }
  state.activeTab = tab;
  renderUiState();
  if (tab === "banner") {
    // Banner editor is hidden in the other tab, so recalc after it becomes visible.
    requestAnimationFrame(() => {
      refreshTextSetTextareaHeights();
      requestAnimationFrame(() => refreshTextSetTextareaHeights());
    });
    setTimeout(() => refreshTextSetTextareaHeights(), 80);
  }
}

tabImageEl.addEventListener("click", () => setActiveTab("image"));
tabBannerEl.addEventListener("click", () => setActiveTab("banner"));
if (tabVideoEl) {
  tabVideoEl.addEventListener("click", () => setActiveTab("video"));
}

countryToggleEl.addEventListener("click", () => {
  state.countryMenuOpen = !state.countryMenuOpen;
  state.transportMenuOpen = false;
  state.styleMenuOpen = false;
  renderImageControls();
});

if (styleToggleEl) {
  styleToggleEl.addEventListener("click", () => {
    state.styleMenuOpen = !state.styleMenuOpen;
    state.countryMenuOpen = false;
    state.transportMenuOpen = false;
    renderImageControls();
  });
}

transportToggleEl.addEventListener("click", () => {
  if (!state.selectedCountry) return;
  state.transportMenuOpen = !state.transportMenuOpen;
  state.countryMenuOpen = false;
  state.styleMenuOpen = false;
  renderImageControls();
});

document.addEventListener("click", (event) => {
  if (!countryToggleEl || !countryMenuEl || !transportToggleEl || !transportMenuEl) return;
  const target = event.target;
  if (
    target instanceof Node &&
    (countryToggleEl.contains(target) ||
      countryMenuEl.contains(target) ||
      styleToggleEl?.contains(target) ||
      styleMenuEl?.contains(target) ||
      transportToggleEl.contains(target) ||
      transportMenuEl.contains(target))
  ) {
    return;
  }
  if (state.countryMenuOpen || state.transportMenuOpen || state.styleMenuOpen || state.sourceLibraryCountryMenuOpen) {
    state.countryMenuOpen = false;
    state.transportMenuOpen = false;
    state.styleMenuOpen = false;
    state.sourceLibraryCountryMenuOpen = false;
    renderImageControls();
    renderSourceLibrary();
  }
});

heroDescriptionInputEl.addEventListener("input", (event) => {
  state.heroDescription = event.target.value;
});

situationDescriptionInputEl.addEventListener("input", (event) => {
  state.situationDescription = event.target.value;
});

if (bannerAccentColorInput) {
  bannerAccentColorInput.addEventListener("input", (event) => {
    state.bannerAccentPreset = "custom";
    state.bannerAccentCustomColor = event.target.value || ACCENT_PRESET_VALUES.lime;
    invalidateRenderedBanners();
    renderLayoutTypes();
    renderBannerSetsView();
    renderTopAction();
  });
}

generateBtn.addEventListener("click", generatePrompt);
if (generateVideoBtnEl) {
  generateVideoBtnEl.addEventListener("click", generateVideoFromPrompt);
}

async function applyQuickImageEdit(editPrompt, referenceImageUrl = "") {
  if (!state.imageUrl) {
    alert("GENERATE IMAGE FIRST");
    return;
  }
  const resolvedReferenceImageUrl = referenceImageUrl
    ? new URL(referenceImageUrl, window.location.href).href
    : "";
  try {
    state.generating = true;
    renderUiState();
    const response = await fetchWithTimeout("/api/edit-image", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        imageUrl: state.imageUrl,
        editPrompt,
        referenceImageUrl: resolvedReferenceImageUrl,
        country: state.selectedCountry,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Edit failed");
    const editedUrl = payload.image_local_url || "";
    if (!editedUrl) throw new Error("Edited image URL missing");
    if (state.imageUrl && state.imageUrl !== editedUrl) {
      pushImageToHistory(state.imageUrl);
    }
    state.imageUrl = editedUrl;
    state.bannerSourceImageUrl = editedUrl;
    state.editPromptText = "";
    state.videoPromptText = "";
    state.videoRenderStatus = "No video yet.";
    state.videoResultUrl = "";
    invalidateRenderedBanners();
    setSourceStatus("generated");
    renderBannerSetsView();
  } catch (error) {
    showError(error, "Image editing failed. Please try again.");
  } finally {
    state.generating = false;
    renderUiState();
  }
}

if (seatbeltActionBtn) {
  seatbeltActionBtn.addEventListener("click", () => {
    applyQuickImageEdit(
      "Edit the current image so every visible person inside the car is wearing a clearly visible, physically correct seat belt. Preserve the same people, vehicle, composition, camera angle, clothing, lighting, location, and documentary photo style. Do not add logos, app UI, text, or watermarks."
    );
  });
}

if (brandingActionBtn) {
  brandingActionBtn.addEventListener("click", () => {
    const referenceImageUrl = getBrandingReferenceUrl();
    if (!referenceImageUrl) {
      alert("BRANDING IS DISABLED FOR THIS COUNTRY OR TARIFF");
      return;
    }
    applyQuickImageEdit(
      "Use the second image as the exact vehicle-branding reference. Apply realistic Yango car branding decals to the visible exterior panels of the car in the current image: the red side panel, white YANGO wordmark, black app-download block in the reference language, and small checkered marks. Match the reference layout, scale, perspective, curvature, reflections, and surface lighting so it looks physically printed on the same car. Preserve the same car, people, scene, composition, lighting, and photo realism. Do not brand motorcycles, tuk-tuks, UAE scenes, or business/premium cars. Do not add unrelated text, app UI, or watermarks.",
      referenceImageUrl
    );
  });
}

if (removeBackgroundPeopleActionBtn) {
  removeBackgroundPeopleActionBtn.addEventListener("click", () => {
    applyQuickImageEdit(
      "Edit the current image to remove all non-essential background people and crowds. Preserve the main character or main characters, the vehicle, composition, camera angle, clothing, lighting, location, and documentary photo realism. Reconstruct the background naturally with matching architecture, pavement, shadows, reflections, and depth of field. Do not remove the driver or passenger if they are part of the main ride-hailing story. Do not add logos, app UI, text, or watermarks."
    );
  });
}

promptApplyBtn.addEventListener("click", () => {
  (async () => {
    const editPrompt = state.editPromptText.trim();
    if (!state.imageUrl) {
      alert("GENERATE IMAGE FIRST");
      return;
    }

    try {
      promptApplyBtn.disabled = true;
      state.generating = true;
      renderUiState();
      let response;
      if (!editPrompt) {
        if (!state.basePromptText.trim()) {
          throw new Error("ENTER EDIT PROMPT OR GENERATE BASE IMAGE FIRST");
        }
        response = await fetchWithTimeout("/api/regenerate-image", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: state.basePromptText,
            country: state.selectedCountry,
          }),
        });
      } else {
        response = await fetchWithTimeout("/api/edit-image", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            imageUrl: state.imageUrl,
            editPrompt,
            country: state.selectedCountry,
          }),
        });
      }
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Edit failed");
      const editedUrl = payload.image_local_url || "";
      if (!editedUrl) throw new Error("Edited image URL missing");
      if (state.imageUrl && state.imageUrl !== editedUrl) {
        pushImageToHistory(state.imageUrl);
      }
      state.imageUrl = editedUrl;
      state.bannerSourceImageUrl = editedUrl;
      state.editPromptText = "";
      state.videoPromptText = "";
      state.videoRenderStatus = "No video yet.";
      state.videoResultUrl = "";
      invalidateRenderedBanners();
      setSourceStatus("generated");
      renderBannerSetsView();
    } catch (error) {
      showError(error, "Image editing failed. Please try again.");
    } finally {
      state.generating = false;
      promptApplyBtn.disabled = false;
      renderUiState();
    }
  })();
});
renderBannersBtn.addEventListener("click", createBanners);

if (imageShiftXEl) {
  imageShiftXEl.addEventListener("input", (event) => {
    const hadRenderedBanners = state.hasRenderedBanners;
    updateActiveImagePosition({ imageShiftXStep: clampShiftStep(Number(event.target.value) || 0) });
    markImagePositionChanged(hadRenderedBanners);
  });
}

if (imageScaleEl) {
  imageScaleEl.addEventListener("input", (event) => {
    const hadRenderedBanners = state.hasRenderedBanners;
    const raw = Number(event.target.value);
    if (!Number.isFinite(raw)) {
      updateActiveImagePosition({ imageScalePercent: IMAGE_SCALE_MIN });
    } else {
      const clamped = Math.max(IMAGE_SCALE_MIN, Math.min(IMAGE_SCALE_MAX, raw));
      const snapped = Math.round((clamped - IMAGE_SCALE_MIN) / IMAGE_SCALE_STEP) * IMAGE_SCALE_STEP + IMAGE_SCALE_MIN;
      updateActiveImagePosition({ imageScalePercent: Math.max(IMAGE_SCALE_MIN, Math.min(IMAGE_SCALE_MAX, snapped)) });
    }
    markImagePositionChanged(hadRenderedBanners);
  });
}

if (imageShiftYEl) {
  imageShiftYEl.addEventListener("input", (event) => {
    const hadRenderedBanners = state.hasRenderedBanners;
    updateActiveImagePosition({ imageShiftYStep: clampShiftStep(Number(event.target.value) || 0) });
    markImagePositionChanged(hadRenderedBanners);
  });
}

if (resetBannerShiftBtnEl) {
  resetBannerShiftBtnEl.addEventListener("click", () => {
    const hadRenderedBanners = state.hasRenderedBanners;
    resetActiveBannerPosition();
    markImagePositionChanged(hadRenderedBanners);
  });
}

if (useGlobalShiftBtnEl) {
  useGlobalShiftBtnEl.addEventListener("click", () => {
    state.activeBannerPositionKey = "";
    renderShiftControls();
    renderBannerSetsView();
  });
}

uploadImageBtnEl.addEventListener("click", () => uploadImageInputEl.click());
uploadImageInputEl.addEventListener("change", async (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  setSourceStatus("uploading");
  try {
    const localUrl = await uploadCustomImage(file);
    if (!localUrl) throw new Error("Upload failed");
    if (state.imageUrl && state.imageUrl !== localUrl) {
      pushImageToHistory(state.imageUrl);
    }
    state.imageUrl = localUrl;
    state.bannerSourceImageUrl = localUrl;
    state.basePromptText = "";
    state.editPromptText = "";
    state.videoPromptText = "";
    state.videoRenderStatus = "No video yet.";
    state.videoResultUrl = "";
    invalidateRenderedBanners();
    setSourceStatus("uploaded");
    renderBannerSetsView();
    renderUiState();
  } catch (error) {
    setSourceStatus("failed");
    showError(error, "Upload failed. Please try another file.");
  } finally {
    uploadImageInputEl.value = "";
  }
});

if (editUploadImageBtnEl && editUploadImageInputEl) {
  editUploadImageBtnEl.addEventListener("click", () => editUploadImageInputEl.click());
  editUploadImageInputEl.addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    state.editSourceStatus = "uploading";
    renderEditSource();
    renderUiState();
    try {
      const localUrl = await uploadCustomImage(file);
      if (!localUrl) throw new Error("Upload failed");
      state.editSourceImageUrl = localUrl;
      state.editSourceStatus = "uploaded";
      state.imageUrl = "";
      state.bannerSourceImageUrl = "";
      state.basePromptText = "";
      state.editPromptText = "";
      state.videoPromptText = "";
      state.videoRenderStatus = "No video yet.";
      state.videoResultUrl = "";
      invalidateRenderedBanners();
      renderBannerSetsView();
      renderUiState();
    } catch (error) {
      state.editSourceStatus = "failed";
      showError(error, "Upload failed. Please try another file.");
      renderUiState();
    } finally {
      editUploadImageInputEl.value = "";
    }
  });
}

if (editClearSourceBtnEl) {
  editClearSourceBtnEl.addEventListener("click", () => {
    state.editSourceImageUrl = "";
    state.editSourceStatus = "none";
    if (state.selectedImageStyle === "edit") {
      state.imageUrl = "";
      state.bannerSourceImageUrl = "";
      invalidateRenderedBanners();
      renderBannerSetsView();
    }
    renderUiState();
  });
}

if (uploadVideoBtnEl && uploadVideoInputEl) {
  uploadVideoBtnEl.addEventListener("click", () => uploadVideoInputEl.click());
  uploadVideoInputEl.addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    if (videoSourceStatusEl) {
      videoSourceStatusEl.textContent = SOURCE_STATUS.uploading;
    }
    try {
      const payload = await uploadCustomVideo(file);
      if (!payload.videoUrl) {
        throw new Error("Upload failed");
      }
      state.videoResultUrl = payload.videoUrl;
      state.videoRenderStatus = "Uploaded video ready for titles.";
      if (payload.libraryVideo) {
        state.videoLibrary = [
          payload.libraryVideo,
          ...state.videoLibrary.filter((item) => item.video_url !== payload.libraryVideo.video_url),
        ];
      }
      if (videoSourceStatusEl) {
        videoSourceStatusEl.textContent = SOURCE_STATUS.uploaded;
      }
      renderUiState();
    } catch (error) {
      if (videoSourceStatusEl) {
        videoSourceStatusEl.textContent = SOURCE_STATUS.failed;
      }
      showError(error, "Upload failed. Please try another file.");
    } finally {
      uploadVideoInputEl.value = "";
    }
  });
}

addTextSetBtn.addEventListener("click", () => {
  const sourceIndex = state.bannerTextSets.length - 1;
  const sourceSet =
    state.bannerTextSets.length > 0
      ? state.bannerTextSets[state.bannerTextSets.length - 1]
      : {
          title: "Drive with comfort every day",
          subtitle: "Book your car in seconds and enjoy premium routes.",
          disclaimer: "Terms and conditions apply",
          badgeEnabled: false,
          badgeTopText: "From",
          badgeBottomText: "65 AED",
          badgeShiftX: 0,
          badgeShiftY: 0,
        };

  const nextSetIndex = state.bannerTextSets.length;
  state.bannerTextSets.push({
    title: String(sourceSet.title || ""),
    subtitle: String(sourceSet.subtitle || ""),
    disclaimer: String(sourceSet.disclaimer || ""),
    textAlign: String(sourceSet.textAlign || "left"),
    badgeEnabled: Boolean(sourceSet.badgeEnabled),
    badgeTopText: String(sourceSet.badgeTopText || "From"),
    badgeBottomText: String(sourceSet.badgeBottomText || "65 AED"),
    badgeShiftX: Math.max(0, Math.min(100, Number(sourceSet.badgeShiftX) || 0)),
    badgeShiftY: Math.max(0, Math.min(100, Number(sourceSet.badgeShiftY) || 0)),
  });
  if (sourceIndex >= 0) {
    copyBannerImageOverridesToSet(sourceIndex, nextSetIndex);
  }
  invalidateRenderedBanners();
  renderTextSetsEditor();
  renderBannerSetsView();
  renderTopAction();
});

topActionBtn.addEventListener("click", async () => {
  if (state.activeTab === "image") {
    const copyValue = state.basePromptText.trim() || state.imageUrl.trim();
    if (!copyValue) return;
    try {
      await navigator.clipboard.writeText(copyValue);
      topActionBtn.textContent = "Copied";
      setTimeout(renderTopAction, 1000);
    } catch (_e) {
      topActionBtn.textContent = "Failed";
      setTimeout(renderTopAction, 1000);
    }
    return;
  }

  if (state.activeTab === "video") {
    const videoUrl = state.videoResultUrl.trim();
    if (!videoUrl) return;
    try {
      window.open(videoUrl, "_blank", "noopener,noreferrer");
      topActionBtn.textContent = "Opening";
      setTimeout(renderTopAction, 1000);
    } catch (_e) {
      topActionBtn.textContent = "Failed";
      setTimeout(renderTopAction, 1000);
    }
    return;
  }

  await downloadAllBanners();
});

if (sourceLibraryToggleEl) {
  sourceLibraryToggleEl.addEventListener("click", () => {
    if (!state.imageLibrary.length) return;
    state.sourceLibraryOpen = !state.sourceLibraryOpen;
    if (!state.sourceLibraryOpen) {
      state.sourceLibraryCountryMenuOpen = false;
    }
    renderUiState();
  });
}

if (videoLibraryToggleEl) {
  videoLibraryToggleEl.addEventListener("click", () => {
    if (!state.videoLibrary.length) return;
    state.videoLibraryOpen = !state.videoLibraryOpen;
    renderUiState();
  });
}

if (clearSourceBtnEl) {
  clearSourceBtnEl.addEventListener("click", () => {
    state.bannerSourceImageUrl = "";
    invalidateRenderedBanners();
    setSourceStatus("none");
    renderBannerSetsView();
    renderUiState();
  });
}

promptInputEl.value = state.editPromptText;
setSourceStatus("none");
renderImageControls();
renderLayoutTypes();
renderShiftControls();
renderTextSetsEditor();
renderBannerSetsView();
renderUiState();
fetchVehicleData();
fetchImageLibrary();
fetchVideoLibrary();

window.addEventListener("resize", () => {
  if (state.activeTab === "banner") {
    refreshTextSetTextareaHeights();
  }
});

if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(() => {
    refreshTextSetTextareaHeights();
    setTimeout(() => refreshTextSetTextareaHeights(), 150);
  });
}

promptInputEl.addEventListener("input", (event) => {
  state.editPromptText = event.target.value;
});

[
  [videoHeadline1El, 0],
  [videoHeadline2El, 1],
  [videoHeadline3El, 2],
].forEach(([input, index]) => {
  if (!input) return;
  input.addEventListener("input", (event) => {
    state.videoHeadlines[index] = event.target.value;
  });
});

if (promptBackBtn) {
  promptBackBtn.addEventListener("click", () => {
    if (!state.imageHistory.length) return;
    const previous = state.imageHistory.pop();
    if (!previous) return;
    state.imageUrl = previous;
    state.bannerSourceImageUrl = previous;
    state.editPromptText = "";
    state.videoPromptText = "";
    state.videoRenderStatus = "No video yet.";
    state.videoResultUrl = "";
    invalidateRenderedBanners();
    setSourceStatusForImage(findLibraryImageByUrl(previous));
    renderBannerSetsView();
    renderUiState();
  });
}
