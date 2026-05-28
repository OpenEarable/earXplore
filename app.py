from flask import Flask, render_template, request, jsonify, url_for, redirect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mailman import Mail, EmailMessage
from flask_wtf.csrf import CSRFProtect
from typing import List
from dotenv import load_dotenv
import pandas as pd
import json
import os
import mimetypes
import traceback
import yaml
import requests
mimetypes.add_type('application/javascript', '.mjs')

# Categories that should not be filtered for
EXCLUDED_SIDEBAR_CATEGORIES = []

# Categories that go in the metadata panel
METADATA_SIDEBAR_CATEGORIES = []

# Categories that are displayed as sliders in the sidebar, should be numerical !
SLIDER_CATEGORIES = []

# Categories that should have a "select/deselect all" button in the sidebar
SELECT_DESELECT_ALL_CATEGORIES = []

# Categories that should have an "exclusive filtering" button in the sidebar
EXCLUSIVE_FILTERING_CATEGORIES = []

# Panels that should have a "select/deselect all" button in the sidebar
SELECT_DESELECT_ALL_PANELS = []

# Panels that should be initially hidden in the sidebar
INITIALLY_HIDDEN_PANELS = []

# Columns that contain parentheses but only the part before the parentheses should be used for filtering
PARENTHICAL_COLUMNS = []

# Categories that should be displayed initially in the tabular and bar chart views 
# Do not delete the "INFO" category !
START_CATEGORY_FILTERS = json.dumps([])

# Categories whose explanations should be formatted in a special way
SPECIAL_FORMAT_EXPLANATIONS = []

# Columns for combined performance metrics filtering
PERFORMANCE_METRICS_COLUMNS = []

# Column name for device model custom filter
DEVICE_MODEL_COLUMN = ""

# Fixed answer options for device model filter
DEVICE_MODEL_OPTIONS = []

# Columns for which rare values (count < 2) should be grouped into "Other" in sidebar/charts/colors
OTHER_THRESHOLD_COLUMNS = []

# Computed at startup: { column: [list of rare values] }
OTHER_THRESHOLD_RARE_VALUES = {}

# Columns that use token-search UI instead of checkboxes (opt-in filter: empty = show all)
TOKEN_SEARCH_COLUMNS = []

# Computed at startup: { column: sorted list of unique individual options }
TOKEN_SEARCH_OPTIONS = {}

# Absolute path to the CSV database file — set by load_data() from the YAML config
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "datasets/data.csv")

app = Flask(__name__)

load_dotenv() # Load environment variables from .env file

# Path to the YAML configuration file used by all main views
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "configs", "earXplore_interaction.yaml")

# Configure Flask-Mail
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT") or 587)
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")

print(f"Mail server: {os.getenv('MAIL_SERVER')}")
print(f"TLS enabled: {os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'}")
print(f"Default sender: {os.getenv('MAIL_DEFAULT_SENDER')}")

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", os.urandom(24).hex())
mail = Mail(app)
csrf = CSRFProtect(app)

# Rate limiter — IP-based, no cookies or user tracking required.
# When running behind a reverse proxy (e.g. nginx), set BEHIND_PROXY=true in
# the server .env so the real client IP is read from X-Forwarded-For instead
# of always seeing 127.0.0.1, which would make the limit shared across all users.
if os.getenv("BEHIND_PROXY", "false").lower() == "true":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],          # no blanket limit on other routes
    storage_uri="memory://",    # in-memory; resets on restart — fine for single-worker
)

@app.errorhandler(429)
def ratelimit_handler(e):
    """Return JSON (not HTML) when the chat rate limit is exceeded."""
    return jsonify({
        "ok": False,
        "response": "You have reached the daily limit of 20 questions. Please come back tomorrow.",
    }), 429

# Template classes for sidebar panel
class Slider:
    def __init__(self, value:str, min_value:int, max_value:int, explanation:str = None, unbounded_max:bool = False):
        self.value = value
        self.min_value = min_value
        self.max_value = max_value
        self.explanation = explanation
        self.unbounded_max = unbounded_max

class Filter:
    def __init__(self, value:str, explanation:str = None, unique_values:List[str] = None, exclusive_filtering:bool = False, select_deselect_all:bool = False):
        self.value = value
        self.explanation = explanation
        self.unique_values = unique_values
        self.exclusive_filtering = exclusive_filtering
        self.select_deselect_all = select_deselect_all

class Panel:
    def __init__ (self, value:str, sliders:List[Slider] = None, filters:List[Filter] = None, select_deselect_buttons:bool = False, initial_visibility:str = "block"):
        self.value = value
        self.sliders = sliders if sliders is not None else []
        self.filters = filters if filters is not None else []
        self.select_deselect_buttons = select_deselect_buttons
        self.initial_visibility = initial_visibility
        self.performance_block = None  # Optional special block rendered at the bottom of the panel
        self.device_model_block = None  # Optional custom device model filter block
        self.token_search_block = []    # Optional token-search entries: [{column, label}, ...]

