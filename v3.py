from flask import Flask, jsonify, request
import pymysql
from flask_cors import CORS
import re
from rapidfuzz import process, fuzz

app = Flask(__name__)
CORS(app)

# Biến toàn cục để lưu tên thiết bị được hỏi cuối cùng
last_asked_equipment = None

# Kết nối cơ sở dữ liệu MySQL
def get_db_connection():
    return pymysql.connect(
        host='137.59.106.62',
        user='q3jg2wfo6014_nhathuy',
        password='@Kalosonits14',
        database='q3jg2wfo6014_beesoft_db',
        port=3306,
        cursorclass=pymysql.cursors.DictCursor
    )

# Lấy danh sách tất cả tên thiết bị
@app.route('/api/equipment-names', methods=['GET'])
def get_all_equipment_names():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Truy vấn danh sách tên thiết bị từ bảng 'equipments'
            sql = "SELECT name FROM equipments"
            cursor.execute(sql)
            equipment_names = [row['name'] for row in cursor.fetchall()]

            # Trả về danh sách tên thiết bị nếu có, ngược lại thông báo lỗi
            if equipment_names:
                return jsonify({"equipment_names": equipment_names})
            else:
                return jsonify({"message": "Không có thiết bị nào trong cơ sở dữ liệu."}), 404
    except Exception as e:
        # Trả về lỗi nếu có vấn đề xảy ra
        return jsonify({"error": str(e)}), 500
    finally:
        # Đóng kết nối cơ sở dữ liệu
        connection.close()

# API chatbot xử lý yêu cầu liên quan đến tồn kho
@app.route('/api/inventory-chatbot', methods=['GET'])
def get_inventory():
    global last_asked_equipment
    # Lấy câu hỏi từ query string
    prompt = request.args.get('prompt')
    if not prompt:
        return jsonify({"error": "Vui lòng cung cấp câu hỏi"}), 400

    # Kiểm tra từ khóa liên quan đến thiết bị tồn kho thấp
    low_stock_match = re.search(r"(thiết bị nào gần hết|sắp hết|còn ít|tồn kho thấp)", prompt, re.IGNORECASE)
    if low_stock_match:
        # Gọi hàm lấy danh sách thiết bị tồn kho thấp
        return get_low_stock_items()

    # Kiểm tra từ khóa liên quan đến tồn kho thiết bị cụ thể
    match = re.search(r"(số lượng tồn kho của|tình trạng tồn kho của|còn bao nhiêu|tồn kho của) (.+)", prompt, re.IGNORECASE)
    if match:
        # Lấy tên thiết bị từ câu hỏi
        equipment_name = match.group(2).strip()
        last_asked_equipment = equipment_name
    else:
        # Nếu không có thiết bị trong câu hỏi, dùng tên thiết bị đã hỏi trước đó
        if last_asked_equipment:
            equipment_name = last_asked_equipment
        else:
            return jsonify({"error": "Không hiểu câu hỏi của bạn. Vui lòng thử lại."}), 400

    # Gọi hàm tìm kiếm tồn kho của thiết bị
    return find_equipment_inventory(equipment_name)

# Tìm thông tin tồn kho của một thiết bị
def find_equipment_inventory(equipment_name):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Tìm kiếm chính xác thiết bị trong cơ sở dữ liệu
            sql = """
                SELECT i.equipment_code, i.current_quantity, i.batch_number, e.name AS equipment_name
                FROM inventories i
                JOIN equipments e ON i.equipment_code = e.code
                WHERE e.name = %s
                LIMIT 1
            """
            cursor.execute(sql, (equipment_name,))
            result = cursor.fetchone()

            # Nếu không tìm thấy, thực hiện fuzzy matching
            if not result:
                best_match = find_best_match(equipment_name, cursor)
                if best_match:
                    # Tìm thiết bị theo tên gần đúng nhất
                    cursor.execute(sql, (best_match,))
                    result = cursor.fetchone()

            # Trả về thông tin thiết bị nếu tìm thấy
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
        # Trả về lỗi nếu xảy ra sự cố
        return jsonify({"error": str(e)}), 500
    finally:
        # Đóng kết nối cơ sở dữ liệu
        connection.close()

# Sử dụng Fuzzy Matching để tìm tên thiết bị gần đúng
def find_best_match(equipment_name, cursor):
    # Lấy tất cả tên thiết bị từ bảng 'equipments'
    sql = "SELECT e.name FROM equipments e"
    cursor.execute(sql)
    all_equipment_names = [row['name'] for row in cursor.fetchall()]

    # Dùng RapidFuzz để tìm tên khớp nhất với độ chính xác cao nhất
    best_match = process.extractOne(equipment_name, all_equipment_names, scorer=fuzz.ratio)

    # Trả về tên thiết bị nếu độ chính xác >= 70%, ngược lại trả về None
    return best_match[0] if best_match and best_match[1] >= 70 else None

# Lấy danh sách thiết bị tồn kho thấp hơn ngưỡng
def get_low_stock_items(threshold=10):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Tìm các thiết bị có số lượng tồn kho <= threshold
            sql = """
                SELECT i.equipment_code, i.current_quantity, i.batch_number, e.name AS equipment_name
                FROM inventories i
                JOIN equipments e ON i.equipment_code = e.code
                WHERE i.current_quantity <= %s
            """
            cursor.execute(sql, (threshold,))
            results = cursor.fetchall()

            # Trả về danh sách thiết bị nếu có, ngược lại trả thông báo không có thiết bị nào
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
        # Trả về lỗi nếu xảy ra sự cố
        return jsonify({"error": str(e)}), 500
    finally:
        # Đóng kết nối cơ sở dữ liệu
        connection.close()

if __name__ == '__main__':
    # Chạy ứng dụng Flask trên cổng 5000 với chế độ gỡ lỗi
    app.run(debug=True, port=5000)
