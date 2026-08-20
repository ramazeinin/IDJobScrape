import asyncio
import json
from pathlib import Path
from wreq import Client, Emulation
from wreq.header import HeaderMap

API_URL = "https://glints.com/api/v2-alc/graphql?op=searchJobsV3"

GRAPHQL_QUERY = """query searchJobsV3($data: JobSearchConditionInput!) {
  searchJobsV3(data: $data) {
    jobsInPage {
      id
      title
      status
      createdAt
      updatedAt
      isHot
      minYearsOfExperience
      maxYearsOfExperience
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
      skills {
        skill {
          name
        }
      }
    }
  }
}"""


def flatten_job_record(role_searched: str, job: dict) -> dict:
    """Extract nested GraphQL fields into a flat dictionary."""
    company_name = job.get("company", {}).get("name") if job.get("company") else ""
    city = job.get("city", {}).get("name") if job.get("city") else ""
    country = job.get("country", {}).get("name") if job.get("country") else ""

    # Process Salaries
    salaries = job.get("salaries") or []
    if salaries:
        sal = salaries[0]
        min_salary = sal.get("minAmount") or ""
        max_salary = sal.get("maxAmount") or ""
        currency = sal.get("CurrencyCode") or ""
    else:
        min_salary, max_salary, currency = "", "", ""

    # Process Skills list
    skills_raw = job.get("skills") or []
    skills = ", ".join(
        [
            s.get("skill", {}).get("name")
            for s in skills_raw
            if s.get("skill", {}).get("name")
        ]
    )

    return {
        "Search Keyword": role_searched,
        "Job ID": job.get("id", ""),
        "Job Title": job.get("title", ""),
        "Company": company_name,
        "City": city,
        "Country": country,
        "Min Exp (Years)": job.get("minYearsOfExperience", ""),
        "Max Exp (Years)": job.get("maxYearsOfExperience", ""),
        "Salary Currency": currency,
        "Min Salary": min_salary,
        "Max Salary": max_salary,
        "Skills": skills,
        "Posted Date": job.get("createdAt", ""),
        "Updated Date": job.get("updatedAt", ""),
        "Status": job.get("status", ""),
        "Is Hot": job.get("isHot", False),
    }


async def fetch_role_jobs(client: Client, role: str) -> list[dict]:
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

    headers = HeaderMap()
    headers.insert("accept", "*/*")
    headers.insert("content-type", "application/json")
    headers.insert("origin", "https://glints.com")
    headers.insert("x-glints-country-code", "ID")

    try:
        response = await client.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = await response.json()
        raw_jobs = (
            data.get("data", {})
            .get("searchJobsV3", {})
            .get("jobsInPage", [])
        )
        return [flatten_job_record(role, job) for job in raw_jobs]
    except Exception as exc:
        print(f"[!] Failed to fetch role '{role}': {exc}")
        return []


async def main():
    roles_file = Path("roles.txt")
    if not roles_file.exists():
        print(f"Error: {roles_file} not found.")
        return

    with open(roles_file, "r", encoding="utf-8") as f:
        roles = [line.strip() for line in f if line.strip()]

    client = Client(emulation=Emulation.Chrome149)
    all_flattened_rows = []

    for role in roles:
        print(f"[+] Scraping role: {role}")
        rows = await fetch_role_jobs(client, role)
        all_flattened_rows.extend(rows)
        await asyncio.sleep(1.0)

    # Save only the 2D matrix JSON required by gsheet.action
    output_gsheet = Path("gsheet_data.json")

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