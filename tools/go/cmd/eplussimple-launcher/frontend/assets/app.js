const chartInstances = {};

const graphOrder = [
  { key: "heating", name: "난방" },
  { key: "cooling", name: "냉방" },
  { key: "lighting", name: "조명" },
  { key: "circulation", name: "팬/펌프/전열" },
  { key: "hotwater", name: "급탕" },
  { key: "generators", name: "발전량" },
];

const energyTypes = [
  { key: "ELECTRICITY", label: "전기", color: "rgba(72,190,141,1)", light_color: "rgba(137,220,181,1)" },
  { key: "NATURALGAS", label: "가스", color: "rgba(195,24,24,1)", light_color: "rgba(227,124,124,1)" },
  { key: "OIL", label: "유류", color: "rgba(242,176,77,1)", light_color: "rgba(247,208,148,1)" },
  { key: "DISTRICTHEATING", label: "지역난방", color: "rgba(186,28,162,1)", light_color: "rgba(218,126,201,1)" },
];

const dataTypeLabels = {
  site_uses: { name: "에너지소요량", unit: "[kWh/m²]" },
  source_uses: { name: "1차에너지소요량", unit: "[kWh/m²]" },
  co2: { name: "CO2 배출량", unit: "[kgCO₂/m²]" },
  cost: { name: "에너지 요금", unit: "[원/m²]" },
};

const monthLabels = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"];

let currentSimData = null;
const progressPollIntervalMs = 1000;

window.addEventListener("DOMContentLoaded", () => {
  const beforeInput = document.getElementById("fileInputBefore");
  const afterInput = document.getElementById("fileInputAfter");
  const form = document.getElementById("uploadForm");
  const rawDataDownloadButton = document.getElementById("rawDataDownloadButton");

  beforeInput.addEventListener("change", () => {
    document.getElementById("filenameBoxBefore").textContent =
      beforeInput.files && beforeInput.files[0] ? beforeInput.files[0].name : "파일이 선택되지 않았습니다.";
  });

  afterInput.addEventListener("change", () => {
    const box = document.getElementById("filenameBoxAfter");

    if (afterInput.files && afterInput.files.length > 0) {
      box.textContent = Array.from(afterInput.files).map(file => file.name).join(", ");
    } else {
      box.textContent = "파일이 선택되지 않았습니다. (선택사항)";
    }
  });

  form.addEventListener("submit", submitSimulation);

  document.getElementById("dataTypeSelector").addEventListener("change", event => {
    if (currentSimData) updateSelectedDataView(currentSimData, event.target.value);
  });

  rawDataDownloadButton.addEventListener("click", downloadRawDataCSV);
});

async function submitSimulation(event) {
  event.preventDefault();

  clearResult();
  setBusy(true);
  setStatus("파일을 준비하는 중입니다.");

  try {
    const formData = await buildSimulationFormData();
    setStatus("파일을 업로드하는 중입니다.");

    const response = await fetch("./api/simulate", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.err || "요청 처리 중 오류가 발생했습니다.");
    }

    renderProgress(payload.progress);
    const finalPayload = await waitForSimulation(payload.job_id, payload);

    renderDebug(finalPayload.debug);

    if (finalPayload.err && !finalPayload.sim_data) {
      renderProgress(finalPayload.progress, true);
      return;
    }

    if (finalPayload.sim_data) {
      renderProgress(withResultStep(finalPayload.progress, "running", "렌더링 중"));
      await nextFrame();
      renderSimulation(finalPayload.sim_data);
      renderProgress(withResultStep(finalPayload.progress, "done", "렌더링 완료"));
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function waitForSimulation(jobID, initialPayload) {
  let payload = initialPayload;

  while (!isTerminalState(payload)) {
    await delay(progressPollIntervalMs);

    const response = await fetch(`./api/simulate/status?job_id=${encodeURIComponent(jobID)}`, {
      cache: "no-store",
    });

    payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.err || "진행 상태를 확인하는 중 오류가 발생했습니다.");
    }

    renderProgress(payload.progress, payload.state === "failed");
  }

  return payload;
}

