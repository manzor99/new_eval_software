import sys
sys.path.append("lib/python2.7/site-packages/")

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

import os
from flask import Flask, flash, render_template, url_for, request, redirect, session
from sqlalchemy import create_engine, distinct
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
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

#for https
from OpenSSL import SSL

context = SSL.Context(SSL.SSLv23_METHOD)
cer = os.path.join(os.path.dirname(__file__), 'certificate/tintin.cs.indiana.edu.crt')
ssl_key = os.path.join(os.path.dirname(__file__), 'certificate/tintin.cs.indiana.edu.key')


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
evalCipher = EvalCipher(key)
urlSerializer = URLSafeSerializer(key)

##TRYING NULLPOOL
engine = create_engine('mysql://' + username + ':' + password + '@' + host +':' + port + '/' + schema, poolclass=NullPool )
#session['logged_in_user'] = "no"

try:
    engine.connect()
    Base.metadata.bind = engine
    DBSession = sessionmaker(autoflush=True, bind=engine)
except Exception as e:
    app.logger.error(e)

def init_dbSession():
    global dbSession
    app.logger.debug('Attempting DB connection via: '+ username)
    try:
        dbSession = DBSession()    
        return
    except Exception as e:
        app.logger.debug(e)
        app.logger.error(e)
        return render_template("error.html") 

@app.route('/', methods=['GET', 'POST'])       
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if dbSession is None:
            init_dbSession()
        try:
            app.logger.debug('Attempting User login: '+ request.form['username'])
            app_user = request.form['username']
            app_user_pwd = request.form['password']
            print session
            print "app_user",app_user
            print "username",username
            isAuthentic = app_user==username and app_user_pwd==password
            
            if isAuthentic != True:
                error = 'Invalid Credentials. Please try again.'
            else:
                print "PRE session['logged_in_user']: ",session.get('logged_in_user')
                session['app_user'] = app_user
                session['logged_in_user'] = "eval"
                print "POST session['logged_in_user']: ",session.get('logged_in_user')
                return redirect(url_for('main'))
                
        except Exception as e:
            app.logger.error(e)
            return render_template("error.html")         
    return render_template('admin_login.html', error=error)
    

@app.route('/main')
def main( ):
    print "session['logged_in_user']: ",session['logged_in_user']
    if session['logged_in_user'] == username:
        return "logged in!"
    else:
        return redirect(url_for('login'))


@app.route('/logout')
def logout( ):
    session['logged_in_user'] = "" #None
    clear_session( )
    app.logger.info('User has logged out successfully.')
    flash('You have been logged out successfully')
    
    return redirect(url_for('login'))
    
def clear_session( ):
    app.logger.debug('Clearing User Session... ')

    session.pop('app_user')
    session.pop('logged_in_user')
    
    clear_DBsession()
    return

def clear_DBsession():
    app.logger.debug('Clearing DB Session...')
    if dbSession is not None:
        dbSession.flush()
        dbSession.close()
    return

@app.errorhandler(Exception)
def unhandled_exception(e):
    app.logger.error(e)
    return render_template("error.html")



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
    ssl_context = { "certfile": cer, "keyfile": ssl_key  }
    http_server = HTTPServer( WSGIContainer(app), ssl_options=ssl_context )
    http_server.listen( 9009 )
    IOLoop.instance().start()
 
        