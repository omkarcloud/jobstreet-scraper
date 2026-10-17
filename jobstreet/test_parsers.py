"""Offline tests: refs resolvers, marshmallow schemas, value helpers, parsers
and the endpoint functions with the transport monkeypatched to serve
fixtures (jobstreet/fixtures/*.json.gz, raw payloads captured 2026-10-15
from my/sg/ph/id.jobstreet.com and hk/th.jobsdb.com) — no network.

    python -m pytest jobstreet/test_parsers.py -q
"""
import gzip
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobstreet import (careers, companies, fetch, jobs, lookups, parsers as P, refs,  # noqa: E402
                       schemas, shared as S)
from schema_fields import load_query  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SAMSUNG = "168550523576228"


def fx(name):
    with gzip.open(os.path.join(FX, name + ".json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)


# ---- refs ------------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("MY", "MY"), ("my", "MY"), ("Malaysia", "MY"), ("sg", "SG"), ("Hong Kong", "HK"), ("thailand", "TH"),
    ("hk.jobsdb.com", "HK"), ("https://my.jobstreet.com/jobs?keywords=x", "MY"), ("https://www.jobstreet.com.ph/job/1", "PH"),
    ("https://id.jobstreet.com/id/job/95291681", "ID"), ("www.jobsdb.com", "HK"), ("jobstreet.co.id", "ID"),
])
def test_resolve_country(value, expected):
    assert refs.resolve_country(value) == expected


@pytest.mark.parametrize("value", ["", "VN", "AU", "Atlantis", "https://example.com/x", "https://www.seek.com.au/job/1"])
def test_resolve_country_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_country(value)


@pytest.mark.parametrize("value,expected", [("en", "en"), ("ID", "id"), ("zh-HK", "zh"), ("th-TH", "th"), ("Thai", "th")])
def test_resolve_language(value, expected):
    assert refs.resolve_language(value) == expected


@pytest.mark.parametrize("value", [
    "95239788", "https://my.jobstreet.com/job/95239788?type=promoted", "https://id.jobstreet.com/id/job/95239788",
    "www.jobstreet.com.my/job/95239788/apply", "https://hk.jobsdb.com/job/95239788#sol=abc",
])
def test_resolve_job(value):
    assert refs.resolve_job(value) == "95239788"


@pytest.mark.parametrize("value", ["", "abc", "https://my.jobstreet.com/jobs?keywords=x", "https://example.com/job/1"])
def test_resolve_job_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_job(value)


@pytest.mark.parametrize("value,expected", [
    (SAMSUNG, {"id": SAMSUNG, "slug": None, "name": None, "country": None}),
    ("samsung-168550523576228", {"id": SAMSUNG, "slug": "samsung-168550523576228", "name": None, "country": None}),
    ("https://my.jobstreet.com/companies/samsung-168550523576228/reviews?page=2",
     {"id": SAMSUNG, "slug": "samsung-168550523576228", "name": None, "country": "MY"}),
    ("https://hk.jobsdb.com/companies/hsbc-171107345917466",
     {"id": "171107345917466", "slug": "hsbc-171107345917466", "name": None, "country": "HK"}),
    ("Bank  Rakyat", {"id": None, "slug": None, "name": "Bank Rakyat", "country": None}),
])
def test_resolve_company(value, expected):
    assert refs.resolve_company(value) == expected


@pytest.mark.parametrize("value", ["", "https://my.jobstreet.com/companies/directory/x", "https://example.com/companies/x-1"])
def test_resolve_company_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_company(value)


@pytest.mark.parametrize("value,expected", [
    ("software-engineer", {"alias": "software-engineer", "title": None}),
    ("Software Engineer", {"alias": None, "title": "Software Engineer"}),
    ("https://my.jobstreet.com/career-advice/role/software-engineer/salary", {"alias": "software-engineer", "title": None}),
])
def test_resolve_role(value, expected):
    assert refs.resolve_role(value) == expected


# ---- schemas ---------------------------------------------------------------------------------------

