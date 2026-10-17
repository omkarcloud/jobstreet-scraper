"""/jobstreet/companies/* — the company directory search (name / industry /
size filters, rating sorts), featured companies, profiles, employee
reviews, salary ranges by role and open jobs.

A `company` param arrives resolved by refs.resolve_company: a company id
(the number on every /companies/<name>-<id> link), or a name that is looked
up through the site's own company name search here (first hit)."""
from jobstreet import cache_config as ttl
from jobstreet import fetch, gql, jobs as J, refdata
from jobstreet import parsers as P
from jobstreet.shared import site


def _zone(country):
    return site(country)["zone"]


def _locale(country, language=None):
    return refdata.locale(country, fetch.language_of(country, language))


def search(query=None, industry=None, size=None, sort=None, country="MY", page=1, page_size=20):
    """One page of the market's company directory: profiles matching a name
    fragment and/or an industry and size band, ordered by a review rating
    (overall by default). Every filter is optional; the directory is capped
    at 10,000 rows per listing by the site."""
    filters = {"zone": _zone(country)}
    if query:
        filters["name"] = query
    if industry:
        filters["industry"] = industry
    if size:
        filters["size"] = size
    if sort:
        filters["sortBy"] = sort
    variables = {"filter": filters, "paging": {"page": page, "pageSize": page_size}}
    raw = fetch.graphql(gql.COMPANY_DIRECTORY, variables, country, label=f"company directory p{page}",
                        operation="SearchCompanyDetails")
    result = P.company_directory(raw, country, page, page_size)
    result["filters"] = {"query": query, "industry": industry, "size": size}
    return result


def lookup(name, country="MY", limit=5):
    """Profiles whose name matches `name` (the site's own name search)."""
    variables = {"name": name, "includeBranding": True, "limit": limit, "zone": _zone(country), "published": True}
    raw = fetch.graphql(gql.COMPANY_SEARCH, variables, country, label=f"company lookup {name!r}",
                        operation="SearchCompanies")
    return P.company_lookup(raw, country)


def featured(country="MY", limit=10):
    """The market's featured ("marquee") company profiles."""
    raw = fetch.graphql(gql.MARQUEE_COMPANIES, {"zone": _zone(country), "limit": limit}, country,
                        label="featured companies", operation="MarqueeCompanies")
    return P.marquee_companies(raw, country)


def resolve_id(company, country="MY"):
    """A resolved `company` ref -> its company id (a name is looked up on
    the site: first search hit, memoised + cached)."""
    if company.get("id"):
        return company["id"]
    name = company["name"]

    def build():
        hits = lookup(name, country, limit=5)
        exact = [c for c in hits if (c.get("name") or "").lower() == name.lower()]
        hit = (exact or hits or [None])[0]
        if not hit:
            raise fetch.JobStreetNotFound(f"JobStreet has no company profile named {name!r}")
        return hit["id"]
    return fetch.shared_raw("company_lookup", {"name": name.lower(), "country": country}, build,
                            ttl.COMPANY_LOOKUP_CACHE)


def organisation(company_id, country="MY"):
    """{id, organisation_id, name, slug} of a company id (the organisation id
    is what the job-search API's company filter takes)."""
    def build():
        raw = fetch.graphql(gql.COMPANY_ORGANISATION, {"companyId": company_id}, country,
                            label=f"company {company_id}", operation="GetCompanyOrganisation")
        info = P.company_organisation(raw)
        if not info:
            raise fetch.JobStreetNotFound(f"JobStreet has no company profile with the id {company_id}")
        return info
    return fetch.shared_raw("company_organisation", {"id": company_id, "country": country}, build,
                            ttl.COMPANY_ORGANISATION_CACHE)


def details(company, country="MY", language=None):
    """The full company profile with its ratings summary, AI review
    summary, the locations reviews come from and its live job count."""
    country = company.get("country") or country
    company_id = resolve_id(company, country)
    variables = {"companyId": company_id, "profileId": company_id, "zone": _zone(country),
                 "locale": _locale(country, language)}
    raw = fetch.graphql(gql.COMPANY_DETAILS, variables, country, label=f"company {company_id}",
                        operation="GetCompanyDetails")
    result = P.company_details(raw, country, company_id)
    if result is None:
        raise fetch.JobStreetNotFound(f"JobStreet has no company profile with the id {company_id}")
    try:
        jobs = fetch.search_api({"companyid": result.get("organisation_id"), "pagesize": 1, "include": "nofeatured"},
                                country, language, label=f"company {company_id} jobs count") \
            if result.get("organisation_id") else None
        result["jobs_count"] = (jobs or {}).get("totalCount") if jobs else None
    except fetch.JobStreetUpstreamError as e:
        print(f"jobstreet: jobs count for company {company_id} skipped: {e}")
        result["jobs_count"] = None
    return result


def _location_id(location, country):
    """A review-location text ('Kuala Lumpur', 'Selangor') -> platform location id."""
    if not location:
        return None
    if str(location).isdigit():
        return str(location)
    from jobstreet import lookups
    # reviews are keyed on areas / states, never on suburbs
    hits = lookups.locations(location, country, limit=1, kinds=lookups.AREA_KINDS)["locations"]
    if not hits or hits[0].get("id") is None:
        raise fetch.JobStreetBadRequest(f"JobStreet knows no location matching {location!r}")
    return str(hits[0]["id"])


def reviews(company, country="MY", language=None, page=1, page_size=20, location=None):
    """One page of employee reviews (newest first) with the rating summary."""
    country = company.get("country") or country
    company_id = resolve_id(company, country)
    variables = {"companyId": company_id, "profileId": company_id, "zone": _zone(country),
                 "locale": _locale(country, language), "page": page, "perPage": page_size, "sort": "",
                 "locationId": _location_id(location, country)}
    raw = fetch.graphql(gql.COMPANY_REVIEWS, variables, country, label=f"reviews {company_id} p{page}",
                        operation="CompanyReviews")
    result = P.company_reviews(raw, country, company_id, page, page_size)
    if result is None:
        raise fetch.JobStreetNotFound(f"JobStreet has no company profile with the id {company_id}")
    return result


def salaries(company, country="MY", language=None):
    """Salary range per role at the company versus its industry."""
    country = company.get("country") or country
    company_id = resolve_id(company, country)
    raw = fetch.graphql(gql.COMPANY_SALARIES, {"companyId": company_id, "locale": _locale(country, language)}, country,
                        label=f"company salaries {company_id}", operation="GetCompanySalaryRange")
    result = P.company_salaries(raw, country, company_id)
    if result is None:
        raise fetch.JobStreetNotFound(f"JobStreet has no company profile with the id {company_id}")
    return result


def open_jobs(company, country="MY", language=None, query=None, page=1, page_size=20, sort=None):
    """The company's live job ads (the job-search API scoped to its organisation)."""
    country = company.get("country") or country
    company_id = resolve_id(company, country)
    info = organisation(company_id, country)
    if not info.get("organisation_id"):
        raise fetch.JobStreetNotFound(f"JobStreet lists no jobs for the company {company_id}")
    params = J.search_params(query=query, page=page, page_size=page_size, sort=sort,
                             organisation=info["organisation_id"], facets=False)
    params["include"] = "nofeatured"
    raw = fetch.search_api(params, country, language, label=f"company jobs {company_id} p{page}")
    result = P.search_result(raw, country, page, page_size)
    result.pop("location", None)
    result.pop("location_suggestions", None)
    result.pop("related_searches", None)
    result.pop("facets", None)
    return {"company": dict(info, link=P.S.company_link(country, info.get("slug") or company_id)), **result}
