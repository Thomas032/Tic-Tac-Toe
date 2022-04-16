from flask_socketio import join_room, leave_room, rooms
from flask import Flask, render_template, request, session, redirect, flash, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
from flask_session import Session
from helpers import login_required
from cs50 import SQL
import random, string

app = Flask(__name__)
db = SQL("sqlite:///database.db")
# make templates auto reload
app.config["TEMPLATES_AUTORELOAD"] = True
app.config["SECRET_KEY"] = "secret"
# configure the session to store as a file not a cookie
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
# start session

Session(app)

# wrap the socket io around the app
socketio = SocketIO(app,  async_mode="eventlet", manage_session=False)

WIN = [ [0, 1, 2],
        [3, 4, 5],
        [6, 7, 8],
        [0, 3, 6],
        [1, 4, 7],
        [2, 5, 8],
        [0, 4, 8],
        [2, 4, 6]
    ]


@app.route("/")
def index():
    if session.get("user_id") is not None:
        # User is already logged in so just forward him to dashboard
        return redirect("/dashboard")
    return render_template("index.html")


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username:
            flash("Missing username", category="danger")
            return redirect("/register")
        existing = db.execute("SELECT * FROM users WHERE username = ?;", username)
        if len(existing) != 0:
            flash("Username already exists", category="danger")
            return redirect("/register")
        if not password:
            flash("Missing password", category="danger")
            return redirect("/register")
        if not confirmation:
            flash("Missing Confirmation Password", category="danger")
            return redirect("/register")
        if password != confirmation:
            flash("Passwords do not match", category="danger")
            return redirect("/register")
        if len(password) < 8:
            flash("Password is too short (must be at least 8 chars)", category="danger")
            return redirect("/register")
        hash = generate_password_hash(password)
        db.execute("INSERT INTO users(username, hash) VALUES (?, ?);", username, hash)
        id = db.execute("SELECT id FROM users WHERE username = ?;", username)[0]["id"]
        session["user_id"] = id
        return redirect("/dashboard")
    else:
        try:
            id = session["user_id"]
            if id:
                return redirect("/dashboard")
        except:    
            return render_template("register.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        new_username = request.form.get("username")
        new_pass = request.form.get("password")
        confirm = request.form.get("confirmation")
        if new_username:
            existing = db.execute("SELECT * FROM users WHERE username = ?;", new_username)
            if len(existing) != 0:
                flash("Username already exists", category="danger")
                return redirect("/profile")
            db.execute("UPDATE users SET username = ? WHERE id = ?;", new_username, session["user_id"])
        if new_pass:
            if new_pass != confirm:
                flash("Passswords do not match", category="danger")
                return redirect("/profile")
            hash = generate_password_hash(new_pass)
            db.execute("UPDATE users SET hash = ? WHERE id = ?;", hash, session["user_id"])
        return redirect("/dashboard")
    else:
        id = session["user_id"]
        user = db.execute("SELECT * FROM users WHERE id = ?", id)
        return render_template("profile.html", user=user[0])

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username:    
            flash("missing username", category="danger")
            return redirect("/login")
        if not password:
            flash("Missing password", category="danger")
            return redirect("/login")
        user = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(user) == 0:
            flash("User doesnt exist", category="danger")
            return redirect(url_for("login"))
        user = user[0]
        if not check_password_hash(user["hash"], password):
            flash("Invalid password", category="danger")
            return redirect(url_for("login"))
        session["user_id"] = user["id"]
        return redirect(url_for("dashboard"))
    else:
        try:
            id = session["user_id"]
            if id:
                return redirect("/dashboard")
        except:
                return render_template("login.html")


def slugify(code:str):
    outcome = ""
    for index, char in enumerate(code):
        index = ord(char) + 3
        new_char = chr(index)
        outcome += new_char
    return outcome


def un_slugify(slug:str):
    code = ""
    for char in slug:
        code += chr(ord(char)-3)
    return code


@app.route("/create-game", methods=["POST", "GET"])
@login_required
def create(): 
    if request.method == "POST":
        id = session["user_id"]
        join_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 6)) 
        exists = len(db.execute("SELECT * FROM game WHERE code = ?", join_code)) == 1
        while(exists):
            join_code = join_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 6))
            exists = len(db.execute("SELECT * FROM game WHERE code = ?", join_code)) == 1
        db.execute("INSERT INTO game (creator_id, code, active) VALUES (?, ?, ?)", id, join_code, 0)
        game_id = db.execute("SELECT * FROM game WHERE code = ?", join_code)[0]["game_id"]
        db.execute("INSERT INTO game_fields (game_id) VALUES (?)", game_id)
        return render_template("wait.html", join_code=join_code)
    else:
        return redirect("/dashboard")


