from flask import Flask, render_template, jsonify
import pandas as pd

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

    return render_template("index.html", data=data, explanations=explanations, similarity_data=similarity_data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
