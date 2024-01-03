from flask import Flask, Response, make_response, send_file
from flask_cors import CORS

import json, os, requests
from datetime import datetime, timedelta

from timeloop import Timeloop
from supabase import create_client, Client
from dotenv import load_dotenv
from colorama import Fore

from typing_extensions import List, Union, Dict, Tuple

from pytz import timezone

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = 'https://www.kore.co.il/redAlert.json'

app = Flask(__name__)
CORS(app)

load_dotenv()

SUPABASE_URL     : str = str(os.environ.get("SUPABASE_URL"    ))
SUPABASE_KEY     : str = str(os.environ.get("SUPABASE_KEY"    ))
GEOCODE_API_KEY  : str = str(os.environ.get("GEOCODE_API_KEY" ))
GEONODE_USERNAME : str = str(os.environ.get("GEONODE_USERNAME"))
GEONODE_PASSWORD : str = str(os.environ.get("GEONODE_PASSWORD"))
GEONODE_DNS      : str = str(os.environ.get("GEONODE_DNS"     ))

supabase : Client = create_client(SUPABASE_URL, SUPABASE_KEY)
proxies = [{ 'http': f'http://{GEONODE_USERNAME}:{GEONODE_PASSWORD}@{GEONODE_DNS }:{i}' } for i in range(11000, 11011)]
proxy_index = 0

def rotate_proxy():
  global proxy_index
  proxy_index += 1
  proxy_index %= len(proxies)
  print('Switched to proxy', proxy_index)
def get_proxy():
  return proxies[proxy_index]

tl = Timeloop()

alert_type: str = ''
cities: List[str] = []
timestamp: Union[datetime, None] = None
red_alert: Union[Dict[str, Union[str, List[str]]], None] = {}

tz = timezone('Asia/Jerusalem')


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
  return jsonify(get_red_alert())


@app.route('/geocode/<city>')
def geocode(city: str):
  r = requests.get(f'https://geocode.maps.co/search?q={city}&api_key={GEOCODE_API_KEY}', proxies=get_proxy())
  response = make_response(r.text)
  response.headers['Content-Type'] = 'application/json'
  return response, r.status_code


@app.route('/history')
def history():
  res = supabase.table('alert_history').select('*').execute()
  return jsonify(res.data)

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
  alert_type, cities, timestamp = get_alert_type(), get_cities(), get_timestamp()
  if timestamp == None:
    return
  print(json.dumps({
    'timestamp': timestamp.replace(microsecond=0).isoformat(),
    'cities': cities,
    'alert_type': alert_type,
  }, indent=2))
  supabase.table('alert_history').insert({
    'timestamp': timestamp.replace(microsecond=0).isoformat(),
    'cities': json.dumps(cities, ensure_ascii=False),
    'alert_type': alert_type,
  }).execute()
  set_cities([])
  set_alert_type('')
  set_timestamp(None)


@tl.job(interval=timedelta(seconds=1))
def process_alerts_t():
  try:
    r = requests.get(API_URL, proxies=get_proxy())
    red_alert = json.loads(r.text.replace("'", '"')) if r != 'null' else None
    print(red_alert)
    set_red_alert(red_alert)

    if red_alert != None:
      print(red_alert)
      if get_alert_type() == '':
        set_alert_type(str(red_alert['title']))
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
  app.run(host="0.0.0.0", port=8080, debug=True)

