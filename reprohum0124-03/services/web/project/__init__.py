# This is the webapp for hosting Prolific surveys for the Edinburgh Napier University lab within the reprohum project.
# The data is in csv format, containing the data from the survey. File name should be data.csv
# The user interface is the interface.html file, which is a template for the survey.
# Each interface has the following structure ${outputb1} where inside the brackets is the name of the variable.
# There can be multiple variables - which should be defined in the python code to match the variable names in the csv file.
import json
import jinja2
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, render_template_string, send_from_directory, send_file
import csv
import pandas as pd
import re
import uuid as uuid_lib
import os
from random import shuffle
import numpy as np
import os
import html
from datetime import datetime, timezone
import random
import sqlite3
from uuid import uuid4
from flask_sqlalchemy import SQLAlchemy
import psycopg2
import zipfile
from pathlib import Path


from flask_apscheduler import APScheduler


MAX_TIME = 4800  # Maximum time in seconds that a task can be assigned to a participant before it is abandoned - 1 hour = 3600 seconds
                 # Should probably note the 1hr limit on the interface/instructions.
                 # NOTE: If you do not want to expire tasks, set this to a very large number, 0 will not work.


COMPLETIONS_PER_TASK = 10  # Number of times each task should be completed by different participants
NUMBER_OF_TASKS = 6  # Number of tasks to create in the database


### study data from file
 
rom_data = {}

reg_df = pd.read_csv('project/rom_input/reprohum_reg_data.csv')

for id in reg_df["id"]:

    this_trial = reg_df.loc[reg_df["id"] == id]

    list_id = this_trial["list_id"].item()

    trial_id = this_trial["trial_id"].item()

    text_snippet = this_trial["text_snippet"].item()

    rdf_data = {} 


    for i in range(1,8):

        # exclude empty rdfs for those with less than 7 triples
        if pd.isna(this_trial[f"rel_{i}"].item()):
            continue
        
        
        rdf_data[i] = {}
        rdf_data[i]["subj"] = this_trial[f"subj_{i}"].item()
        rdf_data[i]["rel"] = this_trial[f"rel_{i}"].item()
        rdf_data[i]["pat"] = this_trial[f"pat_{i}"].item()
    
    rom_data[list_id] = rom_data.get(list_id, {})
    rom_data[list_id][trial_id] = rom_data[list_id].get(trial_id, {})
    rom_data[list_id][trial_id]["text_snippet"] = html.unescape(text_snippet.replace("b'", "").replace("\\n\'", ""))
    rom_data[list_id][trial_id]["rdf_data"] = rdf_data
    rom_data[list_id][trial_id]["trial_id"] = trial_id


order_data = {}

trial_order_df = pd.read_csv('project/rom_input/trial_orders.csv')

for l in trial_order_df["list_id"]:
    list_order = list(trial_order_df.loc[trial_order_df["list_id"] == l, "trial_1":].values[0])
    order_data[l] = list_order





# IDpedia:)

# list_id: 1 to 6, six lists of 24 trials each, configured by original authors
# trial_id: id for each of the WebNLG instances, each id is associated with 6 text snippets (trials) from different systems + original text
# session_id: id supplied from prolific, needed for posting to prolific when a participant has completed
# prolific_id: Id for each participant
# task_id: id of the task, 60 tasks in a whole (10 per list)
# item_id: ordinal id for trials, such that we can identify in which (randomly shuffled) order the trials were presented

# endOfIDpedia

#create app



app = Flask(__name__) # Create the flask app
app.config.from_object("project.config.Config")


### django-style Postgresql schemata
 

db = SQLAlchemy(app)


scheduler = APScheduler()

scheduler.init_app(app)



class Participant(db.Model):
    __tablename__ = "participants"

    prolific_id = db.Column(db.String(128), primary_key=True) 
    name = db.Column(db.String(128), nullable=True)
    age = db.Column(db.String(128), nullable=True)
    nationality = db.Column(db.String(128), nullable=False)
    sex = db.Column(db.String(128), nullable=True)
    proficiency = db.Column(db.String(128), nullable=False)
    native_language = db.Column(db.String(128), nullable=False)
    
    def __init__(self, pid, name, age, nationality, sex, prof, nat):
        self.prolific_id = pid
        self.name = name
        self.age = age
        self.nationality = nationality
        self.sex = sex
        self.proficiency = prof
        self.native_language = nat


