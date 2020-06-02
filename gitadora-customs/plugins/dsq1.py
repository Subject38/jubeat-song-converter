import collections
import copy
import json
import os
import shutil
import struct
import threading
from lxml import etree
from lxml.builder import E
import uuid

import helper
import mdb
import eamxml
import audio
import vas3tool
import wavbintool
import tmpfile

import plugins.wav as wav

USE_THREADS = True

EVENT_ID_MAP = {
    0x00: "note",
    0x01: "note",
    0x02: "note",
    0x03: "note",
    0x04: "note",
    0x05: "note",
    0x06: "note",
    0x07: "measure",
    0x08: "beat",
    0x09: "endpos",
    0x0a: "endpos",
}

EVENT_ID_REVERSE = {EVENT_ID_MAP[k]: k for k in EVENT_ID_MAP}

NOTE_MAPPING = {
    'drum': {
        0x00: "hihat",
        0x01: "snare",
        0x02: "bass",
        0x03: "hightom",
        0x04: "lowtom",
        0x05: "rightcymbal",
        0x06: "auto",
    },
}

REVERSE_NOTE_MAPPING = {
    # Drum
    "hihat": 0x00,
    "snare": 0x01,
    "bass": 0x02,
    "hightom": 0x03,
    "lowtom": 0x04,
    "rightcymbal": 0x05,
    "auto": 0x06,
}


def add_song_info(charts, music_id, music_db):
    song_info = None

    if music_db and music_db.endswith(".csv") or not music_db:
        song_info = mdb.get_song_info_from_csv(music_db if music_db else "gitadora_music.csv", music_id)

    if song_info is None or music_db and music_db.endswith(".xml") or not music_db:
        song_info = mdb.get_song_info_from_mdb(music_db if music_db else "mdb_xg.xml", music_id)

    for chart_idx in range(len(charts)):
        chart = charts[chart_idx]

        if not song_info:
            continue

        game_type = ["drum", "guitar", "bass", "open"][chart['header']['game_type']]

        if 'title' in song_info:
            charts[chart_idx]['header']['title'] = song_info['title']

        if 'artist' in song_info:
            charts[chart_idx]['header']['artist'] = song_info['artist']

        if 'classics_difficulty' in song_info:
            diff_idx = (chart['header']['game_type'] * 4) + chart['header']['difficulty']

            if diff_idx < len(song_info['classics_difficulty']):
                difficulty = song_info['classics_difficulty'][diff_idx]
            else:
                difficulty = 0

            charts[chart_idx]['header']['level'] = {
                game_type: difficulty * 10
            }

        if 'bpm' in song_info:
            charts[chart_idx]['header']['bpm'] = song_info['bpm']

        if 'bpm2' in song_info:
            charts[chart_idx]['header']['bpm2'] = song_info['bpm2']

    return charts


def filter_charts(charts, params):
    filtered_charts = []

    for chart in charts:
        if chart['header']['is_metadata'] != 0:
            continue

        part = ["drum", "guitar", "bass", "open"][chart['header']['game_type']]
        has_all = 'all' in params['parts']
        has_part = part in params['parts']
        if not has_all and not has_part:
            filtered_charts.append(chart)
            continue

        diff = ['nov', 'bsc', 'adv', 'ext', 'mst'][chart['header']['difficulty']]
        has_min = 'min' in params['difficulty']
        has_max = 'max' in params['difficulty']
        has_all = 'all' in params['difficulty']
        has_diff = diff in params['difficulty']

        if not has_min and not has_max and not has_all and not has_diff:
            filtered_charts.append(chart)
            continue

    for chart in filtered_charts:
        charts.remove(chart)

    return charts


def split_charts_by_parts(charts):
    guitar_charts = []
    bass_charts = []
    open_charts = []

    for chart in charts:
        if chart['header']['is_metadata'] != 0:
            continue

        game_type = ["drum", "guitar", "bass", "open"][chart['header']['game_type']]
        if game_type == "guitar":
            guitar_charts.append(chart)
        elif game_type == "bass":
            bass_charts.append(chart)
        elif game_type == "open":
            open_charts.append(chart)

    # Remove charts from chart list
    for chart in guitar_charts:
        charts.remove(chart)

    for chart in bass_charts:
        charts.remove(chart)

    for chart in open_charts:
        charts.remove(chart)

    return charts, guitar_charts, bass_charts, open_charts


def add_note_durations(chart, sound_metadata):
    duration_lookup = {}

    if not sound_metadata or 'entries' not in sound_metadata:
        return chart

    for entry in sound_metadata['entries']:
        duration_lookup[entry['sound_id']] = entry.get('duration', 0)

    for k in chart['timestamp']:
        for i in range(0, len(chart['timestamp'][k])):
            if chart['timestamp'][k][i]['name'] in ['note', 'auto']:
                chart['timestamp'][k][i]['data']['note_length'] = int(round(duration_lookup.get(chart['timestamp'][k][i]['data']['sound_id'], 0) * 300))

    return chart