function isTerminalState(payload) {
  return payload && ["completed", "failed", "severe"].includes(payload.state);
}

function delay(ms) {
  return new Promise(resolve => window.setTimeout(resolve, ms));
}

function nextFrame() {
  return new Promise(resolve => window.requestAnimationFrame(resolve));
}

function withResultStep(progress, state, detail) {
  if (!progress || !progress.steps) return progress;

  return {
    ...progress,
    steps: progress.steps.map(step => (
      step.key === "result" ? { ...step, state, detail } : { ...step }
    )),
  };
}

function renderProgress(progress, isError = false) {
  const area = document.getElementById("statusArea");
  area.hidden = !progress;
  area.classList.toggle("error", Boolean(isError));
  area.innerHTML = "";

  if (!progress || !progress.steps) return;

  progress.steps.forEach(step => {
    const line = document.createElement("div");
    line.className = `progress-line progress-${step.state}`;
    line.textContent = `[${progressMarker(step.state)}] ${step.label}: ${step.detail || progressFallback(step.state)}`;
    area.appendChild(line);
  });
}

function progressMarker(state) {
  switch (state) {
    case "done":
      return "V";
    case "running":
      return "~";
    case "failed":
      return "X";
    case "skipped":
      return "-";
    default:
      return " ";
  }
}

function progressFallback(state) {
  switch (state) {
    case "done":
      return "완료";
    case "running":
      return "진행 중";
    case "failed":
      return "실패";
    case "skipped":
      return "건너뜀";
    default:
      return "대기 중";
  }
}

async function buildSimulationFormData() {
  const beforeInput = document.getElementById("fileInputBefore");
  const afterInput = document.getElementById("fileInputAfter");

  if (!beforeInput.files || beforeInput.files.length === 0) {
    throw new Error("'리모델링 전' 파일이 선택되지 않았습니다.");
  }

  const beforeFile = beforeInput.files[0];
  validateUploadFile(beforeFile, "리모델링 전");

  const formData = new FormData();
  formData.append("file_before", await makeUploadBlob(beforeFile), beforeFile.name);

  if (afterInput.files && afterInput.files.length > 0) {
    for (const [index, file] of Array.from(afterInput.files).entries()) {
      validateUploadFile(file, `리모델링 후 ${index + 1}`);
      formData.append("file_after", await makeUploadBlob(file), file.name);
    }
  }

  return formData;
}

