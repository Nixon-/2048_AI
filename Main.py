from flask import Flask, request, Response, render_template
import json
import random
import datetime
import Scruffy.Analytics
from pymongo import MongoClient

app = Flask(__name__)

## Up right down Left
ACTIONS = [0, 1, 2, 3]
GRID_SIZE = 4
ALPHA = 0.1
GAMMA = 0.9
Exploration = 0.05

client = None


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response


@app.route("/")
def home():
    return "<h1>Whatup</h1>"


@app.route("/analytics")
def analytics():
    return render_template('analytics.html')


@app.route("/analytics/get_scores", methods=['GET'])
def get_reward_data():
    return Scruffy.Analytics.get_reward_data()


@app.route("/api")
def api_home():
    return "<ul><li>/api/get_script</li><li>/api/initialize</li><li>/api/restart</li>" \
           "<li>/api/next_action</li><li>/api/reward_update</li></ul>"


@app.route("/api/initialize", methods=['POST'])
def initialize():
    global client, active_count, game_id
    if client is None:
        client = MongoClient()
        random.seed()
    return (json.dumps({"game_id": game_id}), 201) if client is not None else (json.dumps("Error in client setup"), 501)


@app.route("/api/get_action", methods=['POST'])
def get_next_action_handler():
    if client is None:
        initialize()
    state = request.json["state"]
    illegals = request.json["illegals"]
    return json.dumps({"action": get_next_action(state, illegals)}), 201


def get_next_action(state, illegals):
    if state is None:
        return random.choice(ACTIONS)
    database = client["AI2048"]
    states = database.states
    record = states.find_one({"state": state})
    if record is None:
        record = create_new_entry(state, states)
    return get_e_greedy_action(record["actions"], illegals)


@app.route("/api/reward_update", methods=['POST'])
def update_reward_handler():
    state = request.json["state"]
    next_state = request.json["next_state"]
    reward = request.json["reward"]
    try:
        action_taken = request.json["action_taken"]
    except KeyError:
        print(request.json)

    if state is None:
        return json.dumps("Reward update is not acceptable"), 501
    reward_update(state, float(reward), next_state, action_taken)
    return json.dumps({"game_id": game_id}), 201


def reward_update(state, action_reward, next_state, action_taken):
    database = client["AI2048"]
    states = database.states
    record = states.find_one({"state": state})
    if record is None:
        return json.dumps("Reward update state doesn't exist????"), 501

    next_record = states.find_one({"state": next_state})
    if next_record is None:
        next_record = create_new_entry(next_state, states)

    reward = action_reward
    reward += ALPHA*(GAMMA * next_record["actions"][str(max(next_record["actions"], key=next_record["actions"].get))] -
                    record["actions"][action_taken])
    record["actions"][action_taken] += reward
    states.update({'_id': record['_id']}, record)


@app.route("/api/restart", methods=['POST'])
def restart_handler():
    state = request.json["state"]
    next_state = request.json["next_state"]
    reward = request.json["reward"]
    action_taken = request.json["action_taken"]
    score = request.json["score"]
    restart(state, next_state, reward, action_taken, score)
    return json.dumps({"game_id": game_id}), 201


def restart(state, next_state, reward, action_taken, score):
    database = client["AI2048"]
    scores = database.scores
    scores.insert_one({"reward": score, "time": datetime.datetime.now().timestamp()})
    if state is None:
        return json.dumps("Reward update is not acceptable"), 501
    reward_update(state, float(reward), next_state, action_taken)


@app.route("/api/get_script", methods=["GET"])
def get_script():
    with open('script.js', 'r') as myfile:
        data = myfile.read()
    return Response(data, mimetype='application/javascript')


@app.route("/static/analytics.js", methods=["GET"])
def get_analytics():
    with open('static/analytics.js', 'r') as myfile:
        data = myfile.read()
    return Response(data, mimetype='application/javascript')


def get_e_greedy_action(actions, illegals):
    illegals = [str(x) for x in illegals]
    if random.uniform(0, 1) > Exploration:
        max_value = next(iter(actions.values()))
        keys = list()
        for key, val in actions.items():
            if val > max_value:
                keys = [key]
                max_value = val
            elif val == max_value:
                keys.append(key)
    else:
        keys = list(actions.keys())

    keys = [x for x in keys if x not in illegals]

    if len(keys) == 0:
        keys = [x for x in [str(y) for y in ACTIONS] if x not in illegals]

    return random.choice(keys) if len(keys) > 0 else "1"


def create_new_entry(state, collection):
    new_entry = dict()
    new_entry["state"] = state
    new_entry["actions"] = dict()
    for i in ACTIONS:
        new_entry["actions"][str(i)] = random.gauss(0, 1)
    collection.insert_one(new_entry)
    return new_entry


if __name__ == "__main__":
    app.run(host="0.0.0.0")
