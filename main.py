import threading
import signal
from datetime import datetime,timedelta
from db import my_col,mydb
from pymongo.errors import PyMongoError

debt_accounts = my_col('debt_accounts')
usersetting = my_col('user_settings')
from bson.objectid import ObjectId


from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta  # This handles month increments correctly

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


# def calculate_amortization(balance, interest_rate, monthly_payment, credit_limit, current_date, monthly_budget):
#     amortization_schedule = []
    
#     # Convert interest rate to decimal
#     interest_rate_decimal = interest_rate / 100
       
    
#     while balance > 0:
#         balance = min(balance, credit_limit)
        
#         # Calculate interest for the current balance
#         interest = balance * interest_rate_decimal / 12
        
#         # Calculate the maximum payment we can make considering the monthly budget
#         payment = min(monthly_payment, monthly_budget)
        
#         # Calculate snowball amount
#         snowball_amount = min(payment, balance + interest) - interest
        
#         # Calculate principal payment
#         principle = snowball_amount
#         principle = min(principle, balance)
#         balance -= principle
        
#         if balance < 0:
#             balance = 0
        
#         # Calculate total payment (principle + interest)
#         total_payment = principle + interest
        
#         # Record this month's data
#         amortization_schedule.append({
#             'month': current_date.strftime("%b %Y"),
#             'month_debt_free':current_date,
#             'balance': round(balance, 2),
#             'total_payment': round(total_payment, 2),
#             'snowball_amount': round(snowball_amount, 2),
#             'interest': round(interest, 2),
#             'principle': round(principle, 2)
#         })
        
#         # Move to the next month
#         current_date += timedelta(days=30)
    
#     return amortization_schedule

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

def get_dept_amortization_schedule(accntid:str):

    debtaccounts = debt_accounts.find_one(
        {"_id":ObjectId(accntid)},
        {
        "_id":0,                
        }        
        )

    balance = debtaccounts['balance']
    #highest_balance = debtaccounts['highest_balance']
    monthly_payment = debtaccounts['monthly_payment']
    interest_rate = debtaccounts['interest_rate']
    #monthly_interest = debtaccounts['monthly_interest']
    credit_limit = debtaccounts['credit_limit']
    current_date = debtaccounts['due_date']
    #print(interest_rate)

    user_setting = usersetting.find_one({'user_id':debtaccounts['user_id']},{'debt_payoff_method':1,'monthly_budget':1})
    monthly_budget = user_setting['monthly_budget']
    


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

    # Add amortization schedule to debt dictionary
    '''
    debt['amortization_schedule'] = schedule

    # List of debts (single debt in this case)
    debts = [debt]

    debt_payoff_method = user_setting['debt_payoff_method']['value']
    sorted_debts = sort_debts(debts, debt_payoff_method)

    return jsonify({
        'rows':sorted_debts[0]['amortization_schedule']
    })
    '''
    return schedule

def dropAndGenerateCollection(document_id):
    schedule = get_dept_amortization_schedule(str(document_id))
    collection_name = f"debt_{str(document_id)}"
    schedule_len = len(schedule)
    if schedule_len < 1:
        if collection_name in mydb.list_collection_names():
            mydb.drop_collection(collection_name)
        return None
    # Drop the collection if it exists
    #clean first
    if collection_name in mydb.list_collection_names():
        mydb.drop_collection(collection_name)
        print(f"Collection '{collection_name}' dropped.")
    target_collection = my_col(collection_name)
    target_collection.insert_many(schedule)
    latest_target_collection = target_collection.find_one({},{'month_debt_free':1},sort=[('month_debt_free', -1)])
    month_debt_free = latest_target_collection['month_debt_free']
    return month_debt_free


def dropOncaseDelete(document_id):
    collection_name = f"debt_{str(document_id)}"
    if collection_name in mydb.list_collection_names():
        mydb.drop_collection(collection_name)
        print(f"Collection '{collection_name}' dropped.")

def has_common_element(arr1, arr2):
    return any(elem in arr2 for elem in arr1)

def updateDebtFreeMonth(source_collection,document_id,month_debt_free):
    upsert_query = {'_id': document_id}
    update_fields = {'$set': {'month_debt_free': month_debt_free}}
    source_collection.update_one(upsert_query, update_fields, upsert=True)

def process_changes():
#def process_changes(stop_event):
    try:
        
        source_collection = debt_accounts
        
        
        
       # Define the pipeline to listen for insert, update, and delete operations
        pipeline = [
            {'$match': {'operationType': {'$in': ['insert', 'update', 'delete']}}}
        ]
        
        with source_collection.watch(pipeline=pipeline) as stream:
            for change in stream:
                operation_type = change['operationType']
                full_document = change.get('fullDocument', {})
                document_key = change['documentKey']
                document_id = document_key['_id']
                
                # Check if the 'balance' field is present in the change event
                if operation_type == 'update':
                    updated_fields = change['updateDescription']['updatedFields']
                    fields = ['balance','interest_rate','minimum_payment','highest_balance','monthly_payment','due_date','credit_limit']
                    if has_common_element(fields,updated_fields):
                        #print(f"Update operation: Balance changed to {updated_fields['balance']}")
                        print('updated field: ',updated_fields)
                        month_debt_free = dropAndGenerateCollection(document_id)
                        if month_debt_free != None:
                            print('month_debt_free:', month_debt_free)
                            updateDebtFreeMonth(source_collection, document_id, month_debt_free)
                    if 'deleted_at' in updated_fields:
                        dropOncaseDelete(document_id)
                
                elif operation_type == 'insert':
                    if 'balance' in full_document:
                        print(f"Insert operation: New balance is {full_document['balance']}")
                        month_debt_free = dropAndGenerateCollection(document_id)
                        print('month_debt_free:', month_debt_free)
                        updateDebtFreeMonth(source_collection, document_id, month_debt_free)
                
                elif operation_type == 'delete':
                    dropOncaseDelete(document_id)
                    print(f"Delete operation: Document deleted with key {document_key}")
                    # target_collection.delete_one({'_id': document_key['_id']})

    except PyMongoError as e:
        print(f"An error occurred: {e}")
'''
def start_thread(stop_event):
    change_thread = threading.Thread(target=process_changes, args=(stop_event,))
    change_thread.start()
    return change_thread

def signal_handler(signum, frame):
    print("Signal received, shutting down...")
    stop_event.set()
'''
if __name__ == "__main__":
    process_changes()
    '''
    stop_event = threading.Event()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # Handle termination signals
    
    thread = start_thread(stop_event)
    
    try:
        thread.join()
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        print("Shutting down")
    '''
