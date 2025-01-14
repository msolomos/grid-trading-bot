from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import ccxt
import time
import logging
import json
import os
import pushover



# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Ρύθμιση για εμφάνιση μόνο INFO και πάνω
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("grid_trading_bot.log"),  # Αρχείο log
        logging.StreamHandler()  # Κονσόλα
    ]
)




# 1. ---------------------- Static / Global configuration ----------------------
ENABLE_DEMO_MODE = False  # Toggle for mockup data during testing
mock_order_counter = 0

# Configuration parameters
EXCHANGE_NAME = 'coinbase'
SYMBOL = 'XRP/USDC'
OPEN_ORDERS_FILE = 'open_orders.json'
CRYPTO_SYMBOL = 'XRP'
CRYPTO_CURRENCY = 'USDC'



# Number of grid levels
GRID_SIZE = 0.043
# AMOUNT of pair per order
AMOUNT = 50
# Number of grids above and below current price
GRID_COUNT = 10
# How often to update (seconds)
UPDATE_INTERVAL = 300

# Στατική μεταβλητή για τη διαδρομή του JSON αρχείου
JSON_PATH = "/opt/python/grid-trading-bot/config.json"

# Παράμετροι Αποστολής E-mail
ENABLE_EMAIL_NOTIFICATIONS = True
ENABLE_PUSH_NOTIFICATIONS = True




# 2. ---------------------- Load Keys from external file ----------------------
def load_keys():
    """Load API credentials and notification settings from a JSON file."""
    try:
        with open(JSON_PATH, "r") as file:
            keys = json.load(file)
            
            # Απαραίτητα κλειδιά για το API
            api_key = keys.get("API_KEY")
            api_secret = keys.get("API_SECRET")
            
            # Κλειδιά για ειδοποιήσεις
            sendgrid_api_key = keys.get("SENDGRID_API_KEY")
            pushover_token = keys.get("PUSHOVER_TOKEN")
            pushover_user = keys.get("PUSHOVER_USER")
            email_sender = keys.get("EMAIL_SENDER")
            email_recipient = keys.get("EMAIL_RECIPIENT")

            # Έλεγχος για κενές τιμές
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
             





# 3. ---------------------- Notifications ----------------------
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
        po.send_message(message, title="Grid Bot Alert")
        
        if log_to_file:
            logging.info("Push notification sent successfully!")
    except Exception as e:
        if log_to_file:
            logging.error(f"Error sending push notification: {e}")





