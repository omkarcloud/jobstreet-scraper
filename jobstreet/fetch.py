"""JobStreet / JobsDB transport: plain curl_cffi, no browser, validated
2026-10-15 from a direct India egress with no cookies, on all six markets.

Surfaces (all on the public site hosts — my/sg/ph/id.jobstreet.com,
hk/th.jobsdb.com — picked by `country`):

  search_api(params, country, language)
                                /api/jobsearch/v5/search — the job-search
                                JSON API behind the sites' own result pages:
                                100 cards per call, facets, related searches,
                                every filter the site has, localised through
                                `locale`, and company-scoped
                                (companyid=<organisation id>) and advertiser-
                                scoped listings. Open: no auth, no cookies,
                                and no depth cap (page 500 x 100 still
                                answers).
  graphql(doc, vars, country)   /graphql (the SEEK-platform "chalice" API):
                                job details, company profiles / reviews /
                                salary ranges, the company directory search,
                                featured companies, company name search,
                                location and role-title suggestions, the
                                classification tree, the salary filter
                                bands. Introspection is disabled, but the
                                endpoint is NOT behind the Cloudflare
                                challenge that fronts the HTML pages.
  career_graphql(doc, vars, country, language)
                                career-guide-api.cloud.seek.com.au/graphql:
                                role guides, salary data, role reviews and
                                role search. Country-scoped by headers (each
                                market has its own salary figures).

NOT used: the HTML search pages (/jobs, /<kw>-jobs/in-<loc>) and job pages
(/job/<id>) — Cloudflare answers every scripted client, curl_cffi with Chrome
TLS included, with a managed challenge (cf-mitigated: challenge). The APIs
above cover everything those pages show. No company directory pages exist
on these markets (the chalice directory search replaces them).

Egress: direct by default (config.JOBSTREET_PROXY_COUNTRY None). A failed
call is retried on a fresh sticky residential exit
(config.jobstreet_proxy(fallback=True)) — the Airbnb/Indeed/Seek GraphQL
policy. If direct egress ever starts getting the challenge on the APIs, set
JOBSTREET_PROXY_COUNTRY and every call rides a sticky exit; the patchright
click-through (indeed/fetch.py _browser_page) is the escalation after that
— not built while plain HTTP works.

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  JobStreetUpstreamError  transport failure / 5xx / unexpected body — retryable
  JobStreetBlocked        Cloudflare challenge / 403 / 429            — retryable on a new exit
  JobStreetQueryError     the site refused our GraphQL document (schema drift) — not retried
  JobStreetBadRequest     the site rejected the params                — never retried
  JobStreetNotFound       no such job / company / role               — never retried
"""
import json
import os
import re
import sys
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError
from jobstreet import refdata

SEARCH_PATH = "/api/jobsearch/v5/search"
GRAPHQL_PATH = "/graphql"
CAREER_GRAPHQL_URL = "https://career-guide-api.cloud.seek.com.au/graphql"
IMPERSONATE = "chrome"
TIMEOUT = (10, 40)            # (connect, read)

JSON_HEADERS = {"accept": "application/json, text/plain, */*", "accept-language": "en-US,en;q=0.9"}
CF_MARKERS = ("just a moment", "challenge-error-text", "cf-chl", "challenge-platform", "attention required")


class JobStreetUpstreamError(UpstreamError):
    """Transport failure, 5xx or an unexpected body — retryable."""


class JobStreetBlocked(JobStreetUpstreamError, Blocked):
    """Cloudflare challenge / 403 / 429 — retryable on a fresh exit."""


class JobStreetQueryError(JobStreetUpstreamError):
    """The site refused our GraphQL document (schema drift) — a retry cannot help."""


class JobStreetBadRequest(BadRequest):
    """The site rejected the params — never retried."""


class JobStreetNotFound(NotFound):
    """No such job / company / role — never retried."""


