from dotenv import load_dotenv
import os

import pymongo
from sqlalchemy import func


load_dotenv()
from apscheduler.schedulers.background import BackgroundScheduler
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta  # This handles month increments correctly
from dbpg import SessionLocal
from db import my_col, mydb
from models import DebtAccounts, PaymentBoost, UserSettings
from incometransactions import income_transaction_processing
from savingcontributions import saving_contribution_processing
from calenderscheduler import calender_entry
from incomenext import income_boost_next_payment, income_next_payment
from billnext import bill_next_transaction
from savingnext import saving_next_payment
from cashflow import cashflow_update
debt_accounts_log = my_col('debt_accounts_log')
debt_user_setting = my_col('debt_user_setting')

AMORTIZATION_INTERVAL = int(os.getenv("AMORTIZATION_INTERVAL",10))
INCOME_INTERVAL = int(os.getenv("INCOME_INTERVAL",10))
BILL_INTERVAL = int(os.getenv("BILL_INTERVAL",10))
CALENDER_ENTRY_DURATION = int(os.getenv("CALENDER_ENTRY_DURATION",10))
INCOME_ENTRY_DURATION = int(os.getenv("INCOME_ENTRY_DURATION",10))
INCOME_BOOST_ENTRY_DURATION = int(os.getenv("INCOME_BOOST_ENTRY_DURATION",10))
SAVING_ENTRY_DURATION = int(os.getenv("SAVING_ENTRY_DURATION",10))

CASHFLOW_ENTRY_DURATION = int(os.getenv("CASHFLOW_ENTRY_DURATION",10))
'''
def calculate_amortization(balance, interest_rate, monthly_payment, credit_limit, current_date, monthly_budget):
    amortization_schedule = []
    
    # Convert interest rate to decimal
    interest_rate_decimal = interest_rate / 100


    # Set a maximum date limit (50 years from the current date)
    limit_years = current_date + relativedelta(years=50)
    
    while balance > 0 and current_date <= limit_years:
        
        if credit_limit is not None:
            balance = min(balance, credit_limit)
        
        # Calculate interest for the current balance
        interest = balance * interest_rate_decimal / 12
        
        # Calculate the maximum payment we can make this month
        payment = min(monthly_payment, monthly_budget, balance + interest)
        
        # Calculate the snowball amount (portion going to principal after interest)
        snowball_amount = payment - interest
        
        # Calculate principal payment
        principal = min(snowball_amount, balance)
        balance -= principal
        
        if balance < 0:
            balance = 0
        
        # Calculate total payment (principle + interest)
        total_payment = principal + interest
        
        # Record this month's data
        amortization_schedule.append({
            'month': current_date.strftime("%b %Y"),
            'month_debt_free': current_date,
            'balance': round(balance, 2),
            'total_payment': round(total_payment, 2),
            'snowball_amount': round(snowball_amount, 2),
            'interest': round(interest, 2),
            'principle': round(principal, 2)
        })
        
        # Move to the next month using relativedelta to increment by one month
        current_date += relativedelta(months=1)
    
    return amortization_schedule
'''

def calculate_amortization(balance, interest_rate, monthly_payment, credit_limit, current_date, cashflow_amount):
    amortization_schedule = []

    # Convert interest rate to decimal
    interest_rate_decimal = interest_rate / 100
    limit_years = current_date + relativedelta(years=100)
    is_first_month = True

    while balance > 0 and current_date <= limit_years:
        # Cap balance by credit limit
        if credit_limit is not None:
            balance = min(balance, credit_limit)

        # Calculate interest for the month
        interest = balance * interest_rate_decimal / 12

        # Apply cashflow only in the first month
        extra_payment = 0
        if is_first_month:
            extra_payment = min(cashflow_amount, balance)
            extra_payment = min(cashflow_amount, ((balance+ interest) - monthly_payment))
            cashflow_amount -= extra_payment
        payment = monthly_payment + extra_payment

        # Cap payment to total due (avoid overpaying)
        total_due = balance + interest
        if payment > total_due:
            payment = total_due

        # Principal = payment - interest
        principal_payment = max(payment - interest, 0)
        balance = max(balance - principal_payment, 0)

        amortization_schedule.append({
            'month': current_date.strftime("%b %Y"),
            'month_debt_free': current_date,
            'balance': round(balance, 2),
            'total_payment': round(payment, 2),
            'snowball_amount': round(principal_payment, 2),
            'interest': round(interest, 2),
            'principal': round(principal_payment, 2)
        })

        is_first_month = False
        current_date += relativedelta(months=1)

    return amortization_schedule, cashflow_amount

