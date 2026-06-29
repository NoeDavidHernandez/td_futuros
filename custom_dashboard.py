import os
import json
import traceback
from flask import Flask, render_template, jsonify, request
import ccxt

app = Flask(__name__)

def get_exchange():
    """Reads api-keys.json and initializes CCXT for Binance."""
    try:
        with open("api-keys.json", "r") as f:
            keys = json.load(f)
            
        # Find the binance config (assuming binance_01 or similar)
        binance_config = keys.get("binance_01")
        if not binance_config:
            return None, "No binance_01 config found in api-keys.json"
            
        exchange = ccxt.binance({
            'apiKey': binance_config.get('key'),
            'secret': binance_config.get('secret'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        
        if binance_config.get("testnet"):
            exchange.urls['api']['fapiPublic'] = 'https://demo-fapi.binance.com/fapi/v1'
            exchange.urls['api']['fapiPrivate'] = 'https://demo-fapi.binance.com/fapi/v1'
            exchange.urls['api']['fapiPublicV2'] = 'https://demo-fapi.binance.com/fapi/v2'
            exchange.urls['api']['fapiPrivateV2'] = 'https://demo-fapi.binance.com/fapi/v2'
            exchange.urls['api']['fapiPrivateV3'] = 'https://demo-fapi.binance.com/fapi/v3'
            
        return exchange, None
    except Exception as e:
        return None, str(e)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/stats")
def stats():
    symbol = request.args.get('symbol', 'BTC/USDT')
    exchange, err = get_exchange()
    if err:
        return jsonify({"error": err}), 500
        
    try:
        # 1. Fetch total balance using raw Binance endpoint to avoid CCXT hitting sapi (Mainnet)
        account_info = exchange.fapiPrivateV2GetAccount()
        total_wallet = account_info.get('totalWalletBalance', 0)
        unrealized_pnl = account_info.get('totalUnrealizedProfit', 0)
        
        # 2. Fetch positions
        positions = account_info.get('positions', [])
        active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        
        # 3. Fetch recent trades to calculate win/loss
        # Note: In real scenarios, fetching income history (fetch_income) is better for PnL per trade,
        # but fetch_my_trades is standard. We will just approximate from realizedPnl in income history if available,
        # or just count recent trades.
        try:
            # Binance Futures specific: fapiPrivateGetIncome gives precise realized PnL per trade
            income = exchange.fapiPrivateGetIncome({'incomeType': 'REALIZED_PNL', 'limit': 100})
            wins = len([i for i in income if float(i['income']) > 0])
            losses = len([i for i in income if float(i['income']) < 0])
            total_ops = len(income)
        except Exception as e:
            print("Error fetching income:", e)
            wins, losses, total_ops = 0, 0, 0

        return jsonify({
            "status": "success",
            "balance": float(total_wallet),
            "unrealized_pnl": float(unrealized_pnl),
            "active_positions_count": len(active_positions),
            "total_operations": total_ops,
            "wins": wins,
            "losses": losses
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs")
def get_logs():
    import glob
    import os
    try:
        log_files = glob.glob("logs/*.log")
        if not log_files:
            # Check if passivbot_startup.log exists (for crash debugging)
            if os.path.exists("passivbot_startup.log"):
                with open("passivbot_startup.log", "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if not lines:
                        return jsonify({"status": "success", "logs": "Bot is starting... (no logs yet)"})
                    return jsonify({"status": "success", "logs": "".join(lines[-100:])})
            return jsonify({"status": "success", "logs": "No log files found yet..."})
        
        # Get the most recently modified log file
        latest_log = max(log_files, key=os.path.getmtime)
        with open(latest_log, "r", encoding="utf-8") as f:
            # Read last 100 lines
            lines = f.readlines()
            last_lines = lines[-100:]
            return jsonify({"status": "success", "logs": "".join(last_lines)})
    except Exception as e:
        return jsonify({"status": "error", "logs": f"Error reading logs: {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
