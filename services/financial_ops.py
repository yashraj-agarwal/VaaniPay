import json
from mock_db import db_lock, load_json, save_json, USERS_FILE, ACCOUNTS_FILE, TRANSACTIONS_FILE

async def calculate_behavioral_score(user_phone):
    async with db_lock:
        users = await load_json(USERS_FILE)
        accounts = await load_json(ACCOUNTS_FILE)
        transactions = await load_json(TRANSACTIONS_FILE)
        
        user = users.get(user_phone)
        if not user: return 300, ["No data"]
        
        acc_id = user.get('account_id')
        txns = transactions.get(acc_id, [])
        acc = accounts.get(acc_id, {})
        
        # Base score
        score = 300
        factors = []
        
        # 1. Platform Usage (Transaction Volume)
        if len(txns) > 5:
            score += 150
            factors.append("High transaction volume")
        elif len(txns) > 0:
            score += 50
            factors.append("Active transaction history")
            
        # 2. Savings Consistency
        savings_bal = acc.get('balance', 0)
        if savings_bal > 10000:
            score += 200
            factors.append("Strong savings balance")
        elif savings_bal > 2000:
            score += 100
            factors.append("Moderate savings balance")
            
        # 3. Timely repayment & PF (Mocked signals)
        pf_bal = acc.get('pf', 0)
        if pf_bal > 0:
            score += 150
            factors.append("Formal employment & PF contribution")
            
        # Cap score
        score = min(score, 900)
        
        return score, factors

async def perform_upi_transaction(user_phone, amount):
    amount = float(amount)
    
    async with db_lock:
        users = await load_json(USERS_FILE)
        accounts = await load_json(ACCOUNTS_FILE)
        txns = await load_json(TRANSACTIONS_FILE)
        
        user = users.get(user_phone)
        acc_id = user.get('account_id')
        
        if accounts[acc_id]['balance'] >= amount:
            accounts[acc_id]['balance'] -= amount
            
            # Initialize the transaction list if it doesn't exist yet
            if acc_id not in txns:
                txns[acc_id] = []
                
            txns[acc_id].append({"type": "debit", "amount": amount, "desc": "UPI Payment"})
            
            await save_json(ACCOUNTS_FILE, accounts)
            await save_json(TRANSACTIONS_FILE, txns)
            return True, accounts[acc_id]['balance']
        return False, accounts[acc_id]['balance']
