import asyncio
import pickle
import logging
import json
import willump
from io import BytesIO
import pycurl
from selenium import webdriver
import bs4
import numpy as np
import pandas as pd
import sys
import random
from PySide6 import QtCore, QtWidgets, QtGui

in_champ_select = False
synergies_need_update = False
unpickable_ids = []
teammate_champ = ''

async def update_champ_mapping(wllp):
    available_champs_response = await wllp.request(
        'get', '/lol-champions/v1/owned-champions-minimal')
    available_champs = await available_champs_response.json()
    mapping_champ_to_id = {}
    for champ in available_champs:
        mapping_champ_to_id[champ['name']] = champ['id']
    with open('mapping_champ_to_id.pkl', 'wb') as file:
        pickle.dump(mapping_champ_to_id, file)
    logging.debug('Champ mapping updated')

def update_synergies_opgg():
    with open('mapping_champ_to_id.pkl', 'rb') as file:
        mapping_champ_to_id = pickle.load(file)
    synergy_list = []
    index_list = []
    for champ_name in mapping_champ_to_id.keys():
        logging.info(f'Getting synergies for {champ_name}')
        synergy_list.append(get_synergies_opgg(champ_name))
        logging.info(f'Got synergies for {champ_name}')
        index_list.append(champ_name)
    logging.info('Getting overall winrates')
    index_list.append('')
    synergy_list.append(get_overall_opgg())
    logging.info('Got overall winrates')
    synergy_df = pd.DataFrame(synergy_list, index=index_list).T
    # synergy_df[''] = get_overall_opgg()[0:synergy_df.shape[0]]
    with open('arena_champs_ranking.pkl', 'wb') as file:
        pickle.dump(synergy_df, file)

def get_synergies_opgg(champ_name):
    url_name = champ_name.replace(' ', '').replace('.', '').replace("'", '').lower()
    if champ_name == 'Nunu & Willump':
        url_name = 'nunu'
    elif champ_name == 'Wukong':
        url_name = 'monkeyking'
    elif champ_name == 'Renata Glasc':
        url_name = 'renata'
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL,
             f"https://www.op.gg/modes/arena/{url_name}/synergies?patch=15.07&region=global")
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()
    body = buffer.getvalue()
    soup = bs4.BeautifulSoup(body, 'html.parser')
    synergy_table = soup.find(
        'div', string=f'Synergies').find_next('table')
    champ_infos = synergy_table.find_next('tbody').find_all('td')
    champ_info_list = []
    for td in champ_infos:
        champ_info_list.append(td.text)
    champ_info_df = pd.DataFrame(
        np.array(champ_info_list).reshape(-1, 5),
        columns=[
            'Champion', 'Average Place', 'First Rate', 'Pick Rate', 'Win Rate'
        ]).sort_values(by='First Rate', ascending=False, key=series_str_percent_int)
    return champ_info_df['Champion'].values

def get_overall_opgg():
    url = 'https://www.op.gg/modes/arena'
    # buffer = BytesIO()
    # c = pycurl.Curl()
    # c.setopt(
    #     c.URL,
    #     url)
    # c.setopt(c.WRITEDATA, buffer)
    # c.perform()
    # c.close()
    # body = buffer.getvalue()
    driver = webdriver.Edge()
    driver.get(url)
    html_content = driver.page_source
    soup = bs4.BeautifulSoup(html_content, 'html.parser')
    driver.quit()
    champion_table = soup.find('th', string='Rank').find_parent('table')
    champ_infos = champion_table.find_next('tbody').find_all('tr')
    champ_info_list = []
    for tr in champ_infos:
        strong = tr.find('strong')
        if strong is None:
            continue
        champ_name = strong.text
        win_rate = tr.find_all('td')[-2].text
        champ_info_list.append([champ_name, win_rate])
    champ_info_df = pd.DataFrame(champ_info_list, columns=['Champion', 'Win Rate']
                                 ).sort_values(
        by='Win Rate', ascending=False, key=series_str_percent_int)['Champion'].values
    return champ_info_df

def series_str_percent_int(series):
    """Helper func for sorting,
    turns series of percent strings in representative ints"""
    rep_list = []
    for string in series:
        rep_int = int(float(string.strip('%'))*100)
        rep_list.append(rep_int)
    return pd.Series(rep_list)

