const $ = (selector) => document.querySelector(selector);

const thread = $("#thread");
const promptInput = $("#prompt-input");
const promptForm = $("#prompt-form");
const sendButton = $("#send-button");
const compilePlanButton = $("#compile-plan");
const buildButton = $("#build-candidate");
const ackCheckbox = $("#acknowledge-unparsed");
const toast = $("#toast");

const bodyFields = [
  ["height_cm", "Height", "cm"],
  ["build_percent", "Build", "%"],
  ["shoulder_percent", "Shoulders", "%"],
  ["torso_length_percent", "Torso length", "%"],
  ["bust_percent", "Chest volume", "%"],
  ["stomach_percent", "Abdomen volume", "%"],
  ["hips_percent", "Hip width", "%"],
  ["glutes_percent", "Glute volume", "%"],
  ["thighs_percent", "Thigh size", "%"],
  ["arm_length_percent", "Arm length", "%"],
  ["leg_length_percent", "Leg length", "%"],
  ["head_percent", "Head size", "%"],
  ["hand_percent", "Hand size", "%"],
  ["foot_percent", "Foot size", "%"],
  ["jaw_percent", "Jaw size", "%"],
  ["ear_percent", "Ear size", "%"],
  ["muscle_percent", "Muscle definition", "%"],
  ["nose_percent", "Nose size", "%"],
];

let currentResult = null;
let currentPlan = null;
let toastTimer = 0;
let renderer = null;
let previewScene = null;
let previewCamera = null;
let previewControls = null;
let previewFrame = 0;
let candidates = [];
let selectedCandidate = null;

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { toast.hidden = true; }, 5200);
}

function appendMessage(kind, label, text, details = []) {
  const article = document.createElement("article");
  article.className = `message ${kind === "user" ? "user-message" : "assistant-message"}`;
  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = kind === "user" ? "Y" : "A";
  const content = document.createElement("div");
  content.className = "message-content";
  const meta = document.createElement("div");
  meta.className = "message-meta";
  const sender = document.createElement("span");
  sender.textContent = label;
  const time = document.createElement("time");
  time.textContent = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date());
  meta.append(sender, time);
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  content.append(meta, paragraph);
  if (details.length) {
    const result = document.createElement("div");
    result.className = `compiler-result${kind === "error" ? " error" : ""}`;
    const heading = document.createElement("b");
    heading.textContent = kind === "error" ? "NEEDS ATTENTION" : "EXPLICIT VALUES APPLIED";
    const list = document.createElement("ul");
    for (const detail of details) {
      const item = document.createElement("li");
      item.textContent = detail;
      list.append(item);
    }
    result.append(heading, list);
    content.append(result);
  }
  article.append(avatar, content);
  thread.append(article);
  thread.scrollTop = thread.scrollHeight;
  return article;
}

function renderRecipe(profile, parsed = []) {
  const container = $("#recipe-summary");
  container.replaceChildren();
  const changed = new Set(parsed.map((item) => item.field));
  for (const [key, label, unit] of bodyFields) {
    const row = document.createElement("div");
    row.className = `field-row${changed.has(key) ? " is-changed" : ""}`;
    const name = document.createElement("span");
    name.textContent = label;
    const value = document.createElement("b");
    value.textContent = `${profile.body[key]}${unit}`;
    row.append(name, value);
    container.append(row);
  }
  $("#draft-badge").textContent = "DRAFT";
  $("#draft-badge").className = "draft-badge is-ready";
  $("#recipe-subtitle").textContent = `${parsed.length} explicit ${parsed.length === 1 ? "change" : "changes"} mapped · T-pose`;
}

function updatePlanAvailability() {
  const hasBlocking = Boolean(currentResult?.blocking_questions?.length || currentResult?.needs_revision?.length);
  compilePlanButton.disabled = !currentResult || !currentResult.ready_for_plan || hasBlocking || !ackCheckbox.checked;
}

