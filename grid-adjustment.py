import ccxt
import json
import time
import os
import logging
from datetime import datetime
import pushover

# Configuration
EXCHANGE_NAME = 'binance'
SYMBOL = 'XRP/USDT'
GRID_SIZE = 0.043
AMOUNT = 50
GRID_COUNT = 10
MAX_ORDERS = GRID_COUNT * 2
CRYPTO_CURRENCY = 'USDT'
OPEN_ORDERS_FILE = "/opt/python/grid-trading-bot/open_orders.json"
JSON_PATH = "/opt/python/grid-trading-bot/config.json"
PAUSE_FLAG_PATH = "/opt/python/grid-trading-bot/pause.flag"

# Για το function cancel_orders_outside_range
MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 2


# Παράμετροι Αποστολής E-mail
ENABLE_EMAIL_NOTIFICATIONS = True
ENABLE_PUSH_NOTIFICATIONS = True

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/opt/python/grid-trading-bot/grid_adjustment.log"),
        logging.StreamHandler()
    ]
)

# Load API keys
def load_keys():
    """Load API credentials and notification settings from a JSON file."""
    try:
        with open(JSON_PATH, "r") as file:
            keys = json.load(file)

            # Required API keys
            api_key = keys.get("API_KEY")
            api_secret = keys.get("API_SECRET")

            # Notification keys
            sendgrid_api_key = keys.get("SENDGRID_API_KEY")
            pushover_token = keys.get("PUSHOVER_TOKEN")
            pushover_user = keys.get("PUSHOVER_USER")
            email_sender = keys.get("EMAIL_SENDER")
            email_recipient = keys.get("EMAIL_RECIPIENT")

            # Check for missing keys
            missing_keys = []
            if not api_key or not api_secret:
                missing_keys.extend(["API_KEY", "API_SECRET"])
            if not sendgrid_api_key:
                missing_keys.append("SENDGRID_API_KEY")
            if not pushover_token:
                missing_keys.append("PUSHOVER_TOKEN")
            if not pushover_user:
                missing_keys.append("PUSHOVER_USER")
            if not email_sender:
                missing_keys.append("EMAIL_SENDER")
            if not email_recipient:
                missing_keys.append("EMAIL_RECIPIENT")

            if missing_keys:
                raise ValueError(f"Missing keys in the JSON file: {', '.join(missing_keys)}")

            return api_key, api_secret, sendgrid_api_key, pushover_token, pushover_user, email_sender, email_recipient
    except FileNotFoundError:
        raise FileNotFoundError(f"The specified JSON file '{JSON_PATH}' was not found.")
    except json.JSONDecodeError:
        raise ValueError(f"The JSON file '{JSON_PATH}' is not properly formatted.")
      

# Load API_KEY and API_SECRET from the JSON file
API_KEY, API_SECRET, SENDGRID_API_KEY, PUSHOVER_TOKEN, PUSHOVER_USER, EMAIL_SENDER, EMAIL_RECIPIENT = load_keys()




def create_pause_flag():
    """Δημιουργεί ένα flag αρχείο για pause."""
    with open(PAUSE_FLAG_PATH, "w") as f:
        f.write("PAUSED")



def remove_pause_flag():
    """Αφαιρεί το flag αρχείο pause."""
    if os.path.exists(PAUSE_FLAG_PATH):
        os.remove(PAUSE_FLAG_PATH)


        

# Initialize exchange
def initialize_exchange():
    try:
        exchange = getattr(ccxt, EXCHANGE_NAME)({
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "enableRateLimit": True
        })
        # Testnet ή Production
        exchange.set_sandbox_mode(False)
        exchange.load_markets()  # <--- load markets for safety
        logging.info(f"Connected to {EXCHANGE_NAME.upper()} - Markets loaded: {len(exchange.markets)}")
        return exchange
    except Exception as e:
        logging.error(f"Failed to connect to {EXCHANGE_NAME}: {e}")
        raise



