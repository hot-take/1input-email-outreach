import html

def generate_outreach_email(first_name: str, company_name: str, job_title: str, seed_domain: str) -> tuple:
    """
    Generates a personalized subject line and HTML body for the outreach campaign.
    Returns: (subject, html_content)
    """
    # Clean and escape inputs to prevent HTML issues
    first_name = html.escape(first_name.capitalize() if first_name else "there")
    company_name = html.escape(company_name)
    job_title = html.escape(job_title.lower() if job_title else "leader")
    seed_domain = html.escape(seed_domain)
    
    # Sharp, highly personalized subject line
    subject = f"Quick question regarding B2B outreach at {company_name}"
    
    # Elegant, premium CSS styled HTML content
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #333333;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 24px;
            background-color: #ffffff;
        }}
        .header {{
            border-bottom: 2px solid #5C63E0;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .header h2 {{
            color: #1a1a1a;
            margin: 0;
            font-size: 20px;
        }}
        .content p {{
            font-size: 15px;
            margin-bottom: 18px;
        }}
        .highlight {{
            color: #5C63E0;
            font-weight: 600;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #e0e0e0;
            font-size: 13px;
            color: #666666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Vocallabs Sales Intelligence Pipeline</h2>
        </div>
        <div class="content">
            <p>Hi {first_name},</p>
            
            <p>I was reviewing growth and scale patterns of leading companies in your sector and noticed that <span class="highlight">{company_name}</span> shares several strong B2B firmographic signals with <span class="highlight">{seed_domain}</span>.</p>
            
            <p>Given your focus as the <strong>{job_title}</strong> at {company_name}, I wanted to share how we recently built an automated customer-acquisition engine that maps out exact lookalikes, pulls key decision-maker links, verifies their direct work emails, and reaches out completely hands-off.</p>
            
            <p>We built this exact pipeline using <em>Ocean.io</em> and <em>Prospeo</em> to automate the exact workflow that sales teams spend hours on manually.</p>
            
            <p>I would love to show you a quick 2-minute live demo of how we can scale lookalike outreach for {company_name} to double your outbound response rate. Are you open to a brief conversation sometime next week?</p>
            
            <p>Best regards,</p>
            <p><strong>DRNZ</strong><br>
            <span style="font-size: 12px; color: #888888;">Automated Sales Infrastructure</span></p>
        </div>
        <div class="footer">
            This is an automated, personalized cold outreach demo sent via the DRNZ SDE outreach pipeline.
        </div>
    </div>
</body>
</html>
"""
    return subject, html_content
