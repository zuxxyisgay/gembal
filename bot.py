from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import asyncio
import os
import json
import qrcode
from io import BytesIO
import uuid
import time
from datetime import datetime, timedelta
from aiogram.utils.exceptions import MessageNotModified

# Configuration - You can modify these values
TOKEN = os.environ.get("BOT_TOKEN", "7925108099:AAHXR9jZAebGHmnEZXrHBrNLvqT7s_0g7qY")

# Data storage
DATA_FILE = "bot_data.json"

# Initialize data structures
data = {
    "user_balances": {},
    "user_invoice_data": {},
    "user_withdrawal_data": {},  # New: Store withdrawal data
    "banned_users": [],
    "allowed_groups": [-1002454777356, -1002151122547],
    "admin_users": [6302205267, 5102323588],
    "admin_group": -1002151122547,  # Admin group ID for notifications
    "wallets": {
        "usdt_trc20": "TA78CUTWe21C7gtRw98qCnXx4hGugVwS1a",
        "usdt_bep20": "0x7BD9d8d979075900dcFCcE50B24a97818Cbb0DAf",
        "bitcoin": "bc1qnqta6hjhn7fkwzpuhpas0cpqscr2y98fah2tzu",
        "litecoin": "ltc1qz3j47uggpw4ml60x060frj922fq02g5xgrr7ac"
    },
    "withdrawal_fees": {  # New: Define withdrawal fees
        "usdt_trc20": 1.5,
        "usdt_bep20": 0.1,
        "bitcoin": 2.5,
        "litecoin": 0.05
    },
    "pending_invoices": {},
    "pending_withdrawals": {},  # New: Store pending withdrawals
    "completed_invoices": [],
    "completed_withdrawals": [],  # New: Store completed withdrawals
    "active_games": {},  # Store active games data
    "active_players": {},  # Track which players are in active games
    "user_wagers": {}  # Track total amount wagered by each user
}
data["tip_history"] = []  

# Load data from file if exists
def load_data():
    global data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                loaded_data = json.load(f)
                # Ensure all required keys exist
                for key in data:
                    if key not in loaded_data:
                        loaded_data[key] = data[key]
                data = loaded_data
            print("Data loaded successfully")
    except Exception as e:
        print(f"Error loading data: {e}")

# Save data to file
def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

# Generate QR code
def generate_qr_code(content):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to BytesIO
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

# Generate unique invoice ID
def generate_invoice_id():
    return str(uuid.uuid4())[:8].upper()

# Generate unique withdrawal ID
def generate_withdrawal_id():
    return str(uuid.uuid4())[:8].upper()

# Generate unique game ID
def generate_game_id():
    return str(uuid.uuid4())[:8].upper()

# Get total wagered amount for a user
def get_total_wagered(user_id):
    if user_id not in data["user_wagers"]:
        return 0
    
    wager_data = data["user_wagers"][user_id]
    if isinstance(wager_data, (int, float)):
        return wager_data
    elif isinstance(wager_data, dict) and "total" in wager_data:
        return wager_data["total"]
    return 0

# Update user wager data
def update_user_wager(user_id, amount):
    if user_id not in data["user_wagers"]:
        data["user_wagers"][user_id] = {
            "total": amount,
            "weekly": amount,
            "last_update": time.time()
        }
    else:
        if isinstance(data["user_wagers"][user_id], (int, float)):
            # Convert old format to new format
            old_value = data["user_wagers"][user_id]
            data["user_wagers"][user_id] = {
                "total": old_value + amount,
                "weekly": amount,
                "last_update": time.time()
            }
        else:
            data["user_wagers"][user_id]["total"] += amount
            data["user_wagers"][user_id]["weekly"] += amount
            data["user_wagers"][user_id]["last_update"] = time.time()

async def check_expired_invoices(bot):
    while True:
        current_time = time.time()
        expired_invoices = []
        
        for invoice_id, invoice in data["pending_invoices"].items():
            if current_time > invoice["expiry_time"]:
                expired_invoices.append(invoice_id)
                
                # Notify user about expiration
                try:
                    await bot.send_message(
                        invoice["user_id"],
                        f"❌ Your deposit invoice #{invoice_id} for ${invoice['amount']:.2f} has expired."
                    )
                except Exception as e:
                    print(f"Error notifying user about expired invoice: {e}")
        
    
        for invoice_id in expired_invoices:
            del data["pending_invoices"][invoice_id]
        
        if expired_invoices:
            save_data()
            
        await asyncio.sleep(60)  

async def check_expired_games(bot):
    while True:
        current_time = time.time()
        expired_games = []
        
        for game_id, game in data["active_games"].items():
        
            if game["status"] == "pending" and current_time > game["created_time"] + 600:
                expired_games.append(game_id)
                
                
                try:
                    await bot.edit_message_text(
                        chat_id=game["chat_id"],
                        message_id=game["message_id"],
                        text=f"⏱️ Game #{game_id} has expired.\n\n"
                             f"Bet: ${game['bet_amount']:.2f}\n"
                             f"Player: {game['player1_name'].split()[0]}\n\n"
                             f"❌ EXPIRED - No response",
                        reply_markup=None
                    )
                    
                  
                    if game["player1_id"] in data["active_players"]:
                        del data["active_players"][game["player1_id"]]
                        
                except Exception as e:
                    print(f"Error notifying about expired game: {e}")
        
        for game_id in expired_games:
            del data["active_games"][game_id]
        
        if expired_games:
            save_data()
            
        await asyncio.sleep(60)  # Check every minute

load_data()

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = str(message.from_user.id)
    
    if int(user_id) in data["banned_users"]:
        await message.answer("❌ You are banned from using this bot.")
        return
    
    if user_id not in data["user_balances"]:
        data["user_balances"][user_id] = 0
        save_data()
        
    balance_text = f"\U0001F4B0 Balance: ${data['user_balances'][user_id]:.2f}"
    
    if message.chat.type == "private":
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("Deposit", callback_data="deposit"),
            InlineKeyboardButton("Withdraw", callback_data="withdraw")
        )
        keyboard.add(
            InlineKeyboardButton("Go to Play Area 🎲", url="https://t.me/gamblechats", callback_data="play_area")
        )
        await message.answer(balance_text, reply_markup=keyboard)
    elif message.chat.type in ["supergroup", "group"] and message.chat.id in data["allowed_groups"]:
        await message.answer(balance_text)

@dp.message_handler(commands=['balance'])
async def balance_command(message: types.Message):
    user_id = str(message.from_user.id)
    
    if int(user_id) in data["banned_users"]:
        await message.answer("❌ You are banned from using this bot.")
        return
    
    if user_id not in data["user_balances"]:
        data["user_balances"][user_id] = 0
        save_data()
    
    # Get total wagered amount
    total_wagered = get_total_wagered(user_id)
        
    await message.answer(f"\U0001F4B0 Balance: ${data['user_balances'][user_id]:.2f}\nTotal Wagered: ${total_wagered:.2f}")

