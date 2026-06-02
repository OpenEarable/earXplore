/**
 * studyLogger.mjs — Opt-in behavior logger for the earXplore user study.
 *
 * Flow:
 *   1. Participant clicks "Start Recording Usage".
 *   2. A small modal asks for their participant code (e.g. "P01").
 *   3. All interactions are buffered in sessionStorage (survives same-tab
 *      page navigations between the four views without any cookies).
 *   4. Participant clicks "End Recording Usage" → JSON log is downloaded
 *      automatically and they e-mail it to the researcher.
 *
 * No server communication and no cookies are used.
 *
 * ════════════════════════════════════════════════════════════════════════════
 * EVENT TYPE REFERENCE
 * ════════════════════════════════════════════════════════════════════════════
 *
 * Every event object in the log always contains these fields:
 *   type       {string}  – event type identifier (see catalogue below)
 *   view       {string}  – which of the four views the event occurred on:
 *                            "tableView"      → Tabular Overview
 *                            "chartView"      → Distribution Charts
 *                            "similarityView" → Study Similarity
 *                            "timeView"       → Study Timeline
 *   ts         {number}  – Unix timestamp in milliseconds (UTC)
 *   elapsed_ms {number}  – milliseconds since the recording session started
 *
 * Additional fields specific to each event type are listed below.
 *
 * ── Session lifecycle ────────────────────────────────────────────────────────
 *
 *   session_start
 *     Recording began. The participant clicked "Start Recording Usage" and
 *     confirmed their participant code.
 *     Extra fields: pid {string} – the participant code entered.
 *
 *   session_end
 *     Recording was stopped manually by the participant clicking
 *     "End Recording Usage". The log file download is triggered immediately
 *     after this event is written. No extra fields.
 *
 * ── Page navigation ──────────────────────────────────────────────────────────
 *
 *   page_load
 *     The current view's page finished loading, or the recording session was
 *     resumed after navigating between views. Emitted once per view visit.
 *     No extra fields (the "view" field identifies which view was loaded).
 *
 *   page_unload
 *     The user is leaving the current view (navigating to another view or
 *     closing/refreshing the tab). Always paired with a preceding page_load.
 *     Extra fields:
 *       duration_ms {number} – time spent on this view in milliseconds.
 *
 *   navigate_to_view
 *     The user clicked one of the four view links in the top navigation bar.
 *     Appears immediately before the corresponding page_unload.
 *     Extra fields:
 *       el.section {string} – the destination view (e.g. "chartView").
 *       el.text    {string} – visible label of the nav item clicked.
 *
 *   window_hidden
 *     The browser window or tab became hidden — e.g. the user switched to
 *     another application, another browser tab, or locked the screen.
 *     NOT emitted during same-tab view navigations (those produce page_unload).
 *     No extra fields.
 *
 *   window_visible
 *     The browser window or tab became visible again after being hidden.
 *     Always paired with a preceding window_hidden.
 *     No extra fields.
 *
 * ── Header / top-bar buttons ─────────────────────────────────────────────────
 *
 *   header_button_clicked
 *     The user clicked a button or link in the top header bar that is NOT
 *     one of the four main view nav links. Includes "Add Study", the
 *     "EarXplore Paper" arXiv link, and similar header actions.
 *     Extra fields:
 *       el.text {string} – visible button label.
 *       el.href {string} – target URL if the button contains a link.
 *
 * ── Sidebar filter interactions ──────────────────────────────────────────────
 *
 *   filter_checkbox_toggled
 *     A filter checkbox in the sidebar was checked or unchecked.
 *     Extra fields:
 *       col     {string}  – data column the filter belongs to
 *                           (e.g. "Sensing_PANEL_Type", "General_PANEL_Year").
 *       value   {string}  – option value toggled (e.g. "IMU", "Yes", "2023").
 *       checked {boolean} – true = checkbox is now checked (filter active).
 *
 *   range_filter_moved
 *     A range/slider filter in the sidebar was moved to a new position.
 *     Extra fields:
 *       col    {string}   – data column this slider controls.
 *       values {string[]} – new [lowerBound, upperBound] values as strings.
 *
 *   exclusive_filter_toggled
 *     The "Exclusive Filtering ON/OFF" button for a filter category was clicked,
 *     switching the filter mode between OR (show any) and AND (show all).
 *     Extra fields: col {string} – data column the button belongs to.
 *
 *   sidebar_interaction
 *     A sidebar button was clicked (other than filter checkboxes, which are
 *     captured by filter_checkbox_toggled above).
 *     Extra fields:
 *       subtype {string} – one of:
 *         "panel_select_all"      – "Select All" within a specific filter panel header.
 *         "panel_deselect_all"    – "Deselect All" within a specific filter panel header.
 *         "category_select_all"   – "Select All" for a specific filter category column.
 *         "category_deselect_all" – "Deselect All" for a specific filter category column.
 *         "global_select_all"     – "Select All" button for the entire sidebar.
 *         "global_deselect_all"   – "Deselect All" button for the entire sidebar.
 *         "panel_expand_collapse" – A filter panel section was shown or hidden.
 *         "sidebar_closed"        – The sidebar was closed (visible on small screens).
 *         "token_clear_all"       – "Clear Selection" in a token-search filter block.
 *         "general"               – Other sidebar click not covered by the above.
 *       panel {string} – filter panel name (present for panel-level subtypes).
 *       col   {string} – data column (present for category_select/deselect and token_clear_all).
 *       el    {object} – element description (always present).
 *
 * ── Token-search filter (Authors / Keywords) ─────────────────────────────────
 *
 *   token_filter_added
 *     The user added a token (e.g. an author name or a keyword) to the active
 *     filter by selecting it from the suggestion dropdown.
 *     Extra fields:
 *       col   {string} – data column (e.g. "Authors", "Main Author", "Keywords").
 *       value {string} – the token text that was added.
 *
 *   token_filter_removed
 *     The user removed a previously active token from the filter (by clicking
 *     the × badge, or via "Clear Selection" — the latter also fires
 *     a sidebar_interaction with subtype "token_clear_all").
 *     Extra fields:
 *       col   {string} – data column.
 *       value {string} – the token text that was removed.
 *
 * ── Table view ───────────────────────────────────────────────────────────────
 *
 *   column_sort_clicked
 *     The user clicked a column header in the Tabular Overview to sort by that
 *     column. Clicking the same header again reverses the sort order.
 *     Extra fields: el.text {string} – the column label that was clicked.
 *
 *   column_visibility_toggled
 *     A column show/hide checkbox in the column-filter panel was changed,
 *     showing or hiding that column in the table.
 *     Extra fields:
 *       col     {string}  – the column ID that was toggled.
 *       checked {boolean} – true = column is now visible.
 *
 * ── Dropdowns and radio buttons ──────────────────────────────────────────────
 *
 *   dropdown_changed
 *     A <select> dropdown changed its selected value (e.g. the "Color nodes by"
 *     category selector in the Similarity or Timeline views).
 *     Extra fields:
 *       id    {string} – HTML id of the <select> element.
 *       value {string} – newly selected option value.
 *
 *   radio_changed
 *     A radio button changed state (e.g. switching between "Abstract similarity"
 *     and "Document similarity" in the Similarity view, or changing the citation
 *     direction mode in the Timeline view).
 *     Extra fields:
 *       name  {string} – radio group name attribute.
 *       value {string} – newly selected option value.
 *       id    {string} – HTML id of the selected radio element.
 *
 * ── Study detail modal ────────────────────────────────────────────────────────
 *
 *   study_detail_opened
 *     The study information modal (showing full details of a paper: authors,
 *     abstract, all attribute values) was opened.
 *     No extra fields beyond the standard "view".
 *
 *   study_detail_closed
 *     The study information modal was closed (via Close button, Escape key,
 *     or clicking the backdrop).
 *     No extra fields.
 *
 *   paper_link_opened
 *     The "Open Paper" link inside the study detail modal was clicked —
 *     the participant followed the URL to the paper's external source
 *     (opens in a new browser tab).
 *     Extra fields:
 *       el.href {string} – the full URL of the paper.
 *
 *   find_similar_clicked
 *     The "Find Similar Studies" button inside the study detail modal was
 *     clicked, navigating the user to the Study Similarity view for that paper.
 *     No extra fields.
 *
 *   modal_opened
 *     A secondary modal was opened that is NOT the study detail modal —
 *     for example the paper-connections panel in the Similarity or Timeline view.
 *     Extra fields: id {string} – HTML id of the modal element.
 *
 *   modal_closed
 *     A secondary modal was closed.
 *     Extra fields: id {string} – HTML id of the modal element.
 *
 *   modal_button_clicked
 *     A button or link inside a modal was clicked, not covered by
 *     paper_link_opened or find_similar_clicked above.
 *     Extra fields: el {object} – element description (tag, id, text, href).
 *
 * ── EarBot chatbot ────────────────────────────────────────────────────────────
 *
 *   chatbot_opened
 *     The EarBot assistant panel was opened by clicking the chat button.
 *
 *   chatbot_closed
 *     The EarBot panel was closed (via close button or backdrop overlay).
 *
 *   chatbot_reset
 *     The EarBot conversation was cleared/reset by clicking the refresh icon.
 *
 *   chatbot_message_sent
 *     The user submitted a message to EarBot.
 *     Extra fields:
 *       message_length {number} – character count of the submitted message.
 *                                  The message text itself is NOT recorded.
 *
 * ── Fallback ─────────────────────────────────────────────────────────────────
 * *   csv_download_clicked
 *     The "Download Selection as .csv" or "Download Full Dataset as .csv" button
 *     was clicked, triggering a file download.
 *     Extra fields: id {string} – HTML id of the button ("downloadFilteredCsv" or
 *                                  "downloadFullCsv").
 * *   general_click
 *     A click that did not match any of the more specific categories above.
 *     Extra fields: el {object} – element description (tag, id, text, href).
 *
 * ════════════════════════════════════════════════════════════════════════════
 */

