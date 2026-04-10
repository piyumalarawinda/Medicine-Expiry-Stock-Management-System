from app import app, db
from models import Medicine, Supplier, InventoryLog, Category
from datetime import datetime, timedelta
import random

def seed_data():
    with app.app_context():
        db.create_all()
        # Add a supplier
        if not Supplier.query.filter_by(name='MediGlobal Corp').first():
            supplier = Supplier(
                name='MediGlobal Corp',
                contact_person='John Doe',
                email='john@mediglobal.com',
                phone='123-456-7890',
                address='123 Pharma St, Health City'
            )
            db.session.add(supplier)
            db.session.commit()
            print("Supplier created!")
        
        s = Supplier.query.first()
        
        # Add medicines
        medicines = [
            {
                'name': 'Amoxicillin 500mg',
                'generic_name': 'Amoxicillin',
                'category': 'Antibiotic',
                'price': 15.50,
                'stock_quantity': 100,
                'low_stock_threshold': 20,
                'expiry_date': datetime.now().date() + timedelta(days=200)
            },
            {
                'name': 'Paracetamol 650mg',
                'generic_name': 'Acetaminophen',
                'category': 'Analgesic',
                'price': 5.00,
                'stock_quantity': 5,
                'low_stock_threshold': 10,
                'expiry_date': datetime.now().date() + timedelta(days=15)
            },
            {
                'name': 'Benadryl Syrup',
                'generic_name': 'Diphenhydramine',
                'category': 'Antihistamine',
                'price': 8.75,
                'stock_quantity': 50,
                'low_stock_threshold': 15,
                'expiry_date': datetime.now().date() - timedelta(days=5)
            },
            {
                'name': 'Insulin Glargine',
                'generic_name': 'Insulin',
                'category': 'Antidiabetic',
                'price': 45.00,
                'stock_quantity': 12,
                'low_stock_threshold': 5,
                'expiry_date': datetime.now().date() + timedelta(days=45)
            }
        ]
        
        for m_data in medicines:
            if not Medicine.query.filter_by(name=m_data['name']).first():
                # Get or create category
                cat_name = m_data['category']
                cat = Category.query.filter_by(name=cat_name).first()
                if not cat:
                    cat = Category(name=cat_name)
                    db.session.add(cat)
                    db.session.commit()

                sku = f"PHA-{random.randint(1000, 9999)}"
                
                med = Medicine(
                    name=m_data['name'],
                    generic_name=m_data['generic_name'],
                    category_id=cat.id,
                    sku=sku,
                    buying_price=m_data['price'] * 0.8,
                    selling_price=m_data['price'],
                    stock_quantity=m_data['stock_quantity'],
                    low_stock_threshold=m_data['low_stock_threshold'],
                    expiry_date=m_data['expiry_date'],
                    supplier_id=s.id
                )
                db.session.add(med)
                db.session.commit()
                
                log = InventoryLog(
                    medicine_id=med.id,
                    change_quantity=med.stock_quantity,
                    reason='Initial seed data'
                )
                db.session.add(log)
                db.session.commit()
        
        print("Medicines seeded!")

if __name__ == '__main__':
    seed_data()
