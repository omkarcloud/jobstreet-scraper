"""Marshmallow request schemas for every /jobstreet/* route.

Generic fields live in the shared top-level schema_fields.py; this module
adds the JobStreet resolvers (refs.py). Every schema's load() output is the
kwargs dict its endpoint function takes.

ONE param per input (tripadvisor QueryOrLinkField convention, never a
sibling `url`/`id` pair): `job` takes a job id OR any JobStreet / JobsDB
job link; `company` a company id, a /companies/<name>-<id> slug or link, or
a company name; `role` a career-guide alias, a title or a
/career-advice/role/ link; `location` free text or a location id;
`country` MY / SG / PH / ID / HK / TH, a name or a site link; `language`
en / id / zh / th (validated against the market's own languages).
"""
from marshmallow import ValidationError, fields, validate, validates_schema

from schema_fields import (BaseSchema, ChoiceField, CommaListField, PageField, PageSizeField, PositiveInt,
                           QueryField, RefField, StrippedString)
from jobstreet import refdata, refs
from jobstreet.jobs import MAX_BATCH


def _max_length(n):
    """validate.Length(max=n) that tolerates the None StrippedString returns
    for an empty value (marshmallow runs validators on it; len(None) is a 500)."""
    def check(value):
        if value is not None and len(value) > n:
            raise ValidationError(f"Longer than maximum length {n}.")
    return check


class CountryField(RefField):
    """The market: MY (default), SG, PH, ID, HK or TH, a name, or a site link."""
    resolver = staticmethod(refs.resolve_country)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", refdata.DEFAULT_COUNTRY)
        super().__init__(**kwargs)


class LanguageField(RefField):
    """The UI language for localised labels: en (default), id, zh or th."""
    resolver = staticmethod(refs.resolve_language)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", refdata.DEFAULT_LANGUAGE)
        super().__init__(**kwargs)


class JobField(RefField):
    resolver = staticmethod(refs.resolve_job)


class CompanyField(RefField):
    resolver = staticmethod(refs.resolve_company)


class RoleField(RefField):
    resolver = staticmethod(refs.resolve_role)


class LocationField(RefField):
    resolver = staticmethod(refs.resolve_location)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        super().__init__(**kwargs)


class JobListField(fields.Field):
    """'95239788, https://my.jobstreet.com/job/95290463' -> ['95239788', '95290463']
    (resolved, deduped, 1..MAX_BATCH)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        out = []
        for item in str(value or "").split(","):
            item = item.strip()
            if not item:
                continue
            try:
                job_id = refs.resolve_job(item)
            except ValueError as e:
                raise ValidationError(f"'{item}': {e}")
            if job_id not in out:
                out.append(job_id)
        if not out:
            raise ValidationError("Must list at least one job id or link (comma-separated).")
        if len(out) > MAX_BATCH:
            raise ValidationError(f"At most {MAX_BATCH} jobs.")
        return out


class _TaxonomyListField(CommaListField):
    """Classification / sub-classification ids OR (English) names -> ids."""
    table = {}
    kind = "classification"

    def __init__(self, **kwargs):
        kwargs.setdefault("max_items", 10)
        super().__init__(upper=False, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        items = super()._deserialize(value, attr, data, **kwargs)
        by_name = {name.lower(): cid for cid, name in self.table.items()}
        out = []
        for item in items or []:
            cid = item if item in self.table else by_name.get(item.lower())
            if not cid:
                raise ValidationError(f"'{item}' is not a JobStreet {self.kind} id or name "
                                      f"(see /jobstreet/classifications).")
            if cid not in out:
                out.append(cid)
        return out or None


class ClassificationListField(_TaxonomyListField):
    table = refdata.CLASSIFICATIONS
    kind = "classification"


class SubclassificationListField(_TaxonomyListField):
    table = {sid: name for sid, (_, name) in refdata.SUBCLASSIFICATIONS.items()}
    kind = "sub-classification"


class AdvertiserField(StrippedString):
    """An advertiser (hirer account) id, as the search facets list them."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if value is None:
            return None
        if not value.isdigit():
            raise ValidationError("Must be an advertiser id (digits, from the search facets).")
        return value