@dp.callback_query_handler(lambda c: c.data == "deposit")
async def deposit_callback(callback_query: types.CallbackQuery):
    if callback_query.message.chat.type != "private":
        await callback_query.answer("Deposits can only be made in private chat!", show_alert=True)
        return
    
    await callback_query.message.answer("Enter the amount you want to deposit (Minimum $1):")
    data["user_invoice_data"][str(callback_query.from_user.id)] = {"state": "amount"}
    save_data()
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "withdraw")
async def withdraw_callback(callback_query: types.CallbackQuery):
    if callback_query.message.chat.type != "private":
        await callback_query.answer("Withdrawals can only be made in private chat!", show_alert=True)
        return
    
    user_id = str(callback_query.from_user.id)
    
    # Check if user has sufficient balance for minimum withdrawal
    if user_id not in data["user_balances"] or data["user_balances"][user_id] < 10:
        await callback_query.message.answer("❌ Insufficient balance. Minimum withdrawal amount is $10.")
        await callback_query.answer()
        return
    
    # Create keyboard with cryptocurrency options
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("USDT TRC20 (Fee: $1.5)", callback_data="withdraw_usdt_trc20"),
        InlineKeyboardButton("USDT BEP20 (Fee: $0.1)", callback_data="withdraw_usdt_bep20"),
        InlineKeyboardButton("LITECOIN (Fee: $0.05)", callback_data="withdraw_litecoin"),
        InlineKeyboardButton("BITCOIN (Fee: $2.5)", callback_data="withdraw_bitcoin"),
        InlineKeyboardButton("Cancel", callback_data="cancel_withdraw")
    )
    
    await callback_query.message.answer("Select the cryptocurrency for your withdrawal:", reply_markup=keyboard)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("withdraw_"))
async def process_withdraw_currency(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    
    # Skip if it's the cancel button
    if callback.data == "cancel_withdraw":
        await callback.message.edit_text("❌ Withdrawal process cancelled.")
        await callback.answer()
        return
    
    # Extract currency from callback data
    currency = "_".join(callback.data.split("_")[1:])

    
    # Initialize withdrawal data
    data["user_withdrawal_data"][user_id] = {
        "currency": currency,
        "fee": data["withdrawal_fees"].get(currency, 0),
        "state": "amount"
    }
    save_data()
    
    # Ask for withdrawal amount
    await callback.message.edit_text(
        f"Selected: {currency.upper()}\n"
        f"Fee: ${data['withdrawal_fees'].get(currency, 0):.2f}\n\n"
        f"Enter the amount you want to withdraw (Minimum $10):"
    )
    await callback.answer()

@dp.message_handler(lambda message: message.chat.type == "private" and 
                   str(message.from_user.id) in data["user_withdrawal_data"] and 
                   data["user_withdrawal_data"][str(message.from_user.id)].get("state") == "amount")
async def handle_withdrawal_amount(message: types.Message):
    user_id = str(message.from_user.id)
    withdrawal_data = data["user_withdrawal_data"][user_id]
    
    try:
        amount = round(float(message.text), 2)
        
        # Check minimum withdrawal amount
        if amount < 10:
            await message.answer("❌ Minimum withdrawal amount is $10. Please enter a valid amount.")
            return
        
        # Get fee
        fee = withdrawal_data["fee"]
        
        # Calculate actual amount user will receive (amount - fee)
        receive_amount = round(amount - fee, 2)
        
        # Check if the amount after fee deduction is still valid
        if receive_amount <= 0:
            await message.answer(
                f"❌ The withdrawal amount must be greater than the fee (${fee:.2f})."
            )
            return
        
        # Check if user has sufficient balance
        if user_id not in data["user_balances"] or data["user_balances"][user_id] < amount:
            await message.answer(
                f"❌ Insufficient balance. Your balance: ${data['user_balances'].get(user_id, 0):.2f}\n"
                f"Withdrawal amount needed: ${amount:.2f}"
            )
            return
        
        # Update withdrawal data
        withdrawal_data["amount"] = amount
        withdrawal_data["receive_amount"] = receive_amount
        withdrawal_data["state"] = "address"
        save_data()
        
        # Ask for wallet address
        await message.answer(
            f"💰 You will receive: ${receive_amount:.2f}\n"
            f"Fee: ${fee:.2f}\n"
            f"Total deduction: ${amount:.2f}\n\n"
            f"Enter your {withdrawal_data['currency'].upper()} wallet address for receiving funds:"
        )
        
    except ValueError:
        await message.answer("❌ Please enter a valid number.")

@dp.message_handler(lambda message: message.chat.type == "private" and 
                   str(message.from_user.id) in data["user_withdrawal_data"] and 
                   data["user_withdrawal_data"][str(message.from_user.id)].get("state") == "address")
async def handle_withdrawal_address(message: types.Message):
    user_id = str(message.from_user.id)
    withdrawal_data = data["user_withdrawal_data"][user_id]
    
    # Get wallet address from message
    wallet_address = message.text.strip()
    
    # Basic validation (can be improved with regex for specific currencies)
    if len(wallet_address) < 10:
        await message.answer("❌ Invalid wallet address. Please enter a valid address.")
        return
    
    # Update withdrawal data
    withdrawal_data["wallet_address"] = wallet_address
    withdrawal_data["state"] = "confirm"
    save_data()
    
    # Generate withdrawal ID
    withdrawal_id = generate_withdrawal_id()
    withdrawal_data["withdrawal_id"] = withdrawal_id
    
    # Format currency name for display
    currency_display = {
        "usdt_trc20": "USDT (TRC20)",
        "usdt_bep20": "USDT (BEP20)",
        "bitcoin": "Bitcoin (BTC)",
        "litecoin": "Litecoin (LTC)"
    }.get(withdrawal_data["currency"], withdrawal_data["currency"].upper())
    
    # Create confirmation keyboard
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_withdrawal_{withdrawal_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")
    )
    
    # Send confirmation message
    await message.answer(
        f"📤 Withdrawal Request #{withdrawal_id}\n\n"
        f"Currency: {currency_display}\n"
        f"Amount to withdraw: ${withdrawal_data['amount']:.2f}\n"
        f"Fee: ${withdrawal_data['fee']:.2f}\n"
        f"You will receive: ${withdrawal_data['receive_amount']:.2f}\n"
        f"Wallet Address: {wallet_address}\n\n"
        f"Please confirm your withdrawal request:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_withdrawal_"))