function addCompilerOutcome(result) {
  const parsed = result.parsed_fields || [];
  const details = parsed.map((item) => `${item.source_text} → ${item.message}`);
  const blockers = (result.blocking_questions || []).map((item) => item.message);
  const invalid = (result.needs_revision || []).map((item) => item.message);
  const warnings = [];
  if (result.later_stage_mentions?.length) {
    warnings.push(`Saved for later authoring stages: ${result.later_stage_mentions.join(", ")}.`);
  }
  if (!parsed.length) {
    warnings.push("No explicit supported geometry values were found. Use the examples or specify measurements with units/percentages.");
  }
  const narrative = blockers.length || invalid.length
    ? "Some measurements need revision before Atlas can compile the draft."
    : `I mapped ${parsed.length} explicit ${parsed.length === 1 ? "field" : "fields"}. I did not infer measurements from adjectives; the full text remains attached to the draft profile.`;
  appendMessage(blockers.length || invalid.length ? "error" : "assistant", "ATLAS COMPILER", narrative, [...details, ...invalid, ...blockers, ...warnings]);
  currentResult = result;
  currentPlan = null;
  renderRecipe(result.profile, parsed);
  $("#mapping-notice").hidden = false;
  $("#mapping-notice").className = `mapping-notice${blockers.length || invalid.length ? " is-error" : ""}`;
  $("#mapping-notice").textContent = result.scope_notice;
  $("#acknowledge-wrap").hidden = false;
  ackCheckbox.checked = false;
  compilePlanButton.textContent = "Compile build plan →";
  buildButton.disabled = true;
  updatePlanAvailability();
}

async function postJson(path, value) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

async function compilePrompt(prompt) {
  appendMessage("user", "YOU", prompt);
  sendButton.disabled = true;
  sendButton.querySelector("span").textContent = "Parsing…";
  try {
    const result = await postJson("/api/compile", { prompt });
    addCompilerOutcome(result);
  } catch (error) {
    appendMessage("error", "ATLAS COMPILER", error.message);
    showToast(error.message);
  } finally {
    sendButton.disabled = false;
    sendButton.querySelector("span").textContent = "Parse brief";
  }
}

async function compilePlan() {
  if (!currentResult || !ackCheckbox.checked || compilePlanButton.disabled) return;
  compilePlanButton.disabled = true;
  compilePlanButton.textContent = "Compiling…";
  try {
    currentPlan = await postJson("/api/plan", {
      profile: currentResult.profile,
      prompt: currentResult.profile.concept.source_prompt,
    });
    compilePlanButton.textContent = "Plan compiled ✓";
    buildButton.disabled = false;
    $("#action-caption").textContent = `Candidate-only plan · ${currentPlan.plan.quality_tier} · ${currentPlan.plan.neutral_pose}. No rig is needed for this build.`;
    appendMessage("assistant", "BUILD PLANNER", `Recipe and profile are frozen into a candidate plan (${currentPlan.plan.plan_sha256.slice(0, 16)}…). It is ready to build as a low-detail blockout.`, [
      `Saved locally under ${currentPlan.saved_under}.`,
      "The build plan freezes the profile, recipe, schema, and generator inputs for review.",
    ]);
  } catch (error) {
    compilePlanButton.textContent = "Compile build plan →";
    updatePlanAvailability();
    showToast(error.message);
    appendMessage("error", "BUILD PLANNER", error.message);
  }
}

