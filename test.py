import sqlite3, os
con = sqlite3.connect(r"c:\Users\91264\Desktop\M1\jitsuzou\coma_link.db")
for row in con.execute("PRAGMA table_info(courses)"):
    print(row)
con.close()
