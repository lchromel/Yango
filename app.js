const PRESET_COLORS = [
  { label: "Black", hex: "#000000" },
  { label: "White", hex: "#e5e5e5" },
  { label: "Silver", hex: "#bdbdbd" },
  { label: "Dark Silver", hex: "#98a3bd" },
  { label: "Red", hex: "#c40606" },
  { label: "Custom", hex: "#97a56e", custom: true },
];

const ANGLE_PRESETS = [
  { label: "Front 3/4" },
  { label: "Rear 3/4" },
  { label: "Front 3/4 Low Angle" },
  { label: "Rear 3/4 Low Angle" },
  { label: "Clean Side Profile" },
  { label: "Centered Front Shot" },
  { label: "Rear Light Hero Shot" },
  { label: "Dynamic Tracking Shot" },
];

const CUSTOM_CAR_OPTION = "__custom__";
const TOP_RENTAL_CARS_DUBAI = [
  "Nissan Patrol",
  "Toyota Land Cruiser Prado",
  "Toyota Land Cruiser",
  "Nissan Sunny",
  "Nissan Altima",
  "Nissan X-Trail",
  "Toyota Camry",
  "Kia Sportage",
  "Hyundai Creta",
  "Mitsubishi Pajero",
  "Range Rover Sport",
  "Mercedes-Benz G63 AMG",
  "Mercedes-Benz C200",
  "BMW 5 Series",
  "BMW M4",
  "Porsche 911",
  "Porsche Cayenne",
  "Ford Mustang",
  "Chevrolet Camaro",
  "Lamborghini Huracan",
];