def sendgrid_email(transaction_type, price, quantity, net_profit=None, final_score=None, reasoning=None):
    """
    Στέλνει email μέσω SendGrid για ενέργειες του grid bot.

    Args:
        transaction_type (str): 'buy' ή 'sell'.
        price (float): Η τιμή της συναλλαγής.
        quantity (float): Η ποσότητα της συναλλαγής.
        net_profit (float, optional): Καθαρό κέρδος (μόνο για πωλήσεις).
        final_score (float, optional): Βαθμολογία συναλλαγής.
        reasoning (str, optional): Αιτιολόγηση συναλλαγής.
    """
    if not ENABLE_EMAIL_NOTIFICATIONS:
        logging.info("Email notifications are paused. Email was not sent.")
        return

    # Δημιουργία περιεχομένου email
    transaction = "Αγορά" if transaction_type == 'buy' else "Πώληση"
    current_time = datetime.now().strftime("%d/%m/%Y %H:%M")
    html_content = f"""
        Πραγματοποιήθηκε <strong>{transaction} {CRYPTO_SYMBOL}</strong>.<br>
        Τεμάχια: {quantity}<br>
        Τιμή: {round(price, 2)} {CRYPTO_CURRENCY}<br>
        Ημερομηνία: {current_time}<br>
    """

    if final_score is not None:
        html_content += f"Βαθμολογία: {final_score}<br>"
    if reasoning:
        html_content += f"Αιτιολόγηση: {reasoning}<br>"
    if transaction_type == 'sell' and net_profit is not None:
        html_content += f"Καθαρό Κέρδος: {round(net_profit, 2)} {CRYPTO_CURRENCY}<br>"
    if ENABLE_DEMO_MODE:
        html_content += """
            <div style="border: 2px solid red; padding: 10px; margin-top: 20px;">
                <strong>DEMO MODE:</strong> Αυτή είναι μια προσομοίωση. Καμία πραγματική συναλλαγή δεν έχει εκτελεστεί.
            </div>
        """

    message = Mail(
        from_email=EMAIL_SENDER,
        to_emails=EMAIL_RECIPIENT,
        subject=f'Grid Bot - {transaction} {CRYPTO_SYMBOL}',
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        logging.info("Email sent successfully!")
    except Exception as e:
        logging.error(f"Error sending email: {e}")




# 4. ---------------------- Initialize Exchange ----------------------
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
        logging.info(f"Connected to {EXCHANGE_NAME} - Markets loaded: {len(exchange.markets)}")
        return exchange
    except Exception as e:
        logging.error(f"Failed to connect to {EXCHANGE_NAME}: {e}")
        raise
        

def get_current_price(exchange):
    try:
        ticker = exchange.fetch_ticker(SYMBOL)
        return ticker['last']
    except Exception as e:
        logging.error(f"Failed to fetch ticker for {SYMBOL}: {e}")
        raise



# 5. ---------------------- Order Placement / Cancel ----------------------
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

        logging.debug(f"Orders to be saved: {orders_to_save}")

        # Δημιουργία δομής δεδομένων για αποθήκευση
        data_to_save = {
            "orders": orders_to_save,
            "statistics": statistics if statistics else {
                "total_buys": 0,
                "total_sells": 0,
                "net_profit": 0.0
            }
        }

        # Αποθήκευση σε προσωρινό αρχείο
        temp_file_path = file_path + ".tmp"
        with open(temp_file_path, 'w') as f:
            json.dump(data_to_save, f, indent=4)
        os.replace(temp_file_path, file_path)  # Αντικατάσταση του παλιού αρχείου

        if not silent:
            logging.info(f"Saved open orders and statistics to {file_path}")
    except Exception as e:
        logging.error(f"Failed to save open orders and statistics to file: {e}")






def load_or_fetch_open_orders(exchange, symbol, file_path):
    """
    Φορτώνει τις ανοιχτές παραγγελίες και τις στατιστικές από το τοπικό αρχείο
    ή, αν δεν υπάρχει αρχείο, κάνει fetch από την Binance.
    """
    try:
        # Προσπάθεια φόρτωσης από το αρχείο
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        open_orders = {float(price): order for price, order in data.get("orders", {}).items()}
        statistics = data.get("statistics", {
            "total_buys": 0,
            "total_sells": 0,
            "net_profit": 0.0
        })
        
        logging.info(f"Loaded open orders and statistics from {file_path} successfully.")
        return open_orders, statistics
    except (FileNotFoundError, json.JSONDecodeError):
        # Αν το αρχείο δεν υπάρχει ή είναι κενό/μη έγκυρο, κάνουμε fetch από την Binance
        logging.warning(f"{file_path} not found or invalid. Fetching open orders from Binance...")
        binance_orders = exchange.fetch_open_orders(symbol)
        open_orders = {}
        for order in binance_orders:
            price = float(order['price'])
            open_orders[price] = {
                'id': order['id'],
                'symbol': order['symbol'],
                'price': price,
                'side': order['side'],
                'status': order['status']
            }

        # Δημιουργία αρχικών στατιστικών
        statistics = {
            "total_buys": 0,
            "total_sells": 0,
            "net_profit": 0.0
        }

        # Αποθήκευση των παραγγελιών και των στατιστικών σε τοπικό αρχείο
        save_open_orders_to_file(file_path, open_orders, statistics)
        logging.info(f"Fetched and saved open orders and statistics to {file_path}")
        return open_orders, statistics
    except Exception as e:
        logging.error(f"Failed to load or fetch open orders and statistics: {e}")
        return {}, {
            "total_buys": 0,
            "total_sells": 0,
            "net_profit": 0.0
        }





def check_balance(exchange, currency, required_amount):
    """
    Ελέγχει αν υπάρχει επαρκές υπόλοιπο για την εκτέλεση μιας παραγγελίας.
    """
    try:
        balance = exchange.fetch_balance()
        available_balance = balance['free'].get(currency, 0)
        if available_balance >= required_amount:
            return True
        else:
            logging.warning(f"Insufficient balance: Available {available_balance:.4f} {currency}, Required {required_amount:.4f} {currency}")
            return False
    except Exception as e:
        logging.error(f"Failed to fetch balance: {e}")
        raise
        
        
        


def place_order(exchange, side, price, AMOUNT):
    global mock_order_counter
    rounded_price = round(price, 4)  # Στρογγυλοποίηση τιμής
    
    if ENABLE_DEMO_MODE:
        # Mock mode: Δημιουργία mock παραγγελίας
        mock_order_counter += 1
        order_id = f"mock_{side}_{mock_order_counter}"
        mock_order = {
            "id": order_id,
            "symbol": SYMBOL,
            "type": "limit",
            "side": side,
            "price": rounded_price,
            "amount": AMOUNT,
            "status": "open"
        }
        logging.info(f"[DEMO MODE] Mock order placed: {mock_order}")
        return mock_order



    # Έλεγχος υπολοίπου πριν από την τοποθέτηση παραγγελίας
    try:
        balance = exchange.fetch_balance()
        required_currency = CRYPTO_CURRENCY if side == "buy" else CRYPTO_SYMBOL
        available_balance = balance['free'].get(required_currency, 0)

        if available_balance < AMOUNT:
            logging.warning(f"Insufficient balance for {side.capitalize()} order at {rounded_price:.4f}. "
                            f"Available: {available_balance}, Required: {AMOUNT}. Skipping order.")
            sendgrid_email(
                transaction_type=side,
                price=rounded_price,
                quantity=AMOUNT,
                reasoning=f"Insufficient balance for {side.capitalize()} order at {rounded_price:.4f}"
            )
            send_push_notification(f"Insufficient balance for {side.capitalize()} order at {rounded_price:.4f}")
            return False
            
    except Exception as e:
        logging.error(f"Error checking balance: {e}")
        return False


    # Τοποθέτηση παραγγελίας
    try:
        logging.info(f"Attempting to place {side} order at {rounded_price:.4f} {CRYPTO_CURRENCY} for {AMOUNT} {CRYPTO_SYMBOL}")
        order = exchange.create_limit_order(SYMBOL, side, AMOUNT, rounded_price)
        logging.info(f"Order placed successfully: {order}")
        return {
            "id": order.get("id"),  # Διασφάλιση ότι το 'id' υπάρχει
            "symbol": order.get("symbol", SYMBOL),
            "price": rounded_price,
            "side": side,
            "status": "open"
        }
    except ccxt.NetworkError as e:
        logging.error(f"Network error while placing order at {rounded_price:.4f} ({side}): {e}")
        return None
    except ccxt.BaseError as e:
        logging.error(f"Exchange error while placing order at {rounded_price:.4f} ({side}): {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error while placing order at {rounded_price:.4f} ({side}): {e}")
        return None





def verify_order_exists(exchange, order_id):
    try:
        order = exchange.fetch_order(order_id, SYMBOL)
        return order is not None and order['status'] == 'open'
    except Exception as e:
        logging.debug(f"Order {order_id} verification failed: {e}")
        return False




def cancel_order(exchange, open_orders, order_id, price, reason):
    """
    Ακυρώνει μια εντολή από το exchange ή το mock dictionary.
    Παρέχει πληροφορίες για την ακύρωση και ενημερώνει το state.
    """
    try:
        rounded_price = round(price, 4)
        if not verify_order_exists(exchange, order_id):
            logging.warning(f"Order {order_id} at price {rounded_price:.4f} does not exist. Removing from open_orders.")
            if rounded_price in open_orders:
                del open_orders[rounded_price]
            return  # Δεν προσπαθούμε να ακυρώσουμε κάτι που δεν υπάρχει

        if ENABLE_DEMO_MODE:
            logging.info(f"[DEMO MODE] Mock order {order_id} at price {rounded_price:.4f} cancelled. Reason: {reason}")
            open_orders = {
                k: v for k, v in open_orders.items() if v['id'] != order_id
            }  # Ασφαλής αφαίρεση με βάση το ID
        else:
            logging.info(f"Attempting to cancel order {order_id} at price {rounded_price:.4f}")
            exchange.cancel_order(order_id, SYMBOL)
            logging.info(f"Order {order_id} at price {rounded_price:.4f} successfully cancelled. Reason: {reason}")

        # Αφαίρεση της εντολής από τα ανοιχτά
        if rounded_price in open_orders:
            logging.debug(f"Removing order at price {rounded_price:.4f} from open_orders.")
            del open_orders[rounded_price]

    except Exception as e:
        logging.error(f"Failed to cancel order {order_id} at price {rounded_price:.4f}: {e}")
        logging.debug(f"Open orders: {open_orders}")




def get_order_status(exchange, order_id):
    """
    Get the status of a specific order.
    :param exchange: The exchange object
    :param order_id: The ID of the order to check
    :return: The status of the order ('open', 'closed', 'canceled', etc.)
    """
    try:
        order = exchange.fetch_order(order_id, SYMBOL)
        if order is None:  # Έλεγχος για None απάντηση
            logging.error(f"Fetch order returned None for order {order_id}")
            return None
        return order['status']
    except Exception as e:
        logging.error(f"Failed to fetch status for order {order_id}: {e}")
        return None



# 6. ---------------------- Check Orders Status ----------------------
def check_orders_status(exchange, open_orders, current_price):
    """
    Ελέγχει την κατάσταση των τοπικών παραγγελιών και ενημερώνει τα open_orders αν μια παραγγελία έχει γεμίσει.
    """
    filled_orders = []
    orders_to_remove = []

    for price, order_info in list(open_orders.items()):
        rounded_price = round(price, 4)  # Στρογγυλοποίηση για συνέπεια
        order_id = order_info.get("id")

        if not order_id:
            logging.warning(f"Order at price {rounded_price} has no ID. Skipping...")
            continue

        try:
            if ENABLE_DEMO_MODE:
                # Διαχείριση DEMO mode
                side = order_info["side"]
                order_price = round(order_info["price"], 4)

                logging.debug(f"[DEMO MODE] Checking {side} order at {order_price} with current price {current_price}")
                if side == "buy" and current_price <= order_price:
                    logging.info(f"[DEMO MODE] Buy order at {order_price} filled (current: {current_price})")
                    filled_orders.append(rounded_price)
                elif side == "sell" and current_price >= order_price:
                    logging.info(f"[DEMO MODE] Sell order at {order_price} filled (current: {current_price})")
                    filled_orders.append(rounded_price)
            else:
                # LIVE MODE: Ελέγχει την κατάσταση παραγγελίας μέσω API
                status = get_order_status(exchange, order_id)
                logging.debug(f"Order {order_id} at {rounded_price}: status {status}")

                if status in ["closed", "filled"]:
                    logging.info(f"Order at {rounded_price:.4f} filled.")
                    filled_orders.append(rounded_price)
                    send_push_notification(f"Order Filled at {rounded_price:.4f}")
                    
                elif status == "open":
                    logging.debug(f"Order {order_id} at {rounded_price:.4f} is still active.")
                elif status in ["canceled", "rejected", "expired"]:
                    logging.warning(f"Order {order_id} at {rounded_price:.4f} is {status}. Removing from open_orders.")
                    orders_to_remove.append(rounded_price)
                else:
                    logging.warning(f"Order {order_id} at {rounded_price} has unexpected status: {status}. Skipping...")
        except Exception as e:
            logging.error(f"Error processing order at price {rounded_price}: {e}")
            continue  # Συνεχίζει με την επόμενη παραγγελία

    # Ασφαλής διαγραφή παραγγελιών που έχουν γεμίσει ή ακυρωθεί
    for price in filled_orders + orders_to_remove:
        if price in open_orders:
            del open_orders[price]
            logging.info(f"Order at {price:.4f} removed from open_orders.")

    # Καταγραφή κατάστασης
    logging.info(f"Current open orders after processing: {len(open_orders)} orders remain unchanged.")
    logging.info(f"Filled orders in this iteration: {filled_orders}. Removed orders this iteration: {orders_to_remove}.")
    

    return filled_orders





def fetch_open_orders_from_exchange(exchange, symbol):
    """
    Fetches open orders for a specific symbol from the exchange.

    :param exchange: Instance of the exchange (e.g., ccxt.binance())
    :param symbol: The trading pair symbol (e.g., "XRP/USDT")
    :return: List of open orders
    """
    try:
        open_orders = exchange.fetch_open_orders(symbol)
        logging.info(f"Successfully fetched {len(open_orders)} active open orders for {symbol} from {EXCHANGE_NAME} API.")
        return open_orders
    except Exception as e:
        logging.error(f"Failed to fetch open orders from the exchange: {e}")
        raise




def reconcile_open_orders(exchange, symbol, local_orders):
    """
    Συμφιλίωση τοπικών παραγγελιών με τις ενεργές παραγγελίες στο Exchange, με προτεραιότητα στα δεδομένα του Exchange.
    """
    try:
        # Φέρε τις ενεργές παραγγελίες από το Exchange
        exchange_orders = fetch_open_orders_from_exchange(exchange, symbol)
        exchange_order_ids = {order['id']: order for order in exchange_orders}
        exchange_prices = {round(float(order['price']), 4): order for order in exchange_orders}

        logging.debug(f"Fetched {len(exchange_orders)} open orders from Exchange")

        # Ενημέρωση τοπικών παραγγελιών βάσει Exchange
        for price, local_order in list(local_orders.items()):
            order_id = local_order.get("id")
            
            # Αν η παραγγελία δεν υπάρχει στο Exchange, σημείωσέ την αλλά μην την αφαιρέσεις άμεσα
            if order_id not in exchange_order_ids:
                logging.warning(f"Local order ID {order_id} at price {price} {CRYPTO_CURRENCY} not found on Exchange. Retaining temporarily.")
                local_orders[price]['status'] = 'unknown'
                continue

            # Ενημέρωση παραγγελίας που υπάρχει και τοπικά και στο Exchange
            local_orders[price].update(exchange_order_ids[order_id])

        # Προσθήκη νέων παραγγελιών που υπάρχουν στο Exchange αλλά λείπουν τοπικά
        for price, exchange_order in exchange_prices.items():
            if price not in local_orders:
                logging.info(f"Adding missing order from Exchange at price {price}")
                local_orders[price] = exchange_order

        # Έλεγχος για αναντιστοιχίες και πιθανές αστοχίες
        local_prices = set(local_orders.keys())
        exchange_prices_set = set(exchange_prices.keys())
        if local_prices != exchange_prices_set:
            logging.warning(
                f"Mismatch in orders: Local only: {local_prices - exchange_prices_set}, "
                f"Exchange only: {exchange_prices_set - local_prices}"
            )

        logging.info(f"Reconciliation completed.")
        logging.debug(f"Reconciliation completed. Active orders: {len(local_orders)}")
        return local_orders

    except Exception as e:
        logging.error(f"Error during reconciliation: {e}")
        raise



def adjust_grid_with_file_check(
    exchange, open_orders, current_price, grid_size, grid_count, amount, max_open_orders, statistics
):
    """
    Προσαρμόζει το grid δυναμικά, ακυρώνοντας παραγγελίες εκτός range και τοποθετώντας νέες παραγγελίες του ίδιου τύπου.
    Εκτελείται μόνο αν υπάρχουν ήδη παραγγελίες.
    """
    if not open_orders:  # Αν δεν υπάρχουν ανοιχτές παραγγελίες, δεν χρειάζεται να προσαρμόσουμε το grid
        logging.info("No open orders to adjust the grid.")
        return

    # Υπολογισμός νέων τιμών grid
    buy_prices = [round(current_price - grid_size * i, 4) for i in range(1, grid_count + 1)]
    sell_prices = [round(current_price + grid_size * i, 4) for i in range(1, grid_count + 1)]

    # Επιβεβαίωση της νέας τιμής του grid
    print()
    logging.info(f"Adjusting grid dynamically...")
    logging.info(f"Adjusted buy orders: {buy_prices}")
    logging.info(f"Adjusted sell orders: {sell_prices}")
    


    # Ακύρωση παραγγελιών εκτός range και τοποθέτηση νέων παραγγελιών
    orders_removed = 0  # Μετρητής για ακυρωμένες παραγγελίες

    for price, order in list(open_orders.items()):
        if order["side"] == "buy" and price < min(buy_prices):
            cancel_order(exchange, open_orders, order["id"], price, "Buy order out of range")
            orders_removed += 1
            time.sleep(2)
            # Τοποθέτηση νέας παραγγελίας αγοράς στο νέο grid
            place_order(exchange, "buy", min(buy_prices), amount)
            logging.info(f"Replaced Buy order at {min(buy_prices)} due to being out of range.")
        elif order["side"] == "sell" and price > max(sell_prices):
            cancel_order(exchange, open_orders, order["id"], price, "Sell order out of range")
            orders_removed += 1
            time.sleep(2)
            # Τοποθέτηση νέας παραγγελίας πώλησης στο νέο grid
            place_order(exchange, "sell", max(sell_prices), amount)
            logging.info(f"Replaced Sell order at {max(sell_prices)} due to being out of range.")


    # Αποθήκευση ενημερωμένων δεδομένων
    save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders, statistics, silent=True)


    if orders_removed > 0:
        logging.info(f"Cancelled and replaced {orders_removed} orders that were out of the new grid range.")
        print()
    else:
        logging.info("No orders were out of the new grid range.")
        print()




    # # Εύρεση τρεχουσών τιμών αγοράς και πώλησης
    # current_buy_prices = {price for price, order in open_orders.items() if order["side"] == "buy"}
    # current_sell_prices = {price for price, order in open_orders.items() if order["side"] == "sell"}

    # # Υπολογισμός ελλειπόντων τιμών
    # missing_buy_prices = [price for price in buy_prices if price not in current_buy_prices]
    # missing_sell_prices = [price for price in sell_prices if price not in current_sell_prices]

    # # Έλεγχος μέγιστου αριθμού παραγγελιών
    # if len(open_orders) >= max_open_orders:
        # logging.warning("Reached maximum open orders limit. Skipping grid replenishment.")
        # return

    # # Έλεγχος υπολοίπου
    # try:
        # balance = exchange.fetch_balance()
        # available_usdt = balance["free"].get("USDT", 0)
        # available_xrp = balance["free"].get("XRP", 0)
    # except Exception as e:
        # logging.error(f"Failed to fetch balance: {e}")
        # return

    # # Τοποθέτηση νέων buy orders
    # buy_orders_placed = 0  # Μετρητής για τοποθετημένες παραγγελίες αγοράς
    # for price in missing_buy_prices:
        # if len(open_orders) >= max_open_orders:
            # break
        # if available_usdt < amount * price:
            # logging.warning(f"Insufficient balance for Buy order at {price:.4f}. Skipping order.")
            # continue
        # try:
            # order = place_order(exchange, "buy", price, amount)
            # if order:
                # open_orders[price] = order
                # available_usdt -= amount * price  # Μείωση υπολοίπου
                # buy_orders_placed += 1
                # logging.info(f"Placed missing Buy order at {price:.4f}")
        # except Exception as e:
            # logging.error(f"Error placing Buy order at {price:.4f}: {e}")

    # if buy_orders_placed > 0:
        # logging.info(f"Successfully placed {buy_orders_placed} new Buy orders.")
    # else:
        # logging.info("No new Buy orders were placed.")

    # # Τοποθέτηση νέων sell orders
    # sell_orders_placed = 0  # Μετρητής για τοποθετημένες παραγγελίες πώλησης
    # for price in missing_sell_prices:
        # if len(open_orders) >= max_open_orders:
            # break
        # if available_xrp < amount:
            # logging.warning(f"Insufficient balance for Sell order at {price:.4f}. Skipping order.")
            # continue
        # try:
            # order = place_order(exchange, "sell", price, amount)
            # if order:
                # open_orders[price] = order
                # available_xrp -= amount  # Μείωση υπολοίπου
                # sell_orders_placed += 1
                # logging.info(f"Placed missing Sell order at {price:.4f}")
        # except Exception as e:
            # logging.error(f"Error placing Sell order at {price:.4f}: {e}")

    # if sell_orders_placed > 0:
        # logging.info(f"Successfully placed {sell_orders_placed} new Sell orders.")
    # else:
        # logging.info("No new Sell orders were placed.")

    # # Στοιχεία καταγραφής μετά την προσαρμογή
    # logging.info(f"Grid adjustment completed: {buy_orders_placed} new Buy orders, {sell_orders_placed} new Sell orders.")














