"""
AI Service Module - Uses Google Custom Search + Claude for influencer discovery.

Strategy:
1. Google Custom Search finds REAL Instagram profiles (primary)
2. Claude enriches the real data with descriptions and analysis
3. Falls back to Claude-only if Google search is not configured
"""
import os
import json
import re
import random
import string
import requests
from typing import List, Dict, Optional
from datetime import datetime
import anthropic
from dotenv import load_dotenv

load_dotenv()


def get_client():
    """Get Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_anthropic_api_key_here":
        print("WARNING: ANTHROPIC_API_KEY not set")
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        print(f"ERROR creating Anthropic client: {e}")
        return None


def _random_id(keyword: str) -> str:
    """Generate a unique profile ID."""
    slug = keyword.lower().replace(' ', '_')[:20]
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{slug}_{datetime.now().strftime('%Y%m%d')}_{rand}"


# ============================================================
# GOOGLE CUSTOM SEARCH - FINDS REAL PROFILES
# ============================================================

def _google_search_available() -> bool:
    """Check if Google Custom Search is configured."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("YOUTUBE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    return bool(api_key and cse_id)


def _search_google(query: str, num: int = 10) -> List[Dict]:
    """Run a Google Custom Search query."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("YOUTUBE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        return []

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": api_key, "cx": cse_id, "q": query, "num": min(num, 10)},
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json().get("items", [])
        else:
            print(f"Google Search error {resp.status_code}: {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"Google Search exception: {e}")
        return []


SKIP_USERNAMES = {
    'p', 'explore', 'accounts', 'reel', 'reels', 'stories',
    'tags', 'about', 'directory', 'developer', 'legal', 'tv',
}


def _extract_instagram_profiles(items: List[Dict]) -> List[Dict]:
    """Extract Instagram usernames and info from Google search results."""
    profiles = []
    seen = set()

    for item in items:
        link = item.get("link", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")

        match = re.match(r'https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?', link)
        if not match:
            continue

        username = match.group(1).lower()
        if username in SKIP_USERNAMES or username in seen:
            continue

        seen.add(username)

        # Try to extract follower info from snippet
        follower_match = re.search(r'([\d,.]+[KkMm]?)\s*[Ff]ollowers', snippet)
        followers_str = follower_match.group(1) if follower_match else ""

        # Clean title (often "Username (@handle) • Instagram photos and videos")
        clean_title = re.sub(r'\s*[•·|]\s*Instagram.*', '', title).strip()
        clean_title = re.sub(r'\s*\(@[^)]+\)', '', clean_title).strip()

        profiles.append({
            "username": username,
            "profile_link": f"https://instagram.com/{username}",
            "display_name": clean_title or username,
            "snippet": snippet[:200],
            "followers_hint": followers_str,
        })

    return profiles


def _search_real_profiles(keyword: str, country: str, quantity: int,
                          min_followers: int = 0, max_followers: int = 0) -> List[Dict]:
    """Search Google for real Instagram profiles matching the criteria."""
    all_profiles = []
    seen_usernames = set()

    # Country-specific terms to improve search accuracy
    country_terms = {
        "USA": "USA OR \"United States\"",
        "India": "India OR Indian",
        "UK": "UK OR Britain OR British",
        "Australia": "Australia OR Australian",
        "Canada": "Canada OR Canadian",
    }
    country_q = country_terms.get(country, country)

    # Follower range label for search
    follower_label = ""
    if max_followers > 0 and max_followers <= 10000:
        follower_label = "nano influencer"
    elif max_followers > 0 and max_followers <= 100000:
        follower_label = "micro influencer"
    elif max_followers > 0 and max_followers <= 500000:
        follower_label = "mid-tier influencer"
    elif min_followers >= 500000:
        follower_label = "macro influencer"

    # Use varied search strategies to find more diverse real profiles
    search_queries = [
        # Direct instagram profile searches
        f'site:instagram.com {keyword} {country_q}',
        f'site:instagram.com "{keyword}" bio {country_q}',
        # Listicle and directory searches (these often have real verified handles)
        f'top {keyword} instagram influencers {country} "@"',
        f'best {keyword} instagram accounts {country} handles',
        f'{follower_label} {keyword} instagram {country}' if follower_label else f'{keyword} instagram creator {country}',
        # Niche-specific
        f'"{keyword}" instagram creator {country_q} followers',
        f'{keyword} content creator instagram {country}',
    ]

    for query in search_queries:
        if len(all_profiles) >= quantity + 5:
            break

        items = _search_google(query, num=10)
        profiles = _extract_instagram_profiles(items)

        for p in profiles:
            if p["username"] not in seen_usernames:
                seen_usernames.add(p["username"])
                all_profiles.append(p)

    return all_profiles[:quantity + 10]  # Extra buffer for filtering


def _enrich_with_ai(raw_profiles: List[Dict], keyword: str, country: str,
                    min_followers: int, max_followers: int) -> List[Dict]:
    """Use Claude to enrich real profiles, verify niche match, and filter by follower range."""
    client = get_client()
    if not client or not raw_profiles:
        return _format_raw_profiles(raw_profiles, keyword, country)

    profiles_text = "\n".join([
        f"- @{p['username']} | Name: {p['display_name']} | Snippet: {p['snippet']} | Followers hint: {p['followers_hint']}"
        for p in raw_profiles
    ])

    follower_range_str = f"{min_followers:,} - {max_followers:,}" if max_followers > 0 else f"{min_followers:,}+"

    prompt = f"""I found these Instagram profiles from Google search. I need you to:
