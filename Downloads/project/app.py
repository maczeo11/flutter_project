from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
import mysql.connector
import os

from waitress import serve

app = Flask(__name__)

# Set up global CORS configuration (for all routes)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Set the correct upload folder path
app.config['UPLOAD_FOLDER'] = r'C:\Users\BANU THEJA\Downloads\project\images'  # <-- Updated path
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # Allowed file extensions
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit file size to 16MB

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_db_connection():
    """Establish a database connection."""
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='my#sys()',  # Make sure this is the correct password for your MySQL setup
            database='data'
        )
        return conn
    except mysql.connector.Error as err:
        print("Error connecting to MySQL:", err)
        return None

@app.route('/add_item', methods=['POST'])
@cross_origin(methods=['POST', 'OPTIONS'], headers=['Content-Type', 'Authorization'])
def add_item():
    data = request.form

    # Get item details from the form
    login_id = data.get('user_id')
    item_name = data.get('item_name')
    description = data.get('description')
    price = data.get('price')

    print(f"Received data: user_id={login_id}, item_name={item_name}, description={description}, price={price}")

    # Check if all required fields are present
    if not item_name or not description or not price or not login_id:
        return jsonify({"message": "User ID, Item name, description, and price are required"}), 400

    try:
        price = float(price)
    except ValueError:
        return jsonify({"message": "Price must be a valid number"}), 400

    # Insert the new item into the database
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error"}), 500

    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO items (item_name, description, price, login_id) VALUES (%s, %s, %s, %s)",
                       (item_name, description, price, login_id))
        conn.commit()

        # Get the last inserted item_id
        item_id = cursor.lastrowid

        # Handle image upload
        if 'image' not in request.files:
            return jsonify({"message": "No image file found"}), 400

        image = request.files['image']

        print(f"Received image: {image.filename}")

        if image and allowed_file(image.filename):
            filename = f"{item_id}.jpg"  # Rename image to item_id.jpg
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Ensure the upload folder exists
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            image.save(filepath)

            # Store the image path in the database
            image_path = f"/images/{filename}"

            cursor.execute("UPDATE items SET image_path = %s WHERE item_id = %s", (image_path, item_id))
            conn.commit()

            return jsonify({"message": "Item added successfully with image", "item_id": item_id}), 201
        else:
            return jsonify({"message": "Invalid image format. Only jpg, jpeg, or png allowed"}), 400

    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({"message": f"Database error: {e}"}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/add_user', methods=['POST'])
@cross_origin(methods=['POST', 'OPTIONS'], headers=['Content-Type', 'Authorization'])
def add_user():
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    if not username or not password or not email:
        return jsonify({"message": "Username, password, and email are required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error"}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM login WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user:
            return jsonify({"message": "User already exists"}), 400

        cursor.execute("INSERT INTO login (username, password, email) VALUES (%s, %s, %s)", 
                       (username, password, email))
        conn.commit()
        return jsonify({"message": "User added successfully"}), 201

    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({"message": f"Database error: {e}"}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/items', methods=['GET'])
@cross_origin(methods=['GET', 'OPTIONS'], headers=['Content-Type', 'Authorization'])
def get_items():
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('''
            SELECT 
                items.item_id, 
                items.item_name, 
                items.description, 
                items.price, 
                items.login_id, 
                login.username,      
                login.email          
            FROM items
            JOIN login ON items.login_id = login.id
        ''')

        items = cursor.fetchall()
        return jsonify(items)

    except mysql.connector.Error as e:
        return jsonify({"message": f"Database error: {e}"}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/login', methods=['POST'])
@cross_origin(methods=['POST', 'OPTIONS'], headers=['Content-Type', 'Authorization'])
def login():
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error"}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM login WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and user[2] == password:
            return jsonify({
                "message": "Login successful",
                "user_id": user[0]
            }), 200
        else:
            return jsonify({"message": "Invalid credentials"}), 401

    except mysql.connector.Error as e:
        return jsonify({"message": f"Database error: {e}"}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/item/<int:item_id>/image', methods=['GET'])
@cross_origin(methods=['GET', 'OPTIONS'], headers=['Content-Type', 'Authorization'])
def get_item_image(item_id):
    image_filename = f"{item_id}.jpg"
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)

    if os.path.exists(image_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], image_filename)
    else:
        return jsonify({"message": "Image not found"}), 404

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
