function formatCurrency(value) {
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function drawChart() {
  const canvas = document.querySelector("#bankrollChart");
  if (!canvas) return;

  const context = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const padding = 34;
  const chartData = document.querySelector("#chart-values");
  const values = chartData ? JSON.parse(chartData.textContent) : [0];
  const safeValues = values.length > 1 ? values : [0, 0];
  const min = Math.min(...values) - 220;
  const max = Math.max(...values) + 220;
  const points = safeValues.map((value, index) => {
    const x = padding + (index * (width - padding * 2)) / (safeValues.length - 1);
    const y =
      height - padding - ((value - min) / (max - min)) * (height - padding * 2);
    return { x, y, value };
  });

  context.clearRect(0, 0, width, height);
  context.strokeStyle = "#2f3b38";
  context.lineWidth = 1;

  for (let i = 0; i < 5; i += 1) {
    const y = padding + (i * (height - padding * 2)) / 4;
    context.beginPath();
    context.moveTo(padding, y);
    context.lineTo(width - padding, y);
    context.stroke();
  }

  const area = context.createLinearGradient(0, padding, 0, height - padding);
  area.addColorStop(0, "rgba(79, 209, 139, 0.28)");
  area.addColorStop(1, "rgba(79, 209, 139, 0)");

  context.beginPath();
  points.forEach((point, index) => {
    if (index === 0) context.moveTo(point.x, point.y);
    else context.lineTo(point.x, point.y);
  });
  context.lineTo(points[points.length - 1].x, height - padding);
  context.lineTo(points[0].x, height - padding);
  context.closePath();
  context.fillStyle = area;
  context.fill();

  context.beginPath();
  points.forEach((point, index) => {
    if (index === 0) context.moveTo(point.x, point.y);
    else context.lineTo(point.x, point.y);
  });
  context.strokeStyle = "#4fd18b";
  context.lineWidth = 4;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.stroke();

  points.forEach((point) => {
    context.beginPath();
    context.arc(point.x, point.y, 4, 0, Math.PI * 2);
    context.fillStyle = "#101414";
    context.fill();
    context.strokeStyle = "#4fd18b";
    context.lineWidth = 3;
    context.stroke();
  });

  context.fillStyle = "#9caaa3";
  context.font = "13px Inter, system-ui, sans-serif";
  context.fillText(formatCurrency(min), padding, height - 12);
  context.fillText(formatCurrency(max), width - padding - 96, 24);
}

function drawBarChart() {
  const canvas = document.querySelector("#periodChart");
  if (!canvas) return;

  const context = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const padding = 34;
  const valuesData = document.querySelector("#period-values");
  const labelsData = document.querySelector("#period-labels");
  const values = valuesData ? JSON.parse(valuesData.textContent) : [0, 0, 0];
  const labels = labelsData ? JSON.parse(labelsData.textContent) : ["Hoje", "7 dias", "Mes"];
  const maxValue = Math.max(...values.map((value) => Math.abs(value)), 1);
  const availableWidth = width - padding * 2;
  const barWidth = Math.min(120, availableWidth / values.length - 24);
  const zeroY = height / 2;

  context.clearRect(0, 0, width, height);
  context.strokeStyle = "#2f3b38";
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(padding, zeroY);
  context.lineTo(width - padding, zeroY);
  context.stroke();

  values.forEach((value, index) => {
    const x = padding + index * (availableWidth / values.length) + 18;
    const barHeight = (Math.abs(value) / maxValue) * (height / 2 - 46);
    const y = value >= 0 ? zeroY - barHeight : zeroY;

    context.fillStyle = value >= 0 ? "#4fd18b" : "#f06f65";
    context.fillRect(x, y, barWidth, barHeight);

    context.fillStyle = "#9caaa3";
    context.font = "13px Inter, system-ui, sans-serif";
    context.fillText(labels[index], x, height - 14);
    context.fillText(formatCurrency(value), x, value >= 0 ? y - 8 : y + barHeight + 18);
  });
}

function activateScreen() {
  const screenAliases = {
    overview: "dashboard",
    calendar: "dashboard",
    reports: "analytics",
  };
  const requestedScreen = window.location.hash.replace("#", "") || "dashboard";
  const activeScreen = screenAliases[requestedScreen] || requestedScreen;
  const availableScreens = [...document.querySelectorAll("[data-screen]")].map(
    (section) => section.dataset.screen,
  );
  const safeScreen = availableScreens.includes(activeScreen) ? activeScreen : "dashboard";

  document.querySelectorAll("[data-screen]").forEach((section) => {
    section.classList.toggle("is-active", section.dataset.screen === safeScreen);
  });

  document.querySelectorAll(".nav-list a").forEach((link) => {
    const linkScreen = screenAliases[link.hash.replace("#", "")] || link.hash.replace("#", "");
    link.classList.toggle("active", linkScreen === safeScreen);
  });

  requestAnimationFrame(() => {
    drawChart();
    drawBarChart();
  });
}

function closeSidebar() {
  document.body.classList.remove("sidebar-open");
  document.querySelector(".mobile-menu-toggle")?.setAttribute("aria-expanded", "false");
}

function setupMobileSidebar() {
  const toggle = document.querySelector(".mobile-menu-toggle");
  const sidebar = document.querySelector(".sidebar");
  if (!toggle || !sidebar) return;

  toggle.addEventListener("click", () => {
    const isOpen = document.body.classList.toggle("sidebar-open");
    toggle.setAttribute("aria-expanded", String(isOpen));
  });

  document.querySelector("[data-sidebar-close]")?.addEventListener("click", closeSidebar);
  sidebar.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeSidebar);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSidebar();
  });
}

