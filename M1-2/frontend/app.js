/* My Stock AI 비서 — 바닐라 JS 프론트엔드
   백엔드 주소는 config.js(window.APP_CONFIG.API_BASE_URL)에서 읽는다. */

const API_BASE = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || 'http://localhost:8000').replace(/\/+$/, '');
const PAGE_SIZE = 30;
// Cody 프록시(최대 40초) 실패 후 OpenAI 폴백(최대 30초)까지 기다릴 수 있게 여유를 둔다
const CHAT_TIMEOUT_MS = 90000;
const KEY_LABEL = { cody: 'CODY_OPENAI_API_KEY', openai: 'OPENAI_API_KEY' };

const state = {
  data: [],          // 날짜 오름차순
  summary: null,
  convId: null,      // 현재 보고 있는 대화
  conversations: [],
  shown: PAGE_SIZE,
  editingId: null,
  chart: null,
  sending: false,
};

const $ = id => document.getElementById(id);
const nf = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 });
const fmt = v => (v == null ? '—' : nf.format(v));

/* ── API 공통 ─────────────────────────────── */
async function api(path, { method = 'GET', body, timeout = 15000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(API_BASE + path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    if (res.status === 204) return null;
    const json = await res.json().catch(() => null);
    if (!res.ok) throw new Error(errorText(json, res.status));
    return json;
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.');
    if (e instanceof TypeError) throw new Error('서버에 연결할 수 없습니다. 서버 주소와 실행 상태를 확인하세요.');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// FastAPI 오류 응답({detail: str | [{msg, loc}]})을 사람이 읽을 문장으로
function errorText(json, status) {
  const d = json && json.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map(x => `${(x.loc || []).slice(-1)[0] || ''}: ${x.msg}`).join(', ');
  return `요청 실패 (HTTP ${status})`;
}

/* ── 콜드스타트 대응: /health 로 서버 깨우기 ─── */
async function wakeServer() {
  const status = $('serverStatus');
  const banner = $('coldBanner');
  const slowTimer = setTimeout(() => { banner.hidden = false; }, 2500);
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    try {
      await api('/health', { timeout: 10000 });
      clearTimeout(slowTimer);
      banner.hidden = true;
      status.className = 'status ok';
      status.lastChild.textContent = '서버 연결됨';
      return true;
    } catch (_) {
      await new Promise(r => setTimeout(r, 3000));
    }
  }
  clearTimeout(slowTimer);
  banner.hidden = true;
  status.className = 'status err';
  status.lastChild.textContent = '서버 연결 실패';
  return false;
}

/* ── 요약 + 그래프 ───────────────────────── */
async function loadSummary() {
  try {
    state.summary = await api('/api/data/summary');
    renderSummary();
  } catch (e) {
    $('summaryGrid').innerHTML = '';
    $('summaryGrid').append(el('div', 'empty', `요약을 불러오지 못했습니다: ${e.message}`));
  }
}

function stat(label, value, sub, cls = '') {
  const box = el('div', 'stat ' + cls);
  box.append(el('div', 'stat-label', label), el('div', 'stat-value', value));
  if (sub) box.append(el('div', 'stat-sub', sub));
  return box;
}

function renderSummary() {
  const s = state.summary;
  $('datasetName').textContent = `${s.dataset} · 단위 ${s.unit}`;
  const grid = $('summaryGrid');
  grid.innerHTML = '';
  const m = s.metrics;
  if (!m) {
    grid.append(stat('데이터', '없음', '데이터를 추가하면 요약이 생성됩니다', 'wide'));
    return;
  }
  const trendCls = s.trend.startsWith('상승') ? 'up' : s.trend.startsWith('하락') ? 'down' : '';
  const trendBox = stat('최근 트렌드', s.trend.split(' (')[0], s.trend.match(/\((.*)\)/)?.[1] || '');
  trendBox.querySelector('.stat-value').classList.add(...(trendCls ? [trendCls] : []));
  const chg = stat('기간 변화율', `${m.change_pct > 0 ? '+' : ''}${m.change_pct}%`, '첫 값 대비 최신 값');
  chg.querySelector('.stat-value').classList.add(m.change_pct >= 0 ? 'up' : 'down');
  grid.append(
    stat('기간', s.period, '', 'wide'),
    stat('데이터 개수', `${s.count}개`),
    trendBox,
    stat('최신 값', fmt(m.latest), m.latest_date),
    stat('평균', fmt(m.average)),
    stat('최고', fmt(m.max), m.max_date),
    stat('최저', fmt(m.min), m.min_date),
    chg,
    stat('일간 변동성', `${m.volatility_pct}%`, '일간 변화율 표준편차'),
    stat('이동평균 5 / 20', `${fmt(m.ma5)} / ${fmt(m.ma20)}`, '', 'wide'),
  );
}

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function movingAvg(values, n) {
  return values.map((_, i) => (i + 1 < n ? null : values.slice(i + 1 - n, i + 1).reduce((a, b) => a + b, 0) / n));
}

function renderChart() {
  const labels = state.data.map(d => d.date);
  const values = state.data.map(d => d.value);
  const ds = [
    { label: '값', data: values, borderColor: css('--accent'), backgroundColor: css('--accent-soft'),
      fill: true, tension: .25, pointRadius: 0, borderWidth: 2 },
    { label: '20일 이동평균', data: movingAvg(values, 20), borderColor: css('--warn'),
      borderDash: [5, 4], pointRadius: 0, borderWidth: 1.5, fill: false, tension: .25 },
  ];
  const grid = css('--chart-grid'), tick = css('--muted');
  if (state.chart) {
    state.chart.data.labels = labels;
    state.chart.data.datasets.forEach((d, i) => Object.assign(d, ds[i]));
    state.chart.options.scales.x.grid.color = state.chart.options.scales.y.grid.color = grid;
    state.chart.options.scales.x.ticks.color = state.chart.options.scales.y.ticks.color = tick;
    state.chart.options.plugins.legend.labels.color = tick;
    state.chart.update();
    return;
  }
  state.chart = new Chart($('trendChart'), {
    type: 'line',
    data: { labels, datasets: ds },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: tick, boxWidth: 12 } },
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmt(c.parsed.y)}` } },
      },
      scales: {
        x: { grid: { color: grid }, ticks: { color: tick, maxTicksLimit: 8, maxRotation: 0 } },
        y: { grid: { color: grid }, ticks: { color: tick, callback: v => nf.format(v) } },
      },
    },
  });
}

/* ── 데이터 관리 (CRUD) ───────────────────── */
async function loadData() {
  try {
    state.data = await api('/api/data');
    renderTable();
    renderChart();
  } catch (e) {
    $('dataBody').innerHTML = '';
    const td = el('td', 'empty', `데이터를 불러오지 못했습니다: ${e.message}`);
    td.colSpan = 4;
    $('dataBody').append(rowOf(td));
  }
}

async function refreshData() {
  await Promise.all([loadData(), loadSummary()]);
}

function rowOf(...cells) { const tr = document.createElement('tr'); tr.append(...cells); return tr; }

function renderTable(flashId) {
  const body = $('dataBody');
  body.innerHTML = '';
  const rows = [...state.data].reverse().slice(0, state.shown); // 최신순 표시
  if (!rows.length) {
    const td = el('td', 'empty', '데이터가 없습니다. 위에서 추가하세요.');
    td.colSpan = 4;
    body.append(rowOf(td));
  }
  for (const d of rows) {
    const tr = d.id === state.editingId ? editRow(d) : viewRow(d);
    if (d.id === flashId) tr.classList.add('flash');
    body.append(tr);
  }
  $('dataCount').textContent = `전체 ${state.data.length}개 중 ${Math.min(state.shown, state.data.length)}개 표시 (최신순)`;
  $('moreBtn').hidden = state.shown >= state.data.length;
}

function viewRow(d) {
  const actions = el('td', 'row-actions');
  actions.append(
    button('수정', 'btn small', () => { state.editingId = d.id; renderTable(); }),
    button('삭제', 'btn small danger', () => deleteItem(d)),
  );
  return rowOf(el('td', '', d.date), el('td', 'num', fmt(d.value)), el('td', 'memo', d.memo || ''), actions);
}

function editRow(d) {
  const date = input('date', d.date);
  const value = input('number', d.value); value.min = '0'; value.step = 'any';
  const memo = input('text', d.memo || ''); memo.maxLength = 200;
  const actions = el('td', 'row-actions');
  actions.append(
    button('저장', 'btn small primary', () => saveEdit(d.id, { date: date.value, value: Number(value.value), memo: memo.value })),
    button('취소', 'btn small', () => { state.editingId = null; renderTable(); }),
  );
  const wrap = node => { const td = el('td'); td.append(node); return td; };
  return rowOf(wrap(date), wrap(value), wrap(memo), actions);
}

async function addItem(e) {
  e.preventDefault();
  const btn = $('addBtn');
  const body = { date: $('f-date').value, value: Number($('f-value').value), memo: $('f-memo').value.trim() };
  btn.disabled = true;
  try {
    const item = await api('/api/data', { method: 'POST', body });
    $('dataForm').reset();
    toast(`${item.date} 데이터를 추가했습니다.`, 'ok');
    await refreshData();
    renderTable(item.id);
  } catch (err) {
    toast(`추가 실패: ${err.message}`, 'err');
  } finally {
    btn.disabled = false;
  }
}

async function saveEdit(id, body) {
  if (!body.date || !Number.isFinite(body.value) || body.value < 0) {
    toast('날짜와 0 이상의 값을 입력하세요.', 'err');
    return;
  }
  try {
    const item = await api(`/api/data/${encodeURIComponent(id)}`, { method: 'PUT', body });
    state.editingId = null;
    toast(`${item.date} 데이터를 수정했습니다.`, 'ok');
    await refreshData();
    renderTable(item.id);
  } catch (err) {
    toast(`수정 실패: ${err.message}`, 'err');
  }
}

async function deleteItem(d) {
  if (!confirm(`${d.date} (${fmt(d.value)}) 데이터를 삭제할까요?`)) return;
  try {
    await api(`/api/data/${encodeURIComponent(d.id)}`, { method: 'DELETE' });
    toast(`${d.date} 데이터를 삭제했습니다.`, 'ok');
    await refreshData();
  } catch (err) {
    toast(`삭제 실패: ${err.message}`, 'err');
  }
}

function toast(text, kind) {
  const t = $('dataMsg');
  t.textContent = text;
  t.className = 'toast ' + kind;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.textContent = ''; }, 5000);
}

/* ── 내보내기 (CSV / JSON) ───────────────── */
function download(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportCsv() {
  const esc = s => `"${String(s ?? '').replace(/"/g, '""')}"`;
  const lines = ['date,value,memo', ...state.data.map(d => `${d.date},${d.value},${esc(d.memo)}`)];
  // BOM: 엑셀에서 한글이 깨지지 않도록
  download(`data_${today()}.csv`, '﻿' + lines.join('\r\n'), 'text/csv;charset=utf-8');
}