class Task(db.Model):
    __tablename__ = "tasks"

    t_id = db.Column(db.String(128), primary_key=True)
    list_id = db.Column(db.Integer, nullable=False)
    prolific_id = db.Column(db.String(128), nullable=True)
    time_allocated = db.Column(db.String(128), nullable=True)
    session_id = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(128), nullable=False)

    def __init__(self, t_id, list_id, pid, time, sid, status):

        self.t_id = t_id
        self.list_id = list_id
        self.prolific_id = pid
        self.time_allocated = time
        self.session_id = sid
        self.status = status


class Result(db.Model):
    __tablename__ = "results"

    id = db.Column(db.String(128), unique=True, primary_key=True)
    task_id = db.Column(db.String(128))
    json_string = db.Column(db.Text)
    prolific_id = db.Column(db.String(128))


    def __init__(self, id, task_id, json, pid):

        self.id = id
        self.task_id = task_id
        self.json_string = json
        self.prolific_id = pid


import sqlite3
from uuid import uuid4


def initTasks(db):
    """
    Initializes a specified number of tasks in the 'tasks' table with default values.
    Each task will have multiple entries (as defined by COMPLETIONS_PER_TASK) with unique IDs but the same task number.

    :param num_tasks: The number of tasks to initialize.
    :param db_file: The SQLite database file.
    """
    default_status = 'waiting'
    
    all_tasks = []
    # Insert the specified number of tasks, repeated according to COMPLETIONS_PER_TASK
    for list_id in range(1, NUMBER_OF_TASKS + 1):
        for _ in range(COMPLETIONS_PER_TASK):
            # Generate a unique ID for the task
            task_id = str(uuid4())
            # Execute the SQL query
            all_tasks.append(Task(task_id, list_id, None, None, None, default_status))
    db.session.add_all(all_tasks)
    db.session.commit()
    
    
# --------------------------------------------------

# 
# This function will allocate a task to a participant (prolific_id)
# The allocated task will be updated to have the status 'allocated' and the prolific_id, and session_id and time_allocated will be set.
# It will return the task ID and the task number
# First the function will check if the participant has already been allocated a task (one that is not of status "completed") and return that task if so
# If not, it will find a task that has been assigned less than three times and assign it to the participant
# If no tasks are available, it will return None

def allocate_task(prolific_id, session_id):
    """
    Allocates a task to a participant based on given criteria.

    Parameters:
    prolific_id (str): The ID of the participant.
    session_id (str): The session ID.

    Returns:
    tuple: (task_id, task_number) if a task is allocated, None if no tasks are available,
           or a message and -1 in case of a database error.
    """
        
    try:            
        # equivalent to "SELECT id, list_id FROM tasks WHERE prolific_id=? AND status!='completed'", (prolific_id,)
        allocated_ = db.session.execute(db.select(Task).where(Task.prolific_id == prolific_id, Task.status != "completed")).scalars()
        #allocated_tasks = db.session.scalars(alloca)
        allocated_tasks = [x for x in allocated_]
        print("Already allocated tasks: ")
        for x in allocated_tasks:
            print(x.t_id, x.prolific_id, x.status)

            # Check if the participant has an incomplete allocated task
        if len([x for x in allocated_tasks]) > 0:
            print("Some task was already allocated for this participant")
            this_task = allocated_tasks[0]   # .first()
            return this_task.t_id, this_task.list_id

        else:

            # Find a task that hasn't been assigned to this participant and has been assigned less than three times
            
            #equivalent to """
            #    SELECT id, list_id FROM tasks 
            #    WHERE status='waiting' AND list_id NOT IN (
            #        SELECT list_id FROM tasks WHERE prolific_id=? AND status='completed'
            #    )
            # """, (prolific_id,))

            already_ = db.session.execute(db.select(Task.list_id).where(Task.prolific_id == prolific_id, Task.status == "completed")).scalars()
            already_list = []
            print("Already completed tasks by this participant:")
            for x in already_:
                print(x)
                already_list.append(x)
            if len(already_list) > 0:
                print("You have already completed a task!")
                return None, -1





            waiting_tasks = db.session.scalars(db.session.query(Task).where(Task.status == "waiting", Task.list_id.not_in(already_)))
            waiting_tasks = [x for x in waiting_tasks]        
            print("Waiting Tasks: ")


            if len(waiting_tasks) > 0:


                for x in waiting_tasks:
                    
                    task_limit = db.session.scalars(db.session.query(Task).where(Task.list_id == x.list_id, Task.status == "allocated"))
                    if len([x for x in task_limit]) < 10:
                        possibly_allocated = db.session.query(Task).filter_by(t_id = x.t_id)

                        print("candidate tasks: ")
                        for w in possibly_allocated:
                            print(w.t_id, w.prolific_id, w.list_id, w.status)

                        current_time = datetime.strftime(datetime.now(timezone.utc), '%Y-%m-%d %H:%M:%S.%f%z')

                        possibly_allocated.update(dict(status="allocated", prolific_id=prolific_id, time_allocated=current_time, session_id=session_id))
        
                        db.session.commit()
                        return x.t_id, x.list_id
            else:
                print("No tasks left")
                return None, None

    except:
        db.session.rollback()
        # Consider logging the error
        return "error", -1


