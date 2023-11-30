from moveshelf_api.api import MoveshelfApi
import os
import sys
import json
import time
parentFolder = os.path.dirname(os.path.dirname(__file__))
sys.path.append(parentFolder)

# Readme
# Specify the global id of the session you want to extract the gait evaluations
# from. You can retrieve this by navigating moveshelf.com on the desired
# project, patient and session. The global id is the last part of the url:
#   http://moveshelf.com/project/<projectId>/session/<session_global_id>
session_global_id = "<session_global_id>"

# Specify the IDs of the clinicians that performed the evaluations you want to
# extract.
# Note: an empty array will extract all of the evaluations.
clinician_ids = ["<clinician_id1>", "<clinician_id2>"]

dataFolderSave = r'C:\temp\1'   # data folder where data should be saved
dataFolderSave = r'C:\Users\MarcoGalassi\dev\moveshelf-data-examples'

# Setup the API
# Load config
with open(os.path.join(parentFolder, 'mvshlf-config.json'), 'r') as configFile:
    data = json.load(configFile)

api = MoveshelfApi(api_key_file=os.path.join(
    parentFolder, data['apiKeyFileName']), api_url=data['apiUrl'])

try:
    session = api.getSessionById(session_global_id)
    session_metadata = json.loads(session['metadata'])
    gait_evaluations = session_metadata['gaitScriptEvaluation']
except Exception as e:
    print(f"Error occurred while retrieving gait evaluations: {str(e)}")
    sys.exit(1)

# Loop over all gait evaluations and exlude the ids that are not in the list
# of clinician ids
gait_evaluations_to_download = []
for gait_evaluation in gait_evaluations:
    if len(clinician_ids) == 0 or gait_evaluation['id'] in clinician_ids:
        gait_evaluations_to_download.append(gait_evaluation)

timestamp = int(time.time())
file_name = f"gait_evaluations_{timestamp}.json"

# Write to file
print(f'Writing to file: {file_name}')
with open(os.path.join(dataFolderSave, file_name), 'w') as f:
    json.dump(gait_evaluations_to_download, f, indent=2)

print('Done')
