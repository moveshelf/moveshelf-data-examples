# Copyright (c) 2026 Moveshelf
# See LICENSE file for details. 

# install required packages: pip install -r ../requirements.txt
 
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
parent_folder = os.path.dirname(os.path.dirname(__file__))
sys.path.append(parent_folder)

"""
================================================================================
LOAD AND PLOT GAIT CYCLES FROM NPZ FILE
================================================================================

PURPOSE:
--------
This script demonstrates how to load, process, and visualize gait analysis data
stored in NumPy NPZ format that has been exported using the export_cycles_to_npz.py script.
It extracts motion data across multiple organizational
levels (dataset, project, subject) and plots average angles over the
gait cycle.

USAGE:
------
1. Ensure you have a data_cycles_*.npz file in the scripts directory
2. Modify the npz_filename variable to point to your NPZ file
3. Run the script: python load_and_plot_cycles_from_npz.py

The script will generate a matplotlib plot showing:
- Dataset average (grey) - optional, controlled by calculate_avg_for_whole_set
- First project average (red)
- Second subject from first project (green)

REQUIREMENTS:
-------------
- numpy
- matplotlib
- NPZ file containing gait cycle data

NPZ FILE STRUCTURE:
-------------------
The NPZ file must contain the following arrays:

1. "project_paths" (array of strings, length N):
   Format: "project/subject/session/condition/trial"
   
2. "data_mapping" (array of dictionaries):
   Mapping of data channels to joint angles
   Example structure:
   [
     {
       "title": "Pelvic tilt left",
       "id": "kinematics-pelvic-tilt-left",
       "chartType": "Kinematics"
     },
     {
       "title": "Knee flexion/extension left",
       "id": "kinematics-knee-flexion-left",
       "chartType": "Kinematics"
     },
     {
       "title": "Knee flexion/extension right",
       "id": "kinematics-knee-flexion-right",
       "chartType": "Kinematics"
     }
   ]
   
3. "mean_values" (3D array, shape: N × C × 100):
   N = number of trials
   C = number of channels (defined by data_mapping)
   100 = gait cycle points (0-100%)
   Contains NaN where data is unavailable

CONFIGURATION:
--------------
- calculate_avg_for_whole_set: Set to True to compute and plot dataset-wide average
  (disabled by default for performance)
- dataset_path: Directory containing the NPZ file (defaults to script directory)
- npz_filename: Path to the NPZ data file
- selected_angle_id: ID of the joint angle to plot (must match an ID in data_mapping)

OUTPUT:
-------
Matplotlib figure showing mean ± standard deviation bands for selected joint angle
across the gait cycle at different hierarchical levels.

NOTES:
------
- The script uses memory mapping (mmap_mode="r") to efficiently handle large datasets
- NaN values are automatically excluded from calculations
- Standard deviation is computed using Welford's online algorithm for dataset averages

================================================================================
"""

# Set to True to calculate and plot the average across the entire dataset
# Note: This can be slow for large datasets, hence disabled by default
calculate_avg_for_whole_set = False

# Path to the directory containing the NPZ file (defaults to script directory)
dataset_path = os.path.dirname(__file__)

# Full path to the NPZ file containing gait cycle data
npz_filename = os.path.join(dataset_path, "my_data_file.npz")

selected_angle_id = "kinematics-knee-flexion-left"  # ID of the angle to plot (from data_mapping)

# ============================================================================
# LOAD DATA
# ============================================================================

# Load NPZ file using memory mapping for efficient handling of large datasets
# mmap_mode="r" prevents loading entire file into memory at once
data = np.load(npz_filename, mmap_mode="r", allow_pickle=True)
data_mapping = data["data_mapping"]

print("Mapping used for the joint angles:")
print(data_mapping)

# ============================================================================
# ORGANIZE DATA BY HIERARCHY (PROJECT > SUBJECT > TRIALS)
# ============================================================================

# Parse project paths to group trials by project and subject
# Expected path format: "project/subject/session/condition/trial"
subject_trials = {}  # Will store trial indices grouped by project and subject
projects = {}  # Nested dictionary: projects[project_name][subject_name] = [trial_indices]
project_paths = data["project_paths"]

for i, path in enumerate(data["project_paths"]):
    parts = path.split("/")
    # Extract project and subject names from path structure
    project_name = parts[-5]  # 5th from end: project name
    subject_name = parts[-4]  # 4th from end: subject name

    # Initialize nested dictionary structure
    if project_name not in projects:
        projects[project_name] = {}

    if subject_name not in projects[project_name]:
        projects[project_name][subject_name] = []

    # Store trial index for this project/subject combination
    projects[project_name][subject_name].append(i)