@socketio.on("get_status")
@login_required
def stat(data):
    print(data)
    id = session["user_id"]
    code = data["code"]
    game = db.execute("SELECT * FROM game WHERE code = ? AND creator_id = ?", code, id)
    if len(game) == 0:
        emit("Data_recieved", {"data":"error"} ,json = True)
    game = game[0]
    status = game["active"]
    emit("Data_recieved", {"data":status} ,json = True)

"""
@socketio.on('disconnect')
def test_disconnect():
    emit("end_game")
"""

@app.route('/join-game', methods=['POST', 'GET'])
@login_required
def on_join():
        id = session["user_id"]
        join_code = request.form.get('join_code')
        if not join_code:
            flash("Missing join code!", category="danger")
            return redirect("/dashboard")
        if len(join_code) != 6:
            flash("Join code too short", category="danger")
            return redirect("/dashboard")
        available = db.execute("SELECT * FROM game WHERE code = ?", join_code)
        if len(available) == 0:
            flash("Invalid join code", category="danger")
            return redirect("/dashboard")
        if available[0]["client_id"] == id or available[0]["creator_id"] == id:
            flash("You can't join your own game", category="danger")
            return redirect("/dashboard")
        db.execute("UPDATE game SET active = 1, client_id = ? WHERE code = ?", id,join_code)
        return redirect("/game/" + join_code)


@app.route('/game/<code>')
def game(code):
    id = session["user_id"]
    game = db.execute("SELECT * FROM game WHERE code = ?", code)
    if len(game) == 0:
        return redirect("/dashboard")
    game = game[0]
    if game["creator_id"] != id and game["client_id"] != id:
        return redirect("/dashboard")
    if game["creator_id"] == id:
        my_char = "X"
        oponent_char = "O"
        oponent_id = game["client_id"]
    else:
        my_char = "O"
        oponent_char = "X"
        oponent_id = game["creator_id"]
    db.execute("INSERT INTO game_data(game_id, creator_char, client_char, client_played, creator_played) VALUES (?, ?, ?, ?, ?)", game["game_id"], "X", "O", 0, 0)
    user = db.execute("SELECT * FROM users WHERE id = ?", id)[0]
    oponent = db.execute("SELECT * FROM users WHERE id = ?", oponent_id)[0]
    return render_template("game.html", user=user, oponent=oponent, user_char = my_char, oponent_char=oponent_char, code=code)

   
@socketio.on("user_played")
@login_required
def played(data):
    id = session["user_id"]
    join_code = data["code"]
    game = db.execute("SELECT * FROM game WHERE code = ?",join_code)[0]
    game_id = game["game_id"]
    game_data = db.execute("SELECT * FROM game_data WHERE game_id = ?",  game_id)[0]
    if game_data["client_played"] == 0 and game_data["creator_played"] == 0:
        print("DEF STATE")
        data = 1
        emit("user_played_response", {"data":data})
    if id == game["creator_id"]:
        # CREATOR called
        data = game_data["client_played"]
    else:
        # user is a client -> check if cretaor played
        data = game_data["creator_played"]
    emit("user_played_response", {"data":data})


@socketio.on("make_move")
@login_required
def move(data):
    id = session["user_id"]
    join_code = data["join_code"]
    player = data["character"]
    btn_index = data["index"]
    game = db.execute("SELECT * FROM game WHERE code = ?", join_code)[0]
    game_id = game["game_id"]
    game_data = db.execute("SELECT * FROM game_data WHERE game_id = ?", game_id)
    if game["creator_id"] == id:
        # creator played    
        db.execute("UPDATE game_data SET creator_played = ? WHERE game_id = ?", 1, game_id)
        db.execute("UPDATE game_data SET client_played = ? WHERE game_id = ?", 0, game_id)
    if game["client_id"] == id:
        # client played
        db.execute("UPDATE game_data SET client_played = ? WHERE game_id = ?", 1, game_id)
        db.execute("UPDATE game_data SET creator_played = ? WHERE game_id = ?", 0, game_id)
    field = db.execute("SELECT * FROM game_fields WHERE game_id = ?", game_id)[0]["field"]
    field_list = field.split(',')
    if field_list[btn_index] == '_':
        field_list[btn_index] = player
    outcome = ""
    for item in field_list:
        if field_list.index(item) != len(field_list) -1:
            outcome += item + ","
        else:
            outcome += item
    print(f"Somebody made a move on {btn_index + 1}. button!")
    db.execute("UPDATE game_fields SET field = ? WHERE game_id = ?", outcome, game_id)
    emit("rewrite_field", {"field":str(outcome)})


