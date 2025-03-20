from datetime import datetime
from sqlalchemy import func, update
from models import AppData, Income, IncomeBoost, IncomeMonthlyLog, IncomeTransaction, IncomeYearlyLog, Saving, SavingContribution
from dbpg import SessionLocal
from db import my_col

from savingutil import calculate_breakdown, get_single_breakdown, get_single_boost
saving_accounts_logs = my_col('saving_accounts_logs')
import argparse

def saving_contribution_processing():
    print('---SAVING CONTRIBUTION---')
    session = None
    try:
        session = SessionLocal()
    except Exception as ex:
        print('PGSQL ISSUE',ex)
        session = None
        return

    
    print('---SAVING CONTRIBUTION STARTED---')

    
    
    saving_acc_query = {                
                "finished_at": None,                                
    }
    

    total_balance = 0
    total_balance_xyz = 0
    total_monthly_balance = 0 
    starting_amount = 0   
    progress = 0
    period = 0
    goal_reached = None

    p_total_balance = 0
    p_total_balance_xyz = 0
    p_total_monthly_balance = 0
   

    pb_total_balance = 0    
    pb_total_monthly_balance = 0

    saving_log_data = saving_accounts_logs.find_one(saving_acc_query)
    saving_contribution_data = []
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if saving_log_data !=None:

        saving_id = saving_log_data['saving_id']
        user_id = saving_log_data['user_id']
        saving_acc_query = {
                "saving_id": saving_id,                
                "user_id":user_id,
                
        }
        
        commit = saving_log_data['commit']
        saving_id = saving_log_data['saving_id']
        user_id = saving_log_data['user_id']
        saving = saving_log_data['saving']
        starting_amount = saving['starting_amount']
        contribution = saving['contribution']
        interest = saving['interest']
        goal_amount = saving['goal_amount']
        starting_date = saving['starting_date']
        repeat = saving['repeat']
        i_contribution = saving['increase_contribution_by']
        total_balance = saving['total_balance']
        total_balance_xyz = saving['total_balance_xyz']
        total_monthly_balance = saving['total_monthly_balance']


        p_total_balance = saving['p_total_balance']
        p_total_balance_xyz = saving['p_total_balance_xyz']
        p_total_monthly_balance = saving['p_total_monthly_balance']
       

        boost = saving_log_data['boost']        


        if saving['completed_at']==None:
            contribution_breakdown = calculate_breakdown(
            starting_amount,
            contribution,
            interest, 
            goal_amount, 
            starting_date,
            repeat,
            i_contribution)

            breakdown = contribution_breakdown['breakdown']
            total_balance = contribution_breakdown['total_balance']
            total_balance_xyz = contribution_breakdown['total_balance_xyz']
            progress  = contribution_breakdown['progress']
            next_contribution_date = contribution_breakdown['next_contribution_date']
            goal_reached = contribution_breakdown['goal_reached']
            period = contribution_breakdown['period']
            is_single = contribution_breakdown['is_single']
            total_monthly_balance_xyz = contribution_breakdown['total_monthly_balance_xyz']

            len_breakdown = len(breakdown)

            if next_contribution_date == None:
                goal_reached = goal_reached if len_breakdown > 0 else None

            saving_contribution_data = None
            try:
                if len_breakdown > 0:
                    # Insert transactions into the database
                    if is_single > 0:
                        saving_contribution_data = SavingContribution(
                            saving_id=saving_id,                            
                            commit=commit,
                            user_id=user_id,
                            **breakdown
                        )
                        session.add(saving_contribution_data)
                    else:
                        saving_contribution_data = [
                            SavingContribution(
                                saving_id=saving_id,                                
                                commit=commit,
                                user_id=user_id,
                                **todo
                            ) for todo in breakdown
                        ]                                               
                        session.add_all(saving_contribution_data)

                    stmt_update = update(Saving).where(Saving.id == saving_id).values(
                            total_balance = total_balance,
                            total_balance_xyz = total_balance_xyz,
                            total_monthly_balance = total_monthly_balance_xyz,                   
                            progress = progress,
                            period = period,
                            commit=commit,  # Replace with the actual commit value                    
                        )
                    
                    session.execute(stmt_update)
                    session.commit()

                    update_data = {
                            "total_balance":total_balance,
                            "total_balance_xyz":total_balance_xyz,
                            "total_monthly_balance":total_monthly_balance_xyz,                            
                            "completed_at":datetime.now()
                    }

                    merged_dict  = {**saving,**update_data}

                    saving_log_data["saving"] = merged_dict
                    

                    newvalues = { "$set":  {
                        "saving":merged_dict 
                    } }


                    saving_accounts_logs.update_one(
                        saving_acc_query,
                        newvalues
                    )

            except Exception as ex:
                print('Income Update Exception: ', ex)
                session.rollback()
                return



        if len(boost) > 0:

            

            for k,b in boost.items():
                print(k,b)
                completed_at = b['completed_at']
                
                if completed_at!=None:
                    continue


                pay_date_boost = b['start_date']
                total_balance = 0
                repeat_boost =b['repeat_boost']
                saving_boost_id = b['id']
                saving_boost = b['contribution']
                pb_total_yearly_gross_saving += b['p_total_yearly_gross_saving']
                pb_total_yearly_net_saving += b['p_total_yearly_net_saving']
                pb_total_monthly_gross_saving += b['p_total_monthly_gross_saving']
                pb_total_monthly_net_saving += b['p_total_monthly_net_saving']
                
                

                if pay_date_boost <= today:
                    
                    if repeat_boost > 0:
                        contribution_data = generate_new_transaction_data_for_saving_boost(
                            total_balance,
                            saving_boost,
                            pay_date_boost,
                            repeat_boost,
                            commit,
                            saving_id,
                            saving_boost_id,
                            user_id,
                            total_gross_saving,
                            total_net_saving
                        )

                        saving_contribution_list = contribution_data['saving_contribution']
                        total_balance_b = contribution_data['total_boost_for_period']
                        total_gross_saving = contribution_data['total_gross_for_period']
                        total_net_saving = contribution_data['total_net_for_period']
                        next_contribution_date_b = contribution_data['next_pay_date']
                        is_single = contribution_data['is_single']
                        total_monthly_gross_saving_b = contribution_data['total_monthly_gross_saving']
                        total_monthly_net_saving_b = contribution_data['total_monthly_net_saving']
                        total_yearly_gross_saving_b = contribution_data['total_yearly_gross_saving']
                        total_yearly_net_saving_b = contribution_data['total_yearly_net_saving']

                        # Update the boost status
                        boost_status = {
                            'id': saving_boost_id,
                            'next_pay_date_boost': next_contribution_date_b,
                            'total_balance': total_balance_b,
                            'total_monthly_gross_saving':total_monthly_gross_saving_b,
                            'total_monthly_net_saving':total_monthly_net_saving_b,
                            'total_yearly_gross_saving':total_yearly_gross_saving_b,
                            'total_yearly_net_saving':total_yearly_net_saving_b,
                            'closed_at': None
                        }

                        total_monthly_gross_saving += total_monthly_gross_saving_b
                        total_monthly_net_saving += total_monthly_net_saving_b
                        total_yearly_gross_saving += total_yearly_gross_saving_b
                        total_yearly_net_saving += total_yearly_net_saving_b

                        # Update the saving record
                        update_data = {
                            "total_net_saving": total_net_saving,            
                            'total_gross_saving': total_gross_saving,
                            'total_monthly_gross_saving' :total_monthly_gross_saving,
                            'total_monthly_net_saving':total_monthly_net_saving,
                            'total_yearly_gross_saving':total_yearly_gross_saving,
                            'total_yearly_net_saving':total_yearly_net_saving,       
                            'updated_at': datetime.now()              
                        }

                        try:

                            if len(saving_contribution_list)> 0:
                                if is_single:
                                    session.add(IncomeTransaction(**saving_contribution_list))
                                else:
                                    session.add_all([IncomeTransaction(**entry) for entry in saving_contribution_list])

                            # Update the status of saving boost in the IncomeBoost model
                            session.query(IncomeBoost).filter_by(id=boost_status['id']).update({
                                'next_pay_date_boost': boost_status['next_pay_date_boost'],
                                'total_balance': boost_status['total_balance'],
                                'total_monthly_gross_saving': boost_status['total_monthly_gross_saving'],
                                'total_monthly_net_saving': boost_status['total_monthly_net_saving'],
                                'total_yearly_gross_saving': boost_status['total_yearly_gross_saving'],
                                'total_yearly_net_saving': boost_status['total_yearly_net_saving'],                        
                                'closed_at': boost_status['closed_at']
                            })

                            session.query(Income).filter_by(id=saving_id).update(update_data)
                            session.commit()
                            #update in mongo side
                            update_data = {
                                    "total_balance":total_balance_b,
                                    'total_monthly_gross_saving':total_monthly_gross_saving_b,
                                    'total_monthly_net_saving':total_monthly_net_saving_b,
                                    'total_yearly_gross_saving':total_yearly_gross_saving_b,
                                    'total_yearly_net_saving':total_yearly_net_saving_b,                                    
                                    "completed_at":datetime.now()
                            }

                            merged_dict  = {**b,**update_data}                
                            saving_log_data["boost"][k]=merged_dict 
                                                        
                        except Exception as ex:
                            print('Income Boost Save Exception: ',ex)
                            session.rollback()
                            return



                    else:
                        
                        contribution_breakdown_b = get_single_boost(
                                total_balance,
                                saving_boost,
                                pay_date_boost,
                                None,#repeat_boost,
                                total_gross_saving,
                                total_net_saving
                                )
                        breakdown_b = contribution_breakdown_b['saving_contribution']
                        total_balance_b = contribution_breakdown_b['total_boost_for_period']
                        total_gross_saving = contribution_breakdown_b['total_gross_for_period']
                        total_net_saving = contribution_breakdown_b['total_net_for_period']
                        next_contribution_date_b = contribution_breakdown_b['next_pay_date']
                        total_monthly_gross_saving_b = contribution_breakdown_b['total_monthly_gross_saving']
                        total_monthly_net_saving_b = contribution_breakdown_b['total_monthly_net_saving']
                        total_yearly_gross_saving_b = contribution_breakdown_b['total_yearly_gross_saving']
                        total_yearly_net_saving_b = contribution_breakdown_b['total_yearly_net_saving']

                            

                        saving_contribution_list = {
                                'saving_id':saving_id,
                                'saving_boost_id':saving_boost_id,
                                'commit':commit,
                                'user_id':user_id,
                                **breakdown_b
                        }

                        # Update the boost status
                        boost_status = {
                            'id': saving_boost_id,
                            'next_pay_date_boost': next_contribution_date_b,
                            'total_balance': total_balance_b,
                            'total_monthly_gross_saving' :total_monthly_gross_saving_b,
                            'total_monthly_net_saving':total_monthly_net_saving_b,
                            'total_yearly_gross_saving':total_yearly_gross_saving_b,
                            'total_yearly_net_saving':total_yearly_net_saving_b,
                            'closed_at': None
                        }

                        total_monthly_gross_saving += total_monthly_gross_saving_b
                        total_monthly_net_saving += total_monthly_net_saving_b
                        total_yearly_gross_saving += total_yearly_gross_saving_b
                        total_yearly_net_saving += total_yearly_net_saving_b

                        # Update the saving record
                        update_data = {
                            "total_net_saving": total_net_saving,            
                            'total_gross_saving': total_gross_saving,
                            'total_monthly_gross_saving' :total_monthly_gross_saving,
                            'total_monthly_net_saving':total_monthly_net_saving,
                            'total_yearly_gross_saving':total_yearly_gross_saving,
                            'total_yearly_net_saving':total_yearly_net_saving,       
                            'updated_at': datetime.now()              
                        }

                        print('Single Boost',update_data)        
                        

                        try:

                            session.add(IncomeTransaction(**saving_contribution_list))
                            # Update the status of saving boost in the IncomeBoost model
                            session.query(IncomeBoost).filter_by(id=boost_status['id']).update({
                                'next_pay_date_boost': boost_status['next_pay_date_boost'],
                                'total_balance': boost_status['total_balance'],
                                'total_monthly_gross_saving': boost_status['total_monthly_gross_saving'],
                                'total_monthly_net_saving': boost_status['total_monthly_net_saving'],
                                'total_yearly_gross_saving': boost_status['total_yearly_gross_saving'],
                                'total_yearly_net_saving': boost_status['total_yearly_net_saving'],                        
                                'closed_at': boost_status['closed_at']
                            })

                            session.query(Income).filter_by(id=saving_id).update(update_data)

                            session.commit()

                            #update in mongo side
                            update_data = {
                                    "total_balance":total_balance_b,
                                    'total_monthly_gross_saving':total_monthly_gross_saving_b,
                                    'total_monthly_net_saving':total_monthly_net_saving_b,
                                    'total_yearly_gross_saving':total_yearly_gross_saving_b,
                                    'total_yearly_net_saving':total_yearly_net_saving_b,                                    
                                    "completed_at":datetime.now()
                            }
                            merged_dict  = {**b,**update_data}                            
                            saving_log_data["boost"][k]=merged_dict
                            

                        except Exception as ex:
                                                                
                            print('Income Boost Save Exception: ',ex)                        
                            session.rollback()
                            return


            newvalues = { "$set":  {
                "boost":saving_log_data["boost"]
                
            } }


            saving_accounts_logs.update_one(
                saving_acc_query,
                newvalues
            )                 


        try:

            # # Log the monthly and yearly logs (if needed)
            # session.query(IncomeMonthlyLog).filter_by(saving_id=saving_id).update({
            #     'updated_at': None
            # })
            # session.query(IncomeYearlyLog).filter_by(saving_id=saving_id).update({
            #     'updated_at': None
            # })
            

            app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

            app_data.total_yearly_gross_saving -= p_total_yearly_gross_saving
            app_data.total_yearly_net_saving -= p_total_yearly_net_saving
            app_data.total_monthly_gross_saving -= p_total_monthly_gross_saving
            app_data.total_monthly_net_saving -= p_total_monthly_net_saving

            print('app_data deletion mode', app_data)

            app_data.total_yearly_gross_saving += total_yearly_gross_saving
            app_data.total_yearly_net_saving += total_yearly_net_saving
            app_data.total_monthly_net_saving += total_monthly_net_saving
            app_data.total_monthly_gross_saving +=total_monthly_gross_saving

            print('app_data addition mode', app_data)

            session.add(app_data)

            session.commit()

            newvalues = { "$set":  
                         {
                             "total_gross_saving":total_gross_saving,
                             "total_net_saving":total_net_saving,
                            "finished_at":datetime.now()
                                
                    }}


            saving_accounts_logs.update_one(
                saving_acc_query,
                newvalues
            )
        
        except Exception as ex:


            
                                                                
            print('IncomeMonthlyLog and IncomeYearlyLog Save Exception: ',ex)                        
            session.rollback()
            newvalues = { "$set":  
                         {
                             "total_gross_saving":0,
                             "total_net_saving":0,
                            "finished_at":None
                                
                    }}


            saving_accounts_logs.update_one(
                saving_acc_query,
                newvalues
            )    


    if session!=None:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Run functions from command line")
    
    # Define the command-line argument to run the function
    parser.add_argument('function', type=str, help="Name of the function to run")

    # Parse the arguments
    args = parser.parse_args()

    # Check if the specified function is available and run it
    if args.function == 'saving_tpros':
        saving_contribution_processing()
    else:
        print(f"Function {args.function} not recognized!")


if __name__ == '__main__':
    main()