def site(country):
    return refdata.SITES.get((country or refdata.DEFAULT_COUNTRY).upper(), refdata.SITES[refdata.DEFAULT_COUNTRY])


def language_of(country, language=None):
    """The UI language to ask for: the requested one when the market offers
    it, else the market's default."""
    s = site(country)
    lang = (language or "").lower()
    return lang if lang in s["languages"] else s["languages"][0]


def dump_debug(name, text):
    """Write a raw response to $JOBSTREET_DEBUG_DIR/<name>.txt for post-mortems."""
    dbg = os.environ.get("JOBSTREET_DEBUG_DIR", "")
    if dbg and text:
        try:
            os.makedirs(dbg, exist_ok=True)
            with open(os.path.join(dbg, name + ".txt"), "w") as f:
                f.write(text)
        except OSError:
            pass


# ---- curl sessions (per thread, keyed by exit) ---------------------------------------------------

_local = threading.local()


def _sessions():
    store = getattr(_local, "sessions", None)
    if store is None:
        store = _local.sessions = OrderedDict()
    return store


def _session(key, proxy):
    from curl_cffi import requests as curl_requests
    store = _sessions()
    sess = store.get(key)
    if sess is None:
        sess = curl_requests.Session(impersonate=IMPERSONATE)
        if proxy:
            sess.proxies = {"http": proxy, "https": proxy}
        store[key] = sess
        while len(store) > 4:
            _, old = store.popitem(last=False)
            try:
                old.close()
            except Exception:
                pass
    else:
        store.move_to_end(key)
    return sess


def _drop_session(key):
    sess = _sessions().pop(key, None)
    if sess is not None:
        try:
            sess.close()
        except Exception:
            pass


def _attempts(label, send):
    """Run send(session) under the retry policy: JobStreetUpstreamError (incl.
    Blocked) retries on a fresh exit up to config.JOBSTREET_MAX_ATTEMPTS
    times; BadRequest / NotFound / QueryError surface at once."""
    attempts = max(1, int(config.JOBSTREET_MAX_ATTEMPTS))
    last = None
    for attempt in range(1, attempts + 1):
        proxy = config.jobstreet_proxy(fallback=attempt > 1)
        key = f"{attempt if proxy else 0}:{proxy or 'direct'}"
        sess = _session(key, proxy)
        try:
            return send(sess)
        except (JobStreetBadRequest, JobStreetNotFound, JobStreetQueryError):
            raise
        except JobStreetUpstreamError as e:
            last = e
        except Exception as e:
            last = JobStreetUpstreamError(f"request failed on {label}: {type(e).__name__}: {e}")
        _drop_session(key)
        print(f"jobstreet: attempt {attempt}/{attempts} on {label} failed: {last}")
        if attempt < attempts:
            time.sleep(0.5 * attempt)
    raise last


def is_challenged(status, headers, text):
    if (headers or {}).get("cf-mitigated") == "challenge":
        return True
    head = (text or "")[:4000].lower()
    return status in (403, 429, 503) and any(m in head for m in CF_MARKERS)


def _classify(resp, label, json_body=True):
    """Raise the failure a response represents, else return its JSON (or text)."""
    status = resp.status_code
    headers = dict(resp.headers)
    text = resp.text or ""
    if is_challenged(status, headers, text):
        dump_debug("challenged", text)
        raise JobStreetBlocked(f"Cloudflare challenge (HTTP {status}) on {label}")
    if status in (403, 429):
        raise JobStreetBlocked(f"HTTP {status} on {label}")
    if status in (404, 410):
        raise JobStreetNotFound(f"JobStreet has no page for {label}")
    if status == 400:
        raise JobStreetBadRequest(f"JobStreet rejected the request on {label}: {text[:200]}")
    if status >= 500:
        raise JobStreetUpstreamError(f"HTTP {status} on {label}")
    if status != 200:
        raise JobStreetUpstreamError(f"HTTP {status} on {label}")
    if not json_body:
        return text
    try:
        return json.loads(text)
    except ValueError:
        dump_debug("non_json", text)
        raise JobStreetUpstreamError(f"non-JSON answer on {label}")


