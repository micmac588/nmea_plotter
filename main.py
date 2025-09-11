#!/usr/bin/env python3
import argparse
import datetime
import logging
import re
import numpy as np
import os
logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pynmea2
from simple_term_menu import TerminalMenu
from tqdm import *

INVALID_ANGLE = 1000
INVALID_SPEED = 1000
INVALID_TEMPERATURE = 1000
HEADING_DIFFERENCE_WARNING_THRESHOLD = 10.0
WIND_SPEED_DIFFERENCE_WARNING_THRESHOLD = 0.5

def diff_angles(angle1, angle2):
    d = angle1 - angle2
    if d > 180.0:
        d -= 360.0
    elif d < -180.0:
        d += 360.0
    return d


class NmeaChunk():
    def __init__(self, date, logger):
        '''
        date : A datetime object
        '''
        self._date = date
        self.logger = logger
        self._heading_true = INVALID_ANGLE
        self._heading_magnetic = INVALID_ANGLE
        self._heading_magnetic_hdm = INVALID_ANGLE
        self._water_speed_knots = INVALID_SPEED
        self._heading_true_over_ground = INVALID_ANGLE
        self._heading_magnetic_over_ground = INVALID_ANGLE
        self._speed_over_ground_knots = INVALID_SPEED
        self._rudder_sensor_angle_port = INVALID_ANGLE
        self._rudder_sensor_angle_starboard = INVALID_ANGLE
        self._water_temperature = INVALID_TEMPERATURE
        self._wind_angle = INVALID_ANGLE
        self._true_wind_speed = INVALID_SPEED
        self._apparent_wind_speed = INVALID_SPEED
        self._true_wind_direction = INVALID_ANGLE
        self._magnetic_wind_direction = INVALID_ANGLE
        self._true_wind_speed_mwd = INVALID_SPEED


    def update(self, sentence):
        '''
        sentence : A NMEASentence object from pynmea2
        '''
        if sentence.sentence_type=='VHW':
            self._heading_true = sentence.heading_true
            if self._heading_magnetic_hdm != INVALID_ANGLE and diff_angles(self._heading_magnetic_hdm, sentence.heading_magnetic) > HEADING_DIFFERENCE_WARNING_THRESHOLD:
                self.logger.warning(f"Conflict between VHW and HDM magnetic heading at {self._date} : {self._heading_magnetic_hdm} != {sentence.heading_magnetic}")
            self._heading_magnetic = sentence.heading_magnetic
            self._water_speed_knots = sentence.water_speed_knots
        elif sentence.sentence_type=='VTG':
            self._heading_true_over_ground = sentence.true_track
            self._heading_magnetic_over_ground = sentence.mag_track
            self._speed_over_ground_knots = sentence.spd_over_grnd_kts
        elif sentence.sentence_type=='RSA':
            self._rudder_sensor_angle_starboard = sentence.rsa_starboard
            self._rudder_sensor_angle_port = sentence.rsa_port
        elif sentence.sentence_type=='MTW':
            self._water_temperature = sentence.temperature
        elif sentence.sentence_type=='HDM':
            if self._heading_magnetic != INVALID_ANGLE and diff_angles(self._heading_magnetic, sentence.heading) > HEADING_DIFFERENCE_WARNING_THRESHOLD:
                self.logger.warning(f"Conflict between VHW and HDM magnetic heading at {self._date} : {self._heading_magnetic} != {sentence.heading}")
            self._heading_magnetic_hdm = sentence.heading
        elif sentence.sentence_type == 'MWV':
            self._wind_angle = sentence.wind_angle
            if sentence.reference == 'T':
                self._true_wind_speed = sentence.wind_speed
                if self._true_wind_speed_mwd != INVALID_ANGLE and abs(self._true_wind_speed - self._true_wind_speed_mwd) > WIND_SPEED_DIFFERENCE_WARNING_THRESHOLD:
                    self.logger.warning(f"Conflict between MWV and MWD true wind speed at {self._date} : {self._true_wind_speed} != {self._true_wind_speed_mwd}")
            if sentence.reference == 'R':
                self._apparent_wind_speed = sentence.wind_speed
        elif sentence.sentence_type == 'MWD':
            self._true_wind_direction = sentence.direction_true
            self._magnetic_wind_direction = sentence.direction_magnetic
            self._true_wind_speed_mwd = sentence.wind_speed_knots
            if self._true_wind_speed != INVALID_ANGLE and abs(self._true_wind_speed - self._true_wind_speed_mwd) > WIND_SPEED_DIFFERENCE_WARNING_THRESHOLD:
                self.logger.warning(f"Conflict between MWV and MWD true wind speed at {self._date} : {self._true_wind_speed} != {self._true_wind_speed_mwd}")

    def get(self, what):
        if what == "heading true":
            if self._heading_true == INVALID_ANGLE:
                raise ValueError("No valid true heading")
            return self._heading_true
        elif what == "heading magnetic":
            if self._heading_magnetic == INVALID_ANGLE:
                raise ValueError("No valid magnetic heading")
            return self._heading_magnetic
        elif what == "water speed knots":
            if self._water_speed_knots == INVALID_SPEED:
                raise ValueError("No valid speed")
            return self._water_speed_knots
        elif what == "heading true over ground":
            if self._heading_true_over_ground == INVALID_ANGLE:
                raise ValueError("No valid true heading over ground")
            return self._heading_true_over_ground
        elif what == "heading magnetic over ground":
            if self._heading_magnetic_over_ground == INVALID_ANGLE:
                raise ValueError("No valid magnetic heading over ground")
            return self._heading_magnetic_over_ground
        elif what == "speed over ground":
            if self._speed_over_ground_knots == INVALID_SPEED:
                raise ValueError("No valid speed over ground")
            return self._speed_over_ground_knots
        elif what == "port rudder sensor angle":
            if self._rudder_sensor_angle_port == INVALID_ANGLE:
                raise ValueError("No valid port rudder sensor angle")
            return self._rudder_sensor_angle_port
        elif what == "starboard rudder sensor angle":
            if self._rudder_sensor_angle_starboard == INVALID_ANGLE:
                raise ValueError("No valid starboard rudder sensor angle")
            return self._rudder_sensor_angle_starboard
        elif what == "water temperature":
            if self._water_temperature == INVALID_TEMPERATURE:
                raise ValueError("No valid water temperature")
            return self._water_temperature
        elif what == "heading magnetic (HDM)":
            if self._heading_magnetic_hdm == INVALID_ANGLE:
                raise ValueError("No valid magnetic heading (HDM)")
            return self._heading_magnetic_hdm
        elif what == "wind angle":
            if self._wind_angle == INVALID_ANGLE:
                raise ValueError("No valid wind angle")
            return self._wind_angle
        elif what == "apparent wind speed":
            if self._apparent_wind_speed == INVALID_SPEED:
                raise ValueError("No valid apparent wind speed")
            return self._apparent_wind_speed
        elif what == "true wind speed":
            if self._true_wind_speed == INVALID_SPEED:
                raise ValueError("No valid true wind speed")
            return self._true_wind_speed
        elif what == "true wind direction":
            if self._true_wind_direction == INVALID_ANGLE:
                raise ValueError("No valid true wind direction")
            return self._true_wind_direction
        elif what == "magnetic wind direction":
            if self._magnetic_wind_direction == INVALID_ANGLE:
                raise ValueError("No valid magnetic wind direction")
            return self._magnetic_wind_direction
        elif what == "true wind speed (MWD)":
            if self._true_wind_speed_mwd == INVALID_SPEED:
                raise ValueError("No valid true wind speed (MWD)")
            return self._true_wind_speed_mwd
        else:
            raise ValueError(f"Unknown what: {what}")
        
    def assert_has_what(self, list_of_what):
        for what in list_of_what:
            self.get(what)

    def __str__(self):
        return f"{self._date} : {repr(self._sentence)}"

