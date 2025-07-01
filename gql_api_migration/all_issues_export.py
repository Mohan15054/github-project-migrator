import requests
import csv
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()  # Load variables from .env

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ORG = os.getenv("ORG")
REPO = os.getenv("REPO")
IS_ORG = os.getenv("IS_ORG", "False").lower() == "true"
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "all_issues.csv")

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

def fetch_all_issues(owner, repo):
    query = '''
    query($owner: String!, $repo: String!, $after: String) {
      repository(owner: $owner, name: $repo) {
        issues(first: 100, after: $after) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            id
            number
            title
            url
            state
          }
        }
      }
    }
    '''
    after = None
    all_issues = []
    while True:
        variables = {"owner": owner, "repo": repo, "after": after}
        result = run_graphql(query, variables)
        issues_data = result["data"]["repository"]["issues"]
        all_issues.extend(issues_data["nodes"])  # <-- flatten here
        if not issues_data["pageInfo"]["hasNextPage"]:
            break
        after = issues_data["pageInfo"]["endCursor"]
    print(f"✅ Total issues in '{repo}': {len(all_issues)}")
    return all_issues

def export_all_issues_to_csv():
    issues = fetch_all_issues(ORG, REPO)
    with open(OUTPUT_FILE, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id","issue_number", "issue_title", "issue_url", "issue_state"])
        for issue in issues:
            writer.writerow([
                issue["id"],  # Include ID for better tracking
                issue["number"],
                issue["title"].replace(",", " "),  # Avoid CSV breaking
                issue["url"],
                issue["state"]
            ])
    print(f"\n✅ Exported all issues to: {OUTPUT_FILE}")

# --- Run Script ---
if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("❌ Please set your GitHub token in the GITHUB_TOKEN environment variable.")
    else:
        export_all_issues_to_csv()
