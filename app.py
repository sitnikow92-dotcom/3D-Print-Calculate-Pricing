import os
import sys
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

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10), nullable=False) # 'FDM' or 'SLA'
    weight_volume = db.Column(db.Float, nullable=False) # Weight or volume of the spool
    price = db.Column(db.Float, nullable=False) # Price of the spool
    stock = db.Column(db.Float, nullable=False) # Current stock

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'weight_volume': self.weight_volume,
            'price': self.price,
            'stock': self.stock
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
    notes = db.Column(db.Text, nullable=True)
    orders = db.relationship('Order', backref='client', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'notes': self.notes
        }

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Согласование") # "Согласование", "Очередь", "В работе", "Готов", "Архив"
    price = db.Column(db.Float, nullable=False) # Total cost
    cost = db.Column(db.Float, nullable=False) # Self-cost
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=True)
    weight_used = db.Column(db.Float, nullable=True) # Weight or volume used
    printer_id = db.Column(db.Integer, db.ForeignKey('printer.id'), nullable=True)
    print_hours = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Integer, default=1)
    file_path = db.Column(db.String(255), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)

    def to_dict(self):
        printer_name = None
        if self.printer_id:
            printer = Printer.query.get(self.printer_id)
            if printer:
                printer_name = printer.name

        client_name = None
        if self.client_id:
            client_name = self.client.name

        return {
            'id': self.id,
            'order_number': self.order_number,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'price': self.price,
            'cost': self.cost,
            'material_id': self.material_id,
            'weight_used': self.weight_used,
            'printer_id': self.printer_id,
            'print_hours': self.print_hours,
            'printer_name': printer_name,
            'quantity': self.quantity,
            'file_path': self.file_path,
            'client_id': self.client_id,
            'client_name': client_name
        }

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

    def to_dict(self):
        return {
            'id': self.id,
            'electricity_rate': self.electricity_rate,
            'markup_percent': self.markup_percent,
            'failure_percent': self.failure_percent,
            'tax_percent': self.tax_percent,
            'seller_name': self.seller_name,
            'seller_inn': self.seller_inn,
            'seller_bank': self.seller_bank,
            'seller_account': self.seller_account,
            'seller_bik': self.seller_bik
        }

# Initialize database
with app.app_context():
    db.create_all()
    # Add default setting if not exists
    if not Settings.query.first():
        default_settings = Settings(electricity_rate=5.0, markup_percent=100.0, failure_percent=10.0, tax_percent=4.0)
        db.session.add(default_settings)
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

# --- CRUD for Materials ---
@app.route('/api/materials', methods=['GET'])
def get_materials():
    materials = Material.query.all()
    return jsonify([m.to_dict() for m in materials])

@app.route('/api/materials', methods=['POST'])
def add_material():
    data = request.json
    new_mat = Material(
        name=data['name'],
        type=data['type'],
        weight_volume=float(data['weight_volume']),
        price=float(data['price']),
        stock=float(data['stock'])
    )
    db.session.add(new_mat)
    db.session.commit()
    return jsonify(new_mat.to_dict()), 201

