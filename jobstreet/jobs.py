"""/jobstreet/jobs/* — job search, job details and batch lookup, from the
sites' job-search API (fetch.search_api) and the chalice GraphQL (jobDetails)."""
from jobstreet import fetch, gql, refdata
from jobstreet import parsers as P

MAX_BATCH = 10


def search_params(query=None, location=None, page=1, page_size=20, sort=None, date_range=None, work_type=None,
                  work_arrangement=None, classification=None, subclassification=None, salary_min=None,
                  salary_max=None, salary_type=None, distance=None, advertiser=None, organisation=None,
                  facets=True):
    """Public params -> the search API's own query (its names and ids)."""
    params = {
        "keywords": query,
        "page": page,
        "pageSize": page_size,
        "sortmode": sort,
        "daterange": date_range,
        "worktype": ",".join(work_type) if work_type else None,
        "workarrangement": ",".join(work_arrangement) if work_arrangement else None,
        "classification": ",".join(classification) if classification else None,
        "subclassification": ",".join(subclassification) if subclassification else None,
        "distance": distance,
        "advertiserid": advertiser,
        "companyid": organisation,
        "include": "seodata,relatedsearches",
        "facets": refdata.SEARCH_FACETS if facets else None,
    }
    if location:
        if str(location).isdigit():
            params["whereid"] = location
        else:
            params["where"] = location
    if salary_min is not None or salary_max is not None:
        params["salaryrange"] = f"{salary_min or ''}-{salary_max or ''}"
        params["salarytype"] = salary_type or refdata.DEFAULT_SALARY_TYPE
    return params


def search(query=None, location=None, country="MY", language=None, page=1, page_size=20, sort=None, date_range=None,
           work_type=None, work_arrangement=None, classification=None, subclassification=None, salary_min=None,
           salary_max=None, salary_type=None, distance=None, advertiser=None):
    """One page of job cards with the site's facets, related searches and
    the resolved location. `sort` / `date_range` / `work_type` / ... arrive
    as the site's own tokens (the schema maps the public values)."""
    params = search_params(query, location, page, page_size, sort, date_range, work_type, work_arrangement,
                           classification, subclassification, salary_min, salary_max, salary_type, distance,
                           advertiser)
    raw = fetch.search_api(params, country, language, label=f"job search {query!r} p{page}")
    result = P.search_result(raw, country, page, page_size)
    result["query"] = query
    return result


def details_raw(job_id, country, language=None):
    variables = dict(fetch.standard_variables(country, language), jobId=job_id)
    return fetch.graphql(gql.JOB_DETAILS, variables, country, label=f"job {job_id}", operation="jobDetails")


def details(job, country="MY", language=None):
    """The full job ad: description, bullets, screening questions, applicant
    counts, salary, advertiser, employer profile. 404 when the site has no
    such job (expired ads still come back, flagged is_expired)."""
    raw = details_raw(job, country, language)
    result = P.job_details(raw, country)
    if result is None:
        raise fetch.JobStreetNotFound(f"JobStreet has no job with the id {job}")
    return result


def batch(jobs, country="MY", language=None):
    """Up to MAX_BATCH jobs by id / link, fetched in parallel. Jobs the site
    no longer has are listed under `errors` instead of failing the call."""
    import config
    results = fetch.run_parallel([lambda j=j: details(j, country, language) for j in jobs],
                                 config.JOBSTREET_BATCH_WORKERS)
    out, errors = [], {}
    for job_id, (status, value) in zip(jobs, results):
        if status == "ok":
            out.append(value)
        elif isinstance(value, fetch.JobStreetNotFound):
            errors[job_id] = "not found"
        else:
            raise value
    return {"jobs": out, "count": len(out), "errors": errors or None}
