# Hello World Web App

A simple "Hello World" web application built with Flask.

## Features

- **Home Page (`/`)**: Displays a beautiful "Hello World" landing page with gradient background
- **API Endpoint (`/api/hello`)**: Returns a JSON response with a greeting message

## Installation

1. Install the required dependencies:
   ```bash
   pip install -r web_app_requirements.txt
   ```

## Running the Application

Start the web server:
```bash
python app.py
```

The application will be available at:
- **Main page**: http://localhost:5000
- **API endpoint**: http://localhost:5000/api/hello

## API Example

```bash
curl http://localhost:5000/api/hello
```

Response:
```json
{
  "message": "Hello World!",
  "status": "success"
}
```

## Stopping the Server

Press `Ctrl+C` in the terminal where the app is running to stop the server.
