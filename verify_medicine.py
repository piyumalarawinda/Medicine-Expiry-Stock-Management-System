import os
import sqlite3
from flask import Flask
from models import db, Medicine, Category, Supplier

def verify():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database', 'pharmacy.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        # 1. Check if is_active column exists and default is True
        print("Checking Medicine table for is_active column...")
        medicine = Medicine.query.first()
        if medicine:
            print(f"Sample medicine: {medicine.name}, is_active: {medicine.is_active}")
            if medicine.is_active is not True and medicine.is_active is not 1:
                 # In some sqlite versions it might be 1 instead of True
                 if medicine.is_active == 1:
                     print("is_active is 1 (True)")
                 else:
                    print(f"Warning: is_active is {medicine.is_active}, expected True or 1")
        else:
            print("No medicines found in database to check.")

        # 2. Test Soft Delete
        print("\nTesting soft delete logic...")
        # Create a dummy medicine if none exists for testing
        test_med = Medicine.query.filter_by(name="Test Medicine").first()
        if not test_med:
            cat = Category.query.first()
            sup = Supplier.query.first()
            if cat and sup:
                test_med = Medicine(
                    name="Test Medicine",
                    sku="TEST-SKU-123",
                    category_id=cat.id,
                    supplier_id=sup.id,
                    expiry_date=medicine.expiry_date if medicine else None, # Use existing or handle
                    is_active=True
                )
                if not test_med.expiry_date:
                    from datetime import datetime
                    test_med.expiry_date = datetime.now().date()
                db.session.add(test_med)
                db.session.commit()
                print("Created 'Test Medicine' for verification.")
            else:
                print("Cannot create test medicine: Category or Supplier missing.")
                return

        med_id = test_med.id
        print(f"Soft deleting medicine ID {med_id}...")
        test_med.is_active = False
        db.session.commit()

        # Verify it's inactive in DB
        updated_med = Medicine.query.get(med_id)
        print(f"Medicine {updated_med.name} is_active after delete: {updated_med.is_active}")

        # Verify it's filtered out in query
        active_meds = Medicine.query.filter_by(is_active=True).all()
        active_ids = [m.id for m in active_meds]
        if med_id not in active_ids:
            print("Success: Inactive medicine filtered out from active query.")
        else:
            print("Failure: Inactive medicine still present in active query.")

        # Cleanup: Re-activate or delete the test medicine
        # For verification purposes, we'll delete it physically if it was created just for this
        if updated_med.name == "Test Medicine":
            db.session.delete(updated_med)
            db.session.commit()
            print("Cleaned up test medicine.")
        else:
            # Re-activate it if it was an existing one
            updated_med.is_active = True
            db.session.commit()
            print("Re-activated medicine.")

if __name__ == "__main__":
    verify()
