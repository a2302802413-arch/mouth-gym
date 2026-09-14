const state = {
  categories: [],
  questions: [],
  knowledgeCategories: [],
  knowledgeItems: [],
  currentSession: null,
  setupMode: null,
  setupLibraryCategoryId: null,
  editingLibraryId: null,
  timerId: null,
  notesTimer: null,
  cuesTimer: null,
  outlineTimer: null,
  reviewSaveTimer: null,
  mediaStream: null,
  recorder: null,
  audioChunks: [],
  audioBlob: null,
  audioObjectUrl: '',
  recognition: null,
  recognitionSegments: [],
  recognitionInterim: '',
  recognitionError: '',
  speechEpoch: 0,
  captureActive: false,
  stoppingCapture: false,
  pendingSpeech: null,
  autoStartSpeech: false,
  transitioning: false,
  lastSearchResults: [],
  reviewSaveSeq: 0,
};

const CHECKLISTS = {
  improv: [
    '开场是否让听众知道我在说谁、说什么？',
    '核心信息是否明确？',
    '是否给出了理由、例子或类比？',
    '听众是否能理解这件事的价值或意义？',
    '是否有清楚的收尾？',
  ],
  research: [
    '是否先讲清了研究主题或现象？',
    '是否解释了原理或因果机制？',
    '是否用例子或步骤帮助理解？',
    '是否避免了术语堆砌，并解释了必要术语？',
    '是否做了总结或回扣主题？',
  ],
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.remove('hidden');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => el.classList.add('hidden'), 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let data = {};
  try { data = await response.json(); } catch (_) { /* empty response */ }
  if (!response.ok) {
    const detail = data.detail || data.error || `请求失败（${response.status}）`;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function formatTime(totalSeconds) {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

function parseServerTime(value) {
  if (!value) return 0;
  if (typeof value === 'number') return value;
  const text = String(value);
  if (/Z|[+-]\d{2}:\d{2}$/.test(text)) return Date.parse(text);
  return Date.parse(text.replace(' ', 'T') + 'Z');
}

function clearTimer() {
  if (state.timerId) {
    clearInterval(state.timerId);
    state.timerId = null;
  }
}

function remainFor(session, phase) {
  let duration = 0;
  if (phase === 'prep') duration = 30;
  if (phase === 'research') duration = 600;
  if (phase === 'speech') duration = Number(session.speech_duration_seconds || 60);
  const field = phase === 'prep'
    ? session.prep_started_at
    : (phase === 'research' ? session.research_started_at : session.speech_started_at);
  const started = parseServerTime(field);
  if (!started) return duration;
  return Math.max(0, Math.ceil((started + duration * 1000 - Date.now()) / 1000));
}

function startTimer(seconds, onEnd, render) {
  clearTimer();
  let remaining = Math.max(0, Math.floor(seconds));
  render(remaining);
  if (remaining <= 0) {
    setTimeout(onEnd, 0);
    return;
  }
  state.timerId = setInterval(() => {
    remaining -= 1;
    render(remaining);
    if (remaining <= 0) {
      clearTimer();
      onEnd();
    }
  }, 1000);
}

function renderTimer(seconds) {
  const el = $('#timer-display');
  if (!el) return;
  el.textContent = formatTime(seconds);
  el.classList.toggle('warn', seconds <= 10);
}

function modeLabel(mode) {
  return mode === 'improv' ? '即兴发挥' : '深度研究';
}

function statusText(status) {
  return {
    prep: '准备中',
    research: '研究中',
    speech: '表达中',
    review: '复盘中',
    done: '已完成',
  }[status] || status;
}

function topicText(session) {
  return session?.topic_text || session?.question_text || session?.knowledge_title || '未指定主题';
}

function currentAudioUrl(session) {
  if (state.audioObjectUrl && state.currentSession?.id === session.id) return state.audioObjectUrl;
  return session?.transcript?.audio_path ? `/api/sessions/${session.id}/audio` : '';
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(parseServerTime(value));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

/* ---------------- navigation and initialization ---------------- */
function switchView(name) {
  if (name !== 'home' && state.currentSession?.status === 'speech' && state.captureActive) {
    toast('表达进行中，请先停止并保存');
    return;
  }
  clearTimer();
  $$('.tab-btn').forEach((button) => button.classList.toggle('active', button.dataset.view === name));
  $$('.view').forEach((view) => view.classList.toggle('active', view.id === `view-${name}`));
  if (name === 'home') renderHome();
  if (name === 'bank') renderBank();
  if (name === 'library') renderLibrary();
  if (name === 'history') renderHistory();
}

async function init() {
  $$('.tab-btn').forEach((button) => button.addEventListener('click', () => switchView(button.dataset.view)));
  $('.brand').addEventListener('click', () => switchView('home'));
  $('#improv-mode-btn').addEventListener('click', () => showModeSetup('improv'));
  $('#research-mode-btn').addEventListener('click', () => showModeSetup('research'));
  $('#add-category-btn').addEventListener('click', addCategory);
  $('#add-question-btn').addEventListener('click', addQuestion);
  $('#bank-category-filter').addEventListener('change', renderQuestionList);
  $('#bank-search-input').addEventListener('input', renderQuestionList);
  $('#add-library-category-btn').addEventListener('click', addLibraryCategory);
  $('#library-category-filter').addEventListener('change', renderLibraryList);
  $('#new-library-item-btn').addEventListener('click', () => openLibraryEditor());
  $('#cancel-library-edit-btn').addEventListener('click', closeLibraryEditor);
  $('#save-library-item-btn').addEventListener('click', saveLibraryItem);
  window.addEventListener('beforeunload', () => {
    stopMediaTracks();
    if (state.recognition) {
      try { state.recognition.stop(); } catch (_) { /* ignore */ }
    }
  });

  try {
    await Promise.all([loadCategories(), loadQuestions(), loadLibraryData()]);
  } catch (error) {
    toast(error.message);
  }
  populateCategorySelects();
  populateLibrarySelects();
  await restoreActiveSession();
  renderHome();
}

async function loadCategories() {
  state.categories = (await api('/api/categories')).items || [];
}

async function loadQuestions() {
  state.questions = (await api('/api/questions')).items || [];
}

async function loadLibraryData() {
  const [categories, items] = await Promise.all([
    api('/api/library/categories'),
    api('/api/library/items'),
  ]);
  state.knowledgeCategories = categories.items || [];
  state.knowledgeItems = items.items || [];
}

async function restoreActiveSession() {
  try {
    const data = await api('/api/sessions?limit=50');
    const active = (data.items || []).find((session) =>
      ['prep', 'research', 'speech', 'review'].includes(session.status));
    if (active) state.currentSession = await api(`/api/sessions/${active.id}`);
  } catch (_) { /* remain on home */ }
}
/* ---------------- home and mode setup ---------------- */
function renderHome() {
  const starter = $('#home-start');
  const panel = $('#session-panel');
  if (state.currentSession) {
    starter.classList.add('hidden');
    panel.classList.remove('hidden');
    renderSession();
    return;
  }
  panel.classList.add('hidden');
  panel.innerHTML = '';
  starter.classList.remove('hidden');
  $('#resume-card').classList.add('hidden');
  renderModeSetup(state.setupMode);
}

function showModeSetup(mode) {
  state.setupMode = mode;
  renderModeSetup(mode);
}

function durationField(id = 'speech-duration') {
  return `
    <label class="field"><span>表达时长</span>
      <select id="${id}">
        <option value="60" selected>1 分钟</option>
        <option value="120">2 分钟</option>
        <option value="180">3 分钟</option>
      </select>
    </label>`;
}

function renderModeSetup(mode) {
  const box = $('#mode-setup');
  if (!mode) {
    box.classList.add('hidden');
    box.innerHTML = '';
    return;
  }
  box.classList.remove('hidden');
  if (mode === 'improv') {
    box.innerHTML = `
      <div class="section-heading">
        <div><span class="eyebrow">即兴发挥</span><h2>随机题，不换题</h2></div>
        <button id="close-setup-btn">返回</button>
      </div>
      <p class="hint">点击开始后立即随机抽题，给你 30 秒准备，然后自动进入表达。</p>
      <div class="form-grid compact">${durationField()}</div>
      <button id="start-improv-btn" class="primary large">随机抽题并开始</button>`;
  } else {
    const selectedCategory = state.setupLibraryCategoryId;
    box.innerHTML = `
      <div class="section-heading">
        <div><span class="eyebrow">深度研究</span><h2>随机抽题，或带上自己的主题</h2></div>
        <button id="close-setup-btn">返回</button>
      </div>
      <div class="research-choice-grid">
        <article class="research-choice-card random">
          <span class="choice-number">01</span>
          <h3>随机抽题</h3>
          <p>从本地资料库随机抽取一个效应、实验或机器原理，适合练习快速理解陌生知识。</p>
          <label class="field"><span>抽取范围</span>
            <select id="setup-random-category"><option value="">全部资料</option>
              ${state.knowledgeCategories.map((category) => `<option value="${category.id}" ${category.id === selectedCategory ? 'selected' : ''}>${escapeHtml(category.name)}</option>`).join('')}
            </select>
          </label>
          <button id="start-random-research-btn" class="primary">随机抽题并开始</button>
        </article>
        <article class="research-choice-card custom">
          <span class="choice-number">02</span>
          <h3>自定义主题</h3>
          <p>输入任何想讲清楚的问题，用 10 分钟搜索资料、整理笔记和提纲。</p>
          <label class="field"><span>研究主题</span>
            <input id="setup-custom-topic" placeholder="例如：为什么空调能降低室内温度？">
          </label>
          <button id="start-custom-research-btn" class="primary">自定义主题并开始</button>
        </article>
      </div>
      <div class="research-duration">${durationField()}</div>
      <p class="hint">两种方式都会自动进入 10 分钟研究计时。</p>`;
  }
  $('#close-setup-btn').addEventListener('click', () => {
    state.setupMode = null;
    renderModeSetup(null);
  });
  if (mode === 'improv') {
    $('#start-improv-btn').addEventListener('click', startImprov);
  } else {
    $('#setup-random-category').addEventListener('change', (event) => {
      state.setupLibraryCategoryId = Number(event.target.value) || null;
      renderModeSetup('research');
    });
    $('#start-random-research-btn').addEventListener('click', startRandomResearch);
    $('#start-custom-research-btn').addEventListener('click', startCustomResearch);
  }
}

async function requestMicrophoneForLater() {
  if (!navigator.mediaDevices?.getUserMedia) return false;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    return true;
  } catch (error) {
    toast(`麦克风不可用：${error.message}。仍可进入计时练习。`);
    return false;
  }
}

async function startImprov() {
  const duration = Number($('#speech-duration').value);
  await requestMicrophoneForLater();
  try {
    const data = await api('/api/sessions/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'improv', speech_duration_seconds: duration }),
    });
    state.currentSession = data.session;
    state.setupMode = null;
    renderHome();
  } catch (error) {
    toast(error.message);
  }
}

async function beginResearch(payload) {
  await requestMicrophoneForLater();
  try {
    const data = await api('/api/sessions/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'research', ...payload }),
    });
    state.currentSession = data.session;
    state.setupMode = null;
    renderHome();
  } catch (error) {
    toast(error.message);
  }
}

async function startRandomResearch() {
  const duration = Number($('#speech-duration').value);
  const categoryId = Number($('#setup-random-category').value) || null;
  await beginResearch({
    topic_source: 'random',
    category_id: categoryId,
    speech_duration_seconds: duration,
  });
}

async function startCustomResearch() {
  const duration = Number($('#speech-duration').value);
  const topicText = $('#setup-custom-topic').value.trim();
  if (!topicText) {
    toast('请输入自定义研究主题');
    return;
  }
  await beginResearch({
    topic_source: 'custom',
    topic_text: topicText,
    speech_duration_seconds: duration,
  });
}
/* ---------------- session phase rendering ---------------- */
function renderSession() {
  const session = state.currentSession;
  if (!session) {
    renderHome();
    return;
  }
  clearTimer();
  $('#home-start').classList.add('hidden');
  const panel = $('#session-panel');
  panel.classList.remove('hidden');

  if (session.status === 'prep') {
    panel.innerHTML = renderPrepHtml(session);
    bindPrep(session);
    startTimer(remainFor(session, 'prep'), () => enterSpeech(true), renderTimer);
  } else if (session.status === 'research') {
    panel.innerHTML = renderResearchHtml(session);
    bindResearch(session);
    startTimer(remainFor(session, 'research'), () => enterSpeech(true), renderTimer);
  } else if (session.status === 'speech') {
    panel.innerHTML = renderSpeechHtml(session);
    bindSpeech(session);
    startTimer(remainFor(session, 'speech'), () => stopSpeechCapture(true), renderTimer);
    if (state.autoStartSpeech) {
      state.autoStartSpeech = false;
      setTimeout(() => startSpeechCapture(), 150);
    }
  } else if (session.status === 'review') {
    panel.innerHTML = renderReviewHtml(session);
    bindReview(session);
  } else {
    panel.innerHTML = renderDoneHtml(session);
    bindDone();
  }
}

function renderPrepHtml(session) {
  return `
    <div class="card practice-card">
      <div class="practice-head">
        <div><span class="phase-badge">即兴准备</span><p class="hint">快速确定观点和结构，30 秒后自动开始录音。</p></div>
        <div class="timer" id="timer-display">00:30</div>
      </div>
      <div class="question-card">${escapeHtml(topicText(session))}</div>
      <div class="callout">
        <b>准备提示</b>
        <span>先想结论，再补一个理由或例子，最后想好怎么收尾。</span>
      </div>
      <div class="cue-editor">
        <div class="cue-editor-head">
          <label for="prep-cues-input">表达提示词</label>
          <span id="prep-cue-status" class="hint">只写关键词，表达时会显示</span>
        </div>
        <textarea id="prep-cues-input" placeholder="例如：结论 → 一个理由 → 一个例子 → 收尾">${escapeHtml(session.speech_cues || '')}</textarea>
      </div>
      <button id="early-speech-btn" class="primary">提前开始表达</button>
    </div>`;
}

function bindPrep(session) {
  $('#early-speech-btn').addEventListener('click', () => enterSpeech(true));
  $('#prep-cues-input').addEventListener('input', (event) => {
    if (state.currentSession) state.currentSession.speech_cues = event.target.value;
    clearTimeout(state.cuesTimer);
    const status = $('#prep-cue-status');
    if (status) status.textContent = '正在保存…';
    state.cuesTimer = setTimeout(() => {
      savePrepCues(session.id, event.target.value, true);
    }, 450);
  });
}

async function savePrepCues(sessionId, content, showStatus = false) {
  try {
    await api(`/api/sessions/${sessionId}/cues`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (state.currentSession) state.currentSession.speech_cues = content;
    const status = $('#prep-cue-status');
    if (showStatus && status) status.textContent = '已自动保存';
    return true;
  } catch (error) {
    const status = $('#prep-cue-status');
    if (status) status.textContent = `保存失败：${error.message}`;
    return false;
  }
}

async function enterSpeech(autoStart) {
  if (!state.currentSession || state.transitioning) return;
  state.transitioning = true;
  clearTimer();
  clearTimeout(state.cuesTimer);
  const cuesInput = $('#prep-cues-input');
  if (cuesInput) {
    await savePrepCues(state.currentSession.id, cuesInput.value.trim());
  }
  try {
    state.currentSession = await api(`/api/sessions/${state.currentSession.id}/phase`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'speech' }),
    });
    state.autoStartSpeech = Boolean(autoStart);
    state.transitioning = false;
    renderSession();
  } catch (error) {
    state.transitioning = false;
    toast(error.message);
    if (state.currentSession?.status === 'speech') renderSession();
  }
}