def prepare_logger(logger_name, verbosity, log_file=None):
    """Initialize and set the logger.

    :param logger_name: the name of the logger to create
    :type logger_name: string
    :param verbosity: verbosity level: 0 -> default, 1 -> info, 2 -> debug
    :type  verbosity: int
    :param log_file: if not None, file where to save the logs.
    :type  log_file: string (path)
    :return: a configured logger
    :rtype: logging.Logger
    """

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # set to the lowest, handlers will filter

    # set log level    
    if verbosity == 0:
        log_level = logging.ERROR
    elif verbosity == 1:
        log_level = logging.WARNING
    elif verbosity == 2:
        log_level = logging.INFO
    elif verbosity >= 3:
        log_level = logging.DEBUG
    # set log format
    log_format = "[%(asctime)s] [%(levelname)-7s] [%(filename)s:%(lineno)d] %(message)s"
    formatter = logging.Formatter(log_format)

    # create and add console logger
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # create and add file logger
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

colors = {
    "heading true": "blue",
    "heading magnetic": "orange",
    "heading magnetic (HDM)": "cyan",
    "water speed knots": "green",
    "heading true over ground": "red",
    "heading magnetic over ground": "purple",
    "speed over ground": "brown",
    "port rudder sensor angle": "pink",
    "starboard rudder sensor angle": "gray",
    "water temperature": "olive",
    "wind angle": "black",
    "apparent wind speed": "magenta",
    "true wind speed": "yellow",
    "true wind direction": "lightblue",
    "magnetic wind direction": "lightgreen",
    "true wind speed (MWD)": "lightcoral"
}

