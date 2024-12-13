from flask import Flask, jsonify, request
import pymysql
from flask_cors import CORS
import re
from rapidfuzz import process, fuzz

app = Flask(__name__)
CORS(app)

# Biến toàn cục để lưu tên thiết bị được hỏi cuối cùng
last_asked_equipment = None

# Hàm kết nối cơ sở dữ liệu
def get_db_connection():
    return pymysql.connect(
        host='137.59.106.62',
        user='q3jg2wfo6014_nhathuy',
        password='@Kalosonits14',
        database='q3jg2wfo6014_beesoft_db',
        port=3306,
        cursorclass=pymysql.cursors.DictCursor
    )

# API chính để xử lý yêu cầu kiểm tra tồn kho
@app.route('/api/inventory-chatbot', methods=['GET'])
def get_inventory():
    global last_asked_equipment
    prompt = request.args.get('prompt')  # Lấy câu hỏi từ query string
    if not prompt:
        return jsonify({"error": "Vui lòng cung cấp câu hỏi"}), 400

    # Kiểm tra từ khóa liên quan đến thiết bị tồn kho thấp
    low_stock_match = re.search(r"(thiết bị nào gần hết|sắp hết|còn ít|tồn kho thấp)", prompt, re.IGNORECASE)
    if low_stock_match:
        return get_low_stock_items()

    # Khớp câu hỏi tìm tồn kho thiết bị cụ thể
    match = re.search(r"(số lượng tồn kho của|tình trạng tồn kho của|còn bao nhiêu|tồn kho của) (.+)", prompt, re.IGNORECASE)
    if match:
        equipment_name = match.group(2).strip()
        last_asked_equipment = equipment_name
    else:
        # Nếu không khớp và không có thiết bị trước đó, trả lỗi
        if last_asked_equipment:
            equipment_name = last_asked_equipment
        else:
            return jsonify({"error": "Không hiểu câu hỏi của bạn. Vui lòng thử lại."}), 400

    return find_equipment_inventory(equipment_name)

# Hàm tìm kiếm tồn kho thiết bị
def find_equipment_inventory(equipment_name):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Tìm kiếm chính xác
            sql = """
                SELECT i.equipment_code, i.current_quantity, i.batch_number, e.name AS equipment_name
                FROM inventories i
                JOIN equipments e ON i.equipment_code = e.code
                WHERE e.name = %s
                LIMIT 1
            """
            cursor.execute(sql, (equipment_name,))
            result = cursor.fetchone()

            # Nếu không tìm thấy, thử fuzzy matching
            if not result:
                best_match = find_best_match(equipment_name, cursor)
                if best_match:
                    cursor.execute(sql, (best_match,))
                    result = cursor.fetchone()

            # Trả về kết quả
            if result:
                return jsonify({
                    "equipment_code": result['equipment_code'],
                    "equipment_name": result['equipment_name'],
                    "current_quantity": result['current_quantity'],
                    "batch_number": result['batch_number'],
                })
            else:
                return jsonify({"error": f"Không tìm thấy thiết bị với tên '{equipment_name}'."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        connection.close()

# Hàm tìm kiếm tên thiết bị gần đúng nhất sử dụng Fuzzy Matching
def find_best_match(equipment_name, cursor):
    # Lấy tất cả tên thiết bị từ cơ sở dữ liệu
    sql = "SELECT e.name FROM equipments e"
    cursor.execute(sql)
    all_equipment_names = [row['name'] for row in cursor.fetchall()]

    # Sử dụng RapidFuzz để tìm tên khớp nhất
    best_match = process.extractOne(equipment_name, all_equipment_names, scorer=fuzz.ratio)

    # Trả về tên thiết bị nếu độ chính xác >= 70%
    return best_match[0] if best_match and best_match[1] >= 70 else None

# Hàm trả về danh sách thiết bị tồn kho thấp
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
