from datetime import datetime
from sqlalchemy import Integer, cast, extract, func, select, update
from util import convertDateTostring
from incomeutil import get_single_boost, get_single_income
from models import AppData, Income, IncomeBoost, IncomeTransaction,IncomeTransaction as IT
from dbpg import SessionLocal
from dateutil.relativedelta import relativedelta
import argparse
import os

def income_next_payment():

    INCOME_LIMIT = os.getenv('INCOME_LIMIT',10)

    print('--- INCOME NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f'--- INCOME NEXT PAYMENT STARTED - {current_datetime_now} ---')

    session = SessionLocal()
    

    

    try:
        monthly_gross_income_subq = (
            select(func.coalesce(func.sum(IT.gross_income), 0.0))
            .where(
                IT.income_id == Income.id,
                IT.commit == Income.commit,
                IT.month == cast(func.to_char(Income.next_pay_date, 'YYYYMM'), Integer)
            )
            .scalar_subquery()
        )

        monthly_net_income_subq = (
            select(func.coalesce(func.sum(IT.net_income), 0.0))
            .where(
                IT.income_id == Income.id,
                IT.commit == Income.commit,
                IT.month == cast(func.to_char(Income.next_pay_date, 'YYYYMM'), Integer)
            )
            .scalar_subquery()
        )

        yearly_gross_income_subq = (
            select(func.coalesce(func.sum(IT.gross_income), 0.0))
            .where(
                IT.income_id == Income.id,
                IT.commit == Income.commit,
                IT.month // 100 == func.extract("year", Income.next_pay_date)
            )
            .scalar_subquery()
        )

        yearly_net_income_subq = (
            select(func.coalesce(func.sum(IT.net_income), 0.0))
            .where(
                IT.income_id == Income.id,
                IT.commit == Income.commit,
                IT.month // 100 == func.extract("year", Income.next_pay_date)
            )
            .scalar_subquery()
        )

        query = (
            session.query(
                Income.id,
                Income.user_id,
                Income.next_pay_date,
                Income.total_gross_income,
                Income.total_net_income,
                Income.gross_income,
                Income.net_income,
                Income.commit,
                Income.repeat,
                monthly_gross_income_subq.label("p_monthly_gross_income"),
                monthly_net_income_subq.label("p_monthly_net_income"),
                yearly_gross_income_subq.label("p_yearly_gross_income"),
                yearly_net_income_subq.label("p_yearly_net_income"),
            )
            .filter(
                Income.next_pay_date <= current_datetime_now,
                Income.deleted_at.is_(None),
                Income.closed_at.is_(None)
            )
        )
        #print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))

        incomes_due = query.limit(INCOME_LIMIT).all()
    except Exception as e:
        print("Query failed Income:", e)
        session.close()
        return
    
    for id, user_id, next_pay_date, total_gross_income, total_net_income, \
    gross_income, net_income, commit, repeat, \
    p_monthly_gross_income, p_monthly_net_income, \
    p_yearly_gross_income, p_yearly_net_income in incomes_due:
        try:
            repeat = repeat.get('value') if repeat else None
            pay_date = next_pay_date                    
            income_transaction_generate = get_single_income(
                    total_gross_income,
                    total_net_income,
                    gross_income,
                    net_income,
                    pay_date,
                    repeat,
                    commit,
                    id,
                    user_id                    
                )
            income_transaction_list = income_transaction_generate['income_transaction']
            total_gross_income = income_transaction_generate['total_gross_for_period']
            total_net_income = income_transaction_generate['total_net_for_period']
            next_pay_date = income_transaction_generate['next_pay_date']        
            
            


            monthly_gross_income =  income_transaction_generate['total_monthly_gross_income']
            monthly_net_income = income_transaction_generate['total_monthly_net_income']
            yearly_gross_income = income_transaction_generate['total_yearly_gross_income']
            yearly_net_income =income_transaction_generate['total_yearly_net_income']            

            
            total_yearly_gross_income = p_yearly_gross_income + yearly_gross_income
            total_yearly_net_income = p_yearly_net_income + yearly_net_income                        
            total_monthly_gross_income = p_monthly_gross_income + monthly_gross_income
            total_monthly_net_income = p_monthly_net_income + monthly_net_income
            
           
           
                    
            stmt_update = update(Income).where(Income.id == id).values(
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
            session.flush()

            income_result = (
                session.query(
                    func.coalesce(func.sum(Income.total_monthly_net_income), 0.0),
                    func.coalesce(func.sum(Income.total_monthly_gross_income), 0.0),
                    func.coalesce(func.sum(Income.total_yearly_gross_income), 0.0),
                    func.coalesce(func.sum(Income.total_yearly_net_income), 0.0),
                )
                .filter(
                    Income.user_id == user_id,
                    Income.deleted_at.is_(None),
                    Income.closed_at.is_(None)
                )
                .one()
            )

            (
                total_monthly_net,
                total_monthly_gross,
                total_yearly_gross,
                total_yearly_net
            ) = income_result


            stmt_update = update(AppData).where(AppData.user_id == user_id).values(
               
                total_monthly_gross_income=total_monthly_gross,
                total_monthly_net_income=total_monthly_net,
                total_yearly_gross_income=total_yearly_gross,
                total_yearly_net_income=total_yearly_net,
                income_updated_at=None
            )
            session.execute(stmt_update)
            session.commit()

        except Exception as ex:
            print(f'Exception while preparing income ID {id}:', ex)
            session.rollback()  # discard partial data for this record
            continue

    


            
    if session:
        session.close()    
        #print(result)
        

def income_boost_next_payment():

    INCOME_LIMIT = os.getenv('INCOME_LIMIT',10)

    print('--- INCOME BOOST NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f'--- INCOME BOOST NEXT PAYMENT STARTED - {current_datetime_now} ---')

    session = SessionLocal()
    

    

    try:
        monthly_gross_income_subq = (
            select(func.coalesce(func.sum(IT.gross_income), 0.0))
            .where(
                IT.income_id == IncomeBoost.income_id,
                IT.commit == IncomeBoost.income.commit,
                IT.month == cast(func.to_char(IncomeBoost.next_pay_date_boost, 'YYYYMM'), Integer)
            )
            .scalar_subquery()
        )

        monthly_net_income_subq = (
            select(func.coalesce(func.sum(IT.net_income), 0.0))
            .where(
                IT.income_id == IncomeBoost.income_id,
                IT.commit == IncomeBoost.income.commit,
                IT.month == cast(func.to_char(IncomeBoost.next_pay_date_boost, 'YYYYMM'), Integer)
            )
            .scalar_subquery()
        )

        yearly_gross_income_subq = (
            select(func.coalesce(func.sum(IT.gross_income), 0.0))
            .where(
                IT.income_id == IncomeBoost.income_id,
                IT.commit == IncomeBoost.income.commit,
                IT.month // 100 == func.extract("year", IncomeBoost.next_pay_date_boost)
            )
            .scalar_subquery()
        )

        yearly_net_income_subq = (
            select(func.coalesce(func.sum(IT.net_income), 0.0))
            .where(
                IT.income_id == IncomeBoost.income_id,
                IT.commit == IncomeBoost.income.commit,
                IT.month // 100 == func.extract("year", IncomeBoost.next_pay_date_boost)
            )
            .scalar_subquery()
        )

        query = (
            session.query(
                IncomeBoost.income_id,
                IncomeBoost.id.label('income_boost_id'),
                IncomeBoost.user_id,
                IncomeBoost.next_pay_date_boost.label('next_pay_date'),
                IncomeBoost.total_balance,               
                IncomeBoost.income_boost,               
                IncomeBoost.income.commit.label('commit'),
                IncomeBoost.repeat_boost.label('repeat'),
                IncomeBoost.income.total_gross_income,
                IncomeBoost.income.total_net_income,
                monthly_gross_income_subq.label("p_monthly_gross_income"),
                monthly_net_income_subq.label("p_monthly_net_income"),
                yearly_gross_income_subq.label("p_yearly_gross_income"),
                yearly_net_income_subq.label("p_yearly_net_income"),
            )
            .filter(
                IncomeBoost.next_pay_date_boost <= current_datetime_now,
                IncomeBoost.deleted_at.is_(None),
                IncomeBoost.closed_at.is_(None)
            )
        )
        #print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))

        incomes_due = query.limit(INCOME_LIMIT).all()
    except Exception as e:
        print("Query failed Income:", e)
        session.close()
        return
    
    for income_id, income_boost_id, user_id, next_pay_date, total_balance,\
    income_boost, commit, repeat,total_gross_income, total_net_income, \
    p_monthly_gross_income, p_monthly_net_income, \
    p_yearly_gross_income, p_yearly_net_income in incomes_due:
        try:
            repeat = repeat.get('value') if repeat else None
            pay_date = next_pay_date                    
            contribution_breakdown_b = get_single_boost(
                    total_balance,
                    income_boost,                    
                    pay_date,
                    repeat, 
                    total_gross_income,
                    total_net_income                                    
                )
            breakdown_b = contribution_breakdown_b['income_transaction']
            total_balance_b = contribution_breakdown_b['total_boost_for_period']
            total_gross_income = contribution_breakdown_b['total_gross_for_period']
            total_net_income = contribution_breakdown_b['total_net_for_period']
            next_pay_date = contribution_breakdown_b['next_pay_date']        
            

            income_transaction_list = {
                                'income_id':income_id,
                                'income_boost_id':income_boost_id,
                                'commit':commit,
                                'user_id':user_id,
                                **breakdown_b
                        }
            


            monthly_gross_income =  contribution_breakdown_b['total_monthly_gross_income']
            monthly_net_income = contribution_breakdown_b['total_monthly_net_income']
            yearly_gross_income = contribution_breakdown_b['total_yearly_gross_income']
            yearly_net_income =contribution_breakdown_b['total_yearly_net_income']            

            
            total_yearly_gross_income = p_yearly_gross_income + yearly_gross_income
            total_yearly_net_income = p_yearly_net_income + yearly_net_income                        
            total_monthly_gross_income = p_monthly_gross_income + monthly_gross_income
            total_monthly_net_income = p_monthly_net_income + monthly_net_income
            
           
           
                    
            stmt_update = update(Income).where(Income.id == income_id).values(
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
            
            
            boost_status = {
                'id': income_boost_id,
                'next_pay_date_boost': next_pay_date,
                'total_balance': total_balance_b,
                'total_monthly_gross_income' :total_monthly_gross_income,
                'total_monthly_net_income':total_monthly_net_income,
                'total_yearly_gross_income':total_yearly_gross_income,
                'total_yearly_net_income':total_yearly_net_income,
                'closed_at': None
            }

            session.query(IncomeBoost).filter_by(id=boost_status['id']).update({
                                'next_pay_date_boost': boost_status['next_pay_date_boost'],
                                'total_balance': boost_status['total_balance'],
                                'total_monthly_gross_income': boost_status['total_monthly_gross_income'],
                                'total_monthly_net_income': boost_status['total_monthly_net_income'],
                                'total_yearly_gross_income': boost_status['total_yearly_gross_income'],
                                'total_yearly_net_income': boost_status['total_yearly_net_income'],                        
                                'closed_at': boost_status['closed_at']
                            })
            
            session.flush()

            income_result = (
                session.query(
                    func.coalesce(func.sum(Income.total_monthly_net_income), 0.0),
                    func.coalesce(func.sum(Income.total_monthly_gross_income), 0.0),
                    func.coalesce(func.sum(Income.total_yearly_gross_income), 0.0),
                    func.coalesce(func.sum(Income.total_yearly_net_income), 0.0),
                )
                .filter(
                    Income.user_id == user_id,
                    Income.deleted_at.is_(None),
                    Income.closed_at.is_(None)
                )
                .one()
            )

            (
                total_monthly_net,
                total_monthly_gross,
                total_yearly_gross,
                total_yearly_net
            ) = income_result


            stmt_update = update(AppData).where(AppData.user_id == user_id).values(
               
                total_monthly_gross_income=total_monthly_gross,
                total_monthly_net_income=total_monthly_net,
                total_yearly_gross_income=total_yearly_gross,
                total_yearly_net_income=total_yearly_net,
                income_updated_at=None
            )
            session.execute(stmt_update)
            session.commit()

        except Exception as ex:
            print(f'Exception while preparing income ID {id}:', ex)
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