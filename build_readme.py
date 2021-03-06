from python_graphql_client import GraphqlClient
import feedparser
import httpx
import json
import pathlib
import re
import os

# thanks to https://github.com/simonw/simonw
root = pathlib.Path(__file__).parent.resolve()
client = GraphqlClient(endpoint="https://api.github.com/graphql")


TOKEN = os.environ.get("DELITAMAKANDA_TOKEN", "")


def replace_chunk(content, marker, chunk, inline=False):
    r = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    if not inline:
        chunk = "\n{}\n".format(chunk)
    chunk = "<!-- {} starts -->{}<!-- {} ends -->".format(marker, chunk, marker)
    return r.sub(chunk, content)


def make_query():
    return """
query {
  viewer {
    repositories(first: 100, privacy: PUBLIC) {
      nodes {
        name
        description
        url
        releases(last:1) {
          totalCount
          nodes {
            name
            publishedAt
            url
          }
        }
      }
    }
  }
}
"""


def fetch_releases(oauth_token):
    repos = []
    releases = []
    repo_names = set()

    data = client.execute(
        query=make_query(),
        headers={"Authorization": "Bearer {}".format(oauth_token)},
    )
    print()
    print(json.dumps(data, indent=4))
    print()
    for repo in data["data"]["viewer"]["repositories"]["nodes"]:
        if repo["releases"]["totalCount"] and repo["name"] not in repo_names:
            repos.append(repo)
            repo_names.add(repo["name"])
            releases.append(
                {
                    "repo": repo["name"],
                    "repo_url": repo["url"],
                    "description": repo["description"],
                    "release": repo["releases"]["nodes"][0]["name"]
                    .replace(repo["name"], "")
                    .strip(),
                    "published_at": repo["releases"]["nodes"][0][
                        "publishedAt"
                    ].split("T")[0],
                    "url": repo["releases"]["nodes"][0]["url"],
                }
            )
    return releases


if __name__ == "__main__":
    readme = root / "README.md"
    project_releases = root / "releases.md"
    releases = fetch_releases(TOKEN)
    releases.sort(key=lambda r: r["published_at"], reverse=True)
    md = "\n".join(
        [
            "* [{repo} {release}]({url}) - {published_at}".format(**release)
            for release in releases[:8]
        ]
    )
    readme_contents = readme.open().read()
    rewritten = replace_chunk(readme_contents, "recent_releases", md)

    # Write out full project-releases.md file
    project_releases_md = "\n".join(
        [
            (
                "* **[{repo}]({repo_url})**: [{release}]({url}) - {published_at}\n"
                "<br>{description}"
            ).format(**release)
            for release in releases
        ]
    )
    project_releases_content = project_releases.open().read()
    project_releases_content = replace_chunk(
        project_releases_content, "recent_releases", project_releases_md
    )
    project_releases_content = replace_chunk(
        project_releases_content, "release_count", str(len(releases)), inline=True
    )
    project_releases.open("w").write(project_releases_content)

    readme.open("w").write(rewritten)
