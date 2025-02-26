from dotenv import load_dotenv
import os
load_dotenv()
from apscheduler.schedulers.background import BackgroundScheduler
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta  # This handles month increments correctly
from dbpg import SessionLocal
from db import my_col, mydb
from models import DebtAccounts, UserSettings
from incometransactions import income_transaction_processing

debt_accounts_log = my_col('debt_accounts_log')

AMORTIZATION_INTERVAL = int(os.getenv("AMORTIZATION_INTERVAL",10))
INCOME_INTERVAL = int(os.getenv("INCOME_INTERVAL",10))

def calculate_amortization(balance, interest_rate, monthly_payment, credit_limit, current_date, monthly_budget):
    amortization_schedule = []
    
    # Convert interest rate to decimal
    interest_rate_decimal = interest_rate / 100
    
    while balance > 0:
        balance = min(balance, credit_limit)
        
        # Calculate interest for the current balance
        interest = balance * interest_rate_decimal / 12
        
        # Calculate the maximum payment we can make considering the monthly budget
        payment = min(monthly_payment, monthly_budget)
        
        # Calculate snowball amount
        snowball_amount = min(payment, balance + interest) - interest
        
        # Calculate principal payment
        principle = snowball_amount
        principle = min(principle, balance)
        balance -= principle
        
        if balance < 0:
            balance = 0
        
        # Calculate total payment (principle + interest)
        total_payment = principle + interest
        
        # Record this month's data
        amortization_schedule.append({
            'month': current_date.strftime("%b %Y"),
            'month_debt_free': current_date,
            'balance': round(balance, 2),
            'total_payment': round(total_payment, 2),
            'snowball_amount': round(snowball_amount, 2),
            'interest': round(interest, 2),
            'principle': round(principle, 2)
        })
        
        # Move to the next month using relativedelta to increment by one month
        current_date += relativedelta(months=1)
    
    return amortization_schedule



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
    

def get_dept_amortization_schedule():

    debt_acc_query = {
        "ammortization_at": None,                            
    }

    debtaccounts = debt_accounts_log.find_one(
        debt_acc_query       
        )

    if debtaccounts:
        balance = debtaccounts['balance']
        #highest_balance = debtaccounts['highest_balance']
        monthly_payment = debtaccounts['monthly_payment']
        interest_rate = debtaccounts['interest_rate']
        #monthly_interest = debtaccounts['monthly_interest']
        credit_limit = debtaccounts['credit_limit']
        current_date = debtaccounts['current_date']

        monthly_budget = debtaccounts['user_monthly_budget']
        
    
        debt = {        
            'balance': balance,
            'interest_rate': interest_rate,
            'monthly_payment': monthly_payment,
            'credit_limit': credit_limit,
            'current_date': current_date,
            'monthly_budget': monthly_budget
        }

        schedule = calculate_amortization(
            balance=debt['balance'],
            interest_rate=debt['interest_rate'],
            monthly_payment=debt['monthly_payment'],
            credit_limit=debt['credit_limit'],
            current_date=debt['current_date'],
            monthly_budget=debt['monthly_budget']
        )

            

        return(schedule, debtaccounts)

    
    return ([],None)   



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
                            'ammortization_at':ammortization_at
                            }}
            source_collection.update_one(upsert_query, update_fields, upsert=True)





def process_update():
   
    schedules = get_dept_amortization_schedule()    
    schedule = schedules[0]
    debtaccounts = schedules[1]
    print('debtaccounts',debtaccounts)
    if len(schedule) > 0 and debtaccounts!=None:
        document_id = debtaccounts['_id']
        dept_id = int(debtaccounts['debt_id'])
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

    #print('Schedule', schedule)

# if __name__ == "__main__":
#     #process_changes()
#     process_update()
    
# Initialize scheduler
scheduler = BackgroundScheduler()

# Schedule the query execution every 10 seconds
#scheduler.add_job(process_update, 'interval', seconds=AMORTIZATION_INTERVAL,max_instances=1)

scheduler.add_job(process_update, 'interval', seconds=AMORTIZATION_INTERVAL,max_instances=1)
scheduler.add_job(income_transaction_processing, 'interval', seconds=INCOME_INTERVAL,max_instances=1)

# Start the scheduler
scheduler.start()

# Keep the program running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    scheduler.shutdown()
    print("Scheduler stopped.")