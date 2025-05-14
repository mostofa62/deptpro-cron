from datetime import datetime
from sqlalchemy import func, update
from models import AppData, Income, IncomeBoost, IncomeMonthlyLog, IncomeTransaction, IncomeYearlyLog
from dbpg import SessionLocal
from db import my_col

from incomeutil import generate_new_transaction_data_for_income, generate_new_transaction_data_for_income_boost, get_single_boost, get_single_income
income_accounts_logs = my_col('income_accounts_logs')
import argparse

def income_transaction_processing():
    print('---INCOME TRANSACTION---')
    session = None
    try:
        session = SessionLocal()
    except Exception as ex:
        print('PGSQL ISSUE',ex)
        session = None
        return

    
    print('---INCOME TRANSACTION STARTED---')

    
    
    income_acc_query = {                
                "finished_at": None,                                
    }
    total_gross_income = 0
    total_net_income = 0 
    total_monthly_gross_income = 0
    total_monthly_net_income = 0
    total_yearly_gross_income = 0
    total_yearly_net_income = 0

    p_total_yearly_gross_income = 0
    p_total_yearly_net_income = 0
    p_total_monthly_gross_income = 0
    p_total_monthly_net_income = 0 

    pb_total_yearly_gross_income = 0
    pb_total_yearly_net_income = 0
    pb_total_monthly_gross_income = 0
    pb_total_monthly_net_income = 0

    income_log_data = income_accounts_logs.find_one(income_acc_query)
    income_transaction_data = []
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if income_log_data !=None:

        income_id = income_log_data['income_id']
        user_id = income_log_data['user_id']
        income_acc_query = {
                "income_id": income_id,                
                "user_id":user_id,
                
        }
        
        commit = income_log_data['commit']
        income_id = income_log_data['income_id']
        user_id = income_log_data['user_id']
        income = income_log_data['income']
        total_gross_income = income['total_gross_income']
        total_net_income = income['total_net_income']

        p_total_yearly_gross_income = income['p_total_yearly_gross_income']
        p_total_yearly_net_income = income['p_total_yearly_net_income']
        p_total_monthly_gross_income = income['p_total_monthly_gross_income']
        p_total_monthly_net_income = income['p_total_monthly_net_income']

        


        boost = income_log_data['boost']        


        if income['completed_at']==None:
            income_transaction_generate = generate_new_transaction_data_for_income(
                    income['gross_income'], 
                    income['net_income'], 
                    income['pay_date'], 
                    income['repeat'], 
                    commit, 
                    income_id, 
                    user_id
                )
            income_transaction_list = income_transaction_generate['income_transaction']
            total_gross_income = income_transaction_generate['total_gross_for_period']
            total_net_income = income_transaction_generate['total_net_for_period']
            next_pay_date = income_transaction_generate['next_pay_date']
            is_single = income_transaction_generate['is_single']
            total_monthly_gross_income = income_transaction_generate['total_monthly_gross_income']
            total_monthly_net_income = income_transaction_generate['total_monthly_net_income']
            total_yearly_gross_income = income_transaction_generate['total_yearly_gross_income']
            total_yearly_net_income = income_transaction_generate['total_yearly_net_income']

            income_transaction_data = None
            try:
                if len(income_transaction_list) > 0:
                    # Insert transactions into the database
                    if is_single > 0:
                        income_transaction_data = IncomeTransaction(**income_transaction_list)
                        session.add(income_transaction_data)
                    else:
                        income_transaction_data = [IncomeTransaction(**txn) for txn in income_transaction_list]
                        session.add_all(income_transaction_data)

                    stmt_update = update(Income).where(Income.id == income_id).values(
                            total_gross_income=total_gross_income,
                            total_net_income=total_net_income,
                            total_monthly_gross_income=total_monthly_gross_income,
                            total_monthly_net_income = total_monthly_net_income,
                            total_yearly_gross_income = total_yearly_gross_income,
                            total_yearly_net_income = total_yearly_net_income,                   
                            next_pay_date=next_pay_date,                      
                            commit=commit,  # Replace with the actual commit value                    
                        )
                    
                    session.execute(stmt_update)
                    session.commit()

                    update_data = {
                            "total_gross_income":total_gross_income,
                            "total_net_income":total_net_income,
                            "total_monthly_gross_income":total_monthly_gross_income,
                            "total_monthly_net_income":total_monthly_net_income,
                            "total_yearly_gross_income":total_yearly_gross_income,
                            "total_yearly_net_income":total_yearly_net_income,                                                        
                            "completed_at":datetime.now()
                    }

                    merged_dict  = {**income,**update_data}

                    income_log_data["income"] = merged_dict
                    

                    newvalues = { "$set":  {
                        "income":merged_dict 
                    } }


                    income_accounts_logs.update_one(
                        income_acc_query,
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
                income_boost_id = b['id']
                income_boost = b['contribution']
                pb_total_yearly_gross_income += b['p_total_yearly_gross_income']
                pb_total_yearly_net_income += b['p_total_yearly_net_income']
                pb_total_monthly_gross_income += b['p_total_monthly_gross_income']
                pb_total_monthly_net_income += b['p_total_monthly_net_income']
                
                

                if pay_date_boost <= today:
                    
                    if repeat_boost > 0:
                        contribution_data = generate_new_transaction_data_for_income_boost(
                            total_balance,
                            income_boost,
                            pay_date_boost,
                            repeat_boost,
                            commit,
                            income_id,
                            income_boost_id,
                            user_id,
                            total_gross_income,
                            total_net_income
                        )

                        income_transaction_list = contribution_data['income_transaction']
                        total_balance_b = contribution_data['total_boost_for_period']
                        total_gross_income = contribution_data['total_gross_for_period']
                        total_net_income = contribution_data['total_net_for_period']
                        next_contribution_date_b = contribution_data['next_pay_date']
                        is_single = contribution_data['is_single']
                        total_monthly_gross_income_b = contribution_data['total_monthly_gross_income']
                        total_monthly_net_income_b = contribution_data['total_monthly_net_income']
                        total_yearly_gross_income_b = contribution_data['total_yearly_gross_income']
                        total_yearly_net_income_b = contribution_data['total_yearly_net_income']

                        # Update the boost status
                        boost_status = {
                            'id': income_boost_id,
                            'next_pay_date_boost': next_contribution_date_b,
                            'total_balance': total_balance_b,
                            'total_monthly_gross_income':total_monthly_gross_income_b,
                            'total_monthly_net_income':total_monthly_net_income_b,
                            'total_yearly_gross_income':total_yearly_gross_income_b,
                            'total_yearly_net_income':total_yearly_net_income_b,
                            'closed_at': None
                        }

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

                        try:

                            if len(income_transaction_list)> 0:
                                if is_single:
                                    session.add(IncomeTransaction(**income_transaction_list))
                                else:
                                    session.add_all([IncomeTransaction(**entry) for entry in income_transaction_list])

                            # Update the status of income boost in the IncomeBoost model
                            session.query(IncomeBoost).filter_by(id=boost_status['id']).update({
                                'next_pay_date_boost': boost_status['next_pay_date_boost'],
                                'total_balance': boost_status['total_balance'],
                                'total_monthly_gross_income': boost_status['total_monthly_gross_income'],
                                'total_monthly_net_income': boost_status['total_monthly_net_income'],
                                'total_yearly_gross_income': boost_status['total_yearly_gross_income'],
                                'total_yearly_net_income': boost_status['total_yearly_net_income'],                        
                                'closed_at': boost_status['closed_at']
                            })

                            session.query(Income).filter_by(id=income_id).update(update_data)
                            session.commit()
                            #update in mongo side
                            update_data = {
                                    "total_balance":total_balance_b,
                                    'total_monthly_gross_income':total_monthly_gross_income_b,
                                    'total_monthly_net_income':total_monthly_net_income_b,
                                    'total_yearly_gross_income':total_yearly_gross_income_b,
                                    'total_yearly_net_income':total_yearly_net_income_b,                                    
                                    "completed_at":datetime.now()
                            }

                            merged_dict  = {**b,**update_data}                
                            income_log_data["boost"][k]=merged_dict 
                                                        
                        except Exception as ex:
                            print('Income Boost Save Exception: ',ex)
                            session.rollback()
                            return



                    else:
                        
                        contribution_breakdown_b = get_single_boost(
                                total_balance,
                                income_boost,
                                pay_date_boost,
                                None,#repeat_boost,
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
                        boost_status = {
                            'id': income_boost_id,
                            'next_pay_date_boost': next_contribution_date_b,
                            'total_balance': total_balance_b,
                            'total_monthly_gross_income' :total_monthly_gross_income_b,
                            'total_monthly_net_income':total_monthly_net_income_b,
                            'total_yearly_gross_income':total_yearly_gross_income_b,
                            'total_yearly_net_income':total_yearly_net_income_b,
                            'closed_at': None
                        }

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
                        

                        try:

                            session.add(IncomeTransaction(**income_transaction_list))
                            # Update the status of income boost in the IncomeBoost model
                            session.query(IncomeBoost).filter_by(id=boost_status['id']).update({
                                'next_pay_date_boost': boost_status['next_pay_date_boost'],
                                'total_balance': boost_status['total_balance'],
                                'total_monthly_gross_income': boost_status['total_monthly_gross_income'],
                                'total_monthly_net_income': boost_status['total_monthly_net_income'],
                                'total_yearly_gross_income': boost_status['total_yearly_gross_income'],
                                'total_yearly_net_income': boost_status['total_yearly_net_income'],                        
                                'closed_at': boost_status['closed_at']
                            })

                            session.query(Income).filter_by(id=income_id).update(update_data)

                            session.commit()

                            #update in mongo side
                            update_data = {
                                    "total_balance":total_balance_b,
                                    'total_monthly_gross_income':total_monthly_gross_income_b,
                                    'total_monthly_net_income':total_monthly_net_income_b,
                                    'total_yearly_gross_income':total_yearly_gross_income_b,
                                    'total_yearly_net_income':total_yearly_net_income_b,                                    
                                    "completed_at":datetime.now()
                            }
                            merged_dict  = {**b,**update_data}                            
                            income_log_data["boost"][k]=merged_dict
                            

                        except Exception as ex:
                                                                
                            print('Income Boost Save Exception: ',ex)                        
                            session.rollback()
                            return


            newvalues = { "$set":  {
                "boost":income_log_data["boost"]
                
            } }


            income_accounts_logs.update_one(
                income_acc_query,
                newvalues
            )                 


        try:

            # # Log the monthly and yearly logs (if needed)
            # session.query(IncomeMonthlyLog).filter_by(income_id=income_id).update({
            #     'updated_at': None
            # })
            # session.query(IncomeYearlyLog).filter_by(income_id=income_id).update({
            #     'updated_at': None
            # })
            

            app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

            app_data.total_yearly_gross_income -= p_total_yearly_gross_income
            app_data.total_yearly_net_income -= p_total_yearly_net_income
            app_data.total_monthly_gross_income -= p_total_monthly_gross_income
            app_data.total_monthly_net_income -= p_total_monthly_net_income

            print('app_data deletion mode', app_data)

            app_data.total_yearly_gross_income += total_yearly_gross_income
            app_data.total_yearly_net_income += total_yearly_net_income
            app_data.total_monthly_net_income += total_monthly_net_income
            app_data.total_monthly_gross_income +=total_monthly_gross_income

            print('app_data addition mode', app_data)

            session.add(app_data)

            session.commit()

            newvalues = { "$set":  
                         {
                             "total_gross_income":total_gross_income,
                             "total_net_income":total_net_income,
                            "finished_at":datetime.now()
                                
                    }}


            income_accounts_logs.update_one(
                income_acc_query,
                newvalues
            )
        
        except Exception as ex:


            
                                                                
            print('IncomeMonthlyLog and IncomeYearlyLog Save Exception: ',ex)                        
            session.rollback()
            newvalues = { "$set":  
                         {
                             "total_gross_income":0,
                             "total_net_income":0,
                            "finished_at":None
                                
                    }}


            income_accounts_logs.update_one(
                income_acc_query,
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
    if args.function == 'income_tpros':
        income_transaction_processing()
        
    else:
        print(f"Function {args.function} not recognized!")


if __name__ == '__main__':
    main()