# This function will be run periodically and expire tasks that have been allocated for too long
# eg 2023-11-27 15:45:30.123456

def expire_tasks(time_limit=3600):
    """
    Expires tasks that have been allocated for longer than a specified time limit.

    This function checks all tasks with the status 'allocated' and compares the
    time they were allocated with the current time. If the time elapsed since
    allocation is greater than the time limit, the task's status is reset to 'waiting'.

    Parameters:
    time_limit (int): The time limit in seconds. Tasks allocated for longer than this
                      duration will be expired. Defaults to 3600 seconds (1 hour).

    Returns:
    None: The function doesn't return a value but updates the tasks in the database
          if they exceed the time limit.
    """
    try:
        


        allocated_tasks = db.session.scalars(db.session.query(Task).where(Task.status == "allocated"))
        current_time = datetime.now(timezone.utc)
        for t in allocated_tasks:   
            task_time = datetime.strptime(t.time_allocated, '%Y-%m-%d %H:%M:%S.%f%z')

            delta = (current_time - task_time).seconds
            if delta > time_limit:
                print("EXPIRATION")
                print(f"{t.t_id} abandoned")

                db.session.query(Task).filter_by(t_id = t.t_id).update(dict(status="waiting", prolific_id=None, time_allocated=None, session_id=None))
                db.session.commit()



    except:
        print(f"An error occurred trying to expire tasks")

def complete_task(id, json_string, prolific_id):
    """
    Completes a task assigned to a participant and records the result.

    This function checks if the task with the given ID is allocated to the participant
    identified by their prolific ID. If so, it updates the task's status to 'completed'
    and inserts the task result (provided as a JSON string) into the results table.

    Parameters:
    id (str): The ID of the task to be completed.
    json_string (str): A JSON string representing the result of the task.
    prolific_id (str): The ID of the participant who is completing the task.

    Returns:
    int: -1 if the task is not allocated to the participant, otherwise no explicit return value.
    """
    
    this_task = db.session.scalars(db.session.query(Task).where(Task.t_id == id, Task.prolific_id == prolific_id))

    if len([x for x in this_task]) == 0:
        print("empty!")
        return -1
    else:
        result_uuid = str(uuid4())
        db.session.add(Result(result_uuid, id, json_string, prolific_id))
        db.session.query(Task).filter_by(t_id = id, prolific_id = prolific_id).update(dict(status="completed"))
        db.session.commit()



