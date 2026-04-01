# Moveshelf Data Examples - Utils Module

This module provides utility classes and functions for working with Moveshelf data.

## MetadataExcelExporter

The `MetadataExcelExporter` class provides a clean, reusable way to export subject and session metadata from the Moveshelf platform to formatted Excel files.

### Features

- Export subject and session metadata to Excel
- Automatic column name generation (descriptive or ID-based)
- Support for context fields (left/right)
- Professional Excel formatting:
  - Colored header row
  - Auto-sized columns
  - Frozen header row
  - Centered headers
- Flexible input (accepts either subjects list or sessions list)
- Automatic data fetching from API when needed

### Installation

Ensure you have the required dependencies installed:

```bash
pip install -r requirements.txt
```

### Quick Start

```python
from moveshelf_api.api import MoveshelfApi
from utils import MetadataExcelExporter

# Initialize the API
api = MoveshelfApi(
    api_key_file="path/to/api_key.json",
    api_url="https://api.moveshelf.com"
)

# Create exporter instance
exporter = MetadataExcelExporter(api, use_metadata_id_as_column_header=True)

# Fetch subjects
subjects = api.getFilteredProjectSubjects(project_id)

# Export to Excel
exporter.export_metadata_to_excel(
    project_id="your-project-id",
    output_filename="metadata_export.xlsx",
    subjects_list=subjects
)
```

### Usage Examples

#### Example 1: Export All Fields

```python
# Export all available metadata fields
exporter.export_metadata_to_excel(
    project_id="my-project",
    output_filename="all_metadata.xlsx",
    subjects_list=subjects
)
```

#### Example 2: Export Specific Fields

```python
# Export only specific fields
exporter.export_metadata_to_excel(
    project_id="my-project",
    output_filename="selected_metadata.xlsx",
    subjects_list=subjects,
    subject_fields=['ehr-id', 'subject-diagnosis'],
    session_fields=['vicon-height', 'vicon-weight']
)
```

#### Example 3: Use Descriptive Column Headers

```python
# Use descriptive column names instead of field IDs
exporter.export_metadata_to_excel(
    project_id="my-project",
    output_filename="descriptive_headers.xlsx",
    subjects_list=subjects,
    use_metadata_id_as_column_header=False
)
```

#### Example 4: Export from Sessions List

```python
# If you have a flat list of sessions, they'll be automatically grouped
sessions = api.getFilteredProjectSessions(project_id)

exporter.export_metadata_to_excel(
    project_id="my-project",
    output_filename="from_sessions.xlsx",
    sessions_list=sessions
)
```

### API Reference

#### MetadataExcelExporter.__init__(api)

Initialize the exporter with a MoveshelfApi instance.

**Parameters:**
- `api` (MoveshelfApi): Initialized API instance

#### MetadataExcelExporter.export_metadata_to_excel(...)

Export metadata to a formatted Excel file.

**Parameters:**
- `project_id` (str): ID of the Moveshelf project
- `output_filename` (str): Name of the output Excel file (default: "Metadata_Export.xlsx")
- `subjects_list` (list[dict] | None): List of subject dictionaries with 'sessions' key
- `sessions_list` (list[dict] | None): List of session dictionaries with 'patient' key
- `subject_fields` (list[str] | None): List of subject metadata field keys to export (None = all)
- `session_fields` (list[str] | None): List of session metadata field keys to export (None = all)
- `use_metadata_id_as_column_header` (bool): If True, use field IDs; if False, use descriptive labels (default: True)

**Raises:**
- `ValueError`: If both subjects_list and sessions_list are provided, or both are None

### Column Header Formats

The `use_metadata_id_as_column_header` parameter controls column naming:

**When True (default):**
- `vicon-height`
- `vicon-leg-length-right`
- `sessioninfo-comments`

**When False:**
- `Physical exam 1: Height (cm)`
- `Physical exam 1: Leg length (mm) - right`
- `Session info: Comments`

### Context Fields

Fields with left/right context (e.g., leg measurements) are automatically split into separate columns:

- With IDs: `vicon-leg-length-left`, `vicon-leg-length-right`
- With labels: `Physical exam 1: Leg length (mm) - left`, `Physical exam 1: Leg length (mm) - right`

