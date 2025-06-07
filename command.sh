# Command to export projects from GitHub
# Export command to extract project data from source organization
python Export.py --org "source_org" --output project.json --token YOUR_GITHUB_TOKEN --type v2

# Command to import projects into GitHub
# Import command to create projects in target organization
python Import.py --input project.json --token YOUR_GITHUB_TOKEN --type v2
