from flask import Flask, render_template, jsonify
import pandas as pd
import os  # Add this import for os.path.exists

app = Flask(__name__)

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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
