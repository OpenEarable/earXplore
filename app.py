from flask import Flask, render_template, request, jsonify, url_for
from flask_mailman import Mail, EmailMessage
from typing import List
from dotenv import load_dotenv
import pandas as pd
import json
import os

# Categories that should not be filtered for
EXCLUDED_SIDEBAR_CATEGORIES = ['ID', 'Abstract', 'Study Link']

# Categories that go in the advanced filters panel
ADVANCED_SIDEBAR_CATEGORIES = ['Main Author', 'Gesture', 'Keywords']

# Categories that are displayed as sliders in the sidebar, should be numerical !
SLIDER_CATEGORIES = ['Year', 'Interaction_PANEL_Number of Selected Gestures']

# Categories that should have a "select/deselect all" button in the sidebar
SELECT_DESELECT_ALL_CATEGORIES = ['Location', 'Input Body Part', 'Sensing_PANEL_Sensors', 'Applications_PANEL_Intended Applications', 'Main Author', 'Gesture', 'Keywords']

# Categories that should have an "exclusive filtering" button in the sidebar
EXCLUSIVE_FILTERING_CATEGORIES = ['Sensing_PANEL_Sensors']

# Panels that should have a "select/deselect all" button in the sidebar
SELECT_DESELECT_ALL_PANELS = ['Interaction', 'Implementation', 'Study']

# Panels that should be initially hidden in the sidebar
INITIALLY_HIDDEN_PANELS = ['Advanced Filters']

# Columns that contain parentheses but only the part before the parentheses should be used for filtering
PARENTHICAL_COLUMNS = [
                    'Interaction_PANEL_Accuracy of Interaction Recognition', 
                    'Interaction_PANEL_Robustness of Interaction Detection', 
                    'Study_PANEL_Elicitation Study', 
                    'Study_PANEL_Usability Evaluations', 
                    'Study_PANEL_Cognitive Ease Evaluations', 
                    'Study_PANEL_Discreetness of Interactions Evaluations', 
                    'Study_PANEL_Social Acceptability of Interactions Evaluations', 
                    'Study_PANEL_Accuracy of Interactions Evaluations', 
                    'Study_PANEL_Alternative Interaction Validity Evaluations'
                ]

# Categories that should be displayed initially in the tabular and bar chart views 
# Do not delete the "INFO" category !
START_CATEGORY_FILTERS = json.dumps(["INFO", "Main Author", "Year", "Location", "Input Body Part", "Gesture"])

# Categories whose explanations should be formatted in a special way
SPECIAL_FORMAT_EXPLANATIONS = ["Interaction_PANEL_Discreetness of Interaction Techniques", "Interaction_PANEL_Social Acceptability of Interaction Techniques", "Interaction_PANEL_Accuracy of Interaction Recognition", "Interaction_PANEL_Robustness of Interaction Detection", "Motivations_PANEL_Motivations"]

app = Flask(__name__)

load_dotenv() # Load environment variables from .env file

# Configure Flask-Mail
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = os.getenv("MAIL_PORT")
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")
mail = Mail(app)

# Template classes for sidebar panel
class Slider:
    def __init__(self, value:str, min_value:int, max_value:int, explanation:str = None):
        self.value = value
        self.min_value = min_value
        self.max_value = max_value
        self.explanation = explanation

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

def load_data():
    # Load data from CSV file into data variable
    try:
        csv_path = os.path.join(os.path.dirname(__file__), "data.csv")
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
    
    return data

def load_explanations():
    # Load explanations from CSV file into explanations variable
    try:
        csv_path = os.path.join(os.path.dirname(__file__), "explanations.csv")
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
    
    return explanations

def load_abstracts():
    try:
        csv_path = os.path.join(os.path.dirname(__file__), "data.csv")
        df = pd.read_csv(csv_path, usecols=["Abstract", "ID"])  # Load only the Abstract column
        df = df.fillna('N/A')  # Replace actual NaN values
        df = df.replace('nan', 'N/A')  # Replace string 'nan' values
        abstracts = df.to_dict(orient="records")
    except FileNotFoundError:
        return "data.csv file not found"
    except pd.errors.EmptyDataError:
        return "data.csv file is empty"
    except Exception as e:
        return f"Error loading data.csv: {e}"
    
    return abstracts

def additional_data():
    try:
        csv_path = os.path.join(os.path.dirname(__file__), "data.csv")
        df = pd.read_csv(csv_path, usecols=["Gesture", "Keywords"])
        df = df.fillna('N/A')  # Replace actual NaN values
        df = df.replace('nan', 'N/A')  # Replace string 'nan' values
        additional_data = df.to_dict(orient="records")
    except FileNotFoundError:
        return "data.csv file not found"
    except pd.errors.EmptyDataError:
        return "data.csv file is empty"
    except Exception as e:
        return f"Error loading data.csv: {e}"
    
    helper = {}
    for entry in additional_data:
        for key in entry.keys():
            if key not in helper:
                helper[key] = [entry[key]]
            else:    
                helper[key].append(entry[key])
    
    return helper

