import os
import sys
import threading
import time
import webbrowser
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    db_path = os.path.join(os.path.dirname(sys.executable), 'database.db')
    upload_folder = os.path.join(os.path.dirname(sys.executable), 'uploads')
else:
    template_folder = 'templates'
    db_path = 'database.db'
    upload_folder = 'uploads'

if not os.path.exists(upload_folder):
    os.makedirs(upload_folder)

app = Flask(__name__, template_folder=template_folder)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = upload_folder

db = SQLAlchemy(app)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False) # 'resin', 'filament', 'consumables', 'packaging', 'services'

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'type': self.type}

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    unit_type = db.Column(db.String(20), nullable=False) # 'weight' or 'piece'
    unit_total = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock_current = db.Column(db.Float, nullable=False)

    category = db.relationship('Category', backref='items')

    def to_dict(self):
        return {
            'id': self.id, 'category_id': self.category_id, 'name': self.name,
            'unit_type': self.unit_type, 'unit_total': self.unit_total,
            'price': self.price, 'stock_current': self.stock_current,
            'type': self.category.type if self.category else ''
        }

class Printer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    power = db.Column(db.Float, nullable=False) # Power in Watts
    cost = db.Column(db.Float, nullable=False) # Cost of printer
    resource = db.Column(db.Float, nullable=False) # Depreciation resource in hours

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'power': self.power,
            'cost': self.cost,
            'resource': self.resource
        }

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    inn = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    orders = db.relationship('Order', backref='client', lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'phone': self.phone,
            'email': self.email, 'inn': self.inn, 'address': self.address,
            'notes': self.notes
        }