async function makeUploadBlob(file) {
  const buffer = await file.arrayBuffer();
  return new Blob([buffer], {
    type: file.type || "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

function validateUploadFile(file, label) {
  if (!file) {
    throw new Error(`${label} 파일이 선택되지 않았습니다.`);
  }

  const lowerName = file.name.toLowerCase();
  if (!(lowerName.endsWith(".xlsx") || lowerName.endsWith(".xlsm") || lowerName.endsWith(".xls"))) {
    throw new Error(`${label} 파일 형식이 지원되지 않습니다: ${file.name}`);
  }
}

function setBusy(isBusy) {
  const button = document.getElementById("submitButton");
  button.disabled = isBusy;
  button.textContent = isBusy ? "시뮬레이션 실행중" : "시뮬레이션";
}

function setStatus(message, isError = false) {
  const area = document.getElementById("statusArea");
  area.hidden = !message;
  area.textContent = message || "";
  area.classList.toggle("error", Boolean(isError));
}

function clearResult() {
  currentSimData = null;

  document.getElementById("debugReportsArea").hidden = true;
  document.getElementById("debugReportsArea").innerHTML = "";

  document.getElementById("comparison-filenames").hidden = true;
  document.getElementById("comparison-filenames").innerHTML = "";

  document.getElementById("resultControls").hidden = true;
  document.getElementById("graphsArea").hidden = true;
  document.getElementById("rawDataArea").hidden = true;
  document.getElementById("annualSummaryContainer").innerHTML = "";
  document.getElementById("rawDataTables").innerHTML = "";

  Object.values(chartInstances).forEach(chart => chart.destroy());
  Object.keys(chartInstances).forEach(key => delete chartInstances[key]);
}

function renderDebug(debug) {
  if (!debug || !debug.report || debug.report.length === 0) return;

  const area = document.getElementById("debugReportsArea");
  area.hidden = false;
  area.innerHTML = "";

  const title = document.createElement("h2");
  title.textContent = "디버그 리포트";
  area.appendChild(title);

  const severeRows = debug.report.filter(row => row.importance === "ERROR");
  const warningRows = debug.report.filter(row => row.importance === "WARNING");

  if (severeRows.length > 0) {
    area.appendChild(makeReportSection("심각 (SEVERE)", severeRows, "report-severe"));
  }

  if (warningRows.length > 0) {
    area.appendChild(makeReportSection("경고 (WARNING)", warningRows, "report-warning"));
  }
}

function makeReportSection(titleText, rows, className) {
  const fragment = document.createDocumentFragment();

  const title = document.createElement("h3");
  title.textContent = titleText;
  fragment.appendChild(title);

  const box = document.createElement("div");
  box.className = `report-box ${className}`;
  box.appendChild(makeDebugTable(rows));
  fragment.appendChild(box);

  return fragment;
}

function makeDebugTable(rows) {
  const columns = ["file", "importance", "category", "subcategory", "type", "object", "message"];

  const table = document.createElement("table");
  table.className = "debug-table";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");

  columns.forEach(column => {
    const th = document.createElement("th");
    th.textContent = column;
    headerRow.appendChild(th);
  });

  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");

  rows.forEach(row => {
    const tr = document.createElement("tr");

    columns.forEach(column => {
      const td = document.createElement("td");
      td.textContent = row[column] == null ? "" : String(row[column]);
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  return table;
}

function renderSimulation(simData) {
  currentSimData = simData;

  renderComparisonFilenames(simData);

  document.getElementById("resultControls").hidden = false;
  document.getElementById("graphsArea").hidden = false;
  document.getElementById("rawDataArea").hidden = false;

  const selector = document.getElementById("dataTypeSelector");
  updateSelectedDataView(simData, selector.value);
  drawAnnualSummary(simData.before, simData.afters);
}

function updateSelectedDataView(simData, dataType) {
  updateCharts(simData, dataType);
  renderRawDataTables(simData, dataType);
}

function renderComparisonFilenames(simData) {
  const container = document.getElementById("comparison-filenames");
  container.hidden = false;

  const afterItems = (simData.filenames_after || [])
    .map((name, index) => `<li><strong>(${index + 1})</strong>: ${escapeHTML(name)}</li>`)
    .join("");

  container.innerHTML = `
    <strong>비교 대상:</strong> [전] ${escapeHTML(simData.filename_before || "")}
    <br>
    <strong>리모델링 후 옵션:</strong>
    <ol>${afterItems}</ol>
  `;
}

function updateCharts(allData, dataType) {
  if (!window.Chart) {
    setStatus("Chart.js가 로드되지 않아 그래프를 표시할 수 없습니다.", true);
    return;
  }

  const labels = dataTypeLabels[dataType];
  if (!labels) return;

  graphOrder.forEach(itemInfo => {
    const dataAfters = (allData.afters || []).map(dataAfter => dataAfter?.[dataType]?.[itemInfo.key]);

    document.getElementById(`title-${itemInfo.key}`).textContent =
      `${itemInfo.name} 월별 ${labels.name} 비교 ${labels.unit}`;

    drawGroupedStackedBar(
      `bar-${itemInfo.key}`,
      `legend-${itemInfo.key}`,
      allData.before?.[dataType]?.[itemInfo.key],
      dataAfters,
      labels.unit,
    );
  });

  const annualData = calculateAnnualData(allData, dataType);

  document.getElementById("title-annual-by-purpose").textContent =
    `용도별 연간 ${labels.name} 비교 ${labels.unit}`;

  drawAnnualByPurposeChart("bar-annual-by-purpose", annualData, labels.unit);

  const valuesAfters = (allData.afters || []).map(dataAfter => dataAfter?.summary_per_area?.[dataType]?.total_monthly);

  document.getElementById("title-total").textContent =
    `월별 총 ${labels.name} 비교 ${labels.unit}`;

  drawDualLineChart(
    "line-total",
    allData.before?.summary_per_area?.[dataType]?.total_monthly,
    valuesAfters,
    labels.unit,
  );
}

function generateCustomLegend(chart, container) {
  const uniqueLabels = {};

  chart.data.datasets.forEach((dataset, i) => {
    const baseLabel = dataset.label.replace(/ \((전|후\s*\d*)\)$/, "").trim();

    if (!uniqueLabels[baseLabel]) {
      uniqueLabels[baseLabel] = {
        label: baseLabel,
        backgroundColor: dataset.stack === "Before"
          ? dataset.backgroundColor
          : energyTypes.find(item => item.label === baseLabel)?.light_color || "#ccc",
        datasetIndices: [i],
      };
    } else {
      uniqueLabels[baseLabel].datasetIndices.push(i);
    }
  });

  container.innerHTML = Object.values(uniqueLabels).map(item => {
    const isHidden = item.datasetIndices.every(index => !chart.isDatasetVisible(index));

    return `
      <div class="legend-item ${isHidden ? "legend-item-hidden" : ""}" data-dataset-indices="${escapeHTML(JSON.stringify(item.datasetIndices))}">
        <span class="legend-color-box" style="background-color: ${item.backgroundColor}"></span>
        <span>${escapeHTML(item.label)}</span>
      </div>
    `;
  }).join("");

  container.querySelectorAll(".legend-item").forEach(item => {
    item.onclick = () => {
      const datasetIndices = JSON.parse(item.dataset.datasetIndices);
      const isVisible = chart.isDatasetVisible(datasetIndices[0]);

      datasetIndices.forEach(index => chart.setDatasetVisibility(index, !isVisible));
      chart.update();
      generateCustomLegend(chart, container);
    };
  });
}

const caseNumberPlugin = {
  id: "caseNumber",
  afterDatasetsDraw(chart) {
    const { ctx, chartArea: { bottom } } = chart;

    ctx.save();
    ctx.font = "bold 9px sans-serif";
    ctx.fillStyle = "#555";
    ctx.textAlign = "center";

    chart.data.datasets.forEach((dataset, i) => {
      if (dataset.stack && dataset.stack.startsWith("After_") && chart.isDatasetVisible(i)) {
        const caseIndex = parseInt(dataset.stack.split("_")[1], 10);
        const meta = chart.getDatasetMeta(i);

        meta.data.forEach(bar => {
          if (dataset.label.includes("전기")) {
            ctx.fillText(String(caseIndex + 1), bar.x, bottom + 6);
          }
        });
      }
    });

    ctx.restore();
  },
};

function drawGroupedStackedBar(canvasId, legendContainerId, dataBefore, dataAfters, yAxisLabel) {
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();

  const ctx = document.getElementById(canvasId).getContext("2d");
  const legendContainer = document.getElementById(legendContainerId);

  if (!dataBefore || !dataAfters || dataAfters.length === 0) {
    if (legendContainer) legendContainer.innerHTML = "";
    return;
  }

  const datasets = [];

  energyTypes.forEach(energyType => {
    datasets.push({
      label: `${energyType.label} (전)`,
      data: dataBefore[energyType.key] || new Array(12).fill(0),
      backgroundColor: energyType.color,
      stack: "Before",
    });
  });

  dataAfters.forEach((dataAfter, index) => {
    energyTypes.forEach(energyType => {
      datasets.push({
        label: `${energyType.label} (후 ${index + 1})`,
        data: dataAfter?.[energyType.key] || new Array(12).fill(0),
        backgroundColor: energyType.light_color,
        stack: `After_${index}`,
      });
    });
  });

  const chart = new Chart(ctx, {
    type: "bar",
    plugins: [caseNumberPlugin],
    data: { labels: monthLabels, datasets },
    options: {
      plugins: { legend: { display: false } },
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { font: { size: 10 } } },
        y: { stacked: true, beginAtZero: true, title: { display: true, text: yAxisLabel } },
      },
      layout: { padding: { bottom: 15 } },
    },
  });

  chartInstances[canvasId] = chart;
  generateCustomLegend(chart, legendContainer);
}

function calculateAnnualData(allData, dataType) {
  const result = {
    before: {},
    afters: [],
  };

  energyTypes.forEach(energyType => result.before[energyType.key] = []);

  graphOrder.forEach(itemInfo => {
    energyTypes.forEach(energyType => {
      const values = allData.before?.[dataType]?.[itemInfo.key]?.[energyType.key] || [];
      result.before[energyType.key].push(values.reduce((sum, value) => sum + value, 0));
    });
  });

  (allData.afters || []).forEach(dataAfter => {
    const afterResult = {};
    energyTypes.forEach(energyType => afterResult[energyType.key] = []);

    graphOrder.forEach(itemInfo => {
      energyTypes.forEach(energyType => {
        const values = dataAfter?.[dataType]?.[itemInfo.key]?.[energyType.key] || [];
        afterResult[energyType.key].push(values.reduce((sum, value) => sum + value, 0));
      });
    });

    result.afters.push(afterResult);
  });

  return result;
}

function drawAnnualByPurposeChart(canvasId, data, yAxisLabel) {
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();

  const ctx = document.getElementById(canvasId).getContext("2d");
  if (!data) return;

  const datasets = [];

  energyTypes.forEach(energyType => {
    datasets.push({
      label: energyType.label,
      data: data.before[energyType.key],
      backgroundColor: energyType.color,
      stack: "Before",
    });
  });

  data.afters.forEach((dataAfter, index) => {
    energyTypes.forEach(energyType => {
      datasets.push({
        label: energyType.label,
        data: dataAfter[energyType.key],
        backgroundColor: energyType.light_color,
        stack: `After_${index}`,
      });
    });
  });

  chartInstances[canvasId] = new Chart(ctx, {
    type: "bar",
    data: { labels: graphOrder.map(item => item.name), datasets },
    options: {
      plugins: {
        legend: {
          position: "top",
          labels: {
            font: { size: 10 },
            filter(item, chartData) {
              const labels = chartData.datasets.map(dataset => dataset.label);
              return labels.indexOf(item.text) === item.datasetIndex;
            },
          },
        },
      },
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { stacked: true, beginAtZero: true, title: { display: true, text: yAxisLabel }, grace: "10%" },
      },
    },
  });
}

function drawDualLineChart(canvasId, valuesBefore, valuesAfters, yAxisLabel) {
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();

  const ctx = document.getElementById(canvasId).getContext("2d");
  if (!valuesBefore || !valuesAfters || valuesAfters.length === 0) return;

  const pointStyles = ["circle", "triangle", "rect", "star", "diamond", "crossRot"];

  const datasets = [{
    label: "전",
    data: valuesBefore,
    borderColor: "#e76537",
    backgroundColor: "rgba(230, 101, 55, 0.1)",
    tension: 0.15,
    fill: true,
    pointStyle: "circle",
    pointRadius: 4,
    borderWidth: 3,
  }];

  valuesAfters.forEach((valuesAfter, index) => {
    datasets.push({
      label: `후 ${index + 1}`,
      data: valuesAfter,
      borderColor: `hsl(215, 70%, ${Math.max(30, 70 - index * 10)}%)`,
      backgroundColor: "transparent",
      tension: 0.15,
      fill: false,
      pointStyle: pointStyles[index % pointStyles.length],
      pointRadius: 4,
      borderWidth: 1.5,
    });
  });

  chartInstances[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels: monthLabels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "top", align: "center" } },
      scales: { y: { beginAtZero: true, title: { display: true, text: yAxisLabel } } },
    },
  });
}

