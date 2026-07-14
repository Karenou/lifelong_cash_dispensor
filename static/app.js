/* ============================================================
   人生提款模拟器 · 前端逻辑
   - 参数实时联动（debounce 300ms）
   - 预设场景一键加载
   - ECharts 图表渲染
   ============================================================ */

const API_BASE = '';
const DEBOUNCE_MS = 300;

// ---------- 状态 ----------
let lastResponse = null;
let debounceTimer = null;
let charts = {
  basic: null,
  ratio: null,
  mc: null,
};

// ---------- 工具函数 ----------
const $ = (id) => document.getElementById(id);

const fmtMoney = (n, digits = 0) => {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return '¥' + Number(n).toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

const fmtPct = (n, digits = 1) => {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return (n * 100).toFixed(digits) + '%';
};

const fmtMoneyShort = (n) => {
  if (n === null || n === undefined || isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e8) return '¥' + (n / 1e8).toFixed(2) + '亿';
  if (abs >= 1e4) return '¥' + (n / 1e4).toFixed(1) + '万';
  return '¥' + Math.round(n).toLocaleString('zh-CN');
};

// ---------- 读取参数 ----------
function readParams() {
  const w0 = parseFloat($('w0').value);
  const rate = parseFloat($('rate').value);
  const years = parseInt($('years').value);
  const inflation = parseFloat($('inflation').value);
  const returnRate = parseFloat($('return-rate').value);
  const sigma = parseFloat($('sigma').value);
  const numSimulations = parseInt($('sims').value);
  const enableMc = $('enable-mc').checked;

  return {
    w0,
    rate,
    years,
    inflation,
    return_rate: returnRate,
    sigma,
    num_simulations: numSimulations,
    enable_mc: enableMc,
    seed: 42,
  };
}

// ---------- 更新参数显示 ----------
function updateParamDisplays() {
  const w0 = parseFloat($('w0').value);
  const rate = parseFloat($('rate').value);
  const years = parseInt($('years').value);
  const inflation = parseFloat($('inflation').value);
  const returnRate = parseFloat($('return-rate').value);
  const sigma = parseFloat($('sigma').value);
  const sims = parseInt($('sims').value);
  const enableMc = $('enable-mc').checked;

  $('w0-display').textContent = fmtMoney(w0);
  $('rate-display').textContent = (rate * 100).toFixed(1) + '%';
  $('years-display').textContent = years + ' 年';
  $('inflation-display').textContent = (inflation * 100).toFixed(1) + '%';
  $('return-rate-display').textContent = (returnRate * 100).toFixed(1) + '%';
  $('sigma-display').textContent = (sigma * 100).toFixed(0) + '%';
  $('sims-display').textContent = sims.toLocaleString('zh-CN');
  $('e0-hint').textContent = '首年提款 ' + fmtMoney(w0 * rate);
  $('mc-status').textContent = enableMc ? '已开启' : '已关闭';

  // 蒙特卡洛区显示控制
  $('mc-section').style.display = enableMc ? '' : 'none';

  // 蒙特卡洛相关指标卡的状态
  if (!enableMc) {
    $('m-bankrupt').textContent = '—';
    $('m-survival').textContent = '—';
    $('m-median').textContent = '—';
    $('m-bankrupt-sub').textContent = '未启用';
    $('m-survival-sub').textContent = '未启用';
    $('m-median-sub').textContent = '未启用';
  } else {
    $('m-bankrupt-sub').textContent = '蒙特卡洛';
    $('m-survival-sub').textContent = '蒙特卡洛';
    $('m-median-sub').textContent = '蒙特卡洛';
  }
}

// ---------- 调用后端 ----------
async function callSimulate(params) {
  const resp = await fetch(API_BASE + '/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || '请求失败');
  }
  return resp.json();
}

// ---------- 触发计算（带 debounce） ----------
function scheduleCompute() {
  updateParamDisplays();
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runCompute, DEBOUNCE_MS);
}

async function runCompute() {
  const params = readParams();
  const overlay = $('loading-overlay');
  const loadingText = $('loading-text');

  // 蒙特卡洛模拟次数较多时显示加载
  if (params.enable_mc && params.num_simulations >= 10000) {
    loadingText.textContent = `正在进行 ${params.num_simulations.toLocaleString()} 次模拟...`;
    overlay.classList.remove('hidden');
  }

  try {
    const data = await callSimulate(params);
    lastResponse = data;
    renderResult(data, params);
  } catch (e) {
    console.error(e);
    alert('计算失败：' + e.message);
  } finally {
    overlay.classList.add('hidden');
  }
}

