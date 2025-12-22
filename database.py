import sqlite3

def init_db():
    conn = sqlite3.connect('casita.db')
    c = conn.cursor()
    # Create the table required for your team
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  email TEXT UNIQUE, 
                  password_hash TEXT)''')
    conn.commit()
    conn.close()
    print("Database and 'users' table initialized successfully.")

if __name__ == "__main__":
    init_db()