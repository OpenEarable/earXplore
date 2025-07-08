import { filterData, cleanDataString, specialOrders, showStudyModal, defaultColors } from "./dataUtility.mjs";

// The available categories passed by the server for the bar charts
const categories = $("body").data("filter-categories");
const questionCirclePath = $("#toggle-menu-container").data("question-circle-path");
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
  const activeData = filterData(JSON.parse(window.sessionStorage.getItem('filters')));
  const fullCategory = getFullCategory(category);

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
        ${activeData.filter(entry => entry[fullCategory].toString().includes(label)).map(elem => 
          `
          <tr>
            <td>
              <img class="info-circle" src="${$("#table-modal-body").data("url-path-info-circle")}" alt="Info cirle for this row" title="Information about this row" data-id="${elem["ID"]}"/>
            </td>
            <td>${elem["ID"]}</td>
            <td>${elem["Main Author"]}</td>
            <td>${elem["Year"]}</td>
            <td>${elem["Location"]}</td>
            <td>${elem["Input Body Part"]}</td>
            <td>${elem["Gesture"]}</td> 
          </tr>
          `
        ).join("")}
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
  const filters = JSON.parse(window.sessionStorage.getItem('filters'));
  const activeCategories = filters.categoryFilters.map(cat => getFullCategory(cat)).filter(cat => cat !== undefined);
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
    $("#chartsContainer").html("<p class='text-center mx-auto'>No studies available for the selected sidebar filters. Please select some of the criteria from the sidebar at the right.</p>");
    return;
  };

  if (activeCategories.length === 0) {
    // Reset the hidden charts message and list
    $("#hiddenChartsMessage").hide();
    $("#hiddenChartsList").empty();
    $("#chartsContainer").html("<p class='text-center mx-auto'>No studies found for the selected filters. Please select some of the criteria from the toggle menu at the top.</p>");
    return;
  }

  // Create a bar chart for each active category
  for (const category of activeCategories) {
    // Only provide the data needed for the current category
    const barData = activeData.map(entry => entry[category]);

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
    <img src="${questionCirclePath}" title="${explanations[category]}" alt="Information about the category of this chart">
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
  // Count the occurrences of each value in the data entries
  const occurrences = {};
  for (const entry of barData) {
    const values = cleanDataString(category, entry.toString());
    for (const value of values) {
      occurrences[value] = (occurrences[value] || 0) + 1;
    }
  }

  // The keys of the occurrences will be the labels for the chart
  const labels = Object.keys(occurrences).sort((a, b) => {
    // Check if the labels are all convertable to numbers
    if (Object.keys(occurrences).every(key => !isNaN(key))) {
      return parseFloat(a) - parseFloat(b);
    }

    const prioA = specialOrders[a] ?? 0;
    const prioB = specialOrders[b] ?? 0;
    return prioA !== prioB ? prioA - prioB : a.localeCompare(b);
  });

  return {
    labels: labels,
    datasets: [{
      data: labels.map(label => occurrences[label]),
      backgroundColor: labels.map((_, index) => defaultColors[index % defaultColors.length]),
      barThickness: "flex",
      maxBarThickness: 50,
    }]
  }
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
          label: function(tooltipItem) {
            return `${tooltipItem.raw} studies. Click for list!`;
          }
        }
      },
    },
    scales: {
      x: {
        ticks: {
          autoSkip: false,
          callback: function(value, index, ticks) {
            const label = this.getLabelForValue(value);

            // Limit the number of characters displayed on the x-axis
            return label.length > 20 ? label.slice(0, 20) + '...' : label;
          },
          maxRotation: 40,
          padding: 2,
        }
      },
      y: {  
        beginAtZero: true, 
        ticks: { 
          stepSize: 1,
        }
      }
    },
    onClick: function(event, elements, chart) {
      if (elements.length === 0) return;
      const label = chart.data.labels[elements[0].index];

      const tableHTML = createModalHTML(category, label);
      $("#modal-header-info").text(`Studies for ${category.split("_").pop()} filtered by "${label}"`);
      $("#rowDetailsContainerBarCharts").html(tableHTML);
      $("#table-modal").modal("show");
    },
  }
}

// Finds the full category name based on the short name provided by the checkbox
function getFullCategory(category) {
  return categories.find((cat) => cat.includes(category));
}

/*
  Section for the visibility of the charts
  - The visibility of the charts is updated based on the maximum number of bars set in the dropdown menu
  - If a chart exceeds the maximum number of bars, it is hidden and a message is displayed in the hidden charts list
  - If any filter changes, the charts and the chart's visibility is updated accordingly
*/

function updateVisibility() {
  const maxBars = parseInt($("#maxBarsDropdown").val());
  const filters = JSON.parse(window.sessionStorage.getItem('filters'));
  const activeCategories = filters.categoryFilters.map(cat => getFullCategory(cat)).filter(cat => cat !== undefined);
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
    const chartWrapper = document.getElementById("chart-wrapper-" + category.replaceAll(" ", "€"));

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
      $("#hiddenChartsList").append(`<li id="message-${category}"><strong>${category.split("_").pop()}</strong>: ${chart.data.labels.length} bars (exceeds threshold of ${maxBars})</li>`);
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

/*
  Intialization of the interactive elements
  - The charts are created when the document is ready
  - The visibility is updated whenever the maximum number of bars is changed or a filter changed
  - Charts are created for each category that is currently selected
  - Modals are set up to show study details when a info-circle is clicked
  - When values in the sidebar are changed, the charts are updated accordingly
*/
$(document).ready(function() {
  // Create bar charts for each category that is currently selected
  createBarCharts();

  // When the maximum number of displayed bars is changed, create the view again
  $("#maxBarsDropdown").on("change", function() {
    // Remove all existing charts and hidden messages
    updateVisibility();
  })

  // Add an event listener to the every category checkbox
  $(".form-check-input").on("change", function () {   
    createBarCharts();
  });

  // Add an event listener to each value filter checkbox
  $(".value-filter").on("change", function() {
    createBarCharts();
  });

  // Add an event listener to the exclusive filters button
  $(".exclusive-filter").on("click", function() {
    createBarCharts();
  });

  // Use Event Delegation to handle clicks on the info-circle images
  $("#rowDetailsContainerBarCharts").on("click", ".info-circle", function(e) {
    const id = e.target.getAttribute("data-id");
    showStudyModal(id);
  });

  $(".range-slider").each(function() {
    this.noUiSlider.on("end", function() {
      createBarCharts();
    });
  });
});