function renderResearchHtml(session) {
  const material = session.material_snapshot
    ? `<details class="material-panel" open><summary>本次研究资料</summary><div class="pre-wrap">${escapeHtml(session.material_snapshot)}</div></details>`
    : '<p class="hint">这是自定义主题。可先搜索资料，再把关键内容写进笔记和提纲。</p>';
  return `
    <div class="card practice-card">
      <div class="practice-head">
        <div><span class="phase-badge">深度研究</span><p class="hint">10 分钟后自动进入表达，也可以提前结束。</p></div>
        <div class="timer" id="timer-display">10:00</div>
      </div>
      <div class="question-card">${escapeHtml(topicText(session))}</div>
      ${material}
      <div class="research-grid">
        <section class="research-column search-column">
          <div class="section-heading compact-heading search-heading">
            <div><h3>网页搜索</h3><p class="hint">结果会完整展开；点击“ai搜索”会在应用旁边打开 DeepSeek 小窗。</p></div>
            <button id="deepseek-popup-btn" class="quick-search-link" type="button" title="在应用窗口旁边打开 DeepSeek AI 搜索">ai搜索</button>
          </div>
          <div class="row">
            <input id="search-input" placeholder="搜索关键词" style="flex:1" value="${escapeHtml(topicText(session))}">
            <button id="search-btn" class="primary">搜索</button>
          </div>
          <div id="search-results" class="search-results"></div>
        </section>
        <div class="notes-grid">
          <section class="research-column">
            <h3>我的笔记</h3>
            <textarea id="notes-input" placeholder="记录现象、原理、例子和数字">${escapeHtml(session.notes || '')}</textarea>
          </section>
          <section class="research-column">
            <h3>我的提纲</h3>
            <textarea id="outline-input" placeholder="1. 开场\n2. 核心机制\n3. 例子\n4. 收尾">${escapeHtml(session.outline || '')}</textarea>
          </section>
        </div>
      </div>
      <button id="early-speech-btn" class="primary">结束研究并开始表达</button>
      <div id="research-status" class="status"></div>
    </div>`;
}