def test_job_search_schema_maps_filters():
    data, error = load_query(schemas.JobSearchSchema, {
        "query": "nurse", "location": "Kuala Lumpur", "country": "id", "language": "ID", "sort": "date",
        "date_range": "last_7_days", "work_type": "full_time,casual", "work_arrangement": "remote",
        "classification": "Healthcare & Medical,6281", "subclassification": "6290", "salary_min": "5000000",
        "salary_max": "12000000", "salary_type": "Monthly", "distance": "25", "advertiser": "63914379",
        "page": "2", "page_size": "50"})
    assert error is None
    assert data["country"] == "ID" and data["language"] == "id" and data["sort"] == "ListedDate" and data["date_range"] == "7"
    assert data["work_type"] == ["242", "245"] and data["work_arrangement"] == ["3"]
    assert data["classification"] == ["1211", "6281"] and data["subclassification"] == ["6290"]
    assert data["salary_min"] == 5000000 and data["salary_type"] == "monthly" and data["page_size"] == 50
    data, error = load_query(schemas.JobSearchSchema, {"query": "x"})
    assert error is None and data["country"] == "MY" and data["language"] == "en" and data["salary_type"] == "monthly"


@pytest.mark.parametrize("query,field", [
    ({"page": "1001"}, "page"),
    ({"salary_min": "100", "salary_max": "50"}, "salary_max"),
    ({"classification": "Astrology"}, "classification"),
    ({"work_type": "weekend"}, "work_type"),
    ({"advertiser": "acme"}, "advertiser"),
    ({"bogus": "1"}, "bogus"),
    ({"page_size": "101"}, "page_size"),
    ({"country": "MY", "language": "th"}, "language"),
    ({"country": "VN"}, "country"),
    ({"language": "fr"}, "language"),
])
def test_job_search_schema_rejects(query, field):
    data, error = load_query(schemas.JobSearchSchema, query)
    assert data is None and field in error["errors"]


def test_batch_schema():
    data, error = load_query(schemas.JobBatchSchema, {"jobs": "95239788, https://sg.jobstreet.com/job/80000000,95239788",
                                                      "country": "sg"})
    assert error is None and data["jobs"] == ["95239788", "80000000"] and data["country"] == "SG"
    data, error = load_query(schemas.JobBatchSchema, {"jobs": ",".join(str(i) for i in range(11))})
    assert data is None and "jobs" in error["errors"]


def test_company_and_role_schemas():
    data, error = load_query(schemas.CompanyReviewsSchema, {"company": "samsung-168550523576228", "page": "3",
                                                            "location": "Kuala Lumpur"})
    assert error is None and data["company"]["id"] == SAMSUNG and data["page"] == 3 and data["page_size"] == 20
    data, error = load_query(schemas.CompanySearchSchema, {"industry": "Banking & Credit", "size": "more than 10,000",
                                                           "sort": "Work_Life_Balance", "country": "hk"})
    assert error is None and data["size"] == "More than 10,000" and data["sort"] == "WORK_LIFE_BALANCE"
    assert data["country"] == "HK" and data["query"] is None and data["page_size"] == 20
    data, error = load_query(schemas.CompanySearchSchema, {"size": "huge"})
    assert data is None and "size" in error["errors"]
    data, error = load_query(schemas.FeaturedSchema, {"limit": "30"})
    assert data is None and "limit" in error["errors"]
    data, error = load_query(schemas.RoleSearchSchema, {"query": "nurse", "sort": "salary", "country": "TH", "language": "th"})
    assert error is None and data["sort"] == "SALARY" and data["page_size"] == 10 and data["language"] == "th"
    data, error = load_query(schemas.AutocompleteSchema, {"query": "kuala", "type": "Keywords"})
    assert error is None and data["type"] == "keywords"
    data, error = load_query(schemas.ClassificationsSchema, {"country": "HK", "language": "zh"})
    assert error is None and data == {"country": "HK", "language": "zh"}


# ---- value helpers ----------------------------------------------------------------------------------

