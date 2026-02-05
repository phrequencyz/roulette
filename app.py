import os
import requests
import random
from flask import Flask, jsonify, render_template

app = Flask(__name__)

JSON_URL = "https://raw.githubusercontent.com/phrequencyz/roulette/refs/heads/main/prizes.json"

def get_prizes():
    try:
        r = requests.get(JSON_URL, timeout=5)
        r.raise_for_status()
        return r.json(), False
    except Exception as e:
        print(f"Ошибка загрузки JSON: {e}")
        # Возвращаем дефолтный набор и флаг ошибки True
        return [{"name": "Ошибка данных", "chance": 100}], True

@app.route('/')
def index():
    return render_template('wheel.html')

@app.route('/spin', methods=['POST'])
def spin():
    prizes, is_error = get_prizes()
    names = [p['name'] for p in prizes]
    weights = [p['chance'] for p in prizes]
    
    selected_prize = random.choices(names, weights=weights, k=1)[0]
    
    return jsonify({
        "prize": selected_prize,
        "index": names.index(selected_prize),
        "total_segments": len(names),
        "all_names": names,
        "error": is_error
    })

if __name__ == '__main__':
    app.run()

