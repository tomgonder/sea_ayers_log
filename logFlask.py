from flask import Flask, request, session, g, jsonify, redirect, url_for, abort, \
     render_template, flash, _app_ctx_stack, send_from_directory

import csv
from sqlite3 import dbapi2 as sqlite3
import json
from datetime import datetime
import re
import urllib2
import sys
import os
from contextlib import closing
from werkzeug import secure_filename
import unidecode
import logging

log_data_type = ( 'Dive', 'Fish', 'Fix', 'Ent.', 'Info', 'other')
log_array = [ ]
inventory_data_type = ( 'Added', 'Removed', 'Sold')
inventory_array = [ ]
log_config = None

# when used on the RASPI
#ROOT_DIR='/usr/local/www/ship_log'
#ROOT_DIR='/Library/WebServer/Documents/logFlask'
ROOT_DIR='/Users/tgonder/DEV/sea_ayers_log/logFlask'

DATABASE=ROOT_DIR + '/LOG.db'
DATABASE_SCHEMA='LOG.schema.sql'

CONFIG_FILE = ROOT_DIR + '/logFlask.config'
LOG_FILE = ROOT_DIR + '/logFlask.log'

logging.basicConfig( filename=LOG_FILE, level=logging.DEBUG )

#ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])
ALLOWED_EXTENSIONS = set(['jpg', 'jpeg'])


app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_pyfile('logFlask.cfg', silent=True)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
UPLOAD_FOLDER='uploads/'
app.config['UPLOAD_FOLDER'] = ROOT_DIR + '/' + UPLOAD_FOLDER


def connect_db():
    #print 'connect_db()... DB',app.config['DATABASE']
    try:
        return sqlite3.connect(app.config['DATABASE'])
    except Exception,e:
        print 'Exception: e',e


