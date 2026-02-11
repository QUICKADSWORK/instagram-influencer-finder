#!/bin/bash

# Instagram Influencer Finder - Run Script

echo "🔍 Instagram Influencer Finder"
echo "=============================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -q

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env and add your ANTHROPIC_API_KEY"
    echo ""
fi

# Run the application
echo ""
echo "🚀 Starting server..."
echo "Open http://localhost:8001 in your browser"
echo ""
python main.py