def send_push_notification(message, log_to_file=True):
    """
    Στέλνει push notification μέσω Pushover.

    Args:
        message (str): Το μήνυμα που θα σταλεί.
        log_to_file (bool): Αν είναι True, καταγράφει το μήνυμα στο log αρχείο.
    """
    if not ENABLE_PUSH_NOTIFICATIONS:
        if log_to_file:
            logging.info("Push notifications are paused. Notification was not sent.")
        return

    try:
        # Αποστολή push notification μέσω Pushover
        po = pushover.Client(user_key=PUSHOVER_USER, api_token=PUSHOVER_TOKEN)
        po.send_message(message, title="Grid Bot Alert (range)")
        
        if log_to_file:
            logging.info("Push notification sent successfully!")
    except Exception as e:
        if log_to_file:
            logging.error(f"Error sending push notification: {e}")
            
            
            


# Fetch open orders from exchange
def fetch_open_orders(exchange):
    return exchange.fetch_open_orders(SYMBOL)




# Calculate grid levels
def calculate_grid_levels(current_price, grid_size, grid_count):
    buy_prices = [round(current_price - grid_size * i, 4) for i in range(1, grid_count + 1)]
    sell_prices = [round(current_price + grid_size * i, 4) for i in range(1, grid_count + 1)]

    logging.info(f"Adjusting grid dynamically...")
    logging.info(f"Adjusted buy orders: {buy_prices}")
    logging.info(f"Adjusted sell orders: {sell_prices}")

    return {"buy": buy_prices, "sell": sell_prices}



# Cancel orders outside range
def cancel_orders_outside_range(exchange, orders_to_cancel):
    canceled_order_ids = []
    for order in orders_to_cancel:
        try:
            exchange.cancel_order(order['id'], SYMBOL)
            logging.info(f"Canceled order | ID: {order['id']} | Price: {order['price']} | Side: {order['side']}")
            canceled_order_ids.append(order['id'])
        except Exception as e:
            logging.error(f"Failed to cancel order ID {order['id']}: {e}")

    # Μετά την ακύρωση, κάνε loop για να δεις αν πράγματι εξαφανίστηκαν
    if canceled_order_ids:
        for _ in range(MAX_RETRIES):
            open_orders = exchange.fetch_open_orders(SYMBOL)
            # Ελεγξε αν οι canceled_order_ids υπάρχουν ακόμα
            still_visible = []
            for order_id in canceled_order_ids:
                if any(o for o in open_orders if o.get('id') == order_id):
                    still_visible.append(order_id)

            if not still_visible:
                logging.info("All canceled orders have disappeared from open_orders.")
                
                #open_orders = exchange.fetch_open_orders(SYMBOL)
                #logging.info(f"Refetched open orders after confirming cancellations. Found {len(open_orders)} orders.")
                
                
                break

            logging.info(f"Canceled orders {still_visible} still present. Retrying in {RETRY_DELAY_SECONDS}s...")
            time.sleep(RETRY_DELAY_SECONDS)
        else:
            # Αν φτάσουμε εδώ, σημαίνει ότι μετά από MAX_RETRIES, κάποια canceled orders
            # δεν έχουν εμφανιστεί ως ακυρωμένες στο fetch_open_orders().
            logging.warning(f"Canceled orders still present after {MAX_RETRIES} retries: {still_visible}")

    return canceled_order_ids



def filter_orders_outside_grid(open_orders, grid_levels, tolerance=0.01):
    """
    Επιστρέφει τις παραγγελίες που είναι εκτός των επιτρεπτών τιμών στο grid, με ανοχή.
    """
    orders_to_cancel = []

    for order in open_orders:
        price = float(order["price"])
        side = order["side"].lower()

        if side == "buy":
            if not any(abs(price - grid_price) <= tolerance for grid_price in grid_levels["buy"]):
                orders_to_cancel.append(order)
        elif side == "sell":
            if not any(abs(price - grid_price) <= tolerance for grid_price in grid_levels["sell"]):
                orders_to_cancel.append(order)

    return orders_to_cancel