async function buildCandidate() {
  if (!currentPlan || buildButton.disabled) return;
  buildButton.disabled = true;
  buildButton.innerHTML = "Building blockout… <span>◌</span>";
  $("#action-caption").textContent = "Blender is building a local review candidate. This can take a little while.";
  try {
    const result = await postJson("/api/build", { draft_id: currentPlan.draft_id });
    $("#preview-card").hidden = false;
    $("#preview-meta").replaceChildren();
    const stats = [
      ["QUALITY", result.quality_tier],
      ["SURFACE", `${result.vertex_count.toLocaleString()} vertices · ${result.polygon_count.toLocaleString()} polygons`],
      ["ARMATURE", result.rigging.armature_generated ? "Generated" : "None"],
      ["REVIEW", result.candidate_status.replaceAll("_", " ")],
    ];
    for (const [label, value] of stats) {
      const item = document.createElement("div");
      const bold = document.createElement("b");
      bold.textContent = `${label}  `;
      item.append(bold, document.createTextNode(value));
      $("#preview-meta").append(item);
    }
    $("#action-caption").textContent = `Saved to ${result.candidate_directory}. Review the preview and record accept/reject against its checksum.`;
    buildButton.textContent = "Rebuild candidate ↗";
    buildButton.disabled = false;
    appendMessage("assistant", "BLENDER BUILDER", "The unrigged T-pose blockout is ready for visual review. It is not a finished or production-ready model.", [
      `${result.vertex_count.toLocaleString()} vertices and ${result.polygon_count.toLocaleString()} polygons.`,
      `Candidate record: ${result.record_path}.`,
      "No armature, skin weights, or animation were generated.",
    ]);
    await refreshCandidates().catch((error) => showToast(error.message));
    const built = candidates.find((item) => item.draft_id === result.draft_id && item.build_id === result.build_id);
    if (built) await selectCandidate(built, false);
    else await loadPreview(result.draft_id, result.build_id);
    $("#preview-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    buildButton.textContent = "Build blockout candidate ↗";
    buildButton.disabled = false;
    $("#action-caption").textContent = error.message;
    showToast(error.message);
    appendMessage("error", "BLENDER BUILDER", error.message);
  }
}

function formatDate(value) {
  if (!value) return "Build date unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Build date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function renderCandidateList() {
  const filter = $("#candidate-filter").value;
  const visible = candidates.filter((item) => filter === "all" || item.review_status === filter);
  const list = $("#candidate-list");
  list.replaceChildren();
  $("#candidate-list-summary").textContent = `${visible.length} shown · ${candidates.length} total generated candidate${candidates.length === 1 ? "" : "s"}`;
  $("#candidate-empty").hidden = visible.length > 0;
  for (const candidate of visible) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `candidate-item${selectedCandidate?.build_id === candidate.build_id && selectedCandidate?.draft_id === candidate.draft_id ? " is-selected" : ""}`;
    button.setAttribute("aria-pressed", String(selectedCandidate?.build_id === candidate.build_id && selectedCandidate?.draft_id === candidate.draft_id));
    const title = document.createElement("b");
    title.textContent = "Parametric character blockout";
    const state = document.createElement("span");
    state.className = `candidate-state${candidate.review_status === "kept_for_reference" ? " is-kept" : ""}`;
    state.textContent = candidate.review_status === "kept_for_reference" ? "KEPT FOR REFERENCE" : "REVIEW REQUIRED";
    const detail = document.createElement("small");
    const vertices = Number.isInteger(candidate.vertex_count) ? `${candidate.vertex_count.toLocaleString()} vertices` : "geometry details unavailable";
    detail.textContent = `${formatDate(candidate.built_at)} · ${vertices}`;
    const previewState = document.createElement("small");
    previewState.textContent = candidate.has_preview ? "3D preview available" : "Preview file missing";
    button.append(title, state, detail, previewState);
    button.addEventListener("click", () => selectCandidate(candidate));
    list.append(button);
  }
}

async function refreshCandidates() {
  const response = await fetch("/api/candidates");
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not load generated candidates.");
  candidates = data.candidates || [];
  renderCandidateList();
  if (selectedCandidate) {
    const updated = candidates.find((item) => item.draft_id === selectedCandidate.draft_id && item.build_id === selectedCandidate.build_id);
    if (updated) {
      selectedCandidate = updated;
      updateCandidateInspector(updated);
      renderCandidateList();
    }
  }
}

