import sys
sys.path.append("lib/python2.7/site-packages/")

from flask import Flask, render_template, url_for, request, redirect, session

#from flask.ext.session import Session
import * from toJSON
from sqlalchemy import create_engine, distinct, asc, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Student, Base, Groups, Semester, Group_Student, Enrollment, Evaluation, EncryptedEvaluation, EncryptedManagerEval
from ConfigParser import SafeConfigParser
from encrypt import EvalCipher
from highcharts import Highchart
from itertools import groupby
from sqlalchemy import func, and_
from sqlalchemy.orm import aliased
from sqlalchemy.sql import exists
import copy
import operator
import os
import subprocess
import json
import time
import collections
from drawManagerGrid import drawThickRectangle, getColorFromValue, drawBoxedItem, generateCollageImage, generateIndividualImages, adjustValue

from sqlalchemy.pool import NullPool

#https
from OpenSSL import SSL

context = SSL.Context(SSL.SSLv23_METHOD)
#cer = os.path.join(os.path.dirname(__file__), 'certificate/tintin.cs.indiana.edu.crt')
#ssl_key = os.path.join(os.path.dirname(__file__), 'certificate/tintin.cs.indiana.edu.key')
cer = os.path.join(os.path.dirname(__file__), 'certificate/snowy.sice.indiana.edu.cer')
ssl_key = os.path.join(os.path.dirname(__file__), 'certificate/snowy.sice.indiana.edu.key')



# If you want to debug the sentiment analysis, you can do so by uncommenting the lines in report.html for sentiment analysis
# or you can just view the source of the page to see it...
#

decodeUTF=True


round_digits = 3
tokenRange = 100
chart_folder = 'templates/charts/'
parser = SafeConfigParser()
parser.read('config.ini')
username = parser.get('login', 'username')
password = parser.get('login', 'password')
schema = parser.get('login', 'schema')
host = parser.get('login', 'host')
port = parser.get('login', 'port')

CURRENT_SEASON = parser.get('currentsem', 'season')
CURRENT_YEAR = int(parser.get('currentsem', 'year'))
CURRENT_COURSE_NO = parser.get('currentsem', 'course_no')


BAD_ADJECTIVES = parser.get('adjectives', 'BAD_ADJECTIVES').replace(' ','').split(",")
GOOD_ADJECTIVES = parser.get('adjectives', 'GOOD_ADJECTIVES').replace(' ','').split(",")

weightsForAverageRank = []
for weight in parser.get('constants', 'weights_for_average_rank').split(','):
    weightsForAverageRank.append(int(weight))

app = Flask(__name__)
db_session = None

#######

parser.read('semester_encryption_keys.ini')
key = parser.get('encryptionkeys', CURRENT_SEASON + '-' + str(CURRENT_YEAR) + '-' + CURRENT_COURSE_NO)
evalCipher = EvalCipher(key)

#must be enabled to allow session variables to be stored
app.config['CSRF_ENABLED'] = True
app.config['SECRET_KEY'] = key



raw_options = {
    'chart':{
            'width': 1000,
            'height' : 500,
    },
    'title':{
    },
    'xAxis': {
        'allowDecimals': False,
        'title': {
                'enabled': True,
        },
        'labels': {
            'formatter': 'function () {\
                return this.value;\
            }'
        },
        'showLastLabel': True
    },
    'yAxis': {
        'reversedStacks' : False,
        'min' : -1,
        'max' : 1,
        'reversed': True,
            'title': {

            },
            'labels': {
                'formatter': "function () {\
                    return this.value;\
                }"
            },
            'lineWidth': 2
    },
    'legend': {
            'enabled': True,
            'layout' : 'vertical',

    },
        'tooltip': {
            'headerFormat': '<b>{series.name}</b><br/>',
            'pointFormat': 'Rank {point.y} : Week {point.x}'
        },
    'navigation':{
            'buttonOptions':{
                'enabled': False,
            }
    },
}
@app.route('/main', methods=['GET', 'POST'])
def main():

    #print "session['client_session_auth']: "
    #print session['client_session_auth']

    #if not db_session:
    if not db_session or not session['client_session_auth']:
        return redirect(url_for('login'))

    if request.method == 'POST':
        semester_id = request.form['semester']
        if request.form['submit'] == 'Get reports':
            week=request.form['week']
            #print "URL"
            #print url_for('reports', semester_id=semester_id, currentWeek=week)
            #print "END URL"
            return redirect(url_for('reports', semester_id=semester_id, currentWeek=week))
        elif request.form['submit'] == 'Set student alias_name':
            return redirect(url_for('set_alias', semester_id=semester_id))
        elif request.form['submit'] == 'Student drop class':
            return redirect(url_for('drop_class', semester_id=semester_id))
        elif request.form['submit'] == 'Get Manager Report':
            week=request.form['week']
            return redirect(url_for('manager_report', semester_id=semester_id, currentWeek=week))
        elif request.form['submit'] == 'Logout':
            #set session to False
            session['client_session_auth'] = False
            return redirect(url_for('login'))

    else:
        semesters = db_session.query(Semester).all()
        semesters.reverse()

        weeks = db_session.query(distinct(Groups.week)).all()
        return render_template('main.html', semesters=semesters, weeks=weeks, str=str)

