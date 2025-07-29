import { data, showStudyModal, filterData } from "./dataUtility.mjs";

const table = $("#table");
const categories = ["INFO", "ID", ...$("body").data("filter-categories"), "Study Link"];
const infoCirclePath = table.data("info-circle-path");

let categoryOrder = JSON.parse(window.sessionStorage.getItem("sortByCategory")) || null;
if (!categoryOrder) {
  categoryOrder = {};
  // Initialize categoryOrder with default values
  categories.forEach(category => {
    categoryOrder[category] = "asc"; // Default sorting order is ascending
  });
  window.sessionStorage.setItem("sortByCategory", JSON.stringify(categoryOrder));
}

function showTableData(filters, sortCategory) {
  const activeData = filterData(filters);
  const categoryFilters = filters.categoryFilters.sort((a, b) => categories.indexOf(a) - categories.indexOf(b));

  // If a sort category is provided, use it to sort the active data
  if (sortCategory) {
    const order = categoryOrder[sortCategory] === "asc" ? 1 : -1;
    activeData.sort((a, b) => {
      const valA = a[sortCategory], valB = b[sortCategory];
      if (typeof valA === "number" && typeof valB === "number") {
        return (valA - valB) * order;
      }
      return String(valA).localeCompare(String(valB)) * order;
    });
  };

  // Clear the table before appending new data
  table.empty();
  $("#literature-info").hide();
  $("#missing-category-filters").hide();
  $("#missing-value-filters").hide();

  // If no categories are selected, show the missing category filters message
  if (activeData.length === 0) {
    $("#missing-value-filters").show();
    return;
  }
  
  // If there is only the info column selected, show the info message and return
  if (categoryFilters.length === 1 && categoryFilters[0] === "INFO") {
    $("#missing-category-filters").show();
    return;
  }

  // If other columns are selected, show the table and filter the columns based on the selected categories   
  table.append(`
    <thead>
      <tr>
      ${categoryFilters.map(category => {
        if (category === "INFO") {
          return "<th></th>"
        }
        const shortCategory = category.split("_").pop();
        const isActiveSorted = sortCategory === category;
        const sortDirection = isActiveSorted ? categoryOrder[category] : null;
        const arrowClass = isActiveSorted ? 'active' : '';
        
        let arrowsHtml;
        if (isActiveSorted) {
          arrowsHtml = sortDirection === 'asc' ? 
            `<span class="sort-arrows active">▲&nbsp;&nbsp;&nbsp;</span>` : 
            `<span class="sort-arrows active">▼&nbsp;&nbsp;&nbsp;</span>`;
        } else {
          arrowsHtml = `<span class="sort-arrows">▲▼</span>`;
        }
        
        const displayText = shortCategory.length > 30 ? 
          shortCategory.slice(0, 30) + "..." : 
          shortCategory;
        
        return `<th data-category="${category}" class="left-cell sortable">${displayText}${arrowsHtml}</th>`;
      }).join("\n")}
      </tr>
    </thead>`);

  // Fill the table body with the active data
  const tbody = `
    <tbody>
      ${activeData.map(entry => {
        return `
          <tr>
            ${categoryFilters.map(category => {
              const id = entry["ID"];
              const link = entry["Study Link"];

              if (category === "INFO") {
                return `<td class="centered-cell"><img class="info-circle" src="${infoCirclePath}" alt="Information about this row" title="Information about the study with ID: ${id}" data-id="${id}"></td>`
              } else if (category === "Study Link") {
                return `<td class="left-cell"><a href="${link}" target="_blank"><button class="btn-link">Link!</button></a></td>`
              } else {
                return `<td class="left-cell" >${entry[category]}</td>`;
              }
            }).join("\n")}
          </tr>
        `
      }).join("\n")}
    </tbody>
  `;

  table.append(tbody);
  table.show();
  $("#literature-info").show();
};

function downloadCsv(data, filename) {
   // Convert data to CSV string
  const header = Object.keys(data[0]).map(column => column.split("_").pop()).join(",") + "\n";
  const rows = data.map(row => Object.values(row).join(",")).join("\n");
  const csvContent = header + rows;
  
  // Create a Blob from the CSV string
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  // Create a temporary link and trigger download
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.visibility = 'hidden';
  document.body.appendChild(a);
  a.click();

  // Clean up
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

$(document).ready(function() {
  showTableData(JSON.parse(window.sessionStorage.getItem("filters")));
  
  // add event listener to each checkbox to filter the table
  $(".form-check-input").on("change", function() {
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    showTableData(filters);
  });

  // Add event listener to each value filter to filter the table
  $(".value-filter").on("change", function() {
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    showTableData(filters);
  });

  // Add event listener to exclusive filters button to filter the table
  $(".exclusive-filter").on("click", function() {
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    showTableData(filters);
  });

  // Add event listener to each range slider to filter the table
  $(".range-slider").each(function() {
    this.noUiSlider.on("end", function() {
      const filters = JSON.parse(window.sessionStorage.getItem("filters"));
      showTableData(filters);
    });
  });

  // Add event listener to info circle to toggle the study modal
  $("#table").on("click", ".info-circle", function() {
    const id = $(this).data("id");
    showStudyModal(id);
  });

  // Use event delegation to handle clicks on sorting headers
  $("#table").on("click", ".sortable", function() {
    const sortCategory = $(this).data("category");
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));

    // Toggle the sorting order
    categoryOrder[sortCategory] = categoryOrder[sortCategory] === "asc" ? "desc" : "asc";
    window.sessionStorage.setItem("sortByCategory", JSON.stringify(categoryOrder));

    // Show the table data with the new sorting order
    showTableData(filters, sortCategory);
  });

  // Add event listener to the download filtered dataset button
  $("#downloadFilteredCsv").on("click", function() {
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    const activeData = filterData(filters);
    downloadCsv(activeData, "filtered_data.csv");
  });

  // Add event listener to the download full dataset button
  $("#downloadFullCsv").on("click", function() {
    downloadCsv(data, "full_data.csv");
  });
});