# Place new orders
def place_new_orders(exchange, grid_levels, existing_prices, max_orders):
    """
    Τοποθετεί νέες παραγγελίες με σεβασμό στο max_orders.
    """
    new_orders = {}
    total_orders = len(existing_prices)

    for side, levels in {"buy": grid_levels["buy"], "sell": grid_levels["sell"]}.items():
        for price in levels:
            if total_orders >= max_orders:
                logging.info("Reached maximum number of orders. Stopping further order placement.")
                return new_orders

            if round(price, 4) not in existing_prices:
                try:
                    if side == 'buy':
                        order = exchange.create_limit_buy_order(SYMBOL, AMOUNT, price)
                    else:
                        order = exchange.create_limit_sell_order(SYMBOL, AMOUNT, price)

                    new_orders[price] = {
                        "id": order['id'],
                        "symbol": SYMBOL,
                        "price": price,
                        "side": side,
                        "status": "open",
                        "amount": AMOUNT,
                    }
                    logging.info(f"Placed {side} order: {new_orders[price]}")
                    total_orders += 1
                    time.sleep(0.2)  # Avoid rate limits
                except Exception as e:
                    logging.error(f"Failed to place {side} order for {price}: {e}")

    return new_orders


# Save orders to file
def save_open_orders_to_file(file_path, open_orders, statistics=None, silent=False):
    try:
        orders_to_save = {}
        for _, order in open_orders.items():  # Αλλάξαμε το key loop από price σε _
            try:
                orders_to_save[str(order.get('price'))] = {  # Χρησιμοποιούμε το price ως κλειδί
                    'id': order.get('id'),
                    'symbol': order.get('symbol'),
                    'price': order.get('price'),
                    'side': order.get('side'),
                    'status': order.get('status'),
                    'amount': order.get('amount'),
                    'remaining': order.get('remaining'),
                    'datetime': order.get('datetime'),
                    'timestamp': order.get('timestamp'),
                }
            except AttributeError as e:
                logging.error(f"Error serializing order with ID {order.get('id')}: {e}. Order: {order}")
                continue

        data_to_save = {
            "orders": orders_to_save,
            "statistics": statistics if statistics else {
                "total_buys": 0,
                "total_sells": 0,
                "net_profit": 0.0
            }
        }

        temp_file_path = file_path + ".tmp"
        with open(temp_file_path, 'w') as f:
            json.dump(data_to_save, f, indent=4)
        os.replace(temp_file_path, file_path)

        if not silent:
            logging.info(f"Saved open orders and statistics to {file_path}")
    except Exception as e:
        logging.error(f"Failed to save open orders and statistics to file: {e}")





# -- Νέες βοηθητικές συναρτήσεις, προσαρμοσμένες ώστε να χρησιμοποιούν τα παραπάνω --

def fetch_and_initialize_exchange():
    """
    1) Καλεί την initialize_exchange()
    2) Παίρνει το current_price
    3) Επιστρέφει (exchange, current_price)
    """
    # Χρησιμοποιούμε τη δική σου βασική συνάρτηση
    exchange = initialize_exchange()
    
    # Παίρνουμε το ticker για να βρούμε την τρέχουσα τιμή
    ticker = exchange.fetch_ticker(SYMBOL)
    current_price = ticker['last']
    
    logging.info(f"Current price: {current_price} {CRYPTO_CURRENCY}")
    return exchange, current_price


