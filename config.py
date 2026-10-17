"""Configuration for the Jobstreet Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT             port the API listens on (default 8000)
    JOBSTREET_PROXY  proxy URL for every request, e.g. http://user:pass@host:port
                     (default: none — direct). JobStreet's and JobsDB's job-search
                     and GraphQL APIs answer plain HTTP with no cookies, so you
                     very likely don't need this. Set it only if you start
                     seeing failures at high volume.

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

JOBSTREET_PROXY = os.environ.get("JOBSTREET_PROXY") or None

# Names the jobstreet package reads.
JOBSTREET_PROXY_COUNTRY = None              # unused here: JOBSTREET_PROXY above is the whole proxy policy
JOBSTREET_MAX_ATTEMPTS = MAX_RETRIES        # attempts per upstream call
JOBSTREET_BATCH_WORKERS = 4                 # parallel upstream calls in /jobs/batch and /countries


def jobstreet_proxy(fallback=False):
    """The proxy for one JobStreet / JobsDB request: JOBSTREET_PROXY, or None for direct."""
    return os.environ.get("JOBSTREET_PROXY") or None