// ── sessionStorage keys ────────────────────────────────────────────────────────
const SS_RECORDING = 'earXplore_recording';
const SS_PID       = 'earXplore_pid';
const SS_START     = 'earXplore_start';
const SS_BUFFER    = 'earXplore_buf';

// ── Module-level state ─────────────────────────────────────────────────────────
let _recording          = false;
let _pid                = null;    // participant code
let _startTs            = 0;       // epoch ms when recording began
let _buffer             = [];      // in-memory event buffer
let _viewTs             = 0;       // epoch ms when the current view was entered
let _unloading          = false;   // true between a nav-link click and page teardown
let _listenerController = null;    // AbortController for current session's listeners
let _sliderRetryId      = null;    // setInterval id for slider attachment retry
let _tokenState         = new Map(); // col → Set<string> of active token values

// ── Utilities ─────────────────────────────────────────────────────────────────
function _now()     { return Date.now(); }
function _elapsed() { return _recording ? _now() - _startTs : 0; }

function _currentView() {
  return document.querySelector('nav[data-current-view]')?.dataset.currentView ?? 'unknown';
}

/**
 * Build a privacy-safe descriptor for a DOM element.
 * Captures only structural info (tag, id, data-*, short text, href).
 * Never captures the content of input / textarea / select nodes.
 */
