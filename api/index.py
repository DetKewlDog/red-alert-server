from flask import Flask, Response, make_response, send_file
from flask_cors import CORS

import json, os, requests

from dotenv import load_dotenv

from typing_extensions import Tuple

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

load_dotenv()

GEONODE_USERNAME : str = str(os.environ.get("GEONODE_USERNAME"))
GEONODE_PASSWORD : str = str(os.environ.get("GEONODE_PASSWORD"))
GEONODE_DNS      : str = str(os.environ.get("GEONODE_DNS"     ))

proxies = [
  { 'http': f'http://{GEONODE_USERNAME}:{GEONODE_PASSWORD}@{GEONODE_DNS }:{i}' }
  for i in range(11000, 11011)
]
proxy_index = 0

def rotate_proxy():
  global proxy_index
  proxy_index += 1
  proxy_index %= len(proxies)

def get_proxy():
  return proxies[proxy_index]


def jsonify(data: object, status_code: int = 200) -> Tuple[Response, int]:
  return to_json(make_response(json.dumps(data, indent=4, ensure_ascii=False)), status_code)

def to_json(data: str, status_code: int = 200) -> Tuple[Response, int]:
  response = make_response(data)
  response.headers['Content-Type'] = 'application/json'
  return response, status_code

def relay_request(url):
  r = requests.get(url, proxies=get_proxy())
  rotate_proxy()
  return to_json(r.text, r.status_code)

@app.route('/')
def main():
  return 'Connected'

@app.route('/cities')
def fetch_cities():
  return send_file('./cities.json')

@app.route('/realtime')
def realtime():
  return relay_request('https://www.kore.co.il/redAlert.json')

@app.route('/geometry')
def geometry():
  return relay_request('https://www.tzevaadom.co.il/static/polygons.json')

@app.route('/history')
@app.route('/history/<id>')
def history(id=''):
  id = '' if id == '' else f'/id/{id}'
  return relay_request(f'https://api.tzevaadom.co.il/alerts-history/{id}')


if __name__ == '__main__':
  app.run(host="0.0.0.0", port=8080, debug=False)

