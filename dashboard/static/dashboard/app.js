function formatCurrency(value) {
  const currency = document.body.dataset.currencyCode || "BRL";
  const locale = document.body.dataset.currencyLocale || "pt-BR";
  return value.toLocaleString(locale, {
    style: "currency",
    currency,
  });
}

const UI_TRANSLATIONS = {
  es: {
    "Gestão inteligente": "Gestión inteligente",
    Dashboard: "Panel",
    Financeiro: "Finanzas",
    "Nova aposta": "Nueva apuesta",
    Histórico: "Historial",
    Metas: "Metas",
    Configurações: "Configuración",
    "Conta ativa": "Cuenta activa",
    "Trocar senha": "Cambiar contraseña",
    Sair: "Salir",
    "Teste gratuito": "Prueba gratis",
    "Ver planos": "Ver planes",
    "Mês": "Mes",
    "Ano": "Año",
    "Tipo de aposta": "Tipo de apuesta",
    "Apostas simples": "Apuestas simples",
    "Arbitragem": "Arbitraje",
    "Extração de freebet": "Extracción de freebet",
    "Aplicar": "Aplicar",
    "Atual": "Actual",
    "Conta principal": "Cuenta principal",
    "Selecionar conta bancária": "Seleccionar cuenta bancaria",
    "Nenhuma conta": "Ninguna cuenta",
    "cadastre em Financeiro": "regístrala en Finanzas",
    "Ocultar saldo": "Ocultar saldo",
    "Mostrar saldo": "Mostrar saldo",
    "Saldo total": "Saldo total",
    "disponível": "disponible",
    "Apostas abertas": "Apuestas abiertas",
    "exposição": "exposición",
    "Total apostado": "Total apostado",
    "apostas feitas": "apuestas realizadas",
    "Lucro líquido": "Ganancia neta",
    "resultado fechado": "resultado cerrado",
    "apostas registradas": "apuestas registradas",
    "Freebets": "Freebets",
    "bonus pendentes": "bonos pendientes",
    "Calendário": "Calendario",
    "Resultado diário de": "Resultado diario de",
    "aposta(s) fechada(s)": "apuesta(s) cerrada(s)",
    "aposta(s)": "apuesta(s)",
    "Gestão de saldos": "Gestión de saldos",
    "Disponível": "Disponible",
    "Aberto": "Abierto",
    "Total": "Total",
    "Atalhos": "Accesos rápidos",
    "Cadastrar": "Registrar",
    "Nova entidade": "Nueva entidad",
    "Cliente, projeto ou operador": "Cliente, proyecto u operador",
    "Nome": "Nombre",
    "Salvar entidade": "Guardar entidad",
    "Nova casa": "Nueva casa",
    "Saldo inicial vinculado a uma entidade": "Saldo inicial vinculado a una entidad",
    "Entidade": "Entidad",
    "Casa": "Casa",
    "Saldo inicial": "Saldo inicial",
    "Cadastrar saldo": "Registrar saldo",
    "Buscar casa": "Buscar casa",
    "Buscar por nome ou casa de aposta...": "Buscar por nombre o casa de apuestas...",
    "Filtrar bancas por entidade": "Filtrar bancas por entidad",
    "Opções de filtro": "Opciones de filtro",
    Filtros: "Filtros",
    "Ocultar casas com saldo zerado": "Ocultar casas con saldo cero",
    "Todas": "Todas",
    "Editar banca": "Editar banca",
    "Editar": "Editar",
    "Valor disponível": "Valor disponible",
    "Valor aberto": "Valor abierto",
    "Valor total": "Valor total",
    "+ Depósito": "+ Depósito",
    "- Saque": "- Retiro",
    "Reajuste": "Ajuste",
    "Valor": "Valor",
    "Conta": "Cuenta",
    "Observação rápida": "Observación rápida",
    "Aplicar": "Aplicar",
    "Cadastre sua primeira casa para começar.": "Registra tu primera casa para empezar.",
    "Movimentações": "Movimientos",
    "Financeiro e transferências": "Finanzas y transferencias",
    "Gerenciar movimentações": "Gestionar movimientos",
    "Configurações": "Configuración",
    "Preferências da conta": "Preferencias de la cuenta",
    "Idioma": "Idioma",
    "Moeda": "Moneda",
    "Moeda atual": "Moneda actual",
    "Símbolo": "Símbolo",
    "Salvar configurações": "Guardar configuración",
    "Configurações salvas com sucesso.": "Configuración guardada correctamente.",
    "Português": "Portugués",
    "Español": "Español",
    "English": "Inglés",
    "Espanhol": "Español",
    "Inglês": "Inglés",
    "Real brasileiro": "Real brasileño",
    "Dólar": "Dólar",
    "Euro": "Euro",
    "Estratégia": "Estrategia",
    "Resultado": "Resultado",
    "Odd": "Cuota",
    "Stake": "Stake",
    "Comissão": "Comisión",
    "Status": "Estado",
    "Retorno possível": "Retorno posible",
    "Lucro": "Ganancia",
    "Ações": "Acciones",
    "Mercado": "Mercado",
    "Tipo": "Tipo",
    "Pre-live": "Pre-live",
    "Ao vivo": "En vivo",
    "Ganha": "Ganada",
    "Perdida": "Perdida",
    "Aberta": "Abierta",
    "Excluir": "Eliminar",
    "Observações": "Observaciones",
    "Respons.": "Respons.",
    "Retorno": "Retorno",
    "Cashback": "Cashback",
    "Ganha / Perde": "Gana / Pierde",
    "Responsabilidade": "Responsabilidad",
    "Retorno por resultado": "Retorno por resultado",
    "Melhor cenário": "Mejor escenario",
    "Pior cenário": "Peor escenario",
    "Dinheiro usado": "Dinero usado",
    "Valor extraído alvo": "Valor extraído objetivo",
    "Conversão": "Conversión",
    "Lucro estimado": "Ganancia estimada",
    "Buscando jogos...": "Buscando partidos...",
    "Nenhum jogo encontrado. Você pode continuar digitando manualmente.": "No se encontró ningún partido. Puedes seguir escribiendo manualmente.",
    "Nenhuma odd disponível para esse jogo com os filtros atuais.": "No hay cuotas disponibles para ese partido con los filtros actuales.",
    "Escolha um jogo da lista antes de carregar as odds.": "Elige un partido de la lista antes de cargar las cuotas.",
    "Carregando odds por casa...": "Cargando cuotas por casa...",
    "Não foi possível carregar as odds.": "No fue posible cargar las cuotas.",
    "Não foi possível carregar as odds agora.": "No fue posible cargar las cuotas ahora.",
    "Selecione a casa": "Selecciona la casa",
  },
  en: {
    "Gestão inteligente": "Smart management",
    Dashboard: "Dashboard",
    Financeiro: "Finance",
    "Nova aposta": "New bet",
    Histórico: "History",
    Metas: "Goals",
    Configurações: "Settings",
    "Conta ativa": "Active account",
    "Trocar senha": "Change password",
    Sair: "Log out",
    "Teste gratuito": "Free trial",
    "Ver planos": "View plans",
    "Mês": "Month",
    "Ano": "Year",
    "Tipo de aposta": "Bet type",
    "Apostas simples": "Simple bets",
    "Arbitragem": "Arbitrage",
    "Extração de freebet": "Freebet extraction",
    "Aplicar": "Apply",
    "Atual": "Current",
    "Conta principal": "Primary account",
    "Selecionar conta bancária": "Select bank account",
    "Nenhuma conta": "No account",
    "cadastre em Financeiro": "add it in Finance",
    "Ocultar saldo": "Hide balance",
    "Mostrar saldo": "Show balance",
    "Saldo total": "Total balance",
    "disponível": "available",
    "Apostas abertas": "Open bets",
    "exposição": "exposure",
    "Total apostado": "Total staked",
    "apostas feitas": "bets placed",
    "Lucro líquido": "Net profit",
    "resultado fechado": "settled result",
    "apostas registradas": "registered bets",
    "Freebets": "Freebets",
    "bonus pendentes": "pending bonuses",
    "Calendário": "Calendar",
    "Resultado diário de": "Daily result for",
    "aposta(s) fechada(s)": "settled bet(s)",
    "aposta(s)": "bet(s)",
    "Gestão de saldos": "Balance management",
    "Disponível": "Available",
    "Aberto": "Open",
    "Total": "Total",
    "Atalhos": "Shortcuts",
    "Cadastrar": "Add",
    "Nova entidade": "New entity",
    "Cliente, projeto ou operador": "Client, project or operator",
    "Nome": "Name",
    "Salvar entidade": "Save entity",
    "Nova casa": "New bookmaker",
    "Saldo inicial vinculado a uma entidade": "Initial balance linked to an entity",
    "Entidade": "Entity",
    "Casa": "Bookmaker",
    "Saldo inicial": "Initial balance",
    "Cadastrar saldo": "Add balance",
    "Buscar casa": "Search bookmaker",
    "Buscar por nome ou casa de aposta...": "Search by name or bookmaker...",
    "Filtrar bancas por entidade": "Filter bankrolls by entity",
    "Opções de filtro": "Filter options",
    Filtros: "Filters",
    "Ocultar casas com saldo zerado": "Hide bookmakers with zero balance",
    "Todas": "All",
    "Editar banca": "Edit bankroll",
    "Editar": "Edit",
    "Valor disponível": "Available value",
    "Valor aberto": "Open value",
    "Valor total": "Total value",
    "+ Depósito": "+ Deposit",
    "- Saque": "- Withdraw",
    "Reajuste": "Adjustment",
    "Valor": "Amount",
    "Conta": "Account",
    "Observação rápida": "Quick note",
    "Cadastre sua primeira casa para começar.": "Add your first bookmaker to get started.",
    "Movimentações": "Transactions",
    "Financeiro e transferências": "Finance and transfers",
    "Gerenciar movimentações": "Manage transactions",
    "Preferências da conta": "Account preferences",
    "Idioma": "Language",
    "Moeda": "Currency",
    "Moeda atual": "Current currency",
    "Símbolo": "Symbol",
    "Salvar configurações": "Save settings",
    "Configurações salvas com sucesso.": "Settings saved successfully.",
    "Português": "Portuguese",
    "Español": "Spanish",
    "English": "English",
    "Espanhol": "Spanish",
    "Inglês": "English",
    "Real brasileiro": "Brazilian real",
    "Dólar": "Dollar",
    "Euro": "Euro",
    "Estratégia": "Strategy",
    "Resultado": "Result",
    "Odd": "Odds",
    "Stake": "Stake",
    "Comissão": "Commission",
    "Status": "Status",
    "Retorno possível": "Possible return",
    "Lucro": "Profit",
    "Ações": "Actions",
    "Mercado": "Market",
    "Tipo": "Type",
    "Pre-live": "Pre-live",
    "Ao vivo": "Live",
    "Ganha": "Won",
    "Perdida": "Lost",
    "Aberta": "Open",
    "Excluir": "Delete",
    "Observações": "Notes",
    "Respons.": "Liability",
    "Retorno": "Return",
    "Cashback": "Cashback",
    "Ganha / Perde": "Win / Lose",
    "Responsabilidade": "Liability",
    "Retorno por resultado": "Return per outcome",
    "Melhor cenário": "Best case",
    "Pior cenário": "Worst case",
    "Dinheiro usado": "Cash used",
    "Valor extraído alvo": "Target extracted value",
    "Conversão": "Conversion",
    "Lucro estimado": "Estimated profit",
    "Buscando jogos...": "Searching games...",
    "Nenhum jogo encontrado. Você pode continuar digitando manualmente.": "No game found. You can keep typing manually.",
    "Nenhuma odd disponível para esse jogo com os filtros atuais.": "No odds available for this game with the current filters.",
    "Escolha um jogo da lista antes de carregar as odds.": "Choose a game from the list before loading odds.",
    "Carregando odds por casa...": "Loading odds by bookmaker...",
    "Não foi possível carregar as odds.": "Could not load odds.",
    "Não foi possível carregar as odds agora.": "Could not load odds right now.",
    "Selecione a casa": "Select bookmaker",
  },
};

