import sys
import logging
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.prompt import Confirm

from config.settings import settings
from core.pipeline import OutreachPipeline
from templates.outreach import generate_outreach_email

# Set up logging early
log_file = "outreach_pipeline.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Adjust logger so requests/urllib3 noise is reduced
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
# Remove stream handler from root logging to prevent double logs on stdout when we print using rich
logger = logging.getLogger("outreach_pipeline")
logger.handlers = []
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)


console = Console()

def print_banner():
    """Prints a beautiful ASCII art banner for the CLI."""
    banner_text = """
   ____        _                     _      
  / __ \\ _   _| |_ _ __ ___  __ _  _| |__   
 / / _` | | | | __| '__/ _ \\/ _` |/ _` '_ \\ 
| | (_| | |_| | |_| | |  __/ (_| | (_| | | |
 \\ \\__,_|\\__,_|\\__|_|  \\___|\\__,_|\\__,_| |_|
  \\____/                                    
    """
    console.print(Panel(Text(banner_text, style="bold cyan"), subtitle="Zero Humans in the Loop Outreach Pipeline", border_style="cyan"))


@click.command()
@click.argument("seed_domain", type=str)
@click.option("--dry-run/--no-dry-run", default=None, help="Force override dry-run/mock mode.")
@click.option("--dedup-days", default=30, type=int, help="De-duplication window in days (default: 30).")
def main(seed_domain, dry_run, dedup_days):
    """
    Automated Outreach Pipeline CLI.
    
    SEED_DOMAIN is the domain of a company you already know is a strong customer (e.g. stripe.com).
    The pipeline will source lookalike companies, find decision-makers, resolve emails, and send personalized pitches.
    """
    print_banner()
    
    # Apply override for dry-run if specified
    if dry_run is not None:
        settings.DRY_RUN = dry_run
        
    # Print status of environmental variables
    console.print(Panel(settings.print_status(), title="Configuration Status", border_style="yellow" if settings.is_dry_run else "green"))
    
    # Validate input
    if "." not in seed_domain or len(seed_domain) < 4:
        console.print("[red]Error: Invalid seed domain format. Must be a valid company domain (e.g., stripe.com).[/red]")
        sys.exit(1)
        
    pipeline = OutreachPipeline()
    
    # Run Stages 1-3 with visual progress indicators
    pending_campaigns = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console
    ) as progress:
        # Stage 1: Ocean.io Sourcing
        sourcing_task = progress.add_task("[cyan]Stage 1: Sourcing lookalike companies (Ocean.io)...", total=1)
        try:
            lookalikes = pipeline.ocean_client.find_lookalikes(seed_domain)
            progress.update(sourcing_task, completed=1)
            logger.info(f"Sourced lookalikes for {seed_domain}: {lookalikes}")
        except Exception as e:
            progress.update(sourcing_task, description=f"[red]Stage 1 Failed: {str(e)}")
            console.print(f"[red]Error in Stage 1 Sourcing: {e}[/red]")
            sys.exit(1)

        if not lookalikes:
            console.print("[yellow]Ocean.io found no similar domains. Exiting.[/yellow]")
            sys.exit(0)

        # Stage 2 & 3: Prospecting & Email Resolution (Prospeo)
        enrich_task = progress.add_task("[cyan]Stage 2 & 3: Extracting contacts and resolving emails...", total=len(lookalikes))
        
        for idx, domain in enumerate(lookalikes):
            # Check history (skip for dry runs to allow repeated testing)
            if not settings.is_dry_run and pipeline.history.has_contacted_domain_recently(domain, days=dedup_days):
                logger.info(f"Skipping domain '{domain}' (already contacted).")
                progress.update(enrich_task, advance=1, description=f"[yellow]Skipped (Dupe): {domain}")
                continue

            try:
                progress.update(enrich_task, description=f"[cyan]Prospecting: {domain}")
                prospects = pipeline.prospeo_client.find_decision_makers(domain)
                
                # Limit the number of prospects to enrich per company to avoid credit/rate limits
                prospects_to_enrich = prospects[:settings.MAX_PROSPECTS_PER_COMPANY]
                
                for prospect in prospects_to_enrich:
                    progress.update(enrich_task, description=f"[cyan]Resolving Email: {prospect['name']} ({domain})")
                    email = pipeline.prospeo_client.enrich_person(
                        linkedin_url=prospect["linkedin_url"],
                        first_name=prospect["first_name"],
                        last_name=prospect["last_name"],
                        domain=domain
                    )
                    
                    if email and (settings.is_dry_run or not pipeline.history.has_contacted_email(email)):
                        subject, html_content = generate_outreach_email(
                            first_name=prospect["first_name"],
                            company_name=prospect["company_name"],
                            job_title=prospect["job_title"],
                            seed_domain=seed_domain
                        )
                        
                        pending_campaigns.append({
                            "domain": domain,
                            "company_name": prospect["company_name"],
                            "name": prospect["name"],
                            "first_name": prospect["first_name"],
                            "last_name": prospect["last_name"],
                            "job_title": prospect["job_title"],
                            "email": email,
                            "linkedin_url": prospect["linkedin_url"],
                            "subject": subject,
                            "html_content": html_content
                        })
                        logger.info(f"Drafted outreach to {prospect['name']} <{email}> for {domain}")
                        
            except Exception as e:
                logger.error(f"Error enriching domain {domain}: {e}")
                
            progress.update(enrich_task, advance=1, description=f"[cyan]Processed: {domain}")
            
    # Stage 3 Summary & Safety Gate
    if not pending_campaigns:
        console.print("\n[yellow]No new contacts were found or all prospects were skipped due to de-duplication.[/yellow]")
        console.print("[green]Pipeline completed successfully with 0 pending campaigns.[/green]")
        sys.exit(0)

    console.print(f"\n[green]Enrichment completed! Found {len(pending_campaigns)} new qualified lead(s).[/green]")
    
    # Display results table
    table = Table(title="Outreach Verification Summary (Safety Checkpoint)", show_header=True, header_style="bold magenta")
    table.add_column("Company", style="bold")
    table.add_column("Contact Name")
    table.add_column("Job Title")
    table.add_column("Verified Email", style="cyan")
    table.add_column("LinkedIn Profile", style="dim", max_width=40)
    table.add_column("Subject Preview", style="italic green", max_width=35)
    
    for c in pending_campaigns:
        table.add_row(
            c["company_name"],
            c["name"],
            c["job_title"],
            c["email"],
            c["linkedin_url"],
            c["subject"]
        )
        
    console.print(table)
    console.print()

    # Safety Gate Checkpoint Prompt
    confirm = Confirm.ask("[bold yellow]Do you want to send these personalized outreach emails now?[/bold yellow]", default=False)
    
    if not confirm:
        console.print("[yellow]Outreach cancelled by user. No emails were sent.[/yellow]")
        sys.exit(0)
        
    # Stage 4: Send via Brevo
    console.print("\n[cyan]Firing Stage 4: Launching Brevo Cold Outreach Sequence...[/cyan]")
    
    results = {"sent": 0, "failed": 0}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console
    ) as progress:
        sending_task = progress.add_task("[cyan]Sending emails...", total=len(pending_campaigns))
        
        for c in pending_campaigns:
            progress.update(sending_task, description=f"[cyan]Mailing: {c['name']} <{c['email']}>")
            try:
                msg_id = pipeline.brevo_client.send_email(
                    to_email=c["email"],
                    to_name=c["name"],
                    subject=c["subject"],
                    html_content=c["html_content"]
                )
                pipeline.history.record_outreach(
                    domain=c["domain"],
                    email=c["email"],
                    first_name=c["first_name"],
                    last_name=c["last_name"],
                    job_title=c["job_title"],
                    status="success",
                    message_id=msg_id
                )
                results["sent"] += 1
                logger.info(f"Successfully sent email to {c['email']}. Message ID: {msg_id}")
            except Exception as e:
                pipeline.history.record_outreach(
                    domain=c["domain"],
                    email=c["email"],
                    first_name=c["first_name"],
                    last_name=c["last_name"],
                    job_title=c["job_title"],
                    status=f"failed: {str(e)}"
                )
                results["failed"] += 1
                logger.error(f"Failed to send email to {c['email']}: {e}")
                console.print(f"[red]Error sending to {c['email']}: {e}[/red]")
                
            progress.update(sending_task, advance=1)

    # Final Summary Report
    summary_text = f"Total Sourced/Enriched: {len(pending_campaigns)}\nEmails Fired: {results['sent']}\nSends Failed: {results['failed']}"
    console.print(Panel(summary_text, title="Outreach Job Execution Summary", border_style="green" if results["failed"] == 0 else "yellow"))
    console.print(f"[green]Job completed. Logs written to '{log_file}'.[/green]")

if __name__ == "__main__":
    main()