# custom sort the values of columns in the data
def custom_sort(values):
    special_orders = {'Yes': 1, 'Partly': 2, 'No': 3, 'Low': 1, 'Medium': 2, 'High': 3, 
                     'Semantic': 1, 'Coarse': 2, 'Fine': 3, 'N/A': 4, 'Yes (Performance Loss)': 2, 'Visual Attention': 2}  # Changed from 'nan' to 'N/A'
    sorted_values = sorted(values, key=lambda x: (special_orders.get(x, 0), 
                                               str(x).lower() if isinstance(x, str) else str(x)))
    return sorted_values

def filter_categories(data):
    # Filter out categories that should not be filtered for
    return [category for category in data[0].keys() if category not in EXCLUDED_SIDEBAR_CATEGORIES]

def load_data(config_path):
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        return f"Configuration file {config_path} not found"
    except yaml.YAMLError as e:
        return f"Error parsing configuration file {config_path}: {e}"
    
    database_path = config.get("database-path", "data.csv")
    explanations_path = config.get("explanations-path", "explanations.csv")
    global EXCLUDED_SIDEBAR_CATEGORIES, METADATA_SIDEBAR_CATEGORIES, SLIDER_CATEGORIES, SELECT_DESELECT_ALL_CATEGORIES, EXCLUSIVE_FILTERING_CATEGORIES, PARENTHICAL_COLUMNS, SELECT_DESELECT_ALL_PANELS, INITIALLY_HIDDEN_PANELS, START_CATEGORY_FILTERS, SPECIAL_FORMAT_EXPLANATIONS, PERFORMANCE_METRICS_COLUMNS, DEVICE_MODEL_COLUMN, DEVICE_MODEL_OPTIONS, OTHER_THRESHOLD_COLUMNS, OTHER_THRESHOLD_RARE_VALUES, TOKEN_SEARCH_COLUMNS, TOKEN_SEARCH_OPTIONS, DATABASE_PATH
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), database_path)
    EXCLUDED_SIDEBAR_CATEGORIES = config.get("excluded-sidebar-categories", [])
    METADATA_SIDEBAR_CATEGORIES = config.get("metadata-sidebar-categories", [])
    SLIDER_CATEGORIES = config.get("slider-categories", [])
    SELECT_DESELECT_ALL_CATEGORIES = config.get("select-deselect-all-categories", [])
    EXCLUSIVE_FILTERING_CATEGORIES = config.get("exclusive-filtering-categories", [])
    PARENTHICAL_COLUMNS = config.get("parenthical-columns", [])
    SELECT_DESELECT_ALL_PANELS = config.get("select-deselect-all-panels", [])
    INITIALLY_HIDDEN_PANELS = config.get("initially-hidden-panels", [])
    START_CATEGORY_FILTERS = json.dumps(["INFO"] + config.get("start-category-filters", []))
    SPECIAL_FORMAT_EXPLANATIONS = config.get("special-format-explanations", [])
    PERFORMANCE_METRICS_COLUMNS = config.get("performance-metrics-columns", [])
    # Performance metric columns are automatically excluded from the normal sidebar filter UI
    # and treated as parenthical — users only need to list them under performance-metrics-columns.
    for _col in PERFORMANCE_METRICS_COLUMNS:
        if _col not in EXCLUDED_SIDEBAR_CATEGORIES:
            EXCLUDED_SIDEBAR_CATEGORIES.append(_col)
        if _col not in PARENTHICAL_COLUMNS:
            PARENTHICAL_COLUMNS.append(_col)
    DEVICE_MODEL_COLUMN = config.get("device-model-column", "")
    DEVICE_MODEL_OPTIONS = config.get("device-model-options", [])
    OTHER_THRESHOLD_COLUMNS = config.get("other-threshold-columns", [])
    TOKEN_SEARCH_COLUMNS = config.get("token-search-columns", [])

    # Load data from CSV file into data variable
    try:
        csv_path = os.path.join(os.path.dirname(__file__), database_path)
        df = pd.read_csv(csv_path)
        df = df.fillna('N/A')  # Replace actual NaN values
        df = df.replace('nan', 'N/A')  # Replace string 'nan' values
        data = df.to_dict(orient="records")
    except FileNotFoundError:
        return "data.csv file not found"
    except pd.errors.EmptyDataError:
        return "data.csv file is empty"
    except Exception as e:
        return f"Error loading data.csv: {e}"
    
    # delete the 'Abstract' column from the data
    for data_entry in data:
        if 'Abstract' in data_entry:
            del data_entry['Abstract']

    # Compute rare values for other-threshold columns (values appearing fewer than 2 times)
    OTHER_THRESHOLD_RARE_VALUES = {}
    for col in OTHER_THRESHOLD_COLUMNS:
        counts = {}
        for row in data:
            raw = row.get(col, 'N/A')
            parts = [v.strip() for v in str(raw).split(',')]
            for part in parts:
                if part:
                    counts[part] = counts.get(part, 0) + 1
        OTHER_THRESHOLD_RARE_VALUES[col] = [v for v, c in counts.items() if c <= 2]

    # Compute unique individual options for token-search columns
    TOKEN_SEARCH_OPTIONS = {}
    for col in TOKEN_SEARCH_COLUMNS:
        options = set()
        for row in data:
            raw = row.get(col, 'N/A')
            if raw and str(raw) != 'N/A':
                for part in str(raw).split(','):
                    part = part.strip()
                    if part and part != 'N/A':
                        options.add(part)
        TOKEN_SEARCH_OPTIONS[col] = sorted(options, key=lambda x: x.lower())

    # Load explanations from CSV file into explanations variable
    try:
        csv_path = os.path.join(os.path.dirname(__file__), explanations_path)
        explanations_df = pd.read_csv(csv_path)
        explanations = dict(zip(explanations_df["Column"], explanations_df["Explanation"]))
    except FileNotFoundError:
        return "explanations.csv file not found"
    except pd.errors.EmptyDataError:
        return "explanations.csv file is empty"
    except KeyError:
        return "explanations.csv file is missing required columns"
    except Exception as e:
        return f"Error loading explanations.csv: {e}"

    return data, explanations

