import sys
import os
lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'lib/python2.7/site-packages'))
# sys.path.append("./lib/python2.7/site-packages/")
sys.path.append(lib_path)

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

import os
from flask import Flask, flash, render_template, url_for, request, redirect, session, jsonify, make_response
import jwt
# import flask_login
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
# from datetime import timedelta
import datetime
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
app.permanent_session_lifetime = datetime.timedelta(seconds=10800)

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
        return render_template("error.html")

@app.route('/eval', methods=['GET', 'POST'])
def list_all():
    app.logger.debug('inside list_all')
    try:
        if not session.get('app_user'):
            clear_DBsession()
            app.logger.debug('clear_DBsession')
            return redirect(url_for('login'))
        app_user = session['app_user']
        app.logger.debug('Currently logged in user : '+ app_user)
        if request.method == 'POST':
            form = EvalListForm()
            if form.validate_on_submit():
                evals = []
                evaler = dbSession.query(Student).filter_by(user_name=form.evaluations[0]['evaler_id'].data).first()
                semester = dbSession.query(Semester).filter_by(year=CURRENT_YEAR, season=CURRENT_SEASON, course_no=CURRENT_COURSE_NO).first()
                for eval in form.evaluations:
                    evalee = dbSession.query(Student).filter_by(user_name=eval['evalee_id'].data).first()

                    encryptedManagerEval = None
                    if eval['is_manager'].data == 1:
                        print "inside is_manager"
                        managerEval = Manager_Eval(approachable_attitude = eval['managerEval']['approachable'].data,
                                    team_communication = eval['managerEval']['communication'].data,
                                    client_interaction = eval['managerEval']['client_interaction'].data,
                                    decision_making = eval['managerEval']['decision_making'].data,
                                    resource_utilization = eval['managerEval']['resource_utilization'].data,
                                    follow_up_to_completion = eval['managerEval']['follow_up_to_completion'].data,
                                    task_delegation_and_ownership = eval['managerEval']['task_delegation_and_ownership'].data,
                                    encourage_team_development = eval['managerEval']['encourage_team_development'].data,
                                    realistic_expectation = eval['managerEval']['realistic_expectation'].data,
                                    performance_under_stress = eval['managerEval']['performance_under_stress'].data,
                                    mgr_description = 'None')

                        encryptedManagerEval = evalCipher.encryptManagerEval(managerEval)
                        dbSession.add(encryptedManagerEval)

                    eval['description'].data = eval['description'].data.encode('utf8')
                    evaluation = Evaluation(evaler=evaler,
                                            evalee=evalee,
                                            week=eval['week'].data,
                                            rank=eval['rank'].data,
                                            token=eval['tokens'].data,
                                            description=eval['description'].data,
                                            adjective=eval['adjective'].data,
                                            encryptedManagerEval=encryptedManagerEval,
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
                    return render_template("error.html")
                app.logger.debug('dbsession commit')
                print ( app_user )
                clear_session()
                return render_template('eval-success.html', week=form.evaluations[0]['week'].data)
            else:
                return render_template('eval.html',form = form, ga=GOOD_ADJECTIVES, ba=BAD_ADJECTIVES)
    except Exception as e:
            app.logger.debug(e)
            if dbSession is not None:
                dbSession.rollback()
            clear_DBsession()
            app.logger.error(e)
            return render_template("error.html")

    # get the maxweek from the groups table in database
    max_week = dbSession.query(func.max(Groups.week).label('maxweek')).filter_by(semester=semester)
    number_of_evaluations_submitted = dbSession.query(EncryptedEvaluation)\
                                                .filter(EncryptedEvaluation.week == max_week,
                                                        EncryptedEvaluation.evaler_id == app_user,
                                                        EncryptedEvaluation.semester == semester)\
                                                .count()

    # resubmission error if the number of submissions is greater than 0 for the student, for the current semester
    if number_of_evaluations_submitted > 0:
        app.logger.debug("number_of_evaluations_submitted > 0")
        clear_session()
        return render_template('resubmitError.html', week=max_week.scalar())

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
                                        evalee.student_id.label('EVALEE_ID'))\
                                .filter(Groups.id==evaler.group_id,
                                        evaler.group_id == evalee.group_id,
                                        evaler.student_id <> evalee.student_id,
                                        evaler.student_id == app_user,
                                        Groups.semester == semester, Groups.week >= limit)\
                                .order_by(Groups.week,
                                          evaler.student_id,
                                          evalee.student_id)\
                                .subquery()

    current_evals = dbSession.query(sub_groups.c.week.label('WEEK'),
                                    sub_student_evals.c.EVALER_ID,
                                    sub_student_evals.c.EVALEE_ID)\
                            .filter(sub_groups.c.week >= sub_student_evals.c.week,
                                    sub_groups.c.student_id == sub_student_evals.c.EVALER_ID)\
                            .group_by(sub_groups.c.week.label('WEEK'),
                                      sub_student_evals.c.EVALER_ID,
                                      sub_student_evals.c.EVALEE_ID)\
                            .order_by(sub_groups.c.week,
                                      sub_student_evals.c.EVALER_ID)\
                            .subquery()



    # get the group ids for the current week(max week in the groups table)
    max_week_group_ids = dbSession.query(Groups.id)\
                                    .filter(Groups.week == max_week, Groups.semester == semester)\
                                    .subquery()
    current_managers = dbSession.query(Group_Student.student_id, Group_Student.is_manager)\
                                .filter(Group_Student.group_id.in_(max_week_group_ids), Group_Student.is_manager == 1)\
                                .subquery()
    # create the
    form_evals = dbSession.query(current_evals.c.WEEK,
                                 current_evals.c.EVALEE_ID,
                                 Student.first_name,
                                 Student.last_name,
                                 current_managers.c.is_manager)\
                        .join(Student,
                              current_evals.c.EVALEE_ID == Student.user_name)\
                        .outerjoin(current_managers,
                                   current_evals.c.EVALEE_ID == current_managers.c.student_id)\
                        .order_by(current_evals.c.EVALEE_ID)\
                        .all()

    evalData = {'evaluations': form_evals}
    form = EvalListForm(data=MultiDict(evalData))

    # put information in the form for the current week and the current evaluator
    for x, y in itertools.izip(form_evals,form.evaluations):
      y.evalee_id.data = x.EVALEE_ID
      y.evaler_id.data = app_user
      y.week.data = x.WEEK
      y.is_manager.data = x.is_manager
      y.evalee_fname.data = x.first_name
      y.evalee_lname.data = x.last_name

    return render_template('eval.html',form = form,ga=GOOD_ADJECTIVES,ba=BAD_ADJECTIVES)


