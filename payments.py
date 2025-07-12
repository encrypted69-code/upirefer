def request_withdrawal(users, withdrawals, user_id, amount, upi_id):
    withdrawals.insert_one({
        "user_id": user_id,
        "amount": amount,
        "upi_id": upi_id,
        "status": "pending"
    })

