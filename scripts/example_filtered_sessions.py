"""
Script to retrieve and print filtered sessions and export metadata to Excel.
"""
# install required packages: pip install -r ../requirements.txt
#from scripts.download_gait_abnormalities_example import file_name
import os, sys, json
import requests
import utils
from concurrent.futures import ThreadPoolExecutor
from utils import MetadataExcelExporter
parentFolder = os.getcwd() 
api_path = os.path.abspath(os.path.join(parentFolder, '..', 'moveshelf-python-api', 'src'))
sys.path.insert(0, api_path)
# --------------------#
from moveshelf_api.api import MoveshelfApi, Metadata

# Use a requests.Session for connection pooling
requests_session = requests.Session()

def download_with_session(url):
    return download_json_file(url, session=requests_session)

def download_json_file(url, session=None):
    try:
        response = session.get(url) if session else requests.get(url)
        decoded_content = response.content.decode()
        return json.loads(decoded_content)
    except Exception as e:
        print(f"Failed to download or parse {url}: {e}")
        return None

def download_and_save_json(args):
    """Download JSON file and save to disk in one operation"""
    url, file_path = args
    try:
        # Download using existing function
        data = download_with_session(url)
        
        if data:
            # Create directory structure
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save JSON with formatting
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, file_path
        return False, None
    except Exception as e:
        print(f"Failed to save {url}: {e}")
        return False, None

def sanitize_filename(path):
    """Remove invalid characters for Windows filenames"""
    invalid_chars = '<>:"|?*'
    sanitized = path
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '')
    return sanitized

## Setup the API
# Load config
with open(os.path.join(parentFolder,'mvshlf-config.spec.json'), 'r') as configFile:
    data = json.load(configFile)

# And overwrite if available
personalConfig = os.path.join(parentFolder,'mvshlf-config.json')
if os.path.isfile(personalConfig):
    with open(personalConfig, 'r') as configFile:
        data.update(json.load(configFile))

api = MoveshelfApi(api_key_file = os.path.join(parentFolder,data['apiKeyFileName']), api_url = data['apiUrl'])


## ============================================================================
## RETRIEVE A FILTERED SUBSET OF SESSIONS - Edit these before running
## ============================================================================
## Your URL from the filtered sessions overview page
url = "https://internal.moveshelf.com/project/UHJvamVjdOBrHC7VPkpFmN_aOh7YMFw/sessions?startDate=2017-01-01&endDate=2021-09-01&subject-diagnosis=Cerebral%20Palsy&subject-diagnosis=Idiopathic%20Toe%20Walking&sessioninfo-data-collected=Surface%20EMG" ## Include you URL
# Extract project_id from URL (comes after /project/)
project_id = url.split('/project/')[1].split('/')[0]

print("\nRetrieving sessions...")
print("=" * 80)

## Retrieve filtered session
sessions = api.getFilteredProjectSessions(
    project_id=project_id,
    session_overview_url=url,
)

print(f"\nFound {len(sessions)} sessions")

## Print information of each filtered session 
for i, session in enumerate(sessions, 1):
    print(f"Session {i}:")
    print(f"  ID: {session['id']}")
    print(f"  Date: {session.get('date', 'N/A')}")
    print(f"  Path: {session.get('projectPath', 'N/A')}")
    
    # Patient metadata summary
    if session.get('patient'):
        patient = session['patient']
        patient_name = patient.get('name', 'N/A')
        
        # Count filled patient metadata fields
        patient_meta = {}
        if 'metadata' in patient:
            try:
                patient_meta = json.loads(patient['metadata']) if isinstance(patient['metadata'], str) else patient['metadata']
            except:
                pass
        
        filled_fields = sum(1 for v in patient_meta.values() if v not in [None, '', [], {}])
        total_fields = len(patient_meta)
        
        print(f"\n  Patient: {patient_name}")
        print(f"    Patient metadata has {filled_fields}/{total_fields} parameters filled")
    
    # Session metadata summary
    if session.get('metadata'):
        try:
            metadata_obj = json.loads(session['metadata'])
            session_meta = metadata_obj.get('metadata', {})
            
            filled_fields = sum(1 for v in session_meta.values() if v not in [None, '', [], {}])
            total_fields = len(session_meta)
            
            print(f"\n  Session metadata ('metadata') has {filled_fields}/{total_fields} parameters filled")
        except Exception as e:
            print(f"\n  Session metadata: (Could not parse: {e})")



## ============================================================================
## CONFIGURATION VARIABLES - Edit these before running
## ============================================================================
OUTPUT_FILENAME = "Metadata_Export_AFO_study.xlsx"

# Specify which fields to export (leave empty for all)
SUBJECT_METADATA_FIELDS: list[str] = ['ehr-id', 'subject-diagnosis']
SESSION_METADATA_FIELDS: list[str] = ['interview-gmfcs', 'interview-orthotics', 'vicon-dmc-barefoot', 'vicon-dmc-braced']#  'sessioninfo-conditions-collected', 'sessioninfo-data-collected'

# Column header format configuration
# When True: Use metadata field IDs as column headers
# (e.g., 'sessioninfo-comments', 'vicon-leg-length-right')
# When False: Use descriptive labels with tab context
# (e.g., 'Session info: Comments', 'Physical exam 1: Leg length (mm) - right')
USE_METADATA_ID_AS_COLUMN_HEADER: bool = False

# Create exporter instance
exporter = MetadataExcelExporter(
    api,
    use_metadata_id_as_column_header=USE_METADATA_ID_AS_COLUMN_HEADER
)

# Export metadata. Uncomment one of the following options (Option 1 or Option 2)
# # Option 1: Export metadata for a list of subjects
# subjects_list = subjects # e.g., the output from Retrieving a subset of subjects
## Note: It is also possible to export metadata from a single subject by assigning 
## subjects_list = [subject_details] # where subject_details results from the Retrieve a subject example 

# exporter.export_metadata_to_excel(
#     project_id=my_project_id,
#     output_filename=OUTPUT_FILENAME,
#     subjects_list=subjects_list,
#     subject_fields=SUBJECT_METADATA_FIELDS,
#     session_fields=SESSION_METADATA_FIELDS
# )

# Option 2: Export metadata for a list of sessions
# Sessions will be automatically grouped by patient in export_metadata_to_excel
sessions_list = sessions # e.g., the output from Retrieving a subset of sessions
# Note: It is also possible to export metadata from a single session by assigning 
# sessions_list = [session] # where session results from the Retrieve a session example 

exporter.export_metadata_to_excel(
    project_id=project_id,
    output_filename=OUTPUT_FILENAME,
    sessions_list=sessions_list,
    subject_fields=SUBJECT_METADATA_FIELDS,
    session_fields=SESSION_METADATA_FIELDS
)


