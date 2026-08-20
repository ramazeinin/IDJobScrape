import asyncio
import json
from pathlib import Path
import uuid
from typing import Any, Dict, List
from wreq import Client, Emulation
from wreq.header import HeaderMap

GRAPHQL_URL = "https://id.jobstreet.com/graphql"

JOB_SEARCH_QUERY = """
query JobSearchV7($params: JobSearchV7QueryInput!) {
  jobSearchV7(params: $params) {
    results {
      jobs {
        id
        title
        abstract
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


def flatten_job_record(role_searched: str, job: dict) -> dict:
    """Extract nested JobStreet GraphQL fields into a flat dictionary."""
    company_name = job.get("organisation", {}).get("name") if job.get("organisation") else ""
    location = (job.get("location") or {}).get("displayName", {}).get("text", "")
    
    salary = job.get("salary") or {}
    min_salary = salary.get("min") or ""
    max_salary = salary.get("max") or ""
    currency = salary.get("currency") or ""
    period = salary.get("period") or ""

    listed_at = (job.get("listedAt") or {}).get("dateTimeUtc", "")

    return {
        "Search Keyword": role_searched,
        "Job ID": job.get("id", ""),
        "Job Title": job.get("title", ""),
        "Company": company_name,
        "Location": location,
        "Salary Currency": currency,
        "Min Salary": min_salary,
        "Max Salary": max_salary,
        "Salary Period": period,
        "Listed Date": listed_at,
        "Abstract": job.get("abstract", ""),
        "Source": "Jobstreet",
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


async def fetch_role_jobs(client: Client, headers: HeaderMap, role: str, max_pages: int = 2) -> List[dict]:
    role_records = []

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
                role_records.append(flatten_job_record(role, job))

            await asyncio.sleep(1.0)
        except Exception as exc:
            print(f"[!] Failed to fetch role '{role}' on page {page}: {exc}")
            break

    return role_records


async def main():
    roles_file = Path("roles.txt")
    if not roles_file.exists():
        print(f"Error: {roles_file} not found.")
        return

    with open(roles_file, "r", encoding="utf-8") as f:
        roles = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    client = Client(emulation=Emulation.Chrome149)

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

    all_flattened_rows = []
    seen_ids = set()

    for role in roles:
        print(f"[+] Scraping role: {role}")
        rows = await fetch_role_jobs(client, headers, role, max_pages=2)
        for row in rows:
            job_id = row.get("Job ID")
            if job_id and job_id not in seen_ids:
                seen_ids.add(job_id)
                all_flattened_rows.append(row)

    client.close()

    output_gsheet = Path("gsheet_jobstreet_data.json")

    if all_flattened_rows:
        fieldnames = list(all_flattened_rows[0].keys())

        sheet_matrix = [fieldnames] + [
            [str(row.get(k, "")) for k in fieldnames]
            for row in all_flattened_rows
        ]

        with open(output_gsheet, "w", encoding="utf-8") as f:
            json.dump(sheet_matrix, f, ensure_ascii=False)

        print(f"[✓] Successfully exported {len(all_flattened_rows)} records to {output_gsheet}")


if __name__ == "__main__":
    asyncio.run(main())