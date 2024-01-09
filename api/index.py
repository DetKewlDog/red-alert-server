from flask import Flask, Response, make_response, send_file, request
from flask_cors import CORS

import json, os, requests
from datetime import datetime, timedelta

from overpy import Overpass

from dotenv import load_dotenv

from typing_extensions import Tuple

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)
api = Overpass()

load_dotenv()

GEOCODE_API_KEY  : str = str(os.environ.get("GEOCODE_API_KEY" ))
GEONODE_USERNAME : str = str(os.environ.get("GEONODE_USERNAME"))
GEONODE_PASSWORD : str = str(os.environ.get("GEONODE_PASSWORD"))
GEONODE_DNS      : str = str(os.environ.get("GEONODE_DNS"     ))

proxies = [{ 'http': f'http://{GEONODE_USERNAME}:{GEONODE_PASSWORD}@{GEONODE_DNS }:{i}' } for i in range(11000, 11011)]
proxy_index = 0

def rotate_proxy():
  global proxy_index
  proxy_index += 1
  proxy_index %= len(proxies)
  print('Switched to proxy', proxy_index)
def get_proxy():
  return proxies[proxy_index]


def jsonify(data: object, status_code: int = 200) -> Tuple[Response, int]:
  response = make_response(json.dumps(data, indent=4, ensure_ascii=False))
  response.headers['Content-Type'] = 'application/json'
  return response, status_code

@app.route('/')
def main():
  return 'Connected'

@app.route('/cities')
def fetch_cities():
  return send_file('./cities.json')

@app.route('/realtime')
def realtime():
  r = requests.get('https://www.kore.co.il/redAlert.json', proxies=get_proxy())
  response = make_response(r.text)
  response.headers['Content-Type'] = 'application/json'
  return response, r.status_code


@app.route('/geocode/<city>')
def geocode(city: str):
  r = requests.get(f'https://geocode.maps.co/search?q={city}&api_key={GEOCODE_API_KEY}', proxies=get_proxy())
  response = make_response(r.text)
  response.headers['Content-Type'] = 'application/json'
  return response, r.status_code


@app.route('/geometry')
def geometry():
  data = request.args.get('data')
  print(data)
  return jsonify(api.query(data), 200)


@app.route('/history')
def history():
  r = requests.get('https://api.tzevaadom.co.il/alerts-history/?', proxies=get_proxy())
  response = make_response(r.text)
  response.headers['Content-Type'] = 'application/json'
  return response, r.status_code


if __name__ == '__main__':
  app.run(host="0.0.0.0", port=8080, debug=True)

