import requests
import json
import time
import argparse
import sys
import os
import logging
from datetime import datetime

# --- Setup Logging ---
def setup_logger():
    """Set up and configure the logger"""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Create log file with timestamp
    log_file = f"project_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(log_formatter)
    
    # Also output to console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    
    # Set up the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger

logger = setup_logger()

# --- CONFIG ---
# Use environment variables for sensitive configuration
TARGET_ORG = os.environ.get("GITHUB_TARGET_ORG", "")  # Target organization name
TARGET_API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com")  # GitHub API URL
TARGET_GRAPHQL_URL = os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql")  # GitHub GraphQL API
TOKEN = os.environ.get("GITHUB_TOKEN", "")  # GitHub token

# Try loading config from file if exists
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            TARGET_ORG = config.get('target_org', TARGET_ORG)
            TARGET_API_URL = config.get('api_url', TARGET_API_URL)
            TARGET_GRAPHQL_URL = config.get('graphql_url', TARGET_GRAPHQL_URL)
            # Don't load token from file for security reasons
    except Exception as e:
        logger.warning(f"Failed to load config file: {str(e)}")

# --- Initialize headers ---
HEADERS = {}  # Will be set based on project type

def update_headers(token, project_type="classic"):
    """Update request headers based on token and project type"""
    global HEADERS
    if project_type.lower() == "classic":
        HEADERS = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    else:  # v2
        HEADERS = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v4+json"
        }

