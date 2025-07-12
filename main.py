from dotenv import load_dotenv
load_dotenv()


import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from pymongo import MongoClient
from dotenv import load_dotenv
from payments import request_withdrawal
from utils import admin_only, get_or_create_user, process_referral, leaderboard_message

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_IDS = [int(uid) for uid in os.getenv("ADMIN_IDS").split(",")]
MIN_WITHDRAW = int(os.getenv("MIN_WITHDRAW", 30))
BOT_USERNAME = os.getenv("BOT_USERNAME")

client = MongoClient(MONGO_URI)
db = client["refer_earn_bot"]
users = db["users"]
withdrawals = db["withdrawals"]

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    args = context.args
    referral_code = args[0] if args else None
    get_or_create_user(users, user_id)
    process_referral(users, user_id, referral_code)
    update.message.reply_text(
        f"Welcome! Your referral link:\nhttps://t.me/{BOT_USERNAME}?start={user_id}"
    )

def refer(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    update.message.reply_text(
        f"Your referral link:\nhttps://t.me/{BOT_USERNAME}?start={user_id}"
    )

def balance(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = get_or_create_user(users, user_id)
    update.message.reply_text(f"Your balance: ₹{user['balance']}")

def set_upi(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        update.message.reply_text("Usage: /upi your_upi_id@bank")
        return
    upi_id = args[0]
    users.update_one({"user_id": user_id}, {"$set": {"upi_id": upi_id}})
    update.message.reply_text(f"UPI ID set to: {upi_id}")

def withdraw(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = get_or_create_user(users, user_id)
    if user["balance"] < MIN_WITHDRAW:
        update.message.reply_text(f"Minimum withdrawal is ₹{MIN_WITHDRAW}.")
        return
    if not user.get("upi_id"):
        update.message.reply_text("Set your UPI ID first using /upi command.")
        return
    request_withdrawal(users, withdrawals, user_id, user["balance"], user["upi_id"])
    users.update_one({"user_id": user_id}, {"$set": {"balance": 0}})
    update.message.reply_text(f"Withdrawal request of ₹{user['balance']} submitted for {user['upi_id']}. Await admin approval.")

def info(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = get_or_create_user(users, user_id)
    referred = user.get("referrals", [])
    update.message.reply_text(
        f"Your balance: ₹{user['balance']}\n"
        f"Your UPI ID: {user.get('upi_id','Not set')}\n"
        f"Referred users: {len(referred)}"
    )

def leaderboard(update: Update, context: CallbackContext):
    msg = leaderboard_message(users)
    update.message.reply_text(msg)

@admin_only
def admin_stats(update: Update, context: CallbackContext):
    total_users = users.count_documents({})
    total_balance = sum(u['balance'] for u in users.find())
    pending_withdrawals = withdrawals.count_documents({"status": "pending"})
    update.message.reply_text(
        f"Total users: {total_users}\n"
        f"Total balance in system: ₹{total_balance}\n"
        f"Pending withdrawals: {pending_withdrawals}"
    )

@admin_only
def approve_withdrawal(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 1:
        update.message.reply_text("Usage: /approve_withdrawal withdrawal_id")
        return
    withdrawal_id = args[0]
    withdrawal = withdrawals.find_one({"_id": withdrawal_id, "status": "pending"})
    if not withdrawal:
        update.message.reply_text("No such pending withdrawal.")
        return
    # Integrate with payment gateway API for payout here
    withdrawals.update_one({"_id": withdrawal_id}, {"$set": {"status": "approved"}})
    update.message.reply_text(f"Withdrawal {withdrawal_id} approved and marked as paid.")

def help_cmd(update: Update, context: CallbackContext):
    update.message.reply_text(
        "/start [referral_code] - Start bot\n"
        "/refer - Get your referral link\n"
        "/balance - Check your balance\n"
        "/upi your_upi_id@bank - Set your UPI ID\n"
        "/withdraw - Withdraw your earnings\n"
        "/info - Show your info\n"
        "/leaderboard - Top referrers\n"
        "/help - Show this message\n"
        "Admin commands: /admin_stats, /approve_withdrawal"
    )

updater = Updater(BOT_TOKEN)
dp = updater.dispatcher
dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("refer", refer))
dp.add_handler(CommandHandler("balance", balance))
dp.add_handler(CommandHandler("upi", set_upi))
dp.add_handler(CommandHandler("withdraw", withdraw))
dp.add_handler(CommandHandler("info", info))
dp.add_handler(CommandHandler("leaderboard", leaderboard))
dp.add_handler(CommandHandler("help", help_cmd))
dp.add_handler(CommandHandler("admin_stats", admin_stats))
dp.add_handler(CommandHandler("approve_withdrawal", approve_withdrawal, pass_args=True))

updater.start_polling()
updater.idle()