# 7. ---------------------- Main Bot Logic ----------------------
def run_grid_trading_bot(AMOUNT):
    logging.info(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    logging.info(f"Starting {SYMBOL} Grid Trading bot...")
    
    # --- NEW CODE ---
    # Αρχικοποίηση μεταβλητών για καταμέτρηση και κέρδος
    total_buys = 0
    total_sells = 0
    net_profit = 0.0
    # --- END NEW CODE ---    

    exchange = initialize_exchange()

    # Φόρτωση παραγγελιών και στατιστικών από το αρχείο
    open_orders, statistics = load_or_fetch_open_orders(exchange, SYMBOL, OPEN_ORDERS_FILE)
    
    # Διασφάλιση consistency στα open_orders
    open_orders = {float(k): v for k, v in open_orders.items()}  # Τιμές σε float
    
    
    # Logging αρχικών τιμών
    logging.info(f"Loaded statistics: {statistics}")
    logging.debug(f"Loaded open orders: {open_orders}")
    

    # Συγχρονισμός με τα πραγματικά open orders από την Binance
    logging.info("Reconciling local open orders with Binance...")
    open_orders = reconcile_open_orders(exchange, SYMBOL, open_orders)
    logging.debug(f"Reconciliation complete. Active orders: {open_orders}")

    # Αποθήκευση του συγχρονισμένου state
    save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders)

    # Βρες την τρέχουσα τιμή
    current_price = get_current_price(exchange)
    logging.debug(f"Current price for {CRYPTO_SYMBOL}: {current_price}")


   
    
    # Αρχική τοποθέτηση εντολών (buy / sell) μόνο αν δεν υπάρχουν ήδη εντολές
    if not open_orders:
        
        # Δημιουργία grid (παράδειγμα: 10 * 10$ πάνω/κάτω)
        buy_prices = [round(current_price - GRID_SIZE * i, 4) for i in range(1, GRID_COUNT + 1)]
        sell_prices = [round(current_price + GRID_SIZE * i, 4) for i in range(1, GRID_COUNT + 1)]

        logging.info("No existing open orders. Placing initial grid orders.")
        
        logging.info(f"Generated buy prices: {buy_prices}")
        logging.info(f"Generated sell prices: {sell_prices}")               
        

        all_orders_successful = True  # Flag για επιτυχία τοποθέτησης όλων των παραγγελιών

        for price in buy_prices:
            if price > 0:  # Λίγο έλεγχος ότι δεν πάμε σε απίθανη αρνητική τιμή
                order = place_order(exchange, "buy", price, AMOUNT)
                if order:
                    open_orders[price] = order
                else:
                    logging.error(f"Stopping initial grid setup due to issue at buy price {price:.4f}.")
                    all_orders_successful = False
                    return

        if all_orders_successful:  # Μόνο αν όλες οι αγορές ήταν επιτυχείς
            for price in sell_prices:
                order = place_order(exchange, "sell", price, AMOUNT)
                if order:
                    open_orders[price] = order
                else:
                    logging.error(f"Stopping initial grid setup due to issue at sell price {price:.4f}.")
                    all_orders_successful = False
                    return

        # Αποθήκευση μόνο αν όλες οι παραγγελίες τοποθετήθηκαν επιτυχώς
        if all_orders_successful:
            save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders)
            logging.info(f"Initial orders placed and saved: {open_orders}")
            
            # Send notifications on successful orders
            send_push_notification(f"Initial orders placed and saved: {open_orders}")          
                       
        else:
            logging.error("Initial grid setup incomplete. Orders not saved.")
            
            # Send notifications on failed orders
            send_push_notification(f"Failed to place initial orders")
            
            return


    # Αρχικοποίηση της local_open_orders πριν το loop
    local_open_orders = {}    
    

    # Ξεκινάμε το loop
    while True:
        iteration_start = time.time()
        failed_attempts = 0  # Counter για αποτυχημένες προσπάθειες
           
        
        try:
            logging.info(f"==========================================================")
            logging.info(f"Starting a new loop iteration for {CRYPTO_SYMBOL}")
            logging.info(f"==========================================================")


            # Λήψη τρέχουσας τιμής
            try:
                current_price = get_current_price(exchange)
                logging.info(f"Current price: {current_price} {CRYPTO_CURRENCY}.")
            except Exception as e:
                logging.error(f"Failed to fetch current price: {e}")
                continue  # Προχωράει στην επόμενη επανάληψη


            # --- NEW CODE ---
            
            # Εμφάνιση συνολικών αγορών, πωλήσεων και κέρδους στην αρχή του iteration
            logging.info(f"Total Buys: {statistics['total_buys']}, Total Sells: {statistics['total_sells']}, Net Profit: {statistics['net_profit']:.2f}")


            # Φιλτράρισμα τιμών για buy και sell παραγγελίες
            buy_order_prices = [price for price, order in open_orders.items() if order['side'] == 'buy']
            sell_order_prices = [price for price, order in open_orders.items() if order['side'] == 'sell']

            # Εμφάνιση τιμών με κόμμα
            print()
            logging.info(f"Buy Orders in file: {', '.join(map(str, sorted(buy_order_prices, reverse=True)))}")
            logging.info(f"Sell Orders in file: {', '.join(map(str, sorted(sell_order_prices, reverse=True)))}")
            print()
            
            # # --- END NEW CODE ---
            








            if open_orders:
                # Ορισμός μέγιστου αριθμού παραγγελιών
                max_open_orders = GRID_COUNT * 2

                # Δυναμική προσαρμογή του grid
                adjust_grid_with_file_check(
                    exchange, open_orders, current_price, GRID_SIZE, GRID_COUNT, AMOUNT, max_open_orders, statistics
                )




            # Συγχρονισμός ανοιχτών παραγγελιών με την ανταλλαγή
            try:
                open_orders = reconcile_open_orders(exchange, SYMBOL, open_orders)
                open_orders_count = len(open_orders)
                logging.debug(f"Currently, there are {open_orders_count} open orders.")
                logging.debug(f"Open orders after reconciliation: {open_orders}")
            except Exception as e:
                logging.error(f"Error reconciling open orders: {e}")
                continue


