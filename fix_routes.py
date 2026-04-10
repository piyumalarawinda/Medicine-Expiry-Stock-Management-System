import os

file_path = r'c:\Users\ippiu\OneDrive\Desktop\test 3\app.py'

with open(file_path, 'r') as f:
    content = f.read()

new_routes = """
@app.route('/stock-movement')
@login_required
def stock_movement():
    logs = InventoryLog.query.order_by(InventoryLog.timestamp.desc()).all()
    return render_template('stock_movement.html', logs=logs)

@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    medicines = Medicine.query.filter(Medicine.name.contains(query)).all()
    suppliers = Supplier.query.filter(Supplier.name.contains(query)).all()
    customers = Customer.query.filter(Customer.name.contains(query)).all()
    return render_template('search_results.html', query=query, medicines=medicines, suppliers=suppliers, customers=customers)

@app.route('/notifications')
@login_required
def notifications():
    medicines = Medicine.query.all()
    near_expiry = [m for m in medicines if m.is_near_expiry]
    expired = [m for m in medicines if m.is_expired]
    low_stock = [m for m in medicines if m.stock_quantity <= m.low_stock_threshold]
    return render_template('notifications.html', near_expiry=near_expiry, expired=expired, low_stock=low_stock)
"""

if "def stock_movement():" not in content:
    if "if __name__ == '__main__':" in content:
        content = content.replace("if __name__ == '__main__':", new_routes + "\nif __name__ == '__main__':")
    else:
        content += new_routes

with open(file_path, 'w') as f:
    f.write(content)

print("Routes added successfully!")
