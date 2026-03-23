# Copyright (c) 2025 Moveshelf
# See LICENSE file for details. 

# install required packages: pip install -r ../requirements.txt
import os, sys, json, re
parentFolder = os.path.dirname(os.path.dirname(__file__))
sys.path.append(parentFolder)

from moveshelf_api import util
from api.api_additions import MoveshelfApiCustomized
import urllib3

'''
## Readme - General
The datastructure of Moveshelf is organized as follows:
* Project: Projects are the highest level and associated to a single organization in Moveshelf.
* Subjects: Each project contains a list of subjects. At project level, access to the Electronic Health Record (EHR) of a subject can be made.
* Sessions: A session contains the relevant information for a specific measurement session and is typically defined by the date of the measurement.
* Conditions: Conditions specify a group of trials that were performed within a session.
* Trials: Trials, aka clips, are containers used to store our data. It consists of metadata and 'Additional Data', where the actual data of a trial is stored.

## Instructions for this example script
This script will, based on a given root folder and a project name, batch upload files to Moveshelf.
The script consists of two main functionalities;
1. Read data from a directory/folder
    a. function batchPrepare: reads subjects from a main root folder (for uploading data of multiple subjects)
    b. function prepareFilesinSubjectFolder: reads and structures the actual data per main subject folder (Sessions/Conditions/Trials/Files)
-> These functions can be called separately based on your use-case. 
NOTE: Check the bottom of the file for examples of how to use the functions (1 subject or batch).
2. Upload data to Moveshelf
    a. function uploadSubjectstoMoveshelf: takes the project name and the structured dictionary on where to find each file and uploads it to Moveshelf
-> This function also checks if your given project/subject/session/condition/trial exists already, and will create a new one if not found (except for the project).

**Important!**
Your input data should have the following structure for correct handling. Multiple subjects, sessions, conditions and trials can be handled.
Structure Batch upload:
    root_folder/ (input of the batchPrepare function!)
        subject_name/ (input of the prepareFilesinSubjectFolder function)
            session_name/
                condition_name/
                    trial_files (the code will sort and appoint a trial name based on the filename)

A GUI (see example in this repo) can be used to handle this Module, only having the root folder batch upload functionality.
'''

## DEFAULTS
defaultProject = '<organizationName/projectName>'  # e.g. support/demoProject

# Adjust to your own needs - Filter your extension to upload
extensions_to_upload = ('_TheiaKinematics.c3d', '.settings.xml','.avi')  # To upload all files, leave empty.

# For the current version of supported data types on Moveshelf, see https://moveshelf.com/docs/edit#supporteddatatypes
# All files (filtered or unfiltered) will be exported with datatype "raw", except:
allowed_files_video = ["mp4", "avi", "mov", "mkv"]
allowed_files_doc = ["pdf"]
allowed_files_img = ["png", "jpeg", "webp"]


