from datetime import datetime
from sqlalchemy import func, update
from util import convertDateTostring
from incomeutil import get_single_boost, get_single_income
from models import AppData, Income, IncomeBoost, IncomeTransaction
from dbpg import SessionLocal
from dateutil.relativedelta import relativedelta
import argparse

def income_next_payment():

    print('--- INCOME NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)+relativedelta(months=1)
    
    print(f'--- INCOME NEXT PAYMENT STARTED - {current_datetime_now} ---')

    session = SessionLocal()

    try:
        incomes_due = session.query(Income).filter(
            Income.next_pay_date <= current_datetime_now,
            Income.deleted_at.is_(None),
            Income.closed_at.is_(None)
        ).all()
    except Exception as e:
        print("Query failed Income:", e)
        session.close()
        return
    
    for income in incomes_due:
        try:
            repeat = income.repeat.get('value') if income.repeat else None
            pay_date = income.next_pay_date        
            pay_date_yr = pay_date.year
            pay_date_mn = int(convertDateTostring(pay_date,'%Y%m'))
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
            next_pay_date_yr =  next_pay_date.year
            next_pay_date_mn = int(convertDateTostring(next_pay_date,'%Y%m'))

            p_monthly_gross_income = income.total_monthly_gross_income
            p_monthly_net_income = income.total_monthly_net_income
            p_yearly_gross_income = income.total_yearly_gross_income
            p_yearly_net_income = income.total_yearly_net_income

            monthly_gross_income =  income_transaction_generate['total_monthly_gross_income']
            monthly_net_income = income_transaction_generate['total_monthly_net_income']
            yearly_gross_income = income_transaction_generate['total_yearly_gross_income']
            yearly_net_income =income_transaction_generate['total_yearly_net_income']

            total_monthly_gross_income = monthly_gross_income
            total_monthly_net_income = monthly_net_income
            total_yearly_gross_income = yearly_gross_income
            total_yearly_net_income = yearly_net_income

            if pay_date_yr == next_pay_date_yr:
                total_yearly_gross_income = p_yearly_gross_income + yearly_gross_income
                total_yearly_net_income = p_yearly_net_income + yearly_net_income                
            
            if pay_date_mn == next_pay_date_mn:
                total_monthly_gross_income = p_monthly_gross_income + monthly_gross_income
                total_monthly_net_income = p_monthly_net_income + monthly_net_income
            


            app_data = session.query(AppData).filter(AppData.user_id == income.user_id).first()
            if app_data:
                    if pay_date_yr == next_pay_date_yr:
                        app_data.total_yearly_gross_income += yearly_gross_income
                        app_data.total_yearly_net_income += yearly_net_income
                    else:
                        app_data.total_yearly_gross_income -= p_yearly_gross_income
                        app_data.total_yearly_net_income -= p_yearly_net_income
                        app_data.total_yearly_gross_income += yearly_gross_income
                        app_data.total_yearly_net_income += yearly_net_income
                    
                    if pay_date_mn == next_pay_date_mn:                                    
                        app_data.total_monthly_gross_income += monthly_gross_income
                        app_data.total_monthly_net_income += monthly_net_income
                    else:
                        app_data.total_monthly_gross_income -= p_monthly_gross_income
                        app_data.total_monthly_net_income -= p_monthly_net_income
                        app_data.total_monthly_gross_income += monthly_gross_income
                        app_data.total_monthly_net_income += monthly_net_income
                    app_data.income_updated_at = None
                    
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
            
            session.add(IncomeTransaction(**income_transaction_list))
            session.add(app_data)
            session.commit()
        except Exception as ex:
            print(f'Exception while preparing income ID {income.id}:', ex)
            session.rollback()  # discard partial data for this record
            continue


            
    if session:
        session.close()    
        #print(result)
        

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