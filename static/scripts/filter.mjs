import { updateFilters } from "./dataUtility.mjs";

// Load the start categories from the backend
const startCategories = $("#toggle-menu-container").data("start-categories");

let filters = JSON.parse(window.sessionStorage.getItem("filters"));
let categoryFilters = filters.categoryFilters || null;
if (!categoryFilters) {
  categoryFilters = startCategories;
  filters.categoryFilters = categoryFilters;

  $(".column-filter").each((index, element) => {
    const id = $(element).attr("id");
    categoryFilters.includes(id) ?
      $(element).prop("checked", true) :
      $(element).prop("checked", false);
  });
  updateFilters(filters);
} else {
  // If there are category filters in session storage, set the respective checkboxes to checked
  $(".column-filter").each((index, element) => {
    const id = $(element).attr("id");
    categoryFilters.includes(id) ?
      $(element).prop("checked", true) :
      $(element).prop("checked", false);
  });
}

$(document).ready(function() {
  // When a checkbox is clicked, update the filters in local storage and the current view
  $(".column-filter").on("change", function() {
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));

    const id = $(this).attr("id");

    if (this.checked && !filters.categoryFilters.includes(id)) {
      filters.categoryFilters.push(id);
    } else if (!this.checked && filters.categoryFilters.includes(id)) {
      filters.categoryFilters.splice(filters.categoryFilters.indexOf(id), 1);
    }
    updateFilters(filters);
  });
  
  // Add selecting functionality to the "Select All" button
  $("#toggleSelectAllColumns").on("click", function() {
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    const checkboxes = ["INFO"]; // Start with INFO to ensure it is always selected

    // Select all checkboxes and store their IDs in an array
    $("#columnToggles .column-filter").each((index, element) => {
      element.checked = true;
      checkboxes.push($(element).attr("id"));
    });

    // Storing the culminated checkboxes in session storage
    filters.categoryFilters = checkboxes;
    updateFilters(filters);

    // triggering only one change event is sufficient
    $("#columnToggles .column-filter").first().trigger("change");
  });

  // Add deselecting functionality to the "Deselect All" button
  $("#toggleDeselectAllColumns").on("click", function() {
    $("#columnToggles .column-filter").each((index, element) => {
      element.checked = false;
    });

    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    filters.categoryFilters = ["INFO"]; // Always keep INFO selected
    updateFilters(filters);

    // triggering only one change event is sufficient
    $("#columnToggles .column-filter").first().trigger("change");
  });

  $("#reset-filters-button").on("click", function() {
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    filters.categoryFilters = startCategories; // Reset to the initial categories
    updateFilters(filters);

    // Reset checkboxes to match the initial categories
    $(".column-filter").each((index, element) => {
      const id = $(element).attr("id");
      $(element).prop("checked", startCategories.includes(id));
    });

    $(".column-filter").first().trigger("change");
  });

  $("#select-filter-button").on("click", function() {
    $("#toggle-menu-container").toggleClass("visible-filters");
  });
});