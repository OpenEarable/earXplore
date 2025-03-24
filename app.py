from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

def custom_sort(values):
    special_orders = {'Yes': 1, 'Partly': 2, 'No': 3, 'Low': 1, 'Medium': 2, 'High': 3, 
                     'Semantic': 1, 'Coarse': 2, 'Fine': 3, 'N/A': 4, 'Yes (Performance Loss)': 2}  # Changed from 'nan' to 'N/A'
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

    print(explanations)
    return render_template("index.html", data=data, explanations=explanations)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