# ---- job search API ------------------------------------------------------------------------------

def search_api(params, country=None, language=None, label="job search"):
    """GET the job-search API with `params` (the site's own names) -> its JSON."""
    s = site(country)
    query = {"siteKey": s["site_key"], "sourcesystem": "houston",
             "locale": refdata.locale(country, language_of(country, language))}
    query.update({k: v for k, v in (params or {}).items() if v not in (None, "", [])})
    url = f"https://{s['host']}{SEARCH_PATH}?{urlencode(query, doseq=True)}"

    def send(sess):
        resp = sess.get(url, headers=JSON_HEADERS, timeout=TIMEOUT)
        body = _classify(resp, label)
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            dump_debug("search_unexpected", resp.text)
            raise JobStreetUpstreamError(f"unexpected job-search payload on {label}")
        return body
    return _attempts(label, send)


# ---- GraphQL -------------------------------------------------------------------------------------------

# Field-level errors of the last GraphQL answer on this thread (tolerated
# when real data came with them) — for the fixture capture / debugging.
_diag = threading.local()


def last_graphql_errors():
    return list(getattr(_diag, "errors", None) or [])


def _graphql_data(resp, label, partial_ok=True):
    body = _classify(resp, label)
    if not isinstance(body, dict):
        raise JobStreetUpstreamError(f"unexpected GraphQL answer on {label}")
    errors = [e for e in (body.get("errors") or []) if isinstance(e, dict)]
    _diag.errors = errors
    data = body.get("data")
    has_data = isinstance(data, dict) and any(v is not None for v in data.values())
    if errors and not (partial_ok and has_data):
        codes = {str((e.get("extensions") or {}).get("code")) for e in errors}
        messages = "; ".join(str(e.get("message", ""))[:300] for e in errors)
        if codes & {"GRAPHQL_VALIDATION_FAILED", "GRAPHQL_PARSE_FAILED"}:
            dump_debug("graphql_validation", resp.text)
            raise JobStreetQueryError(f"JobStreet refused the query on {label}: {messages}")
        if "BAD_USER_INPUT" in codes:
            raise JobStreetBadRequest(messages or "JobStreet rejected the parameters.")
        if re.search(r"\bnot found\b", messages, re.I):
            # a missing company comes back as data: null + a DOMAIN_ERROR
            # "CompanyDetails not found" — an entity miss, not an outage
            raise JobStreetNotFound(f"JobStreet has no {label} ({messages})")
        dump_debug("graphql_error", resp.text)
        raise JobStreetUpstreamError(f"GraphQL error on {label}: {messages or 'empty data'}")
    if not isinstance(data, dict):
        raise JobStreetUpstreamError(f"GraphQL answer without data on {label}")
    return data


def graphql(query, variables=None, country=None, label="graphql", operation=None):
    """POST one chalice GraphQL document on the country's site host -> `data`.
    Field-level errors next to real data are tolerated (the API reports
    optional sub-fields it will not serve as errors)."""
    s = site(country)
    url = f"https://{s['host']}{GRAPHQL_PATH}"
    headers = dict(JSON_HEADERS, **{
        "content-type": "application/json",
        "seek-request-brand": s["brand"],
        "seek-request-country": (country or refdata.DEFAULT_COUNTRY).upper(),
        "x-seek-site": "chalice",
        "origin": f"https://{s['host']}",
        "referer": f"https://{s['host']}/",
    })
    payload = {"operationName": operation, "variables": variables or {}, "query": query}

    def send(sess):
        resp = sess.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        return _graphql_data(resp, label)
    return _attempts(label, send)


