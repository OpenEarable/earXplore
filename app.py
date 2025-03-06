from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

def custom_sort(values):
    special_orders = {'Yes': 1, 'Partly': 2, 'No': 3, 'Low': 1, 'Medium': 2, 'High': 3, 'Semantic': 1, 'Coarse': 2, 'Fine': 3}
    sorted_values = sorted(values, key=lambda x: (special_orders.get(x, 0), x.lower()))
    return sorted_values

app.jinja_env.filters['custom_sort'] = custom_sort

@app.route("/")
def index():
    data = pd.read_csv("data.csv").to_dict(orient="records")
    
    # Load explanations correctly as a dictionary
    explanations_df = pd.read_csv("explanations.csv")
    explanations = dict(zip(explanations_df["Column"], explanations_df["Explanation"]))

    print(explanations)
    return render_template("index.html", data=data, explanations=explanations)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
