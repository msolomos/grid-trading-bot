from flask import Flask, jsonify
import ccxt
import json
from datetime import datetime

app = Flask(__name__)

# Configuration
ORDERS_FILE = "/opt/python/grid-trading-bot/open_orders.json"
PAIR = "XRP/USDT"
EXCHANGE_NAME = "binance"
CONFIG_FILE = "/opt/python/grid-trading-bot/config.json"

# Σύνδεση με το exchange μέσω ccxt
def initialize_exchange():
    try:
        with open(CONFIG_FILE, "r") as f:
            keys = json.load(f)
        exchange = getattr(ccxt, EXCHANGE_NAME)({
            "apiKey": keys["API_KEY"],
            "secret": keys["API_SECRET"],
            "enableRateLimit": True
        })
        exchange.load_markets()
        return exchange
    except Exception as e:
        raise RuntimeError(f"Failed to initialize exchange: {e}")

# Φόρτωση παραγγελιών και στατιστικών από το αρχείο JSON
def load_open_orders():
    try:
        with open(ORDERS_FILE, "r") as f:
            data = json.load(f)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "orders": {},
            "statistics": {
                "total_buys": 0,
                "total_sells": 0,
                "net_profit": 0.0
            }
        }

# Endpoint 1: Τρέχουσα Τιμή
@app.route("/GRID/current-price", methods=["GET"])
def get_current_price():
    exchange = initialize_exchange()
    try:
        ticker = exchange.fetch_ticker(PAIR)
        current_price = ticker["last"]
        return jsonify({"current_price": current_price})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch current price: {e}"}), 500

# Endpoint 2: Ανοιχτές Παραγγελίες
@app.route("/GRID/existing-orders", methods=["GET"])
def get_existing_orders():
    data = load_open_orders()
    orders = []
    for price, order in data["orders"].items():
        order_info = {
            "order_id": order["id"],
            "amount": order["amount"],
            "bought_at": order["price"],
            "side": order["side"],
            "status": order["status"],
            "days_open": (datetime.now() - datetime.strptime(order["datetime"], "%Y-%m-%dT%H:%M:%S.%fZ")).days
        }
        orders.append(order_info)
    return jsonify({"orders": orders})

# Endpoint 3: Sell Threshold Evaluation
@app.route("/GRID/sell-threshold", methods=["GET"])
def sell_threshold_evaluation():
    data = load_open_orders()
    exchange = initialize_exchange()
    try:
        ticker = exchange.fetch_ticker(PAIR)
        current_price = ticker["last"]
    except Exception as e:
        return jsonify({"error": f"Failed to fetch current price: {e}"}), 500

    evaluations = []
    for price, order in data["orders"].items():
        if order["side"] == "sell":
            sell_threshold = round(float(price), 4)  # Το sell threshold είναι η τιμή πώλησης
            status = "Not selling" if current_price < sell_threshold else "Selling"
            evaluations.append({
                "order_id": order["id"],
                "sell_threshold": sell_threshold,
                "current_price": current_price,
                "status": status
            })

    return jsonify({"evaluations": evaluations})

# Endpoint 4: Συνολικές Συναλλαγές
@app.route("/GRID/totals", methods=["GET"])
def get_totals():
    data = load_open_orders()
    statistics = data.get("statistics", {})
    return jsonify({
        "total_buys": statistics.get("total_buys", 0),
        "total_sells": statistics.get("total_sells", 0),
        "net_profit": statistics.get("net_profit", 0.0)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5013, debug=False)
