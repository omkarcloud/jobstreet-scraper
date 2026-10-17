"""Live endpoint smoke tests: one call per /jobstreet/* route against a
running service, with example values proven to return data (2026-10-15).
The listing tooling (derive_facts.py) reads each route's FIRST call from
this file's AST as its working example, so the values stay literals.

Skipped unless JOBSTREET_BASE points at a running service:

    SCRAPERS_PORT=6089 ONLY_SCRAPER=jobstreet python run.py
    JOBSTREET_BASE=http://127.0.0.1:6089 python -m pytest jobstreet/test_endpoints.py -q
"""
import os

import pytest

BASE = os.environ.get("JOBSTREET_BASE", "").rstrip("/")

pytestmark = pytest.mark.skipif(not BASE, reason="set JOBSTREET_BASE to run live endpoint tests")


def call(path, **params):
    from curl_cffi import requests
    resp = requests.get(BASE + path, params=params, timeout=300)
    assert resp.status_code == 200, f"{path} {params} -> {resp.status_code} {resp.text[:300]}"
    body = resp.json()
    assert body, f"{path} returned an empty body"
    return body


def status(path, **params):
    from curl_cffi import requests
    return requests.get(BASE + path, params=params, timeout=300).status_code


def test_job_search():
    body = call("/jobstreet/jobs/search", query="software engineer", location="Kuala Lumpur")
    assert body["count"] > 50 and len(body["jobs"]) == 20 and body["next"]
    job = body["jobs"][0]
    assert job["id"].isdigit() and job["title"] and job["link"].startswith("https://my.jobstreet.com/job/")
    assert job["classifications"] and job["listed_at"] and body["facets"]["work_types"]
    assert body["location"]["id"] == 1000190
    page2 = call("/jobstreet/jobs/search", query="software engineer", location="Kuala Lumpur", page=2)
    assert page2["jobs"][0]["id"] not in {j["id"] for j in body["jobs"]}
    body = call("/jobstreet/jobs/search", query="nurse", country="SG", work_type="full_time", date_range="last_30_days",
                sort="date", page_size=5)
    assert body["jobs"] and all(j["link"].startswith("https://sg.jobstreet.com/") for j in body["jobs"])
    assert all(w["value"] == "full_time" for j in body["jobs"] for w in j["work_types"])
    body = call("/jobstreet/jobs/search", query="engineer", country="ID", language="id", salary_min=5000000,
                salary_type="monthly", page_size=5)
    assert body["jobs"] and body["jobs"][0]["link"].startswith("https://id.jobstreet.com/job/")
    assert any((j["salary"] or {}).get("currency") == "IDR" for j in body["jobs"])
    body = call("/jobstreet/jobs/search", query="engineer", classification="Information & Communication Technology",
                work_arrangement="remote", country="PH", page_size=5)
    assert body["jobs"] and all(c["id"] == "6281" for j in body["jobs"] for c in j["classifications"])
    body = call("/jobstreet/jobs/search", query="accountant", country="HK", language="zh", page_size=3)
    assert body["jobs"] and body["jobs"][0]["link"].startswith("https://hk.jobsdb.com/job/")
    assert status("/jobstreet/jobs/search", query="nurse", country="MY", language="th") == 400
    assert status("/jobstreet/jobs/search", query="nurse", country="VN") == 400


def test_job_details():
    listing = call("/jobstreet/jobs/search", query="accountant", location="Selangor", page_size=1)
    job_id = listing["jobs"][0]["id"]
    body = call("/jobstreet/jobs/details", job=f"https://my.jobstreet.com/job/{job_id}")
    assert body["id"] == job_id and body["description_html"] and body["description_text"]
    assert body["classification"]["id"] and body["location"]["country_code"] == "MY" and body["advertiser"]["name"]
    assert body["apply"]["link"].endswith(f"/job/{job_id}/apply") and body["listed_at"]
    th = call("/jobstreet/jobs/search", query="engineer", country="TH", page_size=1)
    body = call("/jobstreet/jobs/details", job=th["jobs"][0]["id"], country="TH", language="th")
    assert body["link"].startswith("https://th.jobsdb.com/job/") and body["location"]["country_code"] == "TH"
    assert status("/jobstreet/jobs/details", job="1") == 404
    assert status("/jobstreet/jobs/details", job="abc") == 400


def test_job_batch():
    listing = call("/jobstreet/jobs/search", query="accountant", page_size=3)
    ids = sorted({j["id"] for j in listing["jobs"]})      # sponsored cards can repeat an id
    body = call("/jobstreet/jobs/batch", jobs=",".join(ids + ["1"]))
    assert body["count"] == len(ids) and body["errors"] == {"1": "not found"}


