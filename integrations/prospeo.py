import logging
import time
from integrations.base import BaseClient
from config.settings import settings

logger = logging.getLogger("outreach_pipeline")

class ProspeoClient(BaseClient):
    """Client for Prospeo.io to find decision makers (C-level/VP) by domain."""
    
    def __init__(self):
        super().__init__(settings.PROSPEO_API_URL, settings.PROSPEO_API_KEY)

    def find_decision_makers(self, domain: str) -> list:
        """
        Find decision-makers (C-suite and VP-level) and their LinkedIn profiles for a domain.
        Returns a list of dictionaries with: name, job_title, linkedin_url.
        """
        domain = domain.strip().lower()
        
        if settings.is_dry_run:
            logger.info(f"[Mock] Finding decision-makers for domain: {domain}")
            # Generate mock decision makers
            company_name = domain.split(".")[0].capitalize()
            return [
                {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "name": "Jane Doe",
                    "job_title": "CEO & Co-Founder",
                    "linkedin_url": f"https://www.linkedin.com/in/jane-doe-{domain.split('.')[0]}",
                    "company_domain": domain,
                    "company_name": company_name
                },
                {
                    "first_name": "John",
                    "last_name": "Smith",
                    "name": "John Smith",
                    "job_title": "VP of Sales & Growth",
                    "linkedin_url": f"https://www.linkedin.com/in/john-smith-{domain.split('.')[0]}",
                    "company_domain": domain,
                    "company_name": company_name
                }
            ]

        logger.info(f"Searching Prospeo for decision-makers at domain: {domain}...")
        headers = {
            "X-KEY": self.api_key
        }
        
        # We target C-level, VP, and Director seniorities for decision makers
        payload = {
            "filters": {
                "company": {
                    "websites": {
                        "include": [domain]
                    }
                },
                "person_seniority": {
                    "include": ["C-Suite", "Vice President", "Director"]
                }
            },
            "page": 1
        }
        
        try:
            # Pacing sleep to stay within Prospeo rate limits
            time.sleep(2)
            # POST /search-person
            response = self._send_request(
                method="POST",
                path="/search-person",
                headers=headers,
                json_data=payload
            )
            
            results = response.get("results", [])
            prospects = []
            
            for item in results:
                # Extract contact details
                person = item.get("person", {})
                first_name = person.get("first_name", "")
                last_name = person.get("last_name", "")
                name = person.get("name", f"{first_name} {last_name}".strip())
                job_title = person.get("job_title", "")
                linkedin_url = person.get("linkedin_url")
                
                # We need LinkedIn URL for the email enrichment stage
                if linkedin_url:
                    prospects.append({
                        "first_name": first_name,
                        "last_name": last_name,
                        "name": name,
                        "job_title": job_title,
                        "linkedin_url": linkedin_url,
                        "company_domain": domain,
                        "company_name": domain.split(".")[0].capitalize()
                    })
            
            # Fallback to domain search if search-person returned no results
            if not prospects:
                logger.info(f"No results from /search-person. Trying /domain-search fallback for {domain}...")
                response_ds = self._send_request(
                    method="POST",
                    path="/domain-search",
                    headers=headers,
                    json_data={"domain": domain}
                )
                
                email_list = response_ds.get("email_list", [])
                for item in email_list:
                    linkedin_url = item.get("linkedin")
                    if linkedin_url:
                        name = item.get("name", "")
                        parts = name.split(" ")
                        first_name = parts[0] if parts else ""
                        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                        prospects.append({
                            "first_name": first_name,
                            "last_name": last_name,
                            "name": name,
                            "job_title": item.get("title", "Executive"),
                            "linkedin_url": linkedin_url,
                            "company_domain": domain,
                            "company_name": domain.split(".")[0].capitalize()
                        })
            
            logger.info(f"Found {len(prospects)} decision-maker(s) with LinkedIn profiles for {domain}.")
            return prospects
            
        except Exception as e:
            logger.error(f"Failed to fetch decision-makers from Prospeo: {e}")
            raise e

    def enrich_person(self, linkedin_url: str, first_name: str = "", last_name: str = "", domain: str = "") -> str:
        """
        Enrich a contact via Prospeo's /enrich-person endpoint using their LinkedIn URL.
        Returns the resolved verified email address, or an empty string on failure.
        """
        linkedin_url = linkedin_url.strip()
        first_name = first_name.strip().lower()
        last_name = last_name.strip().lower()
        domain = domain.strip().lower()

        if settings.is_dry_run:
            logger.info(f"[Mock] Resolving LinkedIn URL via Prospeo enrichment: {linkedin_url}")
            if first_name and domain:
                return f"{first_name}@{domain}"
            elif last_name and domain:
                return f"{last_name}@{domain}"
            elif domain:
                return f"contact@{domain}"
            else:
                return "prospect@example.com"

        logger.info(f"Enriching LinkedIn profile via Prospeo for URL: {linkedin_url}...")
        headers = {
            "X-KEY": self.api_key
        }
        
        payload = {
            "data": {
                "linkedin_url": linkedin_url
            }
        }
        
        try:
            # Pacing sleep to stay within Prospeo rate limits
            time.sleep(2)
            response = self._send_request(
                method="POST",
                path="/enrich-person",
                headers=headers,
                json_data=payload
            )
            
            email = None
            if isinstance(response, dict):
                person = response.get("person", {})
                if isinstance(person, dict):
                    email_field = person.get("email")
                    if isinstance(email_field, dict):
                        email = email_field.get("email")
                    elif isinstance(email_field, str):
                        email = email_field
            
            if email and isinstance(email, str):
                logger.info(f"Successfully enriched and resolved email: {email}")
                return email.strip()
            else:
                logger.warning(f"Prospeo enrichment did not return an email for LinkedIn URL: {linkedin_url}")
                return ""
                
        except Exception as e:
            logger.error(f"Failed to enrich person via Prospeo: {e}")
            return ""
