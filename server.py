from flask import Flask, render_template, request, redirect, url_for
import os
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
# set the port of the flask serveer
app.secret_key = os.urandom(24)

# Database setup
DB_PATH = 'kebab_orders.db'


def init_db():
    """Initialize the database with the necessary table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create orders table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kebab_type TEXT NOT NULL,
        meat TEXT NOT NULL,
        sauces TEXT,
        is_nature INTEGER,
        vegetables TEXT,
        timestamp DATETIME NOT NULL
    )
    ''')

    conn.commit()
    conn.close()


# Initialize database when application starts
init_db()

# Kebab options
kebab_types = ['Galette', 'Sandwich']
meat_options = ['Poulet', 'Boeuf&Veaux', 'Boeuf', 'Veaux', 'Vegetarian (Falafel)']
sauce_options = ['Blanche', 'Cocktail', 'Piquante']
vegetable_options = ['Salade melee', 'Carotte', 'Choux']


def get_recent_orders():
    """Get orders from the past 4 hours"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    cursor = conn.cursor()

    # Calculate timestamp for 4 hours ago
    four_hours_ago = (datetime.now() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")

    # Get orders from the past 4 hours
    cursor.execute('SELECT * FROM orders WHERE timestamp > ? ORDER BY timestamp DESC', (four_hours_ago,))
    rows = cursor.fetchall()

    # Process the rows into a list of dictionaries
    orders = []
    for row in rows:
        order = dict(row)

        # Convert sauces string to list
        if order['sauces']:
            order['sauces'] = order['sauces'].split(',')
        else:
            order['sauces'] = []

        # Convert vegetables string to list
        if order['vegetables'] and not order['is_nature']:
            order['vegetables'] = order['vegetables'].split(',')
        else:
            order['vegetables'] = []

        # Convert is_nature to boolean
        order['is_nature'] = bool(order['is_nature'])

        orders.append(order)

    conn.close()
    return orders


@app.route('/')
def index():
    # Get recent orders from the database
    orders = get_recent_orders()

    return render_template('index.html',
                           kebab_types=kebab_types,
                           meat_options=meat_options,
                           sauce_options=sauce_options,
                           vegetable_options=vegetable_options,
                           orders=orders)


@app.route('/delete/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Delete the order with the specified ID
    cursor.execute('DELETE FROM orders WHERE id = ?', (order_id,))

    conn.commit()
    conn.close()

    # Redirect back to the main page
    return redirect(url_for('index'))


@app.route('/order', methods=['POST'])
def place_order():
    if request.method == 'POST':
        name = request.form.get('name', 'Anonymous')
        kebab_type = request.form.get('kebab_type')
        meat = request.form.get('meat')
        sauces = request.form.getlist('sauces')  # Gets multiple selected values

        # Get veggie option
        veggie_option = request.form.get('veggie_option', 'nature')

        # Process vegetables
        if veggie_option == 'nature':
            vegetables = []
            is_nature = 1  # SQLite doesn't have a boolean type, use 1 for True
        elif veggie_option == 'all':
            # All vegetables selected
            vegetables = vegetable_options.copy()
            is_nature = 0
        else:
            # Custom vegetables selected
            is_nature = 0
            vegetables = request.form.getlist('vegetables')

        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Insert order into database
        cursor.execute('''
        INSERT INTO orders (name, kebab_type, meat, sauces, is_nature, vegetables, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            name,
            kebab_type,
            meat,
            ','.join(sauces) if sauces else '',
            is_nature,
            ','.join(vegetables) if vegetables else '',
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

        # Redirect back to the main page
        return redirect(url_for('index'))


# Create template directory
if not os.path.exists('templates'):
    os.makedirs('templates')

# Write the template file
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write('''
<!DOCTYPE html>
<html>
<head>
    <title>Kebab Order System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
        }
        h1, h2 {
            color: #333;
            text-align: center;
        }
        .container {
            display: flex;
            flex-wrap: wrap;
            width: 100%;
        }
        .order-form {
            flex: 1;
            min-width: 350px;
            background-color: #f9f9f9;
            padding: 20px;
            border-radius: 5px;
            margin: 0 15px;
        }
        .order-list {
            flex: 1;
            min-width: 350px;
            padding: 20px;
        }
        label {
            display: block;
            margin: 10px 0 5px;
            font-weight: bold;
        }
        input, select {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }
        button:hover {
            background-color: #45a049;
        }
        .order {
            background-color: #f9f9f9;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
            position: relative;
        }
        .order p {
            margin: 5px 0;
        }
        .delete-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: #f44336;
            color: white;
            border: none;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            text-align: center;
            cursor: pointer;
            font-weight: bold;
            font-size: 16px;
            padding: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .delete-btn:hover {
            background-color: #d32f2f;
        }
        .timestamp {
            color: #888;
            font-size: 0.8em;
        }
        .no-orders {
            color: #888;
            font-style: italic;
        }
        .sauce-options {
            display: flex;
            flex-direction: column;
        }
        .sauce-option {
            margin: 5px 0;
            display: flex;
            align-items: center;
        }
        .sauce-option input {
            width: auto;
            margin-right: 10px;
        }
        .sauce-option label {
            display: inline;
            margin: 0;
            font-weight: normal;
        }
        .radio-option {
            margin: 10px 0;
            display: flex;
            align-items: center;
        }
        .radio-option input {
            width: auto;
            margin-right: 10px;
        }
        .radio-option label {
            display: inline;
            margin: 0;
            font-weight: bold;
        }
        .option-group {
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }
        .group-header {
            margin-bottom: 10px;
            font-weight: bold;
        }
        .veggie-selections {
            margin-left: 30px;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 5px;
        }
        .veggie-checkbox {
            display: flex;
            align-items: center;
            margin: 5px 0;
        }
        .veggie-checkbox input {
            width: auto;
            margin-right: 10px;
        }
        .veggie-checkbox.disabled label {
            color: #999;
        }
        .db-status {
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9em;
        }
        .orders-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .time-info {
            font-size: 0.8em;
            color: #666;
            font-style: italic;
        }
        @media (max-width: 768px) {
            .container {
                flex-direction: column;
            }
            .order-form, .order-list {
                margin: 10px 0;
            }
        }
    </style>
</head>
<body>
    <h1>Kebab Order System</h1>

    <div class="container">
        <div class="order-form">
            <h2>Place Your Order</h2>
            <form action="/order" method="post">
                <div>
                    <label for="name">Your Name:</label>
                    <input type="text" id="name" name="name" required>
                </div>

                <div>
                    <label for="kebab_type">Kebab Type:</label>
                    <select id="kebab_type" name="kebab_type" required>
                        <option value="" disabled selected>Select kebab type</option>
                        {% for type in kebab_types %}
                        <option value="{{ type }}">{{ type }}</option>
                        {% endfor %}
                    </select>
                </div>

                <div>
                    <label for="meat">Meat Option:</label>
                    <select id="meat" name="meat" required>
                        <option value="" disabled selected>Select meat option</option>
                        {% for meat in meat_options %}
                        <option value="{{ meat }}">{{ meat }}</option>
                        {% endfor %}
                    </select>
                </div>

                <div class="option-group">
                    <div class="group-header">
                        <span>Vegetable Options:</span>
                    </div>

                    <div class="radio-option">
                        <input type="radio" id="nature" name="veggie_option" value="nature" checked onclick="handleVeggieOptions()">
                        <label for="nature">Nature (no vegetables)</label>
                    </div>

                    <div class="radio-option">
                        <input type="radio" id="all_veggies_option" name="veggie_option" value="all" onclick="handleVeggieOptions()">
                        <label for="all_veggies_option">All vegetables (Salade melee, Carotte, Choux)</label>
                    </div>

                    <div class="radio-option">
                        <input type="radio" id="custom_veggies" name="veggie_option" value="custom" onclick="handleVeggieOptions()">
                        <label for="custom_veggies">Custom vegetable selection:</label>
                    </div>

                    <div class="veggie-selections" id="veggieSelections">
                        {% for veggie in vegetable_options %}
                        <div class="veggie-checkbox">
                            <input type="checkbox" id="veggie_{{ veggie }}" name="vegetables" value="{{ veggie }}" disabled>
                            <label for="veggie_{{ veggie }}">{{ veggie }}</label>
                        </div>
                        {% endfor %}
                    </div>
                </div>

                <div>
                    <label>Sauces (select multiple):</label>
                    <div class="sauce-options">
                        {% for sauce in sauce_options %}
                        <div class="sauce-option">
                            <input type="checkbox" id="sauce_{{ sauce }}" name="sauces" value="{{ sauce }}">
                            <label for="sauce_{{ sauce }}">{{ sauce }}</label>
                        </div>
                        {% endfor %}
                    </div>
                </div>

                <button type="submit">Place Order</button>
            </form>
        </div>

        <div class="order-list">
            <div class="orders-header">
                <h2>Current Orders</h2>
                <span class="time-info">Showing orders from the past 4 hours</span>
            </div>

            {% if orders %}
                {% for order in orders %}
                <div class="order">
                    <form action="/delete/{{ order.id }}" method="post" onsubmit="return confirm('Are you sure you want to delete this order?');">
                        <button type="submit" class="delete-btn" title="Delete Order">×</button>
                    </form>
                    <p><strong>Name:</strong> {{ order.name }}</p>
                    <p><strong>Kebab Type:</strong> {{ order.kebab_type }}</p>
                    <p><strong>Meat:</strong> {{ order.meat }}</p>
                    <p><strong>Sauces:</strong> {{ ', '.join(order.sauces) if order.sauces else 'None' }}</p>
                    <p><strong>Vegetables:</strong> 
                        {% if order.is_nature %}
                            Nature (no vegetables)
                        {% else %}
                            {{ ', '.join(order.vegetables) if order.vegetables else 'None selected' }}
                        {% endif %}
                    </p>
                    <p class="timestamp">Ordered at: {{ order.timestamp }}</p>
                </div>
                {% endfor %}
            {% else %}
                <p class="no-orders">No orders have been placed in the last 4 hours.</p>
            {% endif %}
        </div>
    </div>

    <div class="db-status">
        <p>Orders are stored in SQLite database: kebab_orders.db</p>
    </div>

    <script>
        function handleVeggieOptions() {
            // Get radio buttons and checkboxes
            var natureRadio = document.getElementById('nature');
            var allVeggiesRadio = document.getElementById('all_veggies_option');
            var customVeggiesRadio = document.getElementById('custom_veggies');
            var veggieCheckboxes = document.querySelectorAll('input[name="vegetables"]');

            // Enable or disable checkboxes based on selection
            if (customVeggiesRadio.checked) {
                // Enable checkboxes for custom selection
                veggieCheckboxes.forEach(function(checkbox) {
                    checkbox.disabled = false;
                });
            } else {
                // Disable and uncheck when not using custom selection
                veggieCheckboxes.forEach(function(checkbox) {
                    checkbox.disabled = true;
                    checkbox.checked = false;
                });
            }
        }

        // Initialize the form when page loads
        document.addEventListener('DOMContentLoaded', function() {
            handleVeggieOptions();
            console.log("Form initialized");
        });
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    print("Kebab Order System is running!")
    print("Open http://127.0.0.1:41586/ in your browser")
    app.run(debug=True, host="0.0.0.0", port = 41586)