class _Localised(BaseSchema):
    """country + language, checked against the market's own UI languages."""
    country = CountryField()
    language = LanguageField()

    @validates_schema
    def validate_language(self, data, **kwargs):
        country = data.get("country") or refdata.DEFAULT_COUNTRY
        language = data.get("language") or refdata.DEFAULT_LANGUAGE
        offered = refdata.SITES.get(country, {}).get("languages") or [refdata.DEFAULT_LANGUAGE]
        if language not in offered:
            raise ValidationError({"language": [f"{refdata.SITES[country]['name']} offers {', '.join(offered)}; "
                                                f"'{language}' is not one of them."]})


# ---- jobs ----------------------------------------------------------------------------------------------------

class _JobListing(_Localised):
    query = StrippedString(required=False, load_default=None, validate=_max_length(200))
    page = PageField(max_page=refdata.MAX_PAGE)
    page_size = PageSizeField(default=20, max_size=refdata.MAX_PAGE_SIZE)
    sort = ChoiceField(refdata.SORT_MODES, load_default=None)


class JobSearchSchema(_JobListing):
    location = LocationField()
    date_range = ChoiceField(refdata.DATE_RANGES)
    work_type = CommaListField(value_map=refdata.WORK_TYPES, max_items=4)
    work_arrangement = CommaListField(value_map=refdata.WORK_ARRANGEMENTS, max_items=3)
    classification = ClassificationListField()
    subclassification = SubclassificationListField()
    salary_min = PositiveInt(max_value=100_000_000_000)
    salary_max = PositiveInt(max_value=100_000_000_000)
    salary_type = ChoiceField(refdata.SALARY_TYPES, load_default=refdata.DEFAULT_SALARY_TYPE)
    distance = fields.Integer(load_default=None, strict=False, validate=validate.Range(min=0, max=500))
    advertiser = AdvertiserField()

    @validates_schema
    def validate_salary(self, data, **kwargs):
        low, high = data.get("salary_min"), data.get("salary_max")
        if low is not None and high is not None and high < low:
            raise ValidationError({"salary_max": ["Must be >= salary_min."]})


class JobSchema(_Localised):
    job = JobField()


class JobBatchSchema(_Localised):
    jobs = JobListField()


# ---- companies ----------------------------------------------------------------------------------------------------

class CompanySearchSchema(BaseSchema):
    query = StrippedString(required=False, load_default=None, validate=_max_length(100))
    industry = StrippedString(required=False, load_default=None, validate=_max_length(100))
    size = ChoiceField({s: s for s in refdata.COMPANY_SIZES})
    sort = ChoiceField(refdata.COMPANY_SORTS, load_default=None)
    country = CountryField()
    page = PageField(max_page=500)
    page_size = PageSizeField(default=20, max_size=50)


class FeaturedSchema(BaseSchema):
    country = CountryField()
    limit = fields.Integer(load_default=10, strict=False, validate=validate.Range(min=1, max=refdata.MARQUEE_LIMIT_MAX))


class CompanySchema(_Localised):
    company = CompanyField()


class CompanyReviewsSchema(CompanySchema):
    page = PageField(max_page=1000)
    page_size = PageSizeField(default=20, max_size=30)
    location = LocationField()


class CompanyJobsSchema(_JobListing):
    company = CompanyField()


# ---- careers ----------------------------------------------------------------------------------------------------------

class RoleSchema(_Localised):
    role = RoleField()


class RoleReviewsSchema(RoleSchema):
    page = PageField(max_page=500)
    page_size = PageSizeField(default=10, max_size=50)


class RoleSearchSchema(_Localised):
    query = QueryField(max_length=100)
    page = PageField(max_page=100)
    page_size = PageSizeField(default=10, max_size=50)
    sort = ChoiceField(refdata.ROLE_SORTS, load_default=None)


# ---- lookups ------------------------------------------------------------------------------------------------------------

class AutocompleteSchema(_Localised):
    query = QueryField(max_length=100)
    type = ChoiceField(["locations", "keywords"], load_default="locations")
    limit = fields.Integer(load_default=10, strict=False, validate=validate.Range(min=1, max=20))


class ClassificationsSchema(_Localised):
    pass


class EmptySchema(BaseSchema):
    pass