function openDeepSeekPopup() {
  const margin = 16;
  const screenWidth = Number(window.screen?.availWidth || window.screen?.width || 1440);
  const screenHeight = Number(window.screen?.availHeight || window.screen?.height || 900);
  const width = Math.round(Math.min(540, Math.max(380, screenWidth * 0.38)));
  const height = Math.round(Math.min(920, Math.max(600, (window.outerHeight || screenHeight) - 40), screenHeight - 32));
  const appLeft = Number.isFinite(window.screenX) ? window.screenX : Math.max(0, (screenWidth - (window.outerWidth || screenWidth)) / 2);
  const appTop = Number.isFinite(window.screenY) ? window.screenY : 20;
  const appRight = appLeft + (window.outerWidth || window.innerWidth || screenWidth);
  const rightSideLeft = appRight + margin;
  const leftSideLeft = appLeft - width - margin;
  const left = rightSideLeft + width <= screenWidth - margin
    ? rightSideLeft
    : (leftSideLeft >= margin ? leftSideLeft : Math.max(margin, screenWidth - width - margin));
  const top = Math.max(0, Math.min(appTop, screenHeight - height - margin));
  const features = `popup=yes,width=${width},height=${height},left=${Math.round(left)},top=${Math.round(top)},resizable=yes,scrollbars=yes`;
  const popup = window.open('https://chat.deepseek.com/', 'mouthGymDeepSeek', features);
  if (!popup) {
    toast('浏览器拦截了 DeepSeek 弹窗，请允许本站弹出窗口后重试');
    return;
  }
  popup.focus();
}

function bindResearch(session) {
  $('#early-speech-btn').addEventListener('click', () => enterSpeech(true));
  $('#deepseek-popup-btn').addEventListener('click', openDeepSeekPopup);
}

async function saveResearchText(sessionId, kind, content) {
  const path = kind === 'notes' ? 'notes' : 'user-outline';
  try {
    await api(`/api/sessions/${sessionId}/research/${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (state.currentSession) state.currentSession[kind] = content;
    const status = $('#research-status');
    if (status) status.textContent = '已自动保存';
  } catch (error) {
    const status = $('#research-status');
    if (status) status.textContent = `保存失败：${error.message}`;
  }
}

async function searchResearch(sessionId) {
  const query = $('#search-input').value.trim();
  const results = $('#search-results');
  if (!query) {
    toast('请输入搜索词');
    return;
  }
  results.innerHTML = '<p class="hint">搜索中…</p>';
  try {
    const data = await api(`/api/sessions/${sessionId}/research/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    if (data.warning) {
      results.innerHTML = `<p class="hint warning-text">${escapeHtml(data.warning)}</p>`;
      return;
    }
    state.lastSearchResults = data.items || [];
    results.innerHTML = state.lastSearchResults.length
      ? state.lastSearchResults.map((item, index) => `
          <article class="search-result">
            <div class="search-result-head">
              <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>
              <span class="search-source">网页资料</span>
            </div>
            <p class="search-snippet">${escapeHtml(item.body)}</p>
            <div class="search-result-actions">
              <button data-open-index="${index}" class="small primary">打开原文</button>
            </div>
          </article>`).join('')
      : '<p class="hint">没有搜索到结果。</p>';
    $$('#search-results [data-open-index]').forEach((button) => {
      button.addEventListener('click', () => openSearchResult(Number(button.dataset.openIndex)));
    });
  } catch (error) {
    results.innerHTML = `<p class="hint warning-text">${escapeHtml(error.message)}</p>`;
  }
}

function openExternalUrl(url) {
  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('unsupported');
    const link = document.createElement('a');
    link.href = parsed.href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    document.body.appendChild(link);
    link.click();
    link.remove();
  } catch (_) {
    toast('这条结果没有可打开的原网页链接');
  }
}

