import { filterData, getDataEntry, showStudyModal, sortNodesByCategory } from "./dataUtility.mjs";
import { createLegend, highlightNode, removeHighlighting, drawNode } from "./d3DrawingUtility.mjs";

// Load the similarity data from the HTML element
const similarityData = $("#graphContainer").data("similarity");
// Load the categories of the dropdown menu
const filterCategories = $("body").data("filter-categories");
const excluded_categories = $("#categoryDropdownContainer").data("excluded-categories");
const infoCirclePath = $("#graphContainer").data("info-circle-path");

// Define some texts for the tooltips
const abstractTooltip = "This visualization shows semantic similarity between paper abstracts. Similarities were calculated using Google Gemini embeddings (gemini-embedding-exp-03-07) with cosine similarity and then z-standardized. Values above 0 indicate above-average similarity (0=mean, 1=one standard deviation above mean). Higher thresholds show only the most similar papers.";
const databaseTooltip = "This visualization shows similarity between studies based on features extracted from the database. Features were normalized and similarity was calculated based on their values.";

const abstractStudyIDs = similarityData["abstract_study_ids"];
const abstractMatrix = similarityData["abstract_matrix"];
const databaseStudyIDs = similarityData["database_study_ids"];
const databaseMatrix = similarityData["database_matrix"];

// Set the default similarity type from session storage or fallback to "database"
let similarityType = window.sessionStorage.getItem("similarityType") || "database";
$(`input[value='${similarityType}']`).prop("checked", true);

// Add tooltip text based on the selected similarity type
$("#thresholdInfoIcon").attr("title", similarityType === "abstract" ? abstractTooltip : databaseTooltip);

// Populate the color nodes dropdown menu
filterCategories.forEach(category => {
  if (excluded_categories.includes(category)) return; 
  const shortCategory = category.split("_").pop();
  $("#similarityColorCategory").append(
    `<option value="${category}">${shortCategory}</option>`
  );
});

let colorCategory = window.sessionStorage.getItem("colorCategory") || "";
$(`#similarityColorCategory > option[value="${colorCategory}"]`).prop("selected", true);

let similarityThreshold = parseFloat(window.sessionStorage.getItem("similarityThreshold")) || 1;
// Set the displayed threshold value in the UI
$("#thresholdValue").text(similarityThreshold.toFixed(2));

// Create the slider
const slider = document.getElementById("thresholdSlider");
noUiSlider.create(slider, {
  start: [similarityThreshold], // Default to 1 steddev
  connect: [true, false], // Connect to the left
  range: {
    'min': -3, // Typically -3 standard deviations
    'max': 3   // Typically +3 standard deviations
  },
  step: 0.1,
  tooltips: [true], // Show tooltip
  format: {
    to: function (value) {
        return value.toFixed(2);
    },
    from: function (value) {
        return parseFloat(value);
    }
  },
})
.on("change", function(values, handle) {
  similarityThreshold = parseFloat(values[handle]);
  // Update the threshold text
  $("#thresholdValue").text(similarityThreshold.toFixed(2));
  // Draw the graph with the new threshold
  drawGraph(similarityThreshold);
  window.sessionStorage.setItem("similarityThreshold", similarityThreshold);
});

