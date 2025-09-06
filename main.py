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

INVALID_HEADING = 1000
INVALID_SPEED = 1000


class NmeaChunk():
    def __init__(self, date):
        '''
        date : A datetime object
        '''
        self._date = date
        self._heading_true = INVALID_HEADING
        self._heading_magnetic = INVALID_HEADING
        self._water_speed_knots = INVALID_SPEED

    def update(self, sentence):
        '''
        sentence : A NMEASentence object from pynmea2
        '''
        if sentence.sentence_type=='VHW':
            self._heading_true = sentence.heading_true
            self._heading_magnetic = sentence.heading_magnetic
            self._water_speed_knots = sentence.water_speed_knots

    def get(self, what):
        if what == "heading true":
            if self._heading_true == INVALID_HEADING:
                raise ValueError("No valid true heading")
            return self._heading_true
        elif what == "heading magnetic":
            if self._heading_magnetic == INVALID_HEADING:
                raise ValueError("No valid magnetic heading")
            return self._heading_magnetic
        elif what == "water speed knots":
            if self._water_speed_knots == INVALID_SPEED:
                raise ValueError("No valid speed")
            return self._water_speed_knots
        else:
            raise ValueError(f"Unknown what: {what}")

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
    "water speed knots": "green"
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

def assert_nmea_is_valid(msg, logger):
    if not hasattr(msg, 'sentence_type'):
        raise ValueError(f"Unknown NMEA sentence: {repr(msg)}")
    assert_zda_is_valid(msg, logger)
    assert_vhw_is_valid(msg, logger)

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
                        nmea_chunk = NmeaChunk(next_date)
                        nmea_chunks.append(nmea_chunk)
                    else:
                        nmea_chunk.update(msg)

                except Exception as e:
                    # logger.warning(f"Line {line_counter}: {e} : {line.strip()}")
                    fail += 1
                    continue
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

        options = ["heading true", "heading magnetic", "water speed knots", "exit"]
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

