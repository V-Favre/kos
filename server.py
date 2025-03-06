from flask import Flask, render_template, request, redirect, url_for, session, Response
import os
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
# set the port of the flask server
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


def get_order_by_id(order_id):
    """Get a specific order by ID"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    row = cursor.fetchone()

    if row:
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

        conn.close()
        return order

    conn.close()
    return None


def generate_text_summary(orders):
    """Generate a text summary of orders for phone ordering"""
    if not orders:
        return "No orders to summarize."

    summary = "KEBAB ORDERS:"

    for i, order in enumerate(orders, 1):
        # Get vegetables text
        if order['is_nature']:
            veg_text = "Nature"
        else:
            veg_text = ', '.join(order['vegetables']) if order['vegetables'] else "None"

        # Get sauces text
        sauce_text = ', '.join(order['sauces']) if order['sauces'] else "None"

        # Format each order on a single line without customer name and with minimal spacing
        summary += f"\n{i}. Kebab {order['kebab_type']} {order['meat']} {veg_text} {sauce_text}"

    return summary


@app.route('/')
def index():
    # Get recent orders from the database
    orders = get_recent_orders()

    # Check if we're in edit mode
    edit_order = None
    if 'edit_order_id' in session:
        edit_order = get_order_by_id(session['edit_order_id'])
        # Clear the session after retrieving the order
        session.pop('edit_order_id', None)

    return render_template('index.html',
                           kebab_types=kebab_types,
                           meat_options=meat_options,
                           sauce_options=sauce_options,
                           vegetable_options=vegetable_options,
                           orders=orders,
                           edit_order=edit_order)


@app.route('/view_text_summary')
def view_text_summary():
    # Get recent orders
    orders = get_recent_orders()

    # Generate the text summary
    summary = generate_text_summary(orders)

    # Return as plain text for viewing in browser
    return Response(summary, mimetype="text/plain")


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


@app.route('/edit/<int:order_id>', methods=['POST'])
def edit_order(order_id):
    # Store the order ID in session for retrieval on the main page
    session['edit_order_id'] = order_id

    # Redirect back to the main page with the edit_order_id in the session
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

        # Check if this is an update or a new order
        order_id = request.form.get('order_id', None)

        if order_id:
            # Update existing order
            cursor.execute('''
            UPDATE orders 
            SET name = ?, kebab_type = ?, meat = ?, sauces = ?, 
                is_nature = ?, vegetables = ?
            WHERE id = ?
            ''', (
                name,
                kebab_type,
                meat,
                ','.join(sauces) if sauces else '',
                is_nature,
                ','.join(vegetables) if vegetables else '',
                order_id
            ))
        else:
            # Insert new order
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
        .edit-btn {
            position: absolute;
            top: 10px;
            right: 50px;
            background-color: #2196F3;
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
        .edit-btn:hover {
            background-color: #0b7dda;
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
        .form-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .cancel-edit {
            background-color: #f44336;
            color: white;
            padding: 5px 10px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
        }
        .cancel-edit:hover {
            background-color: #d32f2f;
        }
        .hidden {
            display: none;
        }
        .summary-container {
            background-color: #f5f5f5;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 4px solid #009688;
            white-space: pre-line;
            font-family: monospace;
            font-size: 14px;
            line-height: 1.2;
        }
        .summary-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 5px;
        }
        .summary-title {
            font-weight: bold;
            color: #009688;
        }
        .refresh-btn {
            background-color: #009688;
            color: white;
            padding: 5px 10px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            text-decoration: none;
        }
        .refresh-btn:hover {
            background-color: #00796B;
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
            <div class="form-header">
                <h2 id="formTitle">Place Your Order</h2>
                <a href="/" id="cancelEdit" class="cancel-edit hidden">Cancel Edit</a>
            </div>

            <form action="/order" method="post" id="orderForm">
                <!-- Hidden field for order ID when editing -->
                <input type="hidden" id="order_id" name="order_id" value="">

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

                <button type="submit" id="submitButton">Place Order</button>
            </form>
        </div>

        <div class="order-list">
            <div class="orders-header">
                <h2>Current Orders</h2>
                <span class="time-info">Showing orders from the past 4 hours</span>
            </div>

            <div class="summary-container">
                <div class="summary-header">
                    <span class="summary-title">Order Summary for Phone:</span>
                    <a href="#" onclick="refreshSummary(); return false;" class="refresh-btn">Refresh</a>
                </div>
                <div id="summaryText">Loading summary...</div>
            </div>

            {% if orders %}
                {% for order in orders %}
                <div class="order">
                    <form action="/delete/{{ order.id }}" method="post" onsubmit="return confirm('Are you sure you want to delete this order?');">
                        <button type="submit" class="delete-btn" title="Delete Order">×</button>
                    </form>

                    <form action="/edit/{{ order.id }}" method="post">
                        <button type="submit" class="edit-btn" title="Edit Order">✎</button>
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

        // Function to fill the form with order data for editing
        function setupEditMode(order) {
            if (!order) return;

            // Update form title and button text
            document.getElementById('formTitle').textContent = 'Edit Your Order';
            document.getElementById('submitButton').textContent = 'Update Order';
            document.getElementById('cancelEdit').classList.remove('hidden');

            // Fill in the form fields
            document.getElementById('order_id').value = order.id;
            document.getElementById('name').value = order.name;
            document.getElementById('kebab_type').value = order.kebab_type;
            document.getElementById('meat').value = order.meat;

            // Handle vegetable options
            if (order.is_nature) {
                document.getElementById('nature').checked = true;
            } else if (order.vegetables.length === {{ vegetable_options|length }}) {
                document.getElementById('all_veggies_option').checked = true;
            } else {
                document.getElementById('custom_veggies').checked = true;
                // Check the appropriate vegetables
                order.vegetables.forEach(function(veggie) {
                    const veggieCheckbox = document.getElementById('veggie_' + veggie);
                    if (veggieCheckbox) {
                        veggieCheckbox.checked = true;
                    }
                });
            }

            // Handle veggie options after setting the radio buttons
            handleVeggieOptions();

            // Check the appropriate sauces
            order.sauces.forEach(function(sauce) {
                const sauceCheckbox = document.getElementById('sauce_' + sauce);
                if (sauceCheckbox) {
                    sauceCheckbox.checked = true;
                }
            });

            // Scroll to the top of the form
            document.querySelector('.order-form').scrollIntoView({behavior: 'smooth'});
        }

        // Function to fetch and update the text summary
        function refreshSummary() {
            fetch('/view_text_summary')
                .then(response => response.text())
                .then(text => {
                    document.getElementById('summaryText').textContent = text;
                })
                .catch(error => {
                    console.error('Error fetching summary:', error);
                    document.getElementById('summaryText').textContent = 'Error loading summary. Please try again.';
                });
        }

        // Initialize the form when page loads
        document.addEventListener('DOMContentLoaded', function() {
            handleVeggieOptions();

            // Load the initial summary
            refreshSummary();

            // Check if we have an edit order
            {% if edit_order %}
                setupEditMode({{ edit_order|tojson }});
            {% endif %}
        });
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    print("Kebab Order System is running!")
    print("Open http://127.0.0.1:55846/ in your browser")
    app.run(debug=True, host="0.0.0.0", port=41586)