function openSearchResult(index) {
  const item = state.lastSearchResults[index];
  if (!item?.url) return toast('这条结果没有原网页链接');
  openExternalUrl(item.url);
}

/* ---------------- browser recording and speech recognition ---------------- */
function renderSpeechHtml(session) {
  const cues = String(session.speech_cues || '').trim();
  return `
    <div class="card practice-card speech-card">
      <div class="practice-head">
        <div><span class="phase-badge recording">表达中</span><p class="hint">录音和中文识别会同时进行，时间到会自动停止。</p></div>
        <div class="timer" id="timer-display">${formatTime(session.speech_duration_seconds)}</div>
      </div>
      <div class="question-card">${escapeHtml(topicText(session))}</div>
      ${cues ? `
        <section class="cue-display">
          <div class="cue-display-head"><span>表达提示词</span><small>按关键词继续表达</small></div>
          <div class="pre-wrap">${escapeHtml(cues)}</div>
        </section>` : ''}
      <div class="recording-wave"><span></span><span></span><span></span><span></span><span></span></div>
      <div class="row center-row">
        <button id="manual-start-btn" class="primary" ${state.captureActive ? 'disabled' : ''}>开始录音</button>
        <button id="stop-speech-btn" ${state.captureActive ? '' : 'disabled'}>停止并保存</button>
      </div>
      <div id="recording-status" class="status">${state.captureActive ? '● 正在录音并识别…' : '正在准备麦克风和语音识别…'}</div>
      <div class="live-transcript">
        <h3>实时文字</h3>
        <div id="live-transcript-text">${state.recognitionSegments.map((segment) => escapeHtml(segment.text)).join('')}${escapeHtml(state.recognitionInterim)}</div>
      </div>
    </div>`;
}

function bindSpeech() {
  $('#manual-start-btn').addEventListener('click', startSpeechCapture);
  $('#stop-speech-btn').addEventListener('click', () => stopSpeechCapture(false));
}

function updateLiveTranscript() {
  const box = $('#live-transcript-text');
  if (!box) return;
  box.innerHTML = state.recognitionSegments.map((segment) => escapeHtml(segment.text)).join('')
    + escapeHtml(state.recognitionInterim);
}

function sentenceChunks(text) {
  return (String(text).match(/[^。！？!?；;\n]+[。！？!?；;]?/g) || [String(text)])
    .map((part) => part.trim())
    .filter(Boolean);
}

function mergeInterim() {
  if (!state.recognitionInterim.trim()) return;
  const text = state.recognitionInterim.trim();
  const elapsed = Math.max(0, Date.now() - state.speechEpoch);
  const previousEnd = state.recognitionSegments.length
    ? state.recognitionSegments[state.recognitionSegments.length - 1].end_ms
    : 0;
  sentenceChunks(text).forEach((sentence, index, list) => {
    const start = previousEnd + Math.round((elapsed - previousEnd) * index / list.length);
    const end = previousEnd + Math.round((elapsed - previousEnd) * (index + 1) / list.length);
    state.recognitionSegments.push({ text: sentence, start_ms: start, end_ms: end, unclear: false, note: '' });
  });
  state.recognitionInterim = '';
  updateLiveTranscript();
}

function startSpeechCapture() {
  if (state.captureActive || state.stoppingCapture) return;
  if (state.currentSession?.status !== 'speech') return;
  if (!navigator.mediaDevices?.getUserMedia) {
    setRecordingStatus('当前浏览器不支持录音，请使用新版 Chrome 或 Edge。');
    toast('当前浏览器不支持麦克风录音');
    return;
  }

  state.speechEpoch = parseServerTime(state.currentSession.speech_started_at) || Date.now();
  state.recognitionSegments = [];
  state.recognitionInterim = '';
  state.recognitionError = '';
  state.audioChunks = [];
  state.stoppingCapture = false;

  navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    state.mediaStream = stream;
    const canRecord = typeof MediaRecorder !== 'undefined';
    if (canRecord) {
      const preferred = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4');
      state.recorder = new MediaRecorder(stream, { mimeType: preferred });
      state.recorder.ondataavailable = (event) => {
        if (event.data?.size) state.audioChunks.push(event.data);
      };
      state.recorder.onstop = finishSpeechCapture;
      state.recorder.start(250);
    }

    state.captureActive = true;
    startSpeechRecognition();
    const startButton = $('#manual-start-btn');
    const stopButton = $('#stop-speech-btn');
    if (startButton) startButton.disabled = true;
    if (stopButton) stopButton.disabled = false;
    setRecordingStatus(canRecord
      ? '● 正在录音并识别…'
      : '● 浏览器不支持录音文件，仅进行文字识别…');
  }).catch((error) => {
    state.captureActive = false;
    setRecordingStatus(`无法访问麦克风：${error.message}。仍可等待计时结束或手动记录。`);
    toast('无法访问麦克风');
  });
}

function startSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    state.recognitionError = '当前浏览器不支持自动语音识别，你仍可录音后在复盘页手动补充文字。';
    setRecordingStatus(`● 正在录音… ${state.recognitionError}`);
    return;
  }
  const recognition = new SpeechRecognition();
  state.recognition = recognition;
  recognition.lang = 'zh-CN';
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    let interim = '';
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      const text = result[0]?.transcript?.trim() || '';
      if (!text) continue;
      if (!result.isFinal) {
        interim += text;
        continue;
      }
      const elapsed = Math.max(0, Date.now() - state.speechEpoch);
      const parts = sentenceChunks(text);
      const previousEnd = state.recognitionSegments.length
        ? state.recognitionSegments[state.recognitionSegments.length - 1].end_ms
        : 0;
      parts.forEach((sentence, partIndex) => {
        const start = previousEnd + Math.round((elapsed - previousEnd) * partIndex / parts.length);
        const end = previousEnd + Math.round((elapsed - previousEnd) * (partIndex + 1) / parts.length);
        state.recognitionSegments.push({
          text: sentence,
          start_ms: start,
          end_ms: Math.max(start, end),
          unclear: false,
          note: '',
        });
      });
    }
    state.recognitionInterim = interim;
    updateLiveTranscript();
  };
  recognition.onerror = (event) => {
    if (event.error === 'no-speech' || event.error === 'aborted') return;
    state.recognitionError = event.error === 'not-allowed'
      ? '语音识别权限被拒绝，录音仍会继续。'
      : `语音识别暂时不可用（${event.error}），录音仍会继续。`;
    setRecordingStatus(`● 正在录音… ${state.recognitionError}`);
  };
  recognition.onend = () => {
    if (state.captureActive && !state.stoppingCapture && state.recognitionError !== '语音识别权限被拒绝，录音仍会继续。') {
      setTimeout(() => {
        if (state.captureActive && !state.stoppingCapture) {
          try { recognition.start(); } catch (_) { /* already started */ }
        }
      }, 180);
    }
  };
  try {
    recognition.start();
  } catch (error) {
    state.recognitionError = `无法启动语音识别：${error.message}`;
    setRecordingStatus(`● 正在录音… ${state.recognitionError}`);
  }
}

function setRecordingStatus(message) {
  const status = $('#recording-status');
  if (status) status.textContent = message;
}

