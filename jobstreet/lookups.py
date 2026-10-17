"""/jobstreet/autocomplete, /jobstreet/classifications, /jobstreet/countries
— the search box's location and role-title suggestions (chalice GraphQL),
the classification tree in the market's language (chalice, with the static
table as fallback) and the markets with their filter vocabularies and
salary filter bands."""
import uuid

from jobstreet import cache_config as ttl
from jobstreet import fetch, gql, refdata
from jobstreet import parsers as P
from jobstreet.shared import site


# The area / region / state kinds (no suburbs): what company review
# locations ("Kuala Lumpur", "Selangor") are keyed on.
AREA_KINDS = ["SEEKLocation", "SEEKArea", "Region", "State", "Country"]


def locations(query, country="MY", language=None, limit=10, kinds=None):
    """Suburbs, areas, regions and states matching `query`, with the
    location ids the job search's `location` param accepts."""
    variables = {"searchText": query, "session": uuid.uuid4().hex, "kind": kinds or gql.LOCATION_KINDS,
                 "zone": site(country)["zone"], "languageCode": fetch.language_of(country, language),
                 "countries": [country.upper()]}
    raw = fetch.graphql(gql.LOCATION_SUGGEST, variables, country, label=f"locations {query!r}",
                        operation="MKLocationSuggestions")
    return {"locations": P.location_suggestions(raw, limit)}


def keywords(query, country="MY", language=None, limit=10):
    """Role titles the site's search box would suggest for `query`."""
    variables = {"query": query, "count": limit, "session": uuid.uuid4().hex, "countryCode2": country.upper(),
                 "languageCode": fetch.language_of(country, language)}
    raw = fetch.graphql(gql.KEYWORD_SUGGEST, variables, country, label=f"keywords {query!r}",
                        operation="OntologyRoleTitlesSeniority")
    return {"keywords": P.keyword_suggestions(raw, limit)}


def autocomplete(query, type="locations", country="MY", language=None, limit=10):
    if type == "keywords":
        return keywords(query, country, language, limit)
    return locations(query, country, language, limit)


def _static_classifications():
    subs = {}
    for sid, (parent, name) in refdata.SUBCLASSIFICATIONS.items():
        subs.setdefault(parent, []).append({"id": sid, "name": name})
    out = []
    for cid, name in sorted(refdata.CLASSIFICATIONS.items(), key=lambda kv: kv[1]):
        out.append({"id": cid, "name": name,
                    "subclassifications": sorted(subs.get(cid, []), key=lambda s: s["name"])})
    return out


def classifications(country="MY", language=None):
    """The 30 job classifications with their sub-classifications (the ids
    the job search's classification / subclassification params take), named
    in the market's language (en / id / zh / th); the static English table
    when the site does not answer."""
    lang = fetch.language_of(country, language)
    source = "site"
    try:
        raw = fetch.graphql(gql.CLASSIFICATIONS, {"zone": site(country)["zone"], "languageCode": lang}, country,
                            label="classifications", operation="Classifications")
        out = P.classification_tree(raw)
    except fetch.JobStreetUpstreamError as e:
        print(f"jobstreet: live classifications skipped: {e}")
        out = []
    if len(out) < 20:
        out, source, lang = _static_classifications(), "static", "en"
    return {"country": country.upper(), "language": lang, "source": source, "classifications": out, "count": len(out)}


def _salary_ranges(code):
    def build():
        raw = fetch.graphql(gql.SALARY_RANGES, {"zone": refdata.SITES[code]["zone"], "languageCode": "en"}, code,
                            label=f"salary ranges {code}", operation="SearchSalaryRanges")
        return P.salary_ranges(raw, refdata.SITES[code]["currency"])
    return fetch.shared_raw("salary_ranges", {"country": code}, build, ttl.SALARY_RANGES_CACHE)


def countries():
    """The JobStreet / JobsDB markets this API serves, their UI languages,
    currencies and salary filter bands, and the filter vocabularies."""
    import config
    codes = list(refdata.SITES)
    results = fetch.run_parallel([lambda c=c: _salary_ranges(c) for c in codes], config.JOBSTREET_BATCH_WORKERS)
    bands = {}
    for code, (status, value) in zip(codes, results):
        if status == "ok":
            bands[code] = value
        else:
            print(f"jobstreet: salary ranges for {code} skipped: {value}")
            bands[code] = None
    return {
        "countries": [{"code": code, "name": s["name"], "brand": s["brand"], "host": s["host"],
                       "link": f"https://{s['host']}/", "currency": s["currency"],
                       "languages": [{"code": l, "name": refdata.LANGUAGES[l]} for l in s["languages"]],
                       "salary_ranges": bands.get(code)}
                      for code, s in refdata.SITES.items()],
        "work_types": [{"value": k, "name": refdata.WORK_TYPE_LABELS[v]} for k, v in refdata.WORK_TYPES.items()],
        "work_arrangements": [{"value": k, "name": refdata.WORK_ARRANGEMENT_LABELS[v]}
                              for k, v in refdata.WORK_ARRANGEMENTS.items()],
        "date_ranges": list(refdata.DATE_RANGES),
        "sorts": list(refdata.SORT_MODES),
        "salary_types": list(refdata.SALARY_TYPES),
        "company_sorts": list(refdata.COMPANY_SORTS),
        "company_sizes": list(refdata.COMPANY_SIZES),
        "max_page_size": refdata.MAX_PAGE_SIZE,
    }
