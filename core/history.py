import sqlite3
import datetime
import logging
from config.settings import settings

logger = logging.getLogger("outreach_pipeline")

class HistoryManager:
    """Manages local SQLite database to track outreach history and prevent double contacting."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DB_PATH
        self._init_db()

    def _get_connection(self):
        """Returns a connection to the SQLite database."""
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initializes the database schema if it doesn't exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Create history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS outreach_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        domain TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE,
                        first_name TEXT,
                        last_name TEXT,
                        job_title TEXT,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT NOT NULL,
                        message_id TEXT
                    )
                """)
                # Create indexes for speed
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON outreach_history(email)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_domain ON outreach_history(domain)")
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error initializing outreach history database: {e}")
            raise e

    def has_contacted_email(self, email: str) -> bool:
        """Check if an email address has already been successfully contacted."""
        email = email.strip().lower()
        if not email:
            return False
            
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM outreach_history WHERE email = ? AND status = 'success'", (email,))
                result = cursor.fetchone()
                return result is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking email history: {e}")
            return False

    def has_contacted_domain_recently(self, domain: str, days: int = 30) -> bool:
        """
        Check if we have successfully contacted this company domain in the last N days.
        Prevents spamming multiple people at the same company in close succession.
        """
        domain = domain.strip().lower()
        if not domain:
            return False
            
        # Calculate date threshold
        threshold_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM outreach_history WHERE domain = ? AND sent_at >= ? AND status = 'success'", 
                    (domain, threshold_date)
                )
                result = cursor.fetchone()
                return result is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking domain history: {e}")
            return False

    def record_outreach(self, domain: str, email: str, first_name: str, last_name: str, job_title: str, status: str, message_id: str = None):
        """Record a sent email attempt in the database."""
        domain = domain.strip().lower()
        email = email.strip().lower()
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO outreach_history 
                    (domain, email, first_name, last_name, job_title, sent_at, status, message_id)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
                    """,
                    (domain, email, first_name, last_name, job_title, status, message_id)
                )
                conn.commit()
                logger.debug(f"Recorded outreach to {email} in database with status {status}")
        except sqlite3.Error as e:
            logger.error(f"Error recording outreach history: {e}")
            # Do not crash if DB writing fails, but log it
