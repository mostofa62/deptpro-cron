from datetime import datetime
from sqlalchemy import Integer, and_, cast, extract, func, or_, select, update
from savingutil import calculate_breakdown_single
from util import convertDateTostring
from dbpg import SessionLocal
from dateutil.relativedelta import relativedelta
import argparse
import os
from sqlalchemy.orm import aliased
from models import AppData,Saving, SavingBoost, SavingContribution, SavingContribution as SC
def saving_next_payment():

    SAVING_LIMIT = os.getenv('SAVING_LIMIT',10)

    print('--- SAVING NEXT PAYMENT ---')

    current_datetime_now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f'--- SAVING NEXT PAYMENT STARTED - {current_datetime_now} ---')

    session = SessionLocal()

    try:
        '''
        monthly_contribution_subq = (
            select(func.coalesce(func.sum(SC.contribution_i_intrs), 0.0))
            .where(
                SC.saving_id == Saving.id,
                SC.commit == Saving.commit,
                SC.month == cast(func.to_char(Saving.next_contribution_date, 'YYYYMM'), Integer)
            )
            .scalar_subquery()
        )
        '''

        query = (
            session.query(
                Saving.id,
                Saving.user_id,
                Saving.next_contribution_date,
                Saving.total_balance_xyz,
                Saving.contribution,
                Saving.goal_amount,
                Saving.interest,
                Saving.interest_type,
                Saving.increase_contribution_by,
                Saving.savings_strategy,
                Saving.period,               
                Saving.commit,
                Saving.repeat,
                Saving.total_monthly_balance,
                Saving.total_monthly_balance_f
                #monthly_contribution_subq.label("p_total_monthly_balance"),
                
            )
            .filter(
                Saving.next_contribution_date <= current_datetime_now,
                Saving.deleted_at.is_(None),
                Saving.closed_at.is_(None)
            ).order_by(Saving.next_contribution_date)
        )

        saving_due = query.limit(SAVING_LIMIT).all()

    except Exception as e:
        print("Query failed Income:", e)
        session.close()
        return
    
    current_saving_month = int(convertDateTostring(datetime.now(),'%Y%m'))
    current_running_month = current_saving_month 
    
    for id, user_id, next_contribution_date, total_balance_xyz, contribution,goal_amount, \
    interest, interest_type,increase_contribution_by,savings_strategy,period ,commit, repeat, \
    total_monthly_balance, total_monthly_balance_f in saving_due:
        try:
            starting_amount = total_balance_xyz
            repeat = repeat.get('value') if repeat else None
            starting_date = next_contribution_date
            i_contribution = increase_contribution_by
            interest_type = interest_type['value']
            savings_strategy = savings_strategy['value']

            contribution_breakdown = calculate_breakdown_single(
            starting_amount,
            contribution,
            interest, 
            goal_amount, 
            starting_date,
            repeat,
            i_contribution,
            period,
            interest_type,
            savings_strategy,
            1,
            0,
            total_monthly_balance
            )

            breakdown = contribution_breakdown['breakdown']
            total_balance = contribution_breakdown['total_balance']
            total_balance_xyz = contribution_breakdown['total_balance_xyz']
            progress  = contribution_breakdown['progress']
            next_contribution_date = contribution_breakdown['next_contribution_date']
            goal_reached = contribution_breakdown['goal_reached']
            period = contribution_breakdown['period']
            is_single = contribution_breakdown['is_single']
            total_monthly_balance_xyz = contribution_breakdown['total_monthly_balance_xyz']
            contribution_i_intrs = contribution_breakdown['contribution_i_intrs']

            len_breakdown = len(breakdown)

            if len_breakdown < 1:
                continue

            if next_contribution_date == None:
                goal_reached = goal_reached if len_breakdown > 0 else None

            
            if next_contribution_date!=None:
                current_running_month = int(convertDateTostring(next_contribution_date,'%Y%m'))
                if current_running_month == current_saving_month:
                    total_monthly_balance_f -=contribution_i_intrs


            
            
            contribution_data = SavingContribution(
                    saving_id=id,                            
                    commit=commit,
                    user_id=user_id,
                    **breakdown
                )
            session.add(contribution_data)

            stmt_update = update(Saving).where(Saving.id == id).values(
                total_balance=total_balance,
                total_balance_xyz=total_balance_xyz,
                progress=progress,
                period=period,
                total_monthly_balance=total_monthly_balance_xyz,
                total_monthly_balance_f=total_monthly_balance_f,
                current_month=current_saving_month,
                next_contribution_date=next_contribution_date,
                goal_reached = goal_reached,
                updated_at= datetime.now()
            )
            session.execute(stmt_update)
            

            app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

            if app_data:
                # Update the existing record
                                    
                app_data.current_saving_month = current_saving_month
                
                if app_data.current_saving_month == current_saving_month:
                    app_data.total_monthly_saving += total_monthly_balance_xyz
                    app_data.total_monthly_saving_f -= contribution_i_intrs
                else:
                    app_data.total_monthly_saving =  total_monthly_balance_xyz 
                    app_data.total_monthly_saving_f = 0                  
                app_data.saving_updated_at = None
                
                
            else:
                # Insert a new record if the user doesn't exist
                app_data = AppData(
                    user_id=user_id,
                    current_saving_month = current_saving_month,
                    total_monthly_saving=total_monthly_balance_xyz,
                    total_monthly_saving_f=total_monthly_balance_f,                        
                    saving_updated_at=None
                )
            
            session.add(app_data)
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
    if args.function == 'saving_cpros':
        saving_next_payment()
    else:
        print(f"Function {args.function} not recognized!")


if __name__ == '__main__':
    main()