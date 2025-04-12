#Import Modules
import requests
import base64 as b64
import pandas as pd
import json
import time

class SpotifyAPIClient:
    def __init__(self, client_id, client_secret, redirect_uri, scopes, refresh_token = None):
        #Define Class Properties
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        if refresh_token == None:
            self.refresh_token = self.get_refresh_token()
        else:
            self.refresh_token = refresh_token
        self.access_token, self.expiration_time = self.get_access_token()
        self.user_id = self.get_user_id()
    
    def get_refresh_token(self):
        """
        Generate a Refresh Token for the Spotify API
        """
        #Generate authorization code
        auth_code_url = fr'https://accounts.spotify.com/authorize?client_id={self.client_id}&response_type=code&redirect_uri={self.redirect_uri}&scope={self.scopes}'
        print(auth_code_url)
        code = input('Enter authorization code: ')

        #Define POST request details
        url = r'https://accounts.spotify.com/api/token?'
        headers = {
            'Authorization' : 'Basic ' + b64.b64encode((self.client_id + ':' + self.client_secret).encode()).decode()
            ,'Content-Type' : r'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type'    : 'authorization_code'
            ,'code'         : code
            ,'redirect_uri' : self.redirect_uri
        }

        #Generate Refresh Token
        response = requests.post(url, headers = headers, data = data)

        return response.json()['refresh_token']

    def get_access_token(self):
        """
        Generate an Access Token for the Spotify API
        """
        #Define POST request details
        url = r'https://accounts.spotify.com/api/token?'
        headers = {
            'Authorization' : 'Basic ' + b64.b64encode((self.client_id + ':' + self.client_secret).encode()).decode()
            ,'Content-Type' : r'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type'    : 'refresh_token'
            ,'refresh_token': self.refresh_token
            ,'client_id'    : self.client_id
        }

        #Generate access token
        response = requests.post(url, headers = headers, data = data)

        #Assign Access Token & expiration time to API Client properties
        return (response.json()['access_token'], time.time() + 3600)

    def check_access_token(func):
        """
        Decorator function that refreshed access token if it is close to expiration
        """
        def wrapper(self, *args, **kwargs):
            #Generate new access token if current access token is close to expiration
            if self.expiration_time - time.time() <= 600:
                self.get_access_token()
            return func(self, *args, **kwargs)
        return wrapper

    @check_access_token
    def get_user_id(self):
        """
        Retrieve the Spotify User ID of the current user
        """
        #Define GET request details
        url = 'https://api.spotify.com/v1/me'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }

        #Send GET request to retrieve user ID
        response = requests.get(url, headers = headers)

        return response.json()['id']
    
    @check_access_token
    def get_followed_artists(self):
        """
        Generate a Pandas DataFrame of all the artists that the current user follows
        """
        #Generate new access token if current access token is close to expiration
        if self.expiration_time - time.time() <= 600:
            self.get_access_token()

        #Define GET request details
        url = 'https://api.spotify.com/v1/me/following'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        params = {
            'type'      : 'artist'
            ,'limit'    : 50
            ,'locale'   : 'en-US'
        }

        #Generate full list of followed artists
        artists = []
        while True:
            response = requests.get(url, headers = headers, params = params)
            data = [
                {
                    'artist'    : artist['name']
                    ,'artist_id': artist['id']
                    ,'genres'   : ' | '.join(artist['genres'])
                } 
                for artist in response.json()['artists']['items']
            ]
            artists += data
            if len(artists) == response.json()['artists']['total']:
                break
            else:
                params['after'] = data[-1]['artist_id']
                
        return pd.DataFrame(artists)

    @check_access_token
    def follow_artist(self, artist_id:str):
        """
        Add the current user as a follower for the specified artist

        Parameters
        ----------
        artist_id : The Spotify ID of the artist
        """
        #Define PUT request details
        url = 'https://api.spotify.com/v1/me/following'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        params = {
            'type': 'artist'
            ,'ids': artist_id
        }

        #Send PUT request to follow artist
        response = requests.put(url, headers = headers, params = params)

        if response.status_code == 204:
            print(f'Successfully followed {artist_id}')
        else:
            print(f'Failed to follow {artist_id}')
            print(f'ERROR: {response.json()['error']['message']}')

    @check_access_token
    def get_current_user_playlists(self):
        """
        Generate a Pandas DataFrame of all the playlists that the current user owns
        """
        #Define GET request details
        url = 'https://api.spotify.com/v1/me/playlists'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        params = {
            'limit'   : 50
            ,'offset' : 0
        }

        #Generate full list of playlists from current user
        playlists = []
        while True:
            response = requests.get(url, headers = headers, params = params)
            data = [
                {
                    'playlist_id'    : playlist['id']
                    ,'playlist_name' : playlist['name']
                } 
                for playlist in response.json()['items']
            ]
            playlists += data
            if len(playlists) == response.json()['total']:
                break
            else:
                params['offset'] += 50

        return pd.DataFrame(playlists)

    @check_access_token
    def create_playlist(self, playlist_name:str, playlist_description = ''):
        """
        Create a new playlist for the current user

        Parameters
        ----------
        playlist_name : The name for the new playlist
        playlist_description: Value for playlist description as displayed in Spotify Clients and in the Web API
        """
        #Check if playlists exists
        user_playlists = self.get_current_user_playlists()
        if playlist_name in user_playlists['playlist_name'].values:
            print(f'Playlist {playlist_name} already exists.')
            return None

        #Define POST request details
        url = f'https://api.spotify.com/v1/users/{self.user_id}/playlists'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
            ,'Content-Type': 'application/json'
        }
        data = {
            'name'          : playlist_name
            ,'public'       : False
            ,'collaborative': False
            ,'description'  : playlist_description
        }

        #Send PUT reqest to create new playlist
        response = requests.post(url, headers = headers, json = data)

        if response.status_code == 201:
            print(f'Successfully created playlist {playlist_name}.')
        else:
            print(f'Failed to create playlist {playlist_name}.')

    @check_access_token
    def get_playlist_items(self, playlist_id:str):
        """
        Generate a Pandas DataFrame of all the tracks in the specified Spotify playlist

        Parameters
        ----------
        playist_id : The Spotify ID of the playlist
        """
        #Define GET request details
        url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        params = {
            'market'  : 'US'
            ,'limit'  : 50
            ,'offset' : 0
        }

        #Generate full list of tracks in playlist
        tracks = []
        while True:
            response = requests.get(url, headers = headers, params = params)
            data = [
                {
                    'playlist_id'   : playlist_id
                    ,'track_id'     : track['track']['id']
                    ,'track_name'   : track['track']['name']
                    ,'track_uri'    : track['track']['uri']
                    ,'artist_ids'   : '|'.join([artist['id'] for artist in track['track']['artists']])
                    ,'artist_names' : '|'.join([artist['name'] for artist in track['track']['artists']])
                    ,'album_name'   : track['track']['album']['name']
                    ,'album_uri'    : track['track']['album']['uri']
                    ,'added_at'     : track['added_at']
                } 
                for track in response.json()['items']
            ]
            tracks += data
            if len(tracks) == response.json()['total']:
                break
            else:
                params['offset'] += 50

        return pd.DataFrame(tracks)

    @check_access_token
    def add_items_to_playlist(self, playlist_id:str, track_uris:list):
        """
        Adds track(s) to the specified Spotify playlist

        Parameters
        ----------
        playist_id : The Spotify ID of the playlist
        track_uris : A comma-seperated list of Spotify URIs to add to the playlist
        """
        #Define PUT request details
        url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
            ,'Content-Type': 'application/json'
        }
        body = {
            'uris': track_uris
        }

        #Send PUT reqest to create new playlist
        response = requests.post(url, headers = headers, data = json.dumps(body))

        if response.status_code == 201:
            print(f'Successfully added all tracks to playlist {playlist_id}.')
        else:
            print(f'Failed to add all tracks to playlist {playlist_id}.')
    
    @check_access_token
    def get_artists_albums(self, artist_id:str):
        """
        Generate a Pandas DataFrame of all the albums affiliated with the specified artist

        Parameters
        ----------
        artist_id : The Spotify ID of the artist
        """        
        #Define GET request details
        url = f'https://api.spotify.com/v1/artists/{artist_id}/albums'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        params = {
            'include_groups': 'album,single,appears_on,compilation'
            ,'market'       : 'US'
            ,'locale'       : 'en-US'
            ,'limit'        : 50
            ,'offset'       : 0
        }

        #Generate full list of albums associated with artist
        albums = []
        while True:
            response = requests.get(url, headers = headers, params = params)
            data = [
                {
                    'artist_id'             : artist_id
                    ,'album_name'           : album['name']
                    ,'album_id'             : album['id']
                    ,'album_group'          : album['album_group']
                    ,'album_release_date'   : album['release_date']
                    ,'album_is_playable'    : album['is_playable']
                } 
                for album in response.json()['items']
            ]
            albums += data
            if len(albums) == response.json()['total']:
                break
            else:
                params['offset'] += 50

        return pd.DataFrame(albums)
    
    @check_access_token
    def get_albums_tracks(self, album_id:str):
        """
        Generate a list of dictionaries for all the tracks in the specified album

        Parameters
        ----------
        album_id : The Spotify ID of the album
        """  
        #Define request details
        url = f'https://api.spotify.com/v1/albums/{album_id}/tracks'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        params = {
            'market'    : 'US'
            ,'limit'    : 50
            ,'offset'   : 0
        }

        #Generate full list of tracks associated with albums
        tracks = []
        while True:
            response = requests.get(url, headers = headers, params = params)
            data = [
                {
                    'album_id'            : album_id
                    ,'track_name'         : track['name']
                    ,'track_id'           : track['id']
                    ,'track_uri'          : track['uri']
                    ,'track_artist_ids'   : '|'.join([artist['id'] for artist in track['artists']])
                    ,'track_artist_names' : '|'.join([artist['name'] for artist in track['artists']])
                    ,'disc_number'        : track['disc_number']
                    ,'track_number'       : track['track_number']
                    ,'track_is_playable'  : track['is_playable']
                    ,'track_length'       : round(track['duration_ms']/1000)
                } 
                for track in response.json()['items']
            ]
            tracks += data
            if len(tracks) == response.json()['total']:
                break
            else:
                params['offset'] += 50

        return tracks
    
    @check_access_token
    def get_several_albums_tracks(self,album_ids:list):
        """
        Generate a Pandas DataFrame of all the tracks in the specified album(s)

        Parameters
        ----------
        album_ids : A list of album Spotify IDs
        """  
        #Define GET request details
        url = 'https://api.spotify.com/v1/albums'
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        params = {
            'ids'       : album_ids
            ,'market'   : 'US'
        }

        #Generate full list of tracks associated with albums
        response = requests.get(url, headers = headers, params = params)
        album_list = [album for album in response.json()['albums']]

        tracks = []
        for album in album_list:
            if album['total_tracks'] >= album['tracks']['limit']:   #Get all tracks from album that exceeds limit
                tracks += self.get_albums_tracks(album['id'])
            else:
                album_id = album['id']
                tracks += [
                    {
                        'album_id'            : album_id
                        ,'track_name'         : track['name']
                        ,'track_id'           : track['id']
                        ,'track_uri'          : track['uri']
                        ,'track_artist_ids'   : '|'.join([artist['id'] for artist in track['artists']])
                        ,'track_artist_names' : '|'.join([artist['name'] for artist in track['artists']])
                        ,'disc_number'        : track['disc_number']
                        ,'track_number'       : track['track_number']
                        ,'track_is_playable'  : track['is_playable']
                        ,'track_length'       : round(track['duration_ms']/1000)
                    } 
                    for track in album['tracks']['items']
                ]

        return pd.DataFrame(tracks)
    
    @check_access_token
    def review_artist_discography(self, artist_id:str, reviewed_playlist_filepath:str):
        """
        Add the entirety of an artist's discography to the Pending Reviewed playlist, including only
        the most recent version of each track

        Parameters
        ----------
        artist_id : The Spotify ID of the artist
        reviewed_playlist_filepath: Filepath of CSV containing tracks to exclude from review
        """
        #Get playlist details
        playlists = self.get_current_user_playlists()
        pending_review_playlist_id = playlists.loc[playlists['playlist_name'] == 'Pending Review', 'playlist_id'].values[0]
        reviewed_playlist_tracks = pd.read_csv(reviewed_playlist_filepath)

        #Get all albums associated with artist
        albums = self.get_artists_albums(artist_id)
        album_count = albums.shape[0]
        print(f'{album_count} albums identified from {artist_id}.')

        #Remove reviewed albums
        albums = albums.loc[~albums['album_id'].isin(reviewed_playlist_tracks['album_id'])]

        #Get all tracks associated with artist
        tracks = []
        for i in range((album_count // 20) + 1):
            album_ids = ','.join(albums['album_id'].values[20 * i:20 * (i + 1)])
            tracks.append(self.get_several_albums_tracks(album_ids))
        tracks = pd.concat(tracks)

        #Remove irrelevant tracks
        tracks = tracks.loc[tracks['track_artist_ids'].apply(lambda x: artist_id in x)]     #Do not feature artist
        tracks = tracks.loc[~tracks['track_id'].isin(reviewed_playlist_tracks['track_id'])] #Already reviewed

        #Dedup for latest version of track
        pending_review_tracks = tracks.loc[~tracks.duplicated(subset = ['track_name','track_artist_ids','track_length'])]
        
        #Confirm playlist upload
        print(f'{pending_review_tracks.shape[0]} tracks to be added to Pending Review Playlist')
        if input('Enter Y to continue: ') != 'Y':
            return

        #Upload tracks to Pending Reviewed Playlist
        track_count = pending_review_tracks.shape[0]
        total_uploads = 0
        for i in range((track_count // 100) + 1):
            track_uris = pending_review_tracks['track_uri'].values[100 * i:100 * (i + 1)].tolist()
            self.add_items_to_playlist(pending_review_playlist_id, track_uris)
            total_uploads += len(track_uris)
            print(f'{total_uploads} tracks successfully loaded to Playlist {pending_review_playlist_id}')

        #Update reviewed playlist CSV
        updated_reviewed_playlist_tracks = pd.concat([reviewed_playlist_tracks,tracks[['track_id','album_id']]]).drop_duplicates(ignore_index = True)
        updated_reviewed_playlist_tracks.to_csv(reviewed_playlist_filepath, index = False)
        print('Reviewed PLaylist CSV updated.')

        #Follow Artist
        self.follow_artist(artist_id)

        print('Completed')