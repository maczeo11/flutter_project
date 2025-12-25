from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
import mysql.connector
import os
from werkzeug.utils import secure_filename  # For safely saving the file
# Removed password hashing imports: from werkzeug.security import generate_password_hash, check_password_hash
from waitress import serve

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}}, methods=["POST", "GET", "OPTIONS"], allow_headers=["Content-Type", "Authorization"], supports_credentials=True)


# Set the correct upload folder path
app.config['UPLOAD_FOLDER'] = r'C:\Users\BANU THEJA\Downloads\project\images'
# <-- Updated path
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
            password='my#sys()',
            database='data'
        )
        return conn
    except mysql.connector.Error as err:
        print("Error connecting to MySQL:", err)
        return None

@app.route('/add_item', methods=['POST'])
@cross_origin(origins='*')  # Allow all origins for this specific route (for testing)
def add_item():
    data = request.form

    # Get item details from the form
    login_id = data.get('user_id')
    item_name = data.get('item_name')
    description = data.get('description')
    price = data.get('price')

    # Log the incoming request for debugging purposes
    print(f"Received data: user_id={login_id}, item_name={item_name}, description={description}, price={price}")

    # Check if all required fields are present
    if not item_name or not description or not price or not login_id:
        return jsonify({"message": "User ID, Item name, description, and price are required"}), 400

    try:
        price = float(price)
    except ValueError:
        return jsonify({"message": "Price must be a valid number"}), 400

    # Insert the new item into the database first (without the image)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO items (item_name, description, price, login_id) VALUES (%s, %s, %s, %s)", 
                   (item_name, description, price, login_id))
    conn.commit()

    # Get the last inserted item_id
    item_id = cursor.lastrowid

    # Handle image upload
    if 'image' not in request.files:
        return jsonify({"message": "No image file found"}), 400

    image = request.files['image']

    # Log the image information for debugging
    print(f"Received image: {image.filename}")

    # Check if the image has a valid extension
    if image and allowed_file(image.filename):
        # Secure the filename and create the file path
        filename = f"{item_id}.jpg"  # Rename image to item_id.jpg
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Create the 'images' folder if it does not exist
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        # Save the image with the new filename
        image.save(filepath)

        # Store the image path in the database
        image_path = f"/images/{filename}"

        # Update the item with the image path
        cursor.execute("UPDATE items SET image_path = %s WHERE item_id = %s", (image_path, item_id))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Item added successfully with image", "item_id": item_id}), 201
    else:
        return jsonify({"message": "Invalid image format. Only jpg, jpeg, or png allowed"}), 400

@app.route('/add_user', methods=['POST'])
@cross_origin(origins='*')  # Allow all origins for this specific route (for testing)
def add_user():
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error"}), 500

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM login WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user:
        cursor.close()
        conn.close()
        return jsonify({"message": "User already exists"}), 400

    cursor.execute("INSERT INTO login (username, password) VALUES (%s, %s)", (username, password))  # Store password as plain text
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "User added successfully"}), 201

@app.route('/items', methods=['GET'])
@cross_origin(origins='*')  # Allow all origins for this specific route (for testing)
def get_items():
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT item_id, item_name, description, price, login_id FROM items')
    items = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(items)

@app.route('/login', methods=['POST'])
@cross_origin(origins='*')  # Allow all origins for this specific route (for testing)
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
    cursor.execute("SELECT * FROM login WHERE username = %s", (username,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    # Compare the plain text password directly
    if user and user[2] == password:  # Compare the stored plain text password
        return jsonify({
            "message": "Login successful",
            "user_id": user[0]  # User ID from the database
        }), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@app.route('/item/<int:item_id>/image', methods=['GET'])
def get_item_image(item_id):
    # Generate the filename based on item_id
    image_filename = f"{item_id}.jpg"
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)

    # Check if the file exists in the directory
    if os.path.exists(image_path):
        # Send the image directly from the directory
        return send_from_directory(app.config['UPLOAD_FOLDER'], image_filename)
    else:
        return jsonify({"message": "Image not found"}), 404

if __name__ == '__main__':
    # Run the app using Waitress for production
    serve(app, host='0.0.0.0', port=5000)