function exportJson() {
  const payload = { exported_at: new Date().toISOString(), summary: state.summary,
    data: state.data.map(({ date, value, memo }) => ({ date, value, memo })) };
  download(`data_${today()}.json`, JSON.stringify(payload, null, 2), 'application/json');
}

// 현지(브라우저) 날짜 YYYY-MM-DD — toISOString()은 UTC라 한국 오전 9시 전에는 전날이 된다
function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/* ── 대화 기록 ───────────────────────────── */
async function loadConversations() {
  try {
    state.conversations = await api('/api/conversations');
    renderConversations();
  } catch (e) {
    $('convList').innerHTML = '';
    $('convList').append(el('li', 'empty', `목록을 불러오지 못했습니다: ${e.message}`));
  }
}

function renderConversations() {
  const list = $('convList');
  list.innerHTML = '';
  if (!state.conversations.length) {
    list.append(el('li', 'empty', '아직 저장된 대화가 없습니다.'));
    return;
  }
  for (const c of state.conversations) {
    const li = el('li', 'conv-item' + (c.id === state.convId ? ' active' : ''));
    const main = el('div', 'conv-main');
    main.append(el('div', 'conv-title', c.title), el('div', 'conv-meta', `${shortTime(c.updated_at)} · 메시지 ${c.message_count}개`));
    const del = button('✕', 'conv-del', ev => { ev.stopPropagation(); deleteConversation(c); });
    del.title = '대화 삭제';
    li.append(main, del);
    li.addEventListener('click', () => openConversation(c.id));
    list.append(li);
  }
}

function shortTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

async function openConversation(id) {
  if (state.sending) return;
  try {
    const conv = await api(`/api/conversations/${encodeURIComponent(id)}`);
    state.convId = conv.id;
    $('chatTitle').textContent = conv.title;
    $('chatMeta').textContent = `불러온 대화 · 메시지 ${conv.message_count}개`;
    const box = $('messages');
    box.innerHTML = '';
    conv.messages.forEach(m => addMessage(m.role, m.content));
    renderConversations();
  } catch (e) {
    addMessage('error', `대화를 불러오지 못했습니다: ${e.message}`);
  }
}

async function deleteConversation(c) {
  if (!confirm(`'${c.title}' 대화를 삭제할까요?`)) return;
  try {
    await api(`/api/conversations/${encodeURIComponent(c.id)}`, { method: 'DELETE' });
    if (state.convId === c.id) newChat();
    await loadConversations();
  } catch (e) {
    alert(`삭제 실패: ${e.message}`);
  }
}

function newChat() {
  state.convId = null;
  $('chatTitle').textContent = '새 대화';
  $('chatMeta').textContent = '대화는 자동 저장됩니다';
  const box = $('messages');
  box.innerHTML = '';
  box.append(welcomeNode);
  renderConversations();
  $('chatInput').focus();
}

