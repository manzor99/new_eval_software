import os
import sys
sys.path.append("lib/python2.7/site-packages/")
from sqlalchemy import Column, ForeignKey, Integer, String, VARCHAR, TIMESTAMP, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from ConfigParser import SafeConfigParser
from database_setup import Student, Base, Groups, Semester, Group_Student, Enrollment, Evaluation, EncryptedEvaluation, EvalForm, EvalListForm
from encrypt import EvalCipher

course_no = 'P532'
parser = SafeConfigParser()
parser.read('config.ini')
username = parser.get('login', 'username')
password = parser.get('login', 'password')
schema = parser.get('login', 'schema')
host = parser.get('login', 'host')
port = parser.get('login', 'port')
key = parser.get('security', 'key')

evalCipher = EvalCipher(key)

engine = create_engine('mysql://' + username + ':' + password + '@' + host +':' + port + '/' + schema) 
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

Base0 = declarative_base()
#OLD DB CREDENTIALS
exit
#PASSWORD = regular mysql password
engine0 = create_engine('mysql://eval:PASSWORD@tintin.cs.indiana.edu:8099/eval')  



Base0.metadata.bind = engine0
DBSession0 = sessionmaker(bind=engine0)
session0 = DBSession0()

class Semester0(Base0):  
    __tablename__ = 'SEMESTER'
    __table_args__ = (
            UniqueConstraint('YEAR', 'SEASON'),
            )
    YEAR = Column(Integer, nullable=False)
    SEASON = Column(VARCHAR(11), nullable=False)
    CREATE_TIME = Column(TIMESTAMP, nullable=False, server_default=func.now())
    ID = Column(Integer, primary_key=True, autoincrement=True)
    def convert(self):
        semester = Semester()
        semester.id = self.ID
        semester.year = self.YEAR
        semester.season = self.SEASON
        semester.create_time = self.CREATE_TIME
        semester.course_no = course_no
        return semester
        
