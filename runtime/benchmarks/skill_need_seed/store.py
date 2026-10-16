import sqlite3


def find_user(db, name):
    query = "SELECT * FROM users WHERE name = '" + name + "'"
    return db.execute(query).fetchall()


def ProcessData(x):
    return [i * 2 for i in x]