function translateTextValue(value, translations) {
  const trimmed = value.trim();
  if (!trimmed) return value;
  if (translations[trimmed]) {
    return value.replace(trimmed, translations[trimmed]);
  }
  return value
    .replace(/\bdisponível\b/g, translations["disponível"] || "disponível")
    .replace(/\bexposição\b/g, translations["exposição"] || "exposição")
    .replace(/\bapostas feitas\b/g, translations["apostas feitas"] || "apostas feitas")
    .replace(/\bapostas registradas\b/g, translations["apostas registradas"] || "apostas registradas")
    .replace(/\baposta\(s\)\b/g, translations["aposta(s)"] || "aposta(s)")
    .replace(/\bResultado diário de\b/g, translations["Resultado diário de"] || "Resultado diário de");
}

function translateInterface(root = document.body) {
  const language = document.body.dataset.language || "pt-BR";
  const translations = UI_TRANSLATIONS[language];
  if (!translations || !root) return;

  const walker = document.createTreeWalker(
    root,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent || ["SCRIPT", "STYLE", "TEXTAREA"].includes(parent.tagName)) {
          return NodeFilter.FILTER_REJECT;
        }
        return node.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    },
  );
  const textNodes = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode);
  textNodes.forEach((node) => {
    node.nodeValue = translateTextValue(node.nodeValue, translations);
  });

  root.querySelectorAll?.("[placeholder], [aria-label], [title], option, input[type='submit']").forEach((element) => {
    ["placeholder", "aria-label", "title"].forEach((attribute) => {
      const value = element.getAttribute(attribute);
      if (value) element.setAttribute(attribute, translateTextValue(value, translations));
    });
    if (element.tagName === "OPTION" || element.type === "submit") {
      element.textContent = translateTextValue(element.textContent, translations);
      if (element.value && translations[element.value]) element.value = translations[element.value];
    }
  });
}

function setupInterfaceTranslationObserver() {
  const language = document.body.dataset.language || "pt-BR";
  if (!UI_TRANSLATIONS[language]) return;

  let translating = false;
  const observer = new MutationObserver((mutations) => {
    if (translating) return;
    translating = true;
    window.requestAnimationFrame(() => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) translateInterface(node);
          if (node.nodeType === Node.TEXT_NODE && node.parentElement) {
            translateInterface(node.parentElement);
          }
        });
      });
      translating = false;
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