function enhanceResponsiveTables() {
  document.querySelectorAll("table").forEach((table) => {
    const headers = [...table.querySelectorAll("thead th")].map((header) =>
      header.textContent.trim(),
    );
    table.querySelectorAll("tbody tr").forEach((row) => {
      row.querySelectorAll("td").forEach((cell, index) => {
        if (headers[index]) cell.dataset.label = headers[index];
      });
    });
  });
}

function updateBetPreview() {
  const odds = Number.parseFloat(document.querySelector("#id_odds")?.value || 0);
  const stake = Number.parseFloat(document.querySelector("#id_stake")?.value || 0);
  const commissionPercentage = Number.parseFloat(
    document.querySelector("#id_exchange_commission")?.value || 0,
  );

  const grossProfit = odds > 1 && stake > 0 ? stake * (odds - 1) : 0;
  const commission = grossProfit * (commissionPercentage / 100);
  const netProfit = grossProfit - commission;
  const totalReturn = stake + netProfit;

  document.querySelector("#previewProfit").textContent = formatCurrency(netProfit);
  document.querySelector("#previewCommission").textContent = formatCurrency(commission);
  document.querySelector("#previewReturn").textContent = formatCurrency(totalReturn);
}

function setBetMode(mode) {
  document.querySelectorAll("[data-bet-mode-button]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.betModeButton === mode);
  });
  document.querySelectorAll("[data-bet-mode-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.betModePanel === mode);
  });
}

