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

function updateBetPreview() {
  const odds = Number.parseFloat(document.querySelector("#id_odds")?.value || 0);
  const stake = Number.parseFloat(document.querySelector("#id_stake")?.value || 0);
  const bankrollId = Number.parseInt(document.querySelector("#id_bankroll")?.value || 0, 10);
  const commissionPercentage = Number.parseFloat(
    document.querySelector("#id_exchange_commission")?.value || 0,
  );
  const bankrollData = document.querySelector("#bankroll-options");
  const bankrolls = bankrollData ? JSON.parse(bankrollData.textContent) : [];
  const selectedBankroll = bankrolls.find((bankroll) => bankroll.id === bankrollId);

  const grossProfit = odds > 1 && stake > 0 ? stake * (odds - 1) : 0;
  const commission = grossProfit * (commissionPercentage / 100);
  const netProfit = grossProfit - commission;
  const totalReturn = stake + netProfit;
  const units = selectedBankroll?.unit ? stake / selectedBankroll.unit : 0;

  document.querySelector("#previewProfit").textContent = formatCurrency(netProfit);
  document.querySelector("#previewCommission").textContent = formatCurrency(commission);
  document.querySelector("#previewReturn").textContent = formatCurrency(totalReturn);
  document.querySelector("#previewUnits").textContent = `${units.toFixed(2)}u`;
}

["#id_bankroll", "#id_odds", "#id_stake", "#id_exchange_commission"].forEach((selector) => {
  document.querySelector(selector)?.addEventListener("input", updateBetPreview);
  document.querySelector(selector)?.addEventListener("change", updateBetPreview);
});

updateBetPreview();
activateScreen();
drawChart();
drawBarChart();

window.addEventListener("hashchange", activateScreen);
window.addEventListener("resize", drawChart);
window.addEventListener("resize", drawBarChart);
