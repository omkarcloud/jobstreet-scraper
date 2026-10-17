"""JobStreet input parsing: ONE param per input that auto-detects its forms
(tripadvisor QueryOrLinkField convention, never a sibling `url`/`id` pair).
Every resolver returns plain JSON values so validated params stay usable as
a response-cache key, and raises ValueError with a user-facing message.

  country   MY | my | Malaysia | sg | Hong Kong | hk.jobsdb.com
            | https://my.jobstreet.com/jobs?...                  -> "MY" / "SG" / "PH" / "ID" / "HK" / "TH"
  job       95239788 | https://my.jobstreet.com/job/95239788?type=standard
            | id.jobstreet.com/id/job/95239788 | /job/95239788/apply -> "95239788"
  company   168550523576228 | samsung-168550523576228
            | https://my.jobstreet.com/companies/samsung-168550523576228/reviews
            | Samsung (a name, looked up on the site at call time)
                                        -> {"id": "168550523576228", "slug": "samsung-168550523576228",
                                            "name": None, "country": None}
                                         | {"id": None, "slug": None, "name": "Samsung", "country": None}
            (country is the link's market when a jobstreet / jobsdb link was given)
  role      software-engineer | Software Engineer
            | https://my.jobstreet.com/career-advice/role/software-engineer/salary
                                        -> {"alias": "software-engineer", "title": None}
                                         | {"alias": None, "title": "Software Engineer"} (normalised at call time)
  location  (job search) free text, or a platform location id (1000190) -> as given
"""
import re
from urllib.parse import parse_qs, unquote, urlparse

from jobstreet import refdata

_SLUG_BAD = re.compile(r"[/?#\\<>\"]")
_SITE_HOST_RE = re.compile(r"(?:^|\.)(jobstreet|jobsdb)\.")


def _parse_url(value):
    """-> (host, path, query dict) when value looks like a JobStreet / JobsDB
    URL or host path, None when it is plain text. Raises ValueError for
    another site."""
    raw = (value or "").strip()
    low = raw.lower()
    if low.startswith("//"):
        raw = "https:" + raw
    elif not low.startswith(("http://", "https://")):
        head = low.split("/", 1)[0]
        if not _SITE_HOST_RE.search(head):
            return None
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host not in refdata.HOST_COUNTRIES and not _SITE_HOST_RE.search(host):
        raise ValueError("Must be a jobstreet.com or jobsdb.com link.")
    return host, unquote(parsed.path), parse_qs(parsed.query)


def _country_of_host(host):
    host = (host or "").lower()
    if host in refdata.HOST_COUNTRIES:
        return refdata.HOST_COUNTRIES[host]
    # <cc>.jobstreet.com / <cc>.jobsdb.com / www.jobstreet.com.<cc> / jobstreet.co.id
    match = re.match(r"^([a-z]{2})\.(?:jobstreet|jobsdb)\.", host)
    if match and match.group(1).upper() in refdata.SITES:
        return match.group(1).upper()
    match = re.search(r"jobstreet\.(?:com|co)\.([a-z]{2})$", host)
    if match and match.group(1).upper() in refdata.SITES:
        return match.group(1).upper()
    if "jobsdb" in host:
        return "HK"           # jobsdb.com with no market label is the Hong Kong site
    return None


# ---- country ------------------------------------------------------------------------------------

COUNTRY_HINT = ("Must be a JobStreet / JobsDB market: MY (Malaysia), SG (Singapore), PH (Philippines), "
                "ID (Indonesia), HK (Hong Kong) or TH (Thailand), its name, or a jobstreet.com / jobsdb.com link.")


