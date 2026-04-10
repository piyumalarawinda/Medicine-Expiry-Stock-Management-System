from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='Staff')  # Admin or Staff
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    department = db.Column(db.String(50), default='General')
    profile_picture = db.Column(db.String(255))
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    medicines = db.relationship('Medicine', backref='category', lazy=True)

    def __repr__(self):
        return self.name

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    contact_person = db.Column(db.String(100))
    address = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    medicines = db.relationship('Medicine', backref='supplier', lazy=True)
    orders = db.relationship('Order', backref='supplier', lazy=True)

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    generic_name = db.Column(db.String(100))
    sku = db.Column(db.String(50), unique=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)
    buying_price = db.Column(db.Float, default=0.0)
    selling_price = db.Column(db.Float, default=0.0)
    unit_price = db.Column(db.Float, default=0.0) # Mapping to legacy column to satisfy NOT NULL
    expiry_date = db.Column(db.Date, nullable=False)
    low_stock_threshold = db.Column(db.Integer, default=10)
    msds_info = db.Column(db.Text)
    msds_file = db.Column(db.String(255))
    msds_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    sale_items = db.relationship('SaleItem', backref='medicine', lazy=True)
    order_items = db.relationship('OrderItem', backref='medicine', lazy=True)
    batches = db.relationship('Batch', backref='medicine', lazy=True, cascade="all, delete-orphan")

    @property
    def is_near_expiry(self):
        if not self.expiry_date:
            return False
        days_diff = (self.expiry_date - datetime.now().date()).days
        return 0 <= days_diff <= 30

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < datetime.now().date()

class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)
    batch_number = db.Column(db.String(50), nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)
    expiry_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class InventoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    change_quantity = db.Column(db.Integer, nullable=False) # Positive for addition, negative for reduction
    reason = db.Column(db.String(200)) # e.g., "Sale", "Purchase Order", "Manual Adjustment", "Return"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    medicine = db.relationship('Medicine', backref='inventory_logs_ref')
    batch = db.relationship('Batch', backref='inventory_logs_ref')

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    loyalty_program = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    sales = db.relationship('Sale', backref='customer', lazy=True)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    items = db.relationship('SaleItem', backref='sale', lazy=True)
    user = db.relationship('User', backref='sales_records', lazy=True)

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending') # Pending, Received
    total_cost = db.Column(db.Float, nullable=False)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    currency = db.Column(db.String(10), default='USD')
    currency_symbol = db.Column(db.String(10), default='$')
    timezone = db.Column(db.String(50), default='UTC')
    language = db.Column(db.String(20), default='en-US')
    theme = db.Column(db.String(20), default='system')
    date_format = db.Column(db.String(20), default='MM/DD/YYYY')
    time_format = db.Column(db.String(20), default='12 Hour')
    country = db.Column(db.String(100), default='United States')
    
    # Notification Settings
    low_stock_threshold_alert = db.Column(db.Boolean, default=True)
    expiry_alert = db.Column(db.Boolean, default=True)
    new_sale_alert = db.Column(db.Boolean, default=False)



class NotificationRead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notification_key = db.Column(db.String(100), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'notification_key', name='_user_notification_uc'),)

class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Optional for now
    subject = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Open') # Open, In Progress, Closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='support_tickets', lazy=True)
