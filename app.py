import os
import json
import random
import gspread
from flask import Flask, jsonify, render_template, request
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

SHEET_NAME = "codes_roulette"


def get_gspread_client():
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDS not set")
    creds_dict = json.loads(creds_json)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)


@app.route('/')
def index():
    return render_template('wheel.html')


@app.route('/get_prizes_list')
def get_prizes_list():
    """Возвращаем все призы для отрисовки колеса (даже если stock = 0)"""
    try:
        client = get_gspread_client()
        stock_sheet = client.open(SHEET_NAME).worksheet("prizes_stock")
        rows = stock_sheet.get_all_records()
        if not rows:
            names = ["Ошибка"]
        else:
            names = [row.get("name", "?") for row in rows]
        return jsonify({"names": names})
    except Exception as e:
        print(f"Ошибка получения списка призов: {e}")
        return jsonify({"names": ["Ошибка"]})


@app.route('/spin', methods=['POST'])
def spin():
    try:
        data = request.get_json()
        user_code = data.get('code', '').strip().upper()
        nickname = data.get('nickname', '').strip()

        if not user_code:
            return jsonify({"error": "Введите код"}), 400
        if not nickname:
            return jsonify({"error": "Введите никнейм"}), 400

        client = get_gspread_client()
        spreadsheet = client.open(SHEET_NAME)

        # Лист с кодами
        codes_sheet = spreadsheet.sheet1

        # Лист с призами
        stock_sheet = spreadsheet.worksheet("prizes_stock")

        # Проверяем код
        try:
            cell = codes_sheet.find(user_code)
        except gspread.exceptions.CellNotFound:
            return jsonify({"error": "Код не найден"}), 404

        row = cell.row
        status = codes_sheet.cell(row, 2).value
        if status and status.upper() == "TRUE":
            return jsonify({"error": "Код уже использован"}), 403

        # Получаем все призы из prizes_stock
        rows = stock_sheet.get_all_records()

        # Выбираем только доступные призы (stock > 0)
        available_prizes = []
        weights = []
        for row_data in rows:
            try:
                name = row_data["name"]
                chance = int(row_data.get("chance", 1))
                stock = int(row_data.get("stock", 0))
                if stock > 0:
                    available_prizes.append(name)
                    weights.append(chance)
            except Exception:
                continue  # пропускаем некорректные строки

        if not available_prizes:
            return jsonify({"error": "Все призы закончились"}), 400

        # Выбираем приз
        selected_prize = random.choices(available_prizes, weights=weights, k=1)[0]

        # Уменьшаем stock выбранного приза безопасно
        try:
            prize_cell = stock_sheet.find(selected_prize)
            prize_row = prize_cell.row
            current_stock = stock_sheet.cell(prize_row, 3).value
            current_stock = int(current_stock) if current_stock else 1
            stock_sheet.update_cell(prize_row, 3, max(0, current_stock - 1))
        except Exception as e:
            print(f"Ошибка обновления stock: {e}")

        # Обновляем код как использованный
        codes_sheet.update_cell(row, 2, "TRUE")
        codes_sheet.update_cell(row, 3, nickname)
        codes_sheet.update_cell(row, 4, selected_prize)

        # Для фронта (все сегменты колеса)
        all_names = [row.get("name", "?") for row in rows] or ["Ошибка"]

        return jsonify({
            "prize": selected_prize,
            "index": all_names.index(selected_prize) if selected_prize in all_names else 0,
            "total_segments": len(all_names),
            "all_names": all_names
        })

    except Exception as e:
        print(f"Ошибка сервера: {e}")
        return jsonify({"error": "Ошибка сервера"}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