def plot_data(nmea_chunks, list_of_what, logger):
    if nmea_chunks is None or len(nmea_chunks) == 0 or list_of_what is None or len(list_of_what) == 0:
        logger.warning("Nothing to plot")
        return
    logger.debug(f"Number of nmea_chunks: {len(nmea_chunks)}")
    dict_of_what = {}
    time = []
    for nmea_chunk in nmea_chunks:
        try:
            nmea_chunk.assert_has_what(list_of_what)
            for what in list_of_what:
                if what not in dict_of_what:
                    dict_of_what[what] = []
                dict_of_what[what].append(nmea_chunk.get(what))
            time.append(nmea_chunk._date)
        except ValueError as e:
            continue
            
    logger.debug(f"Number of dates: {len(time)}")
    xpoints = np.array(time)

    for what, _list in dict_of_what.items():
        logger.debug(f"Number of {what}: {len(_list)}")
        ypoints = np.array(_list)
        plt.gca().plot(xpoints, ypoints, label = what, color = colors[what])
    
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    
    plt.legend()
    plt.show(block=False)
    plt.pause(1)
    input("press any key to continue...")
    plt.close()

def update_current_date(msg, logger, line_counter, previous_date):

    # Ignore other source of date than GP ZDA sentences
    if msg.talker == 'GP' and msg.sentence_type=='ZDA':
        _current_date = datetime.datetime(msg.year, msg.month, msg.day,
                                            msg.timestamp.hour,
                                            msg.timestamp.minute,
                                            msg.timestamp.second)
        if previous_date and _current_date < previous_date:
            logger.error(f"Time went backwards at line {line_counter}: {_current_date} < {previous_date}")
            exit(-1)
        if previous_date and _current_date.timestamp()-previous_date.timestamp() > 10:
            logger.error(f"Time jump detected at line {line_counter}: {_current_date} - {previous_date} > 10s")
            exit(-1)
        return _current_date
    else:
        return previous_date