def fetch_and_check_open_orders(exchange):
    """
    1) Καλεί τη δική σου fetch_open_orders(exchange)
    2) Κάνει logging + checks
    3) Επιστρέφει open_orders ή None αν δεν υπάρχουν
    """
    # Χρησιμοποιούμε τη δική σου βασική συνάρτηση
    open_orders = fetch_open_orders(exchange)
    logging.info(f"Fetched {len(open_orders)} open orders from {EXCHANGE_NAME.upper()}.")
    logging.debug(f"Open orders fetched from {EXCHANGE_NAME.upper()}: {open_orders}")
    
    # Έλεγχος αν δεν υπάρχουν open orders
    if not open_orders:
        logging.warning(f"No open orders fetched from {EXCHANGE_NAME.upper()}. Exiting...")
        return None
    
    return open_orders


# -- Οι υπόλοιπες βοηθητικές συναρτήσεις σου (ίδιες όπως πριν) --

def separate_buy_sell_orders(open_orders):
    buy_orders = sorted(
        [round(float(order['price']), 4) for order in open_orders if order['side'] == 'buy']
    )
    sell_orders = sorted(
        [round(float(order['price']), 4) for order in open_orders if order['side'] == 'sell']
    )
    logging.info(f"Buy orders on exchange: {buy_orders}")
    logging.info(f"Sell orders on exchange: {sell_orders}")
    return buy_orders, sell_orders

def find_farthest_orders(buy_orders, sell_orders):
    farthest_buy_order = buy_orders[0] if buy_orders else None
    farthest_sell_order = sell_orders[-1] if sell_orders else None
    logging.info(f"Farthest buy order: {farthest_buy_order}")
    logging.info(f"Farthest sell order: {farthest_sell_order}")
    return farthest_buy_order, farthest_sell_order

def find_orders_out_of_range(open_orders, current_price, buy_orders, sell_orders):
    orders_to_cancel = []
    new_buy_orders = []
    new_sell_orders = []
    
    # Υπολογισμός των ορίων του grid
    lower_bound = current_price - (GRID_SIZE * GRID_COUNT)
    upper_bound = current_price + (GRID_SIZE * GRID_COUNT)

    farthest_buy_order = buy_orders[0] if buy_orders else None
    farthest_sell_order = sell_orders[-1] if sell_orders else None

    # Έλεγχος για ακύρωση της πιο απομακρυσμένης buy παραγγελίας
    if farthest_buy_order and farthest_buy_order < lower_bound:
        try:            
            order = next((order for order in open_orders if abs(float(order['price']) - farthest_buy_order) < 0.0001), None)
            
            orders_to_cancel.append(order)
            logging.info(f"Buy order at price {farthest_buy_order} is out of range. "
                         f"Lower bound: {lower_bound:.4f}. It will be canceled.")
        except Exception as e:
            logging.error(f"Error finding farthest buy order: {e}")

    # Έλεγχος για ακύρωση της πιο απομακρυσμένης sell παραγγελίας
    if farthest_sell_order and farthest_sell_order > upper_bound:
        try:
            order = next((order for order in open_orders if abs(float(order['price']) - farthest_sell_order) < 0.0001), None)

            orders_to_cancel.append(order)
            logging.info(f"Sell order at price {farthest_sell_order} is out of range. "
                         f"Upper bound: {upper_bound:.4f}. It will be canceled.")
        except Exception as e:
            logging.error(f"Error finding farthest sell order: {e}")
    
    if orders_to_cancel:
        logging.info(f"Orders to cancel: {len(orders_to_cancel)}")
        logging.info(f"Order prices to cancel: {[order['price'] for order in orders_to_cancel]}")
    else:
        logging.info("No orders to cancel.")
    
    logging.debug(f"Orders to cancel (prices): {[order['price'] for order in orders_to_cancel if isinstance(order, dict)]}")

    return orders_to_cancel, new_buy_orders, new_sell_orders





