import os
import unittest
import sqlite3
import tempfile
import datetime
from pathlib import Path

# Adjust path to import from workspace
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.history import HistoryManager
from templates.outreach import generate_outreach_email
from core.pipeline import OutreachPipeline
from config.settings import settings

class TestHistoryManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary database file
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()
        self.history = HistoryManager(db_path=self.temp_db_path)

    def tearDown(self):
        # Close database connections and remove the temp file
        os.close(self.temp_db_fd)
        try:
            os.remove(self.temp_db_path)
        except OSError:
            pass

    def test_record_and_check_email_success(self):
        email = "test@company.com"
        domain = "company.com"
        
        # Initially should be False
        self.assertFalse(self.history.has_contacted_email(email))
        
        # Record successful outreach
        self.history.record_outreach(
            domain=domain,
            email=email,
            first_name="Alice",
            last_name="Smith",
            job_title="VP of Product",
            status="success",
            message_id="msg-123"
        )
        
        # Should now be True
        self.assertTrue(self.history.has_contacted_email(email))

    def test_record_and_check_email_failure_allows_retry(self):
        email = "fail@company.com"
        domain = "company.com"
        
        # Record failed outreach
        self.history.record_outreach(
            domain=domain,
            email=email,
            first_name="Bob",
            last_name="Jones",
            job_title="CEO",
            status="failed: connection timeout",
            message_id=None
        )
        
        # Should be False because we only block successful contacts
        self.assertFalse(self.history.has_contacted_email(email))

    def test_domain_dedup_success(self):
        domain = "target.com"
        email = "contact@target.com"
        
        self.assertFalse(self.history.has_contacted_domain_recently(domain, days=30))
        
        # Record successful outreach
        self.history.record_outreach(
            domain=domain,
            email=email,
            first_name="Jane",
            last_name="Doe",
            job_title="CEO",
            status="success"
        )
        
        # Should be True
        self.assertTrue(self.history.has_contacted_domain_recently(domain, days=30))

    def test_domain_dedup_failure_allows_retry(self):
        domain = "retrytarget.com"
        email = "contact@retrytarget.com"
        
        # Record failed outreach
        self.history.record_outreach(
            domain=domain,
            email=email,
            first_name="Jane",
            last_name="Doe",
            job_title="CEO",
            status="failed: 400 Bad Request"
        )
        
        # Should be False because the attempt was unsuccessful
        self.assertFalse(self.history.has_contacted_domain_recently(domain, days=30))

    def test_domain_dedup_expired_threshold(self):
        domain = "oldcontact.com"
        email = "contact@oldcontact.com"
        
        # Record successful outreach
        self.history.record_outreach(
            domain=domain,
            email=email,
            first_name="John",
            last_name="Doe",
            job_title="Director",
            status="success"
        )
        
        # Force the sent_at time to be 31 days ago
        old_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=31)).strftime('%Y-%m-%d %H:%M:%S')
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE outreach_history SET sent_at = ? WHERE domain = ?", (old_time, domain))
            conn.commit()
            
        # Checking with default 30 days should be False (not contacted recently)
        self.assertFalse(self.history.has_contacted_domain_recently(domain, days=30))
        # Checking with 40 days should be True
        self.assertTrue(self.history.has_contacted_domain_recently(domain, days=40))


class TestEmailTemplates(unittest.TestCase):
    def test_generate_outreach_email(self):
        first_name = "john"
        company_name = "Stripe"
        job_title = "VP of Sales"
        seed_domain = "hubspot.com"
        
        subject, html_content = generate_outreach_email(
            first_name=first_name,
            company_name=company_name,
            job_title=job_title,
            seed_domain=seed_domain
        )
        
        # Subject should be formatted
        self.assertEqual(subject, "Quick question regarding B2B outreach at Stripe")
        
        # HTML body should capitalize first name and contain fields
        self.assertIn("Hi John,", html_content)
        self.assertIn("Stripe", html_content)
        self.assertIn("vp of sales", html_content)
        self.assertIn("hubspot.com", html_content)


class TestPipelineMockMode(unittest.TestCase):
    def test_pipeline_dry_run_flow(self):
        # Force dry run mode in settings
        original_dry_run = settings.DRY_RUN
        settings.DRY_RUN = True
        
        try:
            pipeline = OutreachPipeline()
            # We use a unique seed domain to bypass any existing SQLite database history
            seed = f"test-{int(datetime.datetime.now().timestamp())}.com"
            
            # Run first 3 stages
            campaigns = pipeline.run_lookup_and_enrichment(seed)
            self.assertGreater(len(campaigns), 0)
            
            # Verify structure of campaigns
            for c in campaigns:
                self.assertIn("domain", c)
                self.assertIn("email", c)
                self.assertIn("subject", c)
                self.assertIn("html_content", c)
                self.assertTrue(c["email"].endswith(c["domain"]))
                
            # Execute email sends
            results = pipeline.execute_sends(campaigns)
            self.assertEqual(results["total"], len(campaigns))
            self.assertEqual(results["sent"], len(campaigns))
            self.assertEqual(results["failed"], 0)
            
        finally:
            settings.DRY_RUN = original_dry_run


if __name__ == "__main__":
    unittest.main()
