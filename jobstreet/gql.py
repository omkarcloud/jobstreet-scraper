"""GraphQL documents for the two SEEK-platform GraphQL APIs JobStreet /
JobsDB run on (jobstreet/fetch.py sends them):

  * chalice (https://<site host>/graphql) — job details, company profiles /
    reviews / salaries, the company directory search, featured companies,
    company name search, location and role-title suggestions, the
    localised classification tree and the salary filter bands.
    Introspection is off, but the company-candidate-ui bundle ships the
    schema (read 2026-10-15); these documents are the site's own operations
    trimmed to the fields the parsers read.
  * career guide (career-guide-api.cloud.seek.com.au/graphql) — role guides,
    salary suggestions, role reviews and role search (introspection on).
"""

# ---- chalice: jobs ---------------------------------------------------------------------------------

JOB_DETAILS = """
query jobDetails($jobId: ID!, $zone: Zone!, $locale: Locale!, $languageCode: LanguageCodeIso!,
                 $countryCode: CountryCodeIso2!, $timezone: Timezone!, $visitorId: UUID!) {
  jobDetails(id: $jobId) {
    job {
      id
      title
      phoneNumber
      isExpired
      isLinkOut
      isProfileApply
      isVerified
      status
      source
      abstract
      content(platform: WEB)
      url(zone: $zone, locale: $locale)
      createdAt { dateTimeUtc }
      updatedAt { dateTimeUtc }
      listedAt { label(context: JOB_POSTED, length: SHORT, timezone: $timezone, locale: $locale) dateTimeUtc }
      expiresAt { dateTimeUtc }
      expiredAt { dateTimeUtc }
      contactMatches { type value }
      salary { label currencyLabel(zone: $zone) }
      workTypes { label(locale: $locale) }
      advertiser { id name(locale: $locale) isVerified registrationDate { dateTimeUtc } }
      location { label(locale: $locale, type: LONG) }
      classifications { label(languageCode: $languageCode) }
      products {
        branding { id cover { url } logo { url } }
        bullets
        questionnaire { questions }
        video { url position }
        displayTags { label(locale: $locale) }
      }
    }
    insights {
      message(locale: $locale)
      ... on ApplicantCount { count countLabel(locale: $locale) volumeLabel(locale: $locale) }
      ... on ApplicantsWithResumePercentage { percentage }
      ... on ApplicantsWithCoverLetterPercentage { percentage }
    }
    badges(visitorId: $visitorId, platform: WEB, locale: $locale) { badges { badge } }
    companyProfile(zone: $zone) {
      id
      organisationId
      name
      companyNameSlug
      shouldDisplayReviews
      branding { logo }
      overview { description { paragraphs } industry size { description } website { url } }
      reviewsSummary { overallRating { numberOfReviews { value } value } }
      perksAndBenefits { title }
    }
    companySearchUrl(zone: $zone, languageCode: $languageCode)
    companyTags { key value }
    sourcrRecruiter { name jobTitle overallRating reviewCount avatarImageUrl agencyImageUrl contactUrl agencyName }
    restrictedApplication(countryCode: $countryCode) { label(locale: $locale) }
    gfjInfo {
      location { countryCode country(locale: $locale) suburb(locale: $locale) region(locale: $locale) state(locale: $locale) postcode }
      workTypes { label }
    }
    seoInfo {
      normalisedRoleTitle workType classification subClassification
      where(zone: $zone) broaderLocationName(locale: $locale) normalisedOrganisationName
    }
  }
}
"""

# ---- chalice: companies ------------------------------------------------------------------------------

# name lookup (what the site's company search box does): fuzzy on the name
COMPANY_SEARCH = """
query SearchCompanies($name: String!, $includeBranding: Boolean!, $limit: Int, $zone: Zone, $published: Boolean) {
  searchCompanyProfilesByName(name: $name, includeBranding: $includeBranding, limit: $limit, zone: $zone,
                              published: $published) {
    companyId
    organisationId
    zone
    data { name branding { logo } reviewCount reviewRating slug published }
  }
}
"""

# the company directory: filter by name / industry / size, sort by a rating, paged
COMPANY_DIRECTORY = """
query SearchCompanyDetails($filter: SearchCompanyDetailsFilterInput, $paging: SearchCompanyDetailsPagingInput) {
  searchCompanyDetails(filter: $filter, paging: $paging) {
    data {
      companyId
      organisationId
      name
      companySlug
      companyOverview
      logoUrl
      coverUrl
      size
      industry
      sortRating { rating type }
      overallRating { rating count }
      location { suburb area location state country region }
      jobCount
    }
    paging { page perPage total totalPages }
  }
}
"""