@app.route('/manager-report/<int:semester_id>/<int:currentWeek>', methods=['GET', 'POST'])
def manager_report(semester_id, currentWeek):
    #if not session['client_session_auth']:
    if not db_session or not session['client_session_auth']:
        return redirect(url_for('login'))
    # names is a map from "user_name" to "alias_name" (if exists) or "first_name last_name"
    names = mapNames(queryStudents(semester_id))

    semester = db_session.query(Semester).filter_by(id=semester_id).one()

    encrypted_evals = db_session.query(EncryptedEvaluation).filter(EncryptedEvaluation.semester==semester, EncryptedEvaluation.week==currentWeek, EncryptedEvaluation.manager_id.isnot(None)).order_by(asc(
    EncryptedEvaluation.evalee_id))

    manager_list = db_session.query(distinct(encrypted_evals.subquery().c.evalee_id)).all()

    ###########  REPEAT FROM REGULAR EVAL TO GET DATA FOR GENERATING CHARTS

    # list of students
    students = queryStudents(semester_id)

    # which weeks do two students work together, connection[student1][student2] = [week1, week2]
    connection = queryConnection(students, semester)

    # Evaluation dictionary: evals[currentWeek][evaler][evalee] = evaluation
    evals = []
    # normalized ranks dictionary: reversedEvals[Week][evalee][evaler][0] = evaluation
    #                              reversedEvals[Week][evalee][evaler][1] = normalized_rank
    #                              reversedEvals[Week][evalee][evaler][1] = normalized_token
    reversedEvals = []
    # sort evaler according to current week and rank
    sortedEvaler = []
    # average rank: averageRank[week][student]
    averageRank = []
    # average token: averageToken[week][student]
    averageToken = []

    #Need to pass averageRank through inside
    evals, reversedEvals, sortedEvaler, averageRank, averageToken = queryEvals(currentWeek, semester_id, students, connection)

    #############  END REPEAT

    managerEvals = {}
    avgMgrEvals = {}
    for manager in manager_list:
        manager_id = manager[0]
        managerEvals[manager_id] = {}
        for encrypted_eval in encrypted_evals.all():
            if manager_id == encrypted_eval.evalee_id:
                encryptedMgrEval = db_session.query(EncryptedManagerEval).filter_by(manager_id=encrypted_eval.manager_id).first()
                mgrEval = evalCipher.decryptManagerEval(encryptedMgrEval)

                #ADJUST FOR RAWLINS - change in drawManagerGrid::adjustValue if you want to change it back
                mgrEval.approachable_attitude=adjustValue(mgrEval.approachable_attitude)
                mgrEval.team_communication=adjustValue(mgrEval.team_communication)
                mgrEval.client_interaction=adjustValue(mgrEval.client_interaction)
                mgrEval.decision_making=adjustValue(mgrEval.decision_making)
                mgrEval.resource_utilization=adjustValue(mgrEval.resource_utilization)
                mgrEval.follow_up_to_completion=adjustValue(mgrEval.follow_up_to_completion)
                mgrEval.task_delegation_and_ownership=adjustValue(mgrEval.task_delegation_and_ownership)
                mgrEval.encourage_team_development=adjustValue(mgrEval.encourage_team_development)
                mgrEval.realistic_expectation=adjustValue(mgrEval.realistic_expectation)
                mgrEval.performance_under_stress=adjustValue(mgrEval.performance_under_stress)


                eval = evalCipher.decryptEval(encrypted_eval)
                #decode bad chars
                if decodeUTF:
                    eval.description  = eval.description.decode('utf8')

                managerEvals[manager_id][encrypted_eval.evaler_id] = []
                managerEvals[manager_id][encrypted_eval.evaler_id].append(mgrEval)
                managerEvals[manager_id][encrypted_eval.evaler_id].append( eval.description )




        for manager in managerEvals:
            avgMgrEvals[manager] = {}

            avgMgrEvals[manager]['approachable_attitude'] = []
            avgMgrEvals[manager]['team_communication'] = []
            avgMgrEvals[manager]['client_interaction'] = []
            avgMgrEvals[manager]['decision_making'] = []
            avgMgrEvals[manager]['resource_utilization'] = []
            avgMgrEvals[manager]['follow_up_to_completion'] = []
            avgMgrEvals[manager]['task_delegation_and_ownership'] = []
            avgMgrEvals[manager]['encourage_team_development'] = []
            avgMgrEvals[manager]['realistic_expectation'] = []
            avgMgrEvals[manager]['performance_under_stress'] = []

            approachable_attitude = 0.0
            team_communication = 0.0
            client_interaction = 0.0
            decision_making = 0.0
            resource_utilization = 0.0
            follow_up_to_completion = 0.0
            task_delegation_and_ownership = 0.0
            encourage_team_development = 0.0
            realistic_expectation = 0.0
            performance_under_stress = 0.0


            #pus={}

            for evaler in managerEvals[manager]:
                e = managerEvals[manager][evaler][0]
                approachable_attitude = approachable_attitude + e.approachable_attitude
                team_communication = team_communication + e.team_communication
                client_interaction = client_interaction + e.client_interaction
                decision_making = decision_making + e.decision_making
                resource_utilization = resource_utilization + e.resource_utilization
                follow_up_to_completion = follow_up_to_completion + e.follow_up_to_completion
                task_delegation_and_ownership = task_delegation_and_ownership + e.task_delegation_and_ownership
                encourage_team_development = encourage_team_development + e.encourage_team_development
                realistic_expectation = realistic_expectation + e.realistic_expectation
                performance_under_stress = performance_under_stress + e.performance_under_stress

                ####TODO jasonayoder
                #print "pus"
                #print pus
                #print "averageRank"
                #print averageRank
                #print "evaler"
                #print evaler
                #print "averageRank[-1][evaler]"
                #print averageRank[-1][evaler]

                #pus[evaler]={"value":e.performance_under_stress, "weight": averageRank[-1][evaler]}
                #print "pus[evaler]"
                #print pus[evaler]


            num_of_evalers = len(managerEvals[manager])
            avgMgrEvals[manager]['approachable_attitude'].append(round(approachable_attitude/num_of_evalers , round_digits))
            avgMgrEvals[manager]['team_communication'].append(round(team_communication/num_of_evalers , round_digits))
            avgMgrEvals[manager]['client_interaction'].append(round(client_interaction/num_of_evalers , round_digits))
            avgMgrEvals[manager]['decision_making'].append(round(decision_making/num_of_evalers , round_digits))
            avgMgrEvals[manager]['resource_utilization'].append(round(resource_utilization/num_of_evalers , round_digits))
            avgMgrEvals[manager]['follow_up_to_completion'].append(round(follow_up_to_completion/num_of_evalers , round_digits))
            avgMgrEvals[manager]['task_delegation_and_ownership'].append(round(task_delegation_and_ownership/num_of_evalers , round_digits))
            avgMgrEvals[manager]['encourage_team_development'].append(round(encourage_team_development/num_of_evalers , round_digits))
            avgMgrEvals[manager]['realistic_expectation'].append(round(realistic_expectation/num_of_evalers , round_digits))
            avgMgrEvals[manager]['performance_under_stress'].append(round(performance_under_stress/num_of_evalers , round_digits))

            #TODO jasonayoder
            #avgMgrEvals[manager]['performance_under_stress'].append( pus[evaler] )
            #print "avgMgrEvals[manager]"
            #print avgMgrEvals[manager]


        filename = generateImageFromManagerValues(avgMgrEvals, names, semester_id, currentWeek )

    return render_template('manager-report.html', semester=semester, currentWeek=currentWeek, managerEvals=managerEvals, avgMgrEvals=avgMgrEvals, names=names, filename=filename)


