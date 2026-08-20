import asyncio
import json
from pathlib import Path
from wreq import Client, Emulation

from glints_scraper import scrape_glints
from jobstreet_scraper import scrape_jobstreet


async def main():
    roles_file = Path("roles.txt")
    if not roles_file.exists():
        print(f"Error: {roles_file} not found.")
        return

    with open(roles_file, "r", encoding="utf-8") as f:
        roles = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    client = Client(emulation=Emulation.Chrome149)

    print("[*] Fetching data from Glints...")
    glints_jobs = await scrape_glints(client, roles)

    print("[*] Fetching data from JobStreet...")
    jobstreet_jobs = await scrape_jobstreet(client, roles, max_pages=2)

    client.close()

    combined_jobs = glints_jobs + jobstreet_jobs

    # Deduplicate across unique Job IDs
    seen_ids = set()
    deduped_jobs = []
    for job in combined_jobs:
        job_id = job.get("Job ID")
        if job_id and job_id not in seen_ids:
            seen_ids.add(job_id)
            deduped_jobs.append(job)

    output_gsheet = Path("gsheet_data.json")

    if deduped_jobs:
        fieldnames = list(deduped_jobs[0].keys())

        sheet_matrix = [fieldnames] + [
            [str(row.get(k, "")) for k in fieldnames]
            for row in deduped_jobs
        ]

        with open(output_gsheet, "w", encoding="utf-8") as f:
            json.dump(sheet_matrix, f, ensure_ascii=False)

        print(f"[✓] Successfully exported {len(deduped_jobs)} unified records to {output_gsheet}")
    else:
        print("[!] No records extracted.")


if __name__ == "__main__":
    asyncio.run(main())