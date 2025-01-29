# Grid Trading Bot Suite

## Overview
The Grid Trading Bot Suite consists of two Python-based tools designed to automate grid trading strategies for cryptocurrencies. These tools integrate with exchanges via the CCXT library, support advanced configurations, and offer detailed logging and notifications for seamless operation.

---

## Features

### 1. **Main Grid Trading Bot**
- Implements a grid trading strategy:
  - Dynamically places buy and sell orders based on a predefined grid structure.
  - Adjusts the grid dynamically to market conditions.
  - Tracks metrics such as total buys, sells, and net profit.
- Synchronizes local orders with exchange orders.
- Supports demo mode for safe testing.

### 2. **Grid Range Adjustment Bot**
- Automatically adjusts the grid range based on the current price:
  - Cancels orders outside the configured grid range.
  - Places new buy and sell orders to replenish the grid.
  - Maintains balance between buy and sell orders.
- Handles excess orders to respect the maximum allowed orders.

### 3. **Notifications**
- Push notifications via Pushover.
- Email notifications via SendGrid.

### 4. **Logging**
- Detailed logs for all operations, including grid adjustments and order management.
- Logs are saved to files and displayed in the console.

---

## Configuration

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

### Key Parameters
- **`GRID_SIZE`**: Price gap between grid levels.
- **`GRID_COUNT`**: Number of grid levels for buys and sells.
- **`MAX_ORDERS`**: Maximum number of active orders.
- **`TARGET_BALANCE`**: Minimum balance for both currencies.

---

## Usage

### 1. **Setup**
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Place your `config.json` file in the root directory.

### 2. **Run the Bots**
#### Main Grid Trading Bot
```bash
python grid_trading_bot.py
```

#### Grid Range Adjustment Bot
```bash
python grid_range_adjustment.py
```

### 3. **Logging and Monitoring**
- **Main Bot Logs**: `grid_trading_bot.log`
- **Grid Adjustment Bot Logs**: `grid_adjustment.log`

---

## Key Functions

### Main Grid Trading Bot
- **Order Placement**: Dynamically calculates and places grid orders.
- **Reconciliation**: Synchronizes local orders with the exchange.
- **Balance Management**: Ensures sufficient funds for trading.
- **Profit Tracking**: Logs net profits and completed trades.

### Grid Range Adjustment Bot
- **Range Adjustments**: Cancels out-of-range orders and places new ones.
- **Balance Maintenance**: Ensures balanced buy and sell orders.
- **Excess Order Handling**: Cancels excess orders to respect limits.

---

## File Structure
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

## Requirements

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

## Notes
- Ensure your API keys are stored securely.
- Test the bots in demo mode before using them with real funds.
- Regularly monitor their operations.

---

## License
This project is open-source and available under the [MIT License](LICENSE).

---

## Contributions
Contributions are welcome! Whether it's improving code efficiency, adding features, or fixing bugs, your input is valuable. Feel free to submit issues or pull requests.

---

## Disclaimer
These bots are provided for educational purposes only. Use them at your own risk. The creators are not responsible for financial losses incurred.