function stopSpeechCapture(auto) {
  if (state.stoppingCapture) return;
  clearTimer();
  if (!state.captureActive) {
    if (auto) enterReviewWithoutCapture();
    return;
  }
  state.stoppingCapture = true;
  mergeInterim();
  if (state.recognition) {
    try { state.recognition.stop(); } catch (_) { /* ignore */ }
  }
  setRecordingStatus(auto ? '时间到，正在停止录音…' : '正在停止并保存…');
  if (state.recorder && state.recorder.state !== 'inactive') {
    state.recorder.stop();
  } else {
    finishSpeechCapture();
  }
}

function stopMediaTracks() {
  if (state.mediaStream) {
    state.mediaStream.getTracks().forEach((track) => track.stop());
    state.mediaStream = null;
  }
}

async function finishSpeechCapture() {
  state.captureActive = false;
  stopMediaTracks();
  if (state.audioObjectUrl) URL.revokeObjectURL(state.audioObjectUrl);
  const type = state.recorder?.mimeType || 'audio/webm';
  state.audioBlob = state.audioChunks.length ? new Blob(state.audioChunks, { type }) : null;
  state.audioObjectUrl = state.audioBlob ? URL.createObjectURL(state.audioBlob) : '';
  await uploadPendingSpeech();
}

function buildSpeechText() {
  return state.recognitionSegments.map((segment) => segment.text).join('');
}

async function uploadPendingSpeech() {
  const session = state.currentSession;
  if (!session) return;
  setRecordingStatus('正在保存录音和文字…');
  const type = state.audioBlob?.type || state.recorder?.mimeType || 'audio/webm';
  const extension = type.includes('mp4') ? 'mp4' : 'webm';
  const form = new FormData();
  if (state.audioBlob) form.append('file', state.audioBlob, `speech.${extension}`);
  form.append('text', buildSpeechText());
  form.append('segments_json', JSON.stringify(state.recognitionSegments));
  state.pendingSpeech = { form };
  try {
    const response = await fetch(`/api/sessions/${session.id}/speech`, { method: 'POST', body: form });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || '保存失败');
    state.currentSession = data;
    state.pendingSpeech = null;
    state.stoppingCapture = false;
    renderSession();
  } catch (error) {
    state.stoppingCapture = false;
    renderUploadPending(error.message);
  }
}

function renderUploadPending(message) {
  const panel = $('#session-panel');
  const audio = state.audioObjectUrl ? `<audio controls src="${state.audioObjectUrl}"></audio>` : '';
  const transcript = buildSpeechText() || '没有识别到文字，可在保存后手动补充。';
  panel.innerHTML = `
    <div class="card practice-card">
      <span class="phase-badge warning">等待保存</span>
      <h2>表达已经结束</h2>
      <p class="hint warning-text">${escapeHtml(message)}</p>
      ${audio}
      <h3>本次文字草稿</h3>
      <div class="card pre-wrap">${escapeHtml(transcript)}</div>
      <div class="row">
        <button id="retry-upload-btn" class="primary">重试保存</button>
      </div>
    </div>`;
  $('#retry-upload-btn').addEventListener('click', uploadPendingSpeech);
}

async function enterReviewWithoutCapture() {
  try {
    state.currentSession = await api(`/api/sessions/${state.currentSession.id}/phase`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'review' }),
    });
    renderSession();
  } catch (error) {
    toast(error.message);
  }
}
/* ---------------- review ---------------- */
function reviewChecklist(session) {
  return session.review?.checklist || {};
}

function reviewSegments(session) {
  const segments = Array.isArray(session.segments) ? session.segments : [];
  if (segments.length) return segments;
  const text = session.transcript?.text || '';
  if (!text) return [];
  const duration = Number(session.speech_duration_seconds || 60) * 1000;
  const parts = sentenceChunks(text);
  return parts.map((part, index) => ({
    id: `draft-${index}`,
    text: part,
    start_ms: Math.round(duration * index / parts.length),
    end_ms: Math.round(duration * (index + 1) / parts.length),
    unclear: 0,
    note: '',
  }));
}

const REVIEW_STEP_MARKER = /^(第[一二三四五六七八九十]+|首先|其次|然后|接下来|最后|另外|此外|总结|综上|一是|二是|三是)/;

function groupReviewSteps(segments) {
  const groups = [];
  let current = [];
  let currentChars = 0;

  function flush() {
    if (!current.length) return;
    groups.push(current);
    current = [];
    currentChars = 0;
  }

  segments.forEach((segment) => {
    const text = String(segment.text || '').trim();
    const previous = current[current.length - 1];
    const gap = previous
      ? Math.max(0, Number(segment.start_ms || 0) - Number(previous.end_ms || 0))
      : 0;
    const startsNewPoint = current.length >= 2 && REVIEW_STEP_MARKER.test(text);
    const hasEnoughSentences = current.length >= 3 && currentChars >= 72;
    const hasTooManySentences = current.length >= 5;
    const wouldBeTooLong = currentChars > 0 && currentChars + text.length > 180;
    const hasLongPause = current.length >= 2 && gap >= 2200;

    if (startsNewPoint || hasEnoughSentences || hasTooManySentences || wouldBeTooLong || hasLongPause) {
      flush();
    }

    current.push(segment);
    currentChars += text.length;
  });
  flush();

  if (groups.length >= 2) {
    const last = groups[groups.length - 1];
    const previous = groups[groups.length - 2];
    if (last.length === 1 && previous.length < 5 && previous.length + last.length <= 5) {
      previous.push(...last);
      groups.pop();
    }
  }
  return groups;
}