class CalculationDraft(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    payload = db.Column(db.Text, nullable=False) # JSON
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'payload': self.payload, 'created_at': self.created_at}

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Согласование")
    price = db.Column(db.Float, nullable=False) # Final Client Price
    cost = db.Column(db.Float, nullable=False) # Total Self Cost
    printer_id = db.Column(db.Integer, db.ForeignKey('printer.id'), nullable=True)
    print_hours = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Integer, default=1)
    file_path = db.Column(db.String(255), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    draft_id = db.Column(db.Integer, db.ForeignKey('calculation_draft.id'), nullable=True)
    discount_type = db.Column(db.String(20), nullable=True) # 'percent', 'absolute'
    discount_value = db.Column(db.Float, default=0.0)
    acquiring_applied = db.Column(db.Boolean, default=False)

    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        printer_name = Printer.query.get(self.printer_id).name if self.printer_id else None
        client_name = self.client.name if self.client_id else None
        return {
            'id': self.id, 'order_number': self.order_number, 'name': self.name,
            'description': self.description, 'status': self.status, 'price': self.price,
            'cost': self.cost, 'printer_id': self.printer_id, 'print_hours': self.print_hours,
            'printer_name': printer_name, 'quantity': self.quantity, 'file_path': self.file_path,
            'client_id': self.client_id, 'client_name': client_name,
            'draft_id': self.draft_id, 'discount_type': self.discount_type,
            'discount_value': self.discount_value, 'acquiring_applied': self.acquiring_applied,
            'items': [i.to_dict() for i in self.items]
        }

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    usage_amount = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {'id': self.id, 'order_id': self.order_id, 'inventory_id': self.inventory_id, 'usage_amount': self.usage_amount}

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    electricity_rate = db.Column(db.Float, nullable=False, default=5.0)
    markup_percent = db.Column(db.Float, nullable=False, default=100.0)
    failure_percent = db.Column(db.Float, nullable=False, default=10.0)
    tax_percent = db.Column(db.Float, nullable=False, default=4.0)
    seller_name = db.Column(db.String(200), nullable=True)
    seller_inn = db.Column(db.String(20), nullable=True)
    seller_bank = db.Column(db.String(200), nullable=True)
    seller_account = db.Column(db.String(50), nullable=True)
    seller_bik = db.Column(db.String(20), nullable=True)

    operator_rate_per_hour = db.Column(db.Float, nullable=False, default=500.0)
    acquiring_fee_percent = db.Column(db.Float, nullable=False, default=3.0)
    base_tax_percent = db.Column(db.Float, nullable=False, default=6.0)

    def to_dict(self):
        return {
            'id': self.id, 'electricity_rate': self.electricity_rate,
            'markup_percent': self.markup_percent, 'failure_percent': self.failure_percent,
            'tax_percent': self.tax_percent, 'seller_name': self.seller_name,
            'seller_inn': self.seller_inn, 'seller_bank': self.seller_bank,
            'seller_account': self.seller_account, 'seller_bik': self.seller_bik,
            'operator_rate_per_hour': self.operator_rate_per_hour,
            'acquiring_fee_percent': self.acquiring_fee_percent,
            'base_tax_percent': self.base_tax_percent
        }

# Initialize database
with app.app_context():
    db.create_all()
    # Add default setting if not exists
    if not Settings.query.first():
        default_settings = Settings(
            electricity_rate=5.0, markup_percent=100.0, failure_percent=10.0, tax_percent=4.0,
            operator_rate_per_hour=500.0, acquiring_fee_percent=3.0, base_tax_percent=6.0
        )
        db.session.add(default_settings)
        db.session.commit()

    # Initialize basic categories if not exists
    if not Category.query.first():
        for t in ['resin', 'filament', 'consumables', 'packaging', 'services']:
            db.session.add(Category(name=t.capitalize(), type=t))
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

# --- CRUD for Materials ---




# --- CRUD for Printers ---
@app.route('/api/printers', methods=['GET'])
def get_printers():
    printers = Printer.query.all()
    return jsonify([p.to_dict() for p in printers])

@app.route('/api/printers', methods=['POST'])
def add_printer():
    data = request.json
    new_printer = Printer(
        name=data['name'],
        power=float(data['power']),
        cost=float(data['cost']),
        resource=float(data['resource'])
    )
    db.session.add(new_printer)
    db.session.commit()
    return jsonify(new_printer.to_dict()), 201

@app.route('/api/printers/<int:id>', methods=['DELETE'])
def delete_printer(id):
    printer = Printer.query.get_or_404(id)
    db.session.delete(printer)
    db.session.commit()
    return '', 204

# --- CRUD for Orders ---
@app.route('/api/orders', methods=['GET'])
def get_orders():
    orders = Order.query.all()
    return jsonify([o.to_dict() for o in orders])

@app.route('/api/clients', methods=['GET'])
def get_clients():
    clients = Client.query.all()
    return jsonify([c.to_dict() for c in clients])

@app.route('/api/clients', methods=['POST'])
def add_client():
    data = request.json
    new_client = Client(
        name=data['name'],
        phone=data.get('phone', ''),
        email=data.get('email', ''),
        inn=data.get('inn', ''),
        address=data.get('address', ''),
        notes=data.get('notes', '')
    )
    db.session.add(new_client)
    db.session.commit()
    return jsonify(new_client.to_dict()), 201

@app.route('/api/clients/<int:id>', methods=['PUT'])
def edit_client(id):
    client = Client.query.get_or_404(id)
    data = request.json
    if 'name' in data:
        client.name = data['name']
    if 'phone' in data:
        client.phone = data['phone']
    if 'email' in data:
        client.email = data['email']
    if 'inn' in data:
        client.inn = data['inn']
    if 'address' in data:
        client.address = data['address']
    if 'notes' in data:
        client.notes = data['notes']

    db.session.commit()
    return jsonify(client.to_dict())

@app.route('/api/clients/<int:id>', methods=['DELETE'])
def delete_client(id):
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    return '', 204


@app.route('/api/orders', methods=['POST'])
def add_order():
    data = request.form

    file_path = None
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            file_path = filename

    client_id = data.get('client_id')
    if client_id == 'new':
        if data.get('new_client_name'):
            new_client = Client(
                name=data.get('new_client_name'),
                phone=data.get('new_client_phone', ''),
                email=data.get('new_client_email', ''),
                inn=data.get('new_client_inn', ''),
                address=data.get('new_client_address', ''),
                notes=data.get('new_client_notes', '')
            )
            db.session.add(new_client)
            db.session.flush()
            client_id = new_client.id
        else:
            client_id = None
    elif client_id:
        client_id = int(client_id)
    else:
        client_id = None

    last_order = Order.query.order_by(Order.id.desc()).first()
    next_num = last_order.id + 1 if last_order else 1
    order_number = f"{next_num:04d}"

    new_order = Order(
        order_number=order_number,
        name=data['name'],
        description=data.get('description', ''),
        status=data.get('status', 'Согласование'),
        price=float(data['price']),
        cost=float(data['cost']),
        printer_id=int(data.get('printer_id')) if data.get('printer_id') else None,
        print_hours=float(data.get('print_hours', 0.0)),
        quantity=int(data.get('quantity', 1)),
        file_path=file_path,
        client_id=client_id,
        draft_id=int(data.get('draft_id')) if data.get('draft_id') else None,
        discount_type=data.get('discount_type'),
        discount_value=float(data.get('discount_value', 0.0)),
        acquiring_applied=data.get('acquiring_applied', 'false').lower() == 'true'
    )
    db.session.add(new_order)
    db.session.flush() # get order ID

    import json
    items_json = data.get('items', '[]')
    try:
        items = json.loads(items_json)
        for item in items:
            new_item = OrderItem(
                order_id=new_order.id,
                inventory_id=int(item['inventory_id']),
                usage_amount=float(item['usage_amount'])
            )
            db.session.add(new_item)
    except:
        pass

    db.session.commit()
    return jsonify(new_order.to_dict()), 201

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/orders/<int:id>', methods=['DELETE'])
def delete_order(id):
    order = Order.query.get_or_404(id)
    db.session.delete(order)
    db.session.commit()
    return '', 204

@app.route('/api/orders/<int:id>/status', methods=['POST'])
def update_order_status(id):
    data = request.json
    order = Order.query.get_or_404(id)
    new_status = data.get('status')

    if new_status:
        if new_status == "Готов" and order.status != "Готов":
            for item in order.items:
                inv_item = InventoryItem.query.get(item.inventory_id)
                if inv_item:
                    # Deduct the usage from the total current stock multiplied by quantity
                    inv_item.stock_current -= (item.usage_amount * order.quantity)
                    if inv_item.stock_current < 0:
                        inv_item.stock_current = 0

        order.status = new_status
        db.session.commit()
        return jsonify(order.to_dict())
    return jsonify({'error': 'No status provided'}), 400

# --- Categories & Inventory ---
@app.route('/api/categories', methods=['GET'])
def get_categories():
    categories = Category.query.all()
    return jsonify([c.to_dict() for c in categories])

@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.json
    new_cat = Category(
        name=data['name'],
        type=data['type']
    )
    db.session.add(new_cat)
    db.session.commit()
    return jsonify(new_cat.to_dict()), 201

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    items = InventoryItem.query.all()
    return jsonify([i.to_dict() for i in items])

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.json
    new_item = InventoryItem(
        category_id=int(data['category_id']),
        name=data['name'],
        unit_type=data['unit_type'],
        unit_total=float(data['unit_total']),
        price=float(data['price']),
        stock_current=float(data['stock_current'])
    )
    db.session.add(new_item)
    db.session.commit()
    return jsonify(new_item.to_dict()), 201

@app.route('/api/inventory/<int:id>', methods=['DELETE'])
def delete_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return '', 204

# --- Calculations & Drafts ---
@app.route('/api/calculate', methods=['POST'])
def calculate_cost():
    data = request.json
    try:
        items = data.get('items', [])
        print_time_hours = float(data.get('print_time_hours', 0.0))
        operator_time_hours = float(data.get('operator_time_hours', 0.0))
        services = data.get('services', [])
        printer_id = data.get('printer_id')
        qty = int(data.get('qty', 1))

        pricing_strategy = data.get('pricing_strategy', {'mode': 'markup', 'value': 100})
        discounts = data.get('discounts', {'type': 'percent', 'value': 0})

        settings = Settings.query.first()
        if not settings:
            return jsonify({'error': 'Settings missing'}), 400

        # Step 1: Self-Cost
        material_cost = 0.0
        for item_data in items:
            inv_item = InventoryItem.query.get(item_data['inventory_id'])
            if inv_item:
                # Material scales by quantity
                material_cost += (inv_item.price / inv_item.unit_total) * float(item_data['usage_amount']) * qty

        machine_cost = 0.0
        if printer_id:
            printer = Printer.query.get(printer_id)
            if printer:
                # Machine cost scales by quantity
                machine_cost = (((printer.power / 1000.0) * print_time_hours * settings.electricity_rate) +                                ((printer.cost / printer.resource) * print_time_hours)) * qty

        labor_cost = operator_time_hours * settings.operator_rate_per_hour

        services_cost = sum([float(s.get('cost', 0)) for s in services])

        total_self_cost = material_cost + machine_cost + labor_cost + services_cost

        # Step 2: Base Price Strategy
        mode = pricing_strategy.get('mode', 'markup')
        val = float(pricing_strategy.get('value', 0))

        if mode == 'markup':
            base_price = total_self_cost * (1 + val/100.0)
        elif mode == 'target_profit':
            base_price = total_self_cost + val
        elif mode == 'fixed_price':
            base_price = val
        else:
            base_price = total_self_cost

        # Step 3: Discounts & Fees
        discount_val = float(discounts.get('value', 0))
        if discounts.get('type') == 'absolute':
            price_after_discount = base_price - discount_val
        else:
            price_after_discount = base_price * (1 - discount_val/100.0)

        # Reverse calculate to ensure final profit margin matches expectations after tax/acquiring
        final_client_price = price_after_discount / (1 - (settings.acquiring_fee_percent/100.0) - (settings.base_tax_percent/100.0))

        # Step 4: Profit Metrics
        acquiring_cost = final_client_price * (settings.acquiring_fee_percent/100.0)
        tax_cost = final_client_price * (settings.base_tax_percent/100.0)

        net_profit = final_client_price - total_self_cost - acquiring_cost - tax_cost
        margin_percent = (net_profit / final_client_price * 100.0) if final_client_price > 0 else 0.0

        return jsonify({
            'total_self_cost': total_self_cost,
            'breakdown': {
                'material_cost': material_cost,
                'machine_cost': machine_cost,
                'labor_cost': labor_cost,
                'services_cost': services_cost
            },
            'base_price': base_price,
            'price_after_discount': price_after_discount,
            'final_client_price': final_client_price,
            'acquiring_cost': acquiring_cost,
            'tax_cost': tax_cost,
            'net_profit': net_profit,
            'margin_percent': margin_percent
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/drafts', methods=['GET', 'POST'])
def handle_drafts():
    if request.method == 'GET':
        drafts = CalculationDraft.query.order_by(CalculationDraft.id.desc()).all()
        return jsonify([d.to_dict() for d in drafts])

    data = request.json
    import json
    new_draft = CalculationDraft(
        name=data.get('name', 'Черновик расчета'),
        payload=json.dumps(data.get('payload', {}))
    )
    db.session.add(new_draft)
    db.session.commit()
    return jsonify(new_draft.to_dict()), 201

# --- Settings ---
@app.route('/api/settings', methods=['GET'])
def get_settings():
    settings = Settings.query.first()
    return jsonify(settings.to_dict())

@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.json
    settings = Settings.query.first()
    if settings:
        settings.electricity_rate = float(data.get('electricity_rate', settings.electricity_rate))
        settings.markup_percent = float(data.get('markup_percent', settings.markup_percent))
        settings.failure_percent = float(data.get('failure_percent', settings.failure_percent))
        settings.tax_percent = float(data.get('tax_percent', settings.tax_percent))
        settings.seller_name = data.get('seller_name', settings.seller_name)
        settings.seller_inn = data.get('seller_inn', settings.seller_inn)
        settings.seller_bank = data.get('seller_bank', settings.seller_bank)
        settings.seller_account = data.get('seller_account', settings.seller_account)
        settings.seller_bik = data.get('seller_bik', settings.seller_bik)

        db.session.commit()
        return jsonify(settings.to_dict())
    return jsonify({'error': 'Settings not found'}), 404

# --- Invoices ---
@app.route('/invoice/<int:id>', methods=['GET'])
def get_invoice(id):
    order = Order.query.get_or_404(id)
    settings = Settings.query.first()
    doc_type = request.args.get('type', 'schet') # 'schet' or 'contract'
    from datetime import datetime
    now = datetime.now().strftime("%d.%m.%Y")
    return render_template('invoice.html', order=order, settings=settings, now=now, doc_type=doc_type)

@app.route('/waybill/<int:id>', methods=['GET'])
def get_waybill(id):
    order = Order.query.get_or_404(id)
    settings = Settings.query.first()
    from datetime import datetime
    now = datetime.now().strftime("%d.%m.%Y")
    return render_template('waybill.html', order=order, settings=settings, now=now)

def open_browser():
    time.sleep(1)
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    # Start the browser in a separate thread so it doesn't block Flask from starting
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False, port=5000)
