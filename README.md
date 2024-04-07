![Build Status](https://github.com/TheWicklowWolf/Lidagigs/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/lidagigs.svg)


Web GUI for finding gigs of Lidarr artists.
Can also provide a ICS calendar with found events.

Most of the code is from [thewicklowwolf](https://github.com/TheWicklowWolf/Lidify)


## Run using docker-compose

```yaml
version: "2.1"
services:
  lidagigs:
    image: ghcr.io/vincent/lidagigs:latest
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
* __fallback_to_top_result__: Whether to use the top result if no match is found. Defaults to `False`.
* __lidarr_api_timeout__: Timeout duration for Lidarr API calls. Defaults to `120`.
* __app_name__: Name of the application. Defaults to `Lidagigs`.
* __app_rev__: Application revision. Defaults to `0.01`.
* __app_url__: URL of the application. Defaults to `Random URL`.
* __mode__: Mode for discovery (Songkick only). Defaults to `Songkick`.

