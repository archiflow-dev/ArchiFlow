#!/bin/bash
# Setup script for ArchiFlow

set -e

echo "Setting up ArchiFlow..."

# Check if Python 3.10+ is installed
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy environment template if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env file with your API keys"
fi

echo ""
echo "Setup complete! To start using ArchiFlow:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Edit .env file with your API keys"
echo "  3. Run: python run_dev.py"
echo ""
echo "For development, install dev dependencies:"
echo "  pip install -r requirements-dev.txt"