def get_start_timestamp(chart):
    for timestamp_key in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][timestamp_key]:
            if beat['name'] in ["startpos"]:
                return timestamp_key

    return sorted(chart['timestamp'].keys(), key=lambda x: int(x))[0]


def get_end_timestamp(chart):
    for timestamp_key in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][timestamp_key]:
            if beat['name'] in ["endpos"]:
                return timestamp_key

    return sorted(chart['timestamp'].keys(), key=lambda x: int(x))[-1]


def find_next_measure_event(chart, start_key=None):
    keys_sorted = sorted(chart['timestamp'].keys(), key=lambda x: int(x))

    for idx, timestamp_key in enumerate(keys_sorted[1:]):
        if timestamp_key in [0xffff, 0xffffffff]:
            break

        if start_key and timestamp_key <= start_key:
            continue

        for beat in chart['timestamp'][timestamp_key]:
            if beat['name'] in ["measure"]:
                return timestamp_key

    return None


def generate_bpm_events(chart):
    bpms = []

    last_bpm_timestamp_key = 0
    last_bpm = None

    while True:
        next_bpm_timestamp_key = find_next_measure_event(chart, last_bpm_timestamp_key)

        if not next_bpm_timestamp_key:
            break

        cur_bpm = 300 / (((next_bpm_timestamp_key - last_bpm_timestamp_key) / 4) / 60)

        if cur_bpm != last_bpm:
            chart['timestamp'][last_bpm_timestamp_key].append({
                "data": {
                    "bpm": cur_bpm
                },
                "name": "bpm"
            })

            last_bpm = cur_bpm

        last_bpm_timestamp_key = next_bpm_timestamp_key


    return chart


def generate_metadata(chart):
    chart = generate_bpm_events(chart)

    keys_sorted = sorted(chart['timestamp'].keys(), key=lambda x: int(x))

    chart['timestamp'][keys_sorted[0]].append({
        "name": "baron",
        "data": {}
    })

    chart['timestamp'][keys_sorted[0]].append({
        "name": "startpos",
        "data": {}
    })

    chart['timestamp'][keys_sorted[-1]].append({
        "name": "endpos",
        "data": {}
    })

    return chart


def generate_notes_metadata(chart):
    keys_sorted = sorted(chart['timestamp'].keys(), key=lambda x: int(x))

    chart['timestamp'][keys_sorted[0]].append({
        "name": "chipstart",
        "data": {}
    })

    return chart


########################
#   DSQ parsing code   #
########################
def parse_event_block(mdata, game, difficulty, is_metadata=False):
    packet_data = {}

    timestamp, cmd, param1, param2 = struct.unpack("<IBBH", mdata[0:8])
    timestamp *= 4

    if is_metadata and cmd not in [0x07, 0x08]:
        return None

    if not is_metadata and cmd in [0x07, 0x08]:
        return None

    game_type_id = {"drum": 0, "guitar": 1, "bass": 2, "open": 3}[game]

    event_name = EVENT_ID_MAP[cmd]

    if event_name == "note":
        packet_data['sound_id'] = param2
        packet_data['volume'] = param1
        packet_data['note'] = NOTE_MAPPING[game][cmd]

        if packet_data['note'] == "auto":
            packet_data['auto_volume'] = 1
            packet_data['auto_note'] = 1

    return {
        "name": event_name,
        'timestamp': timestamp,
        "data": packet_data
    }


def read_dsq1_data(data, game_type, difficulty, is_metadata):
    output = {
        "beat_data": []
    }

    if data is None:
        return None

    unk_sys = 0
    time_division = 300
    beat_division = 480

    output['header'] = {
        "unk_sys": unk_sys,
        "difficulty": difficulty,
        "is_metadata": is_metadata,
        "game_type": game_type,
        "time_division": time_division,
        "beat_division": beat_division,
    }

    header_size = 0
    entry_size = 0x08
    entry_count = len(data) // entry_size

    for i in range(entry_count):
        mdata = data[header_size + (i * entry_size):header_size + (i * entry_size) + entry_size]
        part = ["drum", "guitar", "bass", "open"][game_type]
        parsed_data = parse_event_block(mdata, part, difficulty, is_metadata=is_metadata)

        if parsed_data:
            output['beat_data'].append(parsed_data)

    return output


def convert_to_timestamp_chart(chart):
    chart['timestamp'] = collections.OrderedDict()

    for x in sorted(chart['beat_data'], key=lambda x: int(x['timestamp'])):
        if x['timestamp'] not in chart['timestamp']:
            chart['timestamp'][x['timestamp']] = []

        beat = x['timestamp']
        del x['timestamp']

        chart['timestamp'][beat].append(x)

    del chart['beat_data']

    return chart


