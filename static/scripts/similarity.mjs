import {
  filterData,
  getDataEntry,
  showStudyModal,
  sortNodesByCategory,
} from "./dataUtility.mjs";
import {
  createLegend,
  highlightNode,
  removeHighlighting,
  drawNode,
} from "./d3DrawingUtility.mjs";

// Load the similarity data from the HTML element
const similarityData = $("#graphContainer").data("similarity");
// Load the categories of the dropdown menu
const filterCategories = $("body").data("filter-categories");
const excluded_categories = $("#categoryDropdownContainer").data(
  "excluded-categories"
);
const infoCirclePath = $("#graphContainer").data("info-circle-path");

// Define some texts for the tooltips
const abstractTooltip =
  "This visualization shows semantic similarity between paper abstracts. Similarities were calculated using Google Gemini embeddings (gemini-embedding-exp-03-07) with cosine similarity and then z-standardized. Values above 0 indicate above-average similarity (0=mean, 1=one standard deviation above mean). Higher thresholds show only the most similar papers.";
const databaseTooltip =
  "This visualization shows similarity between studies based on features extracted from the database. Features were normalized and similarity was calculated based on their values.";

const abstractStudyIDs = similarityData["abstract_study_ids"];
const abstractMatrix = similarityData["abstract_matrix"];
const databaseStudyIDs = similarityData["database_study_ids"];
const databaseMatrix = similarityData["database_matrix"];

// Set the default similarity type from session storage or fallback to "database"
let similarityType =
  window.sessionStorage.getItem("similarityType") || "database";
$(`input[value='${similarityType}']`).prop("checked", true);

// Add tooltip text based on the selected similarity type
$("#thresholdInfoIcon").attr(
  "title",
  similarityType === "abstract" ? abstractTooltip : databaseTooltip
);

// Populate the color nodes dropdown menu
filterCategories.forEach((category) => {
  if (excluded_categories.includes(category)) return;
  const shortCategory = category.split("_").pop();
  $("#similarityColorCategory").append(
    `<option value="${category}">${shortCategory}</option>`
  );
});

let colorCategory = window.sessionStorage.getItem("colorCategory") || "";
$(`#similarityColorCategory > option[value="${colorCategory}"]`).prop(
  "selected",
  true
);

let similarityThreshold =
  parseFloat(window.sessionStorage.getItem("similarityThreshold")) || 1;
// Set the displayed threshold value in the UI
$("#thresholdValue").text(similarityThreshold.toFixed(2));

