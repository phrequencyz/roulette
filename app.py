import os
import json
import random
import requests
import gspread
from flask import Flask, jsonify, render_template, request
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# --- НАСТРОЙКА GOOGLE ТАБЛИЦ ---
def get_gspread_client():
    # Мы берем JSON-строку из переменной окружения GOOGLE_CREDS
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        raise ValueError("Переменная GOOGLE_CREDS не найдена в настройках Render!")
    
    creds_dict = json.loads(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# Название твоей таблицы (в точности как в Google Sheets)
SHEET_NAME = "Название_Твоей_Таблицы" 
JSON_URL = "https://raw.githubusercontent.com/phrequencyz/roulette/refs/heads/main/prizes.json"

def get_prizes():
    try:
        r = requests.get(JSON_URL, timeout=5)
        r.raise_for_status()
        return r.json(), False
    except Exception as e:
        print(f"Ошибка JSON: {e}")
        return [{"name": "Ошибка", "chance": 100}], True

@app.route('/')
def index():
    return render_template('wheel.html')

@app.route('/spin', methods=['POST'])
def spin():
    data = request.get_json()
    user_code = data.get('code', '').strip()

    if not user_code:
        return jsonify({"error": "Введите код"}), 400

    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME).sheet1
        
        # 1. Ищем код в колонке A
        cell = sheet.find(user_code)
        row = cell.row
        
        # 2. Проверяем статус в колонке B (2-я колонка)
        # Мы ожидаем там пустоту или "FALSE", если код не использован
        status = sheet.cell(row, 2).value
        
        if status and status.upper() == "TRUE":
            return jsonify({"error": "Код уже использован!"}), 403

        # 3. Если все ок, сначала помечаем код как использованный
        sheet.update_cell(row, 2, "TRUE")

        # 4. Логика выбора приза
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

    except gspread.exceptions.CellNotFound:
        return jsonify({"error": "Неверный код"}), 404
    except Exception as e:
        print(f"Ошибка сервера: {e}")
        return jsonify({"error": "Ошибка базы данных"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
