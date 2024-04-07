import json
import logging
import os
import random
import requests
import string
import threading
import time
import urllib.parse
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from flask_socketio import SocketIO
from datetime import datetime, timezone
from unidecode import unidecode
from pathlib import Path
from icalendar import Calendar, Event, vCalAddress, vText

class DataHandler:
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        self.logger = logging.getLogger()
        self.search_in_progress_flag = False
        self.gig_event = None
        self.new_found_gigs_counter = 0
        self.clients_connected_counter = 0
        self.config_folder = "config"
        self.gigs = []
        self.lidarr_items = []
        self.cleaned_lidarr_items = []
        self.stop_event = threading.Event()
        self.stop_event.set()
        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)
        self.load_environ_or_config_settings()

    def load_environ_or_config_settings(self):
        # Defaults
        default_settings = {
            "lidarr_address": "http://192.168.1.2:8686",
            "lidarr_api_key": "",
            "fallback_to_top_result": False,
            "lidarr_api_timeout": 120.0,
            "app_name": "Calidarr",
            "app_rev": "0.04",
            "app_url": "http://" + "".join(random.choices(string.ascii_lowercase, k=10)) + ".com",
            "mode": "Songkick",
        }

        # Load settings from environmental variables (which take precedence) over the configuration file.
        self.lidarr_address = os.environ.get("lidarr_address", "")
        self.lidarr_api_key = os.environ.get("lidarr_api_key", "")
        fallback_to_top_result = os.environ.get("fallback_to_top_result", "")
        self.fallback_to_top_result = fallback_to_top_result.lower() == "true" if fallback_to_top_result != "" else ""
        lidarr_api_timeout = os.environ.get("lidarr_api_timeout", "")
        self.lidarr_api_timeout = float(lidarr_api_timeout) if lidarr_api_timeout else ""
        self.app_name = os.environ.get("app_name", "")
        self.app_rev = os.environ.get("app_rev", "")
        self.app_url = os.environ.get("app_url", "")
        self.mode = os.environ.get("mode", "")

        # Load variables from the configuration file if not set by environmental variables.
        try:
            self.settings_config_file = os.path.join(self.config_folder, "settings_config.json")
            if os.path.exists(self.settings_config_file):
                self.logger.info(f"Loading Config via file")
                with open(self.settings_config_file, "r") as json_file:
                    ret = json.load(json_file)
                    for key in ret:
                        if getattr(self, key) == "":
                            setattr(self, key, ret[key])
        except Exception as e:
            self.logger.error(f"Error Loading Config: {str(e)}")

        # Load defaults if not set by an environmental variable or configuration file.
        for key, value in default_settings.items():
            if getattr(self, key) == "":
                setattr(self, key, value)

        # Save config.
        self.save_config_to_file()

    def connection(self):
        self.clients_connected_counter += 1

    def disconnection(self):
        self.clients_connected_counter = max(0, self.clients_connected_counter - 1)

    def start(self, data):
        try:
            socketio.emit("clear")
            self.new_found_gigs_counter = 1
            self.raw_new_gigs = []
            self.artists_to_use_in_search = []
            self.gigs = []

            for item in self.lidarr_items:
                item_name = item["name"]
                if item_name in data:
                    item["checked"] = True
                    self.artists_to_use_in_search.append(item_name)
                else:
                    item["checked"] = False

            if self.artists_to_use_in_search:
                self.stop_event.clear()
            else:
                self.stop_event.set()
                raise Exception("No Lidarr Artists Selected")

        except Exception as e:
            self.logger.error(f"Startup Error: {str(e)}")
            self.stop_event.set()
            ret = {"Status": "Error", "Code": str(e), "Data": self.lidarr_items, "Running": not self.stop_event.is_set()}
            socketio.emit("lidarr_sidebar_update", ret)

        else:
            self.find_gigs()

    def on_gig_event(self, fn):
        self.gig_event = fn

    def set_artists_from_lidarr(self, items):
        self.lidarr_items = [{"name": unidecode(artist, replace_str=" "), "checked": False} for artist in items]
        self.cleaned_lidarr_items = [item["name"].lower() for item in self.lidarr_items]

    def get_artists_from_lidarr(self):
        try:
            self.logger.info(f"Getting Artists from Lidarr")
            self.lidarr_items = []
            endpoint = f"{self.lidarr_address}/api/v1/artist"
            headers = {"X-Api-Key": self.lidarr_api_key}
            response = requests.get(endpoint, headers=headers, timeout=self.lidarr_api_timeout)

            if response.status_code == 200:
                self.full_lidarr_artist_list = response.json()
                self.lidarr_items = [{"name": unidecode(artist["artistName"], replace_str=" "), "checked": False} for artist in self.full_lidarr_artist_list]
                self.lidarr_items.sort(key=lambda x: x["name"].lower())
                self.cleaned_lidarr_items = [item["name"].lower() for item in self.lidarr_items]
                status = "Success"
                data = self.lidarr_items
            else:
                status = "Error"
                data = response.text

            ret = {"Status": status, "Code": response.status_code if status == "Error" else None, "Data": data, "Running": not self.stop_event.is_set()}

        except Exception as e:
            self.logger.error(f"Getting Artist Error: {str(e)}")
            ret = {"Status": "Error", "Code": 500, "Data": str(e), "Running": not self.stop_event.is_set()}

        finally:
            socketio.emit("lidarr_sidebar_update", ret)

    def find_gigs(self):
        if self.stop_event.is_set() or self.search_in_progress_flag:
            return
        elif self.mode == "Songkick" and self.new_found_gigs_counter > 0:
            try:
                self.logger.info(f"Searching for new gigs via {self.mode}")
                self.new_found_gigs_counter = 0
                self.search_in_progress_flag = True
                # random_artists = random.sample(self.artists_to_use_in_search, min(5, len(self.artists_to_use_in_search)))
                random_artists = self.artists_to_use_in_search

                for artist_name in random_artists:
                    if self.stop_event.is_set():
                        break

                    try:
                        self.logger.info(f"Searching for new gigs of {artist_name}")
                        response = requests.get(f'https://www.songkick.com/search?query={artist_name}&type=')
                        time.sleep(2)

                        soup = BeautifulSoup(response.text, 'html.parser')
                        artist_url = soup.select_one('.artist .thumb.search-link')

                        if artist_url is None:
                            self.logger.info(f"  nothing for {artist_name}")
                            continue

                        artist_url = f"https://www.songkick.com{artist_url['href']}/calendar"
                        self.logger.info(f"  fetching {artist_url}")
                        response = requests.get(artist_url)
                        time.sleep(2)

                        soup = BeautifulSoup(response.text, 'html.parser')
                        artist_img = soup.select_one('.profile-picture-wrap img.artist-profile-image')
                        img_link = artist_img['src'] if artist_img else None

                        gigs = soup.select('ol.event-listings.tour-calendar-summary li.event-listing')
                        self.logger.info(f"  {len(gigs)} gigs found for {artist_name}")

                        for gig in gigs:
                            evt_link = gig.select_one('a')
                            evt_link = f"https://www.songkick.com{evt_link['href']}" if evt_link else None

                            evt_date = gig.select_one('a time')
                            evt_date = evt_date['datetime'] if evt_date else None

                            state_tag = gig.select_one('.event-details .item-state-tag')
                            state_tag = state_tag.get_text().strip() if state_tag else None

                            venue = gig.select_one('.event-details .secondary-detail')
                            venue = venue.get_text().strip() if venue else None

                            location = gig.select_one('.event-details .primary-detail')
                            location = location.get_text().strip() if location else None

                            gig_data = {
                                "Name": artist_name,
                                "Img_Link": img_link,
                                "Evt_Link": evt_link,
                                "Evt_Date": evt_date,
                                "Venue": venue,
                                "Location": location,
                                "Status": state_tag,
                            }
                            self.raw_new_gigs.append(gig_data)
                            socketio.emit("more_gigs_loaded", [gig_data])
                            self.new_found_gigs_counter += 1
                            if self.gig_event is not None:
                                self.gig_event(gig_data)

                    except Exception as e:
                        self.logger.error(f"Songkick Error: {str(e)}")

                if self.new_found_gigs_counter == 0:
                    self.logger.info("Search Exhausted - Try selecting more artists from existing Lidarr library")
                    socketio.emit("new_toast_msg", {"title": "Search Exhausted", "message": "Try selecting more artists from existing Lidarr library"})
                else:
                    self.gigs.extend(self.raw_new_gigs)

            except Exception as e:
                self.logger.error(f"Songkick Error: {str(e)}")

            finally:
                self.search_in_progress_flag = False

        elif self.new_found_gigs_counter == 0:
            try:
                self.search_in_progress_flag = True
                self.logger.info("Search Exhausted - Try selecting more artists from existing Lidarr library")
                socketio.emit("new_toast_msg", {"title": "Search Exhausted", "message": "Try selecting more artists from existing Lidarr library"})
                time.sleep(2)

            except Exception as e:
                self.logger.error(f"Search Exhausted Error: {str(e)}")

            finally:
                self.search_in_progress_flag = False

    def load_settings(self):
        try:
            data = {
                "lidarr_address": self.lidarr_address,
                "lidarr_api_key": self.lidarr_api_key,
            }
            socketio.emit("settingsLoaded", data)
        except Exception as e:
            self.logger.error(f"Failed to load settings: {str(e)}")

    def update_settings(self, data):
        try:
            self.lidarr_address = data["lidarr_address"]
            self.lidarr_api_key = data["lidarr_api_key"]
        except Exception as e:
            self.logger.error(f"Failed to update settings: {str(e)}")

    def format_numbers(self, count):
        if count >= 1000000:
            return f"{count / 1000000:.1f}M"
        elif count >= 1000:
            return f"{count / 1000:.1f}K"
        else:
            return count

    def save_config_to_file(self):
        try:
            with open(self.settings_config_file, "w") as json_file:
                json.dump(
                    {
                        "lidarr_address": self.lidarr_address,
                        "lidarr_api_key": self.lidarr_api_key,
                        "fallback_to_top_result": self.fallback_to_top_result,
                        "lidarr_api_timeout": float(self.lidarr_api_timeout),
                        "app_name": self.app_name,
                        "app_rev": self.app_rev,
                        "app_url": self.app_url,
                        "mode": self.mode,
                    },
                    json_file,
                    indent=4,
                )

        except Exception as e:
            self.logger.error(f"Error Saving Config: {str(e)}")