function reviewBodyHtml(session, readonly = false) {
  const audioUrl = currentAudioUrl(session);
  const segments = reviewSegments(session);
  const steps = groupReviewSteps(segments);
  const checklist = reviewChecklist(session);
  const items = CHECKLISTS[session.mode] || CHECKLISTS.improv;

  const segmentHtml = (segment, index) => `
    <article class="segment-card ${segment.unclear ? 'unclear' : ''}" data-segment-index="${index}">
      <div class="segment-time">${formatTime((segment.start_ms || 0) / 1000)}</div>
      ${readonly
        ? `<div class="segment-text readonly">${escapeHtml(segment.text)}</div>`
        : `<textarea class="segment-text" data-field="text">${escapeHtml(segment.text)}</textarea>`}
      <div class="segment-actions">
        ${readonly
          ? (segment.unclear ? '<span class="mark-label">已标记没讲清楚</span>' : '')
          : `<button type="button" class="mark-btn ${segment.unclear ? 'active' : ''}">${segment.unclear ? '已标记' : '标记没讲清楚'}</button>`}
      </div>
      ${readonly
        ? (segment.note ? `<div class="segment-note">${escapeHtml(segment.note)}</div>` : '')
        : `<input class="segment-note-input" data-field="note" placeholder="为什么这一步不清楚？" value="${escapeHtml(segment.note || '')}">`}
    </article>`;

  const stepsHtml = steps.length
    ? steps.map((step, stepIndex) => {
        const start = Number(step[0]?.start_ms || 0);
        const end = Number(step[step.length - 1]?.end_ms || start);
        const stepUnclear = step.some((segment) => Boolean(segment.unclear));
        const childHtml = step.map((segment) => segmentHtml(segment, segments.indexOf(segment))).join('');
        return `
          <section class="review-step ${stepUnclear ? 'unclear' : ''}" data-step-index="${stepIndex}">
            <div class="review-step-head">
              <div class="step-heading">
                <span class="step-badge">步骤 ${stepIndex + 1}</span>
                <span class="step-meta">${formatTime(start / 1000)} - ${formatTime(end / 1000)} · ${step.length} 句</span>
              </div>
              ${readonly ? '' : `<button type="button" class="step-mark-btn ${stepUnclear ? 'active' : ''}">${stepUnclear ? '本步骤已标记' : '标记整步没讲清楚'}</button>`}
            </div>
            <div class="segment-list">${childHtml}</div>
          </section>`;
      }).join('')
    : `${readonly ? '<p class="hint">没有自动识别到文字。</p>' : `
        <label class="field"><span>手动补充转写</span>
          <textarea id="manual-review-text" placeholder="听录音后，在这里补充或修正你的表达内容"></textarea>
        </label>`}`;

  const checklistHtml = items.map((item, index) => {
    const key = `item_${index}`;
    const checked = Boolean(checklist[key]);
    return `<label class="check-item ${readonly ? 'readonly' : ''}">
      <input type="checkbox" data-check-key="${key}" ${checked ? 'checked' : ''} ${readonly ? 'disabled' : ''}>
      <span>${escapeHtml(item)}</span>
    </label>`;
  }).join('');

  return `
    <div class="review-summary">
      <span class="phase-badge">${statusText(session.status)}</span>
      <span>时长 ${formatTime(session.speech_duration_seconds)}</span>
      <span>${steps.length} 个步骤 · ${segments.length} 句</span>
      <span>${segments.filter((segment) => segment.unclear).length} 处标记</span>
    </div>
    <div class="question-card">${escapeHtml(topicText(session))}</div>
    ${audioUrl ? `<audio id="review-audio" controls src="${audioUrl}"></audio>` : '<p class="hint">本次没有录音文件，可在下方补充文字。</p>'}
    <div class="review-grid">
      <section>
        <h3>逐步复盘</h3>
        <p class="hint">相邻的 2-4 句话会按停顿、转折词和内容长度合并成一步；点击句子定位录音，也可以整步标记。</p>
        <div class="step-list">${stepsHtml}</div>
      </section>
      <section>
        <h3>表达自检</h3>
        <div class="checklist">${checklistHtml}</div>
        <h3>自由复盘</h3>
        <textarea id="review-reflection" placeholder="下次最想改进的一件事是什么？" ${readonly ? 'disabled' : ''}>${escapeHtml(session.review?.reflection || '')}</textarea>
      </section>
    </div>
    ${readonly ? '' : `
      <div class="row center-row review-save-row">
        <button id="save-review-btn">保存复盘</button>
        <button id="complete-review-btn" class="primary">完成复盘</button>
      </div>
      <div id="review-save-status" class="status"></div>`}`;
}

function renderReviewHtml(session) {
  return `
    <div class="card practice-card">
      <div class="section-heading">
        <div><span class="eyebrow">表达结束</span><h2>听一遍，再看哪里没讲清楚</h2></div>
        <span class="hint">内容会自动保存在本机</span>
      </div>
      ${reviewBodyHtml(session, false)}
    </div>`;
}

function syncStepMarkButton(step) {
  const button = $('.step-mark-btn', step);
  if (!button) return;
  const marked = $$('.mark-btn', step).some((item) => item.classList.contains('active'));
  button.classList.toggle('active', marked);
  button.textContent = marked ? '本步骤已标记' : '标记整步没讲清楚';
}

function setStepMarked(step, marked) {
  $$('.mark-btn', step).forEach((button) => {
    button.classList.toggle('active', marked);
    button.textContent = marked ? '已标记' : '标记没讲清楚';
    button.closest('.segment-card')?.classList.toggle('unclear', marked);
  });
  step.classList.toggle('unclear', marked);
  syncStepMarkButton(step);
}

function bindReview(session) {
  $('#save-review-btn').addEventListener('click', () => saveReview(false));
  $('#complete-review-btn').addEventListener('click', () => saveReview(true));

  $$('.segment-card').forEach((card) => {
    card.addEventListener('click', (event) => {
      if (event.target.closest('button, textarea, input')) return;
      const segment = collectReviewSegments()[Number(card.dataset.segmentIndex)];
      seekAudio(segment?.start_ms || 0);
    });
  });
  $$('.mark-btn').forEach((button) => {
    button.addEventListener('click', () => {
      const card = button.closest('.segment-card');
      const marked = button.classList.toggle('active');
      card.classList.toggle('unclear', marked);
      button.textContent = marked ? '已标记' : '标记没讲清楚';
      syncStepMarkButton(card.closest('.review-step'));
      scheduleReviewSave();
    });
  });
  $$('.step-mark-btn').forEach((button) => {
    button.addEventListener('click', () => {
      const step = button.closest('.review-step');
      setStepMarked(step, !button.classList.contains('active'));
      scheduleReviewSave();
    });
  });
  $$('.segment-text, .segment-note-input, #manual-review-text, #review-reflection, [data-check-key]').forEach((element) => {
    element.addEventListener('input', scheduleReviewSave);
    element.addEventListener('change', scheduleReviewSave);
  });
}

function seekAudio(milliseconds) {
  const audio = $('#review-audio');
  if (!audio) return;
  audio.currentTime = Math.max(0, Number(milliseconds || 0) / 1000);
  audio.play().catch(() => { /* browser may require another gesture */ });
}

function collectReviewSegments() {
  const cards = $$('.segment-card');
  if (cards.length) {
    return cards.map((card) => {
      const text = $('[data-field="text"]', card).value.trim();
      const startSeconds = $('.segment-time', card).textContent.split(':')
        .reduce((sum, part) => sum * 60 + Number(part), 0);
      return {
        text,
        start_ms: Math.round(startSeconds * 1000),
        end_ms: Math.round(startSeconds * 1000 + Math.max(1000, 20 * text.length)),
        unclear: $('.mark-btn', card).classList.contains('active'),
        note: $('[data-field="note"]', card).value.trim(),
      };
    }).filter((segment) => segment.text);
  }
  const manual = $('#manual-review-text');
  if (!manual) return reviewSegments(state.currentSession);
  const text = manual.value.trim();
  if (!text) return [];
  const duration = Number(state.currentSession?.speech_duration_seconds || 60) * 1000;
  const parts = sentenceChunks(text);
  return parts.map((part, index) => ({
    text: part,
    start_ms: Math.round(duration * index / parts.length),
    end_ms: Math.round(duration * (index + 1) / parts.length),
    unclear: false,
    note: '',
  }));
}

function collectReviewPayload(complete) {
  const checklist = {};
  $$('[data-check-key]').forEach((input) => { checklist[input.dataset.checkKey] = input.checked; });
  return {
    segments: collectReviewSegments(),
    checklist,
    reflection: $('#review-reflection')?.value || '',
    complete,
  };
}

function scheduleReviewSave() {
  if (!state.currentSession || state.currentSession.status !== 'review') return;
  clearTimeout(state.reviewSaveTimer);
  const status = $('#review-save-status');
  if (status) status.textContent = '等待自动保存…';
  state.reviewSaveTimer = setTimeout(() => saveReview(false), 700);
}

