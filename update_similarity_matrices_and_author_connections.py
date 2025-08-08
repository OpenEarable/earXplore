import os
import numpy as np
import pandas as pd
import re

from google import genai
from google.genai import types

import time
from sklearn.metrics.pairwise import cosine_similarity


df = pd.read_csv('data.csv')

## DATABASE SIMILARITY RECOMPUTE

# Function to transform values based on partial matches
def transform_value(value):
    if pd.isna(value):
        return np.nan
    
    # Convert to string to ensure we can perform string operations
    value_str = str(value).lower()
    
    # Check for patterns
    if re.search(r'\byes\b', value_str):
        return 1.0
    elif re.search(r'\bno\b', value_str):
        return 0.0
    elif re.search(r'\blow\b', value_str):
        return 0.0
    elif re.search(r'\bmedium\b', value_str):
        return 0.5
    elif re.search(r'\bhigh\b', value_str):
        return 1.0
    elif re.search(r'\bvisual attention\b', value_str):
        return 0.5
    elif re.search(r'\bpartly\b', value_str):
        return 0.5
    elif re.search(r'\bn\/a\b', value_str) or value_str == 'n/a':
        return np.nan
    else:
        return np.nan

# Create a function to calculate similarity between two studies
def calculate_similarity(row1, row2, numeric_columns, string_columns):
    similarity = 0
    total_features = 0
    
    # Handle numerical columns with absolute difference
    for col in numeric_columns:
        if col in row1 and col in row2:
            # Skip if the column is 'ID'
            if col == 'ID':
                continue
                
            # Get the values
            val1 = row1[col]
            val2 = row2[col]
            
            # Calculate similarity based on absolute difference
            if pd.isna(val1) or pd.isna(val2):
                # If either value is NaN, use maximum difference
                similarity += 0  # 1-1=0 (using 1 as max difference)
            else:
                # Otherwise calculate absolute difference and invert (1-diff)
                # Since values are normalized to [0,1], the difference is also [0,1]
                similarity += 1 - abs(val1 - val2)
            
            total_features += 1
    
    # Handle string/multi-value columns with adjusted Jaccard similarity
    for col in string_columns:
        if col in row1 and col in row2:
            # Skip if the column is 'ID'
            if col == 'ID':
                continue
                
            # Get the values and convert to sets
            # Handle NaN, empty strings, etc.
            val1 = row1[col]
            val2 = row2[col]
            
            if pd.isna(val1) or pd.isna(val2) or val1 == '' or val2 == '':
                similarity += 0  # No similarity if either is empty/NaN
            else:
                # Convert to lowercase before splitting
                # Split by common separators like comma, semicolon, etc.
                # and convert to sets
                set1 = set(str(val1).lower().split(','))
                set2 = set(str(val2).lower().split(','))
                
                # Calculate intersection length
                intersection_len = len(set1.intersection(set2))
                
                # Calculate adjusted Jaccard similarity
                denominator = (len(set1) * len(set2))**0.5
                if denominator > 0:
                    similarity += intersection_len / denominator
                else:
                    similarity += 0
                    
            total_features += 1
    
    # Return average similarity across all features
    if total_features > 0:
        return similarity / total_features
    else:
        return 0
        

# Assign column types for calculation
single_value_columns = [
    'Sensing_PANEL_No Additional Sensing', 'Interaction_PANEL_Hands-Free', 'Interaction_PANEL_Eyes-Free', 
    'Interaction_PANEL_Adaptation of the Interaction Detection Algorithm to User',
    'Interaction_PANEL_Discreetness of Interaction Techniques', 
    'Interaction_PANEL_Social Acceptability of Interaction Techniques',
    'Interaction_PANEL_Accuracy of Interaction Recognition',
    'Interaction_PANEL_Robustness of Interaction Detection',
    'Study_PANEL_Elicitation Study',
    'Study_PANEL_Usability Evaluations',
    'Study_PANEL_Cognitive Ease Evaluations',
    'Study_PANEL_Discreetness of Interactions Evaluations',
    'Study_PANEL_Social Acceptability of Interactions Evaluations',
    'Study_PANEL_Accuracy of Interactions Evaluations',
    'Study_PANEL_Alternative Interaction Validity Evaluations',
    'Device_PANEL_Real-Time Processing', 'Device_PANEL_On-Device Processing'
]

multi_value_and_string_columns = [
    'Location', 'Input Body Part', 'Gesture', 'Sensing_PANEL_Sensors', 'Interaction_PANEL_Resolution', 
    'Study_PANEL_Evaluation of Different Conditions (User-Related)',
    'Study_PANEL_Evaluation of Different Conditions (Environment-Related)',
    'Study_PANEL_Evaluation of Different Settings',
    'Device_PANEL_Earphone Type', 'Device_PANEL_Development Stage',
    'Motivations_PANEL_Motivations',
    'Applications_PANEL_Intended Applications', 'Keywords'
]

numerical_columns_log_transformed = [
    'Interaction_PANEL_Number of Selected Gestures'
]

single_value_columns_special_treatment = ['Interaction_PANEL_Possible on One Ear']

# Recode values for later calculations
df_transformed = df.copy()
df_transformed = df_transformed.drop(columns=['Main Author', 'Study Link', 'Abstract'])

# Apply the transformation to each column in single_value_columns
for col in single_value_columns:
    if col in df_transformed.columns:
        df_transformed[col] = df_transformed[col].apply(transform_value)
        
# Apply min-max scaling using pandas
for col in numerical_columns_log_transformed:
    if col in df_transformed.columns:
        # Apply natural log transformation
        df_transformed[col] = np.log(df_transformed[col]+1) # Adding 1 to avoid log(0)
        df_transformed[col] = (df_transformed[col] - df_transformed[col].min()) / (df_transformed[col].max() - df_transformed[col].min())
        