def generateImageFromManagerValues( reports, names, semester_id, currentWeek ):
    values={}
    filename="semester_"+str(semester_id)+"_week_"+str(currentWeek)+"_"+ time.strftime("%H_%M_%S")
    for manager in reports.keys():
        report = reports[manager]
        values[names[manager]]=[ report['approachable_attitude'][0], report['team_communication'][0],  report['client_interaction'][0], report['decision_making'][0], report['follow_up_to_completion'][0],    report['task_delegation_and_ownership'][0], report['encourage_team_development'][0], report['realistic_expectation'][0], report['performance_under_stress'][0] ]
        #TODO jasonayoder
        #print "report['performance_under_stress'][1]"
        #print report['performance_under_stress'][1]

    generateCollageImage(values, filename)
    generateIndividualImages(values, filename, names)

    return filename



@app.route('/reports/<int:semester_id>/<int:currentWeek>', methods=['GET', 'POST'])
def reports(semester_id, currentWeek):


    print "session: ", session

    #if not session['client_session_auth']:
    if not db_session or not session['client_session_auth']:
        return redirect(url_for('login'))
    semester = db_session.query(Semester).filter_by(id=semester_id).one()

    # list of students
    students = queryStudents(semester_id)

    # which weeks do two students work together, connection[student1][student2] = [week1, week2]
    connection = queryConnection(students, semester)

    # Evaluation dictionary: evals[currentWeek][evaler][evalee] = evaluation
    evals = []
    # normalized ranks dictionary: reversedEvals[Week][evalee][evaler][0] = evaluation
    #                              reversedEvals[Week][evalee][evaler][1] = normalized_rank
    #                              reversedEvals[Week][evalee][evaler][1] = normalized_token
    reversedEvals = []
    # sort evaler according to current week and rank
    sortedEvaler = []
    # average rank: averageRank[week][student]
    averageRank = []
    # average token: averageToken[week][student]
    averageToken = []

    #Need to pass averageRank through inside
    evals, reversedEvals, sortedEvaler, averageRank, averageToken = queryEvals(currentWeek, semester_id, students, connection)


    # sort students by unweighted average rank
    sortedByAverageRank = sorted(averageRank[currentWeek-1], key=averageRank[currentWeek-1].get)


    # names is a map from "user_name" to "alias_name" (if exists) or "first_name last_name"
    names = mapNames(students)

    # isStudentActive is a map from "user_name" to student's status in class
    isStudentActive = mapActiveStudents(students)

    # students name list who fail to submit eval
    missingNames = missingEvalers(currentWeek, evals, students)

    # compute weighted average rank
    weightedRank = computeWeightedRanks(currentWeek, connection, reversedEvals, weightsForAverageRank)

    # generate performance trend comparison chart for all students
    compareChart(currentWeek, students, names, averageRank)

    # generate performance trend chart for each student
    generateCharts(currentWeek, students, names, averageRank, averageToken)

    # most frequent adjective for each evalee, adjectives[evalee] = adjective
    adjectives = mostFrequentAdjectives(currentWeek, reversedEvals, averageRank)

    # list of names of the project that each team is on
    teamNames = getTeamNames(students, currentWeek, semester_id)

    thisWeekTeamNames = getTeamNames(students, currentWeek+1, semester_id)


    studentsByTeamLastWeek = sorted( teamNames.items(), key=operator.itemgetter(1) )
    studentsByTeamThisWeek = sorted( thisWeekTeamNames.items(), key=operator.itemgetter(1) )

    for i in range(0, len(studentsByTeamLastWeek)):
        studentsByTeamLastWeek[i] = studentsByTeamLastWeek[i][0]

    for i in range(0, len(studentsByTeamThisWeek)):
        studentsByTeamThisWeek[i] = studentsByTeamThisWeek[i][0]



    #reversedEvals[currentWeek-1][student_id][evaler][0].description

    for student in students:
        student_id = student.user_name
        if student_id in reversedEvals[currentWeek-1].keys():
            for evaler in reversedEvals[currentWeek-1][student_id].keys():
                #trying to fix bug
                if decodeUTF:
                    reversedEvals[currentWeek-1][student_id][evaler][0].description = reversedEvals[currentWeek-1][student_id][evaler][0].description.decode('utf8')
                else:
                    reversedEvals[currentWeek-1][student_id][evaler][0].description = reversedEvals[currentWeek-1][student_id][evaler][0].description

                description=reversedEvals[currentWeek-1][student_id][evaler][0].description
                #reversedEvals[currentWeek-1][student_id][evaler][0].description = negativeSentiment(description) + description

                reversedEvals[currentWeek-1][student_id][evaler][0].sentiment = negativeSentiment(description)



    return render_template('reports.html',
        semester=semester,
        currentWeek=currentWeek,
        students=students,
        sortedByAverageRank=sortedByAverageRank,
        names=names,
        isStudentActive=isStudentActive,
        missingNames=missingNames,
        connection=connection,
        evals=evals,
        reversedEvals=reversedEvals,
        sortedEvaler=sortedEvaler,
        averageRank=averageRank,
        averageToken=averageToken,
        len=len,
        weightedRank=weightedRank,
        adjectives=adjectives,
        teamNames=teamNames,
        thisWeekTeamNames=thisWeekTeamNames,
        BAD_ADJECTIVES=BAD_ADJECTIVES,
        GOOD_ADJECTIVES=GOOD_ADJECTIVES,
        studentsByTeamLastWeek=studentsByTeamLastWeek,
        studentsByTeamThisWeek=studentsByTeamThisWeek
        )

