import sys
import os
lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'lib/python2.7/site-packages'))
# sys.path.append("./lib/python2.7/site-packages/")
sys.path.append(lib_path)

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

import os
from flask import Flask, flash, render_template, url_for, request, redirect, session, jsonify
from sqlalchemy import create_engine, distinct
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
from sqlalchemy import exc
from database_setup import Student, Base, Groups, Semester, Group_Student, Enrollment, Evaluation, EncryptedEvaluation, EvalForm, EvalListForm, Manager_Eval, ResetPassword, ResetPasswordSubmit
from ConfigParser import SafeConfigParser
from encrypt import EvalCipher
from highcharts import Highchart
from itertools import groupby
from sqlalchemy import func, and_
from sqlalchemy.orm import aliased
from sqlalchemy.sql import exists
from wtforms.validators import DataRequired
from wtforms import Form
from werkzeug.datastructures import MultiDict
import itertools
import ast
from flask_mail import Mail, Message
from itsdangerous import URLSafeSerializer
import socket
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta
from flask_cors import CORS, cross_origin
#for https
from OpenSSL import SSL

context = SSL.Context(SSL.SSLv23_METHOD)
#cer = os.path.join(os.path.dirname(__file__), 'certificate/tintin.cs.indiana.edu.crt')
#ssl_key = os.path.join(os.path.dirname(__file__), 'certificate/tintin.cs.indiana.edu.key')
cer = os.path.join(os.path.dirname(__file__), 'certificate/snowy.sice.indiana.edu.cer')
ssl_key = os.path.join(os.path.dirname(__file__), 'certificate/snowy.sice.indiana.edu.key')



parser = SafeConfigParser()
parser.read('config.ini')

username = parser.get('login', 'username')
password = parser.get('login', 'password')
schema = parser.get('login', 'schema')
host = parser.get('login', 'host')
port = parser.get('login', 'port')

#key = parser.get('security', 'key')

MAIL_SERVER = parser.get('email', 'MAIL_SERVER')
MAIL_PORT = parser.get('email', 'MAIL_PORT')
MAIL_USE_SSL = ast.literal_eval(parser.get('email', 'MAIL_USE_SSL'))
MAIL_DEFAULT_SENDER = parser.get('email', 'MAIL_DEFAULT_SENDER')

APP_HOST = parser.get('apprun', 'host')
APP_PORT = parser.get('apprun', 'port')

CURRENT_SEASON = parser.get('currentsem', 'season')
CURRENT_YEAR = int(parser.get('currentsem', 'year'))
CURRENT_COURSE_NO = parser.get('currentsem', 'course_no')
# CURRENT_WEEK = date(parser.get('currentsem', 'first_monday'))
LOGGING_LEVEL = parser.get('logs', 'LOGGING_LEVEL')

GOOD_ADJECTIVES = parser.get('adjectives', 'GOOD_ADJECTIVES').replace(' ','').split(",")
BAD_ADJECTIVES = parser.get('adjectives', 'BAD_ADJECTIVES').replace(' ','').split(",")
GOOD_ADJECTIVES.sort()
BAD_ADJECTIVES.sort()

LIMIT_EVALS_TO_CURRENT_WEEK = parser.get('limitevals', 'LIMIT_TO_CURRENT_WEEK')

parser.read('semester_encryption_keys.ini')
key = parser.get('encryptionkeys', CURRENT_SEASON + '-' + str(CURRENT_YEAR) + '-' + CURRENT_COURSE_NO)

app = Flask(__name__)
app.config['CSRF_ENABLED'] = True
app.config['SECRET_KEY'] = key

app.config["MAIL_SERVER"] = MAIL_SERVER
app.config["MAIL_PORT"] = MAIL_PORT
app.config["MAIL_USE_SSL"] = MAIL_USE_SSL
app.config["MAIL_DEFAULT_SENDER"] = MAIL_DEFAULT_SENDER
app.permanent_session_lifetime = timedelta(seconds=10800)

mail = Mail(app)
dbSession = None

#print 'key:', key
evalCipher = EvalCipher(key)
urlSerializer = URLSafeSerializer(key)