def uploadSubjectstoMoveshelf(my_project=defaultProject, subject_files=[]):
    '''
    Uploads subject data to a project in Moveshelf by looping over:
    subject -> session -> trials -> files

    Structure:
        subject_files = [{
            "subject": subject_name,
            "sessions_to_upload": [
                {
                    "session": session_name,
                    "conditions": [
                        {
                            "condition": condition_name,
                            "trials": [
                                {
                                    "trial_name": trial_name,
                                    "files": [
                                        {"file_extension": ext, "filepath": path},
                                        ...
                                    ]
                                },
                                ...
                            ]
                        },
                        ...
                    ]
                },
                ...
            ]
        }]
    '''
    # Only start uploading if files were entered
    if not subject_files:
        return
    # If only one subject is entered, make it a list (still loopable)
    if type(subject_files) != type([]): subject_files = [subject_files]
    
    failed_uploads = []  # Save files that fail to upload after 5 tries to try again at the end
    
    # To track progress in output; calculate total number of files to upload
    total_files = sum(
        len(trial["files"])
        for subject in subject_files
        for session in subject["sessions_to_upload"]
        for condition in session["conditions"]
        for trial in condition["trials"]
    )
    uploaded_files = 0  # Upload tracker
    skipped_files = 0  # Skipped uploads due to current version tracker
    
    ## Setup the API
    # Load config
    with open(os.path.join(parentFolder,'mvshlf-config.json'), 'r') as configFile:
        data = json.load(configFile)

    # And overwrite if available
    personalConfig = os.path.join(parentFolder,'mvshlf-config.json')
    if os.path.isfile(personalConfig):
        with open(personalConfig, 'r') as configFile:
            data.update(json.load(configFile))

    api = MoveshelfApiCustomized(api_key_file = os.path.join(parentFolder,data['apiKeyFileName']), api_url = data['apiUrl'])

    ## Get available projects
    projects = api.getUserProjects()

    ## Select the project
    project_names = [project["name"] for project in projects if len(projects) > 0]
    try:
        idx_my_project = project_names.index(my_project)
    except ValueError:
        print(f"\n!! Error: The project name '{my_project}' does not exist or you do not have access using the current API key.")
        print("Try again with a valid project name...")
        success = False
        return success
    my_project_id = projects[idx_my_project]["id"]
    
    for subject_idx, subject_entry in enumerate(subject_files, 1):
        my_subject_name = subject_entry["subject"]
        subject_tally = f'{subject_idx}/{len(subject_files)}'
        print('\n---------------------------------------')
        print(f"Processing subject {subject_tally}: {my_subject_name}")
        subject_found = False
        
        # Search existing subjects by name
        if not subject_found and my_subject_name is not None:
            subjects = api.getProjectSubjects(my_project_id)
            for subject in subjects:        
                if my_subject_name == subject['name']:
                    subject_found = True
                    break
        if my_subject_name is None:
            print("Warning: We need the subject's name to be defined to be able to search for the subject.")
        
        ## Retrieve subject details if there was a match. Create new subject if there is no match
        if subject_found:
            subject_details = api.getSubjectDetails(subject["id"])
            subject_metadata = json.loads(subject_details.get("metadata", "{}"))
            print(
                f"-> Found subject with name: {subject_details['name']}, "
                f"and id: {subject_details['id']}. "
            )
        else:
            print(f"Couldn't find subject in project: {my_project}.")
            new_subject = api.createSubject(my_project, my_subject_name)
            subject_details = api.getSubjectDetails(new_subject["id"])
            print(f"-> Created new subject with name {new_subject}")
        print('---------------------------------------')
        
        for session_idx, session_entry in enumerate(subject_entry["sessions_to_upload"], 1):
            session = session_entry["session"]
            session_tally = f"{session_idx}/{len(subject_entry['sessions_to_upload'])}"
            print(f"\n-- Processing Session '{session}' ({session_tally}) of subject ({subject_tally})...")
            
            sessiondate = None
            # If a date is included in the session name, assign sessiondate
            date_match = re.match(r"^\d{4}-\d{2}-\d{2}", session_entry["session"])
            if date_match:
                sessiondate = date_match.group(0)
            try:
                # Load session metadata via a config_import JSON file
                local_metadata_json = os.path.join(session_entry["session_path"], "moveshelf_config_import.json")
                with open(local_metadata_json, "r") as file:
                    local_metadata = json.load(file)
                my_session_metadata = local_metadata.get("sessionMetadata", {})
                # Try to take the session date from the session_date in either the metadata json, or inside the sessionMetadata key
                sessiondate = (
                    local_metadata.get('session_date')
                    or my_session_metadata.get('session_date')
                    or None
                )

            except FileNotFoundError:
                print("No session metadata file found in the subject's session folder. Continuing without adding session metadata...")
                my_session_metadata = {}

            except json.JSONDecodeError:
                print("Session metadata file exists but is not valid JSON. Continuing without adding session metadata...")
                my_session_metadata = {}

            except Exception as e:
                print(f"Unexpected error while reading session metadata: {e}. Continuing without adding session metadata...")
                my_session_metadata = {}

            ## Find existing session
            sessions = subject_details.get('sessions', [])
            session_found = False
            for existing_session in sessions:
                try:
                    session_name = session_entry["session"]
                except:
                    session_name = ""
                if session_name == existing_session['projectPath'].split('/')[-2]:
                    session_id = existing_session['id']
                    session = api.getSessionById(session_id) # get all required info for that session
                    session_found = True
                    print(f"  (Session already exists)")
                    break

            ## Create new session if no match was found
            if not session_found:
                session_path = "/" + subject_details['name'] + "/" + session + "/"
                session = api.createSession(my_project, session_path, subject_details['id'], session_date=sessiondate)
                session_id = session['id']
                session = api.getSessionById(session_id) # get all required info for that session
                print(f"->  New session created with name '{session_entry['session']}'")
            
            # Update session metadata if available
            if my_session_metadata:
                api.updateSessionMetadataInfo(session_id=session_id, 
                                            session_name=session_entry["session"], 
                                            # For now, the given session name from the folder is not changed, even if the session date is different;
                                            # This behaviour can be changed here
                                            session_metadata=json.dumps({"metadata": my_session_metadata}),
                                            session_date=sessiondate)
            
            # Get conditions in the session
            conditions = []
            conditions = util.getConditionsFromSession(session, conditions)
            
            for condition_entry in session_entry["conditions"]:
                my_condition = condition_entry["condition"]
                condition_exists = any(c["path"].replace("/", "") == my_condition for c in conditions)
                condition = next(c for c in conditions if c["path"].replace("/", "") == my_condition) \
                    if condition_exists else {"path": my_condition, "clips": []}
                print(f"--- Condition: {condition['path']}")
                
                for trial_idx, trial_entry in enumerate(condition_entry["trials"], 1):
                    my_trial = trial_entry["trial_name"]
                    trial_tally = f'{trial_idx}/{len(condition_entry["trials"])}'
                    print(f"---- Processing Trial '{my_trial}' ({trial_tally}) (Session {session_tally}) (Subject {subject_tally})")

                    # Create trial
                    clip_id = util.addOrGetTrial(api, session, condition, my_trial)                    
                    for file_idx, file_entry in enumerate(trial_entry["files"], 1):
                        filepath = file_entry["filepath"]
                        filename = os.path.basename(filepath)
                        # Check file extension
                        ext = file_entry["file_extension"]
                        if ext in allowed_files_video:
                            data_type = "video"
                        elif ext in allowed_files_img:
                            data_type = "img"
                        elif ext in allowed_files_doc:
                            data_type = "doc"
                        else:
                            data_type = "raw"
                        
                        file_tally = f"{file_idx}/{len(trial_entry['files'])}"
                        print(f"({file_tally})    Uploading file: {filename} ({ext})...")
                        
                        # Check if a current version of your file is already uploaded on Moveshelf, skip if it is
                        is_current = None
                        try:
                            is_current = api.isCurrentVersionUploaded(filepath, clip_id)
                        except ValueError:
                            print("(Skipped check for if current version of file is already uploaded (file size too large (> 10MB)))")
                        
                        if is_current:
                            uploaded_files += 1
                            print(f"----- Skipped uploading file ({uploaded_files} of total {total_files}) (current version already uploaded)")
                            skipped_files += 1
                            continue
                        
                        # Upload file
                        try:
                            dataId = api.uploadAdditionalData(filepath, clip_id, data_type, filename)
                            uploaded_files += 1
                            print(f'----- Uploaded file ({uploaded_files} of total {total_files}) at id {dataId}')
                        except (urllib3.exceptions.MaxRetryError, urllib3.exceptions.ProtocolError):
                            failed_uploads.append((filepath, clip_id, data_type, filename))
                            print('\n---------------------------------------------------')
                            print(f'!!! Failed upload ({filename}) after 5 tries, trying again after all files have tried uploading')
                            print('---------------------------------------------------\n')
    if failed_uploads:
        print('\nList of files that failed to upload and will be retried:')
        print('---------------------------------------------------')
        for f in failed_uploads:
            print(f" - {f[3]} ({f[2]})")

        for failed_file_tuple in failed_uploads[:]:
            filepath, clip_id, data_type, filename = failed_file_tuple
            print(f"\nRetrying upload for {filename} ({data_type})...")
            try:
                dataId = api.uploadAdditionalData(filepath, clip_id, data_type, filename)
                print(f"Success on retry: {filename} (dataId={dataId})")
                failed_uploads.remove(failed_file_tuple)
            except (urllib3.exceptions.MaxRetryError, urllib3.exceptions.ProtocolError):
                print(f"Retry failed for {filename} ({data_type})")

        if failed_uploads:
            print('\nFiles that still failed after retry:')
            print('---------------------------------------------------')
            for f in failed_uploads:
                print(f" - {f[3]} ({f[2]})")
            success = False
            return Exception("Some files failed to upload after retrying.")
        else:
            print('\nAll files uploaded successfully on retry.')
    print('\n---------------------------------------------------')
    if skipped_files > 0:
        print("Done uploading.")
        print(f"-> Uploaded {total_files - skipped_files} files to Moveshelf")
        print(f"-> Skipped uploading {skipped_files} files (current version already uploaded)")
    else:
        print(f"Done uploading {total_files} files.")
    print('---------------------------------------------------')
    success = True
    return success