def resolve_country(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(COUNTRY_HINT)
    try:
        url = _parse_url(raw) if ("." in raw or "/" in raw) else None
    except ValueError:
        raise ValueError(COUNTRY_HINT)
    if url:
        code = _country_of_host(url[0])
        if code:
            return code
        raise ValueError(COUNTRY_HINT)
    low = raw.lower()
    if low in refdata.COUNTRY_NAMES:
        return refdata.COUNTRY_NAMES[low]
    code = raw.upper()
    if code in refdata.SITES:
        return code
    raise ValueError(f"JobStreet has no site for '{raw}'. " + COUNTRY_HINT)


def country_of_link(value):
    """The country of a JobStreet / JobsDB link's host, or None."""
    try:
        url = _parse_url(value or "")
    except ValueError:
        return None
    return _country_of_host(url[0]) if url else None


# ---- language -------------------------------------------------------------------------------------

LANGUAGE_HINT = "Must be a UI language code: en, id (Indonesia), zh (Hong Kong) or th (Thailand)."


def resolve_language(value):
    raw = (value or "").strip().lower().replace("_", "-")
    if not raw:
        raise ValueError(LANGUAGE_HINT)
    lang = raw.split("-", 1)[0]
    aliases = {"english": "en", "bahasa": "id", "indonesian": "id", "chinese": "zh", "thai": "th", "zh-hant": "zh",
               "zh-hk": "zh"}
    lang = aliases.get(raw, aliases.get(lang, lang))
    if lang not in refdata.LANGUAGES:
        raise ValueError(LANGUAGE_HINT)
    return lang


# ---- jobs -------------------------------------------------------------------------------------------

JOB_HINT = ("Must be a JobStreet / JobsDB job id (digits, e.g. 95239788) or a job link "
            "(https://my.jobstreet.com/job/95239788).")


def resolve_job(value):
    raw = (value or "").strip()
    if raw.isdigit():
        return raw
    try:
        url = _parse_url(raw)
    except ValueError:
        raise ValueError(JOB_HINT)
    if not url:
        raise ValueError(JOB_HINT)
    _, path, query = url
    match = re.search(r"/job/(\d+)(?:[/?#]|$)", path)
    if match:
        return match.group(1)
    for name in ("jobId", "jobid", "id"):
        for candidate in query.get(name, []):
            if candidate.strip().isdigit():
                return candidate.strip()
    raise ValueError(JOB_HINT)


# ---- companies ----------------------------------------------------------------------------------------

COMPANY_HINT = ("Must be a company id (168550523576228), the slug from a company page link "
                "(samsung-168550523576228), a jobstreet.com / jobsdb.com /companies/ link, or a company name.")


def resolve_company(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(COMPANY_HINT)
    if raw.isdigit():
        return {"id": raw, "slug": None, "name": None, "country": None}
    try:
        url = _parse_url(raw)
    except ValueError:
        raise ValueError(COMPANY_HINT)
    country = None
    if url:
        match = re.search(r"/companies/([^/?#]+)", url[1])
        if not match or match.group(1) in ("directory", "search", "write-a-review"):
            raise ValueError("Links must be company pages (/companies/<name>-<id>).")
        raw = match.group(1)
        country = _country_of_host(url[0])   # the link's market is the profile's zone
    match = re.fullmatch(r"([a-z0-9][a-z0-9-]*)-(\d+)", raw.lower())
    if match and " " not in raw:
        return {"id": match.group(2), "slug": raw.lower(), "name": None, "country": country}
    name = " ".join(raw.split())
    if _SLUG_BAD.search(name) or len(name) > 150:
        raise ValueError(COMPANY_HINT)
    return {"id": None, "slug": None, "name": name, "country": country}


# ---- roles (career guide) ---------------------------------------------------------------------------------

ROLE_HINT = ("Must be a role title (Software Engineer), a career-guide role alias (software-engineer) "
             "or a jobstreet.com / jobsdb.com /career-advice/role/ link.")


def resolve_role(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(ROLE_HINT)
    try:
        url = _parse_url(raw)
    except ValueError:
        raise ValueError(ROLE_HINT)
    if url:
        match = re.search(r"/career-advice/role/([^/?#]+)", url[1])
        if not match:
            raise ValueError("Links must be career-guide role pages (/career-advice/role/<alias>).")
        return {"alias": match.group(1).lower(), "title": None}
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", raw) and len(raw) <= 120:
        return {"alias": raw, "title": None}
    title = " ".join(raw.split())
    if _SLUG_BAD.search(title) or len(title) > 120:
        raise ValueError(ROLE_HINT)
    return {"alias": None, "title": title}


def slugify_role(title):
    """'Software Engineer' -> 'software-engineer' (the career guide's alias shape)."""
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return slug or None


# ---- locations ----------------------------------------------------------------------------------------------

def resolve_location(value):
    """Free text as typed in the site's 'Where' box, or a platform location id."""
    raw = " ".join((value or "").split())
    if not raw:
        return None
    if len(raw) > 120:
        raise ValueError("Location must be at most 120 characters.")
    return raw
