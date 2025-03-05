
from datetime import datetime
import time


from util import convertDateTostring



from models import BillAccounts, DebtAccounts, Income, Saving
from dbpg import SessionLocal
from db import my_col
calender_data = my_col('calender_data')
from pymongo import UpdateOne
from sqlalchemy.exc import SQLAlchemyError

def bill_to_calendar():
    session = None
    try:
        session = SessionLocal()

        # Querying the bill accounts that do not have a calendar entry
        bill_list = session.query(BillAccounts.id,
            BillAccounts.next_due_date,
            BillAccounts.name,
            BillAccounts.user_id,
            BillAccounts.calender_at                      
        ).filter(BillAccounts.calender_at == None).limit(5).all()

        if not bill_list:
            return  # No records to process

        calendar_data_list = []
        bill_id_list = []
        

        for todo in bill_list:
            bill_id_list.append(todo.id)
            entry = {
                'module_name': 'Bill',
                'module_id': 'bill',
                'month': convertDateTostring(todo.next_due_date, '%Y-%m'),
                'month_word': convertDateTostring(todo.next_due_date),
                'event_date': convertDateTostring(todo.next_due_date, '%Y-%m-%d'),
                'data': {
                    'name': todo.name,
                    'description': 'Next Due Date',
                    'data_id': todo.id
                },                
                'user_id': todo.user_id
            }
            calendar_data_list.append(

                UpdateOne(
                    {'module_id': 'bill', 'data.data_id': todo.id},  # Matching condition
                    {'$set': entry},  # Updating the existing or inserting a new document
                    upsert=True
                )
                
            )

        if calendar_data_list and bill_id_list:
            # Inserting the calendar data entries
            c_d = calender_data.bulk_write(calendar_data_list)

            if c_d.upserted_count > 0 or c_d.modified_count > 0:
                # Updating the bill accounts with calendar_at timestamp
                session.query(BillAccounts).filter(BillAccounts.id.in_(bill_id_list)).update(
                    {BillAccounts.calender_at: datetime.now()}, synchronize_session=False
                )
                session.commit()

    except SQLAlchemyError as e:
        if session:
            session.rollback()
        print(f"Database error: {e}")  # Replace with proper logging
    except Exception as e:
        print(f"Unexpected error: {e}")  # Replace with proper logging
    finally:
        if session:
            session.close()




def debt_to_calendar():
    session = None
    try:
        session = SessionLocal()

        # Querying the debt accounts that do not have a calendar entry and have a 'month_debt_free'
        debt_list = session.query(
            DebtAccounts.id,
            DebtAccounts.user_id,
            DebtAccounts.month_debt_free,
            DebtAccounts.name,
            DebtAccounts.calender_at
        ).filter(DebtAccounts.calender_at == None).limit(5).all()

        if not debt_list:
            return  # No records to process

        calendar_data_list = []
        debt_id_list = []

        for todo in debt_list:
            if todo.month_debt_free is None:
                continue
            debt_id_list.append(todo.id)

            entry = {
                'module_name': 'Debt',
                'module_id': 'debt',
                'month': convertDateTostring(todo.month_debt_free, '%Y-%m'),
                'month_word': convertDateTostring(todo.month_debt_free),
                'event_date': convertDateTostring(todo.month_debt_free, '%Y-%m-%d'),
                'data': {
                    'name': todo.name,
                    'description': 'Month Debt Free',
                    'data_id': todo.id
                },
                'user_id': todo.user_id
            }
            calendar_data_list.append(

                UpdateOne(
                    {'module_id': 'debt', 'data.data_id': todo.id},  # Matching condition
                    {'$set': entry},  # Updating the existing or inserting a new document
                    upsert=True
                )
                
            )

        if calendar_data_list and debt_id_list:
            # Inserting the calendar data entries
            c_d = calender_data.bulk_write(calendar_data_list)

            if c_d.upserted_count > 0 or c_d.modified_count > 0:
                # Updating the debt accounts with calendar_at timestamp
                session.query(DebtAccounts).filter(DebtAccounts.id.in_(debt_id_list)).update(
                    {DebtAccounts.calender_at: datetime.now()}, synchronize_session=False
                )
                session.commit()

    except SQLAlchemyError as e:
        if session:
            session.rollback()
        print(f"Database error: {e}")  # Replace with proper logging
    except Exception as e:
        print(f"Unexpected error: {e}")  # Replace with proper logging
    finally:
        if session:
            session.close()