# *********************************************************logout()*****************************************************
# Description : This method clears the session and returns a json specifying the either the success msg or error msg
#               with respective status code
# Input : None
# Output : 200 code for successful logout, 500 with error msg in json for unsuccessful logout
# **********************************************************************************************************************


# @app.route('/logout', methods = ['GET', 'POST'])
# def logout():
#     flask_login.logout_user()
#     return 'Logged out'

@app.route('/logout')
def logout():
    output = {}
    try:
        clear_session()
        app.logger.info('User has logged out successfully.')
        output['log'] = 'Successful logging out'
        output['status_code'] = 500
        # flash('You have been logged out successfully')
    except Exception as e:
        app.logger.error(e)
        output['log'] = str(e)
        output['status_code'] = 500
    return jsonify(output)


def clear_session( ):
    app.logger.debug('Clearing User Session... ')
    session.pop('app_user')
    clear_DBsession()
    return


def clear_DBsession():
    app.logger.debug('Clearing DB Session...')
    if dbSession is not None:
        dbSession.flush()
        dbSession.close()
    return


@app.route('/reset-password', methods=('GET', 'POST',))
def forgot_password():
    app.logger.debug('Inside forgot_password')
    form = ResetPassword()
    if request.method == 'POST':
        if dbSession is None:
            init_dbSession()

        if form.validate_on_submit():
            user_name = form.user_name.data
            user = dbSession.query(Student).filter_by(user_name=user_name).first()
            app.logger.debug('Attempting to request a new password: '+ user_name)
            if user:
                token = user.get_token()
                url = APP_HOST + ':' + APP_PORT + url_for('verify_user') + '?token=' + token
                user = urlSerializer.dumps({"user":user.email})
                url = urlSerializer.dumps({"url":url})
                return redirect(url_for('mail_sender', user=user, url=url))
    return render_template('reset.html', form=form)