def make_api_request(url, method="GET", data=None, headers=None, max_retries=3):
    """Make REST API request with retries"""
    if headers is None:
        headers = HEADERS
        
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            logger.debug(f"Making {method} request to {url}")
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                resp = requests.post(url, headers=headers, json=data)
            elif method.upper() == "PATCH":
                resp = requests.patch(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle rate limiting
            if resp.status_code == 403 and 'X-RateLimit-Remaining' in resp.headers and int(resp.headers['X-RateLimit-Remaining']) == 0:
                reset_time = int(resp.headers.get('X-RateLimit-Reset', 0))
                current_time = int(time.time())
                sleep_time = max(reset_time - current_time + 1, 1)
                logger.warning(f"Rate limit exceeded. Waiting for {sleep_time} seconds...")
                time.sleep(sleep_time)
                continue
                
            # Success case
            if resp.status_code in [200, 201, 202]:
                logger.debug(f"Request successful: {resp.status_code}")
                return resp
            
            # Handle other errors
            if attempt < max_retries - 1:
                logger.warning(f"Request failed with status {resp.status_code}. Retrying in {retry_delay} seconds...")
                logger.debug(f"Error details: {resp.text}")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Request failed after {max_retries} attempts. Status: {resp.status_code}")
                resp.raise_for_status()
                
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"Request error: {str(e)}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"Request failed after {max_retries} attempts: {str(e)}")
                raise
    
    raise Exception("Maximum retries exceeded")

def run_graphql_query(query, variables=None):
    """Execute a GraphQL query against the Enterprise GitHub API"""
    request_data = {"query": query}
    if variables:
        request_data["variables"] = variables
    
    for attempt in range(3):
        try:
            response = requests.post(
                TARGET_GRAPHQL_URL,
                headers=HEADERS,
                json=request_data
            )
            
            if response.status_code == 200:
                result = response.json()
                if "errors" in result:
                    logger.error(f"GraphQL Error: {json.dumps(result['errors'], indent=2)}")
                    if attempt < 2:
                        logger.info(f"Retrying in {2**attempt} seconds...")
                        time.sleep(2**attempt)
                        continue
                    raise Exception(f"GraphQL query failed: {result['errors'][0].get('message', 'Unknown error')}")
                return result
            
            # Handle errors
            if attempt < 2:
                logger.warning(f"Request failed with status {response.status_code}. Retrying in {2**attempt} seconds...")
                logger.debug(f"Response: {response.text}")
                time.sleep(2**attempt)
            else:
                response.raise_for_status()
                
        except requests.RequestException as e:
            if attempt < 2:
                logger.warning(f"Request error: {str(e)}. Retrying in {2**attempt} seconds...")
                time.sleep(2**attempt)
            else:
                raise
    
    raise Exception("Maximum retries exceeded")

def import_classic_projects(data, org):
    """Import classic projects to GitHub Enterprise"""
    imported_projects = []
    
    for project in data:
        logger.info(f"Creating project: {project['name']}")
        
        # Create project
        project_url = f"{TARGET_API_URL}/orgs/{org}/projects"
        project_data = {
            "name": project["name"],
            "body": project.get("body", ""),
            "organization_permission": "write"  # Adjust as needed
        }
        
        resp = make_api_request(project_url, method="POST", data=project_data)
        new_project = resp.json()
        logger.info(f"  Created project ID: {new_project['id']}")
        
        # Create columns
        for column in project.get("columns", []):
            column_url = f"{TARGET_API_URL}/projects/{new_project['id']}/columns"
            column_data = {
                "name": column["name"]
            }
            
            resp = make_api_request(column_url, method="POST", data=column_data)
            new_column = resp.json()
            logger.info(f"    Created column: {new_column['name']} (ID: {new_column['id']})")
            
            # Create cards
            for card in column.get("cards", []):
                card_url = f"{TARGET_API_URL}/projects/columns/{new_column['id']}/cards"
                card_data = {}
                
                if card.get("note"):
                    card_data["note"] = card["note"]
                elif card.get("content_url"):
                    # If this is an issue/PR link, we'd need to map it to the new repository
                    # This is complex and depends on how repos were migrated
                    logger.warning(f"      Skipping card with content_url: {card['content_url']} - manual linking required")
                    continue
                
                try:
                    resp = make_api_request(card_url, method="POST", data=card_data)
                    new_card = resp.json()
                    logger.info(f"      Created card ID: {new_card['id']}")
                except Exception as e:
                    logger.error(f"      Failed to create card: {str(e)}")
        
        imported_projects.append({
            "original_name": project["name"],
            "new_id": new_project["id"],
            "new_url": new_project["html_url"]
        })
    
    return imported_projects

def import_projects_v2(data, org):
    """Import Projects V2 to GitHub Enterprise"""
    imported_projects = []
    
    # Create Projects V2 using GraphQL API
    for project in data:
        logger.info(f"Creating Project V2: {project['title']}")
        logger.debug(f"Project details: {json.dumps({k: v for k, v in project.items() if k != 'items'}, indent=2)}")
        
        # Create project
        query = """
        mutation($input: CreateProjectV2Input!) {
          createProjectV2(input: $input) {
            projectV2 {
              id
              number
              url
            }
          }
        }
        """
        
        variables = {
            "input": {
                "ownerId": get_organization_node_id(org),
                "title": project["title"]
                # repositoryId is not needed for org projects
            }
        }
        
        # Remove the description field as it's not supported in the CreateProjectV2Input
        # We'll update the description separately after creation if needed
        
        try:
            result = run_graphql_query(query, variables)
            new_project = result.get("data", {}).get("createProjectV2", {}).get("projectV2", {})
            logger.info(f"  Created Project V2 ID: {new_project['id']} (#{new_project['number']})")
            
            # If we need to set a description, we can do it with a separate mutation
            if project.get("shortDescription"):
                try:
                    # Use updateProjectV2 mutation to set the readme content
                    update_query = """
                    mutation($projectId: ID!, $readme: String!) {
                      updateProjectV2(input: {projectId: $projectId, readme: $readme}) {
                        projectV2 { id }
                      }
                    }
                    """
                    update_variables = {
                        "projectId": new_project['id'],
                        "readme": project["shortDescription"]
                    }
                    run_graphql_query(update_query, update_variables)
                    logger.info(f"  Updated project readme/description")
                except Exception as e:
                    logger.warning(f"  Failed to update project description: {str(e)}")
            
            # Create fields
            field_mapping = {}
            for field in project.get("fields", {}).get("nodes", []):
                if field.get("name") and field.get("id"):
                    # Create custom fields as needed
                    # This would need to be expanded based on field types
                    pass
            
            # Create items
            for item in project.get("items", []):
                # This would need significant work to recreate all item types and field values
                if item.get("content"):
                    content = item["content"]
                    if "title" in content:
                        logger.info(f"    Would create item: {content['title']} (manual recreation needed)")
            
            imported_projects.append({
                "original_title": project["title"],
                "new_id": new_project["id"],
                "new_url": new_project["url"]
            })
            
        except Exception as e:
            logger.error(f"  Failed to create Project V2: {str(e)}")
    
    return imported_projects

def get_organization_node_id(org):
    """Get the GraphQL node ID for an organization"""
    query = """
    query($login: String!) {
      organization(login: $login) {
        id
      }
    }
    """
    
    variables = {
        "login": org
    }
    
    result = run_graphql_query(query, variables)
    return result.get("data", {}).get("organization", {}).get("id")

def import_projects_from_json(filename, org, project_type="classic"):
    """Import projects from JSON file to GitHub Enterprise"""
    try:
        logger.info(f"Reading project data from {filename}...")
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not data:
            logger.warning("No project data found in the file.")
            return False
        
        if project_type.lower() == "classic":
            imported = import_classic_projects(data, org)
        elif project_type.lower() == "v2":
            imported = import_projects_v2(data, org)
        else:
            raise ValueError(f"Unknown project_type: {project_type}. Must be 'classic' or 'v2'")
        
        # Save mapping information
        mapping_file = f"project_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(imported, f, indent=2)
        
        logger.info(f"Import completed. Project mapping saved to {mapping_file}")
        return True
    
    except Exception as e:
        logger.error(f"Error during import: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import GitHub projects to Enterprise instance")
    parser.add_argument("--input", required=True, help="Input JSON filename with project data")
    parser.add_argument("--org", help="Target GitHub Enterprise organization name")
    parser.add_argument("--token", help="GitHub Enterprise personal access token")
    parser.add_argument("--api-url", help="GitHub Enterprise REST API URL (defaults to GitHub.com API)")
    parser.add_argument("--graphql-url", help="GitHub Enterprise GraphQL API URL (defaults to GitHub.com GraphQL API)")
    parser.add_argument("--type", choices=["classic", "v2"], default="v2", 
                        help="Project type to import (classic or v2)")
    
    args = parser.parse_args()
    
    # Command-line args take precedence over environment variables
    TOKEN = args.token or TOKEN
    TARGET_ORG = args.org or TARGET_ORG
    TARGET_API_URL = args.api_url or TARGET_API_URL
    TARGET_GRAPHQL_URL = args.graphql_url or TARGET_GRAPHQL_URL
    
    if not TOKEN:
        logger.error("GitHub token is required. Set GITHUB_TOKEN environment variable or pass via --token")
        sys.exit(1)
        
    if not TARGET_ORG:
        logger.error("Target organization is required. Set GITHUB_TARGET_ORG environment variable or pass via --org")
        sys.exit(1)
    
    update_headers(TOKEN, args.type)
    
    logger.info(f"Starting project import process")
    logger.info(f"Target organization: {TARGET_ORG}")
    logger.info(f"API URLs: REST={TARGET_API_URL}, GraphQL={TARGET_GRAPHQL_URL}")
    logger.info(f"Project type: {args.type}")
    
    success = import_projects_from_json(args.input, TARGET_ORG, args.type)
    
    if success:
        logger.info("Import process completed successfully")
    else:
        logger.error("Import process failed")
    
    sys.exit(0 if success else 1)