def income_to_calendar():
    session = None
    try:
        session = SessionLocal()

        # Querying the income accounts that do not have a calendar entry
        income_list = session.query(
            Income.id,
            Income.earner,
            Income.next_pay_date,
            Income.user_id,
            Income.calender_at
            
        ).filter(Income.calender_at == None).limit(5).all()

        if not income_list:
            return  # No records to process

        calendar_data_list = []
        income_id_list = []

        for todo in income_list:
            if todo.next_pay_date is None:
                continue
            income_id_list.append(todo.id)

            entry = {
                'module_name': 'Income',
                'module_id': 'income',
                'month': convertDateTostring(todo.next_pay_date, '%Y-%m'),
                'month_word': convertDateTostring(todo.next_pay_date),
                'event_date': convertDateTostring(todo.next_pay_date, '%Y-%m-%d'),
                'data': {
                    'name': todo.earner,
                    'description': 'Next Pay Date',
                    'data_id': todo.id
                },
                'user_id': todo.user_id
            }
            
            calendar_data_list.append(

                UpdateOne(
                    {'module_id': 'income', 'data.data_id': todo.id},  # Matching condition
                    {'$set': entry},  # Updating the existing or inserting a new document
                    upsert=True
                )
                
            )

        if calendar_data_list and income_id_list:
            # Inserting the calendar data entries
            c_d = calender_data.bulk_write(calendar_data_list)

            if c_d.upserted_count > 0 or c_d.modified_count > 0:
                # Updating the income accounts with calendar_at timestamp
                session.query(Income).filter(Income.id.in_(income_id_list)).update(
                    {Income.calender_at: datetime.now()}, synchronize_session=False
                )
                session.commit()

    except SQLAlchemyError as e:
        if session:
            session.rollback()
        print(f"Database error: {e}")  # Replace with proper logging
    except Exception as e:
        print(f"Unexpected error: {e}")  # Replace with proper logging
    finally:
        if session:
            session.close()



def saving_to_calendar():
    session = None
    try:
        session = SessionLocal()

        # Querying the saving accounts that do not have a calendar entry
        saving_list = session.query(
            Saving.id,
            Saving.next_contribution_date,
            Saving.saver,
            Saving.user_id,
            Saving.calender_at
        ).filter(Saving.calender_at == None).limit(5).all()

        if not saving_list:
            return  # No records to process

        calendar_data_list = []
        saving_id_list = []

        for todo in saving_list:
            if todo.next_contribution_date is None:
                continue
            saving_id_list.append(todo.id)

            entry = {
                'module_name': 'Saving',
                'module_id': 'saving',
                'month': convertDateTostring(todo.next_contribution_date, '%Y-%m'),
                'month_word': convertDateTostring(todo.next_contribution_date),
                'event_date': convertDateTostring(todo.next_contribution_date, '%Y-%m-%d'),
                'data': {
                    'name': todo.saver,
                    'description': 'Next Pay Date',
                    'data_id': todo.id
                },
                'user_id': todo.user_id
            }

            calendar_data_list.append(

                UpdateOne(
                    {'module_id': 'saving', 'data.data_id': todo.id},  # Matching condition
                    {'$set': entry},  # Updating the existing or inserting a new document
                    upsert=True
                )
                
            )

        if calendar_data_list and saving_id_list:
            # Inserting the calendar data entries
            c_d = calender_data.bulk_write(calendar_data_list)

            if c_d.upserted_count > 0 or c_d.modified_count > 0:
                # Updating the saving accounts with calendar_at timestamp
                session.query(Saving).filter(Saving.id.in_(saving_id_list)).update(
                    {Saving.calender_at: datetime.now()}, synchronize_session=False
                )
                session.commit()

    except SQLAlchemyError as e:
        if session:
            session.rollback()
        print(f"Database error: {e}")  # Replace with proper logging
    except Exception as e:
        print(f"Unexpected error: {e}")  # Replace with proper logging
    finally:
        if session:
            session.close()


def calender_entry():   
    print('CALENER ENTRY RUNNING', datetime.now())
    bill_to_calendar()
    time.sleep(1)
    debt_to_calendar()
    time.sleep(1)
    income_to_calendar()
    time.sleep(1)
    saving_to_calendar()




