from dotenv import load_dotenv
load_dotenv()

import os
from functools import wraps

# Debug print to check if ADMIN_IDS is being loaded
print("ADMIN_IDS from env:", os.getenv("ADMIN_IDS"))

# Safely handle missing or empty ADMIN_IDS
admin_ids_env = os.getenv("ADMIN_IDS")
if admin_ids_env:
    ADMIN_IDS = [int(uid) for uid in admin_ids_env.split(",")]
else:
    ADMIN_IDS = []
    print("Warning: ADMIN_IDS environment variable is missing or empty.")

def admin_only(func):
    @wraps(func)
    def wrapper(update, context):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            update.message.reply_text("Unauthorized.")
            return
        return func(update, context)
    return wrapper

def get_or_create_user(users, user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        users.insert_one({
            "user_id": user_id,
            "balance": 0,
            "referral_code": str(user_id),
            "referred_by": None,
            "upi_id": None,
            "referrals": [],
            "level": 1
        })
        user = users.find_one({"user_id": user_id})
    return user

def process_referral(users, new_user_id, referral_code):
    if referral_code and referral_code != str(new_user_id):
        referrer = users.find_one({"referral_code": referral_code})
        if referrer:
            users.update_one({"user_id": referrer["user_id"]}, {"$inc": {"balance": 10}})
            users.update_one({"user_id": new_user_id}, {"$set": {"referred_by": referrer["user_id"]}})
            users.update_one({"user_id": referrer["user_id"]}, {"$push": {"referrals": new_user_id}})
            if referrer.get("referred_by"):
                level2 = users.find_one({"user_id": referrer["referred_by"]})
                if level2:
                    users.update_one({"user_id": level2["user_id"]}, {"$inc": {"balance": 5}})

def leaderboard_message(users):
    top_users = users.find().sort("balance", -1).limit(10)
    msg = "🏆 Top Referrers:\n"
    for i, u in enumerate(top_users, 1):
        msg += f"{i}. {u['user_id']} - ₹{u['balance']}\n"
    return msg
