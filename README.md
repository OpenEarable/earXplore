
# EarXplore

![The Open Earables Logo which simultaneously is the logo for the web project](./static/images/OE_Logo_black_RGB.png)
<!-- change to white background version -->

## About the Project

This Web Project was build as an additional to support the exploration of research on interaction with earables (as defined in the respective paper [EarXplore: An Open Earable Research Database on Interaction](https://github.com/OpenEarable/earXplore "Link to the Study which introduces this Repository")<!-- Add the right link -->. For the motivation and methodology of the review we therefore encourage anyone interested to read the paper themselves. The Web Project visualizes the EarXplore Database in four distinct views:

- Tabular View
- Graphical View
- Similarity View
- Timeline View

Please refer to the [Usage Section](#usage) or [Forking Section](#forking) for more information.

## Getting Started

### Installation
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
To host your own version of the project locally type:
```terminal
flask run --debug
```
The `--debug` flag will apply any change you make to your project directly and restart the website on your machine. You can omit this flag.  
You can also change the host address and the port in the code and the bottom of the [app.py](./app.py) file:
```python
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=888) # you can change the debug mode, host and port
```

### Forking

## Usage

## Issues

Currently there are no known issues. If you happen to encounter an issue with the website or need some insight on the code there are two ways to let us know:

1. This implementation of the website is currently hosted at earxplore.dmz.teco.edu <!-- Link not working, change to correct link -->. In the navigation bar you will find a button for reporting a mistake (or submitting an additional study). When clicked you are able to submit a form where you can specify your issue.
2. You can contact us directly by going to the [Contact Section](#contact) and using a communication type of your choice.

## License

This Project is currently not licensed. <!-- TODO: Add license -->

## Contact

You can contact us either via this [GitHub Profile](https://github.com/98JoHu) or via E-Mail: jonas.hummel@kit.edu.
The full address of the institution which this project stems from is:

Vincenz-Prießnitz-Str.1  
Gebäude 07.07  
2.OG [TECO]  
76131 Karlsruhe  

Telefon: +49 721 608-41701  
Fax: +49 721 608-41702  
E-Mail: sekretariat@teco.edu  