def prepareFilesinSubjectFolder(subjectdata_folder):
    '''
    Reads a subject folder and creates session dictionaries for upload.
    Structure:
        subject_name/
          session_name/
            condition/
              trial_files
    Returns:
        A list of files for one subject with the following structure:
        subject_files = {
            "subject": subject_name,
            "sessions_to_upload": [
                {
                    "session": session_name,
                    "conditions": [
                        {
                            "condition": condition_name,
                            "trials": [
                                {
                                    "trial_name": trial_name,
                                    "files": [
                                        {"file_extension": ext, "filepath": path},
                                        ...
                                    ]
                                },
                                ...
                            ]
                        },
                        ...
                    ]
                },
                ...
            ]
        }
    '''
    subject_name = os.path.basename(subjectdata_folder)
    sessions_to_upload = []

    # Iterate over session folders
    for session_name in os.listdir(subjectdata_folder):
        if session_name == ".DS_Store":
            continue
        session_path = os.path.join(subjectdata_folder, session_name)
        if not os.path.isdir(session_path):
            continue

        # Start dict for this session
        session_dict = {
            "session": session_name,
            "session_path": session_path,
            "conditions": []
        }

        # Iterate over conditions inside session
        for condition_name in os.listdir(session_path):
            if condition_name == ".DS_Store":
                continue
            condition_path = os.path.join(session_path, condition_name)
            if not os.path.isdir(condition_path):
                continue

            condition_dict = {
                "condition": condition_name,
                "trials": []
            }

            # Build trials in a dict to merge multiple files per trial
            trials_dict = {}
            
            # Check for files and inform user
            if len(os.listdir(condition_path)) == 0:
                NoFilesError = "No files were found in the Condition folder. Stopping upload. Check your folders(' structure)..."
                print(NoFilesError)
                return NoFilesError

            # Iterate over files in this condition
            for filename in sorted(os.listdir(condition_path)):
                if filename == ".DS_Store":
                    continue

                filepath = os.path.join(condition_path, filename)
                file_extension = filename.split(".", 1)[-1]
                if len(extensions_to_upload)==0 or filename.endswith(extensions_to_upload):
                    # Trial name parsing
                    if not '_' in filename:
                        trial_name = filename.split(".", 1)[0]
                    else:
                        trial_name = filename.split("_", 1)[0]

                    # Add trial if not yet in dict
                    if trial_name not in trials_dict:
                        trials_dict[trial_name] = {
                            "trial_name": trial_name,
                            "files": []
                        }

                    # Add file to this trial
                    trials_dict[trial_name]["files"].append({
                        "file_extension": file_extension,
                        "filepath": filepath
                    })
                else:
                    continue
                print(f"- '{filename}' at Trial '{trial_name}' ({subject_name}/{session_name})")

            # Add trials list to condition
            condition_dict["trials"] = list(trials_dict.values())
            session_dict["conditions"].append(condition_dict)

        # Add session dict to sessions list
        sessions_to_upload.append(session_dict)

    # Wrap everything in subject dict
    subject_files = {
        "subject": subject_name,
        "sessions_to_upload": sessions_to_upload
    }

    return subject_files

