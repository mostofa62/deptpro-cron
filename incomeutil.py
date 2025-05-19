import calendar
from datetime import date, datetime,timedelta
from itertools import groupby
from operator import itemgetter

from bson import ObjectId

import hashlib
from dateutil.relativedelta import relativedelta

def get_delta(frequency):
    if frequency == 1:
        delta = relativedelta(days=1)
    elif frequency == 7:
        delta = relativedelta(weeks=1)
    elif frequency == 14:
        delta = relativedelta(weeks=2)
    elif frequency == 30:
        delta = relativedelta(months=1)
    elif frequency == 90:
        delta = relativedelta(months=3)
    elif frequency == 365:
        delta = relativedelta(years=1)
    else:
        return {'error': 'Invalid contribution frequency'}, 400
    
    return delta


#this below 2 function will generate the amonunt based on frequency
def calcuate_frequncey_wise_income(input, frequency):
    normalized_income = input * (30 / frequency)
    return normalized_income

def calculate_periods(start_date,frequency=None, end_date=None):
    if end_date is None:
        end_date = datetime.now()

    if start_date > end_date:
        return 0  # If start date is in the future, return 0 periods

    delta_days = (end_date - start_date).days

    if frequency in [1, 7, 14]:  # Daily, Weekly, Bi-weekly
        return delta_days // frequency

    elif frequency == 30:  # Monthly Frequency
        delta_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        return max(0, delta_months)  # Ensure non-negative

    elif frequency == 90:  # Quarterly (Every 3 months)
        delta_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        return max(0, delta_months // 3)

    elif frequency == 365:  # Yearly Frequency
        delta_years = end_date.year - start_date.year
        return max(0, delta_years)

    return 0  # If frequency is not recognized
#here for each
## if we have fraction for daily-7, biweekly-14 then delete due day amount


#now we need to get next_pay_date based on pay_date and frequnecy
### we dont need day ,week , biweek becuase we all goes to month
## for single entry
def calculate_next_payment(pay_date, repeat_value):
    if repeat_value == 30:  # Monthly
        next_payment = pay_date.replace(month=pay_date.month % 12 + 1) if pay_date.month != 12 else pay_date.replace(year=pay_date.year + 1, month=1)
    elif repeat_value == 90:  # Quarterly
        next_payment = pay_date.replace(month=pay_date.month + 3 if pay_date.month <= 9 else pay_date.month - 9, year=pay_date.year if pay_date.month <= 9 else pay_date.year + 1)
    elif repeat_value == 365:  # Annually
        try:
            next_payment = pay_date.replace(year=pay_date.year + 1)
        except ValueError:
            # Handle leap year case for February 29
            if pay_date.month == 2 and pay_date.day == 29:
                next_payment = pay_date.replace(year=pay_date.year + 1, day=28)
            else:
                raise
    else:
        next_payment = None  # For unsupported repeat values
    return next_payment


# Function to calculate the next payment date based on frequency
def move_next_time(current_date, frequency, repeat_count=1):
    if frequency == 30:
        month = current_date.month - 1 + repeat_count
        year = current_date.year + month // 12
        month = month % 12 + 1
        day = min(current_date.day, calendar.monthrange(year, month)[1])        
        return current_date.replace(year=year, month=month, day=day)
    elif frequency == 90:
        return move_next_time(current_date, 30, 3 * repeat_count)
    elif frequency == 365:
        return current_date.replace(year=current_date.year + repeat_count)
    elif frequency <= 14:
        # Move by 28 days for weekly frequency
        new_date = current_date + timedelta(days=28)  # 4 weeks
        return new_date
    """ elif frequency == 14:
        return current_date + timedelta(weeks=2 * repeat_count) """


def calculate_prorated_income(pay_date, input, frequency):
    # Get the last day of the current month
    last_day_of_month = calendar.monthrange(pay_date.year, pay_date.month)[1]    
    # Calculate the number of days left in the month after the pay date
    days_remaining_in_month = last_day_of_month - pay_date.day + 1    
    # Calculate daily income rate based on the gross input and frequency

    if frequency in [7,14]:
        if days_remaining_in_month > 7 and days_remaining_in_month < 14:
                days_remaining_in_month = 7
                
        if days_remaining_in_month > 14 and days_remaining_in_month < 21:
                days_remaining_in_month = 14
                
        if days_remaining_in_month > 21 and days_remaining_in_month < 28:
                days_remaining_in_month = 21
            
        if days_remaining_in_month > 28:
            days_remaining_in_month = 28


    daily_rate = input / frequency    
    # Calculate the prorated gross income for the remaining days in the month
    prorated_income = daily_rate * days_remaining_in_month    
    return prorated_income



def get_single_boost(initial_amount, 
                     contribution, 
                     start_date,
                     frequency, 
                     initial_gross_input,
                     initial_net_input,                   
                     ):
  
    balance = initial_amount
    total_gross_for_period = initial_gross_input
    total_net_for_period = initial_net_input

    total_monthly_gross_income = 0
    total_monthly_net_income = 0
    total_yearly_gross_income = 0
    total_yearly_net_income = 0

    
    
    next_pay_date =  None
    current_date = start_date
    if frequency!=None:
        delta = get_delta(frequency)
        next_pay_date = current_date + delta

    balance += contribution

    balance = round(balance,2)

    total_gross_for_period +=  contribution
    total_net_for_period += contribution


    total_gross_for_period = round(total_gross_for_period,2)
    total_net_for_period = round(total_net_for_period,2)

    current_datetime_now = datetime.now()

    # month = current_date.strftime("%Y-%m")
    # month_word = current_date.strftime("%b, %Y")
    
    month = int(current_date.strftime("%Y%m"))
    income_transaction = {                
                #'month_word':month_word,
                'month':month,
                'pay_date':current_date,
                "next_pay_date":next_pay_date,
                'gross_income':contribution,
                'net_income':contribution,   
                "total_gross_for_period": total_gross_for_period,
                'total_net_for_period':total_net_for_period,
                # "deleted_at":None,
                # "closed_at":None            
                      
    }

    if month == int(current_datetime_now.strftime('%Y%m')):
        total_monthly_gross_income += contribution
        total_monthly_net_income += contribution

    if int(month/100) == current_datetime_now.year:
        total_yearly_gross_income += contribution
        total_yearly_net_income += contribution
    

    return ({
               
        
        'income_transaction':income_transaction,
        'total_gross_for_period':total_gross_for_period,
        'total_net_for_period':total_net_for_period,
        'next_pay_date':next_pay_date,
        'total_boost_for_period': balance,
        'total_monthly_gross_income':total_monthly_gross_income,
        'total_monthly_net_income':total_monthly_net_income,
        'total_yearly_gross_income':total_yearly_gross_income,
        'total_yearly_net_income':total_yearly_net_income,         
    })



def get_single_income(
        initial_gross_input,
        initial_net_input,
        gross_input,
        net_input,
        pay_date,
        frequency,
        commit,
        income_id,
        user_id              
):
    
    delta = get_delta(frequency)    
    current_date = pay_date
    
    

    next_pay_date = current_date + delta    
    
    
    total_gross_for_period = initial_gross_input
    total_net_for_period = initial_net_input

    total_gross_for_period +=  gross_input
    total_net_for_period += net_input

    total_gross_for_period = round(total_gross_for_period,2)
    total_net_for_period = round(total_net_for_period,2)

    total_monthly_gross_income= 0
    total_monthly_net_income = 0
    total_yearly_gross_income = 0
    total_yearly_net_income = 0 

    

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    month = int(current_date.strftime("%Y%m"))
    income_transaction = {                
                #'month_word':month_word,
                'month':month,
                'pay_date':current_date,
                "next_pay_date":next_pay_date,
                'gross_income':gross_input,
                'net_income':net_input,   
                "total_gross_for_period": total_gross_for_period,
                'total_net_for_period':total_net_for_period,
                "income_id":income_id,
                "income_boost_id":None,
                'user_id':user_id,
                'commit':commit,          
                      
    }

    if month == int(current_datetime_now.strftime('%Y%m')):
        total_monthly_gross_income += gross_input
        total_monthly_net_income += net_input

    if int(month/100) == current_datetime_now.year:
        total_yearly_gross_income += gross_input
        total_yearly_net_income += net_input


    
    return ({
        'income_transaction':income_transaction,
        'total_gross_for_period':total_gross_for_period,
        'total_net_for_period':total_net_for_period,
        'next_pay_date':next_pay_date,
        'total_monthly_gross_income':total_monthly_gross_income,
        'total_monthly_net_income':total_monthly_net_income,
        'total_yearly_gross_income':total_yearly_gross_income,
        'total_yearly_net_income':total_yearly_net_income, 
    })

    

def generate_new_transaction_data_for_income(
        gross_input,
        net_input,
        pay_date,
        frequency,
        commit,
        income_id,
        user_id

):
    
    delta = get_delta(frequency)
    
    income_transaction = []
    
    current_date = pay_date    
    
   

    total_gross_for_period = 0
    total_net_for_period = 0
    total_monthly_gross_income = 0
    total_monthly_net_income = 0
    total_yearly_gross_income = 0
    total_yearly_net_income = 0


    
    next_pay_date = current_date + delta

    current_datetime_now = datetime.now()
    is_single = 0

    if current_datetime_now <= next_pay_date:
        
        is_single = 1
        total_gross_for_period +=  gross_input
        total_net_for_period += net_input                        

        total_gross_for_period = round(total_gross_for_period,3)
        total_net_for_period = round(total_net_for_period,3)
       

        #month = current_date.strftime("%Y-%m")
        #month_word = current_date.strftime("%b, %Y")
        month = int(current_date.strftime("%Y%m"))
        income_transaction = {
                #'month_word':month_word,
                'month':month,
                #'month_number':month_number,
                'pay_date':current_date,
                "next_pay_date":next_pay_date,
                'gross_income':gross_input,                
                'net_income':net_input,                         
                "total_gross_for_period": total_gross_for_period,
                'total_net_for_period':total_net_for_period,           
                "income_id":income_id,
                "income_boost_id":None,
                'user_id':user_id,
                'commit':commit,
                # "deleted_at":None,
                # "closed_at":None            
                
            }
        
        if month == int(current_datetime_now.strftime('%Y%m')):
            total_monthly_gross_income += gross_input
            total_monthly_net_income += net_input

        if int(month/100) == current_datetime_now.year:
            total_yearly_gross_income += gross_input
            total_yearly_net_income += net_input  
        
        return ({
            'income_transaction':income_transaction,
            'total_gross_for_period':total_gross_for_period,
            'total_net_for_period':total_net_for_period,
            'total_monthly_gross_income':total_monthly_gross_income,
            'total_monthly_net_income':total_monthly_net_income,
            'total_yearly_gross_income':total_yearly_gross_income,
            'total_yearly_net_income':total_yearly_net_income,         
            'next_pay_date':next_pay_date,
            'is_single':is_single
        })

    

    if next_pay_date <= current_datetime_now:
        is_single = 0
        while next_pay_date <= current_datetime_now:

            total_gross_for_period +=  gross_input
            total_net_for_period += net_input                        

            total_gross_for_period = round(total_gross_for_period,3)
            total_net_for_period = round(total_net_for_period,3)

           

            
            next_pay_date = current_date + delta

            #month = current_date.strftime("%Y-%m")
            #month_word = current_date.strftime("%b, %Y")
            month = int(current_date.strftime("%Y%m"))


            income_transaction.append({
                #'month_word':month_word,
                'month':month,
                #'month_number':month_number,
                'pay_date':current_date,
                "next_pay_date":next_pay_date,
                'gross_income':gross_input,                
                'net_income':net_input,                         
                "total_gross_for_period": total_gross_for_period,
                'total_net_for_period':total_net_for_period,           
                "income_id":income_id,
                "income_boost_id":None,
                'user_id':user_id,
                'commit':commit,
                # "deleted_at":None,
                # "closed_at":None            
                
            })

            if month == int(current_datetime_now.strftime('%Y%m')):
                total_monthly_gross_income += gross_input
                total_monthly_net_income += net_input


            if int(month/100) == current_datetime_now.year:
                total_yearly_gross_income += gross_input
                total_yearly_net_income += net_input  

            # Move to the next period based on base income frequency
            current_date = next_pay_date
        
        return ({
            'income_transaction':income_transaction,
            'total_gross_for_period':total_gross_for_period,
            'total_net_for_period':total_net_for_period,
            'total_monthly_gross_income':total_monthly_gross_income,
            'total_monthly_net_income':total_monthly_net_income,
            'total_yearly_gross_income':total_yearly_gross_income,
            'total_yearly_net_income':total_yearly_net_income,         
            'next_pay_date':next_pay_date,
            'is_single':is_single
        })


   
        




def generate_new_transaction_data_for_income_boost(
        initial_amount,
        contribution,
        start_date,
        frequency,
        commit,
        income_id,
        income_boost_id,
        user_id,
        initial_gross_input,
        initial_net_input        

):

    delta = get_delta(frequency)
    
    income_transaction = []

    current_date = start_date
    
    balance = initial_amount
    total_gross_for_period = initial_gross_input
    total_net_for_period = initial_net_input

    total_monthly_gross_income = 0
    total_monthly_net_income = 0
    total_yearly_gross_income = 0
    total_yearly_net_income = 0

    next_pay_date = current_date + delta

    current_datetime_now = datetime.now()
    is_single = 0

    if current_datetime_now <= next_pay_date:
        
        is_single = 1
        balance += contribution
        balance = round(balance,2)

        total_gross_for_period +=  contribution
        total_net_for_period += contribution


        total_gross_for_period = round(total_gross_for_period,2)
        total_net_for_period = round(total_net_for_period,2)
       

        #month = current_date.strftime("%Y-%m")
        #month_word = current_date.strftime("%b, %Y")
        month = int(current_date.strftime("%Y%m"))
        income_transaction = {
                #'month_word':month_word,
                'month':month,
                'pay_date':current_date,
                "next_pay_date":next_pay_date,
                'gross_income':contribution,                
                'net_income':contribution,                         
                "total_gross_for_period": total_gross_for_period,
                'total_net_for_period':total_net_for_period,           
                "income_id":income_id,
                "income_boost_id":income_boost_id,
                'user_id':user_id,
                'commit':commit,
                #"deleted_at":None,
                #"closed_at":None            
                
            }
        
        if month == int(current_datetime_now.strftime('%Y%m')):
            total_monthly_gross_income += contribution
            total_monthly_net_income += contribution

        if int(month/100) == current_datetime_now.year:
            total_yearly_gross_income += contribution
            total_yearly_net_income += contribution 
        
        return ({                       
            'income_transaction':income_transaction,
            'total_gross_for_period':total_gross_for_period,
            'total_net_for_period':total_net_for_period,
            'next_pay_date':next_pay_date,
            'total_boost_for_period': balance,
            'is_single':is_single,
            'total_monthly_gross_income':total_monthly_gross_income,
            'total_monthly_net_income':total_monthly_net_income,
            'total_yearly_gross_income':total_yearly_gross_income,
            'total_yearly_net_income':total_yearly_net_income,       
        })


    

    if next_pay_date <= current_datetime_now:
        is_single = 0
        while next_pay_date <= current_datetime_now:

            balance += contribution
            balance = round(balance,2)

            total_gross_for_period +=  contribution
            total_net_for_period += contribution


            total_gross_for_period = round(total_gross_for_period,2)
            total_net_for_period = round(total_net_for_period,2)

            

            next_pay_date = current_date + delta

            # month = current_date.strftime("%Y-%m")
            # month_word = current_date.strftime("%b, %Y")
            
            month = int(current_date.strftime("%Y%m"))

            income_transaction.append({
                #'month_word':month_word,
                'month':month,
                'pay_date':current_date,
                "next_pay_date":next_pay_date,
                'gross_income':contribution,                
                'net_income':contribution,                         
                "total_gross_for_period": total_gross_for_period,
                'total_net_for_period':total_net_for_period,           
                "income_id":income_id,
                "income_boost_id":income_boost_id,
                'user_id':user_id,
                'commit':commit,
                #"deleted_at":None,
                #"closed_at":None            
                
            })

            if month == int(current_datetime_now.strftime('%Y%m')):
                total_monthly_gross_income += contribution
                total_monthly_net_income += contribution

            if int(month/100) == current_datetime_now.year:
                total_yearly_gross_income += contribution
                total_yearly_net_income += contribution

             # Move to the next period based on base income frequency
            current_date = next_pay_date

        return ({                       
            'income_transaction':income_transaction,
            'total_gross_for_period':total_gross_for_period,
            'total_net_for_period':total_net_for_period,
            'next_pay_date':next_pay_date,
            'total_boost_for_period': balance,
            'is_single':is_single,
            'total_monthly_gross_income':total_monthly_gross_income,
            'total_monthly_net_income':total_monthly_net_income,
            'total_yearly_gross_income':total_yearly_gross_income,
            'total_yearly_net_income':total_yearly_net_income,       
        })
   
        





def generate_new_transaction_data_for_future_income_boost(
        input_boost,
        pay_date,
        frequency               
):
    
    income_transaction = []

    current_date = pay_date
    first_pay_date = current_date
    today = datetime.now() + timedelta(days=365)
    
    #print(current_date, today)

    total_input_boost_for_period = 0
   

    next_pay_date_boost = None

    while current_date <= today:

        base_input_boost = input_boost
        
        if frequency < 90:
            
            if frequency < 30 and current_date == first_pay_date:
                base_input_boost = calculate_prorated_income(first_pay_date, input_boost, frequency)
                
            else:
                base_input_boost = calcuate_frequncey_wise_income(input_boost, frequency)
                


        base_input_boost = round(input_boost,2)
        

        total_input_boost_for_period += base_input_boost
        
        
        next_pay_date_boost = move_next_time(current_date, frequency)

        total_input_boost_for_period = round(total_input_boost_for_period,2)
        
        
        
        income_transaction.append({
            'month_word':current_date.strftime("%b, %Y"),
            'month':current_date.strftime("%Y-%m"),
            'base_input_boost':base_input_boost,        
            "total_input_boost_for_period": total_input_boost_for_period                            
            
        })

        # Move to the next period based on base income frequency
        current_date = next_pay_date_boost


        
   
        

    return ({
        'income_transaction':income_transaction,
        'total_input_boost_for_period':total_input_boost_for_period,
        'next_pay_date_boost':next_pay_date_boost
    })




def calculate_total_income_for_sepecific_month(data, target_month, key='base_net_income',keyg='base_gross_income'):
    # Sum gross_income and net_income for documents where the month matches target_month    
    total_monthly_gross_income = sum(doc[keyg] for doc in data if doc["month"] == target_month)
    total_monthly_net_income = sum(doc[key] for doc in data if doc["month"] == target_month)
    return total_monthly_net_income,total_monthly_gross_income

