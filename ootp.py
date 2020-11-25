from os import path
from time import sleep
from bs4 import BeautifulSoup
import pandas as pd
import pyautogui
import numpy as np


class Matchup:
    def __init__(self, soup):
        self.soup = soup
        self.set_ids()
        self.set_player_stats()
        self.set_team_stats()
        self.flatten_ind_stats()

    def set_ids(self):

        team_ids = []
        team_values = {'align': 'center',
                       'style': 'color:FFFFFF; font-size:16px; font-weight:bold;'}
        team_logos = self.soup.find_all('td', team_values)

        for team in team_logos:
            if team.a:
                team_ids.append(int(team.a['href'].split(
                    '/')[-1].split('.')[0].split('_')[-1]))

        self.away_id, self.home_id = team_ids

    def identify_table_type(self, table):
        if table.find_all('th', class_='hsn dr')[-1].text == 'OPS':
            return 'batting'
        elif table.find_all('th', class_='hsn dr')[-1].text == 'BABIP':
            return 'pitching'

    def parse_stats_table(self, table):
        headers = self.get_table_headers(table.find_all('th', class_='hsn dr'))

        players = table.find_all('tr')[1:]
        return self.parse_player_stats(headers, players)

    def get_table_headers(self, header_tags):
        headers = [column.text for column in header_tags]
        headers.insert(0, 'player_id')
        return headers

    def get_player_id(self, player):
        return int(player.a['href'].split('/')[-1].split('.')[0].split('_')[-1])

    def parse_player_stats(self, headers, players):
        stats_list = []
        for player in players:
            player_stats = [self.get_player_id(player.find('td', class_='dl'))]
            for column in player.find_all('td', class_='dr'):
                try:
                    stat = int(column.text)
                except ValueError:
                    stat = float(column.text)
                player_stats.append(stat)

            stats_list.append(dict(zip(headers, player_stats)))
        return stats_list

    def set_player_stats(self):
        tables = self.soup.find_all('table', class_='data sortable')[:4]
        self.player_batting, self.player_pitching = [], []

        for table in tables:
            table_type = self.identify_table_type(table)
            if table_type == 'batting':
                self.player_batting.append(self.parse_stats_table(table))
            elif table_type == 'pitching':
                self.player_pitching.append(self.parse_stats_table(table))

    def set_team_stats(self):
        self.team_batting, self.team_pitching = [], []
        for team in self.player_batting:
            agg_dict = self.agg_team_batting_stats(team)
            if self.player_batting.index(team) == 0:
                agg_dict['team_id'] = self.away_id
            else:
                agg_dict['team_id'] = self.home_id
            self.team_batting.append(agg_dict)

        for bat, pitch in zip(self.player_batting[::-1], self.player_pitching):
            agg_dict = self.agg_team_pitching_stats(bat, pitch)
            if self.player_pitching.index(pitch) == 0:
                agg_dict['team_id'] = self.away_id
            else:
                agg_dict['team_id'] = self.home_id

            self.team_pitching.append(agg_dict)

    def agg_team_batting_stats(self, stats, return_dict=True):
        df = pd.DataFrame(stats)
        df['1B'] = df['H'] - df['2B'] - df['3B'] - df['HR']
        df = df[['AB', 'R', 'H', '1B', '2B', '3B', 'HR', 'RBI', 'TB',
                 'BB', 'K', 'SB', 'CS']].aggregate(sum).astype(int)

        if return_dict:
            return df.round(4).to_dict()
        else:
            return df

    def agg_team_pitching_stats(self, batting, pitching, return_dict=True):
        pitch = pd.DataFrame(pitching)
        pitch['IP'] = pitch['IP'] // 1 + pitch['IP'] % 1 * 10 * 1 / 3
        pitch_agg = pitch[['W', 'L', 'SV', 'HA', 'R', 'ER',
                           'HR', 'BB', 'K']].aggregate(sum).astype(int)
        pitch_agg['IP'] = round(pitch['IP'].aggregate(sum), 1)

        hitting = self.agg_team_batting_stats(batting, return_dict=False)

        pitch_agg = pitch_agg.append(
            hitting[['AB', 'SB', 'CS', 'TB', '1B', '2B', '3B']])

        if return_dict:
            return pitch_agg.to_dict()
        else:
            return pitch_agg

    def flatten_ind_stats(self):
        self.player_batting = [
            player for team in self.player_batting for player in team]
        self.player_pitching = [
            player for team in self.player_pitching for player in team]


class Simulation:

    def __init__(self, file_path):
        self.file_path = file_path
        try:
            self.file_time = path.getmtime(self.file_path)
        except FileNotFoundError:
            self.file_time = 0

    def watch_file_updates(self):
        new_time = 0
        while new_time <= self.file_time:
            sleep(3.0)
            new_time = path.getmtime(self.file_path)
        self.file_time = new_time
        self.create_soup()

    def create_soup(self):
        with open(self.file_path, 'r') as f:
            self.soup = BeautifulSoup(f, "html.parser")
            #self.soup = BeautifulSoup(f, 'lxml')