function _describeEl(el) {
  if (!el) return {};
  const out = { tag: (el.tagName ?? 'UNKNOWN').toLowerCase() };
  if (el.id)               out.id      = el.id;
  if (el.dataset?.col)     out.col     = el.dataset.col;
  if (el.dataset?.section) out.section = el.dataset.section;
  if (el.dataset?.panel)   out.panel   = el.dataset.panel;
  if (el.tagName === 'A' || el.tagName === 'a') out.href = el.getAttribute('href');
  if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) {
    const text = (el.innerText ?? '').replace(/\s+/g, ' ').trim().slice(0, 100);
    if (text) out.text = text;
  }
  return out;
}

function _generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return 'anon-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 9);
}

// ── Buffer persistence ─────────────────────────────────────────────────────────
function _saveBuffer() {
  try {
    sessionStorage.setItem(SS_BUFFER, JSON.stringify(_buffer));
  } catch {
    _buffer.splice(0, Math.ceil(_buffer.length / 4));
    try { sessionStorage.setItem(SS_BUFFER, JSON.stringify(_buffer)); } catch { /* ignore */ }
  }
}

// ── Core event logging ─────────────────────────────────────────────────────────
function _log(type, payload = {}) {
  if (!_recording) return;
  _buffer.push({ type, view: _currentView(), ts: _now(), elapsed_ms: _elapsed(), ...payload });
  _saveBuffer();
}

