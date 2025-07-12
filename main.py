import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from pymongo import MongoClient
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    referral_code = args[0] if args else None
    get_or_create_user(users, user_id)
    process_referral(users, user_id, referral_code)
    await update.message.reply_text(
        f"Welcome! Your referral link:\nhttps://t.me/{BOT_USERNAME}?start={user_id}"
    )

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"Your referral link:\nhttps://t.me/{BOT_USERNAME}?start={user_id}"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_or_create_user(users, user_id)
    await update.message.reply_text(f"Your balance: ₹{user['balance']}")

async def set_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /upi your_upi_id@bank")
        return
    upi_id = args[0]
    users.update_one({"user_id": user_id}, {"$set": {"upi_id": upi_id}})
    await update.message.reply_text(f"UPI ID set to: {upi_id}")

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_or_create_user(users, user_id)
    if user["balance"] < MIN_WITHDRAW:
        await update.message.reply_text(f"Minimum withdrawal is ₹{MIN_WITHDRAW}.")
        return
    if not user.get("upi_id"):
        await update.message.reply_text("Set your UPI ID first using /upi command.")
        return
    request_withdrawal(users, withdrawals, user_id, user["balance"], user["upi_id"])
    users.update_one({"user_id": user_id}, {"$set": {"balance": 0}})
    await update.message.reply_text(f"Withdrawal request of ₹{user['balance']} submitted for {user['upi_id']}. Await admin approval.")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_or_create_user(users, user_id)
    referred = user.get("referrals", [])
    await update.message.reply_text(
        f"Your balance: ₹{user['balance']}\n"
        f"Your UPI ID: {user.get('upi_id','Not set')}\n"
        f"Referred users: {len(referred)}"
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = leaderboard_message(users)
    await update.message.reply_text(msg)

@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users = users.count_documents({})
    total_balance = sum(u['balance'] for u in users.find())
    pending_withdrawals = withdrawals.count_documents({"status": "pending"})
    await update.message.reply_text(
        f"Total users: {total_users}\n"
        f"Total balance in system: ₹{total_balance}\n"
        f"Pending withdrawals: {pending_withdrawals}"
    )

@admin_only
async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Usage: /approve_withdrawal withdrawal_id")
        return
    withdrawal_id = args[0]
    withdrawal = withdrawals.find_one({"_id": withdrawal_id, "status": "pending"})
    if not withdrawal:
        await update.message.reply_text("No such pending withdrawal.")
        return
    # Integrate with payment gateway API for payout here
    withdrawals.update_one({"_id": withdrawal_id}, {"$set": {"status": "approved"}})
    await update.message.reply_text(f"Withdrawal {withdrawal_id} approved and marked as paid.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
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

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("upi", set_upi))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin_stats", admin_stats))
    app.add_handler(CommandHandler("approve_withdrawal", approve_withdrawal))
    app.run_polling()