class Stats:
        
    def __init__(self):
        self.stats = {'team_batting': [],
                      'team_pitching': [],
                      'player_batting': [],
                      'player_pitching': []
                      }

    def add_matchup_stats(self, matchup):
        keys = [stat for stat in matchup.__dict__.keys()
                if stat in self.stats.keys()]
        for key in keys:
            self.stats[key].extend(matchup.__dict__[key])

    def aggregate_stats(self):
        self.df_dict = {}
        for group in ['player', 'team']:

            df_batting = pd.DataFrame(
                self.stats[''.join([group, '_batting'])]).groupby(''.join([group, '_id'])).sum()
            self.calculate_batting_stats(df_batting)
            self.df_dict[''.join([group, '_batting'])] = df_batting

            df_pitching = pd.DataFrame(
                self.stats[''.join([group, '_pitching'])])
            self.convert_ip(df_pitching)
            df_pitching = df_pitching.groupby(''.join([group, '_id'])).sum()
            if group == 'team':
                self.calculate_batting_stats(df_pitching, type='pitching')

            self.calculate_pitching_stats(df_pitching, group)
            self.df_dict[''.join([group, '_pitching'])] = df_pitching

    def calculate_batting_stats(self, dataframe, type='batting'):
        if type != 'batting':
            hits = 'HA'
        else:
            hits = 'H'

        dataframe['AVG'] = round(dataframe[hits] / dataframe['AB'], 3)
        dataframe['SLG'] = round(dataframe['TB'] / dataframe['AB'], 3)
        dataframe['OBP'] = round(
            (dataframe[hits] + dataframe['BB']) / (dataframe['AB'] + dataframe['BB']), 3)
        dataframe['OPS'] = round(dataframe['OBP'] + dataframe['SLG'], 3)
        if '1B' not in dataframe.columns:
            dataframe['1B'] = dataframe[hits] - \
                dataframe['2B'] - dataframe['3B'] - dataframe['HR']
        dataframe['wOBA'] = round((dataframe['BB'] * .69 + dataframe['1B'] * .888 + dataframe['2B'] * 1.271 +
                                   dataframe['3B'] * 1.616 + dataframe['HR'] * 2.101) / (dataframe['AB'] + dataframe['BB']), 4)
        return dataframe

    def convert_ip(self, dataframe):
        dataframe['IP'] = round(dataframe['IP'] // 1 +
                                dataframe['IP'] % 1 * 10 * 1 / 3, 1)
        dataframe['BF'] = round(dataframe['IP'] * 3 +
                                dataframe['HA'] + dataframe['BB'], 0)

    def calculate_pitching_stats(self, dataframe, focus='player'):
        dataframe['FIP'] = round(
            ((dataframe['HR'] * 13 + dataframe['BB'] * 3 - dataframe['K'] * 2) / dataframe['IP']) + 3.20, 2)
        dataframe['K/9'] = round(dataframe['K'] / dataframe['IP'] * 9, 1)
        dataframe['BB/9'] = round(dataframe['BB'] / dataframe['IP'] * 9, 1)
        dataframe['HR/9'] = round(dataframe['HR'] / dataframe['IP'] * 9, 1)
        dataframe['IP'] = round(dataframe['IP'], 1)
        dataframe['BF'] = round(dataframe['BF'], 0)

        if focus != 'player':
            dataframe['BABIP'] = round((dataframe['HA'] - dataframe['HR']) /
                                       (dataframe['AB'] - dataframe['K'] - dataframe['HR']), 3)
        else:
            # Pitchers don't have number of opponent ABs or BFs, so BABIP and OAVG are best estimates
            dataframe['BABIP'] = round((dataframe['HA'] - dataframe['HR']) / (
                dataframe['BF'] - dataframe['BB'] - dataframe['K'] - dataframe['HR']), 3)
            dataframe['OAVG'] = round(
                dataframe['HA'] / (dataframe['BF'] - dataframe['BB']), 3)

        return dataframe

    def send_to_csv(self, prepend=None, append=None, path=None):

        print("to csv")
        for key in self.df_dict.keys():
            path_list = [path, prepend, key, append, '.csv']
            path_string = ''.join(
                [txt for txt in path_list if isinstance(txt, str)])
            self.df_dict[key].to_csv(path_string)

    def send_to_mysql(self, tables=None, connector=None, schema=None, if_exists=None):
        for key in self.df_dict.keys():
            self.df_dict[key].replace([np.inf, -np.inf], np.nan).dropna()
            if tables:
                self.df_dict[key].to_sql(tables[list(self.df_dict.keys()).index(
                    key)], connector, schema=schema, if_exists=if_exists)
            else:
                self.df_dict[key].to_sql(
                    key, connector, schema=schema, if_exists=if_exists)


