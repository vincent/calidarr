import json
import logging
import os
import pylast
import random
import requests
import string
import threading
import time
import urllib.parse
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from flask_socketio import SocketIO
from thefuzz import fuzz
from unidecode import unidecode

class DataHandler:
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        self.lidagigs_logger = logging.getLogger()
        self.musicbrainzngs_logger = logging.getLogger("musicbrainzngs")
        self.musicbrainzngs_logger.setLevel("WARNING")
        self.pylast_logger = logging.getLogger("pylast")
        self.pylast_logger.setLevel("WARNING")
        self.search_in_progress_flag = False
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
            "root_folder_path": "/data/media/music/",
            "spotify_client_id": "",
            "spotify_client_secret": "",
            "fallback_to_top_result": False,
            "lidarr_api_timeout": 120.0,
            "quality_profile_id": 1,
            "metadata_profile_id": 1,
            "search_for_missing_albums": False,
            "dry_run_adding_to_lidarr": False,
            "app_name": "Lidagigs",
            "app_rev": "0.04",
            "app_url": "http://" + "".join(random.choices(string.ascii_lowercase, k=10)) + ".com",
            "last_fm_api_key": "",
            "last_fm_api_secret": "",
            "mode": "Spotify",
        }

        # Load settings from environmental variables (which take precedence) over the configuration file.
        self.lidarr_address = os.environ.get("lidarr_address", "")
        self.lidarr_api_key = os.environ.get("lidarr_api_key", "")
        self.root_folder_path = os.environ.get("root_folder_path", "")
        self.spotify_client_id = os.environ.get("spotify_client_id", "")
        self.spotify_client_secret = os.environ.get("spotify_client_secret", "")
        fallback_to_top_result = os.environ.get("fallback_to_top_result", "")
        self.fallback_to_top_result = fallback_to_top_result.lower() == "true" if fallback_to_top_result != "" else ""
        lidarr_api_timeout = os.environ.get("lidarr_api_timeout", "")
        self.lidarr_api_timeout = float(lidarr_api_timeout) if lidarr_api_timeout else ""
        quality_profile_id = os.environ.get("quality_profile_id", "")
        self.quality_profile_id = int(quality_profile_id) if quality_profile_id else ""
        metadata_profile_id = os.environ.get("metadata_profile_id", "")
        self.metadata_profile_id = int(metadata_profile_id) if metadata_profile_id else ""
        search_for_missing_albums = os.environ.get("search_for_missing_albums", "")
        self.search_for_missing_albums = search_for_missing_albums.lower() == "true" if search_for_missing_albums != "" else ""
        dry_run_adding_to_lidarr = os.environ.get("dry_run_adding_to_lidarr", "")
        self.dry_run_adding_to_lidarr = dry_run_adding_to_lidarr.lower() == "true" if dry_run_adding_to_lidarr != "" else ""
        self.app_name = os.environ.get("app_name", "")
        self.app_rev = os.environ.get("app_rev", "")
        self.app_url = os.environ.get("app_url", "")
        self.last_fm_api_key = os.environ.get("last_fm_api_key", "")
        self.last_fm_api_secret = os.environ.get("last_fm_api_secret", "")
        self.mode = os.environ.get("mode", "")

        # Load variables from the configuration file if not set by environmental variables.
        try:
            self.settings_config_file = os.path.join(self.config_folder, "settings_config.json")
            if os.path.exists(self.settings_config_file):
                self.lidagigs_logger.info(f"Loading Config via file")
                with open(self.settings_config_file, "r") as json_file:
                    ret = json.load(json_file)
                    for key in ret:
                        if getattr(self, key) == "":
                            setattr(self, key, ret[key])
        except Exception as e:
            self.lidagigs_logger.error(f"Error Loading Config: {str(e)}")

        # Load defaults if not set by an environmental variable or configuration file.
        for key, value in default_settings.items():
            if getattr(self, key) == "":
                setattr(self, key, value)

        # Save config.
        self.save_config_to_file()

    def connection(self):
        if self.gigs:
            if self.clients_connected_counter == 0:
                if len(self.gigs) > 15:
                    self.gigs = random.sample(self.gigs, 15)
                else:
                    self.lidagigs_logger.info(f"Shuffling Artists")
                    random.shuffle(self.gigs)
                self.raw_new_gigs = []
            socketio.emit("more_gigs_loaded", self.gigs)

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
            self.lidagigs_logger.error(f"Statup Error: {str(e)}")
            self.stop_event.set()
            ret = {"Status": "Error", "Code": str(e), "Data": self.lidarr_items, "Running": not self.stop_event.is_set()}
            socketio.emit("lidarr_sidebar_update", ret)

        else:
            self.find_gigs()

    def get_artists_from_lidarr(self):
        try:
            self.lidagigs_logger.info(f"Getting Artists from Lidarr")
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
            self.lidagigs_logger.error(f"Getting Artist Error: {str(e)}")
            ret = {"Status": "Error", "Code": 500, "Data": str(e), "Running": not self.stop_event.is_set()}

        finally:
            socketio.emit("lidarr_sidebar_update", ret)

    def find_gigs(self):
        if self.stop_event.is_set() or self.search_in_progress_flag:
            return
        elif self.mode == "Songkick" and self.new_found_gigs_counter > 0:
            try:
                self.lidagigs_logger.info(f"Searching for new gigs via {self.mode}")
                self.new_found_gigs_counter = 0
                self.search_in_progress_flag = True
                random_artists = random.sample(self.artists_to_use_in_search, min(5, len(self.artists_to_use_in_search)))

                for artist_name in random_artists:
                    if self.stop_event.is_set():
                        break

                    self.lidagigs_logger.info(f"Searching for new gigs of {artist_name}")
                    response = requests.get(f'https://www.songkick.com/search?query={artist_name}&type=')
                    time.sleep(2)

                    soup = BeautifulSoup(response.text, 'html.parser')
                    artist_url = soup.select_one('.artist .thumb.search-link')

                    if artist_url is None:
                        self.lidagigs_logger.info(f"  nothing for {artist_name}")
                        break

                    artist_url = f"https://www.songkick.com{artist_url['href']}/calendar"
                    self.lidagigs_logger.info(f"  fetching {artist_url}")
                    response = requests.get(artist_url)
                    time.sleep(2)

                    soup = BeautifulSoup(response.text, 'html.parser')
                    artist_img = soup.select_one('img.artist-profile-image.artist')
                    img_link = artist_img['src'] if artist_img else None
                    gigs = soup.select('ol.event-listings.tour-calendar-summary li.event-listing')
                    self.lidagigs_logger.info(f"  {len(gigs)} gigs found for {artist_name}")
                    for gig in gigs:
                        if self.stop_event.is_set():
                            break

                        evt_link = gig.select_one('a')
                        evt_link = f"https://www.songkick.com{evt_link['href']}" if evt_link else None

                        evt_date = gig.select_one('a time')
                        evt_date = evt_date['datetime'] if evt_date else None

                        venue = gig.select_one('.concert .secondary-detail')
                        venue = venue.get_text().strip() if venue else None

                        location = gig.select_one('.concert .primary-detail')
                        location = location.get_text().strip() if location else None

                        gig_data = {
                            "Name": artist_name,
                            "Img_Link": img_link,
                            "Evt_Link": evt_link,
                            "Evt_Date": evt_date,
                            "Venue": venue,
                            "Location": location,
                        }
                        self.raw_new_gigs.append(gig_data)
                        socketio.emit("more_gigs_loaded", [gig_data])
                        # self.new_found_gigs_counter += 1

                if self.new_found_gigs_counter == 0:
                    self.lidagigs_logger.info("Search Exhausted - Try selecting more artists from existing Lidarr library")
                    socketio.emit("new_toast_msg", {"title": "Search Exhausted", "message": "Try selecting more artists from existing Lidarr library"})
                else:
                    self.gigs.extend(self.raw_new_gigs)

            except Exception as e:
                self.lidagigs_logger.error(f"Songkick Error: {str(e)}")

            finally:
                self.search_in_progress_flag = False

        elif self.new_found_gigs_counter == 0:
            try:
                self.search_in_progress_flag = True
                self.lidagigs_logger.info("Search Exhausted - Try selecting more artists from existing Lidarr library")
                socketio.emit("new_toast_msg", {"title": "Search Exhausted", "message": "Try selecting more artists from existing Lidarr library"})
                time.sleep(2)

            except Exception as e:
                self.lidagigs_logger.error(f"Search Exhausted Error: {str(e)}")

            finally:
                self.search_in_progress_flag = False

    def add_artists(self, raw_artist_name):
        try:
            artist_name = urllib.parse.unquote(raw_artist_name)
            artist_folder = artist_name.replace("/", " ")
            musicbrainzngs.set_useragent(self.app_name, self.app_rev, self.app_url)
            mbid = self.get_mbid_from_musicbrainz(artist_name)
            if mbid:
                lidarr_url = f"{self.lidarr_address}/api/v1/artist"
                headers = {"X-Api-Key": self.lidarr_api_key}
                payload = {
                    "ArtistName": artist_name,
                    "qualityProfileId": self.quality_profile_id,
                    "metadataProfileId": self.metadata_profile_id,
                    "path": os.path.join(self.root_folder_path, artist_folder, ""),
                    "rootFolderPath": self.root_folder_path,
                    "foreignArtistId": mbid,
                    "monitored": True,
                    "addOptions": {"searchForMissingAlbums": self.search_for_missing_albums},
                }
                if self.dry_run_adding_to_lidarr:
                    response = requests.Response()
                    response.status_code = 201
                else:
                    response = requests.post(lidarr_url, headers=headers, json=payload)

                if response.status_code == 201:
                    self.lidagigs_logger.info(f"Artist '{artist_name}' added successfully to Lidarr.")
                    status = "Added"
                    self.lidarr_items.append({"name": artist_name, "checked": False})
                    self.cleaned_lidarr_items.append(unidecode(artist_name).lower())
                else:
                    self.lidagigs_logger.error(f"Failed to add artist '{artist_name}' to Lidarr.")
                    error_data = json.loads(response.content)
                    error_message = error_data[0].get("errorMessage", "No Error Message Returned") if error_data else "Error Unknown"
                    self.lidagigs_logger.error(error_message)
                    if "already been added" in error_message:
                        status = "Already in Lidarr"
                        self.lidagigs_logger.info(f"Artist '{artist_name}' is already in Lidarr.")
                    elif "configured for an existing artist" in error_message:
                        status = "Already in Lidarr"
                        self.lidagigs_logger.info(f"'{artist_folder}' folder already configured for an existing artist.")
                    elif "Invalid Path" in error_message:
                        status = "Invalid Path"
                        self.lidagigs_logger.info(f"Path: {os.path.join(self.root_folder_path, artist_folder, '')} not valid.")
                    else:
                        status = "Failed to Add"

            else:
                status = "Failed to Add"
                self.lidagigs_logger.info(f"No Matching Artist for: '{artist_name}' in MusicBrainz.")
                socketio.emit("new_toast_msg", {"title": "Failed to add Artist", "message": f"No Matching Artist for: '{artist_name}' in MusicBrainz."})

            for item in self.gigs:
                if item["Name"] == artist_name:
                    item["Status"] = status
                    socketio.emit("refresh_artist", item)
                    break

        except Exception as e:
            self.lidagigs_logger.error(f"Adding Artist Error: {str(e)}")

    def get_mbid_from_musicbrainz(self, artist_name):
        result = musicbrainzngs.search_artists(artist=artist_name)
        mbid = None

        if "artist-list" in result:
            artists = result["artist-list"]

            for artist in artists:
                match_ratio = fuzz.ratio(artist_name.lower(), artist["name"].lower())
                decoded_match_ratio = fuzz.ratio(unidecode(artist_name.lower()), unidecode(artist["name"].lower()))
                if match_ratio > 90 or decoded_match_ratio > 90:
                    mbid = artist["id"]
                    self.lidagigs_logger.info(f"Artist '{artist_name}' matched '{artist['name']}' with MBID: {mbid}  Match Ratio: {max(match_ratio, decoded_match_ratio)}")
                    break
            else:
                if self.fallback_to_top_result and artists:
                    mbid = artists[0]["id"]
                    self.lidagigs_logger.info(f"Artist '{artist_name}' matched '{artists[0]['name']}' with MBID: {mbid}  Match Ratio: {max(match_ratio, decoded_match_ratio)}")

        return mbid

    def load_settings(self):
        try:
            data = {
                "lidarr_address": self.lidarr_address,
                "lidarr_api_key": self.lidarr_api_key,
                "root_folder_path": self.root_folder_path,
                "spotify_client_id": self.spotify_client_id,
                "spotify_client_secret": self.spotify_client_secret,
            }
            socketio.emit("settingsLoaded", data)
        except Exception as e:
            self.lidagigs_logger.error(f"Failed to load settings: {str(e)}")

    def update_settings(self, data):
        try:
            self.lidarr_address = data["lidarr_address"]
            self.lidarr_api_key = data["lidarr_api_key"]
            self.root_folder_path = data["root_folder_path"]
            self.spotify_client_id = data["spotify_client_id"]
            self.spotify_client_secret = data["spotify_client_secret"]
        except Exception as e:
            self.lidagigs_logger.error(f"Failed to update settings: {str(e)}")

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
                        "root_folder_path": self.root_folder_path,
                        "spotify_client_id": self.spotify_client_id,
                        "spotify_client_secret": self.spotify_client_secret,
                        "fallback_to_top_result": self.fallback_to_top_result,
                        "lidarr_api_timeout": float(self.lidarr_api_timeout),
                        "quality_profile_id": self.quality_profile_id,
                        "metadata_profile_id": self.metadata_profile_id,
                        "search_for_missing_albums": self.search_for_missing_albums,
                        "dry_run_adding_to_lidarr": self.dry_run_adding_to_lidarr,
                        "app_name": self.app_name,
                        "app_rev": self.app_rev,
                        "app_url": self.app_url,
                        "last_fm_api_key": self.last_fm_api_key,
                        "last_fm_api_secret": self.last_fm_api_secret,
                        "mode": self.mode,
                    },
                    json_file,
                    indent=4,
                )

        except Exception as e:
            self.lidagigs_logger.error(f"Error Saving Config: {str(e)}")

    def preview(self, raw_artist_name):
        artist_name = urllib.parse.unquote(raw_artist_name)
        if self.mode == "Spotify":
            try:
                preview_info = None
                sp = spotipy.Spotify(retries=0, auth_manager=SpotifyClientCredentials(client_id=self.spotify_client_id, client_secret=self.spotify_client_secret))
                results = sp.search(q=artist_name, type="artist")
                items = results.get("artists", {}).get("items", [])
                cleaned_artist_name = unidecode(artist_name).lower()
                for item in items:
                    match_ratio = fuzz.ratio(cleaned_artist_name, item.get("name", "").lower())
                    decoded_match_ratio = fuzz.ratio(unidecode(cleaned_artist_name), unidecode(item.get("name", "").lower()))
                    if match_ratio > 90 or decoded_match_ratio > 90:
                        artist_id = item.get("id", "")
                        top_tracks = sp.artist_top_tracks(artist_id)
                        random.shuffle(top_tracks["tracks"])
                        for track in top_tracks["tracks"]:
                            if track.get("preview_url"):
                                preview_info = {"artist": track["artists"][0]["name"], "song": track["name"], "preview_url": track["preview_url"]}
                                break
                        else:
                            preview_info = f"No preview tracks available for artist: {artist_name}"
                            self.lidagigs_logger.error(preview_info)
                        break
                else:
                    preview_info = f"No Artist match for: {artist_name}"
                    self.lidagigs_logger.error(preview_info)

            except Exception as e:
                preview_info = f"Error retrieving artist previews: {str(e)}"
                self.lidagigs_logger.error(preview_info)

            finally:
                socketio.emit("spotify_preview", preview_info, room=request.sid)

        elif self.mode == "LastFM":
            try:
                preview_info = {}
                biography = None
                lfm = pylast.LastFMNetwork(api_key=self.last_fm_api_key, api_secret=self.last_fm_api_secret)
                search_results = lfm.search_for_artist(artist_name)
                artists = search_results.get_next_page()
                cleaned_artist_name = unidecode(artist_name).lower()
                for artist_obj in artists:
                    match_ratio = fuzz.ratio(cleaned_artist_name, artist_obj.name.lower())
                    decoded_match_ratio = fuzz.ratio(unidecode(cleaned_artist_name), unidecode(artist_obj.name.lower()))
                    if match_ratio > 90 or decoded_match_ratio > 90:
                        biography = artist_obj.get_bio_content()
                        preview_info["artist_name"] = artist_obj.name
                        preview_info["biography"] = biography
                        break
                else:
                    preview_info = f"No Artist match for: {artist_name}"
                    self.lidagigs_logger.error(preview_info)

                if biography is None:
                    preview_info = f"No Biography available for: {artist_name}"
                    self.lidagigs_logger.error(preview_info)

            except Exception as e:
                preview_info = {"error": f"Error retrieving artist bio: {str(e)}"}
                self.lidagigs_logger.error(preview_info)

            finally:
                socketio.emit("lastfm_preview", preview_info, room=request.sid)


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)
data_handler = DataHandler()


@app.route("/")
def home():
    return render_template("base.html")


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


@socketio.on("adder")
def add_artists(data):
    thread = threading.Thread(target=data_handler.add_artists, args=(data,), name="Add_Artists_Thread")
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


@socketio.on("load_more_artists")
def load_more_artists():
    thread = threading.Thread(target=data_handler.find_gigs, name="FindSimilar")
    thread.daemon = True
    thread.start()


@socketio.on("preview_req")
def preview(artist):
    data_handler.preview(artist)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