def test_company_search_and_featured():
    body = call("/jobstreet/companies/search", industry="Banking & Credit", sort="rating")
    assert body["count"] > 50 and len(body["companies"]) == 20 and body["next"]
    assert all(c["industry"] == "Banking & Credit" for c in body["companies"]) and body["companies"][0]["rating"]
    body = call("/jobstreet/companies/search", query="bank", country="SG", page_size=5)
    assert body["companies"] and all("bank" in c["name"].lower() for c in body["companies"])
    assert body["companies"][0]["link"].startswith("https://sg.jobstreet.com/companies/")
    body = call("/jobstreet/companies/search", size="More than 10,000", country="HK", page_size=5)
    assert body["companies"] and all(c["size"] == "More than 10,000" for c in body["companies"])
    body = call("/jobstreet/companies/featured", limit=10)
    assert body["count"] == 10 and body["companies"][0]["id"] and body["companies"][0]["logo"]
    assert status("/jobstreet/companies/search", size="huge") == 400


def test_company_details():
    body = call("/jobstreet/companies/details", company="Samsung")
    assert body["id"] == "168550523576228" and body["industry"]["name"] and body["ratings"]["review_count"] > 100
    assert body["description"] and body["link"] == "https://my.jobstreet.com/companies/samsung-168550523576228"
    assert body["jobs_count"] is not None and body["review_locations"]
    body = call("/jobstreet/companies/details", company="https://hk.jobsdb.com/companies/hsbc-171107345917466")
    assert body["name"] == "HSBC" and body["link"].startswith("https://hk.jobsdb.com/")
    assert status("/jobstreet/companies/details", company="zzqqxx nonexistent corp") == 404


def test_company_reviews_salaries_jobs():
    body = call("/jobstreet/companies/reviews", company="samsung-168550523576228", page_size=5)
    assert body["count"] > 100 and len(body["reviews"]) == 5 and body["reviews"][0]["created_at"]
    assert body["reviews"][0]["rating"] and body["company"]["rating"]
    body = call("/jobstreet/companies/reviews", company="168550523576228", location="Kuala Lumpur", page_size=5)
    assert body["reviews"] and all("Kuala Lumpur" in (r["work_location"] or "") for r in body["reviews"])
    body = call("/jobstreet/companies/salaries", company="Accenture")
    assert body["count"] > 0 and body["roles"][0]["company"]["min"] and body["last_updated"]
    body = call("/jobstreet/companies/jobs", company="Samsung", page_size=5)
    assert body["count"] > 3 and body["jobs"] and body["company"]["organisation_id"] == "407946"
    ph = call("/jobstreet/companies/reviews", company="Accenture", country="PH", page_size=3)
    assert ph["count"] > 1000 and ph["company"]["link"].startswith("https://ph.jobstreet.com/")


def test_roles():
    body = call("/jobstreet/roles/search", query="nurse")
    assert body["count"] > 3 and body["roles"][0]["alias"] and body["roles"][0]["typical_salary"]
    body = call("/jobstreet/roles/details", role="Software Engineer")
    assert body["alias"] == "software-engineer" and 2000 < body["salary"]["typical"]["min"] < 20000
    assert body["salary"]["currency"] == "MYR" and body["salary"]["by_location"] and body["tasks_and_duties"]
    idn = call("/jobstreet/roles/details", role="software-engineer", country="ID", language="id")
    assert idn["salary"]["currency"] == "IDR" and idn["link"].startswith("https://id.jobstreet.com/")
    assert idn["salary"]["typical"]["min"] > 1000000 and idn["summary"]
    body = call("/jobstreet/roles/reviews", role="software-engineer", page_size=5)
    assert body["count"] > 3 and body["reviews"] and body["reviews"][0]["good_things"]
    assert status("/jobstreet/roles/details", role="zzqx-no-role") == 404


def test_lookups():
    body = call("/jobstreet/autocomplete", query="kuala")
    assert body["locations"][0]["id"] == 1000190 and "Kuala Lumpur" in body["locations"][0]["name"]
    body = call("/jobstreet/autocomplete", query="data sci", type="keywords", country="SG")
    assert body["keywords"][0]["name"].startswith("Data Sci")
    body = call("/jobstreet/classifications")
    assert body["count"] == 30 and body["source"] == "site" and body["classifications"][0]["subclassifications"]
    th = call("/jobstreet/classifications", country="TH", language="th")
    assert th["count"] == 30 and th["language"] == "th" and th["classifications"][0]["name"] != body["classifications"][0]["name"]
    body = call("/jobstreet/countries")
    assert [c["code"] for c in body["countries"]] == ["MY", "SG", "PH", "ID", "HK", "TH"]
    assert body["countries"][0]["salary_ranges"]["monthly"]["bands"]
    assert status("/jobstreet/jobs/search", query="x", bogus=1) == 400
