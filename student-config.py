import sys
sys.path.append("lib/python2.7/site-packages/")
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

engine = create_engine('mysql://' + username + ':' + password + '@' + host +':' + port + '/' + schema) 
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

file = open('student-config.csv', 'rb')
reader = csv.reader(file, delimiter=',')
next(reader)
print 'Populating student configuration data...'

try:
    if requested_operation == 'add':
        for row in reader:
            year = row[0].strip()
            season = row[1].strip()
            course_no = row[2].strip()
            user_name = row[3].strip()
            first_name = row[4].strip()
            last_name = row[5].strip()
            email = row[6].strip()
            alias_name = row[7].strip()
            
            
            
            semester = session.query(Semester).filter_by(year=year, season=season, course_no=course_no).first()
            if semester == None:
                print 'One or more semester configuration not found for: ' + year +' ' + season + ' ' + course_no
                sys.exit(10)
                
            is_student_exists = session.query(Student).filter_by(user_name=user_name).count()
            is_student_enrolled = session.query(Enrollment).filter_by(student_id=user_name, semester=semester).count()
            
            if is_student_exists == 0:
                student = Student(user_name=user_name, first_name=first_name, last_name=last_name, email=email, alias_name=alias_name)
                enrollment = Enrollment(student=student, semester=semester)
                session.add(student)
                session.add(enrollment)
            else:
                if is_student_enrolled == 0:
                    student = session.query(Student).filter_by(user_name=user_name).first()
                    enrollment = Enrollment(student=student, semester=semester)
                    session.add(enrollment)    
    elif requested_operation == 'update':            
        for row in reader:
            year = row[0].strip()
            season = row[1].strip()
            course_no = row[2].strip()
            user_name = row[3].strip()
            first_name = row[4].strip()
            last_name = row[5].strip()
            email = row[6].strip()
            alias_name = row[7].strip()
            
            semester = session.query(Semester).filter_by(year=year, season=season, course_no=course_no).first()
            if semester == None:
                print 'One or more semester configuration not found for: ' + year +' ' + season + ' ' + course_no
                sys.exit(11)
                
            is_student_exists = session.query(Student).filter_by(user_name=user_name).count()
            is_student_enrolled = session.query(Enrollment).filter_by(student_id=user_name, semester=semester).count()
            
            if is_student_exists > 0:
                student = session.query(Student).filter_by(user_name=user_name).first()
                student.first_name = first_name
                student.last_name = last_name
                student.email = email
                student.alias_name = alias_name
                
    session.commit()
    print "Student configuration tables successfully populated."
except Exception as e:
    print "Error populating student configuration tables.", str(e)
