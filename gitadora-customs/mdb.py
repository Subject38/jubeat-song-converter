import csv
import os
from lxml import objectify

def get_song_info_from_mdb(input_filename, music_id):
    if not os.path.exists(input_filename):
        return None

    try:
        with open(input_filename, "r", encoding="utf-8") as f:
            root = objectify.fromstring(f.read())
    except ValueError:
        with open(input_filename, "rb") as f:
            root = objectify.fromstring(f.read())
    except:
        return None

    for data in root.mdb_data:
        if int(data.music_id) == music_id:
            song_info = {
                'music_id': music_id
            }

            if hasattr(data, 'title_name'):
                song_info['title'] = data.title_name.text or ""

            if hasattr(data, 'artist_title'):
                song_info['artist'] = data.artist_title.text or ""
            elif hasattr(data, 'artist_title_ascii'):
                song_info['artist'] = data.artist_title_ascii.text or ""

            if hasattr(data, 'xg_diff_list'):
                # The original ordering is guitar, drum, bass, but I want them to be in drum, guitar, bass order
                difficulties = data.xg_diff_list.text.split(' ')
                difficulties = difficulties[5:10] + difficulties[0:5] + difficulties[10:]
                song_info['difficulty'] = [int(x) for x in difficulties]

            if hasattr(data, 'classics_diff_list'):
                # The original ordering is guitar, bass, open, drum but I want them to be in drum, guitar, bass, open order
                difficulties = data.classics_diff_list.text.split(' ')
                difficulties = difficulties[-4:] + difficulties[:-4]
                song_info['classics_difficulty'] = [int(x) for x in difficulties]

            if hasattr(data, 'bpm'):
                song_info['bpm'] = int(data.bpm.text)

            if hasattr(data, 'bpm2'):
                song_info['bpm2'] = int(data.bpm2.text)

            return song_info

    return None

def get_song_info_from_csv(input_filename, music_id):
    if not os.path.exists(input_filename):
        return None

    #csv_file = open(input_filename, 'r', encoding="utf-8")
    reader = csv.DictReader(open(input_filename, 'r', encoding="shift-jis"))

    song_info_ver = 0
    song_info = None
    for data in reader:
        if int(data['music_id']) == music_id:
            if int(data['game_version']) >= song_info_ver and int(data['game_version']) < 1000:
                song_info_ver = int(data['game_version'])

                song_info = {
                    'music_id': music_id
                }

                song_info['title'] = data['title_name']
                song_info['artist'] = data['artist_title']
                song_info['difficulty'] = [data[k] for k in ["diff_dm_easy","diff_dm_bsc","diff_dm_adv","diff_dm_ext","diff_dm_mst","diff_gf_easy","diff_gf_bsc","diff_gf_adv","diff_gf_ext","diff_gf_mst","diff_gf_b_easy","diff_gf_b_bsc","diff_gf_b_adv","diff_gf_b_ext","diff_gf_b_mst"]]

                #Also add bpm and bpm2
                song_info['bpm'] = data['bpm']
                song_info['bpm2'] = data['bpm2']

                #Add movie filename
                song_info['movie_filename'] = data['movie_filename']
    return song_info