// Create the slider
const slider = document.getElementById("thresholdSlider");
noUiSlider
  .create(slider, {
    start: [similarityThreshold], // Default to 1 steddev
    connect: [true, false], // Connect to the left
    range: {
      min: -3, // Typically -3 standard deviations
      max: 3, // Typically +3 standard deviations
    },
    step: 0.1,
    tooltips: [true], // Show tooltip
    format: {
      to: function (value) {
        return value.toFixed(2);
      },
      from: function (value) {
        return parseFloat(value);
      },
    },
  })
  .on("change", function (values, handle) {
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
  const connectedNodes = links
    .filter((link) => link.sourceID === nodeID || link.targetID === nodeID)
    .map((link) => {
      return {
        id: link.sourceID === nodeID ? link.targetID : link.sourceID,
        similarity: link.value,
      };
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
            <th>Main Author</th>
            <th>Year</th>
            <th>Location</th>
            <th>Input Body Part</th>
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
            <td>${nodeData["Input Body Part"]}</td>
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
          ${
            connectedNodes.length > 0
              ? connectedNodes
                  .map((node) => {
                    const nodeData = getDataEntry(node.id);
                    return `
              <tr>
                <td><img src="${infoCirclePath}" alt="Info cirle for this row" title="Information about this row" data-ID=${
                      nodeData["ID"]
                    } class="info-circle network-information"/></td>
                <td>${nodeData["ID"]}</td>
                <td>${nodeData["Main Author"]}</td>
                <td>${nodeData["Year"]}</td>
                <td>${nodeData["Location"]}</td>
                <td>${nodeData["Input Body Part"]}</td>
                <td>${nodeData["Gesture"]}</td>
                <td><strong>${node.similarity.toFixed(2)}</strong></td>
              </tr>
            `;
                  })
                  .join("")
              : `<tr><td colspan="8" class="text-center">No connected studies found.</td></tr>`
          }
        </tbody>
      </table>
    </div>
  `;
  // Add information about the total number of connections
  const totalConnectionsHTML = `<p class="text-muted mt-2">Total connections: ${connectedNodes.length}</p>`;

  // Append to the connections container
  $("#connectionsContainer").empty();
  $("#connectionsContainer").html(sourceHTML);
  $("#connectionsContainer").append(connectionsHTML);
  $("#connectionsContainer").append(totalConnectionsHTML);

  // Show the modal
  $("#connectionsModal").modal("show");
}

function findSimilarStudies(links) {
  const modalID = window.sessionStorage.getItem("modalID");
  if (modalID) {
    openNetworkDetails(modalID, links);
  }
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
  const { sortedNodes, colorScale } = sortNodesByCategory(
    studyIDs,
    $("#similarityColorCategory").val()
  );

  // Only check each pair once (i < j)
  for (let i = 0; i < sortedNodes.length; i++) {
    for (let j = i + 1; j < sortedNodes.length; j++) {
      const nodeA = sortedNodes[i];
      const nodeB = sortedNodes[j];

      const similarity =
        similarityMatrix[parseInt(nodeA) - 1][parseInt(nodeB) - 1];
      if (similarity && similarity >= threshold) {
        links.push({
          sourceID: nodeA,
          targetID: nodeB,
          value: similarity,
        });
      }
    }
  }

  return { sortedNodes, links, colorScale };
}

// Gets the current similarity data based on the selected type and the selected filters so only active studies are included, returns an object with the study IDs and the similarity matrix like this: {studyIDs: [...], similarityMatrix: [[...]]}
function getCurrentSimilarityData() {
  const filters = JSON.parse(window.sessionStorage.getItem("filters"));
  // Get the IDs of all data studies that are currently active based on the selected filters
  const activeDataIDs = filterData(filters).map((item) =>
    item["ID"].toString()
  );

  if (similarityType === "abstract") {
    return {
      studyIDs: abstractStudyIDs.filter((id) => activeDataIDs.includes(id)),
      similarityMatrix: abstractMatrix,
    };
  } else if (similarityType === "database") {
    return {
      studyIDs: databaseStudyIDs.filter((id) => activeDataIDs.includes(id)),
      similarityMatrix: databaseMatrix,
    };
  }
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
  $("#legend").empty();

  const { sortedNodes, links, colorScale } = generateGraphData(threshold);
  const nodes = [...sortedNodes];

  // If there are no nodes, do not draw the graph
  if (nodes.length === 0) {
    $("#graphContainer").append(
      "<p class='text-center m-2 p-0'>No studies available for the selected sidebar filters. Please select some of the criteria from the sidebar at the right.</p>"
    );
    return;
  }

  // Determine graph dimensions
  const useULayout = nodes.length > 50; // Use U-Layout for larger graphs

  // Breakpoint for vertical alignment of axes
  const alignVertically = window.innerWidth <= 850;

  // Define constants for the layout
  const margin = alignVertically
    ? { top: 10, right: 5, bottom: 10, left: 5 }
    : { top: 10, right: 20, bottom: 10, left: 20 };

  const containerWidth = $("#graphContainer").width();
  const headerHeight = $("header").outerHeight(true) || 0;
  const controlsHeight = $(".controls").outerHeight(true) || 0;
  const visualizationWarningHeight =
    window.innerWidth <= 850
      ? $("#visualization-warning").outerHeight(true) || 0
      : 0;
  $("#graphContainer").height(
    alignVertically
      ? "120vh"
      : `calc(90vh - ${
          headerHeight + controlsHeight + visualizationWarningHeight
        }px)`
  );

  // Create SVG with calculated dimensions
  const svg = d3
    .select("#graphContainer")
    .append("svg")
    .attr("width", "100%")
    .attr("height", "100%")
    .attr(
      "viewBox",
      `${alignVertically ? 0 : containerWidth * 0.2} ${
        alignVertically ? 0 : -$("#graphContainer").height() * 0.2
      } ${containerWidth} ${
        alignVertically
          ? $("#graphContainer").height()
          : $("#graphContainer").height() * 1.4
      }`
    );

  // Choose layout based on number of nodes
  const layoutFunction = useULayout ? drawULayout : drawStandardLayout;
  layoutFunction(svg, margin, { nodes, links }, colorScale, !alignVertically);

  // Draw the legend
  createLegend(
    nodes,
    colorScale,
    $("#similarityColorCategory").val(),
    $("#legend")
  );

  findSimilarStudies(links);
}

function drawULayout(
  container,
  margin,
  graphData,
  colorScale,
  alignHorizontal
) {
  const { nodes, links } = graphData;

  const height = parseInt($("svg").height()) - margin.top - margin.bottom;
  const width = alignHorizontal
    ? parseInt($("svg").width()) * 1.4 - margin.left - margin.right
    : parseInt($("svg").width()) - margin.left - margin.right;
  const firstAxisPos = alignHorizontal ? height / 4 : width / 4;
  const axisMiddle = alignHorizontal ? height / 2 : width / 2;

  // Base node radius
  const nodeRadius = alignHorizontal ? Math.min(8, width / 150) : 6;

  // Split the nodes into two groups based on their IDs
  const firstNodes = nodes.filter(
    (node) => nodes.indexOf(node) <= nodes.length / 2
  );
  const secondNodes = nodes.filter(
    (node) => nodes.indexOf(node) > nodes.length / 2
  );

  const responsiveFontSize = getComputedStyle(document.body)
    .getPropertyValue("--resp-font-ticks")
    .trim();

  // Create a scale for the top nodes
  const firstScale = d3
    .scalePoint()
    .domain(firstNodes)
    .rangeRound([0, alignHorizontal ? width : height]);

  // Create a scale for the bottom nodes
  const secondScale = d3
    .scalePoint()
    .domain(secondNodes)
    .rangeRound([0, alignHorizontal ? width : height]);

  // Create an arc generator for the nodes
  const arc = d3.arc().innerRadius(0).outerRadius(nodeRadius);

  // Create the top axis for the nodes
  const firstAxis = alignHorizontal
    ? d3
        .axisTop(firstScale)
        .tickValues(firstNodes)
        .tickFormat((d) => "")
        .tickSize(0)
        .tickPadding(-4)
    : d3
        .axisLeft(firstScale)
        .tickValues(firstNodes)
        .tickFormat((d) => "")
        .tickSize(0)
        .tickPadding(8);

  // Create the bottom axis for the nodes
  const secondAxis = alignHorizontal
    ? d3
        .axisBottom(secondScale)
        .tickValues(secondNodes)
        .tickFormat((d) => "")
        .tickSize(0)
        .tickPadding(-4)
    : d3
        .axisRight(secondScale)
        .tickValues(secondNodes)
        .tickFormat((d) => "")
        .tickSize(0)
        .tickPadding(8);

  // Append group element for zooming
  const g = container
    .append("g")
    .attr("transform", `translate (${margin.left}, ${margin.top})`);

  // Draw the top axis
  g.append("g")
    .attr(
      "transform",
      alignHorizontal
        ? `translate(0, ${firstAxisPos})`
        : `translate(${firstAxisPos}, 0)`
    ) // Position the first Axis
    .attr("class", "top-axis")
    .call(firstAxis);

  // Draw the bottom axis
  g.append("g")
    .attr(
      "transform",
      alignHorizontal
        ? `translate(0, ${3 * firstAxisPos})`
        : `translate(${3 * firstAxisPos}, 0)`
    ) // Position the axis at the bottom
    .attr("class", "bottom-axis")
    .call(secondAxis);

  // Add info circle and label to top axis ticks
  container.selectAll(".top-axis text").html((d) => {
    const label = formatTickLabel(d);
    const infoCircle = '<tspan class="info-circle">ⓘ </tspan>';
    const labelSpan = `<tspan>${label}</tspan>`;

    return alignHorizontal
      ? `${labelSpan} ${infoCircle}`
      : `${infoCircle} ${labelSpan}`;
  });

  // Add info circle and label to bottom axis ticks
  container.selectAll(".bottom-axis text").html((d) => {
    const label = formatTickLabel(d);
    const infoCircle = '<tspan class="info-circle">ⓘ </tspan>';
    const labelSpan = `<tspan>${label}</tspan>`;

    return alignHorizontal
      ? `${infoCircle} ${labelSpan}`
      : `${labelSpan} ${infoCircle}`;
  });

  // Rotate the axis labels for better readability and adjust the position for bigger screens
  if (alignHorizontal) {
    container
      .select(".top-axis")
      .selectAll("text")
      .attr("text-anchor", "start")
      .attr("transform", "rotate(-90)")
      .attr("dx", "2em");
  }

  // Rotate the axis labels for better readability for bigger screens
  if (alignHorizontal) {
    container
      .select(".bottom-axis")
      .selectAll("text")
      .attr("text-anchor", "end")
      .attr("transform", "rotate(-90)")
      .attr("dx", "-2em"); // Adjust label position
  }

  // Add click event to the axis ticks, so that clicking on a node opens the study modal
  d3.selectAll(".tick")
    .on("click", function (event, d) {
      showStudyModal(d);
    })
    .style("cursor", "pointer")
    .style("font-size", responsiveFontSize)
    .style("user-select", "none"); // Change cursor to pointer for better UX

  // Create a group for the links
  const linkGroup = g.append("g").attr("class", "links");

  // Create a group for the top and bottom nodes
  const nodeGroup = g.append("g").attr("class", "nodes");

  // Draw the top nodes and add click and hover events
  nodeGroup
    .selectAll(".node")
    .data(firstNodes, (d) => d)
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("transform", (d) =>
      alignHorizontal
        ? `translate(${firstScale(d)}, ${firstAxisPos})`
        : `translate(${firstAxisPos}, ${firstScale(d)})`
    )
    .each(function (d) {
      drawNode(d3.select(this), colorCategory, arc, colorScale);
    })
    .on("click", function (event, d) {
      openNetworkDetails(d, links);
    })
    .on("mouseover", function (event, d) {
      highlightNode(d, nodeRadius);
    })
    .on("mouseout", () => removeHighlighting(nodeRadius));

  // Draw the bottom nodes and add click and hover events
  nodeGroup
    .selectAll(".node")
    .data(secondNodes, (d) => d)
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("transform", (d) =>
      alignHorizontal
        ? `translate(${secondScale(d)}, ${3 * firstAxisPos})`
        : `translate(${3 * firstAxisPos}, ${secondScale(d)})`
    )
    .each(function (d) {
      drawNode(d3.select(this), colorCategory, arc, colorScale);
    })
    .on("click", function (event, d) {
      openNetworkDetails(d, links);
    })
    .on("mouseover", function (event, d) {
      highlightNode(d, nodeRadius);
    })
    .on("mouseout", () => removeHighlighting(nodeRadius));

  // Draw the links
  linkGroup
    .selectAll(".link")
    .data(links)
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("d", (d) => {
      // Check on which axis the source and target nodes are located
      const isSourceFirst = firstNodes.includes(d.sourceID);
      const isTargetFirst = firstNodes.includes(d.targetID);

      // Get scale based on node position (first or second group)
      const sourceScale = isSourceFirst ? firstScale : secondScale;
      const targetScale = isTargetFirst ? firstScale : secondScale;

      // Get positions based on orientation and scale
      const sourceX = alignHorizontal
        ? sourceScale(d.sourceID)
        : isSourceFirst
        ? firstAxisPos
        : 3 * firstAxisPos;
      const targetX = alignHorizontal
        ? targetScale(d.targetID)
        : isTargetFirst
        ? firstAxisPos
        : 3 * firstAxisPos;
      const sourceY = alignHorizontal
        ? isSourceFirst
          ? firstAxisPos
          : 3 * firstAxisPos
        : sourceScale(d.sourceID);
      const targetY = alignHorizontal
        ? isTargetFirst
          ? firstAxisPos
          : 3 * firstAxisPos
        : targetScale(d.targetID);

      // Create the path
      if (alignHorizontal) {
        // When the nodes are on the same horizontal line
        if (sourceY === targetY) {
          const midPointY =
            axisMiddle + (isSourceFirst ? margin.top : -margin.top) * 15;
          return `M ${sourceX} ${sourceY} Q ${
            (sourceX + targetX) / 2
          } ${midPointY}, ${targetX} ${targetY}`;
        }
        // Normal case - nodes on different horizontal lines
        return `M ${sourceX} ${sourceY} C ${sourceX} ${axisMiddle}, ${targetX} ${axisMiddle}, ${targetX} ${targetY}`;
      } else {
        // When the nodes are on the same vertical line
        if (sourceX === targetX) {
          const midPointX =
            axisMiddle + (isSourceFirst ? margin.left : -margin.right) * 20;
          return `M ${sourceX} ${sourceY} Q ${midPointX} ${
            (sourceY + targetY) / 2
          }, ${targetX} ${targetY}`;
        }
        // Normal case - nodes on different vertical lines
        return `M ${sourceX} ${sourceY} C ${axisMiddle} ${sourceY}, ${axisMiddle} ${targetY}, ${targetX} ${targetY}`;
      }
    });

  // Add tooltips to the links
  linkGroup
    .selectAll(".link")
    .append("title")
    .text(
      (d) =>
        `${
          similarityType === "database" ? "Database" : "Abstract"
        } Similarity: ${d.value.toFixed(2)} between [${d.sourceID}] and [${
          d.targetID
        }]`
    );

  // Add zoom for smaller screen widths
  const mobileQuery = window.matchMedia("(max-width: 850px)");

  if (mobileQuery.matches) {
    const zoom = d3
      .zoom()
      .scaleExtent([0.8, 10])
      .on("zoom", ({ transform }) => {
        // On mobile allow panning/zooming
        const x = margin.left + transform.x;
        const y = margin.top + transform.y;
        const k = transform.k;
        g.attr("transform", `translate(${x}, ${y}) scale(${k})`);
      });

    container.call(zoom).call(zoom.transform, d3.zoomIdentity);
  }
}

// Draws the standard layout for the similarity graph
function drawStandardLayout(
  container,
  margin,
  graphData,
  colorScale,
  alignHorizontal
) {
  const { nodes, links } = graphData;

  // Define constants for the layout
  const height = parseInt($("svg").height()) - margin.top - margin.bottom;
  const width = parseInt($("svg").width()) - margin.left - margin.right;
  const axisMiddle = alignHorizontal ? height / 2 : width / 2;

  // Base node radius
  const nodeRadius = 7;

  // Create a scale for the node positions
  const nodeScale = d3
    .scalePoint()
    .domain(nodes)
    .rangeRound([0, alignHorizontal ? width : height]);

  // Create an axis for the nodes to be displayed horizontally
  const axis = alignHorizontal
    ? d3
        .axisBottom(nodeScale)
        .tickValues(nodes)
        .tickFormat((d) => "")
        .tickSize(0)
        .tickPadding(-4)
    : d3
        .axisLeft(nodeScale)
        .tickFormat((d) => "")
        .tickSize(0)
        .tickPadding(8);

  const responsiveFontSize = getComputedStyle(document.body)
    .getPropertyValue("--resp-font-ticks")
    .trim();

  // Append group element for zooming
  const g = container.append("g");

  // Draw the axis
  g.append("g")
    .attr("class", "axis")
    .attr(
      "transform",
      alignHorizontal
        ? `translate(0, ${axisMiddle})`
        : `translate(${axisMiddle}, 0)`
    ) // Position the axis in the middle of the graph
    .call(axis);

  d3.selectAll("text").html(
    (d) =>
      `<tspan class="info-circle">ⓘ </tspan><tspan>${formatTickLabel(
        d
      )}</tspan>`
  );

  // Rotate the axis labels for better readability and adjust the position
  if (alignHorizontal) {
    d3.selectAll("text")
      .attr("text-anchor", "end")
      .attr("transform", "rotate(-90)")
      .attr("dx", "-2em")
      .style("font-size", responsiveFontSize)
      .style("user-select", "none");
  }

  // Add click event to the axis ticks, so that clicking on a node opens the study modal
  d3.selectAll(".tick")
    .on("click", function (event, d) {
      showStudyModal(d);
    })
    .style("cursor", "pointer"); // Change cursor to pointer for better UX

  // Create a group for the links
  const linkGroup = g.append("g").attr("class", "links");

  // Create a group for the nodes
  const nodeGroup = g
    .append("g")
    .attr(
      "transform",
      alignHorizontal
        ? `translate(0, ${axisMiddle})`
        : `translate(${axisMiddle}, 0)`
    )
    .attr("class", "nodes");

  const arc = d3.arc().innerRadius(0).outerRadius(nodeRadius);

  // Draw the nodes and add click and hover events
  nodeGroup
    .selectAll(".node")
    .data(nodes)
    .join("g")
    .attr("class", "node")
    .attr("transform", (d) =>
      alignHorizontal
        ? `translate(${nodeScale(d)}, 0)`
        : `translate(0, ${nodeScale(d)})`
    )
    .each(function (d) {
      drawNode(d3.select(this), colorCategory, arc, colorScale);
    })
    .on("click", function (event, d) {
      openNetworkDetails(d, links);
    })
    .on("mouseover", function (event, d) {
      highlightNode(d, nodeRadius);
    })
    .on("mouseout", () => removeHighlighting(nodeRadius));

  // Draw the links
  linkGroup
    .selectAll(".link")
    .data(links)
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("d", (d) => {
      if (alignHorizontal) {
        const sourceX = nodeScale(d.sourceID);
        const targetX = nodeScale(d.targetID);
        const midX = (sourceX + targetX) / 2;
        const arcHeight = Math.min(
          Math.abs(sourceX - targetX) * 0.4,
          height / 3
        );

        // Draw a curved path between nodes
        return `M ${sourceX} ${axisMiddle} Q ${midX} ${
          axisMiddle - arcHeight
        }, ${targetX} ${axisMiddle}`;
      } else {
        const sourceY = nodeScale(d.sourceID);
        const targetY = nodeScale(d.targetID);
        const midY = (sourceY + targetY) / 2;
        const arcWidth = Math.min(Math.abs(sourceY - targetY) * 2, width / 2);

        // Draw a curved path between nodes
        return `M ${axisMiddle} ${sourceY} Q ${
          axisMiddle + arcWidth
        } ${midY}, ${axisMiddle} ${targetY}`;
      }
    });

  // Add tooltips to the links
  linkGroup
    .selectAll(".link")
    .append("title")
    .text(
      (d) =>
        `${
          similarityType === "database" ? "Database" : "Abstract"
        } Similarity: ${d.value.toFixed(2)} between [${d.sourceID}] and [${
          d.targetID
        }]`
    );

  const mobileQuery = window.matchMedia("(max-width: 850px)");

  if (mobileQuery.matches) {
    const zoom = d3
      .zoom()
      .scaleExtent([0.8, 10])
      .on("zoom", ({ transform }) => {
        // On mobile allow panning/zooming
        const x = margin.left + transform.x;
        const y = margin.top + transform.y;
        const k = transform.k;
        g.attr("transform", `translate(${x}, ${y}) scale(${k})`);
      });

    container.call(zoom).call(zoom.transform, d3.zoomIdentity);
  }
}

/*
  Interaction section
  Here the event listeners for the interaction possibilities of the similarity graph are set up
*/
$(document).ready(function () {
  drawGraph(similarityThreshold); // Initial draw of the graph

  // Add event listener for similarity type change
  $("input[name='similarityType']").on("change", function () {
    similarityType = $(this).val();
    window.sessionStorage.setItem("similarityType", similarityType);

    // Update the tooltip text based on the selected similarity type
    $("#thresholdInfoIcon").attr(
      "title",
      similarityType === "abstract" ? abstractTooltip : databaseTooltip
    );
    drawGraph(similarityThreshold); // Redraw the graph with the new similarity type
  });

  // Add event listener for the category dropdown change
  $("#similarityColorCategory").on("change", function () {
    colorCategory = $(this).val();
    window.sessionStorage.setItem("colorCategory", colorCategory);
    drawGraph(similarityThreshold); // Redraw the graph with the new color category
  });

  window.addEventListener("resize", function () {
    drawGraph(similarityThreshold); // Redraw the graph on window resize
  });

  $(".value-filter").on("change", function () {
    drawGraph(similarityThreshold); // Redraw the graph when a value filter changes
  });

  $(".exclusive-filter").on("click", function () {
    drawGraph(similarityThreshold); // Redraw the graph when an exclusive filter is applied
  });

  $("#connectionsContainer").on("click", ".info-circle", function () {
    const id = $(this).data("id");

    if (this.classList.contains("network-information")) {
      $(`#connectionsModal`).modal("hide"); // Hide the connections modal
    }

    showStudyModal(id);
  });

  $(".range-slider").each(function () {
    this.noUiSlider.on("end", function (values, handle) {
      drawGraph(similarityThreshold);
    });
  });

  $("#connectionsModal").on("hidden.bs.modal", function () {
    window.sessionStorage.removeItem("modalID");
  });
});