@pytest.mark.parametrize("label,low,high,period", [
    ("RM\xa03,800 – RM\xa04,800 per month", 3800, 4800, "monthly"),
    ("Rp\xa05.500.000 – Rp\xa08.000.000 per month", 5500000, 8000000, "monthly"),
    ("Rp10.000.000 – Rp15.000.000 per month", 10000000, 15000000, "monthly"),
    ("Rp\xa012,000,000 – Rp\xa018,000,000 per month", 12000000, 18000000, "monthly"),
    ("₱19,000 – ₱20,000 per month", 19000, 20000, "monthly"),
    ("฿100,000 – ฿150,000 per month", 100000, 150000, "monthly"),
    ("$5 – $7.80 per hour", 5, 7.8, "hourly"),
    ("$70000.00 - $80000.00 p.m.", 70000, 80000, "monthly"),
    ("80-100k THB", 80000, 100000, None),
    ("MYR 3,000 - 4,500", 3000, 4500, None),
    ("RM\xa015,000 per month", 15000, 15000, "monthly"),
    ("RM 3,500.00 – RM 4,500.00 per month", 3500, 4500, "monthly"),
    ("Rp 5.500.000,00 – Rp 8.000.000,00 per bulan", 5500000, 8000000, "monthly"),
    ("฿40,000 - ฿55,000 /month", 40000, 55000, "monthly"),
    ("$25/hour", 25, 25, "hourly"),
    ("Up to RM 12,000 per month", None, 12000, "monthly"),
    ("Salaried Monthly", None, None, "monthly"),
    ("Competitive salary", None, None, None),
])
def test_salary_from_label(label, low, high, period):
    out = S.salary_from_label(label, "MYR")
    assert (out["min"], out["max"], out["period"], out["currency"]) == (low, high, period, "MYR")
    assert set(out) == {"label", "min", "max", "currency", "period"}


def test_salary_from_label_empty():
    assert S.salary_from_label("", "MYR") is None and S.salary_from_label(None, "MYR") is None


def test_html_to_text():
    out = S.html_to_text("<p>Hello <b>world</b></p><ul><li>a</li><li>b</li></ul>x &amp; y<br>z<script>no()</script>")
    assert out == "Hello world\n- a\n- b\n\nx & y\nz"
    assert S.html_to_text("plain") == "plain" and S.html_to_text(None) is None


def test_iso_datetime_and_ids():
    assert S.iso_datetime({"dateTimeUtc": "2026-09-18T04:30:49.433Z"}) == "2026-09-18T04:30:49Z"
    assert S.iso_date("21 Sep 2026") == "2026-09-21" and S.iso_date(S.iso_datetime("2026-10-13T01:00:00Z")) == "2026-10-13"
    assert S.seek_id("seek-1000190") == 1000190 and S.seek_id(1000190) == 1000190 and S.seek_id(None) is None
    assert S.company_slug_id("samsung-168550523576228") == ("samsung", SAMSUNG)
    assert S.count(-1) == 0 and S.count(5) == 5 and S.count(None) is None
    assert S.text("2 小時前") == "2 小時前"


def test_work_type_localised():
    assert P.work_type(None, "Kontrak") == {"value": "contract", "label": "Kontrak"}
    assert P.work_type(None, "งานเต็มเวลา") == {"value": "full_time", "label": "งานเต็มเวลา"}
    assert P.work_type(None, "Paruh waktu")["value"] == "part_time"
    assert P.work_type("242") == {"value": "full_time", "label": "Full time"}
    assert P.work_type(None, "Something else") == {"value": "something_else", "label": "Something else"}


# ---- parsers: jobs ----------------------------------------------------------------------------------------

