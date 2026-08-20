import asyncio
from wreq import Client
from wreq.header import HeaderMap

API_URL = "https://glints.com/api/v2-alc/graphql?op=searchJobsV3"

GRAPHQL_QUERY = """query searchJobsV3($data: JobSearchConditionInput!) {
  searchJobsV3(data: $data) {
    jobsInPage {
      id
      title
      createdAt
      company {
        name
      }
      city {
        name
      }
      country {
        name
      }
      salaries {
        minAmount
        maxAmount
        CurrencyCode
      }
    }
  }
}"""


def flatten_glints_record(role_searched: str, job: dict) -> dict:
    job_id = job.get("id", "")
    company_name = job.get("company", {}).get("name", "") if job.get("company") else ""
    city = job.get("city", {}).get("name", "") if job.get("city") else ""
    country = job.get("country", {}).get("name", "") if job.get("country") else ""
    location = f"{city}, {country}".strip(", ") if (city or country) else ""

    salaries = job.get("salaries") or []
    if salaries:
        sal = salaries[0]
        min_salary = sal.get("minAmount") or ""
        max_salary = sal.get("maxAmount") or ""
        currency = sal.get("CurrencyCode") or ""
    else:
        min_salary, max_salary, currency = "", "", ""

    job_url = f"https://glints.com/id/en/opportunities/jobs/{job_id}" if job_id else ""

    return {
        "Search Keyword": role_searched,
        "Job ID": job_id,
        "Job Title": job.get("title", ""),
        "Company": company_name,
        "Location": location,
        "Salary Currency": currency,
        "Min Salary": min_salary,
        "Max Salary": max_salary,
        "Salary Period": "Monthly" if (min_salary or max_salary) else "",
        "Posted Date": job.get("createdAt", ""),
        "Source": "Glints",
        "Job URL": job_url,
    }


async def fetch_role_jobs(client: Client, headers: HeaderMap, role: str) -> list[dict]:
    payload = {
        "operationName": "searchJobsV3",
        "variables": {
            "data": {
                "SearchTerm": role,
                "CountryCode": "ID",
                "sortBy": "LATEST",
                "includeExternalJobs": True,
                "pageSize": 30,
                "page": 1,
            }
        },
        "query": GRAPHQL_QUERY,
    }

    try:
        response = await client.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = await response.json()
        raw_jobs = (
            data.get("data", {})
            .get("searchJobsV3", {})
            .get("jobsInPage", [])
        )
        return [flatten_glints_record(role, job) for job in raw_jobs]
    except Exception as exc:
        print(f"[Glints] Failed to fetch role '{role}': {exc}")
        return []


async def scrape_glints(client: Client, roles: list[str]) -> list[dict]:
    headers = HeaderMap({
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://glints.com",
        "x-glints-country-code": "ID",
    })[cite: 4]

    all_jobs = []
    for role in roles:
        print(f"[Glints] Scraping: {role}")
        jobs = await fetch_role_jobs(client, headers, role)
        all_jobs.extend(jobs)
        await asyncio.sleep(1.0)
    return all_jobs