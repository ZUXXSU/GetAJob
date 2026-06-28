"""
Application form auto-fill kit.
Generates a JSON snippet you can use with browser autofill / Bitwarden / 1Password
to instantly fill common ATS forms (Greenhouse, Lever, Workday, Ashby).

Most ATS forms ask the same 30 fields. This module provides the answers
pre-filled from your profile + tailored cover letter.
"""
import json
import logging

logger = logging.getLogger(__name__)


# Common field name patterns across ATS systems
_FIELD_MAP = {
    "first_name": ["first_name", "firstName", "fname"],
    "last_name": ["last_name", "lastName", "lname", "surname"],
    "full_name": ["name", "fullName", "candidate_name"],
    "email": ["email", "email_address", "candidateEmail"],
    "phone": ["phone", "phone_number", "mobile", "telephone"],
    "location": ["city", "location", "current_location", "candidate_location"],
    "linkedin": ["linkedin", "linkedinUrl", "linkedin_profile"],
    "github": ["github", "githubUrl", "github_profile", "portfolio"],
    "website": ["website", "personal_site", "portfolio_url"],
    "current_company": ["current_company", "currentEmployer", "employer"],
    "current_title": ["current_title", "current_role", "job_title"],
    "years_experience": ["years_of_experience", "experience", "yrs_exp"],
    "salary_expectation": ["salary_expectation", "expected_salary", "desired_salary"],
    "notice_period": ["notice_period", "notice_period_days"],
    "willing_to_relocate": ["relocate", "willing_to_relocate", "relocation"],
    "work_authorization": ["work_authorization", "visa_status", "authorized_to_work"],
    "require_sponsorship": ["require_sponsorship", "needs_visa", "visa_required"],
    "cover_letter": ["cover_letter", "coverLetter", "additional_info", "message"],
    "why_company": ["why_us", "why_company", "interested_because"],
    "how_did_you_hear": ["referral_source", "source", "heard_from"],
    "gender": ["gender"],
    "ethnicity": ["ethnicity", "race"],
    "veteran_status": ["veteran_status"],
    "disability_status": ["disability"],
}


def build_autofill_pack(job_title: str = "", company: str = "", cover_letter: str = "") -> dict:
    """Returns a dict of {standardized_field: value} ready to copy into ATS forms."""
    from config import PROFILE

    name = PROFILE.get("name", "")
    first, _, last = name.partition(" ")
    location = PROFILE.get("location", "")

    return {
        "first_name": first,
        "last_name": last or first,
        "full_name": name,
        "email": PROFILE.get("email", ""),
        "phone": PROFILE.get("phone", ""),
        "location": location.split(",")[0].strip() or location,
        "city": location.split(",")[0].strip() or location,
        "country": os.getenv("CANDIDATE_COUNTRY", "India"),
        "linkedin": f"https://{PROFILE.get('linkedin', '')}" if PROFILE.get("linkedin") else "",
        "github": f"https://{PROFILE.get('github', '')}" if PROFILE.get("github") else "",
        "website": os.getenv("CANDIDATE_WEBSITE", ""),
        "current_company": os.getenv("CANDIDATE_CURRENT_COMPANY", ""),
        "current_title": os.getenv("CANDIDATE_CURRENT_TITLE", "Developer"),
        "years_experience": str(PROFILE.get("experience_years", 1.5)),
        "salary_expectation": f"{PROFILE.get('min_salary_inr', 500000) // 100000}-{(PROFILE.get('min_salary_inr', 500000) // 100000) + 3} LPA",
        "notice_period_days": os.getenv("CANDIDATE_NOTICE_PERIOD_DAYS", "30"),
        "willing_to_relocate": os.getenv("CANDIDATE_RELOCATE", "No"),
        "work_authorization": os.getenv("CANDIDATE_WORK_AUTH", ""),
        "require_sponsorship": os.getenv("CANDIDATE_NEEDS_SPONSORSHIP", "No"),
        "cover_letter": cover_letter or "",
        "why_company": f"I'm interested in {company} because of your work and team culture." if company else "",
        "how_did_you_hear": "Online job board",
        "gender": "Prefer not to say",
        "ethnicity": "Prefer not to say",
        "veteran_status": "Not a veteran",
        "disability_status": "Prefer not to say",
    }


def generate_browser_bookmark_js(values: dict) -> str:
    """
    Generates a 'javascript:' bookmarklet that auto-fills any form on the current page.
    User saves as bookmark, clicks it on an application form — fills all fields.
    """
    js_values = json.dumps(values).replace("'", "\\'")
    js = f"""javascript:(function(){{
    var d={js_values};
    var maps={json.dumps(_FIELD_MAP)};
    function fillField(el,val){{
      if(!el||!val)return;
      el.value=val;
      el.dispatchEvent(new Event('input',{{bubbles:true}}));
      el.dispatchEvent(new Event('change',{{bubbles:true}}));
    }}
    Object.keys(d).forEach(function(k){{
      var patterns=maps[k]||[k];
      patterns.forEach(function(p){{
        document.querySelectorAll('input,textarea,select').forEach(function(el){{
          var name=(el.name||'')+' '+(el.id||'')+' '+(el.placeholder||'')+' '+(el.getAttribute('aria-label')||'');
          if(name.toLowerCase().includes(p.toLowerCase())){{
            fillField(el,d[k]);
          }}
        }});
      }});
    }});
    alert('GetAJob: Filled '+Object.keys(d).length+' fields');
  }})();"""
    return " ".join(js.split())
