# GitHub Project Migration Tool

## Problem Statement

Organizations often need to migrate GitHub Projects between organizations or GitHub instances (e.g., from public GitHub to GitHub Enterprise) while preserving project structure, columns, cards, and other metadata. GitHub does not provide a native way to export and import projects between organizations, especially for the newer Projects V2.

Specific challenges include:
- No built-in migration path for GitHub Projects between organizations
- Manual recreation is time-consuming and error-prone
- Projects V2 have a complex structure with custom fields that are difficult to recreate manually
- Need to maintain project history and relationships
- Ensuring secure handling of GitHub tokens and sensitive information

## Solution

This tool provides a two-step process to export GitHub projects from a source organization and import them into a target organization. It supports both classic projects and the newer Projects V2, handling their different structures through appropriate API calls (REST API for classic projects, GraphQL for Projects V2).

### Key Components

1. **Export.py**: Extracts project data from a source GitHub organization
   - Uses GitHub REST API for classic projects
   - Uses GitHub GraphQL API for Projects V2
   - Saves project data to a JSON file

2. **Import.py**: Creates projects in a target GitHub organization
   - Uses GitHub REST API for classic projects
   - Uses GitHub GraphQL API for Projects V2
   - Reads project data from a JSON file
   - Creates appropriate project structure in the target organization

3. **Configuration Management**:
   - Secure handling of GitHub tokens
   - Flexible configuration via environment variables, config file, or command-line arguments
   - No hardcoded sensitive information

## Features

- **Support for Multiple Project Types**:
  - Classic GitHub Projects (columns and cards)
  - GitHub Projects V2 (issues, fields, views)

- **Comprehensive Data Migration**:
  - Project structure (columns, fields)
  - Cards and items
  - Metadata (descriptions, states)

- **Security**:
  - Token-based authentication
  - No hardcoded credentials
  - Multiple secure ways to provide authentication

- **Robust Error Handling**:
  - Rate limiting management
  - Request retries with exponential backoff
  - Comprehensive logging

- **Flexibility**:
  - Configurable via environment variables, config file, or command-line
  - Support for both GitHub.com and GitHub Enterprise instances

## Setup and Configuration

### Requirements

- Python 3.6+
- `requests` library

### Installation

1. Clone or download this repository
2. Install required dependencies:
   ```
   pip install requests
   ```

### Configuration Options

Configure the tool in one of these ways (in order of precedence):

1. **Command-line Arguments**:
   - Highest priority
   - See usage examples below

2. **Environment Variables**:
   - `GITHUB_TOKEN` - GitHub personal access token
   - `GITHUB_SOURCE_ORG` - Source organization name
   - `GITHUB_TARGET_ORG` - Target organization name
   - `GITHUB_API_URL` - GitHub API URL (defaults to https://api.github.com)
   - `GITHUB_GRAPHQL_URL` - GitHub GraphQL API URL

3. **Config File** (`config.json`):
   - Place in the same directory as the scripts
   - Sample format provided in `config.json.sample`

4. **Token File**:
   - Create a `.github_token` file with just your token

## Usage

### Export Projects

Export projects from a source organization:

```bash
# Basic usage
python Export.py --org "Source-Organization" --output projects_data.json --token YOUR_GITHUB_TOKEN --type v2

# With environment variables
export GITHUB_TOKEN=your-github-token
export GITHUB_SOURCE_ORG=Source-Organization
python Export.py --type v2 --output projects_data.json
```

### Import Projects

Import projects to a target organization:

```bash
# Basic usage
python Import.py --input projects_data.json --org "Target-Organization" --token YOUR_GITHUB_TOKEN --type v2

# With environment variables
export GITHUB_TOKEN=your-github-token
export GITHUB_TARGET_ORG=Target-Organization
python Import.py --input projects_data.json --type v2
```

### GitHub Enterprise Example

For GitHub Enterprise, specify API URLs:

```bash
python Export.py --org "Source-Organization" --output projects_data.json --token YOUR_GITHUB_TOKEN \
  --api-url "https://github.enterprise.com/api/v3" \
  --graphql-url "https://github.enterprise.com/api/graphql" \
  --type v2
```

## Complete Workflow Example

This example shows migrating projects from "org1" to "org2":

```bash
# Set environment variables
export GITHUB_TOKEN=your-github-token
export GITHUB_SOURCE_ORG=org1
export GITHUB_TARGET_ORG=org2

# Step 1: Export projects
python Export.py --output neo_development_project.json --type v2

# Step 2: Import projects
python Import.py --input neo_development_project.json --type v2
```

## Logging and Monitoring

The scripts provide detailed logging to both console and log files:
- `project_export_[timestamp].log`: Export process logs
- `project_import_[timestamp].log`: Import process logs
- `project_mapping_[timestamp].json`: Mapping between original and imported projects

## Limitations

- Linked issues/PRs may need manual reattachment if repositories were also migrated
- Custom field configurations in Projects V2 may require additional manual setup
- Some advanced project features might not transfer completely

## Contributing

Contributions to improve the tool are welcome. Please feel free to submit issues and pull requests.