1. Check if each profile is relevant to the "{keyword}" niche
2. Estimate their follower count
3. SKIP profiles that are NOT related to "{keyword}" niche (set relevant: false)
4. SKIP profiles whose estimated followers are outside {follower_range_str}

TARGET: "{keyword}" creators in {country} with {follower_range_str} followers

PROFILES TO ANALYZE:
{profiles_text}

For each profile return:
- username (exact same)
- relevant (true/false - is this actually a {keyword} creator?)
- estimated_followers (best estimate as number)
- in_range (true if followers within {follower_range_str}, false if way off)
- profile_description (short bio)
- content_focus (their specific content type)
- suggested_hashtags (array of 3-5 hashtags)
- open_to_collaborations (true/false)

IMPORTANT: Only mark relevant=true if profile genuinely relates to "{keyword}".
If a profile seems like a business page, spam, or unrelated niche - mark relevant=false.

Return ONLY JSON array, no markdown:
[{{"username": "...", "relevant": true, "estimated_followers": 50000, "in_range": true, "profile_description": "...", "content_focus": "...", "suggested_hashtags": ["tag1"], "open_to_collaborations": true}}]
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )

        text = message.content[0].text
        text = re.sub(r'```json\n?', '', text)
        text = re.sub(r'```\n?', '', text)
        enriched = json.loads(text.strip())

        enriched_map = {e['username'].lower(): e for e in enriched}

        result = []
        for raw in raw_profiles:
            username = raw['username'].lower()
            e = enriched_map.get(username, {})

            # Skip irrelevant profiles
            if not e.get('relevant', True):
                print(f"  Skipping @{username} - not relevant to '{keyword}'")
                continue

            # Skip profiles way outside follower range
            if not e.get('in_range', True) and max_followers > 0:
                print(f"  Skipping @{username} - followers outside range")
                continue

            followers = e.get('estimated_followers', 0)
            if not followers and raw.get('followers_hint'):
                followers = _parse_follower_hint(raw['followers_hint'])

            hashtags = e.get('suggested_hashtags', [])
            if isinstance(hashtags, list):
                hashtags = ', '.join(hashtags)

            collab = e.get('open_to_collaborations', True)
            if isinstance(collab, bool):
                collab = 'Yes' if collab else 'No'

            result.append({
                'unique_profile_id': _random_id(keyword),
                'username': raw['username'],
                'profile_link': raw['profile_link'],
                'estimated_followers': str(followers or ''),
                'profile_description': e.get('profile_description', raw.get('snippet', '')[:100]),
                'content_focus': e.get('content_focus', keyword),
                'suggested_hashtags': hashtags,
                'open_to_collaborations': collab,
                'country': country,
                'niche': keyword,
                'discovery_date': datetime.now().strftime('%Y-%m-%d'),
                'status': 'New',
                'source': 'google_search',
            })

        print(f"  Enrichment: {len(raw_profiles)} found → {len(result)} relevant and in range")
        return result

    except Exception as e:
        print(f"AI enrichment failed: {e}")
        return _format_raw_profiles(raw_profiles, keyword, country)


def _parse_follower_hint(hint: str) -> int:
    """Parse follower hint strings like '28.3K' or '1.2M'."""
    if not hint:
        return 0
    hint = hint.strip().replace(',', '')
    try:
        if hint.upper().endswith('M'):
            return int(float(hint[:-1]) * 1_000_000)
        elif hint.upper().endswith('K'):
            return int(float(hint[:-1]) * 1_000)
        else:
            return int(float(hint))
    except:
        return 0