// ---------- 渲染结果 ----------
function renderResult(data, params) {
  const basic = data.basic;
  const mc = data.monte_carlo;

  // ----- 指标卡 -----
  if (basic.is_bankrupt) {
    $('m-status').textContent = '破产';
    $('m-status').className = 'metric-value text-coral';
    $('m-status-sub').textContent = `第 ${basic.bankrupt_year} 年耗尽`;
  } else {
    $('m-status').textContent = '成功';
    $('m-status').className = 'metric-value text-teal';
    $('m-status-sub').textContent = `残值 ${fmtMoneyShort(basic.final_wealth)}`;
  }

  if (mc) {
    $('m-bankrupt').textContent = fmtPct(mc.bankrupt_probability);
    $('m-survival').textContent = fmtPct(mc.survival_probability);
    $('m-median').textContent = fmtMoneyShort(mc.median_final_wealth);
  }

  // ----- 图表 -----
  renderBasicChart(basic, params);
  renderRatioChart(basic, params);
  if (mc) {
    renderMcChart(mc, basic, params);
  }

  // ----- 明细表 -----
  renderDetailTable(basic);
}

// ---------- 图表：资产轨迹 + 提款 ----------
function renderBasicChart(basic, params) {
  if (!charts.basic) {
    charts.basic = echarts.init($('chart-basic'));
  }
  const years = basic.records.map(r => '第' + r.year + '年');
  const wealth = basic.records.map(r => r.wealth_after);
  const withdrawal = basic.records.map(r => r.withdrawal);

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#CECBF6',
      borderWidth: 0.5,
      textStyle: { color: '#1A163F', fontSize: 12 },
      formatter: (params) => {
        let s = params[0].axisValue + '<br/>';
        params.forEach(p => {
          s += `${p.marker} ${p.seriesName}: ¥${Math.round(p.value).toLocaleString('zh-CN')}<br/>`;
        });
        return s;
      },
    },
    legend: {
      data: ['年末资产', '提款金额'],
      bottom: 0,
      textStyle: { color: '#3C3489', fontSize: 12 },
      itemWidth: 12,
      itemHeight: 12,
    },
    grid: { left: 70, right: 70, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: years,
      axisLine: { lineStyle: { color: '#CECBF6' } },
      axisLabel: { color: '#3C3489', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '资产',
        nameLocation: 'end',
        nameGap: 8,
        nameTextStyle: { color: '#3C3489', fontSize: 11, align: 'right' },
        axisLabel: {
          color: '#3C3489',
          fontSize: 11,
          formatter: (v) => fmtMoneyShort(v),
        },
        splitLine: { lineStyle: { color: 'rgba(175, 169, 236, 0.2)', type: 'dashed' } },
      },
      {
        type: 'value',
        name: '提款',
        nameLocation: 'end',
        nameGap: 8,
        nameTextStyle: { color: '#3C3489', fontSize: 11, align: 'left' },
        axisLabel: {
          color: '#3C3489',
          fontSize: 11,
          formatter: (v) => fmtMoneyShort(v),
        },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '年末资产',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        data: wealth,
        itemStyle: { color: '#534AB7' },
        lineStyle: { width: 2.5, color: '#534AB7' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(83, 74, 183, 0.15)' },
              { offset: 1, color: 'rgba(83, 74, 183, 0)' },
            ],
          },
        },
      },
      {
        name: '提款金额',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        data: withdrawal,
        itemStyle: { color: '#BA7517' },
        lineStyle: { width: 2, color: '#BA7517', type: 'dashed' },
      },
    ],
  };
  charts.basic.setOption(option, true);
}