function formatPlainAmount(value) {
  return value.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function parseBrazilianCurrencyAmount(value) {
  return Number.parseFloat(value.replace(/\./g, "").replace(",", "."));
}

function applyUserCurrencyPreference() {
  const currency = document.body.dataset.currencyCode || "BRL";
  if (currency === "BRL") return;

  const replaceCurrencyText = (text) =>
    text.replace(/R\$\s*(-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})/g, (_match, amount) =>
      formatCurrency(parseBrazilianCurrencyAmount(amount)),
    ).replace(/R\$\s*--,--/g, `${document.body.dataset.currencySymbol || "$"} --`);

  const walker = document.createTreeWalker(
    document.body,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        return node.nodeValue.includes("R$") ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    },
  );
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach((node) => {
    node.nodeValue = replaceCurrencyText(node.nodeValue);
  });

  document.querySelectorAll("[data-balance]").forEach((element) => {
    element.dataset.balance = replaceCurrencyText(element.dataset.balance || "");
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
  area.addColorStop(0, "rgba(90, 167, 255, 0.28)");
  area.addColorStop(1, "rgba(90, 167, 255, 0)");

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
  context.strokeStyle = "#5aa7ff";
  context.lineWidth = 4;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.stroke();

  points.forEach((point) => {
    context.beginPath();
    context.arc(point.x, point.y, 4, 0, Math.PI * 2);
    context.fillStyle = "#101414";
    context.fill();
    context.strokeStyle = "#5aa7ff";
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

    const barColor = value > 0 ? "#5aa7ff" : value < 0 ? "#f06f65" : "#56635f";
    context.fillStyle = barColor;
    if (index === hoveredIndex) {
      context.shadowColor = value >= 0 ? "rgba(90, 167, 255, 0.32)" : "rgba(240, 111, 101, 0.32)";
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
    context.fillStyle = bar.value >= 0 ? "#5aa7ff" : "#f06f65";
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
  const screenSections = [...document.querySelectorAll("[data-screen]")];
  if (!screenSections.length) return;
  const screenAliases = {
    overview: "dashboard",
    calendar: "dashboard",
  };
  const publicScreens = new Set(["dashboard", "new-bet", "bankroll", "bets", "goals", "settings"]);
  const requestedScreen = window.location.hash.replace("#", "") || "dashboard";
  const activeScreen = screenAliases[requestedScreen] || requestedScreen;
  const availableScreens = screenSections.map(
    (section) => section.dataset.screen,
  );
  const safeScreen =
    publicScreens.has(activeScreen) && availableScreens.includes(activeScreen)
      ? activeScreen
      : "dashboard";

  screenSections.forEach((section) => {
    section.classList.toggle("is-active", section.dataset.screen === safeScreen);
  });

  document.querySelectorAll(".nav-list a").forEach((link) => {
    const linkScreen = screenAliases[link.hash.replace("#", "")] || link.hash.replace("#", "");
    link.classList.toggle("active", linkScreen === safeScreen);
  });

  const messageStack = document.querySelector(".message-stack");
  if (messageStack) {
    if (!messageStack.dataset.screen) {
      messageStack.dataset.screen = safeScreen;
    } else if (messageStack.dataset.screen !== safeScreen) {
      messageStack.remove();
    }
  }

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

function setupAccountPopover() {
  const popover = document.querySelector(".account-popover");
  if (!popover) return;

  document.addEventListener("click", (event) => {
    if (!popover.contains(event.target)) popover.removeAttribute("open");
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") popover.removeAttribute("open");
  });
}

function setupCollapsiblePanels() {
  document.querySelectorAll("[data-collapsible-toggle]").forEach((button) => {
    const target = document.getElementById(button.dataset.collapsibleToggle);
    if (!target) return;

    button.addEventListener("click", () => {
      const isOpen = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", isOpen ? "false" : "true");
      target.hidden = isOpen;
    });
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
  if (!document.querySelector("#previewProfit")) return;
  const odds = Number.parseFloat(document.querySelector("#id_odds")?.value || 0);
  const boost = Number.parseFloat(document.querySelector("#id_odds_boost")?.value || 0);
  const effectiveOdds = boostedProfitOdds(odds, boost);
  const stakeInput = document.querySelector("#id_stake");
  const stake = Number.parseFloat(stakeInput?.value || 0);
  const freebetSelect = document.querySelector("[data-simple-freebet-select]");
  const selectedFreebet = freebetSelect?.selectedOptions?.[0];
  const freebetAmount = Number.parseFloat(selectedFreebet?.dataset.amount || 0);
  const usesFreebet = Boolean(freebetSelect?.value && freebetAmount > 0);
  const commissionPercentage = Number.parseFloat(
    document.querySelector("#id_exchange_commission")?.value || 0,
  );

  if (usesFreebet && stakeInput && document.activeElement !== stakeInput) {
    stakeInput.value = freebetAmount.toFixed(2);
  }

  const effectiveStake = usesFreebet ? freebetAmount : stake;
  const grossProfit = effectiveOdds > 1 && effectiveStake > 0 ? effectiveStake * (effectiveOdds - 1) : 0;
  const commission = grossProfit * (commissionPercentage / 100);
  const netProfit = grossProfit - commission;
  const totalReturn = usesFreebet ? netProfit : effectiveStake + netProfit;

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

function setupBalanceVisibility() {
  const card = document.querySelector("[data-balance-card]");
  const button = document.querySelector("[data-balance-toggle]");
  const value = document.querySelector("[data-balance-value]");
  const select = document.querySelector("[data-bank-account-select]");
  const meta = document.querySelector("[data-bank-account-meta]");
  const accountName = document.querySelector("[data-bank-account-name]");
  if (!card || !button || !value) return;

  const hiddenValue = `${document.body.dataset.currencySymbol || "R$"} --`;
  let visibleValue = value.textContent.trim();

  function applyHiddenState(isHidden) {
    card.classList.toggle("is-balance-hidden", isHidden);
    value.textContent = isHidden ? hiddenValue : visibleValue;
    button.setAttribute("aria-pressed", String(isHidden));
    button.setAttribute("aria-label", isHidden ? "Mostrar saldo" : "Ocultar saldo");
  }

  function selectAccount(accountId) {
    if (!select) return;
    const option = [...select.options].find((candidate) => candidate.value === accountId)
      || select.selectedOptions[0];
    if (!option) return;

    select.value = option.value;
    visibleValue = option.dataset.balance || "R$ 0,00";
    if (accountName) accountName.textContent = option.dataset.name || option.textContent.trim();
    if (meta) meta.textContent = option.dataset.bank || "";
    localStorage.setItem("freebetarBankAccountId", option.value);
    applyHiddenState(card.classList.contains("is-balance-hidden"));
  }

  applyHiddenState(localStorage.getItem("freebetarBalanceHidden") === "1");
  if (select) {
    selectAccount(localStorage.getItem("freebetarBankAccountId") || select.value);
    select.addEventListener("change", () => selectAccount(select.value));
  }

  button.addEventListener("click", () => {
    const nextState = !card.classList.contains("is-balance-hidden");
    localStorage.setItem("freebetarBalanceHidden", nextState ? "1" : "0");
    applyHiddenState(nextState);
  });
}

function localDateInputValue(date = new Date()) {
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 10);
}

function readNumber(input) {
  return Number.parseFloat((input?.value || "0").replace(",", ".")) || 0;
}

function boostedProfitOdds(odds, boost) {
  if (odds <= 0) return 0;
  return 1 + (odds - 1) * (1 + boost / 100);
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
  const sportInput = form.querySelector("[data-event-sport-input]") || form.querySelector("[name='surebet_sport']") || document.querySelector("#id_sport");
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
          '<div class="event-empty">Nenhum jogo encontrado. Você pode continuar digitando manualmente.</div>',
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
        '<div class="event-empty">Não foi possível buscar jogos agora. Você pode digitar manualmente.</div>',
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
    if (sportInput) {
      const isSportSelect = sportInput.matches("select");
      const nextSport = isSportSelect
        ? option.dataset.sportKey || sportInput.value
        : option.dataset.sport || "";
      if (nextSport) sportInput.value = nextSport;
    }
    if (competitionInput && option.dataset.competition) {
      competitionInput.value = option.dataset.competition;
    }
    if (eventDateInput && option.dataset.eventDate) {
      eventDateInput.value = option.dataset.eventDate.slice(0, 10);
    }
    if (eventIdInput) eventIdInput.value = option.dataset.eventId || "";
    if (sportKeyInput) sportKeyInput.value = option.dataset.sportKey || "";
    if (homeTeamInput) homeTeamInput.value = option.dataset.homeTeam || "";
    if (awayTeamInput) awayTeamInput.value = option.dataset.awayTeam || "";
    container.hidden = true;
  });

  sportInput?.addEventListener("change", () => {
    if (sportKeyInput) sportKeyInput.value = "";
    if (eventIdInput) eventIdInput.value = "";
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

function formatOdd(value) {
  return Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function readPreviousEventOdds(eventId) {
  try {
    return JSON.parse(window.sessionStorage.getItem(`event-odds:${eventId}`) || "{}");
  } catch (_error) {
    return {};
  }
}

function writePreviousEventOdds(eventId, payload) {
  try {
    window.sessionStorage.setItem(`event-odds:${eventId}`, JSON.stringify(payload));
  } catch (_error) {
    // Session storage can be unavailable in private browsing modes.
  }
}

function renderEventOddsBoard(board, payload, eventId) {
  if (!board) return;
  const outcomeNames = payload.outcome_names || [];
  const bookmakers = payload.bookmakers || [];

  if (!bookmakers.length || !outcomeNames.length) {
    board.innerHTML = '<div class="empty-state">Nenhuma odd disponível para esse jogo com os filtros atuais.</div>';
    return;
  }

  const previous = readPreviousEventOdds(eventId);
  const nextSnapshot = {};
  const rows = bookmakers.map((bookmaker) => {
    const bookmakerKey = bookmaker.key || bookmaker.title;
    const odds = outcomeNames.map((outcomeName) => {
      const price = bookmaker.outcomes[outcomeName];
      if (!price) {
        return '<span class="event-odd is-empty">-</span>';
      }

      const snapshotKey = `${bookmakerKey}:${outcomeName}`;
      const oldPrice = previous[snapshotKey];
      nextSnapshot[snapshotKey] = price;
      const trend =
        oldPrice && price > oldPrice ? "is-up" : oldPrice && price < oldPrice ? "is-down" : "";
      const arrow = trend === "is-up" ? "↑" : trend === "is-down" ? "↓" : "";

      return `
        <button class="event-odd ${trend}" type="button" data-odd="${escapeHtml(price)}" title="Usar odd ${escapeHtml(formatOdd(price))}">
          <span>${arrow}</span>
          <strong>${escapeHtml(formatOdd(price))}</strong>
        </button>
      `;
    }).join("");

    return `
      <div class="event-odds-row">
        <div class="bookmaker-pill">${escapeHtml(bookmaker.title || bookmaker.key || "Casa")}</div>
        <span class="live-badge">Pré</span>
        <div class="event-odds-values">${odds}</div>
      </div>
    `;
  }).join("");

  board.innerHTML = `
    <div class="event-odds-header">
      <div>
        <strong>${escapeHtml(payload.event || "Jogo selecionado")}</strong>
        <span>${escapeHtml(payload.sport || "")}${payload.used_cache ? " | cache" : ""}</span>
      </div>
      <div class="event-outcome-labels">
        ${outcomeNames.map((name) => `<span>${escapeHtml(name)}</span>`).join("")}
      </div>
    </div>
    ${payload.filter_note ? `<div class="event-odds-note">${escapeHtml(payload.filter_note)}</div>` : ""}
    <div class="event-odds-list">${rows}</div>
  `;
  writePreviousEventOdds(eventId, nextSnapshot);
}

function setupEventOddsLookup() {
  const form = document.querySelector("[data-event-odds-form]");
  const board = document.querySelector("[data-event-odds-board]");
  if (!form || !board) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const eventIdInput = form.querySelector("[name='event_id']");
    const sportKeyInput = form.querySelector("[name='sport_key']");
    const sportInput = form.querySelector("[data-event-sport-input]");
    const eventId = eventIdInput?.value || "";
    if (!eventId) {
      board.innerHTML = '<div class="empty-state">Escolha um jogo da lista antes de carregar as odds.</div>';
      return;
    }

    const params = new URLSearchParams(new FormData(form));
    if (!sportKeyInput?.value && sportInput?.value) {
      params.set("sport_key", sportInput.value);
    }

    board.innerHTML = '<div class="empty-state">Carregando odds por casa...</div>';
    try {
      const response = await fetch(`${form.dataset.oddsUrl}?${params.toString()}`);
      const payload = await response.json();
      if (!response.ok) {
        board.innerHTML = `<div class="empty-state">${escapeHtml(payload.error || "Não foi possível carregar as odds.")}</div>`;
        return;
      }
      renderEventOddsBoard(board, payload, eventId);
    } catch (_error) {
      board.innerHTML = '<div class="empty-state">Não foi possível carregar as odds agora.</div>';
    }
  });

  board.addEventListener("click", (event) => {
    const oddButton = event.target.closest("[data-odd]");
    const simpleOddInput = document.querySelector("#id_odds");
    if (!oddButton || !simpleOddInput) return;
    simpleOddInput.value = oddButton.dataset.odd;
    simpleOddInput.dispatchEvent(new Event("input", { bubbles: true }));
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

function bankrollOptionsHtml() {
  return document.querySelector("#bankrollOptionsTemplate")?.innerHTML?.trim()
    || '<option value="">Selecione a casa</option>';
}

function selectedBankrollText(name) {
  const select = document.querySelector(`[name="${name}"]`);
  const option = select?.options?.[select.selectedIndex];
  return option && option.value ? option.textContent.trim() : "-";
}

function surebetBackMultiplier(effectiveOdd, commission) {
  return effectiveOdd > 1 ? 1 + (effectiveOdd - 1) * (1 - commission / 100) : 0;
}

function surebetTargetMultiplier(mode, effectiveOdd, commission) {
  if (effectiveOdd <= 1) return 0;
  return mode === "lay" ? effectiveOdd : surebetBackMultiplier(effectiveOdd, commission);
}

function surebetGrossReturnMultiplier(mode, effectiveOdd, commission) {
  if (effectiveOdd <= 1) return 0;
  return mode === "lay"
    ? effectiveOdd - commission / 100
    : surebetBackMultiplier(effectiveOdd, commission);
}

function surebetExposure(row) {
  return row.mode === "lay" ? row.liability : row.stake;
}

function updateSurebetPreview() {
  if (!document.querySelector("#surebetEntries")) return;
  const activeResultInput = document.activeElement?.classList?.contains("surebet-entry-return")
    ? document.activeElement
    : null;
  const activeStakeInput = document.activeElement?.classList?.contains("surebet-stake")
    ? document.activeElement
    : null;
  const firstOdd = readNumber(document.querySelector('[name="surebet_odd_1"]'));
  const firstStake = readNumber(document.querySelector('[name="surebet_stake_1"]'));
  const firstCommission = readNumber(document.querySelector('[name="surebet_commission_1"]'));
  const firstBoost = readNumber(document.querySelector('[name="surebet_boost_1"]'));
  const firstMode = readSurebetMode(1);
  const firstEffectiveOdd = boostedProfitOdds(firstOdd, firstBoost);
  const firstMultiplier = surebetGrossReturnMultiplier(firstMode, firstEffectiveOdd, firstCommission);
  const targetReturn = firstMultiplier > 0 && firstStake > 0 ? firstMultiplier * firstStake : 0;
  const indices = getSurebetIndices();
  const firstResultInput = document.querySelector('[name="surebet_net_1"]');
  const firstManualNet = firstResultInput?.dataset.manualResult === "true"
    ? readNumber(firstResultInput)
    : null;
  const firstExposure = firstMode === "lay" && firstEffectiveOdd > 1
    ? firstStake * (firstEffectiveOdd - 1)
    : firstStake;
  const otherStakeTargets = new Map();

  if (firstManualNet !== null && targetReturn > 0) {
    const otherRows = indices.filter((index) => index > 1).map((index) => {
      const odd = readNumber(document.querySelector(`[name="surebet_odd_${index}"]`));
      const commission = readNumber(document.querySelector(`[name="surebet_commission_${index}"]`));
      const boost = readNumber(document.querySelector(`[name="surebet_boost_${index}"]`));
      const effectiveOdd = boostedProfitOdds(odd, boost);
      const multiplier = surebetGrossReturnMultiplier(readSurebetMode(index), effectiveOdd, commission);
      return { index, multiplier };
    }).filter((row) => row.multiplier > 0);
    const targetOtherExposure = Math.max(targetReturn - firstExposure - firstManualNet, 0);
    const inverseTotal = otherRows.reduce((sum, row) => sum + 1 / row.multiplier, 0);

    otherRows.forEach((row) => {
      if (inverseTotal > 0) {
        otherStakeTargets.set(row.index, targetOtherExposure * (1 / row.multiplier) / inverseTotal);
      }
    });
  }

  indices.filter((index) => index > 1).forEach((index) => {
    const oddInput = document.querySelector(`[name="surebet_odd_${index}"]`);
    const stakeInput = document.querySelector(`[name="surebet_stake_${index}"]`);
    const odd = readNumber(oddInput);
    const commission = readNumber(document.querySelector(`[name="surebet_commission_${index}"]`));
    const boost = readNumber(document.querySelector(`[name="surebet_boost_${index}"]`));
    const mode = readSurebetMode(index);
    const effectiveOdd = boostedProfitOdds(odd, boost);
    const multiplier = surebetGrossReturnMultiplier(mode, effectiveOdd, commission);
    if (
      stakeInput &&
      stakeInput !== activeStakeInput &&
      stakeInput.dataset.manualStake !== "true"
    ) {
      const nextStake = otherStakeTargets.has(index)
        ? otherStakeTargets.get(index)
        : targetReturn > 0 && multiplier > 0 ? targetReturn / multiplier : 0;
      stakeInput.value = nextStake > 0 ? nextStake.toFixed(2) : "";
    }
  });

  const rows = indices.map((index) => {
    const oddInput = document.querySelector(`[name="surebet_odd_${index}"]`);
    const stakeInput = document.querySelector(`[name="surebet_stake_${index}"]`);
    const commission = readNumber(document.querySelector(`[name="surebet_commission_${index}"]`));
    const cashback = readNumber(document.querySelector(`[name="surebet_cashback_${index}"]`));
    const boost = readNumber(document.querySelector(`[name="surebet_boost_${index}"]`));
    const odd = readNumber(oddInput);
    const mode = readSurebetMode(index);
    const effectiveOdd = boostedProfitOdds(odd, boost);
    const multiplier = surebetGrossReturnMultiplier(mode, effectiveOdd, commission);
    const stake = readNumber(stakeInput);
    const liability = mode === "lay" && effectiveOdd > 1 ? stake * (effectiveOdd - 1) : 0;
    const returnAmount = multiplier > 0 && stake > 0 ? stake * multiplier : 0;
    return {
      index,
      bookmaker: selectedBankrollText(`surebet_bankroll_${index}`),
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
      returnAmount,
    };
  }).filter((row) => row.multiplier > 0 && row.stake > 0);

  document.querySelectorAll("[data-surebet-liability]").forEach((output) => {
    output.textContent = "";
    output.closest(".surebet-entry-group")?.classList.remove("has-liability");
  });
  rows.forEach((row) => {
    const output = document.querySelector(`[data-surebet-liability="${row.index}"]`);
    if (output) {
      const group = output.closest(".surebet-entry-group");
      const hasLiability = row.mode === "lay";
      group?.classList.toggle("has-liability", hasLiability);
      output.textContent = hasLiability ? formatCurrency(row.liability) : "";
    }
  });

  const totalStake = rows.reduce((sum, row) => sum + surebetExposure(row), 0);
  const impliedTotal = rows.reduce((sum, row) => sum + 1 / row.multiplier, 0);
  const scenarios = rows.map((row, _index, allRows) => {
    const cashbackReturn = allRows
      .filter((candidate) => candidate !== row && candidate.mode === "back")
      .reduce((sum, candidate) => sum + candidate.stake * (candidate.cashback / 100), 0);
    const scenarioNet = row.returnAmount - totalStake;
    const resultInput = document.querySelector(`[name="surebet_net_${row.index}"]`);
    const net = resultInput === activeResultInput || resultInput?.dataset.manualResult === "true"
      ? readNumber(resultInput)
      : scenarioNet + cashbackReturn;
    return {
      ...row,
      cashbackReturn,
      net,
    };
  });
  const best = scenarios.length ? Math.max(...scenarios.map((row) => row.net)) : 0;
  const worst = scenarios.length ? Math.min(...scenarios.map((row) => row.net)) : 0;
  const margin = impliedTotal > 0 ? (1 / impliedTotal - 1) * 100 : 0;

  scenarios.forEach((row) => {
    const resultInput = document.querySelector(`[name="surebet_net_${row.index}"]`);
    if (
      resultInput &&
      resultInput !== activeResultInput &&
      resultInput.dataset.manualResult !== "true"
    ) {
      resultInput.value = row.net.toFixed(2);
    }
    if (resultInput) {
      resultInput.classList.toggle("positive", row.net >= 0);
      resultInput.classList.toggle("negative", row.net < 0);
    }
  });

  const totalOutput = document.querySelector("#surebetTotal");
  const targetOutput = document.querySelector("#surebetTargetReturn");
  const marginOutput = document.querySelector("#surebetMargin");
  const bestOutput = document.querySelector("#surebetBest");
  const worstOutput = document.querySelector("#surebetWorst");
  if (totalOutput) totalOutput.textContent = formatCurrency(totalStake);
  if (targetOutput) targetOutput.textContent = formatCurrency(targetReturn);
  if (marginOutput) {
    marginOutput.textContent = `${margin.toFixed(2)}%`;
    marginOutput.className = margin >= 0 ? "positive" : "negative";
  }
  if (bestOutput) {
    bestOutput.textContent = formatCurrency(best);
    bestOutput.className = best >= 0 ? "positive" : "negative";
  }
  if (worstOutput) {
    worstOutput.textContent = formatCurrency(worst);
    worstOutput.className = worst >= 0 ? "positive" : "negative";
  }

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
        <select name="surebet_bankroll_${index}" class="surebet-bankroll-select">
          ${bankrollOptionsHtml()}
        </select>
        <input type="hidden" name="surebet_bookmaker_${index}" value="" />
      </label>
      <div class="surebet-mode-control">
        <input type="hidden" name="surebet_mode_${index}" value="back" />
        <button class="surebet-mode-toggle" type="button" aria-label="Alternar entrada back ou lay">Back</button>
      </div>
      <label>
        <span class="sr-only">Valor ${index}</span>
        <input type="number" name="surebet_stake_${index}" class="surebet-stake calculated-stake" step="0.01" min="0.01" placeholder="Calculado" />
        <output class="surebet-liability" data-surebet-liability="${index}"></output>
      </label>
      <label>
        <span class="sr-only">Odd ${index}</span>
        <input type="number" name="surebet_odd_${index}" class="surebet-odd" step="0.01" min="1.01" placeholder="Ex: 2.10" />
      </label>
      <label>
        <span class="sr-only">Comissão % ${index}</span>
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
          <label>
            <span>Quando gera</span>
            <select name="surebet_freebet_trigger_${index}">
              <option value="lost" selected>Se perder</option>
              <option value="won">Se ganhar</option>
              <option value="any">Ambas</option>
            </select>
          </label>
        </div>
        <input type="number" name="surebet_net_${index}" class="surebet-entry-return" step="0.01" placeholder="Resultado" data-surebet-result="${index}" />
      </div>
      <label class="surebet-entry-note">
        <span class="sr-only">Observação ${index}</span>
        <input type="text" name="surebet_notes_${index}" maxlength="180" placeholder="Observação" autocomplete="off" />
      </label>
    </div>
  `;
  return group;
}

function getFreebetIndices() {
  return [...document.querySelectorAll("[data-freebet-row]")]
    .map((row) => Number.parseInt(row.dataset.freebetRow, 10))
    .filter(Boolean)
    .sort((a, b) => a - b);
}

function readFreebetMode(index) {
  if (index === 1) return "back";
  return document.querySelector(`[name="freebet_mode_${index}"]`)?.value === "lay" ? "lay" : "back";
}

function updateSelectedFreebetFields() {
  const select = document.querySelector("[data-freebet-source]");
  if (!select) return;
  const selected = select.options[select.selectedIndex];
  const amount = selected?.dataset.amount || "";
  const bookmaker = selected?.dataset.bookmaker || "";
  const sourceChanged = select.dataset.currentSource !== select.value;
  const stakeInput = document.querySelector('[name="freebet_stake_1"]');
  if (stakeInput && amount && (sourceChanged || !stakeInput.value)) {
    stakeInput.value = Number.parseFloat(amount).toFixed(2);
  }
  const bookmakerInput = document.querySelector('[name="freebet_bookmaker_1"]');
  if (bookmakerInput && bookmaker && !bookmakerInput.value) bookmakerInput.value = bookmaker;
  select.dataset.currentSource = select.value;
}

function prepareFreebetExtractionFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const freebetSource = params.get("freebet_source");
  if (!freebetSource) return;

  const select = document.querySelector("[data-freebet-source]");
  if (select && [...select.options].some((option) => option.value === freebetSource)) {
    select.value = freebetSource;
    select.dataset.currentSource = "";
  }

  const dateInput = document.querySelector('[name="freebet_event_date"]');
  if (dateInput && !dateInput.value) {
    dateInput.value = localDateInputValue();
  }

  setBetMode("freebet-extract");
  updateFreebetExtractionPreview();
  requestAnimationFrame(() => {
    document.querySelector(".freebet-extraction-form")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  });
}

function setFieldValue(name, value) {
  const field = document.getElementsByName(name)[0];
  if (!field || value === null) return;
  field.value = value;
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.dispatchEvent(new Event("change", { bubbles: true }));
}

function ensureEntryRows(prefix, desiredCount) {
  const addButton = document.querySelector(prefix === "surebet" ? "#addProtectionEntry" : "#addFreebetEntry");
  const currentIndices = prefix === "surebet" ? getSurebetIndices() : getFreebetIndices();
  let currentCount = currentIndices.length ? Math.max(...currentIndices) : 0;
  while (addButton && currentCount < desiredCount) {
    addButton.click();
    currentCount += 1;
  }
}

function prepareCalculatorDraftFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const draftMode = params.get("draft_mode");
  const prefix = draftMode === "freebet-extract" ? "freebet" : draftMode === "surebet" ? "surebet" : "";
  if (!prefix) return;

  const entryCount = Number.parseInt(params.get(`${prefix}_entry_count`) || "3", 10);
  ensureEntryRows(prefix, Number.isFinite(entryCount) ? entryCount : 3);

  params.forEach((value, key) => {
    if (key === "draft_mode") return;
    if (!key.startsWith(`${prefix}_`)) return;
    setFieldValue(key, value);
  });

  setBetMode(draftMode);
  if (draftMode === "surebet") updateSurebetPreview();
  if (draftMode === "freebet-extract") updateFreebetExtractionPreview();

  requestAnimationFrame(() => {
    document.querySelector("#new-bet")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  });
}

function setupCalculatorRegistration() {
  document.querySelectorAll("[data-calculator-register]").forEach((button) => {
    button.addEventListener("click", () => {
      const mode = button.dataset.calculatorRegister;
      const prefix = mode === "freebet-extract" ? "freebet" : "surebet";
      const form = button.closest("form");
      const baseUrl = form?.dataset.registerBaseUrl || "/";
      const params = new URLSearchParams();
      const indices = prefix === "freebet" ? getFreebetIndices() : getSurebetIndices();

      params.set("draft_mode", mode);
      params.set(`${prefix}_entry_count`, String(Math.max(...indices, 0)));

      form?.querySelectorAll("input, select, textarea").forEach((field) => {
        if (!field.name || field.disabled) return;
        if (!field.name.startsWith(`${prefix}_`)) return;
        if (field.type === "hidden" || field.value.trim() !== "") {
          params.set(field.name, field.value);
        }
      });

      window.location.href = `${baseUrl}?${params.toString()}#new-bet`;
    });
  });
}

function freebetSourceMultiplier(effectiveOdd, commission) {
  return effectiveOdd > 1 ? (effectiveOdd - 1) * (1 - commission / 100) : 0;
}

function freebetExposure(row) {
  if (row.isFreebetSource) return 0;
  return surebetExposure(row);
}

function updateFreebetExtractionPreview() {
  if (!document.querySelector("#freebetEntries")) return;
  updateSelectedFreebetFields();

  const activeStakeInput = document.activeElement?.classList?.contains("surebet-stake")
    ? document.activeElement
    : null;
  const firstOdd = readNumber(document.querySelector('[name="freebet_odd_1"]'));
  const firstStake = readNumber(document.querySelector('[name="freebet_stake_1"]'));
  const firstCommission = readNumber(document.querySelector('[name="freebet_commission_1"]'));
  const firstBoost = readNumber(document.querySelector('[name="freebet_boost_1"]'));
  const firstEffectiveOdd = boostedProfitOdds(firstOdd, firstBoost);
  const firstMultiplier = freebetSourceMultiplier(firstEffectiveOdd, firstCommission);
  const targetReturn = firstMultiplier > 0 && firstStake > 0 ? firstMultiplier * firstStake : 0;
  const indices = getFreebetIndices();

  indices.filter((index) => index > 1).forEach((index) => {
    const oddInput = document.querySelector(`[name="freebet_odd_${index}"]`);
    const stakeInput = document.querySelector(`[name="freebet_stake_${index}"]`);
    const odd = readNumber(oddInput);
    const commission = readNumber(document.querySelector(`[name="freebet_commission_${index}"]`));
    const boost = readNumber(document.querySelector(`[name="freebet_boost_${index}"]`));
    const mode = readFreebetMode(index);
    const effectiveOdd = boostedProfitOdds(odd, boost);
    const multiplier = surebetTargetMultiplier(mode, effectiveOdd, commission);
    if (
      stakeInput &&
      stakeInput !== activeStakeInput &&
      stakeInput.dataset.manualStake !== "true"
    ) {
      stakeInput.value = targetReturn > 0 && multiplier > 0 ? (targetReturn / multiplier).toFixed(2) : "";
    }
  });

  const rows = indices.map((index) => {
    const oddInput = document.querySelector(`[name="freebet_odd_${index}"]`);
    const stakeInput = document.querySelector(`[name="freebet_stake_${index}"]`);
    const commission = readNumber(document.querySelector(`[name="freebet_commission_${index}"]`));
    const cashback = readNumber(document.querySelector(`[name="freebet_cashback_${index}"]`));
    const boost = readNumber(document.querySelector(`[name="freebet_boost_${index}"]`));
    const odd = readNumber(oddInput);
    const mode = readFreebetMode(index);
    const effectiveOdd = boostedProfitOdds(odd, boost);
    const multiplier = index === 1
      ? freebetSourceMultiplier(effectiveOdd, commission)
      : surebetTargetMultiplier(mode, effectiveOdd, commission);
    const stake = readNumber(stakeInput);
    const liability = mode === "lay" && effectiveOdd > 1 ? stake * (effectiveOdd - 1) : 0;
    return {
      index,
      bookmaker: selectedBankrollText(`freebet_bankroll_${index}`),
      label: index === 1 ? "Freebet" : `Proteção ${index}`,
      mode,
      odd,
      commission,
      cashback,
      boost,
      effectiveOdd,
      multiplier,
      stake,
      liability,
      isFreebetSource: index === 1,
    };
  }).filter((row) => row.multiplier > 0 && row.stake > 0);

  document.querySelectorAll("[data-freebet-liability]").forEach((output) => {
    output.textContent = "";
    output.closest(".surebet-entry-group")?.classList.remove("has-liability");
  });
  rows.forEach((row) => {
    const output = document.querySelector(`[data-freebet-liability="${row.index}"]`);
    if (output) {
      const group = output.closest(".surebet-entry-group");
      const hasLiability = row.mode === "lay" && !row.isFreebetSource;
      group?.classList.toggle("has-liability", hasLiability);
      output.textContent = hasLiability ? formatCurrency(row.liability) : "";
    }
  });

  const cashExposure = rows.reduce((sum, row) => sum + freebetExposure(row), 0);
  const scenarios = rows.map((row) => ({
    ...row,
    returnAmount: row.isFreebetSource
      ? row.stake * row.multiplier
      : row.mode === "lay"
        ? row.stake * (1 - row.commission / 100)
        : row.stake * row.multiplier,
  })).map((row, _index, allRows) => {
    const cashbackReturn = allRows
      .filter((candidate) => candidate !== row && !candidate.isFreebetSource && candidate.mode === "back")
      .reduce((sum, candidate) => sum + candidate.stake * (candidate.cashback / 100), 0);
    const scenarioNet = allRows.reduce((sum, candidate) => {
      if (candidate === row) {
        if (candidate.isFreebetSource) return sum + candidate.returnAmount;
        return sum + (
          candidate.mode === "lay"
            ? candidate.returnAmount
            : candidate.returnAmount - candidate.stake
        );
      }
      if (row.isFreebetSource && candidate.mode === "lay") {
        return sum - candidate.liability;
      }
      return sum - freebetExposure(candidate);
    }, 0);
    return {
      ...row,
      cashbackReturn,
      net: scenarioNet + cashbackReturn,
    };
  });
  const best = scenarios.length ? Math.max(...scenarios.map((row) => row.net)) : 0;
  const worst = scenarios.length ? Math.min(...scenarios.map((row) => row.net)) : 0;
  const conversion = firstStake > 0 ? (worst / firstStake) * 100 : 0;

  document.querySelectorAll("[data-freebet-result]").forEach((output) => {
    output.textContent = formatPlainAmount(0);
    output.classList.remove("positive", "negative");
  });
  scenarios.forEach((row) => {
    const output = document.querySelector(`[data-freebet-result="${row.index}"]`);
    if (output) {
      output.textContent = formatPlainAmount(row.net);
      output.classList.toggle("positive", row.net >= 0);
      output.classList.toggle("negative", row.net < 0);
    }
  });

  const totalOutput = document.querySelector("#freebetTotal");
  const targetOutput = document.querySelector("#freebetTargetReturn");
  const marginOutput = document.querySelector("#freebetMargin");
  const bestOutput = document.querySelector("#freebetBest");
  const worstOutput = document.querySelector("#freebetWorst");
  if (totalOutput) totalOutput.textContent = formatCurrency(cashExposure);
  if (targetOutput) targetOutput.textContent = formatCurrency(targetReturn);
  if (marginOutput) {
    marginOutput.textContent = `${conversion.toFixed(2)}%`;
    marginOutput.className = conversion >= 0 ? "positive" : "negative";
  }
  if (bestOutput) {
    bestOutput.textContent = formatCurrency(best);
    bestOutput.className = best >= 0 ? "positive" : "negative";
  }
  if (worstOutput) {
    worstOutput.textContent = formatCurrency(worst);
    worstOutput.className = worst >= 0 ? "positive" : "negative";
  }

  const table = document.querySelector("#freebetScenarioTable");
  if (!table) return;

  const body = scenarios.length
    ? scenarios.map((row) => `
        <div class="surebet-result-row">
          <span>${escapeHtml(row.bookmaker)}</span>
          <span>${row.isFreebetSource ? "Freebet" : row.mode === "lay" ? "Lay" : "Back"}</span>
          <span>${formatCurrency(freebetExposure(row))}</span>
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

function updateDoubleProtectionPreview() {
  if (!document.querySelector(".double-protection-form")) return;
  const earlyProfit = readNumber(document.querySelector('[name="double_early_profit"]'));
  const secondChanceProfit = readNumber(document.querySelector('[name="double_second_chance_profit"]'));
  const liveOdd = readNumber(document.querySelector('[name="double_live_odd"]'));
  const commission = readNumber(document.querySelector('[name="double_commission"]'));
  const payoutMultiplier = liveOdd > 1 ? 1 + (liveOdd - 1) * (1 - commission / 100) : 0;
  const stake = secondChanceProfit > 0 && payoutMultiplier > 0 ? secondChanceProfit / payoutMultiplier : 0;
  const returnAmount = stake * payoutMultiplier;
  const teamOneNet = earlyProfit + returnAmount - stake;
  const secondNet = earlyProfit + secondChanceProfit - stake;
  const worst = Math.min(teamOneNet, secondNet);
  const bookmaker = selectedBankrollText("double_bankroll");
  const values = {
    "#doubleStake": stake,
    "#doubleTeamOneNet": teamOneNet,
    "#doubleSecondNet": secondNet,
    "#doubleWorst": worst,
  };

  Object.entries(values).forEach(([selector, value]) => {
    const output = document.querySelector(selector);
    if (!output) return;
    output.textContent = formatCurrency(value);
    output.className = value >= 0 ? "positive" : "negative";
  });

  const table = document.querySelector("#doubleScenarioTable");
  if (!table) return;
  table.innerHTML = `
    <div class="surebet-result-head">
      <span>Cenário</span>
      <span>Casa</span>
      <span>Odd</span>
      <span>Respons.</span>
      <span>Retorno</span>
      <span>Cashback</span>
      <span>Ganha / perde</span>
    </div>
    <div class="surebet-result-row">
      <span>Time 1 confirma</span>
      <span>${escapeHtml(bookmaker)}</span>
      <span>${liveOdd > 0 ? liveOdd.toFixed(2) : "-"}</span>
      <span>${formatCurrency(stake)}</span>
      <span>${formatCurrency(returnAmount)}</span>
      <span>${formatCurrency(0)}</span>
      <strong class="${teamOneNet >= 0 ? "positive" : "negative"}">${formatCurrency(teamOneNet)}</strong>
    </div>
    <div class="surebet-result-row">
      <span>Empate / virada</span>
      <span>Cenário protegido</span>
      <span>-</span>
      <span>${formatCurrency(stake)}</span>
      <span>${formatCurrency(earlyProfit + secondChanceProfit)}</span>
      <span>${formatCurrency(0)}</span>
      <strong class="${secondNet >= 0 ? "positive" : "negative"}">${formatCurrency(secondNet)}</strong>
    </div>
  `;
}

function createFreebetEntry(index) {
  const group = document.createElement("div");
  group.className = "surebet-entry-group";
  group.dataset.freebetGroup = String(index);
  group.innerHTML = `
    <div class="surebet-entry-row" data-freebet-row="${index}">
      <label>
        <span class="sr-only">Casa de aposta ${index} opcional</span>
        <select name="freebet_bankroll_${index}" class="surebet-bankroll-select">
          ${bankrollOptionsHtml()}
        </select>
        <input type="hidden" name="freebet_bookmaker_${index}" value="" />
      </label>
      <div class="surebet-mode-control">
        <input type="hidden" name="freebet_mode_${index}" value="back" />
        <button class="surebet-mode-toggle" type="button" aria-label="Alternar entrada back ou lay">Back</button>
      </div>
      <label>
        <span class="sr-only">Valor ${index}</span>
        <input type="number" name="freebet_stake_${index}" class="surebet-stake calculated-stake" step="0.01" min="0.01" placeholder="Calculado ou manual" />
        <output class="surebet-liability" data-freebet-liability="${index}"></output>
      </label>
      <label>
        <span class="sr-only">Odd ${index}</span>
        <input type="number" name="freebet_odd_${index}" class="surebet-odd" step="0.01" min="1.01" placeholder="Ex: 2.10" />
      </label>
      <label>
        <span class="sr-only">Comissão % ${index}</span>
        <input type="number" name="freebet_commission_${index}" class="surebet-adjustment" step="0.01" min="0" max="100" placeholder="Ex: 0" />
      </label>
      <label>
        <span class="sr-only">Cashback % ${index}</span>
        <input type="number" name="freebet_cashback_${index}" class="surebet-adjustment" step="0.01" min="0" max="100" placeholder="Ex: 5" />
      </label>
      <label>
        <span class="sr-only">Aumento % ${index}</span>
        <input type="number" name="freebet_boost_${index}" class="surebet-adjustment" step="0.01" min="0" max="100" placeholder="Ex: 10" />
      </label>
      <div class="freebet-control">
        <input type="hidden" name="freebet_freebet_enabled_${index}" value="0" />
        <output class="surebet-entry-return" data-freebet-result="${index}">0,00</output>
      </div>
      <label class="surebet-entry-note">
        <span class="sr-only">Observação ${index}</span>
        <input type="text" name="freebet_notes_${index}" maxlength="180" placeholder="Observação" autocomplete="off" />
      </label>
    </div>
  `;
  return group;
}

document.querySelector("#addProtectionEntry")?.addEventListener("click", () => {
  const entries = document.querySelector("#surebetEntries");
  const countInput = document.querySelector("#surebetEntryCount");
  if (!entries || !countInput) return;

  const nextIndex = Math.max(...getSurebetIndices(), 0) + 1;
  entries.appendChild(createSurebetEntry(nextIndex));
  countInput.value = String(nextIndex);
  updateSurebetPreview();
});

document.querySelector("#addFreebetEntry")?.addEventListener("click", () => {
  const entries = document.querySelector("#freebetEntries");
  const countInput = document.querySelector("#freebetEntryCount");
  if (!entries || !countInput) return;

  const nextIndex = Math.max(...getFreebetIndices(), 0) + 1;
  entries.appendChild(createFreebetEntry(nextIndex));
  countInput.value = String(nextIndex);
  updateFreebetExtractionPreview();
});

document.querySelectorAll("[data-bet-mode-button]").forEach((button) => {
  button.addEventListener("click", () => setBetMode(button.dataset.betModeButton));
});

document.querySelector(".manual-freebet-form")?.addEventListener("input", (event) => {
  if (!event.target.matches("input, select, textarea")) return;
  event.currentTarget.querySelector(".form-errors")?.remove();
});

document.querySelector(".surebet-form")?.addEventListener("input", (event) => {
  if (event.target.classList.contains("surebet-entry-return")) {
    event.target.dataset.manualResult = "true";
  } else if (event.target.classList.contains("surebet-stake")) {
    event.target.dataset.manualStake = "true";
  } else {
    document.querySelectorAll("[data-surebet-result]").forEach((input) => {
      input.dataset.manualResult = "false";
    });
  }
  updateSurebetPreview();
});
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

document.querySelector(".double-protection-form")?.addEventListener("input", updateDoubleProtectionPreview);
document.querySelector(".double-protection-form")?.addEventListener("change", updateDoubleProtectionPreview);

document.querySelector(".freebet-extraction-form")?.addEventListener("input", (event) => {
  if (event.target.classList.contains("surebet-stake")) {
    event.target.dataset.manualStake = "true";
  }
  updateFreebetExtractionPreview();
});
document.querySelector(".freebet-extraction-form")?.addEventListener("change", updateFreebetExtractionPreview);
document.querySelector(".freebet-extraction-form")?.addEventListener("click", (event) => {
  const modeToggle = event.target.closest(".surebet-mode-toggle");
  if (modeToggle && !modeToggle.disabled) {
    const control = modeToggle.closest(".surebet-mode-control");
    const hiddenInput = control?.querySelector('input[name^="freebet_mode_"]');
    if (!hiddenInput) return;
    const isLay = hiddenInput.value !== "lay";
    hiddenInput.value = isLay ? "lay" : "back";
    modeToggle.textContent = isLay ? "Lay" : "Back";
    modeToggle.classList.toggle("is-lay", isLay);
    updateFreebetExtractionPreview();
    return;
  }
});

function applyBankrollFilters() {
  const selectedEntity = document.querySelector("#bankrollEntityFilter")?.value || "";
  const searchTerm = (document.querySelector("#bankrollSearch")?.value || "").trim().toLowerCase();
  const hideZeroBalance = document.querySelector("#hideZeroBalanceBankrolls")?.checked || false;
  document.querySelectorAll(".bankroll-card[data-entity-id]").forEach((card) => {
    const matchesEntity = !selectedEntity || card.dataset.entityId === selectedEntity;
    const matchesSearch = !searchTerm || (card.dataset.searchText || "").toLowerCase().includes(searchTerm);
    const matchesBalance = !hideZeroBalance || card.dataset.balanceEmpty !== "true";
    const shouldShow = matchesEntity && matchesSearch && matchesBalance;
    card.classList.toggle("is-filtered-out", !shouldShow);
  });
}

document.querySelector("#bankrollEntityFilter")?.addEventListener("change", applyBankrollFilters);
document.querySelector("#bankrollSearch")?.addEventListener("input", applyBankrollFilters);
document.querySelector("#hideZeroBalanceBankrolls")?.addEventListener("change", applyBankrollFilters);

document.querySelectorAll(".finance-card-form").forEach((form) => {
  const kindInput = form.querySelector("[data-finance-kind]");
  const bankAccount = form.querySelector('[name="bank_account"]');
  const setKind = (kind, shouldFocus = false) => {
    if (kindInput) kindInput.value = kind;
    form.querySelectorAll("[data-finance-action]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.financeAction === kind);
    });
    if (bankAccount) {
      bankAccount.required = false;
      bankAccount.disabled = kind === "adjustment";
      if (kind === "adjustment") bankAccount.value = "";
    }
    if (shouldFocus) form.querySelector('[name="amount"]')?.focus();
  };
  setKind(kindInput?.value || "deposit");
  form.querySelectorAll("[data-finance-action]").forEach((button) => {
    button.addEventListener("click", () => setKind(button.dataset.financeAction, true));
  });
});

if (document.querySelector('[data-bet-mode-panel="surebet"] .form-errors')) {
  setBetMode("surebet");
}

if (document.querySelector('[data-bet-mode-panel="double-protection"] .form-errors')) {
  setBetMode("double-protection");
}

if (document.querySelector('[data-bet-mode-panel="freebet-extract"] .form-errors')) {
  setBetMode("freebet-extract");
}

["#id_bankroll", "#id_odds", "#id_odds_boost", "#id_stake", "#id_exchange_commission", "[data-simple-freebet-select]"].forEach((selector) => {
  document.querySelector(selector)?.addEventListener("input", updateBetPreview);
  document.querySelector(selector)?.addEventListener("change", updateBetPreview);
});

updateBetPreview();
updateSurebetPreview();
updateDoubleProtectionPreview();
updateFreebetExtractionPreview();
applyUserCurrencyPreference();
translateInterface();
setupInterfaceTranslationObserver();
setupMobileSidebar();
setupAccountPopover();
setupBalanceVisibility();
setupCollapsiblePanels();
enhanceResponsiveTables();
setupEventAutocomplete();
setupEventOddsLookup();
setupCalculatorRegistration();
activateScreen();
prepareFreebetExtractionFromUrl();
prepareCalculatorDraftFromUrl();
drawChart();
drawBarChart();

window.addEventListener("hashchange", activateScreen);
window.addEventListener("resize", drawChart);
window.addEventListener("resize", drawBarChart);
