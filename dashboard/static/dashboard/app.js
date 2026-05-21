function formatCurrency(value) {
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function formatPlainAmount(value) {
  return value.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
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
  const padding = {
    top: 28,
    right: 18,
    bottom: 32,
    left: 50,
  };
  const valuesData = document.querySelector("#period-values");
  const labelsData = document.querySelector("#period-labels");
  const values = valuesData ? JSON.parse(valuesData.textContent) : [];
  const labels = labelsData ? JSON.parse(labelsData.textContent) : [];
  const chartValues = values.length ? values : [0];
  const chartLabels = labels.length ? labels : ["1"];
  const maxValue = Math.max(...values.map((value) => Math.abs(value)), 1);
  const availableWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const slotWidth = availableWidth / chartValues.length;
  const barWidth = Math.max(4, Math.min(14, slotWidth * 0.64));
  const zeroY = padding.top + plotHeight / 2;
  const hoveredIndex =
    canvas.dataset.hoveredBar !== undefined ? Number(canvas.dataset.hoveredBar) : null;

  context.clearRect(0, 0, width, height);
  context.strokeStyle = "#2f3b38";
  context.lineWidth = 1;

  [padding.top, zeroY, height - padding.bottom].forEach((y) => {
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
  });

  context.beginPath();
  context.moveTo(padding.left, zeroY);
  context.lineTo(width - padding.right, zeroY);
  context.stroke();

  context.fillStyle = "#9caaa3";
  context.font = "12px Inter, system-ui, sans-serif";
  context.fillText(formatCurrency(maxValue), padding.left, 18);
  context.fillText(formatCurrency(-maxValue), padding.left, height - 10);

  const bars = chartValues.map((value, index) => {
    const x = padding.left + index * slotWidth + (slotWidth - barWidth) / 2;
    const barHeight = Math.max(2, (Math.abs(value) / maxValue) * (plotHeight / 2 - 12));
    const y = value >= 0 ? zeroY - barHeight : zeroY;

    const barColor = value > 0 ? "#4fd18b" : value < 0 ? "#f06f65" : "#56635f";
    context.fillStyle = barColor;
    if (index === hoveredIndex) {
      context.shadowColor = value >= 0 ? "rgba(79, 209, 139, 0.32)" : "rgba(240, 111, 101, 0.32)";
      context.shadowBlur = 12;
    }
    context.fillRect(x, y, barWidth, barHeight);
    context.shadowBlur = 0;

    if (index === 0 || Number(chartLabels[index]) % 5 === 0 || index === chartValues.length - 1) {
      context.fillStyle = "#9caaa3";
      context.font = "11px Inter, system-ui, sans-serif";
      context.textAlign = "center";
      context.fillText(chartLabels[index], x + barWidth / 2, height - 12);
      context.textAlign = "left";
    }

    return {
      x,
      y,
      width: barWidth,
      height: barHeight,
      label: chartLabels[index],
      zeroY,
      value,
    };
  });

  canvas._periodBars = bars;

  if (hoveredIndex !== null && bars[hoveredIndex]) {
    const bar = bars[hoveredIndex];
    const text = `Dia ${bar.label}: ${formatCurrency(bar.value)}`;
    context.font = "12px Inter, system-ui, sans-serif";
    const textWidth = context.measureText(text).width;
    const tooltipWidth = textWidth + 18;
    const tooltipHeight = 28;
    const preferredX = bar.x + bar.width / 2 - tooltipWidth / 2;
    const tooltipX = Math.max(8, Math.min(width - tooltipWidth - 8, preferredX));
    const preferredY = bar.value >= 0 ? bar.y - tooltipHeight - 8 : bar.y + bar.height + 8;
    const tooltipY = Math.max(8, Math.min(height - tooltipHeight - 8, preferredY));

    context.fillStyle = "#101414";
    context.strokeStyle = "#2f3b38";
    context.lineWidth = 1;
    context.beginPath();
    context.roundRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight, 7);
    context.fill();
    context.stroke();
    context.fillStyle = bar.value >= 0 ? "#4fd18b" : "#f06f65";
    context.fillText(text, tooltipX + 9, tooltipY + 18);
  }

  if (!canvas.dataset.barEventsReady) {
    canvas.dataset.barEventsReady = "true";
    canvas.addEventListener("mousemove", (event) => {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const mouseX = (event.clientX - rect.left) * scaleX;
      const mouseY = (event.clientY - rect.top) * scaleY;
      const nextIndex = (canvas._periodBars || []).findIndex((bar) => {
        const hitPadding = Math.max(4, bar.width * 0.8);
        return (
          mouseX >= bar.x - hitPadding &&
          mouseX <= bar.x + bar.width + hitPadding &&
          mouseY >= Math.min(bar.y, bar.zeroY) - 12 &&
          mouseY <= Math.max(bar.y + bar.height, bar.zeroY) + 12
        );
      });

      if (nextIndex >= 0) {
        canvas.dataset.hoveredBar = String(nextIndex);
        canvas.style.cursor = "pointer";
      } else {
        delete canvas.dataset.hoveredBar;
        canvas.style.cursor = "default";
      }
      drawBarChart();
    });
    canvas.addEventListener("mouseleave", () => {
      delete canvas.dataset.hoveredBar;
      canvas.style.cursor = "default";
      drawBarChart();
    });
  }
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

function debounce(callback, delay = 350) {
  let timeoutId;
  return (...args) => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => callback(...args), delay);
  };
}

