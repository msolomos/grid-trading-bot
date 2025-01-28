# Grid Trading Bot Suite

This repository contains two key components for automated grid trading on cryptocurrency exchanges:
1. **Main Grid Trading Bot** - Executes grid trading strategies by placing buy and sell orders dynamically.
2. **Grid Range Adjustment Bot** - Manages the range of the grid, adjusts open orders, and maintains balance in the grid.

Both bots utilize the [CCXT](https://github.com/ccxt/ccxt) library for exchange integration and support advanced features like logging, notifications, and error handling.

---

## Features

### 1. Main Grid Trading Bot

#### Core Features:
- **Dynamic Grid Management**: Automatically calculates and places buy/sell orders based on configurable grid parameters (`GRID_SIZE`, `GRID_COUNT`).
- **Balance Management**: Ensures sufficient balances for both base and quote currencies.
- **Order Synchronization**: Keeps local open orders in sync with the exchange.
- **Profit Calculation**: Tracks net profit from executed trades.
- **Notifications**: Sends alerts via email and Pushover for significant events like filled orders or errors.
- **Demo Mode**: Allows safe testing without placing real orders on the exchange.

#### Key Parameters:
- `GRID_SIZE`: Price gap between consecutive grid orders.
- `GRID_COUNT`: Number of grid levels.
- `MAX_ORDERS`: Maximum open orders allowed.
- `TARGET_BALANCE`: Minimum balance to maintain.

---

### 2. Grid Range Adjustment Bot

#### Core Features:
- **Grid Adjustment**: Dynamically adjusts the grid based on the current market price.
- **Order Filtering**: Identifies and cancels orders outside the configured grid range.
- **Excess Order Management**: Ensures the number of open orders does not exceed the `MAX_ORDERS` limit.
- **Order Placement**: Places new buy and sell orders to replenish the grid after cancellations.
- **Balance Maintenance**: Maintains a balance between buy and sell orders within the grid.
- **Pause Flag**: Safely pauses operations for critical adjustments.

#### Process Workflow:
1. **Fetch Current Market Data**: Retrieves the current price and open orders from the exchange.
2. **Filter Out-of-Range Orders**: Identifies orders that are outside the grid range and cancels them.
3. **Replenish Orders**: Places new orders to maintain the grid's integrity.
4. **Balance Validation**: Ensures the balance between buy and sell orders.
5. **Handle Excess Orders**: Cancels orders if the total count exceeds `MAX_ORDERS`.

---

## Configuration

Both bots require a configuration file (`config.json`) with the following structure:

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

````

## Usage
#### Main Grid Trading Bot

1. Place your config.json file in the bot's root directory.
2. Run the bot:

```
python grid_trading_bot.py
```

#### Logging

Logs are saved in the following files:

```
# Logs for the Main Bot
grid_trading_bot.log

# Logs for the Grid Adjustment Bot
grid_adjustment.log
```

#### Prerequisites
```
# Python version
Python 3.8 or higher

# Install dependencies
pip install ccxt pushover
```

#### Notes

1. Ensure you have sufficient funds in your exchange account to execute the grid strategy.
2. Use demo mode to test the strategy without affecting your real funds.

#### Contribution

Feel free to open an issue or submit a pull request for feature suggestions or bug fixes.