# the "featured companies" marquee of the /companies page
MARQUEE_COMPANIES = """
query MarqueeCompanies($zone: Zone!, $limit: Int) {
  marqueeCompanies(limit: $limit, hideJobs: false, zone: $zone) {
    id
    organizationId
    title
    companyNameSlug
    logo
    url
    jobCount
    reviews { rating count }
  }
}
"""

_RATING = "{ rating percentage count }"

COMPANY_DETAILS = """
query GetCompanyDetails($companyId: CompanyId!, $profileId: ID!, $zone: Zone!, $locale: Locale!) {
  companyProfile(id: $profileId, zone: $zone) {
    branding { logo }
    reviewsSummary { overallRating { value numberOfReviews { value } } }
  }
  companyDetails(id: $companyId) {
    id
    companyProfile(draft: false) {
      zone
      organisationId
      companyReviewRating {
        company %(r)s
        perksAndBenefits %(r)s
        careerOpportunity %(r)s
        diversity %(r)s
        executiveManagement %(r)s
        workLifeBalance %(r)s
        workEnvironment %(r)s
        companyRating1Star %(r)s
        companyRating2Star %(r)s
        companyRating3Star %(r)s
        companyRating4Star %(r)s
        companyRating5Star %(r)s
        companyRecommended %(r)s
        salaryPoor %(r)s
        salaryFair %(r)s
        salaryGenerous %(r)s
      }
      data {
        name
        isClaimed
        overview {
          website { url displayName }
          size industry industryId industryName primaryLocation specialities description
        }
        customStatement { title description }
        missionStatement
        featured { title description imageUrl videoUrl }
        awards { imageUrl year name }
        cultureAndValues { title description imageUrl values { title description } }
        perksAndBenefits { title description }
        gallery { title date linkUrl }
        branding { brandId logo cover }
        canonicalUrl
        synonym
        graduates { overview { richTextBody externalUrl } }
      }
    }
    companyReviewsAISummary(locale: $locale) {
      reviewsCount reviewsDateFrom reviewsDateTo
      aISummaryContent { positiveAndChallengesSummary }
    }
    companyReviewLocations(locale: $locale, zone: $zone, sort: true) { contextualName relativeUrl }
  }
}
""" % {"r": _RATING}

COMPANY_REVIEWS = """
query CompanyReviews($companyId: CompanyId!, $profileId: ID!, $zone: Zone!, $locale: Locale!,
                     $page: Int, $perPage: Int, $sort: String, $locationId: ID) {
  companyProfile(id: $profileId, zone: $zone) {
    name
    companyNameSlug
    branding { logo }
    reviewsSummary { overallRating { value numberOfReviews { value } } }
  }
  companyDetails(id: $companyId) {
    id
    companyReviews(zone: $zone, page: $page, sort: $sort, perPage: $perPage, locationId: $locationId) {
      data {
        id
        title
        pros
        cons
        overallExperienceDetails
        jobTitle
        workLocation
        overallRating
        hasBeenFlagged
        upvotes { count description(locale: $locale) }
        salarySummary(locale: $locale)
        employmentStatus(locale: $locale)
        recommended { description(locale: $locale) value }
        ratings { value description(locale: $locale) }
        createdAt { dateTimeUtc }
        reply { createdAt { dateTimeUtc } from text }
      }
      paging { page perPage total totalPages }
    }
  }
}
"""

COMPANY_SALARIES = """
query GetCompanySalaryRange($companyId: CompanyId!, $locale: Locale!) {
  companyDetails(id: $companyId) {
    id
    companyProfile(draft: false) { organisationId data { name canonicalUrl } }
    companySalaryRange(industryId: null) {
      lastUpdatedAt { dateTimeUtc }
      salaryRangeByRoles {
        roleId
        roleTitle(locale: $locale)
        salaryRangeByCompany { jobsCount label(locale: $locale) salaryType }
        salaryRangeByIndustry { jobsCount label(locale: $locale) salaryType industryAverageDescription(locale: $locale) }
      }
    }
  }
}
"""

# The organisation id (what the job-search API's companyid= takes) and the
# profile name of one company id.
COMPANY_ORGANISATION = """
query GetCompanyOrganisation($companyId: CompanyId!) {
  companyDetails(id: $companyId) {
    id
    companyProfile(draft: false) { organisationId data { name canonicalUrl } }
  }
}
"""

# ---- chalice: suggestions + reference data -----------------------------------------------------------

