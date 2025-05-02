from moveshelf_api.api import MoveshelfApi
import os
import sys
import json
parent_folder = os.path.dirname(os.path.dirname(__file__))
sys.path.append(parent_folder)

# Readme
# This script extracts all the gait abnormalities of all sessions of all
# subjects within a project, and saves each gait abnormality dictionary
# in a file called "gaitAbnormalities_<subjectID>_<sessionDate>_<clinicianID>.json".
 
## General configuration. Set values before running the script
# Specify the project you want to extract the gait evaluations from.
my_project = "<organizationName/projectName>"  # e.g. "internal/internal_testproject_GAIT.SCRIPT"

# Specify the IDs of the clinicians that performed the evaluations you want to
# extract.
# Note: an empty list will extract all evaluations.
clinician_ids = ["<clinician_id1>", "<clinician_id2>"]

dataFolderSave = "C:/Temp/annotations_export"   # data folder where data should be saved
# Ensure the folder exists
os.makedirs(dataFolderSave, exist_ok=True)

## Setup the API
# Load config
personal_config = os.path.join(parent_folder, "mvshlf-config.json")
if not os.path.isfile(personal_config):
    raise FileNotFoundError(
        f"Configuration file '{personal_config}' is missing.\n"
        "Ensure the file exists with the correct name and path."
    )

with open(personal_config, "r") as config_file:
    data = json.load(config_file)

api = MoveshelfApi(
    api_key_file=os.path.join(parent_folder, data["apiKeyFileName"]),
    api_url=data["apiUrl"],
)

## Get available projects
projects = api.getUserProjects()

## Select the project
project_names = [project["name"] for project in projects if len(projects) > 0]
idx_my_project = project_names.index(my_project)
my_project_id = projects[idx_my_project]["id"]

subjects = api.getProjectSubjects(my_project_id)
for subject in subjects:
    subject_id = subject["id"]
    subject_name = subject["name"]
    subject_details = api.getSubjectDetails(subject_id)
    ## Get sessions
    sessions = subject_details.get("sessions", [])
    for session in sessions:
        session_id = session["id"]
        try:
            session_name = session['projectPath'].split('/')[2]
        except:
            session_name = ""

        session = api.getSessionById(session_id)
        session_metadata = session.get("metadata", None)
        gait_evaluations = json.loads(session_metadata).get('gaitScriptEvaluation', {}) if session_metadata else {}


        # Loop over all gait evaluations and exclude the ids that are not in the list
        # of clinician ids
        for gait_evaluation in gait_evaluations:
            if len(clinician_ids) == 0 or gait_evaluation['id'] in clinician_ids:
                gait_abnormalities = gait_evaluation.get('state', {}).get('gaitAbnormalities', {})
                file_name = f"gaitAbnormalities_{subject_name}_{session_name}_{gait_evaluation['id']}.json"
                print(f'Writing to file: {file_name}')
                with open(os.path.join(dataFolderSave, file_name), 'w') as f:
                    json.dump(gait_abnormalities, f, indent=2)