@app.route('/verify-user', methods=('GET', 'POST',))
def verify_user():
    app.logger.debug('Inside verify_user')
    if request.method == 'POST':
        form = ResetPasswordSubmit()
        if form.validate_on_submit():
            user_name = form.user_name.data
            pwd = form.password.data
            confirm = form.confirm.data
            app.logger.debug('Attempting to verify user to reset password: '+ user_name)
            if pwd == confirm:
                student = dbSession.query(Student).filter_by(user_name=user_name).update({Student.login_pwd: pwd})
                try:
                    dbSession.commit()
                except exc.InvalidRequestError as e:
                    dbSession.rollback()
                    app.logger.error(e)
                    app.logger.error('Rolling back invalid transaction.')
                    return render_template("error.html")
                return redirect(url_for('reset_password_success'))
            else:
                app.logger.error('Passwords do not match')
                flash('Passwords do not match.')
    else:
        form = ResetPasswordSubmit()
        token = request.args.get('token')
        verified_token = Student.verify_token(token)
        if verified_token:
            student = dbSession.query(Student).filter_by(user_name=verified_token).first()
            if student:
                form.user_name.data = student.user_name
        else:
            app.logger.warning('Token verification failed while resetting the password.')
            return render_template("token-verification-error.html")
    return render_template('reset-pwd.html', form=form)

@app.route('/password-reset-success', methods=('GET', 'POST',))
def reset_password_success():
    app.logger.info('Login password has been reset successfully.')
    return render_template('password-reset-success.html')

@app.route("/send-notification")
def mail_sender():
    try:
        app.logger.debug('Inside mail_sender')
        user = urlSerializer.loads(request.args.get('user'))
        # url = urlSerializer.loads(request.args.get('url'))
        link = "https://"\
               # + url['url']
        msg = Message("P532/P632 Evaluation Account Password Reset",
                      html=render_template("email-template.html", reset_url=link),
                      recipients=[user['user']])

        mail.send(msg)
        return redirect(url_for('notification_success'))
    except Exception as e:
        app.logger.error(e)
        return render_template("error.html")


# @app.route("/notification-success")
# def notification_success():
#     app.logger.info('Email notification successfully sent.')
#     return render_template('notification-success.html')

# @app.errorhandler(Exception)
# def unhandled_exception(e):
#     app.logger.error(e)
#     return render_template("error.html")

# *********************************************************login()******************************************************
# Description : This method takes in a json consisting of username and password and returns whether the user login is
#               valid or not.
# Input : a json consisting of username and password
# Output : 200 code for successful login, 500 with error msg in json for unsuccessful login
# **********************************************************************************************************************

class User():
    def __init__(self, username=None, password=None, first_name = None, last_name = None):
        self.username = username
        self.password = password
        self.first_name = first_name
        self.last_name = last_name

    def is_authenticated(self):
        return True

    def get_id(self):
        return unicode(self.username)

    def encode_auth_token(self, user_name):
        try:
            payload = {
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=0, seconds=10800),
                'iat': datetime.datetime.utcnow(),
                'sub': user_name
            }
            return jwt.encode(
                payload,
                app.config.get('SECRET_KEY'),
                algorithm='HS256'
            )
        except Exception as e:
            return e

    @staticmethod
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
            auth_token = user.encode_auth_token(user.username)
            print("Auth token created")
            if auth_token:
                response_object = {
                    'log': 'Successfully logged in.',
                    'username' : user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'status_code': 200,
                    'auth_token': auth_token
                }
                return jsonify(response_object)
        else:
            response_object = {
                'status_code': 501,
                'log': 'User does not exist.'
            }
            return jsonify(response_object)
    except Exception as e:
        print(e)
        response_object = {
            'status_code': 500,
            'log': 'Try again'
        }
        return jsonify(response_object)