class PlayMenu:

    def __init__(self, x=1082, y=81):
        self.x, self.y = x, y

    def set_menu_location(self, x, y):
        self.x, self.y = x, y

    def use_pyauto_position(self):
        input('Move the mouse of the \'Play Menu\' and press Enter.')
        self.x, self.y = pyautogui.position()

    def open(self):
        pyautogui.moveTo(self.x, self.y, .4)
        sleep(.05)
        # pyautogui.click()
        Mouse.click('left')
        sleep(.05)


class SimMenu:

    # Edit locations or add in function call
    def __init__(self, x=1259, y=676):
        self.x, self.y = x, y

    def open(self):
        pyautogui.moveTo(self.x, self.y, .25)
        sleep(.05)
        # pyautogui.click()
        Mouse.click('left')
        sleep(.05)       


class SimModule:

    def __init__(self, x=1011, away_y=471, home_y=425, clear_y=441, button_y=692, file_path=None):
        self.x = x
        self.away_y = away_y
        self.home_y = home_y
        self.clear_y = clear_y
        self.button_y = button_y
        if file_path is not None:
            self.update_team_locations(file_path)
        else:
            # locsAway is the top dropdown box
            # EDIT LOCATIONS!
            self.locsAway = {'BOI': 469,'CAN': 493,'DVS': 517,'DET': 543,
                             'IND': 566,'KAS': 586,'NSH': 614,'NO': 636,
                             'NYV': 661,'OBX': 687,'PRO': 708,'SAS': 732,
                             'SAR': 757,'VAN': 779}
            # locsHome is the bottom dropdown box.
            # EDIT LOCATIONS!
            self.locsHome = {'BOI': 518,'CAN': 540,'DVS': 560,'DET': 587,
                             'IND': 612,'KAS': 636,'NSH': 659,'NO': 685,
                             'NYV': 705,'OBX': 731,'PRO': 756,'SAS': 776,
                             'SAR': 804,'VAN': 827}


    def update_team_locations(self, file_path):
        self.locs = {}
        with open(file_path, 'r') as f:
            for line in f:
                (key, val) = line.strip().split(',')
                self.locs[key] = val

    def set_window_params(self):
        input('Move the mouse to the Away Team selection menu and press Enter.')
        self.x, self.away_y = pyautogui.position()
        input('Move the mouse to the Home Team selection menu and press Enter.')
        self.home_y = pyautogui.position()[1]
        input('Move the mouse to the \'Simulate\' button and press Enter.')
        self.button_y = pyautogui.position()[1]

    def clear_matchup(self):
        for team in (self.home_y, self.away_y):
            pyautogui.moveTo(self.x, team, .1)
            sleep(.05)
            # pyautogui.click()
            Mouse.click('left')
            #pyautogui.moveTo(self.x, self.clear_y, 2.1)
            pyautogui.moveRel(0,20,.1)
            sleep(.05)
            # pyautogui.click()
            Mouse.click('left')
            sleep(.05)

    def update_team(self, new_y, type='home'):
        if type == 'home':
            pyautogui.moveTo(self.x, self.home_y, .1)
        else:
            pyautogui.moveTo(self.x, self.away_y, .1)
        sleep(.05)
        # pyautogui.click()
        Mouse.click('left')
        sleep(.05)
        pyautogui.moveTo(self.x, new_y, .2)
        sleep(.05)
        # pyautogui.click()
        # sleep(.05)
        Mouse.click('left')
        sleep(.05)

    def simulate(self):
        pyautogui.moveTo(self.x, self.button_y, .1)
        # sleep(.05)
        # pyautogui.click()
        # sleep(.05)
        sleep(.05)
        Mouse.click('left')
        sleep(.05)


class ResetWindow:

    def __init__(self, x=241, y=1063):
        self.x = x
        self.y = y
        # self.restore_position()
        self.iterations = 0

    def restore_position(self):
        input('Move the mouse to the OOTP icon on the task bar and press Enter')
        self.rest_x, self.rest_y = pyautogui.position()

    def iterate(self, type='restore'):
        self.iterations += 1
        if self.iterations % 2 == 0 and type == 'restore':
            self.restore()
        elif self.iterations % 2 == 0 and type == 'reset':
            self.reset()

    def reset(self):
        sleep(.5)
        pyautogui.moveTo(self.x, self.y, .1)
        Mouse.click('left')
        #,pyautogui.click(self.x, self.y)
        sleep(.5)
        Mouse.click('left')
        # pyautogui.click()
        sleep(.5)

    def restore(self):
        # pyautogui.click(self.x, self.y)
        pyautogui.moveTo(self.x, self.y, .1)
        Mouse.click('left')
        sleep(.75)
        # pyautogui.click(self.rest_x, self.rest_y)
        Mouse.click('left')
        sleep(.75)
        
# pyautogui.click() does not work intermittently. Manually down and up click
class Mouse:

    def click(button):
        pyautogui.mouseDown(button=button)
        sleep(.05)
        pyautogui.mouseUp(button=button)