def assert_zda_is_valid(msg, logger):
    if msg.sentence_type=='ZDA':
        if msg.year is None or msg.month is None or msg.day is None:
            raise ValueError(f"Invalid ZDA sentence: {repr(msg)}")
        if msg.timestamp is None:
            raise ValueError(f"Invalid ZDA sentence: {repr(msg)}")
        if not (1 <= msg.month <= 12):
            raise ValueError(f"Invalid month in ZDA sentence: {repr(msg)}")
        if not (1 <= msg.day <= 31):
            raise ValueError(f"Invalid day in ZDA sentence: {repr(msg)}")
        if not (0 <= msg.timestamp.hour < 24):
            raise ValueError(f"Invalid hour in ZDA sentence: {repr(msg)}")
        if not (0 <= msg.timestamp.minute < 60):
            raise ValueError(f"Invalid minute in ZDA sentence: {repr(msg)}")
        if not (0 <= msg.timestamp.second < 60):
            raise ValueError(f"Invalid second in ZDA sentence: {repr(msg)}")

def assert_vhw_is_valid(msg, logger):
    if msg.sentence_type=='VHW':
        if msg.heading_true is not None:
            if not (0.0 <= msg.heading_true < 360.0):
                raise ValueError(f"Invalid true heading in VHW sentence: {repr(msg)}")
        if msg.heading_magnetic is not None:
            if not (0.0 <= msg.heading_magnetic < 360.0):
                raise ValueError(f"Invalid magnetic heading in VHW sentence: {repr(msg)}")
        if msg.water_speed_knots is not None:
            if msg.water_speed_knots < 0.0:
                raise ValueError(f"Invalid speed in knots in VHW sentence {msg.water_speed_knots}")
        if msg.water_speed_km is not None:
            if msg.water_speed_km < 0.0:
                raise ValueError(f"Invalid speed in km/h in VHW sentence")
            
def assert_vtg_is_valid(msg, logger):
    '''
    VTG - Track made good and Ground speed

        1   2 3   4 5  6 7   8 9
        |   | |   | |  | |   | |
 $--VTG,x.x,T,x.x,M,x.x,N,x.x,K*hh<CR><LF>

 Field Number: 
  1) Track Degrees
  2) T = True
  3) Track Degrees
  4) M = Magnetic
  5) Speed Knots
  6) N = Knots
  7) Speed Kilometers Per Hour
  8) K = Kilometers Per Hour
  9) Checksum
  '''
    if msg.sentence_type=='VTG':
        if msg.true_track is not None:
            if not (0.0 <= msg.true_track < 360.0):
                raise ValueError(f"Invalid true track in VTG sentence: {repr(msg)}")
        if msg.mag_track is not None:
            if not (0.0 <= msg.mag_track < 360.0):
                raise ValueError(f"Invalid magnetic track in VTG sentence: {repr(msg)}")
        if msg.spd_over_grnd_kts is not None:
            if msg.spd_over_grnd_kts < 0.0:
                raise ValueError(f"Invalid speed in knots in VTG sentence {msg.speed_knots}")
        if msg.spd_over_grnd_kmph is not None:
            if msg.spd_over_grnd_kmph < 0.0:
                raise ValueError(f"Invalid speed in km/h in VTG sentence")
            
def assert_rsa_is_valid(msg, logger):
    '''
    RSA - Rudder Sensor Angle

        1   2 3   4 5
        |   | |   | |
 $--RSA,x.x,A,x.x,A*hh<CR><LF>

 Field Number: 
  1) Starboard (or single) rudder sensor, "-" means Turn To Port
  2) Status, A means data is valid
  3) Port rudder sensor
  4) Status, A means data is valid
  5) Checksum
  '''
    if msg.sentence_type=='RSA':
        if msg.rsa_starboard is not None:
            if not (-127.0 <= msg.rsa_starboard <= 127.0) or msg.rsa_starboard_status != 'A':
                raise ValueError(f"Invalid starboard rudder angle in RSA sentence: {repr(msg)}")
        if msg.rsa_port is not None:
            if not (-127.0 <= msg.rsa_port <= 127.0) or msg.rsa_port_status != 'A':
                raise ValueError(f"Invalid port rudder angle in RSA sentence: {repr(msg)}")
            
