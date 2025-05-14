from datetime import datetime
from sqlalchemy import func, update
from incomeutil import get_single_income
from models import AppData, Income, IncomeTransaction
from dbpg import SessionLocal
from dateutil.relativedelta import relativedelta
import argparse

def income_next_payment():
    print('--- INCOME NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + relativedelta(months=2)

    c_date_ym = int(current_datetime_now.strftime("%Y%m"))
    c_date_y = int(c_date_ym/100)
    print(f'--- INCOME NEXT PAYMENT STARTED - {current_datetime_now} ---')

    session = SessionLocal()

    try:
        incomes_due = session.query(Income).filter(
            Income.next_pay_date <= current_datetime_now,
            Income.deleted_at.is_(None),
            Income.closed_at.is_(None)
        ).all()
    except Exception as e:
        print("Query failed:", e)
        session.close()
        return

    for income in incomes_due:
        try:
            repeat = income.repeat.get('value') if income.repeat else None
            pay_date = income.next_pay_date
            
            
            total_monthly_gross_income = income.total_monthly_gross_income if repeat < 30 else 0
            total_monthly_net_income = income.total_monthly_net_income if repeat < 30 else 0
            total_yearly_gross_income = income.total_yearly_gross_income if repeat >= 30 and repeat < 365 else 0
            total_yearly_net_income = income.total_yearly_net_income if repeat >= 30 and repeat < 365 else 0

            income_transaction_generate = get_single_income(
                income.total_gross_income,
                income.total_net_income,
                income.gross_income,
                income.net_income,
                pay_date,
                repeat,
                income.commit,
                income.id,
                income.user_id                    
            )

            income_transaction_list = income_transaction_generate['income_transaction']
            total_gross_income = income_transaction_generate['total_gross_for_period']
            total_net_income = income_transaction_generate['total_net_for_period']
            next_pay_date = income_transaction_generate['next_pay_date']
            
            next_pay_date_ym = int(next_pay_date.strftime("%Y%m"))
            next_pay_date_y  = int(next_pay_date_ym/100)
            
            total_monthly_gross_income =  total_monthly_gross_income + income_transaction_generate['total_monthly_gross_income'] if c_date_ym == next_pay_date_ym else income_transaction_generate['total_monthly_gross_income']
            total_monthly_net_income = total_monthly_net_income + income_transaction_generate['total_monthly_net_income'] if c_date_ym == next_pay_date_ym else income_transaction_generate['total_monthly_net_income']
            total_yearly_gross_income = total_yearly_gross_income + income_transaction_generate['total_yearly_gross_income'] if c_date_y == next_pay_date_y else income_transaction_generate['total_yearly_gross_income']
            total_yearly_net_income = total_yearly_net_income +  income_transaction_generate['total_yearly_net_income'] if c_date_y == next_pay_date_y else income_transaction_generate['total_yearly_net_income']

            session.add(IncomeTransaction(**income_transaction_list))

            stmt_update = update(Income).where(Income.id == income.id).values(
                total_gross_income=total_gross_income,
                total_net_income=total_net_income,
                total_monthly_gross_income=total_monthly_gross_income,
                total_monthly_net_income=total_monthly_net_income,
                total_yearly_gross_income=total_yearly_gross_income,
                total_yearly_net_income=total_yearly_net_income,
                next_pay_date=next_pay_date
            )
            session.execute(stmt_update)

            app_data = session.query(AppData).filter(AppData.user_id == income.user_id).first()
            if app_data:
                app_data.total_yearly_gross_income += total_yearly_gross_income
                app_data.total_yearly_net_income += total_yearly_net_income
                app_data.total_monthly_gross_income += total_monthly_gross_income
                app_data.total_monthly_net_income += total_monthly_net_income
                app_data.income_updated_at = None
                session.add(app_data)

            print(f'Prepared income data for user {income.user_id}')

        except Exception as ex:
            print(f'Exception while preparing income ID {income.id}:', ex)
            session.rollback()  # discard partial data for this record
            continue

    try:
        session.commit()
        print('✅ All valid income transactions committed successfully.')
    except Exception as commit_err:
        session.rollback()
        print('❌ Final commit failed:', commit_err)

    session.close()


def main():
    parser = argparse.ArgumentParser(description="Run functions from command line")
    
    # Define the command-line argument to run the function
    parser.add_argument('function', type=str, help="Name of the function to run")

    # Parse the arguments
    args = parser.parse_args()

    # Check if the specified function is available and run it
    if args.function == 'income_tpros':
        #income_transaction_processing()
        income_next_payment()
    else:
        print(f"Function {args.function} not recognized!")


if __name__ == '__main__':
    main()