function updateCandidateInspector(candidate) {
  $("#preview-card").hidden = false;
  $("#selected-candidate-title").textContent = "Unrigged T-pose blockout";
  $("#selected-review-badge").textContent = candidate.review_status === "kept_for_reference" ? "KEPT FOR REFERENCE" : "REVIEW REQUIRED";
  $("#keep-candidate").disabled = candidate.review_status === "kept_for_reference";
  $("#keep-candidate").textContent = candidate.review_status === "kept_for_reference" ? "Kept for reference ✓" : "Keep for reference";
  const meta = $("#preview-meta");
  meta.replaceChildren();
  const stats = [
    ["QUALITY TIER", candidate.quality_tier || "unknown"],
    ["SURFACE", `${Number(candidate.vertex_count || 0).toLocaleString()} vertices · ${Number(candidate.polygon_count || 0).toLocaleString()} polygons`],
    ["BUILT", formatDate(candidate.built_at)],
    ["PRODUCTION", candidate.production_ready ? "Marked production ready" : "Not production ready"],
  ];
  for (const [label, value] of stats) {
    const item = document.createElement("div");
    const bold = document.createElement("b");
    bold.textContent = `${label}  `;
    item.append(bold, document.createTextNode(value));
    meta.append(item);
  }
  $("#candidate-path").textContent = `Generated folder: ${candidate.candidate_directory}`;
}

async function selectCandidate(candidate, shouldScroll = true) {
  selectedCandidate = candidate;
  renderCandidateList();
  updateCandidateInspector(candidate);
  if (candidate.has_preview) {
    await loadPreview(candidate.draft_id, candidate.build_id);
  } else {
    clearPreviewModel();
    $("#preview-hint").textContent = "No preview GLB is available for this candidate.";
  }
  if (shouldScroll) $("#preview-card").scrollIntoView({ behavior: "smooth", block: "center" });
}

async function updateCandidateReview(action) {
  if (!selectedCandidate) return;
  if (action === "delete") {
    const label = `Character build ${selectedCandidate.build_id.slice(0, 8)}`;
    if (!window.confirm(`Permanently delete ${label} and its generated files? This does not affect source or runtime assets.`)) return;
  }
  try {
    await postJson("/api/candidate/review", {
      draft_id: selectedCandidate.draft_id,
      build_id: selectedCandidate.build_id,
      action,
    });
    if (action === "delete") {
      clearPreviewModel();
      selectedCandidate = null;
      $("#preview-card").hidden = true;
      showToast("Selected generated build deleted.");
    } else {
      showToast("Candidate marked kept for reference. It remains unapproved.");
    }
    await refreshCandidates();
  } catch (error) {
    showToast(error.message);
  }
}

function clearPreviewModel() {
  if (!previewScene) return;
  const model = previewScene.children.find((child) => child.userData.atlasModel);
  if (model) previewScene.remove(model);
}

