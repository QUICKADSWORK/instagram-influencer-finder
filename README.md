# Instagram Influencer Finder

AI-powered Instagram influencer discovery tool for marketers. Find creators based on niche, follower count, and location using Claude AI.

## Features

- **AI-Powered Discovery**: Uses Claude AI to find relevant influencers
- **Smart Filtering**: Filter by country, niche, follower range, and status
- **Status Tracking**: Track outreach progress (New → Contacted → Responded → Hired)
- **Export to CSV**: Download your influencer list
- **Search History**: Track all your searches
- **Beautiful UI**: Modern, responsive design with Instagram-inspired styling

## Quick Start

### Prerequisites
- Python 3.9+
- Anthropic API key (get one at https://console.anthropic.com)

### Local Setup

1. **Clone and navigate:**
```bash
cd instagram-influencer-finder
```

2. **Create environment file:**
```bash
cp .env.example .env
```

3. **Add your API key:**
Edit `.env` and replace `your_anthropic_api_key_here` with your actual Anthropic API key.

4. **Run the app:**
```bash
chmod +x run.sh
./run.sh
```

5. **Open in browser:**
Visit http://localhost:8001

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Required |
| `PORT` | Server port | 8001 |

## Usage

1. **Enter a niche/keyword** (e.g., "fitness", "travel", "fashion")
2. **Select country** from the dropdown
3. **Choose follower range** (Nano to Celebrity)
4. **Set quantity** (5-20 influencers)
5. **Click "Find Influencers"**

The AI will generate relevant influencer suggestions based on your criteria.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search` | POST | Search for influencers |
| `/api/influencers` | GET | Get all influencers |
| `/api/influencers` | DELETE | Clear all influencers |
| `/api/influencers/{id}/status` | PUT | Update status |
| `/api/stats` | GET | Get statistics |
| `/api/history` | GET | Get search history |
| `/api/filters` | GET | Get filter options |

## Deploy on Render

1. Push to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click "New +" → "Web Service"
4. Connect your repository
5. Add `ANTHROPIC_API_KEY` environment variable
6. Add a 1GB disk mounted at `/data`
7. Deploy!

## Tech Stack

- **Backend**: FastAPI + Python
- **Database**: SQLite
- **AI**: Anthropic Claude
- **Frontend**: HTML + Tailwind CSS
- **Deployment**: Render

## License

MIT
