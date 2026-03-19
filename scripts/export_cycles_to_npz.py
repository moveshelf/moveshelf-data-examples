# Copyright (c) 2026 Moveshelf
# See LICENSE file for details. 

"""
================================================================================
EXPORT GAIT CYCLES FROM MOVESHELF TO NPZ FILE
================================================================================

PURPOSE:
--------
This script downloads gait cycle data from Moveshelf using its API and exports it
to a NumPy NPZ file format. It processes JSON files containing normalized angle
data, maps them to standardized channels, and organizes them by project, subject,
session, and trial.

WORKFLOW:
---------
1. Load optional subject list or use all subjects from project
2. Connect to Moveshelf API and retrieve project information
3. Download JSON files (angles, events) for each subject/session/trial
4. Parse and map JSON data to standardized channel format
5. Export consolidated dataset to NPZ file

USAGE:
------
1. Install requirements: pip install -r ../requirements.txt
2. Configure paths and project name in the main block
3. Optionally provide a subject list file (one subject per line)
4. Run: python export_cycles_to_npz.py

The script will:
- Download data to the specified dataset_path directory
- Create an NPZ file: data_cycles_{project_name}.npz

CONFIGURATION:
--------------
Key variables to configure in the main block:
- subject_list_file: Path to optional text file with subject names
- dataset_path: Local directory where data will be downloaded
- moveshelf_project: Project name prefix to match in Moveshelf
- json_mapping_file: Path to channel mapping configuration
- forceProcessingOrDownload: Set True to re-download existing files

NPZ OUTPUT STRUCTURE:
---------------------
The output NPZ file contains:
- "data_mapping": Array of channel definitions (title, id, chartType)
- "project_paths": Relative paths to each trial
- "mean_values": 3D array (N × C × 100) of mean gait cycle values
- "std_values": 3D array (N × C × 100) of standard deviation values
- "events": Array of gait events for each trial

Where N = number of trials, C = number of channels, 100 = gait cycle points

REQUIREMENTS:
-------------
- numpy
- moveshelf_api
- requests
- Valid Moveshelf API credentials (mvshlf-config.json and API key file)
- Channel mapping file (util/data_mapping.json)

NOTES:
------
- Subject names with spaces or special characters are cleaned for file paths
- Duplicate subject names are handled by appending subject IDs
- Only 'Complete' status files are downloaded
- Files already downloaded are skipped unless forceProcessingOrDownload is True

================================================================================
"""

import re
from collections import Counter
import numpy as np
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

# Add parent folder to path for module imports
parent_folder = os.path.dirname(os.path.dirname(__file__))
sys.path.append(parent_folder)

from api.api_additions import MoveshelfApiCustomized
from moveshelf_api import util
import requests

# Use a requests.Session for connection pooling (improves download performance)
requests_session = requests.Session()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def download_file_task(download_info):
    """
    Download a single file from Moveshelf API.
    
    Args:
        download_info: Dictionary containing:
            - url: Download URL
            - filename_save: Full path where file should be saved
            - original_filename: Original name of the file
            - force_download: Whether to overwrite existing files
            
    Returns:
        Tuple of (success: bool, filename_save: str, message: str)
    """
    url = download_info['url']
    filename_save = download_info['filename_save']
    original_filename = download_info['original_filename']
    force_download = download_info['force_download']
    
    try:
        # Skip if file exists and not forcing redownload
        if not force_download and os.path.exists(filename_save):
            return (True, filename_save, f"Already exists")
        
        # Download file using session for connection pooling
        response = requests_session.get(url, timeout=120)
        response.raise_for_status()
        
        # Write file to disk
        with open(filename_save, "wb") as file:
            file.write(response.content)
            
        return (True, filename_save, "Downloaded successfully")
        
    except Exception as e:
        return (False, filename_save, f"Download failed: {str(e)}")


def get_all_files_in_dir_with_subdir(data_folder: str, extToCheck: str):
    """
    Recursively find all files with a specific extension in a directory.
    
    Args:
        data_folder: Root directory to search
        extToCheck: File extension to filter (e.g., '.json')
        
    Returns:
        List of full file paths matching the extension
    """
    ext_files = []
    for path, _, files in os.walk(data_folder):
        for name in files:
            if os.path.isfile(os.path.join(path, name)) and os.path.splitext(name)[-1].lower().endswith(extToCheck):
                ext_files.append(os.path.join(path, name))
    return ext_files


