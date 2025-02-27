from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)



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
