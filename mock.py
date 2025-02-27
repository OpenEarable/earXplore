import random 
import pandas as pd
import string

def generate_author_short_name():
    return ''.join(random.choices(string.ascii_uppercase, k=3))

# Define dictionary-based options for each column
mock_data_options = {
    "Author": lambda: f"{generate_author_short_name()} et al",
    "Year":  lambda: f"{2005 + random.randint(1, 20)}",
    "Location": ["Actuation", "Head", "Ear and Earable", "Mouth", "Face", "Eyes", "Brain", "Hand"],
    "Input": ["Brain Activity", "Facial Expression", "Gaze", "Hand", "Head", "Jaw", "Speech Apparatus", "Teeth", "Tensor Tympani", "Tongue"],
    "Gesture": ["Ear-Specific Interaction", "Face-Specific Interaction", "Facial Gestures", "General Motion", "Hand & Finger Interaction", "Head Movements", "Jaw & Mouth Movement", "Mid-Air Gestures", "Speech", "Touch", "Press"],
    "Sensing_PANEL_Sensors": ["IMU", "EMG", "EEG", "Microphone", "Optical", "Pressure", "Temperature", "Ultrasound"],
    "Sensing_PANEL_No Additional Sensing": ["Yes", "No"],
    "Interaction_PANEL_Number of Selected Gestures": lambda: f"{random.randint(1, 10)}",
    "Interaction_PANEL_Hands-Free": ["Yes", "Partly", "No"],
    "Interaction_PANEL_Eyes-Free": ["Yes", "Partly", "No"],
    "Interaction_PANEL_Resolution": ["Semantic", "Coarse", "Fine"],
    "Interaction_PANEL_Possible On One Ear": ["Yes", "No"],
    "Interaction_PANEL_Discreetness": ["Low", "Medium", "High"],
    "Interaction_PANEL_Social Acceptability": ["Low", "Medium", "High"],
    "Interaction_PANEL_Accuracy": ["Low", "Medium", "High"],
    "Interaction_PANEL_Robustness": ["Low", "Medium", "High"],
    "Implementation_PANEL_Implementation Device": ["Earbud", "Headphone", "Custom", "Commercial", "Research Prototype"],
    "Implementation_PANEL_Real-Time Processing": ["Yes", "No"],
    "Implementation_PANEL_On-Device Processing": ["Yes", "No"],
    "Implementation_PANEL_Adaptation to Individual User": ["Yes", "No"],
    "Study_PANEL_Elicitation Study": ["Yes", "No"],
    "Study_PANEL_Usability Evaluation Study": ["Yes", "No"],
    "Study_PANEL_Cognitive Ease Study": ["Yes", "No"],
    "Study_PANEL_Social Acceptance Study": ["Yes", "No"],
    "Study_PANEL_Discreetness Study": ["Yes", "No"],
    "Study_PANEL_Accuracy Evaluation Study": ["Yes", "No"],
    "Study_PANEL_Evaluation of Different Conditions": ["Yes", "No"],
    "Study_PANEL_Evaluation in Different Settings": ["Yes", "No"],
    "Application_PANEL_Applications": ["Accessibility", "Activity Recognition", "AR/VR", "Authentication", "BCI Applications", "Communication", "Customer Analytics", "Data Annotation", "Device Control", "Device Input", 
                     "Emotion Recognition", "Feedback System", "Gaming", "Health", "Music Player", "Phone Calls", "Privacy", "Safety", "Silent Speech", "Social Interaction", "Video Conference"],
}

# Generate mock data using the dictionary approach
mock_data = []
for _ in range(150):  # Generate 50 rows of data
    row = {key: (random.choice(value) if isinstance(value, list) else value()) for key, value in mock_data_options.items()}
    mock_data.append(row)

# Create DataFrame
df_dict_based = pd.DataFrame(mock_data)

# Display DataFrame
df_dict_based.to_csv("data.csv", index=False, quoting=1)  # quoting=1 ensures all values are enclosed in quotes

# Generate explanations for each column
column_explanations = {
    "Author": "The author of the study, formatted as a short name followed by 'et al' to indicate multiple authors.",
    "Year": "The publication year of the study, randomly chosen between 2006 and 2025.",
    "Location": "The body part or area where the interaction is primarily located.",
    "Input": "The input method used for the interaction, such as brain activity or facial expressions.",
    "Gesture": "The type of gesture involved in the interaction, ranging from touch to mid-air gestures.",
    "Sensing_PANEL_Sensors": "The type of sensor(s) used in the system, such as IMU, EEG, or microphones.",
    "Sensing_PANEL_No Additional Sensing": "Indicates whether the system relies only on inherent capabilities or includes additional sensors.",
    "Interaction_PANEL_Number of Selected Gestures": "The number of gestures recognized by the system.",
    "Interaction_PANEL_Hands-Free": "Indicates whether the interaction is completely hands-free, partly hands-free, or not hands-free at all.",
    "Interaction_PANEL_Eyes-Free": "Indicates whether the interaction requires visual attention or not.",
    "Interaction_PANEL_Resolution": "The level of precision of the interaction, categorized as semantic, coarse, or fine.",
    "Interaction_PANEL_Possible On One Ear": "Indicates whether the system can function with only one ear involved.",
    "Interaction_PANEL_Discreetness": "The level of discreetness of the interaction, rated as low, medium, or high.",
    "Interaction_PANEL_Social Acceptability": "How socially acceptable the interaction is, rated as low, medium, or high.",
    "Interaction_PANEL_Accuracy": "The accuracy of the interaction recognition system, rated as low, medium, or high.",
    "Interaction_PANEL_Robustness": "The robustness of the interaction system under different conditions, rated as low, medium, or high.",
    "Implementation_PANEL_Implementation Device": "The type of device used for implementation, such as earbuds or research prototypes.",
    "Implementation_PANEL_Real-Time Processing": "Indicates whether the system processes interactions in real time.",
    "Implementation_PANEL_On-Device Processing": "Indicates whether processing occurs directly on the device or externally.",
    "Implementation_PANEL_Adaptation to Individual User": "Indicates whether the system adapts to the individual user.",
    "Study_PANEL_Elicitation Study": "Indicates whether an elicitation study was conducted.",
    "Study_PANEL_Usability Evaluation Study": "Indicates whether usability was evaluated in a study.",
    "Study_PANEL_Cognitive Ease Study": "Indicates whether cognitive ease was studied.",
    "Study_PANEL_Social Acceptance Study": "Indicates whether social acceptance was studied.",
    "Study_PANEL_Discreetness Study": "Indicates whether discreetness was analyzed in a study.",
    "Study_PANEL_Accuracy Evaluation Study": "Indicates whether accuracy was evaluated.",
    "Study_PANEL_Evaluation of Different Conditions": "Indicates whether the system was evaluated under different conditions.",
    "Study_PANEL_Evaluation in Different Settings": "Indicates whether the system was evaluated in various settings.",
    "Application_PANEL_Applications": "The applications where the system can be used, such as accessibility, gaming, or health monitoring.",
}

# Convert explanations dictionary to DataFrame
df_explanations = pd.DataFrame(list(column_explanations.items()), columns=["Column", "Explanation"])
df_explanations.to_csv("explanations.csv", index=False, quoting=1)