function readNumber(input) {
  return Number.parseFloat((input?.value || "0").replace(",", ".")) || 0;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function getSurebetIndices() {
  return [...document.querySelectorAll("[data-surebet-row]")]
    .map((row) => Number.parseInt(row.dataset.surebetRow, 10))
    .filter(Boolean)
    .sort((a, b) => a - b);
}

function updateSurebetPreview() {
  const firstOdd = readNumber(document.querySelector('[name="surebet_odd_1"]'));
  const firstStake = readNumber(document.querySelector('[name="surebet_stake_1"]'));
  const firstCommission = readNumber(document.querySelector('[name="surebet_commission_1"]'));
  const firstBoost = readNumber(document.querySelector('[name="surebet_boost_1"]'));
  const firstEffectiveOdd = firstOdd * (1 + firstBoost / 100);
  const firstMultiplier = firstEffectiveOdd > 1
    ? 1 + (firstEffectiveOdd - 1) * (1 - firstCommission / 100)
    : 0;
  const targetReturn = firstMultiplier > 0 && firstStake > 0 ? firstMultiplier * firstStake : 0;
  const indices = getSurebetIndices();

  indices.filter((index) => index > 1).forEach((index) => {
    const oddInput = document.querySelector(`[name="surebet_odd_${index}"]`);
    const stakeInput = document.querySelector(`[name="surebet_stake_${index}"]`);
    const odd = readNumber(oddInput);
    const commission = readNumber(document.querySelector(`[name="surebet_commission_${index}"]`));
    const boost = readNumber(document.querySelector(`[name="surebet_boost_${index}"]`));
    const effectiveOdd = odd * (1 + boost / 100);
    const multiplier = effectiveOdd > 1 ? 1 + (effectiveOdd - 1) * (1 - commission / 100) : 0;
    if (stakeInput) {
      stakeInput.value = targetReturn > 0 && multiplier > 0 ? (targetReturn / multiplier).toFixed(2) : "";
    }
  });

  const rows = indices.map((index) => {
    const bookmakerInput = document.querySelector(`[name="surebet_bookmaker_${index}"]`);
    const labelInput = document.querySelector(`[name="surebet_outcome_${index}"]`);
    const oddInput = document.querySelector(`[name="surebet_odd_${index}"]`);
    const stakeInput = document.querySelector(`[name="surebet_stake_${index}"]`);
    const commission = readNumber(document.querySelector(`[name="surebet_commission_${index}"]`));
    const cashback = readNumber(document.querySelector(`[name="surebet_cashback_${index}"]`));
    const boost = readNumber(document.querySelector(`[name="surebet_boost_${index}"]`));
    const odd = readNumber(oddInput);
    const effectiveOdd = odd * (1 + boost / 100);
    const multiplier = effectiveOdd > 1 ? 1 + (effectiveOdd - 1) * (1 - commission / 100) : 0;
    return {
      bookmaker: bookmakerInput?.value?.trim() || "-",
      label: labelInput?.value?.trim() || `Resultado ${index}`,
      odd,
      commission,
      cashback,
      boost,
      effectiveOdd,
      multiplier,
      stake: readNumber(stakeInput),
    };
  }).filter((row) => row.multiplier > 0 && row.stake > 0);

  const totalStake = rows.reduce((sum, row) => sum + row.stake, 0);
  const impliedTotal = rows.reduce((sum, row) => sum + 1 / row.multiplier, 0);
  const scenarios = rows.map((row) => ({
    ...row,
    returnAmount: row.stake * row.multiplier,
  })).map((row, _index, allRows) => {
    const cashbackReturn = allRows
      .filter((candidate) => candidate !== row)
      .reduce((sum, candidate) => sum + candidate.stake * (candidate.cashback / 100), 0);
    return {
      ...row,
      cashbackReturn,
      net: row.returnAmount + cashbackReturn - totalStake,
    };
  });
  const best = scenarios.length ? Math.max(...scenarios.map((row) => row.net)) : 0;
  const worst = scenarios.length ? Math.min(...scenarios.map((row) => row.net)) : 0;
  const margin = impliedTotal > 0 ? (1 / impliedTotal - 1) * 100 : 0;

  document.querySelector("#surebetTotal").textContent = formatCurrency(totalStake);
  document.querySelector("#surebetTargetReturn").textContent = formatCurrency(targetReturn);
  document.querySelector("#surebetMargin").textContent = `${margin.toFixed(2)}%`;
  document.querySelector("#surebetMargin").className = margin >= 0 ? "positive" : "negative";
  document.querySelector("#surebetBest").textContent = formatCurrency(best);
  document.querySelector("#surebetBest").className = best >= 0 ? "positive" : "negative";
  document.querySelector("#surebetWorst").textContent = formatCurrency(worst);
  document.querySelector("#surebetWorst").className = worst >= 0 ? "positive" : "negative";

  const table = document.querySelector("#surebetScenarioTable");
  if (!table) return;

  const body = scenarios.length
    ? scenarios.map((row) => `
        <div class="surebet-result-row">
          <span>${escapeHtml(row.bookmaker)}</span>
          <span>${escapeHtml(row.label)}</span>
          <span>${row.effectiveOdd.toFixed(2)}</span>
          <span>${formatCurrency(row.stake)}</span>
          <span>${formatCurrency(row.returnAmount)}</span>
          <span>${formatCurrency(row.cashbackReturn)}</span>
          <strong class="${row.net >= 0 ? "positive" : "negative"}">${formatCurrency(row.net)}</strong>
        </div>
      `).join("")
    : `
        <div class="surebet-result-row">
          <span>-</span>
          <span>-</span>
          <span>-</span>
          <span>${formatCurrency(0)}</span>
          <span>${formatCurrency(0)}</span>
          <span>${formatCurrency(0)}</span>
          <strong>${formatCurrency(0)}</strong>
        </div>
      `;

  table.innerHTML = `
    <div class="surebet-result-head">
      <span>Casa</span>
      <span>Resultado</span>
      <span>Odd</span>
      <span>Entrada</span>
      <span>Retorno</span>
      <span>Cashback</span>
      <span>Ganha / perde</span>
    </div>
    ${body}
  `;
}

function createSurebetEntry(index) {
  const group = document.createElement("div");
  group.className = "surebet-entry-group";
  group.dataset.surebetGroup = String(index);
  group.innerHTML = `
    <div class="surebet-entry-row" data-surebet-row="${index}">
      <label>
        <span class="sr-only">Casa de aposta ${index} opcional</span>
        <input type="text" name="surebet_bookmaker_${index}" placeholder="Ex: Pinnacle" autocomplete="off" />
      </label>
      <label>
        <span class="sr-only">Tipo ${index} opcional</span>
        <input type="text" name="surebet_outcome_${index}" placeholder="Visitante / terceiro mercado" autocomplete="off" />
      </label>
      <label>
        <span class="sr-only">Odd ${index}</span>
        <input type="number" name="surebet_odd_${index}" class="surebet-odd" step="0.01" min="1.01" />
      </label>
      <label>
        <span class="sr-only">Valor calculado ${index}</span>
        <input type="number" name="surebet_stake_${index}" class="surebet-stake calculated-stake" step="0.01" min="0.01" readonly />
      </label>
      <label>
        <span class="sr-only">Comissao % ${index}</span>
        <input type="number" name="surebet_commission_${index}" class="surebet-adjustment" step="0.01" min="0" max="100" />
      </label>
      <label>
        <span class="sr-only">Cashback % ${index}</span>
        <input type="number" name="surebet_cashback_${index}" class="surebet-adjustment" step="0.01" min="0" max="100" />
      </label>
      <label>
        <span class="sr-only">Aumento % ${index}</span>
        <input type="number" name="surebet_boost_${index}" class="surebet-adjustment" step="0.01" min="0" max="100" />
      </label>
      <div class="freebet-control">
        <input type="hidden" name="surebet_freebet_enabled_${index}" value="0" />
        <button class="freebet-toggle" type="button" title="Essa aposta gera freebet" aria-label="Essa aposta gera freebet">🎁</button>
      </div>
    </div>
    <div class="freebet-fields">
      <label>
        <span>Valor da freebet</span>
        <input type="number" name="surebet_freebet_amount_${index}" step="0.01" min="0.01" placeholder="Ex: 25.00" />
      </label>
    </div>
  `;
  return group;
}

document.querySelector("#addSurebetEntry")?.addEventListener("click", () => {
  const entries = document.querySelector("#surebetEntries");
  const countInput = document.querySelector("#surebetEntryCount");
  if (!entries || !countInput) return;

  const nextIndex = Math.max(...getSurebetIndices(), 0) + 1;
  entries.appendChild(createSurebetEntry(nextIndex));
  countInput.value = String(nextIndex);
  updateSurebetPreview();
});

document.querySelectorAll("[data-bet-mode-button]").forEach((button) => {
  button.addEventListener("click", () => setBetMode(button.dataset.betModeButton));
});

document.querySelector(".surebet-form")?.addEventListener("input", updateSurebetPreview);
document.querySelector(".surebet-form")?.addEventListener("change", updateSurebetPreview);
document.querySelector(".surebet-form")?.addEventListener("click", (event) => {
  const toggle = event.target.closest(".freebet-toggle");
  if (!toggle) return;

  const group = toggle.closest(".surebet-entry-group");
  const hiddenInput = group?.querySelector('input[name^="surebet_freebet_enabled_"]');
  if (!group || !hiddenInput) return;

  const isActive = !group.classList.contains("has-freebet");
  group.classList.toggle("has-freebet", isActive);
  hiddenInput.value = isActive ? "1" : "0";
  if (!isActive) {
    const amountInput = group.querySelector('input[name^="surebet_freebet_amount_"]');
    if (amountInput) amountInput.value = "";
  }
});

document.querySelector("#bankrollEntityFilter")?.addEventListener("change", (event) => {
  const selectedEntity = event.target.value;
  document.querySelectorAll(".bankroll-card[data-entity-id]").forEach((card) => {
    const shouldShow = !selectedEntity || card.dataset.entityId === selectedEntity;
    card.classList.toggle("is-filtered-out", !shouldShow);
  });
});

if (document.querySelector('[data-bet-mode-panel="surebet"] .form-errors')) {
  setBetMode("surebet");
}

["#id_bankroll", "#id_odds", "#id_stake", "#id_exchange_commission"].forEach((selector) => {
  document.querySelector(selector)?.addEventListener("input", updateBetPreview);
  document.querySelector(selector)?.addEventListener("change", updateBetPreview);
});

updateBetPreview();
updateSurebetPreview();
setupMobileSidebar();
enhanceResponsiveTables();
activateScreen();
drawChart();
drawBarChart();

window.addEventListener("hashchange", activateScreen);
window.addEventListener("resize", drawChart);
window.addEventListener("resize", drawBarChart);