def remove_extra_beats(chart):
    new_beat_data = []
    found_measures = []

    for x in sorted(chart['beat_data'], key=lambda x: int(x['timestamp'])):
        if x['name'] == "measure":
            found_measures.append(x['timestamp'])

    for x in sorted(chart['beat_data'], key=lambda x: int(x['timestamp'])):
        if x['name'] == "beat" and x['timestamp'] in found_measures:
            continue

        new_beat_data.append(x)

    chart['beat_data'] = new_beat_data

    return chart


def calculate_timesig(chart):
    found_beats = []

    for x in sorted(chart['beat_data'], key=lambda x: int(x['timestamp'])):
        if x['name'] in ["measure", "beat"]:
            found_beats.append(x)

    beat_count = None
    last_beat = None
    last_measure = None

    for x in found_beats:
        if x['name'] == "measure":
            if beat_count == None:
                beat_count = 1
                last_measure = x['timestamp']
            else:
                if last_beat != beat_count:
                    last_beat = beat_count

                    chart['beat_data'].append({
                        "data": {
                            "numerator": beat_count,
                            "denominator": 4,
                        },
                        "name": "barinfo",
                        "timestamp": last_measure
                    })

                beat_count = 1
                last_measure = x['timestamp']

        elif x['name'] == "beat":
            beat_count += 1

    return chart

def parse_chart_intermediate(chart, game_type, difficulty, is_metadata):
    chart_raw = read_dsq1_data(chart, game_type, difficulty, is_metadata)

    if not chart_raw:
        return None

    chart_raw = remove_extra_beats(chart_raw)
    chart_raw = calculate_timesig(chart_raw)
    chart_raw = convert_to_timestamp_chart(chart_raw)

    start_timestamp = int(get_start_timestamp(chart_raw))
    end_timestamp = int(get_end_timestamp(chart_raw))

    # Handle events based on beat offset in ascending order
    for timestamp_key in sorted(chart_raw['timestamp'].keys(), key=lambda x: int(x)):
        if int(timestamp_key) < start_timestamp or int(timestamp_key) > end_timestamp:
            del chart_raw['timestamp'][timestamp_key]

    return chart_raw


def generate_json_from_dsq1(params):
    combine_guitars = params['merge_guitars'] if 'merge_guitars' in params else False
    output_data = {}

    def get_data(params, game_type, difficulty, is_metadata):
        part = ["drum", "guitar", "bass", "open"][game_type]
        diff = ['nov', 'bsc', 'adv', 'ext', 'mst'][difficulty]

        if 'input_split' in params and part in params['input_split'] and diff in params['input_split'][part] and params['input_split'][part][diff]:
            data = open(params['input_split'][part][diff], "rb").read()
            return (data, game_type, difficulty, is_metadata)

        return None

    raw_charts = [
        # Drum
        get_data(params, 0, 0, False),
        get_data(params, 0, 1, False),
        get_data(params, 0, 2, False),
        get_data(params, 0, 3, False),
        get_data(params, 0, 4, False),
    ]
    raw_charts = [x for x in raw_charts if x is not None]

    if len(raw_charts) > 0:
        raw_charts.append((raw_charts[0][0], raw_charts[0][1], raw_charts[0][2], True))

    musicid = params.get('musicid', None) or 0

    output_data['musicid'] = musicid
    output_data['format'] = Dsq1Format.get_format_name()

    charts = []
    for chart_info in raw_charts:
        chart, game_type, difficulty, is_metadata = chart_info

        parsed_chart = parse_chart_intermediate(chart, game_type, difficulty, is_metadata)

        if not parsed_chart:
            continue

        game_type = ["drum", "guitar", "bass", "open"][parsed_chart['header']['game_type']]
        if game_type in ["guitar", "bass", "open"]:
            parsed_chart = add_note_durations(parsed_chart, params.get('sound_metadata', []))

        if is_metadata:
            parsed_chart = generate_metadata(parsed_chart)
        else:
            parsed_chart = generate_notes_metadata(parsed_chart)

        charts.append(parsed_chart)
        charts[-1]['header']['musicid'] = musicid

    charts = add_song_info(charts, musicid, params['musicdb'])
    charts = filter_charts(charts, params)
    charts, guitar_charts, bass_charts, open_charts = split_charts_by_parts(charts)

    if combine_guitars:
        guitar_charts, bass_charts = combine_guitar_charts(guitar_charts, bass_charts)

    # Merge all charts back together after filtering, merging guitars etc
    charts += guitar_charts
    charts += bass_charts
    charts += open_charts

    output_data['charts'] = charts

    return json.dumps(output_data, indent=4, sort_keys=True)


class Dsq1Format:
    @staticmethod
    def get_format_name():
        return "Dsq1"

    @staticmethod
    def to_json(params):
        return generate_json_from_dsq1(params)

    @staticmethod
    def to_chart(params):
        super()

    @staticmethod
    def is_format(filename):
        return False


def get_class():
    return Dsq1Format
