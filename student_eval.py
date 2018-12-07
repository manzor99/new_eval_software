import sys
import os
lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'lib/python2.7/site-packages'))
# sys.path.append("./lib/python2.7/site-packages/")
sys.path.append(lib_path)

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

import os
import traceback
from flask import Flask, flash, url_for, request, redirect, session, jsonify, make_response
import jwt
from random import randint
from sqlalchemy import create_engine, distinct
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
from sqlalchemy import exc
from database_setup import Student, Base, Groups, Semester, Group_Student, Enrollment, Evaluation, \
    EncryptedEvaluation, EvalForm, EvalListForm, Manager_Eval, ResetPassword, ResetPasswordSubmit, User, Otp
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
# from datetime import timedelta
import datetime
from flask_cors import CORS, cross_origin
#for https
from OpenSSL import SSL

context = SSL.Context(SSL.SSLv23_METHOD)
#cer = os.path.join(os.path.dirname(__file__), 'certificate/tintin.cs.indiana.edu.crt')
#ssl_key = os.path.join(os.path.dirname(__file__), 'certificate/tintin.cs.indiana.edu.key')
# cer = os.path.join(os.path.dirname(__file__), 'certificate/snowy.sice.indiana.edu.cer')
# ssl_key = os.path.join(os.path.dirname(__file__), 'certificate/snowy.sice.indiana.edu.key')

cer = os.path.join(os.path.dirname(__file__), 'certificate/localhost.cer')
ssl_key = os.path.join(os.path.dirname(__file__), 'certificate/localhost.key')


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
VALIDITY_OF_AUTH_TOKEN = parser.get('validity', 'VALIDITY_OF_AUTH_TOKEN')
VALIDITY_OF_OTP = parser.get('validity', 'VALIDITY_OF_OTP')

parser.read('semester_encryption_keys.ini')
key = parser.get('encryptionkeys', CURRENT_SEASON + '-' + str(CURRENT_YEAR) + '-' + CURRENT_COURSE_NO)

app = Flask(__name__)
app.config['CSRF_ENABLED'] = True
app.config['SECRET_KEY'] = key

app.config["MAIL_SERVER"] = MAIL_SERVER
app.config["MAIL_PORT"] = MAIL_PORT
app.config["MAIL_USE_SSL"] = MAIL_USE_SSL
app.config['MAIL_USE_TLS'] = False
app.config["MAIL_DEFAULT_SENDER"] = MAIL_DEFAULT_SENDER

# app.config['MAIL_SERVER']='smtp.gmail.com'
# app.config['MAIL_PORT'] = 465
# app.config["MAIL_DEFAULT_SENDER"] = ''
# app.config['MAIL_USERNAME'] = ''
# app.config['MAIL_PASSWORD'] = ''
# app.config['MAIL_USE_SSL'] = True
# app.config['MAIL_USE_TLS'] = False

mail = Mail(app)
dbSession = None

evalCipher = EvalCipher(key)
urlSerializer = URLSafeSerializer(key)

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
        return jsonify({"log": str(e), "status_code": 500})


# *********************************************************sign_up******************************************************
# Description : This method takes in a json consisting of username and password and returns whether the user login is
#               valid or not.
# Input : a json consisting of username and password
# Output : 200 code for successful login, 500 with error msg in json for unsuccessful login
# **********************************************************************************************************************