// ---------- 图表：提款率 ----------
function renderRatioChart(basic, params) {
  if (!charts.ratio) {
    charts.ratio = echarts.init($('chart-ratio'));
  }
  const years = basic.records.map(r => '第' + r.year + '年');
  const ratios = basic.records.map(r => r.withdrawal_ratio);

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#CECBF6',
      borderWidth: 0.5,
      textStyle: { color: '#1A163F', fontSize: 12 },
      formatter: (params) => {
        const p = params[0];
        return `${p.axisValue}<br/>${p.marker} 提款率: ${(p.value * 100).toFixed(2)}%`;
      },
    },
    grid: { left: 55, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: years,
      axisLine: { lineStyle: { color: '#CECBF6' } },
      axisLabel: { color: '#3C3489', fontSize: 10, interval: Math.floor(years.length / 6) },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '提款率',
      nameLocation: 'end',
      nameGap: 8,
      nameTextStyle: { color: '#3C3489', fontSize: 11, align: 'right' },
      axisLabel: {
        color: '#3C3489',
        fontSize: 11,
        formatter: (v) => (v * 100).toFixed(0) + '%',
      },
      splitLine: { lineStyle: { color: 'rgba(175, 169, 236, 0.2)', type: 'dashed' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: ratios,
        lineStyle: { width: 2, color: '#1D9E75' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(29, 158, 117, 0.20)' },
              { offset: 1, color: 'rgba(29, 158, 117, 0)' },
            ],
          },
        },
        markLine: {
          symbol: 'none',
          data: [{ yAxis: params.rate }],
          lineStyle: { color: '#993C1D', type: 'dashed', width: 1 },
          label: {
            formatter: '初始 ' + (params.rate * 100).toFixed(1) + '%',
            color: '#993C1D',
            fontSize: 10,
          },
        },
      },
    ],
  };
  charts.ratio.setOption(option, true);
}

// ---------- 图表：蒙特卡洛扇形 ----------
function renderMcChart(mc, basic, params) {
  if (!charts.mc) {
    charts.mc = echarts.init($('chart-mc'));
  }
  const years = basic.records.map(r => '第' + r.year + '年');
  const p5 = mc.percentile_paths['5'];
  const p25 = mc.percentile_paths['25'];
  const p50 = mc.percentile_paths['50'];
  const p75 = mc.percentile_paths['75'];
  const p95 = mc.percentile_paths['95'];
  const basicWealth = basic.records.map(r => r.wealth_after);

  $('mc-desc').textContent = `N=${mc.num_simulations.toLocaleString()} · μ=${(params.return_rate * 100).toFixed(1)}% · σ=${(params.sigma * 100).toFixed(0)}%`;

    // 用 stack 技巧 + 高度差实现区间填充
    const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#CECBF6',
      borderWidth: 0.5,
      textStyle: { color: '#1A163F', fontSize: 12 },
      formatter: (params) => {
        let s = params[0].axisValue + '<br/>';
        params.forEach(p => {
          if (p.value === '-' || p.value === null || p.value === undefined) return;
          s += `${p.marker} ${p.seriesName}: ¥${Math.round(p.value).toLocaleString('zh-CN')}<br/>`;
        });
        return s;
      },
    },
    legend: {
      data: ['5%-95% 区间', '25%-75% 区间', '中位数 (50%)', '基础模式'],
      bottom: 0,
      textStyle: { color: '#3C3489', fontSize: 11 },
      itemWidth: 14,
      itemHeight: 10,
    },
    grid: { left: 75, right: 40, top: 30, bottom: 45 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: years,
      axisLine: { lineStyle: { color: '#CECBF6' } },
      axisLabel: { color: '#3C3489', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '资产',
      nameLocation: 'end',
      nameGap: 8,
      nameTextStyle: { color: '#3C3489', fontSize: 11, align: 'right' },
      min: 0,
      axisLabel: {
        color: '#3C3489',
        fontSize: 11,
        formatter: (v) => fmtMoneyShort(v),
      },
      splitLine: { lineStyle: { color: 'rgba(175, 169, 236, 0.2)', type: 'dashed' } },
    },
    series: [
      // 5%-95% 区间：先放 p5 作为基线，再放 (p95-p5) 高度差，stack 后会到达 p95
      {
        name: '_p5_lower',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: p5,
        lineStyle: { opacity: 0 },
        stack: 'ci_5_95',
        showInLegend: false,
        tooltip: { show: false },
      },
      {
        name: '5%-95% 区间',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: p95.map((v, i) => Math.max(v - p5[i], 0)),
        lineStyle: { opacity: 0 },
        stack: 'ci_5_95',
        areaStyle: { color: 'rgba(175, 169, 236, 0.20)' },
      },
      // 25%-75% 区间
      {
        name: '_p25_lower',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: p25,
        lineStyle: { opacity: 0 },
        stack: 'ci_25_75',
        showInLegend: false,
        tooltip: { show: false },
      },
      {
        name: '25%-75% 区间',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: p75.map((v, i) => Math.max(v - p25[i], 0)),
        lineStyle: { opacity: 0 },
        stack: 'ci_25_75',
        areaStyle: { color: 'rgba(127, 119, 221, 0.32)' },
      },
      // 中位数
      {
        name: '中位数 (50%)',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: p50,
        lineStyle: { width: 2.5, color: '#534AB7' },
        z: 10,
      },
      // 基础模式对照
      {
        name: '基础模式',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: basicWealth,
        lineStyle: { width: 1.8, color: '#D85A30', type: 'dashed' },
        z: 11,
      },
    ],
  };
  charts.mc.setOption(option, true);
}

