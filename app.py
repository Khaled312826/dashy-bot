from flask import Flask, render_template, request, send_from_directory, jsonify
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/')
@app.route('/index.html')
def index():
    return send_from_directory('webapp', 'index.html')

@app.route('/style.css')
def css():
    return send_from_directory('webapp', 'style.css')

@app.route('/app.js')
def js():
    return send_from_directory('webapp', 'app.js')

@app.route('/api/track')
def api_track():
    order_id = request.args['orderId']
    # your logic to fetch latest driver coords from DB or cache
    data = get_driver_position(order_id)
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)