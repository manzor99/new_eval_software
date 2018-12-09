import sys
import os
lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'lib/python2.7/site-packages'))
# sys.path.append("./lib/python2.7/site-packages/")
sys.path.append(lib_path)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Student, Base, Groups, Semester, Group_Student, Enrollment, Evaluation, EncryptedEvaluation
from ConfigParser import SafeConfigParser
from encrypt import EvalCipher
from sqlalchemy import func, and_
import csv
import openpyxl

parser = SafeConfigParser()
parser.read('config.ini')
username = parser.get('login', 'username')
password = parser.get('login', 'password')
schema = parser.get('login', 'schema')
host = parser.get('login', 'host')
port = parser.get('login', 'port')

engine = create_engine(
    'mysql+pymysql://' + "praneta" + ':' + "praneta25" + '@' + "mysqldb.c76lby8pfil5.us-east-2.rds.amazonaws.com" + ':' + "3306" + '/' + "Evaluation")

# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()

requested_operation = None

num_of_arguments = len(sys.argv)
if num_of_arguments == 2:
    requested_operation = sys.argv[1]
else:
    print 'Incorrect number of arguments specified.'
    sys.exit(10)

if requested_operation != 'add' and requested_operation != 'update':
    print 'Invalid argument specified.'
    sys.exit(11)
    
file = open('semester-config.csv', 'rb')
reader = csv.reader(file, delimiter=',')
next(reader)
print 'Populating semester configuration data...'

try:
    if requested_operation == 'add':
        for row in reader:
            year = row[0].strip()
            season = row[1].strip()
            course_no = row[2].strip()
            
            is_semester_exists = session.query(Semester).filter_by(year=year, season=season, course_no=course_no).count()
            
            if is_semester_exists == 0:
                session.add(Semester(year=year, season=season, course_no=course_no))
    else:    
        for row in reader:
            year = row[0].strip()
            season = row[1].strip()
            course_no = row[2].strip()
        
            is_semester_exists = session.query(Semester).filter_by(year=year, season=season, course_no=course_no).count()
            if is_semester_exists > 0:
                semester = session.query(Semester).filter_by(year=year, season=season, course_no=course_no).first()
                semester.year = year
                semester.season = season
                semester.course_no = course_no
            
    session.commit()
    session.close()
    print "Semester configuration successfully populated."
except Exception as e:
    print "Error populating Semester configuration.", str(e)
