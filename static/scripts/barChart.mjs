import {
  filterData,
  cleanDataString,
  specialOrders,
  showStudyModal,
  defaultColors,
  performanceColumns,
  getPerformanceBucket,
  _dmCol,
  _dmOptions,
  _dmKeywords,
  _otCols,
  _otRareValues,
  escapeHtml,
} from "./dataUtility.mjs";


/*
Intialization of the interactive elements
- The charts are created when the document is ready
- The visibility is updated whenever the maximum number of bars is changed or a filter changed
- Charts are created for each category that is currently selected
- Modals are set up to show study details when a info-circle is clicked
- When values in the sidebar are changed, the charts are updated accordingly
*/
$(document).ready(function () {
  // The available categories passed by the server for the bar charts
  const categories = $("body").data("filter-categories");
  // performanceColumns is the imported Set from dataUtility.mjs; spread it to build allCategories
  const allCategories = [...categories, ...performanceColumns];
  const questionCirclePath = $("#toggle-menu-container").data(
    "question-circle-path"
  );
  const explanations = $("body").data("explanations");
  
  /*
    Section for the Modal setup
    - The modal opens up when a bar in a chart is clicked
    - The modal contains a table with the details of the studies that match the clicked bar's label
    - The table contains the following columns: ID, Main Author, Year, Location, Input Body Part, Gesture
    - In the table, the info-circle in each row can be clicked to open another modal with more information about the study
  */
  
  // Function to create Modal HTML for a given category and label
  function createModalHTML(category, label) {
    const activeData = filterData(
      JSON.parse(window.sessionStorage.getItem("filters"))
    );
    const fullCategory = getFullCategory(category);
    const isPerf = performanceColumns.has(fullCategory);
  
    const tableHTML = `
      <table class="table table-striped">
        <thead>
          <tr>
            <th></th>
            <th>ID</th>
            <th>Main Author</th>
            <th>Year</th>
            <th>Location</th>
            <th>Input Body Part</th>
            <th>Gesture</th>
          </tr>
        </thead>
        <tbody>
          ${activeData
            .filter((entry) => {
              if (isPerf) {
                const num = parseFloat(entry[fullCategory]);
                const bucket = isNaN(num) ? "N/A" : getPerformanceBucket(num);
                return bucket === label;
              }
              // Device model column: use keyword/substring matching
              if (_dmCol && fullCategory === _dmCol) {
                const parts = entry[fullCategory].toString().split(",").map(s => s.trim());
                if (label === "N/A") return parts.some(p => p === "" || p === "N/A");
                if (label === "Other") return parts.some(p => {
                  if (p === "" || p === "N/A") return false;
                  return !_dmKeywords.some(kw => p.toLowerCase().includes(kw.toLowerCase()));
                });
                return parts.some(p => p.toLowerCase().includes(label.toLowerCase()));
              }
              // Other-threshold columns: "Other" bar matches entries with any rare value
              if (_otCols.has(fullCategory)) {
                const rareSet = _otRareValues[fullCategory];
                const parts = entry[fullCategory].toString().split(",").map(s => s.trim());
                if (label === "Other") {
                  return parts.some(p => p !== "" && rareSet && rareSet.has(p));
                }
                return parts.some(p => p === label);
              }
              return entry[fullCategory].toString().includes(label);
            })
            .map(
              (elem) =>
                `
            <tr>
              <td>
                <img class="info-circle" src="${$("#table-modal-body").data(
                  "url-path-info-circle"
                )}" alt="Info cirle for this row" title="Information about this row" data-id="${
                  escapeHtml(elem["ID"])
                }"/>
              </td>
              <td>${escapeHtml(elem["ID"])}</td>
              <td>${escapeHtml(elem["Main Author"])}</td>
              <td>${escapeHtml(elem["Year"])}</td>
              <td>${escapeHtml(elem["Location"])}</td>
              <td>${escapeHtml(elem["Input Body Part"])}</td>
              <td>${escapeHtml(elem["Gesture"])}</td> 
            </tr>
            `
            )
            .join("")}
        </tbody>
      </table>
      `;
    return tableHTML;
  }
  
  /*
    Section for the Bar Chart setup
    - The bar charts are created based on the data and categories as well as the filters set in the sidebar
    - Each chart is created in a separate canvas element
    - The charts are responsive and can be resized
    - ChartJS is used to create the bar charts, they suggest splitting the data creation and options creation into separate functions
  */
  
  // Creates all bar charts based on the data passed by the server and the currently active filters (categories and value filters)
  function createBarCharts() {
    $("#chartsContainer").empty(); // Clear the charts container
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    const activeCategories = filters.categoryFilters
      .map((cat) => getFullCategory(cat))
      .filter((cat) => cat !== undefined);
    // Remove "Main Author" category if it is in the active categories
    const firstAuthorIndex = activeCategories.indexOf("Main Author");
    if (firstAuthorIndex !== -1) {
      activeCategories.splice(firstAuthorIndex, 1);
    }
  
    // Filter the data so that only the entries that match the active categories and value filters are included
    const activeData = filterData(filters);
  
    if (activeData.length === 0) {
      $("#hiddenChartsMessage").hide();
      $("#hiddenChartsList").empty();
      $("#chartsContainer").html(
        "<p class='text-center mx-auto'>No studies available for the selected sidebar filters. Please select some of the criteria from the sidebar at the right.</p>"
      );
      return;
    }
  
    if (activeCategories.length === 0) {
      // Reset the hidden charts message and list
      $("#hiddenChartsMessage").hide();
      $("#hiddenChartsList").empty();
      $("#chartsContainer").html(
        "<p class='text-center mx-auto'>No studies found for the selected filters. Please select some of the criteria from the toggle menu at the top.</p>"
      );
      return;
    }
  
    // Create a bar chart for each active category
    for (const category of activeCategories) {
      // Only provide the data needed for the current category
      const barData = activeData.map((entry) => entry[category]);
  
      // Create the bar chart for the current category
      createBarChart(barData, category);
    }
  
    // Update the visibility of the charts based on the maximum number of bars set in the dropdown menu
    updateVisibility();
  }
  
  // Function to create a bar chart for each category
  function createBarChart(barData, category) {
    // Calculate the data for the bar chart
    const data = createBarChartData(barData, category);
  
    const labels = data.labels;
  
    // Creating a wrapper element for the chart since resizing is easier for divs
    const chartWrapper = document.createElement("div");
    chartWrapper.className = "chart-wrapper";
    chartWrapper.id = "chart-wrapper-" + category.replaceAll(" ", "€");
  
    const chartTitle = category.split("_").pop();
  
    // Calculate width of container based on the number of labels and the length of the category name
    const width = Math.max(labels.length * 6);
    chartWrapper.style.width = `${width}em`;
  
    // Create a new DOM element for the chart title
    const chartTitleElement = document.createElement("div");
    chartTitleElement.className = "chart-title";
    chartTitleElement.innerHTML = `
      <h5>${chartTitle}</h5>
      <img src="${questionCirclePath}" class="question-circle" title="${explanations[category]}" alt="Information about the category of this chart">
    `;
  
    const chartContainer = document.createElement("div");
    chartContainer.className = "chart-container";
  
    // create new DOM element for the chart
    const canvas = document.createElement("canvas");
    canvas.id = "chart-" + category.replaceAll(" ", "€");
    chartContainer.appendChild(canvas);
  
    // Append the chart container to the element for all charts
    $("#chartsContainer").append(chartWrapper);
    chartWrapper.appendChild(chartTitleElement);
    chartWrapper.appendChild(chartContainer);
  
    // Create the chart for the current category and append it to the container
    const chart = new Chart(canvas.id, {
      type: "bar",
      data: data,
      options: createChartOptions(category),
    });
  }
  
  // Function to create the data in the format required by Chart.js for bar charts
  function createBarChartData(barData, category) {
    const isPerf = performanceColumns.has(category);

    // Device model column: aggregate by keyword option (same logic as the filter)
    if (_dmCol && category === _dmCol) {
      const occurrences = {};
      for (const opt of _dmOptions) occurrences[opt] = 0;

      for (const raw of barData) {
        const parts = raw.toString().split(",").map(s => s.trim());
        for (const part of parts) {
          const isNA = part === "" || part === "N/A";
          if (isNA) { occurrences["N/A"]++; continue; }
          const lower = part.toLowerCase();
          let matchedKeyword = false;
          for (const kw of _dmKeywords) {
            if (lower.includes(kw.toLowerCase())) {
              occurrences[kw]++;
              matchedKeyword = true;
            }
          }
          if (!matchedKeyword) occurrences["Other"]++;
        }
      }

      // Keep _dmOptions order; drop options with zero count
      const labels = _dmOptions.filter(opt => occurrences[opt] > 0);
      return {
        labels,
        datasets: [{
          data: labels.map(l => occurrences[l]),
          backgroundColor: labels.map((_, i) => defaultColors[i % defaultColors.length]),
          barThickness: "flex",
          maxBarThickness: 50,
        }],
      };
    }

    // Other-threshold columns: aggregate rare values under "Other" bar
    if (_otCols.has(category)) {
      const rareSet = _otRareValues[category];
      const occurrences = {};
      for (const raw of barData) {
        const parts = raw.toString().split(",").map(s => s.trim());
        for (const part of parts) {
          if (part === "") continue;
          const label = rareSet && rareSet.has(part) ? "Other" : part;
          occurrences[label] = (occurrences[label] || 0) + 1;
        }
      }
      const labels = Object.keys(occurrences).filter(l => l !== "Other" && l !== "N/A").sort((a, b) => {
        const prioA = specialOrders[a] ?? 0;
        const prioB = specialOrders[b] ?? 0;
        return prioA !== prioB ? prioA - prioB : a.toLowerCase().localeCompare(b.toLowerCase());
      });
      if (occurrences["Other"] !== undefined) labels.push("Other");
      if (occurrences["N/A"] !== undefined) labels.push("N/A");
      return {
        labels,
        datasets: [{
          data: labels.map(l => occurrences[l]),
          backgroundColor: labels.map((_, i) => defaultColors[i % defaultColors.length]),
          barThickness: "flex",
          maxBarThickness: 50,
        }],
      };
    }

    // Count the occurrences of each value (or bucket) in the data entries
    const occurrences = {};
    for (const entry of barData) {
      const values = cleanDataString(category, entry.toString());
      for (const value of values) {
        let key = value;
        if (isPerf) {
          const num = parseFloat(value);
          key = isNaN(num) ? "N/A" : getPerformanceBucket(num);
        }
        occurrences[key] = (occurrences[key] || 0) + 1;
      }
    }
  
    // The keys of the occurrences will be the labels for the chart
    const labels = Object.keys(occurrences).sort((a, b) => {
      // For performance buckets (e.g. "96-100"), sort by the lower bound numerically descending
      if (isPerf) {
        if (a === "N/A") return 1;
        if (b === "N/A") return -1;
        return parseFloat(b.split("-")[0]) - parseFloat(a.split("-")[0]);
      }
      // Check if the labels are all convertable to numbers
      if (Object.keys(occurrences).every((key) => !isNaN(key))) {
        return parseFloat(a) - parseFloat(b);
      }
      const prioA = specialOrders[a] ?? 0;
      const prioB = specialOrders[b] ?? 0;
      return prioA !== prioB ? prioA - prioB : a.localeCompare(b);
    });
  
    return {
      labels: labels,
      datasets: [
        {
          data: labels.map((label) => occurrences[label]),
          backgroundColor: labels.map(
            (_, index) => defaultColors[index % defaultColors.length]
          ),
          barThickness: "flex",
          maxBarThickness: 50,
        },
      ],
    };
  }
  
  // Creating the chart options based on the category
  function createChartOptions(category) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: {
            label: function (tooltipItem) {
              return `${tooltipItem.raw} studies. Click for list!`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            autoSkip: false,
            callback: function (value, index, ticks) {
              const label = this.getLabelForValue(value);
  
              // Limit the number of characters displayed on the x-axis
              return label.length > 20 ? label.slice(0, 20) + "..." : label;
            },
            maxRotation: 40,
            padding: 2,
          },
        },
        y: {
          beginAtZero: true,
          ticks: {
            stepSize: 1,
          },
        },
      },
      onClick: function (event, elements, chart) {
        if (elements.length === 0) return;
        const label = chart.data.labels[elements[0].index];
  
        const tableHTML = createModalHTML(category, label);
        $("#modal-header-info").text(
          `Studies for ${category.split("_").pop()} filtered by "${label}"`
        );
        $("#rowDetailsContainerBarCharts").html(tableHTML);
        $("#table-modal").modal("show");
      },
    };
  }
  
  // Finds the full category name based on the short name provided by the checkbox
  function getFullCategory(category) {
    return allCategories.find((cat) => cat.includes(category));
  }
  
  /*
    Section for the visibility of the charts
    - The visibility of the charts is updated based on the maximum number of bars set in the dropdown menu
    - If a chart exceeds the maximum number of bars, it is hidden and a message is displayed in the hidden charts list
    - If any filter changes, the charts and the chart's visibility is updated accordingly
  */
  
  function updateVisibility() {
    const maxBars = parseInt($("#maxBarsDropdown").val());
    const filters = JSON.parse(window.sessionStorage.getItem("filters"));
    const activeCategories = filters.categoryFilters
      .map((cat) => getFullCategory(cat))
      .filter((cat) => cat !== undefined);
    // Remove "Main Author" category if it is in the active categories
    const firstAuthorIndex = activeCategories.indexOf("Main Author");
    if (firstAuthorIndex !== -1) {
      activeCategories.splice(firstAuthorIndex, 1);
    }
  
    // Reset the hidden charts message and list
    $("#hiddenChartsMessage").hide();
    $("#hiddenChartsList").empty();
  
    // Hide all charts that exceed the maximum number of bars
    for (const category of activeCategories) {
      const chart = Chart.getChart("chart-" + category.replaceAll(" ", "€"));
      const chartWrapper = document.getElementById(
        "chart-wrapper-" + category.replaceAll(" ", "€")
      );
  
      // if there are no labels, dont show the chart
      if (chart.data.labels.length === 0) {
        chartWrapper.style.display = "none";
        continue;
      }
  
      // Hide the chart if it exceeds the maximum number of bars
      if (chart.data.labels.length > maxBars) {
        // Hide the chart wrapper
        chartWrapper.style.display = "none";
  
        // Add a message to the hidden charts list
        $("#hiddenChartsList").append(
          `<li id="message-${category}"><strong>${category
            .split("_")
            .pop()}</strong>: ${
            chart.data.labels.length
          } bars (exceeds threshold of ${maxBars})</li>`
        );
      } else {
        // Show the chart if it does not exceed the maximum number of bars
        chartWrapper.style.display = "flex";
      }
    }
  
    // If there is at least one hidden chart, show the hidden charts message
    if ($("#hiddenChartsList").children().length > 0) {
      $("#hiddenChartsMessage").show();
    }
  }
  // Create bar charts for each category that is currently selected
  createBarCharts();

  // When the maximum number of displayed bars is changed, create the view again
  $("#maxBarsDropdown").on("change", function () {
    // Remove all existing charts and hidden messages
    updateVisibility();
  });

  // Add an event listener to the every category checkbox
  $(".form-check-input").on("change", function () {
    createBarCharts();
  });

  // Add an event listener to each value filter checkbox
  $(".value-filter").on("change", function () {
    createBarCharts();
  });

  // Add an event listener to the exclusive filters button
  $(".exclusive-filter").on("click", function () {
    createBarCharts();
  });

  // Use Event Delegation to handle clicks on the info-circle images
  $("#rowDetailsContainerBarCharts").on("click", ".info-circle", function (e) {
    const id = e.target.getAttribute("data-id");
    showStudyModal(id);
  });

  $(".range-slider").each(function () {
    this.noUiSlider.on("end", function () {
      createBarCharts();
    });
  });
});