def load_abstracts_and_titles():
    """Load abstracts and titles from the dataset CSV in a single read.

    Returns:
        (abstracts, titles, None) on success, where abstracts and titles are
        lists of dicts with keys ``"ID"`` and ``"Abstract"``/``"Title"``
        respectively.
        (None, None, error_string) on failure.
    """
    try:
        csv_path = DATABASE_PATH
        df = pd.read_csv(csv_path, usecols=["ID", "Abstract", "Title"])
        df = df.fillna('N/A').replace('nan', 'N/A')
        abstracts = df[["ID", "Abstract"]].to_dict(orient="records")
        titles = df[["ID", "Title"]].to_dict(orient="records")
        return abstracts, titles, None
    except FileNotFoundError:
        return None, None, "data.csv file not found"
    except pd.errors.EmptyDataError:
        return None, None, "data.csv file is empty"
    except Exception as e:
        return None, None, f"Error loading data.csv: {e}"

def get_performance_metrics_mapping():
    """
    Generate a mapping for performance metrics filtering.
    Returns a dictionary that maps checkbox selections to actual data columns.
    """
    if not PERFORMANCE_METRICS_COLUMNS:
        return {}
    
    mapping = {
        "Accuracy": {
            "User-Dependent": "Interaction_PANEL_Accuracy of Interaction Detection (User-Dependent)",
            "User-Independent": "Interaction_PANEL_Accuracy of Interaction Detection (User-Independent)"
        },
        "F1-Score": {
            "User-Dependent": "Interaction_PANEL_F1-Score of Interaction Detection (User-Dependent)",
            "User-Independent": "Interaction_PANEL_F1-Score of Interaction Detection (User-Independent)"
        }
    }
    return mapping

