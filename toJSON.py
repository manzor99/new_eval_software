import database_setup

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

from student_eval import app
from flask import flash
from flask import Flask
from sqlalchemy import Column, ForeignKey, Integer, String, VARCHAR, TIMESTAMP, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.sql import func
from ConfigParser import SafeConfigParser
from flask.ext.wtf import Form
from wtforms import IntegerField, TextField, validators, FieldList, FormField, TextAreaField, HiddenField, RadioField, SelectField, PasswordField
from wtforms.validators import Required, Length, Optional
from wtforms import Form as WTForm
from itsdangerous import TimedJSONWebSignatureSerializer
import codecs
import ast
from datetime import timedelta

parser = SafeConfigParser()
parser.read('config.ini')

CURRENT_SEASON = parser.get('currentsem', 'season')
CURRENT_YEAR = int(parser.get('currentsem', 'year'))
CURRENT_COURSE_NO = parser.get('currentsem', 'course_no')

MAIL_SERVER = parser.get('email', 'MAIL_SERVER')
MAIL_PORT = parser.get('email', 'MAIL_PORT')
MAIL_USE_SSL = ast.literal_eval(parser.get('email', 'MAIL_USE_SSL'))
MAIL_DEFAULT_SENDER = parser.get('email', 'MAIL_DEFAULT_SENDER')

APP_HOST = parser.get('apprun', 'host')
APP_PORT = parser.get('apprun', 'port')

LOGGING_LEVEL = parser.get('logs', 'LOGGING_LEVEL')

GOOD_ADJECTIVES = parser.get('adjectives', 'GOOD_ADJECTIVES').replace(' ','').split(",")
BAD_ADJECTIVES = parser.get('adjectives', 'BAD_ADJECTIVES').replace(' ','').split(",")
GOOD_ADJECTIVES.sort()
BAD_ADJECTIVES.sort()

LIMIT_EVALS_TO_CURRENT_WEEK = parser.get('limitevals', 'LIMIT_TO_CURRENT_WEEK')

parser.read('semester_encryption_keys.ini')
key = parser.get('encryptionkeys', CURRENT_SEASON + '-' + str(CURRENT_YEAR) + '-' + CURRENT_COURSE_NO)

#TODO: fix the setup of this file so it recognizes the mappings

def verifyLogin():
    if not session.get('app_user'):
        clear_DBsession()
        app.logger.debug('clear_DBsession')
        return redirect(url_for('login'))

#@app.route('/student/', methods=['GET', 'POST'])
def studentJson(name = ""):
    return '{name:rocco,semester:fall18}'
    engine = create_engine('mysql+pymysql://' + username + ':' + password + '@localhost:3306/evaluation', poolclass=NullPool)

    engine.connect()
    Base.metadata.bind = engine
    DBSession = sessionmaker(autoflush=True, bind=engine)
    dbSession = DBSession()

    evalCipher = EvalCipher("we_welcome_u_2_fall_2018")

    semester = dbSession.query(Student).filter_by(id = id, week = week, semester_id = semester_id, name = name).all()

    return '{name:rocco,semester:fall18}'
