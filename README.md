# 💼 Jobstreet Scraper

Jobstreet Scraper is a **free and open-source** scraper that gets you **unlimited** detailed JobStreet and JobsDB job data for free.

## ✨ What Can I Get?

- 💼 **300,000+ live jobs across 6 markets** — Malaysia, Singapore, Philippines, Indonesia, Hong Kong & Thailand: full description, salary, applicant counts & screening questions
- 🔍 **Search with every JobStreet filter** — location, monthly salary band, work type, remote / hybrid, classification & date listed
- 🏢 **45,000+ company profiles** — ratings breakdown, AI review summary, employee reviews & pay per role
- 📈 **1,500+ career guides** — monthly salary by state and city, skills, growth & job satisfaction for every role

## 🎥 Example: A Full JobStreet Job Ad

```json
{
  "id": "95144083",
  "title": "Yield Development Engineer",
  "link": "https://my.jobstreet.com/job/95144083",
  "status": "active",
  "description_text": "As a Yield Development Engineer, you will play a critical role in advancing Intel's manufacturing capabilities by driving technology yield improvements ...",
  "work_type": { "value": "full_time", "label": "Full time" },
  "work_arrangement": { "value": "on_site", "label": "On-site" },
  "classification": {
    "id": "1209",
    "name": "Engineering",
    "subclassification": { "id": "6028", "name": "Electrical/Electronic Engineering" }
  },
  "location": { "label": "Bayan Lepas, Penang", "suburb": "Bayan Lepas", "state": "Penang", "country_code": "MY" },
  "applicants": { "count": 153, "count_label": "More than 150 applicants", "with_resume_percent": 100, "with_cover_letter_percent": 38 },
  "screening_questions": [
    "What's your expected monthly basic salary?",
    "How many years' experience do you have as a Development Engineer?"
  ],
  "apply": { "link": "https://my.jobstreet.com/job/95144083/apply", "is_external": false },
  "advertiser": { "id": "60606718", "name": "Intel Technology Sdn. Bhd.", "is_verified": true },
  "company": {
    "id": "168557465784246",
    "name": "Intel",
    "link": "https://my.jobstreet.com/companies/intel-168557465784246",
    "industry": "Consumer Electronics Manufacturing",
    "size": "More than 10,000 employees",
    "rating": 4.4,
    "review_count": 448,
    "perks_and_benefits": ["Medical", "Education support", "Dental"]
  },
  "listed_at": "2026-10-08T07:58:36Z",
  "expires_at": "2026-11-07T12:59:59Z"
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Jobstreet Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/jobstreet-scraper
cd jobstreet-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/jobs/details?job=95144083"
```

```json
{
  "id": "95144083",
  "title": "Yield Development Engineer",
  "link": "https://my.jobstreet.com/job/95144083",
  "work_type": { "value": "full_time", "label": "Full time" },
  "work_arrangement": { "value": "on_site", "label": "On-site" },
  "classification": {
    "id": "1209",
    "name": "Engineering",
    "subclassification": { "id": "6028", "name": "Electrical/Electronic Engineering" }
  },
  "location": { "label": "Bayan Lepas, Penang", "state": "Penang", "country_code": "MY" },
  "applicants": { "count": 153, "count_label": "More than 150 applicants", "volume_label": "High application volume" },
  "company": {
    "name": "Intel",
    "industry": "Consumer Electronics Manufacturing",
    "size": "More than 10,000 employees",
    "rating": 4.4,
    "review_count": 448
  },
  "listed_at": "2026-10-08T07:58:36Z",
  "expires_at": "2026-11-07T12:59:59Z"
}
```

All 15 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

15 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Job Details | `/jobs/details` | The full job ad: description, salary, applicants, questions, employer |
| Search Jobs | `/jobs/search` | Up to 100 jobs per page with every filter and facets |
| Batch Job Details | `/jobs/batch` | Full details for up to 10 jobs in one call |
| Company Details | `/companies/details` | Overview, ratings breakdown, AI review summary, perks and open jobs |
| Company Reviews | `/companies/reviews` | Employee reviews with pros, cons and ratings, newest first |
| Company Salaries | `/companies/salaries` | Pay range per role, compared with the industry |
| Company Jobs | `/companies/jobs` | Every live job ad a company has posted |
| Search Companies | `/companies/search` | The company directory by name, industry and size, sorted by rating |
| Featured Companies | `/companies/featured` | The market's featured employers with rating and open jobs |
| Role Details | `/roles/details` | Monthly salary by state and city, skills, tasks and growth |
| Search Roles | `/roles/search` | Career guide roles with typical salary and satisfaction |
| Role Reviews | `/roles/reviews` | Reviews written by people working in the role |
| Autocomplete | `/autocomplete` | Location IDs and job-title suggestions |
| Classifications | `/classifications` | 30 classifications with sub-classifications, in the market's language |
| Countries | `/countries` | The six markets, salary bands and every search filter value |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-jobstreet-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-jobstreet-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-jobstreet-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/jobs/search",
    params={"query": "software engineer", "location": "Kuala Lumpur"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Jobstreet Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20Jobstreet%20Scraper%20API.)

[![Ask Us by Email about Jobstreet Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Jobstreet%20Scraper%20API&body=I%20need%20help%20using%20the%20Jobstreet%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**Seek Scraper**](https://github.com/omkarcloud/seek-scraper) — Seek Australia & New Zealand jobs, salaries, companies & reviews
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper-api) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/jobstreet-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/jobstreet-scraper)