# Transform the special treatment column
for col in single_value_columns_special_treatment:
    if col in df_transformed.columns:
        # Define a mapping dictionary for exact matching
        special_mapping = {
            'Yes': 1.0,
            'Yes (Performance Loss)': 0.5,
            'No': 0.0,
            'N/A': np.nan
        }
        
        # Apply the mapping directly
        df_transformed[col] = df_transformed[col].map(special_mapping)
# Get all numeric columns (excluding those in multi_value_and_string_columns)
# numeric_cols = ['Year', 'Interaction_PANEL_Number of Selected Gestures']
numeric_cols = ['Interaction_PANEL_Number of Selected Gestures']


# Create empty similarity matrix
study_ids = df_transformed['ID'].tolist()
n_studies = len(study_ids)
similarity_matrix = pd.DataFrame(np.zeros((n_studies, n_studies)), 
                              index=study_ids, 
                              columns=study_ids)

# Calculate pairwise similarities
for i, id1 in enumerate(study_ids):
    row1 = df_transformed.loc[df_transformed['ID'] == id1].iloc[0]
    
    # For diagonal elements (self-similarity)
    similarity_matrix.loc[id1, id1] = 1.0
    
    # For upper triangular matrix
    for j in range(i+1, n_studies):
        id2 = study_ids[j]
        row2 = df_transformed.loc[df_transformed['ID'] == id2].iloc[0]
        
        # Calculate similarity
        sim = calculate_similarity(row1, row2, numeric_cols, multi_value_and_string_columns)
        
        # Fill both upper and lower triangular parts
        similarity_matrix.loc[id1, id2] = sim
        similarity_matrix.loc[id2, id1] = sim  # Symmetric matrix

# Calculate the mean and standard deviation of similarity values, excluding the diagonal
similarity_values = []
n = similarity_matrix.shape[0]
for i in range(n):
    for j in range(n):
        if i != j:  # Skip diagonal elements
            similarity_values.append(similarity_matrix.iloc[i, j])
            
mean_similarity = np.mean(similarity_values)
std_similarity = np.std(similarity_values)

# Create a new matrix with values in standard deviation units
similarity_matrix_std = similarity_matrix.copy()
for i in range(n):
    for j in range(n):
        if i != j:  # Skip diagonal elements
            similarity_matrix_std.iloc[i, j] = (similarity_matrix.iloc[i, j] - mean_similarity) / std_similarity
        else:
            # Set diagonal elements to NaN to exclude them from the visualization
            similarity_matrix_std.iloc[i, j] = np.nan

# Save the std similarity matrix to a CSV file
similarity_matrix_std.to_csv('database_similarity_datasets/normalized_database_similarity.csv')


## ABSTRACT SIMILARITY RECOMPUTE

def standard_normalize(df):
    # Compute mean and standard deviation, ignoring NaN values
    mean_val = np.nanmean(df.values)
    std_val = np.nanstd(df.values)
    
    # Avoid division by zero
    if std_val == 0:
        return df
    
    # Create a copy to avoid modifying the original
    result = df.copy()
    
    # Apply normalization only to non-NaN values
    mask = ~np.isnan(df.values)
    result.values[mask] = (df.values[mask] - mean_val) / std_val
    
    return result
    

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def get_gemini_embeddings(abstract):

    result = client.models.embed_content(
            model="gemini-embedding-exp-03-07",
            contents=abstract,
            config=types.EmbedContentConfig(task_type="CLUSTERING") # see here: https://ai.google.dev/gemini-api/docs/embeddings?hl=de

    )

    return result.embeddings[0].values

abstract_embeddings_df = pd.read_csv('abstract_similarity_datasets/data_with_embeddings.csv')
ids_with_embeddings = abstract_embeddings_df['ID'].to_numpy(dtype=int)
dataset_ids = df['ID'].to_numpy(dtype=int)
missing_ids = ids_with_embeddings[~np.isin(ids_with_embeddings, dataset_ids)]

new_rows = []

for missing_id in missing_ids:
    match = df.loc[df['ID'] == missing_id]
    if not match.empty:
        abstract = match['Abstract'].values[0]
        embedding = get_gemini_embeddings(abstract)

        new_rows.append({
            'ID': missing_id,
            'Abstract': abstract,
            'Gemini-Embedding': embedding
        })

# Create new DataFrame with the same column structure
new_abstract_embeddings = pd.DataFrame(new_rows, columns=['ID', 'Abstract', 'Gemini-Embedding'])

# Append to the existing embeddings DataFrame
abstract_embeddings_df = pd.concat([abstract_embeddings_df, new_abstract_embeddings], ignore_index=True)
abstract_embeddings_df.to_csv('abstract_similarity_datasets/data_with_embeddings.csv')

# Calculate cosine sims again
# 1. Extract embeddings as a list of vectors
embeddings = np.array(abstract_embeddings_df['Gemini-Embedding'].tolist())

# 2. Calculate pairwise cosine similarities
similarity_matrix = cosine_similarity(embeddings)

# 3. Create a DataFrame to store the similarities with paper IDs as indices
paper_ids = abstract_embeddings_df['ID'].tolist()
similarity_df = pd.DataFrame(similarity_matrix, index=paper_ids, columns=paper_ids)
np.fill_diagonal(similarity_df.values, np.nan)
similarity_df.to_csv('abstract_similarity_datasets/abstract_similarity.csv')

# Apply standard normalization
normalized_similarity_df = standard_normalize(similarity_df)
normalized_similarity_df.to_csv('abstract_similarity_datasets/normalized_abstract_similarity.csv')