async def confirm_withdrawal(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    
    if user_id not in data["user_withdrawal_data"]:
        await callback.answer("❌ Withdrawal session expired. Please start over.", show_alert=True)
        return
    
    withdrawal_data = data["user_withdrawal_data"][user_id]
    withdrawal_id = callback.data.split("_")[2]
    
    # Verify withdrawal ID matches
    if withdrawal_id != withdrawal_data.get("withdrawal_id"):
        await callback.answer("❌ Invalid withdrawal ID. Please start over.", show_alert=True)
        return
    
    # Check if user still has sufficient balance
    if user_id not in data["user_balances"] or data["user_balances"][user_id] < withdrawal_data["amount"]:
        await callback.answer("❌ Insufficient balance. Your withdrawal cannot be processed.", show_alert=True)
        await callback.message.edit_text(
            f"{callback.message.text}\n\n❌ CANCELLED - Insufficient balance"
        )
        
        # Clean up withdrawal data
        if user_id in data["user_withdrawal_data"]:
            del data["user_withdrawal_data"][user_id]
            save_data()
        return
    
    # Deduct amount from user's balance
    data["user_balances"][user_id] -= withdrawal_data["amount"]
    
    # Format currency name for display
    currency_display = {
        "usdt_trc20": "USDT (TRC20)",
        "usdt_bep20": "USDT (BEP20)",
        "bitcoin": "Bitcoin (BTC)",
        "litecoin": "Litecoin (LTC)"
    }.get(withdrawal_data["currency"], withdrawal_data["currency"].upper())
    
    # Create pending withdrawal record
    pending_withdrawal = {
        "withdrawal_id": withdrawal_id,
        "user_id": user_id,
        "amount": withdrawal_data["amount"],
        "fee": withdrawal_data["fee"],
        "receive_amount": withdrawal_data["receive_amount"],
        "currency": withdrawal_data["currency"],
        "wallet_address": withdrawal_data["wallet_address"],
        "created_time": time.time(),
        "username": callback.from_user.username or "Unknown",
        "full_name": f"{callback.from_user.first_name} {callback.from_user.last_name or ''}".strip()
    }
    
    # Add to pending withdrawals
    data["pending_withdrawals"][withdrawal_id] = pending_withdrawal
    
    # Clean up withdrawal data
    if user_id in data["user_withdrawal_data"]:
        del data["user_withdrawal_data"][user_id]
    
    save_data()
    
    # Update message to show pending status
    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ Withdrawal request submitted. Waiting for admin approval."
    )
    
    # Send notification to admin group
    admin_keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_withdrawal_{withdrawal_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_withdrawal_{withdrawal_id}")
    )
    
    try:
        await bot.send_message(
            chat_id=data["admin_group"],
            text=f"🔔 NEW WITHDRAWAL REQUEST #{withdrawal_id}\n\n"
                 f"User: {pending_withdrawal['full_name']} (@{pending_withdrawal['username']})\n"
                 f"User ID: {user_id}\n"
                 f"Currency: {currency_display}\n"
                 f"Amount to withdraw: ${pending_withdrawal['amount']:.2f}\n"
                 f"Fee: ${pending_withdrawal['fee']:.2f}\n"
                 f"User will receive: ${pending_withdrawal['receive_amount']:.2f}\n"
                 f"Wallet: {pending_withdrawal['wallet_address']}\n"
                 f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=admin_keyboard
        )
    except Exception as e:
        print(f"Error sending admin notification: {e}")
    
    await callback.answer("Withdrawal request submitted successfully!")

@dp.callback_query_handler(lambda c: c.data.startswith("approve_withdrawal_") or c.data.startswith("reject_withdrawal_"))
async def process_withdrawal_action(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    
    if admin_id not in data["admin_users"]:
        await callback.answer("❌ You are not authorized to perform this action.", show_alert=True)
        return
    
    action, _, withdrawal_id = callback.data.split("_")
    
    if withdrawal_id not in data["pending_withdrawals"]:
        await callback.answer("❌ This withdrawal request no longer exists.", show_alert=True)
        await callback.message.edit_text(f"{callback.message.text}\n\n❌ WITHDRAWAL NOT FOUND")
        return
    
    withdrawal = data["pending_withdrawals"][withdrawal_id]
    user_id = withdrawal["user_id"]
    
    if action == "approve":
        # Move to completed withdrawals
        withdrawal["status"] = "approved"
        withdrawal["approved_by"] = admin_id
        withdrawal["approved_time"] = time.time()
        data["completed_withdrawals"].append(withdrawal)
        
        # Remove from pending
        del data["pending_withdrawals"][withdrawal_id]
        save_data()
        
        # Notify user
        try:
            await bot.send_message(
                chat_id=int(user_id),
                text=f"✅ Your withdrawal of ${withdrawal['amount']:.2f} {withdrawal['currency'].upper()} has been processed!\n"
                     f"Withdrawal ID: #{withdrawal_id}\n"
                     f"Please check your wallet for the funds.\n"
                     f"Your new balance: ${data['user_balances'].get(user_id, 0):.2f}"
            )
        except Exception as e:
            print(f"Error notifying user about approved withdrawal: {e}")
        
        # Update admin message
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ APPROVED by {callback.from_user.first_name}"
        )
        
    elif action == "reject":
        # Refund the original withdrawal amount to the user's balance
        data["user_balances"][user_id] += withdrawal["amount"]
        
        # Update withdrawal record
        withdrawal["status"] = "rejected"
        withdrawal["rejected_by"] = admin_id
        withdrawal["rejected_time"] = time.time()
        data["completed_withdrawals"].append(withdrawal)
        
        # Remove from pending
        del data["pending_withdrawals"][withdrawal_id]
        save_data()
        
        try:
            await bot.send_message(
                chat_id=int(user_id),
                text=f"❌ Your withdrawal of ${withdrawal['amount']:.2f} {withdrawal['currency'].upper()} has been rejected.\n"
                     f"Withdrawal ID: #{withdrawal_id}\n"
                     f"The funds have been returned to your balance.\n"
                     f"Your current balance: ${data['user_balances'].get(user_id, 0):.2f}\n"
                     f"Please contact support for assistance."
            )
        except Exception as e:
            print(f"Error notifying user about rejected withdrawal: {e}")
        
        await callback.message.edit_text(
            f"{callback.message.text}\n\n❌ REJECTED by {callback.from_user.first_name}"
        )
    
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "cancel_withdraw")
async def cancel_withdraw(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    if user_id in data["user_withdrawal_data"]:
        del data["user_withdrawal_data"][user_id]
        save_data()
    await callback.message.edit_text("❌ Withdrawal process cancelled.")
    await callback.answer()

@dp.message_handler(lambda message: message.chat.type == "private" and 
                   str(message.from_user.id) in data["user_invoice_data"] and 
                   data["user_invoice_data"][str(message.from_user.id)].get("state") == "amount")
async def handle_deposit_amount(message: types.Message):
    user_id = str(message.from_user.id)
    
    try:
        amount = round(float(message.text), 2)
        if amount < 1:
            await message.answer("❌ Minimum deposit is $1. Please enter a valid amount.")
            return
        
        data["user_invoice_data"][user_id] = {"amount": amount, "state": "currency"}
        save_data()
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("USDT TRC20", callback_data="currency_usdt_trc20"),
            InlineKeyboardButton("USDT BEP20", callback_data="currency_usdt_bep20"),
            InlineKeyboardButton("Bitcoin", callback_data="currency_bitcoin"),
            InlineKeyboardButton("Litecoin", callback_data="currency_litecoin"),
            InlineKeyboardButton("Cancel", callback_data="cancel_deposit")
        )
        
        await message.answer(f"Select the currency for your deposit of ${amount:.2f}:", reply_markup=keyboard)
    except ValueError:
        await message.answer("❌ Please enter a valid number.")
