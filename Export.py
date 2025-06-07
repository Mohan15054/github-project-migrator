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
    log_file = f"project_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
SOURCE_ORG = os.environ.get("GITHUB_SOURCE_ORG", "")  # Source organization name
API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com")  # GitHub API URL
GRAPHQL_URL = os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql")  # GitHub GraphQL API
TOKEN = os.environ.get("GITHUB_TOKEN", "")  # GitHub token

# Try loading config from file if exists
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            SOURCE_ORG = config.get('source_org', SOURCE_ORG)
            API_URL = config.get('api_url', API_URL)
            GRAPHQL_URL = config.get('graphql_url', GRAPHQL_URL)
            # Don't load token from file for security reasons
    except Exception as e:
        logger.warning(f"Failed to load config file: {str(e)}")

# If no token in environment or config, try to read from a secure token file
if not TOKEN:
    try:
        token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.github_token')
        with open(token_file, "r") as f:
            TOKEN = f.read().strip()
    except FileNotFoundError:
        pass  # Will check token later

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

# --- FUNCTIONS ---

def make_api_request(url, headers=HEADERS, max_retries=3, retry_delay=2):
    """Make API request with rate limit handling and retries"""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers)
            
            # Handle rate limiting
            if resp.status_code == 403 and 'X-RateLimit-Remaining' in resp.headers and int(resp.headers['X-RateLimit-Remaining']) == 0:
                reset_time = int(resp.headers.get('X-RateLimit-Reset', 0))
                current_time = int(time.time())
                sleep_time = max(reset_time - current_time + 1, 1)
                logger.warning(f"Rate limit exceeded. Waiting for {sleep_time} seconds...")
                time.sleep(sleep_time)
                continue
                
            # Success case
            if resp.status_code == 200:
                return resp
            
            # Handle other errors
            if attempt < max_retries - 1:
                logger.warning(f"Request failed with status {resp.status_code}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                resp.raise_for_status()
                
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"Request error: {str(e)}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                raise
    
    raise Exception("Maximum retries exceeded")

def get_projects(org):
    projects = []
    url = f"https://api.github.com/orgs/{org}/projects"
    while url:
        resp = make_api_request(url)
        projects.extend(resp.json())
        url = resp.links.get("next", {}).get("url")
    return projects

def get_columns(project_id):
    columns = []
    url = f"https://api.github.com/projects/{project_id}/columns"
    while url:
        resp = make_api_request(url)
        columns.extend(resp.json())
        url = resp.links.get("next", {}).get("url")
    return columns

def get_cards(column_id):
    cards = []
    url = f"https://api.github.com/projects/columns/{column_id}/cards"
    while url:
        resp = make_api_request(url)
        cards.extend(resp.json())
        url = resp.links.get("next", {}).get("url")
    return cards

def export_projects_to_json(org, filename, project_type="classic"):
    """Export GitHub projects to a JSON file.
    
    Args:
        org: GitHub organization name
        filename: Output JSON filename
        project_type: Type of projects to export ("classic" or "v2")
    """
    data = []
    try:
        if project_type.lower() == "classic":
            logger.info(f"Fetching classic projects for org '{org}' ...")
            projects = get_projects(org)
            logger.info(f"Found {len(projects)} classic projects.")

            for i, project in enumerate(projects):
                logger.info(f"Processing project {i+1}/{len(projects)}: {project['name']} (ID: {project['id']})")
                proj_data = {
                    "name": project["name"],
                    "body": project.get("body", ""),
                    "state": project.get("state", "open"),
                    "columns": []
                }

                columns = get_columns(project["id"])
                logger.info(f"  Found {len(columns)} columns.")

                for col in columns:
                    col_data = {
                        "name": col["name"],
                        "cards": []
                    }
                    cards = get_cards(col["id"])
                    logger.info(f"    Found {len(cards)} cards.")
                    for card in cards:
                        card_data = {
                            "note": card.get("note"),
                            "content_url": card.get("content_url"),
                            "content_id": card.get("content_id"),
                            "content_type": card.get("content_type")
                        }
                        col_data["cards"].append(card_data)
                    proj_data["columns"].append(col_data)

                data.append(proj_data)
        
        elif project_type.lower() == "v2":
            logger.info(f"Fetching Projects V2 for org '{org}' ...")
            data = get_projects_v2(org)
        
        else:
            raise ValueError(f"Unknown project_type: {project_type}. Must be 'classic' or 'v2'")

        logger.info(f"Saving data to {filename} ...")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info("Export completed successfully.")
        return True
    except Exception as e:
        logger.error(f"Error during export: {str(e)}")
        return False

def get_projects_v2(org):
    """Get Projects V2 using the GraphQL API"""
    query = """
    query($org: String!, $cursor: String) {
      organization(login: $org) {
        projectsV2(first: 20, after: $cursor) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            id
            title
            shortDescription
            number
            url
            closed
            fields(first: 50) {
              nodes {
                ... on ProjectV2Field {
                  id
                  name
                }
                ... on ProjectV2SingleSelectField {
                  id
                  name
                  options {
                    id
                    name
                    color
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    projects_data = []
    has_next_page = True
    cursor = None
    
    logger.info("Fetching Projects V2 data via GraphQL API...")
    
    while has_next_page:
        variables = {
            "org": org,
            "cursor": cursor
        }
        response = run_graphql_query(query, variables)
        data = response.get("data", {}).get("organization", {}).get("projectsV2", {})
        
        projects = data.get("nodes", [])
        for project in projects:
            # Get items for each project
            project_items = get_project_v2_items(project["id"])
            project_with_items = project.copy()
            project_with_items["items"] = project_items
            projects_data.append(project_with_items)
            
        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")
        
    return projects_data

def get_project_v2_items(project_id):
    """Get items for a specific Project V2"""
    query = """
    query($projectId: ID!, $cursor: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              id
              type
              fieldValues(first: 50) {
                nodes {
                  ... on ProjectV2ItemFieldTextValue {
                    text
                    field {
                      ... on ProjectV2FieldCommon {
                        name
                      }
                    }
                  }
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    name
                    field {
                      ... on ProjectV2FieldCommon {
                        name
                      }
                    }
                  }
                }
              }
              content {
                ... on DraftIssue {
                  title
                  body
                }
                ... on Issue {
                  title
                  body
                  repository {
                    name
                  }
                  number
                }
                ... on PullRequest {
                  title
                  body
                  repository {
                    name
                  }
                  number
                }
              }
            }
          }
        }
      }
    }
    """
    items = []
    has_next_page = True
    cursor = None
    
    while has_next_page:
        variables = {
            "projectId": project_id,
            "cursor": cursor
        }
        response = run_graphql_query(query, variables)
        data = response.get("data", {}).get("node", {}).get("items", {})
        
        items.extend(data.get("nodes", []))
        
        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")
        
    return items

def run_graphql_query(query, variables=None):
    """Execute a GraphQL query against the GitHub API"""
    request_data = {"query": query}
    if variables:
        request_data["variables"] = variables
    
    for attempt in range(3):
        try:
            response = requests.post(
                GRAPHQL_URL,  # Use the configured GraphQL URL
                headers=HEADERS,
                json=request_data
            )
            
            if response.status_code == 200:
                result = response.json()
                if "errors" in result:
                    logger.error(f"GraphQL Error: {json.dumps(result['errors'], indent=2)}")
                    if attempt < 2:
                        logger.warning(f"Retrying in {2**attempt} seconds...")
                        time.sleep(2**attempt)
                        continue
                    raise Exception(f"GraphQL query failed: {result['errors'][0].get('message', 'Unknown error')}")
                return result
            
            # Handle rate limits and other errors
            if attempt < 2:
                logger.warning(f"Request failed with status {response.status_code}. Retrying in {2**attempt} seconds...")
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export GitHub projects to JSON")
    parser.add_argument("--org", help="GitHub organization name")
    parser.add_argument("--output", help="Output JSON filename")
    parser.add_argument("--token", help="GitHub personal access token")
    parser.add_argument("--api-url", help="GitHub REST API URL (defaults to api.github.com)")
    parser.add_argument("--graphql-url", help="GitHub GraphQL API URL")
    parser.add_argument("--type", choices=["classic", "v2"], default="v2", 
                        help="Project type to export (classic or v2)")
    
    args = parser.parse_args()
    
    # Command-line args take precedence over environment variables and config
    TOKEN = args.token or TOKEN
    SOURCE_ORG = args.org or SOURCE_ORG
    API_URL = args.api_url or API_URL
    GRAPHQL_URL = args.graphql_url or GRAPHQL_URL
    
    # Default output filename if not specified
    output_file = args.output or f"projects_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    if not TOKEN:
        logger.error("GitHub token is required. Set GITHUB_TOKEN environment variable or pass via --token")
        sys.exit(1)
        
    if not SOURCE_ORG:
        logger.error("Source organization is required. Set GITHUB_SOURCE_ORG environment variable or pass via --org")
        sys.exit(1)
    
    update_headers(TOKEN, args.type)
    
    logger.info(f"Starting project export process")
    logger.info(f"Source organization: {SOURCE_ORG}")
    logger.info(f"API URLs: REST={API_URL}, GraphQL={GRAPHQL_URL}")
    logger.info(f"Project type: {args.type}")
    logger.info(f"Output file: {output_file}")
    
    success = export_projects_to_json(SOURCE_ORG, output_file, args.type)
    sys.exit(0 if success else 1)