#Create SessionMaker just once
#engine = create_engine('mysql://' + username + ':' + password + '@' + host +':' + port + '/' + schema, pool_size=0, pool_recycle=14400)

##TRYING NULLPOOL
engine = create_engine('mysql+pymysql://' + username + ':' + password + '@' + host +':' + port + '/' + schema, poolclass=NullPool )


try:
    engine.connect()
    Base.metadata.bind = engine
    DBSession = sessionmaker(autoflush=True, bind=engine)
except Exception as e:
    app.logger.error(e)


def init_dbSession():
    global dbSession
    global DBSession
    app.logger.debug('Attempting DB connection via: '+ username)
    try:
        engine.connect()
        Base.metadata.bind = engine
        DBSession = sessionmaker(autoflush=True, bind=engine)
        dbSession = DBSession()
        return
    except Exception as e:
        app.logger.debug(e)
        app.logger.error(e)
        return render_template("error.html")

@app.route('/save-eval', methods=['POST'])
def saveEval():
    app.logger.debug('inside list_all')
    semester = dbSession.query(Semester).filter_by(year=CURRENT_YEAR, season=CURRENT_SEASON, course_no=CURRENT_COURSE_NO).first()
    finalEvals = []
    try:
        if not session.get('app_user'):
            clear_DBsession()
            app.logger.debug('clear_DBsession')
            return redirect(url_for('login'))
        app_user = session['app_user']
        app.logger.debug('Currently logged in user : '+ app_user)
        evals = request.get_json()
        print("evals team", evals['team'][0]['username'])
        evaler = session.get('app_user')
        print("semester: ", semester)

        weekQuery = dbSession.query(Groups).filter_by().all()
        weekNumberList = []
        for item in weekQuery:
            weekNumberList.append(int(item.week))
        weekNumber = max(weekNumberList)
        #evaluation = Evaluation(evaler=evaler, evalee=evalee, week=eval['week'].data, rank=eval['rank'].data, token=eval['tokens'].data, description=eval['description'].data, adjective=eval['adjective'].data, encryptedManagerEval=encryptedManagerEval, semester=semester)
        print("evals =", evals)
        for eval in evals['team']:
            print("eval =", eval)
            evalee = eval['username']
            encryptedManagerEval = None
            if eval['is_manager'] == 1:
                print "inside is_manager"
                managerEval = Manager_Eval(approachable_attitude = eval['approachable'],
                            team_communication = eval['communication'],
                            client_interaction = eval['client_interaction'],
                            decision_making = eval['decision_making'],
                            resource_utilization = eval['resource_utilization'],
                            follow_up_to_completion = eval['follow_up_to_completion'],
                            task_delegation_and_ownership = eval['task_delegation_and_ownership'],
                            encourage_team_development = eval['encourage_team_development'],
                            realistic_expectation = eval['realistic_expectation'],
                            performance_under_stress = eval['performance_under_stress'],
                            mgr_description = 'None')
                encryptedManagerEval = evalCipher.encryptManagerEval(managerEval)
                dbSession.add(encryptedManagerEval)
            evaluation = Evaluation(evaler=evaler,
                                    evalee=evalee,
                                    week=weekNumber,
                                    rank=eval['evaluation']['rank'],
                                    token=eval['evaluation']['tokens'],
                                    description=eval['evaluation']['description'],
                                    adjective=eval['evaluation']['adjective'],
                                    encryptedManagerEval=encryptedManagerEval,
                                    semester=semester)
            finalEvals.append(evaluation)
        for e in finalEvals:
            encryptedEval = evalCipher.encryptEval(e)
            dbSession.add(encryptedEval) #Line of code causing the error
        try:
            dbSession.commit()
        except exc.InvalidRequestError as e:
            dbSession.rollback()
            app.logger.error(e)
            app.logger.error('Rolling back invalid transaction.')
            errorDict = {}
            errorDict['message'] = str(e)
            errorDict['code'] = 400
            return jsonify(errorDict)
        app.logger.debug('dbsession commit')
        print ( app_user )
        clear_session(  )
        successDict = {}
        successDict['code'] = 200
        successDict['message'] = "The data was save to the database"
        return jsonify(successDict)
    except Exception as e:
        app.logger.debug(e)
        if dbSession is not None:
            dbSession.rollback()
        clear_DBsession()
        app.logger.error(e)
        errorDict = {}
        errorDict['message'] = str(e)
        errorDict['code'] = 400
        return jsonify(errorDict)



