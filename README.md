![Build Status](https://github.com/TheWicklowWolf/Lidagigs/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/lidagigs.svg)


Web GUI for finding gigs of selected Lidarr artists.

Most of the code is from [thewicklowwolf](https://github.com/TheWicklowWolf/Lidify)


## Run using docker-compose

```yaml
version: "2.1"
services:
  lidagigs:
    image: allyouneedisgnu/lidagigs:latest
    container_name: lidagigs
    volumes:
      - /path/to/config:/lidagigs/config
      - /etc/localtime:/etc/localtime:ro
    ports:
      - 5000:5000
    restart: unless-stopped
```

## Configuration via environment variables

Certain values can be set via environment variables:

* __lidarr_address__: The URL for Lidarr. Defaults to `http://192.168.1.2:8686`.
* __lidarr_api_key__: The API key for Lidarr. Defaults to ``.
* __root_folder_path__: The root folder path for music. Defaults to `/data/media/music/`.
* __fallback_to_top_result__: Whether to use the top result if no match is found. Defaults to `False`.
* __lidarr_api_timeout__: Timeout duration for Lidarr API calls. Defaults to `120`.
* __quality_profile_id__: Quality profile ID in Lidarr. Defaults to `1`.
* __metadata_profile_id__: Metadata profile ID in Lidarr. Defaults to `1`
* __search_for_missing_albums__: Whether to start searching for albums when adding artists. Defaults to `False`
* __dry_run_adding_to_lidarr__: Whether to run without adding artists in Lidarr. Defaults to `False`
* __app_name__: Name of the application. Defaults to `Lidagigs`.
* __app_rev__: Application revision. Defaults to `0.01`.
* __app_url__: URL of the application. Defaults to `Random URL`.
* __last_fm_api_key__: The API key for LastFM. Defaults to ``.
* __last_fm_api_secret__: The API secret for LastFM. Defaults to ``.
* __mode__: Mode for discovery (Spotify or LastFM). Defaults to `Spotify`.

---

https://hub.docker.com/r/allyouneedisgnu/lidagigs