function drawAnnualSummary(dataBefore, dataAfters) {
  const container = document.getElementById("annualSummaryContainer");
  container.innerHTML = "";

  const summaryMetrics = [
    { key: "site_uses", name: "에너지소요량", unit_per_area: "kWh/m²", unit_gross: "MWh" },
    { key: "source_uses", name: "1차에너지소요량", unit_per_area: "kWh/m²", unit_gross: "MWh" },
    { key: "co2", name: "CO2 배출량", unit_per_area: "kgCO₂/m²", unit_gross: "tCO₂" },
    { key: "cost", name: "에너지 요금", unit_per_area: "원/m²", unit_gross: "천 원" },
  ];

  let html = '<table class="summary-table">';

  summaryMetrics.forEach(metric => {
    html += `<thead><tr><th colspan="5" class="metric-title">${metric.name}</th></tr>`;
    html += `<tr><th>구분</th><th>면적당 [${metric.unit_per_area}]</th><th>변화율</th><th>총량 [${metric.unit_gross}]</th><th>변화율</th></tr></thead><tbody>`;

    const beforePerArea = dataBefore?.summary_per_area?.[metric.key]?.total_annual || 0;
    const beforeGross = (dataBefore?.summary_gross?.[metric.key]?.total_annual || 0) / 1000;

    html += `<tr><td class="case-label">Before</td><td>${formatNumber(beforePerArea)}</td><td>-</td><td>${formatNumber(beforeGross)}</td><td>-</td></tr>`;

    (dataAfters || []).forEach((dataAfter, index) => {
      const afterPerArea = dataAfter?.summary_per_area?.[metric.key]?.total_annual || 0;
      const afterGross = (dataAfter?.summary_gross?.[metric.key]?.total_annual || 0) / 1000;

      html += `<tr><td class="case-label">After ${index + 1}</td><td>${formatNumber(afterPerArea)}</td><td>${changeHTML(beforePerArea, afterPerArea)}</td><td>${formatNumber(afterGross)}</td><td>${changeHTML(beforeGross, afterGross)}</td></tr>`;
    });

    html += "</tbody>";
  });

  html += "</table>";
  container.innerHTML = html;
}

