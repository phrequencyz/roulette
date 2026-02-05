import os
import requests
import random
import sqlite3
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

JSON_URL = "https://raw.githubusercontent.com/phrequencyz/roulette/refs/heads/main/prizes.json"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('codes.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

init_db()

def get_prizes():
    try:
        r = requests.get(JSON_URL, timeout=5)
        r.raise_for_status()
        return r.json(), False
    except Exception as e:
        print(f"Ошибка загрузки JSON: {e}")
        return [{"name": "Ошибка данных", "chance": 100}], True

@app.route('/')
def index():
    return render_template('wheel.html')

@app.route('/spin', methods=['POST'])
def spin():
    data = request.json
    user_code = data.get('code', '').strip()

    # Проверка кода в БД
    conn = sqlite3.connect('codes.db')
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM promo_codes WHERE code = ?", (user_code,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return jsonify({"error_msg": "Неверный или использованный код"}), 403

    # Если код верный, удаляем его (одноразовое использование)
    cursor.execute("DELETE FROM promo_codes WHERE code = ?", (user_code,))
    conn.commit()
    conn.close()

    # Логика рулетки
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