def test_search_result():
    raw = fx("search_my")
    out = P.search_result(raw, "MY", 1, 20)
    assert out["pagination"]["total_count"] == raw["totalCount"] > 1000
    assert out["pagination"] == {"page": 1, "items_per_page": 20, "total_pages": -(-raw["totalCount"] // 20),
                                 "total_count": raw["totalCount"]}
    assert out["location"]["id"] == 1000190 and out["location"]["type"] == "state"
    assert out["facets"]["work_types"][0]["value"] == "full_time" and out["facets"]["locations"]
    assert out["related_searches"] and out["related_searches"][0]["total_jobs"]
    job = out["jobs"][0]
    assert job["id"] == "95158155" and job["link"] == "https://my.jobstreet.com/job/95158155"
    assert job["salary"] == {"label": "RM 3,800 – RM 4,800 per month", "min": 3800, "max": 4800, "currency": "MYR",
                             "period": "monthly"}
    assert job["listed_at"] == "2026-10-09T01:30:50Z" and job["classifications"][0]["id"] == "1209"
    assert job["work_types"] == [{"value": "full_time", "label": "Full time"}]
    assert "results_limit" not in out
    dumped = json.dumps(out)
    assert "solMetadata" not in dumped and "tracking" not in job and "__typename" not in dumped


def test_search_result_empty_and_company():
    out = P.search_result(fx("search_empty"), "MY", 1, 5)
    assert out["jobs"] == [] and out["pagination"]["total_pages"] == 0 and out["facets"] is None
    out = P.search_result(fx("search_company"), "MY", 1, 20)
    assert out["jobs"] and all(j["company"]["id"] == SAMSUNG for j in out["jobs"])
    assert out["jobs"][0]["company"]["link"] == "https://my.jobstreet.com/companies/samsung-168550523576228"


def test_search_cards_localised():
    job = P.job_card(fx("search_id")["data"][0], "ID")
    assert job["link"].startswith("https://id.jobstreet.com/job/") and job["salary"]["currency"] == "IDR"
    assert job["salary"]["min"] >= 1000000 and job["salary"]["period"] == "monthly"
    assert job["classifications"][0]["name"] == "Teknik"          # localised label, SEEK id
    cards = [P.job_card(c, "ID") for c in fx("search_id")["data"]]
    assert {w["value"] for j in cards for w in j["work_types"]} <= {"full_time", "part_time", "contract", "casual"}
    th = P.job_card(fx("search_th")["data"][0], "TH")
    assert th["link"].startswith("https://th.jobsdb.com/job/") and th["work_types"][0]["value"] == "full_time"
    assert th["work_arrangements"][0]["value"] == "on_site" and th["work_arrangements"][0]["label"] == "เข้าออฟฟิศ"
    hk = P.job_card(fx("search_hk")["data"][0], "HK")
    assert hk["link"].startswith("https://hk.jobsdb.com/job/") and hk["locations"][0]["country_code"] == "HK"


def test_job_details():
    job = P.job_details(fx("job_details"), "MY")
    assert job["id"] == "95158155" and job["title"].startswith("Graduate Engineer") and job["status"] == "active"
    assert not job["is_expired"] and job["description_text"] and "<" not in job["description_text"]
    assert job["description_html"].startswith("<")
    assert job["salary"]["min"] == 3800 and job["salary"]["currency"] == "MYR" and job["salary"]["period"] == "monthly"
    assert job["work_type"]["value"] == "full_time" and job["classification"]["id"] == "1209"
    assert job["location"]["country_code"] == "MY" and job["location"]["state"]
    assert job["apply"]["link"] == "https://my.jobstreet.com/job/95158155/apply" and job["listed_at"] and job["expires_at"]
    assert job["advertiser"]["id"] and job["advertiser"]["name"]
    assert job["applicants"] is None or job["applicants"]["count"] is not None
    company = P.job_details(fx("job_details_company"), "MY")
    assert company["advertiser"]["jobs_link"].startswith("https://my.jobstreet.com/")


def test_job_details_company_expired_missing_localised():
    job = P.job_details(fx("job_details_company"), "MY")
    assert job["company"]["id"] and job["company"]["link"].startswith("https://my.jobstreet.com/companies/")
    assert job["company"]["industry"] == "Construction" and job["company"]["has_reviews"] is True
    expired = P.job_details(fx("job_details_expired"), "MY")
    assert expired["is_expired"] and expired["status"] == "expired" and expired["expired_at"]
    assert P.job_details(fx("job_details_missing"), "MY") is None
    idn = P.job_details(fx("job_details_id"), "ID")
    assert idn["link"] == "https://id.jobstreet.com/job/95291681" and idn["location"]["country_code"] == "ID"
    assert idn["classification"] == {"id": "1209", "name": "Teknik", "subclassification": {"id": "6035", "name": "Teknik Mesin"}}
    assert idn["work_type"]["value"] == "contract" and idn["salary"]["min"] == 5500000
    assert idn["applicants"]["count"] and idn["applicants"]["with_resume_percent"] and idn["applicants"]["with_cover_letter_percent"]
    hk = P.job_details(fx("job_details_hk"), "HK")
    assert hk["link"].startswith("https://hk.jobsdb.com/job/") and hk["company"]["link"].startswith("https://hk.jobsdb.com/")


# ---- parsers: companies ---------------------------------------------------------------------------------------

def test_company_lookup_and_directory():
    hits = P.company_lookup(fx("company_lookup"), "MY")
    assert hits[0]["name"].startswith("Samsung") and hits[0]["link"].startswith("https://my.jobstreet.com/companies/")
    assert hits[0]["organisation_id"] and hits[0]["is_published"] is True
    out = P.company_directory(fx("company_directory"), "MY", 1, 20)
    assert out["pagination"]["total_count"] == 174 and out["pagination"]["items_per_page"] == 20
    assert len(out["companies"]) == 20 and out["pagination"]["total_pages"] == 9
    c = out["companies"][0]
    assert c["industry"] == "Banking & Credit" and c["rating"] and c["sort_rating"]["type"] == "overall_rating"
    assert c["link"] == f"https://my.jobstreet.com/companies/{c['slug']}" and c["organisation_id"]
    out = P.company_directory(fx("company_directory_name"), "MY", 2, 5)
    assert out["pagination"]["page"] == 2 and all("bank" in c["name"].lower() for c in out["companies"])
    out = P.company_directory(fx("company_directory_empty"), "MY", 1, 5)
    assert out["companies"] == [] and out["pagination"]["total_count"] == 0
    feat = P.marquee_companies(fx("marquee"), "MY")
    assert feat["count"] == 10 and feat["companies"][0]["link"].startswith("https://my.jobstreet.com/companies/")
    assert "serviceToken" not in json.dumps(feat)


def test_company_details():
    out = P.company_details(fx("company_details"), "MY", SAMSUNG)
    assert out["name"] == "Samsung" and out["organisation_id"] == "407946" and out["slug"] == "samsung-168550523576228"
    assert out["industry"] == {"id": "I0017", "name": "Consumer Electronics Manufacturing"} and out["size"] == "101-1,000"
    assert out["ratings"]["overall"] == 4.2 and out["ratings"]["review_count"] == 303
    assert out["ratings"]["recommended_percent"] == 83 and out["ratings"]["distribution"]["5"] == 151
    assert out["ratings"]["categories"]["work_life_balance"] == {"rating": 3.4, "count": 303}
    assert out["ratings"]["salary"] == {"poor_percent": 12, "fair_percent": 67, "generous_percent": 21}
    assert out["review_summary"]["reviews_count"] == 30 and "<strong>" not in out["review_summary"]["text"]
    assert out["review_locations"][0]["link"].startswith("https://my.jobstreet.com/companies/samsung-168550523576228/reviews/locations/")
    assert "traditional_land" not in out
    hk = P.company_details(fx("company_details_hk"), "HK", "171107345917466")
    assert hk["name"] == "HSBC" and hk["link"] == "https://hk.jobsdb.com/companies/hsbc-171107345917466"
    assert hk["industry"]["name"] == "Banking & Credit"


def test_company_reviews():
    out = P.company_reviews(fx("company_reviews"), "MY", SAMSUNG, 1, 20)
    assert out["pagination"] == {"page": 1, "items_per_page": 20, "total_pages": 16, "total_count": 304}
    assert out["company"]["rating"] == 4.2 and len(out["reviews"]) == 20
    review = out["reviews"][0]
    assert review["created_at"] and review["created_at"].endswith("Z") and review["rating"]
    assert review["ratings"] and review["is_recommended"] in (True, False) and review["salary_summary"]
    loc = P.company_reviews(fx("company_reviews_location"), "MY", SAMSUNG, 1, 5)
    assert loc["pagination"]["total_count"] == 14 and all("Kuala Lumpur" in r["work_location"] for r in loc["reviews"])


def test_company_salaries_and_organisation():
    out = P.company_salaries(fx("company_salaries"), "MY", "168556930331378")
    assert out["company"]["name"] == "Accenture" and out["last_updated"] and out["count"] == len(out["roles"]) == 12
    role = out["roles"][0]
    assert role["company"]["currency"] == "MYR" and role["company"]["period"] == "monthly" and role["company"]["min"]
    assert role["company"]["label"] == "RM 8.5K - RM 10K" and role["company"]["max"] == 10000
    assert P.company_organisation(fx("company_organisation")) == {"id": SAMSUNG, "organisation_id": "407946",
                                                                   "name": "Samsung", "slug": "samsung-168550523576228"}
    missing = {"companyDetails": {"id": "999999", "companyProfile": None,
                                  "companySalaryRange": {"lastUpdatedAt": {"dateTimeUtc": "2026-10-13T00:00:00Z"},
                                                         "salaryRangeByRoles": []}}}
    assert P.company_salaries(missing, "MY", "999999") is None


def test_graphql_not_found_domain_error():
    """data: null + a DOMAIN_ERROR 'CompanyDetails not found' (what chalice
    answers for an unknown company id) is a 404, not a retried 502."""
    class Resp:
        status_code, headers = 200, {}
        text = json.dumps({"data": None, "errors": [{"message": "CompanyDetails not found",
                                                      "extensions": {"kind": "domain_error", "code": "DOMAIN_ERROR"}}]})
    with pytest.raises(fetch.JobStreetNotFound):
        fetch._graphql_data(Resp(), "company 999999")
    Resp.text = json.dumps({"data": None, "errors": [{"message": "upstream timeout", "extensions": {"code": "INTERNAL"}}]})
    with pytest.raises(fetch.JobStreetUpstreamError):
        fetch._graphql_data(Resp(), "company 1")


# ---- parsers: suggestions, reference data, careers ------------------------------------------------------------

def test_suggestions_and_reference_data():
    assert P.location_suggestions(fx("location_suggest"), 2) == [
        {"id": 1000190, "name": "Kuala Lumpur", "country_code": "MY"},
        {"id": 28275, "name": "Kuala Lumpur City Centre Kuala Lumpur", "country_code": "MY"}]
    assert P.keyword_suggestions(fx("keyword_suggest"), 1) == [{"id": "software-engineer", "name": "Software Engineer"}]
    tree = P.classification_tree(fx("classifications_my"))
    assert len(tree) == 30 and tree[0]["name"] == "Accounting" and tree[0]["id"] == "1200"
    assert {s["id"] for s in tree[0]["subclassifications"]} == {sid for sid, (p, _) in
                                                                 __import__("jobstreet.refdata").refdata.SUBCLASSIFICATIONS.items()
                                                                 if p == "1200"}
    th = P.classification_tree(fx("classifications_th"))
    assert len(th) == 30 and all(c["name"] for c in th) and th[0]["name"] != tree[0]["name"]
    bands = P.salary_ranges(fx("salary_ranges_my"), "MYR")
    assert bands["monthly"]["is_default"] is True and bands["monthly"]["bands"][1] == {"label": "RM 1K", "value": 1000}
    assert bands["annual"]["currency"] == "MYR" and bands["monthly"]["bands"][-1]["value"] is None


def test_role_details():
    out = P.role_details(fx("role"), fx("role_salaries"), "MY")
    assert out["alias"] == "software-engineer" and out["link"] == "https://my.jobstreet.com/career-advice/role/software-engineer"
    assert out["salary"]["typical"] == {"min": 4200, "max": 6000} and out["salary"]["currency"] == "MYR"
    assert out["salary"]["period"] == "monthly" and out["salary"]["national"]["median"] == 5000
    states = [l for l in out["salary"]["by_location"] if l["location"]["type"] == "state"]
    assert states[0]["location"]["name"] == "Johor" and states[0]["median"] == 5500
    assert out["skills"]["experience"] and len(out["tasks_and_duties"]) >= 3 and out["how_to_become"]["steps"]
    assert out["review_statistics"]["review_count"] == 10 and out["review_statistics"]["job_satisfaction"] == 3.6
    assert out["review_statistics"]["working_hours"]["overtime_percent"]["sometimes"] == 50.0
    assert out["similar_roles"][0]["alias"] and out["classifications"][0]["id"]
    idn = P.role_details(fx("role_id"), fx("role_salaries_id"), "ID")
    assert idn["salary"]["currency"] == "IDR" and idn["salary"]["typical"]["min"] == 6000000
    assert idn["summary"].startswith("Merancang") and idn["link"].startswith("https://id.jobstreet.com/")
    hk = P.role_details(fx("role_hk"), {}, "HK")
    assert hk["salary"]["currency"] == "HKD" and hk["salary"]["by_location"] == [] and hk["review_statistics"] is None
    assert P.role_details(fx("role_missing"), {}, "MY") is None


def test_role_reviews_and_search():
    out = P.role_reviews(fx("role_reviews"), "MY", "software-engineer", 1, 10)
    assert out["pagination"]["total_count"] == 8 and out["pagination"]["total_pages"] == 1
    review = out["reviews"][0]
    assert review["rating"] and review["submitted_at"].endswith("Z") and review["good_things"]
    none = P.role_reviews(fx("role_reviews_none"), "SG", "software-engineer", 1, 10)
    assert none["pagination"]["total_count"] == 0 and none["reviews"] == []
    out = P.role_search(fx("role_search"), "MY", 1, 10)
    assert out["pagination"]["total_count"] == 7 and out["roles"][0]["alias"] == "nurse"
    assert out["roles"][0]["typical_salary"]["min"] == 3000 and out["classifications"][0]["name"]
    assert P.normalised_role_alias(fx("role_normalise")) == "software-engineer"


# ---- endpoint functions on fixtures (transport monkeypatched) -------------------------------------------

@pytest.fixture
def offline(monkeypatch):
    calls = []

    def search_api(params, country=None, language=None, label=""):
        calls.append(("search", dict(params), country, language))
        if params.get("companyid"):
            return fx("search_company")
        return {"ID": fx("search_id"), "TH": fx("search_th"), "HK": fx("search_hk")}.get(country, fx("search_my"))

    def graphql(query, variables=None, country=None, label="", operation=None):
        calls.append((operation, dict(variables or {}), country))
        return {
            "jobDetails": fx("job_details"), "SearchCompanies": fx("company_lookup"),
            "SearchCompanyDetails": fx("company_directory"), "MarqueeCompanies": fx("marquee"),
            "GetCompanyDetails": fx("company_details"), "CompanyReviews": fx("company_reviews"),
            "GetCompanySalaryRange": fx("company_salaries"), "GetCompanyOrganisation": fx("company_organisation"),
            "MKLocationSuggestions": fx("location_suggest_area" if "SEEKLocation" in (variables or {}).get("kind", [])
                                        else "location_suggest"),
            "OntologyRoleTitlesSeniority": fx("keyword_suggest"),
            "Classifications": fx("classifications_th" if country == "TH" else "classifications_my"),
            "SearchSalaryRanges": fx("salary_ranges_my"),
        }[operation]

    def career_graphql(query, variables=None, country=None, language=None, label="", operation=None):
        calls.append((operation, dict(variables or {}), country, language))
        return {"GetRole": fx("role"), "GetRoleSalaries": fx("role_salaries"), "GetRoleReviews": fx("role_reviews"),
                "SearchV2": fx("role_search"), "GetNormalisedRoles": fx("role_normalise")}[operation]

    monkeypatch.setattr(fetch, "search_api", search_api)
    monkeypatch.setattr(fetch, "graphql", graphql)
    monkeypatch.setattr(fetch, "career_graphql", career_graphql)
    monkeypatch.setattr(fetch, "shared_raw", lambda name, params, build, ttl: build())
    return calls


def test_jobs_endpoints(offline):
    out = jobs.search("engineer", "Kuala Lumpur", "MY", "en", page=2, page_size=20, sort="ListedDate",
                      work_type=["242"], salary_min=3000)
    sent = offline[-1][1]
    assert sent["keywords"] == "engineer" and sent["where"] == "Kuala Lumpur" and sent["page"] == 2
    assert sent["sortmode"] == "ListedDate" and sent["worktype"] == "242" and sent["salaryrange"] == "3000-"
    assert sent["salarytype"] == "monthly" and out["query"] == "engineer" and len(out["jobs"]) == 20
    jobs.search(location="1000190", country="ID", language="id")
    assert offline[-1][1]["whereid"] == "1000190" and "where" not in offline[-1][1] and offline[-1][3] == "id"
    assert jobs.details("95158155")["id"] == "95158155" and offline[-1][1]["jobId"] == "95158155"
    assert offline[-1][1]["zone"] == "asia-5" and offline[-1][1]["locale"] == "en-MY"
    jobs.details("95158155", "TH", "th")
    assert offline[-1][1]["locale"] == "th-TH" and offline[-1][1]["languageCode"] == "th" and offline[-1][1]["zone"] == "asia-3"
    out = jobs.batch(["95158155", "95158155"])
    assert out["count"] == 2 and out["errors"] is None


def test_companies_endpoints(offline):
    out = companies.search(industry="Banking & Credit", sort="OVERALL_RATING", country="MY", page=1, page_size=20)
    assert offline[-1][1]["filter"] == {"zone": "asia-5", "industry": "Banking & Credit", "sortBy": "OVERALL_RATING"}
    assert out["pagination"]["total_count"] == 174 and out["filters"]["industry"] == "Banking & Credit"
    assert companies.featured("HK", 5)["count"] == 10 and offline[-1][1] == {"zone": "asia-1", "limit": 5}
    out = companies.details({"id": None, "slug": None, "name": "Samsung", "country": None})
    assert out["id"] == SAMSUNG and out["jobs_count"] == fx("search_company")["totalCount"]
    assert [c for c in offline if c[0] == "SearchCompanies"][-1][1]["name"] == "Samsung"
    out = companies.reviews({"id": SAMSUNG, "slug": None, "name": None, "country": None}, page=1, page_size=20,
                            location="Kuala Lumpur")
    assert offline[-1][1]["locationId"] == "1000190" and out["pagination"]["total_count"] == 304
    assert companies.salaries({"id": "168556930331378", "slug": None, "name": None, "country": None})["count"] == 12
    out = companies.open_jobs({"id": SAMSUNG, "slug": None, "name": None, "country": None}, page_size=20)
    assert offline[-1][1]["companyid"] == "407946" and out["company"]["organisation_id"] == "407946" and out["jobs"]
    assert "facets" not in out
    # a link's market wins over the country param
    companies.details({"id": "171107345917466", "slug": None, "name": None, "country": "HK"}, "MY")
    assert offline[-1][2] == "HK" and offline[-2][1]["zone"] == "asia-1" or offline[-1][1].get("zone") == "asia-1"


def test_careers_and_lookups(offline):
    out = careers.details({"alias": None, "title": "Software Engineer"})
    assert out["alias"] == "software-engineer" and offline[0][0] == "GetNormalisedRoles"
    assert careers.reviews({"alias": "software-engineer", "title": None}, "ID", "id", page=2, page_size=10)["pagination"]["page"] == 2
    assert offline[-1][1]["from"] == 10 and offline[-1][3] == "id"
    out = careers.search("nurse", page=1, page_size=10, sort="SALARY")
    assert out["query"] == "nurse" and offline[-1][1]["sortBy"] == "SALARY"
    assert lookups.autocomplete("kuala", "locations", "MY", limit=2)["locations"][0]["id"] == 1000190
    assert lookups.autocomplete("softw", "keywords", "TH", "th", 1)["keywords"][0]["name"] == "Software Engineer"
    assert offline[-1][1]["countryCode2"] == "TH" and offline[-1][1]["languageCode"] == "th"
    table = lookups.classifications("TH", "th")
    assert table["count"] == 30 and table["source"] == "site" and table["language"] == "th"
    table = lookups.classifications()
    assert table["count"] == 30 and all(c["subclassifications"] for c in table["classifications"])
    out = lookups.countries()
    assert [c["code"] for c in out["countries"]] == ["MY", "SG", "PH", "ID", "HK", "TH"]
    assert out["countries"][4]["brand"] == "jobsdb" and out["countries"][3]["languages"][1]["code"] == "id"
    assert out["countries"][0]["salary_ranges"]["monthly"]["bands"]


def test_language_fallback():
    assert fetch.language_of("MY", "th") == "en" and fetch.language_of("TH", "th") == "th"
    assert fetch.standard_variables("HK", "zh")["locale"] == "zh-HK"
    assert fetch.standard_variables("SG")["locale"] == "en-SG"
