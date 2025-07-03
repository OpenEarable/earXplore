import { filterData, sortNodesByCategory, getDataEntry, showStudyModal } from "./dataUtility.mjs";
import { createLegend, drawNode, highlightNode, removeHighlighting } from "./d3DrawingUtility.mjs";

// Load data from the backend
const coauthorMatrix = $("#timeline-graph-container").data("coauthor");
const citationMatrix = $("#timeline-graph-container").data("citation");
const filterCategories = $("body").data("filter-categories");
const excludedCategories = $(".category-dropdown-container").data("excluded-categories");
const infoCirclePath = $("#timelineConnectionsModal").data("info-circle-path");
// Citing order
const citingOrder = {"Cites": 0, "Cited By": 1, "Coauthor": 2};

// Populate the timeline dropdown menu
filterCategories.forEach(category => {
  if (excludedCategories.includes(category)) return;
  const shortCategory = category.split("_").pop();
  $("#timelineColorCategory").append(
    `<option value="${category}">${shortCategory}</option>`
  );
});

// Set the default value for the dropdown menu
let colorCategory = window.sessionStorage.getItem("colorCategory") || "";
$("#timelineColorCategory").val(colorCategory);

// Set the shared authors option
let showSharedAuthors = window.sessionStorage.getItem("showSharedAuthors") || "true";
$("#timeline-toggle-shared-authors").prop("checked", showSharedAuthors === "true");

// Set the current citation mode
let citationMode = window.sessionStorage.getItem("citationMode") || "both";
$(`#timeline-mode-${citationMode}`).prop("checked", true);