def negativeSentiment(description):
    proc = subprocess.Popen(["curl", "-d", "text="+description, "http://text-processing.com/api/sentiment/"], stdout=subprocess.PIPE)
    (out, err) = proc.communicate()
    obj = json.loads(out)

    neg_label= obj["label"] == "neg"
    neg_minus_pos_neu=obj["probability"]["neg"]-obj["probability"]["pos"]-obj["probability"]["neutral"] > 0
    neg_minus_pos=obj["probability"]["neg"]-obj["probability"]["pos"] > 0.4
    neg_high=obj["probability"]["neg"] > 0.8
    neg_med=obj["probability"]["neg"] > 0.71
    neg_low=obj["probability"]["neg"] > 0.65

    ret= "LABEL:"+str(obj["label"])
    ret+= "  negative:"+ str(round(obj["probability"]["neg"],2))
    ret+= "  neutral:"+ str(round(obj["probability"]["neutral"],2))
    ret+= "  positive:"+ str(round(obj["probability"]["pos"],2))


    if neg_label and ( neg_med or neg_low and (neg_minus_pos_neu or neg_minus_pos or neg_high )):
        diff=(obj["probability"]["neg"]-obj["probability"]["pos"]-obj["probability"]["neutral"])
        #return "[NEGATIVE NLTK]" # Neg-Pos-Neu: "+str(neg_minus_pos_neu)+" Neg-Pos "+str(neg_minus_pos)+"  "+str(obj["probability"])
        return "NEGATIVE "+ret
    else:
        return ret
        #return "POSITIVE Neg-Pos-Neu: "+str(neg_minus_pos_neu)+" Neg-Pos "+str(neg_minus_pos)+"  "+str(obj["probability"])


