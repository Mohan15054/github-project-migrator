import csv
import requests
import os
from dotenv import load_dotenv

# === CONFIGURATION ===
load_dotenv()  # Load variables from .env

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")
PROJECT_ID = os.getenv("PROJECT_ID")  # ProjectV2 ID

# === HEADERS ===
headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# === GRAPHQL ENDPOINT ===
GITHUB_API_URL = "https://api.github.com/graphql"

# === STEP 1: Get Issue Node ID ===
def get_issue_node_id(issue_number):
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        issue(number: $number) {
          id
        }
      }
    }
    """
    variables = {
        "owner": REPO_OWNER,
        "name": REPO_NAME,
        "number": int(issue_number)
    }

    response = requests.post(GITHUB_API_URL, json={"query": query, "variables": variables}, headers=headers)
    data = response.json()
    return data["data"]["repository"]["issue"]["id"]

# === STEP 2: Add Issue to Project ===
def add_issue_to_project(issue_node_id):
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {
        projectId: $projectId,
        contentId: $contentId
      }) {
        item {
          id
        }
      }
    }
    """
    variables = {
        "projectId": PROJECT_ID,
        "contentId": issue_node_id
    }

    response = requests.post(GITHUB_API_URL, json={"query": mutation, "variables": variables}, headers=headers)
    return response.json()

# === STEP 3: Read CSV and Process ===
with open("all_issues.csv", newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        node_id = row["id"]
        try:
            # node_id = get_issue_node_id(issue_number)
            result = add_issue_to_project(node_id)
            print(f"Issue #{row['issue_number']} mapped: {result}")
        except Exception as e:
            print(f"Failed for issue #{row['issue_number']}: {e}")
