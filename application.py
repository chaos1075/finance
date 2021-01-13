import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")



@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    cnt = db.execute('''SELECT COUNT(name) FROM sqlite_master WHERE type='table' and name='transactions' ''')
    if cnt[0]['COUNT(name)'] == 0:
        return apology("no transaction is found", 403)
    portfolio = []
    portfolio = db.execute("SELECT symbol, company, SUM(shares) FROM transactions WHERE user_id = :id GROUP BY symbol HAVING SUM(shares) > 0", id=session['user_id'])
    allStockValue = 0
    for stock in portfolio:
        info = lookup(stock['symbol'])
        stock['price'] = usd(info['price'])
        total = info['price'] * stock['SUM(shares)']
        stock['total'] = usd(total)
        allStockValue += total
    balance = db.execute("SELECT cash from users WHERE id = :id", id=session['user_id'])
    cash = balance[0]['cash']
    totalValue = cash + allStockValue
    cash_usd = usd(cash)
    totalValue_usd = usd(totalValue)
    return render_template("index.html", portfolio=portfolio, cash=cash_usd, totalValue=totalValue_usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # current date and time
    dt = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
    trans = {}
    if request.method == "GET":
        return render_template("buy.html")
    symbol = request.form.get("symbol")
    if not symbol:
        return apology("must provide a symbol", 403)
    share = request.form.get("shares")
    if not share:
        return apology("must provide number of shares to buy", 403)
    if not share.isdecimal():
        return apology("must provide a positive integer for number of shares", 403)
    stock = lookup(symbol)
    if stock is None:
        return apology("symbol error", 403)
    share = int(share)
    if share <= 0:
        return apology("must provide positive integer for number of shares", 403)
    balance = db.execute("SELECT cash FROM users WHERE id = :id", id=session['user_id'])
    total = stock['price'] * share
    cashfwd = balance[0]['cash']
    cashremain = cashfwd - total
    if cashremain < 0:
        return apology("balance is not enough", 403)
    trans['symbol'] = symbol
    trans['name'] = stock['name']
    trans['shares'] = share
    trans['price_usd'] = usd(stock['price'])
    trans['total'] = usd(total)
    trans['remain_cash'] = usd(cashremain)
    trans['fwd_cash'] = usd(cashfwd)
    cnt = db.execute('''SELECT COUNT(name) FROM sqlite_master WHERE type='table' and name='transactions' ''')
    # print(cnt)
    if cnt[0]['COUNT(name)'] == 0:
        db.execute("CREATE TABLE transactions (trans_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER, datetime DATETIME, symbol TEXT, company TEXT, shares INTEGER, price NUMERIC, total NUMERIC)")
        db.execute("CREATE UNIQUE INDEX user_id_datetime on transactions (user_id, datetime)")
    db.execute("INSERT INTO transactions (user_id, datetime, symbol, company, shares, price, total) VALUES(?, ?, ?, ?, ?, ?, ?)", session["user_id"], dt, symbol, stock['name'], share, stock['price'], total)
    db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cashremain, id=session['user_id'])
    return render_template("bought.html", trans=trans)



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    cnt = db.execute('''SELECT COUNT(name) FROM sqlite_master WHERE type='table' and name='transactions' ''')
    # print(cnt)
    if cnt[0]['COUNT(name)'] == 0:
        return apology("no transaction is found", 403)
    trans = db.execute("SELECT * FROM transactions")
    if not trans:
        return apology("no transaction is found", 403)
    for t in trans:
        t['price_usd'] = usd(t['price'])
    return render_template("history.html", trans=trans)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    symbol = request.form.get("symbol")
    if not symbol:
        return apology("must provide a symbol", 403)
    stock = lookup(symbol)
    if stock is None:
        return apology("symbol error", 403)
    value = stock['price']
    stock['price_usd'] = usd(value)
    return render_template("quoted.html", stock=stock)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    name = request.form.get("username")
    if not name:
        return apology("must provide a username", 403)
    rows = db.execute("SELECT * FROM users WHERE username=:username",
                        username=name)
    if len(rows) == 1:
        return apology("username already exists", 403)
    pw = request.form.get("password")
    repw = request.form.get("confirmation")
    if not pw:
        return apology("must set up a password", 403)
    if not repw:
        return apology("must retype the password", 403)
    if pw != repw:
        return apology("the passwords provided don't match", 403)
    hashpw = generate_password_hash(pw)
    db.execute("INSERT INTO users (username, hash, cash) VALUES(?, ?, ?)", name, hashpw, 10000)
    return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    dt = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
    trans = {}
    portfolio = db.execute("SELECT symbol, company, SUM(shares) FROM transactions WHERE user_id = :id GROUP BY symbol HAVING SUM(shares) > 0", id=session['user_id'])
    if not portfolio:
        return apology("no portfolio set up yet", 403)
    if request.method == "GET":
        return render_template("sell.html", portfolio=portfolio)
    symbol = request.form.get("symbol")
    # print(f"symbol: {symbol}")
    if not symbol:
        return apology("must provide a symbol to sell", 403)
    share = request.form.get("shares")
    if not share:
        return apology("must provide number of shares to sell", 403)
    if not share.isdecimal():
        return apology("must provide a positive integer for the number of shares", 403)
    isSymbolFound = False
    isShareInRange = False
    for stock in portfolio:
        if symbol == stock['symbol']:
            isSymbolFound = True
            if int(share) >=0 and int(share) <= stock['SUM(shares)']:
                isShareInRange = True
                trans['symbol'] = symbol
                trans['shares'] = share
                trans['name'] = stock['company']
                info = lookup(symbol)
                trans['price'] = info['price']
                trans['price_usd'] = usd(info['price'])
                trans['total'] = info['price'] *  int(share)
                trans['total_usd'] = usd(info['price'] *  int(share))
                balance = db.execute("SELECT cash FROM users WHERE id = :id", id=session['user_id'])
                cashfwd = balance[0]['cash']
                cashremain = cashfwd + info['price'] * int(share)
                trans['cashfwd'] = usd(cashfwd)
                trans['cashremain'] = usd(cashremain)
            break

    if not isSymbolFound:
        return apology("symbol not found in portfolio", 403)
    if not isShareInRange:
        return apology("shares out of range that you own", 403)
    db.execute("INSERT INTO transactions (user_id, datetime, symbol, company, shares, price, total) VALUES(?, ?, ?, ?, ?, ?, ?)", session["user_id"], dt, symbol, trans['name'], -int(share), trans['price'], trans['total'])
    db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cashremain, id=session['user_id'])
    return render_template("sold.html", trans=trans)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
