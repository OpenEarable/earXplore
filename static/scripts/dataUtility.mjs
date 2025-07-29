/**
 * The data passed from the backend formated as an array of objects.
 * 
 * @constant
 * @type {Array}
 * @see parseData
 */
const data = parseData($("body").data("data"));

/**
 * The categories for which parenthises should be removed when filtering.
 * 
 * @constant
 * @type {Array}
 */
const parenthicalCategories = $("body").data("parenthical-categories");

const filterCategories = $("body").data("filter-categories");

/**
 * The abstracts for the studies passed from the backend.
 * 
 * @constant
 * @type {Array}
 */
const abstracts = $("body").data("abstracts");

/**
 * An object mapping specific string labels to their corresponding numeric order or priority.
 * Used for sorting or categorizing qualitative values in a standardized way.
 *
 * Keys represent qualitative descriptors (e.g., 'Yes', 'No', 'Low', etc.).
 * Values are integers indicating the order or priority for each descriptor.
 *
 * @constant
 * @type {Object.<string, number>}
 */
const specialOrders = {'Yes': 1, 'Partly': 2, 'No': 3, 'Low': 1, 'Medium': 2, 'High': 3, 'Semantic': 1, 'Coarse': 2, 'Fine': 3, 'N/A': 4, 'Yes (Performance Loss)': 2, 'Visual Attention': 2};

const defaultColors = ['#d1615d', '#5778a4', '#6a9f58', '#e49444', '#85b6b2', '#e7ca60', '#a87c9f', '#f1a2a9', '#967662', '#b8b0ac'];
const brighterColors = defaultColors.map(color => d3.color(color).brighter(0.7).hex());
const darkerColors = defaultColors.map(color => d3.color(color).darker(0.7).hex());
/**
 * An array containing a combined set of colors from the default, brighter, and darker color palettes.
 * 
 * @constant
 * @type {string[]}
 * @see defaultColors
 * @see brighterColors
 * @see darkerColors
 */
const colorPalette = [...defaultColors, ...brighterColors, ...darkerColors];


/**
 * The default color used in the application, represented as a hexadecimal string.
 * This value is derived from the RGB color "rgb(184, 148, 145)" using D3's color utility.
 * 
 * @constant
 * @type {string}
 */
const defaultColor = d3.color("rgb(184, 148, 145)").hex();

/**
 * Updates the filters in the session storage to the provided filters object.
 * @param {Object} filters 
 */
function updateFilters(filters) {
  window.sessionStorage.setItem("filters", JSON.stringify(filters));
}

/**
 * Converts all occurrences of the "€" character in the given HTML ID to spaces.
 *
 * @param {string} htmlID - The HTML ID string to convert.
 * @returns {string} The converted string with "€" replaced by spaces.
 */
function convertToID(htmlID) {
  return htmlID.replaceAll("€", " ");
}

function getCategory(htmlID) {
  return convertToID(htmlID).split("--")[1];
}

function getValue(htmlID) {
  return convertToID(htmlID).split("--")[0];
}

/*
 * This section capsulates the utility functions for parsing and retrieving data.
 */

/**
 * Parses a string containing multiple object literals into an array of objects.
 *
 * The input string should contain objects in the format `{key: 'value'}` separated by any characters.
 * Single quotes in object values are replaced with double quotes to allow JSON parsing.
 *
 * @param {string} dataString - The string containing object literals to parse.
 * @returns {Object[]} An array of parsed objects.
 */
