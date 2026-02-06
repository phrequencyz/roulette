import os
import json
import random
import requests
import gspread
from flask import Flask, jsonify, render_template, request
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

SHEET_NAME = "codes_roulette"
JSON_URL = "https://raw.githubusercontent.com/phrequencyz/roulette/refs/heads/main/prizes.json"

def get_gspread_client():
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDS not set")
    creds_dict = json.loads(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def get_prizes():
    try:
        r = requests.get(JSON_URL, timeout=5)
        r.raise_for_status()
        return r.json(), False
    except:
        return [{"name": "Ошибка JSON", "chance": 1}], True

@app.route('/')
def index():
    return render_template('wheel.html')

@app.route('/get_prizes_list')
def get_prizes_list():
    prizes, is_error = get_prizes()
    names = [p['name'] for p in prizes]
    return jsonify({"names": names})

@app.route('/spin', methods=['POST'])
def spin():
    try:
        data = request.get_json()
        user_code = data.get('code', '').strip().upper()
        nickname = data.get('nickname', '').strip() # ПОЛУЧАЕМ НИКНЕЙМ

        if not user_code:
            return jsonify({"error": "Введите код"}), 400
        if not nickname:
            return jsonify({"error": "Введите никнейм"}), 400

        client = get_gspread_client()
        sheet = client.open(SHEET_NAME).sheet1
        
        try:
            cell = sheet.find(user_code)
        except gspread.exceptions.CellNotFound:
            return jsonify({"error": "Код не найден"}), 404

        row = cell.row
        # Получаем статус из колонки 2 (B)
        status = sheet.cell(row, 2).value
        
        if status and status.upper() == "TRUE":
            return jsonify({"error": "Код уже использован"}), 403

        # Сначала выбираем приз, чтобы записать его в таблицу
        prizes, _ = get_prizes()
        names = [p['name'] for p in prizes]
        weights = [p['chance'] for p in prizes]
        selected_prize = random.choices(names, weights=weights, k=1)[0]

        # ОБНОВЛЯЕМ ТАБЛИЦУ:
        # Колонка 2: TRUE (статус)
        # Колонка 3: Никнейм
        # Колонка 4: Название приза
        sheet.update_cell(row, 2, "TRUE")
        sheet.update_cell(row, 3, nickname)
        sheet.update_cell(row, 4, selected_prize)

        return jsonify({
            "prize": selected_prize,
            "index": names.index(selected_prize),
            "total_segments": len(names),
            "all_names": names
        })
    except Exception as e:
        print(f"Ошибка: {e}") # Полезно для логов в консоли
        return jsonify({"error": "Ошибка сервера"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