// ── JSON download ──────────────────────────────────────────────────────────────
function _downloadLog() {
  const log = {
    participant_id: _pid,
    recorded_from:  new Date(_startTs).toISOString(),
    recorded_to:    new Date().toISOString(),
    total_events:   _buffer.length,
    events:         _buffer,
  };
  const blob = new Blob([JSON.stringify(log, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement('a'), {
    href: url, download: `earXplore-study-log-${_pid}.json`,
  });
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Click classification ───────────────────────────────────────────────────────
function _classifyAndLogClick(e) {
  const raw = e.composedPath?.()[0] ?? e.target;
  if (!raw) return;

  // Skip the logger UI itself
  if (raw.closest?.('#study-log-btn') || raw.closest?.('#study-logger-modal')) return;

  // noUiSlider internal elements — the 'change' listener already captures range_filter_moved.
  // Also skip .slider-container (the wrapper div that receives click events when a drag releases
  // on the surrounding area rather than on the handle itself).
  if (raw.closest?.('.noUi-target') || raw.closest?.('.slider-container')) return;

  // Token-search areas — token add/remove is fully captured by MutationObserver.
  // The suggestion list uses mousedown+preventDefault, causing a synthetic click to land
  // on .token-search-group (the outer wrapper div) or .token-selected-container after the
  // suggestion hides; guard all three token-related elements.
  if (raw.closest?.('.token-search-group') ||
      raw.closest?.('.token-selected-container') ||
      raw.closest?.('.token-suggestions')) return;

  // INPUT / TEXTAREA / SELECT state changes are captured by the 'change' listener.
  // Labels for checkboxes/radios: skip here too — let 'change' handle the action.
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(raw.tagName)) return;
  if (raw.tagName === 'LABEL') {
    const forId = raw.getAttribute('for');
    if (forId) {
      const target = document.getElementById(forId);
      if (target?.type === 'checkbox' || target?.type === 'radio') return;
    }
    // Also skip sidebar / toggle-menu labels without explicit `for` attributes
    // (Bootstrap form-check labels implicitly label their sibling input)
    if (raw.closest('#sidebar') || raw.closest('#toggle-menu-container')) return;
  }

  const el   = raw.closest('button, a, th, [data-section], .navbar-item') ?? raw;
  if (!el) return;
  // Skip noise: pointer-capture releases that land on body or html
  if (['BODY', 'HTML'].includes(el.tagName)) return;
  const desc = _describeEl(el);

  // Skip programmatic blob/data URL clicks (e.g. temporary download anchors created by JS)
  if (el.tagName === 'A' && el.getAttribute?.('href')?.match(/^(blob:|data:)/)) return;

  // ── Specific high-value actions ────────────────────────────────────────────
  // "Open Paper" link / button inside the study detail modal
  if (el.id === 'study-link' || el.closest?.('#study-link-btn')) {
    const anchor = el.tagName === 'A' ? el : (el.querySelector('a') ?? el);
    _log('paper_link_opened', { el: _describeEl(anchor) });
    return;
  }
  // "Find Similar Studies" button inside the study detail modal
  if (el.id === 'similar-studies-btn' || el.closest?.('#similar-studies-btn')) {
    _log('find_similar_clicked', {});
    return;
  }
  // Chatbot open / close / reset
  if (el.id === 'chatbot-btn'   || el.closest?.('#chatbot-btn'))   { _log('chatbot_opened', {}); return; }
  if (el.id === 'chatbot-close' || el.closest?.('#chatbot-close')) { _log('chatbot_closed', {}); return; }
  if (el.id === 'chatbot-reset' || el.closest?.('#chatbot-reset')) { _log('chatbot_reset',  {}); return; }
  // All other clicks inside the chatbot panel (e.g. Send button) are already
  // covered by the form 'submit' listener → chatbot_message_sent. Skip here.
  if (raw.closest?.('#chatbot-panel')) return;

  // ── Sidebar interactions ───────────────────────────────────────────────────
  if (el.closest('#sidebar') || raw.closest('#sidebar')) {
    let subtype = 'general';
    let extra   = {};
    if      (el.id === 'select-all-sidebar-button')   subtype = 'global_select_all';
    else if (el.id === 'deselect-all-sidebar-button') subtype = 'global_deselect_all';
    else if (el.id === 'close-sidebar')               subtype = 'sidebar_closed';
    else if (el.classList?.contains('select-all-panel')   || el.closest?.('.select-all-panel')) {
      const b = el.closest('.select-all-panel') ?? el;
      subtype = 'panel_select_all';
      extra.panel = b.dataset.panel;
    }
    else if (el.classList?.contains('deselect-all-panel') || el.closest?.('.deselect-all-panel')) {
      const b = el.closest('.deselect-all-panel') ?? el;
      subtype = 'panel_deselect_all';
      extra.panel = b.dataset.panel;
    }
    // Category-level select/deselect (class .select-all / .deselect-all, data-col attribute)
    else if (el.classList?.contains('select-all')   || el.closest?.('.select-all')) {
      const b = el.closest('.select-all') ?? el;
      subtype = 'category_select_all';
      extra.col = b.dataset.col;
    }
    else if (el.classList?.contains('deselect-all') || el.closest?.('.deselect-all')) {
      const b = el.closest('.deselect-all') ?? el;
      subtype = 'category_deselect_all';
      extra.col = b.dataset.col;
    }
    else if (el.classList?.contains('exclusive-filter')   || el.closest?.('.exclusive-filter')) {
      const b = el.closest('.exclusive-filter') ?? el;
      _log('exclusive_filter_toggled', { col: b.dataset.col ?? null });
      return;
    }
    else if (el.classList?.contains('toggle-visibility-button') || el.closest?.('.toggle-visibility-button')) {
      const b = el.closest('.toggle-visibility-button') ?? el;
      subtype = 'panel_expand_collapse';
      extra.panel = b.dataset.panel;
    }
    else if (el.classList?.contains('token-deselect-all') || el.closest?.('.token-deselect-all')) {
      const b = el.closest('.token-deselect-all') ?? el;
      subtype = 'token_clear_all';
      extra.col = b.dataset.col;
    }
    _log('sidebar_interaction', { subtype, ...extra, el: desc });
    return;
  }

  // ── Navigation bar view links ──────────────────────────────────────────────
  if (el.closest('.link-section')) {
    _unloading = true; // suppress the spurious window_hidden fired during navigation
    _log('navigate_to_view', { el: desc });
    return;
  }

  // ── Header buttons (Add Study, EarXplore Paper, …) ────────────────────────
  if (el.closest('#nav-r')) {
    _log('header_button_clicked', { el: desc });
    return;
  }

  // ── Table column header click (sort) ──────────────────────────────────────
  if (el.tagName === 'TH') {
    _log('column_sort_clicked', { el: desc });
    return;
  }

  // ── Column visibility toggle panel ────────────────────────────────────────
  // Download buttons live inside #toggle-menu-container — handle them before the generic branch
  if (el.id === 'downloadFilteredCsv' || el.id === 'downloadFullCsv') {
    _log('csv_download_clicked', { id: el.id });
    return;
  }
  // Button clicks (Select All, Deselect All, Reset) — checkbox changes are
  // captured separately by the 'change' event handler.
  if (el.closest('#toggle-menu-container')) {
    _log('column_visibility_toggled', { el: desc });
    return;
  }

  // ── Buttons inside modals (excluding chatbot and logger modal) ─────────────
  if (el.closest?.('.modal:not(#study-logger-modal):not(#chatbot-panel)')) {
    _log('modal_button_clicked', { el: desc });
    return;
  }

  // ── Fallback ───────────────────────────────────────────────────────────────
  _log('general_click', { el: desc });
}

// ── Slider attachment (retried until all sliders are ready) ───────────────────
function _bindSliders() {
  document.querySelectorAll('.range-slider').forEach(el => {
    if (el._studyLoggerBound || !el.noUiSlider) return;
    el._studyLoggerBound = true;
    el.noUiSlider.on('change', (values) => {
      _log('range_filter_moved', { col: el.dataset.col ?? null, values });
    });
  });
}

function _startSliderRetry() {
  if (_sliderRetryId !== null) return;
  let attempts = 0;
  _sliderRetryId = setInterval(() => {
    _bindSliders();
    if (++attempts >= 20) { // give up after 10 s
      clearInterval(_sliderRetryId);
      _sliderRetryId = null;
    }
  }, 500);
}

// ── Token-search tracking via MutationObserver ────────────────────────────────
// tokenSearch.mjs rebuilds the badge container completely on every change, so we
// compare the new rendered badge set against the previously known state to infer
// which token was added or removed.
function _attachTokenObservers() {
  document.querySelectorAll('.token-selected-container').forEach(container => {
    if (container._studyLoggerObserver) return;
    const col = container.dataset.col ?? null;
    // Seed initial state from already-rendered badges (session restored from storage)
    const initial = new Set(
      Array.from(container.querySelectorAll('.token-badge-text'))
           .map(el => el.textContent.trim()).filter(Boolean)
    );
    _tokenState.set(col, initial);

    const obs = new MutationObserver(() => {
      const current = new Set(
        Array.from(container.querySelectorAll('.token-badge-text'))
             .map(el => el.textContent.trim()).filter(Boolean)
      );
      const prev = _tokenState.get(col) ?? new Set();
      for (const v of current) { if (!prev.has(v)) _log('token_filter_added',   { col, value: v }); }
      for (const v of prev)    { if (!current.has(v)) _log('token_filter_removed', { col, value: v }); }
      _tokenState.set(col, current);
    });
    obs.observe(container, { childList: true, subtree: true });
    container._studyLoggerObserver = obs;
  });
}

// ── Listener attachment / detachment ──────────────────────────────────────────
function _attachListeners() {
  if (_listenerController) return; // already attached for this session
  _unloading = false;
  _listenerController = new AbortController();
  const sig = _listenerController.signal;

  // Record entry time and log page_load
  _viewTs = _now();
  _log('page_load', {});

  // Log view duration and set _unloading before the page tears down
  window.addEventListener('beforeunload', () => {
    _unloading = true;
    _log('page_unload', { duration_ms: _now() - _viewTs });
    _saveBuffer();
  }, { signal: sig });

  // Tab visibility — suppressed during same-tab view navigation
  document.addEventListener('visibilitychange', () => {
    if (_unloading) return;
    _log(document.hidden ? 'window_hidden' : 'window_visible', {});
  }, { signal: sig });

  // Click delegation (capture phase so we see all clicks before stopPropagation)
  document.addEventListener('click', _classifyAndLogClick, { capture: true, signal: sig });

  // Checkbox / radio / select state changes
  document.addEventListener('change', (e) => {
    const el = e.target;
    if (!el) return;
    if (el.closest?.('#study-log-btn') || el.closest?.('#study-logger-modal')) return;

    if (el.type === 'checkbox') {
      if (el.classList.contains('column-filter')) {
        // Column show/hide toggle in the column-filter panel
        _log('column_visibility_toggled', { col: el.id, checked: el.checked });
      } else {
        // Filter checkbox in the sidebar (value filters, performance N/A, device model, etc.)
        const colEl = el.closest('[data-col]');
        _log('filter_checkbox_toggled', {
          col:     colEl?.dataset.col ?? el.id ?? null,
          value:   el.value,
          checked: el.checked,
        });
      }
    } else if (el.type === 'radio') {
      _log('radio_changed', { name: el.name, value: el.value, id: el.id });
    } else if (el.tagName === 'SELECT') {
      _log('dropdown_changed', { id: el.id, value: el.value });
    }
  }, { signal: sig });

  // Bootstrap modal lifecycle events
  document.addEventListener('show.bs.modal', (e) => {
    if (e.target.id === 'study-logger-modal') return;
    if (e.target.id === 'study-info-modal')   { _log('study_detail_opened', {}); return; }
    _log('modal_opened', { id: e.target.id });
  }, { signal: sig });

  document.addEventListener('hidden.bs.modal', (e) => {
    if (e.target.id === 'study-logger-modal') return;
    if (e.target.id === 'study-info-modal')   { _log('study_detail_closed', {}); return; }
    _log('modal_closed', { id: e.target.id });
  }, { signal: sig });

  // Chatbot message submit — capture phase so we read the value before any
  // other handler (e.g. base.mjs jQuery) might clear the input field.
  document.getElementById('chatbot-form')?.addEventListener('submit', () => {
    const len = (document.getElementById('chatbot-input')?.value ?? '').trim().length;
    _log('chatbot_message_sent', { message_length: len });
  }, { capture: true, signal: sig });

  // Sliders and token search are deferred — wait for base.mjs $(document).ready() to finish
  _startSliderRetry();
  setTimeout(_attachTokenObservers, 600);
}

function _detachListeners() {
  _listenerController?.abort();
  _listenerController = null;

  // Disconnect token observers and clear their flags
  document.querySelectorAll('.token-selected-container').forEach(container => {
    container._studyLoggerObserver?.disconnect();
    delete container._studyLoggerObserver;
  });
  _tokenState.clear();

  // Clear slider flags so they can be re-bound on the next session
  document.querySelectorAll('.range-slider').forEach(el => delete el._studyLoggerBound);

  if (_sliderRetryId !== null) {
    clearInterval(_sliderRetryId);
    _sliderRetryId = null;
  }
}

// ── Button state ───────────────────────────────────────────────────────────────
function _updateBtn(recording) {
  const btn = document.getElementById('study-log-btn');
  if (!btn) return;
  btn.dataset.recording = recording ? '1' : '0';
  const dot   = btn.querySelector('.sl-dot');
  const label = btn.querySelector('.sl-label');
  if (dot)   dot.style.display = recording ? 'inline-block' : 'none';
  if (label) label.textContent = recording ? 'End Recording Usage' : 'Start Recording Usage';
}

// ── Participant-code modal ─────────────────────────────────────────────────────
function _showCodeModal() {
  const modal = document.getElementById('study-logger-modal');
  if (!modal) return;
  const input = document.getElementById('sl-code-input');
  if (input) input.value = '';
  new bootstrap.Modal(modal).show();
  modal.addEventListener('shown.bs.modal', () => input?.focus(), { once: true });
}

// ── Public API ─────────────────────────────────────────────────────────────────
export function isRecording() { return _recording; }

export function startRecording(code) {
  if (_recording) return;
  _pid     = (typeof code === 'string' && code.trim()) ? code.trim() : _generateId();
  _startTs = _now();
  _buffer  = [];
  sessionStorage.setItem(SS_PID,       _pid);
  sessionStorage.setItem(SS_START,     String(_startTs));
  sessionStorage.setItem(SS_RECORDING, '1');
  _saveBuffer();
  _recording = true;
  _log('session_start', { pid: _pid });
  _attachListeners();
  _updateBtn(true);
}

export function stopRecording() {
  if (!_recording) return;
  _log('session_end', {});
  _recording = false;
  _downloadLog();  // download BEFORE clearing state so all events are in the file
  _detachListeners();
  sessionStorage.removeItem(SS_PID);
  sessionStorage.removeItem(SS_START);
  sessionStorage.removeItem(SS_BUFFER);
  sessionStorage.removeItem(SS_RECORDING);
  _buffer  = [];
  _pid     = null;
  _startTs = 0;
  _unloading = false;
  _updateBtn(false);
}

export function init() {
  // Restore an in-progress session after same-tab view navigation
  if (sessionStorage.getItem(SS_RECORDING) === '1') {
    const savedPid   = sessionStorage.getItem(SS_PID);
    const savedStart = parseInt(sessionStorage.getItem(SS_START) ?? '0', 10);
    if (savedPid && savedStart) {
      _pid     = savedPid;
      _startTs = savedStart;
      try   { _buffer = JSON.parse(sessionStorage.getItem(SS_BUFFER) ?? '[]'); }
      catch { _buffer = []; }
      _recording = true;
      _attachListeners();
      _updateBtn(true);
    }
  }

  // "Start / End Recording Usage" button
  document.getElementById('study-log-btn')?.addEventListener('click', () => {
    if (_recording) { stopRecording(); } else { _showCodeModal(); }
  });

  // Modal confirm button
  document.getElementById('sl-confirm-btn')?.addEventListener('click', () => {
    const code = document.getElementById('sl-code-input')?.value ?? '';
    bootstrap.Modal.getInstance(document.getElementById('study-logger-modal'))?.hide();
    startRecording(code);
  });

  // Enter key in the code input field
  document.getElementById('sl-code-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); document.getElementById('sl-confirm-btn')?.click(); }
  });
}

// ── Auto-init ──────────────────────────────────────────────────────────────────
// studyLogger.mjs is loaded as a module script (deferred), so by the time it runs
// jQuery's $(document).ready() has already fired — sliders, token search and all
// other UI components are fully initialised.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