async def update_completions(wllp):
    challenges_response = await wllp.request('get', '/lol-challenges/v1/challenges/local-player')
    challenges_json = await challenges_response.json()
    with open('Situations_Adapted_To.pkl', 'wb') as file:
        pickle.dump(challenges_json['602002']['completedIds'], file)
    logging.info('Completions updated')

async def champ_select_loop(wllp):
    global synergies_need_update
    everything_subscription = await wllp.subscribe(
        'OnJsonApiEvent', default_handler=None)
    everything_subscription.filter_endpoint(
        '/lol-champ-select/v1/session', handler=session_handler)
    everything_subscription.filter_endpoint(
        '/lol-champ-select/v1/summoners/', handler=summoner_handler)
    while not in_champ_select:
        logging.debug('Waiting for champ select session to start')
        await asyncio.sleep(1)
    print('Champ select session started')
    pickable_ids_response = await wllp.request(
        'get', '/lol-lobby-team-builder/champ-select/v1/pickable-champion-ids')
    pickable_ids = await pickable_ids_response.json()
    anvils_response = await wllp.request(
        'get', '/lol-lobby-team-builder/champ-select/v1/crowd-favorte-champion-list')
    anvil_ids = await anvils_response.json()
    while in_champ_select:
        if synergies_need_update:
            show_synergies(pickable_ids, anvil_ids)
            synergies_need_update = False
        await asyncio.sleep(1)
    print('Champ select session ended')

async def session_handler(msg):
    global in_champ_select
    if msg['eventType'] == 'Create' or msg['eventType'] == 'Update':
        in_champ_select = True
    else:
        in_champ_select = False

async def summoner_handler(msg):
    global teammate_champ
    global unpickable_ids
    global synergies_need_update
    if msg['data']['isSelf']:
        return
    if msg['data']['nameVisibilityType'] == 'VISIBLE':
        teammate_champ = msg['data']['championName']
        synergies_need_update = True
    if msg['data']['championId'] not in unpickable_ids:
        unpickable_ids.append(msg['data']['championId'])
        synergies_need_update = True
    if msg['data']['banIntentChampionId'] not in unpickable_ids:
        unpickable_ids.append(msg['data']['banIntentChampionId'])
        synergies_need_update = True

def show_synergies(pickable_ids, anvil_ids):
    print(f'Teammate champ: {teammate_champ}')
    with open('mapping_champ_to_id.pkl', 'rb') as file:
        mapping_champ_to_id = pickle.load(file)
    with open('arena_champs_ranking.pkl', 'rb') as file:
        arena_champs_ranking = pickle.load(file)
    with open('Situations_Adapted_To.pkl', 'rb') as file:
        completed_ids = pickle.load(file)
    anvil_synergies = []
    best_playable_synergies = []
    for champ in arena_champs_ranking[teammate_champ]:
        if champ is None:
            continue
        champ_id = mapping_champ_to_id[champ]
        if champ_id in unpickable_ids or champ_id in completed_ids or champ_id not in pickable_ids:
            continue
        if champ_id in anvil_ids:
            anvil_synergies.append(champ)
        best_playable_synergies.append(champ)
    if len(best_playable_synergies) == 0:
        logging.debug('No playable synergies found')
        for champ in arena_champs_ranking['']:
            if champ is None:
                continue
            champ_id = mapping_champ_to_id[champ]
            if champ_id not in completed_ids and champ_id in pickable_ids:
                best_playable_synergies.append(champ)
    if len(anvil_synergies) == 0:
        print('No anvil synergies found')
    else:
        print(f'Anvil synergies:')
        print(*anvil_synergies, sep='\n')
    print(f'Best playable synergies:')
    print(*best_playable_synergies[:5], sep='\n')
    print('')

# class MainWindow(QtWidgets.QMenu):

async def main():
    # TODO clean(willump fork: msg size, logging) , gui
    # logging.basicConfig(level=logging.INFO)
    # update_synergies_opgg()
    wllp = await willump.start()
    try:
        # await update_champ_mapping(wllp)
        while True:
            await update_completions(wllp)
            await champ_select_loop(wllp)
        pass
    finally:
        await wllp.close()

if __name__ == "__main__":
    asyncio.run(main())
