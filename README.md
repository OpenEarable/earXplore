
# 🎧 EarXplore

![Paper Teaser Figure](./teaser_figure_interactive.png)

## 📝 About the Project

*EarXplore* is a curated, structured, and interactive online database consolidating published work on interaction with earables. Beyond merely listing studies, it supports in-depth exploration through four dynamic and integrated views that enable filtering, comparison, and visualization. The *Tabular View* presents a structured overview of all included studies, allowing users to filter and query based on multiple categories and criteria. The *Graphical View* provides a visual summary of key study characteristics, supporting quick comparisons and high-level insights. The *Similarity View* highlights connections between studies that share similar attributes, helping users discover related work. Finally, the *Timeline View* visualizes the temporal evolution of the field, revealing trends, citation links, and author networks. These views are interconnected, enabling users to explore data from multiple perspectives while maintaining context through features such as persistent filtering across all views. For more information on the project, we refer to an accompanying [arXiv publication](http://arxiv.org/abs/2507.20656) and to the *[EarXplore](https://earXplore.teco.edu "Link to the Study which introduces this Repository")* website itself.

## 🚀 Getting Started

### 💾 Installation
We highly recommend using a [virtual environment](https://docs.python.org/3/library/venv.html) in python to install all the dependencies from the [requirements.txt](./requirements.txt).  
In order to do that, activate your virtual environment in a terminal beforehand:  
```bash
# venv is the usual name for your virtual environment
path\to\venv\Scripts\activate
```
To install the depencies simply type:
```venv
pip install -r requirements.txt
```
To host your own version of the project locally, type:
```terminal
flask run --debug
```
The `--debug` flag will apply any change you make to your project directly and restart the website on your machine. You can omit this flag.  
You can also change the host address and the port in the code and the bottom of the [app.py](./app.py) file:
```python
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=888) # you can change the debug mode, host and port
```

### 🔀 Forking

While *EarXplore* was designed to visualize data from studies on earable interaction, its code can be reused to visualize just about any data with only minor additional configuration. To visualize your customized data, you need to adapt the [data.csv](./data.csv) according to your specific data points. Note that the header needs a special format that allows it to form different filter panels. If you would also like to have explanations for your categories, you will also need to update the [explanations.csv](./explanations.csv) file accordingly. The project will then extract all the information it needs from your data and produce a website from it. There are some customization options for the sidebar listed below (see [Usage Section](#%EF%B8%8F-usage)):
```python
# Categories that should not be filtered for
EXCLUDED_SIDEBAR_CATEGORIES = ['ID', ...]

# Categories that go in the advanced filters panel
ADVANCED_SIDEBAR_CATEGORIES = ['Keywords', ...]

# Categories that are displayed as sliders in the sidebar, should be numerical !
SLIDER_CATEGORIES = ['Year', ...]

# Categories that should have a "select/deselect all" button in the sidebar
SELECT_DESELECT_ALL_CATEGORIES = ['Location', ...]

# Categories that should have an "exclusive filtering" button in the sidebar
EXCLUSIVE_FILTERING_CATEGORIES = ['Sensors', ...]

# Panels that should have a "select/deselect all" button in the sidebar
SELECT_DESELECT_ALL_PANELS = ['Interaction', 'Implementation', 'Study']

# Panels that should be initially hidden in the sidebar
INITIALLY_HIDDEN_PANELS = ['Advanced Filters']

# Columns that contain parentheses but only the part before the parentheses should be used for filtering
PARENTHICAL_COLUMNS = ['Interaction_PANEL_Accuracy of Interaction Recognition', ...]

# Categories that should be displayed initially in the tabular and bar chart views
# Do not delete the "INFO" category !
START_CATEGORY_FILTERS = json.dumps(["INFO", "Main Author", ...])

# Categories whose explanations should be formatted in a special way
SPECIAL_FORMAT_EXPLANATIONS = ["Interaction_PANEL_Discreetness of Interaction Techniques", ...]
```
Following these instructions will give the full functionalities for the *Tabular* and *Graphical View*. 

To add the *Database* and *Abstract Similarity* metrics to the *Similarity View*, it is moreover necessary to run the [database_similarity.ipynb](./database_similarity.ipynb) and the [abstract_similarity.ipynb](./abstract_similarity.ipynb) to calculate both metrics, saved in the [normalized_database_similarity.csv](./database_similarity_datasets/normalized_database_similarity.csv) and [normalized_abstract_similarity.csv](./abstract_similarity_datasets/normalized_abstract_similarity.csv). For the latter, an API key is needed for `gemini-embedding-exp-03-07` model in order to obtain the text embeddings. Of course, any other text embedding model can be employed as well but requires an according adaption of the code. For the former, the headers of the [data.csv](./data.csv) need to be copied and pasted into the code along their datatype as shown below. 

```python
single_value_columns = [
    'Sensing_PANEL_No Additional Sensing', 'Interaction_PANEL_Hands-Free', 'Interaction_PANEL_Eyes-Free', 
    ...
]

multi_value_and_string_columns = [
    'Location', 'Input Body Part', 'Gesture', 'Sensing_PANEL_Sensors', 'Interaction_PANEL_Resolution',
    ...
]

numerical_columns_log_transformed = [
    'Interaction_PANEL_Number of Selected Gestures'
]

# the special treatment is due this being the only category with two different "Yes" options
single_value_columns_special_treatment = [ 
    'Interaction_PANEL_Possible on One Ear'
]

```

To add the citations and shared authors to the *Timeline View*, the grobid_citations_metadata.ipynb [grobid_citations_metadata.ipynb](./grobid_citations_metadata.ipynb) needs to be employed. [GROBID](https://grobid.readthedocs.io/en/latest/Introduction/) is a machine learning library that extracts structured information from scholarly PDFs. Running GROBID requires Docker - refer to the [GROBID documentation](https://grobid.readthedocs.io/en/latest/Run-Grobid/) for setup instructions. The notebook creates the [coauthor_matrix.csv](./interconnections_datasets/coauthor_matrix.csv) and the [citation_matrix.csv](./interconnections_datasets/citation_matrix.csv). These matrices identify which papers cite each other and which share authors, enabling visualization of research communities and knowledge flow in the *Timeline View*. To use it with your data, first prepare a folder with your corpus PDFs. Then create a dictionary mapping IDs to filenames in the notebook.

```python
path_constant_part = "YOUR PATH"

pdf_path_dict = {
    1: '33_weisenberger.pdf',
    2: '714_brewster.pdf',
    3: '32_metzger.pdf',
    4: '40_buil.pdf', 
    5: '84_buil.pdf',
    ...
```
Prepare an Excel file with paper IDs and their BibTeX entries (see [bibtex_mapping_of_ids.xlsx](./interconnections_datasets/bibtex_mapping_of_ids.xlsx)) that will be needed to map the extracted metadata from the references to the paper of your corpus. Then you can run the GROBID server via Docker (typically on port 8070). For the citations, the notebook uses a confidence-based approach for citation matching, automatically accepting high-confidence matches while flagging uncertain ones for manual review in an Excel file. After reviewing the uncertain matches, run the final cells to create the completed matrices saved as CSV files.

Additionally you may want to configure the Mail-Server to your liking. The configuration is pulled from your .env file. It has the following parameters:
```bash
MAIL_SERVER = "your-smtp-server.example.com"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = "your-email@example.com"
MAIL_PASSWORD = "your-password"
MAIL_DEFAULT_SENDER = "default-sender'
RECIPIENTS= "an-email@example.com"
```
If you are unsure about the some of the configurations, please refer to the [Flask Mail Documentation](https://pypi.org/project/Flask-Mail/).

## 🛠️ Usage

This project is hosted under [earXplore.teco.edu](https://earxplore.teco.edu/). You may want to visit the site to try out all the features yourself. In this section, we interactively give a quick intro into the main features of the platform before introducing each of its four views in detail.

#### View Selection Menu
You can navigate between the four different views (*Tabular*, *Graphical*, *Similarity*, *Timeline*) and the *Add study or report mistake*-section via the navigation bar at the top of the page:

![navbar_demonstration gif](https://github.com/user-attachments/assets/35882867-cc68-4fb3-a751-a620af3d7141)

#### Filter Sidebar
At the sidebar on the right, you can choose the values for every category to filter the data. There is also the option to select or deselect all values:

![sidebar_demonstration gif](https://github.com/user-attachments/assets/ebfe356d-436f-4bb1-b6f5-89214b0ef8a2)

#### Data Display Customization Options
Similar to the sidebar filters, there are additional data display customization options available. For the *Tabular* and the *Graphical View*, the toggle menu can be used to show or hide the columns on each category. For the *Similarity* and *Timeline View*, you can color the nodes representing the studies by category. All the filter selections are consistent across all views. Here is a quick example on how you may use these features:

![filter_demonstration gif](https://github.com/user-attachments/assets/b41978e1-dd71-4031-ab6a-c6ee65fe1129)

#### Modal Overlays
Every info icon on the website is clickable. When clicked it shows a modal with the all the information on the respective study. Additionally, you can click on the bars in the *Graphical View* to get an overview for all studies that match the value of the bar in the specific category of the chart. In the *Similarity* and *Timeline View*, the nodes are also clickable. Upon clicking you receive information about the relationship to other studies in this specific network:

![modal_demonstration gif](https://github.com/user-attachments/assets/d4f809e5-bd01-49d7-857a-8685bd7ce8bd)


After giving a general introductory overview on the functionalities of *EarXplore*, we detail the functionalities of each of the views in the following:

#### Tabular View

(1) The Tabular View serves as landing page and can also be selected via the view selection menu. (2) By default, key information on each study (Main Author, Year, Location, Input Body Part, and Gesture) is displayed. (3) The top toggle menu allows users to show or hide columns with additional information. (4) Filters in the sidebar enable users to refine the database by including or excluding specific attribute values. (5) Clicking the info icons at the beginning of each row opens a modal overlay that displays all available information for the selected study. (6 - not visible) The entire dataset or a selected subset can be downloaded as a CSV file.

<img width="2513" height="969" alt="Tabular View" src="https://github.com/user-attachments/assets/afe5826d-585a-4bb2-b476-8557143a3df4" />

#### Graphical View

Graphical View -- (1) The Graphical View can be selected via the view selection menu. (2) The top toggle menu allows users to show or hide bar charts with additional information. (3) Filters in the sidebar enable users to refine the database by including or excluding specific attribute values. (4) For each selected criterion, a bar chart displays the distribution of answer options. Chart size automatically adapts to the number of bars. (5) Users can adjust the threshold for the maximum number of bars shown per chart. (6) Clicking on a bar opens a modal overlay showing key information on all studies represented by that bar. (7) Clicking on the info icons at the beginning of each row within the modal overlay reveals the full information modal overlay for the respective study.

<img width="2507" height="968" alt="Graphical View" src="https://github.com/user-attachments/assets/a2d7f7aa-c1a5-4c09-92e5-5aebf63a8aab" />

#### Similarity View

(1) The Similarity View can be selected via the view selection menu. (2) Filters allow the user to refine the database along several criteria. (3) The user can choose between Database Similarity and Abstract Similarity. (4) A threshold slider controls which similarity connections are displayed. (5) The nodes representing the studies can be colored and sorted along several criteria. (6) Clicking on a node opens a modal overlay showing key information on all studies that meet the similarity threshold with the selected study. (7) Clicking the info icons at the beginning of each row within the modal overlay reveals the full information modal overlay for the respective study. The full information view can also be displayed via the info icons attached to each study node.

<img width="2493" height="935" alt="Similarity View" src="https://github.com/user-attachments/assets/cb998750-08e0-404e-bbe1-2a3738c1f4d7" />

#### Timeline View

(1) The Timeline View can be selected via the view selection menu. (2) Filters allow the user to refine the database along several criteria. (3) The user can display shared author connections as dashed lines. (4) Citation connections, including their direction, can be shown as solid lines. (5) The nodes representing the studies can be colored and sorted along several criteria. (6) Clicking on a node opens a modal overlay displaying key information on all studies connected to the selected study through shared authorship or citations based on the user's selection. (7) Clicking the info icons at the beginning of each row within the modal overlay reveals the full information modal overlay for the respective study.

<img width="2506" height="915" alt="Timeline View" src="https://github.com/user-attachments/assets/38d581a1-4386-4466-b338-990198b6af20" />


## 💡 Contribute

*EarXplore* is designed not as a static, one-time release, but as a dynamic, extensible resource that evolves alongside ongoing developments in earable interaction research. Its architecture includes updating mechanisms that support long-term sustainability and flexible data integration. Both the structure of the website and its individual views enable seamless incorporation of new content. In addition to updates made by the maintainers, *EarXplore* supports two mechanisms for community contributions. First, researchers can suggest the incorporation of additional studies via the contact form embedded in the platform. Second, they can fork the GitHub repository and propose additions directly. In both cases, submissions undergo review by the maintainers before being automatically integrated into all views of the database via backend scripts. These mechanisms position *EarXplore* as a sustainable, community-driven resource that supports the ongoing curation, comparison, and exploration of earable interaction research.

## 🪪 License

This project is currently licensed under the terms of the [MIT](./LICENSE) license.

## 📩 Contact

You can contact us either via this [GitHub Profile](https://github.com/98JoHu) or via E-Mail: jonas.hummel@kit.edu.