def generate_sidebar_panels(data, explanations):
    # Create a list for the panels on the side bar
    sidebar_panels = []
    panels = {}
    for col in data[0].keys(): # all records in the database have the same keys = column headings = data[0].keys()
        prefix = "Metadata" if col in METADATA_SIDEBAR_CATEGORIES else (col.split("_")[0] if "_" in col else "General Information")
        if prefix not in panels:
            panels.update({prefix: []})
        panels[prefix].append(col)
    # now all column headings are grouped by their prefix and in panels dictionary

    for panel, columns in panels.items():
        new_panel = Panel(value=panel)
        if panel in SELECT_DESELECT_ALL_PANELS:
            new_panel.select_deselect_buttons = True

        if panel in INITIALLY_HIDDEN_PANELS:
            new_panel.initial_visibility = "none"
        
        for col in columns:
          # skip all columns that are excluded
          if col in EXCLUDED_SIDEBAR_CATEGORIES:
            continue

          # skip the device model column – it is rendered via a custom block instead
          if DEVICE_MODEL_COLUMN and col == DEVICE_MODEL_COLUMN:
            continue

          # token-search columns use a custom UI instead of checkboxes
          if col in TOKEN_SEARCH_COLUMNS:
            new_panel.token_search_block.append({'column': col, 'label': col.split('_')[-1]})
            continue
          
          # for numerical columns, get min and max values and add Slider to the respective panel
          if col in SLIDER_CATEGORIES:
            # determine min and max values for the slider
            min_value = min(list(map(lambda entry: entry[col], data)))
            max_value = max(list(map(lambda entry: entry[col], data)))

            unbounded_max = False
            # Fixed / capped overrides for specific sliders
            if col == "Interaction_PANEL_Number of Selected Gestures":
                max_value = 25
                unbounded_max = True  # values > 25 are all captured when slider is at max

            # create a new slider
            new_slider = Slider(value=col, min_value=min_value, max_value=max_value, unbounded_max=unbounded_max)
            new_slider.explanation = explanations.get(col, None)

            # add the slider to the respective panel
            new_panel.sliders.append(new_slider)
          else:
            # for categorical columns, get unique values
            unique_values = set()
            for row in data:
              # some cells contain multiple values separated by commas
              cell_values = row[col].split(",")
              for value in cell_values:
                  # trim values
                  trimmed_value = value.strip()

                  # remove parentheses and choose the first value for values containing parentheses
                  base_value = trimmed_value.split("(")[0].strip() if col in PARENTHICAL_COLUMNS else trimmed_value
                  unique_values.add(base_value)

            # sort the unique values using custom_sort function
            sorted_unique_values = custom_sort(list(unique_values))

            # For other-threshold columns, replace rare values with a single "Other" option
            if col in OTHER_THRESHOLD_COLUMNS and col in OTHER_THRESHOLD_RARE_VALUES:
                rare = set(OTHER_THRESHOLD_RARE_VALUES[col])
                frequent_values = [v for v in sorted_unique_values if v not in rare]
                if rare:
                    # Insert "Other" before "N/A" (Other is still a valid option, not not-applicable)
                    has_na = "N/A" in frequent_values
                    if has_na:
                        frequent_values = [v for v in frequent_values if v != "N/A"]
                    frequent_values.append("Other")
                    if has_na:
                        frequent_values.append("N/A")
                sorted_unique_values = frequent_values

            # create a new filter for the column and add it to the respective panel
            if col in EXCLUSIVE_FILTERING_CATEGORIES:
                new_filter = Filter(value=col, unique_values=sorted_unique_values, exclusive_filtering=True, select_deselect_all=True)
            elif col in SELECT_DESELECT_ALL_CATEGORIES:
                new_filter = Filter(value=col, unique_values=sorted_unique_values, select_deselect_all=True)
            else:
                new_filter = Filter(value=col, unique_values=sorted_unique_values)

            # retrieve the explanation for the column from explanations dictionary
            explanation = explanations.get(col, None)

            # if the explanation is in SPECIAL_FORMAT_EXPLANATIONS, format it accordingly
            if (col in SPECIAL_FORMAT_EXPLANATIONS):
                # split the explanation by ".;" and trim each part
                parts = [part.strip() for part in explanation.split(".;")]

                # ensure the first part ends with a dot and the last part does not
                if (len(parts) > 0 and not parts[0].endswith(".")):
                    parts[0] += "."
                if parts[-1].endswith("."):
                    parts[-1] = parts[-1][:-1]

                # combine the parts into a single explanation string
                explanation = "\n".join(parts)
            new_filter.explanation = explanation
            new_panel.filters.append(new_filter)
        sidebar_panels.append(new_panel)

    # Add special performance metrics block (slider + type checkboxes + N/A) at the bottom of the Interaction panel
    if PERFORMANCE_METRICS_COLUMNS:
        for panel in sidebar_panels:
            if panel.value == "Interaction":
                # Calculate min and max values across all 4 performance columns
                all_values = []
                for row in data:
                    for col in PERFORMANCE_METRICS_COLUMNS:
                        val = row.get(col, 'N/A')
                        if val != 'N/A' and val != '':
                            try:
                                numeric_val = float(str(val).split('(')[0].strip())
                                all_values.append(numeric_val)
                            except (ValueError, AttributeError):
                                pass

                if all_values:
                    min_value = 0    # fixed range: 0–100 regardless of data
                    max_value = 100
                    performance_slider = Slider(
                        value="Accuracy/F1-Score of Interaction Detection",
                        min_value=min_value,
                        max_value=max_value,
                        explanation="The system's ability to accurately detect and interpret interactions, considering only the most basic reported condition and setting (e.g., sitting in a lab) for consistency. Only applies to studies reporting accuracies/F-1 scores."
                    )
                else:
                    performance_slider = None

                panel.performance_block = {
                    'slider': performance_slider,
                    'metric_types': ["Accuracy", "F1-Score"],
                    'eval_types': ["User-Dependent", "User-Independent"],
                    'col_map': get_performance_metrics_mapping(),
                }
                break

    # Metadata panel should be at the end
    sidebar_panels.sort(key=lambda x: x.value == "Metadata")

    # Add "Authors" and "Title" to the Metadata token-search block
    # (both are excluded from normal sidebar processing but should be searchable via the token UI)
    if TOKEN_SEARCH_COLUMNS:
        for panel in sidebar_panels:
            if panel.value == "Metadata":
                existing_cols = {entry['column'] for entry in panel.token_search_block}
                for col in ["Authors", "Title"]:
                    if col in TOKEN_SEARCH_COLUMNS and col not in existing_cols:
                        panel.token_search_block.append({'column': col, 'label': col})
                # Sort into desired display order
                desired_order = ["Keywords", "Main Author", "Authors", "Title"]
                panel.token_search_block.sort(
                    key=lambda x: desired_order.index(x['column'])
                    if x['column'] in desired_order else len(desired_order)
                )
                break

    # Add custom device model filter block at the bottom of the Device panel
    if DEVICE_MODEL_COLUMN and DEVICE_MODEL_OPTIONS:
        for panel in sidebar_panels:
            if panel.value == "Device":
                panel.device_model_block = {
                    'column': DEVICE_MODEL_COLUMN,
                    'options': DEVICE_MODEL_OPTIONS,
                }
                break

    return sidebar_panels