function parseData(dataString) {
  // Parse the data string into an array of objects
  const dataRegex = /{[^}]*?}/g;
  const dataMatches = [...dataString.matchAll(dataRegex)];
  const jsonData = [];
  dataMatches.forEach((match) => {
    jsonData.push(JSON.parse(match[0].replaceAll(/'/g, '"')));
  });
  return jsonData;
}

/**
 * Retrieves a data entry from the {@link data} by its ID.
 * If a category is specified, returns the value of that category for the found entry.
 * If no category is specified, returns the entire entry object.
 *
 * @param {string|number} id - The ID of the data entry to retrieve.
 * @param {string} [category] - Optional. The category/property to retrieve from the entry.
 * @returns {Object|any} The found data entry object, or the value of the specified category, or undefined if not found.
 */
function getDataEntry(id, category) {
  return category == undefined ?
    data.find(item => item["ID"].toString() === id.toString()) :
    data.find(item => item["ID"].toString() === id.toString())[category];
}

/**
 * Cleans a comma-separated data string based on the provided category.
 * - Splits the data string into individual values.
 * - If the category is in {@link parenthicalCategories}, removes any text after '(' in each value.
 * - Trims whitespace from each value.
 *
 * @param {string} category - The category used to determine if parenthetical cleaning is needed.
 * @param {string} dataString - The comma-separated string of data values to clean.
 * @returns {string[]} An array of cleaned data values.
 */
function cleanDataString(category, dataString) {
  // Split the data string by commas to get individual values
  let dataValues = dataString.split(",");

  // Remove parentheses for parenthical categories
  if (parenthicalCategories.includes(category)) {
    dataValues = dataValues.map(value => value.split("(")[0]);
  }

  // Remove whitespace from the values
  dataValues = dataValues.map(value => value.trim());

  return dataValues;
}

/**
 * Filters the global {@link data} array based on the provided categories and filter criteria.
 * Each data entry must match at least one value for each category to be included in the result.
 * For range filters, the data value must fall within the specified range.
 *
 * Uses {@link getActiveFilters} to retrieve active filters for each category.
 *
 * @param {string[]} allCategories - Array of category names to filter by.
 * @param {Object} filters - Object containing filter criteria, including value and range filters.
 * @returns {Object[]} Filtered array of data entries matching the filter criteria.
 */
function filterData(filters) {
  // Each data entry has to match at least one value for each category to be included in the filtered data
  const activeData = data.filter(dataItem => {
    // Each category has to be checked
    return filterCategories.every(category => {
      const filterValues = getActiveFilters(category, filters);

      // For range filters, we need to check if the data falls within the specified range
      if (Object.keys(filters.rangeFilters).includes(category)) {
        return dataItem[category] >= filterValues[0] && dataItem[category] <= filterValues[1];
      }

      // Every other category is a value filter
      const dataValues = cleanDataString(category, dataItem[category].toString());

      // If there are no active filters for the category, we can skip the check
      if (filterValues.length === 0) {
        return false;
      }

      // If the category is in the exclusive filters, all values must be active
      if (filters.exclusiveFilters.includes(category)) {
        return dataValues.every(dataValue => filterValues.includes(dataValue));
      }

      // At least one value in the data must match one of the active filters for the category
      return dataValues.some(dataValue => filterValues.includes(dataValue));
    });
  });
  return activeData;
}

/**
 * Retrieves the active filters for a given category from the provided filters object.
 *
 * Depending on the category, this function handles value filters, range filters, and special cases for "Gesture" and "Keywords".
 * - For range filters, it returns the min and max values from {@link filters.rangeFilters}.
 * - For other categories, it extracts values from {@link filters.valueFilters} that match the given category.
 *
 * @param {string} category - The filter category to retrieve active filters for.
 * @param {Object} filters - The filters object containing {@link filters.valueFilters} and {@link filters.rangeFilters}.
 * @returns {Array} An array of active filter values for the specified category.
 */
function getActiveFilters(category, filters) {
  const valueFilters = filters.valueFilters;
  const rangeFilters = filters.rangeFilters;

  // create an array to hold the active filters
  const activeFilters = [];

  // For range filters add the min and max values to the active filters
  if (Object.keys(rangeFilters).includes(category)) {
    return rangeFilters[category];
  }

  // For every other category: populate the active filters with the value filters
  valueFilters.forEach(filter => {
    const [value, valueCategory] = filter.split("--");
    if (category === valueCategory) {
      activeFilters.push(value);
    }
  });

  return activeFilters;
}

/**
 * Sorts an array of nodes based on a specified category, returning the sorted nodes and a color scale function.
 * 
 * This function uses {@link getDataEntry} to extract category values for each node and {@link createColorScale} to generate a color scale for the unique values.
 * Nodes are sorted by the number of category values, then by the order of their values in the color scale, and finally by their IDs.
 * 
 * @param {Array<string>} nodes - The array of node IDs to sort.
 * @param {string} category - The category by which to sort the nodes.
 * @returns {{sortedNodes: Array<string>, colorScale: function}} An object containing the sorted nodes and a color scale function for the category values.
 */
function sortNodesByCategory(nodes, category) {
  if (!category) {
    return {sortedNodes: nodes, colorScale: function(value) {return defaultColor}}; // No category selected, return original nodes and a default color function
  }

  // Get the unique values for the selected category
  const uniqueValues = new Set();
  const valueMap = {};
  nodes.forEach(node => {
    // Get the values for the selected category from the data matching the node ID, category is defined at this point
    const values = cleanDataString(category, getDataEntry(node, category).toString());
    valueMap[node] = [];

    // Add each value to the value map and the unique values set
    values.forEach(value => {
      valueMap[node].push(value);
      uniqueValues.add(value);
    })
  });

  // Create a legend from the unique values
  const colorScale = createColorScale(uniqueValues);

  // Sorts nodes by:
  // 1. Number of values (ascending)
  // 2. First value's position in legend
  // 3. Second value's position in legend (if any)
  // Etc.
  const sortedNodes = nodes.sort((a, b) => {
    const valuesA = valueMap[a];
    const valuesB = valueMap[b];
    
    // First sort by number of values
    if (valuesA.length !== valuesB.length) {
      return valuesA.length - valuesB.length;
    }
    
    // Sort by values in order
    for (let i = 0; i < Math.min(valuesA.length, valuesB.length); i++) {
      const indexA = colorPalette.indexOf(colorScale(valuesA[i]));
      const indexB = colorPalette.indexOf(colorScale(valuesB[i]));
      
      if (indexA !== indexB) {
          return indexA - indexB;
      }
    }
    
    // Default to ID sort if everything else is equal
    return a.localeCompare(b);
  });

  return {sortedNodes, colorScale};
}

/*
 * This section capsulates the utility functions for a D3-based data visualization.
 */

/**
 * Creates a D3 ordinal color scale for a given category and its unique values.
 * The function sorts the unique values based on custom logic, including {@link specialOrders}
 * for certain categorical values and numeric sorting for specific categories.
 * 
 * @param {string} category - The name of the category for which the color scale is created.
 * @param {Iterable<string>} uniqueValues - An iterable of unique values within the category.
 * @returns {d3.ScaleOrdinal<string, string>} A D3 ordinal scale mapping each unique value to a color.
 */
function createColorScale(uniqueValues) {
  // Convert to an array
  const items =  Array.from(uniqueValues);
  
  // Sort the items based on the entries
  items.sort((a, b) => {
    // Check if every item can be parsed as a number
    if (items.every(item => !isNaN(item))) {
        // Parse as numbers for numeric comparison
        return Number(a) - Number(b);
    }
    
    // Use special order for specific values
    const orderA = specialOrders[a] || 0;
    const orderB = specialOrders[b] || 0;
    
    // First sort by special order
    if (orderA !== orderB) {
        return orderA - orderB;
    }
    
    // Then sort alphabetically
    return a.toLowerCase().localeCompare(b.toLowerCase());
  });

  // Create a scale for the colors based on the number of unique values
  const colorScale = d3.scaleOrdinal()
    .domain(items)
    .range(colorPalette);

  return colorScale;
};

/*
 * This section is about showing modals based on the data.
 */

/**
 * Displays a modal with detailed information about a study based on the provided study ID.
 * The modal is included in the base template, which is extended by every page.
 *
 * This function retrieves the study data entry, populates the modal with relevant information
 * (including panel-specific fields, keywords, and abstract), sets the study link, and shows the modal.
 *
 * @param {string|number} studyID - The unique identifier of the study to display information for.
 */
function showStudyModal(studyID) {
  // Find the data entry for the given ID
  const entry = getDataEntry(studyID.toString());

  // Set the header text of the modal
  $("#study-info-header").text(`Paper Info (ID: ${studyID})`);

  // All the selections here are present because the modal is rendered in the base template which every page extends
  const infoHTML = $(".panel").map((index, panel) => {
      // Skip the "Advanced Filters" panel
      if ($(panel).data("panel-value") === "Advanced Filters") {
        return;
      }

      const heading = $(panel).find("h3")[0].innerText;

      const filters = $(panel).find(".filter-group").map((index, filter) => $(filter).data("col")).get();

      let filtersHTML = filters
        .map(filter => `<strong>${filter.split("_").pop()}</strong>: ${entry[filter] || "N/A"}`)
        .join("<br />");
      if (heading === "General Information") {
        filtersHTML = `<strong>Main Author</strong>: ${entry["Main Author"] || "N/A"}<br />${filtersHTML}<br /><strong>Gesture</strong>: ${entry["Gesture"] || "N/A"}`;
      }

      const panelHTML = `<h5 class="study-info-panel-header">${heading}</h5>` + filtersHTML;
      
      return panelHTML;
  }).get();

  // Add Study Summary to the infoHTML
  infoHTML.push(`
    <h5 class="study-info-panel-header">Study Summary</h5>
    <strong>Title</strong>: ${titles.find(elem => elem["ID"] === entry["ID"])["Title"] || "N/A"}<br />
    <strong>Keywords</strong>: ${entry["Keywords"] || "N/A"}<br />
    <strong>Abstract</strong>: ${abstracts.find(elem => elem["ID"] === entry["ID"])["Abstract"] || "N/A"}<br />
  `)

  $(`#study-info-modal-body`).html(infoHTML.join("<br />"));

  // Add link to the study in the modal body
  $("#study-link").attr("href", entry["Study Link"]);

  // Show the modal
  $(`#study-info-modal`).modal("show");
}

export  {data, colorPalette, defaultColor, updateFilters, convertToID, getCategory, getValue, filterData, getActiveFilters, parseData, getDataEntry, showStudyModal, createColorScale, sortNodesByCategory, cleanDataString, specialOrders, defaultColors};