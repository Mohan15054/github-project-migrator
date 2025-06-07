# Set your configuration as environment variables (more secure)
# Don't include tokens in script files
export GITHUB_SOURCE_ORG="your-source-org"
export GITHUB_TARGET_ORG="your-target-org" 
export GITHUB_TOKEN="your-token"  # Better to input this directly when running

# Command to export projects from GitHub
# Export command to extract project data from source organization
python Export.py --org "$GITHUB_SOURCE_ORG" --output neo_development_project.json --type v2

# Command to import projects into GitHub
# Import command to create projects in target organization
python Import.py --input neo_development_project.json --org "$GITHUB_TARGET_ORG" --type v2
