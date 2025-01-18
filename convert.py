import json

# Παλιό αρχείο
old_file_path = "open_orders.json"
# Νέο αρχείο
new_file_path = "new_orders.json"

# Φόρτωμα του παλιού JSON
with open(old_file_path, "r") as f:
    data = json.load(f)

# Έλεγχος αν το "orders" είναι ήδη λίστα
if isinstance(data["orders"], list):
    print("Το 'orders' είναι ήδη λίστα. Δεν απαιτείται μετατροπή.")
else:
    # Μετατροπή του dictionary "orders" σε λίστα
    data["orders"] = [
        {
            "id": order["id"],
            "symbol": order["symbol"],
            "price": float(price),  # Το price γίνεται float για συνέπεια
            "side": order["side"],
            "status": order["status"],
            "amount": order["amount"],
            "remaining": order["remaining"],
            "datetime": order["datetime"],
            "timestamp": order["timestamp"],
        }
        for price, order in data["orders"].items()
    ]
    print("Η μετατροπή του 'orders' σε λίστα ολοκληρώθηκε.")

    # Αποθήκευση στο νέο αρχείο
    with open(new_file_path, "w") as f:
        json.dump(data, f, indent=4)

    print(f"Το αρχείο αποθηκεύτηκε στο {new_file_path}.")
