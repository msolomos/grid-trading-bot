from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from collections import defaultdict 
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
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/opt/python/grid-trading-bot/grid_trading_bot.log"),  # Αρχείο log
        logging.StreamHandler()  # Κονσόλα
    ]
)




# 1. ---------------------- Static / Global configuration ----------------------
# Διαδρομές αρχείων συστήματος
JSON_PATH = "/opt/python/grid-trading-bot/config.json"
PAUSE_FLAG_PATH = "/opt/python/grid-trading-bot/pause.flag"
OPEN_ORDERS_FILE = '/opt/python/grid-trading-bot/open_orders.json'

# Παράμετροι Αποστολής E-mail
ENABLE_EMAIL_NOTIFICATIONS = True
ENABLE_PUSH_NOTIFICATIONS = True

# Ενεργοποίηση demo mode
ENABLE_DEMO_MODE = False  # Toggle for mockup data during testing
mock_order_counter = 0



# 2. ---------------------- Load Keys from external file ----------------------
def load_keys():
    """Load API credentials, notification settings, and grid configuration from a JSON file."""
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

            # Ρυθμίσεις Grid Configuration
            grid_config = keys.get("GRID_CONFIG", {})
            exchange_name = grid_config.get("EXCHANGE_NAME")
            symbol = grid_config.get("SYMBOL")
            crypto_symbol = grid_config.get("CRYPTO_SYMBOL")
            crypto_currency = grid_config.get("CRYPTO_CURRENCY")
            grid_size = grid_config.get("GRID_SIZE")
            amount = grid_config.get("AMOUNT")
            grid_count = grid_config.get("GRID_COUNT")
            max_orders = grid_config.get("MAX_ORDERS")
            target_balance = grid_config.get("TARGET_BALANCE")
            
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
            if not exchange_name or not symbol or not crypto_symbol or not crypto_currency:
                missing_keys.extend(["EXCHANGE_NAME", "SYMBOL", "CRYPTO_SYMBOL", "CRYPTO_CURRENCY"])
            if grid_size is None or amount is None or grid_count is None or max_orders is None:
                missing_keys.extend(["GRID_SIZE", "AMOUNT", "GRID_COUNT", "MAX_ORDERS"])
            
            if missing_keys:
                raise ValueError(f"Missing keys in the JSON file: {', '.join(missing_keys)}")

            return (api_key, api_secret, sendgrid_api_key, pushover_token, pushover_user, email_sender, email_recipient,
                    exchange_name, symbol, crypto_symbol, crypto_currency, grid_size, amount, grid_count, max_orders, target_balance)
    except FileNotFoundError:
        raise FileNotFoundError(f"The specified JSON file '{JSON_PATH}' was not found.")
    except json.JSONDecodeError:
        raise ValueError(f"The JSON file '{JSON_PATH}' is not properly formatted.")





# Load configuration from the JSON file
(API_KEY, API_SECRET, SENDGRID_API_KEY, PUSHOVER_TOKEN, PUSHOVER_USER, EMAIL_SENDER, EMAIL_RECIPIENT,
 EXCHANGE_NAME, SYMBOL, CRYPTO_SYMBOL, CRYPTO_CURRENCY, GRID_SIZE, AMOUNT, GRID_COUNT, MAX_ORDERS, TARGET_BALANCE) = load_keys()

             


