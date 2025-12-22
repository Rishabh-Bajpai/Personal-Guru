import os
import json

DATA_DIR = 'data'

def save_topic(topic, data):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    filepath = os.path.join(DATA_DIR, f"{topic}.json")
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def load_topic(topic):
    filepath = os.path.join(DATA_DIR, f"{topic}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return None

def get_all_topics():
    if not os.path.exists(DATA_DIR):
        return []
    return [f.replace('.json', '') for f in os.listdir(DATA_DIR) if f.endswith('.json') and f != '.json' and f.strip() != '.json']

def delete_topic(topic):
    filepath = os.path.join(DATA_DIR, f"{topic}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