function setEventAutocompleteState(container, html) {
  if (!container) return;
  container.innerHTML = html;
  container.hidden = false;
}

function setupSingleEventAutocomplete(container) {
  const form = container.closest("form") || document;
  const gameInput = form.querySelector("[data-event-game-input]") || document.querySelector("#id_game");
  const sportInput = form.querySelector("[name='surebet_sport']") || document.querySelector("#id_sport");
  const competitionInput = form.querySelector("[name='surebet_competition']") || document.querySelector("#id_competition");
  const eventDateInput = form.querySelector("[data-event-date-input]") || document.querySelector("#id_event_date");
  const eventIdInput = form.querySelector("[data-event-id-input]") || document.querySelector("#id_external_event_id");
  const sportKeyInput = form.querySelector("[data-event-sport-key-input]") || document.querySelector("#id_external_sport_key");
  const homeTeamInput = form.querySelector("[data-event-home-team-input]") || document.querySelector("#id_home_team");
  const awayTeamInput = form.querySelector("[data-event-away-team-input]") || document.querySelector("#id_away_team");
  const url = container.dataset.url;
  if (!gameInput || !url) return;

  const searchEvents = debounce(async () => {
    const query = gameInput.value.trim();
    const sport = sportInput?.value || "";
    const competition = competitionInput?.value || "";
    if (query.length < 2 && competition.length < 2) {
      container.hidden = true;
      return;
    }

    setEventAutocompleteState(container, '<div class="event-empty">Buscando jogos...</div>');
    const params = new URLSearchParams({ q: query, sport, competition });

    try {
      const response = await fetch(`${url}?${params.toString()}`);
      const payload = await response.json();
      const results = payload.results || [];
      if (!results.length) {
        setEventAutocompleteState(
          container,
          '<div class="event-empty">Nenhum jogo encontrado. Voce pode continuar digitando manualmente.</div>',
        );
        return;
      }

      setEventAutocompleteState(
        container,
        results.map((event) => `
          <button
            class="event-option"
            type="button"
            data-game="${escapeHtml(event.game)}"
            data-sport="${escapeHtml(event.sport)}"
            data-competition="${escapeHtml(event.competition)}"
            data-event-date="${escapeHtml(event.event_date)}"
            data-event-id="${escapeHtml(event.id || "")}"
            data-sport-key="${escapeHtml(event.sport_key || "")}"
            data-home-team="${escapeHtml(event.home_team || "")}"
            data-away-team="${escapeHtml(event.away_team || "")}"
          >
            <strong>${escapeHtml(event.game)}</strong>
            <span>${escapeHtml(event.competition)}${event.display_date ? ` | ${escapeHtml(event.display_date)}` : ""}</span>
          </button>
        `).join(""),
      );
    } catch (_error) {
      setEventAutocompleteState(
        container,
        '<div class="event-empty">Nao foi possivel buscar jogos agora. Voce pode digitar manualmente.</div>',
      );
    }
  });

  gameInput.addEventListener("input", searchEvents);
  competitionInput?.addEventListener("input", searchEvents);
  sportInput?.addEventListener("input", searchEvents);

  container.addEventListener("click", (event) => {
    const option = event.target.closest(".event-option");
    if (!option) return;
    gameInput.value = option.dataset.game || "";
    if (sportInput && option.dataset.sport) sportInput.value = option.dataset.sport;
    if (competitionInput && option.dataset.competition) {
      competitionInput.value = option.dataset.competition;
    }
    if (eventDateInput && option.dataset.eventDate) {
      eventDateInput.value = option.dataset.eventDate;
    }
    if (eventIdInput) eventIdInput.value = option.dataset.eventId || "";
    if (sportKeyInput) sportKeyInput.value = option.dataset.sportKey || "";
    if (homeTeamInput) homeTeamInput.value = option.dataset.homeTeam || "";
    if (awayTeamInput) awayTeamInput.value = option.dataset.awayTeam || "";
    container.hidden = true;
  });

  document.addEventListener("click", (event) => {
    if (!container.contains(event.target) && event.target !== gameInput) {
      container.hidden = true;
    }
  });
}

