import os
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Medicine, Supplier, Customer, Sale, SaleItem, Order, OrderItem, InventoryLog, Category, Batch, NotificationRead, Settings, SupportTicket
from datetime import datetime
import pandas as pd

app = Flask(__name__)

def get_unread_notifications():
    from models import Medicine, NotificationRead
    medicines = Medicine.query.all()
    
    # Get read notifications for current user
    read_keys = []
    if current_user.is_authenticated:
        read_logs = NotificationRead.query.filter_by(user_id=current_user.id).all()
        read_keys = [log.notification_key for log in read_logs]
    
    near_expiry = [m for m in medicines if m.is_active and m.is_near_expiry and f"expiry:{m.id}" not in read_keys]
    expired = [m for m in medicines if m.is_active and m.is_expired and f"expiry:{m.id}" not in read_keys]
    low_stock = [m for m in medicines if m.is_active and m.stock_quantity <= m.low_stock_threshold and f"low_stock:{m.id}" not in read_keys]
    
    return near_expiry, expired, low_stock

@app.context_processor
def inject_settings():
    from models import Settings
    settings = Settings.query.first() or Settings()
    
    near_expiry, expired, low_stock = get_unread_notifications()
    notification_count = len(near_expiry) + len(expired) + len(low_stock)
    
    return dict(settings=settings, notification_count=notification_count)

app.config['SECRET_KEY'] = 'your-secret-key-here'

# Absolute path for the database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database', 'pharmacy.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize database
def init_db():
    with app.app_context():
        if not os.path.exists('database'):
            os.makedirs('database')
        db.create_all()
        
        # Create admin if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@example.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created!")

# Routes
@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    medicines = Medicine.query.all()
    
    # Calculate distribution counts (mutually exclusive)
    total_active = [m for m in medicines if m.is_active]
    expired_list = [m for m in total_active if m.is_expired]
    near_expiry_list = [m for m in total_active if m.is_near_expiry and not m.is_expired]
    low_stock_list = [m for m in total_active if m.stock_quantity <= m.low_stock_threshold and not m.is_expired and not m.is_near_expiry]
    
    dist_counts = {
        'expired': len(expired_list),
        'near_expiry': len(near_expiry_list),
        'low_stock': len(low_stock_list),
        'healthy': len(total_active) - len(expired_list) - len(near_expiry_list) - len(low_stock_list)
    }

    # Get unread alerts count for the header notification bell
    near_expiry_unread, expired_unread, unread_low_stock = get_unread_notifications()
    notification_count = len(near_expiry_unread) + len(expired_unread) + len(unread_low_stock)
    
    # Fetch recent logs from InventoryLog
    recent_logs = InventoryLog.query.order_by(InventoryLog.timestamp.desc()).limit(5).all()
    
    from models import Settings
    app_settings = Settings.query.first()
    
    return render_template('dashboard.html', 
                           medicines=medicines,
                           near_expiry=near_expiry_list, 
                           expired=expired_list, 
                           low_stock=low_stock_list,
                           dist_counts=dist_counts,
                           recent_logs=recent_logs,
                           notification_count=notification_count,
                           app_settings=app_settings)

