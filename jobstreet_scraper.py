import asyncio
import uuid
from typing import Any, Dict, List
from wreq import Client
from wreq.header import HeaderMap

GRAPHQL_URL = "https://id.jobstreet.com/graphql"

JOB_SEARCH_QUERY = """
query JobSearchV7($params: JobSearchV7QueryInput!) {
  jobSearchV7(params: $params) {
    results {
      jobs {
        id
        title
        listedAt {
          dateTimeUtc
        }
        organisation {
          name
        }
        location {
          displayName {
            text
          }
        }
        salary {
          currency
          min
          max
          period
        }
      }
    }
  }
}
"""


def flatten_jobstreet_record(role_searched: str, job: dict) -> dict:
    job_id = job.get("id", "")
    company_name = job.get("organisation", {}).get("name", "") if job.get("organisation") else ""
    location = (job.get("location") or {}).get("displayName", {}).get("text", "")

    salary = job.get("salary") or {}
    min_salary = salary.get("min") or ""
    max_salary = salary.get("max") or ""
    currency = salary.get("currency") or ""
    period = salary.get("period") or ""

    listed_at = (job.get("listedAt") or {}).get("dateTimeUtc", "")
    job_url = f"https://id.jobstreet.com/id/job/{job_id}" if job_id else ""

    return {
        "Search Keyword": role_searched,
        "Job ID": job_id,
        "Job Title": job.get("title", ""),
        "Company": company_name,
        "Location": location,
        "Salary Currency": currency,
        "Min Salary": min_salary,
        "Max Salary": max_salary,
        "Salary Period": period,
        "Posted Date": listed_at,
        "Source": "Jobstreet",
        "Job URL": job_url,
    }


def build_payload(keyword: str, page: int = 1, page_size: int = 30) -> Dict[str, Any]:
    return {
        "operationName": "JobSearchV7",
        "variables": {
            "params": {
                "searchIntent": {
                    "country": "ID",
                    "locale": "id-ID",
                    "text": keyword,
                    "sort": "listedAt",
                },
                "searchContext": {
                    "brand": "jobstreet",
                    "channel": "web",
                    "intent": "SEARCH",
                    "source": "SEARCH_ENG",
                    "solVisitorId": str(uuid.uuid4()),
                },
                "responseConfig": {
                    "results": ["jobs"],
                    "representations": ["uiV1"],
                    "page": page,
                    "pageSize": page_size,
                },
                "sessionId": str(uuid.uuid4()),
            }
        },
        "query": JOB_SEARCH_QUERY,
    }


async def scrape_jobstreet(client: Client, roles: list[str], max_pages: int = 2) -> List[dict]:
    headers = HeaderMap({
        "accept": "application/graphql-response+json,application/json;q=0.9",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://id.jobstreet.com",
        "referer": "https://id.jobstreet.com/",
        "seek-request-brand": "jobstreet",
        "seek-request-country": "ID",
        "x-seek-site": "chalice",
        "x-custom-features": "application/features.seek.all+json",
    })

    all_jobs = []
    for role in roles:
        print(f"[Jobstreet] Scraping: {role}")
        for page in range(1, max_pages + 1):
            payload = build_payload(keyword=role, page=page)
            try:
                resp = await client.post(url=GRAPHQL_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = await resp.json()
                jobs = (
                    data.get("data", {})
                    .get("jobSearchV7", {})
                    .get("results", {})
                    .get("jobs", [])
                )
                if not jobs:
                    break

                for job in jobs:
                    all_jobs.append(flatten_jobstreet_record(role, job))

                await asyncio.sleep(1.0)
            except Exception as exc:
                print(f"[Jobstreet] Failed '{role}' on page {page}: {exc}")
                break

    return all_jobs