def load_similarity_data():
    try:
        # Read the similarity matrix with the first column as index
        csv_path_as = os.path.join(os.path.dirname(__file__), "datasets/abstract_similarity/normalized_abstract_similarity.csv")
        abstract_similarity_df = pd.read_csv(csv_path_as, index_col=0)
        abstract_similarity_df = abstract_similarity_df.fillna('N/A')  # Replace actual NaN values
        abstract_similarity_df = abstract_similarity_df.replace('nan', 'N/A')  # Replace string 'nan' values
        csv_path_ds = os.path.join(os.path.dirname(__file__), "datasets/database_similarity/normalized_database_similarity.csv")
        database_similarity_df = pd.read_csv(csv_path_ds, index_col=0)
        database_similarity_df = database_similarity_df.fillna('N/A')  # Replace actual NaN values
        database_similarity_df = database_similarity_df.replace('nan', 'N/A')  # Replace string 'nan' values

        # Prepare data structure that preserves row/column information
        similarity_data = {
            'abstract_study_ids': abstract_similarity_df.columns.tolist(),
            'abstract_index_ids': abstract_similarity_df.index.tolist(),
            'abstract_matrix': abstract_similarity_df.values.tolist(),

            'database_study_ids': database_similarity_df.columns.tolist(),
            'database_index_ids': database_similarity_df.index.tolist(),
            'database_matrix': database_similarity_df.values.tolist(),
        }
    except FileNotFoundError:
        return "similarity.csv file not found"
    except pd.errors.EmptyDataError:
        return "similarity.csv file is empty"
    except Exception as e:
        return f"Error loading similarity.csv: {e}"
    
    return similarity_data

def load_citation_data(all_data_ids=None):
    # Load citation and co-author matrices for timeline view.
    # Returns two dict-of-dicts: { rowId(str): { colId(str): value } }
    # so that JS can do matrix[nodeA][nodeB] directly.
    # IDs present in data.csv but absent from the CSV files get all-zero rows.

    if all_data_ids is None:
        all_data_ids = []

    def load_matrix(csv_path):
        """Read a square matrix CSV and return a dict-of-dicts keyed by string ID."""
        df = pd.read_csv(csv_path, index_col=0)
        # Ensure both index and column names are strings
        df.index = df.index.astype(str)
        df.columns = df.columns.astype(str)

        result = {}
        for row_id in df.index:
            result[row_id] = {col_id: int(df.at[row_id, col_id])
                              for col_id in df.columns}

        # Pad any IDs present in data.csv but missing from the matrix
        for sid in all_data_ids:
            if sid not in result:
                # Add a zero row and a zero column entry for every existing row
                result[sid] = {other: 0 for other in all_data_ids}
                for other in result:
                    if sid not in result[other]:
                        result[other][sid] = 0

        return result

    citation_matrix = {}
    coauthor_matrix = {}

    try:
        csv_path = os.path.join(os.path.dirname(__file__), "datasets/interconnections/citation_matrix.csv")
        citation_matrix = load_matrix(csv_path)
    except Exception as e:
        print(f"Warning: could not load citation matrix: {e}")
        # Fall back to an all-zero matrix so the timeline still renders
        citation_matrix = {sid: {other: 0 for other in all_data_ids} for sid in all_data_ids}

    try:
        csv_path = os.path.join(os.path.dirname(__file__), "datasets/interconnections/coauthor_matrix.csv")
        coauthor_matrix = load_matrix(csv_path)
    except Exception as e:
        print(f"Warning: could not load coauthor matrix: {e}")
        coauthor_matrix = {sid: {other: 0 for other in all_data_ids} for sid in all_data_ids}

    return citation_matrix, coauthor_matrix


def _load_view_data():
    """Load, validate, and pre-process all data needed by the four main views.

    Returns:
        ``((data, explanations, sidebar_panels), None)`` on success.
        ``(None, (response, status_code))`` on failure — routes can do
        ``if err: return err`` to short-circuit immediately.
    """
    result = load_data(config_path=CONFIG_PATH)
    if isinstance(result, str):
        return None, (render_template("error.html", error=result), 500)
    data, explanations = result
    if not isinstance(data, list):
        return None, (render_template("error.html", error=data), 500)
    if not isinstance(explanations, dict):
        return None, (render_template("error.html", error=explanations), 500)
    return (data, explanations, generate_sidebar_panels(data, explanations)), None


def _build_common_kwargs(data, explanations, sidebar_panels, abstracts, titles):
    """Build the template kwargs shared by all four main views.

    Centralising these here means adding a new global config key only requires
    a change in one place instead of four.
    """
    return dict(
        data=data,
        data_json=json.dumps(data),
        sidebar_panels=sidebar_panels,
        explanations=json.dumps(explanations),
        abstracts=json.dumps(abstracts),
        titles=json.dumps(titles),
        parenthical_columns=json.dumps(PARENTHICAL_COLUMNS),
        filter_categories=json.dumps(filter_categories(data)),
        start_categories=START_CATEGORY_FILTERS,
        performance_metrics_mapping=json.dumps(get_performance_metrics_mapping()),
        device_model_column=json.dumps(DEVICE_MODEL_COLUMN),
        device_model_options=json.dumps(DEVICE_MODEL_OPTIONS),
        other_threshold_columns=json.dumps(OTHER_THRESHOLD_COLUMNS),
        other_threshold_rare_values=json.dumps(OTHER_THRESHOLD_RARE_VALUES),
        token_search_columns=json.dumps(TOKEN_SEARCH_COLUMNS),
        token_search_options=json.dumps(TOKEN_SEARCH_OPTIONS),
    )