@app.route('/medicine')
@login_required
def medicine():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id')
    filter_type = request.args.get('filter')
    PER_PAGE = 8
    
    query = Medicine.query.filter_by(is_active=True)
    
    current_category = None
    if category_id and category_id != 'All':
        query = query.filter_by(category_id=int(category_id))
        current_category = Category.query.get(int(category_id))
    
    # SQL-level filtering for "Expiring Soon"
    if filter_type == 'expiring':
        from datetime import date, timedelta
        thirty_days_later = date.today() + timedelta(days=30)
        query = query.filter(Medicine.expiry_date <= thirty_days_later)
    
    pagination = query.order_by(Medicine.name.asc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    medicines = pagination.items
        
    categories = Category.query.all()
    suppliers = Supplier.query.filter_by(is_active=True).all()
    
    return render_template('medecine.html', 
                           medicines=medicines, 
                           pagination=pagination,
                           categories=categories,
                           suppliers=suppliers,
                           current_category=current_category,
                           current_filter=filter_type)

@app.route('/medicine/add', methods=['GET', 'POST'])
@login_required
def add_medicine():
    if request.method == 'POST':
        name = request.form.get('name')
        sku = request.form.get('sku')
        category = request.form.get('category')
        stock_quantity = int(request.form.get('stock_quantity', 0))
        buying_price = float(request.form.get('buying_price', 0))
        selling_price = float(request.form.get('selling_price', 0))
        supplier_id = int(request.form.get('supplier_id'))
        expiry_date_str = request.form.get('expiry_date')
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()

        # Look up or create category
        cat = Category.query.filter_by(name=category).first()
        if not cat:
            cat = Category(name=category)
            db.session.add(cat)
            db.session.commit()

        new_medicine = Medicine(
            name=name,
            sku=sku,
            category_id=cat.id,
            stock_quantity=stock_quantity,
            buying_price=buying_price,
            selling_price=selling_price,
            supplier_id=supplier_id,
            expiry_date=expiry_date
        )
        db.session.add(new_medicine)
        db.session.commit()
        
        # Log inventory movement
        log = InventoryLog(
            medicine_id=new_medicine.id,
            change_quantity=stock_quantity,
            reason='RESTOCK: Initial stock'
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Medicine added successfully!', 'success')
        return redirect(url_for('medicine'))
    
    suppliers = Supplier.query.filter_by(is_active=True).all()
    return render_template('add-new-medicine.html', suppliers=suppliers)

@app.route('/edit_medicine/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_medicine(id):
    medicine = Medicine.query.get_or_404(id)
    categories = Category.query.all()
    suppliers = Supplier.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        medicine.name = request.form.get('name')
        medicine.sku = request.form.get('sku')
        category_name = request.form.get('category')
        
        # Look up or create category
        cat = Category.query.filter_by(name=category_name).first()
        if not cat:
            cat = Category(name=category_name)
            db.session.add(cat)
            db.session.commit()
            
        medicine.category_id = cat.id
        medicine.supplier_id = int(request.form.get('supplier_id'))
        medicine.stock_quantity = int(request.form.get('stock_quantity', 0))
        medicine.buying_price = float(request.form.get('buying_price', 0))
        medicine.selling_price = float(request.form.get('selling_price', 0))
        medicine.expiry_date = datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d').date()
        
        db.session.commit()
        flash('Medicine updated successfully!', 'success')
        return redirect(url_for('medicine'))
        
    return render_template('edit-medicine.html', medicine=medicine, categories=categories, suppliers=suppliers)

@app.route('/delete_medicine/<int:id>')
@login_required
def delete_medicine(id):
    medicine = Medicine.query.get_or_404(id)
    try:
        medicine.is_active = False
        db.session.commit()
        flash('Medicine deactivated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deactivating medicine: An unexpected error occurred.', 'error')
    return redirect(url_for('medicine'))

@app.route('/medicine/details/<int:id>')
@login_required
def medicine_details(id):
    med = Medicine.query.get_or_404(id)
    
    # Check if category is None
    category_name = med.category.name if med.category else 'General'
    supplier_name = med.supplier.name if med.supplier else 'N/A'
    
    return jsonify({
        'id': med.id,
        'name': med.name,
        'generic_name': med.generic_name or 'N/A',
        'sku': med.sku or 'N/A',
        'category': category_name,
        'supplier': supplier_name,
        'stock': med.stock_quantity,
        'buying_price': med.buying_price,
        'selling_price': med.selling_price,
        'expiry_date': med.expiry_date.strftime('%d %b %Y') if med.expiry_date else 'N/A',
        'low_stock_threshold': med.low_stock_threshold,
        'msds_info': med.msds_info or 'No specific safety data provided. Handle with standard pharmaceutical care.',
        'is_expired': med.is_expired,
        'is_near_expiry': med.is_near_expiry
    })

@app.route('/supplier')
@login_required
def supplier():
    suppliers = Supplier.query.filter_by(is_active=True).all()
    return render_template('supplier.html', suppliers=suppliers)

@app.route('/supplier/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        contact_person = request.form.get('contact_person')
        address = request.form.get('address')

        new_supplier = Supplier(
            name=name,
            email=email,
            phone=phone,
            contact_person=contact_person,
            address=address
        )
        db.session.add(new_supplier)
        db.session.commit()
        flash('Supplier added successfully!', 'success')
        return redirect(url_for('supplier'))
    return render_template('add-new-supplier.html')

@app.route('/edit_supplier/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    
    if request.method == 'POST':
        supplier.name = request.form.get('name')
        supplier.email = request.form.get('email')
        supplier.phone = request.form.get('phone')
        supplier.contact_person = request.form.get('contact_person')
        supplier.address = request.form.get('address')
        
        db.session.commit()
        flash('Supplier updated successfully!', 'success')
        return redirect(url_for('supplier'))
        
    return render_template('edit-supplier.html', supplier=supplier)

@app.route('/delete_supplier/<int:id>')
@login_required
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    try:
        supplier.is_active = False
        db.session.commit()
        flash('Supplier deactivated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deactivating supplier: An unexpected error occurred.', 'error')
    return redirect(url_for('supplier'))

@app.route('/customer')
@login_required
def customer():
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 8
    pagination = Customer.query.order_by(Customer.name.asc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    customers = pagination.items
    return render_template('customer.html', customers=customers, pagination=pagination)

@app.route('/customer/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')

        new_customer = Customer(
            name=name,
            email=email,
            phone=phone,
            address=address
        )
        db.session.add(new_customer)
        db.session.commit()
        flash('Customer added successfully!', 'success')
        return redirect(url_for('customer'))
    return render_template('add-new-customer.html')

@app.route('/edit_customer/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    
    if request.method == 'POST':
        customer.name = request.form.get('name')
        customer.phone = request.form.get('phone')
        customer.email = request.form.get('email')
        customer.address = request.form.get('address')
        customer.loyalty_program = 'loyalty_program' in request.form
        customer.notes = request.form.get('notes')
        
        db.session.commit()
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('customer'))
        
    return render_template('edit-customer.html', customer=customer)

@app.route('/delete_customer/<int:id>')
@login_required
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    try:
        db.session.delete(customer)
        db.session.commit()
        flash('Customer deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting customer: This customer might have existing sales records.', 'error')
    return redirect(url_for('customer'))

@app.route('/sale')
@login_required
def sale():
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 10
    pagination = Sale.query.order_by(Sale.date.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    sales = pagination.items
    return render_template('sale.html', sales=sales, pagination=pagination)


@app.route('/Order/create', methods=['GET', 'POST'])
@login_required
def create_order():
    if request.method == 'POST':
        medicine_id = int(request.form.get('medicine_id'))
        supplier_id = int(request.form.get('supplier_id'))
        quantity = int(request.form.get('quantity'))
        unit_price = float(request.form.get('unit_price'))
        
        total_cost = quantity * unit_price
        
        new_purchase = Order(
            supplier_id=supplier_id,
            total_cost=total_cost,
            status='RECEIVED' # Auto-received for this demo
        )
        db.session.add(new_purchase)
        db.session.flush()
        
        item = OrderItem(
            order_id=new_purchase.id,
            medicine_id=medicine_id,
            quantity=quantity,
            unit_cost=unit_price
        )
        db.session.add(item)
        
        # Update stock
        medicine = Medicine.query.get(medicine_id)
        medicine.stock_quantity += quantity
        
        # Log inventory movement
        log = InventoryLog(
            medicine_id=medicine_id,
            change_quantity=quantity,
            reason=f'RESTOCK: Order #{new_purchase.id}'
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Order created and stock updated!', 'success')
        return redirect(url_for('purchase'))
        
    medicines = Medicine.query.filter_by(is_active=True).all()
    suppliers = Supplier.query.filter_by(is_active=True).all()
    return render_template('create-new-order.html', medicines=medicines, suppliers=suppliers)

@app.route('/sale/create', methods=['GET', 'POST'])
@login_required
def create_sale():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        medicine_id = int(request.form.get('medicine_id'))
        quantity = int(request.form.get('quantity'))
        
        medicine = Medicine.query.get(medicine_id)
        if medicine.stock_quantity < quantity:
            flash('Error: Not enough stock!', 'error')
            return redirect(url_for('create_sale'))
            
        total_amount = quantity * medicine.selling_price
        
        new_sale = Sale(
            customer_id=int(customer_id) if customer_id else None,
            total_amount=total_amount
        )
        db.session.add(new_sale)
        db.session.flush()
        
        item = SaleItem(
            sale_id=new_sale.id,
            medicine_id=medicine_id,
            quantity=quantity,
            unit_price=medicine.selling_price,
            subtotal=total_amount
        )
        db.session.add(item)
        
        # Update stock
        medicine.stock_quantity -= quantity
        
        # Log inventory movement
        log = InventoryLog(
            medicine_id=medicine_id,
            change_quantity=-quantity,
            reason=f'SALE: Sale #{new_sale.id}'
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Sale completed successfully!', 'success')
        return redirect(url_for('sale'))
        
    medicines = Medicine.query.filter(Medicine.stock_quantity > 0, Medicine.is_active == True).all()
    customers = Customer.query.all()
    return render_template('create-a-new-sale.html', medicines=medicines, customers=customers)

@app.route('/export/inventory/csv')
@login_required
def export_inventory():
    medicines = Medicine.query.all()
    data = []
    for m in medicines:
        data.append({
            'ID': m.id,
            'Name': m.name,
            'Category': m.category.name if m.category else 'General',
            'Stock': m.stock_quantity,
            'Unit Price': f"${m.unit_price:.2f}",
            'Expiry Date': m.expiry_date.strftime('%Y-%m-%d') if m.expiry_date else 'N/A'
        })
    df = pd.DataFrame(data)
    filename = f"medicine_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df.to_csv(filepath, index=False)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/export/inventory/pdf')
@login_required
def export_medicine_pdf():
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO
    from flask import make_response

    medicines = Medicine.query.all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    title_style.alignment = 1 # Center
    
    elements.append(Paragraph("Medicine Inventory Report", title_style))
    elements.append(Spacer(1, 12))
    
    # Create Table Data
    data = [['ID', 'Name', 'Category', 'Stock', 'Price', 'Expiry']]
    for m in medicines:
        data.append([
            str(m.id),
            m.name,
            m.category.name if m.category else 'General',
            str(m.stock_quantity),
            f"${m.selling_price:.2f}",
            m.expiry_date.strftime('%Y-%m-%d') if m.expiry_date else 'N/A'
        ])
    
    # Table Styling
    table = Table(data, colWidths=[30, 180, 100, 50, 60, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#137fec')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    pdf = buffer.getvalue()
    buffer.close()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"medicine_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response

@app.route('/export/stock/pdf')
@login_required
def export_stock_pdf():
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO
    from flask import make_response

    logs = InventoryLog.query.order_by(InventoryLog.timestamp.desc()).all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    title_style.alignment = 1
    
    elements.append(Paragraph("Stock Movement Report", title_style))
    elements.append(Spacer(1, 12))
    
    data = [['Date', 'Medicine', 'Change', 'Reason']]
    for log in logs:
        data.append([
            log.timestamp.strftime('%Y-%m-%d %H:%M'),
            log.medicine.name,
            f"{'+' if log.change_quantity > 0 else ''}{log.change_quantity}",
            log.reason or 'N/A'
        ])
    
    table = Table(data, colWidths=[110, 160, 60, 170])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#137fec')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    pdf = buffer.getvalue()
    buffer.close()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"stock_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@app.route('/export/purchase/pdf')
@login_required
def export_purchase_pdf():
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO
    from flask import make_response

    orders = Order.query.order_by(Order.date.desc()).all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    title_style.alignment = 1
    
    elements.append(Paragraph("Purchase History Report", title_style))
    elements.append(Spacer(1, 12))
    
    data = [['Date', 'Order ID', 'Supplier', 'Total Cost', 'Status']]
    for order in orders:
        data.append([
            order.date.strftime('%Y-%m-%d'),
            f"PO-{order.id:04d}",
            order.supplier.name,
            f"${order.total_cost:.2f}",
            order.status
        ])
    
    table = Table(data, colWidths=[100, 80, 150, 80, 90])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#137fec')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    pdf = buffer.getvalue()
    buffer.close()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"purchase_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@app.route('/invoice/<int:sale_id>')
@login_required
def invoice(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('invoice.html', sale=sale)

@app.route('/delete_sale/<int:id>')
@login_required
def delete_sale(id):
    sale = Sale.query.get_or_404(id)
    try:
        # Before deleting, restore stock for each item in the sale
        for item in sale.items:
            medicine = Medicine.query.get(item.medicine_id)
            if medicine:
                medicine.stock_quantity += item.quantity
                # Log the restoration
                log = InventoryLog(
                    medicine_id=medicine.id,
                    change_quantity=item.quantity,
                    reason=f'VOID SALE: Sale #{sale.id} deleted'
                )
                db.session.add(log)
        
        db.session.delete(sale)
        db.session.commit()
        flash('Sale voided and deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting sale: {str(e)}', 'error')
    return redirect(url_for('sale'))


@app.route('/sales-report')
@login_required
def sales_report():
    # Filters
    date_range = request.args.get('date_range', 'Last 30 Days')
    category_id = request.args.get('category_id')
    user_id = request.args.get('user_id')
    customer_name = request.args.get('customer')

    # Date range logic
    from datetime import timedelta
    end_date = datetime.utcnow()
    
    if date_range == 'All Time':
        start_date = datetime(2000, 1, 1) # Effectively all time
    elif date_range == 'This Month':
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif date_range == 'Last Quarter':
        start_date = end_date - timedelta(days=90)
    elif date_range == 'Year to Date':
        start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else: # Default: Last 30 Days
        start_date = end_date - timedelta(days=30)

    # Base query for Sales
    query = Sale.query.filter(Sale.date >= start_date)
    
    if category_id and category_id != 'All Categories':
        query = query.join(SaleItem).join(Medicine).filter(Medicine.category_id == int(category_id))
        
    if user_id and user_id != 'All Representatives':
        query = query.filter(Sale.user_id == user_id)
    
    if customer_name:
        query = query.join(Customer).filter(Customer.name.contains(customer_name))

    sales_list = query.order_by(Sale.date.desc()).distinct().all()
    
    # Calculate Metrics based on filtered sales
    total_sales = sum(s.total_amount for s in sales_list)
    transaction_count = len(sales_list)
    avg_sale_value = total_sales / transaction_count if transaction_count > 0 else 0
    
    # Top Product (aggregate SaleItems) respecting filters
    from sqlalchemy import func
    top_product_query = db.session.query(
        Medicine.name, 
        func.sum(SaleItem.quantity).label('total_sold')
    ).select_from(Medicine).join(SaleItem).join(Sale).filter(Sale.date >= start_date)
    
    if category_id and category_id != 'All Categories':
        top_product_query = top_product_query.filter(Medicine.category_id == int(category_id))
    if user_id and user_id != 'All Representatives':
        top_product_query = top_product_query.filter(Sale.user_id == user_id)
    
    top_product_res = top_product_query.group_by(Medicine.id).order_by(db.text('total_sold DESC')).first()
    
    top_product = top_product_res[0] if top_product_res else "N/A"
    top_product_count = top_product_res[1] if top_product_res else 0

    # Sales by Category respecting date and user filters
    cat_query = db.session.query(
        Category.name,
        func.sum(SaleItem.subtotal).label('total')
    ).select_from(Category).join(Medicine).join(SaleItem).join(Sale).filter(Sale.date >= start_date)
    
    if user_id and user_id != 'All Representatives':
        cat_query = cat_query.filter(Sale.user_id == user_id)
        
    category_sales = cat_query.group_by(Category.id).all()
    
    cat_names = [c[0] for c in category_sales]
    cat_values = [str(c[1]) for c in category_sales]

    # Revenue History (Last 7 days)
    # Note: History usually doesn't filter by range, but let's keep it consistent if needed.
    # For now, leaving it as last 7 days as it's a "History" chart.
    revenue_history = []
    for i in range(6, -1, -1):
        d = end_date.date() - timedelta(days=i)
        day_query = db.session.query(func.sum(Sale.total_amount)).filter(
            func.date(Sale.date) == d
        )
        if user_id and user_id != 'All Representatives':
            day_query = day_query.filter(Sale.user_id == user_id)
            
        day_total = day_query.scalar() or 0
        revenue_history.append({'day': d.strftime('%a'), 'amount': day_total})
    
    rev_days = [r['day'] for r in revenue_history]
    rev_amounts = [r['amount'] for r in revenue_history]
    max_rev = max(rev_amounts) if rev_amounts else 1

    # Get data for filters
    categories = Category.query.all()
    users = User.query.filter_by(role='Staff').all() 
    app_settings = Settings.query.first()

    return render_template('sales-report.html',
                           sales=sales_list, # Show all for "Enable All"
                           total_sales=total_sales,
                           avg_sale_value=avg_sale_value,
                           transaction_count=transaction_count,
                           top_product=top_product,
                           top_product_count=top_product_count,
                           categories=categories,
                           users=users,
                           cat_names=cat_names,
                           cat_values=cat_values,
                           rev_days=rev_days,
                           rev_amounts=rev_amounts,
                           max_rev=max_rev,
                           settings=app_settings,
                           current_filters={
                               'date_range': date_range,
                               'category_id': category_id,
                               'user_id': user_id,
                               'customer': customer_name
                           })

@app.route('/export/sales/csv')
@login_required
def export_sales_csv():
    # Filters
    date_range = request.args.get('date_range', 'Last 30 Days')
    category_id = request.args.get('category_id')
    user_id = request.args.get('user_id')
    customer_name = request.args.get('customer')

    from datetime import timedelta
    end_date = datetime.utcnow()
    
    if date_range == 'All Time':
        start_date = datetime(2000, 1, 1)
    elif date_range == 'This Month':
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif date_range == 'Last Quarter':
        start_date = end_date - timedelta(days=90)
    elif date_range == 'Year to Date':
        start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = end_date - timedelta(days=30)

    query = Sale.query.filter(Sale.date >= start_date)
    if category_id and category_id != 'All Categories':
        query = query.join(SaleItem).join(Medicine).filter(Medicine.category_id == int(category_id))
    if user_id and user_id != 'All Representatives':
        query = query.filter(Sale.user_id == user_id)
    if customer_name:
        query = query.join(Customer).filter(Customer.name.contains(customer_name))

    sales = query.order_by(Sale.date.desc()).distinct().all()
    
    app_settings = Settings.query.first() or Settings()
    data = []
    for s in sales:
        data.append({
            'Date': s.date.strftime('%Y-%m-%d'),
            'Invoice': f'#INV-{s.id:05d}',
            'Customer': s.customer.name if s.customer else 'Walk-in',
            'Rep': s.user.first_name if s.user else 'System',
            'Amount': f'{app_settings.currency_symbol}{s.total_amount:.2f}',
            'Items': ", ".join([f"{item.medicine.name} ({item.quantity})" for item in s.items])
        })
    df = pd.DataFrame(data)
    filename = f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df.to_csv(filepath, index=False)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/export/sales/pdf')
@login_required
def export_sales_pdf():
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO
    from flask import make_response

    # Filters (Reuse logic)
    date_range = request.args.get('date_range', 'Last 30 Days')
    category_id = request.args.get('category_id')
    user_id = request.args.get('user_id')
    customer_name = request.args.get('customer')

    from datetime import timedelta
    end_date = datetime.utcnow()
    if date_range == 'All Time': start_date = datetime(2000, 1, 1)
    elif date_range == 'This Month': start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif date_range == 'Last Quarter': start_date = end_date - timedelta(days=90)
    elif date_range == 'Year to Date': start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else: start_date = end_date - timedelta(days=30)

    query = Sale.query.filter(Sale.date >= start_date)
    if category_id and category_id != 'All Categories':
        query = query.join(SaleItem).join(Medicine).filter(Medicine.category_id == int(category_id))
    if user_id and user_id != 'All Representatives':
        query = query.filter(Sale.user_id == user_id)
    if customer_name:
        query = query.join(Customer).filter(Customer.name.contains(customer_name))

    sales = query.order_by(Sale.date.desc()).distinct().all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    title_style.alignment = 1
    
    elements.append(Paragraph(f"Sales Report ({date_range})", title_style))
    elements.append(Spacer(1, 12))
    
    app_settings = Settings.query.first() or Settings()
    data = [['Date', 'Invoice', 'Customer', 'Rep', 'Amount']]
    for s in sales:
        data.append([
            s.date.strftime('%Y-%m-%d'),
            f"#INV-{s.id:05d}",
            s.customer.name if s.customer else 'Walk-in',
            s.user.first_name if s.user else 'System',
            f"{app_settings.currency_symbol}{s.total_amount:.2f}"
        ])
    
    table = Table(data, colWidths=[80, 80, 150, 100, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#137fec')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    pdf = buffer.getvalue()
    buffer.close()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response



@app.route('/help', methods=['GET', 'POST'])
@login_required
def help():
    if request.method == 'POST':
        subject = request.form.get('subject')
        category = request.form.get('category')
        message = request.form.get('message')
        
        if subject and category and message:
            ticket = SupportTicket(
                user_id=current_user.id,
                subject=subject,
                category=category,
                message=message
            )
            db.session.add(ticket)
            db.session.commit()
            flash('Your support ticket has been submitted successfully!', 'success')
            return redirect(url_for('help'))
        else:
            flash('Please fill in all required fields.', 'error')
            
    return render_template('help.html')

@app.route('/knowledge-base')
@login_required
def knowledge_base():
    return render_template('knowledge-base.html')

@app.route('/tutorials')
@login_required
def tutorials():
    return render_template('tutorials.html')

@app.route('/forum')
@login_required
def forum():
    from models import Settings
    app_settings = Settings.query.first()
    if not app_settings:
        app_settings = Settings()
        db.session.add(app_settings)
        db.session.commit()
    
    if not app_settings.forum_enabled:
        flash('The social forum is currently disabled by the administrator.', 'info')
        return redirect(url_for('dashboard'))
        
    return render_template('forum.html', settings=app_settings)

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot-password.html')

@app.route('/setting', methods=['GET', 'POST'])
@login_required
def setting():
    from models import Settings
    import os
    from werkzeug.utils import secure_filename

    # Ensure at least one settings record exists
    app_settings = Settings.query.first()
    if not app_settings:
        app_settings = Settings()
        db.session.add(app_settings)
        db.session.commit()

    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'profile':
            current_user.first_name = request.form.get('first_name')
            current_user.last_name = request.form.get('last_name')
            current_user.email = request.form.get('email')
            
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename:
                    filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    current_user.profile_picture = filename
                    
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            
        elif form_type == 'general':
            app_settings.language = request.form.get('language')
            app_settings.theme = request.form.get('theme')
            app_settings.date_format = request.form.get('date_format')
            app_settings.time_format = request.form.get('time_format')
            app_settings.currency = request.form.get('currency')
            app_settings.timezone = request.form.get('timezone')
            app_settings.country = request.form.get('country')
            
            # Simple mapping for currency symbol
            symbols = {'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': 'Rs', 'CAD': 'C$', 'AUD': 'A$', 'JPY': '¥'}
            app_settings.currency_symbol = symbols.get(app_settings.currency, '$')
            
            db.session.commit()
            flash('General settings updated successfully!', 'success')
            
        elif form_type == 'notifications':
            app_settings.low_stock_threshold_alert = 'low_stock' in request.form
            app_settings.expiry_alert = 'expiry' in request.form
            app_settings.new_sale_alert = 'new_sale' in request.form
            
            db.session.commit()
            flash('Notification preferences updated successfully!', 'success')



        return redirect(url_for('setting'))

    return render_template('setting.html', app_settings=app_settings)


@app.route('/inventory/adjust', methods=['GET', 'POST'])
@login_required
def adjust_stock():
    if request.method == 'POST':
        medicine_id = int(request.form.get('medicine_id'))
        adjustment_type = request.form.get('adjustment_type') # 'IN' or 'OUT'
        quantity = int(request.form.get('quantity'))
        reason = request.form.get('reason')
        notes = request.form.get('notes', '')
        
        medicine = Medicine.query.get(medicine_id)
        if not medicine:
            flash('Medicine not found!', 'error')
            return redirect(url_for('adjust_stock'))
            
        change = quantity if adjustment_type == 'IN' else -quantity
        
        # Check for negative stock
        if adjustment_type == 'OUT' and medicine.stock_quantity < quantity:
            flash(f'Error: Not enough stock for {medicine.name}. Current: {medicine.stock_quantity}', 'error')
            return redirect(url_for('adjust_stock'))
            
        medicine.stock_quantity += change
        
        # Log movement
        log = InventoryLog(
            medicine_id=medicine_id,
            change_quantity=change,
            reason=f'ADJUSTMENT: {reason} ({notes})' if notes else f'ADJUSTMENT: {reason}'
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Stock adjusted successfully for {medicine.name}!', 'success')
        return redirect(url_for('stock_movement'))
        
    medicines = Medicine.query.filter_by(is_active=True).all()
    return render_template('adjust-stock.html', medicines=medicines)


@app.route('/stock-movement')
@login_required
def stock_movement():
    from models import Category
    
    # Filters
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '')
    m_type = request.args.get('type', 'All')
    category_id = request.args.get('category', 'All')
    PER_PAGE = 10
    
    query = InventoryLog.query.join(Medicine)
    
    if q:
        query = query.filter(Medicine.name.contains(q))
    if m_type != 'All':
        query = query.filter(InventoryLog.reason.contains(m_type))
    if category_id != 'All':
        query = query.filter(Medicine.category_id == int(category_id))
        
    pagination = query.order_by(InventoryLog.timestamp.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    logs = pagination.items
    
    # Monthly Stats (Separate query for metrics)
    first_day = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_logs = InventoryLog.query.filter(InventoryLog.timestamp >= first_day).all()
    
    total_inward = sum(log.change_quantity for log in month_logs if log.change_quantity > 0)
    total_outward = abs(sum(log.change_quantity for log in month_logs if log.change_quantity < 0))
    net_adjustment = sum(log.change_quantity for log in month_logs)
    
    categories = Category.query.all()
    
    return render_template('stock_movement.html', 
                          logs=logs, 
                          pagination=pagination,
                          categories=categories,
                          stats={
                              'inward': total_inward,
                              'outward': total_outward,
                              'net': net_adjustment
                          },
                          filters={
                              'q': q,
                              'type': m_type,
                              'category': category_id
                          })

@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    medicines = Medicine.query.filter(Medicine.name.contains(query), Medicine.is_active == True).all()
    suppliers = Supplier.query.filter(Supplier.name.contains(query)).all()
    customers = Customer.query.filter(Customer.name.contains(query)).all()
    
    # Search for Sales (by ID or Customer Name)
    sales = Sale.query.join(Customer, isouter=True).filter(
        (Sale.id.contains(query)) | 
        (Customer.name.contains(query))
    ).all() if query else []
    
    # Search for Purchase Orders (by ID or Supplier Name)
    purchases = Order.query.join(Supplier).filter(
        (Order.id.contains(query)) | 
        (Supplier.name.contains(query))
    ).all() if query else []
    
    return render_template('search_results.html', 
                           query=query, 
                           medicines=medicines, 
                           suppliers=suppliers, 
                           customers=customers,
                           sales=sales,
                           purchases=purchases)

@app.route('/notifications')
@login_required
def notifications():
    filter_type = request.args.get('filter', 'All')
    
    near_expiry, expired, low_stock = get_unread_notifications()
    
    # Calculate counts
    counts = {
        'all': len(near_expiry) + len(expired) + len(low_stock),
        'low_stock': len(low_stock),
        'expiring': len(near_expiry) + len(expired)
    }
    
    # Filter lists based on type
    display_near_expiry = near_expiry if filter_type in ['All', 'Expiring Soon'] else []
    display_expired = expired if filter_type in ['All', 'Expiring Soon'] else []
    display_low_stock = low_stock if filter_type in ['All', 'Low Stock'] else []
    
    return render_template('notifications.html', 
                          near_expiry=display_near_expiry, 
                          expired=display_expired, 
                          low_stock=display_low_stock,
                          counts=counts,
                          filter_type=filter_type)

@app.route('/notifications/mark-all-read')
@login_required
def mark_all_notifications_read():
    medicines = Medicine.query.filter_by(is_active=True).all()
    
    for m in medicines:
        # Check low stock
        if m.stock_quantity <= m.low_stock_threshold:
            key = f"low_stock:{m.id}"
            if not NotificationRead.query.filter_by(user_id=current_user.id, notification_key=key).first():
                read = NotificationRead(user_id=current_user.id, notification_key=key)
                db.session.add(read)
        
        # Check expiry
        if m.is_near_expiry or m.is_expired:
            key = f"expiry:{m.id}"
            if not NotificationRead.query.filter_by(user_id=current_user.id, notification_key=key).first():
                read = NotificationRead(user_id=current_user.id, notification_key=key)
                db.session.add(read)
                
    db.session.commit()
    flash('All notifications marked as read', 'success')
    return redirect(url_for('notifications'))

@app.route('/notifications/action/<action>/<int:medicine_id>')
@login_required
def notification_action(action, medicine_id):
    medicine = Medicine.query.get_or_404(medicine_id)
    
    if action == 'dismiss_low_stock':
        key = f"low_stock:{medicine.id}"
        if not NotificationRead.query.filter_by(user_id=current_user.id, notification_key=key).first():
            read = NotificationRead(user_id=current_user.id, notification_key=key)
            db.session.add(read)
            db.session.commit()
            flash(f'Alert for {medicine.name} dismissed', 'success')
            
    elif action == 'dismiss_expiry':
        key = f"expiry:{medicine.id}"
        if not NotificationRead.query.filter_by(user_id=current_user.id, notification_key=key).first():
            read = NotificationRead(user_id=current_user.id, notification_key=key)
            db.session.add(read)
            db.session.commit()
            flash(f'Expiry alert for {medicine.name} dismissed', 'success')
            
    elif action == 'urgent_discard':
        # Zero out stock
        old_stock = medicine.stock_quantity
        medicine.stock_quantity = 0
        
        # Log it
        log = InventoryLog(
            medicine_id=medicine.id,
            change_quantity=-old_stock,
            reason=f'DISCARDED: Expired stock urgent removal'
        )
        db.session.add(log)
        
        # Mark as read
        key = f"expiry:{medicine.id}"
        if not NotificationRead.query.filter_by(user_id=current_user.id, notification_key=key).first():
            read = NotificationRead(user_id=current_user.id, notification_key=key)
            db.session.add(read)
            
        db.session.commit()
        flash(f'URGENT: {medicine.name} discarded and stock zeroed.', 'warning')
        
    return redirect(url_for('notifications'))


@app.route('/user-management')
@login_required
def user_management():
    if current_user.role != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    users = User.query.all()
    return render_template('user_management.html', users=users)

@app.route('/user-management/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')

        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return redirect(url_for('add_user'))

        new_user = User(
            username=username,
            role=role,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('User added successfully!', 'success')
        return redirect(url_for('user_management'))

    return render_template('add-user.html')

@app.route('/user-management/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.role = request.form.get('role')
        user.email = request.form.get('email')
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        
        password = request.form.get('password')
        if password:
            user.set_password(password)
            
        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('user_management'))

    return render_template('edit-user.html', user=user)

@app.route('/user-management/delete/<int:id>')
@login_required
def delete_user(id):
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    if current_user.id == id:
        flash('You cannot delete your own account!', 'error')
        return redirect(url_for('user_management'))
    
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('user_management'))


@app.route('/purchase')
@login_required
def purchase():
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 10
    pagination = Order.query.order_by(Order.date.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    purchases = pagination.items
    return render_template('purchase.html', purchases=purchases, pagination=pagination)

@app.route('/order-summary/<int:order_id>')
@login_required
def order_summary(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order-summary.html', order=order)

@app.route('/delete-order/<int:id>')
@login_required
def delete_order(id):
    order = Order.query.get_or_404(id)
    try:
        # Before deleting, reverse stock for each item in the order
        for item in order.items:
            medicine = Medicine.query.get(item.medicine_id)
            if medicine:
                # Decrease stock as the purchase is being voided
                medicine.stock_quantity -= item.quantity
                # Log the restoration
                log = InventoryLog(
                    medicine_id=medicine.id,
                    change_quantity=-item.quantity,
                    reason=f'VOID ORDER: Order #{order.id} deleted'
                )
                db.session.add(log)
        
        db.session.delete(order)
        db.session.commit()
        flash('Purchase order voided and deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting order: {str(e)}', 'error')
    return redirect(url_for('purchase'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5555, debug=True)