function setupEventAutocomplete() {
  const legacyContainer = document.querySelector("#eventAutocomplete");
  if (legacyContainer) setupSingleEventAutocomplete(legacyContainer);
  document.querySelectorAll("[data-event-autocomplete]").forEach((container) => {
    setupSingleEventAutocomplete(container);
  });
}

function getSurebetIndices() {
  return [...document.querySelectorAll("[data-surebet-row]")]
    .map((row) => Number.parseInt(row.dataset.surebetRow, 10))
    .filter(Boolean)
    .sort((a, b) => a - b);
}

function readSurebetMode(index) {
  return document.querySelector(`[name="surebet_mode_${index}"]`)?.value === "lay" ? "lay" : "back";
}

function surebetBackMultiplier(effectiveOdd, commission) {
  return effectiveOdd > 1 ? 1 + (effectiveOdd - 1) * (1 - commission / 100) : 0;
}

function surebetTargetMultiplier(mode, effectiveOdd, commission) {
  if (effectiveOdd <= 1) return 0;
  return mode === "lay" ? effectiveOdd : surebetBackMultiplier(effectiveOdd, commission);
}

function surebetExposure(row) {
  return row.mode === "lay" ? row.liability : row.stake;
}

function updateSurebetPreview() {
  const firstOdd = readNumber(document.querySelector('[name="surebet_odd_1"]'));
  const firstStake = readNumber(document.querySelector('[name="surebet_stake_1"]'));
  const firstCommission = readNumber(document.querySelector('[name="surebet_commission_1"]'));
  const firstBoost = readNumber(document.querySelector('[name="surebet_boost_1"]'));
  const firstMode = readSurebetMode(1);
  const firstEffectiveOdd = firstOdd * (1 + firstBoost / 100);
  const firstMultiplier = surebetTargetMultiplier(firstMode, firstEffectiveOdd, firstCommission);
  const targetReturn = firstMultiplier > 0 && firstStake > 0 ? firstMultiplier * firstStake : 0;
  const indices = getSurebetIndices();

  indices.filter((index) => index > 1).forEach((index) => {
    const oddInput = document.querySelector(`[name="surebet_odd_${index}"]`);
    const stakeInput = document.querySelector(`[name="surebet_stake_${index}"]`);
    const odd = readNumber(oddInput);
    const commission = readNumber(document.querySelector(`[name="surebet_commission_${index}"]`));
    const boost = readNumber(document.querySelector(`[name="surebet_boost_${index}"]`));
    const mode = readSurebetMode(index);
    const effectiveOdd = odd * (1 + boost / 100);
    const multiplier = surebetTargetMultiplier(mode, effectiveOdd, commission);
    if (stakeInput) {
      stakeInput.value = targetReturn > 0 && multiplier > 0 ? (targetReturn / multiplier).toFixed(2) : "";
    }
  });

  const rows = indices.map((index) => {
    const bookmakerInput = document.querySelector(`[name="surebet_bookmaker_${index}"]`);
    const oddInput = document.querySelector(`[name="surebet_odd_${index}"]`);
    const stakeInput = document.querySelector(`[name="surebet_stake_${index}"]`);
    const commission = readNumber(document.querySelector(`[name="surebet_commission_${index}"]`));
    const cashback = readNumber(document.querySelector(`[name="surebet_cashback_${index}"]`));
    const boost = readNumber(document.querySelector(`[name="surebet_boost_${index}"]`));
    const odd = readNumber(oddInput);
    const mode = readSurebetMode(index);
    const effectiveOdd = odd * (1 + boost / 100);
    const multiplier = surebetTargetMultiplier(mode, effectiveOdd, commission);
    const stake = readNumber(stakeInput);
    const liability = mode === "lay" && effectiveOdd > 1 ? stake * (effectiveOdd - 1) : 0;
    return {
      index,
      bookmaker: bookmakerInput?.value?.trim() || "-",
      label: `Entrada ${index}`,
      mode,
      odd,
      commission,
      cashback,
      boost,
      effectiveOdd,
      multiplier,
      stake,
      liability,
    };
  }).filter((row) => row.multiplier > 0 && row.stake > 0);

  const totalStake = rows.reduce((sum, row) => sum + surebetExposure(row), 0);
  const impliedTotal = rows.reduce((sum, row) => sum + 1 / row.multiplier, 0);
  const scenarios = rows.map((row) => ({
    ...row,
    returnAmount: row.mode === "lay"
      ? row.stake * (1 - row.commission / 100)
      : row.stake * row.multiplier,
  })).map((row, _index, allRows) => {
    const cashbackReturn = allRows
      .filter((candidate) => candidate !== row && candidate.mode === "back")
      .reduce((sum, candidate) => sum + candidate.stake * (candidate.cashback / 100), 0);
    const scenarioNet = allRows.reduce((sum, candidate) => {
      if (candidate === row) {
        return sum + (
          candidate.mode === "lay"
            ? -candidate.liability
            : candidate.returnAmount - candidate.stake
        );
      }
      if (candidate.mode === "lay") {
        return sum + candidate.stake * (1 - candidate.commission / 100);
      }
      return sum - candidate.stake;
    }, 0);
    return {
      ...row,
      cashbackReturn,
      net: scenarioNet + cashbackReturn,
    };
  });
  const best = scenarios.length ? Math.max(...scenarios.map((row) => row.net)) : 0;
  const worst = scenarios.length ? Math.min(...scenarios.map((row) => row.net)) : 0;
  const margin = impliedTotal > 0 ? (1 / impliedTotal - 1) * 100 : 0;

  document.querySelectorAll("[data-surebet-result]").forEach((output) => {
    output.textContent = formatPlainAmount(0);
    output.classList.remove("positive", "negative");
  });
  scenarios.forEach((row) => {
    const output = document.querySelector(`[data-surebet-result="${row.index}"]`);
    if (output) {
      output.textContent = formatPlainAmount(row.net);
      output.classList.toggle("positive", row.net >= 0);
      output.classList.toggle("negative", row.net < 0);
    }
  });

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
          <span>${row.mode === "lay" ? "Lay" : "Back"}</span>
          <span>${row.effectiveOdd.toFixed(2)}</span>
          <span>${formatCurrency(surebetExposure(row))}</span>
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
      <span>Modo</span>
      <span>Odd</span>
      <span>Respons.</span>
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
      <div class="surebet-mode-control">
        <input type="hidden" name="surebet_mode_${index}" value="back" />
        <button class="surebet-mode-toggle" type="button" aria-label="Alternar entrada back ou lay">Back</button>
      </div>
      <label>
        <span class="sr-only">Valor ${index}</span>
        <input type="number" name="surebet_stake_${index}" class="surebet-stake calculated-stake" step="0.01" min="0.01" placeholder="Calculado" readonly />
      </label>
      <label>
        <span class="sr-only">Odd ${index}</span>
        <input type="number" name="surebet_odd_${index}" class="surebet-odd" step="0.01" min="1.01" placeholder="Ex: 2.10" />
      </label>
      <label>
        <span class="sr-only">Comissao % ${index}</span>
        <input type="number" name="surebet_commission_${index}" class="surebet-adjustment" step="0.01" min="0" max="100" placeholder="Ex: 0" />
      </label>
      <label>
        <span class="sr-only">Cashback % ${index}</span>
        <input type="number" name="surebet_cashback_${index}" class="surebet-adjustment" step="0.01" min="0" max="100" placeholder="Ex: 5" />
      </label>
      <label>
        <span class="sr-only">Aumento % ${index}</span>
        <input type="number" name="surebet_boost_${index}" class="surebet-adjustment" step="0.01" min="0" max="100" placeholder="Ex: 10" />
      </label>
      <div class="freebet-control">
        <input type="hidden" name="surebet_freebet_enabled_${index}" value="0" />
        <button class="freebet-toggle" type="button" title="Essa aposta gera freebet" aria-label="Essa aposta gera freebet">🎁</button>
        <div class="freebet-fields">
          <label>
            <span>Valor da freebet</span>
            <input type="number" name="surebet_freebet_amount_${index}" step="0.01" min="0.01" placeholder="Ex: 25.00" />
          </label>
        </div>
        <output class="surebet-entry-return" data-surebet-result="${index}">0,00</output>
      </div>
      <label class="surebet-entry-note">
        <span class="sr-only">Observacao ${index}</span>
        <input type="text" name="surebet_notes_${index}" maxlength="180" placeholder="Observacao" autocomplete="off" />
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
  const modeToggle = event.target.closest(".surebet-mode-toggle");
  if (modeToggle) {
    const control = modeToggle.closest(".surebet-mode-control");
    const hiddenInput = control?.querySelector('input[name^="surebet_mode_"]');
    if (!hiddenInput) return;
    const isLay = hiddenInput.value !== "lay";
    hiddenInput.value = isLay ? "lay" : "back";
    modeToggle.textContent = isLay ? "Lay" : "Back";
    modeToggle.classList.toggle("is-lay", isLay);
    updateSurebetPreview();
    return;
  }

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
setupEventAutocomplete();
activateScreen();
drawChart();
drawBarChart();

window.addEventListener("hashchange", activateScreen);
window.addEventListener("resize", drawChart);
window.addEventListener("resize", drawBarChart);