/*
  Section for showing the modal
  - The modal is prepared with the information about the selected study
  - If the study is connected to other studies, the connections are shown in a table
*/
function openNetworkDetails(nodeID, links) {
  const nodeData = getDataEntry(nodeID);
  const connectedNodes = links.filter(link => link.sourceID === nodeID || link.targetID === nodeID).map(link => {
    return {
      id: link.sourceID === nodeID ? link.targetID : link.sourceID,
      similarity: link.value,
    }
  });
  // Sort connected nodes by similarity
  connectedNodes.sort((a, b) => b.similarity - a.similarity);

  const colGroupHTML = `
    <colgroup>
      <col style="width: 3%;">  <!-- Info icon column -->
      <col style="width: 5%;"> <!-- ID column -->
      <col style="width: 17%;"> <!-- Authors column -->
      <col style="width: 8%;">  <!-- Year column -->
      <col style="width: 15%;"> <!-- Location column -->
      <col style="width: 12%;"> <!-- Body Part column -->
      <col style="width: 18%;"> <!-- Gesture column -->
      <col style="width: 10%;"> <!-- Empty column for alignment -->
    </colgroup>
    `;

  // Populate the connections container with information about the selected study
  const sourceHTML = `
    <h5 class="mb-3">Selected Study</h5>
    <div class="table-responsive mb-4">
      <table class="table table-striped">
        ${colGroupHTML}
        <thead>
          <tr>
            <th></th>
            <th>ID</th>
            <th>Authors</th>
            <th>Year</th>
            <th>Location</th>
            <th>Body Part</th>
            <th>Gesture</th>
            <th></th> <!-- Empty column for alignment -->
          </tr>
        </thead>
        <tbody>
          <tr class="selected-study-row">
            <td><img src="${infoCirclePath}" alt="Info cirle for this row" title="Information about this row" data-ID=${nodeData["ID"]} class="info-circle network-information"/></td>
            <td>${nodeData["ID"]}</td>
            <td>${nodeData["Main Author"]}</td>
            <td>${nodeData["Year"]}</td>
            <td>${nodeData["Location"]}</td>
            <td>${nodeData['Input Body Part']}</td>
            <td>${nodeData["Gesture"]}</td>
            <td></td> <!-- Empty cell for alignment -->
          </tr>
        </tbody>
      </table>
    `;

  // Populate the connections container with information about the connected studies
  const connectionsHTML = `
    <h5 class="mb-3">Study Network</h5>
    <div class="table-responsive">
      <table class="table table-striped">
        ${colGroupHTML}
        <thead>
          <tr>
            <th></th>
            <th>ID</th>
            <th>Authors</th>
            <th>Year</th>
            <th>Location</th>
            <th>Body Part</th>
            <th>Gesture</th>
            <th>Similarity</th>
          </tr>
        </thead>
        <tbody>
          ${connectedNodes.length > 0 ?
            connectedNodes.map(node => {
            const nodeData = getDataEntry(node.id);
            return `
              <tr>
                <td><img src="${infoCirclePath}" alt="Info cirle for this row" title="Information about this row" data-ID=${nodeData["ID"]} class="info-circle network-information"/></td>
                <td>${nodeData["ID"]}</td>
                <td>${nodeData["Main Author"]}</td>
                <td>${nodeData["Year"]}</td>
                <td>${nodeData["Location"]}</td>
                <td>${nodeData["Input Body Part"]}</td>
                <td>${nodeData["Gesture"]}</td>
                <td><strong>${node.similarity.toFixed(2)}</strong></td>
              </tr>
            `
          }).join("") : 
        `<tr><td colspan="8" class="text-center">No connected studies found.</td></tr>`}
        </tbody>
      </table>
    </div>
  `
  // Add information about the total number of connections
  const totalConnectionsHTML = `<p class="text-muted mt-2">Total connections: ${connectedNodes.length}</p>`
  
  // Append to the connections container
  $("#connectionsContainer").empty();
  $("#connectionsContainer").html(sourceHTML);
  $("#connectionsContainer").append(connectionsHTML);
  $("#connectionsContainer").append(totalConnectionsHTML);

  // Show the modal
  $("#connectionsModal").modal("show");
}

/*
  Section for preparing the data for the similarity graph
  - The data needs to be available with respect to the current filters
  - The nodes have to be sorted by the selected category and how many values they have in that category
  - For each value there needs to be a color assigned
*/
// Generate graph data from the similarity matrix, create links based on the threshold, and return sorted nodes, links and the color scale
function generateGraphData(threshold) {
  const { studyIDs, similarityMatrix } = getCurrentSimilarityData();
  const links = [];
  
  // Sort the nodes by category if a category is selected
  const {sortedNodes, colorScale} = sortNodesByCategory(studyIDs, $("#similarityColorCategory").val());
  
  // Only check each pair once (i < j)
  for (let i = 0; i < sortedNodes.length; i++) {
    for (let j = i + 1; j < sortedNodes.length; j++) {
      const nodeA = sortedNodes[i];
      const nodeB = sortedNodes[j];
      
      const similarity = similarityMatrix[parseInt(nodeA) - 1][parseInt(nodeB) - 1];
      if (similarity && similarity >= threshold) {
        links.push({
          sourceID: nodeA,
          targetID: nodeB,
          value: similarity
        });
      }
    }
  }
  
  return { sortedNodes, links, colorScale };
};

// Gets the current similarity data based on the selected type and the selected filters so only active studies are included, returns an object with the study IDs and the similarity matrix like this: {studyIDs: [...], similarityMatrix: [[...]]}
function getCurrentSimilarityData() {
  const filters = JSON.parse(window.sessionStorage.getItem("filters"));
  // Get the IDs of all data studies that are currently active based on the selected filters
  const activeDataIDs = filterData(filters).map(item => item["ID"].toString());
  
  if (similarityType === "abstract") {
    return {
      studyIDs: abstractStudyIDs.filter(id => activeDataIDs.includes(id)),
      similarityMatrix: abstractMatrix
    };
  } else if (similarityType === "database") {
    return {
      studyIDs: databaseStudyIDs.filter(id => activeDataIDs.includes(id)),
      similarityMatrix: databaseMatrix
    };
  };
}