def is_paused():
    """Ελέγχει αν υπάρχει το pause flag."""
    return os.path.exists(PAUSE_FLAG_PATH)




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
            logging.info(f"Saved open orders and statistics to {file_path}.")
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
        
        logging.info(f"Loaded open orders and statistics from {file_path}")
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
        logging.info(f"Fetched and saved open orders and statistics to {file_path}.")
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
    MAX_RETRIES = 3  # Μέγιστος αριθμός προσπαθειών
    RETRY_DELAY = 30  # Χρόνος καθυστέρησης σε δευτερόλεπτα

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

    retries = 0
    while retries < MAX_RETRIES:  # Προσθήκη retry μηχανισμού
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
        except ccxt.BaseError as e:
            logging.error(f"Exchange error while placing order at {rounded_price:.4f} ({side}): {e}")            
        except Exception as e:
            logging.error(f"Unexpected error while placing order at {rounded_price:.4f} ({side}): {e}")            

        retries += 1
        logging.warning(f"Retrying to place order ({retries}/{MAX_RETRIES}) in {RETRY_DELAY} seconds...")
        time.sleep(RETRY_DELAY)

    logging.error("Failed to place order after maximum retries.")
    return False






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
    cancelled_orders = []
    

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
                elif status in ["canceled"]:
                    logging.debug(f"Order {order_id} at {rounded_price:.4f} was canceled by grid range bot. Retaining locally.")
                    cancelled_orders.append(rounded_price)
                    #orders_to_remove.append(rounded_price)                    
                elif status in ["rejected", "expired"]:
                    logging.warning(f"Order {order_id} at {rounded_price:.4f} is {status}. Removing from open_orders.")
                    orders_to_remove.append(rounded_price)
                else:
                    logging.warning(f"Order {order_id} at {rounded_price} has unexpected status: {status}. Skipping...")
        except Exception as e:
            logging.error(f"Error processing order at price {rounded_price}: {e}")
            continue  # Συνεχίζει με την επόμενη παραγγελία

    # Καταγραφή κατάστασης
    active_orders = {price: order for price, order in open_orders.items() if order.get("status") == "open"}

    canceled_orders = {price: order for price, order in open_orders.items() if order.get("status") == "canceled"}

    logging.info(f"Active orders: {len(active_orders)}, Canceled orders: {len(canceled_orders)}.")


    logging.info(
        f"Filled orders in this iteration: {filled_orders}. "
        f"Removed orders in this iteration: {orders_to_remove}. "
        f"Cancelled orders by bot: {cancelled_orders}."
    )    
    

    # Ασφαλής διαγραφή παραγγελιών που έχουν γεμίσει ή ακυρωθεί
    for price in filled_orders + orders_to_remove:
        if price in open_orders:
            del open_orders[price]
            logging.info(f"Order at {price:.4f} removed from open_orders.")



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



def fetch_filled_orders_from_exchange(exchange, symbol, since=None,days_ago=1, limit=100):
    """
    Φέρνει παραγγελίες με κατάσταση 'filled' από το Exchange για το συγκεκριμένο σύμβολο.

    :param exchange: Αντικείμενο σύνδεσης με το Exchange (π.χ. ccxt.binance())
    :param symbol: Το σύμβολο για το οποίο θέλουμε τις παραγγελίες (π.χ. "XRP/USDT").
    :param since: Χρονικό σημείο από το οποίο να ξεκινήσει η αναζήτηση.
    :param limit: Μέγιστος αριθμός παραγγελιών που θα επιστραφούν.
    :return: Λίστα παραγγελιών που έχουν ολοκληρωθεί.
    """
    try:
        since_timestamp = int((datetime.now() - timedelta(days=days_ago)).timestamp() * 1000)

        # Φέρνουμε όλες τις filled orders μέσω fetch_my_trades() (το σωστό API της Binance)
        trades = exchange.fetch_my_trades(symbol, since=None, limit=limit) or []

        # Φιλτράρουμε τις συναλλαγές του τελευταίου X ημερών
        filtered_trades = [trade for trade in trades if trade['timestamp'] >= since_timestamp]

        # Ομαδοποίηση των trades με βάση το `order_id`
        grouped_orders = defaultdict(lambda: {'id': None, 'status': 'closed', 'amount': 0, 'price': 0, 'timestamp': None})

        for trade in filtered_trades:
            order_id = trade.get('order')
            price = trade.get('price')
            amount = trade.get('amount')
            timestamp = trade.get('timestamp')

            if order_id:
                grouped_orders[order_id]['id'] = order_id
                grouped_orders[order_id]['amount'] += amount
                grouped_orders[order_id]['timestamp'] = timestamp  # Κρατάμε το timestamp της τελευταίας εκτέλεσης

                # Υπολογισμός μέσης τιμής (σταθμισμένος μέσος όρος)
                previous_total = grouped_orders[order_id]['amount'] - amount
                if previous_total > 0:
                    grouped_orders[order_id]['price'] = (grouped_orders[order_id]['price'] * previous_total + price * amount) / (previous_total + amount)
                else:
                    grouped_orders[order_id]['price'] = price

        # Μετατροπή σε λίστα για επιστροφή
        filled_orders = list(grouped_orders.values())

        logging.info(f"Successfully fetched {len(filled_orders)} unique filled orders for {symbol}.")

        return filled_orders  # ✅ Η επιστροφή παραμένει όπως ήταν για τη reconcile

    except Exception as e:
        logging.error(f"Failed to fetch filled orders: {e}")
        return []  # ✅ Αν υπάρξει σφάλμα, επιστρέφουμε κενή λίστα