# get list of students for specified semester
def queryStudents(semester_id):
    students = []
    enrollments = db_session.query(Enrollment).filter_by(semester_id=semester_id).all()
    for enrollment in enrollments:
        student = enrollment.student_id
        students.append(enrollment.student)
    return students
# get connection matrix for students
def queryConnection(students, semester):
    connection = {}
    #intialize connection
    for student1 in students:
        #print str(student1)
        connection[student1.user_name] = {}
        for student2 in students:
            connection[student1.user_name][student2.user_name] = []

    #assign connection - must query by both semester and group
    groups = db_session.query(Groups).filter_by(semester=semester).all()
    for group in groups:
        studentsInGroup = db_session.query(Group_Student).filter_by(group_id=group.id).all()
        for student1 in studentsInGroup:
            for student2 in studentsInGroup:
                if student1 != student2:
                    connection[student1.student_id][student2.student_id].append(int(group.week))
    return connection

# query evaluation for each week
def queryEvalByWeek(semester_id, week, students, connection):
    # Evaluation dictionary: evalsOneWeek[evaler][evalee] = evaluation
    evalsOneWeek = {}
    # normalized ranks dictionary: reversedEvalsOneWeek[evalee][evaler][0] = evaluation
    #                           reversedEvalsOneWeek[evalee][evaler][1] = normalized_rank
    #                           reversedEvalsOneWeek[evalee][evaler][2] = normalized_token
    reversedEvalsOneWeek = {}
    # sort evaler according to current week and rank
    sortedEvalerOneWeek = {}
    # average rank
    averageRankOneWeek = {}
    # average token
    averageTokenOneWeek = {}

    for student in students:
        evaler = student.user_name
        evalsOneWeek[evaler] = {}
        evalsFromOneStudent = db_session.query(EncryptedEvaluation).filter_by(evaler_id=evaler, week=int(week), semester_id=semester_id).all()
        for encryptedEval in evalsFromOneStudent:
            eval = evalCipher.decryptEval(encryptedEval)
            evalee = eval.evalee_id
            evalsOneWeek[evaler][evalee] = eval

        for evalee, eval in evalsOneWeek[evaler].iteritems():
            if not reversedEvalsOneWeek.get(evalee):
                reversedEvalsOneWeek[evalee] = {}
            reversedEvalsOneWeek[evalee][evaler] = []
            reversedEvalsOneWeek[evalee][evaler].append(eval)
            numberOfEval = len(evalsOneWeek[evaler])
            reversedEvalsOneWeek[evalee][evaler].append(round((eval.rank - (numberOfEval + 1.0) / 2.0 ) / numberOfEval, round_digits))
            reversedEvalsOneWeek[evalee][evaler].append( round( ( ( 100.0 / len(evalsOneWeek[evaler] )) - eval.token ) / ( 100.0 / len(evalsOneWeek[evaler]) ), round_digits)  )

    #sort evaler for each evalee
    for evalee in reversedEvalsOneWeek:
        sortedEvalerOneWeek[evalee] = []

        #sort by rank that evaler gives to evalee - not what we want, but will resort it below
        sortedByRank = sorted(reversedEvalsOneWeek[evalee].items(), key=lambda e: e[1][1]) #[1][3]

        #put current team members top
        sortedEvalerOneWeek[evalee].append([])
        for item in sortedByRank:
            evaler = item[0]
            if week in connection[evalee][evaler]:
                sortedEvalerOneWeek[evalee][0].append(evaler)
        # non-current team members
        sortedEvalerOneWeek[evalee].append([])
        for item in sortedByRank:
            evaler = item[0]
            if week not in connection[evalee][evaler]:
                sortedEvalerOneWeek[evalee][1].append(evaler)

    for evalee in reversedEvalsOneWeek:
        flag = True
        for student in students:
            if student.user_name == evalee and not student.is_active:
                flag = False
                break
        if not flag:
            continue
        averageRankOneWeek[evalee] = 0
        averageTokenOneWeek[evalee] = 0
        for evaler in reversedEvalsOneWeek[evalee]:
            rank = reversedEvalsOneWeek[evalee][evaler][1]
            token = reversedEvalsOneWeek[evalee][evaler][2]
            averageRankOneWeek[evalee] += rank / len(reversedEvalsOneWeek[evalee])
            averageTokenOneWeek[evalee] += token / len(reversedEvalsOneWeek[evalee])
        averageRankOneWeek[evalee] = round(averageRankOneWeek[evalee], round_digits)


    #### use averageRankOneWeek to update the order on  sortedByRank
    #This is a pretty significant chicken or the egg problem, because the calculations are so involved
    #It is easier to just update the order after the fact.

    #sort evaler for each evalee
    for evalee in reversedEvalsOneWeek:
        sortedEvalerOneWeek[evalee] = []

        #TODO: this seems to cause an error when I remove a student from being active (srri...)
        #Might need to do a safety check somehow
        #This data is not accessible in the loop above, so we just use it to update here after it exists above

        sortedByRank = sorted(reversedEvalsOneWeek[evalee].items(), key=lambda e: averageRankOneWeek[e[0]] if e[0] in averageRankOneWeek else [] )

        #put current team members top
        sortedEvalerOneWeek[evalee].append([])
        for item in sortedByRank:
            evaler = item[0]
            if week in connection[evalee][evaler]:
                sortedEvalerOneWeek[evalee][0].append(evaler)
        # non-current team members
        sortedEvalerOneWeek[evalee].append([])
        for item in sortedByRank:
            evaler = item[0]
            if week not in connection[evalee][evaler]:
                sortedEvalerOneWeek[evalee][1].append(evaler)

    return evalsOneWeek, reversedEvalsOneWeek, sortedEvalerOneWeek, averageRankOneWeek, averageTokenOneWeek

