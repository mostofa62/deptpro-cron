from datetime import datetime
from sqlalchemy import func, update
from incomeutil import get_single_boost, get_single_income
from models import AppData, Income, IncomeBoost, IncomeTransaction
from dbpg import SessionLocal

import argparse

from contextlib import contextmanager

@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        print('Session error:', e)
        raise
    finally:
        session.close()


def income_boost_next_payment():
    print('--- INCOME BOOST NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    print(f'--- INCOME BOOST NEXT PAYMENT STARTED - {current_datetime_now} ---')

    with get_session() as session:
        try:
            incomes_boosts = session.query(IncomeBoost).filter(
                IncomeBoost.next_pay_date_boost <= current_datetime_now,
                IncomeBoost.deleted_at.is_(None),
                IncomeBoost.closed_at.is_(None)
            ).all()
        except Exception as e:
            print("Query failed:", e)
            return

        for income_b in incomes_boosts:
            try:
                income_id = income_b.income_id
                income_boost_id = income_b.id
                commit = income_b.income.commit
                user_id = income_b.user_id

                total_balance = income_b.total_balance
                income_boost = income_b.income_boost
                repeat_boost = income_b.repeat_boost.get('value') if income_b.repeat_boost else None
                pay_date_boost = income_b.next_pay_date_boost if repeat_boost else None
                

                contribution_breakdown_b = get_single_boost(
                                total_balance,
                                income_boost,
                                pay_date_boost,
                                repeat_boost,
                                total_gross_income,
                                total_net_income
                                )
                breakdown_b = contribution_breakdown_b['income_transaction']
                total_balance_b = contribution_breakdown_b['total_boost_for_period']
                total_gross_income = contribution_breakdown_b['total_gross_for_period']
                total_net_income = contribution_breakdown_b['total_net_for_period']
                next_contribution_date_b = contribution_breakdown_b['next_pay_date']
                total_monthly_gross_income_b = contribution_breakdown_b['total_monthly_gross_income']
                total_monthly_net_income_b = contribution_breakdown_b['total_monthly_net_income']
                total_yearly_gross_income_b = contribution_breakdown_b['total_yearly_gross_income']
                total_yearly_net_income_b = contribution_breakdown_b['total_yearly_net_income']

                            

                income_transaction_list = {
                        'income_id':income_id,
                        'income_boost_id':income_boost_id,
                        'commit':commit,
                        'user_id':user_id,
                        **breakdown_b
                }

                # Update the boost status
               
                income_b.next_pay_date_boost = next_contribution_date_b
                income_b.total_balance =  total_balance_b
                income_b.total_monthly_gross_income+=total_monthly_gross_income_b
                income_b.total_monthly_net_income += total_monthly_net_income_b
                income_b.total_yearly_gross_income += total_yearly_gross_income_b
                income_b.total_yearly_net_income += total_yearly_net_income_b
                income_b.closed_at = None
                

                total_monthly_gross_income += total_monthly_gross_income_b
                total_monthly_net_income += total_monthly_net_income_b
                total_yearly_gross_income += total_yearly_gross_income_b
                total_yearly_net_income += total_yearly_net_income_b

                # Update the income record
                update_data = {
                    "total_net_income": total_net_income,            
                    'total_gross_income': total_gross_income,
                    'total_monthly_gross_income' :total_monthly_gross_income,
                    'total_monthly_net_income':total_monthly_net_income,
                    'total_yearly_gross_income':total_yearly_gross_income,
                    'total_yearly_net_income':total_yearly_net_income,       
                    'updated_at': datetime.now()              
                }

                print('Single Boost',update_data)

                            
                income_tx = IncomeTransaction(**income_transaction_list)

                app_data = session.query(AppData).filter(AppData.user_id == income_b.user_id).first()

                if app_data:
                    app_data.total_yearly_gross_income += total_yearly_gross_income
                    app_data.total_yearly_net_income += total_yearly_net_income
                    app_data.total_monthly_gross_income += total_monthly_gross_income
                    app_data.total_monthly_net_income += total_monthly_net_income
                    app_data.income_updated_at = None
                else:
                    app_data = AppData(
                        user_id=income_b.user_id,
                        total_yearly_gross_income=total_yearly_gross_income,
                        total_yearly_net_income=total_yearly_net_income,
                        total_monthly_gross_income=total_monthly_gross_income,
                        total_monthly_net_income=total_monthly_net_income,
                        income_updated_at=None
                    )

                session.add(income_tx)
                session.add(app_data)

                print(f'Income processed for user {income_b.income_id}')

            except Exception as ex:
                print(f'Exception while processing income ID {income_b.id}:', ex)



def main():
    parser = argparse.ArgumentParser(description="Run functions from command line")
    
    # Define the command-line argument to run the function
    parser.add_argument('function', type=str, help="Name of the function to run")

    # Parse the arguments
    args = parser.parse_args()

    # Check if the specified function is available and run it
    if args.function == 'income_tpros':
        #income_transaction_processing()
        income_boost_next_payment()
    else:
        print(f"Function {args.function} not recognized!")


if __name__ == '__main__':
    main()