def get_all_tasks():
    """
    Retrieves all tasks from the tasks table in the database.

    This function queries the database for all entries in the tasks table.
    It is intended to fetch every task, regardless of its status or other attributes.

    Returns:
    list: A list of tuples, where each tuple represents a task with all its database fields.
          Returns None if a database error occurs.
    """
    try:
        task_data = []
        all_tasks = db.session.scalars(db.session.query(Task))
        for x in all_tasks:
            task_data.append(tuple([x.t_id, x.list_id, x.prolific_id, x.time_allocated, x.session_id, x.status]))
        return task_data
    except:
        
        return [("No entries to retrieve from the database or db error",)]
    

def get_specific_result(result_id):
    """
    Retrieves a specific result from the results table based on the result ID.

    This function is designed to query the database for a single entry in the results
    table that matches the provided result ID. It returns the specific result associated
    with that ID.

    Parameters:
    result_id (int): The ID of the result to be retrieved.

    Returns:
    tuple: A tuple representing the result with all its database fields, or None if
           the result is not found or a database error occurs.
    """
    try:
        alls = db.session.scalars(db.session.query(Result).where(Result.task_id == result_id))
        spec = alls.first()
        return [tuple([spec.id, spec.task_id, spec.json_string, spec.prolific_id])]
    except:
        
        return [("No results retrievable from the database or db error", )]


def register_participant(pid, name, age, gender, country, native, prof):

    try:
        db.session.add(Participant(pid, name, age,country, gender, prof, native))
        db.session.commit()
    except:
        # participant already registered
        pass







# Routes

@app.route('/return_to_prolific', methods=['GET', 'POST'])
def return_to_prolific():

    prolific_pid = request.args.get('prolific_pid')
    session_id = request.args.get('session_pid')

    all_tasks = db.session.execute(db.select(Task).where(Task.t_id!=None)).scalars()
    print("ALL TASKS AFHTER FINISH: ")
    for x in all_tasks:
        print(x.t_id, x.status)

    return render_template("return.html", session_id=session_id, prolific_pid=prolific_pid)

@app.route('/error')
def error():

    return render_template("error.html", message="Could not complete task, probably due to time out. Please contact us via Prolific.")

@app.route('/submit', methods=['GET', 'POST'])
def submit():

    if request.method == 'POST':
        print(request.json)

        # Save JSON to file with task_id as the folder and uuid as the filename
        task_id = request.json['task_id']
        session_id = request.json['session_id']
        prolific_pid = request.json['prolific_pid']

        # Complete the task
        print(task_id, request.json, prolific_pid)

        complete = complete_task(task_id, str(request.json), prolific_pid)

        if complete == -1:
            print("Something went wrong")
            return redirect(url_for('error'))

        print("everything worked fine")
        return redirect(url_for('return_to_prolific', prolific_pid=prolific_pid, session_id=session_id))
    else:
        raise Exception("DATA NOT WRITTEN")
        return "Nothing Here.", 200


@app.route("/tableex/", methods=['GET', 'POST'])
def tableex():

    static_list = []
    for file in os.listdir(app.config["STATIC_FOLDER"]):
        static_list.append((file,))
    return render_template("data.html", data=static_list)


@app.route('/', methods=['POST', 'GET'])
def consent():

    prolific_pid = request.args.get('PROLIFIC_PID')
    session_id = request.args.get('SESSION_ID')


    return render_template('consent.html', participant_id=prolific_pid, session_id=session_id)

@app.route('/intro', methods=['POST', 'GET'])
def index():

    # Get PROLIFIC_PID, STUDY_ID and SESSION_ID from URL parameters
    prolific_pid = request.args.get('PROLIFIC_PID')
    session_id = request.args.get('SESSION_ID')



    return render_template('intro.html', participant_id=prolific_pid, session_id=session_id)