def generate_sidebar_panels(data, explanations):
    # Create a list for the panels on the side bar
    sidebar_panels = []
    panels = {}
    for col in data[0].keys(): # all records in the database have the same keys = column headings = data[0].keys()
        prefix = "Advanced Filters" if col in ADVANCED_SIDEBAR_CATEGORIES else (col.split("_")[0] if "_" in col else "General Information")
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
          
          # for numerical columns, get min and max values and add Slider to the respective panel
          if col in SLIDER_CATEGORIES:
            # determine min and max values for the slider
            min_value = min(list(map(lambda entry: entry[col], data)))
            max_value = max(list(map(lambda entry: entry[col], data)))

            # create a new slider
            new_slider = Slider(value=col, min_value=min_value, max_value=max_value)
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

    # Panel for advanced filters should be at the end
    sidebar_panels.sort(key=lambda x: x.value == "Advanced Filters")

    return sidebar_panels

def load_similarity_data():
    try:
        # Read the similarity matrix with the first column as index
        csv_path_as = os.path.join(os.path.dirname(__file__), "abstract_similarity_datasets/normalized_abstract_similarity.csv")
        abstract_similarity_df = pd.read_csv(csv_path_as, index_col=0)
        abstract_similarity_df = abstract_similarity_df.fillna('N/A')  # Replace actual NaN values
        abstract_similarity_df = abstract_similarity_df.replace('nan', 'N/A')  # Replace string 'nan' values
        csv_path_ds = os.path.join(os.path.dirname(__file__), "database_similarity_datasets/normalized_database_similarity.csv")
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

def load_citation_data():
    # Load citation and co-author matrices for timeline view
    citation_matrix = []
    coauthor_matrix = []
    
    try:
        # Read CSV - convert index to a column for proper processing in JS
        csv_path = os.path.join(os.path.dirname(__file__), "interconnections_datasets/citation_matrix.csv")
        citation_df = pd.read_csv(csv_path, index_col=0)
        
        # Get column names and index
        col_headers = citation_df.columns.tolist()
        row_indices = citation_df.index.tolist()
        
        # Create header row with empty first cell plus column names
        header_row = [""] + col_headers
        
        # Create matrix with header row and data rows (index + values)
        citation_matrix = [header_row]
        for idx in row_indices:
            row_data = [idx] + citation_df.loc[idx].tolist()
            citation_matrix.append(row_data)
                
    except Exception as e:
        return f"Error loading citation matrix: {e}"
    
    try:
        # Read CSV - convert index to a column for proper processing in JS
        csv_path = os.path.join(os.path.dirname(__file__), "interconnections_datasets/coauthor_matrix.csv")
        coauthor_df = pd.read_csv(csv_path, index_col=0)
        
        # Get column names and index
        col_headers = coauthor_df.columns.tolist()
        row_indices = coauthor_df.index.tolist()
        
        # Create header row with empty first cell plus column names
        header_row = [""] + col_headers
        
        # Create matrix with header row and data rows (index + values)
        coauthor_matrix = [header_row]
        for idx in row_indices:
            row_data = [idx] + coauthor_df.loc[idx].tolist()
            coauthor_matrix.append(row_data)
            
    except Exception as e:
        return f"Error loading coauthor matrix: {e}"
    
    return citation_matrix, coauthor_matrix

@app.get("/")
def home():
    data = load_data()
    if not isinstance(data, list):
        return render_template("error.html", error=data), 500

    explanations = load_explanations()
    if not isinstance(explanations, dict):
        return render_template("error.html", error=explanations), 500
    
    sidebar_panels = generate_sidebar_panels(data, explanations)

    return render_template("table-view.html", current_view="tableView", data=data, sidebar_panels=sidebar_panels, explanations=json.dumps(explanations), abstracts=json.dumps(load_abstracts()), parenthical_columns=json.dumps(PARENTHICAL_COLUMNS), filter_categories=json.dumps(filter_categories(data)), start_categories=START_CATEGORY_FILTERS)

@app.get("/bar-chart")
def bar_chart():
    data = load_data()
    if not isinstance(data, list):
        return render_template("error.html", error=data), 500

    explanations = load_explanations()
    if not isinstance(explanations, dict):
        return render_template("error.html", error=explanations), 500
    
    sidebar_panels = generate_sidebar_panels(data, explanations)

    categories = []
    for category in data[0].keys():
        if category in EXCLUDED_SIDEBAR_CATEGORIES:
            continue
        categories.append(category)


    abstracts = load_abstracts()
    if not isinstance(abstracts, list):
        return render_template("error.html", error=abstracts), 500
    
    
    return render_template("bar-chart.html", current_view="chartView", data=data, sidebar_panels=sidebar_panels, explanations=json.dumps(explanations), abstracts=json.dumps(load_abstracts()), parenthical_columns=json.dumps(PARENTHICAL_COLUMNS), filter_categories=json.dumps(filter_categories(data)), start_categories=START_CATEGORY_FILTERS,)

