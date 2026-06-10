import logging
from config.settings import settings
from integrations.ocean import OceanClient
from integrations.prospeo import ProspeoClient
from integrations.brevo import BrevoClient
from core.history import HistoryManager
from templates.outreach import generate_outreach_email

logger = logging.getLogger("outreach_pipeline")

class OutreachPipeline:
    """Orchestrates the 4-stage outreach pipeline: Sourcing -> Prospecting -> Email Resolution (Prospeo) -> Sending."""
    
    def __init__(self):
        self.ocean_client = OceanClient()
        self.prospeo_client = ProspeoClient()
        self.brevo_client = BrevoClient()
        self.history = HistoryManager()

    def run_lookup_and_enrichment(self, seed_domain: str) -> list:
        """
        Execures the first 3 stages of the pipeline:
        1. Find lookalike domains via Ocean.io.
        2. Find C-suite/VP decision-makers via Prospeo.
        3. Resolve LinkedIn profiles to verified emails via Prospeo.
        4. Draft the personalized outreach emails.
        
        Returns a list of drafted outreach dictionaries ready for confirmation.
        """
        logger.info(f"Starting lookup and enrichment stages for seed domain: {seed_domain}")
        
        # 1. Get lookalike company domains
        try:
            lookalike_domains = self.ocean_client.find_lookalikes(seed_domain)
        except Exception as e:
            logger.error(f"Critical error in Stage 1 (Ocean.io): {e}. Pipeline aborted.")
            return []
            
        if not lookalike_domains:
            logger.warning("Ocean.io returned zero lookalike domains. Pipeline stopping.")
            return []

        logger.info(f"Retrieved {len(lookalike_domains)} lookalike company domains: {', '.join(lookalike_domains)}")
        
        pending_campaigns = []

        # 2. Iterate through each lookalike domain
        for domain in lookalike_domains:
            # Check domain de-duplication rule (e.g., contacted within last 30 days) (skip for dry runs)
            if not settings.is_dry_run and self.history.has_contacted_domain_recently(domain):
                logger.info(f"Skipping domain '{domain}': Already contacted in the last 30 days.")
                continue

            # Get decision makers
            try:
                prospects = self.prospeo_client.find_decision_makers(domain)
            except Exception as e:
                logger.error(f"Error querying decision-makers for {domain} (Prospeo): {e}. Skipping company.")
                continue

            if not prospects:
                logger.warning(f"No decision makers found with LinkedIn profiles for {domain}. Skipping.")
                continue

            # Limit prospects to avoid rate limit / credit exhaustion
            prospects_to_enrich = prospects[:settings.MAX_PROSPECTS_PER_COMPANY]

            # 3. Enrich prospects (LinkedIn -> Verified Email)
            for prospect in prospects_to_enrich:
                linkedin_url = prospect["linkedin_url"]
                first_name = prospect["first_name"]
                last_name = prospect["last_name"]
                name = prospect["name"]
                job_title = prospect["job_title"]
                
                # Check email/prospect de-duplication (never mail same person twice)
                # Note: We don't have the email yet, but we'll check it right after resolving.
                
                logger.info(f"Resolving contact email for {name} ({job_title}) via Prospeo...")
                try:
                    email = self.prospeo_client.enrich_person(
                        linkedin_url=linkedin_url,
                        first_name=first_name,
                        last_name=last_name,
                        domain=domain
                    )
                except Exception as e:
                    logger.error(f"Error resolving email for {name} via Prospeo: {e}. Skipping prospect.")
                    continue

                if not email:
                    logger.warning(f"Could not resolve email for {name} ({linkedin_url}). Skipping.")
                    continue

                # Now check if email has been contacted previously (skip for dry runs)
                if not settings.is_dry_run and self.history.has_contacted_email(email):
                    logger.info(f"Skipping contact '{email}': Email already exists in outreach history.")
                    continue

                # 4. Generate personalized outreach subject & HTML body
                subject, html_content = generate_outreach_email(
                    first_name=first_name,
                    company_name=prospect["company_name"],
                    job_title=job_title,
                    seed_domain=seed_domain
                )

                # Queue the draft
                pending_campaigns.append({
                    "domain": domain,
                    "company_name": prospect["company_name"],
                    "name": name,
                    "first_name": first_name,
                    "last_name": last_name,
                    "job_title": job_title,
                    "email": email,
                    "linkedin_url": linkedin_url,
                    "subject": subject,
                    "html_content": html_content
                })
                
        return pending_campaigns

    def execute_sends(self, campaigns: list) -> dict:
        """
        Executes Stage 4 of the pipeline (Brevo Email Sending) for the confirmed campaigns.
        Records status (success/failure) in the local history database.
        Returns a dict summarizing results.
        """
        logger.info(f"Executing email sends for {len(campaigns)} campaigns...")
        
        results = {
            "total": len(campaigns),
            "sent": 0,
            "failed": 0
        }

        for camp in campaigns:
            email = camp["email"]
            name = camp["name"]
            domain = camp["domain"]
            subject = camp["subject"]
            html_content = camp["html_content"]
            
            # Re-check de-duplication database right before sending to prevent race conditions
            if self.history.has_contacted_email(email):
                logger.warning(f"Double-check fail: {email} was already contacted during this run. Skipping.")
                results["failed"] += 1
                continue

            try:
                # Send email via Brevo
                message_id = self.brevo_client.send_email(
                    to_email=email,
                    to_name=name,
                    subject=subject,
                    html_content=html_content
                )
                
                # Record success
                self.history.record_outreach(
                    domain=domain,
                    email=email,
                    first_name=camp["first_name"],
                    last_name=camp["last_name"],
                    job_title=camp["job_title"],
                    status="success",
                    message_id=message_id
                )
                results["sent"] += 1
                
            except Exception as e:
                logger.error(f"Failed to execute outreach for {name} ({email}): {e}")
                # Record failure so we can debug later
                self.history.record_outreach(
                    domain=domain,
                    email=email,
                    first_name=camp["first_name"],
                    last_name=camp["last_name"],
                    job_title=camp["job_title"],
                    status=f"failed: {str(e)}"
                )
                results["failed"] += 1
                
        return results