LOCATION_SUGGEST = """
query MKLocationSuggestions($searchText: String!, $session: String!, $kind: [String!]!, $zone: Zone!,
                            $languageCode: LanguageCodeIso, $countries: [CountryCodeIso2!]) {
  mkLocationSuggestions(searchText: $searchText, session: $session, kind: $kind, zone: $zone,
                        languageCode: $languageCode, countries: $countries) {
    text id countryCode
  }
}
"""
LOCATION_KINDS = ["Suburb", "SEEKArea", "Region", "State", "Country"]

KEYWORD_SUGGEST = """
query OntologyRoleTitlesSeniority($query: String!, $count: Int!, $session: String!,
                                  $countryCode2: CountryCodeIso2, $languageCode: LanguageCodeIso) {
  ontologyRoleTitlesSeniority(query: $query, count: $count, session: $session, countryCode2: $countryCode2,
                              languageCode: $languageCode) {
    id normalisedText
  }
}
"""

# the classification tree in the market's language
CLASSIFICATIONS = """
query Classifications($zone: Zone!, $languageCode: LanguageCodeIso) {
  classifications(zone: $zone) {
    id
    description(languageCode: $languageCode)
    subClassifications { id description(languageCode: $languageCode) }
  }
}
"""

# the salary filter bands of the market's search page, per pay frequency
SALARY_RANGES = """
query SearchSalaryRanges($zone: Zone!, $languageCode: LanguageCodeIso) {
  searchSalaryRanges(zone: $zone) {
    frequency { type label(languageCode: $languageCode) isDefault }
    range { label(type: LONG, languageCode: $languageCode) value }
  }
}
"""

# ---- career guide: roles ----------------------------------------------------------------------------------

ROLE = """
query GetRole($alias: String!, $specReqInput: RoleSpecReqsInput!) {
  roleByAlias(alias: $alias) {
    id
    alias
    url
    title
    isReleased
    isThick
    typicalSalary { salary_min salary_max }
    hero { title bannerUrl }
    whatsItLike { introduction extraContent imageUrl videoUrl tasksAndDuties { key text } }
    howToBecome { content steps { key text } }
    classifications { classification classificationCode subclassificationCode classificationUrlSegment }
    roleReviewStatistics {
      total remuneration employability jobSatisfaction workLifeBalance diversityInTasks
      careerProgressionOpportunities overtime weekends shiftWork lateNights workingHoursCount
    }
    growth { startYear endYear value source }
    specReqs(input: $specReqInput) { id name type label }
    salarySuggestion { suggestion locationName salary_min salary_max salary_median }
    similarRoles {
      id alias title isReleased
      typicalSalary { salary_min salary_max }
      roleReviewStatistics { jobSatisfaction }
    }
    pathwayRoles(input: {}) {
      cgRoles { role { id alias title isReleased typicalSalary { salary_min salary_max } } }
    }
    additionalLocales
  }
}
"""

ROLE_SALARIES = """
query GetRoleSalaries($roleId: ID!, $roleTitle: String!) {
  states: salarySuggestionsByRoleId(roleId: $roleId, roleTitle: $roleTitle, locationType: "states") {
    salary_min salary_max salary_median suggestion locationId locationName urlToSearch
  }
  cities: salarySuggestionsByRoleId(roleId: $roleId, roleTitle: $roleTitle) {
    salary_min salary_max salary_median suggestion locationId locationName urlToSearch
  }
  role(role_id: $roleId) { classSalaries { class_id class_title avg_salary } }
}
"""

ROLE_REVIEWS = """
query GetRoleReviews($roleId: ID!, $sentiment: String, $from: Int, $size: Int) {
  roleReviewsCount(role_id: $roleId, sentiment: $sentiment)
  roleReviews(role_id: $roleId, sentiment: $sentiment, from: $from, size: $size) {
    id role_id title submitted overallRating
    relevantQualificationFullName yearsInCurrentRole sizeOfOrganisation currentDepartment
    goodThings challenges
    remuneration employability jobSatisfaction workLifeBalance diversityInTasks careerProgressionOpportunities
  }
}
"""

ROLE_SEARCH = """
query SearchV2($term: String, $sortBy: SORT_BY, $size: Int, $filter: Filter, $from: Int) {
  searchV2(term: $term, sortBy: $sortBy, size: $size, filter: $filter, aggClassifications: true, from: $from) {
    total
    classifications { class classSegmentUrl count }
    items {
      id alias type title growthValue jobSatisfaction typicalSalaryMin typicalSalaryMax image video readTime
      classifications { class classSegmentUrl }
    }
  }
}
"""

# A free-text role title -> the career guide's role (alias), when it has one.
ROLE_NORMALISE = """
query GetNormalisedRoles($roleTitles: [String!]!) {
  getNormalisedRoles(roleTitles: $roleTitles) {
    title normalisedText
    caRole { role_id alias title isReleased }
  }
}
"""