def init_db():
    print 'init_db()...'
    with closing(connect_db()) as db:
        with app.open_resource(DATABASE_SCHEMA, mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


@app.before_request
def before_request():
    #print 'before_request()...'
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    #print 'teardown_request()...'
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()




def allowed_file(filename):
    return '.' in filename and \
           filename.lower().rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


def clear_session_filter():
    session['search_filter'] = None
    session['search_filter_page'] = 1







'''
*************************
'''
@app.route('/')
def index():
    session['logged_in'] = False
    return redirect(url_for('log'))


'''
*************************
'''
@app.route('/login', methods=['POST'])
def do_admin_login():
    print 'do_admin_login()'
    if request.form['password'] == 'mbh' and request.form['username'] == 'henry':
        session['logged_in'] = True
        return redirect(url_for('log'))
    else:
        flash('wrong password!')
        return render_template('login.html')



'''
*************************
'''
@app.route("/logout")
def logout():
    session['logged_in'] = False
    return log()



'''
*************************
'''
@app.route('/log')
def log():
    print 'log()...'
    if not session.get('logged_in'):
        return render_template('login.html')

    try:
        filter = session['search_filter']
        page = session['search_filter_page']
    except:
        filter = None
        page = 1

    init(filter=filter, page=page)

    hasPrev = page > 1
    return render_template('show_entries.html', entries=log_array, config=log_config, doFilter=True, doAdd=True, hasPrev=hasPrev)

'''
*************************
'''
@app.route('/map')
def map():
    print 'map()...'
    if not session.get('logged_in'):
        return render_template('login.html')

    return render_template('map.html', config=log_config, doAdd=False)


'''
*************************
'''
@app.route('/show_inventory')
def show_inventory():
    print 'show_inventory()...'
    if not session.get('logged_in'):
        return render_template('login.html')

    init_inventory_log()
    return render_template('show_inventory.html', entries=inventory_array, config=log_config)




'''
*************************
'''
@app.route('/delete_entry', methods=['GET', 'POST'])
def delete_entry():
    print 'delete_entry()...'
    if not session.get('logged_in'):
        return render_template('login.html')

    if  request.method == 'POST':
        submit_type = request.form['btn']
        print 'submit:',submit_type
        if submit_type == 'Delete':
            id = request.args.get('id', None)
            try:
                print 'trying SQL DELETE for {0}...'.format(id)
                g.db.execute('delete from entries where id=?', [ id ])
                print 'successfully DELETED LOG entry'
                g.db.commit()
            except Exception,e:
                print 'SQL delete() ERROR',e

    return redirect(url_for('log'))

'''
*************************
'''
@app.route('/delete_inventory', methods=['GET', 'POST'])
def delete_inventory():
    print 'delete_inventory()...'
    if not session.get('logged_in'):
        return render_template('login.html')

    if  request.method == 'POST':
        submit_type = request.form['btn']
        print 'submit:',submit_type
        if submit_type == 'Delete':
            id = request.args.get('id', None)
            try:
                print 'trying SQL DELETE for {0}...'.format(id)
                g.db.execute('delete from inventory where id=?', [ id ])
                print 'successfully DELETED INVENTORY entry'
                g.db.commit()
            except Exception,e:
                print 'SQL delete() ERROR',e

    return redirect(url_for('show_inventory'))



def print_session_data():
    try:
        for entry in session:
            print 'log.session',entry,':',session[entry]
    except:
        pass


'''
*************************
'''
@app.route('/filter', methods=['GET', 'POST'])
def filter():
    print 'filter()... Type: {0}'.format(request.method)
    if not session.get('logged_in'):
        return render_template('login.html')


    try:
        if  request.method == 'POST':
            filter = request.form['FILTER']
            print 'filter:',filter," type:",type(filter)

            session['search_filter'] = filter
            session['search_filter_page'] = 1

            for s in ('SEARCH_ABOARD_ONLY', 'SEARCH_CASE_SENSITIVE'):
                try:
                    session[s] = (request.form[s] == 'on')
                except:
                    session[s] = False
                print 'setting',s," is ",session[s]


            print 'SET filter:',session['search_filter']
            print 'SET filter page:',session['search_filter_page']
            print 'SET filter search only aboard:',session['SEARCH_ABOARD_ONLY']
            print 'SET filter search case:',session['SEARCH_CASE_SENSITIVE']
            #print 'CONFIG:',log_config
    except Exception,e:
        print 'Failed to process filter e:',e

    try:
        filter = session['search_filter']
        page = session['search_filter_page']
    except:
        filter = None
        page = 1

    init(filter=filter, page=page)
    hasPrev = page > 1
    return render_template('show_entries.html', entries=log_array, config=log_config, filter=filter, doFilter=True, doAdd=True, page=page, hasPrev=hasPrev)


'''
*************************
'''
@app.route('/home')
def home():
    print 'home()...'
    if not session.get('logged_in'):
        return render_template('login.html')


    session['search_filter'] = ''
    session['search_filter_page'] = 1

    init(filter=None, page=1)
    return render_template('show_entries.html', entries=log_array, config=log_config, doFilter=True, doAdd=True, hasPrev=False)

'''
*************************
'''
@app.route('/first')
def first():
    print 'first()...'
    if not session.get('logged_in'):
        return render_template('login.html')


    try:
        filter = session['search_filter']
    except:
        filter = None

    session['search_filter_page'] = 1

    init(filter=filter, page=1)
    return render_template('show_entries.html', entries=log_array, config=log_config, doFilter=True, doAdd=True, hasPrev=False)



'''
*************************
'''
@app.route('/last')
def last():
    print 'last()...'
    if not session.get('logged_in'):
        return render_template('login.html')


    try:
        filter = session['search_filter']
        page = session['last_page']
        print 'page:', page
        session['search_filter_page'] = page
    except:
        filter = None
        page = 1


    init(filter=filter, page=page)
    hasPrev = page > 1
    return render_template('show_entries.html', entries=log_array, config=log_config, doFilter=True, doAdd=True, hasPrev=hasPrev)





'''
*************************
'''
@app.route('/prev')
def prev():
    print 'prev()...'
    if not session.get('logged_in'):
        return render_template('login.html')


    try:
        filter = session['search_filter']
        page = session['search_filter_page']

        # check to prevent it from going negative
        if int(page) > 1:
            page = int(page) - 1
            session['search_filter_page'] = page
    except:
        session['search_filter'] = None
        session['search_filter_page'] = 1
        filter = None
        page = 1

    init(filter=filter, page=page)
    hasPrev = page > 1
    return render_template('show_entries.html', entries=log_array, config=log_config, doFilter=True, doAdd=True, hasPrev=hasPrev)

'''
*************************
'''
@app.route('/next')
def next():
    print 'next()...'
    if not session.get('logged_in'):
        return render_template('login.html')


    hasPrev = True
    try:
        filter = session['search_filter']
        page = session['search_filter_page']

        page = int(page) + 1
        session['search_filter_page'] = page
    except:
        session['search_filter'] = None
        session['search_filter_page'] = 1
        filter = None
        page = 1
        hasPrev = False


    init(filter=filter, page=page)
    error = None
    return render_template('show_entries.html', entries=log_array, config=log_config, doFilter=True, doAdd=True, hasPrev=hasPrev)




'''
*************************
'''
@app.route('/entry', methods=['GET', 'POST'])
def entry():
    print 'entry()... Type: {0}'.format(request.method)
    if not session.get('logged_in'):
        return render_template('login.html')

    load_config()

    date = ''
    aboard = ''
    details = ''
    lobsters_caught = ''
    log_type_html = ''
    log_type = 'Dive'
    for html_type in log_data_type:
        style = ' style="background-image:url(static/{0}.png);"'.format(html_type.lower())
        log_type_html =  log_type_html + '<option value="' + html_type + '"' + style + '>' + html_type + '</option>'
    #print log_type_html

    error = None
    info = None

    if  request.method == 'GET':
        id = request.args.get('id', None)
        if id != None:
            print 'entry for id:',id
            try:
                cur = g.db.execute('select id, date, log_type, aboard, details, lobsters_caught from entries where id is {0}'.format(id))
                print 'after cursor'
                db_row = cur.fetchall()[0]
                #print 'db_row:',db_row
                cur.close()
            except Exception,e:
                print 'Failed to get DB entry for ',id,' e:',e

            date = db_row[1]
            log_type = db_row[2]
            aboard = db_row[3]
            details = db_row[4]
            lobsters_caught = db_row[5]
            # modify the html to set the type to be "selected"
            log_type_html =  re.sub('value=\"' + log_type + "\"",'value=\"' + log_type + "\" selected", log_type_html)
        else:
            # must be for a new log entry
            info = 'You MUST hit Save to record log entry!'
            try:
                date = datetime.today().strftime('%Y-%m-%d')
            except:
                date = ''

            try:
                aboard = log_config['CAPTAIN']
            except:
                aboard = ''

        return render_template('entry.html', id=id, config=log_config, error=error, info=info, date=date,
                               log_type_html=log_type_html, aboard=aboard, details=details, lobsters_caught=lobsters_caught)

    elif  request.method == 'POST':
        try:
            submit_type = request.form['btn']
            print 'submit:',submit_type
            if submit_type == 'Cancel':
                return redirect(url_for('log'))
            elif submit_type == 'Delete':
                id = request.args.get('id', None)
                delete_url = url_for('delete_entry')
                print 'delete_url:',delete_url
                return render_template('confirm_delete.html', delete_url=delete_url, id=id, message='Are you sure you want to delete this log entry?')

            try:
                date = str(request.form['LOG_DATE'])
                #print 'date:',date
                aboard = str(request.form['ABOARD'])
                print 'TAG TLG aboard:',aboard
                u_details = request.form['DETAILS']
                print 'u_details:',type(u_details),':',u_details
                details = unidecode.unidecode(u_details)
                #details = str(request.form['DETAILS'])
                print 'TAG TLG details:',details
                lobsters_caught = str(request.form['LOBSTERS_CAUGHT'])
                #print 'lobsters_caught:',lobsters_caught
            except Exception,e:
                print 'Detail Exception, e:',e
                error = "Log cannot contain weird characters like ellipse and i with two dots. Use Browser back to return to form."

            log_type = str(request.form['LOG_TYPE'])
            print 'log_type:',log_type

            # massage the details that contain unwanted <div> and </div> markers
            details = re.sub('<div>', '<br>', details)
            details = re.sub('</div>', '', details)

            print 'mod details:',details

            db_date = is_valid_date(date)
            if db_date == None:
                error = 'Date is not valid format. YYYY-MM-DD. e.g. 1969-03-27'


        except:
            pass

        if error:
            return render_template('entry.html', config=log_config, error=error, date=date, log_type_html=log_type_html, aboard=aboard, details=details)
        else:
            db_id = str(request.args.get('id'))

            # replace any quotes with escape-quote
            #aboard = re.sub('"', '\"', aboard)
            #details = re.sub('"', '\"', details)

            print 'db_date',db_date,type(db_date)
            print 'type',log_type,type(log_type)
            print 'aboard',aboard,type(aboard)
            print 'details',details,type(details)
            print 'lobsters_caught',lobsters_caught,type(lobsters_caught)
            try:
                if db_id == 'None':
                    print 'trying to INSERT...'
                    g.db.execute('insert into entries (date, log_type, aboard, details, lobsters_caught) values (?, ?, ?, ?, ?)',
                                 [db_date, log_type, aboard, details, lobsters_caught])
                    print 'successfully saved new LOG entry'

                    if lobsters_caught and lobsters_caught != None and lobsters_caught > 0:
                        try:
                            inventory_details = 'Dive Trip with ' + aboard
                            print 'try to INSERT a one-time entry into the INVENTORY log for count:',lobsters_caught,inventory_details
                            g.db.execute('insert into inventory (date, lobs_in, lobs_out, money, details) values (?, ?, ?, ?, ?)',
                                         [db_date, str(lobsters_caught), '', '', inventory_details])
                            print 'successfully saved new INVENTORY entry'
                        except Exception,inventoryError:
                            print 'Failed to insert into inventory log for this new log e:',inventoryError


                else:
                    print 'trying to UPDATE',db_id
                    #sql_cmd = 'update entries set date="{0}", log_type="{1}", aboard="{2}", details="{3}" where id={4}'.format(db_date, log_type, aboard, details, db_id)
                    #print sql_cmd
                    g.db.execute('update entries set date=?, log_type=?, aboard=?, details=?, lobsters_caught=? where id=?;',
                                 [db_date, log_type, aboard, details, lobsters_caught, db_id])
                    #g.db.execute(sql_cmd)
                    print 'successfully updated existing LOG entry'
                g.db.commit()
            except Exception,e:
                print 'SQL insert() ERROR',e
            #update_row(id, date, log_type, aboard, details)

            return redirect(url_for('log'))
    else:
        # we're doing a GET
        aboard = ''
        try:
            aboard = log_config['CAPTAIN']
        except:
            pass
        return render_template('entry.html', config=log_config, error=error, date=date, log_type_html=log_type_html, aboard=aboard, details=details)




'''
*************************
'''
@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    print 'inventory()... Type: {0}'.format(request.method)
    if not session.get('logged_in'):
        return render_template('login.html')

    load_config()

    date = ''
    lobsters_in = ''
    lobsters_out = ''
    money = ''
    details = ''

    error = None
    info = None
    id = None

    if  request.method == 'GET':
        id = request.args.get('id', None)
        if id != None:
            print 'entry for id:',id
            try:
                cur = g.db.execute('select id, date, lobs_in, lobs_out, money, details from inventory where id is {0}'.format(id))
                db_row = cur.fetchall()[0]
                #print 'db_row:',db_row
                cur.close()
            except Exception,e:
                print 'Failed to get Inventory DB entry for ',id,' e:',e

            date = db_row[1]
            lobsters_in = db_row[2]
            lobsters_out = db_row[3]
            money = db_row[4]
            details = db_row[5]
        else:
            # must be for a new log entry
            info = 'You MUST hit Save to record inventory entry!'
            try:
                date = datetime.today().strftime('%Y-%m-%d')
            except:
                date = ''

        return render_template('inventory.html', id=id, config=log_config, error=error, info=info, date=date,
                               lobsters_in=lobsters_in, lobsters_out=lobsters_out, money=money, details=details)

    elif  request.method == 'POST':
        try:
            submit_type = request.form['btn']
            print 'submit:',submit_type
            if submit_type == 'Cancel':
                return redirect(url_for('show_inventory'))
            elif submit_type == 'Delete':
                id = request.args.get('id', None)
                delete_url = url_for('delete_inventory')
                return render_template('confirm_delete.html', delete_url=delete_url, id=id, message='Are you sure you want to delete this inventory entry?')

            # else we are Creating a new entry
            try:
                date = str(request.form['LOG_DATE'])
                print 'INVENTORY date:',date
                lobsters_in = str(request.form['LOBSTERS_IN'])
                print 'INVENTORY lobsters_in:',lobsters_in
                lobsters_out = str(request.form['LOBSTERS_OUT'])
                print 'INVENTORY lobsters_out:',lobsters_out
                money = str(request.form['MONEY'])
                print 'INVENTORY money:',money
                details = str(request.form['DETAILS'])
                print 'INVENTORY details:',details
            except Exception,e:
                print 'Inventory Request Get Exception, e:',e
                error = "Entry cannot contain weird characters like ellipse and i with two dots. Use Browser back to return to form."

            '''
            inventory_type = str(request.form['INVENTORY_TYPE'])
            print 'inventory_type:',inventory_type
            '''

            # massage the details that contain unwanted <div> and </div> markers
            details = re.sub('<div>', '<br>', details)
            details = re.sub('</div>', '', details)
            print 'mod details:',details

            db_date = is_valid_date(date)
            if db_date == None:
                error = 'Date is not valid format. YYYY-MM-DD. e.g. 1969-03-27'


        except:
            pass

        if error:
            return render_template('inventory.html', config=log_config, error=error, info=info, date=date,
                                   lobsters_in=lobsters_in, lobsters_out=lobsters_out, money=money, details=details)
        else:
            db_id = str(request.args.get('id'))

            # replace any quotes with escape-quote
            #aboard = re.sub('"', '\"', aboard)
            #details = re.sub('"', '\"', details)

            print 'db_date',db_date,type(db_date)
            print 'lobsters_in',lobsters_in,type(lobsters_in)
            print 'lobsters_out',lobsters_out,type(lobsters_out)
            print 'money',money,type(money)
            print 'details',details,type(details)
            try:
                if db_id == 'None':
                    print 'trying to INSERT...'
                    g.db.execute('insert into inventory (date, lobs_in, lobs_out, money, details) values (?, ?, ?, ?, ?)',
                                 [db_date, lobsters_in, lobsters_out, money, details])
                    print 'successfully saved new INVENTORY entry'
                else:
                    print 'trying to UPDATE',db_id
                    #sql_cmd = 'update entries set date="{0}", log_type="{1}", aboard="{2}", details="{3}" where id={4}'.format(db_date, log_type, aboard, details, db_id)
                    #print sql_cmd
                    g.db.execute('update inventory set date=?, lobs_in=?, lobs_out=?, money=?, details=? where id=?;',
                                 [db_date, lobsters_in, lobsters_out, money, details, db_id])
                    #g.db.execute(sql_cmd)
                    print 'successfully updated existing INVENTORY entry for',db_id
                g.db.commit()
            except Exception,e:
                print 'SQL insert() ERROR',e
            #update_row(id, date, log_type, aboard, details)

            return redirect(url_for('show_inventory'))




'''
*************************
'''
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global log_config

    print 'settings()... Type: {0}'.format(request.method)
    if not session.get('logged_in'):
        return render_template('login.html')

    load_config()
    #print 'after ',log_config

    error = None
    if  request.method == 'POST':
        try:
            submit_type = request.form['btn']
            print 'submit:',submit_type

            if submit_type == 'Cancel':
                return redirect(url_for('log'))

            temp_config = dict(log_config)
            try:
                summary_text = int(request.form['SUMMARY_TEXT'])
                if summary_text < 0:
                    raise Exception
                temp_config['SUMMARY_TEXT'] = summary_text
            except:
                error = 'Characters per Summary log must be a valid value between zero and a positive integer'
                temp_config['SUMMARY_TEXT'] = request.form['SUMMARY_TEXT']

            try:
                summary_rows = int(request.form['SUMMARY_ROWS'])
                if summary_rows < 1 or summary_rows > 50:
                    raise Exception
                temp_config['SUMMARY_ROWS'] = summary_rows
            except:
                error = 'Logs per page must be a valid value between 1 and 50'
                temp_config['SUMMARY_ROWS'] = request.form['SUMMARY_ROWS']

            try:
                temp_config['VESSEL'] = str(request.form['VESSEL'])
            except:
                error = 'Vessel must be a valid text string with no special characters'
                temp_config['VESSEL'] = request.form['VESSEL']

            try:
                temp_config['CAPTAIN'] = str(request.form['CAPTAIN'])
            except:
                error = 'Captain must be a valid text string with no special characters'
                temp_config['CAPTAIN'] = request.form['CAPTAIN']


            if error:
                return render_template('settings.html', config=temp_config, error=error)
            else:
                # if we got here the all of the temp_config changes must be valid
                log_config = temp_config
                save_config()
                print 'after save settings:'
                print log_config
                return redirect(url_for('log'))

        except Exception,e:
            print 'error with settings POST e:',e
    else:
        return render_template('settings.html', config=log_config, error=error)



'''
*************************
'''
@app.route('/uploads/<filename>')
def uploads(filename):
    print 'uploads()...'
    if not session.get('logged_in'):
        return render_template('login.html')

    try:
        full_filename = app.config['UPLOAD_FOLDER'] + filename
        print ' got here into uploads...',full_filename
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception,e:
        print 'e:',e



'''
*************************
'''
@app.route('/pictures', methods=['GET', 'POST'])
def pictures():
    print 'pictures()...'
    if not session.get('logged_in'):
        return render_template('login.html')

    load_config()
    filename = None
    if request.method == 'POST':
        try:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_to_filename = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                print 'uploading file:',file,'to',save_to_filename
                file.save(save_to_filename)
                print 'done'
        except Exception,e:
            print 'failed to upload file! e:',e

    images = []
    ct = 0
    print 'looking for images in',app.config['UPLOAD_FOLDER']
    for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
      print 'root:',root
      print 'dirs:',dirs
      for file in files:
        if allowed_file(file):
            ct += 1
            print 'ct:',ct,' file:',root + file
            images.append('uploads/' + file)

    print 'images:',images
    return render_template('pictures.html', filename=filename, images=images, config=log_config)




def is_valid_date(date):
    print 'is_valid_date({0})...'.format(date)
    try:
        return datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m-%d')
    except:
        pass

    return None


def load_config():
    global log_config
    print 'load_config()...'

    try:
        print 'Reading: ', CONFIG_FILE
        with open(CONFIG_FILE, 'r') as f:
            log_config = json.loads(f.read())
            f.close()
            print log_config
    except:
        print 'Failed to load configuration file ',CONFIG_FILE
        log_config = { }
        log_config['CAPTAIN'] = ''
        log_config['VESSEL'] = ''
        log_config['SUMMARY_ROWS'] = 170
        log_config['SUMMARY_TEXT'] = 5



def save_config():
    global log_config
    print 'save_config()...'
    try:
        print 'Writing: ', CONFIG_FILE
        with open(CONFIG_FILE, 'w') as f:
            f.write(json.dumps(log_config))
            f.close()
            print log_config
    except Exception,e:
        print 'Failed to write configuration file ',CONFIG_FILE,'. e:{0}'.format(e)


def init_inventory_log():
    global inventory_array

    print 'into inventory log count...'
    try:
        db_ct = 0
        lobs_in_ct = 0
        lobs_out_ct = 0
        total_income = 0.0
        total_expense = 0.0
        current_season_lobs_in_ct = 0
        current_season_lobs_out_ct = 0
        current_season_total_income = 0.0
        current_season_total_expense = 0.0

        print 'inventory init()...'
        load_config()

        filter_date = None

        #print 'sql() select...'
        cur = g.db.execute('select id, date, lobs_in, lobs_out, money, details from inventory order by date desc, id desc')
        #print 'after cur'
        inventory_array = [ ]
        for db_row in cur.fetchall():
            db_ct += 1
            #print db_row

            id = db_row[0]
            date = db_row[1]
            lobsters_in = db_row[2]
            lobsters_out = db_row[3]
            money = db_row[4]
            details = db_row[5]


            #print 'money:',money,type(money),'money_formatted:',money_formatted

            db_ct += 1

            current_season = False

            row = { }
            row['id']=id
            row['date']=date
            row['lobsters_in']=lobsters_in
            row['lobsters_out']=lobsters_out
            row['money']=money
            row['details']=details

            try:
                date_object = datetime.strptime(date, '%Y-%m-%d')
                row['day_log_format'] = date_object.strftime('%m/%d/%y')

                if filter_date == None:
                    filter_date_str = '07-01-' + str(date_object.timetuple().tm_year)
                    filter_date = datetime.strptime(filter_date_str, '%m-%d-%Y')
                    if date_object < filter_date:
                        # change filter date to the previous July 1st
                        filter_date_str = '07-01-' + str(date_object.timetuple().tm_year - 1)
                        filter_date = datetime.strptime(filter_date_str, '%m-%d-%Y')
                    print filter_date_str,'results in',filter_date


                if date_object > filter_date:
                    #print date_object,'is within filter date',filter_date
                    current_season = True
                    row['current_lobster_season'] = True

            except Exception,e:
                row['day_log_format'] = 'err'
                print e


            try:
                lobs_in_ct += int(lobsters_in)
                if current_season:
                    current_season_lobs_in_ct += int(lobsters_in)
            except:
                pass
            try:
                lobs_out_ct += int(lobsters_out)
                if current_season:
                    current_season_lobs_out_ct += int(lobsters_out)
            except:
                pass

            if money == None or money == '':
                money = 0

            if money == 0:
                money_formatted = ''
            else:
                if money > 0:
                    money_formatted = 'Income $'
                    try:
                        total_income += float(money)
                        if current_season:
                            current_season_total_income += float(money)
                    except:
                        pass
                else:
                    money_formatted = 'Expense $'
                    try:
                        total_expense += float(abs(money))
                        if current_season:
                            current_season_total_expense += float(abs(money))
                    except:
                        pass

                if int(money*100) % 100 == 0:
                    money_formatted += '{:.0f}'.format(abs(money))
                else:
                    money_formatted = '{:.2f}'.format(abs(money))

            row['money_formatted']=money_formatted


            try:
                details_short = None
                char_to_display = log_config['SUMMARY_TEXT']
                if char_to_display > 0:
                    details_short = details[0:char_to_display]
                    if len(details) > char_to_display:
                        details_short += "..."
                row['details_short'] = details_short
            except:
                pass


            #print total_ct,'  - ',row
            inventory_array.append(row)

        # close the DB cursor
        cur.close()
        print 'returning results with inventory_array ct:',len(inventory_array),'total_ct:',db_ct

        session['lobs_freezer_ct'] = lobs_in_ct - lobs_out_ct
        session['lobs_in_ct'] = lobs_in_ct
        session['lobs_out_ct'] = lobs_out_ct
        session['total_income'] = total_income
        session['total_expense'] = total_expense

        session['current_season_lobs_freezer_ct'] = current_season_lobs_in_ct - current_season_lobs_out_ct
        session['current_season_lobs_in_ct'] = current_season_lobs_in_ct
        session['current_season_lobs_out_ct'] = current_season_lobs_out_ct
        session['current_season_total_income'] = current_season_total_income
        session['current_season_total_expense'] = current_season_total_expense


    except Exception,e:
        if details:
            print details
        print 'error:',e
        app.logger.error('init_inventory_log() error. {0}'.format(e))



def init(filter=None, page=1):
    global log_array

    try:
        total_ct = 0
        found_ct = 0
        added_ct = 0
        index = 0
        first_found_index = None

        print 'init()...'
        load_config()

        #print 'Filter:',filter
        page = int(page)
        print 'Looking for page:', page

        logs_per_page = log_config['SUMMARY_ROWS']

        is_search_case = False
        is_search_aboard = False
        try:
            print_session_data()
            is_search_case = session['SEARCH_CASE_SENSITIVE']
            is_search_aboard = session['SEARCH_ABOARD_ONLY']
        except Exception,e:
            print 'Failed to get session data e:',e

        print 'sql() select...'
        cur = g.db.execute('select id, date, log_type, aboard, details, lobsters_caught from entries order by date desc, id desc')
        print 'after cur'
        log_array = [ ]
        for db_row in cur.fetchall():
            total_ct += 1
            #print db_row

            id = db_row[0]
            date = db_row[1]
            log_type = db_row[2]
            aboard = db_row[3]
            details = db_row[4]
            lobsters_caught = db_row[5]


            if filter and filter != '':
                if is_search_case:
                    filter = str(filter)
                    is_date = filter in date
                    is_aboard = filter in aboard
                    is_details = filter in details and not is_search_aboard
                else:
                    filter = str(filter).lower()
                    is_date = filter in date.lower()
                    is_aboard = filter in aboard.lower()
                    is_details = filter in details.lower() and not is_search_aboard
            else:
                filter = None
                is_aboard = False
                is_date = False
                is_details = False

                #if is_aboard or is_date or is_details:
                #    print 'entry id:',id,' at ct:',found_ct,' Filter:',filter,' CASE:',is_search_case,' ABOARD:',is_search_aboard,' filters  date:',is_date,' aboard:',is_aboard,' details:',is_details

            if not filter or is_aboard or is_date or is_details:
                found_ct += 1
                if found_ct > ((page-1) * logs_per_page) and not added_ct >= logs_per_page:
                    #print 'adding entry ',id
                    row = { }
                    row['id']=id
                    row['date']=date
                    row['log_type']=log_type
                    row['aboard']=aboard
                    row['details']=details
                    row['lobsters_caught']=lobsters_caught
                    try:
                        date_object = datetime.strptime(date, '%Y-%m-%d')
                        row['day_log_format'] = date_object.strftime('%b, %d, %Y, %a')
                    except Exception,e:
                        row['day_log_format'] = 'err'
                        print e


                    try:
                        details_short = None
                        char_to_display = log_config['SUMMARY_TEXT']
                        if char_to_display > 0:
                            details_short = details[0:char_to_display]
                            if len(details) > char_to_display:
                                details_short += "..."
                        row['details_short'] = details_short
                    except:
                        pass

                    try:
                        image_url = url_for('static', filename='{0}.png'.format(log_type.lower()))
                    except:
                        image_url = url_for('static', filename='default.png')
                    row['type_image_url'] = image_url

                    row['lobsters_image_url'] = url_for('static', filename='lobster.png')

                    log_array.append(row)
                    added_ct += 1
                    index = found_ct
                    if first_found_index == None:
                        first_found_index = index

        # close the DB cursor
        cur.close()
        print 'returning results with log_array ct:',len(log_array),' index:',index,' filter_ct:',found_ct
    except Exception,e:
        if date and aboard:
            print date,' ',aboard
        if details:
            print details
        print 'error:',e
        app.logger.error('init() error. {0}'.format(e))

    if first_found_index and first_found_index != index:
        on_page_results = '{0}-{1}'.format(first_found_index, index)
    else:
        on_page_results = index

    #on_page_results = index
    if filter:
        session['position_stats'] = '{0} of {1} searched log entries'.format(on_page_results, found_ct)
        ct = found_ct
    else:
        session['position_stats'] = '{0} of {1} total log entries'.format(on_page_results, total_ct)
        ct = total_ct

    session['last_page'] = ct / logs_per_page
    if ct % logs_per_page != 0:
        session['last_page'] += 1

    session['total_ct'] = total_ct
    session['search_filter_index'] = index
    session['search_filter_ct'] = found_ct



if __name__ == '__main__':
    print 'starting Sea Ayers Log...'
    app.secret_key = 'A0Zr98j/3yX R~GGH!jmN]LWX/,?RG'
    #app.run(host="0.0.0.0", port=8080, debug=True, ssl_context='adhoc')
    app.run(host="0.0.0.0", port=8080, debug=True)
