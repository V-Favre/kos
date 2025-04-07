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

    # Check if konami code was activated via a query parameter (for demonstration)
    # This is a workaround since we can't directly communicate JS state to Python
    # In a real app, you might use a session variable or other state management
    konami_active = False

    # Create a dictionary to count identical orders
    order_counts = {}
    total_kebabs = 0

    # First, collect all orders in a format that can be counted
    for order in orders:
        # Get vegetables text
        if order['is_nature']:
            veg_text = "Nature"
        else:
            veg_text = ', '.join(order['vegetables']) if order['vegetables'] else "None"

        # Get sauces text with Konami code transformation if active
        sauces = []
        for sauce in order['sauces']:
            if konami_active and sauce == 'Blanche':
                sauces.append('Planche')
            elif konami_active and sauce == 'Cocktail':
                sauces.append('Coque-tel')
            else:
                sauces.append(sauce)

        sauce_text = ', '.join(sauces) if sauces else "None"

        # Create a unique key for this order configuration
        order_key = f"Kebab {order['kebab_type']} {order['meat']} {veg_text} {sauce_text}"

        # Increment the count for this order configuration
        if order_key in order_counts:
            order_counts[order_key] += 1
        else:
            order_counts[order_key] = 1

        total_kebabs += 1

    # Generate the header with total count
    summary = f"KEBAB ORDERS: (TOTAL: {total_kebabs})"

    # Now generate the summary with counts
    for order_key, count in order_counts.items():
        # If there's more than one identical order, add the count at the beginning
        if count > 1:
            summary += f"\n*{count} {order_key}"
        else:
            summary += f"\n{order_key}"

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
        .spinning-wheel-link {
            margin: 15px 0;
            text-align: center;
        }
        .wheel-link-btn {
            background-color: #ff9800;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            text-decoration: none;
            display: inline-block;
            font-weight: bold;
            transition: background-color 0.3s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .wheel-link-btn:hover {
            background-color: #f57c00;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
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
            <div class="spinning-wheel-link">
                <a href="/spinning_wheel" class="wheel-link-btn">
                    <span style="margin-right: 5px;">🎡</span> Spin the Wheel
                </a>
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

        // Konami Code implementation
        const konamiCode = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
        let konamiIndex = 0;
        let konamiActivated = false;

        document.addEventListener('keydown', function(e) {
            // Check if the key matches the expected key in the Konami sequence
            if (e.key === konamiCode[konamiIndex]) {
                konamiIndex++;

                // If we've reached the end of the sequence
                if (konamiIndex === konamiCode.length) {
                    konamiActivated = !konamiActivated;
                    konamiIndex = 0;

                    // Apply the sauce name changes
                    updateSauceLabels();

                    // Easter egg notification
                    alert(konamiActivated ? 'Easter Egg Activated! Sauces renamed.' : 'Easter Egg Deactivated! Sauces restored.');
                }
            } else {
                // Reset if the sequence is broken
                konamiIndex = 0;
            }
        });

        // Function to update sauce labels based on Konami code status
        function updateSauceLabels() {
            // Get all sauce labels
            const sauceLabels = document.querySelectorAll('.sauce-option label');
            const sauceInputs = document.querySelectorAll('.sauce-option input');

            sauceLabels.forEach((label, index) => {
                const input = sauceInputs[index];
                const originalValue = input.value;

                if (originalValue === 'Blanche') {
                    label.textContent = konamiActivated ? 'Planche' : 'Blanche';
                    // We don't change the value to maintain database consistency
                } else if (originalValue === 'Cocktail') {
                    label.textContent = konamiActivated ? 'Coque-tel' : 'Cocktail';
                }
            });

            // Also update the summary to reflect the changes
            refreshSummary();
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


@app.route('/spinning_wheel')
def spinning_wheel():
    """Show a spinning wheel to randomly select a customer from orders"""
    # Get recent orders from the database
    orders = get_recent_orders()

    # Extract unique customer names
    customer_names = []
    for order in orders:
        if order['name'] not in customer_names and order['name'] != 'Anonymous':
            customer_names.append(order['name'])

    # If no names, add a placeholder
    if not customer_names:
        customer_names = ['No customers found']

    return render_template('spinning_wheel.html', customer_names=customer_names)


# Create a new template file for the spinning wheel
with open('templates/spinning_wheel.html', 'w', encoding='utf-8') as f:
    f.write('''
<!DOCTYPE html>
<html>
<head>
    <title>Kebab Order - Random Customer Selector</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1, h2 {
            color: #333;
            text-align: center;
        }
        .container {
            width: 100%;
            max-width: 600px;
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-top: 20px;
        }
        .wheel-container {
            position: relative;
            width: 400px;
            height: 400px;
            margin: 20px auto;
        }
        .wheel {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            position: relative;
            overflow: hidden;
            box-shadow: 0 0 10px rgba(0,0,0,0.3);
        }
        .pointer {
            position: absolute;
            top: -10px;
            left: 50%;
            transform: translateX(-50%);
            width: 0;
            height: 0;
            border-left: 20px solid transparent;
            border-right: 20px solid transparent;
            border-top: 40px solid #d32f2f;
            z-index: 10;
        }
        .spin-button {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 18px;
            cursor: pointer;
            border-radius: 5px;
            margin-top: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }
        .spin-button:hover {
            background-color: #45a049;
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(0,0,0,0.15);
        }
        .spin-button:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        .winner-display {
            margin-top: 30px;
            padding: 20px;
            border-radius: 10px;
            background-color: #fff;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            text-align: center;
            opacity: 0;
            transition: all 0.5s;
            transform: scale(0.95);
            max-width: 500px;
            width: 100%;
            border: 3px dashed #FF9800;
        }
        .winner-display.show {
            opacity: 1;
            transform: scale(1);
        }
        .winner-title {
            font-size: 24px;
            color: #FF9800;
            margin-bottom: 10px;
            font-weight: bold;
        }
        .winner-name {
            font-size: 28px;
            font-weight: bold;
            color: #E91E63;
            margin-bottom: 15px;
        }
        .winner-message {
            font-size: 16px;
            color: #555;
            line-height: 1.5;
            margin-bottom: 15px;
        }
        .winner-phone {
            font-size: 20px;
            font-weight: bold;
            color: #673AB7;
            margin-top: 10px;
            padding: 5px;
            border-radius: 5px;
            background-color: #f3e5f5;
            display: inline-block;
        }
        .winner-emoji {
            font-size: 30px;
            margin: 5px;
        }
        .confetti {
            position: fixed;
            width: 10px;
            height: 10px;
            background-color: #f00;
            pointer-events: none;
            opacity: 0;
        }
        .back-button {
            background-color: #2196F3;
            color: white;
            border: none;
            padding: 10px 20px;
            font-size: 16px;
            cursor: pointer;
            border-radius: 5px;
            margin-top: 20px;
            text-decoration: none;
            display: inline-block;
        }
        .back-button:hover {
            background-color: #0b7dda;
        }
        .subsections-control {
            margin-top: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .subsections-control label {
            font-weight: bold;
        }
        .subsections-control select {
            padding: 5px;
            border-radius: 4px;
            border: 1px solid #ccc;
        }
    </style>
</head>
<body>
    <h1>Kebab Order Random Selector</h1>

    <div class="container">
        <div class="wheel-container">
            <div class="pointer"></div>
            <div class="wheel" id="wheel">
                <!-- Wheel will be created with canvas -->
            </div>
        </div>

        <div class="subsections-control">
            <label for="subsectionsPerUser">Subsections per user:</label>
            <select id="subsectionsPerUser">
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3" selected>3</option>
                <option value="4">4</option>
                <option value="5">5</option>
            </select>
            <button id="updateWheel" style="padding: 5px 10px; background: #666; color: white; border: none; border-radius: 4px; cursor: pointer;">Update Wheel</button>
        </div>

        <button id="spinButton" class="spin-button">SPIN THE WHEEL</button>

        <div id="winnerDisplay" class="winner-display">
            <!-- Winner will be displayed here -->
        </div>

        <a href="/" class="back-button">Back to Orders</a>
    </div>

    <script>
        // Customer names from server
        const customerNames = {{ customer_names|tojson }};

        // Wheel configuration
        const wheel = document.getElementById('wheel');
        const spinButton = document.getElementById('spinButton');
        const winnerDisplay = document.getElementById('winnerDisplay');
        const subsectionsSelect = document.getElementById('subsectionsPerUser');
        const updateWheelButton = document.getElementById('updateWheel');

        let isSpinning = false;
        let subsectionsPerUser = 3; // Default to 3 subsections per user
        let wheelCanvas; // Reference to canvas
        let currentRotation = 0; // Current rotation angle in degrees

        // Colors for the wheel sections - one color per user (more professional and vibrant palette)
        const userColors = [
            '#3498DB', '#2ECC71', '#9B59B6', '#F1C40F', 
            '#E74C3C', '#1ABC9C', '#34495E', '#F39C12',
            '#16A085', '#27AE60', '#8E44AD', '#D35400',
            '#2980B9', '#C0392B', '#7D3C98', '#2574A9'
        ];

        // Generate wheel sections with canvas
        function generateWheel() {
            wheel.innerHTML = '';

            const numUsers = customerNames.length;
            const totalSegments = numUsers * subsectionsPerUser;
            const anglePerSegment = (2 * Math.PI) / totalSegments;
            const radius = 200; // Radius of the wheel (400px/2)

            // Create canvas for the wheel
            wheelCanvas = document.createElement('canvas');
            wheelCanvas.width = 400;
            wheelCanvas.height = 400;
            wheel.appendChild(wheelCanvas);

            // Apply current rotation
            wheel.style.transform = `rotate(${currentRotation}deg)`;

            const ctx = wheelCanvas.getContext('2d');
            const centerX = wheelCanvas.width / 2;
            const centerY = wheelCanvas.height / 2;

            // For each user, create their subsections
            for (let userIndex = 0; userIndex < numUsers; userIndex++) {
                const userName = customerNames[userIndex];
                const userColor = userColors[userIndex % userColors.length];

                // Create subsections for this user
                for (let subIndex = 0; subIndex < subsectionsPerUser; subIndex++) {
                    // Calculate the segment index in the wheel
                    // We want to distribute user subsections evenly around the wheel
                    // instead of grouping them together
                    const segmentIndex = (subIndex * numUsers) + userIndex;
                    const startAngle = segmentIndex * anglePerSegment;
                    const endAngle = startAngle + anglePerSegment;

                    // Draw pie segment
                    ctx.beginPath();
                    ctx.moveTo(centerX, centerY);
                    ctx.arc(centerX, centerY, radius, startAngle, endAngle);
                    ctx.closePath();

                    // Fill with user's color (same for all subsections)
                    ctx.fillStyle = userColor;
                    ctx.fill();

                    // Add border
                    ctx.lineWidth = 1.5;
                    ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
                    ctx.stroke();

                    // Add name label to EVERY subsection
                    const middleAngle = startAngle + (anglePerSegment / 2);
                    const labelDistance = radius * 0.7; // Place text at 70% of radius

                    const labelX = centerX + Math.cos(middleAngle) * labelDistance;
                    const labelY = centerY + Math.sin(middleAngle) * labelDistance;

                    // Save context state
                    ctx.save();

                    // Position and rotate text
                    ctx.translate(labelX, labelY);
                    ctx.rotate(middleAngle + Math.PI/2);

                    // Draw text
                    ctx.textAlign = 'center';
                    ctx.fillStyle = '#333';
                    ctx.font = 'bold 12px Arial';

                    // Add a white text shadow for better readability
                    ctx.shadowColor = 'white';
                    ctx.shadowBlur = 3;
                    ctx.shadowOffsetX = 0;
                    ctx.shadowOffsetY = 0;

                    // Make sure text fits in the segment
                    const maxTextWidth = radius * 0.4;
                    ctx.fillText(userName, 0, 0, maxTextWidth);

                    // Restore context
                    ctx.restore();
                }
            }
        }

        // Animate the wheel using requestAnimationFrame for smoother performance
        function animateWheel(startTime, duration, startAngle, targetAngle) {
            const now = performance.now();
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function - slow down towards the end
            const easeOut = function(t) {
                return 1 - Math.pow(1 - t, 3);
            };

            // Calculate current angle
            const easedProgress = easeOut(progress);
            const currentAngle = startAngle + (targetAngle - startAngle) * easedProgress;

            // Apply rotation
            wheel.style.transform = `rotate(${currentAngle}deg)`;

            // Continue animation if not complete
            if (progress < 1) {
                requestAnimationFrame(() => animateWheel(startTime, duration, startAngle, targetAngle));
            } else {
                // Animation complete
                currentRotation = currentAngle % 360; // Store the current rotation (0-359)

                // Calculate which user will be the winner
                const numUsers = customerNames.length;
                const totalSegments = numUsers * subsectionsPerUser;
                const degreesPerSegment = 360 / totalSegments;

                // The wheel rotates clockwise, but the actual position is counterclockwise from the starting point
                const finalPosition = currentRotation;

                // The pointer is at top (0 degrees), so we need to determine which segment that points to
                // Since the wheel rotates clockwise, we need to convert to the correct index
                const segmentIndex = Math.floor(((360 - finalPosition) % 360) / degreesPerSegment) % totalSegments;

                // Convert segment index to user index
                const userIndex = segmentIndex % numUsers;

                // Show winner with fun display
                const winner = customerNames[userIndex];
                winnerDisplay.innerHTML = `
                    <div class="winner-emoji">🎉 🌯 🎊</div>
                    <div class="winner-title">JACKPOT!</div>
                    <div class="winner-name">${winner}</div>
                    <div class="winner-message">Tu dois appeler le meilleur kebab de la région!</div>
                    <div class="winner-phone">+41 22 341 35 90</div>
                    <div class="winner-emoji">🍗 🥙 🔥</div>
                `;
                winnerDisplay.classList.add('show');
                createConfetti();

                // Re-enable spin button
                setTimeout(() => {
                    isSpinning = false;
                    spinButton.disabled = false;
                }, 1000);
            }
        }

        // Spin the wheel
        function spinWheel() {
            if (isSpinning) return;

            isSpinning = true;
            spinButton.disabled = true;
            winnerDisplay.classList.remove('show');

            // Start angle is the current rotation
            const startAngle = currentRotation;

            // Calculate target angle - at least 5 full rotations + random extra
            const minRotations = 5;
            const randomExtraRotations = 2 + Math.random() * 3;
            const totalRotations = minRotations + randomExtraRotations;

            // Random final position (0-359 degrees)
            const randomFinalPosition = Math.floor(Math.random() * 360);

            // Calculate the total target angle
            const targetAngle = startAngle + (totalRotations * 360) + randomFinalPosition;

            // Animation duration between 4 and 7 seconds
            const duration = 4000 + Math.random() * 3000;

            // Start the animation
            animateWheel(performance.now(), duration, startAngle, targetAngle);
        }

        // Create confetti effect
        function createConfetti() {
            const confettiColors = ['#f00', '#0f0', '#00f', '#ff0', '#f0f', '#0ff'];
            const confettiCount = 150;

            for (let i = 0; i < confettiCount; i++) {
                const confetti = document.createElement('div');
                confetti.className = 'confetti';

                // Random position
                const startX = Math.random() * window.innerWidth;
                const startY = -20;

                // Random color
                const color = confettiColors[Math.floor(Math.random() * confettiColors.length)];

                // Set styles
                confetti.style.left = `${startX}px`;
                confetti.style.top = `${startY}px`;
                confetti.style.backgroundColor = color;
                confetti.style.opacity = '1';

                // Randomize size and shape
                const size = 5 + Math.random() * 10;
                confetti.style.width = `${size}px`;
                confetti.style.height = `${size}px`;

                // Occasionally make rectangle confetti
                if (Math.random() > 0.5) {
                    confetti.style.width = `${size * 0.5}px`;
                    confetti.style.height = `${size * 1.5}px`;
                }

                // Occasionally make round confetti
                if (Math.random() > 0.7) {
                    confetti.style.borderRadius = '50%';
                }

                // Add to body
                document.body.appendChild(confetti);

                // Animate falling
                const animationDuration = 2 + Math.random() * 4;
                const fallDistance = window.innerHeight + 100;
                const horizontalSwing = (Math.random() - 0.5) * 300;

                confetti.animate([
                    { transform: 'translate(0px, 0px) rotate(0deg)' },
                    { transform: `translate(${horizontalSwing}px, ${fallDistance}px) rotate(${Math.random() * 720}deg)` }
                ], {
                    duration: animationDuration * 1000,
                    easing: 'cubic-bezier(0.4, 0.0, 0.2, 1)'
                });

                // Remove after animation
                setTimeout(() => {
                    if (document.body.contains(confetti)) {
                        document.body.removeChild(confetti);
                    }
                }, animationDuration * 1000);
            }
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            // Set default subsections
            subsectionsSelect.value = subsectionsPerUser.toString();

            // Generate initial wheel
            generateWheel();

            // Event listeners
            spinButton.addEventListener('click', spinWheel);

            updateWheelButton.addEventListener('click', function() {
                subsectionsPerUser = parseInt(subsectionsSelect.value);
                generateWheel();
            });
        });
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    print("Kebab Order System is running!")
    print("Open http://127.0.0.1:41586/ in your browser")
    app.run(debug=True, host="0.0.0.0", port=41586)