def career_graphql(query, variables=None, country=None, language=None, label="career graphql", operation=None):
    """POST one career-guide document -> `data`; country-scoped by headers
    (the salary figures and typical salaries differ per market) and
    language-scoped (role guides exist in id / th as well as en)."""
    s = site(country)
    code = (country or refdata.DEFAULT_COUNTRY).upper()
    headers = dict(JSON_HEADERS, **{
        "content-type": "application/json",
        "x-seek-site": "skl-career-guide-site",
        "country": code,
        "seek-request-country": code,
        "seek-request-brand": s["brand"],
        "language": language_of(country, language),
        "origin": f"https://{s['host']}",
        "referer": f"https://{s['host']}/career-advice/",
    })
    payload = {"operationName": operation, "variables": variables or {}, "query": query}

    def send(sess):
        resp = sess.post(CAREER_GRAPHQL_URL, headers=headers, json=payload, timeout=TIMEOUT)
        return _graphql_data(resp, label)
    return _attempts(label, send)


def standard_variables(country, language=None):
    """The zone / locale / language / country / timezone variable set the
    chalice documents take, plus a fresh visitor id."""
    s = site(country)
    lang = language_of(country, language)
    return {
        "zone": s["zone"],
        "locale": refdata.locale(country, lang),
        "languageCode": lang,
        "countryCode": (country or refdata.DEFAULT_COUNTRY).upper(),
        "timezone": s["timezone"],
        "visitorId": str(uuid.uuid4()),
    }


# ---- memo / cache / parallel ---------------------------------------------------------------------------

_memo = OrderedDict()
_memo_lock = threading.Lock()
MEMO_TTL = 600
MEMO_MAX = 256


def memoized(key, fn, ttl=MEMO_TTL):
    now = time.monotonic()
    with _memo_lock:
        hit = _memo.get(key)
        if hit and now - hit[0] < ttl:
            _memo.move_to_end(key)
            return hit[1]
    value = fn()
    with _memo_lock:
        _memo[key] = (now, value)
        _memo.move_to_end(key)
        while len(_memo) > MEMO_MAX:
            _memo.popitem(last=False)
    return value


def shared_raw(name, params, build, ttl):
    """An upstream payload shared by several routes: in-process memo, then
    the service's response cache (pods share it) when one is installed,
    then build(). Without a `cache` module (the standalone package) it is
    the in-process memo alone."""
    try:
        from cache import cached_call
    except ImportError:
        cached_call = None
    seconds = ttl.total_seconds() if hasattr(ttl, "total_seconds") else ttl
    key = (name, json.dumps(params, sort_keys=True))
    if cached_call is None:
        return memoized(key, build, ttl=min(seconds, MEMO_TTL))
    return memoized(key, lambda: cached_call(f"jobstreet.raw.{name}", params, lambda **_: build(), ttl),
                    ttl=min(seconds, MEMO_TTL))


def run_parallel(fns, workers):
    """Run zero-arg callables in parallel; results align with `fns`. Each
    result is ("ok", value) or ("error", exception)."""
    def guard(fn):
        try:
            return ("ok", fn())
        except Exception as e:
            return ("error", e)
    if not fns:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(fns)))) as ex:
        return list(ex.map(guard, fns))


if __name__ == "__main__":
    # Smoke test: python jobstreet/fetch.py
    body = search_api({"keywords": "engineer", "pageSize": 2}, "MY")
    print("search:", body.get("totalCount"), [j.get("title") for j in body["data"]])
    job_id = body["data"][0]["id"]
    from jobstreet import gql
    data = graphql(gql.JOB_DETAILS, dict(standard_variables("MY"), jobId=job_id), "MY", label=f"job {job_id}")
    print("job:", (data.get("jobDetails") or {}).get("job", {}).get("title"))
    data = career_graphql(gql.ROLE_SEARCH, {"term": "nurse", "size": 3, "from": 0, "filter": {"type": "ROLE"}}, "MY")
    print("roles:", [i["title"] for i in data["searchV2"]["items"]])