@app.route('/verify-user', methods=['POST'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def verify_user():
    if dbSession is None:
        init_dbSession()
    try:
        app.logger.debug('Inside sign up')
        post_data = request.get_json()
        user_name = post_data.get('username')
        user = dbSession.query(Student).filter_by(user_name=user_name).first()
        if user:
            email = [user.email]
            msg = Message("P532/P632 Evaluation Account Password Reset",
                          recipients=email)
            otp = randint(10000, 99999)
            msg.body = "The One-Time Password for resetting the password is : " + str(otp)

            # save the otp for current username in database
            if dbSession.query(Otp).filter_by(user_name=user_name):
                dbSession.query(Otp).filter_by(user_name=user_name).delete()
                dbSession.add(Otp(user_name=user_name, otp=otp))
                try:
                    dbSession.commit()
                except exc.InvalidRequestError as e:
                    dbSession.rollback()
                    app.logger.error(e)
                    app.logger.error('Rolling back invalid transaction.')
                    return jsonify({ "error": e, "status_code": 500})
            mail.send(msg)
            return jsonify({"log": "User verified", "status_code": 200, "first_name":user.first_name})
        else:
            return jsonify({"log": "User is not present in the database", "status_code": 501})
    except Exception as e:
        return jsonify({"log": str(e), "status_code": 500})


@app.route('/check-otp', methods=['POST'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def check_otp():
    if dbSession is None:
        init_dbSession()
    try:
        post_data = request.get_json()
        entered_otp = post_data.get('otp')
        user_name = post_data.get('username')
        pwd = post_data.get('password')
        user = dbSession.query(Student).filter_by(user_name=user_name).first()
        # Check if user exists
        if user:
            # Check time elapsed
            otp = dbSession.query(Otp).filter_by(user_name=user_name).first()
            creation_time = otp.create_time
            time_elapsed = datetime.datetime.now() - creation_time
            if time_elapsed.seconds <= VALIDITY_OF_OTP:
                # Check if the otp is correct match
                if entered_otp == otp.otp:
                    # remove the entry from database
                    dbSession.query(Otp).filter_by(user_name=user_name).delete()
                    dbSession.query(Student).filter_by(user_name=user_name).update({Student.login_pwd: pwd})
                    try:
                        dbSession.commit()
                    except exc.InvalidRequestError as e:
                        dbSession.rollback()
                        app.logger.error(e)
                        app.logger.error('Rolling back invalid transaction.')
                        return jsonify({"error": e, "status_code": 500})

                    return jsonify({"log": "Otp verified", "status_code": 200})
                else:
                    return jsonify({"log": "OTP is incorrect", "status_code": 501})
            else:
                return jsonify({"log": "OTP is no longer valid", "status_code": 502})
        else:
            return jsonify({"log": "User is not present in the database", "status_code": 503})
    except Exception as e:
        return jsonify({"log": str(e), "status_code": 500})


# *********************************************************login()******************************************************
# Description : This method takes in a json consisting of username and password and returns whether the user login is
#               valid or not.
# Input : a json consisting of username and password
# Output : 200 code for successful login, 500 with error msg in json for unsuccessful login
# **********************************************************************************************************************
def encode_auth_token(user_name):
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=0, seconds=int(VALIDITY_OF_AUTH_TOKEN)),
            'iat': datetime.datetime.utcnow(),
            'sub': user_name
        }
        return jwt.encode(
            payload,
            app.config.get('SECRET_KEY'),
            algorithm='HS256'
        )
    except Exception as e:
        return str(e)


def decode_auth_token(auth_token):
    try:
        payload = jwt.decode(auth_token, app.config.get('SECRET_KEY'))
        return payload['sub']
    except jwt.ExpiredSignatureError:
        return 'Signature expired. Please log in again.'
    except jwt.InvalidTokenError:
        return 'Invalid token. Please log in again.'


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def login():
    if dbSession is None:
        init_dbSession()

    post_data = request.get_json()
    try:
        # fetch the user data
        db_data = dbSession.query(Student).filter_by(
            user_name = post_data.get('username')
        ).first()

        if db_data and (db_data.login_pwd == post_data.get('password')):
            # create the user object
            user = User(db_data.user_name, db_data.login_pwd, db_data.first_name, db_data.last_name)
            auth_token = encode_auth_token(user.username)
            app.logger.debug("Auth token created")
            if auth_token:
                response_object = {
                    'log': 'Successfully logged in.',
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'status_code': 200,
                    'auth_token': auth_token
                }
                return jsonify(response_object)
        else:
            response_object = {
                'status_code': 501,
                'log': 'Username/password is incorrect'
            }
            return jsonify(response_object)
    except Exception as e:
        response_object = {
            'status_code': 500,
            'log': 'Try again'
        }
        return jsonify(response_object)

# ***********************************************************team()*****************************************************
# Description: team() creates a Json of all the students except the logged in student to be used by the web application
#               to create the list of evalees using the username provided from the student_group table;
#               returns error if the evaluation for the current week has been submitted already
# Input : auth_token; uses the username from session information to find the team details
# Output : returns a json which consists of all the team-members and their respective details
# **********************************************************************************************************************


@app.route('/team',  methods=['GET', 'POST'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def team():
    if dbSession is None:
        init_dbSession()
    try:
        post_data = request.get_json()
        auth_token = post_data.get('auth_token')

        if auth_token:
            app_user = decode_auth_token(auth_token)
            if not isinstance(app_user, str):
                # Check if the evaluation has already been submitted by the student for the current week
                # get the max week from the groups table in database and the current semester
                # get the maxweek from the groups table in database
                semester = dbSession.query(Semester).filter_by(year=CURRENT_YEAR, season=CURRENT_SEASON,
                                                               course_no=CURRENT_COURSE_NO).first()
                max_week = dbSession.query(func.max(Groups.week).label('maxweek')).filter_by(semester=semester)
                number_of_evaluations_submitted = dbSession.query(EncryptedEvaluation) \
                    .filter(EncryptedEvaluation.week == max_week,
                            EncryptedEvaluation.evaler_id == app_user,
                            EncryptedEvaluation.semester == semester) \
                    .count()

                # resubmission error if the number of submissions is greater than 0 for the student, for the current semester
                if number_of_evaluations_submitted > 0:
                    app.logger.debug("number_of_evaluations_submitted > 0")
                    return jsonify({"status_code": 501, "log": "Evaluation already submitted for this week"})

                # Aliasing is used for using an alias name for the tables to make writing queries easier; SQLAlchemy
                evaler = aliased(Group_Student)
                evalee = aliased(Group_Student)
                sub_groups = dbSession.query(Groups.week, Groups.id.label('GROUP_ID'),
                                             Group_Student.student_id).filter(Groups.id == Group_Student.group_id,
                                                                              Groups.week == max_week,
                                                                              Groups.semester == semester).subquery()

                # Use this flag to limit evaluations of students in the current week (Fix for P532 project phase)
                limit = 0
                if LIMIT_EVALS_TO_CURRENT_WEEK == 'True':
                    limit = max_week
                sub_student_evals = dbSession.query(Groups.week,
                                                    Groups.id,
                                                    evaler.student_id.label('EVALER_ID'),
                                                    evalee.student_id.label('EVALEE_ID')) \
                    .filter(Groups.id == evaler.group_id,
                            evaler.group_id == evalee.group_id,
                            evaler.student_id <> evalee.student_id,
                            evaler.student_id == app_user,
                            Groups.semester == semester,
                            Groups.week >= limit) \
                    .order_by(Groups.week,
                              evaler.student_id,
                              evalee.student_id) \
                    .subquery()

                current_evals = dbSession.query(sub_groups.c.week.label('WEEK'),
                                                sub_student_evals.c.EVALER_ID,
                                                sub_student_evals.c.EVALEE_ID) \
                    .filter(sub_groups.c.week >= sub_student_evals.c.week,
                            sub_groups.c.student_id == sub_student_evals.c.EVALER_ID) \
                    .group_by(sub_groups.c.week.label('WEEK'),
                              sub_student_evals.c.EVALER_ID,
                              sub_student_evals.c.EVALEE_ID) \
                    .order_by(sub_groups.c.week,
                              sub_student_evals.c.EVALER_ID) \
                    .subquery()

                # get the group ids for the current week(max week in the groups table)
                max_week_group_ids = dbSession.query(Groups.id) \
                    .filter(Groups.week == max_week, Groups.semester == semester) \
                    .subquery()
                current_managers = dbSession.query(Group_Student.student_id, Group_Student.is_manager) \
                    .filter(Group_Student.group_id.in_(max_week_group_ids), Group_Student.is_manager == 1) \
                    .subquery()

                form_evals = dbSession.query(current_evals.c.WEEK,
                                             current_evals.c.EVALEE_ID,
                                             Student.first_name,
                                             Student.last_name,
                                             current_managers.c.is_manager) \
                    .join(Student,
                          current_evals.c.EVALEE_ID == Student.user_name) \
                    .outerjoin(current_managers,
                               current_evals.c.EVALEE_ID == current_managers.c.student_id) \
                    .order_by(current_evals.c.EVALEE_ID) \
                    .all()

                team_list = []
                i = 1
                for student_data in form_evals:
                    member_dict = {'week' : student_data[0],
                                   'username': student_data[1],
                                   'first_name': student_data[2],
                                   'last_name': student_data[3],
                                   'initials': student_data[2][0].upper() +  student_data[3][0].upper(),
                                   'is_manager': student_data[4],
                                   'is_complete' : False,
                                   'evaluation' : {'rank': i, 'tokens': 0, 'description': "", 'adjective': ""}
                                   }
                    i += 1
                    manager_dict = {}
                    if student_data[4] == 1:
                        manager_dict['approachable_attitude'] = -1
                        manager_dict['team_communication'] = -1
                        manager_dict['client_interaction'] = -1
                        manager_dict['decision_making'] = -1
                        manager_dict['resource_utilization'] = -1
                        manager_dict['follow_up_to_completion'] = -1
                        manager_dict['task_delegation_and_ownership'] = -1
                        manager_dict['encourage_team_development'] = -1
                        manager_dict['realistic_expectation'] = -1
                        manager_dict['performance_under_stress'] = -1
                        manager_dict['mgr_description'] = -1
                    member_dict['manager'] = manager_dict
                    team_list.append(member_dict)

                output = jsonify({'team': team_list,
                                  'good_adjectives': GOOD_ADJECTIVES,
                                  'bad_adjectives': BAD_ADJECTIVES,
                                  'status_code': 200,
                                  'log': "Success in extracting team information"
                                  })
                return output
            else:
                return jsonify({"status_code": 502, "log": "invalid token"})

    except Exception as e:
        return jsonify({"log": str(e), "status_code": 500})

# ***********************************************************team_evaluations()*****************************************
# Description: uses the username from decoded auth_token received from client along with evaluation and updates the
#           same in database.
# Input :   auth_token and the evaluations
# Output : returns log message and status code
# **********************************************************************************************************************


@app.route('/evaluations',  methods=['POST'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def team_evaluations():
    try:
        if dbSession is None:
            init_dbSession()
        post_data = request.get_json()
        auth_token = post_data.get('auth_token')

        if auth_token:
            app_user = decode_auth_token(auth_token)
            app.logger.debug('Currently logged in user : ' + app_user)
            if not isinstance(app_user, str):
                evals = []
                evaler = dbSession.query(Student).filter_by(user_name=app_user).first()
                semester = dbSession.query(Semester).filter_by(year=CURRENT_YEAR,
                                                               season=CURRENT_SEASON,
                                                               course_no=CURRENT_COURSE_NO).first()

                teammates = post_data.get('team')
                for person in teammates:
                    evalee = dbSession.query(Student).filter_by(user_name=person.get('username')).first()
                    eval = person.get('evaluation')
                    max_week = person.get("week")
                    manager_attributes = person.get('manager')
                    encrypted_manager_eval = None
                    if person['is_manager'] == 1:
                        manager_eval = Manager_Eval(approachable_attitude=manager_attributes['approachable_attitude'],
                                                    team_communication=manager_attributes['team_communication'],
                                                    client_interaction=manager_attributes['client_interaction'],
                                                    decision_making=manager_attributes['decision_making'],
                                                    resource_utilization=manager_attributes['resource_utilization'],
                                                    follow_up_to_completion=manager_attributes['follow_up_to_completion'],
                                                    task_delegation_and_ownership=manager_attributes['task_delegation_and_ownership'],
                                                    encourage_team_development=manager_attributes['encourage_team_development'],
                                                    realistic_expectation=manager_attributes['realistic_expectation'],
                                                    performance_under_stress=manager_attributes['performance_under_stress'],
                                                    mgr_description='None')
                        encrypted_manager_eval = evalCipher.encryptManagerEval(manager_eval)
                        dbSession.add(encrypted_manager_eval)

                    evaluation = Evaluation(evaler=evaler,
                                            evalee=evalee,
                                            week=max_week,
                                            rank=eval['rank'],
                                            token=eval['tokens'],
                                            description=eval['description'],
                                            adjective=eval['adjective'],
                                            encryptedManagerEval=encrypted_manager_eval,
                                            semester=semester)
                    evals.append(evaluation)
                for e in evals:
                    encrypted_eval = evalCipher.encryptEval(e)
                    dbSession.add(encrypted_eval)
                try:
                    dbSession.commit()
                except exc.InvalidRequestError as e:
                    dbSession.rollback()
                    app.logger.error(e)
                    app.logger.error('Rolling back invalid transaction.')
                    return jsonify({ "log": e, "status_code": 500})
                return jsonify({"log" : "evaluation updated in db successfully", "status_code": 200})
            else:
                return jsonify({"status_code": 502, "log": "invalid token"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"log": str(e), "status_code": 500})


# **********************************************************************************************************************


if __name__ == '__main__':
    context = (cer, ssl_key)
    app.debug = True
    handler = RotatingFileHandler('application.log', maxBytes=10000, backupCount=5)
    formatter = logging.Formatter("[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(LOGGING_LEVEL)
    app.logger.addHandler(handler)
    app.secret_key = key

    #trying to use tornado
    ssl_context = { "certfile": cer, "keyfile": ssl_key}

    http_server = HTTPServer( WSGIContainer(app), ssl_options=ssl_context)

    http_server.listen(55555)

    IOLoop.instance().start()