def queryEvals(currentWeek, semester_id, students, connection):
    evals = []
    reversedEvals = []
    sortedEvaler = []
    averageRank = []
    averageToken = []
    for week in range(1, currentWeek+1):
        #NEED averageRank
        evalsOneWeek, reversedEvalsOneWeek, sortedEvalerOneWeek, averageRankOneWeek, averageTokenOneWeek = queryEvalByWeek(semester_id, week, students, connection)
        evals.append(evalsOneWeek)
        reversedEvals.append(reversedEvalsOneWeek)
        sortedEvaler.append(sortedEvalerOneWeek)
        averageRank.append(averageRankOneWeek)
        averageToken.append(averageTokenOneWeek)

    return evals, reversedEvals, sortedEvaler, averageRank, averageToken



def compareChart(currentWeek, students, names, averageRank):
    if not os.path.exists(chart_folder):
        os.makedirs(chart_folder)
    raw_options['chart']['height'] = 800
    options = copy.deepcopy(raw_options)
    options['title']['text'] = 'Normalized Rank Comparison Chart'
    options['yAxis']['title']['text'] = 'Normalized Rank'
    options['xAxis']['title']['text'] = 'Week'
    chart = Highchart()
    chart.set_dict_options(options)
    series = []

    print averageRank[currentWeek-1]