#######################################################################################################################



            # Έλεγχος κατάστασης παραγγελιών
            try:
                filled_orders = check_orders_status(exchange, open_orders, current_price)
                logging.debug(f"Orders identified as filled: {filled_orders}")
                logging.debug(f"Check order status has been completed")
            except Exception as e:
                logging.error(f"Error checking order status: {e}")
                continue

            # Υπολογισμός δυναμικού grid
            buy_prices = [current_price - GRID_SIZE * i for i in range(1, GRID_COUNT + 1)]
            sell_prices = [current_price + GRID_SIZE * i for i in range(1, GRID_COUNT + 1)]
            logging.debug(f"Buy prices: {buy_prices}")
            logging.debug(f"Sell prices: {sell_prices}")

            # Επεξεργασία παραγγελιών που εκτελέστηκαν
            for filled_price in filled_orders:
                rounded_filled_price = round(filled_price, 4)
                if rounded_filled_price in open_orders:
                    order_info = open_orders.pop(rounded_filled_price)
                    side = order_info["side"]
                    amount = order_info["amount"]
                    new_price = round(rounded_filled_price + (GRID_SIZE if side == "buy" else -GRID_SIZE), 4)
                    order_price = order_info["price"]  # Τιμή της παραγγελίας (αγοράς ή πώλησης)
                    
                    
                    # --- NEW CODE ---
                    # Υπολογισμός κέρδους ή ζημίας
                    if side == "sell":
                        buy_price = order_price  # Χρησιμοποιούμε την τιμή αγοράς από την παραγγελία
                        profit = (rounded_filled_price - buy_price) * amount
                        statistics["total_sells"] += 1
                        logging.info(f"Profit from Sell Order: {profit:.2f}, Updated Net Profit: {statistics['net_profit']:.2f}")
                    elif side == "buy":
                        # Αύξηση total_buys
                        statistics["total_buys"] += 1
                    # --- END NEW CODE ---

                    

                    # Ελέγχουμε αν η νέα παραγγελία είναι εντός του grid
                    if (side == "buy" and new_price >= min(buy_prices)) or (side == "sell" and new_price <= max(sell_prices)):
                        if new_price not in open_orders:
                            try:
                                # Ελέγχουμε αν υπάρχει ήδη παραγγελία στο exchange για αυτή την τιμή
                                exchange_orders = fetch_open_orders_from_exchange(exchange, SYMBOL)
                                exchange_prices = {round(float(order['price']), 4) for order in exchange_orders}

                                if new_price in exchange_prices:
                                    logging.info(f"{side.capitalize()} order at {new_price:.4f} already active on exchange. Skipping.")
                                    continue  # Προχωράμε στην επόμενη παραγγελία
                            except Exception as e:
                                logging.error(f"Error verifying new order at {new_price:.4f} on exchange: {e}")
                                continue

                            try:
                                # Τοποθέτηση νέας παραγγελίας
                                order = place_order(exchange, side, new_price, AMOUNT)
                                if order:
                                    open_orders[new_price] = order
                                    logging.info(f"Placed new {side.capitalize()} order at {new_price:.4f}")
                                else:
                                    logging.warning(f"Failed to place new {side.capitalize()} order at {new_price:.4f}. Skipping.")
                            except RuntimeError as e:
                                logging.error(f"Critical error while placing {side.capitalize()} order at {new_price:.4f}: {e}")
                                continue
                        else:
                            logging.debug(f"{side.capitalize()} order at {new_price:.4f} already exists locally.")
                    else:
                        logging.warning(f"New order price {new_price:.4f} is outside the dynamic grid. Skipping.")
                else:
                    logging.warning(f"Filled order at {rounded_filled_price:.4f} not found in local open orders.")






            # Αναπλήρωση ελλείψεων στο grid
            current_buy_orders = list(set(price for price, order in open_orders.items() if order["side"] == "buy"))
            current_sell_orders = list(set(price for price, order in open_orders.items() if order["side"] == "sell"))

            logging.info(f"Current grid status - Buy orders: {len(current_buy_orders)}, Sell orders: {len(current_sell_orders)} ")
            logging.debug(f"Grid Count {GRID_COUNT}")


            GRID_COUNT_TOTAL = GRID_COUNT * 2
            
            if len(open_orders) >= GRID_COUNT * 2:
                
                logging.info(
                f"WARNING: Reached maximum open orders limit. "
                f"Grid replenishment skipped to avoid exceeding the defined Grid_count ({GRID_COUNT_TOTAL}) "
                f"or the available capital."
            )
            
            
            
            else:
                # Λογική αναπλήρωσης για buy και sell παραγγελίες
                while len(current_buy_orders) < GRID_COUNT:
                    new_buy_price = round(min(current_buy_orders or buy_prices) - GRID_SIZE, 4)
                    if new_buy_price > 0 and new_buy_price not in open_orders:
                        try:
                            order = place_order(exchange, "buy", new_buy_price, AMOUNT)
                            if order:
                                open_orders[new_buy_price] = order
                                current_buy_orders.append(new_buy_price)
                                statistics["total_buys"] += 1
                                logging.info(f"Placed missing Buy order at {new_buy_price:.4f}")
                            else:
                                logging.warning(f"Failed to place Buy order at {new_buy_price:.4f}.")
                                return
                                
                        except Exception as e:
                            logging.error(f"Error placing buy order at {new_buy_price}: {e}")
                    else:
                        break

                while len(current_sell_orders) < GRID_COUNT:
                    new_sell_price = round(max(current_sell_orders or sell_prices) + GRID_SIZE, 4)
                    if new_sell_price not in open_orders:
                        try:
                            order = place_order(exchange, "sell", new_sell_price, AMOUNT)
                            if order:
                                open_orders[new_sell_price] = order
                                current_sell_orders.append(new_sell_price)
                                statistics["total_sells"] += 1
                                logging.info(f"Placed missing Sell order at {new_sell_price:.4f}")
                            else:
                                logging.warning(f"Failed to place Sell order at {new_sell_price:.4f}.")
                                return
                                
                        except Exception as e:
                            logging.error(f"Error placing sell order at {new_sell_price}: {e}")
                    else:
                        break


            logging.debug(f"Open orders to be saved: {open_orders}")
            
            # Αποθήκευση ενημερωμένων δεδομένων
            save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders, statistics, silent=True)
            
            logging.info("Open orders saved to file.")
           
            # Μετά την ολοκλήρωση του iteration
            iteration_end = time.time()
            logging.info(f"Loop iteration completed in {iteration_end - iteration_start:.2f} seconds.")
            
            
            time.sleep(UPDATE_INTERVAL)

        except Exception as e:
            logging.exception(f"Error in grid trading loop: {e}")
            time.sleep(UPDATE_INTERVAL)




if __name__ == "__main__":
    try:
        run_grid_trading_bot(AMOUNT)
    except Exception as e:
        import logging
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        print("An error occurred. Check the logs for more details.")