class CalendarHandler:
    def __init__(self):
        self.backend = DataHandler()
        self.logger = logging.getLogger()
        self.cal = Calendar()
        self.cal.add('prodid', "-//Next gigs//example.com//")
        self.cal.add('version', '2.0')

    def add_event(self, gig):
        event = Event()
        event.add('name', vText("%s at %s" % (gig["Name"], gig["Venue"])))
        event.add('description', vText(""))
        date = datetime.strptime(gig["Evt_Date"], '%Y-%m-%dT%H:%M:%S%z')
        event.add('dtstart', date)
        event.add('dtend', date)
        event.add('location', vText("%s, %s" % (gig["Venue"], gig["Location"])))
        self.cal.add_component(event)

    def display(self, countries, names):
        cache = str(hash("%s - %s - %s" % (','.join(countries), ','.join(names), datetime.now().strftime("%j"))))
        expected_file = os.path.join(self.backend.config_folder, "calendar_%s" % cache)
        ical = ''
        if os.path.exists(expected_file):
            self.logger.info("Return cached result %s" % expected_file)
            with open(expected_file, mode='r') as file:
                ical = file.read()
            return ical

        thread = threading.Thread(target=self.run, args=(countries, names, cache,), name="Calendar_Thread")
        thread.daemon = True
        thread.start()

        # just a fake event as feedback
        self.add_event({
            "Name": "This calendar will be updated once data are found",
            "Venue": "System",
            "Location": "",
            "Evt_Date": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z'),
        })
        return self.cal.to_ical().decode("utf-8").replace('\r\n', '\n').strip()

    def run(self, countries, names, cache = None):
        if len(names) <= 0:
            self.backend.get_artists_from_lidarr()
            names = self.backend.cleaned_lidarr_items

        def try_add_event(gig):
            try:
                country_pass = any([gig["Location"].lower().endswith(c.lower()) for c in countries])
                if len(countries) == 0 or country_pass:
                    self.add_event(gig)
            except Exception as e:
                print("ERROR: %s" % e)
                pass

        self.backend.set_artists_from_lidarr(names)
        self.backend.on_gig_event(try_add_event)
        self.backend.start(names)

        if cache:
            expected_file = os.path.join(self.backend.config_folder, "calendar_%s" % cache)
            self.logger.info("Write cached result %s" % expected_file)
            with open(expected_file, "wb") as file:
                file.write(self.cal.to_ical())


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)
data_handler = DataHandler()