#    for student, r in averageRank[currentWeek-1].items():
    for student in students:
        if student.user_name not in averageRank[currentWeek-1]:
            averageRank[currentWeek-1][student.user_name]=1000


    for student in sorted(students, key=lambda s: averageRank[currentWeek-1][s.user_name] ):

        if averageRank[currentWeek-1][student.user_name]==1000 or not student.is_active:
            continue
        name = names[student.user_name]
        data = []
        for week in range(1, currentWeek + 1):
            rank = averageRank[week-1].get(student.user_name)
            if rank is not None:
                point = [week, rank]
                data.append(point)
        series.append({'name': name, 'data': data})
        #splie
        chart.add_data_set(data, 'line', name, marker={'enabled': True})
    #options['series'] = series
    chart.save_file(chart_folder + 'compare')

def generateCharts(currentWeek, students, names, averageRank, averageToken):
    if not os.path.exists(chart_folder):
        os.makedirs(chart_folder)
    raw_options['chart']['height'] = 500
    options = copy.deepcopy(raw_options)
    options['yAxis'] = [{
        'min' : -1,
        'max' : 1,
        'reversed': True,
            'title': {
                'text': 'Normalized Rank'
            },
            'labels': {
                'formatter': "function () {\
                    return this.value;\
                }"
            },
            'lineWidth': 2
    },
    {
            'min' : -1,
            'max' : 1,
            'reversed': True,
            'title': {
                'text': 'Normalized Token'
            },
            'labels': {
                'formatter': "function () {\
                    return this.value;\
                }"
            },
            'lineWidth': 2,
            'opposite': True
    },
    ]
    options['xAxis']['title']['text'] = 'Week'
    for student in students:
        if not student.is_active:
            continue
        chart = Highchart()
        options['title']['text'] = names[student.user_name]
        options['chart']['renderTo'] = 'container_' + student.user_name
        chart.set_dict_options(options)
        rank_data = []
        token_data = []
        for week in range(1, currentWeek + 1):
            rank = averageRank[week-1].get(student.user_name)
            token = averageToken[week-1].get(student.user_name)
            if rank is not None and token is not None:
                point = [week, rank]
                rank_data.append(point)
                point = [week, token]
                token_data.append(point)
        #spline
        chart.add_data_set(rank_data, 'line', 'Normalized Rank', marker={'enabled': True})
        chart.add_data_set(token_data, 'line', 'Normalized Token', marker={'enabled': True}, yAxis=1)
        chart.save_file(chart_folder + student.user_name)

def mapNames(students):
    names = {}
    for student in students:
        if student.alias_name:
            names[student.user_name] = student.alias_name
        else:
            names[student.user_name] = student.first_name + " " + student.last_name
    return names

def mapActiveStudents(students):
    isStudentActive = {}
    for student in students:
        isStudentActive[student.user_name] = student.is_active
    return isStudentActive

def missingEvalers(currentWeek, evals, students):
    missingNames = []
    for student in students:
        if not evals[currentWeek-1].get(student.user_name) and student.is_active:
           missingNames.append(student.user_name)
    return missingNames

