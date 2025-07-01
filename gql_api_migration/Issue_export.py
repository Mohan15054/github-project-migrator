import requests
import csv
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()  # Load variables from .env

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ORG = os.getenv("ORG")
IS_ORG = os.getenv("IS_ORG", "False").lower() == "true"
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "issues_with_projects.csv")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def run_graphql(query, variables=None):
    url = "https://api.github.com/graphql"
    json_data = {"query": query}
    if variables:
        json_data["variables"] = variables
    resp = requests.post(url, json=json_data, headers=HEADERS)
    if resp.status_code != 200:
        raise Exception(f"Query failed: {resp.text}")
    return resp.json()

def fetch_projects():
    print("Fetching projects...")
    query = '''
    query($login: String!) {
      %s(login: $login) {
        projectsV2(first: 50) {
          nodes {
            id
            number
            title
          }
        }
      }
    }
    ''' % ("organization" if IS_ORG else "user")
    result = run_graphql(query, {"login": ORG})
    return result["data"][("organization" if IS_ORG else "user")]["projectsV2"]["nodes"]

def fetch_repo_issues_in_project(owner, repo, target_project_number):
    query = '''
    query($owner: String!, $repo: String!, $after: String) {
      repository(owner: $owner, name: $repo) {
        issues(first: 100, after: $after) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            number
            title
            url
            state
            projectItems(first: 10) {
              nodes {
                project {
                  ... on ProjectV2 {
                    id
                    number
                    title
                  }
                }
              }
            }
          }
        }
      }
    }
    '''
    after = None
    filtered_issues = []

    while True:
        variables = {"owner": owner, "repo": repo, "after": after}
        result = run_graphql(query, variables)
        issues_data = result["data"]["repository"]["issues"]

        for issue in issues_data["nodes"]:
            project_items = issue["projectItems"]["nodes"]
            for item in project_items:
                project = item.get("project")
                if project and project.get("number") == target_project_number:
                    filtered_issues.append(issue)
                    break  # One match is enough

        if not issues_data["pageInfo"]["hasNextPage"]:
            break
        after = issues_data["pageInfo"]["endCursor"]

    print(f"✅ Total issues in '{repo}' for project #{target_project_number}: {len(filtered_issues)}")
    return filtered_issues

def export_issues_with_projects():
    projects = fetch_projects()
    with open(OUTPUT_FILE, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["project_number", "issue_number", "issue_title", "issue_url"])

        for project in projects:
            if project['number'] in (1):
                project_id = project["id"]
                project_number = project["number"]
                project_title = project["title"]
                print(f"Processing project {project_number}: {project['title']}")
                issues = fetch_repo_issues_in_project(ORG, "neo-web", project_number)

                for issue in sorted(issues, key=lambda x: x["number"]):
                    writer.writerow([
                        project_number,
                        project_title,
                        issue["number"],
                        issue["title"].replace(",", " "),  # Avoid CSV breaking
                        issue["url"],
                        issue["state"]
                    ])


    print(f"\n✅ Exported to: {OUTPUT_FILE}")

# --- Run Script ---
if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("❌ Please set your GitHub token in the GITHUB_TOKEN environment variable.")
    else:
        export_issues_with_projects()