@app.route("/")
def home():
    return render_template("base.html")

@app.route('/calendar/<countries>')
def calendar(countries):
    cal = CalendarHandler()
    return cal.display(countries.split(','), []), {"Content-Type": "text/calendar"}

@socketio.on("side_bar_opened")
def side_bar_opened():
    if data_handler.lidarr_items:
        ret = {"Status": "Success", "Data": data_handler.lidarr_items, "Running": not data_handler.stop_event.is_set()}
        socketio.emit("lidarr_sidebar_update", ret)


@socketio.on("get_lidarr_artists")
def get_lidarr_artists():
    thread = threading.Thread(target=data_handler.get_artists_from_lidarr, name="Lidarr_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("finder")
def find_gigs(data):
    thread = threading.Thread(target=data_handler.find_gigs, args=(data,), name="Find_gigs_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("connect")
def connection():
    data_handler.connection()


@socketio.on("disconnect")
def disconnection():
    data_handler.disconnection()


@socketio.on("load_settings")
def load_settings():
    data_handler.load_settings()


@socketio.on("update_settings")
def update_settings(data):
    data_handler.update_settings(data)
    data_handler.save_config_to_file()


@socketio.on("start_req")
def starter(data):
    data_handler.start(data)


@socketio.on("stop_req")
def stopper():
    data_handler.stop_event.set()


@socketio.on("load_more_gigs")
def load_more_gigs():
    thread = threading.Thread(target=data_handler.find_gigs, name="FindSimilar")
    thread.daemon = True
    thread.start()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
