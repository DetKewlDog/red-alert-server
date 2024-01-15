from flask import Flask, Response, make_response, send_file
from flask_cors import CORS

import json, os, requests, random, urllib3
from typing_extensions import Tuple
from dotenv import load_dotenv
from itertools import groupby
from dateutil import parser

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

def get(url, headers={}):
  r = requests.get(url, headers=headers, proxies=get_proxy())
  rotate_proxy()
  return r

def relay_request(url):
  r = get(url)
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

@app.route('/dev/history')
def dev_history():
  headers = {
    'Referer': 'https://www.oref.org.il/11226-he/pakar.aspx',
    'X-Requested-With': 'XMLHttpRequest',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
  }
  r = get('https://www.oref.org.il//Shared/Ajax/GetAlarmsHistory.aspx?lang=he&mode=3', headers=headers)
  try:
    data = json.loads(r.text)
    key_func = lambda i: i['alertDate']

    def create_alert(data):
      data = list(data)
      categories = [i['category_desc'] for i in data]
      return {
        'data': [i['data'] for i in data],
        'title': max(set(categories), key=categories.count),
      }

    return jsonify({
      parser.parse(k).strftime("%m/%d/%Y, %H:%M:%S"):create_alert(v)
      for k, v in groupby(
        sorted(data, key=key_func, reverse=True), key_func
      )
    })
  except Exception as e:
    return str(e) + '\n' + r.text


@app.route('/dev/random')
@app.route('/dev/random/<int:area>')
def random_cities(area = -1):
  with open('api/cities.json', 'r', encoding='utf8') as f:
    cities = json.loads(f.read())

  city_names = [city for city, data in cities.items() if data['area'] == area or area == -1]

  amount = random.randint(0, len(city_names))
  if amount == 0:
    return jsonify(None)

  return jsonify({
    'id': 1,
    'cat': 1,
    'title': 'Rockets',
    'data': random.sample(city_names, amount),
    'desc': 'Enter a shelter and remain in it for 10 minutes'
  })

@app.route('/dev/all')
@app.route('/dev/all/<int:area>')
def all_cities(area = -1):
  with open('api/cities.json', 'r', encoding='utf8') as f:
    cities = json.loads(f.read())

  return jsonify({
    'id': 1,
    'cat': 1,
    'title': 'Rockets',
    'data': [city for city, data in cities.items() if data['area'] == area or area == -1],
    'desc': 'Enter a shelter and remain in it for 10 minutes'
  })


if __name__ == '__main__':
  app.run(host="0.0.0.0", port=8080, debug=False)