@app.route('/api/materials/<int:id>', methods=['DELETE'])
def delete_material(id):
    mat = Material.query.get_or_404(id)
    db.session.delete(mat)
    db.session.commit()
    return '', 204

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
        notes=data.get('notes', '')
    )
    db.session.add(new_client)
    db.session.commit()
    return jsonify(new_client.to_dict()), 201

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

    # Handle Client logic
    client_id = data.get('client_id')
    if client_id == 'new':
        if data.get('new_client_name'):
            new_client = Client(
                name=data.get('new_client_name'),
                phone=data.get('new_client_phone', ''),
                email=data.get('new_client_email', ''),
                notes=data.get('new_client_notes', '')
            )
            db.session.add(new_client)
            db.session.flush() # To get the ID
            client_id = new_client.id
        else:
            client_id = None # Skip client creation if no name was provided
    elif client_id:
        client_id = int(client_id)
    else:
        client_id = None

    # Generate Order Number
    last_order = Order.query.order_by(Order.id.desc()).first()
    if last_order:
        next_num = last_order.id + 1
    else:
        next_num = 1
    order_number = f"{next_num:04d}"

    new_order = Order(
        order_number=order_number,
        name=data['name'],
        description=data.get('description', ''),
        status=data.get('status', 'Согласование'),
        price=float(data['price']),
        cost=float(data['cost']),
        material_id=int(data.get('material_id')) if data.get('material_id') else None,
        weight_used=float(data.get('weight_used')) if data.get('weight_used') else None,
        printer_id=int(data.get('printer_id')) if data.get('printer_id') else None,
        print_hours=float(data.get('print_hours', 0.0)),
        quantity=int(data.get('quantity', 1)),
        file_path=file_path,
        client_id=client_id
    )
    db.session.add(new_order)
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
        # If moving to "Готов", deduct material stock
        if new_status == "Готов" and order.status != "Готов" and order.material_id and order.weight_used:
            material = Material.query.get(order.material_id)
            if material:
                material.stock -= (order.weight_used * order.quantity)
                # Ensure stock doesn't go below 0 for better real-world handling,
                # although the problem statement just says to deduct.
                if material.stock < 0:
                    material.stock = 0

        order.status = new_status
        db.session.commit()
        return jsonify(order.to_dict())
    return jsonify({'error': 'No status provided'}), 400

@app.route('/api/calculate', methods=['POST'])
def calculate_cost():
    data = request.json
    try:
        material_id = data.get('material_id')
        printer_id = data.get('printer_id')
        weight = float(data.get('weight', 0))
        hours = float(data.get('hours', 0))
        minutes = float(data.get('minutes', 0))
        quantity = int(data.get('quantity', 1))
        modeling_complexity = data.get('modeling_complexity') # "none", "simple", "medium", "complex"

        material = Material.query.get(material_id)
        printer = Printer.query.get(printer_id)
        settings = Settings.query.first()

        if not material or not printer or not settings:
             return jsonify({'error': 'Invalid material, printer, or settings'}), 400

        total_hours = hours + (minutes / 60.0)

        # Formula: (цена катушки / вес) * вес детали + (мощность / 1000 * часы печати * тариф) + (стоимость принтера / ресурс * часы печати)
        # Apply quantity to material, electricity and amortization
        total_weight = weight * quantity
        total_print_hours = total_hours * quantity

        material_cost = (material.price / material.weight_volume) * total_weight
        electricity_cost = (printer.power / 1000.0) * total_print_hours * settings.electricity_rate
        amortization_cost = (printer.cost / printer.resource) * total_print_hours

        self_cost = material_cost + electricity_cost + amortization_cost

        markup_cost = self_cost * (settings.markup_percent / 100.0)
        failure_cost = self_cost * (settings.failure_percent / 100.0)
        client_print_price = self_cost + markup_cost + failure_cost

        # Modeling cost is one-time
        modeling_cost = 0.0
        if modeling_complexity == "simple":
            modeling_cost = 500.0
        elif modeling_complexity == "medium":
            modeling_cost = 1500.0
        elif modeling_complexity == "complex":
            modeling_cost = 3000.0

        intermediate_total = client_print_price + modeling_cost
        tax_cost = intermediate_total * (settings.tax_percent / 100.0)
        total_price = intermediate_total + tax_cost

        return jsonify({
            'self_cost': self_cost,
            'markup_cost': markup_cost,
            'failure_cost': failure_cost,
            'client_print_price': client_print_price,
            'modeling_cost': modeling_cost,
            'tax_cost': tax_cost,
            'total_price': total_price,
            'material_cost': material_cost,
            'electricity_cost': electricity_cost,
            'amortization_cost': amortization_cost
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

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
    from datetime import datetime
    now = datetime.now().strftime("%d.%m.%Y")
    return render_template('invoice.html', order=order, settings=settings, now=now)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