@app.route('/prepare/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        print("POST")
        print(request.is_json)
        print(request.json, type(request.json))
        session_id = request.json['session_id']
        prolific_pid = request.json['prolific_pid']

        name = request.json['name']
        age = request.json['age']
        gender = request.json['gender']
        country = request.json['country']
        native_language = request.json['native_language']
        english_proficiency_level = request.json['lang_prof']
  
        register_participant(prolific_pid, name, age, gender, country, native_language, english_proficiency_level)


        return redirect(url_for('study', PROLIFIC_PID=prolific_pid, SESSION_ID=session_id))#, code=307)


# Study route, get PROLIFIC_PID, STUDY_ID and SESSION_ID from URL parameters

@app.route('/study/', methods=['GET', 'POST'])
def study():

    print("routed to study")
    prolific_pid = request.args.get('PROLIFIC_PID')
    session_id = request.args.get('SESSION_ID')

    print(prolific_pid, session_id)
    
    if prolific_pid is None or session_id is None:
        return "PROLIFIC_PID and SESSION_ID are required parameters.", 400
    else:
        task_id, list_id = allocate_task(prolific_pid, session_id)

        if task_id == "error" and list_id == -1:
            
            return render_template("error.html", message="Database error. Please contact us through Prolific.")

        elif task_id == None and list_id == -1:

            return render_template("error.html", message="You have already completed a task before. You cannot participate twice.")

        elif task_id == None and list_id == None:

            return render_template("error.html", message="There are no tasks left. You cannot participate anymore. Please return to Prolific.")

        else:                


            trial_keys = order_data[int(list_id)]

            template_data = [rom_data[int(list_id)][x] for x in trial_keys]



            print(os.getcwd())
            return render_template("interface.html", session_id=session_id, task_id=task_id, list_id = list_id, prolific_pid=prolific_pid, data=template_data)

# This route is used for testing - it will return the tasks dictionary showing the number of participants assigned to each task
@app.route('/tasksallocated')
def aloced():

    tasks = get_all_tasks()

    return render_template("data.html", data=tasks)# tasks, 200

# Show a specific task_id's result in the database
@app.route('/results/<task_id>')
def results(task_id):
    result = get_specific_result(str(task_id))
    
    return render_template("data.html", data=result) #str(result)


@app.route('/abdn')
def check_abandonment():
    print("Checking for abandoned tasks...")
    expire_tasks(MAX_TIME) # Do not update MAX_TIME manually, use MAX_TIME variable

    tasks = get_all_tasks()

    return render_template("data.html", data=tasks)# tasks, 200



@app.route('/download')
def serve_db():


    def convert_to_csv():
        engine = db.get_engine() 
        connection = engine.connect()
        
        metadata = db.metadata # MetaData()
        p_table = db.Table("participants", metadata, autoload_with=engine)
        r_table = db.Table("results", metadata, autoload_with=engine)
        t_table = db.Table("tasks", metadata, autoload_with=engine)
        
        p = db.select(p_table)
        t = db.select(t_table)
        r = db.select(r_table)

        p_data = connection.execute(p).fetchall()
        t_data = connection.execute(t).fetchall()
        r_data = connection.execute(r).fetchall()

        p_path = Path("/home/app/web/project/participants.csv")
        r_path = Path("/home/app/web/project/results.csv")
        t_path = Path("/home/app/web/project/tasks.csv")

        p_path.parent.mkdir(parents=True, exist_ok=True)  
        r_path.parent.mkdir(parents=True, exist_ok=True)  
        t_path.parent.mkdir(parents=True, exist_ok=True)  
    
        p_df = pd.DataFrame(p_data)
        r_df = pd.DataFrame(r_data)
        t_df = pd.DataFrame(t_data)
        
        p_df.to_csv(p_path, index=False)
        r_df.to_csv(r_path, index=False)
        t_df.to_csv(t_path, index=False)

        return p_path, r_path, t_path


    p_file, r_file, t_file = convert_to_csv()
    file_list = [p_file, r_file, t_file]
    with zipfile.ZipFile('/home/app/web/project/data.zip', 'w') as zipMe:
        for file in file_list:
            zipMe.write(file, compress_type=zipfile.ZIP_DEFLATED)

    return send_file('/home/app/web/project/data.zip', download_name="reprohum_reg_db.zip")



# Scheduler


@scheduler.task('interval', id='do_job_1', seconds=MAX_TIME, misfire_grace_time=900)
def reset_abandoned():
    with scheduler.app.app_context():
        check_abandonment()
    

scheduler.start()


# CLI Entry Point (for testing) - python main.py

if __name__ == '__main__':
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.run(debug=True)

