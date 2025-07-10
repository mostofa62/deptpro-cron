from datetime import datetime
from sqlalchemy import Integer, and_, cast, extract, func, or_, select, update
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

        monthly_contribution_subq = (
            select(func.coalesce(func.sum(SC.contribution_i_intrs), 0.0))
            .where(
                SC.saving_id == Saving.id,
                SC.commit == Saving.commit,
                SC.month == cast(func.to_char(Saving.next_contribution_date, 'YYYYMM'), Integer)
            )
            .scalar_subquery()
        )

        query = (
            session.query(
                Saving.id,
                Saving.user_id,
                Saving.next_contribution_date,
                Saving.total_balance_xyz,
                Saving.interest,
                Saving.interest_type,
                Saving.increase_contribution_by,
                Saving.savings_strategy,
                Saving.period,               
                Saving.commit,
                Saving.repeat,
                monthly_contribution_subq.label("p_total_monthly_balance"),
                
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