def load_mapping_file():
    """
    Load the channel mapping configuration from JSON file.
    
    Returns:
        List of channel mapping dictionaries
    """
    with open(json_mapping_file) as f:
        return json.load(f)


def get_json_dirs(dataset_path_: str):
    """
    Find all directories containing angle JSON files.
    
    Args:
        dataset_path_: Root directory to search
        
    Returns:
        List of directory paths containing angles.json or angles_normalized.json
    """
    json_dirs = []
    for path, _, files in os.walk(dataset_path_):
        for name in files:
            isFile = os.path.isfile(os.path.join(path, name))
            isJson = os.path.splitext(name)[-1].lower().endswith('json')
            isAngles = 'angles.json' in name or 'angles_normalized_json' in name
            if isFile and isJson and isAngles:
                if path not in json_dirs:
                    json_dirs.append(path)
    return json_dirs


# ============================================================================
# DATA MAPPING FUNCTIONS
# ============================================================================

def check_for_match_with_context(t_item, d_labels):
    """
    Check if a track has context (left/right) and if labels match with context.
    
    Args:
        t_item: Track item from data mapping with 'id' and 'trackNames'
        d_labels: List of data labels from JSON file
        
    Returns:
        Tuple of (has_context, has_match_with_context) booleans
    """
    has_context = t_item["id"].endswith("-left") or t_item["id"].endswith("-right")
    
    has_match_with_context = False
    context_indicator_idx = -1
    
    for trackName in t_item["trackNames"]:
        # Check for context match with right side
        find_context_match = has_context and (
            any("r" + trackName.lower() in d.lower() for d in d_labels) or 
            any("l" + trackName.lower() in d.lower() for d in d_labels)
        )
        
        if find_context_match and any("r" + trackName.lower() in d.lower() for d in d_labels):
            label_match = [d for d in d_labels if "r" + trackName.lower() in d.lower()][0]
            context_indicator_idx = label_match.lower().index("r" + trackName.lower())
            if label_match[context_indicator_idx] == 'R' and label_match[context_indicator_idx + 1].isupper():
                has_match_with_context = True
                
        # Check for context match with left side
        if find_context_match and any("l" + trackName.lower() in d.lower() for d in d_labels):
            label_match = [d for d in d_labels if "l" + trackName.lower() in d.lower()][0]
            context_indicator_idx = label_match.lower().index("l" + trackName.lower())
            if label_match[context_indicator_idx] == 'L' and label_match[context_indicator_idx + 1].isupper():
                has_match_with_context = True
                
    return has_context, has_match_with_context


def check_if_track_in_mapping(t_item_id, trackName, d_label, has_context, has_match_with_context):
    """
    Check if a track from JSON data matches a mapping definition.
    
    Args:
        t_item_id: Track ID from mapping (e.g., 'kinematics-pelvic-tilt-left')
        trackName: Track name to search for
        d_label: Data label from JSON file
        has_context: Whether the track has left/right context
        has_match_with_context: Whether context indicators are properly formatted
        
    Returns:
        True if track matches mapping criteria, False otherwise
    """
    if has_context and has_match_with_context:
        # Only match if we have proper context indicators (L/R prefix)
        if t_item_id.endswith("-left") and "l" + trackName.lower() in d_label.lower():
            idx = d_label.lower().index("l" + trackName.lower())
            if d_label[idx] == 'L' and d_label[idx + 1].isupper():
                return True
                
        elif t_item_id.endswith("-right") and "r" + trackName.lower() in d_label.lower():
            idx = d_label.lower().index("r" + trackName.lower())
            if d_label[idx] == 'R' and d_label[idx + 1].isupper():
                return True
                
    elif trackName.lower() in d_label.lower():
        # Simple name match without context
        return True
        
    return False


# ============================================================================
# DATA LOADING AND PROCESSING
# ============================================================================

# ============================================================================
# DATA LOADING AND PROCESSING
# ============================================================================

