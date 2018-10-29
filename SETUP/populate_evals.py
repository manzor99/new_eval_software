import sys
sys.path.append("lib/python2.7/site-packages/")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Student, Base, Groups, Semester, Group_Student, Enrollment, Evaluation, EncryptedEvaluation
from ConfigParser import SafeConfigParser
from encrypt import EvalCipher
import csv

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

evals = []
semester1 = session.query(Semester).filter_by(year=2015, season="Fall", course_no="P532").first()
#evals

with open('evals.csv', 'rb') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
      #print(row['evaler'],row['evalee'],row['week'],row['rank'],row['token'],row['description'],row['adjective'])
      evaler1 = session.query(Student).filter_by(user_name=row['evaler']).first()
      evalee1 = session.query(Student).filter_by(user_name=row['evalee']).first()
      eval1 = Evaluation(evaler=evaler1, evalee=evalee1, week=row['week'], rank=row['rank'],token=row['token'], description=row['description'], adjective=row['adjective'], semester=semester1)
      evals.append(eval1)

key = 'keyskeyskeyskeys'
evalCipher = EvalCipher(key)

for eval in evals:
    encryptedEval = evalCipher.encryptEval(eval)
    session.add(encryptedEval)
session.commit()
print "DAta inserted Successfully"
session.close()