function renderRawDataTables(simData, dataType) {
  const container = document.getElementById("rawDataTables");
  const title = document.getElementById("rawDataTitle");
  const labels = dataTypeLabels[dataType];

  container.innerHTML = "";
  title.textContent = labels ? `상세값 - ${labels.name} ${labels.unit}` : "상세값";

  getSimulationCases(simData).forEach(simCase => {
    const caseSection = document.createElement("section");
    caseSection.className = "raw-case-section";

    const caseTitle = document.createElement("h3");
    caseTitle.textContent = `${simCase.label}: ${simCase.fileName}`;
    caseSection.appendChild(caseTitle);

    graphOrder.forEach(purpose => {
      const purposeData = simCase.data?.[dataType]?.[purpose.key];
      if (!purposeData) return;

      const tableBlock = document.createElement("div");
      tableBlock.className = "raw-table-block";

      const purposeTitle = document.createElement("h4");
      purposeTitle.textContent = purpose.name;
      tableBlock.appendChild(purposeTitle);
      tableBlock.appendChild(makeRawDataTable(purposeData));
      caseSection.appendChild(tableBlock);
    });

    container.appendChild(caseSection);
  });
}

function makeRawDataTable(purposeData) {
  const table = document.createElement("table");
  table.className = "raw-data-table";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  ["열원", ...monthLabels, "합계"].forEach(label => {
    const th = document.createElement("th");
    th.textContent = label;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  energyTypes.forEach(energyType => {
    const values = normalizeMonthlyValues(purposeData[energyType.key]);
    const row = document.createElement("tr");

    const labelCell = document.createElement("td");
    labelCell.className = "raw-energy-label";
    labelCell.textContent = energyType.label;
    row.appendChild(labelCell);

    values.forEach(value => {
      const cell = document.createElement("td");
      cell.textContent = formatRawNumber(value);
      row.appendChild(cell);
    });

    const totalCell = document.createElement("td");
    totalCell.textContent = formatRawNumber(sumValues(values));
    row.appendChild(totalCell);
    tbody.appendChild(row);
  });

  table.appendChild(tbody);
  return table;
}

function downloadRawDataCSV() {
  if (!currentSimData) return;

  const selector = document.getElementById("dataTypeSelector");
  const dataType = selector.value;
  const csv = buildRawDataCSV(currentSimData, dataType);
  const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `eplussimple-grr-${dataType}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function buildRawDataCSV(simData, dataType) {
  const labels = dataTypeLabels[dataType];
  const rows = [];

  rows.push(["지표", labels?.name || dataType, labels?.unit || ""]);

  getSimulationCases(simData).forEach(simCase => {
    rows.push([]);
    rows.push(["파일", simCase.label, simCase.fileName]);

    graphOrder.forEach(purpose => {
      const purposeData = simCase.data?.[dataType]?.[purpose.key];
      if (!purposeData) return;

      rows.push([]);
      rows.push(["용도", purpose.name]);
      rows.push(["열원", ...monthLabels, "합계"]);

      energyTypes.forEach(energyType => {
        const values = normalizeMonthlyValues(purposeData[energyType.key]);
        rows.push([
          energyType.label,
          ...values.map(value => rawNumberForCSV(value)),
          rawNumberForCSV(sumValues(values)),
        ]);
      });
    });
  });

  return rows.map(row => row.map(csvCell).join(",")).join("\r\n");
}

function getSimulationCases(simData) {
  const cases = [{
    label: "Before",
    fileName: simData.filename_before || "",
    data: simData.before,
  }];

  (simData.afters || []).forEach((dataAfter, index) => {
    cases.push({
      label: `After ${index + 1}`,
      fileName: simData.filenames_after?.[index] || `After ${index + 1}`,
      data: dataAfter,
    });
  });

  return cases;
}

function normalizeMonthlyValues(values) {
  const result = Array.isArray(values) ? values.slice(0, 12) : [];
  while (result.length < 12) result.push(0);
  return result.map(value => Number(value || 0));
}

function sumValues(values) {
  return values.reduce((sum, value) => sum + Number(value || 0), 0);
}

function formatRawNumber(value) {
  return Number(value || 0).toLocaleString(undefined, {
    maximumFractionDigits: 3,
    minimumFractionDigits: 0,
  });
}

function rawNumberForCSV(value) {
  const rounded = Math.round(Number(value || 0) * 1000000) / 1000000;
  return Number.isInteger(rounded) ? String(rounded) : String(rounded);
}

function csvCell(value) {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString(undefined, {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  });
}

function changeHTML(beforeValue, afterValue) {
  if (beforeValue <= 0) return "-";

  const change = ((afterValue - beforeValue) / beforeValue) * 100;
  const isDown = change < 0;
  const className = isDown ? "summary-down" : "summary-up";
  const marker = isDown ? "▼" : "▲";

  return `<span class="${className}">${marker} ${Math.abs(change).toFixed(1)}%</span>`;
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