def computeWeightedRanks(currentWeek, connection, reversedEvals, weightsForAverageRank):
    weightedRank = {}
    for evalee in reversedEvals[currentWeek-1]:
        weightedRank[evalee] = 0
        weightsSum = 0
        for evaler in reversedEvals[currentWeek-1][evalee]:
            rank = reversedEvals[currentWeek-1][evalee][evaler][1]
            weeks = connection[evalee][evaler]
            for week in weeks:
                weightedRank[evalee] += rank * weightsForAverageRank[week-1]
                weightsSum += weightsForAverageRank[week-1]

        #TEMP to stop error on old data
        if weightsSum == 0:
           weightsSum = 1
           print "WARNING MISSING WEIGHTSSUM USING VALUE OF 1"

        weightedRank[evalee] = round(weightedRank[evalee] / weightsSum, round_digits)
    return weightedRank

def getTeamNames(students, currentWeek, semester_id):
    result = {}

    #lookup each student_id from teh list of students provided
    for student in students:
        student_id = student.user_name

        #do an outer join on Groups and Group_Student, filtering allows you to constrain the results
        groupsrow = db_session.query(Groups, Group_Student).\
            filter(Groups.id==Group_Student.group_id).\
            filter(Group_Student.student_id==student_id, Groups.week==currentWeek, Groups.semester_id==semester_id).\
            all()


        if ( len(groupsrow) == 1):
            groups = groupsrow[0][0]
            group_student = groupsrow[0][1]
            result.update( {student_id: groups.name} )
        elif (len(groupsrow) > 1 ):
            print "Warning: there were multiple rows returned!"
        else:
            print "Warning: size zero!"

    return result


def mostFrequentAdjectives(currentWeek, reversedEvals, averageRank):

    result = {}
    for evalee in reversedEvals[currentWeek-1]:
        dict = {}

        first=True
        topEvaler=""
        for student, normrank in sorted(averageRank[currentWeek-1].iteritems(), key=operator.itemgetter(1)):

            if student in reversedEvals[currentWeek-1][evalee]:
                evaler = student
                if first:
                    topEvaler=student
                    first=False

                # for evaler in reversedEvals[currentWeek-1][evalee]:
                adjs = reversedEvals[currentWeek-1][evalee][evaler][0].adjective.split(' ,.')
                for adj in adjs:
                    count = dict.get(adj)
                    if not count:
                        count = 0
                    dict[adj] = count + 1

                freqAdjective = max(dict.iteritems(), key=operator.itemgetter(1))[0]

                #If there is only one common adjective, then pick the top ranker evaluator
                if (dict[freqAdjective] == 1):
                    freqAdjective=reversedEvals[currentWeek-1][evalee][topEvaler][0].adjective

                occurrence = freqAdjective + ' (' + str(dict[freqAdjective])+ ')'
                result[evalee] = occurrence
    return result

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    global db_session
    if request.method == 'POST':
        username_from_form = request.form['username']
        pwd = request.form['password']
        engine = create_engine('mysql://' + username + ':' + pwd + '@' + host +':' + port + '/' + schema)
        try:
            engine.connect()
            Base.metadata.bind = engine
            DBSession = sessionmaker(bind=engine)
            db_session = DBSession()


            # we need to have a variable stored per each connected user which indicates whether or not that user
            # has been logged in successfully
            # normally session will do that, but

            #print session
            #session = Session()
            #print session
            #session['username'] = username
            #session['username']=username
            #print session

            if username == username_from_form and pwd == password:
                session['client_session_auth'] = True
            else:
                session['client_session_auth'] = False

            return redirect(url_for('main'))
        except:

            session['client_session_auth'] = False
            error = 'Invalid Credentials. Please try again.'
            return render_template('admin_login.html', error=error)
    return render_template('admin_login.html')

@app.route('/set_alias/<int:semester_id>', methods=['GET', 'POST'])
def set_alias(semester_id):
    students = queryStudents(semester_id)
    if request.method == 'POST':
        student_id = request.form['student']
        alias = request.form['alias_name']
        student = db_session.query(Student).filter_by(user_name=student_id).one()
        student.alias_name = alias
        db_session.commit()
    return render_template('alias.html', students=students)

@app.route('/drop_class/<int:semester_id>', methods=['GET', 'POST'])
def drop_class(semester_id):
    students = queryStudents(semester_id)
    if request.method == 'POST':
        student_id = request.form['student']
        student = db_session.query(Student).filter_by(user_name=student_id).one()
        if request.form['submit'] == 'Add':
            student.is_active = 1
        elif request.form['submit'] == 'Drop':
            student.is_active = 0
        db_session.commit()
    return render_template('drop.html', students=students)
if __name__ == '__main__':
    context = (cer, ssl_key)
    app.debug = True
    app.run(host='0.0.0.0', port=9009, ssl_context=context)
