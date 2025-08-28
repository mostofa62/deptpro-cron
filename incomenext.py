from datetime import datetime
from sqlalchemy import Integer, and_, cast, extract, func, or_, select, update
from util import convertDateTostring
from incomeutil import get_remaining_frequency_with_next, get_remaining_frequency_with_next_yearly, get_single_boost, get_single_income
from models import AppData, CashFlow, Income, IncomeBoost, IncomeTransaction,IncomeTransaction as IT
from dbpg import SessionLocal
from dateutil.relativedelta import relativedelta
import argparse
import os
from sqlalchemy.orm import aliased
def income_next_payment():

    INCOME_LIMIT = os.getenv('INCOME_LIMIT',10)

    print('--- INCOME NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f'--- INCOME NEXT PAYMENT STARTED - {current_datetime_now} ---')

    session = SessionLocal()
    
    current_month = int(convertDateTostring(current_datetime_now,'%Y%m'))
    current_year = int(current_month/100)
    

    try:
        '''
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
        '''

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
                # monthly_gross_income_subq.label("p_monthly_gross_income"),
                # monthly_net_income_subq.label("p_monthly_net_income"),
                # yearly_gross_income_subq.label("p_yearly_gross_income"),
                # yearly_net_income_subq.label("p_yearly_net_income"),
                Income.total_monthly_gross_income,
                Income.total_monthly_net_income,
                Income.total_yearly_gross_income,
                Income.total_yearly_net_income,
                Income.total_monthly_gross_income_f,
                Income.total_monthly_net_income_f,
                Income.total_yearly_gross_income_f,
                Income.total_yearly_net_income_f
            )
            .filter(
                Income.next_pay_date <= current_datetime_now,
                Income.deleted_at.is_(None),
                Income.closed_at.is_(None)
            ).order_by(Income.next_pay_date)
        )
        #print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))

        incomes_due = query.limit(INCOME_LIMIT).all()
    except Exception as e:
        print("Query failed Income:", e)
        session.close()
        return
    
    for id, user_id, next_pay_date, total_gross_income, total_net_income, \
    gross_income, net_income, commit, repeat, \
    total_monthly_gross_income, total_monthly_net_income, \
    total_yearly_gross_income, total_yearly_net_income, \
    total_monthly_gross_income_f, total_monthly_net_income_f, \
    total_yearly_gross_income_f,total_yearly_net_income_f \
    in incomes_due:
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
            
            current_running_month = int(convertDateTostring(next_pay_date,'%Y%m'))
            current_running_year = int(current_running_month / 100)


            monthly_gross_income =  income_transaction_generate['total_monthly_gross_income']
            monthly_net_income = income_transaction_generate['total_monthly_net_income']
            yearly_gross_income = income_transaction_generate['total_yearly_gross_income']
            yearly_net_income =income_transaction_generate['total_yearly_net_income']            

            if current_running_year == current_year:
                total_yearly_gross_income += yearly_gross_income
                total_yearly_net_income += yearly_net_income
                total_yearly_gross_income_f -= yearly_gross_income
                total_yearly_net_income_f -= yearly_net_income

            if current_running_month == current_month and repeat < 30:
                total_monthly_gross_income += monthly_gross_income
                total_monthly_net_income += monthly_net_income
                total_monthly_gross_income_f -= monthly_gross_income
                total_monthly_net_income_f -= monthly_net_income

                    
            stmt_update = update(Income).where(Income.id == id).values(
                total_gross_income=total_gross_income,
                total_net_income=total_net_income,
                total_monthly_gross_income=total_monthly_gross_income,
                total_monthly_net_income=total_monthly_net_income,
                total_yearly_gross_income=total_yearly_gross_income,
                total_yearly_net_income=total_yearly_net_income,
                total_monthly_gross_income_f = total_monthly_gross_income_f,
                total_monthly_net_income_f  = total_monthly_net_income_f,
                total_yearly_gross_income_f = total_yearly_gross_income_f,
                total_yearly_net_income_f = total_yearly_net_income_f,
                next_pay_date=next_pay_date,
                updated_at= datetime.now()
            )
            session.execute(stmt_update)
            
            session.add(IncomeTransaction(**income_transaction_list))            
            session.flush()
            '''
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

            '''

            app_data = session.query(AppData).filter(AppData.user_id == user_id).first()
            if app_data:
                if current_running_month == current_month:
                    if app_data.current_income_month !=None and app_data.current_income_month == current_running_month:
                        app_data.total_monthly_gross_income += monthly_gross_income
                        app_data.total_monthly_net_income += monthly_net_income
                        app_data.total_monthly_gross_income_f -= monthly_gross_income
                        app_data.total_monthly_net_income_f -= monthly_net_income
                    else:
                        app_data.total_monthly_gross_income = monthly_gross_income
                        app_data.total_monthly_net_income = monthly_net_income
                        app_data.total_monthly_gross_income_f = monthly_gross_income
                        app_data.total_monthly_net_income_f = monthly_net_income
                        app_data.current_income_month = current_running_month
                if current_running_year == current_year: 
                    if app_data.current_income_year !=None and app_data.current_income_year == current_running_year:
                        app_data.total_yearly_gross_income += yearly_gross_income
                        app_data.total_yearly_net_income += yearly_net_income
                        app_data.total_yearly_gross_income_f -= yearly_gross_income
                        app_data.total_yearly_net_income_f -= yearly_net_income
                    else:
                        app_data.total_yearly_gross_income = yearly_gross_income
                        app_data.total_yearly_net_income = yearly_net_income
                        app_data.total_yearly_gross_income_f = yearly_gross_income
                        app_data.total_yearly_net_income_f = yearly_net_income
                        app_data.current_income_year = current_running_year
                
                app_data.income_updated_at = None
                session.add(app_data)
            
            cashflow_data = session.query(CashFlow).filter(
                        CashFlow.user_id == user_id,
                        CashFlow.month == current_month
                    ).first()
            if not cashflow_data:
                cashflow_data = CashFlow(
                    user_id = user_id,
                    amount = 0,
                    month = current_month,
                    updated_at = None
                )
            else:
                cashflow_data.updated_at = None
                
            session.add(cashflow_data)
            # stmt_update = update(AppData).where(AppData.user_id == user_id).values(
               
            #     total_monthly_gross_income=total_monthly_gross,
            #     total_monthly_net_income=total_monthly_net,
            #     total_yearly_gross_income=total_yearly_gross,
            #     total_yearly_net_income=total_yearly_net,
            #     income_updated_at=None
            # )
            # session.execute(stmt_update)
            session.commit()

        except Exception as ex:
            print(f'Exception while preparing income ID {id}:', ex)
            session.rollback()  # discard partial data for this record
            continue

    


            
    if session:
        session.close()    
        #print(result)
        

