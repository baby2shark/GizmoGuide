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

const dimensionLabels = {
  price: "价格",
  performance: "性能",
  camera: "拍照",
  battery: "续航",
  screen: "屏幕",
  portability: "便携",
  storage: "存储",
  stability: "稳定",
  repair: "维修",
};

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

  const typingNode = appendTypingMessage();
  setBusy(true);

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        candidate_products: activeCandidates,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    typingNode.remove();
    appendAssistantResponse(data);
  } catch (error) {
    typingNode.remove();
    appendErrorMessage(error);
  } finally {
    setBusy(false);
  }
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

function appendErrorMessage(error) {
  const node = document.createElement("article");
  node.className = "message assistant";
  node.innerHTML = `
    <div class="avatar">G</div>
    <div class="bubble">
      <div class="error-box">
        <h2>需要调整一下</h2>
        <p>${escapeHtml(error.message || "未知错误")}</p>
      </div>
    </div>
  `;
  chatStream.appendChild(node);
  scrollToLatest();
}

function renderAssistantContent(data) {
  if (data.mode === "chat" || !data.recommendation) {
    return `<div class="plain-answer">${escapeHtml(data.assistant_message).replaceAll("\n", "<br>")}</div>`;
  }

  const recommendation = data.recommendation;
  return `
    <div class="plain-answer">${escapeHtml(data.assistant_message).replaceAll("\n", "<br>")}</div>
    <header class="result-header">
      <div>
        <h2>更推荐 ${escapeHtml(recommendation.winner_name)}</h2>
        <p class="result-meta">预算 ${data.user_profile.budget ?? "未明确"} 元 · 场景 ${formatScenarios(data.user_profile.primary_scenarios)} · ${data.products.length} 款候选 · ${data.answer_source === "llm" ? "Agent" : "Fallback"}</p>
      </div>
      <div class="confidence">
        <strong>${Math.round(recommendation.confidence * 100)}%</strong>
        <span>置信度</span>
      </div>
    </header>

    <section class="score-grid">
      ${recommendation.scores.map(renderScoreCard).join("")}
    </section>

    ${renderListBlock("主要理由", recommendation.key_reasons, "clean-list")}
    ${renderListBlock("风险提示", recommendation.risks, "clean-list danger-list")}
    ${renderListBlock("结论反转条件", recommendation.reversal_conditions, "clean-list warning-list")}
    ${renderListBlock("缺失信息", recommendation.missing_information, "clean-list")}
  `;
}

function renderScoreCard(score) {
  const rows = Object.entries(score.dimension_scores)
    .map(([key, value]) => {
      const width = Math.max(5, Math.min(100, value * 10));
      return `
        <div class="dimension-row">
          <span>${dimensionLabels[key] ?? key}</span>
          <div class="bar"><span style="width:${width}%"></span></div>
          <strong>${Number(value).toFixed(1)}</strong>
        </div>
      `;
    })
    .join("");

  return `
    <article class="score-card">
      <div class="score-title">
        <span>${escapeHtml(score.product_name)}</span>
        <span class="score-value">${Number(score.total_score).toFixed(1)}</span>
      </div>
      <div class="dimension-list">${rows}</div>
    </article>
  `;
}

function renderListBlock(title, items, className) {
  if (!items || items.length === 0) return "";
  return `
    <section class="section-block">
      <h3>${title}</h3>
      <ul class="${className}">
        ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </section>
  `;
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

function formatScenarios(scenarios) {
  if (!scenarios || scenarios.length === 0) return "未明确";
  const labels = { photo: "拍照", gaming: "游戏", daily: "日常", business: "商务", elder: "长辈", student: "学生", travel: "旅行" };
  return scenarios.map((item) => labels[item] ?? item).join("、");
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

autosizeTextarea();
loadProducts();