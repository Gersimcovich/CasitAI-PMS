import sqlite3
import bcrypt

def add_team_member(email, password):
    # 1. Connect to Database
    conn = sqlite3.connect('casita.db')
    c = conn.cursor()
    
    # 2. Securely Hash Password
    # We turn the string into bytes, salt it, and hash it
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # 3. Store the hash as a string in the DB
    try:
        # We decode the hash to store it as a clean string
        c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", 
                  (email, hashed.decode('utf-8')))
        conn.commit()
        print(f"SUCCESS: User {email} added to the team.")
    except sqlite3.IntegrityError:
        print(f"NOTICE: User {email} is already in the database.")
    finally:
        conn.close()

if __name__ == "__main__":
    # Add your 5 team members here
    add_team_member("georgia@hellocasita.com", "CasitaAdmin2025")
    add_team_member("team1@casita.com", "ServiceTeam01")
    # add_team_member("...", "...")