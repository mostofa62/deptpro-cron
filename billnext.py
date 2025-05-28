import argparse
from datetime import datetime

from sqlalchemy import and_, or_, update
from pgutils import ExtraType
from util import convertDateTostring
from dbpg import SessionLocal
import os
from dateutil.relativedelta import relativedelta
from models import BillAccounts , BillTransactions
from billutil import generate_single_bill
def bill_next_transaction():

    BILL_LIMIT = os.getenv('BILL_LIMIT',10)

    print('--- BILL NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f'--- BILL NEXT PAYMENT STARTED - {current_datetime_now} ---')

    session = SessionLocal()

    try:

        query = (
            session.query(
                BillAccounts.id,
                BillAccounts.user_id,
                BillAccounts.admin_id,
                BillAccounts.next_due_date,
                BillAccounts.default_amount,
                BillAccounts.current_amount,
                BillAccounts.paid_total,               
                BillAccounts.repeat_frequency                
            )
            .filter(
                BillAccounts.next_due_date <= current_datetime_now,
                BillAccounts.deleted_at.is_(None),
                BillAccounts.closed_at.is_(None),
                or_(
                    BillAccounts.repeat_frequency != 0,  # If not 0, don't check single_done
                    and_(
                        BillAccounts.repeat_frequency == 0,
                        BillAccounts.single_done == 0
                    )
                ),
                BillAccounts.auto_update == 1
            ).order_by(BillAccounts.next_due_date)
        )
        print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))
        bill_all = query.limit(BILL_LIMIT).all()
    except Exception as e:
        print("Query failed Income:", e)
        session.close()
        return
    
    op_type = ExtraType[0]['value']
    
    for id, user_id,admin_id, next_due_date, \
    default_amount,current_amount,paid_total,\
    repeat_frequency in bill_all:
        try:
            frequency = repeat_frequency
            pay_date = next_due_date
            amount = default_amount
            #print('FREQUENCY:', frequency)
            if frequency > 0:

                bill_transaction_generate = generate_single_bill(
                    amount,
                    pay_date,
                    frequency,
                    user_id,
                    admin_id,
                    id,
                    op_type,
                    current_amount
                )
                bill_transaction_list = bill_transaction_generate['bill_transaction']
                current_amount = bill_transaction_generate['current_amount']
                next_due_date = bill_transaction_generate['next_pay_date']

                

                bill_transaction = BillTransactions(**bill_transaction_list)
                session.add(bill_transaction)                        
                session.flush()
                bill_trans_id = bill_transaction.id

                stmt_update = update(BillAccounts).where(BillAccounts.id == id).values(
                    current_amount=current_amount,
                    next_due_date=next_due_date,
                    latest_transaction_id = bill_trans_id,
                    updated_at= datetime.now()
                )
                session.execute(stmt_update)
                session.commit()
            
            else:
                today = datetime.now()
                single_done = 0
                #print('SINGLE :', next_due_date, current_datetime_now) 
                if next_due_date <= current_datetime_now:
                    single_done = 1
                    current_amount += amount
                    bill_transaction = BillTransactions(
                        amount=amount,
                        type=op_type,
                        payor=None,
                        note=None,
                        current_amount=current_amount,
                        pay_date = next_due_date,
                        due_date=next_due_date,
                        created_at=today,
                        updated_at=today,
                        user_id=user_id,
                        admin_id=admin_id,
                        bill_acc_id=id,
                        payment_status=0,                        
                        repeat_frequency=frequency                        
                    )
                    session.add(bill_transaction)
                    session.flush()  # Commit to get the transaction ID
                    bill_trans_id = bill_transaction.id                    
                    stmt_update = update(BillAccounts).where(BillAccounts.id == id).values(
                        current_amount=current_amount,
                        next_due_date=next_due_date,
                        latest_transaction_id = bill_trans_id,
                        updated_at= datetime.now(),
                        single_done =single_done 
                    )
                    session.execute(stmt_update)
                    session.commit()
                

        except Exception as ex:
            print(f'Exception while preparing income ID {id}:', ex)
            session.rollback()  # discard partial data for this record
            continue
    if session:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Run functions from command line")
    
    # Define the command-line argument to run the function
    parser.add_argument('function', type=str, help="Name of the function to run")

    # Parse the arguments
    args = parser.parse_args()

    # Check if the specified function is available and run it
    if args.function == 'billnext':
        #income_transaction_processing()
        #income_next_payment()
        bill_next_transaction()
    else:
        print(f"Function {args.function} not recognized!") 

if __name__ == '__main__':
    main()