# simtest.py
#
# Script to automate simulation of all possible matchups between teams.
# Outputs batting and pitching reports for individuals and teams. 
# Before running script obtain mouse position coordinates for Play menu,
# simulation module button, taskbar icon, and team menu box locations.
# Mouse coordinates can be found by placing mouse at location of interest
# and running pyautogui.position()
#
# Insert coordinates for simulation module in SimMenu init class
# Add Y coordinates for each team for top and bottom drop down selections in SimModule.locsAway/locsHome


import ootp
from itertools import combinations


def main():
    teams = 'CAN IND NO NYV OBX PRO SAR BOI DVS DET KAS NSH SAS VAN'.split()

    matchups = combinations(teams, 2)

    # OOTP saved games path
    report_path = 'C:/Users/treas/Documents/Out of the Park Developments/OOTP Baseball 21/saved_games/S22PreSeasonOfflinev8.lg/news/html/temp/simulation_report.html'

    # Setting up where the OOTP client has certain menu items
    sim = ootp.Simulation(report_path)
    play_menu = ootp.PlayMenu(x=1180, y=89)
    sim_menu = ootp.SimMenu()
    sim_module = ootp.SimModule(x=1011, away_y=425, home_y=471, clear_y=441,
                                button_y=692)
    reset = ootp.ResetWindow(x=241, y=1063)

    stats = ootp.Stats()

    home = None

    # Run through each matchup, simulate, and parse the report
    for matchup in matchups:
        play_menu.open()
        sim_menu.open()

        # Changes the top team and will iterate matchups with the bottom team
        if matchup[0] != home:
            home = matchup[0]
            print('Starting {}'.format(home))
            
            # Setting a team in the top dropdown causes team to be removed from top and bottom dropdowns
            # causing locations for each team to shift. Clear matchups to reset team locations
            sim_module.clear_matchup()
            sim_module.update_team(sim_module.locsHome[home])

        sim_module.update_team(sim_module.locsAway[matchup[1]], type='away')

        sim_module.simulate()
        sim.watch_file_updates()
        sim.create_soup()
        result = ootp.Matchup(sim.soup)
        stats.add_matchup_stats(result)
        # Running two simulations causes play menu to bug out. So minimize and restore window
        reset.iterate()

    # Takes all those stats from the simulations and just combines them based on player and team IDs
    stats.aggregate_stats()

    # Can save as a CSV with specific path and file name
    stats.send_to_csv(prepend='mlb_', append='_2020-11-22', path='C:/projects/ootp')

if __name__ == '__main__':
    main()