def _load_and_map_json_data(first_trial_added):
    """
    Load and process JSON angle data from directories, mapping to standardized channels.
    
    This function:
    1. Reads angles.json or angles_normalized.json files
    2. Extracts mean and standard deviation values for gait cycles
    3. Maps data to standardized channel definitions
    4. Loads associated event data if available
    5. Consolidates data into NPZ dictionary structure
    s
    Args:
        first_trial_added: Boolean indicating if this is the first data batch
        
    Returns:
        Updated first_trial_added boolean
        
    Side Effects:
        Updates global npz_dict with processed data
    """
    # Pre-allocate arrays for all trials
    all_mean_values = np.empty((len(json_dirs), len(data_mapping), 100))
    all_mean_values[:] = np.nan
    all_std_values = np.empty((len(json_dirs), len(data_mapping), 100))
    all_std_values[:] = np.nan
    all_events = np.empty((len(json_dirs)), dtype=object)
    all_events[:] = None
    
    project_paths = []
    rows_without_data = []
    
    # Process each JSON directory
    for iFile, json_dir in enumerate(json_dirs):
        json_files = [f for f in os.listdir(json_dir) 
                     if os.path.isfile(os.path.join(json_dir, f)) 
                     and os.path.splitext(f)[-1].lower().endswith('json')]
        
        # Check what types of files are available
        has_angles_normalized = any("angles_normalized.json" in x for x in json_files)
        has_angles = any("angles.json" in x for x in json_files)
        has_events = any("event.json" in x for x in json_files)
        
        d_angles = None
        d_events = None
        has_data = False
        skip_file = False
        
        # ----------------------------------------------------------------
        # Load angle data (prefer normalized, fallback to regular)
        # ----------------------------------------------------------------
        if not has_angles_normalized and has_angles:
            file_to_load = json_files[json_files.index("angles.json")]
            with open(os.path.join(json_dir, file_to_load)) as f:
                d_angles = json.load(f)
                
                # Verify we have cycle data (not time-series)
                if "data" in d_angles:
                    for item in d_angles['data']:
                        if "values" in item:
                            if "perc" in item["values"][0]:
                                break  # Valid cycle data
                            elif not "perc" in item["values"][0] or len(item["values"]) > 120:
                                skip_file = True  # Time-series data, skip
                                break

        elif has_angles_normalized:
            file_to_load = json_files[json_files.index("angles_normalized.json")]
            if os.path.getsize(os.path.join(json_dir, file_to_load)) > 0:
                with open(os.path.join(json_dir, file_to_load)) as f:
                    d_angles = json.load(f)
            else:
                continue  # Empty file, skip

        # ----------------------------------------------------------------
        # Process angle data and map to channels
        # ----------------------------------------------------------------
        if not skip_file and d_angles is not None and "data" in d_angles:
            d_labels = [d["label"] for d in d_angles["data"]]
            
            for d_item in d_angles["data"]:
                d_label = d_item["label"]
                d_values = d_item["values"]
                
                # Check what statistics are available
                has_mean = any("mean" in v for v in d_values)
                has_cycle = any("cycle-0" in v for v in d_values)
                has_std = any("std" in v for v in d_values)
                
                d_mean = []
                d_std = []
                
                # Extract mean values
                if has_mean:
                    d_mean = [d["mean"] for d in d_values if "mean" in d]
                elif has_cycle:
                    # Calculate mean from individual cycles
                    for v in d_values:
                        cycle_values = [v[v_item] for v_item in v 
                                       if "cycle" in v_item and v[v_item] is not None]
                        sample_mean = np.mean(cycle_values) if cycle_values else np.nan
                        d_mean.append(sample_mean)

                # Extract standard deviation values
                if has_std:
                    d_std = [d["std"] for d in d_values if "std" in d]
                elif has_cycle:
                    # Calculate std from individual cycles
                    for i, v in enumerate(d_values):
                        cycle_vals = [val for k, val in v.items()
                                     if "cycle" in k and val is not None]
                        
                        if len(cycle_vals) > 1:
                            mean_val = d_mean[i]
                            sample_std = np.sqrt(
                                sum((x - mean_val) ** 2 for x in cycle_vals) 
                                / (len(cycle_vals) - 1)
                            )
                            d_std.append(sample_std)
                        else:
                            d_std.append(np.nan)

                # Map data to standardized channels
                if len(d_mean) > 0:
                    for idx, t_item in enumerate(data_mapping):
                        has_context, has_match_with_context = check_for_match_with_context(t_item, d_labels)
                        
                        for trackName in t_item["trackNames"]:
                            trackFound = check_if_track_in_mapping(
                                t_item["id"], trackName, d_label, 
                                has_context, has_match_with_context
                            )
                            
                            if trackFound:
                                has_data = True
                                all_mean_values[iFile, idx, :] = d_mean
                                if len(d_std) > 0:
                                    all_std_values[iFile, idx, :] = d_std
                                    
        # ----------------------------------------------------------------
        # Load event data if available
        # ----------------------------------------------------------------
        events_found = False
        if has_events:
            file_to_load = json_files[json_files.index("event.json")]
            if os.path.getsize(os.path.join(json_dir, file_to_load)) > 0:
                with open(os.path.join(json_dir, file_to_load)) as f:
                    d_events = json.load(f)
                    events_found = True
            else:
                continue  # Empty file, skip

        # ----------------------------------------------------------------
        # Store project path and event data
        # ----------------------------------------------------------------
        project_path = json_dir.replace("\\", "/").split(dataset_path)
        project_path_save = project_path[1] if len(project_path) > 1 else project_path[0]
        project_paths.append(project_path_save)
        
        if not has_data:
            rows_without_data.append(int(iFile))
        elif events_found:
            all_events[iFile] = d_events["events"]

    # ----------------------------------------------------------------
    # Clean up arrays by removing rows without valid data
    # ----------------------------------------------------------------
    project_paths = np.array(project_paths)
    if len(rows_without_data) > 0:
        all_mean_values = np.delete(all_mean_values, rows_without_data, 0)
        all_std_values = np.delete(all_std_values, rows_without_data, 0)
        project_paths = np.delete(project_paths, rows_without_data, 0)
        all_events = np.delete(all_events, rows_without_data, 0)

    # ----------------------------------------------------------------
    # Add or concatenate data to NPZ dictionary
    # ----------------------------------------------------------------
    if not first_trial_added:
        # First batch: initialize arrays
        npz_dict["project_paths"] = project_paths
        npz_dict["mean_values"] = all_mean_values
        npz_dict["std_values"] = all_std_values
        npz_dict["events"] = all_events
        first_trial_added = True
    else:
        # Subsequent batches: concatenate to existing arrays
        npz_dict["project_paths"] = np.concatenate((npz_dict["project_paths"], project_paths), axis=0)
        npz_dict["mean_values"] = np.concatenate((npz_dict["mean_values"], all_mean_values), axis=0)
        npz_dict["std_values"] = np.concatenate((npz_dict["std_values"], all_std_values), axis=0)
        npz_dict["events"] = np.concatenate((npz_dict["events"], all_events), axis=0)

    return first_trial_added