@app.get("/similarity")
def similarity():
    data = load_data()
    if not isinstance(data, list):
        return render_template("error.html", error=data), 500

    explanations = load_explanations()
    if not isinstance(explanations, dict):
        return render_template("error.html", error=explanations), 500
    
    sidebar_panels = generate_sidebar_panels(data, explanations)

    similarity_data = load_similarity_data()
    if not isinstance(similarity_data, dict):
        return render_template("error.html", error=similarity_data), 500
    
    excluded_categories = EXCLUDED_SIDEBAR_CATEGORIES + ADVANCED_SIDEBAR_CATEGORIES + ["Year"]

    return render_template("similarity.html", current_view="similarityView", data=data, sidebar_panels=sidebar_panels, explanations=explanations, abstracts=json.dumps(load_abstracts()), parenthical_columns=json.dumps(PARENTHICAL_COLUMNS), filter_categories=json.dumps(filter_categories(data)), similarity_data=json.dumps(similarity_data), excluded_categories=json.dumps(excluded_categories))

@app.get("/timeline")
def timeline():
    data = load_data()
    if not isinstance(data, list):
        return render_template("error.html", error=data), 500

    explanations = load_explanations()
    if not isinstance(explanations, dict):
        return render_template("error.html", error=explanations), 500
    
    sidebar_panels = generate_sidebar_panels(data, explanations)

    categories = []
    for category in data[0].keys():
        if category in EXCLUDED_SIDEBAR_CATEGORIES or category == "Year":
            continue
        categories.append(category)

    citation_matrix, coauthor_matrix = load_citation_data()
    excluded_categories = EXCLUDED_SIDEBAR_CATEGORIES + ADVANCED_SIDEBAR_CATEGORIES + ["Year"]

    return render_template("timeline.html", current_view="timeView", data=data, sidebar_panels=sidebar_panels, explanations=explanations, abstracts=json.dumps(load_abstracts()), parenthical_columns=json.dumps(PARENTHICAL_COLUMNS), filter_categories=json.dumps(filter_categories(data)), citation_matrix=json.dumps(citation_matrix), coauthor_matrix=json.dumps(coauthor_matrix), excluded_categories=json.dumps(excluded_categories))

@app.get('/add_study')
def add_study():
    try:
        # Load the data
        csv_path = os.path.join(os.path.dirname(__file__), "data.csv")
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
            elif col not in ['ID', 'Main Author', 'Abstract', 'Study Link', 'Keywords']:
                # Add general columns not in panels
                if 'General' not in panels:
                    panels['General'] = []
                panels['General'].append(col)
        
        # Process each panel to extract unique values
        for panel, columns in panels.items():
            panel_options = {}
            
            for col in columns:
                # Skip certain columns that shouldn't be in the form
                if col in ['ID', 'Main Author', 'Abstract', 'Study Link']:
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
        # Get form data from request
        form_data = request.json
        
        # Format email body
        body = "A new study has been submitted to earXplore:\n\n"
        for key, value in form_data.items():
            body += f"{key}: {value}\n\n"
        
        # Create and send the email
        msg = EmailMessage(
            subject=f"earXplore: New Study Submission - {form_data.get('Title', 'Untitled')}",
            recipients=[os.getenv("RECIPIENTS")],
            body=body
        )
        mail.send(msg)
        
        return jsonify({"success": True, "message": "Study submitted successfully"})
    
    except Exception as e:
        print(f"Error processing form submission: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.route('/submit_mistake', methods=['POST'])
def submit_mistake():
    try:
        # Get form data from request
        mistake_data = request.json
        
        # Format email body
        body = "A mistake report has been submitted to earXplore:\n\n"
        body += f"Study ID/Title: {mistake_data.get('studyId', 'Not specified')}\n\n"
        body += f"Description: {mistake_data.get('description', 'No description provided')}\n\n"
        body += f"Reporter Email: {mistake_data.get('email', 'No email provided')}"
        
        # Create and send the email
        msg = EmailMessage(
            subject="earXplore: Mistake Report",
            recipients=[os.getenv("RECIPIENTS")],
            body=body
        )
        mail.send(msg)
        
        return jsonify({"success": True, "message": "Report submitted successfully"})
    
    except Exception as e:
        print(f"Error processing mistake report: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500
    
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=888)
