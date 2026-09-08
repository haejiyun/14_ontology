import sqlite3


conn=sqlite3.connect("db/tiny_mall.db")
cursor=conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables=cursor.fetchall()
tables

cursor.execute("SELECT * FROM products")
cursor.fetchall()

cursor.execute("SELECT count(*) FROM products").fetchall()