# ============================================================================
# MAIN EXECUTION
# ============================================================================
# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # ========================================================================
    # STEP 1: LOAD CONFIGURATION AND SUBJECT LIST
    # ========================================================================
    
    # Optional: Load subject list from a text file
    # If the file doesn't exist, all subjects from the project will be processed
    subject_list_file = "C:/Temp/subject_list.txt"
    subject_list = []
    use_all_subjects = False
    
    if os.path.exists(subject_list_file):
        with open(subject_list_file, "r", encoding='utf-8') as f:
            subject_list = [line.strip().replace('\xa0', '') for line in f.readlines()]
        print(f"Loaded {len(subject_list)} subjects from {subject_list_file}")
    else:
        print(f"Subject list file not found at {subject_list_file}.")
        print("Will process all subjects in the project.")
        use_all_subjects = True
    
    # Track duplicate subject names for proper identification
    subject_counts = Counter(subject_list)
    subject_duplicates = {name: count > 1 for name, count in subject_counts.items()}

    # Configuration parameters
    dataset_path = "C:/Temp/downloaded_data"  # Local directory to save downloaded files
    moveshelf_project = "org/project_name"  # Process projects matching this string
    json_mapping_file = os.path.join(parent_folder, "util", "data_mapping.json")
    forceProcessingOrDownload = False  # Set True to re-download existing files
    first_trial_added = False
    
    # Prepare output filename
    moveshelf_project_replaced = moveshelf_project.replace("/", "_")
    npz_filename = os.path.join(dataset_path, f"data_cycles_{moveshelf_project_replaced}.npz")

    # ========================================================================
    # STEP 2: INITIALIZE DATA STRUCTURES
    # ========================================================================
    
    npz_dict = {}
    data_mapping = load_mapping_file()

    # Store channel mapping in NPZ output
    npz_dict["data_mapping"] = []
    for item in data_mapping:
        npz_dict["data_mapping"] = np.append(npz_dict["data_mapping"], {
            "title": item["title"],
            "id": item["id"],
            "chartType": item["chartType"]
        })

    json_dirs_dict = {}  # Will store directories for each subject
    file_extensions_to_download = [".json", ".JSON"]

    # ========================================================================
    # STEP 3: SETUP MOVESHELF API CONNECTION
    # ========================================================================
    
    personal_config = os.path.join(parent_folder, "mvshlf-config.json")
    if not os.path.isfile(personal_config):
        raise FileNotFoundError(
            f"Configuration file '{personal_config}' is missing.\n"
            "Ensure the file exists with the correct name and path."
        )

    with open(personal_config, "r") as config_file:
        data = json.load(config_file)

    api = MoveshelfApiCustomized(
        api_key_file=os.path.join(parent_folder, data["apiKeyFileName"]),
        api_url=data["apiUrl"],
    )

    # ========================================================================
    # STEP 4: DOWNLOAD DATA FROM MOVESHELF (WITH MULTITHREADING)
    # ========================================================================
    
    print("\n" + "="*80)
    print("PHASE 1: DOWNLOADING DATA FROM MOVESHELF")
    print("="*80 + "\n")
    
    projects = api.getUserProjects()
    project_names = [project["name"] for project in projects if len(projects) > 0]
    
    # Collect all download tasks before executing them in parallel
    download_tasks = []
    
    for project_name in project_names:
        if moveshelf_project in project_name:
            idx_my_project = project_names.index(project_name)
            my_project_id = projects[idx_my_project]["id"]
            
            print(f"\nProcessing project: {project_name}")

            # Get all subjects with their clips
            subjects = api.getProjectSubjectsWithClips(my_project_id)
            project_subject_names = [subject['name'].strip() for subject in subjects if len(subjects) > 0]
            
            # If no subject list file provided, use all subjects from project
            if use_all_subjects:
                subject_list = project_subject_names
                subject_counts = Counter(subject_list)
                subject_duplicates = {name: count > 1 for name, count in subject_counts.items()}
                print(f"Processing all {len(subject_list)} subjects from project")

            # Process each subject in the list
            for subject_name, has_duplicates in subject_duplicates.items():
                if subject_name not in project_subject_names:
                    print(f"  ⚠ Subject '{subject_name}' not found in project, skipping")
                    continue
                    
                for subject in subjects:
                    if subject['name'].strip() != subject_name:
                        continue
                        
                    # Create pseudonym (add ID suffix if duplicate names exist)
                    pseudonym = subject['name'].strip() if not has_duplicates else f"{subject['name'].strip()}_{subject['id']}"
                    
                    if pseudonym == 'test':
                        continue

                    print(f"  Processing subject: {pseudonym}")
                    json_dirs_dict[f"{project_name}/{pseudonym}"] = []
                    
                    # Iterate through sessions, conditions, and clips
                    sessions = subject.get('sessions', [])
                    for session in sessions:
                        conditions = util.getConditionsFromSession(session, [])
                        
                        for condition in conditions:
                            clips = condition.get('clips', [])
                            
                            for clip in clips:
                                # Construct save path
                                filename_dir_save = os.path.join(
                                    dataset_path, project_name, pseudonym,
                                    session['projectPath'].split('/')[2],
                                    condition['path'], clip['title']
                                )
                                # Remove invalid filename characters
                                filename_dir_save = re.sub(r'[*?"<>|]', "", filename_dir_save)
                                
                                # Get additional data (JSON files) for this clip
                                existing_additional_data = api.getAdditionalData(clip['id'])
                                
                                # Prepare download tasks for each file
                                for data in existing_additional_data:
                                    filename, file_extension = os.path.splitext(data['originalFileName'])
                                    
                                    # Filter by extension if specified
                                    if len(file_extensions_to_download) > 0 and file_extension not in file_extensions_to_download:
                                        continue

                                    upload_status = data['uploadStatus']
                                    
                                    if upload_status == 'Processing':
                                        print(f"    ⏳ File '{data['originalFileName']}' still processing, skipping")
                                        
                                    elif upload_status == 'Complete':
                                        # Create directory if needed
                                        if not os.path.isdir(filename_dir_save):
                                            os.makedirs(filename_dir_save, exist_ok=True)
                                            
                                        filename_save = os.path.join(filename_dir_save, data['originalFileName'])
                                        
                                        # Track this directory for later processing
                                        if filename_dir_save not in json_dirs_dict[f"{project_name}/{pseudonym}"]:
                                            json_dirs_dict[f"{project_name}/{pseudonym}"].append(filename_dir_save)
                                        
                                        # Add download task to list
                                        download_tasks.append({
                                            'url': data['originalDataDownloadUri'],
                                            'filename_save': filename_save,
                                            'original_filename': data['originalFileName'],
                                            'force_download': forceProcessingOrDownload
                                        })

                                    else:
                                        print(f"    ⚠ File '{data['originalFileName']}' status: {upload_status}, skipping")
    
    # Execute all downloads in parallel using ThreadPoolExecutor
    if len(download_tasks) > 0:
        print(f"\n{'='*80}")
        print(f"Starting parallel download of {len(download_tasks)} files...")
        print(f"{'='*80}\n")
        
        successful_downloads = 0
        skipped_files = 0
        failed_downloads = 0
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(download_file_task, download_tasks))
        
        # Process results
        for success, filename, message in results:
            if success:
                if "Already exists" in message:
                    skipped_files += 1
                    print(f"  ✓ {os.path.basename(filename)}: {message}")
                else:
                    successful_downloads += 1
                    print(f"  ⬇ {os.path.basename(filename)}: {message}")
            else:
                failed_downloads += 1
                print(f"  ✗ {os.path.basename(filename)}: {message}")
        
        print(f"\n{'='*80}")
        print(f"Download Summary:")
        print(f"  - Successfully downloaded: {successful_downloads}")
        print(f"  - Already existed (skipped): {skipped_files}")
        print(f"  - Failed: {failed_downloads}")
        print(f"  - Total: {len(download_tasks)}")
        print(f"{'='*80}\n")
    else:
        print("\nNo files to download.\n")

    # ========================================================================
    # STEP 5: PROCESS DOWNLOADED JSON FILES
    # ========================================================================
    
    print("\n" + "="*80)
    print("PHASE 2: PROCESSING JSON FILES AND CREATING NPZ")
    print("="*80 + "\n")
    
    for project_name in project_names:
        if moveshelf_project in project_name:
            idx_my_project = project_names.index(project_name)
            my_project_id = projects[idx_my_project]["id"]

            # Get subject IDs (lighter API call than getProjectSubjectsWithClips)
            subjects = api.getProjectSubjectIds(my_project_id)
            project_subject_names = [subject['name'].strip() for subject in subjects if len(subjects) > 0]
            
            # If no subject list file provided, use all subjects from project
            if use_all_subjects:
                subject_list = project_subject_names
                subject_counts = Counter(subject_list)
                subject_duplicates = {name: count > 1 for name, count in subject_counts.items()}
            
            # Process each subject's data
            for subject_name, has_duplicates in subject_duplicates.items():
                if subject_name not in project_subject_names:
                    print(f"  ⚠ Subject '{subject_name}' not found in project, skipping")
                    continue
                    
                for subject in subjects:
                    if subject['name'].strip() != subject_name:
                        continue
                        
                    pseudonym = subject['name'].strip() if not has_duplicates else f"{subject['name'].strip()}_{subject['id']}"
                    folder_path = f"{project_name}/{pseudonym}"

                    # Load and map JSON data for this subject
                    json_dirs = json_dirs_dict.get(folder_path, [])
                    if len(json_dirs) == 0:
                        print(f"  ⚠ No data found for: {folder_path}")
                    else:
                        print(f"  Processing {len(json_dirs)} trials for: {pseudonym}")
                        first_trial_added = _load_and_map_json_data(first_trial_added)

    # ========================================================================
    # STEP 6: SAVE NPZ FILE
    # ========================================================================
    
    print("\n" + "="*80)
    print("SAVING NPZ FILE")
    print("="*80 + "\n")
    
    np.savez(npz_filename, **npz_dict)
    print(f"✓ Successfully saved: {npz_filename}")
    print("\nExport complete!\n\n")

