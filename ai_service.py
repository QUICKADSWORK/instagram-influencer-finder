"""
AI Service Module - Uses Anthropic Claude for influencer discovery
"""
import os
import json
import re
from typing import List, Dict, Optional
from datetime import datetime
import anthropic
from dotenv import load_dotenv

load_dotenv()

BATCH_SIZE = 10


def get_client():
    """Get Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_anthropic_api_key_here":
        raise ValueError("Please set a valid ANTHROPIC_API_KEY in your .env file")
    return anthropic.Anthropic(api_key=api_key)


def _build_prompt(keyword: str, min_followers: int, max_followers: int,
                  country: str, quantity: int, exclude_usernames: List[str] = None) -> str:
    """Build the AI prompt for influencer discovery."""
    
    exclude_block = ""
    if exclude_usernames:
        exclude_block = f"\n\nDO NOT include these usernames (already found): {', '.join(exclude_usernames)}\n"

    return f"""You are an Instagram influencer research assistant. Your job is to suggest REAL Instagram creators that you know exist from your training data.

SEARCH PARAMETERS:
- Niche: {keyword}
- Follower Range: {min_followers:,} - {max_followers:,}
- Country: {country}
- Quantity: {quantity} influencers
{exclude_block}
CRITICAL RULES - READ CAREFULLY:
1. ONLY suggest Instagram accounts you are CONFIDENT actually exist
2. These must be REAL creators you've seen referenced in articles, news, social media discussions, or your training data
3. DO NOT make up or fabricate usernames - every username must be a real Instagram handle you know about
4. If you cannot find enough REAL creators, return fewer results rather than making up fake ones
5. Follower counts should be your best estimate - add a note if you're unsure
6. It's MUCH better to return 5 real creators than 20 fake ones

For each influencer provide:
1. username - their REAL Instagram handle (without @)
2. estimated_followers - your best estimate (mark as approximate)
3. profile_description - what their profile is about
4. content_focus - their specific content niche
5. profile_link - https://instagram.com/username
6. unique_profile_id - format: {keyword.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}_{{random_5chars}}
7. suggested_hashtags - array of 3-5 hashtags they use
8. open_to_collaborations - true if they typically do brand deals
9. confidence - "high" if you're very sure this account exists, "medium" if somewhat sure, "low" if uncertain

IMPORTANT:
- Prefer well-known creators in the {keyword} space from {country}
- Include a mix of micro and macro influencers within the follower range
- If the niche is broad, include diverse sub-niches
- For {country} specifically, think of creators popular in that region

OUTPUT: Return ONLY valid JSON array, no markdown:
[
  {{
    "username": "realcreator",
    "estimated_followers": 50000,
    "profile_description": "Fitness coach | NYC | DM for collabs",
    "content_focus": "Home workouts and nutrition",
    "profile_link": "https://instagram.com/realcreator",
    "unique_profile_id": "fitness_20240115_abc12",
    "suggested_hashtags": ["fitness", "workout", "healthylifestyle"],
    "open_to_collaborations": true,
    "confidence": "high"
  }}
]
"""


def _parse_ai_response(response_text: str, keyword: str, country: str) -> List[Dict]:
    """Parse and clean AI response into influencer list."""
    response_text = re.sub(r'```json\n?', '', response_text)
    response_text = re.sub(r'```\n?', '', response_text)
    response_text = response_text.strip()

    influencers = json.loads(response_text)

    for inf in influencers:
        inf['country'] = country
        inf['niche'] = keyword
        inf['discovery_date'] = datetime.now().strftime('%Y-%m-%d')
        inf['status'] = 'New'

        if isinstance(inf.get('suggested_hashtags'), list):
            inf['suggested_hashtags'] = ', '.join(inf['suggested_hashtags'])

        if isinstance(inf.get('open_to_collaborations'), bool):
            inf['open_to_collaborations'] = 'Yes' if inf['open_to_collaborations'] else 'No'

        confidence = inf.pop('confidence', 'medium')
        follower_note = " (verified)" if confidence == "high" else " (approx)"
        inf['estimated_followers'] = str(inf.get('estimated_followers', ''))

        if not inf.get('profile_link'):
            inf['profile_link'] = f"https://instagram.com/{inf.get('username', '')}"

    return influencers


def generate_influencers(
    keyword: str,
    min_followers: int,
    max_followers: int,
    country: str,
    quantity: int = 10
) -> List[Dict]:
    """
    Use Claude to find real Instagram influencers.
    For quantities > BATCH_SIZE, runs multiple calls to avoid token limits.
    """
    client = get_client()

    all_influencers = []
    remaining = quantity
    seen_usernames = []

    while remaining > 0:
        batch = min(remaining, BATCH_SIZE)

        prompt = _build_prompt(keyword, min_followers, max_followers, country, batch, 
                               exclude_usernames=seen_usernames if seen_usernames else None)

        try:
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            influencers = _parse_ai_response(response_text, keyword, country)

            for inf in influencers:
                username = inf.get('username', '').lower()
                if username and username not in seen_usernames:
                    seen_usernames.append(username)
                    all_influencers.append(inf)

            remaining -= batch

        except json.JSONDecodeError as e:
            print(f"JSON parsing error in batch: {e}")
            if all_influencers:
                break
            raise ValueError(f"Failed to parse AI response: {e}")
        except anthropic.APIError as e:
            print(f"Anthropic API error in batch: {e}")
            if all_influencers:
                break
            raise ValueError(f"AI service error: {e}")
        except Exception as e:
            print(f"Error in batch: {e}")
            if all_influencers:
                break
            raise ValueError(f"Error generating influencers: {e}")

    return all_influencers[:quantity]


def validate_api_key() -> bool:
    """Check if the Anthropic API key is valid."""
    try:
        client = get_client()
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        return True
    except Exception as e:
        print(f"API key validation failed: {e}")
        return False