function showNetworkModal(id) {
  // Get the data entry for the selected ID
  const entry = getDataEntry(id);

  // Get links which represent a citing relationship (the source cites the target)
  const citingLinks = d3.selectAll(".citing")
    .filter(d => d.sourceID === id).data();

  // Get links which represent a cited by relationship (the source is cited by the target)
  const citedByLinks = d3.selectAll(".cited-by")
    .filter(d => d.sourceID === id).data();

  // Get the links that represent a coauthor relationship
  const coauthorLinks = d3.selectAll(".coauthor")
    .filter(d => d.sourceID === id).data();

  // Combine target IDs that appear in more than one type of link
  const targetIDs = {};
  citingLinks.forEach(link => (targetIDs[link.targetID] = (targetIDs[link.targetID] || [])).push("Cites"));
  citedByLinks.forEach(link => (targetIDs[link.targetID] = (targetIDs[link.targetID] || [])).push("Cited By"));
  coauthorLinks.forEach(link => (targetIDs[link.targetID] = (targetIDs[link.targetID] || [])).push("Coauthor"));
  const orderedIDs = Object.keys(targetIDs).sort((a, b) => {
    if (targetIDs[a].length !== targetIDs[b].length) {
      return targetIDs[b].length - targetIDs[a].length; // Sort by number of connections
    }
    return citingOrder[targetIDs[a][0]] - citingOrder[targetIDs[b][0]]; // Sort by connection type priority
  })

  const colgroupHTML = `
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

  const headerHTML = `
    <h5 class="mb-3 text-start">Selected Study</h5>
    <div class="table-responsive">
      <table class="table table-striped">
        ${colgroupHTML}
        <thead>
          <tr>
            <th class="centered-cell" ></th>
            <th class="centered-cell" >ID</th>
            <th class="centered-cell" >Authors</th>
            <th class="centered-cell" >Year</th>
            <th class="centered-cell" >Location</th>
            <th class="centered-cell" >Body Part</th>
            <th class="centered-cell" >Gesture</th>
            <th class="centered-cell" ></th> <!-- Empty header for alignment -->
          </tr>
        </thead>
        <tbody>
          <tr class="selected-study-row">
            <td class="centered-cell" ><img src="${infoCirclePath}" alt="Info cirle for this row" title="View details" data-ID=${entry["ID"]} class="info-circle"/></td>
            <td class="centered-cell" >${entry["ID"]}</td>
            <td class="centered-cell" >${entry["Main Author"]}</td>
            <td class="centered-cell" >${entry["Year"]}</td>
            <td class="centered-cell" >${entry["Location"]}</td>
            <td class="centered-cell" >${entry["Input Body Part"]}</td>
            <td class="centered-cell" >${entry["Gesture"]}</td>
            <td class="centered-cell" ></td> <!-- Empty cell for alignment -->
          </tr>
        </tbody>
      </table>
    </div>
  `;

  let connectionsHTML;
  if (citingLinks.length === 0 && citedByLinks.length === 0 && coauthorLinks.length === 0) {
    connectionsHTML = "<h5 class='text-start'>Study Network</h5><p>No connections found with the current filter settings.</p>";
  } else {
    connectionsHTML = `
      <h5 class="mb-3 text-start">Study Network</h5>
      <div class="table-responsive">
        <table class="table table-striped">
        ${colgroupHTML}
          <thead>
            <tr>
              <th class="centered-cell"></th>
              <th class="centered-cell">ID</th>
              <th class="centered-cell">Authors</th>
              <th class="centered-cell">Year</th>
              <th class="centered-cell">Location</th>
              <th class="centered-cell">Body Part</th>
              <th class="centered-cell">Gesture</th>
              <th class="centered-cell">Connection Type</th>
            </tr>
          </thead>
          <tbody>
            ${orderedIDs.map(targetID => {
              const entry = getDataEntry(targetID);
              return `
                <tr>
                  <td class="centered-cell"><img src="${infoCirclePath}" alt="Info cirle for this row" title="View details" data-ID=${entry["ID"]} class="info-circle"/></td>
                  <td class="centered-cell">${entry["ID"]}</td>
                  <td class="centered-cell">${entry["Main Author"]}</td>
                  <td class="centered-cell">${entry["Year"]}</td>
                  <td class="centered-cell">${entry["Location"]}</td>
                  <td class="centered-cell">${entry["Input Body Part"]}</td>
                  <td class="centered-cell">${entry["Gesture"]}</td>
                  <td class="centered-cell">${targetIDs[targetID].map(formatConnectionType).join(", ")}</td>
                </tr>`;
            }).join("\n")}
          </tbody>
        </table>
      </div>
      <p class="text-start"> Total connections: ${citingLinks.length + citedByLinks.length + coauthorLinks.length} </p>
    `;
  };

  // Append the generated HTML to the modal and show it
  $("#timelineConnectionsContainer").html(headerHTML);
  $("#timelineConnectionsContainer").append(connectionsHTML);
  $("#timelineConnectionsModal").modal("show");
}

function formatConnectionType(value) {
  switch (value) {
    case "Cites":
      return "<span class='text-primary'>Cites</span>";
    case "Cited By":
      return "<span class='text-success'>Cited By</span>";
    default:
      return "<span class='text-secondary'>Shared Authors</span>";
  };
};

/*
 * Preparing the data for the timeline graph.
 * The graph will be rendered using the coauthor and citation matrices.
 */
function generateTimelineData() {
  // Get the currently active nodes based on the selected category and filters
  const activeNodes = filterData(JSON.parse(window.sessionStorage.getItem("filters"))).map(item => item["ID"].toString());

  // Order the nodes by the selected category
  const { sortedNodes, colorScale } = sortNodesByCategory(activeNodes, colorCategory);

  // Append the year to each node
  const nodes = sortedNodes.map(node => {
    return {
      id: node,
      year: getDataEntry(node, "Year"),
    }
  });

  const years = {};
  nodes.forEach(node => {
    if (!years[node.year]) {
      years[node.year] = [node.id];
    } else {
      years[node.year].push(node.id);
    }
  });
  const maxYears = Math.max(...Object.keys(years).map(year => years[year].length));
  
  // Create links for co-authors and citations
  const links = {coauthorLinks: [], citingLinks: [], citedByLinks: []};
  for (const node of sortedNodes) {
    for (const other of sortedNodes) {

      // Populate the links for co-authors
      if (coauthorMatrix[node][other]) {
        links.coauthorLinks.push({
          sourceID: node,
          targetID: other,
        });
      };

      // Populate the links for citations
      if (citationMatrix[node][other]) {
        links.citingLinks.push({
          sourceID: node,
          targetID: other,
        });
      };

      if (citationMatrix[other][node]) {
        links.citedByLinks.push({
          sourceID: node,
          targetID: other,
        });
      }
    }
  }

  return {
    nodes,
    years,
    links,
    maxYears,
    colorScale
  }
}

function drawTimelineGraph() {
  // Clear the previous graph
  $("#timeline-graph-container").empty();
  $("#timeline-graph-container").height("auto");
  $("#legend").empty();

  const { nodes, years, links, maxYears, colorScale } = generateTimelineData();
  const { coauthorLinks, citingLinks, citedByLinks } = links;
  const maxYearsCount = Math.max(...Object.values(years).map(year => year.length));

  // If there are no nodes, do not draw the graph
  if (nodes.length === 0) {
    $("#timeline-graph-container").append("<p class='m-2 p-0'>No studies available for the selected sidebar filters. Please select some of the criteria from the sidebar at the right.</p>");
    return;
  }

  // Set up layout dimensions for the graph
  const margin = { top: 20, right: 50, bottom: 50, left: 50 };
  const innerWidth = $("#timeline-graph-container").width() - margin.left - margin.right;
  const nodeRadius = innerWidth / 150;
  const height = maxYearsCount * (nodeRadius * 4);
  const innerHeight = height - margin.top - margin.bottom;
  const axisHeight = innerHeight;

  // Create the svg container for the timeline graph
  const svg = d3.select("#timeline-graph-container")
    .append("svg")
    .attr("width", $("#timeline-graph-container").width())
    .attr("height", height)
    .attr("viewBox", `0 0 ${$("#timeline-graph-container").width()} ${height}`);

  // Create an x scale for the years
  const xScale = d3.scalePoint()
    .domain(Object.keys(years).map(Number))
    .range([0, innerWidth]);

  // Create a y scale for the nodes
  const yScale = d3.scaleLinear()
    .domain([0, maxYears])
    .range([axisHeight - margin.bottom, 0]);

  // Create an x axis for the years
  const xAxis = d3.axisBottom(xScale)
    .tickFormat(d3.format("d"))
    .tickSize(5);

  // Draw the x axis
  svg.append("g")
    .attr("class", "x-axis")
    .attr("transform", `translate(${margin.left}, ${axisHeight + margin.top})`)
    .call(xAxis);

  // Format the labels for the axis
  svg.selectAll(".x-axis text")
    .style("font-size", "1.2em")
    .style("user-select", "none");

  // Create a link group for the links
  const linkGroup = svg.append("g")
    .attr("class", "links")
    .attr("transform", `translate(${margin.left}, ${margin.top})`);

  // Create a node group for the nodes
  const nodeGroup = svg.append("g")
    .attr("class", "nodes")
    .attr("transform", `translate(${margin.left}, ${margin.top})`);

  const arc = d3.arc()
    .innerRadius(0)
    .outerRadius(nodeRadius);

  // Draw the nodes on the timeline
  nodeGroup.selectAll(".node")
    .data(nodes.map(node => node.id))
    .join("g")
    .attr("class", "node")
    .attr("transform", d => {
      const year = nodes.find(node => node.id === d).year;
      return `translate(${xScale(year)}, ${yScale(years[year].indexOf(d))})`;
    })
    .each(function(d) {
      drawNode(d3.select(this), colorCategory, arc, colorScale)
    })
    .on("click", function(event, d) {
      showNetworkModal(d);
    })
    .on("mouseover", function(event, d) {
      // Show the tooltip next to the node
      nodeTooltip.style("visibility", "visible");
      nodeTooltip.style("left", `${event.pageX + 15}px`);
      nodeTooltip.style("top", `${event.pageY}px`);

      // Populate the tooltip with the node data
      const entry = getDataEntry(d);
      nodeTooltip.html(`
        <strong>Study ${entry["ID"]}</strong>
        <p>${entry["Main Author"]} (${entry["Year"]})</p>
        <p>Location: ${entry["Location"]}</p>
        `);
        
      // Highlight the node and its connections
      highlightNode(d, nodeRadius, citationMode === "cited-by" || citationMode === "cites");
    })
    .on("mouseout", function(event, d) {
      // Hide the tooltip when the mouse leaves the node
      nodeTooltip.style("visibility", "hidden");
      removeHighlighting(nodeRadius);
    });

  
  const nodeTooltip = d3.select("#timeline-graph-container").append("div")
    .attr("class", "node-tooltip")
    .style("visibility", "hidden");

  // Draw the links between the nodes
  if (showSharedAuthors === "true") {
    linkGroup.selectAll(".link .coauthor")
      .data(coauthorLinks)
      .join("path")
      .attr("class", "coauthor link")
      .attr("d", d => drawLink(d));
  };

  if (citationMode === "both" || citationMode === "cites") {
    linkGroup.selectAll(".link .citing")
      .data(citingLinks)
      .join("path")
      .attr("class", "citing link")
      .attr("d", d => drawLink(d));
  };

  if (citationMode === "both" || citationMode === "cited-by") {
    linkGroup.selectAll(".link .cited-by")
      .data(citedByLinks)
      .join("path")
      .attr("class", "cited-by link")
      .attr("d", d => drawLink(d));
  }

  function drawLink(d) {
    const sourceNode = nodes.find(node => node.id === d.sourceID);
    const targetNode = nodes.find(node => node.id === d.targetID);
    const sourceX = xScale(sourceNode.year);
    const targetX = xScale(targetNode.year);
    const sourceY = yScale(years[sourceNode.year].indexOf(sourceNode.id));
    const targetY = yScale(years[targetNode.year].indexOf(targetNode.id));

    if (sourceX === targetX) {
      // If the souce and target are in the same year, draw an arc
      const midY = (sourceY + targetY) / 2;
      return `M ${sourceX},${sourceY} Q ${Math.min(sourceX + xScale.step(), $("#timeline-graph-container").width() - margin.right / 2)},${midY} ${targetX},${targetY}`;
    } else {
      // For different years, create a bezier curve
      const dx = targetX - sourceX;
      const controlOffset = Math.min(Math.abs(dx) * 0.4, 100); // Limit control point offset
      
      // Calculate control points - higher curves for connections between distant years
      const controlX1 = sourceX + Math.sign(dx) * controlOffset;
      const controlY1 = sourceY - 40; // Curve upward
      const controlX2 = targetX - Math.sign(dx) * controlOffset;
      const controlY2 = targetY - 40; // Curve upward

      // If the source and target are in different years, draw a bezier curve
      return `M ${sourceX},${sourceY} C ${controlX1},${controlY1} ${controlX2},${controlY2} ${targetX},${targetY}`;
    };
  };

  // Add hover title to links
  linkGroup.selectAll(".citing")
    .append("title")
    .text(d => `[${d.sourceID}] cites [${d.targetID}]`);

  linkGroup.selectAll(".cited-by")
    .append("title")
    .text(d => `[${d.sourceID}] is cited by [${d.targetID}]`);

  linkGroup.selectAll(".coauthor")
    .append("title")
    .text(d => `[${d.sourceID}] shares authors with [${d.targetID}]`);

  // Create a legend for the colors
  createLegend(nodes.map(node => node.id), colorScale, colorCategory, $("#legend"));
}

$(document).ready(function() {
  drawTimelineGraph();

  $("#timeline-toggle-shared-authors").on("click", function() {
    showSharedAuthors = $(this).is(":checked").toString();
    window.sessionStorage.setItem("showSharedAuthors", showSharedAuthors);
    drawTimelineGraph();
  })

  $("input[name='citation-mode']").on("click", function() {
    citationMode = $(this).val();
    window.sessionStorage.setItem("citationMode", citationMode);
    drawTimelineGraph();
  });

  // Set the coloring strategy to the session storage
  $("#timelineColorCategory").on("change", function() {
    colorCategory = $(this).val();
    window.sessionStorage.setItem("colorCategory", colorCategory);
    drawTimelineGraph();
  });

  window.addEventListener("resize", function() {
    drawTimelineGraph();
  });

  $(".value-filter").on("change", function() {
    drawTimelineGraph();
  });

  $(".exclusive-filter").on("click", function() {
    drawTimelineGraph();
  });

  $(".range-slider").each(function() {
    this.noUiSlider.on("end", function() {
      drawTimelineGraph();
    })
  });

  // Handle clicks on the info circles in the connections modal
  $("#timelineConnectionsContainer").on("click", ".info-circle", function() {
    const id = $(this).data("id");

    // Close the network modal if it's open
    $("#timelineConnectionsModal").modal("hide");
    showStudyModal(id);
  });
})