def reconcile_open_orders(exchange, symbol, local_orders):
    """
    Συμφιλίωση τοπικών παραγγελιών με τις ενεργές παραγγελίες στο Exchange, με προτεραιότητα στα δεδομένα του Exchange.
    Επιστρέφει:
    - Τα ενεργά open orders (local_orders)
    - Ένα dictionary με τις ακυρωμένες παραγγελίες.
    """
    try:
        # Φέρε τις ενεργές παραγγελίες από το Exchange
        exchange_orders = fetch_open_orders_from_exchange(exchange, symbol)      
        filled_orders = fetch_filled_orders_from_exchange(exchange, symbol)       
        
        exchange_order_ids = {order['id']: order for order in exchange_orders}
        filled_order_ids = {order['id']: order for order in filled_orders}

        exchange_prices = {round(float(order['price']), 4): order for order in exchange_orders}

        logging.debug(f"Fetched {len(exchange_orders)} open orders from Exchange")

        canceled_orders = {}  # Dictionary για τις ακυρωμένες παραγγελίες

        # Ενημέρωση τοπικών παραγγελιών βάσει Exchange
        for price, local_order in list(local_orders.items()):
            order_id = local_order.get("id")
            
            # Debug για να δεις τι συγκρίνεται
            logging.debug(f"Comparing local order ID {order_id} with Exchange IDs {exchange_order_ids.keys()}")            
            


            # Αν η παραγγελία είναι στα filled orders, ενημέρωσε και διέγραψέ την
            if order_id in filled_order_ids:
                logging.info(f"Local order ID {order_id} at price {price} was filled on Exchange. Removing from local orders.")
                del local_orders[price]
                continue

                
            
            # Αν η παραγγελία δεν υπάρχει στο Exchange, ελέγξτε την κατάσταση
            if order_id not in exchange_order_ids:
                try:
                    order_status = exchange.fetch_order_status(order_id, symbol)
                    if order_status == "canceled":
                        #logging.info(f"Local order ID {order_id} at price {price} {CRYPTO_CURRENCY} was canceled on Exchange. Removing from local orders.")
                        local_orders[price]["status"] = "canceled"  # Ενημέρωση status στο αρχειο json
                        canceled_orders[price] = local_order  # Προσθήκη στην λίστα ακυρωμένων
                    else:
                        logging.warning(f"Local order ID {order_id} at price {price} {CRYPTO_CURRENCY} not found on Exchange for an unknown reason. Removing from local orders.")
                        # Διαγράψτε την παραγγελία από το τοπικό αρχείο
                        del local_orders[price]                        
                except Exception as e:
                    logging.error(f"Failed to fetch status for order ID {order_id} at price {price}: {e}. Assuming it no longer exists and removing it.")

                continue

            # Ενημέρωση παραγγελίας που υπάρχει και τοπικά και στο Exchange
            local_orders[price].update(exchange_order_ids[order_id])

        # Προσθήκη νέων παραγγελιών που υπάρχουν στο Exchange αλλά λείπουν τοπικά
        for price, exchange_order in exchange_prices.items():
            if price not in local_orders:
                logging.info(f"Adding missing order from Exchange at price {price}")
                local_orders[price] = exchange_order

        logging.info(f"Reconciliation completed.")
        logging.debug(f"Reconciliation completed. Active orders: {len(local_orders)}")
        
        
        return local_orders, canceled_orders  # Επιστροφή ενεργών και ακυρωμένων παραγγελιών

    except Exception as e:
        logging.error(f"Error during reconciliation: {e}")
        raise