# *********************************************************login()******************************************************
# Description : This method takes in a json consisting of username and password and returns whether the user login is
#               valid or not.
# Input : a json consisting of username and password
# Output : 200 code for successful login, 500 with error msg in json for unsuccessful login
# **********************************************************************************************************************

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def login():
    output = {"log" : None, "status_code" : 0}
    if dbSession is None:
        init_dbSession()

    try:
        profile_information = request.get_json()
        print("profile information:", profile_information)
        app.logger.debug('Attempting User login: '+ profile_information['username'])
        app_user = profile_information['username']
        app_user_pwd = profile_information['password']
        is_authentic = dbSession.query(exists().where(and_(Student.user_name == app_user, Student.login_pwd == app_user_pwd))).scalar()
        if not is_authentic:
            app.logger.error('Invalid Credentials. Please try again.')
            output['log'] = 'Invalid Credentials. Please try again.'
            output['status_code'] = 500
            return jsonify(output)
        else:
            session['app_user'] = app_user
            student = dbSession.query(Student).filter_by(user_name=app_user).first()
            output['first_name'] = student.first_name
            output['last_name'] = student.last_name
            output['log'] = "Success logging in " + app_user
            output['status_code'] = 200
            return jsonify(output)
    except exc.InvalidRequestError as e:
        dbSession.rollback()
        app.logger.error(e)
        output['log'] = str(e)
        app.logger.error('Rolling back invalid transaction.')
        output['status_code'] = 500
        return jsonify(output)
    except Exception as e:
        app.logger.error(e)
        output['log'] = str(e)
        output['status_code'] = 500
        return jsonify(output)


# ***********************************************************team()*****************************************************
# Description: team() creates a Json of all the students except the logged in student to be used by the web application
#               to create the list of evalees using the username provided from the student_group table;
#               returns error if the evaluation for the current week has been submitted already
# Input : None; uses the username from session information to find the team details
# Output : returns a json which consists of all the team-members and their respective details
# **********************************************************************************************************************

@app.route('/team',  methods=('GET',))
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def team():
    if dbSession is None:
        init_dbSession()
    try:
        if 'app_user' in session:
            app_user = session['app_user']
        else:
            raise Exception('User not logged in')

        # Check if the evaluation has already been submitted by the student for the current week
        # get the max week from the groups table in database and the current semester
        semester = dbSession.query(Semester).filter_by(year=CURRENT_YEAR, season=CURRENT_SEASON,
                                                       course_no=CURRENT_COURSE_NO).first()
        max_week = dbSession.query(func.max(Groups.week).label('maxweek')).filter_by(semester=semester)
        number_of_evaluations_submitted = dbSession.query(EncryptedEvaluation) \
            .filter(EncryptedEvaluation.week == max_week,
                    EncryptedEvaluation.evaler_id == app_user,
                    EncryptedEvaluation.semester == semester) \
            .count()

        weekQuery = dbSession.query(Groups).filter_by().all()
        weekNumberList = []
        for item in weekQuery:
            weekNumberList.append(int(item.week))
        weekNumber = max(weekNumberList)
        # resubmission error if the number of submissions is greater than 0 for the student, for the current semester
        if number_of_evaluations_submitted > 0:
            app.logger.debug("number_of_evaluations_submitted > 0")
            clear_session()
            return jsonify({"log": "Evaluation already submitted for the current week", "status_code": 500})

        student = dbSession.query(Student).filter_by(user_name = app_user).first()
        team_number = dbSession.query(Group_Student).filter_by(student = student).first().group_id
        group_student = dbSession.query(Group_Student).filter_by(group_id=team_number).all()
        new_group_student = []

        # Removing the logged in user from the list of team members
        for member in group_student:
            if student.user_name != member.student_id:
                new_group_student.append(member)

        # Extracting the team members details from student table
        student_data = []
        for member in new_group_student:
            student_data.append(dbSession.query(Student).filter_by(user_name = member.student_id).first())

        team_dict = {}
        for i in range(len(student_data)):
            member_dict = {'username': student_data[i].user_name,
                           'first_name': student_data[i].first_name,
                           'last_name': student_data[i].last_name,
                           'initials': student_data[i].first_name[0].upper()+ student_data[i].last_name[0].upper(),
                           'is_manager': str(new_group_student[i].is_manager),
                           'evaluation' : {'rank' : -1, 'tokens': -1, 'description': -1, 'adjective': -1}
                           }
            if new_group_student[i].is_manager == 1:
                member_dict['approachable_attitude'] = -1
                member_dict['team_communication'] = -1
                member_dict['client_interaction'] = -1
                member_dict['decision_making'] = -1
                member_dict['resource_utilization'] = -1
                member_dict['follow_up_to_completion'] = -1
                member_dict['task_delegation_and_ownership'] = -1
                member_dict['encourage_team_development'] = -1
                member_dict['realistic_expectation'] = -1
                member_dict['performance_under_stress'] = -1
                member_dict['mgr_description'] = -1
            team_dict['evalee'+str(i)] = member_dict

        output = jsonify({'team': team_dict,
                          'good_adjectives': GOOD_ADJECTIVES,
                          'bad_adjectives': BAD_ADJECTIVES,
                          'status_code': 200,
                          'log': "Success in extracting team information",
                          'week':weekNumber
                          })

    except Exception as e:
        errorDict = {}
        errorDict['message'] = str(e)
        errorDict['code'] = 400
        return jsonify(errorDict)

    return output

