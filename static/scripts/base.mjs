import { convertToID, updateFilters, _dmCol, _dmOptions, _otCols, _otRareValues, _tokenSearchCols } from "./dataUtility.mjs";



$(document).ready(function () {
  // Highlight the current view in the navbar
  const selectedView = $("nav").data("current-view");
  $(".navbar-item").each((index, element) => {
    selectedView === $(element).attr("data-section")
      ? $(element).addClass("navbar-item-selected")
      : $(element).removeClass("navbar-item-selected");
  });

  /*
   * Merge all the filters into a single object
   * This object will be used to filter the data displayed on the page
   * The filters are stored in the session storage to persist across page reloads
   * The filters are stored in the following format:
   * {valueFilters: [value1-category1, value2-category1, ..., valueN-categoryN],
   * rangeFilters: {rangeCategory: [handle1-value, handle2-value], rangeCategory2: [handle1-value], ...},
   * categoryFilters: [category1, category2, ...]} <--- will not be set here, but will be set in the respective scripts
   */

  // Load the current value filters from the session storage
  let filters = JSON.parse(window.sessionStorage.getItem("filters")) || null;
  if (!filters) {
    // If there isnt a filter object in session storage, create a new one
    filters = {};
    updateFilters(filters);
  }

  let valueFilters = filters.valueFilters || null;
  let rangeFilters = filters.rangeFilters || null;
  let exclusiveFilters = filters.exclusiveFilters || null;

  // Ensure tokenFilters object is always present
  if (!filters.tokenFilters) {
    filters.tokenFilters = {};
    updateFilters(filters);
  }

  // If there are no value filters in session storage, meaning user is visiting for the first time, default to all value filters being selected
  if (!valueFilters) {
    valueFilters = [];

    $(".value-filter").each((index, element) => {
      // Check the checkbox and add its ID to the value filters
      $(element).prop("checked", true);
      valueFilters.push(convertToID($(element).attr("id")));
    });

    filters.valueFilters = valueFilters;
    updateFilters(filters);
  } else {
    // If there are value filters in session storage, set the respective checkboxes to checked
    $(".value-filter").each((index, element) => {
      valueFilters.includes(convertToID($(element).attr("id")))
        ? $(element).prop("checked", true)
        : $(element).prop("checked", false);
    });

    // Auto-add any newly introduced checkboxes that are not yet in session storage
    // (e.g. the device model filter added after user's first visit).
    // These default to checked so they don't silently hide rows.
    let newFiltersAdded = false;
    $(".value-filter").each((index, element) => {
      const id = convertToID($(element).attr("id"));
      if (!valueFilters.includes(id)) {
        $(element).prop("checked", true);
        valueFilters.push(id);
        newFiltersAdded = true;
      }
    });
    if (newFiltersAdded) {
      filters.valueFilters = valueFilters;
      updateFilters(filters);
    }

    // Remove stale device model entries: exact device names stored by a previous
    // version of the filter (when Device Model was a regular checklist).  Any
    // session-storage entry whose category matches the device model column but
    // whose value is not one of the configured keyword options is stale and must
    // be removed, otherwise those values act as accidental substring matches.
    if (_dmCol && _dmOptions.length > 0) {
      const before = valueFilters.length;
      valueFilters = valueFilters.filter(entry => {
        const sep = entry.indexOf("--");
        if (sep === -1) return true;
        const entryCategory = entry.slice(sep + 2);
        if (entryCategory !== _dmCol) return true;          // not device model → keep
        const entryValue = entry.slice(0, sep);
        return _dmOptions.includes(entryValue);             // only keep known options
      });
      if (valueFilters.length !== before) {
        console.log("[earXplore] Removed", before - valueFilters.length, "stale device model entries from sessionStorage.");
        filters.valueFilters = valueFilters;
        updateFilters(filters);
      }
    }

    // Clean up stale rare-value filter entries for other-threshold columns.
    // If a user's session still contains a filter for a value that has now been
    // collapsed into "Other", remove it to avoid unexpected filtering behaviour.
    if (_otCols.size > 0) {
      const beforeOt = valueFilters.length;
      valueFilters = valueFilters.filter(entry => {
        const sep = entry.indexOf("--");
        if (sep === -1) return true;
        const entryCategory = entry.slice(sep + 2);
        if (!_otCols.has(entryCategory)) return true;   // not an OT column → keep
        const entryValue = entry.slice(0, sep);
        const rareSet = _otRareValues[entryCategory];
        if (!rareSet) return true;
        return !rareSet.has(entryValue);                 // remove if value is rare
      });
      if (valueFilters.length !== beforeOt) {
        console.log("[earXplore] Removed", beforeOt - valueFilters.length, "stale other-threshold entries from sessionStorage.");
        filters.valueFilters = valueFilters;
        updateFilters(filters);
      }
    }

    // Clean up stale valueFilter entries for token-search columns.
    // These columns no longer use checkboxes; any old entries must be removed
    // to prevent the value list from accidentally influencing filterData.
    if (_tokenSearchCols.size > 0) {
      const beforeTs = valueFilters.length;
      valueFilters = valueFilters.filter(entry => {
        const sep = entry.indexOf("--");
        if (sep === -1) return true;
        const entryCategory = entry.slice(sep + 2);
        return !_tokenSearchCols.has(entryCategory);   // remove if token-search column
      });
      if (valueFilters.length !== beforeTs) {
        console.log("[earXplore] Removed", beforeTs - valueFilters.length, "stale token-search column entries from sessionStorage.");
        filters.valueFilters = valueFilters;
        updateFilters(filters);
      }
    }
  }

  // If there are no range sliders in session storage, initialize them with default values
  if (!rangeFilters) {
    rangeFilters = {};

    $(".range-slider").each(function () {
      const slider = this;
      const min = $(this).data("min");
      const max = $(this).data("max");
      const category = $(this).data("col");
      const unboundedMax = $(this).attr("data-unbounded-max") === "true";

      noUiSlider
        .create(this, getSliderConfig([min, max], min, max, unboundedMax))
        .on("change", function (values, handle) {
          const filters = JSON.parse(window.sessionStorage.getItem("filters"));
          filters.rangeFilters[category] = values;
          updateFilters(filters);
        });

      // Store the initial values in session storag
      rangeFilters[category] = slider.noUiSlider.get();
    });

    filters.rangeFilters = rangeFilters;
    updateFilters(filters);
  } else {
    // If there are range filters in session storage, configure the sliders with the stored valus
    for (const [category, values] of Object.entries(rangeFilters)) {
      const slider = $(`.range-slider[data-col="${category}"]`);
      const max = slider.data("max");
      const min = slider.data("min");
      const unboundedMax = slider.attr("data-unbounded-max") === "true";

      // Recreate the slider with the stored configuartion
      noUiSlider
        .create(slider[0], getSliderConfig(values, min, max, unboundedMax))
        .on("change", function (values, handle) {
          const filters = JSON.parse(window.sessionStorage.getItem("filters"));
          filters.rangeFilters[category] = values;
          updateFilters(filters);
        });
    }

    // Also initialize any new sliders that are not yet in session storage
    $(".range-slider").each(function () {
      const category = $(this).data("col");
      if (rangeFilters[category] !== undefined) return; // already initialized above

      const min = $(this).data("min");
      const max = $(this).data("max");
      const slider = this;
      const unboundedMax = $(this).attr("data-unbounded-max") === "true";

      noUiSlider
        .create(this, getSliderConfig([min, max], min, max, unboundedMax))
        .on("change", function (values, handle) {
          const filters = JSON.parse(window.sessionStorage.getItem("filters")) || { rangeFilters: {}, valueFilters: [], exclusiveFilters: [] };
          if (!filters.rangeFilters) filters.rangeFilters = {};
          filters.rangeFilters[category] = values;
          updateFilters(filters);
        });

      rangeFilters[category] = slider.noUiSlider.get();
    });

    filters.rangeFilters = rangeFilters;
    updateFilters(filters);
  }

  // If there are no exclusive filters in session storage, initialize them as an empty array
  if (!exclusiveFilters) {
    exclusiveFilters = [];
    filters.exclusiveFilters = exclusiveFilters;
    $(".exclusive-filter").each((index, element) => {
      $(element).text("Exclusive filtering: OFF");
    });
    updateFilters(filters);
  } else {
    // If there are exclusive filters in session storage, set the respective button text to "Exclusive filtering: ON" or "Exclusive filtering: OFF"
    $(".exclusive-filter").each((index, element) => {
      const category = $(element).data("col");
      if (exclusiveFilters.includes(category)) {
        $(element).text("Exclusive Filtering: ON");
      } else {
        $(element).text("Exclusive Filtering: OFF");
      }
    });
  }

  function getSliderConfig(startValues, min, max, unboundedMax = false) {
    const upperTooltipFmt = unboundedMax
      ? { to: v => Math.round(v) >= max ? `${max}+` : `${Math.round(v)}` }
      : { to: v => `${Math.round(v)}` };
    return {
      start: startValues,
      connect: true,
      range: {
        min: min,
        max: max,
      },
      tooltips: [{ to: v => `${Math.round(v)}` }, upperTooltipFmt],
      format: {
        to: function (value) {
          return Math.round(value);
        },
        from: function (value) {
          return Number(value);
        },
      },
    };
  }

  // Auto-uncheck the "Include N/A" performance checkbox and remove it from session storage.
  // Called when the performance slider is moved or when metric/eval type checkboxes change.
  function autoUncheckPerformanceNA() {
    const naCheckbox = document.getElementById("Include\u20acN/A--Performance_NA_Include");
    if (!naCheckbox || !naCheckbox.checked) return; // already unchecked, nothing to do
    naCheckbox.checked = false;
    const f = JSON.parse(window.sessionStorage.getItem("filters")) || { rangeFilters: {}, valueFilters: [], exclusiveFilters: [] };
    if (!f.valueFilters) return;
    const naId = "Include N/A--Performance_NA_Include";
    const idx = f.valueFilters.indexOf(naId);
    if (idx !== -1) f.valueFilters.splice(idx, 1);
    updateFilters(f);
  }

  // Auto-check the "Include N/A" checkbox and add it to session storage.
  // Called when the performance slider is returned to its full default range.
  function autoCheckPerformanceNA() {
    const naCheckbox = document.getElementById("Include\u20acN/A--Performance_NA_Include");
    if (!naCheckbox || naCheckbox.checked) return; // already checked, nothing to do
    naCheckbox.checked = true;
    const f = JSON.parse(window.sessionStorage.getItem("filters")) || { rangeFilters: {}, valueFilters: [], exclusiveFilters: [] };
    if (!f.valueFilters) return;
    const naId = "Include N/A--Performance_NA_Include";
    if (!f.valueFilters.includes(naId)) f.valueFilters.push(naId);
    updateFilters(f);
  }

  // Attach an additional change listener to the performance slider so N/A is auto-managed when it moves
  const _perfSliderEl = $(".range-slider[data-col='Accuracy/F1-Score of Interaction Detection']");
  if (_perfSliderEl.length && _perfSliderEl[0].noUiSlider) {
    const _perfMin = parseFloat(_perfSliderEl.data("min"));
    const _perfMax = parseFloat(_perfSliderEl.data("max"));
    _perfSliderEl[0].noUiSlider.on("change", function (values) {
      const lo = parseFloat(values[0]);
      const hi = parseFloat(values[1]);
      if (lo <= _perfMin && hi >= _perfMax) {
        autoCheckPerformanceNA();
      } else {
        autoUncheckPerformanceNA();
      }
    });
  }

  function selectAll(checkboxSelection) {
    const filters = JSON.parse(window.sessionStorage.getItem("filters")) || { rangeFilters: {}, valueFilters: [], exclusiveFilters: [] };
    if (!filters.rangeFilters) filters.rangeFilters = {};
    if (!filters.valueFilters) return;

    // Check all the checkboxes in the selection
    const changedCheckboxes = [];
    checkboxSelection.find(".value-filter").each((_, element) => {
      element.checked = true;
      changedCheckboxes.push(element);
    });

    // Reset the slider to the default range by setting both handles to the minimum and maximum values
    const changedSliders = [];
    checkboxSelection.find(".range-slider").each((_, element) => {
      const min = $(element).data("min");
      const max = $(element).data("max");
      element.noUiSlider.set([min, max]);
      changedSliders.push(element);
    });

    // Add the IDs of the changed checkboxes to the value filters if they are not already included
    changedCheckboxes.forEach((element) => {
      const id = convertToID($(element).attr("id"));
      if (!filters.valueFilters.includes(id)) {
        filters.valueFilters.push(id);
      }
    });

    // Update the range filters for the changed sliders
    changedSliders.forEach((element) => {
      const category = $(element).data("col");
      const min = $(element).data("min");
      const max = $(element).data("max");
      filters.rangeFilters[category] = [min, max];
    });

    // Store the updated value filters in session storage
    updateFilters(filters);

    // Trigger the change event only once for performance
    checkboxSelection.find(".value-filter").first().trigger("change");
  }

  function deselectAll(checkboxSelection) {
    const filters = JSON.parse(window.sessionStorage.getItem("filters")) || { rangeFilters: {}, valueFilters: [], exclusiveFilters: [] };
    if (!filters.rangeFilters) filters.rangeFilters = {};
    if (!filters.valueFilters) return;

    // Uncheck all the checkboxes in the selection
    const changedCheckboxes = [];
    checkboxSelection.find(".value-filter").each((_, element) => {
      element.checked = false;
      changedCheckboxes.push(element);
    });

    // Change the slider to no selection by setting both handles to the minimum value
    const changedSliders = [];
    checkboxSelection.find(".range-slider").each((_, element) => {
      const min = $(element).data("min");
      element.noUiSlider.set([min, min]);
      changedSliders.push(element);
    });

    // Remove the IDs of the changed checkboxes to the value filters if they are included
    changedCheckboxes.forEach((element) => {
      const id = convertToID($(element).attr("id"));
      if (filters.valueFilters.includes(id)) {
        filters.valueFilters.splice(filters.valueFilters.indexOf(id), 1);
      }
    });

    // Update the range filters for the changed sliders
    changedSliders.forEach((element) => {
      const category = $(element).data("col");
      const min = $(element).data("min");
      filters.rangeFilters[category] = [min, min];
    });

    // Store the updated value filters in session storage
    updateFilters(filters);

    // Trigger the change event only once for performance
    checkboxSelection.find(".value-filter").first().trigger("change");
  }
    // Add event listener to each value filter to update the session storage
    $(".value-filter").on("change", function () {
      // Get the ID of the checkbox and convert it to a format suitable for storage
      const id = convertToID($(this).attr("id"));
      const filters = JSON.parse(window.sessionStorage.getItem("filters")) || { rangeFilters: {}, valueFilters: [], exclusiveFilters: [] };
      if (!filters.rangeFilters) filters.rangeFilters = {};
      if (!filters.valueFilters) return;

      if (this.checked && !filters.valueFilters.includes(id)) {
        // Add the ID to the session storage
        filters.valueFilters.push(id);
      } else if (!this.checked && filters.valueFilters.includes(id)) {
        // Remove the ID from the session storage
        filters.valueFilters.splice(filters.valueFilters.indexOf(id), 1);
      }

      // Auto-uncheck the N/A checkbox when metric/eval type selections change
      if (id.endsWith("--Performance_Metric_Type") || id.endsWith("--Performance_Evaluation_Type")) {
        autoUncheckPerformanceNA();
      }

      updateFilters(filters);
    });

  $(".exclusive-filter").on("click", function () {
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    const category = $(this).data("col");

      if (filters.exclusiveFilters.includes(category)) {
        // If the category is already in the exclusive filters, remove it
        filters.exclusiveFilters.splice(
          filters.exclusiveFilters.indexOf(category),
          1
        );
        $(this).text("Exclusive Filtering: OFF");
      } else {
        // If the category is not in the exclusive filters, add it
        filters.exclusiveFilters.push(category);
        $(this).text("Exclusive Filtering: ON");
      }
      updateFilters(filters);
    });

  // Add "selecting / deselecting all" functionality to certain categories
  $(".select-all").on("click", function () {
    const category = $(this).data("col");

    // Find the div with the the same data-col attribute
    const categoryDiv = $(`.category[data-col="${category}"]`);

    // Select all the checkboxes within the category div
    selectAll(categoryDiv);
  });

  $(".deselect-all").on("click", function () {
    const category = $(this).data("col");

    // Find the div with the the same data-col attribute
    const categoryDiv = $(`.category[data-col="${category}"]`);

    // Deselect all the checkboxes within the category div
    deselectAll(categoryDiv);
  });

  // Add "selecting / deselecting all" functionality to certain panels
  $(".select-all-panel").on("click", function () {
    const panelValue = $(this).data("panel");

    // Find the div with the the same data-panel attribute
    const panelDiv = $(`.panel[data-panel-value="${panelValue}"]`);

    // Select all the checkboxes within the panel div
    selectAll(panelDiv);
  });

  $(".deselect-all-panel").on("click", function () {
    const panelValue = $(this).data("panel");

    // Find the div with the the same data-panel attribute
    const panelDiv = $(`.panel[data-panel-value="${panelValue}"]`);

    // Deselect all the checkboxes within the panel div
    deselectAll(panelDiv);
  });

  $(".toggle-visibility-button").on("click", function () {
    const panel = $(this).data("panel");

    // Find the div with the the same data-panel attribute
    const panelDiv = $(`.panel[data-panel-value="${panel}"]`);

    // Toggle the visibility of the filter section
    panelDiv.find(".filters").toggleClass("hidden-filters");

    // Change button text based on current state
    const isHidden = panelDiv.find(".filters").hasClass("hidden-filters");
    $(this).text(isHidden ? "Show" : "Hide");
  });

  $("#select-all-sidebar-button").on("click", function () {
    selectAll($("#sidebar"));
  });

  $("#deselect-all-sidebar-button").on("click", function () {
    deselectAll($("#sidebar"));
  });

  $("#toggle-sidebar").on("click", function () {
    $("#sidebar").toggleClass("visible-sidebar");
    $("#mask").show();
  });

  $("#close-sidebar, #mask").on("click", function () {
    $("#sidebar").toggleClass("visible-sidebar");
    $("#mask").hide();
  });

  $("#study-info-modal").on("hidden.bs.modal", function () {
    window.sessionStorage.removeItem("modalID");
  });
});