/*
  Section for drawing the similarity graph
  This section contains the functions for drawing the similarity graph such as the standard layout and the U-Layout.
*/

// Helper to format axis tick labels
function formatTickLabel(d) {
  const author = getDataEntry(d, "Main Author");
  return `${author} [${d}]`;
}

function drawGraph(threshold) {
  // Clear graph and legend container
  $("#graphContainer").empty();
  $("#graphContainer").height("auto");
  $("#legend").empty();

  // TODO: change to slider value
  const { sortedNodes, links, colorScale } = generateGraphData(threshold);
  const nodes = [...sortedNodes];

  // If there are no nodes, do not draw the graph
  if (nodes.length === 0) {
    $("#graphContainer").append("<p class='text-center m-2 p-0'>No studies available for the selected sidebar filters. Please select some of the criteria from the sidebar at the right.</p>");
    return;
  }

  // Determine graph dimensions
  const useULayout = nodes.length > 50; // Use U-Layout for larger graphs

  const height = useULayout ? 800 : 500;

  $("#graphContainer").height(height);

  // Create SVG with calculated dimensions
  const svg = d3.select("#graphContainer").append("svg")
    .attr("width", "100%")
    .attr("height", height)
    .attr("viewBox", `0 0 ${$("#graphContainer").width()} ${height}`);

  if (useULayout) {
    drawULayout(svg, {nodes, links}, colorScale);
  } else {
    // Draw links, nodes, and labels for standard layout
    drawStandardLayout(svg, {nodes, links}, colorScale);
  }

  // Draw the legend
  createLegend(nodes, colorScale, $("#similarityColorCategory").val(), $("#legend"));
}

