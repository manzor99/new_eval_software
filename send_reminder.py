#Rocco Manzo
#11/30/2018

import sys
import smtplib
from email.mime.text import MIMEText

#takes a list of emails and sends a reminder
def sendEmail(emails):
    msg = MIMEText("Submit your evals by midnight.")
    msg['Subject'] = "Submit Eval"


    for email in emails:
        msg['From'], msg['To'] = "oosdreminder@gmail.com", email
        # Send the message via gmail SMTP server
        s = smtplib.SMTP('smtp.gmail.com', 587)
        #connect to the gmail server
        s.ehlo()
        s.starttls()
        s.login(msg['From'], 'oosdisgreat')
        #TODO: make it parse email and pass from config.ini?
        s.sendmail(msg['From'], [msg['To']], msg.as_string())


        s.quit()

sendEmail(['rmanzo@iu.edu'])