def process_canceled_orders(exchange, canceled_orders, all_orders, current_price, new_buy_orders, new_sell_orders):
    """
    Επεξεργάζεται τις ακυρωμένες παραγγελίες, αντικαθιστά τις θέσεις τους και ανανεώνει το αρχείο παραγγελιών.
    """
    try:
        # Φόρτωμα όλων των παραγγελιών από το γνωστό αρχείο
        with open(OPEN_ORDERS_FILE, 'r') as f:
            data = json.load(f)
            all_orders_from_file = data.get("orders", {})

        # Ενημερωμένο dictionary για παραγγελίες
        updated_orders = all_orders_from_file.copy()

        for order_id in canceled_orders:
            logging.info(f"Processing canceled order ID: {order_id}")

            # Αναζήτηση της παραγγελίας με βάση το Order ID
            order_details = None
            for price, order in all_orders_from_file.items():
                if str(order.get('id')) == str(order_id):
                    order_details = order
                    # Αφαιρούμε την παραγγελία από το ενημερωμένο dictionary
                    updated_orders.pop(price, None)
                    break

            if not order_details:
                logging.warning(f"Order details not found in file for ID: {order_id}")
                continue

            logging.info(f"Found order details for ID {order_id}: {order_details}")

            # Προσθήκη νέας παραγγελίας
            if order_details['side'] == 'buy':
                price = round(current_price - GRID_SIZE * (len(new_buy_orders) + 1), 4)
                logging.info(f"Preparing to place new buy order at price: {price}")
                try:
                    new_order = exchange.create_limit_buy_order(SYMBOL, AMOUNT, price)
                    if isinstance(new_order, dict) and 'id' in new_order and 'price' in new_order:
                        logging.info(f"Placed new buy order successfully: {new_order}")
                        new_buy_orders.append({
                            "id": new_order['id'],
                            "price": new_order['price'],
                            "side": "buy",
                        })
                        updated_orders[str(new_order['price'])] = {
                            "id": new_order['id'],
                            "price": new_order['price'],
                            "side": "buy",
                            "status": "open",
                            "amount": AMOUNT,
                            "remaining": AMOUNT,
                            "datetime": new_order.get('datetime'),
                            "timestamp": new_order.get('timestamp'),
                        }
                except Exception as e:
                    logging.error(f"Error placing new buy order at price {price}: {e}")

            elif order_details['side'] == 'sell':
                price = round(current_price + GRID_SIZE * (len(new_sell_orders) + 1), 4)
                logging.info(f"Preparing to place new sell order at price: {price}")
                try:
                    new_order = exchange.create_limit_sell_order(SYMBOL, AMOUNT, price)
                    if isinstance(new_order, dict) and 'id' in new_order and 'price' in new_order:
                        logging.info(f"Placed new sell order successfully: {new_order}")
                        new_sell_orders.append({
                            "id": new_order['id'],
                            "price": new_order['price'],
                            "side": "sell",
                        })
                        updated_orders[str(new_order['price'])] = {
                            "id": new_order['id'],
                            "price": new_order['price'],
                            "side": "sell",
                            "status": "open",
                            "amount": AMOUNT,
                            "remaining": AMOUNT,
                            "datetime": new_order.get('datetime'),
                            "timestamp": new_order.get('timestamp'),
                        }
                except Exception as e:
                    logging.error(f"Error placing new sell order at price {price}: {e}")

        # Αποθήκευση των ενημερωμένων παραγγελιών στο αρχείο
        with open(OPEN_ORDERS_FILE, 'w') as f:
            json.dump({"orders": updated_orders}, f, indent=4)

        #logging.info(f"Updated open orders file after processing canceled orders.")

    except Exception as e:
        logging.error(f"Error processing canceled orders: {e}")