def batchPrepare(measurement_dir):
    '''
    Takes a directory path with subjectdatafolders and loops over them.
    Returns a list of subject files
    '''
    processed_subject_files = []
    all_subject_files = os.listdir(measurement_dir)
    all_subject_files.sort()
    print('\n---------------------------------------')
    print('Preparing the following files for upload to Moveshelf (Subject/Session):\n')
    for subjectdatafolder_name in all_subject_files:
        if subjectdatafolder_name == ".DS_Store":
            continue
        subjectdatafolder = os.path.join(measurement_dir, subjectdatafolder_name)
        processed_subject_files.append(prepareFilesinSubjectFolder(subjectdatafolder))
    return processed_subject_files


if __name__ == "__main__":
    ## Data for tests
    test_project = '<organizationName/projectName>'
    
    ## Single subject upload
    # test_subject_path = '<yourRootFolderPath/AnySubjectFolder>'
    # subject = prepareFilesinSubjectFolder(test_subject_path)
    # uploadSubjectstoMoveshelf(test_project, [subject])

    ## Batch subjects upload
    test_measurementdir = '<yourRootFolderPath>'  # Batch root folder housing all subject folders
    
    all_subject_files = batchPrepare(test_measurementdir)
    uploadSubjectstoMoveshelf(test_project, all_subject_files)
