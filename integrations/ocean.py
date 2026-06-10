import logging
from integrations.base import BaseClient
from config.settings import settings

logger = logging.getLogger("outreach_pipeline")

class OceanClient(BaseClient):
    """Client for Ocean.io to search for lookalike companies."""
    
    def __init__(self):
        super().__init__(settings.OCEAN_API_URL, settings.OCEAN_API_KEY)

    def find_lookalikes(self, seed_domain: str) -> list:
        """Find lookalike company domains for a given seed domain."""
        seed_domain = seed_domain.strip().lower()
        
        if settings.is_dry_run:
            logger.info(f"[Mock] Finding lookalikes for seed: {seed_domain}")
            # Generate mock lookalikes based on common domains
            clean_name = seed_domain.split(".")[0]
            mock_data = {
                "stripe": ["adyen.com", "checkout.com", "paddle.com", "gocardless.com"],
                "hubspot": ["salesforce.com", "pipedrive.com", "zoho.com", "activecampaign.com"],
                "slack": ["zoom.us", "discord.com", "microsoft.com", "mattermost.com"],
                "vocallabs": ["ocean.io", "prospeo.io", "eazyreach.app", "hunter.io"],
                "google": ["microsoft.com", "apple.com", "meta.com", "amazon.com"]
            }
            # Fallback for other domains
            return mock_data.get(
                clean_name, 
                [f"competitor-of-{clean_name}1.com", f"competitor-of-{clean_name}2.com", f"similar-{clean_name}.io"]
            )

        logger.info(f"Querying Ocean.io lookalikes for domain: {seed_domain}...")
        headers = {
            "X-Api-Token": self.api_key,
            "x-api-key": self.api_key  # Standard headers
        }
        
        # Payload according to Ocean.io API v3 standards for finding lookalikes
        payload = {
            "companiesFilters": {
                "lookalike_domains": [seed_domain]
            },
            "size": 5
        }
        
        try:
            # Send search query to Ocean.io v3 search endpoint
            response = self._send_request(
                method="POST",
                path="/search/companies",
                headers=headers,
                json_data=payload
            )
            
            domains = []
            if isinstance(response, dict):
                companies = response.get("companies", response.get("data", response.get("results", [])))
                for company in companies:
                    if isinstance(company, dict):
                        # The domain is typically nested under a 'company' key in v3 search responses, 
                        # but we check both formats for robustness.
                        inner_company = company.get("company")
                        if isinstance(inner_company, dict):
                            domain = inner_company.get("domain") or inner_company.get("website")
                        else:
                            domain = company.get("domain") or company.get("website")
                        
                        if domain:
                            domains.append(domain)
                    elif isinstance(company, str):
                        domains.append(company)
            
            return list(set(domains)) if domains else []
            
        except Exception as e:
            logger.error(f"Failed to fetch lookalikes from Ocean.io: {e}")
            # Raise exception so orchestrator knows this stage failed
            raise e
