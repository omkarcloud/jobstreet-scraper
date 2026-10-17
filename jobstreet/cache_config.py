"""Cache TTL per /jobstreet/* endpoint (cache.py, keyed on the validated
params — marshmallow fills the defaults, so an omitted param and its default
share a row).

Job listings churn hourly (new ads, expiries, sponsored rotation); one ad
changes rarely once posted; company profiles, reviews and salary ranges
move daily at most; the career guide's role pages and salary figures are
refreshed about monthly; suggestions and reference tables are stable."""
from datetime import timedelta

# --- raw upstream payloads shared by several routes (fetch.shared_raw) ----------
COMPANY_ORGANISATION_CACHE = timedelta(days=30)   # company id -> organisation id (never changes)
COMPANY_LOOKUP_CACHE = timedelta(days=7)          # company name -> first search hit
ROLE_ALIAS_CACHE = timedelta(days=30)             # role title -> career-guide alias
SALARY_RANGES_CACHE = timedelta(days=7)           # a market's salary filter bands

# --- jobs -----------------------------------------------------------------------------
SEARCH_CACHE = timedelta(hours=1)
JOB_CACHE = timedelta(hours=6)

# --- companies ----------------------------------------------------------------------------
COMPANY_SEARCH_CACHE = timedelta(days=1)
FEATURED_CACHE = timedelta(days=1)
COMPANY_CACHE = timedelta(days=1)
REVIEWS_CACHE = timedelta(hours=12)
COMPANY_SALARIES_CACHE = timedelta(days=3)

# --- careers -------------------------------------------------------------------------------
ROLE_CACHE = timedelta(days=3)
ROLE_REVIEWS_CACHE = timedelta(days=1)
ROLE_SEARCH_CACHE = timedelta(days=3)

# --- lookups ------------------------------------------------------------------------------
AUTOCOMPLETE_CACHE = timedelta(days=7)
CLASSIFICATIONS_CACHE = timedelta(days=7)
COUNTRIES_CACHE = timedelta(days=7)