// ---------- 明细表 ----------
function renderDetailTable(basic) {
  const tbody = $('detail-tbody');
  const note = $('detail-note');
  if (!basic.records.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-ink-500 py-8">无数据</td></tr>';
    note.textContent = '';
    note.className = 'detail-note';
    return;
  }
  tbody.innerHTML = basic.records.map(r => `
    <tr>
      <td>${r.year}</td>
      <td class="text-right">${fmtMoney(r.wealth_before)}</td>
      <td class="text-right">${fmtMoney(r.withdrawal)}</td>
      <td class="text-right">${fmtPct(r.withdrawal_ratio, 2)}</td>
      <td class="text-right">${fmtPct(r.return_rate, 2)}</td>
      <td class="text-right">${fmtMoney(r.wealth_after)}</td>
    </tr>
  `).join('');

  // 动态备注：破产 vs 未破产
  if (basic.is_bankrupt) {
    note.textContent = `仅展示至破产年份（第 ${basic.bankrupt_year} 年），后续年份资产已耗尽`;
    note.className = 'detail-note warn';
  } else {
    note.textContent = `共 ${basic.records.length} 年明细，规划期满资产未耗尽`;
    note.className = 'detail-note';
  }
}

// ---------- CSV 导出 ----------
function exportCsv() {
  if (!lastResponse || !lastResponse.basic) return;
  const rows = [['年份', '年初资产', '提款金额', '提款率', '收益率', '年末资产']];
  lastResponse.basic.records.forEach(r => {
    rows.push([
      r.year,
      r.wealth_before.toFixed(2),
      r.withdrawal.toFixed(2),
      r.withdrawal_ratio.toFixed(4),
      r.return_rate.toFixed(4),
      r.wealth_after.toFixed(2),
    ]);
  });
  const csv = '\uFEFF' + rows.map(r => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `lifelong_cash_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------- 预设场景 ----------
async function loadPresets() {
  try {
    const resp = await fetch(API_BASE + '/api/presets');
    const data = await resp.json();
    const container = $('presets-container');
    data.presets.forEach(p => {
      const btn = document.createElement('button');
      btn.className = 'preset-btn';
      btn.textContent = p.name;
      btn.title = p.description;
      btn.onclick = () => applyPreset(p);
      container.appendChild(btn);
    });
  } catch (e) {
    console.error('加载预设失败', e);
  }
}

function applyPreset(preset) {
  const p = preset.params;
  $('w0').value = p.w0;
  $('rate').value = p.rate;
  $('years').value = p.years;
  $('inflation').value = p.inflation;
  $('return-rate').value = p.return_rate;
  $('sigma').value = p.sigma;
  $('sims').value = p.num_simulations;
  $('enable-mc').checked = true;
  scheduleCompute();
}

// ---------- 重置 ----------
function resetParams() {
  $('w0').value = 1000000;
  $('rate').value = 0.04;
  $('years').value = 30;
  $('inflation').value = 0.03;
  $('return-rate').value = 0.055;
  $('sigma').value = 0.15;
  $('sims').value = 5000;
  $('enable-mc').checked = true;
  scheduleCompute();
}

// ---------- 事件绑定 ----------
function bindEvents() {
  ['w0', 'rate', 'years', 'inflation', 'return-rate', 'sigma', 'sims'].forEach(id => {
    $(id).addEventListener('input', scheduleCompute);
  });
  $('enable-mc').addEventListener('change', scheduleCompute);
  $('reset-btn').addEventListener('click', resetParams);
  $('export-csv').addEventListener('click', exportCsv);

  // 窗口尺寸变化时重绘图表
  window.addEventListener('resize', () => {
    Object.values(charts).forEach(c => c && c.resize());
  });
}

// ---------- 启动 ----------
document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  loadPresets();
  updateParamDisplays();
  // 首次自动计算
  runCompute();
});