def maintain_order_balance(exchange, current_price, buy_orders, sell_orders, new_buy_orders, new_sell_orders):
    """
    Διατηρεί την ισορροπία μεταξύ buy και sell παραγγελιών, αποφεύγοντας να ξεπεράσει το MAX_ORDERS.
    """
    # Φόρτωσε τα open orders και έλεγξε τη μορφή τους
    open_orders = exchange.fetch_open_orders(SYMBOL)
    if not isinstance(open_orders, list):
        logging.error(f"Expected open_orders to be a list but got {type(open_orders)}.")
        return

    logging.debug(f"Refetched open orders after confirming cancellations. Found {len(open_orders)} orders.")
    
    total_orders = len(open_orders)
    if total_orders >= MAX_ORDERS:
        logging.debug(f"We have {total_orders} orders, which is at or above MAX_ORDERS={MAX_ORDERS}.")
        logging.info(f"No new orders will be placed to maintain balance. ({total_orders})")
        return

    # Επαλήθευση ισορροπίας για buy παραγγελίες
    while (len(new_buy_orders) + len(buy_orders)) < (len(new_sell_orders) + len(sell_orders)):
        total_orders = len(open_orders)
        if total_orders >= MAX_ORDERS:
            logging.info(f"Reached MAX_ORDERS={MAX_ORDERS} while trying to add buy orders. Stopping.")
            break

        logging.info("Adjusting buy orders to maintain balance...")
        price = round(current_price - GRID_SIZE * (len(buy_orders) + len(new_buy_orders) + 1), 4)

        # Επαλήθευση τιμών
        existing_prices = []
        for order in buy_orders + new_buy_orders:
            if isinstance(order, dict) and 'price' in order:
                try:
                    existing_prices.append(round(float(order['price']), 4))
                except (ValueError, TypeError) as e:
                    logging.error(f"Invalid price in order: {order}. Error: {e}")
        
        if price not in existing_prices:
            try:
                order = exchange.create_limit_buy_order(SYMBOL, AMOUNT, price)
                if isinstance(order, dict) and 'id' in order and 'price' in order:
                    new_buy_orders.append({
                        "id": str(order['id']),
                        "price": float(order['price']),
                        "side": "buy",
                    })
                    logging.info(f"Placed new buy order at price: {price:.4f} to maintain order balance.")
                    # Επιπλέον logging με βασικές πληροφορίες της παραγγελίας
                    logging.info(f"Order Details - ID: {order['id']}, Price: {order['price']:.4f}, Amount: {AMOUNT}, Side: buy")                    
            except Exception as e:
                logging.error(f"Failed to place new buy order at price {price:.4f}: {e}")
                

    # Επαλήθευση ισορροπίας για sell παραγγελίες
    while (len(new_sell_orders) + len(sell_orders)) < (len(new_buy_orders) + len(buy_orders)):
        total_orders = len(open_orders)
        if total_orders >= MAX_ORDERS:
            logging.info(f"Reached MAX_ORDERS={MAX_ORDERS} while trying to add sell orders. Stopping.")
            break

        price = round(current_price + GRID_SIZE * (len(sell_orders) + len(new_sell_orders) + 1), 4)

        # Επαλήθευση τιμών
        existing_prices = []
        for order in sell_orders + new_sell_orders:
            if isinstance(order, dict) and 'price' in order:
                try:
                    existing_prices.append(round(float(order['price']), 4))
                except (ValueError, TypeError) as e:
                    logging.error(f"Invalid price in order: {order}. Error: {e}")
        
        if price not in existing_prices:
            try:
                order = exchange.create_limit_sell_order(SYMBOL, AMOUNT, price)
                if isinstance(order, dict) and 'id' in order and 'price' in order:
                    new_sell_orders.append({
                        "id": str(order['id']),
                        "price": float(order['price']),
                        "side": "sell",
                    })
                    logging.info(f"Placed new sell order at price: {price:.4f} to maintain order balance.")
                    # Επιπλέον logging με βασικές πληροφορίες της παραγγελίας
                    logging.info(f"Order Details - ID: {order['id']}, Price: {order['price']:.4f}, Amount: {AMOUNT}, Side: sell")                    
            except Exception as e:
                logging.error(f"Failed to place new sell order at price {price:.4f}: {e}")
                




