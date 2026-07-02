const compareForm = document.querySelector("#compare-form");
const chatForm = document.querySelector("#chat-form");
const productA = document.querySelector("#product-a");
const productB = document.querySelector("#product-b");
const userMessage = document.querySelector("#user-message");
const submitButton = document.querySelector("#submit-button");
const chatStream = document.querySelector("#chat-stream");
const welcomeState = document.querySelector("#welcome-state");

let productOptions = [];
let activeCandidates = [];
let hasCompared = false;
let sessionId = `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;

for (const button of document.querySelectorAll(".preset")) {
  button.addEventListener("click", () => {
    selectProduct(productA, button.dataset.a);
    selectProduct(productB, button.dataset.b);
  });
}

compareForm.addEventListener("submit", (event) => {
  event.preventDefault();
  startComparison();
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await sendChatMessage();
});

userMessage.addEventListener("input", autosizeTextarea);

async function loadProducts() {
  try {
    const response = await fetch("/products");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    productOptions = await response.json();
    renderProductSelect(productA, "iphone_15");
    renderProductSelect(productB, "vivo_x100");
  } catch (error) {
    appendErrorMessage(new Error("商品列表加载失败，请检查后端服务。"));
    console.warn("Failed to load products", error);
  }
}

function renderProductSelect(select, selectedId) {
  select.innerHTML = productOptions
    .map((product) => {
      const selected = product.id === selectedId ? " selected" : "";
      const label = `${product.name} · ¥${product.price}`;
      return `<option value="${escapeHtml(product.id)}"${selected}>${escapeHtml(label)}</option>`;
    })
    .join("");
}

function selectProduct(select, nameOrId) {
  const normalized = normalize(nameOrId);
  const product = productOptions.find((item) => {
    const aliases = [item.id, item.name, ...(item.aliases || [])];
    return aliases.some((alias) => normalize(alias) === normalized);
  });
  if (product) select.value = product.id;
}

function startComparison() {
  const left = getProduct(productA.value);
  const right = getProduct(productB.value);
  if (!left || !right) {
    appendErrorMessage(new Error("请选择两款候选商品。"));
    return;
  }
  if (left.id === right.id) {
    appendErrorMessage(new Error("请选择两款不同的候选商品。"));
    return;
  }

  activeCandidates = [left.id, right.id];
  hasCompared = true;
  sessionId = `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  welcomeState.classList.add("hidden");
  chatForm.classList.remove("hidden");
  appendAssistantComparison(left, right);
  userMessage.focus();
  scrollToLatest();
}

async function sendChatMessage() {
  const message = userMessage.value.trim();
  if (!message || !hasCompared || activeCandidates.length < 2) return;

  appendUserMessage(message);
  userMessage.value = "";
  autosizeTextarea();

  const streamNode = appendStreamingMessage();
  setBusy(true);

  try {
    const payload = {
      session_id: sessionId,
      message,
      candidate_products: activeCandidates,
    };
    const data = await sendChatMessageStream(payload, streamNode);
    renderFinalAssistantResponse(streamNode, data);
  } catch (error) {
    renderStreamError(streamNode, error);
  } finally {
    setBusy(false);
  }
}

async function sendChatMessageStream(payload, streamNode) {
  const response = await fetch("/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  if (!response.body) return sendChatMessageFallback(payload);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const parsed = parseSseEvent(rawEvent);
      if (!parsed) continue;
      const finalResponse = handleStreamEvent(parsed, streamNode);
      if (finalResponse) return finalResponse;
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseEvent(buffer);
    const finalResponse = parsed ? handleStreamEvent(parsed, streamNode) : null;
    if (finalResponse) return finalResponse;
  }

  throw new Error("流式连接已结束，但没有收到最终回答。");
}

