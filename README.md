# 🚀 Grid Trading Bot Suite

## 📌 Overview
The Grid Trading Bot Suite consists of two Python-based tools designed to automate grid trading strategies for cryptocurrencies. These tools integrate with exchanges via the CCXT library, support advanced configurations, and offer detailed logging and notifications for seamless operation.

---

## 🌟 Features

### 1. **Main Grid Trading Bot**
- 📈 Implements a grid trading strategy:
  - Dynamically places buy and sell orders based on a predefined grid structure.
  - Adjusts the grid dynamically to market conditions.
  - Tracks metrics such as total buys, sells, and net profit.
- 🔄 Synchronizes local orders with exchange orders.
- 🛠️ Supports demo mode for safe testing.

### 2. **Grid Range Adjustment Bot**
- ⚙️ Automatically adjusts the grid range based on the current price:
  - Cancels orders outside the configured grid range.
  - Places new buy and sell orders to replenish the grid.
  - Maintains balance between buy and sell orders.
- 📊 Handles excess orders to respect the maximum allowed orders.

### 3. **🔔 Notifications**
- 📲 Push notifications via Pushover.
- 📧 Email notifications via SendGrid.

### 4. **📜 Logging**
- 📑 Detailed logs for all operations, including grid adjustments and order management.
- 🗂️ Logs are saved to files and displayed in the console.

---

## ⚙️ Installation & Execution

### 1️⃣ **Installation**
1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/grid-trading-bot.git
   cd grid-trading-bot
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Place your `config.json` file in the root directory.

### 2️⃣ **Execution**
#### Run the Main Grid Trading Bot
```bash
python grid_trading_bot.py
```

#### Run the Grid Range Adjustment Bot
```bash
python grid_range_adjustment.py
```

---

## 🔄 Execution Flow
1. **Initialization**
   - Loads API credentials and exchange settings from `config.json`.
   - Initializes connection to the exchange.
   - Loads existing open orders and syncs with exchange data.

2. **Grid Order Placement**
   - Places buy and sell orders according to the grid strategy.
   - Dynamically adjusts grid levels based on market movement.

3. **Monitoring & Adjustments**
   - Continuously checks order execution status.
   - Cancels and repositions orders as needed to maintain grid integrity.
   - Sends notifications upon order execution.

4. **Grid Range Adjustment (Secondary Bot)**
   - Cancels out-of-range orders.
   - Places new orders to maintain balance within grid levels.

5. **Logging & Notifications**
   - Logs every action for debugging and record-keeping.
   - Sends push/email notifications for trade activity and errors.

---

## 🔧 Configuration

The bots use a `config.json` file for settings. Example configuration:

```json
{
    "API_KEY": "your_api_key",
    "API_SECRET": "your_api_secret",
    "SENDGRID_API_KEY": "your_sendgrid_api_key",
    "PUSHOVER_TOKEN": "your_pushover_token",
    "PUSHOVER_USER": "your_pushover_user",
    "EMAIL_SENDER": "your_email_sender",
    "EMAIL_RECIPIENT": "your_email_recipient",
    "GRID_CONFIG": {
        "EXCHANGE_NAME": "binance",
        "SYMBOL": "XRP/USDT",
        "CRYPTO_SYMBOL": "XRP",
        "CRYPTO_CURRENCY": "USDT",
        "GRID_SIZE": 10,
        "AMOUNT": 1,
        "GRID_COUNT": 10,
        "MAX_ORDERS": 50,
        "TARGET_BALANCE": 100
    }
}
```

---

## 📂 File Structure
```
.
├── grid_trading_bot.py          # Main bot script
├── grid_range_adjustment.py     # Grid adjustment bot
├── config.json                  # Configuration file
├── open_orders.json             # Tracks active orders
├── requirements.txt             # Python dependencies
├── grid_trading_bot.log         # Main bot logs
├── grid_adjustment.log          # Adjustment bot logs
```

---

## 📌 Example Logs

