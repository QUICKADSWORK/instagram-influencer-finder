"""
SQLite Database Module for Instagram Influencer Finder
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

# Use /data directory for Render persistent disk, fallback to local
DATA_DIR = "/data" if os.path.exists("/data") else "."
DATABASE_PATH = os.path.join(DATA_DIR, "influencers.db")


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Influencers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS influencers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_profile_id TEXT UNIQUE,
                username TEXT NOT NULL,
                profile_link TEXT,
                estimated_followers TEXT,
                profile_description TEXT,
                content_focus TEXT,
                suggested_hashtags TEXT,
                open_to_collaborations TEXT,
                country TEXT,
                niche TEXT,
                discovery_date TEXT,
                status TEXT DEFAULT 'New',
                source TEXT DEFAULT 'ai_suggestion',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: add source column if missing
        try:
            cursor.execute("ALTER TABLE influencers ADD COLUMN source TEXT DEFAULT 'ai_suggestion'")
        except:
            pass
        
        # Search history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                min_followers INTEGER,
                max_followers INTEGER,
                country TEXT,
                results_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()


def add_influencer(influencer: Dict) -> bool:
    """Add a new influencer to the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO influencers 
                (unique_profile_id, username, profile_link, estimated_followers, 
                 profile_description, content_focus, suggested_hashtags, 
                 open_to_collaborations, country, niche, discovery_date, status, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                influencer.get('unique_profile_id', ''),
                influencer.get('username', ''),
                influencer.get('profile_link', ''),
                str(influencer.get('estimated_followers', '')),
                influencer.get('profile_description', ''),
                influencer.get('content_focus', ''),
                influencer.get('suggested_hashtags', ''),
                influencer.get('open_to_collaborations', 'No'),
                influencer.get('country', ''),
                influencer.get('niche', ''),
                influencer.get('discovery_date', datetime.now().strftime('%Y-%m-%d')),
                influencer.get('status', 'New'),
                influencer.get('source', 'ai_suggestion')
            ))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False


def add_search_history(keyword: str, min_followers: int, max_followers: int, 
                       country: str, results_count: int) -> int:
    """Add a search to history and return the search ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO search_history (keyword, min_followers, max_followers, country, results_count)
            VALUES (?, ?, ?, ?, ?)
        """, (keyword, min_followers, max_followers, country, results_count))
        conn.commit()
        return cursor.lastrowid


def get_all_influencers(
    country: Optional[str] = None,
    niche: Optional[str] = None,
    min_followers: Optional[int] = None,
    max_followers: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """Get all influencers with optional filters."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM influencers WHERE 1=1"
        params = []
        
        if country:
            query += " AND country = ?"
            params.append(country)
        
        if niche:
            query += " AND niche LIKE ?"
            params.append(f"%{niche}%")
        
        if status:
            query += " AND status = ?"
            params.append(status)

        # Follower filter - estimated_followers stored as text, cast to int
        if min_followers and min_followers > 0:
            query += " AND CAST(REPLACE(estimated_followers, ',', '') AS INTEGER) >= ?"
            params.append(min_followers)

        if max_followers and max_followers > 0:
            query += " AND CAST(REPLACE(estimated_followers, ',', '') AS INTEGER) <= ?"
            params.append(max_followers)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_influencer_count(
    country: Optional[str] = None,
    niche: Optional[str] = None,
    status: Optional[str] = None
) -> int:
    """Get total count of influencers with optional filters."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = "SELECT COUNT(*) FROM influencers WHERE 1=1"
        params = []
        
        if country:
            query += " AND country = ?"
            params.append(country)
        
        if niche:
            query += " AND niche LIKE ?"
            params.append(f"%{niche}%")
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        cursor.execute(query, params)
        return cursor.fetchone()[0]


def get_search_history(limit: int = 20) -> List[Dict]:
    """Get recent search history."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM search_history 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_unique_countries() -> List[str]:
    """Get list of unique countries."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT country FROM influencers WHERE country != '' ORDER BY country")
        return [row[0] for row in cursor.fetchall()]


def get_unique_niches() -> List[str]:
    """Get list of unique niches."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT niche FROM influencers WHERE niche != '' ORDER BY niche")
        return [row[0] for row in cursor.fetchall()]


def update_influencer_status(profile_id: str, status: str) -> bool:
    """Update influencer status."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE influencers SET status = ? WHERE unique_profile_id = ?
        """, (status, profile_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_influencer(profile_id: str) -> bool:
    """Delete an influencer."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM influencers WHERE unique_profile_id = ?", (profile_id,))
        conn.commit()
        return cursor.rowcount > 0


def clear_all_influencers() -> int:
    """Clear all influencers from the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM influencers")
        count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM influencers")
        conn.commit()
        return count


def get_stats() -> Dict:
    """Get database statistics."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM influencers")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM influencers WHERE status = 'New'")
        new_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM influencers WHERE status = 'Contacted'")
        contacted = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM influencers WHERE open_to_collaborations = 'Yes'")
        open_collab = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT country) FROM influencers")
        countries = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT niche) FROM influencers")
        niches = cursor.fetchone()[0]
        
        return {
            "total_influencers": total,
            "new": new_count,
            "contacted": contacted,
            "open_to_collaborations": open_collab,
            "countries": countries,
            "niches": niches
        }