# ============================================================================
# SETUP FOR PLOTTING
# ============================================================================

# Identify the angle to plot (selected_angle_id)
left_angle_id = next(i for i, item in enumerate(data_mapping) if item["id"] == selected_angle_id)

# Gait cycle percentage points (1-100%)
perc = np.arange(1, 101, 1)

# Initialize the figure
plt.figure(figsize=(8, 6))

# Define colors for different organizational levels
dataset_color = "grey"   # Color for entire dataset average
project_color = "red"    # Color for project-level average
subject_color = "green"  # Color for subject-level average

# ============================================================================
# COMPUTE AND PLOT DATASET-LEVEL STATISTICS (OPTIONAL)
# ============================================================================

if calculate_avg_for_whole_set:
    # Compute statistics for the entire dataset using Welford's online algorithm
    # This approach minimizes memory usage for large datasets
    mean_left_running = np.zeros(100)  # Running mean (100 points in gait cycle)
    variance_left = np.zeros(100)       # Running variance accumulator
    n_samples = 0                        # Count of valid trials

    # Iterate through all trials without loading entire dataset into memory
    for i_trial in range(len(data["mean_values"])):
        trial_data = data["mean_values"][i_trial, left_angle_id, :]
        
        # Skip trials with missing data
        if np.isnan(trial_data).any():
            continue
        
        # Update running statistics using Welford's algorithm
        n_samples += 1
        delta = trial_data - mean_left_running
        mean_left_running += delta / n_samples
        delta2 = trial_data - mean_left_running
        variance_left += delta * delta2

    # Compute final standard deviation from accumulated variance
    std_left_final = np.sqrt(variance_left / (n_samples - 1)) if n_samples > 1 else np.zeros(100)

    # Plot dataset average with standard deviation band
    plt.plot(perc, mean_left_running, color=dataset_color, linestyle="-", label="Dataset average")
    plt.fill_between(perc, mean_left_running - std_left_final, mean_left_running + std_left_final, 
                     color=dataset_color, alpha=0.2)

# ============================================================================
# COMPUTE AND PLOT PROJECT-LEVEL STATISTICS
# ============================================================================

# Analyze the first project in the dataset
first_project_name = list(projects.keys())[0]
first_project_subjects = projects[first_project_name]
project_left_angles = []

# Collect all valid trials from all subjects in this project
for trials in first_project_subjects.values():
    for i_trial in trials:
        trial_data = data["mean_values"][i_trial, left_angle_id, :]
        
        # Skip trials with missing data
        if np.isnan(trial_data).any():
            continue
            
        project_left_angles.append(trial_data)

# Convert to numpy array and compute statistics
project_left_angles = np.array(project_left_angles)
mean_class = np.mean(project_left_angles, axis=0)
std_class = np.std(project_left_angles, axis=0)

# Plot project average with standard deviation band
plt.plot(perc, mean_class, color=project_color, linestyle="-", label=f"{first_project_name} average")
plt.fill_between(perc, mean_class - std_class, mean_class + std_class, 
                 color=project_color, alpha=0.2)

# ============================================================================
# COMPUTE AND PLOT SUBJECT-LEVEL STATISTICS
# ============================================================================

# Analyze the second subject from the first project
second_subject_name = list(projects[first_project_name].keys())[1]
subject_trials = projects[first_project_name][second_subject_name]

subject_left_angles = []

# Collect all valid trials for this specific subject
for i_trial in subject_trials:
    trial_data = data["mean_values"][i_trial, left_angle_id, :]
    
    # Skip trials with missing data
    if np.isnan(trial_data).any():
        continue
        
    subject_left_angles.append(trial_data)

# Convert to numpy array and compute statistics
subject_left_angles = np.array(subject_left_angles)
mean_subject = np.mean(subject_left_angles, axis=0)
std_subject = np.std(subject_left_angles, axis=0)

# Plot subject average with standard deviation band
plt.plot(perc, mean_subject, color=subject_color, linestyle="-", 
         label=f"{second_subject_name}, Project {first_project_name}")
plt.fill_between(perc, mean_subject - std_subject, mean_subject + std_subject, 
                 color=subject_color, alpha=0.2)

# ============================================================================
# FINALIZE AND DISPLAY PLOT
# ============================================================================
# Add labels and formatting
plt.title(f"Average {selected_angle_id.replace('-', ' ').title()} Over Gait Cycle")
plt.xlabel("Gait Cycle Percentage (%)")
plt.ylabel("Angle (deg)")
plt.legend()
plt.grid(True, alpha=0.3)

# Display the plot
plt.show()