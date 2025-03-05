
import math

from datetime import datetime


def are_floats_equal(a,b):
    return math.isclose(a, b, rel_tol=1e-9)


def convertStringTodate(date_string:str, format:str="%Y-%m-%d"):
    date_timestamp = None
    if date_string!=None and date_string!='':
        date_timestamp = datetime.strptime(date_string,format)

    return date_timestamp

def convertDateTostring(date_obj, format:str="%d %b, %Y"):
    date_string = None
    if date_obj!=None:
        date_string = date_obj.strftime(format)

    return date_string


def convertNumberToDate(num,format:str="%b, %Y"):
    year = int(str(num)[:4])
    month = int(str(num)[4:])
    date_obj = datetime(year, month, 1)
    return date_obj.strftime(format)  # "Feb 2025"


