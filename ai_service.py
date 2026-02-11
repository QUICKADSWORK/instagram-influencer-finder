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


def get_client():
    """Get Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_anthropic_api_key_here":
        raise ValueError("Please set a valid ANTHROPIC_API_KEY in your .env file")
    return anthropic.Anthropic(api_key=api_key)


def generate_influencers(
    keyword: str,
    min_followers: int,
    max_followers: int,
    country: str,
    quantity: int = 10
) -> List[Dict]:
    """
    Use Claude to generate Instagram influencer suggestions.
    
    Args:
        keyword: Niche/keyword to search for
        min_followers: Minimum follower count
        max_followers: Maximum follower count
        country: Target country/location
        quantity: Number of influencers to generate
    
    Returns:
        List of influencer dictionaries
    """
    client = get_client()
    
    prompt = f"""You are an Instagram influencer discovery assistant specializing in finding real, active creators.

SEARCH PARAMETERS:
- Target Niche/Keyword: {keyword}
- Follower Range: {min_followers:,} - {max_followers:,}
- Location/Country: {country}
- Quantity: {quantity} influencers

YOUR TASK:
Generate a list of {quantity} REALISTIC Instagram influencer profiles in the "{keyword}" niche from {country}.

For each influencer, provide:
1. username (without @ - should be realistic Instagram-style usernames)
2. estimated_followers (number within the specified range, vary across the range)
3. profile_description (brief, realistic bio - 1-2 sentences)
4. content_focus (specific sub-niche or content type they focus on)
5. profile_link (format: https://instagram.com/username)
6. unique_profile_id (generate as: {keyword.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}_{'{random_5chars}'})
7. suggested_hashtags (array of 3-5 relevant hashtags they likely use, without #)
8. open_to_collaborations (boolean - true if they seem open to brand deals based on profile)

CRITICAL REQUIREMENTS:
- All profiles must be UNIQUE - no duplicates
- Usernames should look realistic (mix of names, underscores, numbers)
- Vary follower counts across the entire specified range
- Include diverse content creators within the niche
- Profile descriptions should feel authentic
- Make suggested_hashtags relevant to both the niche and the specific creator

OUTPUT: Return ONLY a valid JSON array with no additional text or markdown. Example format:
[
  {{
    "username": "example_creator",
    "estimated_followers": 50000,
    "profile_description": "Fashion & lifestyle | NYC based",
    "content_focus": "Street style fashion",
    "profile_link": "https://instagram.com/example_creator",
    "unique_profile_id": "fashion_20240115_abc12",
    "suggested_hashtags": ["streetstyle", "nycfashion", "ootd"],
    "open_to_collaborations": true
  }}
]
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the response text
        response_text = message.content[0].text
        
        # Clean up the response - remove any markdown code blocks
        response_text = re.sub(r'```json\n?', '', response_text)
        response_text = re.sub(r'```\n?', '', response_text)
        response_text = response_text.strip()
        
        # Parse JSON
        influencers = json.loads(response_text)
        
        # Add metadata to each influencer
        for inf in influencers:
            inf['country'] = country
            inf['niche'] = keyword
            inf['discovery_date'] = datetime.now().strftime('%Y-%m-%d')
            inf['status'] = 'New'
            
            # Ensure hashtags are a string
            if isinstance(inf.get('suggested_hashtags'), list):
                inf['suggested_hashtags'] = ', '.join(inf['suggested_hashtags'])
            
            # Convert boolean to string for open_to_collaborations
            if isinstance(inf.get('open_to_collaborations'), bool):
                inf['open_to_collaborations'] = 'Yes' if inf['open_to_collaborations'] else 'No'
            
            # Ensure estimated_followers is a string
            inf['estimated_followers'] = str(inf.get('estimated_followers', ''))
        
        return influencers
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Response was: {response_text[:500]}")
        raise ValueError(f"Failed to parse AI response: {e}")
    except anthropic.APIError as e:
        print(f"Anthropic API error: {e}")
        raise ValueError(f"AI service error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise ValueError(f"Error generating influencers: {e}")


def validate_api_key() -> bool:
    """Check if the Anthropic API key is valid."""
    try:
        client = get_client()
        # Make a minimal API call to validate
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        return True
    except Exception as e:
        print(f"API key validation failed: {e}")
        return False
