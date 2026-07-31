from flask import Flask, render_template, request, jsonify, send_file, g
import sqlite3, os, shutil, io
from datetime import datetime

def parse_date(s):
    try:
        return datetime.strptime(s, '%d.%m.%Y')
    except:
        return None

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'farm_data.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS app_settings (
        id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS custom_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT, section_name TEXT NOT NULL, created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS custom_columns (
        id INTEGER PRIMARY KEY AUTOINCREMENT, section_id INTEGER, column_name TEXT, column_order INTEGER, include_in_total INTEGER DEFAULT 0
    )''')
    
    # Add include_in_total column if it does not exist
    c.execute("PRAGMA table_info(custom_sections)")
    if 'section_type' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE custom_sections ADD COLUMN section_type TEXT DEFAULT 'expense'")

    c.execute("PRAGMA table_info(custom_columns)")
    if 'include_in_total' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE custom_columns ADD COLUMN include_in_total INTEGER DEFAULT 0")

    c.execute("PRAGMA table_info(custom_columns)")
    if 'formula' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE custom_columns ADD COLUMN formula TEXT DEFAULT NULL")

    c.execute('''CREATE TABLE IF NOT EXISTS partners_master (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, share_percent REAL, phone TEXT,
        cnic TEXT, address TEXT, notes TEXT
    )''')

    # Add is_active column to partners_master if it does not exist (soft delete)
    c.execute("PRAGMA table_info(partners_master)")
    if 'is_active' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE partners_master ADD COLUMN is_active INTEGER DEFAULT 1")

    c.execute('''CREATE TABLE IF NOT EXISTS staff_salary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, name TEXT, designation TEXT,
        salary REAL, days REAL, total_amount REAL,
        advance REAL, salary_paid TEXT, notes TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS partners_payment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, partner_id INTEGER, partner TEXT,
        item TEXT, amount REAL, notes TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS medicine_expenditure (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, item TEXT, amount REAL, notes TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS feed (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, feed_type TEXT, bags INTEGER,
        rate REAL, amount REAL, notes TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS production (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, total_birds INTEGER, eggs_produced INTEGER,
        eggs_sold INTEGER, price_per_egg REAL, buyer_name TEXT, revenue REAL,
        mortality INTEGER, notes TEXT
    )''')

    # Add buyer_name column if it does not exist
    c.execute("PRAGMA table_info(production)")
    if 'buyer_name' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE production ADD COLUMN buyer_name TEXT DEFAULT ''")

    # Extra columns on hardcoded sections (no changes to existing tables)
    c.execute('''CREATE TABLE IF NOT EXISTS section_extra_columns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_name TEXT NOT NULL,
        column_name TEXT NOT NULL,
        column_order INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS section_extra_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_name TEXT NOT NULL,
        row_id INTEGER NOT NULL,
        column_id INTEGER NOT NULL,
        value TEXT,
        UNIQUE(section_name, row_id, column_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS row_colors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_name TEXT NOT NULL,
        row_id INTEGER NOT NULL,
        color TEXT NOT NULL,
        UNIQUE(section_name, row_id)
    )''')

    # Seed partners master
    c.execute("SELECT COUNT(*) FROM partners_master")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO partners_master (name,share_percent,phone,cnic,address,notes) VALUES (?,?,?,?,?,?)", [
            ('Arshad Ali Shaikh', 40, None, None, None, '40% Share Holder'),
            ('Zakir Hussain Utaro', 40, None, None, None, '40% Share Holder'),
            ('Haji Muhammad Khan Shaikh', 20, None, None, None, '20% Share Holder'),
        ])

    # Seed staff salary
    c.execute("SELECT COUNT(*) FROM staff_salary")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO staff_salary (date,name,designation,salary,days,total_amount,advance,salary_paid,notes) VALUES (?,?,?,?,?,?,?,?,?)", [
            (None,'Siddique','Supervisor',None,None,23000,None,'Cleared','March Clear'),
            (None,'Mustafa','Helper',None,None,23000,None,'Cleared','March Clear'),
            (None,'Mustafa','Helper',None,None,5000,None,None,None),
            ('20.04.2026','Siddique Supervisor','Supervisor',None,None,23000,None,'Cleared','April Month'),
            ('22.04.2026','New Helper Ali Gul','Helper',None,None,None,None,None,None),
            ('04.05.2026','Siddique Supervisor','Supervisor',None,None,5700,None,None,'May Month'),
            ('04.05.2026','New Helper Moosa','Helper',None,None,5000,None,None,'May Month'),
            ('.05.2026','Siddique Supervisor','Supervisor',None,None,23000,None,'Cleared','MAY Month Cleared'),
            ('.05.2026','Moosa Helper','Helper',None,None,22500,None,'Cleared','MAY Month Cleared'),
            ('.05.2026','New Helper Shahmir','Helper',None,None,14000,None,None,'Till Now May Month'),
            ('30.05.2026','Siddique Supervisor','Supervisor',None,None,7100,None,None,'Advance of June Month'),
        ])

    # Seed partners payment from updated file
    c.execute("SELECT COUNT(*) FROM partners_payment")
    if c.fetchone()[0] == 0:
        arsh_id = 1
        zk_id = 2
        hmk_id = 3
        arsh_payments = [
            ('05.02.2026',arsh_id,'Arshad Ali Shaikh','Cash Credit in Account of Zakir Hussain Utaro',2000000,None),
            ('10.02.2026',arsh_id,'Arshad Ali Shaikh','Cash Credit in Account of Zakir Hussain Utaro',200000,None),
            ('22.02.2026',arsh_id,'Arshad Ali Shaikh','15 Bags of Cement Transport',23130,None),
            ('24.02.2026',arsh_id,'Arshad Ali Shaikh','Two Packets Iron Keels',700,None),
            ('24.02.2026',arsh_id,'Arshad Ali Shaikh','Two Cement Slabs',1800,None),
            ('25.02.2026',arsh_id,'Arshad Ali Shaikh','Cash Credit AC Meezan of Haji Afzal Utaro',480000,None),
            ('25.02.2026',arsh_id,'Arshad Ali Shaikh','Credit by Arsh in ZK Account',50000,None),
            ('01.03.2026',arsh_id,'Arshad Ali Shaikh','CCTV with 4 Camera Bill',66010,None),
            ('02.03.2026',arsh_id,'Arshad Ali Shaikh','Yaseen Khoso Supervisor',3000,None),
            ('02.03.2026',arsh_id,'Arshad Ali Shaikh','Siddique Panhyar New Supervisor',1000,None),
            ('02.03.2026',arsh_id,'Arshad Ali Shaikh','Roshan Umrani Guard',1000,None),
            ('04.03.2026',arsh_id,'Arshad Ali Shaikh','1000 given to Siddique for Katahs',1000,None),
            ('09.03.2026',arsh_id,'Arshad Ali Shaikh','Makada Fish Pond 3 Years Paid Cash',45000,None),
            ('18.03.2026',arsh_id,'Arshad Ali Shaikh','Siddique Panhyar New Supervisor',5000,None),
            ('18.03.2026',arsh_id,'Arshad Ali Shaikh','Helper Mustafa',4000,None),
            ('05.04.2026',arsh_id,'Arshad Ali Shaikh','Supervisor Siddique',6000,None),
            ('05.04.2026',arsh_id,'Arshad Ali Shaikh','Helper Mustafa',5000,None),
            ('06.04.2026',arsh_id,'Arshad Ali Shaikh','Brooder Maintenance Labor Cost and Transport',2200,None),
            ('06.04.2026',arsh_id,'Arshad Ali Shaikh','2 Water Dram',5600,None),
            ('10.04.2026',arsh_id,'Arshad Ali Shaikh','26.15 Marh Lakri',24842,None),
            ('10.04.2026',arsh_id,'Arshad Ali Shaikh','Brooder Pipe Fitting for Heat with Transport',11500,None),
            ('10.04.2026',arsh_id,'Arshad Ali Shaikh','0 Feed 2 Bags of HS Feeds',15300,None),
            ('11.04.2026',arsh_id,'Arshad Ali Shaikh','0 Feed 23 Bags Online Meezan HS Feed',176640,None),
            ('11.04.2026',arsh_id,'Arshad Ali Shaikh','Zincbooster',5900,None),
            ('11.04.2026',arsh_id,'Arshad Ali Shaikh','NFC100',2200,None),
            ('11.04.2026',arsh_id,'Arshad Ali Shaikh','10 Packets of Owares',240,None),
            ('11.04.2026',arsh_id,'Arshad Ali Shaikh','Ikhbar 10kg',2000,None),
            ('11.04.2026',arsh_id,'Arshad Ali Shaikh','Latun Wali Dorhi 2kg',700,None),
            ('11.04.2026',arsh_id,'Arshad Ali Shaikh','Khaliq Light Man',3500,None),
            ('11.04.2026',arsh_id,'Arshad Ali Shaikh','Mustafa Helper',5000,None),
            ('11.04.2026',arsh_id,'Arshad Ali Shaikh','Siddique Panhyar New Supervisor',4500,None),
            ('14.04.2026',arsh_id,'Arshad Ali Shaikh','NDI Vaccine for Chicks on 5th Day',4050,None),
            ('14.04.2026',arsh_id,'Arshad Ali Shaikh','Herbatox-forte',3500,None),
            ('14.04.2026',arsh_id,'Arshad Ali Shaikh','Maxsalfade for Flashing of Chicks',200,None),
            ('14.04.2026',arsh_id,'Arshad Ali Shaikh','Deoper for Chicks',300,None),
            ('14.04.2026',arsh_id,'Arshad Ali Shaikh','Respifin',1500,None),
            ('15.04.2026',arsh_id,'Arshad Ali Shaikh','Katah for Partition on Vaccination Day',700,None),
            ('18.04.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',2200,None),
            ('18.04.2026',arsh_id,'Arshad Ali Shaikh','Weight Machine 350K in KG',12000,None),
            ('18.04.2026',arsh_id,'Arshad Ali Shaikh','Weight Machine in Grams',1000,None),
            ('19.04.2026',arsh_id,'Arshad Ali Shaikh','Mustafa Helper',10000,None),
            ('19.04.2026',arsh_id,'Arshad Ali Shaikh','Rent of Generator for Debeaking',1250,None),
            ('20.04.2026',arsh_id,'Arshad Ali Shaikh','Brufen Syrup',120,None),
            ('20.04.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',5500,None),
            ('21.04.2026',arsh_id,'Arshad Ali Shaikh','Gumbooro Vaccination + Deoper',7650,None),
            ('21.04.2026',arsh_id,'Arshad Ali Shaikh','Vitamin4',2200,None),
            ('21.04.2026',arsh_id,'Arshad Ali Shaikh','Sheheryar Vaccination Labor Charges',3000,None),
            ('21.04.2026',arsh_id,'Arshad Ali Shaikh','3 Person Labor During Vaccination',1500,None),
            ('22.04.2026',arsh_id,'Arshad Ali Shaikh','30 Days Vaccination paid to Mohsin',106760,None),
            ('22.04.2026',arsh_id,'Arshad Ali Shaikh','Vitamin4 and Vitamin C',8120,None),
            ('23.04.2026',arsh_id,'Arshad Ali Shaikh','Wood Ghutika 5 Munds',4000,None),
            ('24.04.2026',arsh_id,'Arshad Ali Shaikh','Mustafa Helper Final Pay 20 Days',10500,None),
            ('24.04.2026',arsh_id,'Arshad Ali Shaikh','Ghafar Bro Mustafa 3 Days Labour',1500,None),
            ('24.04.2026',arsh_id,'Arshad Ali Shaikh','Vaccination 2 Helper Labour',1000,None),
            ('24.04.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor April Salary',1000,None),
            ('25.04.2026',arsh_id,'Arshad Ali Shaikh','Feed 35 Bags 0 Feed + 15 Bags',378650,None),
            ('25.04.2026',arsh_id,'Arshad Ali Shaikh','Water Cooler and Balti',3650,None),
            ('25.04.2026',arsh_id,'Arshad Ali Shaikh','Petrol of Generator During Debeaking',300,None),
            ('25.04.2026',arsh_id,'Arshad Ali Shaikh','Debeaking 600 Chicks Labor Cost',1000,None),
            ('25.04.2026',arsh_id,'Arshad Ali Shaikh','Generator Rent During Debeaking 600 Chicks',1000,None),
            ('25.04.2026',arsh_id,'Arshad Ali Shaikh','Ali Gul Wages Labor',1250,None),
            ('27.04.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',200,None),
            ('27.04.2026',arsh_id,'Arshad Ali Shaikh','Brufen Syrup, Arinec, Hydrolin',630,None),
            ('28.04.2026',arsh_id,'Arshad Ali Shaikh','Siddique Mobile',2400,None),
            ('28.04.2026',arsh_id,'Arshad Ali Shaikh','Ice Bar for Vaccination',50,None),
            ('28.04.2026',arsh_id,'Arshad Ali Shaikh','Gamboro + ID + IB in 600 Chicks by Maqsood Magsi',1200,None),
            ('28.04.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',300,None),
            ('28.04.2026',arsh_id,'Arshad Ali Shaikh','Net Package of Shed',580,None),
            ('29.04.2026',arsh_id,'Arshad Ali Shaikh','Siddique Package of Net',650,None),
            ('30.04.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',5000,None),
            ('01.05.2026',arsh_id,'Arshad Ali Shaikh','Arinec Syrup and Hydrolin',535,None),
            ('01.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',200,None),
            ('03.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor April Cleared',4300,None),
            ('03.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor Advance May Month',5700,None),
            ('03.05.2026',arsh_id,'Arshad Ali Shaikh','Arinec Syrup and Hydrolin',500,None),
            ('03.05.2026',arsh_id,'Arshad Ali Shaikh','Muhammad Moosa New Helper Advance May Month',5000,None),
            ('06.05.2026',arsh_id,'Arshad Ali Shaikh','Mohsin Bill of Vaccine Elytel',8740,None),
            ('07.05.2026',arsh_id,'Arshad Ali Shaikh','Partition for Chicks 60ft',1575,None),
            ('07.05.2026',arsh_id,'Arshad Ali Shaikh','Bike Petrol for Purchase of Partition',500,None),
            ('07.05.2026',arsh_id,'Arshad Ali Shaikh','Latoon Dori 1kg',520,None),
            ('07.05.2026',arsh_id,'Arshad Ali Shaikh','Mustafa Helper Final Pay 5 Days',4000,None),
            ('09.05.2026',arsh_id,'Arshad Ali Shaikh','Khaliq Light Solar Petrol',500,None),
            ('09.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',4000,None),
            ('09.05.2026',arsh_id,'Arshad Ali Shaikh','Feed 25 Bags 0 Feed',189625,None),
            ('10.05.2026',arsh_id,'Arshad Ali Shaikh','Trip to Karachi for Medicine & Networking by Junaid',11500,None),
            ('10.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',6000,'May Month Till Now 16000'),
            ('10.05.2026',arsh_id,'Arshad Ali Shaikh','New Helper Shahmir Advance',2000,None),
            ('11.05.2026',arsh_id,'Arshad Ali Shaikh','Dr Khaliq Qureshi',10000,'April Cleared'),
            ('12.05.2026',arsh_id,'Arshad Ali Shaikh','Brufen & Jetiber',700,None),
            ('12.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',300,None),
            ('13.05.2026',arsh_id,'Arshad Ali Shaikh','Liver Star Medicine + 600 Chicks Vaccine',6540,None),
            ('14.05.2026',arsh_id,'Arshad Ali Shaikh','Moosa Helper',5000,None),
            ('15.05.2026',arsh_id,'Arshad Ali Shaikh','Lakra for Chicks given to Siddique',600,None),
            ('16.05.2026',arsh_id,'Arshad Ali Shaikh','Labor Cost During Vaccination',1000,None),
            ('16.05.2026',arsh_id,'Arshad Ali Shaikh','Shahmir Helper',5000,None),
            ('16.05.2026',arsh_id,'Arshad Ali Shaikh','Bricks 120',1200,None),
            ('16.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',1000,None),
            ('17.05.2026',arsh_id,'Arshad Ali Shaikh','Aslam Vaccinator',5000,None),
            ('17.05.2026',arsh_id,'Arshad Ali Shaikh','Moosa Helper',500,None),
            ('19.05.2026',arsh_id,'Arshad Ali Shaikh','0 Feed 10 Bags',75650,None),
            ('19.05.2026',arsh_id,'Arshad Ali Shaikh','2 Ton Mesh Contribution',100000,None),
            ('19.05.2026',arsh_id,'Arshad Ali Shaikh','2 Brufen Syrup',260,None),
            ('19.05.2026',arsh_id,'Arshad Ali Shaikh','Vaccination Charges Akhtar Vaccinator',5100,None),
            ('19.05.2026',arsh_id,'Arshad Ali Shaikh','Labor Cost During Vaccination',1900,None),
            ('22.05.2026',arsh_id,'Arshad Ali Shaikh','Belcho, Karni',1050,None),
            ('22.05.2026',arsh_id,'Arshad Ali Shaikh','Chilko 19 Mons + Katah',11235,None),
            ('22.05.2026',arsh_id,'Arshad Ali Shaikh','Transport of Chilko',1700,None),
            ('22.05.2026',arsh_id,'Arshad Ali Shaikh','Moosa Helper',6000,None),
            ('22.05.2026',arsh_id,'Arshad Ali Shaikh','Shahmir Helper',1000,None),
            ('22.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',1000,None),
            ('24.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',2300,None),
            ('24.05.2026',arsh_id,'Arshad Ali Shaikh','Moosa Helper',4000,None),
            ('24.05.2026',arsh_id,'Arshad Ali Shaikh','Shahmir Helper',1000,None),
            ('24.05.2026',arsh_id,'Arshad Ali Shaikh','Elytyl Antibiotic Medicine',6350,None),
            ('24.05.2026',arsh_id,'Arshad Ali Shaikh','Mohsin Bhai Visit to Farm',2000,None),
            ('26.05.2026',arsh_id,'Arshad Ali Shaikh','3 Shalwar Kameez for Labor',4500,None),
            ('26.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',500,None),
            ('26.05.2026',arsh_id,'Arshad Ali Shaikh','Chapals of Labor',2400,None),
            ('26.05.2026',arsh_id,'Arshad Ali Shaikh','Siddique Supervisor',9000,None),
            ('26.05.2026',arsh_id,'Arshad Ali Shaikh','Shahmir Helper',5000,None),
            ('26.05.2026',arsh_id,'Arshad Ali Shaikh','Mesh Feed 1 Ton from Ahsan',74040,None),
            ('26.05.2026',arsh_id,'Arshad Ali Shaikh','Transport of Mesh Feed',1300,None),
            ('30.05.2026',arsh_id,'Arshad Ali Shaikh','4 Brufen, 2 Jetiber',1400,None),
            ('30.05.2026',arsh_id,'Arshad Ali Shaikh','Moosa Helper',2000,None),
            ('30.05.2026',arsh_id,'Arshad Ali Shaikh','Vitamin CT Mint',4650,None),
            ('30.05.2026',arsh_id,'Arshad Ali Shaikh','Zincbooster',6050,None),
            ('30.05.2026',arsh_id,'Arshad Ali Shaikh','Mesh Feed Medicine for 1 Ton',6320,None),
        ]
        zk_payments = [
            ('06.04.2026',zk_id,'Zakir Hussain Utaro','Zakir Hussain Uttaro Payment',1406190,None),
            ('11.04.2026',zk_id,'Zakir Hussain Utaro','Cash Paid ARSH',150000,None),
            ('11.04.2026',zk_id,'Zakir Hussain Utaro','Temperature Meter',850,None),
            ('15.04.2026',zk_id,'Zakir Hussain Utaro','Dropping of 5517 Chicks Expense',4000,None),
            ('15.04.2026',zk_id,'Zakir Hussain Utaro','Roshan Labor on Dropping Day',1000,None),
            ('19.04.2026',zk_id,'Zakir Hussain Utaro','Debeaking of Chicks',10500,None),
            ('23.04.2026',zk_id,'Zakir Hussain Utaro','Vaccination Oil Base for Chicks Labour Cost',4500,None),
            ('15.05.2026',zk_id,'Zakir Hussain Utaro','15 Bags Fish Feed',120000,'Rate 160/kg, bill not confirmed'),
            ('19.05.2026',zk_id,'Zakir Hussain Utaro','Mesh Feed Contribution',46000,None),
            ('19.05.2026',zk_id,'Zakir Hussain Utaro','Medicine in Mesh Feed',12000,None),
            ('19.05.2026',zk_id,'Zakir Hussain Utaro','Transport Cost of Mesh Feed and HS 0 Feed',3500,'Junaid contributed 1500'),
        ]
        hmk_payments = [
            ('10.03.2026',hmk_id,'Haji Muhammad Khan Shaikh','Cash Payment to Chacho',1500000,None),
        ]
        c.executemany("INSERT INTO partners_payment (date,partner_id,partner,item,amount,notes) VALUES (?,?,?,?,?,?)",
            arsh_payments + zk_payments + hmk_payments)

    # Seed medicine
    c.execute("SELECT COUNT(*) FROM medicine_expenditure")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO medicine_expenditure (date,item,amount,notes) VALUES (?,?,?,?)", [
            (None,'Maxsalfade for Flashing',200,None),
            (None,'NFC100',2200,None),
            (None,'Zincbooster',5900,None),
            ('14.04.2026','NDI Vaccine for Chicks on 5th Day',4050,'ARSH'),
            ('14.04.2026','Herbatox-forte',3500,'ARSH'),
            ('14.04.2026','Respifin',1500,'ARSH'),
            (None,'Deoper',300,None),
            (None,'Owares 10 Packets',240,None),
            (None,'Vitamin K3 before Debeaking on 9th Day',None,None),
            ('24.05.2026','Elytyl Antibiotic Medicine',6350,None),
            ('30.05.2026','Vitamin CT Mint',4650,None),
            ('30.05.2026','Zincbooster',6050,None),
        ])

    # Seed feed
    c.execute("SELECT COUNT(*) FROM feed")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO feed (date,feed_type,bags,rate,amount,notes) VALUES (?,?,?,?,?,?)", [
            ('10.04.2026','Zero Feed',2,7650,15300,'HS Feeds'),
            ('11.04.2026','Zero Feed',23,None,176640,'Online Meezan HS Feed'),
            ('25.04.2026','Zero Feed',35,None,378650,'35 bags 0 feed + 15 bags'),
            ('09.05.2026','Zero Feed',25,None,189625,'HS Feed'),
            ('19.05.2026','Zero Feed',10,None,75650,'HS Feed'),
            ('15.05.2026','Mesh Feed',15,160,120000,'Fish feed, rate 160/kg'),
            ('19.05.2026','Mesh Feed',None,None,46000,'Mesh Feed Contribution by ZK'),
            ('26.05.2026','Mesh Feed',None,None,74040,'1 Ton Mesh Feed from Ahsan'),
            ('30.05.2026','Mesh Feed',None,None,6320,'Mesh Feed Medicine for 1 Ton'),
        ])

    conn.commit()
    conn.close()

# ---- ROUTES ----

@app.route('/api/filter/<table>')
def filter_records(table):
    allowed = ['staff_salary','partners_payment','medicine_expenditure','feed','production']
    if table not in allowed: return jsonify({'error':'invalid'}), 400
    from_d = parse_date(request.args.get('from_date',''))
    to_d = parse_date(request.args.get('to_date',''))
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()
    result = []
    for r in rows:
        d = parse_date(r['date'] or '')
        if d is None: continue
        if from_d and d < from_d: continue
        if to_d and d > to_d: continue
        result.append(dict(r))
    return jsonify(result)

@app.route('/api/filter_custom/<int:sid>')
def filter_custom(sid):
    from_d = parse_date(request.args.get('from_date',''))
    to_d = parse_date(request.args.get('to_date',''))
    conn = get_db()
    try:
        rows = conn.execute(f"SELECT * FROM cs_{sid} ORDER BY id DESC").fetchall()
    except:
        return jsonify([])
    result = []
    for r in rows:
        row_dict = dict(r)
        date_val = None
        for k,v in row_dict.items():
            if 'date' in k.lower() and v:
                date_val = parse_date(str(v))
                if date_val: break
        if date_val is None: continue
        if from_d and date_val < from_d: continue
        if to_d and date_val > to_d: continue
        result.append(row_dict)
    return jsonify(result)

@app.route('/api/pl_report')
def pl_report():
    conn = get_db()
    def s(q):
        try: return conn.execute(q).fetchone()[0] or 0
        except: return 0
    
    staff = s("SELECT SUM(COALESCE(total_amount,0)+COALESCE(advance,0)) FROM staff_salary")
    partners = s("SELECT SUM(amount) FROM partners_payment")
    medicine = s("SELECT SUM(amount) FROM medicine_expenditure")
    feed = s("SELECT SUM(amount) FROM feed")
    revenue = s("SELECT SUM(revenue) FROM production")
    
    # Custom sections — only include_in_total columns
    custom_expenses = []
    custom_revenues = []
    sections = conn.execute("SELECT id, section_name, COALESCE(section_type, 'expense') as section_type FROM custom_sections").fetchall()
    for sec in sections:
        sid = sec['id']
        cols = conn.execute("SELECT column_name FROM custom_columns WHERE section_id=? AND include_in_total=1", (sid,)).fetchall()
        total = 0
        for c in cols:
            safe = sanitize_col(c['column_name'])
            try:
                total += conn.execute(f"SELECT SUM(CAST({safe} AS REAL)) FROM cs_{sid}").fetchone()[0] or 0
            except: pass
        
        if sec['section_type'] == 'revenue':
            custom_revenues.append({'name': sec['section_name'], 'total': total})
        else:
            custom_expenses.append({'name': sec['section_name'], 'total': total})
    
    
    total_expenses = staff + partners + medicine + feed + sum(x['total'] for x in custom_expenses)
    total_revenue = revenue + sum(x['total'] for x in custom_revenues)
    net = total_revenue - total_expenses
    
    return jsonify({
        'revenue': total_revenue,
        'production_revenue': revenue,
        'custom_revenues': custom_revenues,
        'expenses': {
            'Staff Salary': staff,
            'Partners Payment': partners,
            'Medicine': medicine,
            'Feed': feed,
        },
        'custom_expenses': custom_expenses,
        'total_expenses': total_expenses,
        'net': net,
        'profitable': net >= 0
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/partners_master', methods=['GET'])
def get_partners():
    conn = get_db()
    rows = conn.execute("SELECT * FROM partners_master ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/partners_master', methods=['POST'])
def add_partner():
    d = request.json
    conn = get_db()
    conn.execute("INSERT INTO partners_master (name,share_percent,phone,cnic,address,notes) VALUES (?,?,?,?,?,?)",
        (d.get('name'),d.get('share_percent'),d.get('phone'),d.get('cnic'),d.get('address'),d.get('notes')))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/partners_master/<int:pid>', methods=['DELETE'])
def delete_partner(pid):
    conn = get_db()
    conn.execute("UPDATE partners_master SET is_active=0 WHERE id=?", (pid,))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/partners_master/<int:pid>/restore', methods=['POST'])
def restore_partner(pid):
    conn = get_db()
    conn.execute("UPDATE partners_master SET is_active=1 WHERE id=?", (pid,))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/partners_master/<int:pid>', methods=['PATCH'])
def update_partner(pid):
    d = request.json
    conn = get_db()
    fields = []
    values = []
    for k in ['name', 'share_percent', 'phone', 'cnic', 'address', 'notes']:
        if k in d:
            fields.append(f"{k}=?")
            values.append(d.get(k))
    
    if fields:
        values.append(pid)
        conn.execute(f"UPDATE partners_master SET {', '.join(fields)} WHERE id=?", tuple(values))
        conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/<table>', methods=['GET'])
def get_records(table):
    allowed = ['staff_salary','partners_payment','medicine_expenditure','feed','production']
    if table not in allowed: return jsonify({'error':'invalid'}), 400
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/<table>', methods=['POST'])
def add_record(table):
    allowed = ['staff_salary','partners_payment','medicine_expenditure','feed','production']
    if table not in allowed: return jsonify({'error':'invalid'}), 400
    d = request.json
    conn = get_db()
    if table == 'staff_salary':
        conn.execute("INSERT INTO staff_salary (date,name,designation,salary,days,total_amount,advance,salary_paid,notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (d.get('date'),d.get('name'),d.get('designation'),d.get('salary'),d.get('days'),d.get('total_amount'),d.get('advance'),d.get('salary_paid'),d.get('notes')))
    elif table == 'partners_payment':
        conn.execute("INSERT INTO partners_payment (date,partner_id,partner,item,amount,notes) VALUES (?,?,?,?,?,?)",
            (d.get('date'),d.get('partner_id'),d.get('partner'),d.get('item'),d.get('amount'),d.get('notes')))
    elif table == 'medicine_expenditure':
        conn.execute("INSERT INTO medicine_expenditure (date,item,amount,notes) VALUES (?,?,?,?)",
            (d.get('date'),d.get('item'),d.get('amount'),d.get('notes')))
    elif table == 'feed':
        conn.execute("INSERT INTO feed (date,feed_type,bags,rate,amount,notes) VALUES (?,?,?,?,?,?)",
            (d.get('date'),d.get('feed_type'),d.get('bags'),d.get('rate'),d.get('amount'),d.get('notes')))
    elif table == 'production':
        conn.execute("INSERT INTO production (date,total_birds,eggs_produced,eggs_sold,price_per_egg,buyer_name,revenue,mortality,notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (d.get('date'),d.get('total_birds'),d.get('eggs_produced'),d.get('eggs_sold'),d.get('price_per_egg'),d.get('buyer_name'),d.get('revenue'),d.get('mortality'),d.get('notes')))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/<table>/<int:record_id>', methods=['DELETE'])
def delete_record(table, record_id):
    allowed = ['staff_salary','partners_payment','medicine_expenditure','feed','production']
    if table not in allowed: return jsonify({'error':'invalid'}), 400
    conn = get_db()
    conn.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/<table>/<int:record_id>', methods=['PUT'])
def update_record(table, record_id):
    allowed = ['staff_salary','partners_payment','medicine_expenditure','feed','production']
    if table not in allowed: return jsonify({'error':'invalid'}), 400
    d = request.json
    conn = get_db()
    
    if table == 'staff_salary':
        conn.execute("UPDATE staff_salary SET date=?, name=?, designation=?, salary=?, days=?, total_amount=?, advance=?, salary_paid=?, notes=? WHERE id=?", 
                     (d.get('date'), d.get('name'), d.get('designation'), d.get('salary'), d.get('days'), d.get('total_amount'), d.get('advance'), d.get('salary_paid'), d.get('notes'), record_id))
    elif table == 'partners_payment':
        conn.execute("UPDATE partners_payment SET date=?, partner_id=?, partner=?, item=?, amount=?, notes=? WHERE id=?", 
                     (d.get('date'), d.get('partner_id'), d.get('partner'), d.get('item'), d.get('amount'), d.get('notes'), record_id))
    elif table == 'medicine_expenditure':
        conn.execute("UPDATE medicine_expenditure SET date=?, item=?, amount=?, notes=? WHERE id=?", 
                     (d.get('date'), d.get('item'), d.get('amount'), d.get('notes'), record_id))
    elif table == 'feed':
        conn.execute("UPDATE feed SET date=?, feed_type=?, bags=?, rate=?, amount=?, notes=? WHERE id=?", 
                     (d.get('date'), d.get('feed_type'), d.get('bags'), d.get('rate'), d.get('amount'), d.get('notes'), record_id))
    elif table == 'production':
        conn.execute("UPDATE production SET date=?, total_birds=?, eggs_produced=?, eggs_sold=?, price_per_egg=?, buyer_name=?, revenue=?, mortality=?, notes=? WHERE id=?", 
                     (d.get('date'), d.get('total_birds'), d.get('eggs_produced'), d.get('eggs_sold'), d.get('price_per_egg'), d.get('buyer_name'), d.get('revenue'), d.get('mortality'), d.get('notes'), record_id))
    
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/settings/<key>', methods=['GET'])
def get_setting(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return jsonify({'value': row['value'] if row else None})

@app.route('/api/settings', methods=['POST'])
def save_setting():
    d = request.json
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (d.get('key'), d.get('value')))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/custom_sections', methods=['GET'])
def get_custom_sections():
    conn = get_db()
    sections = conn.execute("SELECT * FROM custom_sections ORDER BY id").fetchall()
    res = []
    for s in sections:
        cols = conn.execute("SELECT * FROM custom_columns WHERE section_id=? ORDER BY column_order", (s['id'],)).fetchall()
        res.append({
            'id': s['id'],
            'section_name': s['section_name'],
            'columns': [dict(c) for c in cols]
        })
    return jsonify(res)

import re
def sanitize_col(name):
    return re.sub(r'[^a-zA-Z0-9_]', '_', name).strip('_').lower()

import re as _re
def evaluate_formula(formula, values_dict):
    if not formula:
        return None
    expr = formula.strip()
    tokens = _re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*|[\d\.]+|[\+\-\*/\(\)]', expr)
    safe_expr = ''
    for tok in tokens:
        if _re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', tok):
            val = values_dict.get(tok)
            try:
                num = float(val) if val not in (None, '') else 0
            except:
                num = 0
            safe_expr += str(num)
        elif _re.match(r'^[\d\.]+$', tok) or tok in ('+','-','*','/','(',')'):
            safe_expr += tok
        else:
            return None
    try:
        if not _re.match(r'^[0-9\.\+\-\*/\(\)\s]+$', safe_expr):
            return None
        result = eval(safe_expr, {"__builtins__": {}}, {})
        return round(float(result), 2)
    except:
        return None

@app.route('/api/custom_sections', methods=['POST'])
def create_custom_section():
    d = request.json
    name = str(d.get('section_name') or '').strip()
    columns_data = d.get('columns') or []
    section_type = str(d.get('section_type') or 'expense').strip()
    if section_type not in ('revenue', 'expense'):
        section_type = 'expense'

    if not name or not columns_data:
        return jsonify({'error':'Missing name or columns'}), 400
        
    # extract names for duplicate checking
    column_names = [c.get('name') if isinstance(c, dict) else c for c in columns_data]
    if len(column_names) != len(set(str(c).lower().strip() for c in column_names)):
        return jsonify({'error':'Duplicate columns'}), 400
        
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO custom_sections (section_name, section_type, created_at) VALUES (?, ?, ?)", (name, section_type, datetime.now().isoformat()))
    sec_id = c.lastrowid
    
    col_defs = []
    for i, col in enumerate(columns_data):
        if isinstance(col, dict):
            col_name = str(col.get('name', '')).strip()
            include = 1 if col.get('include_in_total') else 0
            formula = col.get('formula') or None
        else:
            col_name = str(col).strip()
            include = 0
            formula = None

        c.execute("INSERT INTO custom_columns (section_id, column_name, column_order, include_in_total, formula) VALUES (?, ?, ?, ?, ?)", (sec_id, col_name, i, include, formula))
        sanitized = sanitize_col(col_name)
        if not sanitized: sanitized = f"col_{i}"
        col_defs.append(f"{sanitized} TEXT")
        
    c.execute(f"CREATE TABLE IF NOT EXISTS cs_{sec_id} (id INTEGER PRIMARY KEY AUTOINCREMENT, " + ", ".join(col_defs) + ")")
    conn.commit()
    return jsonify({'status':'ok', 'section_id':sec_id})

@app.route('/api/custom_sections/<int:sid>', methods=['PATCH'])
def rename_custom_section(sid):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE custom_sections SET section_name=? WHERE id=?", (d.get('section_name'), sid))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/custom_columns/<int:cid>', methods=['PATCH'])
def update_custom_column(cid):
    d = request.json
    conn = get_db()
    if 'include_in_total' in d:
        conn.execute("UPDATE custom_columns SET include_in_total=? WHERE id=?", (int(bool(d['include_in_total'])), cid))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/custom_sections/<int:sid>', methods=['DELETE'])
def delete_custom_section(sid):
    conn = get_db()
    conn.execute("DELETE FROM custom_sections WHERE id=?", (sid,))
    conn.execute("DELETE FROM custom_columns WHERE section_id=?", (sid,))
    conn.execute(f"DROP TABLE IF EXISTS cs_{sid}")
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/custom_data/<int:sid>', methods=['GET'])
def get_custom_data(sid):
    conn = get_db()
    try:
        rows = conn.execute(f"SELECT * FROM cs_{sid} ORDER BY id DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    except sqlite3.OperationalError:
        return jsonify([])

@app.route('/api/custom_data/<int:sid>', methods=['POST'])
def add_custom_data(sid):
    d = request.json
    conn = get_db()
    # Recalculate formula columns before insert
    sec_cols = conn.execute("SELECT column_name, formula FROM custom_columns WHERE section_id=?", (sid,)).fetchall()
    values_dict = {sanitize_col(k): v for k, v in d.items()}
    for sc in sec_cols:
        if sc['formula']:
            sanitized = sanitize_col(sc['column_name'])
            result = evaluate_formula(sc['formula'], values_dict)
            d[sanitized] = result if result is not None else 0
            values_dict[sanitized] = d[sanitized]
    cols = [sanitize_col(k) for k in d.keys()]
    vals = list(d.values())
    if not cols: return jsonify({'status':'ok'})

    placeholders = ",".join(["?"] * len(cols))
    col_str = ",".join(cols)

    conn.execute(f"INSERT INTO cs_{sid} ({col_str}) VALUES ({placeholders})", vals)
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/custom_data/<int:sid>/<int:rid>', methods=['PUT'])
def update_custom_data(sid, rid):
    d = request.json
    conn = get_db()
    # Recalculate formula columns before update
    sec_cols = conn.execute("SELECT column_name, formula FROM custom_columns WHERE section_id=?", (sid,)).fetchall()
    values_dict = {sanitize_col(k): v for k, v in d.items()}
    for sc in sec_cols:
        if sc['formula']:
            sanitized = sanitize_col(sc['column_name'])
            result = evaluate_formula(sc['formula'], values_dict)
            d[sanitized] = result if result is not None else 0
            values_dict[sanitized] = d[sanitized]
    cols = list(d.keys())
    vals = list(d.values())
    if not cols: return jsonify({'status':'ok'})

    set_str = ", ".join([f"{c}=?" for c in cols])
    vals.append(rid)

    conn.execute(f"UPDATE cs_{sid} SET {set_str} WHERE id=?", vals)
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/custom_data/<int:sid>/<int:rid>', methods=['DELETE'])
def delete_custom_data(sid, rid):
    conn = get_db()
    conn.execute(f"DELETE FROM cs_{sid} WHERE id=?", (rid,))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/custom_columns/<int:cid>', methods=['DELETE'])
def drop_custom_column(cid):
    if sqlite3.sqlite_version_info < (3, 35, 0):
        return jsonify({"error": "Column deletion requires SQLite 3.35 or higher. Please update Python."}), 400
        
    conn = get_db()
    col = conn.execute("SELECT section_id, column_name FROM custom_columns WHERE id=?", (cid,)).fetchone()
    if not col: return jsonify({'error':'not found'}), 404
    
    sid = col['section_id']
    count = conn.execute("SELECT COUNT(*) FROM custom_columns WHERE section_id=?", (sid,)).fetchone()[0]
    if count <= 1:
        return jsonify({'error':'Cannot delete the last column'}), 400
        
    sanitized = re.sub(r'\W+', '_', col['column_name'].lower()).strip('_')
    
    conn.execute("DELETE FROM custom_columns WHERE id=?", (cid,))
    try:
        conn.execute(f"ALTER TABLE cs_{sid} DROP COLUMN {sanitized}")
    except sqlite3.OperationalError:
        pass # fallback if column didn't exist in table
        
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/stats')
def stats():
    conn = get_db()
    def s(q): 
        try:
            return conn.execute(q).fetchone()[0] or 0
        except sqlite3.OperationalError:
            return 0
            
    data = {
        'staff_total': s("SELECT SUM(COALESCE(total_amount,0)+COALESCE(advance,0)) FROM staff_salary"),
        'partners_total': s("SELECT SUM(amount) FROM partners_payment"),
        'medicine_total': s("SELECT SUM(amount) FROM medicine_expenditure"),
        'feed_total': s("SELECT SUM(amount) FROM feed"),
        'production_revenue': s("SELECT SUM(revenue) FROM production"),
        'custom_sections': []
    }
    
    sections = conn.execute("SELECT id, section_name FROM custom_sections ORDER BY id").fetchall()
    for sec in sections:
        sid = sec['id']
        cols = conn.execute("SELECT column_name FROM custom_columns WHERE section_id=? AND include_in_total=1", (sid,)).fetchall()
        
        sum_queries = []
        for c in cols:
            sanitized = re.sub(r'\W+', '_', c['column_name'].lower()).strip('_')
            sum_queries.append(f"SUM(CAST({sanitized} AS REAL))")
            
        total = 0
        if sum_queries:
            q = f"SELECT ({'+'.join(sum_queries)}) FROM cs_{sid}"
            total = s(q)
            
        data['custom_sections'].append({
            'id': sid,
            'name': sec['section_name'],
            'total': total
        })
        
    return jsonify(data)

@app.route('/api/backup')
def backup():
    try:
        import openpyxl
    except:
        import subprocess
        subprocess.run(['pip','install','openpyxl','--break-system-packages','-q'])
        import openpyxl
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    wb = Workbook()

    green = PatternFill("solid", fgColor="1a7a4a")
    light = PatternFill("solid", fgColor="e8f5ee")
    total_fill = PatternFill("solid", fgColor="d5f5e3")
    hfont = Font(bold=True, color="FFFFFF", size=11)
    bfont = Font(bold=True, size=11)
    total_font = Font(bold=True, size=12, color="15803d")
    total_label_font = Font(bold=True, size=12, color="1e293b")
    border = Border(bottom=Side(style='thin', color='cccccc'))
    total_border = Border(
        top=Side(style='double', color='1a7a4a'),
        bottom=Side(style='double', color='1a7a4a')
    )

    def make_sheet(name, headers, rows, sum_cols=None):
        ws = wb.create_sheet(name)
        for i, h in enumerate(headers, 1):
            cell = ws.cell(1, i, h)
            cell.font = hfont; cell.fill = green; cell.alignment = Alignment(horizontal='center')
        for ri, row in enumerate(rows, 2):
            fill = light if ri % 2 == 0 else PatternFill()
            for ci, val in enumerate(row, 1):
                cell = ws.cell(ri, ci, val)
                cell.fill = fill; cell.border = border
                cell.alignment = Alignment(horizontal='left')
        # Append TOTAL row - always ensure one exists
        if sum_cols or True:
            total_row = max(len(rows) + 2, 2)
            for ci in range(1, len(headers) + 1):
                cell = ws.cell(total_row, ci)
                cell.fill = total_fill
                cell.border = total_border
                if ci == 1:
                    cell.value = 'TOTAL'
                    cell.font = total_label_font
                    cell.alignment = Alignment(horizontal='center')
                elif sum_cols and ci in sum_cols:
                    col_letter = cell.column_letter
                    cell.value = sum((
                        r[ci - 1] for r in rows
                        if r[ci - 1] is not None and isinstance(r[ci - 1], (int, float))
                    ), 0)
                    cell.font = total_font
                    cell.number_format = '#,##0'
                    cell.alignment = Alignment(horizontal='right')
                else:
                    cell.value = ''
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(len(str(col[0].value or '')), max((len(str(c.value or '')) for c in col), default=0)) + 4

    conn = get_db()

    # Helpers: fetch extra columns + their data for the 5 hardcoded sections
    def get_extra_cols_and_data(section_name, row_ids):
        ecols = conn.execute("SELECT id, column_name, column_order FROM section_extra_columns WHERE section_name=? ORDER BY column_order, id", (section_name,)).fetchall()
        if not ecols:
            return [], {}
        edata_rows = conn.execute("SELECT row_id, column_id, value FROM section_extra_data WHERE section_name=?", (section_name,)).fetchall()
        edata = {}
        for r in edata_rows:
            edata.setdefault(r['row_id'], {})[r['column_id']] = r['value']
        return ecols, edata

    def is_numeric_col(ecols_id, edata, row_ids):
        for rid in row_ids:
            v = edata.get(rid, {}).get(ecols_id)
            if v not in (None, ''):
                try:
                    float(v)
                    return True
                except:
                    return False
        return False

    pm = conn.execute("SELECT * FROM partners_master").fetchall()
    make_sheet("Partners", ["ID","Name","Share %","Phone","CNIC","Address","Notes"],
        [[r['id'],r['name'],r['share_percent'],r['phone'],r['cnic'],r['address'],r['notes']] for r in pm],
        sum_cols=set())

    ss = conn.execute("SELECT * FROM staff_salary ORDER BY id").fetchall()
    _ss_ids = [r['id'] for r in ss]
    _ss_ecols, _ss_edata = get_extra_cols_and_data('staff_salary', _ss_ids)
    _ss_headers = ["ID","Date","Name","Designation","Salary","Days","Total Amount","Advance","Status","Notes"] + [c['column_name'] for c in _ss_ecols]
    _ss_rows = []
    for r in ss:
        row = [r['id'],r['date'],r['name'],r['designation'],r['salary'],r['days'],r['total_amount'],r['advance'],r['salary_paid'],r['notes']]
        for ec in _ss_ecols:
            v = _ss_edata.get(r['id'], {}).get(ec['id'])
            try: row.append(float(v) if v not in (None,'') else v)
            except: row.append(v)
        _ss_rows.append(row)
    _ss_sum = {5, 7, 8}  # Salary=5, Total Amount=7, Advance=8
    for _i, ec in enumerate(_ss_ecols):
        if is_numeric_col(ec['id'], _ss_edata, _ss_ids):
            _ss_sum.add(11 + _i)  # extra cols start after the 10 fixed cols (1-indexed => pos 11+)
    make_sheet("Staff Salary", _ss_headers, _ss_rows, sum_cols=_ss_sum)

    pp = conn.execute("SELECT * FROM partners_payment ORDER BY date").fetchall()
    _pp_ids = [r['id'] for r in pp]
    _pp_ecols, _pp_edata = get_extra_cols_and_data('partners_payment', _pp_ids)
    _pp_headers = ["ID","Date","Partner","Item","Amount (Rs)","Notes"] + [c['column_name'] for c in _pp_ecols]
    _pp_rows = []
    for r in pp:
        row = [r['id'],r['date'],r['partner'],r['item'],r['amount'],r['notes']]
        for ec in _pp_ecols:
            v = _pp_edata.get(r['id'], {}).get(ec['id'])
            try: row.append(float(v) if v not in (None,'') else v)
            except: row.append(v)
        _pp_rows.append(row)
    _pp_sum = {5}  # Amount=5
    for _i, ec in enumerate(_pp_ecols):
        if is_numeric_col(ec['id'], _pp_edata, _pp_ids):
            _pp_sum.add(7 + _i)  # extra cols start after the 6 fixed cols (pos 7+)
    make_sheet("Partners Payment", _pp_headers, _pp_rows, sum_cols=_pp_sum)

    me = conn.execute("SELECT * FROM medicine_expenditure ORDER BY id").fetchall()
    _me_ids = [r['id'] for r in me]
    _me_ecols, _me_edata = get_extra_cols_and_data('medicine_expenditure', _me_ids)
    _me_headers = ["ID","Date","Item","Amount (Rs)","Notes"] + [c['column_name'] for c in _me_ecols]
    _me_rows = []
    for r in me:
        row = [r['id'],r['date'],r['item'],r['amount'],r['notes']]
        for ec in _me_ecols:
            v = _me_edata.get(r['id'], {}).get(ec['id'])
            try: row.append(float(v) if v not in (None,'') else v)
            except: row.append(v)
        _me_rows.append(row)
    _me_sum = {4}  # Amount=4
    for _i, ec in enumerate(_me_ecols):
        if is_numeric_col(ec['id'], _me_edata, _me_ids):
            _me_sum.add(6 + _i)  # extra cols start after the 5 fixed cols (pos 6+)
    make_sheet("Medicine", _me_headers, _me_rows, sum_cols=_me_sum)

    fd = conn.execute("SELECT * FROM feed ORDER BY id").fetchall()
    _fd_ids = [r['id'] for r in fd]
    _fd_ecols, _fd_edata = get_extra_cols_and_data('feed', _fd_ids)
    _fd_headers = ["ID","Date","Feed Type","Bags","Rate","Amount (Rs)","Notes"] + [c['column_name'] for c in _fd_ecols]
    _fd_rows = []
    for r in fd:
        row = [r['id'],r['date'],r['feed_type'],r['bags'],r['rate'],r['amount'],r['notes']]
        for ec in _fd_ecols:
            v = _fd_edata.get(r['id'], {}).get(ec['id'])
            try: row.append(float(v) if v not in (None,'') else v)
            except: row.append(v)
        _fd_rows.append(row)
    _fd_sum = {4, 6}  # Bags=4, Amount=6
    for _i, ec in enumerate(_fd_ecols):
        if is_numeric_col(ec['id'], _fd_edata, _fd_ids):
            _fd_sum.add(8 + _i)  # extra cols start after the 7 fixed cols (pos 8+)
    make_sheet("Feed", _fd_headers, _fd_rows, sum_cols=_fd_sum)

    pr = conn.execute("SELECT * FROM production ORDER BY id").fetchall()
    _pr_ids = [r['id'] for r in pr]
    _pr_ecols, _pr_edata = get_extra_cols_and_data('production', _pr_ids)
    _pr_headers = ["ID","Date","Total Birds","Eggs Produced","Eggs Sold","Price/Egg","Buyer Name","Revenue","Mortality","Notes"] + [c['column_name'] for c in _pr_ecols]
    _pr_rows = []
    for r in pr:
        row = [r['id'],r['date'],r['total_birds'],r['eggs_produced'],r['eggs_sold'],r['price_per_egg'],r['buyer_name'],r['revenue'],r['mortality'],r['notes']]
        for ec in _pr_ecols:
            v = _pr_edata.get(r['id'], {}).get(ec['id'])
            try: row.append(float(v) if v not in (None,'') else v)
            except: row.append(v)
        _pr_rows.append(row)
    _pr_sum = {3, 4, 5, 8, 9}  # Total Birds=3, Eggs Produced=4, Eggs Sold=5, Revenue=8, Mortality=9
    for _i, ec in enumerate(_pr_ecols):
        if is_numeric_col(ec['id'], _pr_edata, _pr_ids):
            _pr_sum.add(11 + _i)  # extra cols start after the 10 fixed cols (pos 11+)
    make_sheet("Production", _pr_headers, _pr_rows, sum_cols=_pr_sum)

    # Add Custom Sections
    sections = conn.execute("SELECT * FROM custom_sections ORDER BY id").fetchall()
    for sec in sections:
        sid = sec['id']
        s_name = sec['section_name'][:31]
        
        # Ensure unique sheet name
        base_name = s_name
        counter = 2
        while s_name in wb.sheetnames:
            suffix = f" {counter}"
            s_name = base_name[:31 - len(suffix)] + suffix
            counter += 1
            
        cols = conn.execute("SELECT column_name, include_in_total FROM custom_columns WHERE section_id=? ORDER BY column_order", (sid,)).fetchall()
        headers = ["ID"] + [c['column_name'] for c in cols]
        
        try:
            rows = conn.execute(f"SELECT * FROM cs_{sid} ORDER BY id").fetchall()
        except sqlite3.OperationalError:
            rows = []
            
        data_rows = []
        sum_cols_custom = set()
        
        for r in rows:
            data_rows.append([r[0]] + [r[i+1] for i in range(len(cols))])
            
        for c_idx, col_record in enumerate(cols):
            if col_record['include_in_total'] == 1:
                # Add it to sum columns (plus 1 because headers start at 1 and we have an ID col at idx 0)
                sum_cols_custom.add(c_idx + 2)
        
        make_sheet(s_name, headers, data_rows, sum_cols=sum_cols_custom)

        # Update totals for custom sections correctly
        ws = wb[s_name]
        total_row = max(len(data_rows) + 2, 2)
        for c_idx, col_record in enumerate(cols):
            if col_record['include_in_total'] == 1:
                safe_col = sanitize_col(col_record['column_name'])
                try:
                    total = conn.execute(
                        f"SELECT SUM(CAST({safe_col} AS REAL)) FROM cs_{sid}"
                    ).fetchone()[0] or 0
                except sqlite3.OperationalError:
                    total = 0
                cell = ws.cell(total_row, c_idx + 2)
                cell.value = total
                cell.font = total_font
                cell.number_format = '#,##0'
                cell.alignment = Alignment(horizontal='right')

    # Add P&L Report Sheet
    conn = get_db()
    def sq(q):
        try: return conn.execute(q).fetchone()[0] or 0
        except: return 0
    
    pl_staff = sq("SELECT SUM(COALESCE(total_amount,0)+COALESCE(advance,0)) FROM staff_salary")
    pl_partners = sq("SELECT SUM(amount) FROM partners_payment")
    pl_medicine = sq("SELECT SUM(amount) FROM medicine_expenditure")
    pl_feed = sq("SELECT SUM(amount) FROM feed")
    pl_revenue = sq("SELECT SUM(revenue) FROM production")
    
    pl_custom_expense_total = 0
    pl_custom_revenue_total = 0
    pl_expense_sec_rows = []
    pl_revenue_sec_rows = []
    all_secs = conn.execute("SELECT id, section_name, COALESCE(section_type,'expense') as section_type FROM custom_sections").fetchall()
    for sec in all_secs:
        s_total = 0
        s_cols = conn.execute("SELECT column_name FROM custom_columns WHERE section_id=? AND include_in_total=1", (sec['id'],)).fetchall()
        for c in s_cols:
            safe_c = sanitize_col(c['column_name'])
            try: s_total += conn.execute(f"SELECT SUM(CAST({safe_c} AS REAL)) FROM cs_{sec['id']}").fetchone()[0] or 0
            except: pass
        if s_total > 0:
            if sec['section_type'] == 'revenue':
                pl_revenue_sec_rows.append((sec['section_name'], s_total))
                pl_custom_revenue_total += s_total
            else:
                pl_expense_sec_rows.append((sec['section_name'], s_total))
                pl_custom_expense_total += s_total
            
    pl_total_revenue = pl_revenue + pl_custom_revenue_total
    pl_total_exp = pl_staff + pl_partners + pl_medicine + pl_feed + pl_custom_expense_total
    pl_net = pl_total_revenue - pl_total_exp
    
    pl_data_rows = [
        ['Total Revenue', pl_total_revenue],
    ]
    if pl_custom_revenue_total > 0:
        pl_data_rows.append(['  Production Revenue', pl_revenue])
        for sname, sval in pl_revenue_sec_rows:
            pl_data_rows.append(['  ' + sname + ' (Revenue)', sval])
    pl_data_rows += [
        ['Staff Salary Expenses', pl_staff],
        ['Partners Payment Expenses', pl_partners],
        ['Medicine Expenses', pl_medicine],
        ['Feed Expenses', pl_feed]
    ]
    for sname, sval in pl_expense_sec_rows:
        pl_data_rows.append([sname + ' Expenses', sval])
        
    ws = wb.create_sheet("P&L Report")
    for i, h in enumerate(["Category", "Amount (Rs)"], 1):
        cell = ws.cell(1, i, h)
        cell.font = hfont; cell.fill = green; cell.alignment = Alignment(horizontal='center')
        
    for ri, row in enumerate(pl_data_rows, 2):
        for ci, val in enumerate(row, 1):
            cell = ws.cell(ri, ci, val)
            cell.border = border
            if ci == 2:
                cell.number_format = '#,##0'
                cell.alignment = Alignment(horizontal='right')
                if ri == 2: cell.font = total_font
                else: cell.font = Font(bold=True, color="dc2626") # red expenses
            else:
                cell.alignment = Alignment(horizontal='left')
                if ri == 2: cell.font = Font(bold=True, color="15803d") # green revenue revenue
                
    # Total Expenses Row
    tr_idx = len(pl_data_rows) + 2
    c1 = ws.cell(tr_idx, 1, "Total Expenses")
    c1.font = total_label_font; c1.alignment = Alignment(horizontal='center'); c1.fill = total_fill; c1.border = total_border
    c2 = ws.cell(tr_idx, 2, pl_total_exp)
    c2.font = Font(bold=True, size=12, color="dc2626"); c2.alignment = Alignment(horizontal='right'); c2.fill = total_fill; c2.border = total_border; c2.number_format = '#,##0'
    
    # Net Profit/Loss Row
    nr_idx = tr_idx + 1
    c1 = ws.cell(nr_idx, 1, "Net Profit" if pl_net >= 0 else "Net Loss")
    c1.font = total_label_font; c1.alignment = Alignment(horizontal='center'); c1.fill = total_fill; c1.border = total_border
    c2 = ws.cell(nr_idx, 2, abs(pl_net))
    c2.font = Font(bold=True, size=12, color="15803d" if pl_net >= 0 else "dc2626")
    c2.alignment = Alignment(horizontal='right'); c2.fill = total_fill; c2.border = total_border; c2.number_format = '#,##0'
    
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 30

    conn = get_db()
    if 'Sheet' in wb.sheetnames: del wb['Sheet']

    fname = f"Farm_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    path = os.path.join(os.path.dirname(__file__), fname)
    wb.save(path)
    try:
        return send_file(path, as_attachment=True, download_name=fname)
    finally:
        try:
            os.remove(path)
        except:
            pass

@app.route('/api/backup_db')
def backup_db():
    fname = f"Farm_SystemBackup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return send_file(DB_PATH, as_attachment=True, download_name=fname)

# ---- EXTRA COLUMNS ON HARDCODED SECTIONS ----
ALLOWED_EXTRA_SECTIONS = ['staff_salary','partners_payment','medicine_expenditure','feed','production']

@app.route('/api/extra_columns/<section_name>', methods=['GET'])
def get_extra_columns(section_name):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, section_name, column_name, column_order FROM section_extra_columns WHERE section_name=? ORDER BY column_order, id",
        (section_name,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/extra_columns/<section_name>', methods=['POST'])
def add_extra_column(section_name):
    if section_name not in ALLOWED_EXTRA_SECTIONS:
        return jsonify({'error':'Invalid section'}), 400
    d = request.json or {}
    name = str(d.get('column_name') or '').strip()
    if not name:
        return jsonify({'error':'Column name is required'}), 400
    conn = get_db()
    existing = conn.execute("SELECT column_name FROM section_extra_columns WHERE section_name=?", (section_name,)).fetchall()
    if any(name.lower() == (e['column_name'] or '').lower() for e in existing):
        return jsonify({'error':'A column with this name already exists'}), 400
    cur = conn.execute("INSERT INTO section_extra_columns (section_name, column_name, column_order) VALUES (?, ?, ?)",
        (section_name, name, 0))
    conn.commit()
    return jsonify({'status':'ok','id':cur.lastrowid,'column_name':name})

@app.route('/api/extra_columns/<int:column_id>', methods=['DELETE'])
def delete_extra_column(column_id):
    conn = get_db()
    conn.execute("DELETE FROM section_extra_data WHERE column_id=?", (column_id,))
    conn.execute("DELETE FROM section_extra_columns WHERE id=?", (column_id,))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/extra_data_all/<section_name>', methods=['GET'])
def get_all_extra_data(section_name):
    conn = get_db()
    rows = conn.execute("SELECT row_id, column_id, value FROM section_extra_data WHERE section_name=?", (section_name,)).fetchall()
    result = {}
    for r in rows:
        rid = str(r['row_id'])
        result.setdefault(rid, {})[str(r['column_id'])] = r['value']
    return jsonify(result)

@app.route('/api/extra_data/<section_name>/<int:row_id>', methods=['POST'])
def save_extra_data(section_name, row_id):
    d = request.json or {}
    conn = get_db()
    for col_id, value in d.items():
        try:
            cid = int(col_id)
        except (ValueError, TypeError):
            continue
        conn.execute("INSERT OR REPLACE INTO section_extra_data (section_name, row_id, column_id, value) VALUES (?, ?, ?, ?)",
            (section_name, row_id, cid, value if value is not None else ''))
    conn.commit()
    return jsonify({'status':'ok'})

# ---- ADD COLUMN TO EXISTING CUSTOM SECTION ----
@app.route('/api/custom_sections/<int:section_id>/add_column', methods=['POST'])
def add_custom_section_column(section_id):
    d = request.json or {}
    name = str(d.get('column_name') or '').strip()
    include = 1 if d.get('include_in_total') else 0
    if not name:
        return jsonify({'error':'Column name is required'}), 400
    conn = get_db()
    sec = conn.execute("SELECT id FROM custom_sections WHERE id=?", (section_id,)).fetchone()
    if not sec:
        return jsonify({'error':'Section not found'}), 404
    existing = conn.execute("SELECT column_name FROM custom_columns WHERE section_id=?", (section_id,)).fetchall()
    if any(name.lower() == (e['column_name'] or '').lower() for e in existing):
        return jsonify({'error':'A column with this name already exists'}), 400
    max_order = conn.execute("SELECT MAX(column_order) FROM custom_columns WHERE section_id=?", (section_id,)).fetchone()[0]
    new_order = (max_order or 0) + 1
    cur = conn.execute("INSERT INTO custom_columns (section_id, column_name, column_order, include_in_total) VALUES (?, ?, ?, ?)",
        (section_id, name, new_order, include))
    new_cid = cur.lastrowid
    sanitized = sanitize_col(name)
    if not sanitized:
        sanitized = f"col_{new_order}"
    try:
        conn.execute(f"ALTER TABLE cs_{section_id} ADD COLUMN {sanitized} TEXT")
    except sqlite3.OperationalError:
        pass  # column may already exist or table missing
    conn.commit()
    return jsonify({'status':'ok','column_id':new_cid,'column_name':name})

# ---- ROW COLOR MARKING ----
@app.route('/api/row_colors/<section_name>', methods=['GET'])
def get_row_colors(section_name):
    conn = get_db()
    rows = conn.execute("SELECT row_id, color FROM row_colors WHERE section_name=?", (section_name,)).fetchall()
    result = {}
    for r in rows:
        result[str(r['row_id'])] = r['color']
    return jsonify(result)

@app.route('/api/row_colors/<section_name>/<int:row_id>', methods=['POST'])
def set_row_color(section_name, row_id):
    d = request.json or {}
    color = str(d.get('color') or '').strip().lower()
    if color not in ('red', 'yellow', 'green'):
        return jsonify({'error':'Invalid color'}), 400
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO row_colors (section_name, row_id, color) VALUES (?, ?, ?)",
        (section_name, row_id, color))
    conn.commit()
    return jsonify({'status':'ok'})

@app.route('/api/row_colors/<section_name>/<int:row_id>', methods=['DELETE'])
def clear_row_color(section_name, row_id):
    conn = get_db()
    conn.execute("DELETE FROM row_colors WHERE section_name=? AND row_id=?", (section_name, row_id))
    conn.commit()
    return jsonify({'status':'ok'})

if __name__ == '__main__':
    init_db()
    print("\n" + "="*55)
    print("  ✅  APP IS RUNNING — DO NOT CLOSE THIS WINDOW")
    print("  ⚠️   Closing this window will stop the app")
    print("  🌐  Open your browser: http://localhost:5000")
    print("="*55 + "\n")
    app.run(debug=False, port=5000)
