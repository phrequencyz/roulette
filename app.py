import os
import json
import random
import requests
import gspread
from flask import Flask, jsonify, render_template, request
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# --- НАСТРОЙКИ (Проверь их!) ---
SHEET_NAME = "Название_Твоей_Таблицы"  # Должно в точности совпадать с Google Таблицей
JSON_URL = "https://raw.githubusercontent.com/phrequencyz/roulette/refs/heads/main/prizes.json"

def get_gspread_client():
    """Авторизация в Google Sheets через переменную окружения Render."""
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        raise ValueError("Ошибка: Переменная GOOGLE_CREDS не настроена на Render!")
    
    creds_dict = json.loads(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def get_prizes():
    """Загрузка списка призов из твоего GitHub JSON."""
    try:
        r = requests.get(JSON_URL, timeout=5)
        r.raise_for_status()
        return r.json(), False
    except Exception as e:
        print(f"Ошибка загрузки JSON с призами: {e}")
        # Заглушка, если JSON не доступен
        return [{"name": "Приз 1", "chance": 50}, {"name": "Приз 2", "chance": 50}], True

@app.route('/')
def index():
    """Главная страница."""
    return render_template('wheel.html')

@app.route('/get_prizes_list', methods=['GET'])
def get_prizes_list():
    """Отдает список имен призов для отрисовки колеса при загрузке."""
    prizes, is_error = get_prizes()
    if is_error:
        return jsonify({"error": "Не удалось загрузить призы"}), 500
    names = [p['name'] for p in prizes]
    return jsonify({"names": names})

@app.route('/spin', methods=['POST'])
def spin():
    """Проверка кода и запуск рулетки."""
    try:
        data = request.get_json()
        # Приводим код к верхнему регистру, чтобы избежать ошибок ввода
        user_code = data.get('code', '').strip().upper()

        if not user_code:
            return jsonify({"error": "Введите код!"}), 400

        # 1. Подключаемся к таблице
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME).sheet1
        
        # 2. Ищем код в колонке A
        try:
            cell = sheet.find(user_code)
        except gspread.exceptions.CellNotFound:
            return jsonify({"error": "Код не существует"}), 404

        row = cell.row
        # Проверяем колонку B (2-я колонка) на предмет использования
        status = sheet.cell(row, 2).value
        
        if status and status.upper() == "TRUE":
            return jsonify({"error": "Код уже был использован"}), 403

        # 3. Сразу помечаем как использованный
        sheet.update_cell(row, 2, "TRUE")

        # 4. Выбираем приз по весам
        prizes, is_error = get_prizes()
        names = [p['name'] for p in prizes]
        weights = [p['chance'] for p in prizes]
        
        selected_prize = random.choices(names, weights=weights, k=1)[0]

        return jsonify({
            "prize": selected_prize,
            "index": names.index(selected_prize),
            "total_segments": len(names),
            "all_names": names
        })

    except Exception as e:
        print(f"Критическая ошибка сервера: {e}")
        return jsonify({"error": "Ошибка сервера. Проверьте логи."}), 500

if __name__ == '__main__':
    # Настройки порта для Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
