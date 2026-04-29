import { updateFilters } from "./dataUtility.mjs";

// Options for each token-search column, loaded from body data attribute set by the server.
// Format: { "Main Author": ["Alice", "Bob", ...], "Keywords": [...], "Authors": [...] }
const _tokenSearchOptions = (() => {
  const raw = $("body").attr("data-token-search-options");
  if (!raw) return {};
  try { return JSON.parse(raw); } catch (e) { return {}; }
})();

/**
 * Score how well `option` matches `query`.
 * Returns 0 if it should not appear in the suggestions at all.
 * Higher = better match.
 */
function scoreMatch(option, query) {
  if (!query) return 0;
  // Normalize: lowercase + strip diacritics so "roddiger" matches "Röddiger"
  const normalize = s => s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const o = normalize(option);
  const q = normalize(query);

  if (o === q)            return 100;
  if (o.startsWith(q))   return 90;

  const words = o.split(/\s+/);
  if (words.some(w => w.startsWith(q))) return 80;
  if (o.includes(q))     return 60;
  if (words.some(w => w.includes(q))) return 40;
  return 0;
}

/** Return all options for `col` that match `query`, sorted best-first. */
function getMatches(col, query) {
  if (!query.trim()) return [];
  const options = _tokenSearchOptions[col] || [];
  return options
    .map(opt => ({ opt, score: scoreMatch(opt, query) }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score || a.opt.localeCompare(b.opt))
    .map(({ opt }) => opt);
}

// ── sessionStorage helpers ────────────────────────────────────────────────────

function getTokens(col) {
  const filters = JSON.parse(window.sessionStorage.getItem("filters")) || {};
  return (filters.tokenFilters || {})[col] || [];
}

function setTokens(col, tokens) {
  const filters = JSON.parse(window.sessionStorage.getItem("filters")) || {};
  if (!filters.tokenFilters) filters.tokenFilters = {};
  filters.tokenFilters[col] = tokens;
  updateFilters(filters);
}

/** Persist a new token for col (deduplicates). Returns true if the list changed. */
function addToken(col, token) {
  const current = getTokens(col);
  if (current.includes(token)) return false;
  setTokens(col, [...current, token]);
  return true;
}

/** Remove a token from col. Returns true if the list changed. */
function removeToken(col, token) {
  const current = getTokens(col);
  const updated = current.filter(t => t !== token);
  if (updated.length === current.length) return false;
  setTokens(col, updated);
  return true;
}

// ── DOM helpers ───────────────────────────────────────────────────────────────

/** CSS.escape polyfill-safe helper */
function escapeCSS(str) {
  return CSS.escape ? CSS.escape(str) : str.replace(/([^a-zA-Z0-9_-])/g, "\\$1");
}

function getGroupEl(col) {
  return $(`.token-search-group[data-col="${escapeCSS(col)}"]`);
}

function getSuggestionsEl(col) {
  return $(`.token-suggestions[data-col="${escapeCSS(col)}"]`);
}

function getSelectedEl(col) {
  return $(`.token-selected-container[data-col="${escapeCSS(col)}"]`);
}

/** Re-render the selected-token badges for `col` from sessionStorage. */
function renderTokenBadges(col) {
  const container = getSelectedEl(col);
  container.empty();
  const tokens = getTokens(col);
  tokens.forEach(token => {
    const badge = $(`<span class="token-badge"><span class="token-badge-text"></span><span class="token-badge-remove" title="Remove">×</span></span>`);
    badge.find(".token-badge-text").text(token);
    badge.on("click", () => {
      removeToken(col, token);
      renderTokenBadges(col);
      notifyFilterChange();
    });
    container.append(badge);
  });
}

/** Re-render the suggestions dropdown for `col` given a list of matches. */
function renderSuggestions(col, matches) {
  const container = getSuggestionsEl(col);
  container.empty();
  if (matches.length === 0) {
    container.hide();
    return;
  }
  const selected = new Set(getTokens(col));
  matches.forEach(match => {
    const item = $(`<div class="token-suggestion-item"></div>`);
    item.text(match);
    if (selected.has(match)) item.addClass("token-suggestion-selected");
    item.on("mousedown", e => {
      e.preventDefault(); // keep input focused
      const inputEl = getGroupEl(col).find(".token-search-input");
      if (selected.has(match)) {
        // toggle off
        removeToken(col, match);
        renderTokenBadges(col);
        notifyFilterChange();
        // re-render suggestions so the highlight updates
        const query = inputEl.val();
        renderSuggestions(col, getMatches(col, query));
      } else {
        addToken(col, match);
        inputEl.val("");
        container.hide();
        renderTokenBadges(col);
        notifyFilterChange();
      }
    });
    container.append(item);
  });
  container.show();
}

/**
 * Trigger all view re-renders by firing a change event on any visible value-filter
 * checkbox — each view's handler reads from sessionStorage, not from checkbox state.
 */
function notifyFilterChange() {
  const first = $(".value-filter").first();
  if (first.length) {
    first.trigger("change");
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

$(document).ready(function () {
  // Restore persisted tokens on page load
  $(".token-search-group").each(function () {
    const col = $(this).data("col");
    renderTokenBadges(col);
  });

  // Live search: re-score on every keystroke
  $(document).on("input", ".token-search-input", function () {
    const col = $(this).data("col");
    const query = $(this).val();
    renderSuggestions(col, getMatches(col, query));
  });

  // Re-open suggestions on re-focus if there is text
  $(document).on("focus", ".token-search-input", function () {
    const col = $(this).data("col");
    const query = $(this).val();
    if (query.trim()) renderSuggestions(col, getMatches(col, query));
  });

  // Hide suggestions when input loses focus (delay allows mousedown on item to fire first)
  $(document).on("blur", ".token-search-input", function () {
    const col = $(this).data("col");
    setTimeout(() => getSuggestionsEl(col).hide(), 180);
  });

  // Select All: add every option as a token
  $(document).on("click", ".token-select-all", function () {
    const col = $(this).data("col");
    const all = _tokenSearchOptions[col] || [];
    setTokens(col, [...all]);
    renderTokenBadges(col);
    notifyFilterChange();
  });

  // Deselect All: clear all tokens (reverts to "show everything")
  $(document).on("click", ".token-deselect-all", function () {
    const col = $(this).data("col");
    setTokens(col, []);
    renderTokenBadges(col);
    notifyFilterChange();
  });
});
