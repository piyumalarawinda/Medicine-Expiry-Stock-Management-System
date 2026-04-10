from app import app, db
from models import Medicine, Supplier, InventoryLog, Category
from datetime import datetime, timedelta
import random

def bulk_add():
    with app.app_context():
        # Ensure a supplier exists
        s = Supplier.query.first()
        if not s:
            s = Supplier(
                name='Universal Pharma Supply',
                contact_person='Logistics Manager',
                email='supply@universalpharma.com',
                phone='555-0199',
                address='456 Logistics Way, Port City'
            )
            db.session.add(s)
            db.session.commit()
            print("Default supplier created.")

        msds_template = """Hazards: May cause irritation or adverse effects if misused.
Handling: Use gloves, avoid inhalation or ingestion beyond prescribed dose.
Storage: Store in a cool, dry place away from light.
First Aid: In case of overdose, seek medical attention immediately."""

        medicines_data = [
            ("Paracetamol", "Analgesic"),
            ("Ibuprofen", "Analgesic"),
            ("Aspirin", "Analgesic"),
            ("Amoxicillin", "Antibiotic"),
            ("Azithromycin", "Antibiotic"),
            ("Ciprofloxacin", "Antibiotic"),
            ("Metformin", "Antidiabetic"),
            ("Atorvastatin", "Cardiovascular"),
            ("Simvastatin", "Cardiovascular"),
            ("Omeprazole", "Gastrointestinal"),
            ("Pantoprazole", "Gastrointestinal"),
            ("Ranitidine", "Gastrointestinal"),
            ("Losartan", "Cardiovascular"),
            ("Amlodipine", "Cardiovascular"),
            ("Enalapril", "Cardiovascular"),
            ("Lisinopril", "Cardiovascular"),
            ("Hydrochlorothiazide", "Cardiovascular"),
            ("Furosemide", "Cardiovascular"),
            ("Spironolactone", "Cardiovascular"),
            ("Insulin", "Antidiabetic"),
            ("Glimepiride", "Antidiabetic"),
            ("Gliclazide", "Antidiabetic"),
            ("Salbutamol", "Respiratory"),
            ("Budesonide", "Respiratory"),
            ("Prednisolone", "Steroids"),
            ("Dexamethasone", "Steroids"),
            ("Cetirizine", "Antihistamine"),
            ("Loratadine", "Antihistamine"),
            ("Chlorpheniramine", "Antihistamine"),
            ("Diazepam", "Psychiatric"),
            ("Alprazolam", "Psychiatric"),
            ("Clonazepam", "Psychiatric"),
            ("Sertraline", "Psychiatric"),
            ("Fluoxetine", "Psychiatric"),
            ("Amitriptyline", "Psychiatric"),
            ("Tramadol", "Analgesic"),
            ("Morphine", "Analgesic"),
            ("Codeine", "Analgesic"),
            ("Diclofenac", "Analgesic"),
            ("Naproxen", "Analgesic"),
            ("Ketorolac", "Analgesic"),
            ("Vitamin C", "Vitamins"),
            ("Vitamin D3", "Vitamins"),
            ("Vitamin B12", "Vitamins"),
            ("Folic Acid", "Vitamins"),
            ("Iron Sulfate", "Vitamins"),
            ("Calcium Carbonate", "Vitamins"),
            ("Zinc Sulfate", "Vitamins"),
            ("Magnesium Hydroxide", "Gastrointestinal"),
            ("ORS", "Vitamins"),
            ("Domperidone", "Gastrointestinal"),
            ("Metoclopramide", "Gastrointestinal"),
            ("Ondansetron", "Gastrointestinal"),
            ("Loperamide", "Gastrointestinal"),
            ("Albendazole", "Anthelmintic"),
            ("Mebendazole", "Anthelmintic"),
            ("Ivermectin", "Anthelmintic"),
            ("Chloroquine", "Antimalarial"),
            ("Hydroxychloroquine", "Antimalarial"),
            ("Doxycycline", "Antibiotic"),
            ("Clindamycin", "Antibiotic"),
            ("Cefixime", "Antibiotic"),
            ("Ceftriaxone", "Antibiotic"),
            ("Gentamicin", "Antibiotic"),
            ("Vancomycin", "Antibiotic"),
            ("Linezolid", "Antibiotic"),
            ("Fluconazole", "Antifungal"),
            ("Ketoconazole", "Antifungal"),
            ("Acyclovir", "Antiviral"),
            ("Valacyclovir", "Antiviral"),
            ("Oseltamivir", "Antiviral"),
            ("Heparin", "Cardiovascular"),
            ("Warfarin", "Cardiovascular"),
            ("Aspirin (Low dose)", "Cardiovascular"),
            ("Clopidogrel", "Cardiovascular"),
            ("Digoxin", "Cardiovascular"),
            ("Propranolol", "Cardiovascular"),
            ("Metoprolol", "Cardiovascular"),
            ("Carvedilol", "Cardiovascular"),
            ("Isosorbide Dinitrate", "Cardiovascular"),
            ("Nitroglycerin", "Cardiovascular"),
            ("Levodopa", "Psychiatric"),
            ("Carbamazepine", "Psychiatric"),
            ("Phenytoin", "Psychiatric")
        ]

        for name, cat_name in medicines_data:
            if not Medicine.query.filter_by(name=name).first():
                # Get or create category
                cat = Category.query.filter_by(name=cat_name).first()
                if not cat:
                    cat = Category(name=cat_name)
                    db.session.add(cat)
                    db.session.commit()

                sku = f"MED-{random.randint(10000, 99999)}"
                
                med = Medicine(
                    name=name,
                    generic_name=name,  # Simplified for this batch
                    category_id=cat.id,
                    sku=sku,
                    buying_price=round(random.uniform(2.0, 20.0), 2),
                    selling_price=round(random.uniform(25.0, 50.0), 2),
                    stock_quantity=random.randint(50, 200),
                    low_stock_threshold=10,
                    expiry_date=datetime.now().date() + timedelta(days=random.randint(365, 730)),
                    supplier_id=s.id,
                    msds_info=msds_template
                )
                db.session.add(med)
                db.session.commit()
                
                log = InventoryLog(
                    medicine_id=med.id,
                    change_quantity=med.stock_quantity,
                    reason='Bulk add via seed script'
                )
                db.session.add(log)
                db.session.commit()
                print(f"Added {name}")

        print("Bulk addition complete!")

if __name__ == '__main__':
    bulk_add()
