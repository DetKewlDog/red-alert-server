from flask import Flask, Response, make_response, send_file, request
from flask_cors import CORS

import json, os, requests, random, urllib3, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dateutil import parser

from supabase import create_client, Client
from timeloop import Timeloop
from pytz import timezone
from colorama import Fore

from typing_extensions import Union


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

load_dotenv()

GEONODE_USERNAME : str = str(os.environ.get("GEONODE_USERNAME"))
GEONODE_PASSWORD : str = str(os.environ.get("GEONODE_PASSWORD"))
GEONODE_DNS      : str = str(os.environ.get("GEONODE_DNS"     ))

SUPABASE_URL     : str = str(os.environ.get("SUPABASE_URL"    ))
SUPABASE_KEY     : str = str(os.environ.get("SUPABASE_KEY"    ))


supabase : Client = create_client(SUPABASE_URL, SUPABASE_KEY)

tl = Timeloop()

alert_id: int = -1
alert_type: int = -1
cities: list[str] = []
timestamp: Union[datetime, None] = None
red_alert: Union[dict[str, Union[str, list[str]]]] = {}
random_alerts_area: Union[int, None] = None

tz = timezone('Asia/Jerusalem')

proxies = [
  { 'http': f'http://{GEONODE_USERNAME}:{GEONODE_PASSWORD}@{GEONODE_DNS}:{i}' }
  for i in range(11000, 11011)
]
proxy_index = 0


def rotate_proxy():
  global proxy_index
  proxy_index += 1
  proxy_index %= len(proxies)

def get_proxy():
  return proxies[proxy_index]


def jsonify(data: object, status_code: int = 200) -> tuple[Response, int]:
  return to_json(make_response(json.dumps(data, indent=4, ensure_ascii=False)), status_code)

def to_json(data: str, status_code: int = 200) -> tuple[Response, int]:
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
  if random_alerts_area != None:
    r = requests.get(f'{request.host_url}dev/random/{random_alerts_area}')
    return to_json(r.text, r.status_code)

  return jsonify(get_red_alert())

@app.route('/geometry')
def geometry():
  return relay_request('https://www.tzevaadom.co.il/static/polygons.json')

@app.route('/history')
@app.route('/history/<int:id>')
def history(id=-1):
  builder = supabase.table('alert_history').select('*')
  if id != -1:
    builder = builder.eq('alert_id', id)
  res = builder.execute()

  if res == None:
    return None, 404

  data = [
    {
      'id': i['alert_id'],
      'description': None,
      'alerts': [
        {
          'time': int(parser.isoparse(i['timestamp']).timestamp()),
          'cities': json.loads(i['cities']),
          'threat': i['alert_type'],
          'isDrill': False
        }
      ]
    } for i in res.data
  ]

  if id != -1:
    data = data[0]

  return jsonify(data)


@app.route('/dev/sync_db')
def sync_database():
  data = json.loads(get('https://api.tzevaadom.co.il/alerts-history').text)

  data = [
    {
      'timestamp': datetime.fromtimestamp(alert['alerts'][0]['time'], tz).replace(microsecond=0).isoformat(),
      'cities': json.dumps([
        city for cities in (a['cities'] for a in alert['alerts']) for city in cities
      ], ensure_ascii=False),
      'alert_type': alert['alerts'][0]['threat'],
      'alert_id': alert['id']
    } for alert in data
  ]

  try:
    supabase.table('alert_history').delete().neq('alert_id', -1).execute()
    time.sleep(0.1)
    supabase.table('alert_history').delete().is_('alert_id', 'null').execute()
    time.sleep(0.1)
    supabase.table('alert_history').insert(data).execute()
  except:
    raise 'Error raised while trying to contact database, double check that the Supabase instance is running!'

  r = requests.get(f'{request.host_url}history')
  return to_json(r.text, r.status_code)


