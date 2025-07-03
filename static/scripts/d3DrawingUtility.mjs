import { getDataEntry, cleanDataString, defaultColor } from './dataUtility.mjs';

const evenPie = d3.pie()
  .value(d => 1)

// Returns all the colors for a given node based on the selected category
function getColors(node, colorCategory, colorScale) {
  // If no category is selected, return the default color
  if (!colorCategory) {
    return [defaultColor];
  }

  const values = cleanDataString(colorCategory, getDataEntry(node, colorCategory).toString());
  const colors = values.map(value => colorScale(value)).filter(Boolean);

  return colors;
}

function drawNode(nodeSelection, colorCategory, arc, colorScale) {
  const colors = getColors(nodeSelection.data()[0], colorCategory, colorScale);
  const pieData = evenPie(colors);

  // Draw pie charts for each node with the colors from the color scale
  nodeSelection.selectAll(".pie")
    .data(pieData)
    .join("path")
    .attr("class", "pie")
    .attr("d", arc)
    .attr("fill", d => d.data)  // Use the color from the data
    .style("stroke"); 
}

/**
 * Highlights the node and its connected links in a D3 visualization.
 * The CSS classes for highlighting and blurring need to be defined
 * in the CSS separately for this to work.
 * 
 * - Highlights all links connected to the specified node.
 * - Blurs all nodes and links not involved with the specified node.
 * - Increases the radius of the highlighted node's pie chart.
 *
 * @param {string|number} nodeID - The ID of the node to highlight.
 * @param {number} nodeRadius - The base radius of the node, used to scale the highlight.
 */
function highlightNode(nodeID, nodeRadius, unidirectional) {
  // Highlight the links connected to the hovered node
  const highlightedLinks = d3.selectAll(".link")
    .filter(link => unidirectional ? link.sourceID === nodeID : (link.sourceID === nodeID || link.targetID === nodeID))
    .classed("highlighted-link", true);

  const involvedNodes = new Set();
  highlightedLinks.data().forEach(link => {
    involvedNodes.add(link.sourceID);
    involvedNodes.add(link.targetID);
  });
  involvedNodes.add(nodeID); // Also add the hovered node itself

  // Blur the other nodes
  d3.selectAll(".node")
    .filter(node => !involvedNodes.has(node))
    .classed("blurred", true);

  // Increase the radius of the highlighted node
  const arc = d3.arc()
    .innerRadius(0)
    .outerRadius(nodeRadius * 1.4);

  d3.selectAll(".node")
    .filter(node => node === nodeID)
    .selectAll(".pie")
    .attr("d", arc);

  // Blur the other links
  d3.selectAll(".link")
    .filter(link => link.sourceID !== nodeID && link.targetID !== nodeID)
    .classed("blurred", true);
}

/**
 * Removes all highlighting and blurring effects from nodes and links in a D3 visualization,
 * and resets the node radius to the specified default value. The CSS classes for highlighting
 * and blurring need to be defined in the CSS separately for this to work.
 *
 * @param {number} nodeRadius - The default radius to reset each node's arc to.
 */
function removeHighlighting(nodeRadius) {
  // Remove the highlight from the links connected to the hovered node
  d3.selectAll(".link")
    .classed("highlighted-link", false);

  // Remove the blur from the other links
  d3.selectAll(".link")
    .classed("blurred", false);

  // Remove the blur from the other nodes
  d3.selectAll(".node")
    .classed("blurred", false);

  // Reset the node radius to the default value
  const arc = d3.arc()
    .innerRadius(0)
    .outerRadius(nodeRadius);

  d3.selectAll(".node")
    .selectAll(".pie")
    .attr("d", arc);
}

/**
 * Creates and displays a legend for a data visualization based on the provided nodes and category.
 *
 * @param {Array<Object>} nodes - The array of data nodes to extract legend values from.
 * @param {function} colorScale - A function that maps legend values to color strings.
 * @param {string} category - The data category to visualize in the legend. If falsy, the legend is hidden.
 * @param {jQuery} legendContainer - The jQuery element where the legend will be rendered.
 *
 * @returns {void} - The function modifies the legendContainer to display the legend.
 */
function createLegend(nodes, colorScale, category, legendContainer) {
  // Skip legend if no category is selected
  if (!category) {
    legendContainer.hide();
    return;
  }

  // Add the legend title as the category name and a note
  legendContainer.append(`<h4 id="legendTitle">${category.split("_").pop()}</h3>`);
  legendContainer.append(`<p id="legendNote">Note: Studies with multiple values are shown as pie charts</p>`);

  const uniqueValues = new Set();
  for (const node of nodes) {
    const values = cleanDataString(category, getDataEntry(node, category).toString());
    values.forEach(value => uniqueValues.add(value));
  }

  const legendItems = $("<div id='legendItems'></div>");
  Array.from(uniqueValues).forEach(value => {
    const color = colorScale(value);
    if (color) {
      const box = $(`<div class='legendBox' style='background-color: ${color}; width: 0.8em; height: 0.8em;'></div>`);
      const text = $(`<div class='legendText'>${value}</div>`);
      const item = $("<div class='legendItem'></div>");
      item.append(box);
      item.append(text);

      legendItems.append(item);
    }
  });
  legendContainer.append(legendItems);

  legendContainer.show();
}

export {drawNode, highlightNode, removeHighlighting, createLegend};