@socketio.on("get_field")
@login_required
def get(data):
    join_code = data["join_code"]
    game_id = db.execute("SELECT * FROM game WHERE code = ?", join_code)[0]["game_id"]
    field = db.execute("SELECT * FROM game_fields WHERE game_id = ?", game_id)
    field= field[0]["field"]
    emit("rewrite_field", {"field":str(field)})
  

@socketio.on("check_winner")
@login_required
def check_winner(data):
    id = session["user_id"]
    code = data["join_code"]
    game = db.execute("SELECT * FROM game WHERE code = ?", code)[0]
    game_id = game["game_id"]
    game_data = db.execute("SELECT * FROM game_data WHERE game_id = ?", game_id)[0]
    if id == game["creator_id"]:
        player = game_data["creator_char"]
    else:
        player = game_data["client_char"]
    field = db.execute("SELECT * FROM game_fields WHERE game_id = ?", game_id)[0]["field"]
    field = field.split(",")
    for i in range(0,3):
        if field[i] == player and field[i+1] == player and field[i+2] == player:
            won = True
        if field[i] == player and field[i+3] == player and field[i+6] == player:
            won = True
    if field[0] == player and field[4] == player and field[8] == player:
        won = True
    if field[2] == player and field[4] == player and field[6] == player:
        won = True
    if won:
        print("!"*5+player+"WON"+"!"*5)
        winner = db.execute("SELECT * FROM users WHERE id = ?;", id)[0]
        db.execute("UPDATE game_data SET winner_id = ? WHERE game_id = ?;",id ,game_id)
        db.execute("UPDATE game SET winner_id = ? WHERE game_id = ?;", id, game_id)
        emit("user_won", {"winner_id":id, "username":winner["username"], "character":player})
        emit("end_game")

@socketio.on("check_loser")
@login_required
def check_loser(data):
    id = session["user_id"]
    join_code = data["join_code"]
    game_id = db.execute("SELECT * FROM game WHERE code = ?;", join_code)[0]["game_id"]
    winner_id = db.execute("SELECT * FROM game_data WHERE game_id = ?;", game_id)[0]["winner_id"]
    if winner_id:
        if winner_id != id:
            # -> user lost
            emit("user_lost", {"beaver":"Bober"})
            emit("end_game")


@socketio.on("cleanup")
@login_required
def cleanup(data):
    join_code = data["join_code"]
    game_id = db.execute("SELECT * FROM game WHERE code = ?;", join_code)[0]["game_id"]
    db.execute("DELETE FROM game_data WHERE game_id = ?", game_id)
    db.execute("UPDATE game SET code = ? WHERE game_id = ?", "ENDED",game_id)
    db.execute("DELETE FROM game_fields WHERE game_id = ?", game_id)
    print("ALL clear now!")


@app.route("/status", methods=["GET", "POST"])
@login_required
def state():
    id = session["user_id"]
    data = db.execute("SELECT * FROM game WHERE creator_id = ? OR client_id = ?;", id, id)
    if len(data) == 0:
        return redirect("/dashboard")
    data = data[0]
    if len(data) == 0:
        return "ERROR", 404
    if data["client_id"] == id:
        oponent_id = data["creator_id"]
    else:
        oponent_id = data["client_id"]

    oponent = db.execute("SELECT * from users WHERE id = ?", oponent_id)[0]["username"]
    print("Oponent is "+oponent)
    status = str(data["active"])
    return jsonify(status=status, oponent=oponent), 200


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/login")


@app.route("/dashboard")
@login_required
def dashboard():
    user = db.execute("SELECT * FROM users WHERE id = ?;", session["user_id"])[0]
    return render_template("dashboard.html", user=user)


if __name__ == '__main__':
    socketio.run(app)