@app.get("/")
def home():
    view_data, err = _load_view_data()
    if err:
        return err
    data, explanations, sidebar_panels = view_data

    abstracts, titles, load_err = load_abstracts_and_titles()
    if load_err:
        return render_template("error.html", error=load_err), 500

    # Map allowlisted success codes to user-visible messages
    _success_codes = {
        'study_submitted': 'Study submitted successfully!',
        'mistake_reported': 'Mistake report submitted successfully!',
    }
    success_message = _success_codes.get(request.args.get('success'))

    return render_template(
        "table-view.html",
        current_view="tableView",
        success_message=success_message,
        **_build_common_kwargs(data, explanations, sidebar_panels, abstracts, titles),
    )

@app.get("/bar-chart")
def bar_chart():
    view_data, err = _load_view_data()
    if err:
        return err
    data, explanations, sidebar_panels = view_data

    abstracts, titles, load_err = load_abstracts_and_titles()
    if load_err:
        return render_template("error.html", error=load_err), 500

    return render_template(
        "bar-chart.html",
        current_view="chartView",
        **_build_common_kwargs(data, explanations, sidebar_panels, abstracts, titles),
    )

@app.get("/similarity")
def similarity():
    view_data, err = _load_view_data()
    if err:
        return err
    data, explanations, sidebar_panels = view_data

    abstracts, titles, load_err = load_abstracts_and_titles()
    if load_err:
        return render_template("error.html", error=load_err), 500

    similarity_data = load_similarity_data()
    if not isinstance(similarity_data, dict):
        return render_template("error.html", error=similarity_data), 500

    excluded_categories = EXCLUDED_SIDEBAR_CATEGORIES + METADATA_SIDEBAR_CATEGORIES + ["Year"]

    return render_template(
        "similarity.html",
        current_view="similarityView",
        similarity_data=json.dumps(similarity_data),
        excluded_categories=json.dumps(excluded_categories),
        **_build_common_kwargs(data, explanations, sidebar_panels, abstracts, titles),
    )

@app.get("/timeline")
def timeline():
    view_data, err = _load_view_data()
    if err:
        return err
    data, explanations, sidebar_panels = view_data

    abstracts, titles, load_err = load_abstracts_and_titles()
    if load_err:
        return render_template("error.html", error=load_err), 500

    all_data_ids = [str(entry['ID']) for entry in data]
    citation_matrix, coauthor_matrix = load_citation_data(all_data_ids)
    excluded_categories = EXCLUDED_SIDEBAR_CATEGORIES + METADATA_SIDEBAR_CATEGORIES + ["Year"]

    return render_template(
        "timeline.html",
        current_view="timeView",
        citation_matrix=json.dumps(citation_matrix),
        coauthor_matrix=json.dumps(coauthor_matrix),
        excluded_categories=json.dumps(excluded_categories),
        **_build_common_kwargs(data, explanations, sidebar_panels, abstracts, titles),
    )