def find_order_by_id(canceled_orders, search_id):
    """
    Βρίσκει παραγγελία στο dictionary canceled_orders με βάση το ID.
    """
    return next(
        (order for order in canceled_orders.values() if order["id"] == search_id),
        None
    )





def balance_currencies(exchange, symbol, target_balance, min_precision=1, tolerance=5, fee_buffer=0.001):
    """
    Εκτελεί το rebalance στο XRP/USDT grid bot, λαμβάνοντας υπόψη τα διαθέσιμα κεφάλαια.

    :param exchange: Αντικείμενο ανταλλακτηρίου (π.χ. ccxt.binance)
    :param symbol: Το ζεύγος νομισμάτων (π.χ. "XRP/USDT")
    :param target_balance: Στόχος balance (π.χ. 400 XRP και 400 USDT)
    :param min_precision: Ελάχιστη ακρίβεια δεκαδικών για τις συναλλαγές
    :param tolerance: Ανοχή διαφοράς στο balance για αποφυγή συνεχών αλλαγών
    :param fee_buffer: Περιθώριο ασφαλείας για τα fees
    """

    # Ανάκτηση διαθέσιμου υπολοίπου
    balance = exchange.fetch_balance()
    free_base = balance[symbol.split('/')[0]]['free']  # XRP
    free_quote = balance[symbol.split('/')[1]]['free']  # USDT

    current_price = exchange.fetch_ticker(symbol)['last']

    logging.info(f"[BALANCE CHECK] XRP: {free_base:.2f}, USDT: {free_quote:.2f}")
    logging.info(f"[PRICE] Current price for {symbol}: {current_price:.4f} USDT/XRP")

    # **Υπολογισμός διαφοράς για rebalance**
    required_xrp = target_balance - free_base
    required_usdt = target_balance - free_quote

    need_more_xrp = required_xrp > tolerance  # Χρειάζεται αγορά XRP
    need_more_usdt = required_usdt > tolerance  # Χρειάζεται πώληση XRP για USDT

    logging.info(f"[REQUIRED] Need {required_xrp:.2f} XRP, Need {required_usdt:.2f} USDT")
    logging.info(f"[NEED CHECK] Need More XRP: {need_more_xrp}, Need More USDT: {need_more_usdt}")

    # **Έλεγχος διαθεσιμότητας πριν το rebalance**
    if need_more_xrp and free_quote < (required_xrp * current_price):
        message = (
            f"Not enough USDT to buy XRP. Available: {free_quote:.2f} USDT, "
            f"Required: {required_xrp * current_price:.2f} USDT."
        )
        logging.warning(f"[INSUFFICIENT FUNDS] {message}")
        send_push_notification(f"[INSUFFICIENT FUNDS] {message}")
        return {"base_balance": free_base, "quote_balance": free_quote}

    if need_more_usdt:
        required_xrp_to_sell = required_usdt / current_price
        remaining_xrp_after_sell = free_base - required_xrp_to_sell

        if remaining_xrp_after_sell < target_balance:
            message = (
                f"Selling {required_xrp_to_sell:.2f} XRP would drop balance below target of {target_balance} XRP."
            )
            logging.warning(f"[INSUFFICIENT FUNDS] {message}")
            send_push_notification(f"[INSUFFICIENT FUNDS] {message}")
            return {"base_balance": free_base, "quote_balance": free_quote}

    # **Εκτέλεση Rebalance**
    if need_more_xrp:
        amount_to_buy = required_xrp
        cost = amount_to_buy * current_price

        logging.info(f"[TRADE] Buying {amount_to_buy:.2f} XRP for {cost:.2f} USDT.")
        order = exchange.create_market_buy_order(symbol, amount_to_buy)

        # Ενημέρωση των balances
        free_base += amount_to_buy
        free_quote -= cost

    elif need_more_usdt:
        amount_to_sell = required_usdt / current_price

        logging.info(f"[TRADE] Selling {amount_to_sell:.2f} XRP for {required_usdt:.2f} USDT.")
        order = exchange.create_market_sell_order(symbol, amount_to_sell)

        # Ενημέρωση των balances
        free_base -= amount_to_sell
        free_quote += required_usdt

    logging.info(f"[FINAL BALANCE] XRP: {free_base:.2f}, USDT: {free_quote:.2f}")

    return {"base_balance": free_base, "quote_balance": free_quote}






