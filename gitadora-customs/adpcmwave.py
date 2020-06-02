import os
import subprocess
import tmpfile

def decode_data(data, rate, channels, bits):
    input_filename = tmpfile.mkstemp()
    output_filename = tmpfile.mkstemp()

    with open(input_filename, "wb") as f:
        f.write(data)

    prefix = ""
    #if os.name != "nt":
    #    prefix = "wine"

    cmd = "{} ./adpcmwavetool d \"{}\" \"{}\" {}".format(prefix, input_filename, output_filename, channels)
    subprocess.call(cmd, shell=True)

    with open(output_filename, "rb") as f:
        data = bytearray(f.read())

    return data

def encode_data(data, channels):
    input_filename = tmpfile.mkstemp()
    output_filename = tmpfile.mkstemp()

    with open(input_filename, "wb") as f:
        f.write(data)

    prefix = ""
    #if os.name != "nt":
    #    prefix = "wine"

    cmd = "{} ./adpcmwavetool e \"{}\" \"{}\" {}".format(prefix, input_filename, output_filename, channels)
    subprocess.call(cmd, shell=True)

    with open(output_filename, "rb") as f:
        data = bytearray(f.read())

    return data