# Define sorting method (for example, Debt Snowball - lowest balance first)
def sort_debts(debts, method):
    if method == 1:  # Debt Snowball - lowest balance first
        return sorted(debts, key=lambda x: x['balance'])
    elif method == 2:  # Debt Avalanche - highest interest rate first
        return sorted(debts, key=lambda x: x['interest_rate'], reverse=True)
    elif method == 11:  # Hybrid (Debt Ratio)
        return sorted(debts, key=lambda x: x['balance'] / (x['interest_rate'] + 1))
    elif method == 13:  # Cash Flow Index (CFI)
        return sorted(debts, key=lambda x: x['balance'] / (x['monthly_payment'] + 1))
    elif method == 3:  # Custom - highest sort number first
        return sorted(debts, key=lambda x: x['balance'], reverse=True)
    elif method == 4:  # Custom - lowest sort number first
        return sorted(debts, key=lambda x: x['balance'])
    elif method == 5:  # Highest monthly payment first
        return sorted(debts, key=lambda x: x['monthly_payment'], reverse=True)
    elif method == 8:  # Highest credit utilization first
        return sorted(debts, key=lambda x: x['balance'] / (x['credit_limit'] + 1), reverse=True)
    elif method == 10:  # Highest monthly interest paid first
        return sorted(debts, key=lambda x: x['monthly_interest'], reverse=True)
    elif method == 12:  # Lowest interest rate paid first
        return sorted(debts, key=lambda x: x['interest_rate'])
    else:
        raise ValueError("Unknown debt payoff method")
    


def dropAndGenerateCollection(document_id:int,schedule):
    collection_name = f"debt_{str(document_id)}"
    schedule_len = len(schedule)
    if schedule_len < 1:
        if collection_name in mydb.list_collection_names():
            mydb.drop_collection(collection_name)
        return None

    if collection_name in mydb.list_collection_names():
        mydb.drop_collection(collection_name)
        print(f"Collection '{collection_name}' dropped.")
    target_collection = my_col(collection_name)
    target_collection.insert_many(schedule)
    pipeline = [
    {
        '$group': {
            '_id': None,
            'total_payment_sum': {'$sum': '$total_payment'},
            'total_interest_sum': {'$sum': '$interest'},
            'max_month_debt_free': {'$max': '$month_debt_free'}
        }
    }
    ]
    # Execute the aggregation
    result = list(target_collection.aggregate(pipeline))
    total_payment_sum = result[0]['total_payment_sum'] if result else 0
    total_interest_sum = result[0]['total_interest_sum'] if result else 0
    max_month_debt_free = result[0]['max_month_debt_free'] if result else None


    return {
        'month_debt_free':max_month_debt_free,
        'total_payment_sum':total_payment_sum,
        'total_interest_sum':total_interest_sum,
        'months_to_payoff':schedule_len
    }





def dropOncaseDelete(document_id):
    collection_name = f"debt_{str(document_id)}"
    if collection_name in mydb.list_collection_names():
        mydb.drop_collection(collection_name)
        print(f"Collection '{collection_name}' dropped.")


def updateDebtFreeMonth(
                        document_id,
                        month_debt_free, 
                        months_to_payoff, 
                        total_payment_sum,
                        total_interest_sum,
                        debt_id):
    ammortization_at = datetime.now()
    source_collection = debt_accounts_log

    with SessionLocal() as session:
        debt_update = session.query(DebtAccounts).filter(DebtAccounts.id == debt_id).update(
                {
                    DebtAccounts.month_debt_free: month_debt_free,
                    DebtAccounts.months_to_payoff:months_to_payoff,
                    DebtAccounts.total_payment_sum:total_payment_sum,
                    DebtAccounts.total_interest_sum:total_interest_sum,
                    DebtAccounts.ammortization_at:ammortization_at
                    #Income.calender_at: None
                }, synchronize_session=False
            )
        if debt_update:
            session.commit()       
            upsert_query = {'_id': document_id}
            update_fields = {'$set': 
                            {'month_debt_free': month_debt_free,
                            'months_to_payoff':months_to_payoff,
                            'total_payment_sum':total_payment_sum,
                            'total_interest_sum':total_interest_sum,
                            #'ammortization_at':ammortization_at
                            }}
            source_collection.update_one(upsert_query, update_fields, upsert=True)


def get_user_debt_update():
    debt_acc_query = {
        "ammortization_at": None,                            
    }

    debt_usersettings = debt_user_setting.find_one(
        debt_acc_query       
    )
    if debt_usersettings:
        return {
            'user_id':debt_usersettings['user_id'],
            'amount':debt_usersettings['user_monthly_budget'],
            'debt_payoff_method':debt_usersettings['debt_payoff_method']['value']
        }
    
    return None




