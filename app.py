from flask import Flask, render_template, jsonify, request
from flask_mail import Mail, Message
import pandas as pd
import os  # Add this import for os.path.exists

app = Flask(__name__)

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'your-smtp-server.example.com'  # Replace with your SMTP server
app.config['MAIL_PORT'] = 587  # Common port for TLS
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@example.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'your-password'  # Replace with your password
app.config['MAIL_DEFAULT_SENDER'] = 'earXplore@teco.edu'
mail = Mail(app)

def custom_sort(values):
    special_orders = {'Yes': 1, 'Partly': 2, 'No': 3, 'Low': 1, 'Medium': 2, 'High': 3, 
                     'Semantic': 1, 'Coarse': 2, 'Fine': 3, 'N/A': 4, 'Yes (Performance Loss)': 2, 'Visual Attention': 2}  # Changed from 'nan' to 'N/A'
    sorted_values = sorted(values, key=lambda x: (special_orders.get(x, 0), 
                                               str(x).lower() if isinstance(x, str) else str(x)))
    return sorted_values

app.jinja_env.filters['custom_sort'] = custom_sort

@app.route("/")
def index():
    try:
        df = pd.read_csv("data.csv")
        df = df.fillna('N/A')  # Replace actual NaN values
        df = df.replace('nan', 'N/A')  # Replace string 'nan' values
        data = df.to_dict(orient="records")    
    except FileNotFoundError:
        return "data.csv file not found", 500
    except pd.errors.EmptyDataError:
        return "data.csv file is empty", 500
    except Exception as e:
        return f"Error loading data.csv: {e}", 500

    try:
        explanations_df = pd.read_csv("explanations.csv")
        explanations = dict(zip(explanations_df["Column"], explanations_df["Explanation"]))
    except FileNotFoundError:
        return "explanations.csv file not found", 500
    except pd.errors.EmptyDataError:
        return "explanations.csv file is empty", 500
    except KeyError:
        return "explanations.csv file is missing required columns", 500
    except Exception as e:
        return f"Error loading explanations.csv: {e}", 500
    
    # Load similarity data
    try:
        # Read the similarity matrix with the first column as index
        similarity_df = pd.read_csv("abstract_similarity_datasets/normalized_similarity.csv", index_col=0)
        
        # Prepare data structure that preserves row/column information
        similarity_data = {
            'study_ids': similarity_df.columns.tolist(),
            'matrix': similarity_df.values.tolist(),
            'index_ids': similarity_df.index.tolist()
        }
        
        # Also prepare a mapping of study IDs to their metadata for tooltips
        if 'data' in locals():
            # Create a dictionary mapping IDs to study information
            study_dict = {}
            for study in data:
                try:
                    study_id = str(study['ID'])  # Assuming 'ID' is the column name in data.csv
                    
                    # Create a copy of the entire study data for this ID
                    study_details = {
                        # Include all fields from the study
                        **study,
                        # Ensure these critical fields are always present with defaults
                        'title': study.get('Title', f"Study {study_id}"),
                        'authors': study.get('First Author', 'Unknown'),
                        'year': study.get('Year', 'N/A'),
                        'id': study_id
                    }
                    
                    # Convert all values to strings to avoid JSON serialization issues
                    for key, value in study_details.items():
                        if pd.isna(value):
                            study_details[key] = 'N/A'
                        else:
                            study_details[key] = str(value) if not isinstance(value, (int, float, bool, str, list, dict)) else value
                    
                    study_dict[study_id] = study_details
                    
                except (KeyError, TypeError) as e:
                    print(f"Error processing study ID {study.get('ID', 'unknown')}: {e}")
                    continue
            similarity_data['study_details'] = study_dict
    except Exception as e:
        similarity_data = {'study_ids': [], 'matrix': [], 'index_ids': [], 'study_details': {}}
        print(f"Error loading similarity data: {e}")

    # Load citation and co-author matrices for timeline view
    citation_matrix = []
    coauthor_matrix = []
    
    try:
        citation_path = "interconnections_datasets/citation_matrix.csv"
        if os.path.exists(citation_path):
            # Read CSV - convert index to a column for proper processing in JS
            citation_df = pd.read_csv(citation_path, index_col=0)
            
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
                
            print(f"Processed citation matrix: {len(citation_matrix)} rows")
    except Exception as e:
        print(f"Error loading citation matrix: {e}")
    
    try:
        coauthor_path = "interconnections_datasets/coauthor_matrix.csv"
        if os.path.exists(coauthor_path):
            # Read CSV - convert index to a column for proper processing in JS
            coauthor_df = pd.read_csv(coauthor_path, index_col=0)
            
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
                
            print(f"Processed coauthor matrix: {len(coauthor_matrix)} rows")
    except Exception as e:
        print(f"Error loading coauthor matrix: {e}")

    return render_template("index.html", 
                          data=data, 
                          explanations=explanations, 
                          similarity_data=similarity_data,
                          citation_matrix=citation_matrix,
                          coauthor_matrix=coauthor_matrix)
    
@app.route('/add_study')
def add_study():
    try:
        # Load the data
        df = pd.read_csv("data.csv")
        
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
            elif col not in ['ID', 'First Author', 'Abstract', 'Study Link', 'Keywords']:
                # Add general columns not in panels
                if 'General' not in panels:
                    panels['General'] = []
                panels['General'].append(col)
        
        # Fields that need participant count fields and should have parentheticals removed
        participant_count_fields = [
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
        
        # Process each panel to extract unique values
        for panel, columns in panels.items():
            panel_options = {}
            
            for col in columns:
                # Skip certain columns that shouldn't be in the form
                if col in ['ID', 'First Author', 'Abstract', 'Study Link']:
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
                            if col in participant_count_fields and '(' in clean_value:
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
                if col in participant_count_fields:
                    field_data['needs_participant_count'] = True
                
                panel_options[col] = field_data
            
            if panel_options:  # Only add non-empty panels
                form_categories[panel] = panel_options
        
        return render_template('add_study.html', form_categories=form_categories)
        
    except Exception as e:
        print(f"Error preparing add_study form: {e}")
        # Fallback to basic template if data processing fails
        return render_template('add_study.html')
    
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
        msg = Message(
            subject=f"earXplore: New Study Submission - {form_data.get('Title', 'Untitled')}",
            recipients=['hummel@teco.edu'],
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
        msg = Message(
            subject="earXplore: Mistake Report",
            recipients=['hummel@teco.edu'],
            body=body
        )
        mail.send(msg)
        
        return jsonify({"success": True, "message": "Report submitted successfully"})
    
    except Exception as e:
        print(f"Error processing mistake report: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