@app.get('/add_study')
def add_study():
    try:
        # Ensure global config variables (DEVICE_MODEL_COLUMN, PERFORMANCE_METRICS_COLUMNS, etc.)
        # are populated before building the form.  These are set as a side-effect of load_data(),
        # which is normally called by the main view routes.  If a worker receives /add_study
        # as its very first request, the globals would still hold their module-level defaults
        # (empty string / empty list), causing wrong field types in the rendered form.
        load_data(CONFIG_PATH)

        # Load the data
        csv_path = os.path.join(os.path.dirname(__file__), "datasets/data.csv")
        df = pd.read_csv(csv_path)
        
        # Extract categories and their options for the form
        form_categories = {}
        
        # Identify panel categories from column names
        panels = {}
        for col in df.columns:
            if '_PANEL_' in col:
                panel_name = col.split('_PANEL_')[0]
                if panel_name not in panels:
                    panels[panel_name] = []
                panels[panel_name].append(col)
            elif col not in ['ID', 'Main Author', 'Abstract', 'Study Link', 'Keywords', 'Title', 'Authors']:
                # Add general columns not in panels
                if 'General' not in panels:
                    panels['General'] = []
                panels['General'].append(col)
        
        # Process each panel to extract unique values
        for panel, columns in panels.items():
            panel_options = {}
            
            for col in columns:
                # Skip certain columns that shouldn't be in the form
                if col in ['ID', 'Main Author', 'Abstract', 'Study Link', 'Title', 'Authors']:
                    continue
                
                # Get the display name (remove panel prefix if exists)
                if '_PANEL_' in col:
                    display_name = col.split('_PANEL_')[1]
                else:
                    display_name = col
                
                # Special handling for numeric fields
                if col == 'Year' or col == 'Interaction_PANEL_Number of Selected Gestures':
                    panel_options[col] = {
                        'type': 'numeric',
                        'name': display_name,
                        'min': int(df[col].min()),
                        'max': int(df[col].max())
                    }
                    continue

                # Fields that should always be free-text inputs (not checkboxes)
                text_field_cols = {'Gesture', DEVICE_MODEL_COLUMN} | set(PERFORMANCE_METRICS_COLUMNS)
                if col in text_field_cols:
                    panel_options[col] = {
                        'type': 'text',
                        'name': display_name,
                        'options': []
                    }
                    continue
                
                # Extract unique values from the column
                unique_values = []
                for cell in df[col].dropna():
                    # Handle comma-separated values
                    if isinstance(cell, str):
                        for value in cell.split(','):
                            clean_value = value.strip()
                            
                            # For specific fields, remove parenthetical content
                            if col in PARENTHICAL_COLUMNS and '(' in clean_value:
                                base_value = clean_value.split('(')[0].strip()
                                if base_value and base_value not in unique_values:
                                    unique_values.append(base_value)
                            # For other fields, keep parenthetical content
                            elif clean_value and clean_value not in unique_values:
                                unique_values.append(clean_value)
                
                # Use custom_sort instead of default sorting
                unique_values = custom_sort(unique_values)
                
                # Determine field type and properties
                field_type = 'checkbox' if len(unique_values) > 1 else 'text'
                
                # Set up the basic field properties
                field_data = {
                    'type': field_type,
                    'name': display_name,
                    'options': unique_values
                }
                
                # For participant count fields, add a flag to include N input
                if col in PARENTHICAL_COLUMNS:
                    field_data['needs_participant_count'] = True
                
                panel_options[col] = field_data
            
            if panel_options:  # Only add non-empty panels
                form_categories[panel] = panel_options

        
        return render_template('add_study.html', form_categories=form_categories)
        
    except Exception as e:
        print(f"Error preparing add_study form: {e}")
        # Fallback to basic template if data processing fails
        return render_template('error.html', error=str(e)), 500
    