function drawULayout(container, graphData, colorScale) {
  const { nodes, links } = graphData;

  // Define constants for the layout
  const margin = { top: 20, right: 20, bottom: 20, left: 20 };
  const height = parseInt($("svg").height()) - margin.top - margin.bottom;
  const width = parseInt($("svg").width()) - margin.left - margin.right;
  const nodeRadius = Math.floor(width / 150);
  const topAxisHeight = height  / 4;
  const axisMiddle = height / 2;

  // Split the nodes into two groups based on their IDs
  const topNodes = nodes.filter(node => nodes.indexOf(node) <= (nodes.length / 2));
  const bottomNodes = nodes.filter(node => nodes.indexOf(node) > (nodes.length / 2));

  // Create a scale for the top nodes
  const topScale = d3.scalePoint()
    .domain(topNodes)
    .rangeRound([0, width]);

  // Create a scale for the bottom nodes
  const bottomScale = d3.scalePoint()
    .domain(bottomNodes)
    .rangeRound([0, width]);

  // Create an arc generator for the nodes
  const arc = d3.arc()
    .innerRadius(0)
    .outerRadius(nodeRadius);

  // Create the top axis for the nodes
  const topAxis = d3.axisTop(topScale)
    .tickValues(topNodes)
    .tickFormat(d => "")
    .tickSize(0)
    .tickPadding(-4);

  // Create the bottom axis for the nodes
  const bottomAxis = d3.axisBottom(bottomScale)
    .tickValues(bottomNodes)
    .tickFormat(d => "")
    .tickSize(0)
    .tickPadding(-4);

  // Draw the top axis
  container.append("g")
    .attr("transform", `translate(${margin.left}, ${topAxisHeight + margin.top})`) // Position the axis at the top
    .attr("class", "top-axis")
    .call(topAxis);

  // Draw the bottom axis
  container.append("g")
    .attr("transform", `translate(${margin.left}, ${height - topAxisHeight})`) // Position the axis at the bottom
    .attr("class", "bottom-axis")
    .call(bottomAxis);

  // Add info circle and label to top axis ticks
  container.selectAll(".top-axis text")
    .html(d => `<tspan class="info-circle">ⓘ </tspan><tspan>${formatTickLabel(d)}</tspan>`);

  // Add info circle and label to bottom axis ticks
  container.selectAll(".bottom-axis text")
    .html(d => `<tspan class="info-circle">ⓘ </tspan><tspan>${formatTickLabel(d)}</tspan>`);

  // Rotate the axis labels for better readability and adjust the position
  container.select(".top-axis")
    .selectAll("text")
    .attr("text-anchor", "start")
    .attr("transform", "rotate(-90)")
    .attr("dx", "3em");

  // Rotate the axis labels for better readability
  container.select(".bottom-axis")
    .selectAll("text")
    .attr("text-anchor", "end")
    .attr("transform", "rotate(-90)")
    .attr("dx", "-3em"); // Adjust label position

  // Add click event to the axis ticks, so that clicking on a node opens the study modal
  d3.selectAll(".tick")
    .on("click", function(event, d) {
      showStudyModal(d);
    })
    .style("cursor", "pointer")
    .style("font-size", "1.2em")
    .style("user-select", "none"); // Change cursor to pointer for better UX

  // Create a group for the links
  const linkGroup = container.append("g")
    .attr("class", "links")
    .attr("transform", `translate(${margin.left}, ${margin.top})`);

  // Create a group for the top and bottom nodes
  const nodeGroup = container.append("g")
    .attr("class", "nodes")
    .attr("transform", `translate(${margin.left}, ${margin.top})`);

  // Draw the top nodes and add click and hover events
  nodeGroup.selectAll(".node")
    .data(topNodes, d => d)
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("transform", d => `translate(${topScale(d)}, ${topAxisHeight})`)
    .each(function(d) {
      drawNode(d3.select(this), colorCategory, arc, colorScale);
    })
    .on("click", function(event, d) {
      openNetworkDetails(d, links);
    })
    .on("mouseover", function(event, d) {
      highlightNode(d, nodeRadius);
    })
    .on("mouseout", () => removeHighlighting(nodeRadius));

  // Draw the bottom nodes and add click and hover events
  nodeGroup.selectAll(".node")
    .data(bottomNodes, d => d)
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("transform", d => `translate(${bottomScale(d)}, ${height - topAxisHeight - margin.bottom})`)
    .each(function(d) {
      drawNode(d3.select(this), colorCategory, arc, colorScale);
    })
    .on("click", function(event, d) {
      openNetworkDetails(d, links);
    })
    .on("mouseover", function(event, d) {
      highlightNode(d, nodeRadius);
    })
    .on("mouseout", () => removeHighlighting(nodeRadius));

  // Draw the links
  linkGroup.selectAll(".link")
    .data(links)
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("d", d => {
      // Check on which axis the source and target nodes are located
      const isSourceTop = topNodes.includes(d.sourceID);
      const isTargetTop = topNodes.includes(d.targetID);

      // Retrieve the correct x position based on the axis
      const sourceX = isSourceTop ? topScale(d.sourceID): bottomScale(d.sourceID);
      const targetX = isTargetTop ? topScale(d.targetID): bottomScale(d.targetID);

      // Retrieve the correct y position based on the axis
      const sourceY = isSourceTop ? topAxisHeight: height - topAxisHeight - margin.bottom;
      const targetY = isTargetTop ? topAxisHeight: height - topAxisHeight - margin.bottom;

      if (sourceX === targetX && isSourceTop) {
        return `M ${sourceX} ${sourceY} Q ${(sourceX + targetX) / 2} ${axisMiddle + margin.bottom}, ${targetX} ${targetY}`;
      } else if (sourceX === targetX && !isSourceTop) {
        return `M ${sourceX} ${sourceY} Q ${(sourceX + targetX) / 2} ${axisMiddle - margin.top}, ${targetX} ${targetY}`;
      } else {
        return `M ${sourceX} ${sourceY} C ${sourceX} ${axisMiddle}, ${targetX} ${axisMiddle}, ${targetX} ${targetY}`;
      }
    });

  // Add tooltips to the links
  linkGroup.selectAll(".link")
    .append("title")
    .text(d => `${similarityType === "database" ? "Database" : "Abstract"} Similarity: ${d.value.toFixed(2)} between [${d.sourceID}] and [${d.targetID}]`);
}

