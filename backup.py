from flask import Flask, jsonify, request # thư viện này duùng để tạo api, jsonify dùng để trả về json, request để gửi dữ liệu từ yêu cầu của http
import pymysql # thư viện này duùng để kết nối với db mysql
from flask_cors import CORS # cho phép goọi api từ tên miền khác
import re # dùng để xử lý và khớp biêểu thức chính quy

app = Flask(__name__)
CORS(app)

# Biến toàn cục để lưu tên thiết bị được hỏi cuối cùng
last_asked_equipment = None

# Hàm này dùng để kết nối vs db trên hosting
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

# API chính để xử lý yêu cầu kiểm tra tồn kho
@app.route('/api/inventory-chatbot', methods=['GET'])
def get_inventory():
    global last_asked_equipment
    prompt = request.args.get('prompt') # lấy câu hỏi từ prompt trong yêu cầu
    if not prompt:
        return jsonify({"error": "Vui lòng cung cấp câu hỏi"}), 400

    # kiểm tra xem câu hỏi có chứa các từ khóa liên quan đến thiết bị gần hết hay không
    low_stock_match = re.search(r"(thiết bị nào gần hết|thiết bị nào sắp hết|thiết bị nào còn ít|thiết bị nào tồn kho thấp|liệt kê thiết bị gần hết)", prompt, re.IGNORECASE)

    # nếu có từ khóa thì gọi hàm lấy danh sách thiết bị tồn kho thấp
    if low_stock_match:
        return get_low_stock_items()

    # làm khớp câu hỏi để tìm thiết bị và yêu cầu chi tiết về tồn kho của thiết bị
    match = re.search(r"(số lượng tồn kho của thiết bị|cho tôi biết số lượng tồn kho của|số lượng của|tồn kho của|số lượng còn lại của|tình trạng tồn kho của|tôi có bao nhiêu|còn bao nhiêu|có không|đang có|hiện có|số lượng hiện tại của|còn lại bao nhiêu|có tồn kho không|số lượng còn|tình trạng hiện tại của|còn lại của|thông tin tồn kho về|số lượng sản phẩm tồn kho của) (.+?) (còn bao nhiêu|không|hết|không có|hiện tại|còn bao nhiêu|đã hết|có còn|còn tồn tại|hiện có|đang có|tình trạng|tồn kho|đang tồn kho|có không|còn lại|)", prompt, re.IGNORECASE)

    if not match:
        # Nếu không khớp và không có thiết bị được hỏi trước đó, trả về lỗi
        if last_asked_equipment:
            equipment_name = last_asked_equipment
        else:
            return jsonify({"error": "Nội dung này tôi chưa được học ạ"}), 400
    else:
        # Nếu khớp, lấy tên thiết bị từ câu hỏi
        equipment_name = match.group(2).strip()
        last_asked_equipment = equipment_name

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Truy vấn thông tin tồn kho của thiết bị
            sql = """
                SELECT i.equipment_code, i.current_quantity, i.batch_number, e.name AS equipment_name
                FROM inventories i
                JOIN equipments e ON i.equipment_code = e.code
                WHERE e.name = %s
                LIMIT 1
            """
            cursor.execute(sql, (equipment_name,))
            result = cursor.fetchone()

            if not result:
                # Nếu không tìm thấy kết quả chính xác thì thử tìm kiếm tương đối
                sql = """
                    SELECT i.equipment_code, i.current_quantity, i.batch_number, e.name AS equipment_name
                    FROM inventories i
                    JOIN equipments e ON i.equipment_code = e.code
                    WHERE e.name LIKE %s
                    LIMIT 1
                """
                cursor.execute(sql, (equipment_name + '%',))
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
                return jsonify({"error": "Không tìm thấy thiết bị"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        connection.close()

def get_low_stock_items(threshold=10):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Truy vấn các thiết bị có tồn kho thấp hơn hoặc bằng ngưỡng tồn kho thấp
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