# 7. ---------------------- Main Bot Logic ----------------------
def run_grid_trading_bot(AMOUNT):
       
    max_retries = 5  # Μέγιστος αριθμός προσπαθειών
    retries = 0
    waited_for_pause = False  # Σημαία για να ελέγξουμε αν υπήρξε αναμονή λόγω pause

    # Έλεγχος αν το pause flag είναι ενεργό
    while is_paused():
        waited_for_pause = True  # Καταγράφουμε ότι το bot περίμενε
        if retries >= max_retries:
            logging.error("Pause flag remains active after multiple retries. Exiting to avoid infinite loop.")
            raise RuntimeError("Maximum retries exceeded while waiting for pause flag to clear.")
        
        logging.warning(f"Pause flag detected. Retrying in 30 seconds... (Attempt {retries + 1}/{max_retries})")
        retries += 1
        time.sleep(30)  # Αναμονή 30 sec

    # Εμφάνιση μηνύματος μόνο αν έγινε αναμονή λόγω pause
    if waited_for_pause:
        logging.info("Pause flag cleared. Resuming bot execution.")
        

    # Υλοποίηση της κύριας λογικής του bot
   
    logging.info(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    logging.info(f"Starting {SYMBOL} Grid Trading bot...")
    iteration_start = time.time()

    # Φόρτωση αρχείο ρυθμίσεων
    logging.info(f"Loaded configuratio file from config file {JSON_PATH}.")
    

    # Αρχικοποίηση exchange
    exchange = initialize_exchange()  
    logging.info(f"Connected to {EXCHANGE_NAME} - Markets loaded: {len(exchange.markets)}")
    

    # Εξισσοροπηση ισορροπίας κεφαλαίων
    logging.info("Checking currencies balances...")        
    final_balances = balance_currencies(exchange, SYMBOL, TARGET_BALANCE)
    logging.debug(f"Script completed. Final balances: {final_balances}")
    

    # Φόρτωση παραγγελιών και στατιστικών από το αρχείο
    open_orders, statistics = load_or_fetch_open_orders(exchange, SYMBOL, OPEN_ORDERS_FILE)
 

    # Διασφάλιση consistency στα open_orders
    open_orders = {float(k): v for k, v in open_orders.items()}  # Τιμές σε float
        

    # Logging αρχικών τιμών
    logging.info(f"Loaded statistics: {{ {', '.join(f'{key}: {round(value, 2) if isinstance(value, (int, float)) else value}' for key, value in statistics.items())} }}")
    logging.debug(f"Loaded open orders: {open_orders}")
    

    # Συγχρονισμός με τα πραγματικά open orders από την Binance
    logging.info("Reconciling local open orders with Binance...")
    open_orders, canceled_orders = reconcile_open_orders(exchange, SYMBOL, open_orders)
    logging.debug(f"Reconciliation complete. Active orders: {open_orders}")
    
    # Αναφορά για τις ακυρωμένες παραγγελίες
    if canceled_orders:
        for price, order in canceled_orders.items():
            logging.debug(f"Canceled order detected: Price {price}, ID {order['id']}")    

    # Αποθήκευση του συγχρονισμένου state
    #save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders)

    # Βρες την τρέχουσα τιμή
    current_price = get_current_price(exchange)
    logging.info(f"Current price: {current_price} {CRYPTO_CURRENCY}.")

  
    
    # Αρχική τοποθέτηση εντολών (buy / sell) μόνο αν δεν υπάρχουν ήδη εντολές
    if not open_orders:
        
        logging.info("No existing open orders. Placing initial grid orders.")
        
        
        # Δημιουργία grid (παράδειγμα: 10 * 10$ πάνω/κάτω)
        buy_prices = [round(current_price - GRID_SIZE * i, 4) for i in range(1, GRID_COUNT + 1)]
        sell_prices = [round(current_price + GRID_SIZE * i, 4) for i in range(1, GRID_COUNT + 1)]
        
        logging.info(f"Generated buy prices: {buy_prices}")
        logging.info(f"Generated sell prices: {sell_prices}")        
        
        all_orders_successful = True  # Flag για επιτυχία τοποθέτησης όλων των παραγγελιών

        for price in buy_prices:
            if price > 0:  # Λίγο έλεγχος ότι δεν πάμε σε απίθανη αρνητική τιμή
                order = place_order(exchange, "buy", price, AMOUNT)
                if order:
                    open_orders[price] = order
                    statistics["total_buys"] += 1  # Ενημέρωση στατιστικών
                else:
                    logging.error(f"Stopping initial grid setup due to issue at buy price {price:.4f}.")
                    all_orders_successful = False
                    return

        if all_orders_successful:  # Μόνο αν όλες οι αγορές ήταν επιτυχείς
            for price in sell_prices:
                order = place_order(exchange, "sell", price, AMOUNT)
                if order:
                    open_orders[price] = order
                    statistics["total_sells"] += 1  # Ενημέρωση στατιστικών
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


       
    
    try:
        # Execute trade logic 
        logging.info(f"Executing trade logic for {CRYPTO_SYMBOL}")
       
        
        
        # Έλεγχος κατάστασης παραγγελιών
        filled_orders = check_orders_status(exchange, open_orders, current_price)
        
        
        
        # Υπολογισμός δυναμικού grid
        buy_prices = [round(current_price - GRID_SIZE * i, 4) for i in range(1, GRID_COUNT + 1)]
        sell_prices = [round(current_price + GRID_SIZE * i, 4) for i in range(1, GRID_COUNT + 1)] 

 
        # Λογική για εκτελεσμένες παραγγελίες
        if filled_orders:
        
            logging.info(f"Check order status has been completed")
            logging.info(f"Orders identified as filled: {filled_orders}")
                      
            logging.info("Recalculating grid prices to process executed orders and replenish the grid.")

            logging.info(f"Adjusted Buy prices due to filled orders: {buy_prices}")
            logging.info(f"Adjusted Sell prices due to filled orders: {sell_prices}")

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


        else:
            logging.info("No orders were filled in this iteration.")




        
        # Λογική αναπλήρωσης παραγγελιών       
        # Πρώτος έλεγχος - μέγιστος αριθμός παραγγελιών
        if len(open_orders) >= MAX_ORDERS:
            logging.info(f"Reached maximum open orders limit.")
            logging.info(f"Grid replenishment skipped to avoid exceeding the defined Grid_count ({MAX_ORDERS}) or the available capital.")
        else:
            # Λογική αναπλήρωσης για buy και sell παραγγελίες
            current_buy_orders = list(set(price for price, order in open_orders.items() if order["side"] == "buy"))
            current_sell_orders = list(set(price for price, order in open_orders.items() if order["side"] == "sell"))

            logging.info(f"Current grid status - Buy orders: {len(current_buy_orders)}, Sell orders: {len(current_sell_orders)} ")
            logging.debug(f"Grid Count {GRID_COUNT}")            

            logging.debug(f"Current canceled_orders: {canceled_orders}")

            
            while len(current_buy_orders) < GRID_COUNT:
                new_buy_price = round(min(current_buy_orders or buy_prices) - GRID_SIZE, 4)
                logging.info(f"[Buy Replenishment] Calculated new_buy_price: {new_buy_price:.4f}")

                if new_buy_price > 0 and new_buy_price not in open_orders:
                    try:
                        skip_replenishment = False
                        
                        for price, order in canceled_orders.items():
                            order_id = order.get("id")
                            if order_id:
                                status = get_order_status(exchange, order_id)
                                logging.info(f"Order ID {order_id} status: {status}")
                                if status == "canceled":
                                    logging.info(f"[Buy Replenishment] Skipping replenishment for canceled order. Price: {price:.4f}, ID: {order_id}")
                                    skip_replenishment = True
                                    current_buy_orders.append(new_buy_price)
                                    break
                        
                        if skip_replenishment:
                            continue

                        # Τοποθέτηση νέας παραγγελίας
                        logging.info(f"[Buy Replenishment] Attempting to place Buy order at price {new_buy_price:.4f}")
                        order = place_order(exchange, "buy", new_buy_price, AMOUNT)
                        if order:
                            logging.info(f"[Buy Replenishment] Buy order placed successfully. Price: {new_buy_price:.4f}, Order ID: {order['id']}")
                            open_orders[new_buy_price] = order
                            current_buy_orders.append(new_buy_price)
                            statistics["total_buys"] += 1
                        else:
                            logging.warning(f"[Buy Replenishment] Failed to place Buy order at price {new_buy_price:.4f}. Exiting replenishment loop.")
                            send_push_notification(f"Insufficient balance for buy order at {new_buy_price:.4f}")
                            break


                    except Exception as e:
                        logging.error(f"[Buy Replenishment] Error placing Buy order at {new_buy_price:.4f}: {e}")
                else:
                    logging.info(f"[Buy Replenishment] Skipping Buy order placement. Price {new_buy_price:.4f} already in open_orders or invalid.")
                    break

            while len(current_sell_orders) < GRID_COUNT:
                new_sell_price = round(max(current_sell_orders or sell_prices) + GRID_SIZE, 4)
                logging.info(f"[Sell Replenishment] Calculated new_sell_price: {new_sell_price:.4f}")

                if new_sell_price > 0 and new_sell_price not in open_orders:
                    try:
                        skip_replenishment = False
                        
                        for price, order in canceled_orders.items():
                            order_id = order.get("id")
                            if order_id:
                                status = get_order_status(exchange, order_id)
                                logging.debug(f"Order ID {order_id} status: {status}")
                                if status == "canceled":
                                    logging.info(f"[Sell Replenishment] Skipping replenishment for canceled order. Price: {price:.4f}, ID: {order_id}")
                                    skip_replenishment = True
                                    current_sell_orders.append(new_sell_price)
                                    break
                        
                        if skip_replenishment:
                            continue

                        # Τοποθέτηση νέας παραγγελίας
                        logging.info(f"[Sell Replenishment] Attempting to place Sell order at price {new_sell_price:.4f}")
                        order = place_order(exchange, "sell", new_sell_price, AMOUNT)
                        if order:
                            logging.info(f"[Sell Replenishment] Sell order placed successfully. Price: {new_sell_price:.4f}, Order ID: {order['id']}")
                            open_orders[new_sell_price] = order
                            current_sell_orders.append(new_sell_price)
                            statistics["total_sells"] += 1
                        else:
                            logging.warning(f"[Sell Replenishment] Failed to place Sell order at price {new_sell_price:.4f}.")
                            send_push_notification(f"Insufficient balance for sell order at {new_sell_price:.4f}")
                            break

                            
                    except Exception as e:
                        logging.error(f"[Sell Replenishment] Error placing Sell order at {new_sell_price:.4f}: {e}")
                else:
                    logging.info(f"[Sell Replenishment] Skipping Sell order placement. Price {new_sell_price:.4f} already in open_orders or invalid.")
                    break








            logging.info(f"Grid replenishment completed.")


        
        
        logging.debug(f"Open orders to be saved: {open_orders}")
        
        # Αποθήκευση ενημερωμένων δεδομένων
        save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders, statistics, silent=True)
        
        logging.info(f"Saved open orders (including canceled) and statistics to orders file {OPEN_ORDERS_FILE}.")
       
        # Μετά την ολοκλήρωση του iteration
        iteration_end = time.time()
        logging.info(f"Bot execution completed in {iteration_end - iteration_start:.2f} seconds.")
        
        
        

    except Exception as e:
        logging.exception(f"Error in grid trading loop: {e}")
    finally:
        save_open_orders_to_file(OPEN_ORDERS_FILE, open_orders, statistics, silent=True)        
            


if __name__ == "__main__":
    try:        
        run_grid_trading_bot(AMOUNT)

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        
