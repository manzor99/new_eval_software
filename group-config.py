import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import itertools
from database_setup import Student, Base, Groups, Semester, Group_Student, Enrollment, Evaluation, EncryptedEvaluation
from ConfigParser import SafeConfigParser
from encrypt import EvalCipher
from sqlalchemy import func, and_
import csv
import openpyxl
from collections import deque

parser = SafeConfigParser()
parser.read('config.ini')
username = parser.get('login', 'username')
password = parser.get('login', 'password')
schema = parser.get('login', 'schema')
host = parser.get('login', 'host')
port = parser.get('login', 'port')

engine = create_engine('mysql+pymysql://' + username + ':' + password + '@' + host +':' + port + '/' + schema)
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

file = open('group-config.csv', 'rb')
reader = csv.reader(file, delimiter=',')
next(reader)
print 'Populating group configuration data...'

try:
    if requested_operation == 'add':
        for row in reader:
            year = row[0].strip()
            season = row[1].strip()
            course_no = row[2].strip()
            week = row[3].strip()
            assignment_name = row[4].strip()
            group_name = row[5].strip()
            student_id = row[6].strip()
            is_manager = row[7].strip()
                    
            semester = session.query(Semester).filter_by(year=year, season=season, course_no=course_no).first()
            if semester == None:
                print 'One or more semester configuration not found.'
                sys.exit(10)
                
            group = session.query(Groups).filter_by(semester=semester, week=week, name=group_name).first()
            if group == None:
                group = Groups(semester=semester, week=week, name=group_name, assignment_name=assignment_name)
                session.add(group)
            
            student = session.query(Student).filter_by(user_name=student_id).first()
            if student == None:
                print 'One or more student configuration not found. (' + student_id + ')'
                sys.exit(11)
             
            group_student = session.query(Group_Student).filter_by(groups=group, student=student, is_manager = is_manager).first()
            if group_student == None:
                group_student = Group_Student(groups=group, student=student, is_manager = is_manager)
                session.add(group_student)
    else:
        file_tmp = open('group-config.csv', 'rb')
        lastLine = deque(csv.reader(file_tmp, delimiter=','), 1)[0]
        year = lastLine[0].strip()
        season = lastLine[1].strip()
        course_no = lastLine[2].strip()
        week = lastLine[3].strip()
        current_semester = session.query(Semester).filter_by(year=year, season=season, course_no=course_no).first()
        
        if requested_operation == 'update':
            max_week = session.query(func.max(Groups.week)).filter_by(semester=current_semester).scalar()
            session.query(Groups).filter_by(semester=current_semester, week=max_week).delete()
            
            for row in reader:
                year = row[0].strip()
                season = row[1].strip()
                course_no = row[2].strip()
                week = row[3].strip()
                assignment_name = row[4].strip()
                group_name = row[5].strip()
                student_id = row[6].strip()
                is_manager = row[7].strip()
                    
                semester = session.query(Semester).filter_by(year=year, season=season, course_no=course_no).first()
                if semester == None:
                    print 'One or more semester configuration not found.'
                    sys.exit(10)
                    
                group = session.query(Groups).filter_by(semester=semester, week=week, name=group_name).first()
                if group == None:
                    group = Groups(semester=semester, week=week, name=group_name, assignment_name=assignment_name)
                    session.add(group)
                
                student = session.query(Student).filter_by(user_name=student_id).first()
                if student == None:
                    print 'One or more student configuration not found. (' + student_id + ')'
                    sys.exit(11)
                 
                group_student = Group_Student(groups=group, student=student, is_manager = is_manager)
                session.add(group_student)        
    session.commit()
    print "Configuration data successfully populated."
    session.close()
except Exception as e:
    print "Error populating group configuration tables.", str(e)