def handle_excess_orders(exchange, buy_orders, sell_orders):
    total_orders = len(buy_orders) + len(sell_orders)
    
    logging.debug(f"Total buy orders: {len(buy_orders)}")
    logging.debug(f"Total sell orders: {len(sell_orders)}")
    logging.debug(f"Total orders (buy + sell): {total_orders}")
    
    if total_orders > MAX_ORDERS:
        excess = total_orders - MAX_ORDERS
        logging.warning(f"Excess orders detected: {excess}. Adjusting...")
        
        while excess > 0:
            if buy_orders and len(buy_orders) > len(sell_orders):
                price_to_cancel = buy_orders.pop()
                
                # Fetch open orders
                open_orders = fetch_open_orders(exchange)

                orders_summary = ', '.join(
                    ["id={}, price={}, side={}, status={}".format(
                        order.get('id'),
                        order.get('price'),
                        order.get('side'),
                        order.get('status')
                    ) for order in open_orders]
                )
                logging.debug("Fetched open orders: [{}]".format(orders_summary))
                
                # Find the matching order
                order_to_cancel = next(
                    (order for order in open_orders if order['id'] == price_to_cancel),  # Αναζήτηση με βάση το id
                    None
                )
                
                if not order_to_cancel:
                    logging.warning(f"No matching buy order found for price: {price_to_cancel}")
                else:
                    try:
                        logging.info(f"Price of buy order to cancel: {order_to_cancel['price']}, Order ID: {order_to_cancel['id']}")
                        exchange.cancel_order(order_to_cancel['id'], SYMBOL)
                        logging.info(f"Successfully canceled buy order at price: {order_to_cancel['price']}")
                    except Exception as e:
                        logging.error(f"Failed to cancel buy order: {e}")
            elif sell_orders:
                price_to_cancel = sell_orders.pop()
                
                # Fetch open orders
                open_orders = fetch_open_orders(exchange)
                logging.info(f"Fetched open orders: {open_orders}")
                
                # Find the matching order
                order_to_cancel = next(
                    (order for order in open_orders if order['id'] == price_to_cancel),  # Αναζήτηση με βάση το id
                    None
                )
                
                if not order_to_cancel:
                    logging.warning(f"No matching sell order found for price: {price_to_cancel}")
                else:
                    try:
                        logging.info(f"Price of sell order to cancel: {order_to_cancel['price']}, Order ID: {order_to_cancel['id']}")
                        exchange.cancel_order(order_to_cancel['id'], SYMBOL)
                        logging.info(f"Successfully canceled sell order at price: {order_to_cancel['price']}")
                    except Exception as e:
                        logging.error(f"Failed to cancel sell order: {e}")
            excess -= 1
        
        send_push_notification(f"ALERT: Grid range adjusted successfully!")
    else:
        logging.info(f"No excess orders detected. ({total_orders})")



        