### 📜 Main Grid Trading Bot Log
```
2025-01-31 01:30:03,369 INFO Starting XRP/USDT Grid Trading bot...
2025-01-31 01:30:03,369 INFO Loaded configuratio file from config file /opt/python/grid-trading-bot/config.json.
2025-01-31 01:30:08,379 INFO Connected to binance - Markets loaded: 3404
2025-01-31 01:30:08,379 INFO Checking currencies balances...
2025-01-31 01:30:08,929 INFO [BALANCE CHECK] XRP: 1255.76, USDT: 2450.87
2025-01-31 01:30:08,929 INFO [PRICE] Current price for XRP/USDT: 3.1510 USDT/XRP
2025-01-31 01:30:08,929 INFO [REQUIRED] Need -255.76 XRP, Need -1450.87 USDT
2025-01-31 01:30:08,929 INFO [NEED CHECK] Need More XRP: False, Need More USDT: False
2025-01-31 01:30:08,929 INFO [FINAL BALANCE] XRP: 1255.76, USDT: 2450.87
2025-01-31 01:30:08,930 INFO Loaded open orders and statistics from /opt/python/grid-trading-bot/open_orders.json
2025-01-31 01:30:08,930 INFO Loaded statistics: { total_buys: 10, total_sells: 10, net_profit: 221.09 }
2025-01-31 01:30:08,930 INFO Reconciling local open orders with Binance...
2025-01-31 01:30:09,206 INFO Successfully fetched 20 active open orders for XRP/USDT from binance API.
2025-01-31 01:30:09,484 INFO Successfully fetched 2 unique filled orders for XRP/USDT.
2025-01-31 01:30:09,484 INFO Reconciliation completed.
2025-01-31 01:30:09,757 INFO Current price: 3.1509 USDT.
2025-01-31 01:30:09,757 INFO Executing trade logic for XRP
2025-01-31 01:30:19,055 INFO Active orders: 20, Canceled orders: 0.
2025-01-31 01:30:19,055 INFO Filled orders in this iteration: []. Removed orders in this iteration: []. Cancelled orders by bot: [].
2025-01-31 01:30:19,056 INFO No orders were filled in this iteration.
2025-01-31 01:30:19,056 INFO Reached maximum open orders limit.
2025-01-31 01:30:19,056 INFO Grid replenishment skipped to avoid exceeding the defined Grid_count (20) or the available capital.
2025-01-31 01:30:19,059 INFO Saved open orders (including canceled) and statistics to orders file /opt/python/grid-trading-bot/open_orders.json.
2025-01-31 01:30:19,060 INFO Bot execution completed in 15.69 seconds.
```

### 📜 Secondary Grid Adjustment Bot Log
```
2025-01-31 01:30:03,677 - INFO - Starting XRP/USDT Grid Trading bot (grid range worker)...
2025-01-31 01:30:08,604 - INFO - Connected to BINANCE - Markets loaded: 3404
2025-01-31 01:30:08,873 - INFO - Current price: 3.151 USDT
2025-01-31 01:30:09,148 - INFO - Fetched 20 open orders from BINANCE.
2025-01-31 01:30:09,149 - INFO - Buy orders on exchange: [2.7094, 2.7524, 2.7954, 2.8384, 2.9066, 2.9363, 2.9592, 3.0331, 3.095, 3.0986]
2025-01-31 01:30:09,149 - INFO - Sell orders on exchange: [3.2233, 3.2254, 3.2684, 3.3114, 3.3233, 3.3663, 3.4093, 3.4523, 3.4696, 3.4969]
2025-01-31 01:30:09,149 - INFO - No orders to cancel.
2025-01-31 01:30:09,149 - INFO - No grid alteration was made. All orders are within the range.
2025-01-31 01:30:09,423 - INFO - No new orders will be placed to maintain balance. (20)
2025-01-31 01:30:09,423 - INFO - No excess orders detected. (20)
2025-01-31 01:30:09,424 - INFO - Saved open orders and statistics to /opt/python/grid-trading-bot/open_orders.json
2025-01-31 01:30:09,424 - INFO - Bot execution completed in 5.75 seconds.
```

---

## 📌 Requirements

- **Python 3.8+**
- **Libraries**:
  - ccxt
  - pushover
  - sendgrid

Install all dependencies with:
```bash
pip install -r requirements.txt
```

---

## ⚠️ Notes
- Ensure your API keys are stored securely.
- Test the bots in demo mode before using them with real funds.
- Regularly monitor their operations.

---

## 📜 License
This project is open-source and available under the [MIT License](LICENSE).

---

## 🤝 Contributions
Contributions are welcome! Whether it's improving code efficiency, adding features, or fixing bugs, your input is valuable. Feel free to submit issues or pull requests.

---

## ⚠️ Disclaimer
These bots are provided for educational purposes only. Use them at your own risk. The creators are not responsible for financial losses incurred.