/* ── 채팅 ────────────────────────────────── */
function addMessage(role, text) {
  $('welcome')?.remove();
  const m = el('div', `msg ${role}`, text); // textContent 로 넣어 XSS 차단
  $('messages').append(m);
  m.scrollIntoView({ block: 'end', behavior: 'smooth' });
  return m;
}

function addTyping() {
  const m = addMessage('assistant', '');
  m.innerHTML = '<span class="typing"><span></span><span></span><span></span><em>데이터를 살펴보는 중…</em></span>';
  return m;
}

async function sendMessage(text) {
  text = text.trim();
  if (!text || state.sending) return;
  state.sending = true;
  $('sendBtn').disabled = true;
  $('chatInput').value = '';
  autoGrow();
  addMessage('user', text);
  const typing = addTyping();
  try {
    const res = await api('/api/chat', {
      method: 'POST', body: { message: text, conversation_id: state.convId }, timeout: CHAT_TIMEOUT_MS,
    });
    typing.remove();
    addMessage('assistant', res.reply);
    if (!state.convId) {
      state.convId = res.conversation_id;
      $('chatTitle').textContent = text.length > 30 ? text.slice(0, 30) + '…' : text;
    }
    $('chatMeta').textContent = `사용 키: ${KEY_LABEL[res.key_source] || res.key_source} · 요약 반영: ${res.summary_used.period} · ${res.summary_used.count}개 · ${res.summary_used.trend}`;
    loadConversations();
  } catch (e) {
    typing.remove();
    addMessage('error', `⚠️ ${e.message}`);
  } finally {
    state.sending = false;
    $('sendBtn').disabled = false;
    $('chatInput').focus();
  }
}

function autoGrow() {
  const t = $('chatInput');
  t.style.height = 'auto';
  t.style.height = Math.min(t.scrollHeight, 140) + 'px';
}

/* ── 테마 ────────────────────────────────── */
function syncThemeButton() {
  $('themeBtn').textContent = document.documentElement.classList.contains('light') ? '🌙' : '☀️';
}

function toggleTheme() {
  const light = document.documentElement.classList.toggle('light');
  try { localStorage.setItem('theme', light ? 'light' : 'dark'); } catch (_) {}
  syncThemeButton();
  if (state.data.length) renderChart();
}

/* ── DOM 헬퍼 ────────────────────────────── */
function el(tag, cls = '', text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}
function button(text, cls, onClick) { const b = el('button', cls, text); b.type = 'button'; b.addEventListener('click', onClick); return b; }
function input(type, value) { const i = el('input'); i.type = type; i.value = value; return i; }

/* ── 초기화 ──────────────────────────────── */
const welcomeNode = $('welcome');

function bindEvents() {
  $('themeBtn').addEventListener('click', toggleTheme);
  $('newChatBtn').addEventListener('click', newChat);
  $('dataForm').addEventListener('submit', addItem);
  $('exportCsv').addEventListener('click', exportCsv);
  $('exportJson').addEventListener('click', exportJson);
  $('moreBtn').addEventListener('click', () => { state.shown += PAGE_SIZE; renderTable(); });
  $('chatForm').addEventListener('submit', e => { e.preventDefault(); sendMessage($('chatInput').value); });
  $('chatInput').addEventListener('input', autoGrow);
  $('chatInput').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendMessage($('chatInput').value); }
  });
  $('messages').addEventListener('click', e => { if (e.target.classList.contains('chip')) sendMessage(e.target.textContent); });
  $('f-date').value = today();
}

(async function init() {
  syncThemeButton();
  bindEvents();
  if (await wakeServer()) {
    await Promise.all([refreshData(), loadConversations()]);
  } else {
    const msg = `서버(${API_BASE})에 연결할 수 없습니다.`;
    $('summaryGrid').innerHTML = '';
    $('summaryGrid').append(el('div', 'empty', msg));
    $('convList').innerHTML = '';
    $('convList').append(el('li', 'empty', msg));
  }
})();