@app.route('/dev/random')
@app.route('/dev/random/<int:area>')
def random_cities(area = -1):
  global random_alerts_area
  random_alerts_area = area

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

  result = {
    'id': 1,
    'cat': 1,
    'title': 'Rockets',
    'data': [city for city, data in cities.items() if data['area'] == area or area == -1],
    'desc': 'Enter a shelter and remain in it for 10 minutes'
  }

  set_red_alert(result)
  return jsonify(result)

@app.route('/dev/clear')
def clear():
  global random_alerts_area
  random_alerts_area = None
  set_red_alert(None)
  return 'cleared', 200


@app.route('/dev/push/all')
@app.route('/dev/push/all/<int:area>')
def push_all_cities(area = -1):
  r = requests.get(f'{request.host_url}dev/all/{area}')

  red_alert = json.loads(r.text)

  set_alert_type(int(red_alert['cat']) - 1)
  set_alert_id(red_alert['id'])
  set_timestamp(datetime.now(tz))

  cities = get_cities()
  [cities.append(city) for city in red_alert['data'] if city not in cities]
  set_cities(cities)

  create_alert_bundle()

  r = requests.get(f'{request.host_url}dev/clear')
  return to_json(r.text, r.status_code)

@app.route('/dev/push/random')
@app.route('/dev/push/random/<int:area>')
def push_random_cities(area = -1):
  r = requests.get(f'{request.host_url}dev/random/{area}')

  red_alert = json.loads(r.text)

  set_alert_type(int(red_alert['cat']) - 1)
  set_alert_id(red_alert['id'])
  set_timestamp(datetime.now(tz))

  cities = get_cities()
  [cities.append(city) for city in red_alert['data'] if city not in cities]
  set_cities(cities)

  create_alert_bundle()

  r = requests.get(f'{request.host_url}dev/clear')
  return to_json(r.text, r.status_code)

def get_alert_id():
  return alert_id
def set_alert_id(value):
  global alert_id
  alert_id = value

def get_alert_type():
  return alert_type
def set_alert_type(value):
  global alert_type
  alert_type = value

def get_cities():
  return cities
def set_cities(value):
  global cities
  cities = value

def get_timestamp():
  return timestamp
def set_timestamp(value):
  global timestamp
  timestamp = value

def get_red_alert():
  return red_alert
def set_red_alert(value):
  global red_alert
  red_alert = value


def create_alert_bundle():
  alert_id, alert_type, cities, timestamp = get_alert_id(), get_alert_type(), get_cities(), get_timestamp()
  if timestamp == None:
    return

  _timestamp = timestamp.replace(microsecond=0).isoformat()

  print(json.dumps({
    'timestamp': _timestamp,
    'cities': cities,
    'alert_type': alert_type,
    'alert_id': alert_id,
  }, indent=2))

  supabase.table('alert_history').insert({
    'timestamp': _timestamp,
    'cities': json.dumps(cities, ensure_ascii=False),
    'alert_type': alert_type,
    'alert_id': alert_id,
  }).execute()

  set_cities([])
  set_alert_id(-1)
  set_alert_type(-1)
  set_timestamp(None)


@tl.job(interval=timedelta(seconds=3))
def process_alerts_t():
  try:
    r = get('https://www.kore.co.il/redAlert.json')
    red_alert = json.loads(r.text.replace("'", '"')) if r != 'null' else None
    print(red_alert)
    set_red_alert(red_alert)

    if red_alert != None:
      print(red_alert)
      if get_alert_type() == -1:
        set_alert_type(int(red_alert['cat']) - 1)
        set_alert_id(red_alert['id'])
        set_timestamp(datetime.now(tz))
      cities = get_cities()
      [cities.append(city) for city in red_alert['data'] if city not in cities]
      set_cities(cities)
      return

    cities = get_cities()
    if len(cities) == 0:
      return

    set_cities(list(set(cities)))
    create_alert_bundle()
  except Exception as e:
    print(Fore.RED + str(e) + Fore.RESET)
    rotate_proxy()

if __name__ == '__main__':
  tl.start(block=False)
  app.run(host="0.0.0.0", port=8080, debug=False)