# ***********************************************************team_evaluations()******************************************
# Description: team_evaluations()
# Input : None; uses the username from session information to find the team details
# Output : returns a json which consists of all the team-members and their respective details
# ***********************************************************************************************************************


@app.route('/evaluations',  methods=['POST'])
def team_evaluations():
    # calculate the current week using the date of first monday of the se
    # curr_week =

    if dbSession is None:
        init_dbSession()
    if not session.get('app_user'):
        clear_DBsession()
        app.logger.debug('clear_DBsession')
        return jsonify({ "error": ""}), 500
    app_user = session['app_user']
    app.logger.debug('Currently logged in user : '+ app_user)

    evals = []
    evals = request.get_json()

    evaler = dbSession.query(Student).filter_by(user_name=app_user).first()
    semester = dbSession.query(Semester).filter_by(year=CURRENT_YEAR,
                                                   season=CURRENT_SEASON,
                                                   course_no=CURRENT_COURSE_NO).first()

    for eval in evaluations.values():
        evalee = dbSession.query(Student).filter_by(user_name=eval.get('username')).first()
        eval['description'] = eval['description'].encode('utf8')

        # TODO: Write logic for the week to find max from the evaluation table or initilize t 1 if empty
        evaluation = Evaluation(evaler=evaler,
                                evalee=evalee,
                                week=1,
                                rank=eval['rank'],
                                token=eval['tokens'],
                                description=eval['description'],
                                adjective=eval['adjective'],
                                encryptedManagerEval=None,
                                semester=semester)

        evals.append(evaluation)
    for e in evals:
        encryptedEval = evalCipher.encryptEval(e)
        dbSession.add(encryptedEval)
    try:
        dbSession.commit()
    except exc.InvalidRequestError as e:
        dbSession.rollback()
        app.logger.error(e)
        app.logger.error('Rolling back invalid transaction.')
        return jsonify({ "error": e }), 500
    app.logger.debug('dbsession commit')
    clear_session()
    return jsonify({"success" : "evaluation updated in db successfully"}), 200




# ***********************************************************************************************************************************************


if __name__ == '__main__':
    context = (cer, ssl_key)
    app.debug = True
    handler = RotatingFileHandler('application.log', maxBytes=10000, backupCount=5)
    formatter = logging.Formatter("[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(LOGGING_LEVEL)
    app.logger.addHandler(handler)
    app.secret_key = key

    #app.run(host=APP_HOST, port=int(APP_PORT), ssl_context=context) #https

    #trying to use tornado
    ssl_context = { "certfile": cer, "keyfile": ssl_key  }

    http_server = HTTPServer( WSGIContainer(app), ssl_options=ssl_context )

    http_server.listen( 55555 )

    IOLoop.instance().start()
