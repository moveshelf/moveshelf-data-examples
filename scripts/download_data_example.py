# install required packages: pip install -r ../requirements.txt
import os, sys, json
parentFolder = os.path.dirname(os.path.dirname(__file__))
sys.path.append(parentFolder)
from moveshelf_api.api import MoveshelfApi, Metadata
from moveshelf_api import util
import requests
import re

## Readme
# The datastructure of Moveshelf is organized as follows:
# * Project: Projects are the highest level and associated to a single organization in Moveshelf.
# * Subjects: Each project contains a list of subjects. At project level, access to the Electronic Health Record (EHR) of a subject can be made.
# * Sessions: A session contains the relevant information for a specific measurement session and is typically defined by the date of the measurement.
# * Conditions: Conditions specify a group of trials that were performed within a session.
# * Trials: Trials, aka clips, are containers used to store our data. It consists of metadata and 'Additional Data', where the actual data of a trial is stored.

## Instructions
# This script will, based on subject name find the subject on Moveshelf
# After that, the data in the session will be shown with the option to download the data and store locally (see downloadData boolean)

## Specify the details of your data to be uploaded and where it should go
myProject = '<orgName/projectName>'         # e.g. support/demoProject

##
mySubjectSessions = [
    {
        'subjectName': '<subjectName>',                # subject name, e.g. Subject1
        'sessionNames': ['2022-5-23', 'TBD']           # list of sessions
    },
    {
        'subjectName': '<nextSubjectName>',
        'sessionNames': ['...', '...']
    }
]

downloadData = True            # this will download data into the selected folder below
dataFolderSave = 'C:\\temp\\Moveshelf_download'   # data folder where data should be saved
fileExtensionsToDownload = ['.c3d', '.avi']   # Provide file extensions to download or leave empty if all is needed
stopProcessing = False

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

## Get available projects
projects = api.getUserProjects()
projectNames = [project['name'] for project in projects if len(projects) > 0]
print('Available projects:')
print(*projectNames, sep='\n')

## Select the project
try:
    iMyProject = projectNames.index(myProject)
    myProjectId = projects[iMyProject]['id']
    print('Project ID is: ' + myProjectId)

except:
    print('The project you are looking for is not found, searching for: ' + myProject)
    stopProcessing = True


## Find the subject
if not stopProcessing:
    subjects = api.getProjectSubjects(myProjectId)
    subjectNames = [s['name'] for s in subjects]
    for subjectSession in mySubjectSessions:
        mySubject = subjectSession['subjectName']
        mySessions = subjectSession['sessionNames']
        if mySubject not in subjectNames:
            print('The subject you are looking for is not found, searching for: ' + mySubject)
            continue
        
        mySubjectId = next(s['id'] for s in subjects if mySubject == s['name'])
        # Extract subject details
        subjectDetails = api.getSubjectDetails(mySubjectId)
        subjectName = subjectDetails['name']
        ehrId = 'not defined yet'
        if 'metadata' in subjectDetails.keys():
            metadata = json.loads(subjectDetails['metadata'])
            if 'ehr-id' in metadata.keys():
                ehrId = metadata['ehr-id']
        
        print('Subject name: ' + subjectName + ', EHR id: ' + ehrId)

        sessions = subjectDetails['sessions']
        if len(sessions) == 0:
            print('No sessions found')
        else:
            sessionNames = [s['projectPath'] for s in sessions]
        
            for sessionName in mySessions:
                sessionPathToFind = subjectName + '/' + sessionName
                if not any(sessionPathToFind in s for s in sessionNames):
                    print('Session ' + sessionName + ' not found, skipping and moving to next.')
                    continue

                print('Session ' + sessionName + ' found.')
                sessionId = next(s['id'] for s in sessions if sessionPathToFind in s['projectPath'])
                
                session = api.getSessionById(sessionId)

                sessionName = session['projectPath'].split('/')[2]
                
                conditions = []
                conditions = util.getConditionsFromSession(session, conditions)
                print('Session contains:')
                print('========================================================')
                for condition in conditions:
                    conditionName = condition['path'].replace('/','')
                    print('Condition: ' + conditionName)
                    ## Get clip id
                    trialCount = len(condition['clips'])
                    trialNames = [clip['title'] for clip in condition['clips'] if trialCount > 0]
                    for iClip in range(len(trialNames)):
                        trialName = trialNames[iClip]
                        print('Showing files for trial: ' + trialName)
                        clipId = condition['clips'][iClip]['id']

                        existingAdditionalData = api.getAdditionalData(clipId)
                        existingFileNames = [data['originalFileName'] for data in existingAdditionalData if len(existingAdditionalData) > 0]

                        print('Existing data for clip: ')
                        print(*existingFileNames, sep = "\n")

                        ## Download data
                        if downloadData:
                            for data in existingAdditionalData:
                                filename, file_extension = os.path.splitext(data['originalFileName'])
                                if not (len(fileExtensionsToDownload) == 0 or file_extension in fileExtensionsToDownload):
                                    continue

                                uploadStatus = data['uploadStatus']
                                if uploadStatus == 'Processing':
                                    print('File ' + data['originalFileName'] + ' is still being processed, skipping download')
                                elif uploadStatus == 'Complete':
                                    file_data = requests.get(data['originalDataDownloadUri']).content
                                    # create the file in write binary mode, because the data we get from net is in binary
                                    filenameDirSave = os.path.join(dataFolderSave, subjectName, sessionName, conditionName, trialName)
                                    filenameDirSave = re.sub(r'[*?"<>|]',"",filenameDirSave)        # remove "bad" characters from path
                                    if not os.path.isdir(filenameDirSave):
                                        os.makedirs(filenameDirSave)
                                    filenameSave = os.path.join(filenameDirSave, data['originalFileName'])
                                    with open(filenameSave, "wb") as file:
                                        file.write(file_data)


                                    print('Downloaded ' + data['originalFileName'] + ' into ' + filenameSave)
                                else:
                                    print('File ' + data['originalFileName'] + ' status is : ' + uploadStatus  + ', skipping download')

