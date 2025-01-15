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
    """
    Ακυρώνει τις παραγγελίες που έχουν ήδη φιλτραριστεί.
    """
    canceled_orders = []

    for order in orders_to_cancel:
        order_id = order["id"]
        price = round(float(order["price"]), 4)
        side = order["side"]

        try:
            exchange.cancel_order(order_id, SYMBOL)
            canceled_orders.append(order_id)
            logging.info(f"Canceled order | ID: {order_id} | Price: {price:.4f} | Side: {side}")
            time.sleep(0.2)  # Avoid rate limits
        except Exception as e:
            logging.error(f"Failed to cancel order | ID: {order_id} | Error: {e}")

    return canceled_orders



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
        for price, order in open_orders.items():
            try:
                orders_to_save[str(price)] = {
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
                logging.error(f"Error serializing order at price {price}: {e}. Order: {order}")
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

# Main function
def adjust_grid_range():
    try:
        logging.info(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        logging.info(f"Starting {SYMBOL} Grid Trading bot (grid range worker)...")
        
        # Load keys and initialize exchange
        exchange = initialize_exchange()

        # Fetch current price
        ticker = exchange.fetch_ticker(SYMBOL)
        current_price = ticker['last']
        logging.info(f"Current price: {current_price} {CRYPTO_CURRENCY}")

        # Fetch open orders
        open_orders = fetch_open_orders(exchange)
        logging.info(f"Fetched {len(open_orders)} open orders from {EXCHANGE_NAME.upper()}.")
        logging.debug(f"Open orders fetched from {EXCHANGE_NAME.upper()}: {open_orders}")
        
        # Έλεγχος αν δεν υπάρχουν open orders
        if not open_orders:
            logging.warning(f"No open orders fetched from {EXCHANGE_NAME.upper()}. Exiting...")
            return        
        
        # Διαχωρισμός των παραγγελιών σε buy και sell από ανταλλακτήριο
        buy_orders = sorted([round(float(order['price']), 4) for order in open_orders if order['side'] == 'buy'])
        sell_orders = sorted([round(float(order['price']), 4) for order in open_orders if order['side'] == 'sell'])

        logging.info(f"Buy orders on exchange: {buy_orders}")
        logging.info(f"Sell orders on exchange: {sell_orders}")
        
        # Εντοπισμός παραγγελιών στο μακρινό άκρο
        farthest_buy_order = buy_orders[0] if buy_orders else None
        farthest_sell_order = sell_orders[-1] if sell_orders else None
        
        # Debug logging για τις τιμές
        logging.info(f"Farthest buy order: {farthest_buy_order}")
        logging.info(f"Farthest sell order: {farthest_sell_order}")        

        # Ελέγχουμε αν οι πιο μακρινές παραγγελίες είναι εκτός του grid range
        orders_to_cancel = []
        
        # Εντοπισμός των παραγγελιών που είναι εκτός του εύρους
        if farthest_buy_order and farthest_buy_order < current_price - (GRID_SIZE * GRID_COUNT):
            orders_to_cancel.append(next(order for order in open_orders if float(order['price']) == farthest_buy_order))
        if farthest_sell_order and farthest_sell_order > current_price + (GRID_SIZE * GRID_COUNT):
            orders_to_cancel.append(next(order for order in open_orders if float(order['price']) == farthest_sell_order))


        logging.info(f"Orders to cancel: {len(orders_to_cancel)}")
        logging.info(f"Orders to cancel: {[order['price'] for order in orders_to_cancel]}")


#############################################################################################################################################################################


        if orders_to_cancel:
            logging.info(f"Starting cancellation process for {len(orders_to_cancel)} orders.")
            canceled_orders = cancel_orders_outside_range(exchange, orders_to_cancel)
            logging.info(f"Canceled {len(canceled_orders)} orders.")
            logging.info(f"Canceled orders details: {canceled_orders}")

            new_buy_orders = []
            new_sell_orders = []

            try:
                # Process canceled orders
                for order_id in canceled_orders:
                    logging.info(f"Processing canceled order ID: {order_id}")
                    try:
                        # Find order details
                        order_details = next((o for o in open_orders if isinstance(o, dict) and o.get('id') == order_id), None)
                        if not order_details:
                            logging.warning(f"Order details not found or invalid format for ID: {order_id}")
                            continue

                        logging.info(f"Found order details for ID {order_id}: {order_details}")

                        # Create new buy order
                        if order_details['side'] == 'buy':
                            price = round(current_price - GRID_SIZE * (len(new_buy_orders) + 1), 4)
                            logging.info(f"Preparing to place new buy order at price: {price}")
                            try:
                                new_order = exchange.create_limit_buy_order(SYMBOL, AMOUNT, price)
                                logging.info(f"Raw new_order response for buy: {new_order}")
                                if isinstance(new_order, dict) and 'id' in new_order and 'price' in new_order:
                                    # Validate types
                                    if not isinstance(new_order['id'], str) or not isinstance(new_order['price'], (float, int)):
                                        logging.error(f"Unexpected types in new_order for buy: {new_order}")
                                        continue
                                    logging.info(f"Placed new buy order successfully: {new_order}")
                                    new_buy_orders.append({
                                        "id": new_order['id'],
                                        "price": float(new_order['price']),  # Ensure proper type
                                        "side": "buy",
                                    })
                                else:
                                    logging.error(f"Unexpected response from create_limit_buy_order: {new_order}")
                                    send_push_notification(f"ALERT: Unexpected response from create_limit_buy_order: {new_order}")
                            except Exception as e:
                                logging.error(f"Error placing new buy order at price {price}: {e}")
                                send_push_notification(f"ALERT: Error placing new buy order: {e}")

                        # Create new sell order
                        elif order_details['side'] == 'sell':
                            price = round(current_price + GRID_SIZE * (len(new_sell_orders) + 1), 4)
                            logging.info(f"Preparing to place new sell order at price: {price}")
                            try:
                                new_order = exchange.create_limit_sell_order(SYMBOL, AMOUNT, price)
                                logging.info(f"Raw new_order response for sell: {new_order}")
                                if isinstance(new_order, dict) and 'id' in new_order and 'price' in new_order:
                                    # Validate types
                                    if not isinstance(new_order['id'], str) or not isinstance(new_order['price'], (float, int)):
                                        logging.error(f"Unexpected types in new_order for sell: {new_order}")
                                        continue
                                    logging.info(f"Placed new sell order successfully: {new_order}")
                                    new_sell_orders.append({
                                        "id": new_order['id'],
                                        "price": float(new_order['price']),  # Ensure proper type
                                        "side": "sell",
                                    })
                                else:
                                    logging.error(f"Unexpected response from create_limit_sell_order: {new_order}")
                                    send_push_notification(f"ALERT: Unexpected response from create_limit_sell_order: {new_order}")
                            except Exception as e:
                                logging.error(f"Error placing new sell order at price {price}: {e}")
                                send_push_notification(f"ALERT: Error placing new sell order: {e}")
                    except Exception as e:
                        logging.error(f"Error processing canceled order ID {order_id}: {e}")
                        send_push_notification(f"ALERT: Error processing canceled order ID {order_id}: {e}")
            except Exception as e:
                logging.error(f"Error in new order placement logic: {e}")
                send_push_notification(f"ALERT: Error in new order placement logic: {e}")

            # Final state logging
            logging.info(f"Final new_buy_orders: {new_buy_orders}")
            logging.info(f"Final new_sell_orders: {new_sell_orders}")







            #-------------------------------------------------------------------------------------------------------------------------




            # Έλεγχος για ισορροπία παραγγελιών
            while len(new_buy_orders) + len(buy_orders) < len(new_sell_orders) + len(sell_orders):
                price = round(current_price - GRID_SIZE * (len(buy_orders) + len(new_buy_orders) + 1), 4)
                if price not in [o['price'] for o in buy_orders + new_buy_orders]:  # Avoid duplicates
                    try:
                        order = exchange.create_limit_buy_order(SYMBOL, AMOUNT, price)
                        new_buy_orders.append({
                            "id": order['id'],
                            "price": price,
                            "side": "buy",
                            "amount": AMOUNT,
                            "status": "open",
                        })
                        logging.info(f"Placed new buy order at price: {price}")
                        time.sleep(0.2)  # Avoid rate limits
                    except Exception as e:
                        logging.error(f"Failed to place new buy order at price {price}: {e}")
                        break

            while len(new_sell_orders) + len(sell_orders) < len(new_buy_orders) + len(buy_orders):
                price = round(current_price + GRID_SIZE * (len(sell_orders) + len(new_sell_orders) + 1), 4)
                if price not in [o['price'] for o in sell_orders + new_sell_orders]:  # Avoid duplicates
                    try:
                        order = exchange.create_limit_sell_order(SYMBOL, AMOUNT, price)
                        new_sell_orders.append({
                            "id": order['id'],
                            "price": price,
                            "side": "sell",
                            "amount": AMOUNT,
                            "status": "open",
                        })
                        logging.info(f"Placed new sell order at price: {price}")
                        time.sleep(0.2)  # Avoid rate limits
                    except Exception as e:
                        logging.error(f"Failed to place new sell order at price {price}: {e}")
                        break

            # Υπολογισμός συνολικού αριθμού παραγγελιών
            total_orders = len(buy_orders) + len(sell_orders) + len(new_buy_orders) + len(new_sell_orders)

            # Έλεγχος και διόρθωση για υπερβάλλοντες παραγγελίες
            if total_orders > MAX_ORDERS:
                excess = total_orders - MAX_ORDERS
                logging.warning(f"Excess orders detected: {excess}. Adjusting...")
                
                # Διαγραφή επιπλέον παραγγελιών από τις νέες παραγγελίες
                while excess > 0:
                    if new_buy_orders and len(new_buy_orders) > len(new_sell_orders):
                        order_to_cancel = new_buy_orders.pop()
                        try:
                            exchange.cancel_order(order_to_cancel['id'], SYMBOL)
                            logging.info(f"Canceled excess buy order at price: {order_to_cancel['price']}")
                        except Exception as e:
                            logging.error(f"Failed to cancel excess buy order: {e}")
                    elif new_sell_orders and len(new_sell_orders) > len(new_buy_orders):
                        order_to_cancel = new_sell_orders.pop()
                        try:
                            exchange.cancel_order(order_to_cancel['id'], SYMBOL)
                            logging.info(f"Canceled excess sell order at price: {order_to_cancel['price']}")
                        except Exception as e:
                            logging.error(f"Failed to cancel excess sell order: {e}")
                    excess -= 1

                    
                    
#############################################################################################################################################################################
                   
                    

            # Καταγραφή τελικών παραγγελιών
            final_buy_orders = buy_orders + [order['price'] for order in new_buy_orders]
            final_sell_orders = sell_orders + [order['price'] for order in new_sell_orders]

            logging.info(f"Final buy orders: {final_buy_orders}")
            logging.info(f"Final sell orders: {final_sell_orders}")

            send_push_notification(f"ALERT: Grid range adjusted successfully!")

        else:
            logging.info("No grid alteration was made. All orders are within the range.")

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