@app.route('/submit_study', methods=['POST'])
def submit_study():
    try:
        # Honeypot: hidden from real users; bots that fill it are silently rejected
        if request.form.get('website', ''):
            return redirect(url_for('home', success='study_submitted'))

        # Get form data from request - use getlist for potential multiple values
        form_data = request.form
        
        # Process the form data to handle multiple selections
        processed_data = {}
        
        # First, get all unique field names (without the array notation)
        field_names = set()
        for key in form_data.keys():
            if key in ('csrf_token', 'website'):  # skip framework internals and honeypot
                continue
            field_names.add(key)
        
        # Then process each field, using getlist to capture multiple values if present
        for field in field_names:
            values = request.form.getlist(field)
            if len(values) > 1:  # If multiple values were selected
                processed_data[field] = values
            else:
                processed_data[field] = values[0] if values else ""
        
        # Format email body with better organization
        body = "📚 NEW STUDY SUBMISSION TO EARXPLORE 📚\n"
        body += "=" * 50 + "\n\n"
        
        # Basic information section (most important fields first)
        body += "BASIC INFORMATION:\n"
        body += "-" * 20 + "\n"
        for field in ['title', 'authors', 'venue', 'year', 'link']:
            if field in processed_data:
                body += f"{field.capitalize()}: {processed_data[field]}\n"
        body += "\n"
        
        # Abstract section (if present)
        if 'abstract' in processed_data:
            body += "ABSTRACT:\n"
            body += "-" * 20 + "\n"
            body += f"{processed_data.get('abstract')}\n\n"
        
        # Group other fields by their prefixes (based on panel structure)
        panels = {}
        for key in processed_data:
            # Skip already processed fields
            if key in ['title', 'authors', 'venue', 'year', 'link', 'abstract']:
                continue
            
            # Skip empty fields
            if not processed_data[key]:
                continue
                
            # Determine panel for organization
            if "_PANEL_" in key:
                panel = key.split("_PANEL_")[0]
            elif key == 'submitterEmail' or key == 'additionalInfo' or key.endswith('_other'):
                panel = "Submission Info"
            else:
                panel = "General"
                
            if panel not in panels:
                panels[panel] = []
            panels[panel].append(key)
        
        # Define a consistent order for panels - match your desired display order
        panel_order = ["General", "Interaction", "Device", "Implementation", 
                      "Sensing", "Applications", "Study", "Motivations", "Submission Info"]
        
        # Add each panel's fields in a consistent order
        for panel in panel_order:
            if panel not in panels:
                continue  # Skip panels that weren't submitted
                
            body += f"{panel.upper()}:\n"
            body += "-" * 20 + "\n"
            
            for field in panels[panel]:
                # Skip "other" fields as they're handled with their main fields
                if field.endswith('_other'):
                    continue
                    
                # Format the display name nicely
                if "_PANEL_" in field:
                    display_name = field.split("_PANEL_")[1]
                else:
                    display_name = field
                    
                display_name = display_name.replace("_", " ").title()
                
                # Format the value based on whether it's a list or single value
                value = processed_data.get(field)
                
                # Every field gets its own paragraph/section for clarity
                body += f"{display_name}:"
                
                # Handle special formatting for values
                if isinstance(value, list):
                    # Check if there's an "other" field to include
                    other_field = f"{field}_other"
                    if other_field in processed_data and processed_data[other_field]:
                        value.append(processed_data[other_field])
                    
                    # For multiple values, display each on its own line with proper indentation
                    body += "\n"  # Start list on a new line
                    for item in value:
                        body += f"  • {item}\n"
                else:
                    # For single values, display with a space after the field name
                    body += f" {value}\n"
                
                # Add an empty line between fields for better readability
                body += "\n"
            
            # Remove extra line break at the end of the panel section
            body = body.rstrip("\n") + "\n\n"
        
        # Create and send the email
        recipients = os.getenv("RECIPIENTS")
        if not recipients:
            print("Error: RECIPIENTS environment variable is not set.")
            return jsonify({"success": False, "message": "Server is not configured to send emails. Please contact the administrator."}), 503
        msg = EmailMessage(
            subject=f"earXplore: New Study - {processed_data.get('title', 'Untitled')}",
            to=[recipients],
            body=body
        )
        msg.send()
        
        print("Email sent successfully!")
        return redirect(url_for('home', success='study_submitted'))

    except Exception as e:
        print(f"Error processing form submission: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/submit_mistake', methods=['POST'])
def submit_mistake():
    try:
        # Honeypot: hidden from real users; bots that fill it are silently rejected
        if request.form.get('website', ''):
            return redirect(url_for('home', success='mistake_reported'))

        # Get form data from request
        mistake_data = request.form
        
        # Format email body
        body = "A mistake report has been submitted to earXplore:\n\n"
        body += f"Study ID/Title: {mistake_data.get('studyId', 'Not specified')}\n\n"
        body += f"Description: {mistake_data.get('description', 'No description provided')}\n\n"
        body += f"Reporter Email: {mistake_data.get('email', 'No email provided')}"

        print(f"Body of the email:\n{body}\n")

        recipients = os.getenv("RECIPIENTS")
        if not recipients:
            print("Error: RECIPIENTS environment variable is not set.")
            return jsonify({"success": False, "message": "Server is not configured to send emails. Please contact the administrator."}), 503
        
        # Create and send the email
        msg = EmailMessage(
            subject="earXplore: Mistake Report",
            body=body,
            to=[recipients],
        )
        msg.send()
        
        print("Email sent successfully!")
        return redirect(url_for('home', success='mistake_reported'))

    except Exception as e:
        print(f"Error processing mistake report: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.post("/api/chat")
@csrf.exempt
@limiter.limit("20 per day")
def chat():
    body = request.get_json(silent=True) or {}
    user_request = (body.get("query") or "").strip()

    if not user_request:
        return jsonify({"ok": False, "response": "Please enter a message."}), 200

    if len(user_request) > 400:
        return jsonify({"ok": False, "response": "Message too long. Please keep your question under 400 characters."}), 200

    # Validate and sanitize conversation history from the client.
    # Cap at the last 10 messages (5 exchanges) to limit token usage.
    raw_history = body.get("history", [])
    validated_history = []
    if isinstance(raw_history, list):
        for msg in raw_history[-10:]:
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = str(msg.get("content", "")).strip()
                if role in ("user", "assistant") and content:
                    validated_history.append({"role": role, "content": content[:400]})

    llm_url = os.getenv("LLM_API_URL")
    kit_api_key = os.getenv("LLM_API_KEY")

    if not llm_url or not kit_api_key:
        return jsonify(
            {
                "ok": False,
                "response": "Server configuration error: missing LLM_API_URL or LLM_API_KEY.",
            }
        ), 200

    headers = {
        "Authorization": f"Bearer {kit_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        # change to respective model
        "model": os.getenv("LLM_MODEL"),
        "messages": validated_history + [{"role": "user", "content": user_request}],
        "max_tokens": 600,
        "temperature": 0.3,
        "top_p": 0.9,
    }

    try:
        resp = requests.post(llm_url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        reply = (
            data.get("response")
            or data.get("reply")
            or (data.get("choices", [{}])[0].get("message", {}).get("content"))
        )

        if not reply:
            return jsonify(
                {"ok": False, "response": "LLM returned no text reply."}
            ), 200

        return jsonify({"ok": True, "response": reply}), 200

    except requests.Timeout:
        return jsonify(
            {"ok": False, "response": "The LLM request timed out. Please try again."}
        ), 200

    except requests.RequestException as exc:
        return jsonify(
            {"ok": False, "response": f"LLM request failed: {str(exc)}"}
        ), 200

    except Exception as exc:
        return jsonify(
            {"ok": False, "response": f"Unexpected server error: {str(exc)}"}
        ), 200


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true", host="0.0.0.0", port=888)
