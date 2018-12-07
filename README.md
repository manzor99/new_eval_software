## Fall2018 Project(rkasture,ppaithan,sbaranwa,rmanzo) updates 12/7/2018

### Steps to run:
    - python database_setup.py
    - python semester-config.py add
    - python student-config.py add
    - python group-config.py add 
    - python student_eval.py
    
### jasonayoder updates 7/31/2017

This folder has a "lib" directory which contains custom pip installed libraries needed to run the software.
There might be a better way to handle this, but currently these libraries are loaded via:

database_setup.py (line ~3)
sys.path.append("lib/python2.7/site-packages/")


#Below is original documentation which is largely obsolete at this point

### eval_project
Develop evaluation and report generation tool for P532 Object-Oriented Software Development 

I use python , sqlAlchemy, flask, mysql. sqlalchemy is python library for mysql database connection. flask is python framework for web development.

To run locally in ubuntu, you may need to install python 2.7, sqlalchemy 0.8.4, flask 0.10.1, mysql.

database_setup.py - it connects to a database(in my case, 'mysql://root:your_password@localhost:3306/eval'), and create database table, you may need to create a database (e.g. 'eval') first before runnint it

populate_database.py - populate the database by some dummy data

main.py - routes urls. 
    /main                       entry page. 
    /reports/semester_id/week   reports for semester_id, week where semester_id and week are int
    
templates/ - html templates


### SETUP steps:
I am using a virtual machine system provided by udacity course, in which all needed  tools were pre-installed. I assume you need install ubuntu first if you want to setup your own.
