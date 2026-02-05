"""Linear API connector for creating issues/tickets."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://api.linear.app/graphql"
TIMEOUT = 15

PRIORITY_MAP = {"low": 4, "medium": 3, "high": 2, "urgent": 1}


def _get_headers() -> dict:
    api_key = os.getenv("LINEAR_API_KEY", "")
    return {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }


async def dry_run(payload: dict) -> dict:
    """Return a preview of the Linear issue without creating it."""
    title = payload.get("title", "Untitled")
    description = payload.get("description", "")
    priority = payload.get("priority", "medium")
    return {
        "preview": f"Linear Issue: [{priority.upper()}] {title}\n{description[:200]}{'…' if len(description) > 200 else ''}",
        "title": title,
        "priority": priority,
    }


async def execute(payload: dict) -> dict:
    """Create an issue in Linear."""
    api_key = os.getenv("LINEAR_API_KEY", "")
    if not api_key:
        return {"status": "failed", "error": "LINEAR_API_KEY not configured"}

    title = payload.get("title", "Untitled Issue")
    description = payload.get("description", "")
    priority = payload.get("priority", "medium")
    team_id = payload.get("team_id") or os.getenv("LINEAR_TEAM_ID", "")

    priority_num = PRIORITY_MAP.get(priority, 3)

    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue {
          id
          identifier
          url
          title
        }
      }
    }
    """

    variables = {
        "input": {
            "title": title,
            "description": description,
            "priority": priority_num,
        }
    }
    if team_id:
        variables["input"]["teamId"] = team_id

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                API_URL,
                headers=_get_headers(),
                json={"query": mutation, "variables": variables},
            )
            data = resp.json()

            if resp.status_code != 200:
                return {"status": "failed", "error": f"Linear API returned {resp.status_code}"}

            errors = data.get("errors")
            if errors:
                msg = errors[0].get("message", str(errors))
                logger.error("Linear API error: %s", msg)
                return {"status": "failed", "error": msg[:300]}

            issue_data = data.get("data", {}).get("issueCreate", {})
            if issue_data.get("success"):
                issue = issue_data.get("issue", {})
                logger.info("Linear issue created: %s", issue.get("identifier"))
                return {
                    "status": "success",
                    "id": issue.get("id"),
                    "identifier": issue.get("identifier"),
                    "url": issue.get("url"),
                    "summary": f"Created issue {issue.get('identifier')}: {issue.get('title')}",
                }
            else:
                return {"status": "failed", "error": "issueCreate returned success=false"}

    except httpx.TimeoutException:
        return {"status": "failed", "error": "Linear API timed out"}
    except Exception as e:
        logger.exception("Linear create error")
        return {"status": "failed", "error": str(e)[:300]}