# ***********************************************************team()*****************************************************
# Description: team() creates a Json of all the students except the logged in student to be used by the web application
#               to create the list of evalees using the username provided from the student_group table;
#               returns error if the evaluation for the current week has been submitted already
# Input : None; uses the username from session information to find the team details
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
            resp = User.decode_auth_token(auth_token)
            print(resp)
            if not isinstance(resp, str):
                app_user = dbSession.query(Student).filter_by(
                    user_name=resp
                ).first().user_name
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
                print("Week Number: ", weekNumber)
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

                team_list = []
                for i in range(len(student_data)):
                    member_dict = {'username': student_data[i].user_name,
                                   'first_name': student_data[i].first_name,
                                   'last_name': student_data[i].last_name,
                                   'initials': student_data[i].first_name[0].upper()+ student_data[i].last_name[0].upper(),
                                   'is_manager': str(new_group_student[i].is_manager),
                                   'evaluation' : {'rank': i, 'tokens': 0, 'description': "", 'adjective': ""}
                                   }
                    manager_dict = {}
                    if new_group_student[i].is_manager == 1:
                        manager_dict['approachable_attitude'] = 1
                        manager_dict['team_communication'] = 1
                        manager_dict['client_interaction'] = 1
                        manager_dict['decision_making'] = 1
                        manager_dict['resource_utilization'] = 1
                        manager_dict['follow_up_to_completion'] = 1
                        manager_dict['task_delegation_and_ownership'] = 1
                        manager_dict['encourage_team_development'] = 1
                        manager_dict['realistic_expectation'] = 1
                        manager_dict['performance_under_stress'] = 1
                        manager_dict['mgr_description'] = 1
                    member_dict['manager'] = manager_dict
                    team_list.append(member_dict)

                output = jsonify({'team': team_list,
                                  'good_adjectives': GOOD_ADJECTIVES,
                                  'bad_adjectives': BAD_ADJECTIVES,
                                  'status_code': 200,
                                  'log': "Success in extracting team information",
                                  'week': weekNumber
                                  })
                return output
            else:
                return jsonify({"status_code": 500, "log": "invalid token"})

    except Exception as e:
        return jsonify({"log": str(e), "status_code": 500})

# ***********************************************************team_evaluations()******************************************
# Description: team_evaluations()
# Input : None; uses the username from session information to find the team details
# Output : returns a json which consists of all the team-members and their respective details
# ***********************************************************************************************************************


@app.route('/evaluations',  methods=['POST'])
def team_evaluations():
    # calculate the current week using the date of first monday of the semester from the config file
    # curr_week =

    if dbSession is None:
        init_dbSession()
    if not session.get('app_user'):
        clear_DBsession()
        app.logger.debug('clear_DBsession')
        return jsonify({ "error": ""}), 500
    app_user = session['app_user']
    app.logger.debug('Currently logged in user : '+ app_user)

    evaluations = request.get_json()
    evals = []

    evaler = dbSession.query(Student).filter_by(user_name=app_user).first()
    semester = dbSession.query(Semester).filter_by(year=CURRENT_YEAR,
                                                   season=CURRENT_SEASON,
                                                   course_no=CURRENT_COURSE_NO).first()

    for eval in evaluations.values():
        evalee = dbSession.query(Student).filter_by(user_name=eval.get('username')).first()
        eval['description'] = eval['description'].encode('utf8')

        # TODO: Write logic for the week to find max from the evaluation table or initilize t1 if empty
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
    ssl_context = { "certfile": cer, "keyfile": ssl_key}

    http_server = HTTPServer( WSGIContainer(app), ssl_options=ssl_context)

    http_server.listen(55555)

    IOLoop.instance().start()
