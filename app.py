from flask import Flask, render_template_string

app = Flask(__name__)

# HTML template for the Hello World page
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hello World</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            text-align: center;
            color: white;
            padding: 2rem;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        p {
            font-size: 1.2rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>👋 Hello World!</h1>
        <p>Welcome to your first Flask web application</p>
    </div>
</body>
</html>
"""

@app.route('/')
def hello_world():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/hello')
def hello_api():
    return {'message': 'Hello World!', 'status': 'success'}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
