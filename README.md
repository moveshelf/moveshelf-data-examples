# Basic example of using Moveshelf API to gather data from Moveshelf

The [Moveshelf](https://moveshelf.com) API uses [GraphQL](http://graphql.org)
for data access. This project demonstrates basic interaction with this API to
show and download data from the Moveshelf platform.

## Setup

### Dependencies
The example code is compatible with Python 3.7+. The dependencies can be installed with:

```sh
pip install -r requirements.txt
```

### API key
To access the Moveshelf API an access key should be created:
* Go to your profile page on Moveshelf (top-right corner):
* Follow instructions to generate an API key (enter ID for the new key, and click 'Generate API Key'
* Download the API key file and save `mvshlf-api-key.json` in the root folder of your Git folder.

**The API key should be kept secret.**

### Configure API environment
Open `mvshlf-config.json` and adjust "apiUrl" for:
* staging: "https://api.staging.moveshelf.com/graphql"
* production: "https://api.moveshelf.com/graphql"

### Running the script

Open the desired example script (eg: `download_data_example.py`) in your Python editor, follow the instructions, add all relevant information and run the script by running `python scripts/download_data_example.py` (or the example file you want to run).