@dp.callback_query_handler(lambda c: c.data.startswith("currency_"))
async def process_currency(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    user_data = data["user_invoice_data"].get(user_id)
    
    if not user_data or user_data.get("state") != "currency":
        await callback.answer("Session expired. Please start over.", show_alert=True)
        return
    
    currency = "_".join(callback.data.split("_")[1:])
    wallet = data["wallets"].get(currency)
    
    if wallet:
        amount = user_data["amount"]
        network_name = {
            "usdt_trc20": "TRON (TRC20)",
            "usdt_bep20": "Binance Smart Chain (BEP20)",
            "bitcoin": "Bitcoin Network",
            "litecoin": "Litecoin Network"
        }.get(currency, currency.upper())
        
        # Generate invoice ID
        invoice_id = generate_invoice_id()
        
        # Create QR code content based on currency
        if currency == "usdt_trc20":
            qr_content = f"tron:{wallet}"  # TRON protocol
        elif currency == "usdt_bep20":
            qr_content = f"ethereum:{wallet}"  # BSC uses Ethereum format
        elif currency == "bitcoin":
            qr_content = f"bitcoin:{wallet}"
        elif currency == "litecoin":
            qr_content = f"litecoin:{wallet}"
        else:
            qr_content = wallet
        
        # Generate QR code
        qr_bio = generate_qr_code(qr_content)
        
        # Calculate expiry time (30 minutes from now)
        expiry_time = time.time() + (30 * 60)
        expiry_datetime = datetime.now() + timedelta(minutes=30)
        expiry_str = expiry_datetime.strftime("%Y-%m-%d %H:%M:%S")
        
        # Store invoice in pending invoices
        data["pending_invoices"][invoice_id] = {
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "wallet": wallet,
            "network": network_name,
            "created_time": time.time(),
            "expiry_time": expiry_time,
            "username": callback.from_user.username or "Unknown",
            "full_name": f"{callback.from_user.first_name} {callback.from_user.last_name or ''}".strip()
        }
        save_data()
        
        # Send QR code and wallet details to user
        message_text = (
            f"⚠️ Deposit Invoice #{invoice_id}\n\n"
            f"Amount: ${amount:.2f}\n"
            f"Currency: {currency.upper()}\n"
            f"Network: {network_name}\n"
            f"Address: `{wallet}`\n\n"
            f"⏱️ This invoice expires at: {expiry_str}\n\n"
            f"⚠️ IMPORTANT:\n"
            f"• Send EXACTLY ${amount:.2f} worth of {currency.upper()}\n"
            f"• Use ONLY the {network_name} network\n"
            f"• Double check the address before sending\n\n"
            "Scan the QR code or copy the address to complete your payment.\n"
            "After sending, wait for admin approval."
        )
        
        # Send QR code with detailed instructions
        await bot.send_photo(
            chat_id=callback.message.chat.id,
            photo=qr_bio,
            caption=message_text,
            parse_mode="Markdown"
        )
        
        # Send notification to admin group
        admin_keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{invoice_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{invoice_id}")
        )
        
        try:
            await bot.send_message(
                chat_id=data["admin_group"],
                text=f"🔔 NEW DEPOSIT REQUEST #{invoice_id}\n\n"
                     f"User: {data['pending_invoices'][invoice_id]['full_name']} (@{data['pending_invoices'][invoice_id]['username']})\n"
                     f"User ID: {user_id}\n"
                     f"Amount: ${amount:.2f}\n"
                     f"Currency: {currency.upper()}\n"
                     f"Network: {network_name}\n"
                     f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                     f"Expires: {expiry_str}",
                reply_markup=admin_keyboard
            )
        except Exception as e:
            print(f"Error sending admin notification: {e}")
        
        if user_id in data["user_invoice_data"]:
            del data["user_invoice_data"][user_id]
            save_data()
    else:
        await callback.answer("Invalid currency selection.", show_alert=True)
    
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("approve_") or c.data.startswith("reject_"))
async def process_invoice_action(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    
    if admin_id not in data["admin_users"]:
        await callback.answer("❌ You are not authorized to perform this action.", show_alert=True)
        return
    
    action, invoice_id = callback.data.split("_")
    
    if invoice_id not in data["pending_invoices"]:
        await callback.answer("❌ This invoice no longer exists or has expired.", show_alert=True)
        await callback.message.edit_text(f"{callback.message.text}\n\n❌ INVOICE NOT FOUND OR EXPIRED")
        return
    
    invoice = data["pending_invoices"][invoice_id]
    user_id = invoice["user_id"]
    
    if action == "approve":
        # Add balance to user
        if user_id not in data["user_balances"]:
            data["user_balances"][user_id] = 0
        
        data["user_balances"][user_id] += invoice["amount"]
        
        # Move to completed invoices
        invoice["status"] = "approved"
        invoice["approved_by"] = admin_id
        invoice["approved_time"] = time.time()
        data["completed_invoices"].append(invoice)
        
        # Remove from pending
        del data["pending_invoices"][invoice_id]
        save_data()
        
        # Notify user
        try:
            await bot.send_message(
                chat_id=int(user_id),
                text=f"✅ Your deposit of ${invoice['amount']:.2f} has been approved!\n"
                     f"Invoice ID: #{invoice_id}\n"
                     f"Your new balance: ${data['user_balances'][user_id]:.2f}"
            )
        except Exception as e:
            print(f"Error notifying user about approved deposit: {e}")
        
        # Update admin message
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ APPROVED by {callback.from_user.first_name}"
        )
        
    elif action == "reject":
        # Move to completed invoices with rejected status
        invoice["status"] = "rejected"
        invoice["rejected_by"] = admin_id
        invoice["rejected_time"] = time.time()
        data["completed_invoices"].append(invoice)
        
        # Remove from pending
        del data["pending_invoices"][invoice_id]
        save_data()
        
        # Notify user
        try:
            await bot.send_message(
                chat_id=int(user_id),
                text=f"❌ Your deposit of ${invoice['amount']:.2f} has been rejected.\n"
                     f"Invoice ID: #{invoice_id}\n"
                     f"Please contact support for assistance."
            )
        except Exception as e:
            print(f"Error notifying user about rejected deposit: {e}")
        
        # Update admin message
        await callback.message.edit_text(
            f"{callback.message.text}\n\n❌ REJECTED by {callback.from_user.first_name}"
        )
    
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "cancel_deposit")
async def cancel_deposit(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    if user_id in data["user_invoice_data"]:
        del data["user_invoice_data"][user_id]
        save_data()
    await callback.message.edit_text("❌ Deposit process cancelled.")
    await callback.answer()

@dp.message_handler(commands=['setbal'])
async def set_balance(message: types.Message):
    if message.from_user.id not in data["admin_users"]:
        await message.answer("❌ Unauthorized.")
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            raise ValueError("Invalid number of arguments")
            
        user_id = str(command_parts[1])
        amount = round(float(command_parts[2]), 2)
        data["user_balances"][user_id] = amount
        save_data()
        await message.answer(f"✅ Updated balance for {user_id} to ${amount:.2f}")
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /setbal <user_id> <amount>\nError: {str(e)}")

@dp.message_handler(commands=['ban'])
async def ban_user(message: types.Message):
    if message.from_user.id not in data["admin_users"]:
        await message.answer("❌ Unauthorized.")
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            raise ValueError("Invalid number of arguments")
            
        user_id = int(command_parts[1])
        if user_id not in data["banned_users"]:
            data["banned_users"].append(user_id)
            save_data()
            await message.answer(f"✅ User {user_id} banned.")
        else:
            await message.answer(f"User {user_id} is already banned.")
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /ban <user_id>\nError: {str(e)}")

@dp.message_handler(commands=['unban'])
async def unban_user(message: types.Message):
    if message.from_user.id not in data["admin_users"]:
        await message.answer("❌ Unauthorized.")
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            raise ValueError("Invalid number of arguments")
            
        user_id = int(command_parts[1])
        if user_id in data["banned_users"]:
            data["banned_users"].remove(user_id)
            save_data()
            await message.answer(f"✅ User {user_id} unbanned.")
        else:
            await message.answer(f"User {user_id} is not banned.")
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /unban <user_id>\nError: {str(e)}")

@dp.message_handler(commands=['addadmin'])
async def add_admin(message: types.Message):
    if message.from_user.id not in data["admin_users"]:
        await message.answer("❌ Unauthorized.")
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            raise ValueError("Invalid number of arguments")
            
        user_id = int(command_parts[1])
        if user_id not in data["admin_users"]:
            data["admin_users"].append(user_id)
            save_data()
            await message.answer(f"✅ User {user_id} added as admin.")
        else:
            await message.answer(f"User {user_id} is already an admin.")
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /addadmin <user_id>\nError: {str(e)}")

@dp.message_handler(commands=['removeadmin'])
async def remove_admin(message: types.Message):
    if message.from_user.id not in data["admin_users"]:
        await message.answer("❌ Unauthorized.")
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            raise ValueError("Invalid number of arguments")
            
        user_id = int(command_parts[1])
        if user_id in data["admin_users"] and len(data["admin_users"]) > 1:
            data["admin_users"].remove(user_id)
            save_data()
            await message.answer(f"✅ User {user_id} removed from admins.")
        else:
            await message.answer("❌ Cannot remove the last admin.")
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /removeadmin <user_id>\nError: {str(e)}")

@dp.message_handler(commands=['setadmingroup'])
async def set_admin_group(message: types.Message):
    if message.from_user.id not in data["admin_users"]:
        await message.answer("❌ Unauthorized.")
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            raise ValueError("Invalid number of arguments")
            
        group_id = int(command_parts[1])
        data["admin_group"] = group_id
        save_data()
        await message.answer(f"✅ Admin group set to {group_id}")
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /setadmingroup <group_id>\nError: {str(e)}")

@dp.message_handler(commands=['addgroup'])
async def add_group(message: types.Message):
    if message.from_user.id not in data["admin_users"]:
        await message.answer("❌ Unauthorized.")
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            raise ValueError("Invalid number of arguments")
            
        group_id = int(command_parts[1])
        if group_id not in data["allowed_groups"]:
            data["allowed_groups"].append(group_id)
            save_data()
            await message.answer(f"✅ Group {group_id} added to allowed groups.")
        else:
            await message.answer(f"Group {group_id} is already in allowed groups.")
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /addgroup <group_id>\nError: {str(e)}")

@dp.message_handler(commands=['removegroup'])
async def remove_group(message: types.Message):
    if message.from_user.id not in data["admin_users"]:
        await message.answer("❌ Unauthorized.")
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            raise ValueError("Invalid number of arguments")
            
        group_id = int(command_parts[1])
        if group_id in data["allowed_groups"]:
            data["allowed_groups"].remove(group_id)
            save_data()
            await message.answer(f"✅ Group {group_id} removed from allowed groups.")
        else:
            await message.answer(f"Group {group_id} is not in allowed groups.")
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /removegroup <group_id>\nError: {str(e)}")

@dp.message_handler(commands=['setwallet'])
async def set_wallet(message: types.Message):
    if message.from_user.id not in data["admin_users"]:
        await message.answer("❌ Unauthorized.")
        return
    
    try:
        command_parts = message.text.split(maxsplit=2)
        if len(command_parts) != 3:
            raise ValueError("Invalid number of arguments")
            
        currency = command_parts[1].lower()
        wallet_address = command_parts[2].strip()
        
        if currency in ["usdt_trc20", "usdt_bep20", "bitcoin", "litecoin"]:
            data["wallets"][currency] = wallet_address
            save_data()
            await message.answer(f"✅ Wallet for {currency} updated to: {wallet_address}")
        else:
            await message.answer("❌ Invalid currency. Use: usdt_trc20, usdt_bep20, bitcoin, or litecoin")
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /setwallet <currency> <address>\nError: {str(e)}")

# New command for admin to cancel any game
@dp.message_handler(commands=['cancel'])
async def admin_cancel_game(message: types.Message):
    user_id = message.from_user.id
    
    # Check if user is an admin
    if user_id not in data["admin_users"]:
        await message.answer("❌ Unauthorized. Only admins can use this command.")
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            raise ValueError("Invalid number of arguments")
            
        game_id = command_parts[1].upper()
        
        # Check if game exists
        if game_id not in data["active_games"]:
            await message.answer(f"❌ Game #{game_id} not found or already completed.")
            return
        
        game = data["active_games"][game_id]
        
        # Get player information
        player1_id = game["player1_id"]
        player1_name = game["player1_name"].split()[0]
        
        player2_id = None
        player2_name = None
        if "player2_id" in game and game["player2_id"]:
            player2_id = game["player2_id"]
            player2_name = game["player2_name"].split()[0]
        
        # Update message to show admin cancellation
        try:
            await bot.edit_message_text(
                chat_id=game["chat_id"],
                message_id=game["message_id"],
                text=f"🎲 DICE GAME #{game_id}\n\n"
                     f"Player 1: {player1_name}\n"
                     f"{f'Player 2: {player2_name}' if player2_name else ''}\n"
                     f"Bet Amount: ${game['bet_amount']:.2f}\n\n"
                     f"❌ CANCELLED BY ADMIN",
                reply_markup=None
            )
        except Exception as e:
            print(f"Error updating game message: {e}")
            # If we can't edit the original message, send a new one
            try:
                await bot.send_message(
                    chat_id=game["chat_id"],
                    text=f"🎲 DICE GAME #{game_id}\n\n"
                         f"❌ CANCELLED BY ADMIN"
                )
            except Exception as e2:
                print(f"Error sending cancellation message: {e2}")
        
        # Notify players about cancellation
        admin_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        
        try:
            await bot.send_message(
                chat_id=int(player1_id),
                text=f"❌ Your game #{game_id} has been cancelled by admin {admin_name}."
            )
            
            if player2_id:
                await bot.send_message(
                    chat_id=int(player2_id),
                    text=f"❌ Your game #{game_id} has been cancelled by admin {admin_name}."
                )
        except Exception as e:
            print(f"Error notifying players about cancellation: {e}")
        
        # Remove players from active players
        if player1_id in data["active_players"]:
            del data["active_players"][player1_id]
        if player2_id and player2_id in data["active_players"]:
            del data["active_players"][player2_id]
            
        # Remove the game
        del data["active_games"][game_id]
        save_data()
        
        await message.answer(f"✅ Game #{game_id} has been cancelled.")
        
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Invalid format. Use: /cancel <game_id>\nError: {str(e)}")

# New command for leaderboard
@dp.message_handler(commands=['lboard'])
async def leaderboard_command(message: types.Message):
    # Check if in allowed group
    if message.chat.type not in ["supergroup", "group"] or message.chat.id not in data["allowed_groups"]:
        if message.chat.type == "private":
            await message.answer("Leaderboard is only available in designated groups.")
        return
    
    # Filter and sort wagers for this week
    weekly_wagers = {}
    for user_id, wager_info in data["user_wagers"].items():
        if isinstance(wager_info, dict) and "weekly" in wager_info:
            weekly_wagers[user_id] = wager_info["weekly"]
        elif isinstance(wager_info, (int, float)):
            # For backward compatibility
            weekly_wagers[user_id] = wager_info
    
    # Sort by amount wagered
    sorted_wagers = sorted(weekly_wagers.items(), key=lambda x: x[1], reverse=True)
    
    # Get top 10
    top_10 = sorted_wagers[:10]
    
    if not top_10:
        await message.answer("📊 No wagers recorded this week yet.")
        return
    
    # Build leaderboard message
    leaderboard_text = "📊 **Weekly Wager Leaderboard**\n\n"
    
    for i, (user_id, amount) in enumerate(top_10, 1):
        # Try to get user info
        try:
            user = await bot.get_chat(int(user_id))
            user_name = user.first_name
        except:
            user_name = f"User {user_id}"
        
        leaderboard_text += f"{i}. {user_name}: ${amount:.2f}\n"
    
    await message.answer(leaderboard_text, parse_mode="Markdown")

# New command for betting
@dp.message_handler(commands=['bet'])
async def bet_command(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Check if user is banned
    if int(user_id) in data["banned_users"]:
        await message.answer("❌ You are banned from using this bot.")
        return
    
    # Check if in allowed group
    if message.chat.type not in ["supergroup", "group"] or message.chat.id not in data["allowed_groups"]:
        await message.answer("❌ Betting is only allowed in designated groups.")
        return
    
    # Check if user is already in a game
    if user_id in data["active_players"]:
        game_id = data["active_players"][user_id]
        game_status = "unknown"
        if game_id in data["active_games"]:
            game_status = data["active_games"][game_id]["status"]
            
        await message.answer(f"❌ You already have an active game (#{game_id}, status: {game_status}). Please finish or cancel it before starting a new one.")
        return
    
    # Parse bet amount
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.answer("❌ Invalid format. Use: /bet <amount>")
            return
            
        bet_amount = round(float(command_parts[1]), 2)
        
        # Check minimum bet
        if bet_amount < 1:
            await message.answer("❌ Minimum bet is $1.")
            return
        
        # Check user balance
        if user_id not in data["user_balances"]:
            data["user_balances"][user_id] = 0
            save_data()
            
        if data["user_balances"][user_id] < bet_amount:
            await message.answer(f"❌ Insufficient balance. Your balance: ${data['user_balances'][user_id]:.2f}")
            return
        
        # Generate game ID
        game_id = generate_game_id()
        
        # Create game data
        player_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        if message.from_user.username:
            player_name += f" (@{message.from_user.username})"
            
        game_data = {
            "game_id": game_id,
            "chat_id": message.chat.id,
            "bet_amount": bet_amount,
            "player1_id": user_id,
            "player1_name": player_name,
            "created_time": time.time(),
            "status": "pending",
            "rounds": [],
            "player1_score": 0,
            "player2_score": 0
        }
        
        # Mark user as in an active game
        data["active_players"][user_id] = game_id
        
        # Create inline keyboard
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{game_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{game_id}")
        )
        
        # Send game invitation
        sent_message = await message.answer(
            f"🎲 DICE GAME #{game_id}\n\n"
            f"Player: {player_name.split()[0]}\n"
            f"Bet Amount: ${bet_amount:.2f}\n\n"
            f"📜 Rules:\n"
            f"• Each player rolls a dice\n"
            f"• Higher number wins the round\n"
            f"• First to win 3 rounds wins the game\n"
            f"• Winner gets 1.95x the bet amount\n\n"
            f"Waiting for confirmation...",
            reply_markup=keyboard
        )
        
        # Store message ID for future reference
        game_data["message_id"] = sent_message.message_id
        
        # Save game data
        data["active_games"][game_id] = game_data
        save_data()
        
    except ValueError:
        await message.answer("❌ Invalid bet amount. Please enter a valid number.")

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_"))
async def confirm_game(callback: types.CallbackQuery):
    game_id = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    
    # Check if game exists
    if game_id not in data["active_games"]:
        await callback.answer("❌ This game no longer exists.", show_alert=True)
        return
    
    game = data["active_games"][game_id]
    
    # Check if user is the game creator
    if user_id != game["player1_id"]:
        await callback.answer("❌ Only the player who created this game can confirm it.", show_alert=True)
        return
    
    # Check if game is still pending
    if game["status"] != "pending":
        await callback.answer("❌ This game has already been confirmed or cancelled.", show_alert=True)
        return
    
    # Check if user still has enough balance
    if data["user_balances"][user_id] < game["bet_amount"]:
        await callback.answer("❌ You no longer have enough balance for this bet.", show_alert=True)
        
        # Update message to show insufficient balance
        await bot.edit_message_text(
            chat_id=game["chat_id"],
            message_id=game["message_id"],
            text=f"🎲 DICE GAME #{game_id}\n\n"
                 f"Player: {game['player1_name'].split()[0]}\n"
                 f"Bet Amount: ${game['bet_amount']:.2f}\n\n"
                 f"❌ CANCELLED - Insufficient balance",
            reply_markup=None
        )
        
        # Remove game and player from active lists
        del data["active_games"][game_id]
        if user_id in data["active_players"]:
            del data["active_players"][user_id]
        save_data()
        return
    
    # Update game status
    game["status"] = "waiting_player2"
    save_data()
    
    # Create new keyboard for player 2
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🎮 Play", callback_data=f"play_{game_id}"))
    
    # Update message
    await bot.edit_message_text(
        chat_id=game["chat_id"],
        message_id=game["message_id"],
        text=f"🎲 DICE GAME #{game_id}\n\n"
             f"Player 1: {game['player1_name'].split()[0]}\n"
             f"Bet Amount: ${game['bet_amount']:.2f}\n\n"
             f"📜 Rules:\n"
             f"• Each player rolls a dice\n"
             f"• Higher number wins the round\n"
             f"• First to win 3 rounds wins the game\n"
             f"• Winner gets 1.95x the bet amount\n\n"
             f"✅ Confirmed! Waiting for Player 2...",
        reply_markup=keyboard
    )
    
    await callback.answer("Game confirmed! Waiting for Player 2.")

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_"))
async def cancel_game(callback: types.CallbackQuery):
    game_id = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    
    # Check if game exists
    if game_id not in data["active_games"]:
        await callback.answer("❌ This game no longer exists.", show_alert=True)
        return
    
    game = data["active_games"][game_id]
    
    # Check if user is the game creator
    if user_id != game["player1_id"]:
        await callback.answer("❌ Only the player who created this game can cancel it.", show_alert=True)
        return
    
    # Check if game is still pending or waiting for player 2
    if game["status"] not in ["pending", "waiting_player2"]:
        await callback.answer("❌ This game cannot be cancelled anymore.", show_alert=True)
        return
    
    # Update message to show cancellation
    await bot.edit_message_text(
        chat_id=game["chat_id"],
        message_id=game["message_id"],
        text=f"🎲 DICE GAME #{game_id}\n\n"
             f"Player: {game['player1_name'].split()[0]}\n"
             f"Bet Amount: ${game['bet_amount']:.2f}\n\n"
             f"❌ CANCELLED by player",
        reply_markup=None
    )
    
    # Remove game and player from active lists
    del data["active_games"][game_id]
    if user_id in data["active_players"]:
        del data["active_players"][user_id]
    save_data()
    
    await callback.answer("Game cancelled.")

@dp.callback_query_handler(lambda c: c.data.startswith("play_"))
async def play_game(callback: types.CallbackQuery):
    game_id = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    
    # Check if game exists
    if game_id not in data["active_games"]:
        await callback.answer("❌ This game no longer exists.", show_alert=True)
        return
    
    game = data["active_games"][game_id]
    
    # Check if game is waiting for player 2
    if game["status"] != "waiting_player2":
        await callback.answer("❌ This game is not available to join.", show_alert=True)
        return
    
    # Check if user is not player 1 (can't play against yourself)
    if user_id == game["player1_id"]:
        await callback.answer("❌ You cannot play against yourself.", show_alert=True)
        return
    
    # Check if user is already in another game
    if user_id in data["active_players"]:
        existing_game_id = data["active_players"][user_id]
        await callback.answer(f"❌ You are already in an active game (#{existing_game_id}). Please finish it before joining another.", show_alert=True)
        return
    
    # Check if user has enough balance
    if user_id not in data["user_balances"]:
        data["user_balances"][user_id] = 0
        save_data()
        
    if data["user_balances"][user_id] < game["bet_amount"]:
        await callback.answer(f"❌ Insufficient balance. Your balance: ${data['user_balances'][user_id]:.2f}", show_alert=True)
        return
    
    # Set player 2 info
    player2_name = f"{callback.from_user.first_name} {callback.from_user.last_name or ''}".strip()
    if callback.from_user.username:
        player2_name += f" (@{callback.from_user.username})"
        
    game["player2_id"] = user_id
    game["player2_name"] = player2_name
    game["status"] = "playing"
    game["current_round"] = 1
    game["current_player"] = "player1"
    
    # Mark player 2 as in an active game
    data["active_players"][user_id] = game_id
    
    save_data()
    
    # Update message
    await bot.edit_message_text(
        chat_id=game["chat_id"],
        message_id=game["message_id"],
        text=f"🎲 DICE GAME #{game_id}\n\n"
             f"Player 1: {game['player1_name'].split()[0]}\n"
             f"Player 2: {game['player2_name'].split()[0]}\n"
             f"Bet Amount: ${game['bet_amount']:.2f}\n\n"
             f"📜 Game Started!\n"
             f"Round 1 of 5 (Best of 5)\n\n"
             f"Waiting for {game['player1_name'].split()[0]} to roll the dice...\n"
             f"(Please send the 🎲 emoji)",
        reply_markup=None
    )
    
    await callback.answer("Game started! Wait for Player 1 to roll the dice.")

@dp.message_handler(content_types=types.ContentType.DICE)

async def handle_dice(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Check if user is in an active game
    if user_id not in data["active_players"]:
        # Not in an active game
        return
    
    game_id = data["active_players"][user_id]
    
    # Check if game exists
    if game_id not in data["active_games"]:
        # Game doesn't exist anymore
        if user_id in data["active_players"]:
            del data["active_players"][user_id]
            save_data()
        return
    
    game = data["active_games"][game_id]
    
    # Check if it's this user's turn
    current_player_id = game["player1_id"] if game["current_player"] == "player1" else game["player2_id"]
    if user_id != current_player_id or message.chat.id != game["chat_id"]:
        # Not this user's turn or wrong chat
        return
    
    # Check if the dice emoji is used
    if message.dice.emoji != "🎲":
        await message.reply("Please use the dice emoji 🎲")
        return
    
    # Get dice value (1-6)
    dice_value = message.dice.value
    
    # Record the roll
    current_round = game.get("current_round", 1)
    current_player = game["current_player"]
    
    # Initialize round data if needed
    if len(game["rounds"]) < current_round:
        game["rounds"].append({"player1_roll": 0, "player2_roll": 0, "winner": None})
    
    # Record the roll
    game["rounds"][current_round - 1][f"{current_player}_roll"] = dice_value
    
    # Switch to next player or evaluate round
    if current_player == "player1":
        game["current_player"] = "player2"
        
        # Update message for player 2's turn
        await bot.send_message(
            chat_id=game["chat_id"],
            text=f"🎲 {game['player1_name'].split()[0]} rolled: {dice_value}\n\n"
                 f"Now waiting for {game['player2_name'].split()[0]} to roll the dice...\n"
                 f"(Please send the 🎲 emoji)"
        )
    else:
        # Both players have rolled, evaluate the round
        round_data = game["rounds"][current_round - 1]
        player1_roll = round_data["player1_roll"]
        player2_roll = round_data["player2_roll"]
        
        # Determine round winner
        if player1_roll > player2_roll:
            round_data["winner"] = "player1"
            game["player1_score"] += 1
            round_winner = game["player1_name"].split()[0]
        elif player2_roll > player1_roll:
            round_data["winner"] = "player2"
            game["player2_score"] += 1
            round_winner = game["player2_name"].split()[0]
        else:
            round_data["winner"] = "draw"
            round_winner = "Draw"
        
        # Check if game is over
        game_over = False
        game_winner = None
        
        if game["player1_score"] >= 3:
            game_over = True
            game_winner = "player1"
        elif game["player2_score"] >= 3:
            game_over = True
            game_winner = "player2"
        
        if game_over:
            # Game is over, determine winner and distribute rewards
            winner_id = game["player1_id"] if game_winner == "player1" else game["player2_id"]
            loser_id = game["player2_id"] if game_winner == "player1" else game["player1_id"]
            winner_name = game["player1_name"].split()[0] if game_winner == "player1" else game["player2_name"].split()[0]
            
            # Calculate winnings (1.95x bet amount)
            bet_amount = game["bet_amount"]
            winnings = round(bet_amount * 1.95, 2)
            
            # Update balances
            data["user_balances"][winner_id] += winnings
            data["user_balances"][loser_id] -= bet_amount
            
            # Update wager tracking for both players
            for player_id in [game["player1_id"], game["player2_id"]]:
                # Update wager data
                update_user_wager(player_id, bet_amount)
            
            save_data()
            
            # Send game result message
            await bot.send_message(
                chat_id=game["chat_id"],
                text=f"🎲 {game['player1_name'].split()[0]} rolled: {player1_roll}\n"
                     f"🎲 {game['player2_name'].split()[0]} rolled: {player2_roll}\n\n"
                     f"Round {current_round} Result: {round_winner} wins!\n\n"
                     f"🏆 GAME OVER! 🏆\n"
                     f"{game['player1_name'].split()[0]}: {game['player1_score']} | {game['player2_name'].split()[0]}: {game['player2_score']}\n\n"
                     f"🎉 {winner_name} wins ${winnings:.2f}!"
            )
            
            # Remove players from active players
            if game["player1_id"] in data["active_players"]:
                del data["active_players"][game["player1_id"]]
            if game["player2_id"] in data["active_players"]:
                del data["active_players"][game["player2_id"]]
                
            # Remove the game
            del data["active_games"][game_id]
            save_data()
        else:
            # Game continues
            if round_data["winner"] == "draw":
                # If it's a draw, replay the round
                await bot.send_message(
                    chat_id=game["chat_id"],
                    text=f"🎲 {game['player1_name'].split()[0]} rolled: {player1_roll}\n"
                         f"🎲 {game['player2_name'].split()[0]} rolled: {player2_roll}\n\n"
                         f"Round {current_round} Result: It's a draw! Replaying round...\n\n"
                         f"Current Score:\n"
                         f"{game['player1_name'].split()[0]}: {game['player1_score']} | {game['player2_name'].split()[0]}: {game['player2_score']}\n\n"
                         f"Waiting for {game['player1_name'].split()[0]} to roll the dice again...\n"
                         f"(Please send the 🎲 emoji)"
                )
                
                # Reset the round data but keep the same round number
                game["rounds"][current_round - 1] = {"player1_roll": 0, "player2_roll": 0, "winner": None}
                game["current_player"] = "player1"
            else:
                # Move to next round
                game["current_round"] = current_round + 1
                game["current_player"] = "player1"
                
                await bot.send_message(
                    chat_id=game["chat_id"],
                    text=f"🎲 {game['player1_name'].split()[0]} rolled: {player1_roll}\n"
                         f"🎲 {game['player2_name'].split()[0]} rolled: {player2_roll}\n\n"
                         f"Round {current_round} Result: {round_winner} wins!\n\n"
                         f"Current Score:\n"
                         f"{game['player1_name'].split()[0]}: {game['player1_score']} | {game['player2_name'].split()[0]}: {game['player2_score']}\n\n"
                         f"Starting Round {current_round + 1}...\n"
                         f"Waiting for {game['player1_name'].split()[0]} to roll the dice...\n"
                         f"(Please send the 🎲 emoji)"
                )
            
            save_data()




@dp.message_handler(commands=['tip'])
async def tip_command(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Check if user is banned
    if int(user_id) in data["banned_users"]:
        await message.answer("❌ You are banned from using this bot.")
        return
    
    # Check if message is a reply
    if not message.reply_to_message:
        await message.answer("❌ You must reply to a message to tip someone.")
        return
        
    # Get recipient user ID
    recipient_id = str(message.reply_to_message.from_user.id)
    
    # Can't tip yourself
    if user_id == recipient_id:
        await message.answer("❌ You cannot tip yourself.")
        return
    
    # Can't tip the bot
    if recipient_id == str(bot.id):
        await message.answer("❌ You cannot tip the bot.")
        return
    
    try:
        # Parse tip amount
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.answer("❌ Invalid format. Use: /tip <amount>")
            return
            
        tip_amount = round(float(command_parts[1]), 2)
        
        # Check minimum tip
        if tip_amount < 0.01:
            await message.answer("❌ Minimum tip amount is $0.01.")
            return
        
        # Check user balance
        if user_id not in data["user_balances"]:
            data["user_balances"][user_id] = 0
        if recipient_id not in data["user_balances"]:
            data["user_balances"][recipient_id] = 0
            
        if data["user_balances"][user_id] < tip_amount:
            await message.answer(f"❌ Insufficient balance. Your balance: ${data['user_balances'][user_id]:.2f}")
            return
        
        # Process the tip
        data["user_balances"][user_id] -= tip_amount
        data["user_balances"][recipient_id] += tip_amount
        
        # Record the tip in history
        tip_record = {
            "from_id": user_id,
            "to_id": recipient_id,
            "amount": tip_amount,
            "timestamp": time.time(),
            "from_name": f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip(),
            "to_name": f"{message.reply_to_message.from_user.first_name} {message.reply_to_message.from_user.last_name or ''}".strip()
        }
        data["tip_history"].append(tip_record)
        save_data()
        
        # Send confirmation messages
        sender_name = message.from_user.first_name
        recipient_name = message.reply_to_message.from_user.first_name
        
        await message.answer(
            f"✅ You tipped ${tip_amount:.2f} to {recipient_name}\n"
            f"Your new balance: ${data['user_balances'][user_id]:.2f}"
        )
        
        try:
            await bot.send_message(
                chat_id=int(recipient_id),
                text=f"🎁 {sender_name} tipped you ${tip_amount:.2f}!\n"
                     f"Your new balance: ${data['user_balances'][recipient_id]:.2f}"
            )
        except Exception as e:
            print(f"Error notifying tip recipient: {e}")
            
    except ValueError:
        await message.answer("❌ Invalid tip amount. Please enter a valid number.")

# Weekly wager reset task
async def reset_weekly_wagers():
    while True:
        # Get current time
        now = datetime.now()
        
        # Calculate time until next Monday at midnight
        days_until_monday = 7 - now.weekday() if now.weekday() > 0 else 7
        next_monday = now + timedelta(days=days_until_monday)
        next_monday = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate seconds until next Monday
        seconds_until_reset = (next_monday - now).total_seconds()
        
        # Wait until next Monday
        await asyncio.sleep(seconds_until_reset)
        
        # Reset weekly wagers
        for user_id in data["user_wagers"]:
            if isinstance(data["user_wagers"][user_id], dict):
                data["user_wagers"][user_id]["weekly"] = 0
        
        save_data()
        print(f"Weekly wagers reset at {datetime.now()}")

async def on_startup(dp):
    # Start the task to check for expired invoices
    asyncio.create_task(check_expired_invoices(bot))
    # Start the task to check for expired games
    asyncio.create_task(check_expired_games(bot))
    # Start the task to reset weekly wagers
    asyncio.create_task(reset_weekly_wagers())

if __name__ == "__main__":
    print("Bot starting...")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)