def process_update():

    debt_update = get_user_debt_update()

    if debt_update:
        user_id = debt_update['user_id']
        amount  = debt_update['amount']
        debt_payoff_method = debt_update['debt_payoff_method']
        
        query = {
            'user_id':user_id,
            #'ammortization_at':None
        }
        print('debt user settings', debt_update)
        total_count = debt_accounts_log.count_documents(query)
        print('found debt account', total_count)
                    
        if total_count > 0:
            total_monthly_minimum = 0
            total_payment_boost = 0
            monthly_budget = amount
            cashflow_amount = 0
            with SessionLocal() as session:
                total_monthly_minimum = session.query(
                    func.coalesce(func.sum(DebtAccounts.monthly_payment), 0)
                ).filter(
                    DebtAccounts.user_id == user_id,
                    DebtAccounts.deleted_at.is_(None)                    
                ).scalar()
                current_month_string = datetime.now().strftime('%b %Y')

                total_payment_boost = (
                    session.query(func.coalesce(func.sum(PaymentBoost.amount), 0))
                    .filter(
                        PaymentBoost.month == current_month_string,
                        PaymentBoost.deleted_at.is_(None)
                    )
                    .scalar()
                )

                cashflow_amount = round((monthly_budget - total_monthly_minimum) + total_payment_boost,2)

            initail_date = datetime.now()

            debt_accounts_list  = []            
            
            if debt_payoff_method == 3:
                debt_accounts_list = list(debt_accounts_log.find(query).sort("custom_payoff_order", pymongo.ASCENDING))
            
            if debt_payoff_method == 1:
                debt_accounts_list = list(debt_accounts_log.find(query).sort("balance", pymongo.ASCENDING))

            if debt_payoff_method == 2:
                debt_accounts_list = list(debt_accounts_log.find(query).sort("interest_rate", pymongo.DESCENDING))

            if debt_payoff_method == 8:
                debt_accounts_list = list(debt_accounts_log.aggregate([
                {
                    "$match": query
                },
                {
                    "$addFields": {
                        "balance_to_credit_ratio": {
                            "$divide": [
                                {"$ifNull": ["$balance", 0]},
                                {"$add": [{"$ifNull": ["$credit_limit", 0]}, 1]}
                            ]
                        }
                    }
                },
                {
                    "$sort": {
                        "balance_to_credit_ratio": -1  # Sort descending
                    }
                }
            ]))

            if len(debt_accounts_list) > 0:
                for account in debt_accounts_list:
                    print('account', account)
                    schedule, cashflow_amount = calculate_amortization(
                        balance=account['balance'],
                        interest_rate=account['interest_rate'],
                        monthly_payment=account['monthly_payment'],
                        credit_limit=account['credit_limit'],
                        current_date=initail_date,
                        cashflow_amount=cashflow_amount
                    )
                    if len(schedule) > 0:
                        document_id = account['_id']
                        dept_id = int(account['debt_id'])
                        dynamic_data = dropAndGenerateCollection(dept_id,schedule)
                        month_debt_free = dynamic_data['month_debt_free']
                        months_to_payoff = dynamic_data['months_to_payoff']
                        total_payment_sum = dynamic_data['total_payment_sum']
                        total_interest_sum = dynamic_data['total_interest_sum']
                        if dynamic_data['month_debt_free'] != None:
                            print('month_debt_free:', month_debt_free)
                            updateDebtFreeMonth(
                                                document_id, 
                                                month_debt_free, 
                                                months_to_payoff, 
                                                total_payment_sum,
                                                total_interest_sum,
                                                dept_id
                                                )

                
                debt_user_setting.update_one(query,{
                '$set':{
                    'ammortization_at':datetime.now() 
                } 
                })
    else:
        print('No debt modification found!!')


           

# if __name__ == "__main__":
#     #process_changes()
#     process_update()

def income_and_saving_processing():
    print('INCOME PROCESSING')
    income_transaction_processing()
    time.sleep(1)
    print('SAVING PROCESSING')
    saving_contribution_processing()

def my_job():
    print(f'My job running at:{datetime.now()}')

def load_scheduler():    
    # Initialize scheduler
    scheduler = BackgroundScheduler()
    # Schedule the query execution every 10 seconds
    #scheduler.add_job(process_update, 'interval', seconds=AMORTIZATION_INTERVAL,max_instances=1)
    
    scheduler.add_job(process_update, 'interval', seconds=AMORTIZATION_INTERVAL,max_instances=1)
    scheduler.add_job(income_and_saving_processing, 'interval', seconds=INCOME_INTERVAL,max_instances=1)
    scheduler.add_job(calender_entry, 'interval', minutes=CALENDER_ENTRY_DURATION,max_instances=1)
    
    scheduler.add_job(income_next_payment, 'interval', minutes=INCOME_ENTRY_DURATION, max_instances=1)
    scheduler.add_job(income_boost_next_payment, 'interval', minutes=INCOME_BOOST_ENTRY_DURATION, max_instances=1)
    scheduler.add_job(bill_next_transaction, 'interval', minutes=BILL_INTERVAL, max_instances=1)

    scheduler.add_job(saving_next_payment, 'interval', minutes=SAVING_ENTRY_DURATION, max_instances=1)

    scheduler.add_job(cashflow_update, 'interval', minutes=CASHFLOW_ENTRY_DURATION, max_instances=1)
    ##scheduler.add_job(my_job, 'cron', hour=0, minute=0, second=10, max_instances=1)
    # Start the scheduler
    scheduler.start()
    # Keep the program running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("Scheduler stopped.")


import time_machine

fake_time_str = os.getenv('FAKE_TIME')

if fake_time_str:
    with time_machine.travel(fake_time_str):
        print(f'--with fake time--{datetime.now()}--')
        load_scheduler()

else:
    print(f'--with real time--{datetime.now()}--')
    load_scheduler()