async function saveReview(complete) {
  if (!state.currentSession) return false;
  clearTimeout(state.reviewSaveTimer);
  const seq = ++state.reviewSaveSeq;
  const status = $('#review-save-status');
  if (status) status.textContent = complete ? '正在完成复盘…' : '正在保存…';
  try {
    const payload = collectReviewPayload(complete);
    const session = await api(`/api/sessions/${state.currentSession.id}/review`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (seq !== state.reviewSaveSeq && !complete) return false;
    state.currentSession = session;
    if (complete) {
      renderSession();
    } else if (status) {
      status.textContent = '已保存';
    }
    return true;
  } catch (error) {
    if (status) status.textContent = `保存失败：${error.message}`;
    toast(error.message);
    return false;
  }
}

function renderDoneHtml(session) {
  return `
    <div class="card practice-card">
      <div class="section-heading">
        <div><span class="eyebrow">本次练习完成</span><h2>${modeLabel(session.mode)}复盘</h2></div>
        <button id="again-btn" class="primary">再练一次</button>
      </div>
      ${reviewBodyHtml(session, true)}
    </div>`;
}

function bindDone() {
  $('#again-btn').addEventListener('click', resetToHome);
}


function resetToHome() {
  state.currentSession = null;
  state.setupMode = null;
  state.audioObjectUrl = '';
  state.audioBlob = null;
  state.recognitionSegments = [];
  state.captureActive = false;
  switchView('home');
}
/* ---------------- question bank ---------------- */
function populateCategorySelects() {
  const options = ['<option value="">全部</option>']
    .concat(state.categories.map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`))
    .join('');
  $('#bank-category-filter').innerHTML = options;
  $('#new-question-category').innerHTML = options;
}

function renderBank() {
  const enabledCount = state.questions.filter((question) => question.enabled).length;
  $('#bank-stats').innerHTML = `
    <span class="stat-pill"><b>${state.questions.length}</b> 道题目</span>
    <span class="stat-pill"><b>${enabledCount}</b> 道启用</span>
    <span class="stat-pill"><b>${state.categories.length}</b> 个分类</span>`;
  $('#bank-categories').innerHTML = state.categories.length
    ? state.categories.map((category) => `
        <span class="chip">${escapeHtml(category.name)}
          <button data-id="${category.id}" title="删除分类">×</button>
        </span>`).join('')
    : '<span class="hint">暂无分类</span>';
  $$('#bank-categories .chip button').forEach((button) => {
    button.addEventListener('click', () => deleteCategory(Number(button.dataset.id)));
  });
  renderQuestionList();
}

function renderQuestionList() {
  const filterValue = $('#bank-category-filter').value;
  const filter = filterValue ? Number(filterValue) : null;
  const query = ($('#bank-search-input')?.value || '').trim().toLowerCase();
  const items = state.questions.filter((question) => {
    const inCategory = filter === null || question.category_id === filter;
    const haystack = `${question.text} ${question.category_name || ''}`.toLowerCase();
    return inCategory && (!query || haystack.includes(query));
  });
  $('#question-list').innerHTML = items.length
    ? items.map((question) => `
        <article class="list-item">
          <div>
            <div>${escapeHtml(question.text)}</div>
            <div class="meta">${escapeHtml(question.category_name || '未分类')} · ${question.enabled ? '启用' : '已禁用'}</div>
          </div>
          <div class="row compact-row">
            <button data-action="toggle" data-id="${question.id}">${question.enabled ? '禁用' : '启用'}</button>
            <button data-action="edit" data-id="${question.id}">编辑</button>
            <button class="danger" data-action="delete" data-id="${question.id}">删除</button>
          </div>
        </article>`).join('')
    : '<p class="hint">暂无题目</p>';
  $$('#question-list button').forEach((button) => {
    const id = Number(button.dataset.id);
    const action = button.dataset.action;
    button.addEventListener('click', () => {
      if (action === 'toggle') toggleQuestion(id);
      if (action === 'edit') editQuestion(id);
      if (action === 'delete') deleteQuestion(id);
    });
  });
}

async function addCategory() {
  const input = $('#new-category-input');
  const name = input.value.trim();
  if (!name) return toast('请输入分类名称');
  try {
    await api('/api/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    input.value = '';
    await loadCategories();
    populateCategorySelects();
    renderBank();
  } catch (error) { toast(error.message); }
}

async function deleteCategory(id) {
  if (!confirm('删除分类后，该分类下的题目会变为未分类。确定删除？')) return;
  try {
    await api(`/api/categories/${id}`, { method: 'DELETE' });
    await Promise.all([loadCategories(), loadQuestions()]);
    populateCategorySelects();
    renderBank();
  } catch (error) { toast(error.message); }
}

async function addQuestion() {
  const text = $('#new-question-input').value.trim();
  const category = Number($('#new-question-category').value) || null;
  if (!text) return toast('请输入题目');
  try {
    await api('/api/questions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, category_id: category }),
    });
    $('#new-question-input').value = '';
    await loadQuestions();
    renderBank();
  } catch (error) { toast(error.message); }
}

async function toggleQuestion(id) {
  const question = state.questions.find((item) => item.id === id);
  if (!question) return;
  try {
    await api(`/api/questions/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !question.enabled }),
    });
    await loadQuestions();
    renderBank();
  } catch (error) { toast(error.message); }
}

async function editQuestion(id) {
  const question = state.questions.find((item) => item.id === id);
  if (!question) return;
  const text = prompt('编辑题目内容', question.text);
  if (text === null) return;
  if (!text.trim()) return toast('题目不能为空');
  try {
    await api(`/api/questions/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.trim() }),
    });
    await loadQuestions();
    renderBank();
  } catch (error) { toast(error.message); }
}

async function deleteQuestion(id) {
  if (!confirm('确定删除这道题目？')) return;
  try {
    await api(`/api/questions/${id}`, { method: 'DELETE' });
    await loadQuestions();
    renderBank();
  } catch (error) { toast(error.message); }
}
/* ---------------- knowledge library ---------------- */
function populateLibrarySelects() {
  const options = state.knowledgeCategories
    .map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`)
    .join('');
  const filter = $('#library-category-filter');
  const previous = filter.value;
  filter.innerHTML = '<option value="">全部分类</option>' + options;
  filter.value = previous;
  $('#library-category').innerHTML = '<option value="">未分类</option>' + options;
}

function renderLibrary() {
  $('#library-categories').innerHTML = state.knowledgeCategories.length
    ? state.knowledgeCategories.map((category) => `
        <span class="chip">${escapeHtml(category.name)} <small>${category.item_count || 0}</small>
          <button data-id="${category.id}" title="删除分类">×</button>
        </span>`).join('')
    : '<span class="hint">暂无资料分类</span>';
  $$('#library-categories .chip button').forEach((button) => {
    button.addEventListener('click', () => deleteLibraryCategory(Number(button.dataset.id)));
  });
  renderLibraryList();
}

function renderLibraryList() {
  const filter = Number($('#library-category-filter').value) || null;
  const items = state.knowledgeItems.filter((item) => filter === null || item.category_id === filter);
  $('#library-list').innerHTML = items.length
    ? items.map((item) => `
        <article class="list-item library-item" data-id="${item.id}">
          <div>
            <div class="item-title">${escapeHtml(item.title)}</div>
            <div class="meta">${escapeHtml(item.category_name || '未分类')} · ${item.is_seed ? '预置资料' : '个人资料'}</div>
            <p class="item-summary">${escapeHtml(item.summary || item.content.slice(0, 80))}</p>
          </div>
          <div class="row compact-row">
            ${item.source_url ? `<button data-action="open" data-id="${item.id}">打开来源</button>` : ''}
            <button data-action="edit" data-id="${item.id}">查看/编辑</button>
            <button class="danger" data-action="delete" data-id="${item.id}">删除</button>
          </div>
        </article>`).join('')
    : '<p class="hint">这个分类还没有资料</p>';
  $$('#library-list button').forEach((button) => {
    const id = Number(button.dataset.id);
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      if (button.dataset.action === 'delete') deleteLibraryItem(id);
      if (button.dataset.action === 'edit') openLibraryEditor(id);
      if (button.dataset.action === 'open') openLibrarySource(id);
    });
  });
  $$('.library-item').forEach((item) => {
    item.addEventListener('click', () => openLibraryEditor(Number(item.dataset.id)));
  });
}