async function loadPreview(draftId, buildId) {
  const loading = $("#preview-loading");
  loading.hidden = false;
  try {
    const [THREE, { OrbitControls }, { GLTFLoader }] = await Promise.all([
      import("three"),
      import("three/addons/controls/OrbitControls.js"),
      import("three/addons/loaders/GLTFLoader.js"),
    ]);
    const canvas = $("#preview-canvas");
    if (!renderer) {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      previewScene = new THREE.Scene();
      previewScene.add(new THREE.HemisphereLight(0xe3e6cf, 0x25332a, 2.1));
      const key = new THREE.DirectionalLight(0xffe6bd, 3.2);
      key.position.set(-3, -4, 6);
      previewScene.add(key);
      const rim = new THREE.DirectionalLight(0xb4d99e, 2.1);
      rim.position.set(3, 4, 3);
      previewScene.add(rim);
      const grid = new THREE.GridHelper(4, 20, 0x7a8b75, 0x526150);
      grid.rotation.x = Math.PI / 2;
      grid.position.z = -0.015;
      grid.material.transparent = true;
      grid.material.opacity = 0.24;
      previewScene.add(grid);
      previewCamera = new THREE.PerspectiveCamera(34, 1, 0.01, 100);
      previewCamera.up.set(0, 0, 1);
      // Character front is -Y; start on that side so the initial preview shows
      // the face rather than looking at the back of the head.
      previewCamera.position.set(3, -5, 2.5);
      previewControls = new OrbitControls(previewCamera, renderer.domElement);
      previewControls.enableDamping = true;
      previewControls.target.set(0, 0, 1.1);
      previewControls.minDistance = 0.7;
      previewControls.maxDistance = 10;
      const resize = new ResizeObserver(() => {
        const bounds = canvas.getBoundingClientRect();
        if (!bounds.width || !bounds.height) return;
        renderer.setSize(bounds.width, bounds.height, false);
        previewCamera.aspect = bounds.width / bounds.height;
        previewCamera.updateProjectionMatrix();
      });
      resize.observe(canvas.parentElement);
      const animate = () => {
        previewFrame = requestAnimationFrame(animate);
        previewControls.update();
        renderer.render(previewScene, previewCamera);
      };
      animate();
    }
    clearPreviewModel();
    const previewUrl = `/api/candidate/preview?draft_id=${encodeURIComponent(draftId)}&build_id=${encodeURIComponent(buildId)}`;
    const model = await new GLTFLoader().loadAsync(previewUrl);
    const object = model.scene;
    object.userData.atlasModel = true;
    previewScene.add(object);
    const bounds = new THREE.Box3().setFromObject(object);
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    previewControls.target.copy(center);
    previewCamera.position.copy(center).add(new THREE.Vector3(Math.max(size.x * 1.65, 2.2), -Math.max(size.z * 2.5, 4), Math.max(size.z * 0.8, 1.4)));
    previewCamera.near = Math.max(size.z / 1000, 0.005);
    previewCamera.far = Math.max(size.z * 20, 50);
    previewCamera.updateProjectionMatrix();
    previewControls.update();
    // Generated and imported anatomy can contain open surface patches or
    // inconsistent winding. Render both sides in this inspection preview so
    // those faces do not disappear when the camera looks directly at them.
    object.traverse((part) => {
      if (!part.isMesh || !part.material) return;
      const materials = Array.isArray(part.material) ? part.material : [part.material];
      for (const material of materials) {
        material.side = THREE.DoubleSide;
        material.needsUpdate = true;
      }
    });
    $("#preview-hint").textContent = "Drag to orbit · scroll to zoom";
  } catch (error) {
    $("#preview-hint").textContent = "Preview renderer unavailable · open the saved GLB in Blender";
    console.error("Recipe Studio preview failed", error);
  } finally {
    loading.hidden = true;
  }
}

promptForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const prompt = promptInput.value.trim();
  if (!prompt) return;
  promptInput.value = "";
  $("#char-count").textContent = "0 / 2000";
  void compilePrompt(prompt);
});

promptInput.addEventListener("input", () => {
  $("#char-count").textContent = `${promptInput.value.length} / 2000`;
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    promptForm.requestSubmit();
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.dataset.prompt;
    $("#char-count").textContent = `${promptInput.value.length} / 2000`;
    promptInput.focus();
  });
});

ackCheckbox.addEventListener("change", updatePlanAvailability);
compilePlanButton.addEventListener("click", () => void compilePlan());
buildButton.addEventListener("click", () => void buildCandidate());
$("#candidate-filter").addEventListener("change", renderCandidateList);
$("#refresh-candidates").addEventListener("click", () => void refreshCandidates().catch((error) => showToast(error.message)));
$("#keep-candidate").addEventListener("click", () => void updateCandidateReview("keep"));
$("#delete-candidate").addEventListener("click", () => void updateCandidateReview("delete"));
$("#clear-chat").addEventListener("click", () => window.location.reload());

fetch("/api/health").then((response) => response.json()).then((health) => {
  if (!health.blender_available) {
    $("#action-caption").textContent = "Blender was not found. Parsing and plan compilation still work; set BLENDER_BIN to enable local candidate builds.";
  }
}).catch(() => showToast("The local recipe service is not responding."));

refreshCandidates().catch((error) => {
  $("#candidate-list-summary").textContent = "Could not load generated candidates.";
  showToast(error.message);
});