# η κεντρική σου συνάρτηση
def adjust_grid_range():
    try:
        logging.info(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        logging.info(f"Starting {SYMBOL} Grid Trading bot (grid range worker)...")
        
        iteration_start = time.time()

        # 1) Φόρτωμα κλειδιών & αρχικοποίηση (χρησιμοποιεί initialize_exchange())
        exchange, current_price = fetch_and_initialize_exchange()

        # 2) Fetch open orders & check (χρησιμοποιεί fetch_open_orders())
        open_orders = fetch_and_check_open_orders(exchange)
        if not open_orders:
            return  # Σταματάμε, αφού δεν υπάρχουν open_orders
            
            
          

        
        logging.debug(f"2) Type of open_orders: {type(open_orders)}")
        logging.debug(f"Contents of open_orders: {open_orders}")

        
        # 3) Ξεχωρισμός buy / sell
        buy_orders, sell_orders = separate_buy_sell_orders(open_orders)

        # 4) Εντοπισμός παραγγελιών που είναι εκτός range
        orders_to_cancel, new_buy_orders, new_sell_orders = find_orders_out_of_range(
            open_orders, current_price, buy_orders, sell_orders
        )

        logging.debug(f"4) Type of open_orders: {type(open_orders)}")
        
        # 5) Αν υπάρχουν παραγγελίες προς ακύρωση, ακύρωσέ τις
        if orders_to_cancel:
            logging.info(f"Starting cancellation process for {len(orders_to_cancel)} orders.")
            canceled_orders = cancel_orders_outside_range(exchange, orders_to_cancel)
            logging.debug(f"Canceled {len(canceled_orders)} orders.")
            logging.info(f"Canceled orders details: {canceled_orders}")
            
            # Ενημέρωση του αρχείου μετά την ακύρωση
            logging.debug(f"5) Type of open_orders: {type(open_orders)}")
            logging.debug(f"Contents of open_orders: {open_orders}")

            if isinstance(open_orders, list):
                # Μετατροπή λίστας σε dictionary χρησιμοποιώντας την τιμή ως κλειδί
                open_orders = {order['price']: order for order in open_orders}
            
            #save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders)
            #logging.info(f"Updated open orders file after cancellation.")

            
            # Επεξεργασία canceled orders & δημιουργία νέων (buy/sell)
            try:
                process_canceled_orders(
                    exchange, canceled_orders, open_orders, current_price,
                    new_buy_orders, new_sell_orders
                )




                
                # Ενημέρωση του αρχείου μετά την επεξεργασία των ακυρωμένων παραγγελιών
                logging.debug(f"5) Type of open_orders: {type(open_orders)}")
                logging.debug(f"Contents of open_orders: {open_orders}")  
                

                if isinstance(open_orders, list):
                    # Μετατροπή λίστας σε dictionary χρησιμοποιώντας την τιμή ως κλειδί
                    open_orders = {order['price']: order for order in open_orders}                


                
                #save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders)
                #logging.info(f"Updated open orders file after processing canceled orders.")                
                
            except Exception as e:
                logging.error(f"Error in new order placement logic: {e}")
                send_push_notification(f"ALERT: Error in new order placement logic: {e}")

            # Τελικό logging
            logging.debug(f"Final new_buy_orders: {new_buy_orders}")
            logging.debug(f"Final new_sell_orders: {new_sell_orders}")
        else:
            logging.info("No grid alteration was made. All orders are within the range.")

        
        
        
        
        # 6) Διατήρηση ισορροπίας μεταξύ buy & sell
        maintain_order_balance(exchange, current_price, buy_orders, sell_orders, new_buy_orders, new_sell_orders)

        # 7) Έλεγχος & διόρθωση για υπερβάλλοντες παραγγελίες
        handle_excess_orders(exchange, buy_orders, sell_orders)
        
        
        # 8) Στο τέλος του adjust_grid_range
        logging.debug(f"8) Type of open_orders: {type(open_orders)}")
        logging.debug(f"Contents of open_orders: {open_orders}")  

        if isinstance(open_orders, list):
            # Μετατροπή λίστας σε dictionary χρησιμοποιώντας την τιμή ως κλειδί
            open_orders = {order['price']: order for order in open_orders}

        
        save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders)
        
        
        # Μετά την ολοκλήρωση του iteration
        iteration_end = time.time()
        logging.info(f"Bot execution completed in {iteration_end - iteration_start:.2f} seconds.")        

    except Exception as e:
        logging.error(f"An error occurred: {e}")





# Κύριος κώδικας του Grid Adjustment Script
if __name__ == "__main__":
    try:
        # Δημιουργία του pause flag
        create_pause_flag()
        
        # Λογική ρύθμισης grid
        adjust_grid_range()

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        # Διαγραφή του pause flag στο τέλος
        remove_pause_flag()