def assert_mtw_is_valid(msg, logger):
    '''
    MTW - Water Temperature

        1   2 3
        |   | | 
 $--MTW,x.x,C*hh<CR><LF>

 Field Number: 
  1) Degrees
  2) Unit of Measurement, Celcius
  3) Checksum
  '''
    if msg.sentence_type=='MTW':
        if msg.temperature is not None:
            if not (-10.0 <= msg.temperature <= 40.0):
                raise ValueError(f"Invalid water temperature in MTW sentence: {repr(msg)}")

def assert_hdm_is_valid(msg, logger):
    '''HDM - Heading - Magnetic

        1   2 3
        |   | |
 $--HDM,x.x,M*hh<CR><LF>

 Field Number: 
  1) Heading Degrees, magnetic
  2) M = magnetic
  3) Checksum
  '''
    if msg.sentence_type=='HDM':
        if msg.heading is not None:
            if not (0.0 <= msg.heading < 360.0):
                raise ValueError(f"Invalid magnetic heading in HDM sentence: {repr(msg)}")
    
def assert_mwv_is_valid(msg, logger):
    '''
    MWV - Wind Speed and Angle

        1   2 3   4 5
        |   | |   | |
 $--MWV,x.x,a,x.x,a*hh<CR><LF>

 Field Number: 
  1) Wind Angle, 0 to 360 degrees
  2) Reference, R = Relative, T = True
  3) Wind Speed
  4) Wind Speed Units, K/M/N
  5) Status, A = Data Valid
  6) Checksum
  '''
    if msg.sentence_type=='MWV':
        if msg.wind_angle is not None:
            if not (0.0 <= msg.wind_angle < 360.0):
                raise ValueError(f"Invalid wind angle in MWV sentence: {repr(msg)}")
        if msg.wind_speed is not None:
            if msg.wind_speed < 0.0:
                raise ValueError(f"Invalid wind speed in MWV sentence: {repr(msg)}")
        if msg.reference != 'R' and msg.reference != 'T':
            raise ValueError(f"Invalid reference MWV sentence: {repr(msg)}")
        if msg.status != 'A':
            raise ValueError(f"Invalid status in MWV sentence: {repr(msg)}")
        
def assert_mwd_is_valid(msg, logger):
    '''
    MWD - Wind Direction and Speed

        1   2 3   4 5   6 7
        |   | |   | |   | |
 $--MWD,x.x,T,x.x,M,x.x,N*hh<CR><LF>

 Field Number: 
  1) Wind Direction, degrees True
  2) T = True
  3) Wind Direction, degrees Magnetic
  4) M = Magnetic
  5) Wind Speed, knots
  6) N = Knots
  7) Checksum
  '''
    if msg.sentence_type=='MWD':
        if msg.direction_true is not None:
            if not (0.0 <= msg.direction_true < 360.0):
                raise ValueError(f"Invalid true wind direction in MWD sentence: {repr(msg)}")
        if msg.direction_magnetic is not None:
            if not (0.0 <= msg.direction_magnetic < 360.0):
                raise ValueError(f"Invalid magnetic wind direction in MWD sentence: {repr(msg)}")
        if msg.wind_speed_knots is not None:
            if msg.wind_speed_knots < 0.0:
                raise ValueError(f"Invalid wind speed in knots in MWD sentence: {repr(msg)}")    

def assert_nmea_is_valid(msg, logger):
    if not hasattr(msg, 'sentence_type'):
        raise ValueError(f"Unknown NMEA sentence: {repr(msg)}")
    assert_zda_is_valid(msg, logger)
    assert_vhw_is_valid(msg, logger)
    assert_vtg_is_valid(msg, logger)
    assert_rsa_is_valid(msg, logger)
    assert_mtw_is_valid(msg, logger)
    assert_hdm_is_valid(msg, logger)
    assert_mwv_is_valid(msg, logger)
    assert_mwd_is_valid(msg, logger)

