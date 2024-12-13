from flask import Flask, jsonify, request
import pymysql
from flask_cors import CORS
import re
from rapidfuzz import fuzz, process

app = Flask(__name__)
CORS(app)

# Biến toàn cục để lưu thiết bị được hỏi cuối cùng
last_asked_equipment = None

# Kết nối database
def get_db_connection():
    connection = pymysql.connect(
        host='137.59.106.62',
        user='q3jg2wfo6014_nhathuy',
        password='@Kalosonits14',
        database='q3jg2wfo6014_beesoft_db',
        port=3306,
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection

# API kiểm tra tồn kho
@app.route('/api/inventory-chatbot', methods=['GET'])
def get_inventory():
    global last_asked_equipment
    prompt = request.args.get('prompt')
    if not prompt:
        return jsonify({"error": "Vui lòng cung cấp câu hỏi"}), 400

    # Kiểm tra câu hỏi liên quan đến tồn kho thấp
    low_stock_match = re.search(r"(thiết bị nào gần hết|thiết bị nào sắp hết|thiết bị nào còn ít|thiết bị nào tồn kho thấp|liệt kê thiết bị gần hết)", prompt, re.IGNORECASE)
    if low_stock_match:
        return get_low_stock_items()

    # Kiểm tra câu hỏi liên quan đến tồn kho cụ thể
    match = re.search(r"(số lượng tồn kho của|tồn kho của|số lượng của) (.+?) (còn bao nhiêu|không|hết|tình trạng)", prompt, re.IGNORECASE)

    # Lấy tên thiết bị từ câu hỏi hoặc từ lần hỏi trước
    if match:
        equipment_name = match.group(2).strip()
        last_asked_equipment = equipment_name
    elif last_asked_equipment:
        equipment_name = last_asked_equipment
    else:
        return jsonify({"error": "Không tìm thấy tên thiết bị trong câu hỏi"}), 400

    # Tìm thiết bị trong cơ sở dữ liệu
    return find_equipment_inventory(equipment_name)

# Tìm kiếm thiết bị và trả về thông tin tồn kho
def find_equipment_inventory(equipment_name):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Tìm kiếm chính xác thiết bị
            sql = """
                SELECT i.equipment_code, i.current_quantity, i.batch_number, e.name AS equipment_name
                FROM inventories i
                JOIN equipments e ON i.equipment_code = e.code
                WHERE e.name = %s
                LIMIT 1
            """
            cursor.execute(sql, (equipment_name,))
            result = cursor.fetchone()

            # Nếu không tìm thấy chính xác, thử fuzzy matching
            if not result:
                best_match = find_best_match(equipment_name, cursor)
                if best_match:
                    cursor.execute(sql, (best_match,))
                    result = cursor.fetchone()

            # Nếu vẫn không tìm thấy, trả về lỗi
            if not result:
                return jsonify({"error": "Không tìm thấy thiết bị"}), 404

            # Trả về thông tin thiết bị
            return jsonify({
                "equipment_code": result['equipment_code'],
                "equipment_name": result['equipment_name'],
                "current_quantity": result['current_quantity'],
                "batch_number": result['batch_number'],
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        connection.close()

# Tìm kiếm tên thiết bị phù hợp nhất sử dụng Fuzzy Matching
def find_best_match(equipment_name, cursor):
    sql = "SELECT e.name FROM equipments e"
    cursor.execute(sql)
    all_equipment_names = [row['name'] for row in cursor.fetchall()]
    best_match = process.extractOne(equipment_name, all_equipment_names, scorer=fuzz.ratio)
    return best_match[0] if best_match and best_match[1] >= 70 else None

# Lấy danh sách thiết bị tồn kho thấp
def get_low_stock_items(threshold=10):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT i.equipment_code, i.current_quantity, i.batch_number, e.name AS equipment_name
                FROM inventories i
                JOIN equipments e ON i.equipment_code = e.code
                WHERE i.current_quantity <= %s
            """
            cursor.execute(sql, (threshold,))
            results = cursor.fetchall()

            if results:
                return jsonify([{
                    "equipment_code": item['equipment_code'],
                    "equipment_name": item['equipment_name'],
                    "current_quantity": item['current_quantity'],
                    "batch_number": item['batch_number'],
                } for item in results])
            else:
                return jsonify({"message": "Không có thiết bị nào gần hết."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        connection.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
