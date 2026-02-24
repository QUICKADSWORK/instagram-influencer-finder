"""
Instagram Influencer Finder - FastAPI Application
A beautiful web app to discover Instagram influencers using AI.
"""
import os
import csv
import io
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

import database as db
import ai_service

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    try:
        db.init_db()
        print("Database initialized")
    except Exception as e:
        print(f"ERROR initializing database: {e}")

    try:
        mode = ai_service.get_search_mode()
        print(f"Search mode: {mode.get('label', 'unknown')}")
    except Exception as e:
        print(f"Search mode check: {e}")

    yield
    # Shutdown
    print("Application shutting down")


app = FastAPI(
    title="Instagram Influencer Finder",
    description="Discover Instagram influencers using AI",
    version="1.0.0",
    lifespan=lifespan
)

# Create static and templates directories
os.makedirs("static/css", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Pydantic models
class SearchRequest(BaseModel):
    keyword: str
    min_followers: int = 1000
    max_followers: int = 100000
    country: str = "USA"
    quantity: int = 10


class StatusUpdateRequest(BaseModel):
    status: str


# Countries list for the UI
COUNTRIES = [
    "USA", "India", "Brazil", "Indonesia", "United Kingdom",
    "Mexico", "Germany", "France", "Turkey", "Italy",
    "Spain", "Canada", "Australia", "Japan", "South Korea",
    "Russia", "Argentina", "Colombia", "Poland", "South Africa",
    "Nigeria", "Egypt", "UAE", "Saudi Arabia", "Philippines"
]

# Follower range presets
FOLLOWER_RANGES = [
    {"label": "Nano (1K - 10K)", "min": 1000, "max": 10000},
    {"label": "Micro (10K - 50K)", "min": 10000, "max": 50000},
    {"label": "Mid-tier (50K - 100K)", "min": 50000, "max": 100000},
    {"label": "Macro (100K - 500K)", "min": 100000, "max": 500000},
    {"label": "Mega (500K - 1M)", "min": 500000, "max": 1000000},
    {"label": "Celebrity (1M+)", "min": 1000000, "max": 10000000},
]


# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "countries": COUNTRIES,
        "follower_ranges": FOLLOWER_RANGES
    })


@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics."""
    return db.get_stats()


@app.post("/api/search")
async def search_influencers(search: SearchRequest):
    """Search for influencers using AI."""
    try:
        # Generate influencers using AI
        influencers = ai_service.generate_influencers(
            keyword=search.keyword,
            min_followers=search.min_followers,
            max_followers=search.max_followers,
            country=search.country,
            quantity=search.quantity
        )
        
        # Save to database
        added = 0
        for inf in influencers:
            if db.add_influencer(inf):
                added += 1
        
        # Log search history
        db.add_search_history(
            keyword=search.keyword,
            min_followers=search.min_followers,
            max_followers=search.max_followers,
            country=search.country,
            results_count=len(influencers)
        )
        
        return {
            "success": True,
            "found": len(influencers),
            "added": added,
            "influencers": influencers,
            "message": f"Found {len(influencers)} influencers, added {added} new ones"
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/api/influencers")
async def get_influencers(
    country: Optional[str] = Query(None),
    niche: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    format: Optional[str] = Query(None)
):
    """Get all influencers with optional filters."""
    influencers = db.get_all_influencers(
        country=country,
        niche=niche,
        status=status,
        limit=limit,
        offset=offset
    )
    total = db.get_influencer_count(country=country, niche=niche, status=status)
    
    if format == "csv":
        output = io.StringIO()
        if influencers:
            writer = csv.DictWriter(output, fieldnames=influencers[0].keys())
            writer.writeheader()
            writer.writerows(influencers)
        
        return JSONResponse(
            content={"csv": output.getvalue(), "count": len(influencers)},
            headers={"Content-Type": "application/json"}
        )
    
    return {
        "influencers": influencers,
        "count": len(influencers),
        "total": total
    }


@app.get("/api/history")
async def get_history():
    """Get search history."""
    history = db.get_search_history()
    return {"history": history}


@app.get("/api/filters")
async def get_filter_options():
    """Get available filter options."""
    return {
        "countries": COUNTRIES,
        "stored_countries": db.get_unique_countries(),
        "niches": db.get_unique_niches(),
        "follower_ranges": FOLLOWER_RANGES,
        "statuses": ["New", "Contacted", "Responded", "Hired", "Rejected"]
    }


@app.put("/api/influencers/{profile_id}/status")
async def update_status(profile_id: str, update: StatusUpdateRequest):
    """Update influencer status."""
    if db.update_influencer_status(profile_id, update.status):
        return {"success": True, "message": "Status updated"}
    raise HTTPException(status_code=404, detail="Influencer not found")


@app.delete("/api/influencers/{profile_id}")
async def delete_influencer(profile_id: str):
    """Delete an influencer."""
    if db.delete_influencer(profile_id):
        return {"success": True, "message": "Influencer deleted"}
    raise HTTPException(status_code=404, detail="Influencer not found")


@app.delete("/api/influencers")
async def clear_all():
    """Clear all influencers."""
    count = db.clear_all_influencers()
    return {"success": True, "cleared": count, "message": f"Cleared {count} influencers"}


@app.get("/api/search-mode")
async def get_search_mode():
    """Get the current search mode (Google vs AI-only)."""
    return ai_service.get_search_mode()


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