def parse_file(inputfile, logger):
    current_date = None
    line_counter = 0
    fail = 0
    nmea_chunks = []
    nmea_chunk = None

    with tqdm(total=os.path.getsize(inputfile)) as pbar:
        with open(inputfile, "r") as fi:
            for line in fi:
                line_counter +=1
                pbar.update(len(line))
                try:
                    #msg = pynmea2.parse(line, check=True)
                    msg = pynmea2.parse(line[12:], check=True)
                    assert_nmea_is_valid(msg, logger)
                    next_date = update_current_date(msg, logger, line_counter, current_date)
                    if next_date != current_date:
                        nmea_chunk = NmeaChunk(next_date, logger)
                        nmea_chunks.append(nmea_chunk)
                    else:
                        nmea_chunk.update(msg)

                except Exception as e:
                    logger.warning(f"Line {line_counter}: {e} : {line.strip()}")
                    fail += 1
                    continue
    logger.warning(f"Failure percentage : {100.0*fail/line_counter:.2f}%")
    return nmea_chunks

def open_output_file(inputfile, line, previous_fo):
    # look for something like 04/02/2024 07:23:58  - Debut
    pattern = r'(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2}):(\d{2})  - Debut'
    result = re.search(pattern, line)
    if result is None:
        # return the previous file descriptor
        return previous_fo
    if previous_fo:
        previous_fo.close()  # close the previous
    result = re.search(pattern, line)
    day = result.group(1)
    month = result.group(2)
    year = result.group(3)
    hour = result.group(4)
    minute = result.group(5)
    second = result.group(6)
    outputfile = os.path.basename(inputfile).split('.')[0] + day + month + year + hour + minute + second + '.log'
    fo = open(outputfile, 'x') # open the new one
    return fo
                
def split(inputfile, logger):
    # Split the log file when it has several 'Debut'
    line_counter = 0
    fail = 0
    fo = None
    with tqdm(total=os.path.getsize(inputfile)) as pbar:
        with open(inputfile, "r") as fi:
            try:
                for line in fi:
                    line_counter +=1
                    pbar.update(len(line))

                    fo = open_output_file(inputfile, line, fo)
                    if fo:
                        fo.write(line)
                    
            except Exception as e:
                logger.error(e)
                fail +=1

def main():
    print("NMEA parser")
    print(f"version: 0.0.0")
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inputfile", help="the nmea log file.", required=True)
    parser.add_argument("-s", "--split", action="store_true", help="split input file", required=False)
    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase the verbosity", required=False)
    parser.add_argument("-l", "--logfile", help="log file name", required=False)

    args = parser.parse_args()

    logger = prepare_logger("nmea_parser", args.verbosity, args.logfile)

    if args.split:
        logger.debug(f"Start splitting of {args.inputfile}")
        split(args.inputfile, logger)
    else:
        print(f"Start parsing of {args.inputfile}")
        nmea_chunks = parse_file(args.inputfile, logger)
        print(f"End of parsing {args.inputfile}")

        options = ["heading true", "heading magnetic",
                   "heading true over ground", "heading magnetic over ground",
                   "wind angle", "apparent wind speed", "true wind speed",
                   "wind direction true", "wind direction magnetic", "true wind speed (MWD)",
                   "water speed knots", "speed over ground",
                   "port rudder sensor angle", "starboard rudder sensor angle",
                   "water temperature",
                   "exit"]
        terminal_menu = TerminalMenu(options, multi_select=True,
                                     show_multi_select_hint=False,
                                     title="Select what to plot (or exit):")
        while True:
            terminal_menu.show()
            if "exit" in terminal_menu.chosen_menu_entries:
                break
            plot_data(nmea_chunks, terminal_menu.chosen_menu_entries, logger)


if __name__ == "__main__":
    main()