async function sendChatMessageFallback(payload) {
  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function parseSseEvent(rawEvent) {
  const lines = rawEvent.split("\n");
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  return JSON.parse(dataLines.join("\n"));
}

function handleStreamEvent(event, streamNode) {
  if (event.event === "final") {
    return event.data?.response;
  }
  if (event.event === "error") {
    const detail = event.data?.detail ? `：${event.data.detail}` : "";
    throw new Error(`${event.message || "流式回答失败"}${detail}`);
  }
  appendStreamStep(streamNode, event);
  return null;
}

function appendAssistantComparison(left, right) {
  const node = document.createElement("article");
  node.className = "message assistant";
  node.innerHTML = `
    <div class="avatar">G</div>
    <div class="bubble">
      <div class="context-note">已选择 ${escapeHtml(left.name)} 和 ${escapeHtml(right.name)}。我先给你一个基础对比，接下来你可以像和导购聊天一样继续说预算、用途和顾虑。</div>
      ${renderComparison(left, right)}
    </div>
  `;
  chatStream.appendChild(node);
}

function renderComparison(left, right) {
  return `
    <header class="compare-head">
      <div>
        <h2>${escapeHtml(left.name)} vs ${escapeHtml(right.name)}</h2>
        <p>这是基于当前 mock 商品库的基础参数对比，还没有接入实时价格、评测和维修证据。</p>
      </div>
    </header>
    <div class="compare-grid">
      ${renderCompareProduct(left)}
      ${renderCompareProduct(right)}
    </div>
    <div class="compare-summary">${escapeHtml(buildCompareSummary(left, right))}</div>
  `;
}

function renderCompareProduct(product) {
  return `
    <article class="compare-product">
      <h3>${escapeHtml(product.name)}</h3>
      <div class="compare-meta">${escapeHtml(product.brand)} · ${product.os.toUpperCase()} · ¥${product.price}</div>
      <div class="compare-facts">
        ${renderCompareFact("性能", `${product.chip_tier}/10`)}
        ${renderCompareFact("拍照", `${product.camera_tier}/10`)}
        ${renderCompareFact("续航", `${product.battery_tier}/10`)}
        ${renderCompareFact("屏幕", `${product.screen_tier}/10`)}
        ${renderCompareFact("存储", `${product.storage_gb}GB`)}
        ${renderCompareFact("重量", `${product.weight_g}g`)}
        ${renderCompareFact("维修风险", repairRiskLabel(product.repair_risk))}
      </div>
    </article>
  `;
}

function renderCompareFact(label, value) {
  return `<div class="compare-fact"><span>${label}</span><strong>${value}</strong></div>`;
}

function buildCompareSummary(left, right) {
  const parts = [];
  const cheaper = left.price === right.price ? null : left.price < right.price ? left : right;
  const camera = left.camera_tier === right.camera_tier ? null : left.camera_tier > right.camera_tier ? left : right;
  const battery = left.battery_tier === right.battery_tier ? null : left.battery_tier > right.battery_tier ? left : right;
  const lighter = left.weight_g === right.weight_g ? null : left.weight_g < right.weight_g ? left : right;

  if (cheaper) parts.push(`${cheaper.name} 价格更低`);
  if (camera) parts.push(`${camera.name} 拍照参数更强`);
  if (battery) parts.push(`${battery.name} 续航更占优`);
  if (lighter) parts.push(`${lighter.name} 更轻`);
  return parts.length ? `简要看：${parts.slice(0, 3).join("，")}。最终推荐还要结合你的预算、用途和风险偏好。` : "两款基础参数接近，最终更依赖你的预算、用途和风险偏好。";
}

function appendUserMessage(message) {
  const node = document.createElement("article");
  node.className = "message user";
  node.innerHTML = `
    <div class="bubble">${escapeHtml(message)}</div>
    <div class="avatar">我</div>
  `;
  chatStream.appendChild(node);
  scrollToLatest();
}

function appendTypingMessage() {
  const node = document.createElement("article");
  node.className = "message assistant";
  node.innerHTML = `
    <div class="avatar">G</div>
    <div class="bubble">
      <div class="typing" aria-label="正在生成"><span></span><span></span><span></span></div>
    </div>
  `;
  chatStream.appendChild(node);
  scrollToLatest();
  return node;
}

function appendStreamingMessage() {
  const node = document.createElement("article");
  node.className = "message assistant";
  node.innerHTML = `
    <div class="avatar">G</div>
    <div class="bubble">
      <div class="stream-steps" aria-live="polite"></div>
      <div class="typing stream-typing" aria-label="正在生成"><span></span><span></span><span></span></div>
    </div>
  `;
  chatStream.appendChild(node);
  scrollToLatest();
  return node;
}

function appendStreamStep(node, event) {
  const list = node.querySelector(".stream-steps");
  if (!list) return;
  const item = document.createElement("div");
  item.className = `stream-step stream-step-${escapeCssClass(event.event)}`;
  item.textContent = event.message || "正在处理";
  list.appendChild(item);
  while (list.children.length > 6) list.firstElementChild?.remove();
  scrollToLatest();
}

function appendAssistantResponse(data) {
  const node = document.createElement("article");
  node.className = "message assistant";
  node.innerHTML = `
    <div class="avatar">G</div>
    <div class="bubble">${renderAssistantContent(data)}</div>
  `;
  chatStream.appendChild(node);
  scrollToLatest();
}

function renderFinalAssistantResponse(node, data) {
  const bubble = node.querySelector(".bubble");
  if (!bubble) return;
  bubble.innerHTML = renderAssistantContent(data);
  scrollToLatest();
}

function renderStreamError(node, error) {
  const bubble = node.querySelector(".bubble");
  if (!bubble) {
    appendErrorMessage(error);
    return;
  }
  bubble.innerHTML = renderErrorContent(error);
  scrollToLatest();
}

function appendErrorMessage(error) {
  const node = document.createElement("article");
  node.className = "message assistant";
  node.innerHTML = `
    <div class="avatar">G</div>
    <div class="bubble">${renderErrorContent(error)}</div>
  `;
  chatStream.appendChild(node);
  scrollToLatest();
}

function renderErrorContent(error) {
  return `
    <div class="error-box">
      <h2>需要调整一下</h2>
      <p>${escapeHtml(error.message || "未知错误")}</p>
    </div>
  `;
}

function renderAssistantContent(data) {
  return `<div class="plain-answer">${renderRichText(data.assistant_message)}</div>`;
}

function renderRichText(value) {
  // 先转义防 XSS，再把 **xxx** 还原成 <strong>，最后换行转 <br>。
  const escaped = escapeHtml(value ?? "");
  return escaped
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replaceAll("\n", "<br>");
}

function getProduct(idOrName) {
  return productOptions.find((item) => item.id === idOrName || item.name === idOrName);
}

function normalize(value) {
  return String(value).toLowerCase().replace(/\s+/g, "");
}

function repairRiskLabel(value) {
  return { low: "低", medium: "中", high: "高" }[value] ?? value;
}

function autosizeTextarea() {
  userMessage.style.height = "auto";
  userMessage.style.height = `${Math.min(userMessage.scrollHeight, 160)}px`;
}

function setBusy(isBusy) {
  submitButton.disabled = isBusy;
}

function scrollToLatest() {
  requestAnimationFrame(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeCssClass(value) {
  return String(value).replace(/[^a-z0-9_-]/gi, "-");
}

autosizeTextarea();
loadProducts();