const BANNER_LAYOUTS = [
  { label: "Photo", value: "photo", disabled: false },
  { label: "Black", value: "black", disabled: true },
  { label: "Red", value: "master-red", disabled: true },
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

const IMAGE_SHIFT_STEP_COUNT = 4;
const IMAGE_SHIFT_MAX_PX = 150;
const IMAGE_SHIFT_ONE_STEP_PX = IMAGE_SHIFT_MAX_PX / IMAGE_SHIFT_STEP_COUNT;
const IMAGE_SCALE_MIN = 100;
const IMAGE_SCALE_MAX = 150;
const IMAGE_SCALE_STEP = 3;
const BANNER_AUTO_RENDER_DEBOUNCE_MS = 550;
const CUSTOM_ACCENT_TRIGGER_WINDOW_MS = 550;
const CUSTOM_ACCENT_TRIGGER_TAP_COUNT = 3;
const ACCENT_PRESET_VALUES = {
  lime: "#E3FF74",
  red: "#FF1A1A",
};

const state = {
  selectedCarModel: "",
  customCarModel: "",
  carMenuOpen: false,
  colorHex: "#e5e5e5",
  colorLabel: "White",
  selectedPreset: "White",
  selectedAngle: "Front 3/4",
  basePromptText: "",
  editPromptText: "",
  editSuggestions: [],
  imageHistory: [],
  imageLibrary: [],
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
};

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

const carModelToggleEl = document.getElementById("carModelToggle");
const carModelDisplayEl = document.getElementById("carModelDisplay");
const carModelChevronIconEl = document.getElementById("carModelChevronIcon");
const carModelMenuEl = document.getElementById("carModelMenu");
const carModelCustomWrapEl = document.getElementById("carModelCustomWrap");
const carModelCustomInputEl = document.getElementById("carModelCustomInput");
const colorNameEl = document.getElementById("colorName");
const presetColorsEl = document.getElementById("presetColors");
const angleRowEl = document.getElementById("angleRow");
const customColorInput = document.getElementById("customColorInput");
const bannerAccentColorInput = document.getElementById("bannerAccentColorInput");
const generateBtn = document.getElementById("generateBtn");

const loaderEl = document.getElementById("loader");
const loaderLabelEl = document.getElementById("loaderLabel");
const imagePreviewFrameEl = document.getElementById("imagePreviewFrame");
const resultImageEl = document.getElementById("resultImage");
const promptInputEl = document.getElementById("promptInput");
const promptBackBtn = document.getElementById("promptBackBtn");
const promptApplyBtn = document.getElementById("promptApplyBtn");
const promptRowEl = document.querySelector(".prompt-row");
const promptSuggestionsEl = document.getElementById("promptSuggestions");
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

function findLibraryVideoByUrl(url) {
  const target = String(url || "").trim();
  if (!target) return null;
  return state.videoLibrary.find((item) => item.video_url === target) || null;
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
  if (state.selectedCarModel === CUSTOM_CAR_OPTION) {
    return state.customCarModel.trim();
  }
  return state.selectedCarModel.trim();
}

function applySelectedImage(record, options = {}) {
  const image = normalizeLibraryImage(record);
  if (!image) return;
  const { closeLibrary = true } = options;
  state.bannerSourceImageUrl = image.image_url;
  invalidateRenderedBanners();
  if (closeLibrary) {
    state.sourceLibraryOpen = false;
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
    if (state.bannerSourceImageUrl === targetUrl) {
      state.bannerSourceImageUrl = "";
      invalidateRenderedBanners();
      setSourceStatus("none");
      renderBannerSetsView();
    }
    renderUiState();
  } catch (error) {
    alert(`ERROR: ${error.message || "DELETE FAILED"}`);
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
    alert(`ERROR: ${error.message || "DELETE FAILED"}`);
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

  state.imageLibrary.forEach((item) => {
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
    sourceLibraryEl.appendChild(card);
  });
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

function renderCarModelControl() {
  const selectedLabel =
    state.selectedCarModel === CUSTOM_CAR_OPTION
      ? "Enter your own"
      : state.selectedCarModel || "Select a car model";
  carModelDisplayEl.textContent = selectedLabel;

  carModelToggleEl.setAttribute("aria-expanded", state.carMenuOpen ? "true" : "false");
  if (carModelChevronIconEl) {
    carModelChevronIconEl.src = state.carMenuOpen
      ? "./assets/icons/ChevronUpM.svg"
      : "./assets/icons/ChevronDownM.svg";
  }
  carModelMenuEl.classList.toggle("hidden", !state.carMenuOpen);
  carModelCustomWrapEl.classList.toggle("hidden", state.selectedCarModel !== CUSTOM_CAR_OPTION);
  if (state.selectedCarModel === CUSTOM_CAR_OPTION) {
    carModelCustomInputEl.value = state.customCarModel;
  }

  carModelMenuEl.innerHTML = "";
  const items = [
    { label: "Enter your own", value: CUSTOM_CAR_OPTION },
    ...TOP_RENTAL_CARS_DUBAI.map((model) => ({ label: model, value: model })),
  ];
  items.forEach((item) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "car-model-option";
    option.textContent = item.label;
    if (state.selectedCarModel === item.value) {
      option.classList.add("is-active");
    }
    option.addEventListener("click", () => {
      state.selectedCarModel = item.value;
      state.carMenuOpen = false;
      renderCarModelControl();
      if (item.value === CUSTOM_CAR_OPTION) {
        setTimeout(() => carModelCustomInputEl.focus(), 0);
      }
    });
    carModelMenuEl.appendChild(option);
  });
}

function renderTabs() {
  const isImageTab = state.activeTab === "image";
  const isBannerTab = state.activeTab === "banner";
  const isVideoTab = state.activeTab === "video";
  tabImageEl.classList.toggle("is-active", isImageTab);
  tabBannerEl.classList.toggle("is-active", isBannerTab);
  if (tabVideoEl) {
    tabVideoEl.classList.toggle("is-active", isVideoTab);
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
  generateBtn.disabled = state.generating;
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
  imagePreviewFrameEl.classList.toggle("hidden", !state.imageUrl);
  resultImageEl.src = state.imageUrl || "";
  promptRowEl.classList.toggle("hidden", !state.imageUrl);
  if (promptBackBtn) {
    promptBackBtn.disabled = state.generating || !state.imageHistory.length;
  }
  if (promptSuggestionsEl) {
    promptSuggestionsEl.classList.toggle("hidden", !state.imageUrl || !state.editSuggestions.length);
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

function renderPromptSuggestions() {
  if (!promptSuggestionsEl) return;
  promptSuggestionsEl.innerHTML = "";
  state.editSuggestions.forEach((text) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "prompt-suggestion-chip";
    chip.textContent = text;
    chip.addEventListener("click", () => {
      const normalized = String(text || "").trim().replace(/\s+/g, " ").replace(/[.]+$/g, "");
      state.editPromptText = [
        `Add ${normalized}.`,
        "Remove any sense of car motion.",
        "Keep the original composition and car position unchanged.",
      ].join(" ");
      renderUiState();
      promptInputEl.focus();
    });
    promptSuggestionsEl.appendChild(chip);
  });
}

function renderColors() {
  presetColorsEl.innerHTML = "";
  PRESET_COLORS.forEach((preset) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "swatch";
    if (preset.custom) btn.classList.add("is-picker");
    if (state.selectedPreset === preset.label) btn.classList.add("is-active");

    const core = document.createElement("div");
    core.className = "swatch-core";
    if (!preset.custom) {
      core.style.background = preset.hex;
    }
    btn.appendChild(core);
    if (preset.custom) {
      const glyph = document.createElement("span");
      glyph.className = "swatch-picker-glyph";
      glyph.textContent = "⌄";
      btn.appendChild(glyph);
    }

    btn.addEventListener("click", () => {
      if (preset.custom) {
        customColorInput.click();
        return;
      }
      state.colorHex = preset.hex;
      state.colorLabel = preset.label;
      state.selectedPreset = preset.label;
      colorNameEl.textContent = state.colorLabel;
      renderColors();
    });

    presetColorsEl.appendChild(btn);
  });
}

function renderAngles() {
  angleRowEl.innerHTML = "";
  ANGLE_PRESETS.forEach((preset) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "angle-chip";
    chip.textContent = preset.label;
    if (state.selectedAngle === preset.label) chip.classList.add("is-active");
    chip.addEventListener("click", () => {
      state.selectedAngle = preset.label;
      renderAngles();
    });
    angleRowEl.appendChild(chip);
  });
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
  if (imageScaleEl) imageScaleEl.value = String(state.imageScalePercent);
  if (imageShiftXEl) imageShiftXEl.value = String(state.imageShiftXStep);
  if (imageShiftYEl) imageShiftYEl.value = String(state.imageShiftYStep);
  applySliderFill(imageScaleEl);
  applySliderFill(imageShiftXEl);
  applySliderFill(imageShiftYEl);
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
        invalidateRenderedBanners();
        renderTextSetsEditor();
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

function makeSlot(size, url, isLoading) {
  const slot = document.createElement("div");
  slot.className = `banner-slot ${BANNER_SIZES.find((s) => s.value === size)?.slotClass || ""}`;
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
    left.appendChild(makeSlot("1200x1200", map.get(`${index}:1200x1200`), state.bannerRendering));
    left.appendChild(makeSlot("1200x628", map.get(`${index}:1200x628`), state.bannerRendering));

    const mid = document.createElement("div");
    mid.className = "banner-col-mid";
    mid.appendChild(makeSlot("1080x1920", map.get(`${index}:1080x1920`), state.bannerRendering));

    const right = document.createElement("div");
    right.className = "banner-col-right";
    right.appendChild(makeSlot("1200x1350", map.get(`${index}:1200x1350`), state.bannerRendering));

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
    alert(`ERROR: ${error.message || "DOWNLOAD FAILED"}`);
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
  const currentCarModel = getCurrentCarModel();
  if (!currentCarModel) {
    alert("PLEASE ENTER CAR MODEL");
    return;
  }

  const previousImageUrl = state.imageUrl;
  state.generating = true;
  state.basePromptText = "";
  state.editPromptText = "";
  state.editSuggestions = [];
  state.videoPromptText = "";
  state.videoRenderStatus = "No video yet.";
  state.videoResultUrl = "";
  state.imageUrl = "";
  state.renderedBanners = [];
  setSourceStatus("uploading");
  renderPromptSuggestions();
  renderUiState();
  renderBannerSetsView();

  try {
    const response = await fetch("/api/generate-image", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        carModel: currentCarModel,
        colorHex: state.colorHex,
        colorName: state.colorLabel,
        preferredAngle: state.selectedAngle,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Generation failed");

    state.imageUrl = payload.image_local_url || payload.image_url || "";
    state.bannerSourceImageUrl = state.imageUrl;
    state.basePromptText = payload.prompt || "";
    state.editPromptText = "";
    state.editSuggestions = Array.isArray(payload.edit_suggestions)
      ? payload.edit_suggestions.map((item) => String(item || "").trim()).filter(Boolean)
      : [];
    if (!state.imageUrl) throw new Error("No image returned");
    if (previousImageUrl && previousImageUrl !== state.imageUrl) {
      pushImageToHistory(previousImageUrl);
    }
    setSourceStatus("generated");
  } catch (error) {
    alert(`ERROR: ${error.message || "UNKNOWN ERROR"}`);
    setSourceStatus("failed");
  } finally {
    state.generating = false;
    renderPromptSuggestions();
    renderUiState();
  }
}

function buildRenderPayload() {
  return {
    imageUrl: state.bannerSourceImageUrl,
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
    layoutType: "photo",
    sizes: ["1200x1200", "1200x1350", "1200x628", "1080x1920"],
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
  } catch (error) {
    alert(`ERROR: ${error.message || "UNKNOWN ERROR"}`);
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
    alert("PLEASE ENTER CAR MODEL");
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
        colorName: state.colorLabel,
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
    alert(`ERROR: ${error.message || "VIDEO PROMPT FAILED"}`);
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
      alert(`ERROR: ${error.message || "VIDEO GENERATION FAILED"}`);
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
    alert(`ERROR: ${error.message || "VIDEO GENERATION FAILED"}`);
  } finally {
    state.videoRendering = false;
    renderUiState();
  }
}

function setActiveTab(tab) {
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

carModelToggleEl.addEventListener("click", () => {
  state.carMenuOpen = !state.carMenuOpen;
  renderCarModelControl();
});

carModelCustomInputEl.addEventListener("input", (event) => {
  state.customCarModel = event.target.value;
});

document.addEventListener("click", (event) => {
  if (!carModelToggleEl || !carModelMenuEl || !carModelCustomWrapEl) return;
  const target = event.target;
  if (
    target instanceof Node &&
    (carModelToggleEl.contains(target) || carModelMenuEl.contains(target) || carModelCustomWrapEl.contains(target))
  ) {
    return;
  }
  if (state.carMenuOpen) {
    state.carMenuOpen = false;
    renderCarModelControl();
  }
});

customColorInput.addEventListener("input", (event) => {
  state.colorHex = event.target.value;
  state.colorLabel = "Custom";
  state.selectedPreset = "Custom";
  colorNameEl.textContent = state.colorLabel;
  renderColors();
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
        response = await fetch("/api/regenerate-image", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: state.basePromptText,
          }),
        });
      } else {
        response = await fetch("/api/edit-image", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            imageUrl: state.imageUrl,
            editPrompt,
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
      alert(`ERROR: ${error.message || "EDIT FAILED"}`);
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
    state.imageShiftXStep = clampShiftStep(Number(event.target.value) || 0);
    renderShiftControls();
    state.renderedBanners = [];
    renderBannerSetsView();
    renderTopAction();
    if (hadRenderedBanners) {
      scheduleBannerAutoRender();
    }
  });
}

if (imageScaleEl) {
  imageScaleEl.addEventListener("input", (event) => {
    const hadRenderedBanners = state.hasRenderedBanners;
    const raw = Number(event.target.value);
    if (!Number.isFinite(raw)) {
      state.imageScalePercent = IMAGE_SCALE_MIN;
    } else {
      const clamped = Math.max(IMAGE_SCALE_MIN, Math.min(IMAGE_SCALE_MAX, raw));
      const snapped = Math.round((clamped - IMAGE_SCALE_MIN) / IMAGE_SCALE_STEP) * IMAGE_SCALE_STEP + IMAGE_SCALE_MIN;
      state.imageScalePercent = Math.max(IMAGE_SCALE_MIN, Math.min(IMAGE_SCALE_MAX, snapped));
    }
    renderShiftControls();
    state.renderedBanners = [];
    renderBannerSetsView();
    renderTopAction();
    if (hadRenderedBanners) {
      scheduleBannerAutoRender();
    }
  });
}

if (imageShiftYEl) {
  imageShiftYEl.addEventListener("input", (event) => {
    const hadRenderedBanners = state.hasRenderedBanners;
    state.imageShiftYStep = clampShiftStep(Number(event.target.value) || 0);
    renderShiftControls();
    state.renderedBanners = [];
    renderBannerSetsView();
    renderTopAction();
    if (hadRenderedBanners) {
      scheduleBannerAutoRender();
    }
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
    state.editSuggestions = [];
    state.videoPromptText = "";
    state.videoRenderStatus = "No video yet.";
    state.videoResultUrl = "";
    invalidateRenderedBanners();
    setSourceStatus("uploaded");
    renderBannerSetsView();
    renderUiState();
  } catch (error) {
    setSourceStatus("failed");
    alert(`ERROR: ${error.message || "UPLOAD FAILED"}`);
  } finally {
    uploadImageInputEl.value = "";
  }
});

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
      alert(`ERROR: ${error.message || "UPLOAD FAILED"}`);
    } finally {
      uploadVideoInputEl.value = "";
    }
  });
}

addTextSetBtn.addEventListener("click", () => {
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

colorNameEl.textContent = state.colorLabel;
promptInputEl.value = state.editPromptText;
setSourceStatus("none");
renderCarModelControl();
renderColors();
renderAngles();
renderLayoutTypes();
renderShiftControls();
renderTextSetsEditor();
renderBannerSetsView();
renderPromptSuggestions();
renderUiState();
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
    state.editSuggestions = [];
    state.videoPromptText = "";
    state.videoRenderStatus = "No video yet.";
    state.videoResultUrl = "";
    invalidateRenderedBanners();
    setSourceStatusForImage(findLibraryImageByUrl(previous));
    renderBannerSetsView();
    renderUiState();
  });
}