// Draws the standard layout for the similarity graph
function drawStandardLayout(container, graphData, colorScale) {
  const { nodes, links } = graphData;

  // Define constants for the layout
  const margin = { top: 20, right: 20, bottom: 20, left: 20 };
  const height = parseInt($("svg").height()) - margin.top - margin.bottom;
  const width = parseInt($("svg").width()) - margin.left - margin.right;
  const axisHeight = height / 2;
  const nodeRadius = Math.floor(width / 150);

  // Create a scale for the node positions
  const xScale = d3.scalePoint()
    .domain(nodes)
    .rangeRound([0, width]);

  // Create an axis for the nodes to be displayed horizontally
  const axis = d3.axisBottom(xScale)
    .tickValues(nodes)
    .tickFormat(d => "")
    .tickSize(0)
    .tickPadding(-4);

  // Draw the axis
  container.append("g")
    .attr("class", "axis")
    .attr("transform", `translate(${margin.left}, ${axisHeight + margin.top})`) // Position the axis in the middle of the graph
    .call(axis);

  d3.selectAll("text")
    .html(d => `<tspan class="info-circle">ⓘ </tspan><tspan>${formatTickLabel(d)}</tspan>`);

  // Rotate the axis labels for better readability and adjust the position
  d3.selectAll("text")
    .attr("text-anchor", "end")
    .attr("transform", "rotate(-90)")
    .attr("dx", "-2em")
    .style("font-size", "1.2em")
    .style("user-select", "none");
    
  // Add click event to the axis ticks, so that clicking on a node opens the study modal
  d3.selectAll(".tick")
    .on("click", function(event, d) {
      showStudyModal(d);
    })
    .style("cursor", "pointer"); // Change cursor to pointer for better UX

  // Create a group for the links
  const linkGroup = container.append("g")
    .attr("transform", `translate(${margin.left}, ${margin.top})`)
    .attr("class", "links");

  // Create a group for the nodes
  const nodeGroup = container.append("g")
    .attr("transform", `translate(${margin.left}, ${axisHeight + margin.top})`)
    .attr("class", "nodes");

  const arc = d3.arc()
    .innerRadius(0)
    .outerRadius(nodeRadius);

  // Draw the nodes and add click and hover events
  nodeGroup.selectAll(".node")
  .data(nodes)
  .join("g")
  .attr("class", "node")
  .attr("transform", d => `translate(${xScale(d)}, 0)`)
  .each(function(d) {
      drawNode(d3.select(this), colorCategory, arc, colorScale);
    })
  .on("click", function(event, d) {
    openNetworkDetails(d, links);
  })
  .on("mouseover", function(event, d) {
    highlightNode(d, nodeRadius);
  })
  .on("mouseout", () => removeHighlighting(nodeRadius));

  // Draw the links
  linkGroup.selectAll(".link")
    .data(links)
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("d", d => {
      const sourceX = xScale(d.sourceID);
      const targetX = xScale(d.targetID);
      const arcHeight = Math.min(Math.abs(sourceX - targetX) * 15, height / 3);

      // Draw an quadratic curve from the source to the target node
      return `M ${sourceX} ${axisHeight} Q ${(sourceX + targetX) / 2} ${axisHeight - arcHeight - 2 * margin.top}, ${targetX} ${axisHeight}`;
    });

  // Add tooltips to the links
  linkGroup.selectAll(".link")
    .append("title")
    .text(d => `${similarityType === "database" ? "Database" : "Abstract"} Similarity: ${d.value.toFixed(2)} between [${d.sourceID}] and [${d.targetID}]`);
}

/*
  Interaction section
  Here the event listeners for the interaction possibilities of the similarity graph are set up
*/
$(document).ready(function() {
  drawGraph(similarityThreshold); // Initial draw of the graph

  // Add event listener for similarity type change
  $("input[name='similarityType']").on("change", function() {
    similarityType = $(this).val();
    window.sessionStorage.setItem("similarityType", similarityType);

    // Update the tooltip text based on the selected similarity type
    $("#thresholdInfoIcon").attr("title", similarityType === "abstract" ? abstractTooltip : databaseTooltip);
    drawGraph(similarityThreshold); // Redraw the graph with the new similarity type
  });

  // Add event listener for the category dropdown change
  $("#similarityColorCategory").on("change", function() {
    colorCategory = $(this).val();
    window.sessionStorage.setItem("colorCategory", colorCategory);
    drawGraph(similarityThreshold); // Redraw the graph with the new color category
  });

  window.addEventListener("resize", function() {
    drawGraph(similarityThreshold); // Redraw the graph on window resize
  });

  $(".value-filter").on("change", function() {
    drawGraph(similarityThreshold); // Redraw the graph when a value filter changes
  });

  $(".exclusive-filter").on("click", function() {
    drawGraph(similarityThreshold); // Redraw the graph when an exclusive filter is applied
  });

  $("#connectionsContainer").on("click", ".info-circle", function() {
    const id = $(this).data("id");

    if (this.classList.contains("network-information")) {
      $(`#connectionsModal`).modal("hide"); // Hide the connections modal
    }

    showStudyModal(id);
  });

  $(".range-slider").each(function() {
    this.noUiSlider.on("end", function(values, handle) {    
      drawGraph(similarityThreshold);
    });
  })
})