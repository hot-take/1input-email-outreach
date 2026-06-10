import os
from pathlib import Path
from dotenv import load_dotenv

# Load from .env file if it exists
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    # Ocean.io config
    OCEAN_API_KEY: str = os.getenv("OCEAN_API_KEY", "")
    OCEAN_API_URL: str = os.getenv("OCEAN_API_URL", "https://api.ocean.io/v3").rstrip("/")

    # Prospeo config
    PROSPEO_API_KEY: str = os.getenv("PROSPEO_API_KEY", "")
    PROSPEO_API_URL: str = os.getenv("PROSPEO_API_URL", "https://api.prospeo.io").rstrip("/")

    # Eazyreach config
    EAZYREACH_API_KEY: str = os.getenv("EAZYREACH_API_KEY", "")
    EAZYREACH_API_URL: str = os.getenv("EAZYREACH_API_URL", "https://api.eazyreach.app").rstrip("/")

    # Brevo config
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    BREVO_SENDER_EMAIL: str = os.getenv("BREVO_SENDER_EMAIL", "sender@yourdomain.com")
    BREVO_SENDER_NAME: str = os.getenv("BREVO_SENDER_NAME", "Your Name")
    BREVO_API_URL: str = os.getenv("BREVO_API_URL", "https://api.brevo.com/v3").rstrip("/")

    # Database
    DB_PATH: str = os.getenv("DB_PATH", "outreach_history.db")

    # Dry Run / Mock Mode
    # If set to true, or if API keys are missing, the pipeline will run in mock mode
    DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")

    # Max contacts to enrich per company to avoid spamming and running out of credits / hitting rate limits
    MAX_PROSPECTS_PER_COMPANY: int = int(os.getenv("MAX_PROSPECTS_PER_COMPANY", "3"))

    @property
    def is_dry_run(self) -> bool:
        # If any of the essential API keys are missing, we run in dry/mock mode to ensure it doesn't crash
        # and displays the full pipeline behavior using realistic generated mock data.
        missing_keys = not (self.OCEAN_API_KEY and self.PROSPEO_API_KEY and self.BREVO_API_KEY)
        return self.DRY_RUN or missing_keys

    def print_status(self):
        """Returns a string description of the environment configuration status."""
        status = []
        if self.is_dry_run:
            status.append("[yellow]Running in DRY_RUN / MOCK mode (No real API calls will be fired).[/yellow]")
            missing = []
            if not self.OCEAN_API_KEY:
                missing.append("OCEAN_API_KEY")
            if not self.PROSPEO_API_KEY:
                missing.append("PROSPEO_API_KEY")
            if not self.BREVO_API_KEY:
                missing.append("BREVO_API_KEY")
            if missing:
                status.append(f"[yellow]Reason: The following API keys are missing from .env: {', '.join(missing)}[/yellow]")
        else:
            status.append("[green]Running in PRODUCTION mode (Real API calls will be fired).[/green]")
        return "\n".join(status)

settings = Settings()
