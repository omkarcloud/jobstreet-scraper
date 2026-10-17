"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json.
"""
import json
import os

from jobstreet.companies import details as company_details
from jobstreet.jobs import details as job_details
from jobstreet.jobs import search as search_jobs

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # a job id or any jobstreet.com / jobsdb.com job link
    save("job_95144083.json", job_details("95144083"))

    # 20 jobs per page; country MY, SG, PH, ID (JobStreet) or HK, TH (JobsDB)
    save("search_software_engineer_kuala_lumpur.json", search_jobs("software engineer", "Kuala Lumpur", "MY"))

    # a company id, a /companies/ link or a name
    save("company_intel.json", company_details({"id": None, "slug": None, "name": "Intel", "country": None}))
