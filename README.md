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
* Download the API key file and save `mvshlf-api-key.json` in the root folder of your Sportsmedicine Git folder.

**The API key should be kept secret.**

### Running the script

Open `download_data_example.py` in your Python editor, follow the instructions, and run the script.