function openLibrarySource(id) {
  const item = state.knowledgeItems.find((entry) => entry.id === id);
  if (!item?.source_url) return toast('这份资料没有来源链接');
  openExternalUrl(item.source_url);
}

function openLibraryEditor(id = null) {
  const item = id ? state.knowledgeItems.find((entry) => entry.id === id) : null;
  state.editingLibraryId = id;
  $('#library-editor').classList.remove('hidden');
  $('#library-editor-title').textContent = item ? '查看/编辑资料' : '新增资料';
  $('#library-title').value = item?.title || '';
  $('#library-category').value = item?.category_id || '';
  $('#library-summary').value = item?.summary || '';
  $('#library-content').value = item?.content || '';
  $('#library-source-url').value = item?.source_url || '';
  $('#library-editor-status').textContent = '';
  $('#library-editor').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function closeLibraryEditor() {
  state.editingLibraryId = null;
  $('#library-editor').classList.add('hidden');
}

async function saveLibraryItem() {
  const title = $('#library-title').value.trim();
  const summary = $('#library-summary').value.trim();
  const content = $('#library-content').value.trim();
  const sourceUrl = $('#library-source-url').value.trim();
  const categoryId = Number($('#library-category').value) || null;
  const status = $('#library-editor-status');
  if (!title) return toast('请输入资料标题');
  if (!summary && !content) return toast('请输入摘要或正文');
  const payload = { title, summary, content, source_url: sourceUrl, category_id: categoryId };
  try {
    if (state.editingLibraryId) {
      await api(`/api/library/items/${state.editingLibraryId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      await api('/api/library/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }
    status.textContent = '已保存';
    await loadLibraryData();
    populateLibrarySelects();
    renderLibrary();
    closeLibraryEditor();
    toast('资料已保存');
  } catch (error) {
    status.textContent = error.message;
  }
}

async function addLibraryCategory() {
  const input = $('#new-library-category-input');
  const name = input.value.trim();
  if (!name) return toast('请输入资料分类');
  try {
    await api('/api/library/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    input.value = '';
    await loadLibraryData();
    populateLibrarySelects();
    renderLibrary();
  } catch (error) { toast(error.message); }
}

async function deleteLibraryCategory(id) {
  if (!confirm('删除分类后，资料会变为未分类。确定删除？')) return;
  try {
    await api(`/api/library/categories/${id}`, { method: 'DELETE' });
    await loadLibraryData();
    populateLibrarySelects();
    renderLibrary();
  } catch (error) { toast(error.message); }
}

async function deleteLibraryItem(id) {
  if (!confirm('确定删除这份资料？已有练习会保留当时的资料快照。')) return;
  try {
    await api(`/api/library/items/${id}`, { method: 'DELETE' });
    await loadLibraryData();
    populateLibrarySelects();
    renderLibrary();
  } catch (error) { toast(error.message); }
}
/* ---------------- history ---------------- */
async function renderHistory() {
  const box = $('#history-list');
  box.innerHTML = '<p class="hint">加载中…</p>';
  try {
    const data = await api('/api/sessions?limit=100');
    const items = data.items || [];
    box.innerHTML = items.length
      ? items.map((session) => `
          <article class="list-item history-item" data-id="${session.id}">
            <div>
              <div class="item-title">${escapeHtml(topicText(session))}</div>
              <div class="meta">${modeLabel(session.mode)} · ${escapeHtml(formatDate(session.created_at))} · ${statusText(session.status)}</div>
            </div>
            <div class="history-actions">
              <span class="meta">${session.unclear_count ? `${session.unclear_count} 处标记` : (session.has_audio ? '有录音' : '无录音')}</span>
              <button class="danger history-delete-btn" data-delete-id="${session.id}">删除</button>
            </div>
          </article>`).join('')
      : '<p class="hint">还没有练习记录</p>';
    $$('.history-item').forEach((item) => item.addEventListener('click', () => showHistoryDetail(Number(item.dataset.id))));
    $$('.history-delete-btn').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        deleteHistorySession(Number(button.dataset.deleteId));
      });
    });
  } catch (error) {
    box.innerHTML = `<p class="hint warning-text">${escapeHtml(error.message)}</p>`;
  }
}

async function deleteHistorySession(id) {
  if (!confirm('确定删除这条练习记录？录音和复盘内容也会一起删除。')) return;
  try {
    await api(`/api/sessions/${id}`, { method: 'DELETE' });
    if (state.currentSession?.id === id) {
      state.currentSession = null;
      state.captureActive = false;
      if (state.audioObjectUrl) URL.revokeObjectURL(state.audioObjectUrl);
      state.audioObjectUrl = '';
      state.audioBlob = null;
    }
    $('#history-detail').classList.add('hidden');
    await renderHistory();
    toast('练习记录已删除');
  } catch (error) {
    toast(error.message);
  }
}

async function showHistoryDetail(id) {
  try {
    const session = await api(`/api/sessions/${id}`);
    const research = session.mode === 'research'
      ? `
        <section class="history-section"><h3>研究资料</h3><div class="card pre-wrap">${escapeHtml(session.material_snapshot || '无')}</div></section>
        <div class="history-two-column">
          <section><h3>我的笔记</h3><div class="card pre-wrap">${escapeHtml(session.notes || '无')}</div></section>
          <section><h3>我的提纲</h3><div class="card pre-wrap">${escapeHtml(session.outline || '无')}</div></section>
        </div>`
      : '';
    const cues = session.speech_cues
      ? `<section class="history-section"><h3>表达提示词</h3><div class="card pre-wrap">${escapeHtml(session.speech_cues)}</div></section>`
      : '';
    $('#history-detail').innerHTML = `
      <div class="section-heading">
        <div><span class="eyebrow">${modeLabel(session.mode)}</span><h2>练习详情</h2></div>
        <button id="close-history-detail-btn">收起</button>
      </div>
      ${cues}
      ${research}
      ${reviewBodyHtml(session, true)}
    `;
    $('#history-detail').classList.remove('hidden');
    $('#close-history-detail-btn').addEventListener('click', () => $('#history-detail').classList.add('hidden'));
    $('#history-detail').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) { toast(error.message); }
}

document.addEventListener('DOMContentLoaded', init);