IncomeAlias = aliased(Income)

def income_boost_next_payment():

    INCOME_LIMIT = os.getenv('INCOME_LIMIT',10)

    print('--- INCOME BOOST NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f'--- INCOME BOOST NEXT PAYMENT STARTED - {current_datetime_now} ---')

    session = SessionLocal()
    

    

    try:
        effective_pay_date = func.coalesce(IncomeBoost.next_pay_date_boost, IncomeBoost.pay_date_boost)

        monthly_gross_income_subq = (
            select(func.coalesce(func.sum(IT.gross_income), 0.0))
            .where(
                IT.income_id == IncomeBoost.income_id,
                IT.commit == IncomeAlias.commit,
                IT.month == cast(func.to_char( effective_pay_date , 'YYYYMM'), Integer)
            )
            .scalar_subquery()
        )

        monthly_net_income_subq = (
            select(func.coalesce(func.sum(IT.net_income), 0.0))
            .where(
                IT.income_id == IncomeBoost.income_id,
                IT.commit == IncomeAlias.commit,
                IT.month == cast(func.to_char( effective_pay_date , 'YYYYMM'), Integer)
            )
            .scalar_subquery()
        )

        yearly_gross_income_subq = (
            select(func.coalesce(func.sum(IT.gross_income), 0.0))
            .where(
                IT.income_id == IncomeBoost.income_id,
                IT.commit == IncomeAlias.commit,
                IT.month // 100 == func.extract("year", effective_pay_date )
            )
            .scalar_subquery()
        )

        yearly_net_income_subq = (
            select(func.coalesce(func.sum(IT.net_income), 0.0))
            .where(
                IT.income_id == IncomeBoost.income_id,
                IT.commit == IncomeAlias.commit,
                IT.month // 100 == func.extract("year", effective_pay_date )
            )
            .scalar_subquery()
        )

        query = (
            session.query(
                IncomeBoost.income_id.label('income_id'),
                IncomeBoost.id.label('income_boost_id'),
                IncomeBoost.user_id,
                effective_pay_date.label('next_pay_date'),                
                IncomeBoost.total_balance,               
                IncomeBoost.income_boost,               
                IncomeAlias.commit.label('commit'),
                IncomeBoost.repeat_boost.label('repeat'),
                IncomeAlias.total_gross_income,
                IncomeAlias.total_net_income,
                monthly_gross_income_subq.label("p_monthly_gross_income"),
                monthly_net_income_subq.label("p_monthly_net_income"),
                yearly_gross_income_subq.label("p_yearly_gross_income"),
                yearly_net_income_subq.label("p_yearly_net_income"),
            )
            .join(IncomeAlias, IncomeAlias.id == IncomeBoost.income_id)
            .filter(
                ( effective_pay_date <= current_datetime_now),
                IncomeBoost.deleted_at.is_(None),
                IncomeBoost.closed_at.is_(None),
                or_(
                    IncomeBoost.repeat_boost["value"].as_integer() != 0,  # If not 0, don't check single_done
                    and_(
                        IncomeBoost.repeat_boost["value"].as_integer() == 0,
                        IncomeBoost.single_done == 0
                    )
                )
            ).order_by(effective_pay_date)
        )
        print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))

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
            repeat = repeat.get('value') if repeat and repeat.get('value') > 0 else None
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
                updated_at= datetime.now()                
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
                'closed_at': None,
                'single_done':1 if repeat == None else 0
            }

            session.query(IncomeBoost).filter_by(id=boost_status['id']).update({
                                'next_pay_date_boost': boost_status['next_pay_date_boost'],
                                'total_balance': boost_status['total_balance'],
                                'total_monthly_gross_income': boost_status['total_monthly_gross_income'],
                                'total_monthly_net_income': boost_status['total_monthly_net_income'],
                                'total_yearly_gross_income': boost_status['total_yearly_gross_income'],
                                'total_yearly_net_income': boost_status['total_yearly_net_income'],                        
                                'closed_at': boost_status['closed_at'],
                                'single_done':boost_status['single_done']
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
        #income_next_payment()
        income_boost_next_payment()
    else:
        print(f"Function {args.function} not recognized!")


if __name__ == '__main__':
    main()