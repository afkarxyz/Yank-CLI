import os
import time
import requests
import re
from dataclasses import dataclass


BLUE = "\033[38;2;34;136;255m"
RESET = "\033[0m"

TITLE = f"""{BLUE}                   _     
                  | |    
 _   _ _____ ____ | |  _ 
| | | (____ |  _ \| |_/ )
| |_| / ___ | | | |  _ ( 
 \__  \_____|_| |_|_| \_)
(____/                   
                                 
Spotify Track Downloader{RESET}
"""
print(TITLE)
print("Welcome to yank-cli - Your Spotify Track Saver!")
print("=" * 47)
print()

API_REQUEST_HEADERS = {
    'Host': 'api.spotifydown.com',
    'Referer': 'https://spotifydown.com/',
    'Origin': 'https://spotifydown.com',
}

FILENAME_SANITIZATION_PATTERN = re.compile(r'[<>:\"\/\\|?*\|\']')

@dataclass(init=True, eq=True, frozen=True)
class TrackMetadata:
    title: str
    artists: str
    album: str
    tid: str

def normalize_filename(name):
    name = re.sub(FILENAME_SANITIZATION_PATTERN, '', name)
    name = ' '.join(name.split())
    return name.strip()

def fetch_track_metadata(link, max_retries=3):
    track_id = link.split("/")[-1].split("?")[0]
    for attempt in range(max_retries):
        try:
            response = requests.get(f"https://api.spotifydown.com/download/{track_id}", headers=API_REQUEST_HEADERS)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f"Error fetching track metadata. Retrying... (Attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                print(f"Failed to fetch track metadata after {max_retries} attempts.")
                return None

def fetch_album_metadata(link, max_retries=3):
    album_id = link.split("/")[-1].split("?")[0]
    for attempt in range(max_retries):
        try:
            response = requests.get(f"https://api.spotifydown.com/metadata/album/{album_id}", headers=API_REQUEST_HEADERS)
            response.raise_for_status()
            album_data = response.json()
            album_name = album_data['title']
            
            print(f"Album: {album_name} by {album_data['artists']}")
            print("Getting songs from album...")
            
            response = requests.get(f"https://api.spotifydown.com/tracklist/album/{album_id}", headers=API_REQUEST_HEADERS)
            response.raise_for_status()
            track_list = response.json()['trackList']

            return [TrackMetadata(
                title=normalize_filename(track['title']),
                artists=normalize_filename(track['artists']),
                album=album_name,
                tid=track['id']
            ) for track in track_list], album_name
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f"Error fetching album metadata. Retrying... (Attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                print(f"Failed to fetch album metadata after {max_retries} attempts.")
                return None, None

def fetch_playlist_metadata(link, max_retries=3):
    playlist_id = link.split("/")[-1].split("?")[0]
    for attempt in range(max_retries):
        try:
            response = requests.get(f"https://api.spotifydown.com/metadata/playlist/{playlist_id}", headers=API_REQUEST_HEADERS)
            response.raise_for_status()
            playlist_data = response.json()
            playlist_name = playlist_data['title']
            
            print(f"Playlist: {playlist_name} by {playlist_data['artists']}")
            print("Getting songs from playlist...")
            
            track_list = []
            next_offset = 0
            while True:
                response = requests.get(f"https://api.spotifydown.com/tracklist/playlist/{playlist_id}?offset={next_offset}", headers=API_REQUEST_HEADERS)
                response.raise_for_status()
                data = response.json()
                track_list.extend(data['trackList'])
                next_offset = data['nextOffset']
                if not next_offset:
                    break

            return [TrackMetadata(
                title=normalize_filename(track['title']),
                artists=normalize_filename(track['artists']),
                album=track.get('album', 'Unknown Album'),
                tid=track['id']
            ) for track in track_list], playlist_name
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f"Error fetching playlist metadata. Retrying... (Attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                print(f"Failed to fetch playlist metadata after {max_retries} attempts.")
                return None, None

def download_track(track, outpath, max_retries=3):
    trackname = f"{track.title} - {track.artists}"
    print(f"Downloading: {trackname}", end="", flush=True)
    
    for attempt in range(max_retries):
        try:
            if persist_audio_file(trackname, track.tid, outpath):
                print(" Downloaded")
                return True
            else:
                print(" Skipped (already exists)")
                return True
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f" Error downloading. Retrying... (Attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                print(f" Failed to download after {max_retries} attempts.")
                return False

def persist_audio_file(trackname, tid, outpath):
    trackname = normalize_filename(trackname)
    if os.path.exists(os.path.join(outpath, f"{trackname}.mp3")):
        return False
    
    audio_response = requests.get(f"https://yank.g3v.co.uk/track/{tid}")
    audio_response.raise_for_status()
    
    if audio_response.status_code == 200:
        with open(os.path.join(outpath, f"{trackname}.mp3"), "wb") as file:
            file.write(audio_response.content)
        return True
    return False

def main():
    outpath = os.getcwd()
    
    url = input("Enter Spotify track, album, or playlist URL: ")
    
    if "album" in url:
        songs, album_name = fetch_album_metadata(url)
        if songs is None:
            print("Failed to fetch album. Exiting.")
            return
        print("\nTracks in album:")
        for i, song in enumerate(songs, 1):
            print(f"{i}. {song.title} - {song.artists}")
        
        selection = input("\nEnter track numbers to download (space-separated) or press Enter to download all: ")
        if selection.strip():
            indices = [int(x) - 1 for x in selection.split()]
            selected_songs = [songs[i] for i in indices if 0 <= i < len(songs)]
        else:
            selected_songs = songs
        
        album_folder = normalize_filename(album_name)
        outpath = os.path.join(outpath, album_folder)
        os.makedirs(outpath, exist_ok=True)
        
        for song in selected_songs:
            download_track(song, outpath)
    elif "playlist" in url:
        songs, playlist_name = fetch_playlist_metadata(url)
        if songs is None:
            print("Failed to fetch playlist. Exiting.")
            return
        print("\nTracks in playlist:")
        for i, song in enumerate(songs, 1):
            print(f"{i}. {song.title} - {song.artists}")
        
        selection = input("\nEnter track numbers to download (space-separated) or press Enter to download all: ")
        if selection.strip():
            indices = [int(x) - 1 for x in selection.split()]
            selected_songs = [songs[i] for i in indices if 0 <= i < len(songs)]
        else:
            selected_songs = songs
        
        playlist_folder = normalize_filename(playlist_name)
        outpath = os.path.join(outpath, playlist_folder)
        os.makedirs(outpath, exist_ok=True)
        
        for song in selected_songs:
            download_track(song, outpath)
    else:  # Single track
        resp = fetch_track_metadata(url)
        if resp is None or resp.get('success') == False:
            print(f"Error: Unable to fetch track metadata.")
            return
        track = TrackMetadata(
            title=normalize_filename(resp['metadata']['title']),
            artists=normalize_filename(resp['metadata']['artists']),
            album=resp['metadata'].get('album', 'Unknown Album'),
            tid=resp['metadata']['id']
        )
        download_track(track, outpath)
    
    print(f"\n{BLUE}Download completed!{RESET}")
    print("Thank you for using yank-cli!")
    print("=" * 29)

if __name__ == "__main__":
    main()