class Student0(Base0):
    __tablename__ = 'STUDENT'
    USER_NAME = Column(VARCHAR(10), primary_key=True)
    FIRST_NAME = Column(VARCHAR(50), nullable=False)
    LAST_NAME = Column(VARCHAR(50), nullable=False)
    EMAIL = Column(VARCHAR(50))
    CREATE_TIME = Column(TIMESTAMP, nullable=False, server_default=func.now())
    SEMESTER_ID = Column(Integer, ForeignKey('SEMESTER.ID', onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    IU_USER_NAME = Column(VARCHAR(10), nullable=False)
    SEMESTER = relationship(Semester0)

    def convert(self):
        student = Student()
        student.user_name = self.USER_NAME
        student.first_name = self.FIRST_NAME
        student.last_name = self.LAST_NAME
        student.email = self.EMAIL
        student.create_time = self.CREATE_TIME
        semester = session.query(Semester).filter_by(id=self.SEMESTER_ID).first()
        if semester == None:
            print 'Semester Not found for:'
            print self.USER_NAME
        enrollment = Enrollment(student=student, semester=semester)
        if enrollment == None:
            print 'Enrollment Not populated for:'
            print self.USER_NAME
        return student, enrollment
    
class Evaluation0(Base0):
    __tablename__ = 'EVALUATION'

    EVALER_ID = Column(VARCHAR(10), ForeignKey(Student0.USER_NAME, onupdate="CASCADE", ondelete="CASCADE"), primary_key=True, autoincrement=False)
    EVALEE_ID = Column(VARCHAR(10), ForeignKey(Student0.USER_NAME, onupdate="CASCADE", ondelete="CASCADE"), primary_key=True, autoincrement=False)
    WEEK = Column(Integer, primary_key=True, autoincrement=False)
    RANK = Column(Integer, nullable=False)
    TOKEN = Column(Integer, nullable=False)
    DESCRIPTION = Column(String(4096), nullable=False)
    SUBMISSION_TIME = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.current_timestamp())
    ADJ = Column(String(128), nullable=False)
    TYPE = Column(Integer, nullable=False, server_default='1')
    evaler = relationship(Student0, foreign_keys='Evaluation0.EVALER_ID')
    evalee = relationship(Student0, foreign_keys='Evaluation0.EVALEE_ID')
    def convert(self):
        evaluation = Evaluation()
        evaluation.evaler_id = self.EVALER_ID
        evaluation.evalee_id = self.EVALEE_ID
        evaluation.week = self.WEEK
        evaluation.rank = self.RANK
        evaluation.token = self.TOKEN
        evaluation.description = self.DESCRIPTION
        evaluation.submission_time = self.SUBMISSION_TIME
        evaluation.adjective = self.ADJ
        enrollment = session.query(Enrollment).filter_by(   student_id=self.EVALER_ID  ).first()
        if enrollment == None:
            enrollment_tmp = session.query(Enrollment).filter_by(student_id=self.EVALER_ID).all()
            if enrollment_tmp == None:
                print 'No record found in enrollment table.'
            else:    
                for element in enrollment_tmp:
                    print element.student_id, element.semester_id
        evaluation.semester_id = enrollment.semester_id
        evaluation.semester = enrollment.semester
        evaluation.evaler = session.query(Student).filter_by(user_name=self.EVALER_ID).first()
        evaluation.evalee = session.query(Student).filter_by(user_name=self.EVALEE_ID).first()
        return evalCipher.encryptEval(evaluation)
        
        

class Groups0(Base0):
    __tablename__ = 'GROUPS'
    SEMESTER_ID = Column(Integer, ForeignKey('SEMESTER.ID', onupdate="CASCADE", ondelete="CASCADE"))
    WEEK = Column(Integer, nullable=False)
    ID = Column(Integer, primary_key=True, autoincrement=True)
    NAME =  Column(VARCHAR(50))
    SEMESTER = relationship(Semester0)
    CREATE_TIME = Column(TIMESTAMP, nullable=False, server_default=func.now())
    def convert(self):
        group = Groups();
        group.semester_id = self.SEMESTER_ID
        group.week = self.WEEK
        group.id = self.ID
        group.name = self.NAME
        group.create_time = self.CREATE_TIME
        semester = session.query(Semester).filter_by(id=self.SEMESTER_ID).first()
        group.semester = semester
        return group

    
class Group_Student0(Base0):
    __tablename__ = 'GROUP_STUDENT'
    GROUP_ID = Column(Integer, ForeignKey('GROUPS.ID', onupdate="CASCADE", ondelete="CASCADE"), primary_key=True)
    STUDENT_ID = Column(VARCHAR(10), ForeignKey('STUDENT.USER_NAME', onupdate="CASCADE", ondelete="CASCADE"), primary_key=True)
    STUDENT = relationship(Student0)
    GROUPS = relationship(Groups0)
    
    def convert(self):
        group_student = Group_Student()
        group_student.group_id = self.GROUP_ID
        group_student.student_id = self.STUDENT_ID
        groups = session.query(Groups).filter_by(id=self.GROUP_ID).first()
        student = session.query(Student).filter_by(user_name=self.STUDENT_ID).first()
        group_student.student = student
        group_student.groups = groups
        return group_student
        

if __name__ == '__main__':
    semesters0 = session0.query(Semester0).all();
    for semester0 in semesters0:
        semester = semester0.convert()
        session.add(semester)
    students0 = session0.query(Student0).all()
    for student0 in students0:
        student, enrollment = student0.convert()
        session.add(student)
        session.add(enrollment)
        
    groups0 = session0.query(Groups0).all()
    for group0 in groups0:
        group = group0.convert()
        session.add(group)
    
    group_students0 = session0.query(Group_Student0).all()
    for group_student0 in group_students0:
        group_student = group_student0.convert()
        session.add(group_student)

    evaluations0 = session0.query(Evaluation0).all()
    for evaluation0 in evaluations0:
        encryptedEvaluation = evaluation0.convert()
        session.add(encryptedEvaluation)
        
    #exit()
    #quit()
    session.commit()
