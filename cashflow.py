from datetime import datetime
import os
from sqlalchemy import Integer, and_, cast, extract, func, or_, select, update
from util import convertDateTostring
from models import AppData, BillAccounts, BillPayments, BillTransactions, CashFlow, PaymentBoost, UserSettings
from dbpg import SessionLocal

def cashflow_update():
    CASHFLOW_LIMIT = os.getenv('CASHFLOW_LIMIT',10)

    print('--- CASHFLOW NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f'--- CASHFLOW NEXT PAYMENT STARTED - {current_datetime_now} ---')

    session = SessionLocal()

    target_year = current_datetime_now.year
    target_month = current_datetime_now.month
    current_month = int(convertDateTostring(current_datetime_now,'%Y%m'))
    try:

        query = (
            session.query(
                CashFlow.id,
                CashFlow.user_id
            )
            .filter(
                CashFlow.month == current_month,
                CashFlow.updated_at.is_(None),                
            ).order_by(CashFlow.id)
        )

        cashflow_list = query.limit(CASHFLOW_LIMIT).all()
    except Exception as e:
        print("Query failed Cashflow:", e)
        session.close()
        return
    

    for id, user_id in cashflow_list:
        try:
            #BILL PAID 
            monthly_paid_bill_totals = session.query(
                func.sum(BillPayments.amount).label('monthly_paid_bill_totals')
            ).join(
                BillPayments.bill_account
            ).filter(
                BillPayments.user_id == user_id,
                extract('year', BillPayments.pay_date) == target_year,
                extract('month', BillPayments.pay_date) == target_month,
                BillAccounts.deleted_at.is_(None),  # Make sure related account is not deleted
                BillAccounts.closed_at.is_(None)    # Make sure related account is not closed
            ).scalar() or 0

            app_data = session.query(AppData).filter(AppData.user_id == user_id).first()
            #INCOME WITH BOOST PART
            total_monthly_net_income = 0
            if app_data:
                total_monthly_net_income = app_data.total_monthly_net_income


            #DEBT WITH BOOST PART
            monthly_budget = (
                session.query(UserSettings.monthly_budget)
                .filter(UserSettings.user_id == user_id)
                .scalar()
            ) or 0

            monthly_debt_boost = session.query(
                func.sum(PaymentBoost.amount).label('monthly_debt_boost')
            ).filter(
                PaymentBoost.user_id == user_id,
                extract('year', PaymentBoost.pay_date_boost) == target_year,
                extract('month', PaymentBoost.pay_date_boost) == target_month,
                BillAccounts.deleted_at.is_(None)            
            ).scalar() or 0

            total_debt = monthly_budget  + monthly_debt_boost

            #forumal
            cashflow_amount = total_monthly_net_income - monthly_paid_bill_totals - total_debt

            stmt_update = update(CashFlow).where(CashFlow.id == id).values(
                
                amount=cashflow_amount,
                month=current_month,
                updated_at=current_datetime_now,
            )
            session.execute(stmt_update)
            session.commit()

        except Exception as ex:
                print(f'Exception while preparing income ID {id}:', ex)
                session.rollback()  # discard partial data for this record
                continue
        
    if session:
        session.close()  