def _format_raw_profiles(raw_profiles: List[Dict], keyword: str, country: str) -> List[Dict]:
    """Format raw Google search results without AI enrichment."""
    return [{
        'unique_profile_id': _random_id(keyword),
        'username': p['username'],
        'profile_link': p['profile_link'],
        'estimated_followers': str(_parse_follower_hint(p.get('followers_hint', '')) or ''),
        'profile_description': p.get('snippet', '')[:100],
        'content_focus': keyword,
        'suggested_hashtags': keyword,
        'open_to_collaborations': 'Yes',
        'country': country,
        'niche': keyword,
        'discovery_date': datetime.now().strftime('%Y-%m-%d'),
        'status': 'New',
        'source': 'google_search',
    } for p in raw_profiles]


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def generate_influencers(
    keyword: str,
    min_followers: int,
    max_followers: int,
    country: str,
    quantity: int = 10
) -> List[Dict]:
    """
    Find Instagram influencers.
    Primary: Google Custom Search for real profiles + Claude enrichment.
    Fallback: Claude-only (less accurate).
    """

    # Try Google Search first (real data)
    if _google_search_available():
        print(f"Using Google Search for real Instagram profiles...")
        raw_profiles = _search_real_profiles(keyword, country, quantity,
                                             min_followers, max_followers)

        if raw_profiles:
            print(f"Found {len(raw_profiles)} real profiles, enriching with AI...")
            enriched = _enrich_with_ai(raw_profiles, keyword, country, min_followers, max_followers)
            if enriched:
                return enriched[:quantity]

    # Fallback: Claude-only
    print(f"Using AI-only mode (configure GOOGLE_CSE_ID for real results)...")
    return _generate_ai_only(keyword, min_followers, max_followers, country, quantity)


def _generate_ai_only(keyword: str, min_followers: int, max_followers: int,
                      country: str, quantity: int) -> List[Dict]:
    """Fallback: Claude generates suggestions (less accurate)."""
    client = get_client()
    if not client:
        raise ValueError("No AI client available. Set ANTHROPIC_API_KEY.")

    all_results = []
    remaining = quantity
    seen = []

    while remaining > 0:
        batch = min(remaining, 10)
        exclude = f"\nDO NOT include: {', '.join(seen)}\n" if seen else ""

        prompt = f"""You are an Instagram influencer expert. List {batch} REAL, well-known Instagram creators in the "{keyword}" niche from {country}.

FOLLOWER RANGE: {min_followers:,} - {max_followers:,}
{exclude}
RULES:
- ONLY name creators you are CERTAIN exist on Instagram
- These should be established, recognizable creators in this niche
- Return FEWER results rather than making up fake profiles
- Follower counts are your best estimate

Return JSON array only:
[{{"username": "realhandle", "estimated_followers": 50000, "profile_description": "Bio here", "content_focus": "Their niche", "suggested_hashtags": ["tag1", "tag2"], "open_to_collaborations": true}}]
"""
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )
            text = msg.content[0].text
            text = re.sub(r'```json\n?', '', text)
            text = re.sub(r'```\n?', '', text)
            items = json.loads(text.strip())

            for item in items:
                u = item.get('username', '').lower()
                if u and u not in seen:
                    seen.append(u)

                    hashtags = item.get('suggested_hashtags', [])
                    if isinstance(hashtags, list):
                        hashtags = ', '.join(hashtags)
                    collab = item.get('open_to_collaborations', True)
                    if isinstance(collab, bool):
                        collab = 'Yes' if collab else 'No'

                    all_results.append({
                        'unique_profile_id': _random_id(keyword),
                        'username': item.get('username', ''),
                        'profile_link': f"https://instagram.com/{item.get('username', '')}",
                        'estimated_followers': str(item.get('estimated_followers', '')),
                        'profile_description': item.get('profile_description', ''),
                        'content_focus': item.get('content_focus', keyword),
                        'suggested_hashtags': hashtags,
                        'open_to_collaborations': collab,
                        'country': country,
                        'niche': keyword,
                        'discovery_date': datetime.now().strftime('%Y-%m-%d'),
                        'status': 'New',
                        'source': 'ai_suggestion',
                    })

            remaining -= batch
        except Exception as e:
            print(f"AI batch error: {e}")
            if all_results:
                break
            raise ValueError(f"Error: {e}")

    return all_results[:quantity]


def get_search_mode() -> Dict:
    """Return which search mode is active."""
    if _google_search_available():
        return {"mode": "google_search", "label": "Google Search (Real Profiles)", "accurate": True}
    return {"mode": "ai_only", "label": "AI Suggestions (Setup Google for real results)", "accurate": False}


def validate_api_key() -> bool:
    """Check if the Anthropic API key is valid."""
    try:
        client = get_client()
        if not client:
            return False
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        return True
    except Exception as e:
        print(f"API key validation failed: {e}")
        return False
